"""Native toggles reuse unchanged data and verified installed menu recipes."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def test_native_toggle_reuses_installed_data_without_composition(tmp_path, monkeypatch):
    from plugins.ds1 import mod_support, mod_loader, tweak_mods
    from plugins.ds1.store import MARKER, RELATIVE
    from core import mods_service
    from contextlib import nullcontext
    game, library = tmp_path/'game', tmp_path/'library'
    game.mkdir()
    native, data = library/'iframe-display', library/'data'
    for folder in (native, data):
        folder.mkdir(parents=True)
        (folder/MARKER).write_bytes(b'project')
    (native/'native').mkdir()
    (native/'native/iframe-display.json').write_text('{}')
    (data/RELATIVE).parent.mkdir(parents=True)
    (data/RELATIVE).write_bytes(b'data input')
    monkeypatch.setattr(mods_service, 'library_rows', lambda root: [
        {'name':'Iframe Display', 'path':str(native)}, {'name':'Data', 'path':str(data)}])
    adapter = mod_support.Ds1ModAdapter()
    adapter.attach_context(library_root=library)
    monkeypatch.setattr(adapter, '_report_path', lambda: tmp_path/'report.json')
    ordered = adapter._ordered_mods([data])
    adapter._save_report(game, ordered, [], installed=True)
    assert adapter._ordered_mods([native, data]) == ordered
    monkeypatch.setattr(tweak_mods, 'ensure_game_closed', lambda: None)
    monkeypatch.setattr(tweak_mods, 'locked', lambda root: nullcontext())
    monkeypatch.setattr(tweak_mods, 'prepare', lambda *args, **kwargs: {})
    monkeypatch.setattr(tweak_mods, 'commit', lambda *args: None)
    def no_composition(*args, **kwargs):
        pytest.fail('A native toggle must not recompose or redeploy unchanged game data')
    monkeypatch.setattr(mod_loader, 'compose_installed', no_composition)
    monkeypatch.setattr(mod_support.deployment, 'apply', no_composition)
    assert adapter.activate([native, data], game)['timings']['reusedInstalledData']
    assert adapter.activate([data], game)['timings']['reusedInstalledData']
    # An external edit still invalidates the installed recipe immediately.
    (data/RELATIVE).write_bytes(b'changed data input')
    assert adapter._read_report(game, ordered) is None


def test_menu_reuses_verified_install_even_after_cache_eviction(tmp_path, monkeypatch):
    from plugins.ds1 import tweak_mods, menu_layout
    original, installed = b'original menu', b'composed menu'
    managed = tweak_mods.Managed('menu/menu.drb.dcx', 'test menu', 1024, lambda value: value == original)
    monkeypatch.setattr(tweak_mods, 'LAYOUT', managed)
    monkeypatch.setattr(tweak_mods, 'ensure_game_closed', lambda: None)
    live = managed.live(tmp_path)
    live.parent.mkdir()
    live.write_bytes(original)
    specs = [{'owner':'UI', 'nodes':[1]}]
    identity = tweak_mods._menu_identity(original, specs, managed)
    tweak_mods._write(tmp_path, original, installed, ['UI'], managed, inputs=identity)
    manifest = tweak_mods._manifest(tmp_path, managed)
    def compose(*args):
        pytest.fail('An unchanged verified menu must survive disposable cache eviction')
    monkeypatch.setattr(menu_layout, 'compose', compose)
    assert tweak_mods._compose_menu(original, specs, managed, None,
                                   current=installed, manifest=manifest) == installed
    # An interrupted write uses its matching pending recipe, not the old one.
    pending = {**manifest, 'inputs':'0'*64,
               'pending':{'sha256':tweak_mods._sha(installed), 'mods':['UI'],
                          'project':None, 'inputs':identity}}
    tweak_mods._save_manifest(tmp_path, pending, managed)
    assert tweak_mods._compose_menu(original, specs, managed, None, current=installed,
                                   manifest=tweak_mods._manifest(tmp_path, managed)) == installed
    calls = []
    monkeypatch.setattr(menu_layout, 'compose', lambda *args: calls.append(args) or b'new menu')
    assert tweak_mods._compose_menu(original, specs+[{'owner':'New'}], managed, None,
                                   current=installed, manifest=manifest) == b'new menu'
    for invalid in (None, {}, ['broken'], 'bad cache'):
        assert tweak_mods._compose_menu(original, specs, managed, None, current=installed,
                                       manifest={**manifest,'inputs':invalid}) == b'new menu'
    assert tweak_mods._compose_menu(original, specs, managed, None, current=b'external edit',
                                   manifest=manifest) == b'new menu'
    assert len(calls) == 6
    # An unsupported optional cache representation must never become a build
    # failure, nor count as a matching recipe when both identities are absent.
    assert tweak_mods._compose_menu(original, [{'internal':object()}], managed, tmp_path,
                                   current=installed, manifest={**manifest,'inputs':None}) == b'new menu'
    assert len(calls) == 7

