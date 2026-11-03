"""Bundle components as ordinary tweak settings: schema, values, expansion.

A bundle's components used to be ticked in the Mod Library dialog and
applied as one transaction. Now each component is an on/off setting from
the bundle's own schema, saved beside the mod and deployed with it.
"""
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import bundled_mods, mods_service
from core.bundled_mods import components, expand_roots, inspect_bundle, schema, save_values, selected_paths, values
from core.desktop_host import HostApi
from core.mod_library import ModLibrary


class Loader:
    supports_bundle_components = True

    def __init__(self):
        self.deployed = None

    def inspect(self, root, files):
        return {'valid': Path('data.bin') in files, 'problems': [], 'packages': ['data.bin']}

    def activate(self, roots, game):
        self.deployed = [Path(path).name for path in roots]
        (game / 'loaded.json').write_text(json.dumps(self.deployed))

    def active_mod_ids(self, game):
        path = game / 'loaded.json'
        return json.loads(path.read_text()) if path.exists() else []


def fixture(root):
    library, game = root / 'library/test', root / 'game'
    game.mkdir(parents=True)
    bundle = library / 'Collection'
    rows = []
    for key, tweaks in [('combat', ['damage']), ('balance', [])]:
        child = bundle / key
        child.mkdir(parents=True)
        (child / 'data.bin').write_bytes(key.encode())
        rows.append({'id': key, 'name': key.title(), 'path': key, 'tweaks': tweaks})
    (bundle / 'mod.json').write_text(json.dumps({'name': 'Collection', 'enabled': False, 'bundle': {
        'version': 1, 'components': rows}}))
    return bundle, game


def test_schema_lists_one_switch_per_component_default_off(tmp_path):
    bundle, _game = fixture(tmp_path)
    result = schema(bundle)
    assert [(field['key'], field['label'], field['type'], field['default'])
            for field in result['fields']] == [('combat', 'Combat', 'bool', False),
                                               ('balance', 'Balance', 'bool', False)]
    assert values(bundle) == {'combat': False, 'balance': False}
    assert selected_paths(bundle) == []


def test_save_round_trips_and_rejects_unknown_or_non_boolean(tmp_path):
    bundle, _game = fixture(tmp_path)
    assert save_values(bundle, {'combat': True}) == {'combat': True, 'balance': False}
    assert values(bundle) == {'combat': True, 'balance': False}
    assert json.loads((bundle / 'settings.json').read_text()) == {
        'values': {'combat': True, 'balance': False}}
    assert [path.name for path in selected_paths(bundle)] == ['combat']
    with pytest.raises(ValueError, match='Unknown settings: cost'):
        save_values(bundle, {'cost': True})
    with pytest.raises(ValueError, match='combat must be on or off'):
        save_values(bundle, {'combat': 'yes'})
    with pytest.raises(ValueError, match='Settings must be an object'):
        save_values(bundle, ['combat'])
    assert values(bundle) == {'combat': True, 'balance': False}


def test_bad_stored_values_fall_back_but_corrupt_json_is_loud(tmp_path):
    bundle, _game = fixture(tmp_path)
    (bundle / 'settings.json').write_text(json.dumps({'values': {'combat': 'yes', 'balance': True}}))
    assert values(bundle) == {'combat': False, 'balance': True}
    (bundle / 'settings.json').write_text('{broken')
    with pytest.raises(ValueError, match='settings.json is not readable JSON'):
        values(bundle)


def test_expand_roots_replaces_bundles_and_rejects_collisions(tmp_path):
    bundle, _game = fixture(tmp_path)
    plain = bundle.parent / 'Plain'
    plain.mkdir()
    (plain / 'mod.json').write_text(json.dumps({'name': 'Plain'}))
    save_values(bundle, {'balance': True})
    assert expand_roots([plain, bundle], Loader()) == [plain, bundle / 'balance']
    assert expand_roots([bundle], Loader()) == [bundle / 'balance']
    save_values(bundle, {'combat': False, 'balance': False})
    assert expand_roots([bundle], Loader()) == []
    clone = bundle.parent / 'Clone'
    clone.mkdir()
    (clone / 'balance').mkdir()
    (clone / 'balance' / 'data.bin').write_bytes(b'x')
    (clone / 'mod.json').write_text(json.dumps({'name': 'Clone', 'bundle': {'version': 1, 'components': [
        {'id': 'balance', 'name': 'Balance', 'path': 'balance', 'tweaks': []}]}}))
    save_values(clone, {'balance': True})
    save_values(bundle, {'balance': True})
    with pytest.raises(ValueError, match='distinct names'):
        expand_roots([bundle, clone], Loader())


def test_bundles_are_refused_on_loaders_without_component_support(tmp_path):
    bundle, _game = fixture(tmp_path)
    save_values(bundle, {'combat': True})
    adapter = Loader()
    adapter.supports_bundle_components = False
    with pytest.raises(ValueError, match='does not support bundled components'):
        expand_roots([bundle], adapter)
    assert not inspect_bundle(bundle, [Path('combat/data.bin')], adapter)['valid']


def test_component_layout_is_still_validated(tmp_path):
    bundle, _game = fixture(tmp_path)
    metadata = json.loads((bundle / 'mod.json').read_text())
    metadata['bundle']['components'][0]['path'] = '../escape'
    (bundle / 'mod.json').write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        components(bundle)
    with pytest.raises(ValueError):
        schema(bundle)


def test_bundle_import_and_standalone_regression(tmp_path):
    bundle, _game = fixture(tmp_path)
    library = ModLibrary(tmp_path / 'imported')
    report = library.inspect(bundle, Loader())
    assert report['valid'] and len(report['packages']) == 2
    imported = library.import_mod('test', bundle, Loader(), 'Imported')
    assert len(components(imported)) == 2
    assert not inspect_bundle(bundle, [Path('mod.json')], Loader())['valid']
    plain = tmp_path / 'plain'
    plain.mkdir()
    (plain / 'data.bin').write_bytes(b'unchanged standalone')
    assert library.inspect(plain, Loader())['valid']


def test_mod_row_exposes_components_like_script_settings(tmp_path):
    bundle, _game = fixture(tmp_path)
    save_values(bundle, {'combat': True})
    row = mods_service.mod_row(bundle)
    assert row['components']['error'] == ''
    assert [field['key'] for field in row['components']['schema']['fields']] == ['combat', 'balance']
    assert row['components']['values'] == {'combat': True, 'balance': False}
    (bundle / 'combat' / 'data.bin').unlink()
    (bundle / 'combat').rmdir()
    broken = mods_service.mod_row(bundle)
    assert broken['components']['error'] != ''
    assert broken['name'] == 'Collection'


def host_for(library, game, adapter):
    host = HostApi.__new__(HostApi)
    host._mod_library_lock = threading.RLock()
    host._game_mods = lambda _plugin: library
    host._mod_adapter = lambda _plugin: adapter
    host._installations = SimpleNamespace(snapshot=lambda _plugin: {'root': str(game)})
    host.game_process_status = lambda _plugin: {'running': False}
    host.mod_library_status = lambda _plugin: {'canManage': True, 'root': str(library.parent),
                                               'message': ''}
    return host


def test_component_tick_saves_and_deploys_at_once_while_on(tmp_path):
    bundle, game = fixture(tmp_path)
    library = bundle.parent
    info = json.loads((bundle / 'mod.json').read_text())
    info['enabled'] = True
    (bundle / 'mod.json').write_text(json.dumps(info))
    adapter = Loader()
    host = host_for(library, game, adapter)
    row = HostApi.save_mod_settings(host, 'test', str(bundle), {'combat': True, 'balance': True})
    assert row['components']['values'] == {'combat': True, 'balance': True}
    assert adapter.deployed == ['combat', 'balance']
    assert json.loads((game / 'loaded.json').read_text()) == ['combat', 'balance']


def test_component_tick_while_off_saves_without_deploying(tmp_path):
    bundle, game = fixture(tmp_path)
    adapter = Loader()
    host = host_for(bundle.parent, game, adapter)
    HostApi.save_mod_settings(host, 'test', str(bundle), {'combat': True})
    assert values(bundle) == {'combat': True, 'balance': False}
    assert adapter.deployed is None


def test_deploy_failure_keeps_the_saved_tick(tmp_path):
    bundle, game = fixture(tmp_path)
    info = json.loads((bundle / 'mod.json').read_text())
    info['enabled'] = True
    (bundle / 'mod.json').write_text(json.dumps(info))
    adapter = Loader()
    host = host_for(bundle.parent, game, adapter)
    host.game_process_status = lambda _plugin: {'running': True}
    with pytest.raises(ValueError, match='Close the game'):
        HostApi.save_mod_settings(host, 'test', str(bundle), {'combat': True})
    assert values(bundle) == {'combat': True, 'balance': False}


def test_activate_guards_match_the_old_apply(tmp_path):
    bundle, game = fixture(tmp_path)
    adapter = Loader()
    host = host_for(bundle.parent, game, adapter)
    host.game_process_status = lambda _plugin: {'running': True}
    with pytest.raises(ValueError, match='Close the game'):
        HostApi._activate_mods(host, 'test', [str(bundle)])
    host.game_process_status = lambda _plugin: {'running': False}
    with pytest.raises(ValueError, match='Choose each mod once'):
        HostApi._activate_mods(host, 'test', [str(bundle), str(bundle)])
    with pytest.raises(ValueError, match='Choose each mod once'):
        HostApi._activate_mods(host, 'test', [str(tmp_path / 'elsewhere')])


def test_real_pak_adapter_deploys_and_removes_a_ticked_component(tmp_path, monkeypatch):
    from plugins.ff7r.mod_support import PakModAdapter
    from plugins.ff7r import tooling
    from plugins.ff7r.tooling import pack_directory, get_file
    # Use the hash-pinned bundled helper in this test's own cache. A fresh CI
    # runner must not depend on an installation in the developer's user folder.
    monkeypatch.delenv('LEXEDITOR_REPAK', raising=False)
    monkeypatch.setattr(tooling, 'user_data_dir', lambda: tmp_path / 'helper-cache')
    assert tooling.helper_install()['installed']
    bundle, game = fixture(tmp_path)
    exe = game / 'End/Binaries/Win64/ff7remake_.exe'
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b'fixture')
    for row in components(bundle):
        root = Path(row['path'])
        (root / 'data.bin').unlink()
        content = tmp_path / ('content-' + row['id'])
        asset = content / ('End/Content/' + row['id'] + '.txt')
        asset.parent.mkdir(parents=True)
        asset.write_bytes(row['id'].encode())
        pack_directory(content, root / (row['id'] + '_P.pak'), version='V4')
    adapter = PakModAdapter()
    save_values(bundle, {'combat': True})
    adapter.activate(expand_roots([bundle], adapter), game)
    deployed = game / 'End/Content/Paks/~mods/LexeditorLibrary'
    assert get_file(deployed / 'combat_P.pak', 'End/Content/combat.txt') == b'combat'
    save_values(bundle, {'combat': False})
    adapter.activate(expand_roots([bundle], adapter), game)
    assert not list(deployed.glob('*.pak'))


def test_bundled_mods_module_has_no_apply_time_machinery():
    assert not hasattr(bundled_mods, 'BundleManager')
    assert not hasattr(bundled_mods, 'BundledTweak')
    assert not hasattr(HostApi, 'mod_library_entries')
    assert not hasattr(HostApi, 'activate_library_mods')
    assert not hasattr(HostApi, 'set_bundled_tweak')
    assert not hasattr(HostApi, 'recover_bundled_mods')
