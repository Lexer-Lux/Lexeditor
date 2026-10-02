"""Real shared-component ammunition controls and settings API; no retail assets."""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from plugins.ds1.ammunition_tweak import SETTING_FILE
from plugins.ds1.ammunition_controls import TWEAK_ID, EXECUTABLE, LABEL
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-ammunition-ui-") as folder:
        temp = Path(folder)
        game, mod = temp / "game", temp / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        raw = make_archive()
        (game / RELATIVE).write_bytes(raw)
        (mod / RELATIVE).parent.mkdir(parents=True)
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game),
                              "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0", "LEXEDITOR_MOD_READ_ONLY": "0"})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1280, "height": 800})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.evaluate('navigate("tweaks")')
                    page.wait_for_function('state.tab==="tweaks" && state.tweaks && !state.error')
                    box = page.get_by_role("checkbox", name=LABEL, exact=True)
                    assert not box.is_checked()
                    assert not (mod / SETTING_FILE).exists()
                    assert page.get_by_role("button", name="Apply", exact=True).is_disabled()
                    assert page.get_by_role("button", name="Restore original", exact=True).is_disabled()
                    box.check()
                    page.wait_for_function("state.pending===0 && tweakDirty()===1")
                    assert not (mod / SETTING_FILE).exists()
                    page.evaluate("save()")
                    page.wait_for_function("tweakDirty()===0")
                    assert json.loads((mod / SETTING_FILE).read_text())[TWEAK_ID] is True
                    assert not (game / EXECUTABLE).exists(), "Save must not install an executable"
                    assert not (mod / RELATIVE).exists(), "Tweak-only saves must not create a param override"
                    box.uncheck()
                    page.wait_for_function("state.pending===0 && tweakDirty()===1")
                    page.evaluate("discard()")
                    page.wait_for_function("tweakDirty()===0 && state.tweaks.enabled===true")
                    assert box.is_checked()
                    assert not (mod / RELATIVE).exists()
                    archive = mod / RELATIVE
                    archive.write_bytes(raw)
                    os.utime(archive, (1600000000, 1600000000))
                    stamp = archive.stat().st_mtime_ns
                    for enabled in (False, True):
                        box.set_checked(enabled)
                        page.wait_for_function("state.pending===0 && tweakDirty()===1")
                        page.evaluate("save()")
                        page.wait_for_function("tweakDirty()===0")
                        assert json.loads((mod / SETTING_FILE).read_text())[TWEAK_ID] is enabled
                        assert archive.read_bytes() == raw
                        assert archive.stat().st_mtime_ns == stamp
                    if output:
                        page.screenshot(path=str(output / "ammunition-missing-executable.png"))
                    # Only the deployment-status presentation is simulated here.
                    # This is not native game or executable deployment acceptance.
                    page.evaluate("""() => {
                        state.tweaks={...state.tweaks,available:true,applied:true,
                          backupOk:true,problem:"",windows:true};render();
                    }""")
                    assert page.get_by_role("button", name="Apply", exact=True).is_enabled()
                    assert page.get_by_role("button", name="Restore original", exact=True).is_enabled()
                    for width, height, scale in ((1280,800,1),(900,650,1),(900,650,1.25)):
                        page.set_viewport_size({"width":width,"height":height})
                        page.evaluate("(scale)=>{document.documentElement.style.zoom=scale;render()}",scale)
                        assert box.is_visible()
                        bounds=box.bounding_box()
                        assert bounds and bounds["x"]>=0 and bounds["y"]>=0
                        assert bounds["x"]+bounds["width"]<=width
                        if output:
                            page.screenshot(path=str(output / f"ammunition-{width}-{scale}-simulated.png"))
                    page.evaluate("state.readOnly=true;render()")
                    assert box.is_disabled()
                    assert page.get_by_role("button", name="Apply", exact=True).is_disabled()
                    assert page.get_by_role("button", name="Restore original", exact=True).is_enabled()
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
        assert (game / RELATIVE).read_bytes() == raw
        assert (mod / RELATIVE).read_bytes() == raw
    print("ds1 ammunition API/shared UI checks passed; native rendering is not tested")


if __name__ == "__main__":
    main()
