"""Unchanged portable archives hit the cache before any record materialization."""
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
import sqlite3
from hashlib import sha256

import pytest

from core.mod_builds import ModBuildError
from plugins.ds1 import composition_cache,mod_loader,record_edits
from test_ds1_editor_failure_boundaries import event_fixture


@pytest.fixture
def inputs(tmp_path,monkeypatch):
    monkeypatch.setattr(mod_loader,'_compose_cache',OrderedDict())
    monkeypatch.setattr(mod_loader,'_compose_cache_bytes',0)
    emevd,base,call = event_fixture()
    paths = [Path('event/first.emevd'),Path('event/second.emevd')]
    def variant(identity):
        return replace(base,events=(*base.events,emevd.Event(identity,(call(identity,identity),))))
    original = emevd.write(base)
    for relative in paths:
        path = tmp_path/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(original)
    edits = {relative:record_edits.create(relative,original,emevd.write(variant(index+1001)))
             for index,relative in enumerate(paths)}
    mod = mod_loader.Mod('Example',tmp_path/'mod',{},edits)
    calls = []
    materialize = record_edits.materialize
    def counted(relative,*args):
        calls.append(relative)
        return materialize(relative,*args)
    monkeypatch.setattr(record_edits,'materialize',counted)
    return tmp_path,mod,paths,calls,emevd,base,variant


def test_memory_and_disk_hits_skip_portable_materialization(inputs,monkeypatch):
    root,mod,paths,calls,_emevd,_base,_variant = inputs
    expected = mod_loader.compose_installed(root,[mod],cache_root=root/'cache')
    assert calls == paths
    assert mod_loader.compose_installed(root,[mod],cache_root=root/'cache') == expected
    assert calls == paths
    mod_loader._compose_cache.clear()
    monkeypatch.setattr(mod_loader,'_compose_cache_bytes',0)
    assert mod_loader.compose_installed(root,[mod],cache_root=root/'cache') == expected
    assert calls == paths
    # JSON dictionary insertion order is not a semantic source change.
    mod.edits = {path:dict(reversed(list(spec.items()))) for path,spec in mod.edits.items()}
    assert mod_loader.compose_installed(root,[mod],cache_root=root/'cache') == expected
    assert calls == paths


def test_only_the_changed_record_archive_is_rebuilt(inputs):
    root,mod,paths,calls,emevd,base,variant = inputs
    initial = mod_loader.compose_installed(root,[mod],cache_root=root/'cache')
    mod.edits[paths[0]] = record_edits.create(paths[0],emevd.write(base),emevd.write(variant(1003)))
    result = mod_loader.compose_installed(root,[mod],cache_root=root/'cache')
    assert calls == paths+[paths[0]]
    assert result.files[paths[1]] == initial.files[paths[1]]
    assert {event.id for event in emevd.read(result.files[paths[0]]).events} == {0,100,1003}


def test_changed_installed_baseline_misses_cache_and_preserves_foreign_events(inputs):
    root,mod,paths,calls,emevd,_base,variant = inputs
    mod_loader.compose_installed(root,[mod],cache_root=root/'cache')
    (root/paths[0]).write_bytes(emevd.write(variant(1004)))
    result = mod_loader.compose_installed(root,[mod],cache_root=root/'cache')
    assert calls == paths+[paths[0]]
    assert {event.id for event in emevd.read(result.files[paths[0]]).events} == {0,100,1001,1004}


def test_invalid_cache_falls_back_to_verified_records(inputs,monkeypatch):
    root,mod,paths,calls,_emevd,_base,_variant = inputs
    monkeypatch.setattr(composition_cache,'load',lambda *_args:b'bad json\nbad data')
    result = mod_loader.compose_installed(root,[mod],cache_root=root/'cache')
    assert set(result.files) == set(paths) and calls == paths


def test_duplicate_fact_cannot_bypass_validation_through_a_cache_hit(inputs):
    root,mod,paths,_calls,_emevd,_base,_variant = inputs
    mod_loader.compose_installed(root,[mod],cache_root=root/'cache')
    mod.files[paths[0]] = b'duplicate raw file'
    with pytest.raises(ModBuildError,match='duplicate archive and record'):
        mod_loader.compose_installed(root,[mod],cache_root=root/'cache')


def test_cache_retains_a_full_real_library_sized_scan(tmp_path):
    # The measured library touches 93 unique targets. Replaying that scan
    # must retain every small result instead of thrashing a 64-entry cache.
    expected = {index.to_bytes(4,'little'):f'archive {index}'.encode() for index in range(93)}
    for key,value in expected.items():
        composition_cache.store(tmp_path,key,value)
    for _repeat in range(2):
        assert {key:composition_cache.load(tmp_path,key) for key in expected} == expected


def test_recent_cache_hits_do_not_rewrite_the_database_but_older_hits_refresh_recency(tmp_path, monkeypatch):
    clock = [100 * composition_cache._TOUCH_INTERVAL_NS]
    monkeypatch.setattr(composition_cache.time, 'time_ns', lambda: clock[0])
    composition_cache.store(tmp_path, b'key', b'archive')
    path = tmp_path / composition_cache.CACHE_FILE
    def touched():
        with sqlite3.connect(path) as database:
            return database.execute('SELECT touched FROM outputs WHERE key=?', (b'key',)).fetchone()[0]
    before = path.read_bytes()
    clock[0] += 1
    assert composition_cache.load(tmp_path, b'key') == b'archive'
    assert path.read_bytes() == before
    clock[0] += composition_cache._TOUCH_INTERVAL_NS
    assert composition_cache.load(tmp_path, b'key') == b'archive'
    assert touched() == clock[0]
    # A backwards wall-clock adjustment must not leave a future timestamp
    # protecting one archive from eviction indefinitely.
    clock[0] -= 2 * composition_cache._TOUCH_INTERVAL_NS
    assert composition_cache.load(tmp_path, b'key') == b'archive'
    assert touched() == clock[0]


def test_editor_and_packaged_engine_share_semantic_cache_revision(tmp_path,monkeypatch):
    from plugins.ds1 import formats
    first,second = tmp_path/'editor',tmp_path/'game engine'
    for root in (first,second):
        for relative,content in [('plugins/ds1/mod_loader.py','same composer'),
                                 ('plugins/ds3/formats.py','same reader'),
                                 ('plugins/ds1/metadata/table.json','same schema')]:
            path = root/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content)
    def revision(root):
        monkeypatch.setattr(mod_loader,'__file__',str(root/'plugins/ds1/mod_loader.py'))
        monkeypatch.setattr(formats,'METADATA',root/'plugins/ds1/metadata')
        mod_loader._composition_revision.cache_clear()
        return mod_loader._composition_revision()
    try:
        expected = revision(first)
        assert revision(second) == expected
        (second/'plugins/ds1/mod_usage.py').write_text('changed Files usage reporting')
        assert revision(second) == expected
        (second/'plugins/ds1/runtime_package.py').write_text('changed release packaging')
        assert revision(second) == expected
        for source in ('viewport.py','flver.py'):
            (second/'plugins/ds1'/source).write_text('changed read-only model preview')
            assert revision(second) == expected
        (second/'plugins/ds1/mod_loader.py').write_text('changed composer')
        assert revision(second) != expected
    finally:
        mod_loader._composition_revision.cache_clear()


def test_menu_codec_changes_preserve_non_menu_archive_cache_identity(monkeypatch):
    original = Path.read_bytes
    changed = {'name': None}
    def read(path):
        raw = original(path)
        return raw+b'\n# changed codec\n' if path.name == changed['name'] else raw
    monkeypatch.setattr(Path, 'read_bytes', read)
    def revisions():
        mod_loader._composition_revision.cache_clear()
        return (mod_loader._composition_revision(), mod_loader._composition_revision(include_menu=False))
    try:
        baseline = revisions()
        for name in ('menu_layout.py','menu_scripts.py','menu_dim.py','texture_packs.py'):
            changed['name'] = name
            current = revisions()
            assert current[0] != baseline[0], name
            assert current[1] == baseline[1], name
        changed['name'] = 'formats.py'
        current = revisions()
        assert current[0] != baseline[0] and current[1] != baseline[1]
    finally:
        mod_loader._composition_revision.cache_clear()


@pytest.mark.parametrize('unrelated_source', ['menu_layout.py', 'viewport.py', 'flver.py'])
def test_non_menu_outputs_survive_unrelated_code_changes_but_not_their_own_codec(inputs, monkeypatch, unrelated_source):
    root, mod, _paths, calls, _emevd, _base, _variant = inputs
    cache = root/'cache'
    first = mod_loader.compose_installed(root, [mod], cache_root=cache)
    count = len(calls)
    original = Path.read_bytes
    changed = {'name': unrelated_source}
    def read(path):
        raw = original(path)
        return raw+b'\n# changed codec\n' if path.name == changed['name'] else raw
    monkeypatch.setattr(Path, 'read_bytes', read)
    try:
        mod_loader._composition_revision.cache_clear()
        monkeypatch.setattr(mod_loader, '_compose_cache', OrderedDict())
        second = mod_loader.compose_installed(root, [mod], cache_root=cache)
        assert second.files == first.files and len(calls) == count
        changed['name'] = 'emevd.py'
        mod_loader._composition_revision.cache_clear()
        monkeypatch.setattr(mod_loader, '_compose_cache', OrderedDict())
        third = mod_loader.compose_installed(root, [mod], cache_root=cache)
        assert third.files == first.files and len(calls) == count*2
    finally:
        mod_loader._composition_revision.cache_clear()


@pytest.mark.parametrize('damage',['not-a-database','wrong-columns','extra-trigger'])
def test_damaged_disposable_cache_is_rebuilt_without_disabling_mods(tmp_path,damage):
    path = tmp_path/composition_cache.CACHE_FILE
    if damage=='not-a-database':
        path.write_bytes(b'broken cache bytes')
    elif damage=='wrong-columns':
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TABLE outputs (wrong BLOB)')
        connection.close()
    else:
        composition_cache.store(tmp_path,b'old',b'old output')
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TRIGGER broken AFTER INSERT ON outputs BEGIN SELECT 1; END')
        connection.close()
    assert composition_cache.load(tmp_path,b'old') is None
    composition_cache.store(tmp_path,b'healthy',b'healthy output')
    assert composition_cache.load(tmp_path,b'healthy') == b'healthy output'


def test_oversized_cache_is_discarded_before_sqlite_reads_it(tmp_path,monkeypatch):
    monkeypatch.setattr(composition_cache,'LIMIT',64)
    # The table, primary key, LRU index and incremental-vacuum metadata need
    # more than four SQLite pages even for a one-byte archive.
    overhead = 6*4096
    monkeypatch.setattr(composition_cache,'_DATABASE_OVERHEAD',overhead)
    (tmp_path/composition_cache.CACHE_FILE).write_bytes(b'not sqlite'+bytes(32768))
    composition_cache.store(tmp_path,b'key',b'value')
    assert composition_cache.load(tmp_path,b'key') == b'value'
    assert (tmp_path/composition_cache.CACHE_FILE).stat().st_size <= 64+overhead


def test_busy_cache_is_not_mistaken_for_corruption(tmp_path):
    composition_cache.store(tmp_path,b'old',b'old output')
    with sqlite3.connect(tmp_path/composition_cache.CACHE_FILE) as connection:
        connection.execute('BEGIN EXCLUSIVE')
        composition_cache.store(tmp_path,b'new',b'new output')
    connection.close()
    assert composition_cache.load(tmp_path,b'old') == b'old output'


def test_large_cache_entry_evicts_only_the_oldest_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(composition_cache, 'LIMIT', 4096)
    monkeypatch.setattr(composition_cache, '_DATABASE_OVERHEAD', 32768)
    for number in range(64):
        composition_cache.store(tmp_path, str(number).encode(), bytes([number])*48)
    composition_cache.store(tmp_path, b'large', b'new'*800)
    assert composition_cache.load(tmp_path, b'large') == b'new'*800
    assert composition_cache.load(tmp_path, b'0') is None
    assert composition_cache.load(tmp_path, b'63') == bytes([63])*48
    with sqlite3.connect(tmp_path/composition_cache.CACHE_FILE) as connection:
        count, size = connection.execute('SELECT count(*),sum(length(data)) FROM outputs').fetchone()
    connection.close()
    assert count == 36 and size <= 4096


def test_eviction_index_avoids_scanning_archive_blob_rows(tmp_path):
    composition_cache.store(tmp_path, b'one', b'archive')
    with composition_cache._database(tmp_path) as connection:
        plan = connection.execute('EXPLAIN QUERY PLAN SELECT rowid,length(data) FROM outputs ORDER BY touched LIMIT 513').fetchall()
    assert any('outputs_lru' in row[-1] for row in plan), plan
    assert not any('TEMP B-TREE' in row[-1] for row in plan), plan


def previous_cache(root):
    path = root/'composed.sqlite3'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE outputs (key BLOB PRIMARY KEY,data BLOB,checksum BLOB,touched INTEGER)')
        connection.execute('INSERT INTO outputs VALUES (?,?,?,?)',
                           (b'previous', b'compiled archive', sha256(b'compiled archive').digest(), 1))
    connection.close()
    return path


def test_schema_upgrade_reuses_outputs_without_changing_the_older_hosts_cache(tmp_path):
    previous = previous_cache(tmp_path)
    original = previous.read_bytes()
    assert composition_cache.load(tmp_path, b'previous') == b'compiled archive'
    assert previous.read_bytes() == original
    assert (tmp_path/composition_cache.CACHE_FILE).is_file()
    assert not (tmp_path/('.'+composition_cache.CACHE_FILE+'.migrate')).exists()
    # A new write has a separate schema, rather than teaching an older
    # running host to accept a cache it would otherwise delete as corrupt.
    composition_cache.store(tmp_path, b'new', b'new archive')
    assert previous.read_bytes() == original


def test_damaged_previous_cache_cannot_prevent_new_outputs(tmp_path):
    previous = tmp_path/'composed.sqlite3'
    previous.write_bytes(b'broken legacy cache')
    composition_cache.store(tmp_path, b'new', b'valid archive')
    assert composition_cache.load(tmp_path, b'new') == b'valid archive'
    assert previous.read_bytes() == b'broken legacy cache'


def test_locked_previous_cache_does_not_block_the_current_cache(tmp_path):
    previous = previous_cache(tmp_path)
    connection = sqlite3.connect(previous)
    try:
        connection.execute('BEGIN EXCLUSIVE')
        composition_cache.store(tmp_path, b'new', b'valid archive')
        assert composition_cache.load(tmp_path, b'new') == b'valid archive'
    finally:
        connection.close()


def test_previous_cache_copy_has_a_deadline_and_removes_its_partial_file(tmp_path, monkeypatch):
    previous = previous_cache(tmp_path)
    original = previous.read_bytes()
    readings = iter((0., 3.))
    monkeypatch.setattr(composition_cache.time, 'monotonic', lambda: next(readings))
    assert composition_cache.load(tmp_path, b'previous') is None
    assert previous.read_bytes() == original
    assert not (tmp_path/('.'+composition_cache.CACHE_FILE+'.migrate')).exists()
    composition_cache.store(tmp_path, b'new', b'valid archive')
    assert composition_cache.load(tmp_path, b'new') == b'valid archive'


def test_excess_cache_entry_count_is_discarded_without_an_unbounded_eviction_loop(tmp_path, monkeypatch):
    composition_cache.store(tmp_path, b'initial', b'output')
    monkeypatch.setattr(composition_cache, 'ENTRIES', 3)
    with sqlite3.connect(tmp_path/composition_cache.CACHE_FILE) as connection:
        connection.executemany('INSERT INTO outputs VALUES (?,?,?,?)',
                              [(str(n).encode(), b'output', b'checksum', n) for n in range(5)])
    connection.close()
    composition_cache.store(tmp_path, b'first', b'valid output')
    composition_cache.store(tmp_path, b'next', b'valid output')
    assert composition_cache.load(tmp_path, b'next') == b'valid output'


def test_eviction_reuses_pages_with_a_physical_disk_cap(tmp_path,monkeypatch):
    monkeypatch.setattr(composition_cache,'LIMIT',32*1024)
    monkeypatch.setattr(composition_cache,'_DATABASE_OVERHEAD',16*1024)
    # Exercise migration from the old full-vacuum database as well as repeated
    # bounded evictions. Payloads differ so no content reuse can hide writes.
    path=tmp_path/composition_cache.CACHE_FILE
    with sqlite3.connect(path) as database:
        database.execute('PRAGMA auto_vacuum = FULL')
        database.execute('CREATE TABLE outputs (key BLOB PRIMARY KEY, data BLOB, checksum BLOB, touched INTEGER)')
    database.close()
    for index in range(24):
        key=str(index).encode()
        payload=bytes([index])*12*1024
        composition_cache.store(tmp_path,key,payload)
        assert composition_cache.load(tmp_path,key)==payload
        assert path.stat().st_size<=48*1024
    with composition_cache._database(tmp_path) as database:
        assert database.execute('PRAGMA auto_vacuum').fetchone()[0]==2
        assert database.execute('SELECT sum(length(data)) FROM outputs').fetchone()[0]<=32*1024
        assert database.execute('PRAGMA max_page_count').fetchone()[0]*database.execute('PRAGMA page_size').fetchone()[0]<=48*1024


@pytest.mark.parametrize('failure', ['update-full', 'update-locked', 'commit'])
@pytest.mark.parametrize('corrupt', [False, True])
def test_optional_recency_failure_keeps_only_checksum_verified_bytes(tmp_path, monkeypatch, failure, corrupt):
    from contextlib import contextmanager
    payload = b'verified compiled archive'
    composition_cache.store(tmp_path, b'key', payload)
    database = composition_cache._database
    with database(tmp_path) as connection:
        connection.execute('UPDATE outputs SET touched=0')
        if corrupt:
            connection.execute('UPDATE outputs SET checksum=?', (b'wrong checksum',))
    class FailRecency:
        def __init__(self, connection):
            self.connection = connection
        def execute(self, sql, parameters=()):
            if sql.startswith('UPDATE outputs SET touched') and failure.startswith('update-'):
                reason = 'database or disk is full' if failure == 'update-full' else 'database is locked'
                raise sqlite3.OperationalError(reason)
            return self.connection.execute(sql, parameters)
    @contextmanager
    def failing_database(root):
        with database(root) as connection:
            yield FailRecency(connection)
            if failure == 'commit':
                raise sqlite3.OperationalError('optional recency commit failed')
    monkeypatch.setattr(composition_cache, '_database', failing_database)
    assert composition_cache.load(tmp_path, b'key') == (None if corrupt else payload)
