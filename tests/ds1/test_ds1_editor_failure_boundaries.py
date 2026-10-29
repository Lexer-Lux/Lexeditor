"""Failure containment across the shared builder, DS1 Save, and Records layout."""
import sys
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/shared'))
sys.path.insert(0, str(ROOT / 'tests/ds1'))
from test_shared_ui_feedback import page  # noqa: E402,F401
from test_mods_tab import mount, _detail_tabs, STRIP  # noqa: E402
from core import script_mods, mod_builds, mod_requires  # noqa: E402
from plugins.ds1 import tweak_mods, mod_loader, composition_cache, script_worker  # noqa: E402
from plugins.ds1.mod_support import Ds1ModAdapter  # noqa: E402
from test_ds1_tweak_save_rebuild import game  # noqa: E402,F401


def make_script(library, name='Healthy', source=None, **metadata):
    root = library / name
    (root / 'script').mkdir(parents=True)
    (root / 'script/__init__.py').write_text('', encoding='utf-8')
    (root / 'script/tweak.py').write_text(source or 'def build(settings, context):\n    return {"native/result.txt": b"valid"}\n', encoding='utf-8')
    (root / 'mod.json').write_text(json.dumps({'name': name, 'enabled': True,
                                              'script': {'version': 1}, **metadata}), encoding='utf-8')
    return root


def test_worker_preserves_bytes_and_observed_dependencies(tmp_path):
    root = make_script(tmp_path, source='def build(settings, context):\n    context.enabled("other")\n    return {"native/result.txt": bytes([0, 255])}\n')
    context = tweak_mods.BuildContext({}, library_root=tmp_path)
    result = script_mods.build(root, context, allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert result['written'] == ['native/result.txt']
    assert (root / 'native/result.txt').read_bytes() == bytes([0, 255])
    assert 'other' in context._inputs['enabled']


@pytest.mark.parametrize('source', [
    'raise SystemExit(7)',
    'import os\nos._exit(9)',
    'def build(settings, context):\n    raise TypeError("broken mod")',
    'def build(settings, context):\n    return {"native/bad": object()}',
])
def test_worker_failure_disables_only_owner_and_dependent(tmp_path, source):
    healthy = make_script(tmp_path)
    broken = make_script(tmp_path, 'Broken', source)
    dependent = make_script(tmp_path, 'Dependent', requires=['Broken'])
    class Adapter:
        def activate(self, active, game):
            rows = [script_mods.catalog_row(folder) for folder in active]
            script_mods.build_batch(rows, tweak_mods.BuildContext({row['id']: Path(row['path']) for row in rows}),
                                   allowed_roots=tweak_mods.ALLOWED_ROOTS, error=tweak_mods.TweakError)
            return {'activated': [path.name for path in active]}
    result = mod_builds.activate_with_recovery(Adapter(), [healthy, broken, dependent], tmp_path)
    assert result['activated'] == ['Healthy']
    assert {row['folder'] for row in result['disabledMods']} == {'Broken', 'Dependent'}
    assert json.loads((healthy / 'mod.json').read_text())['enabled'] is True
    assert (healthy / 'native/result.txt').read_bytes() == b'valid'
    assert not (broken / script_mods.MANIFEST_FILE).exists()


def test_hanging_worker_is_terminated_without_writing(tmp_path, monkeypatch):
    root = make_script(tmp_path, source='import time\ntime.sleep(30)')
    monkeypatch.setattr(script_worker, 'BUILD_TIMEOUT', .5)
    with pytest.raises(script_mods.ScriptModError, match='did not finish'):
        script_mods.build(root, tweak_mods.BuildContext({}), allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert not (root / script_mods.MANIFEST_FILE).exists()


def test_dependency_import_failure_keeps_its_owner_across_worker_boundary(tmp_path):
    dependency = make_script(tmp_path, 'Dependency')
    (dependency / 'script/helper.py').write_text('raise SystemExit("bad dependency")', encoding='utf-8')
    caller = make_script(tmp_path, 'Caller', 'def build(settings, context):\n    context.module("Dependency", "helper")\n    return {}')
    context = tweak_mods.BuildContext({'Dependency': dependency, 'Caller': caller})
    with pytest.raises(tweak_mods.TweakError) as caught:
        script_mods.build_batch([script_mods.catalog_row(caller)], context,
                               allowed_roots=tweak_mods.ALLOWED_ROOTS, error=tweak_mods.TweakError)
    assert caught.value.folders == (dependency.resolve(),)


def test_game_input_failure_does_not_blame_requesting_script(tmp_path):
    game_root = tmp_path / 'game'
    source = game_root / mod_loader.RELATIVE
    source.parent.mkdir(parents=True)
    source.write_bytes(b'broken vanilla')
    root = make_script(tmp_path / 'library', source='def build(settings, context):\n    context.game_params()\n    return {}')
    context = tweak_mods.BuildContext({}, game_root, tmp_path / 'library')
    with pytest.raises(tweak_mods.TweakError) as caught:
        script_mods.build_batch([script_mods.catalog_row(root)], context,
                               allowed_roots=tweak_mods.ALLOWED_ROOTS, error=tweak_mods.TweakError)
    assert not caught.value.folders


def test_worker_start_failure_does_not_disable_mod(tmp_path, monkeypatch):
    root = make_script(tmp_path)
    def unavailable(*args, **kwargs):
        raise OSError('worker unavailable')
    monkeypatch.setattr(script_worker.subprocess, 'Popen', unavailable)
    with pytest.raises(tweak_mods.TweakError) as caught:
        script_mods.build_batch([script_mods.catalog_row(root)], tweak_mods.BuildContext({}),
                               allowed_roots=tweak_mods.ALLOWED_ROOTS, error=tweak_mods.TweakError)
    assert not caught.value.folders
    assert json.loads((root / 'mod.json').read_text())['enabled'] is True


@pytest.mark.parametrize('phase', ['cached_build', 'build_record'])
def test_optional_script_cache_failure_still_builds(tmp_path, phase):
    root = make_script(tmp_path)
    class Context:
        def cached_build(self, *args):
            if phase == 'cached_build':
                raise TypeError('bad cache')
            return False
        def build_record(self, *args):
            raise AttributeError('bad cache record')
    script_mods.build(root, Context(), allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert (root / 'native/result.txt').read_bytes() == b'valid'
    assert 'build' not in json.loads((root / script_mods.MANIFEST_FILE).read_text())


def test_discovery_keeps_healthy_rows_with_bad_metadata_order_and_duplicate_ids(tmp_path):
    make_script(tmp_path)
    bad = make_script(tmp_path, 'Corrupt')
    (bad / 'mod.json').write_text('{broken', encoding='utf-8')
    make_script(tmp_path, 'BadOrder', order=[])
    make_script(tmp_path, 'DupeOne', id='duplicate')
    make_script(tmp_path, 'DupeTwo', id='duplicate')
    rows = {row['name']: row for row in tweak_mods.tweak_rows(tmp_path)}
    assert not rows['Healthy']['error']
    assert rows['BadOrder']['error']
    assert rows['DupeOne']['error'] and rows['DupeTwo']['error']


def test_missing_requirement_is_attributed_before_build(tmp_path):
    root = make_script(tmp_path, requires=['missing'])
    with pytest.raises(mod_builds.ModBuildError) as caught:
        mod_requires.check_enabled(tmp_path)
    assert caught.value.folders == (root.resolve(),)


def test_disabled_alias_cannot_block_healthy_enabled_mod_with_same_id(tmp_path):
    make_script(tmp_path, 'A_disabled', id='shared', enabled=False, requires=['missing'])
    make_script(tmp_path, 'Healthy', id='shared')
    make_script(tmp_path, 'Dependent', requires=['shared'])
    mod_requires.check_enabled(tmp_path)
    rows = tweak_mods.tweak_rows(tmp_path)
    assert not any(row['error'] for row in rows)


def test_recovery_keeps_dependents_when_a_healthy_alias_provides_the_requirement(tmp_path):
    bad = make_script(tmp_path, 'Broken', id='shared')
    healthy = make_script(tmp_path, 'Healthy', id='shared')
    dependent = make_script(tmp_path, 'Dependent', requires=['shared'])
    class Adapter:
        def activate(self, active, game):
            if bad.resolve() in active:
                raise mod_builds.ModBuildError([bad], 'bad alias')
            return {'activated': [root.name for root in active]}
    result = mod_builds.activate_with_recovery(Adapter(), [bad, healthy, dependent], tmp_path)
    assert result['activated'] == ['Healthy', 'Dependent']
    assert [row['folder'] for row in result['disabledMods']] == ['Broken']


@pytest.mark.parametrize('payload', [b'[]\nwrong', b'{"hasData":true,"conflicts":null}\nwrong',
                                       b'{"hasData":"yes","conflicts":[]}\nwrong',
                                       b'{"hasData":true,"conflicts":[["wrong","part",[1]]]}\nwrong'])
def test_malformed_composition_cache_is_a_miss(tmp_path, monkeypatch, payload):
    relative = Path('opaque.bin')
    mod = mod_loader.Mod('Healthy', tmp_path, {relative: b'new'})
    monkeypatch.setattr(mod_loader, '_compose_cache', {})
    monkeypatch.setattr(composition_cache, 'load', lambda *args: payload)
    monkeypatch.setattr(composition_cache, 'store', lambda *args: None)
    result = mod_loader._compose_file(relative, None, [mod], False, tmp_path)
    assert result.files[relative] == b'new'


def test_cache_write_failure_does_not_fail_composition(tmp_path, monkeypatch):
    relative = Path('opaque.bin')
    monkeypatch.setattr(mod_loader, '_compose_cache', {})
    monkeypatch.setattr(composition_cache, 'load', lambda *args: None)
    def fail(*args):
        raise TypeError('bad cache')
    monkeypatch.setattr(composition_cache, 'store', fail)
    result = mod_loader._compose_file(relative, None, [mod_loader.Mod('Healthy', tmp_path, {relative: b'new'})], False, tmp_path)
    assert result.files[relative] == b'new'


def test_valid_cached_conflict_report_keeps_peer_names(tmp_path, monkeypatch):
    from collections import OrderedDict
    relative = Path('opaque.bin')
    monkeypatch.setattr(mod_loader, '_compose_cache', OrderedDict())
    payload = json.dumps({'hasData': True, 'conflicts': [[str(relative), 'field', ['A', 'B']]]}).encode() + b'\nnew'
    monkeypatch.setattr(composition_cache, 'load', lambda *args: payload)
    result = mod_loader._compose_file(relative, None,
        [mod_loader.Mod('A', tmp_path, {relative: b'input'})], False, tmp_path)
    assert result.files[relative] == b'new'
    assert result.conflicts[0].mods == ['A', 'B']


def test_combined_parameter_reads_reuse_archive_cache_and_skip_other_assets(tmp_path, monkeypatch):
    from collections import OrderedDict
    from ds1_fixture import make_archive
    from plugins.ds1.formats import ItemDocument
    game_root, library = tmp_path / 'game', tmp_path / 'library'
    source = make_archive()
    live = game_root / mod_loader.RELATIVE
    live.parent.mkdir(parents=True)
    live.write_bytes(source)
    data = library / 'Data'
    (data / mod_loader.RELATIVE).parent.mkdir(parents=True)
    (data / mod_loader.MARKER).touch()
    (data / 'mod.json').write_text(json.dumps({'name':'Parameter cache fixture', 'enabled':True}), encoding='utf-8')
    output = data / mod_loader.RELATIVE
    output.write_bytes(source)
    unrelated = data / 'script/talk/unused.talkesdbnd.dcx'
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b'not needed for a parameter lookup')
    read = Path.read_bytes
    def checked_read(path):
        assert path != unrelated, 'Parameter lookup read an unrelated archive'
        return read(path)
    monkeypatch.setattr(Path, 'read_bytes', checked_read)
    monkeypatch.setattr(mod_loader, '_compose_cache', OrderedDict())
    monkeypatch.setattr(mod_loader, '_compose_cache_bytes', 0)
    compose = mod_loader._compose_params
    calls = []
    def counted(*args, **kwargs):
        calls.append(True)
        return compose(*args, **kwargs)
    monkeypatch.setattr(mod_loader, '_compose_params', counted)
    def context():
        return tweak_mods.BuildContext({}, game_root, library, cache_root=tmp_path / 'cache')
    assert context().game_params() == source
    assert context().game_params() == source
    assert len(calls) == 1
    mod_loader._compose_cache.clear()
    monkeypatch.setattr(mod_loader, '_compose_cache_bytes', 0)
    assert context().game_params() == source
    assert len(calls) == 1
    output.write_bytes(make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 17}}}))
    assert ItemDocument(context().game_params()).value('EquipParamGoods', 100, 'basicPrice') == 17
    assert len(calls) == 2


def test_editor_only_source_changes_do_not_invalidate_archive_outputs(monkeypatch):
    mod_loader._composition_revision.cache_clear()
    baseline = mod_loader._composition_revision()
    read = Path.read_bytes
    changed = {'name': 'server.py'}
    def edited(path):
        contents = read(path)
        return contents + b'\n# source edit' if path.parent == Path(mod_loader.__file__).parent and path.name == changed['name'] else contents
    monkeypatch.setattr(Path, 'read_bytes', edited)
    try:
        mod_loader._composition_revision.cache_clear()
        assert mod_loader._composition_revision() == baseline
        changed['name'] = 'mod_loader.py'
        mod_loader._composition_revision.cache_clear()
        assert mod_loader._composition_revision() != baseline
    finally:
        mod_loader._composition_revision.cache_clear()


def test_script_engine_changes_do_not_recompose_unchanged_managed_menu(tmp_path, monkeypatch):
    calls = []
    def compose(*args):
        calls.append(True)
        return b'compiled fixture'
    monkeypatch.setattr(tweak_mods.menu_layout, 'compose', compose)
    monkeypatch.setattr(mod_loader, '_composition_revision', lambda: b'composer-one')
    first = tweak_mods._compose_menu(b'original', [], tweak_mods.LAYOUT, tmp_path)
    monkeypatch.setattr(tweak_mods, '_script_compiler_revision', lambda: 'unrelated script change')
    assert tweak_mods._compose_menu(b'original', [], tweak_mods.LAYOUT, tmp_path) == first
    assert len(calls) == 1
    monkeypatch.setattr(mod_loader, '_composition_revision', lambda: b'composer-two')
    assert tweak_mods._compose_menu(b'original', [], tweak_mods.LAYOUT, tmp_path) == first
    assert len(calls) == 2


def test_saved_and_externally_added_rows_keep_created_origin():
    from ds1_fixture import make_archive
    from plugins.ds1.formats import ItemDocument
    original = make_archive()
    document = ItemDocument(original)
    document.add_rows('EquipParamGoods', [(100, 72350)])
    loaded = ItemDocument(document.export())
    loaded.vanilla_document = ItemDocument(original)
    assert not loaded._added_rows and not loaded.dirty
    rows = {row['id']: row for row in loaded.list_rows('consumables')}
    assert rows[72350]['created'] and rows[72350]['modified']
    assert not rows[100]['created'] and not rows[100]['modified']
    loaded.edit('EquipParamGoods', 100, 'basicPrice', 123)
    assert loaded.row_modified('EquipParamGoods', 100)
    assert not loaded.row_created('EquipParamGoods', 100)


def test_shared_added_and_edited_record_emoji(page, tmp_path):
    from test_shared_ui_feedback import framework
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      document.querySelector('main').append(U.columnList({
        columns:[{key:'name',label:'Name'}],
        rows:[{id:1,name:'Titanite Shard'},
              {id:2,name:'Edited Titanite Shard',modified:true},
              {id:3,name:'Estus Shard',created:true,modified:true}],
        key:row=>row.id,selected:null,select:()=>{}}));
    }''')
    created = page.get_by_role('img', name='Created in this mod', exact=True)
    edited = page.get_by_role('img', name='Changed from vanilla', exact=True)
    assert created.inner_text() == '✒️'
    assert edited.inner_text() == '📝'
    assert 'Segoe UI Emoji' in created.evaluate('(node)=>getComputedStyle(node).fontFamily')
    assert created.count() == edited.count() == 1
    page.screenshot(path=str(tmp_path / 'record-provenance.png'))


def test_layout_lookups_remain_correct_after_insertions_and_moves():
    from plugins.ds1 import menu_layout
    from test_ds1_menu_layout import drb, DIALOGS, snapshot, shape_order
    layout = menu_layout.Drb(drb())
    unchanged = snapshot(layout)
    # Warm every lookup before shifting entries in the first dialog.
    for dialog in layout.dialogs():
        for node in layout.nodes(dialog):
            layout._blob('SHAP', 'SHPR', node.shape)
            layout._blob('CTRL', 'CTPR', node.control)
    for index in range(12):
        layout.add_text('data_simple_arms', f'added_{index}', 'text_param_receive', index, 16,
                        before='text_receive_name')
        layout.move('data_simple_arms', f'added_{index}', [10, 20, 110, 50])
        layout.set_font('data_simple_arms', f'added_{index}', 4)
    again = menu_layout.Drb(layout.to_bytes())
    assert snapshot(again)['list_armor'] == unchanged['list_armor']
    for index in range(12):
        assert again.text('data_simple_arms', f'added_{index}')['rect'] == [10, 20, 110, 50]
    assert shape_order(again) == list(range(0, again.sections['SHAP'][1] * 8, 8))
    assert len(again.nodes('data_simple_arms')) == len(DIALOGS['data_simple_arms']) + 12


def test_linked_library_entry_is_off_without_hiding_healthy_mod(tmp_path):
    from core import mods_service
    library = tmp_path / 'library'
    healthy = make_script(library)
    outside = make_script(tmp_path / 'outside')
    linked = library / 'linked'
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Creating directory links is not available')
    rows = {row['folder']: row for row in mods_service.library_rows(library)}
    assert rows[healthy.name]['enabled']
    assert not rows['linked']['enabled'] and 'symlink' in rows['linked']['error']
    assert [row['name'] for row in tweak_mods.tweak_rows(library)] == ['Healthy']
    mod_requires.check_enabled(library)


def test_report_location_failure_is_optional(tmp_path, monkeypatch):
    def fail():
        raise TypeError('bad cache location')
    monkeypatch.setattr(Ds1ModAdapter, '_report_path', staticmethod(fail))
    adapter = Ds1ModAdapter()
    assert adapter._cache_root() is None
    assert adapter._read_report(tmp_path, []) is None
    adapter._save_report(tmp_path, [], [], installed=True)


@pytest.mark.parametrize('report', [None, {'folder': b'bad'}, {'folder': [b'bad']}, {'folder': ['okay']}])
def test_bad_optional_host_reports_cannot_break_mods_overview(tmp_path, report):
    from core.desktop_host import HostApi
    from types import SimpleNamespace
    result = {'rows': [{'path': str(tmp_path), 'enabled': True}]}
    HostApi._attach_report(result, SimpleNamespace(conflicts=lambda *args: report),
                           [tmp_path], str(tmp_path), 'conflicts', 'conflictError', True)
    if report != {'folder': ['okay']}:
        assert result['conflictError']


def test_host_activation_uses_the_same_recovery_as_save(tmp_path):
    import threading
    from types import SimpleNamespace
    from core.desktop_host import HostApi
    from core.mod_library import relative_path
    library = tmp_path / relative_path('ds1')
    healthy = make_script(library)
    broken = make_script(library, 'Broken')
    seen = []
    class Adapter:
        def activate(self, active, game):
            seen.append(active)
            if broken.resolve() in active:
                raise mod_builds.ModBuildError([broken], 'broken fixture')
            return {}
    host = SimpleNamespace(mod_library_status=lambda _: {'canManage': True, 'root': str(tmp_path)},
        _installations=SimpleNamespace(snapshot=lambda _: {'root': str(tmp_path / 'game')}),
        game_process_status=lambda _: {'running': False}, _mod_adapter=lambda _: Adapter(),
        _mod_library_lock=threading.Lock())
    result = HostApi._activate_mods(host, 'ds1', [str(healthy), str(broken)])
    assert [row['folder'] for row in result['disabledMods']] == ['Broken']
    assert seen[-1] == [healthy.resolve()]


@pytest.mark.parametrize('report', [{'changes': [{'after': b'bad cache'}]}, {'changes': [None]}, None])
def test_bad_record_report_keeps_files_accessible(tmp_path, report):
    from core.desktop_host import HostApi
    from types import SimpleNamespace
    root = make_script(tmp_path)
    host = SimpleNamespace(_game_mods=lambda _: tmp_path,
        _mod_adapter=lambda _: SimpleNamespace(describe_changes=lambda *args: report),
        _installations=SimpleNamespace(snapshot=lambda _: {}))
    result = HostApi.mod_contents(host, 'ds1', str(root))
    assert result['changes'] == [] and result['note']
    assert any(row['relative'] == 'mod.json' for row in result['files'])
    json.dumps(result)


def test_script_corrupting_its_metadata_cannot_stop_healthy_build(tmp_path):
    healthy = make_script(tmp_path)
    bad = make_script(tmp_path, 'Broken')
    class Adapter:
        def activate(self, active, game):
            if bad.resolve() in active:
                (bad / 'mod.json').write_text('{corrupted', encoding='utf-8')
                raise mod_builds.ModBuildError([bad], 'bad script')
            return {'activated': [path.name for path in active]}
    result = mod_builds.activate_with_recovery(Adapter(), [healthy, bad], tmp_path)
    assert result['activated'] == ['Healthy']
    assert result['disabledMods'][0]['name'] == 'Broken'
    assert (bad / 'mod.json').read_text() == '{corrupted'


def test_saved_project_survives_unexpected_deployment_error(tmp_path, monkeypatch):
    from plugins.ds1 import server
    monkeypatch.setattr(server, '_tweaks_flag', lambda: True)
    monkeypatch.setattr(tweak_mods, 'game_closed', lambda: True)
    def fail(*args):
        raise TypeError('bytes cannot serialize')
    monkeypatch.setattr(tweak_mods, 'mods_root', fail)
    result = server._rebuild_tweaks_on_save()
    assert result == {'tweaksNeedRebuild': True, 'tweaksError': 'bytes cannot serialize'}


def test_bad_archive_is_attributed_but_bad_vanilla_is_not(tmp_path, monkeypatch):
    from ds1_fixture import make_archive
    relative = mod_loader.RELATIVE
    vanilla = make_archive()
    good = mod_loader.Mod('Healthy', tmp_path / 'healthy', {relative: vanilla})
    bad = mod_loader.Mod('Broken', tmp_path / 'broken', {relative: b'broken archive'})
    monkeypatch.setattr(mod_loader, 'vanilla_files', lambda *args: {relative: vanilla})
    with pytest.raises(mod_builds.ModBuildError) as caught:
        mod_loader.compose_installed(tmp_path, [good, bad])
    assert caught.value.folders == (bad.folder.resolve(),)
    monkeypatch.setattr(mod_loader, 'vanilla_files', lambda *args: {relative: b'broken original'})
    with pytest.raises(Exception) as caught:
        mod_loader.compose_installed(tmp_path, [good])
    assert not isinstance(caught.value, mod_builds.ModBuildError)


@pytest.mark.parametrize('failure', ['script', 'schema'])
def test_full_activation_recovers_broken_script_and_corrupt_caches(game, tmp_path, monkeypatch, failure):
    from test_ds1_tweak_save_rebuild import enable_loader
    library = tmp_path / 'library'
    healthy = make_script(library)
    broken = make_script(library, 'Broken', 'raise TypeError("fixture failure")')
    if failure == 'schema':
        (broken / 'settings.schema.json').write_text(json.dumps({'fields': [{'key': 'bad', 'type': []}]}), encoding='utf-8')
    dependent = make_script(library, 'Dependent', requires=['Broken'])
    enable_loader(library)
    cache = tmp_path / 'cache'
    cache.mkdir()
    (cache / 'conflicts.json').write_text('{broken', encoding='utf-8')
    (cache / 'composed.sqlite3').write_bytes(b'broken database')
    monkeypatch.setattr(Ds1ModAdapter, '_report_path', staticmethod(lambda: cache / 'conflicts.json'))
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    active = [library / name for name in adapter.active_mod_ids(game)]
    result = mod_builds.activate_with_recovery(adapter, active, game)
    assert {row['folder'] for row in result['disabledMods']} == {'Broken', 'Dependent'}
    assert json.loads((healthy / 'mod.json').read_text())['enabled'] is True
    assert json.loads((broken / 'mod.json').read_text())['enabled'] is False
    assert json.loads((dependent / 'mod.json').read_text())['enabled'] is False
    assert (healthy / 'native/result.txt').read_bytes() == b'valid'
    assert result['timings']['scripts'][0]['mod'] == 'Healthy'
    report = json.loads((cache / 'conflicts.json').read_text('utf-8'))
    assert report['timings'] == result['timings']
    # A fresh adapter can still inspect the library and perform another Save.
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    assert mod_builds.activate_with_recovery(adapter,
        [library / name for name in adapter.active_mod_ids(game)], game)['disabledMods'] == []


def test_failed_rollback_is_reported_and_remaining_files_are_attempted(tmp_path, monkeypatch):
    from types import SimpleNamespace
    managed = SimpleNamespace(label='fixture', live=lambda game: game / 'file')
    monkeypatch.setattr(tweak_mods, '_read', lambda *args: b'after')
    restored = []
    def write(*args, **kwargs):
        restored.append('file')
    def fail(*args, **kwargs):
        restored.append('runtime')
        raise OSError('rollback disk failure')
    monkeypatch.setattr(tweak_mods, '_write', write)
    monkeypatch.setattr(tweak_mods, '_write_runtime', fail)
    done = [{'managed': managed, 'before': b'before', 'after': b'after', 'previous': {}},
            {'managed': None, 'previous': {'patch': None, 'mods': [], 'project': None}}]
    with pytest.raises(tweak_mods.TweakError, match='rollback disk failure'):
        tweak_mods._undo(tmp_path, done)
    assert restored == ['runtime', 'file']


def test_commit_reports_both_failure_and_failed_rollback(tmp_path, monkeypatch):
    monkeypatch.setattr(tweak_mods, '_read', lambda *args: b'executable')
    def fail(*args, **kwargs):
        raise OSError('commit disk failure')
    def undo(*args, **kwargs):
        raise OSError('rollback disk failure')
    monkeypatch.setattr(tweak_mods, '_write_runtime', fail)
    monkeypatch.setattr(tweak_mods, '_undo', undo)
    with pytest.raises(tweak_mods.TweakError, match='commit disk failure; rollback failed: rollback disk failure') as caught:
        tweak_mods.commit(tmp_path, {'executableSha256': tweak_mods._sha(b'executable'), 'files': [],
                                   'runtime': {'previous': {}, 'patch': None, 'mods': [], 'project': None}})
    assert not caught.value.folders


def test_rollback_never_puts_a_legacy_patched_executable_back(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('A rollback must not write a patched executable')
    monkeypatch.setattr(tweak_mods, '_write', forbidden)
    tweak_mods._undo(tmp_path, [{'managed': tweak_mods.EXECUTABLE, 'before': b'patched',
                               'after': b'vanilla', 'previous': {}}])


def test_deployment_warning_does_not_lock_editor(page):
    mount(page)
    source = (ROOT / 'plugins/ds1/editor.js').read_text('utf-8')
    start = source.index('function reportTweakRebuild(')
    end = source.index('\nasync function save()', start)
    page.add_script_tag(content=source[start:end])
    page.evaluate('reportTweakRebuild({tweaksError:"Fixture disk failure"})')
    assert page.locator('.lex-dialog').count() == 0
    page.get_by_text('Changes saved; deployment failed. Fixture disk failure', exact=True).wait_for()
    page.locator('[data-tab="mods"]').click()
    page.get_by_role('textbox', name='Author').fill('Still editable')


@pytest.mark.parametrize('outcome', ['success', 'failure', 'disabled'])
def test_pending_mod_switch_cannot_be_overtaken_by_play(page, tmp_path, outcome):
    mount(page)
    page.evaluate("""() => {
      window.launches=0;
      pywebview.api.lexeditor_settings=async()=>({trustWarning:false});
      pywebview.api.game_process_status=async()=>({running:false,canLaunch:true});
      pywebview.api.launch_game=async()=>{launches++;return {running:true};};
      const original=pywebview.api.set_mod_enabled;
      pywebview.api.set_mod_enabled=(...args)=>new Promise((resolve,reject)=>{
        window.completeSwitch=async()=>resolve(await original(...args));
        window.failSwitch=()=>reject(new Error('Fixture activation failed'));
        window.disableSwitch=()=>resolve({enabled:false,disabledMods:[{name:'Combat',error:'Fixture broken mod'}]});
      });
    }""")
    page.locator('#global-game-process').wait_for(state='visible')
    page.locator('[data-tab="mods"]').click()
    toggle = page.get_by_role('checkbox', name='Switch Combat')
    toggle.click()
    page.wait_for_function('document.body.inert && !!window.completeSwitch')
    assert toggle.evaluate('(node)=>node.indeterminate')
    assert page.get_by_text('Building and applying mods', exact=True).is_visible()
    page.locator('#global-game-process').evaluate('(node)=>node.onclick()')
    assert page.evaluate('launches') == 0
    page.screenshot(path=str(tmp_path / 'applying-mod.png'))
    if outcome == 'success':
        page.evaluate('completeSwitch()')
        page.wait_for_function('!document.body.inert')
        assert page.get_by_role('checkbox', name='Switch Combat').is_checked()
        page.locator('#global-game-process').evaluate('(node)=>node.onclick()')
        page.wait_for_function('launches===1')
    else:
        page.evaluate('failSwitch()' if outcome == 'failure' else 'disableSwitch()')
        page.wait_for_function('!document.body.inert')
        page.locator('.lex-dialog').wait_for()
        page.locator('#global-game-process').evaluate('(node)=>node.onclick()')
        assert page.evaluate('launches') == 0
        assert not page.get_by_role('checkbox', name='Switch Combat').is_checked()


def test_steam_request_waits_until_pending_mod_transaction_finishes(tmp_path, monkeypatch):
    import os
    import threading
    from core import desktop_host
    from core.desktop_host import HostApi
    from plugins.ds1.plugin import PLUGIN
    if os.name != 'nt':
        pytest.skip('Steam dispatch is Windows-only')
    root = make_script(tmp_path, enabled=False)
    api = HostApi.__new__(HostApi)
    api._mod_library_lock = threading.RLock()
    api._plugins = {'ds1': PLUGIN}
    api._launch_notice = lambda _: ''
    api._game_mods = lambda _: tmp_path
    api._mod_adapter = lambda _: object()
    api.mod_library_status = lambda _: {'canManage': True}
    applying, finish, launched = threading.Event(), threading.Event(), threading.Event()
    failures = []
    def activate(*args):
        applying.set()
        assert finish.wait(3)
        return {}
    api._activate_mods = activate
    monkeypatch.setattr(desktop_host.os, 'startfile', lambda _: launched.set())
    def run(function):
        try:
            function()
        except Exception as error:
            failures.append(error)
    change = threading.Thread(target=lambda: run(lambda: api.set_mod_enabled('ds1', str(root), True)))
    launch = threading.Thread(target=lambda: run(lambda: api.launch_game('ds1')))
    change.start()
    try:
        assert applying.wait(3)
        launch.start()
        assert not launched.wait(.1)
    finally:
        finish.set()
        change.join(3)
        if launch.ident:
            launch.join(3)
    assert not failures, failures
    assert launched.is_set()
    assert json.loads((root / 'mod.json').read_text())['enabled']


def test_records_layout_settles_without_pager_font_or_scrollbar_oscillation(page, tmp_path):
    page.set_viewport_size({'width': 2560, 'height': 1352})
    page.add_style_tag(path=str(ROOT / 'plugins/ds1/editor.css'))
    page.evaluate("localStorage.setItem('lexeditor:rows:game-mods', '30')")
    mount(page)
    page.evaluate("""() => { window.__modContents = {
      changes: Array.from({length:1000}, (_, id) => ({id, table:'ItemLotParam',
        label: id < 654 ? 'アイテム達量 騎士オストラ（チュートリアル）' : `Ashen Estus Flask +${id} - Drained`,
        fields: id === 653 ? Array.from({length:30}, (_, n) => `Threshold Coefficient [${n}] (%)`) : [],
        added:true, removed:false, before:null, after:null})),
      files:[], truncated:false, changesTruncated:true, totalChanges:1859,
      canDescribe:true, note:''}; }""")
    detail = _detail_tabs(page)
    detail.locator(STRIP, has_text='Records').click()
    detail.locator('.lex-mod-contents .lex-column-list').wait_for()
    page.wait_for_timeout(300)
    first_size = page.locator('.lex-mod-contents .lex-column-list').get_attribute('data-lex-fitted-page-size')
    page.evaluate("""() => {for(let n=0;n<36;n++) {
      const next=document.querySelector('.lex-mod-contents .lex-pager button[aria-label="Next page"]');
      if(!next || next.disabled) break; next.click();
    }}""")
    samples = page.evaluate("""async () => {
      const result=[];
      for(let frame=0;frame<180;frame++) {
        await new Promise(requestAnimationFrame);
        if(frame<90) continue;
        const box=document.querySelector('.lex-mod-contents');
        const list=box.querySelector('.lex-column-list');
        const title=document.querySelector('.lex-mods-page .lex-detail-panel-name');
        result.push({rows:list.querySelectorAll('.lex-column-list-row').length,
          pager:box.querySelector('.lex-pager').textContent,
          scroll:list.scrollHeight>list.clientHeight+1,
          height:list.clientHeight, rect:list.getBoundingClientRect().height,
          header:list.querySelector('.lex-column-list-header').getBoundingClientRect().height,
          row:list.querySelector('.lex-column-list-row').getBoundingClientRect().height,
          font:getComputedStyle(list.querySelector('.lex-column-cell-text')).fontSize,
          title:title && getComputedStyle(title).fontSize});
      } return result;
    }""")
    page.screenshot(path=str(tmp_path / 'records-stability.png'))
    distinct = {str(sample) for sample in samples}
    assert len(distinct) == 1, list(distinct)[:8]
    assert samples[-1]['rows'] > 5, samples[-1]
    assert not samples[-1]['scroll'], samples[-1]
    assert page.locator('.lex-mod-contents .lex-column-list').get_attribute('data-lex-fitted-page-size') == first_size
    page.evaluate("""() => {
      window.originalHeading=document.querySelector('.lex-mods-page .lex-detail-panel-name');
      document.querySelector('.lex-mod-contents').parentElement.style.maxHeight='500px';
    }""")
    page.wait_for_function("Number(document.querySelector('.lex-mod-contents .lex-column-list').dataset.lexFittedPageSize) < 20")
    page.wait_for_timeout(200)
    assert page.evaluate("originalHeading === document.querySelector('.lex-mods-page .lex-detail-panel-name')")
