"""Rendered native-rule editing and band split/merge with synthetic game data."""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_native_fixture import make_native_archive
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.stamina_rebalance import SETTINGS_FILE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def ready(page):
    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
    page.locator(".lex-plugin-loading-screen").wait_for(state="detached", timeout=60000)
    page.evaluate("document.fonts.ready")


def tab(page, name, target):
    page.get_by_text(name, exact=True).first.click()
    page.wait_for_function("""(tab)=>state.tab===tab && state.sub===tab && state.row &&
        key(state.row)===state.selected && !state.error &&
        (tab==='encumbrance' ? state.rows.length>=1 && state.row.id>=1001 :
         state.row.id===(tab==='misc'?0:100))""", arg=target)


def fill(page, key, value):
    field = page.locator(f'[data-field-key="{key}"]:visible')
    field.fill(str(value))
    field.press("Tab")
    page.wait_for_function(
        "([key,value])=>state.pending===0 && state.row.fields.find(f=>f.key===key)?.value===value",
        arg=[key, value])


def select_band(page, name, identity):
    # The movement selector intentionally has the same profile names as the bands.
    page.get_by_role("table").get_by_text(name, exact=True).click()
    page.wait_for_function("(id)=>state.row.id===id && !state.pending", arg=identity)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "lexeditor-dev" / "ds1-native"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ds1-native-browser-") as folder:
        root = Path(folder)
        game, mod = root / "game", root / "mod"
        source = make_native_archive()
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(source)
        mod.mkdir()
        (mod / MARKER).touch()
        env = {"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
               "LEXEDITOR_NO_MOD": "0", "LEXEDITOR_MOD_READ_ONLY": "0"}
        session = DS1Session(env)
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                launch = {"headless": True}
                if os.environ.get("LEXEDITOR_TEST_CHROMIUM"):
                    launch["executable_path"] = os.environ["LEXEDITOR_TEST_CHROMIUM"]
                browser = play.chromium.launch(**launch)
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    page.goto(session.url, wait_until="domcontentloaded")
                    ready(page)
                    tab(page, "Tweaks", "tweaks")
                    page.locator('[data-field-key="enabled"]').check()
                    page.wait_for_function("state.pending===0 && state.row.fields.find(f=>f.key==='enabled').value")
                    page.locator('[data-field-key="encumbranceEnabled"]').check()
                    page.wait_for_function("state.pending===0 && state.row.fields.find(f=>f.key==='encumbranceEnabled').value")
                    tab(page, "Misc.", "misc")
                    fill(page, "baseRecovery", 70)
                    page.screenshot(path=str(output / "misc.png"))
                    tab(page, "Encumbrance", "encumbrance")
                    assert page.evaluate("state.rows.length") == 4
                    fill(page, "upper", 30)
                    fill(page, "recovery", 115)
                    page.get_by_role("button", name="Add band", exact=True).click()
                    page.get_by_label("Split at (%)", exact=True).fill("12.5")
                    page.get_by_role("button", name="Create band", exact=True).click()
                    page.wait_for_function("!state.pending && !state.bandBusy && state.rows.length===5 && state.row.id===1005")
                    fill(page, "name", "Second light band")
                    fill(page, "recovery", 125)
                    assert page.locator('[data-field-key="movement"]').input_value() == "1"
                    page.screenshot(path=str(output / "band-added.png"))
                    page.get_by_role("button", name="Delete band", exact=True).click()
                    assert page.get_by_role("button", name="Merge and delete", exact=True).is_disabled()
                    page.get_by_label("Merge into", exact=True).select_option("1001")
                    page.get_by_label("Properties to keep", exact=True).select_option("neighbour")
                    page.set_viewport_size({"width": 1000, "height": 700})
                    page.screenshot(path=str(output / "merge-preview-small.png"))
                    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                    page.get_by_role("button", name="Merge and delete", exact=True).click()
                    page.wait_for_function("!state.pending && !state.bandBusy && state.rows.length===4 && state.row.id===1001")
                    assert page.evaluate("state.row.fields.find(f=>f.key==='upper').value") == 30
                    assert page.evaluate("state.row.fields.find(f=>f.key==='recovery').value") == 115
                    page.set_viewport_size({"width": 1440, "height": 900})
                    select_band(page, "Medium", 1002)
                    assert page.evaluate("state.row.fields.find(f=>f.key==='lower').value") == 30
                    fill(page, "upper", 60)
                    fill(page, "recovery", 90)
                    select_band(page, "Heavy", 1003)
                    fill(page, "upper", 120)
                    page.screenshot(path=str(output / "encumbrance.png"))
                    page.set_viewport_size({"width": 1000, "height": 700})
                    control = page.locator('[data-field-key="recovery"]:visible')
                    control.scroll_into_view_if_needed()
                    box = control.bounding_box()
                    assert box and box["y"] >= 0 and box["y"] + box["height"] <= 700
                    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                    page.screenshot(path=str(output / "encumbrance-small.png"))
                    page.locator("#global-save").click()
                    page.wait_for_function("state.dirty===0 && state.pending===0")
                    config = json.loads((mod / SETTINGS_FILE).read_text())["stamina-rebalance"]
                    assert config["baseRecovery"] == 70 and config["bands"][0]["upper"] == 30
                    assert config["bands"][2]["upper"] == 120 and config["bands"][0]["recovery"] == 115
                    assert config["nextBandId"] == 6
                    assert (game / RELATIVE).read_bytes() == source
                    page.reload(wait_until="domcontentloaded")
                    ready(page)
                    tab(page, "Misc.", "misc")
                    assert float(page.locator('[data-field-key="baseRecovery"]').input_value()) == 70
                    fill(page, "baseRecovery", 80)
                    page.evaluate("discard()")
                    page.wait_for_function("state.dirty===0 && state.row.fields[0].value===70")
                    page.evaluate("navigate('info')")
                    page.evaluate("""()=>{
                        state.deployment.everApplied=false;
                        state.deployment.changedExternally=false;
                        state.deployment.rebalance.native.backupOk=true;
                        render();
                    }""")
                    assert page.get_by_role("button", name="Restore original", exact=True).is_enabled()
                    session.stop()
                    session = DS1Session({**env, "LEXEDITOR_NO_MOD": "1", "LEXEDITOR_MOD_READ_ONLY": "1"})
                    session.start()
                    page.goto(session.url, wait_until="domcontentloaded")
                    ready(page)
                    tab(page, "Misc.", "misc")
                    control = page.locator('[data-field-key="baseRecovery"]')
                    assert control.is_disabled() and float(control.input_value()) == 45
                    tab(page, "Encumbrance", "encumbrance")
                    assert page.locator('[data-field-key="recovery"]').is_disabled()
                    assert page.get_by_role("button", name="Add band", exact=True).is_disabled()
                    assert page.get_by_role("button", name="Delete band", exact=True).is_disabled()
                    assert not errors, errors
                except Exception:
                    traceback.print_exc()
                    try:
                        page.screenshot(path=str(output / "failure.png"), timeout=5000)
                    except Exception:
                        pass
                    raise
                finally:
                    browser.close()
        finally:
            session.stop()
    print(json.dumps({"passed": True, "synthetic": True, "screenshots": str(output), "errors": errors}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
