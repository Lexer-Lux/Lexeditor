"""Exercise the rendered stamina editor with synthetic data only."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_stamina_fixture import make_stamina_archive
from plugins.ds1.stamina import StaminaDocument, EFFECT_TABLE
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright


def open_stamina(page):
    page.get_by_text("Stamina", exact=True).first.click()
    page.wait_for_function("state.tab==='stamina' && state.row && !state.error")


def select_effect(page, row_id):
    page.get_by_role("searchbox", name="Search effects").fill(str(row_id))
    page.wait_for_function("(id)=>state.row?.id===id && key(state.row)===state.selected", arg=row_id)


def set_recovery(page, value):
    control = page.locator('input[data-field-key="staminaRecoverChangeSpeed"]:visible')
    control.fill(str(value))
    control.press("Tab")
    page.wait_for_function(
        "(value)=>state.pending===0 && state.row?.fields[0].value===value", arg=value)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(tempfile.gettempdir()) / "lexeditor-dev" / "ds1-stamina")
    output.mkdir(parents=True, exist_ok=True)
    raw = make_stamina_archive()
    errors = []
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-stamina-ui-") as folder:
        root = Path(folder)
        game, mod = root / "game", root / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        mod.mkdir()
        (mod / MARKER).touch()
        env = {"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
               "LEXEDITOR_NO_MOD": "0", "LEXEDITOR_MOD_READ_ONLY": "0"}
        session = DS1Session(env)
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    open_stamina(page)
                    assert page.locator("[data-subtab]").evaluate_all(
                        "nodes=>nodes.map(n=>n.dataset.subtab)") == [
                        "stamina-equipment", "stamina-armor", "stamina-player", "stamina-all"]
                    select_effect(page, 6890)
                    control = page.locator('input[data-field-key="staminaRecoverChangeSpeed"]')
                    assert float(control.input_value().replace(",", "")) == 10
                    assert control.get_attribute("min") == "-100"
                    assert control.get_attribute("max") == "100"
                    assert control.get_attribute("step") == "1"
                    set_recovery(page, 4)
                    assert request_json(session.url + "api/row?table=SpEffectParam&id=6890")["row"]["fields"][0]["value"] == 4
                    page.screenshot(path=str(output / "grass-crest.png"))
                    control.fill("101")
                    control.press("Tab")
                    assert not control.evaluate("node=>node.checkValidity()")
                    assert request_json(session.url + "api/row?table=SpEffectParam&id=6890")["row"]["fields"][0]["value"] == 4
                    set_recovery(page, 4)
                    page.locator('[data-subtab="stamina-armor"]').click()
                    page.wait_for_function("state.sub==='stamina-armor' && state.row?.id===6200")
                    set_recovery(page, -1)
                    assert "not an equip-load percentage tier" in page.evaluate("state.row.staminaContext")
                    page.set_viewport_size({"width": 1000, "height": 700})
                    page.wait_for_timeout(200)
                    control = page.locator('input[data-field-key="staminaRecoverChangeSpeed"]:visible')
                    box = control.bounding_box()
                    assert box and 0 <= box["y"] and box["y"] + box["height"] <= 700, box
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.screenshot(path=str(output / "armour-small.png"))
                    page.locator('[data-subtab="stamina-player"]').click()
                    page.wait_for_function("state.sub==='stamina-player' && state.row?.id===40")
                    assert "not the engine's base recovery" in page.evaluate("state.row.staminaContext")
                    page.locator("#global-save").click()
                    page.wait_for_function("state.pending===0 && state.dirty===0")
                    saved = StaminaDocument((mod / RELATIVE).read_bytes())
                    assert saved.read_row(EFFECT_TABLE, 6890)["fields"][0]["value"] == 4
                    assert saved.read_row(EFFECT_TABLE, 6200)["fields"][0]["value"] == -1
                    assert saved.read_row(EFFECT_TABLE, 2013)["fields"][0]["value"] == 0
                    assert (game / RELATIVE).read_bytes() == raw
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    open_stamina(page)
                    select_effect(page, 6890)
                    assert float(page.locator('input[data-field-key="staminaRecoverChangeSpeed"]').input_value().replace(",", "")) == 4
                    # Inspect the item's actual effect link through the paged details.
                    page.get_by_text("Items", exact=True).first.click()
                    page.locator('[data-subtab="weapons"]').click()
                    page.wait_for_function("state.row?.table==='EquipParamWeapon' && state.row.id===100")
                    link = page.get_by_role("button", name="Grass Crest Shield: 4", exact=True)
                    for _ in range(40):
                        if link.count() and link.is_visible():
                            break
                        next_page = page.locator(".lex-tweaks-pages").get_by_role(
                            "button", name="Next page", exact=True)
                        assert next_page.count() and next_page.is_enabled(), "Recovery link is not reachable"
                        next_page.click()
                    assert link.is_visible()
                    link.click()
                    page.wait_for_function("state.tab==='stamina' && state.row?.id===6890 && !state.error")
                    page.screenshot(path=str(output / "linked-effect.png"))
                    session.stop()
                    session = DS1Session({**env, "LEXEDITOR_NO_MOD": "1",
                                          "LEXEDITOR_MOD_READ_ONLY": "1"})
                    session.start()
                    vanilla = browser.new_page(viewport={"width": 1280, "height": 800})
                    vanilla.on("pageerror", lambda error: errors.append(str(error)))
                    vanilla.goto(session.url + "?lexNoMod=1")
                    vanilla.wait_for_selector('body[data-ds1-ready="true"]')
                    open_stamina(vanilla)
                    select_effect(vanilla, 6890)
                    assert vanilla.locator('input[data-field-key="staminaRecoverChangeSpeed"]').is_disabled()
                    assert float(vanilla.locator('input[data-field-key="staminaRecoverChangeSpeed"]').input_value().replace(",", "")) == 10
                    assert (game / RELATIVE).read_bytes() == raw
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print(json.dumps({"passed": True, "synthetic": True,
                      "source_sha256": hashlib.sha256(raw).hexdigest(),
                      "screenshots": str(output), "errors": errors}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
