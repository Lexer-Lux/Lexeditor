"""Linked component deployment, durable settings, and transaction failures."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.bundled_mods import BundleManager, BundledTweak, components, inspect_bundle
from core.desktop_host import HostApi
from core.mod_library import ModLibrary, file_tree


class Loader:
    supports_bundle_components = True
    fail = False

    def inspect(self, root, files):
        return {'valid': Path('data.bin') in files, 'problems': [], 'packages': ['data.bin']}

    def activate(self, roots, game):
        # A failed deploy may already have replaced part of its output.
        (game / 'loaded.json').write_text(json.dumps([p.name for p in roots]))
        if self.fail:
            self.fail = False
            raise OSError('deployment failed')

    def active_mod_ids(self, game):
        path = game / 'loaded.json'
        return json.loads(path.read_text()) if path.exists() else []


def fixture(root):
    library, game = root / 'library/test', root / 'game'
    game.mkdir(parents=True)
    bundle = library / 'Collection'
    rows = []
    for key, tweaks in [('combat', ['damage']), ('balance', ['damage', 'cost'])]:
        child = bundle / key
        child.mkdir(parents=True)
        (child / 'data.bin').write_bytes(key.encode())
        rows.append({'id': key, 'name': key.title(), 'path': key, 'tweaks': tweaks})
    (bundle / 'mod.json').write_text(json.dumps({'name': 'Collection', 'bundle': {'version': 1, 'components': rows}}))
    def read(key):
        path = game / (key + '.json')
        return json.loads(path.read_text()) if path.exists() else False
    def write(key, value):
        (game / (key + '.json')).write_text(json.dumps(value))
    tweaks = {key: BundledTweak(key.title() + ' tweak', lambda game, key=key: read(key),
                               lambda game, value, key=key: write(key, value)) for key in ('damage', 'cost')}
    return BundleManager(library, game, Loader(), tweaks)


def test_repeated_component_toggles_shared_dependencies_and_reopen(tmp_path):
    manager = fixture(tmp_path)
    for _ in range(3):
        manager.activate([], ['Collection/combat', 'Collection/balance'])
        fresh = BundleManager(manager.library, manager.game, Loader(), manager.tweaks)
        assert fresh.state()['components'] == ['Collection/combat', 'Collection/balance']
        assert fresh.adapter.active_mod_ids(fresh.game) == ['combat', 'balance']
        assert all(t['enabled'] for t in fresh.snapshot()['tweaks'])
        manager.activate([], ['Collection/combat'])
        assert manager.tweaks['damage'].read(manager.game) is True
        assert manager.tweaks['cost'].read(manager.game) is False
        manager.activate([], [])
        assert not any(t['enabled'] for t in manager.snapshot()['tweaks'])
        assert manager.adapter.active_mod_ids(manager.game) == []
    assert not manager.journal.exists()


def test_reverse_tweak_switches_components_and_preserves_other_dependencies(tmp_path):
    manager = fixture(tmp_path)
    manager.toggle_tweak('damage', True)
    assert set(manager.state()['components']) == {'Collection/combat', 'Collection/balance'}
    manager.toggle_tweak('cost', False)
    assert manager.state()['components'] == ['Collection/combat']
    assert manager.tweaks['damage'].read(manager.game)
    manager.toggle_tweak('damage', False)
    assert manager.state()['components'] == []
    assert not manager.snapshot()['inconsistent']


@pytest.mark.parametrize('failure', ['deploy', 'tweak', 'state'])
def test_failure_restores_payload_settings_and_persisted_selection(tmp_path, monkeypatch, failure):
    manager = fixture(tmp_path)
    manager.activate([], ['Collection/combat'])
    before = manager.state_path.read_bytes()
    if failure == 'deploy':
        manager.adapter.fail = True
    elif failure == 'tweak':
        original = manager.tweaks['cost']
        calls = []
        def fail(game, enabled):
            original.write(game, enabled)
            calls.append(enabled)
            if len(calls) == 1:
                raise OSError('tweak failed after writing')
        manager.tweaks['cost'] = BundledTweak(original.name, original.read, fail)
    else:
        save = manager._save
        calls = []
        def fail(path, value):
            if path == manager.state_path and not calls:
                calls.append(True)
                raise OSError('state write failed')
            save(path, value)
        monkeypatch.setattr(manager, '_save', fail)
    with pytest.raises(OSError):
        manager.activate([], ['Collection/balance'])
    assert manager.state_path.read_bytes() == before
    assert manager.adapter.active_mod_ids(manager.game) == ['combat']
    assert manager.tweaks['damage'].read(manager.game) is True
    assert manager.tweaks['cost'].read(manager.game) is False
    assert not manager.journal.exists()


def test_failed_rollback_is_durable_and_recoverable_after_restart(tmp_path, monkeypatch):
    manager = fixture(tmp_path)
    manager.activate([], ['Collection/combat'])
    original = manager.adapter.activate
    monkeypatch.setattr(manager.adapter, 'activate', lambda *_: (_ for _ in ()).throw(OSError('loader unavailable')))
    with pytest.raises(RuntimeError, match='Rollback needs recovery'):
        manager.activate([], ['Collection/balance'])
    assert manager.snapshot()['recoveryRequired']
    with pytest.raises(ValueError, match='Recover'):
        manager.activate([], [])
    fresh = BundleManager(manager.library, manager.game, Loader(), manager.tweaks)
    fresh.recover()
    assert fresh.state()['components'] == ['Collection/combat']
    assert not fresh.snapshot()['inconsistent']
    assert not fresh.journal.exists()


def test_unknown_tweaks_bad_paths_and_unsupported_loaders_fail_before_mutation(tmp_path):
    manager = fixture(tmp_path)
    manager.tweaks.pop('cost')
    with pytest.raises(ValueError, match='not registered'):
        manager.activate([], ['Collection/balance'])
    assert not manager.journal.exists()
    manager.adapter.supports_bundle_components = False
    with pytest.raises(ValueError, match='does not support'):
        manager.activate([], ['Collection/combat'])
    root = manager.library / 'Collection'
    metadata = json.loads((root / 'mod.json').read_text())
    metadata['bundle']['components'][0]['path'] = '../escape'
    (root / 'mod.json').write_text(json.dumps(metadata))
    with pytest.raises(ValueError): components(root)
    assert not list(manager.game.glob('*.json'))


def test_loader_silent_failure_is_detected_and_tweaks_are_rolled_back(tmp_path, monkeypatch):
    manager = fixture(tmp_path)
    manager.activate([], [])
    monkeypatch.setattr(manager.adapter, 'activate', lambda *_: None)
    with pytest.raises(ValueError, match='did not persist'):
        manager.activate([], ['Collection/combat'])
    assert manager.state()['components'] == []
    assert not manager.tweaks['damage'].read(manager.game)
    assert not manager.journal.exists()


def test_bundle_import_and_standalone_regression(tmp_path):
    manager = fixture(tmp_path)
    library = ModLibrary(tmp_path / 'imported')
    source = manager.library / 'Collection'
    report = library.inspect(source, manager.adapter)
    assert report['valid'] and len(report['packages']) == 2
    imported = library.import_mod('test', source, manager.adapter, 'Imported')
    assert len(components(imported)) == 2
    assert not inspect_bundle(source, [Path('mod.json')], manager.adapter)['valid']
    plain = tmp_path / 'plain'
    plain.mkdir()
    (plain / 'data.bin').write_bytes(b'unchanged standalone')
    assert library.inspect(plain, manager.adapter)['valid']


def host_fixture(manager):
    host = HostApi.__new__(HostApi)
    host._mod_library_lock = threading.RLock()
    host._bundle_manager = lambda _: manager
    host._mod_adapter = lambda _: manager.adapter
    host._installations = SimpleNamespace(snapshot=lambda _: {'root': str(manager.game)})
    host._plugins = {'test': SimpleNamespace(managed_mod=None, mod_adapter=manager.adapter, bundled_tweaks=manager.tweaks)}
    host._managed_mod_results = {}
    host.game_process_status = lambda _: {'running': False}
    host.mod_library_status = lambda _: {'canManage': True, 'root': str(manager.library.parent), 'message': ''}
    return host


def test_real_host_api_checks_game_running_and_exposes_relationship(tmp_path):
    manager = fixture(tmp_path)
    host = host_fixture(manager)
    result = host.activate_library_mods('test', [], ['Collection/combat'])
    assert result['entries'][0]['components'][0]['linkedTweaks'][0]['name'] == 'Damage tweak'
    host.set_bundled_tweak('test', 'damage', False)
    assert not manager.state()['components']
    host.game_process_status = lambda _: {'running': True}
    with pytest.raises(ValueError, match='Close the game'):
        host.set_bundled_tweak('test', 'damage', True)
    with pytest.raises(ValueError, match='Close the game'):
        host.activate_library_mods('test', [], ['Collection/combat'])


def test_external_setting_or_deployment_change_is_not_silently_accepted(tmp_path):
    manager = fixture(tmp_path)
    manager.activate([], ['Collection/combat'])
    manager.tweaks['damage'].write(manager.game, False)
    assert manager.snapshot()['inconsistent']
    host = host_fixture(manager)
    with pytest.raises(ValueError, match='before launching'):
        host.launch_game('test')
    manager.activate([], ['Collection/combat'])
    assert not manager.snapshot()['inconsistent']
    manager.adapter.activate([], manager.game)
    assert manager.snapshot()['inconsistent']


def test_real_pak_adapter_deploys_and_removes_linked_component(tmp_path):
    from plugins.ff7r.mod_support import PakModAdapter
    from plugins.ff7r.tooling import pack_directory, get_file
    manager = fixture(tmp_path)
    exe = manager.game / 'End/Binaries/Win64/ff7remake_.exe'
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b'fixture')
    for row in manager.catalog().values():
        root = Path(row['path'])
        (root / 'data.bin').unlink()
        content = tmp_path / ('content-' + row['id'])
        asset = content / ('End/Content/' + row['id'] + '.txt')
        asset.parent.mkdir(parents=True)
        asset.write_bytes(row['id'].encode())
        pack_directory(content, root / (row['id'] + '_P.pak'), version='V4')
    manager.adapter = PakModAdapter()
    manager.activate([], ['Collection/combat'])
    deployed = manager.game / 'End/Content/Paks/~mods/LexeditorLibrary'
    assert get_file(deployed / 'combat_P.pak', 'End/Content/combat.txt') == b'combat'
    assert manager.tweaks['damage'].read(manager.game)
    fresh = BundleManager(manager.library, manager.game, PakModAdapter(), manager.tweaks)
    assert not fresh.snapshot()['inconsistent']
    fresh.toggle_tweak('damage', False)
    assert not list(deployed.glob('*.pak'))
    assert not fresh.tweaks['damage'].read(manager.game)
