"""Persistence, preservation and native library selection for King's Field I."""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from plugins.kf1 import settings
from plugins.kf1.mod_support import Kf1ModAdapter


@pytest.fixture
def port(tmp_path, monkeypatch):
    root = tmp_path / "port"
    root.mkdir()
    assembly = b"synthetic supported assembly"
    (root / "KingsField1.dll").write_bytes(assembly)
    (root / "lexeditor-port.json").write_text(json.dumps({"game": "kf1", "settingsVersion": 1, "assemblySha256": sha256(assembly).hexdigest()}))
    (root / "interface.ini").write_text("[RecompOne]\nunknown.setting=keep\nkf1.renderdistance=16\nkf1.renderdistance.fade=3\n\n[Window][Game]\nPos=1,2\n")
    (root / "settings.json").write_text(json.dumps({"CdPath": "user-disc.cue", "CardAPath": "my-save.sav", "Keys": {"Cross": "Tab"}, "unknown": 42}))
    (root / "carda.sav").write_bytes(b"SAVE-DO-NOT-CHANGE")
    monkeypatch.setenv("LEXEDITOR_KF1_ROOT", str(root))
    monkeypatch.setattr(settings, "live_processes", lambda names: [])
    return root


def change(values, **updates):
    return {**values, **updates}


def test_distance_and_fade_are_independent_and_preserve_native_files(port):
    for distance, fade in ((8, False), (30, False), (30, True), (8, True), (0, True)):
        state = settings.payload()
        values = {field["id"]: field["value"] for field in state["sections"][0]["fields"]}
        values.update({"kf1.renderdistance": distance, "kf1.renderdistance.fade": fade})
        saved = settings.save({"sha256": state["sha256"], "values": values})
        actual = {field["id"]: field["value"] for field in saved["sections"][0]["fields"]}
        assert actual["kf1.renderdistance"] == distance
        assert actual["kf1.renderdistance.fade"] is fade
    text = (port / "interface.ini").read_text()
    assert "unknown.setting=keep" in text
    assert "[Window][Game]\nPos=1,2" in text
    assert (port / "carda.sav").read_bytes() == b"SAVE-DO-NOT-CHANGE"
    assert len(list(port.glob("interface.ini.lexeditor-*"))) == 2


def test_stale_saves_and_live_game_are_refused(port, monkeypatch):
    state = settings.payload()
    values = {field["id"]: field["value"] for field in state["sections"][0]["fields"]}
    (port / "interface.ini").write_text("[RecompOne]\nchanged=elsewhere\n")
    before = (port / "interface.ini").read_bytes()
    with pytest.raises(ValueError, match="changed"):
        settings.save({"sha256": state["sha256"], "values": values})
    monkeypatch.setattr(settings, "live_processes", lambda names: [{"pid": "1"}])
    with pytest.raises(ValueError, match="running"):
        settings.write_settings(port, {"kf1.renderdistance": "30"})
    assert (port / "interface.ini").read_bytes() == before


def test_changing_distance_keeps_the_existing_native_fade_band(port):
    (port / "interface.ini").write_text("[RecompOne]\nkf1.renderdistance=16\nkf1.renderdistance.fade=1.5\n")
    state = settings.payload()
    values = {field["id"]: field["value"] for field in state["sections"][0]["fields"]}
    values["kf1.renderdistance"] = 24
    settings.save({"sha256": state["sha256"], "values": values})
    assert settings.parse_ini((port / "interface.ini").read_bytes())["kf1.renderdistance.fade"] == "1.5"


@pytest.mark.parametrize("distance", [-1, 1, 7.9, 31, float("nan"), True])
def test_invalid_distance_is_rejected(port, distance):
    state = settings.payload()
    values = {field["id"]: field["value"] for field in state["sections"][0]["fields"]}
    values["kf1.renderdistance"] = distance
    with pytest.raises(ValueError):
        settings.save({"sha256": state["sha256"], "values": values})


def test_controls_preserve_saves_and_other_settings(port):
    before = settings.payload()
    settings.write_settings(port, {"kf1.pad.layout": "1", "kf1.controls.holdrun": "1"}, expected=before["sha256"], controls=True)
    config = json.loads((port / "settings.json").read_text())
    assert config["CdPath"] == "user-disc.cue"
    assert config["CardAPath"] == "my-save.sav"
    assert config["unknown"] == 42
    assert config["Keys"] == {"Cross": "Tab", "Circle": "E", "R3": "ShiftLeft"}
    assert config["Pad"]["Square"] == [10, 101]
    assert config["Pad"]["Triangle"] == [9, 100, 2]
    assert config["Pad"]["R3"] == [1]
    assert (port / "carda.sav").read_bytes() == b"SAVE-DO-NOT-CHANGE"


def test_native_mod_library_activation_and_removal_need_no_copies(port, tmp_path):
    library = tmp_path / "library"
    mods = []
    for name in ("first", "second"):
        folder = library / name
        folder.mkdir(parents=True)
        (folder / "mod.json").write_text(json.dumps({"id": name, "name": name}))
        (folder / "Test.cs").write_text("// synthetic source")
        mods.append(folder)
    adapter = Kf1ModAdapter()
    adapter.activate(mods, port)
    assert sorted(adapter.active_mod_ids(port)) == ["first", "second"]
    assert not (port / "mods").exists()
    adapter.activate([], port)
    assert adapter.active_mod_ids(port) == []
    assert (mods[0] / "Test.cs").is_file()
    (mods[1] / "mod.json").write_text(json.dumps({"id": "first", "name": "duplicate"}))
    assert len(adapter.conflicts(mods, port)) == 2
    with pytest.raises(ValueError, match="Two enabled"):
        adapter.activate(mods, port)


def test_unknown_port_build_is_refused(port):
    (port / "KingsField1.dll").write_bytes(b"changed")
    with pytest.raises(ValueError, match="assembly changed"):
        settings.payload()


def test_ini_without_final_newline_keeps_other_sections():
    original = b"[Window][Game]\nPos=1,2"
    saved = settings.update_ini(original, {"kf1.renderdistance": "30"})
    assert settings.parse_ini(saved)["kf1.renderdistance"] == "30"
    assert saved.endswith(original)


def test_native_ini_keys_are_case_insensitive():
    saved = settings.update_ini(b"[RecompOne]\nKF1.RenderDistance=16\n", {"kf1.renderdistance": "24"})
    assert settings.parse_ini(saved) == {"kf1.renderdistance": "24"}
    with pytest.raises(ValueError, match="Duplicate"):
        settings.parse_ini(b"[RecompOne]\nKF1.RenderDistance=16\nkf1.renderdistance=24\n")


def test_rendered_settings_save_and_reload(port):
    import threading
    from http.server import ThreadingHTTPServer
    from plugins.kf1.server import Handler
    playwright_api = pytest.importorskip("playwright.sync_api")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with playwright_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 800, "height": 600})
                page.add_init_script("Object.defineProperty(navigator,'getGamepads',{value:()=>[]})")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')")
                field = page.get_by_role("spinbutton", name="View distance (cells)", exact=True)
                field.fill("24")
                page.get_by_role("checkbox", name="Smooth distance fade", exact=True).uncheck()
                with page.expect_response(lambda response: response.url.endswith("/api/settings") and response.request.method == "POST") as response:
                    page.get_by_role("button", name="Save changes", exact=True).click()
                assert response.value.status == 200
                page.reload()
                field.wait_for()
                assert field.input_value() == "24"
                assert not page.get_by_role("checkbox", name="Smooth distance fade", exact=True).is_checked()
                page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')")
                page.get_by_role("button", name="Apply Lexer's controls", exact=True).click()
                page.wait_for_timeout(250)
                assert json.loads((port / "settings.json").read_text())["Keys"]["Circle"] == "E"
                assert not errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
