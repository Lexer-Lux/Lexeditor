"""Unchanged portable archives hit the cache before any record materialization."""
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
import sqlite3

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
        (second/'plugins/ds1/mod_loader.py').write_text('changed composer')
        assert revision(second) != expected
    finally:
        mod_loader._composition_revision.cache_clear()


@pytest.mark.parametrize('damage',['not-a-database','wrong-columns','extra-trigger'])
def test_damaged_disposable_cache_is_rebuilt_without_disabling_mods(tmp_path,damage):
    path = tmp_path/'composed.sqlite3'
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
    monkeypatch.setattr(composition_cache,'_DATABASE_OVERHEAD',16384)
    (tmp_path/'composed.sqlite3').write_bytes(b'not sqlite'+bytes(32768))
    composition_cache.store(tmp_path,b'key',b'value')
    assert composition_cache.load(tmp_path,b'key') == b'value'
    assert (tmp_path/'composed.sqlite3').stat().st_size <= 64+16384


def test_busy_cache_is_not_mistaken_for_corruption(tmp_path):
    composition_cache.store(tmp_path,b'old',b'old output')
    with sqlite3.connect(tmp_path/'composed.sqlite3') as connection:
        connection.execute('BEGIN EXCLUSIVE')
        composition_cache.store(tmp_path,b'new',b'new output')
    connection.close()
    assert composition_cache.load(tmp_path,b'old') == b'old output'
