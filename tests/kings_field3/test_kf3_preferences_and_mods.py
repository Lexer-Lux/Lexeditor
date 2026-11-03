"""Preservation, native-mod coexistence, and rollback for Verdite3 integration."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import native_port_settings as model
from plugins.kings_field3.model import MODEL
from core.native_source_mods import LEDGER, RECOVERY, NativeSourceModAdapter


def test_service_is_registered_for_normal_and_frozen_launches():
    from core.runtime_bootstrap import service_command
    assert "plugins.kings_field3.server" in service_command("plugins.kings_field3.server", owned=True)


def test_shared_checks_cover_native_factory_and_module_boot(setup, tmp_path, monkeypatch):
    import runpy
    root = Path(__file__).resolve().parents[2]
    runpy.run_path(str(root / 'tests/shared/verify_shared_shell_projects_issue_27.py'))
    routes = runpy.run_path(str(root / 'tests/shared/plugin_module_routes_check.py'))
    assert routes['check']('kings_field3') == []
    script = root / 'tests/shared/data_map_browser_check.py'
    monkeypatch.setenv('DATAMAP_GAMES', 'kings_field3')
    monkeypatch.setattr(sys, 'argv', [str(script), str(tmp_path / 'data-map')])
    runpy.run_path(str(script))


def test_non_steam_game_validates_without_steam_discovery_or_art_requests(tmp_path):
    from core.plugin_api import validate_plugin
    from core.game_installation import GameInstallationManager
    from core.cover_art import CoverArtCache
    from plugins.kings_field3.plugin import PLUGIN
    validate_plugin(PLUGIN)
    assert GameInstallationManager._steam_candidates("", ("Verdite3",)) == []

    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("A non-Steam port must not request a Steam cover")

    covers = CoverArtCache({PLUGIN.plugin_id: PLUGIN}, root=tmp_path,
                          fetcher=unexpected_fetch, steam_roots=())
    assert not covers._threads
    assert covers._states[PLUGIN.plugin_id]["state"] == "unavailable"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    game, data, library = (tmp_path / name for name in ("game", "data", "library"))
    for path in (game / "bin", game / "content/config", data / "mods", library):
        path.mkdir(parents=True)
    for name in ("Verdite3.exe", "RecompOne.Runtime.dll"):
        (game / "bin" / name).write_bytes(b"synthetic only")
    (game / "content/config/kf3.json").write_text('{"game":{"id":"SLUS-00255","name":"KingsField3"}}')
    (data / "settings.json").write_text(json.dumps({"ActiveMods": ["obsolete-not-a-loader-setting"], "Unmodeled": {"keep": 42}}))
    (data / "interface.ini").write_bytes(b"\xef\xbb\xbf[RecompOne]\r\nmods.external.map.enabled=True\r\nmods.external.map.priority=17\r\nother=keep\r\n[Window][Output]\r\nPos=12,34\r\n")
    monkeypatch.setenv("LEXEDITOR_KF3_DATA", str(data))
    monkeypatch.setenv("LEXEDITOR_KF3_ROOT", str(game))
    monkeypatch.setattr(model, "live_processes", lambda _: [])
    return game, data, library


def mod(library, name="example"):
    root = library / name
    root.mkdir()
    (root / "mod.json").write_text(json.dumps({"id": name, "name": name}))
    (root / "Mod.cs").write_text("// synthetic source; never compiled or executed\n")
    return root


def test_ini_noop_is_byte_exact_and_changes_preserve_other_sections():
    raw = b"\xef\xbb\xbf; head\r\n[RecompOne]\r\n  kf3.mouse.turn =1\r\nMystery = keep\r\n[Window][Output]\r\nPos=12,34\r\n"
    assert model.updated_ini(raw, {}) == raw
    assert model.updated_ini(b"[RecompOne]\nother=keep", {"absent": None}) == b"[RecompOne]\nother=keep"
    output = model.updated_ini(raw, {"kf3.mouse.turn": "2", "kf3.mouse.look": "3"})
    assert output == raw.replace(b"kf3.mouse.turn =1", b"kf3.mouse.turn =2").replace(b"[Window]", b"kf3.mouse.look=3\r\n[Window]")


def test_preferences_save_is_bounded_preserves_unknowns_and_refuses_stale(setup):
    _, data, _ = setup
    path = data / "interface.ini"
    path.write_bytes(b"[RecompOne]\nkf3.mouse.turn=1\nother=keep\n[Docking][Data]\nDockNode=0x1\n")
    before = MODEL.preferences(data)
    result = MODEL.save_preferences(data, {"kf3.mouse.turn": 2}, before["fingerprint"])
    assert result["fields"][0]["value"] == 2
    assert b"other=keep\n[Docking][Data]\nDockNode=0x1\n" in path.read_bytes()
    assert path.with_suffix(".ini.lexeditor-previous").read_bytes().startswith(b"[RecompOne]")
    with pytest.raises(ValueError, match="changed since"):
        MODEL.save_preferences(data, {"kf3.mouse.turn": 3}, before["fingerprint"])
    for value in (-1, 6, float("nan"), True, "2"):
        with pytest.raises(ValueError):
            MODEL.save_preferences(data, {"kf3.mouse.turn": value}, result["fingerprint"])


def test_duplicate_ini_facts_are_rejected():
    for text in ("[RecompOne]\na=1\na=2\n", "[RecompOne]\na=1\nA=2\n", "[RecompOne]\na=1\n[RecompOne]\na=2\n"):
        with pytest.raises(ValueError, match="repeat|duplicate"):
            model.ini_values(text)


def test_new_stick_defaults_preserve_saved_sensitivity(setup):
    _, data, _ = setup
    path = data / "interface.ini"
    original = path.read_bytes()
    values = {field["key"]: field["value"] for field in MODEL.preferences(data)["fields"]}
    assert values["kf3.analog.turn"] == values["kf3.analog.pitch"] == 3
    assert values["kf3.mouse.turn"] == 1
    assert path.read_bytes() == original
    saved = original.replace(b"[RecompOne]\r\n", b"[RecompOne]\r\nkf3.analog.turn=2.4\r\nkf3.analog.pitch=1.7\r\n")
    path.write_bytes(saved)
    values = {field["key"]: field["value"] for field in MODEL.preferences(data)["fields"]}
    assert values["kf3.analog.turn"] == 2.4 and values["kf3.analog.pitch"] == 1.7
    assert path.read_bytes() == saved


def test_running_game_is_never_modified(setup, monkeypatch):
    game, data, library = setup
    source = mod(library)
    before = (data / "settings.json").read_bytes()
    monkeypatch.setattr(model, "live_processes", lambda _: [{"pid": 123}])
    with pytest.raises(ValueError, match="Close the game"):
        NativeSourceModAdapter(MODEL).activate([source], game)
    with pytest.raises(ValueError, match="Close the game"):
        MODEL.save_preferences(data, {}, model.fingerprint(b""))
    assert (data / "settings.json").read_bytes() == before
    assert not (data / LEDGER).exists()


def test_activation_and_removal_preserve_native_mods_and_settings(setup):
    game, data, library = setup
    source = mod(library)
    native = data / "mods/map"
    native.mkdir()
    (native / "mod.json").write_text('{"id":"external.map","name":"Native map"}')
    original = (native / "mod.json").read_bytes()
    original_settings = (data / "settings.json").read_bytes()
    original_interface = (data / "interface.ini").read_bytes()
    adapter = NativeSourceModAdapter(MODEL)
    result = adapter.activate([source], game)
    assert result["mods"] == ["external.map", "example"]
    assert (data / "mods/lexeditor-example/Mod.cs").read_bytes() == (source / "Mod.cs").read_bytes()
    assert not (data / RECOVERY).exists()
    active = model.ini_values((data / "interface.ini").read_text(encoding="utf-8-sig"))
    assert active["mods.example.enabled"] == "True"
    assert active["mods.example.priority"] == "1"
    adapter.activate([], game)
    assert not (data / "mods/lexeditor-example").exists()
    settings = json.loads((data / "settings.json").read_text())
    assert settings == {"ActiveMods": ["obsolete-not-a-loader-setting"], "Unmodeled": {"keep": 42}}
    assert (data / "settings.json").read_bytes() == original_settings
    assert (data / "interface.ini").read_bytes() == original_interface
    assert (native / "mod.json").read_bytes() == original


def test_external_mod_edits_refuse_replacement(setup):
    game, data, library = setup
    source = mod(library)
    adapter = NativeSourceModAdapter(MODEL)
    adapter.activate([source], game)
    target = data / "mods/lexeditor-example/Mod.cs"
    target.write_text("// player's changes\n")
    with pytest.raises(ValueError, match="changed outside"):
        adapter.activate([], game)
    assert target.read_text() == "// player's changes\n"


def test_duplicate_native_id_and_binary_packages_are_refused(setup):
    game, data, library = setup
    source = mod(library)
    native = data / "mods/native-example"
    native.mkdir()
    (native / "mod.json").write_text('{"id":"example","name":"Existing native mod"}')
    with pytest.raises(ValueError, match="already exists"):
        NativeSourceModAdapter(MODEL).activate([source], game)
    (source / "game.exe").write_bytes(b"synthetic")
    report = NativeSourceModAdapter(MODEL).inspect(source, [Path("mod.json"), Path("Mod.cs"), Path("game.exe")])
    assert not report["valid"]


def test_failed_configuration_write_rolls_back_mod_files_and_active_ids(setup, monkeypatch):
    game, data, library = setup
    first, second = mod(library, "first"), mod(library, "second")
    adapter = NativeSourceModAdapter(MODEL)
    adapter.activate([first], game)
    old_settings = (data / "settings.json").read_bytes()
    old_interface = (data / "interface.ini").read_bytes()
    original_write = model.atomic_write
    failed = False

    def fail_once(path, raw):
        nonlocal failed
        if path == data / LEDGER and not failed:
            failed = True
            raise OSError("synthetic interrupted write")
        original_write(path, raw)

    monkeypatch.setattr(MODEL, "atomic_write", fail_once)
    with pytest.raises(OSError, match="synthetic interrupted"):
        adapter.activate([second], game)
    assert (data / "mods/lexeditor-first/Mod.cs").is_file()
    assert not (data / "mods/lexeditor-second").exists()
    assert (data / "settings.json").read_bytes() == old_settings
    assert (data / "interface.ini").read_bytes() == old_interface
    assert not (data / RECOVERY).exists()


def test_recovery_preserves_edited_backup_without_replacing_deployed_mod(setup, monkeypatch):
    game, data, library = setup
    first, second = mod(library, "first"), mod(library, "second")
    adapter = NativeSourceModAdapter(MODEL)
    adapter.activate([first], game)
    original_write = model.atomic_write

    def interrupt_with_edited_backup(path, raw):
        if path == data / LEDGER:
            backup = data / RECOVERY / "mods/lexeditor-first/Mod.cs"
            backup.write_text("// recovered player edits\n")
            raise OSError("synthetic interrupted write")
        original_write(path, raw)

    monkeypatch.setattr(MODEL, "atomic_write", interrupt_with_edited_backup)
    with pytest.raises(ValueError, match="Recovery copy.*edited"):
        adapter.activate([second], game)
    assert (data / RECOVERY / "mods/lexeditor-first/Mod.cs").read_text() == "// recovered player edits\n"
    assert (data / "mods/lexeditor-second/Mod.cs").is_file()
    assert not (data / "mods/lexeditor-first").exists()


def test_distance_and_semantic_fade_are_independent_and_keep_custom_band(setup):
    _, data, _ = setup
    path = data / "interface.ini"
    path.write_text("[RecompOne]\nkf3.renderdistance=20.5\nkf3.renderdistance.fade=4.5\nother=keep\n")
    def save(changes):
        return MODEL.save_preferences(data, changes, MODEL.preferences(data)["fingerprint"])
    save({"kf3.renderdistance.fade": True})
    assert "kf3.renderdistance.fade=4.5\n" in path.read_text()
    save({"kf3.renderdistance": 24})
    assert "kf3.renderdistance.fade=4.5\n" in path.read_text()
    save({"kf3.renderdistance.fade": False})
    assert "kf3.renderdistance=24\n" in path.read_text()
    assert "kf3.renderdistance.fade=0\n" in path.read_text()
    save({"kf3.renderdistance.fade": True})
    assert "kf3.renderdistance.fade=3\n" in path.read_text()
    assert "other=keep\n" in path.read_text()
    for invalid in (-1, .5, 31, float("nan"), True):
        with pytest.raises(ValueError):
            save({"kf3.renderdistance": invalid})


def test_integer_boolean_settings_match_kf3_native_encoding(setup):
    _, data, _ = setup
    path = data / "interface.ini"
    MODEL.save_preferences(data, {"kf3.mouse.inverty": True}, MODEL.preferences(data)["fingerprint"])
    assert "kf3.mouse.inverty=1\n" in path.read_text()
    MODEL.save_preferences(data, {"kf3.mouse.inverty": False}, MODEL.preferences(data)["fingerprint"])
    assert "kf3.mouse.inverty=0\n" in path.read_text()


def test_kf2_disc_identity_is_not_accepted_as_kf3(setup):
    game, _, _ = setup
    (game / "content/config/kf3.json").write_text('{"game":{"id":"SLUS-00158","name":"KingsField2"}}')
    assert not MODEL.installation(game)["supported"]


def test_native_enable_flags_priorities_and_prior_values_are_restored(setup):
    game, data, library = setup
    path = data / "interface.ini"
    original = path.read_bytes()
    path.write_bytes(model.updated_ini(original, {"mods.z.enabled": "False", "mods.z.priority": "-7"}))
    before = path.read_bytes()
    z, a = mod(library, "z"), mod(library, "a")
    adapter = NativeSourceModAdapter(MODEL)
    adapter.activate([z, a], game)
    values = model.ini_values(path.read_text(encoding="utf-8-sig"))
    assert values["mods.z.enabled"] == "True" and values["mods.a.enabled"] == "True"
    assert values["mods.z.priority"] == "1" and values["mods.a.priority"] == "2"
    assert values["mods.external.map.priority"] == "17"
    adapter.activate([a, z], game)
    values = model.ini_values(path.read_text(encoding="utf-8-sig"))
    assert values["mods.a.priority"] == "1" and values["mods.z.priority"] == "2"
    adapter.activate([], game)
    assert path.read_bytes() == before


def test_interface_write_failure_restores_files_and_native_flags(setup, monkeypatch):
    game, data, library = setup
    first, second = mod(library, "first"), mod(library, "second")
    adapter = NativeSourceModAdapter(MODEL)
    adapter.activate([first], game)
    before = (data / "interface.ini").read_bytes()
    write = MODEL.atomic_write
    failed = False
    def fail_once(path, raw):
        nonlocal failed
        if path == data / "interface.ini" and not failed:
            failed = True
            raise OSError("synthetic interface write failure")
        write(path, raw)
    monkeypatch.setattr(MODEL, "atomic_write", fail_once)
    with pytest.raises(OSError, match="synthetic interface write failure"):
        adapter.activate([second], game)
    assert (data / "interface.ini").read_bytes() == before
    assert (data / "mods/lexeditor-first/Mod.cs").is_file()
    assert not (data / "mods/lexeditor-second").exists()
    assert not (data / RECOVERY).exists()


def test_private_native_fixture_helper_uses_adapter_and_refuses_player_paths(setup):
    import tempfile
    from prepare_native_fixture import prepare
    game, data, library = setup
    source = mod(library)
    with pytest.raises(ValueError, match="below %TEMP%"):
        prepare(game, data, [source])
    scratch = Path(tempfile.gettempdir()) / "lexeditor-dev"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kf3-loader-fixture-", dir=scratch) as name:
        private = Path(name)
        (private / "settings.json").write_bytes(b'{"customBindings":"keep"}')
        result = prepare(game, private, [source])
        values = model.ini_values((private / "interface.ini").read_text())
        assert values["mods.example.enabled"] == "True"
        assert values["mods.example.priority"] == "1"
        assert (private / "mods/lexeditor-example/Mod.cs").is_file()
        assert result["settingsJsonTouched"] is False


def test_plugin_smoke_is_isolated_from_live_player_data():
    from plugins.kings_field3.plugin import smoke
    assert smoke() == []


def test_settings_and_shared_mods_render_and_edit_without_player_data(setup, tmp_path):
    import threading
    from http.server import ThreadingHTTPServer
    from playwright.sync_api import sync_playwright
    from core.native_port_http import handler
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
    from paged_detail import reveal

    _, data, _ = setup
    app_root = Path(__file__).resolve().parents[2]
    class FixtureHandler(handler(MODEL, str(app_root / "plugins/kings_field3/server.py"))):
        def do_GET(self):
            from urllib.parse import urlparse
            path = urlparse(self.path).path
            if path.startswith("/plugins/blank/"):
                target = (app_root / path.lstrip("/")).resolve()
                if target.parent == app_root / "plugins/blank" and target.is_file():
                    self.send_file(target)
                    return
            super().do_GET()
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    settings = json.loads((Path(__file__).resolve().parents[2] / "ui/default_settings.json").read_text(encoding="utf-8"))
    settings.update(loadingTransitionMinimumSeconds=0, viewPreferences={})
    stub = """
    Object.defineProperty(navigator, 'getGamepads', {value:()=>[]});
    window.__nativeErrors=[];
    addEventListener('error', event=>window.__nativeErrors.push({message:event.message,file:event.filename,line:event.lineno,col:event.colno,stack:event.error?.stack}));
    window.pywebview={api:new Proxy({
      lexeditor_settings:async()=>SETTINGS,
      plugins:async()=>[], window_state:async()=>({maximized:false}),
      game_process_status:async()=>({running:false}),
      project_info:async()=>({canCreate:false,projects:[]}),
      mod_projects:async()=>({canCreate:false,projects:[]}),
      mod_library_status:async()=>({canManage:true,verified:false,packageTypes:['folder','zip']}),
      mods_overview:async()=>({rows:[],remote:[],lexmod:null,canManage:true,root:'isolated fixture'}),
      theme_sounds:async()=>({rows:[]})
    },{get:(target,name)=>target[name]||(async()=>false)})};
    """.replace("SETTINGS", "(" + json.dumps(settings) + ")")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = []
                responses = []
                page.on("response", lambda response: responses.append([response.url, response.status, response.request.resource_type]))
                page.on("pageerror", lambda error: errors.append(str(error) + error.stack))
                page.add_init_script(stub)
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                reach = page.get_by_label("View distance (tiles)", exact=True)
                try:
                    reach.wait_for(state="visible", timeout=5000)
                except Exception:
                    output = Path(__import__('tempfile').gettempdir()) / "lexeditor-dev/kf3-plugin-browser"
                    output.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(output / "failure.png"))
                    (output / "failure.html").write_text(page.content(), encoding="utf-8")
                    raise AssertionError({"errors": errors, "nativeErrors": page.evaluate('window.__nativeErrors'), "responses": responses, "body": page.inner_text("body"), "inputs": page.locator('input').count()})
                assert reach.input_value() == "16"
                fade = page.get_by_label("Smooth distance fade", exact=True)
                assert fade.is_checked()
                output = Path(__import__('tempfile').gettempdir()) / "lexeditor-dev/kf3-plugin-browser"
                output.mkdir(parents=True, exist_ok=True)
                page.locator(".lex-plugin-loading-screen").wait_for(state="hidden")
                page.screenshot(path=str(output / "settings-checked.png"))
                reach.fill("24")
                reach.dispatch_event("change")
                fade.uncheck()
                with page.expect_response(lambda response: response.url.endswith('/api/preferences') and response.request.method == 'POST') as saved_response:
                    page.get_by_role("button", name="Save changes", exact=True).click()
                assert saved_response.value.ok
                page.wait_for_function("document.querySelector('#global-save').disabled")
                text = (data / "interface.ini").read_text()
                assert "kf3.renderdistance=24\n" in text and "kf3.renderdistance.fade=0\n" in text
                page.locator(".lex-plugin-loading-screen").wait_for(state="hidden")
                output = Path(__import__('tempfile').gettempdir()) / "lexeditor-dev/kf3-plugin-browser"
                output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(output / "settings.png"))
                page.evaluate("settings => dispatchEvent(new CustomEvent('lexeditor-settings-changed', {detail:{...settings, booleanBoxStyle:false}}))", settings)
                assert fade.evaluate("node=>getComputedStyle(node).width") == "19px"
                page.screenshot(path=str(output / "settings-arrow.png"))
                page.set_viewport_size({"width": 640, "height": 480})
                page.wait_for_timeout(150)  # Let the shared pager refit after resize.
                reveal(page, reach)
                reveal(page, fade)
                assert reach.is_visible() and fade.is_visible()
                page.screenshot(path=str(output / "settings-small.png"))
                def header_is_contained():
                    return page.evaluate("""() => {
                      const row=document.querySelector('.lex-shell-command-row').getBoundingClientRect();
                      return [...document.querySelectorAll('.lex-shell-command-row button')].filter(node=>{
                        const b=node.getBoundingClientRect();
                        return b.width && b.height && (b.top<row.top-1 || b.bottom>row.bottom+1 || b.left<row.left-1 || b.right>row.right+1);
                      }).map(node=>node.getAttribute('aria-label'));
                    }""")
                assert header_is_contained() == []
                name = page.locator('.lex-project-name')
                assert name.inner_text() == 'Select a mod'
                assert name.evaluate('node=>node.scrollWidth<=node.clientWidth+1'), page.locator('.lex-project-select').evaluate("node=>({width:node.clientWidth,padding:getComputedStyle(node).padding,name:node.querySelector('.lex-project-name').getBoundingClientRect().toJSON(),path:getComputedStyle(node.querySelector('.lex-project-path')).display,container:node.closest('.lex-shell-left-actions').getBoundingClientRect().toJSON()})")
                assert not page.locator('.lex-project-path').is_visible()
                page.get_by_role("button", name="Open King's Field III Data Map", exact=True).click()
                page.get_by_text("Disc: SLUS-00255", exact=True).wait_for(state="visible")
                page.screenshot(path=str(output / "data-map-small.png"))
                page.locator('[data-tab="mods"]').click()
                page.get_by_text("Mods", exact=True).first.wait_for(state="visible")
                page.screenshot(path=str(output / "mods-small.png"))
                assert not errors
                # The same header sizing also serves Blank's existing gallery.
                page.goto(f"http://127.0.0.1:{server.server_port}/plugins/blank/editor.html")
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.locator('.lex-shell-command-row').wait_for(state='visible')
                page.locator('.lex-plugin-loading-screen').wait_for(state='hidden')
                page.wait_for_timeout(150)
                assert header_is_contained() == []
                assert page.locator('.lex-project-name').evaluate('node=>node.scrollWidth<=node.clientWidth+1')
                page.screenshot(path=str(output / "blank-header-small.png"))
                page.evaluate("document.documentElement.style.setProperty('--lex-ui-scale','1.5')")
                page.wait_for_timeout(150)
                assert header_is_contained() == []
                page.screenshot(path=str(output / "blank-header-small-150.png"))
                assert not errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
