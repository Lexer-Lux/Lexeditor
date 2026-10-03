"""Injector settings reject raw invalid drafts, including hidden detail pages."""
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from plugins.ff7r2.plugin import Ff7r2Session
from plugins.ff7r2 import shader_injector as si

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from paged_detail import reveal


def test_injector_integer_float_drafts_and_real_ini_save(tmp_path):
    game = tmp_path / "game"
    folder = game / si.INSTALL_FOLDER
    folder.mkdir(parents=True)
    ini = folder / si.INI
    original = "[InjectorSettings]\nMenuScale=1\n[ShaderDiscovery]\nWorkerThreads=0\n[Custom]\nKeep=untouched\n"
    ini.write_text(original)
    project = tmp_path / "project"
    project.mkdir()
    requests, errors = [], []
    with Ff7r2Session({"LEXEDITOR_FF7R2_ROOT": str(game), "LEXEDITOR_FF7R2_PROJECT": str(project)}) as session:
        with sync_playwright() as play:
            browser = play.chromium.launch(executable_path=shutil.which("chromium") or None, headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: requests.append(request.url) if request.method == "POST" else None)
                page.goto(session.url, wait_until="domcontentloaded")
                page.locator(".lex-plugin-loading-screen").wait_for(state="detached")
                page.evaluate("tweakTab='injector';navigate('tweaks')")
                for label, section, key, invalid, valid in [
                    ("Worker threads", "ShaderDiscovery", "WorkerThreads", ["1.5", "65", "-1", ""], "64"),
                    ("Menu scale", "InjectorSettings", "MenuScale", ["0.49", "4.01", ""], "1.125"),
                ]:
                    control = page.get_by_label(label, exact=True)
                    reveal(page, control)
                    assert control.get_attribute("type") == "number"
                    assert control.get_attribute("step") == ("1" if key == "WorkerThreads" else "any")
                    saved = page.evaluate("([s,k])=>injectorDraft[s][k]", [section, key])
                    for raw in invalid:
                        reveal(page, control).fill(raw)
                        assert page.evaluate("([s,k])=>injectorDraft[s][k]", [section, key]) == saved
                        assert page.evaluate("injectorDirty()")
                        page.evaluate("render()")
                        assert reveal(page, control).input_value() == raw
                        page.evaluate("tweakTab='reshade';render()")
                        page.evaluate("injectorAction('settings',{changes:injectorDraft})")
                        assert not any("/api/shader-injector/settings" in url for url in requests)
                        assert ini.read_text() == original
                        page.evaluate("tweakTab='injector';render()")
                        assert reveal(page, control).input_value() == raw
                    reveal(page, page.get_by_role("button", name="Revert", exact=True)).click()
                    assert not page.evaluate("injectorDirty()")
                    assert reveal(page, control).input_value() == str(saved)
                    reveal(page, control).fill(valid)
                    reveal(page, page.get_by_role("button", name="Save settings", exact=True)).click()
                    page.wait_for_function("!injectorBusy&&!injectorDirty()")
                    assert si.read_settings(folder)["values"][section][key] == float(valid)
                    assert "Keep=untouched" in ini.read_text()
                    page.evaluate("loadInjector()")
                    page.evaluate("render()")
                    assert float(reveal(page, control).input_value()) == float(valid)
                    # The next independent invalid-draft case starts with the saved file.
                    original = ini.read_text()
                    requests.clear()
                assert not errors
            finally:
                browser.close()
