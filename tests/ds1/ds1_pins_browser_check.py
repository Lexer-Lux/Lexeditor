"""Pinned columns and pin buttons update at once, never on the next page turn.

Every rendered detail field carries exactly one pin button, including fields
on lazily rendered panel tabs. Clicking one marks it pressed and adds its
master column immediately; editing the property repaints the master cell
immediately; clicking again removes the column immediately. Synthetic
fixtures only; edits land in the temp mod.
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ds1"))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import expect, sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-pins-") as folder:
        temp = Path(folder)
        game, mod = temp / "game", temp / "mod"
        spells = list(range(1000, 1213))
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive(table_ids={'Magic': spells},
            field_values={'Magic': {identity: {'slotLength': identity % 20 + 1} for identity in spells}}))
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive(names={
            'Magic': {identity: f'Test Spell {identity}' for identity in spells}}))
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game),
                              "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0",
                              "LEXEDITOR_MOD_READ_ONLY": "0"})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-subtab="armor"]').click()
                    page.wait_for_function("state.sub==='armor' && state.row")
                    page.wait_for_timeout(300)
                    fields = page.locator(".lex-detail-panel .lex-detail-field").count()
                    pins = page.locator(".lex-detail-panel .lex-detail-field [data-lex-auto-pin]").count()
                    assert fields > 0 and pins == fields, (fields, pins)
                    page.locator(".lex-tabbed-panel [role=tab]",
                                 has_text="Defense").first.click()
                    page.wait_for_function("state.itemTab==='defense'")
                    page.wait_for_timeout(300)
                    fields = page.locator(".lex-detail-panel .lex-detail-field").count()
                    pins = page.locator(".lex-detail-panel .lex-detail-field [data-lex-auto-pin]").count()
                    assert fields > 0 and pins == fields, (fields, pins)
                    pin = page.locator("[data-lex-auto-pin][data-lex-pin-column='defensePhysics']")
                    assert pin.count() == 1
                    assert pin.get_attribute("aria-pressed") == "false"
                    pin.click()
                    page.wait_for_function(
                        "JSON.parse(localStorage.getItem('lexeditor:pins:ds1-items-armor')||'[]')"
                        ".some(e=>e.key==='defensePhysics')")
                    assert pin.get_attribute("aria-pressed") == "true"
                    cell = (".lex-column-list-row[data-key] > "
                            ".lex-column-list-cell[data-column-key='pin:defensePhysics']")
                    page.wait_for_selector(cell)
                    assert page.locator(cell).first.inner_text() == "0"
                    control = page.locator('[data-field-key="defensePhysics"]:visible')
                    assert control.count() == 1
                    control.first.fill("13")
                    control.first.press("Tab")
                    page.wait_for_function("state.pending===0")
                    page.wait_for_function(
                        "()=>[...document.querySelectorAll(\"" + cell + "\")]"
                        ".some(c=>c.innerText.trim()==='13')")
                    assert page.locator(cell).first.inner_text() == "13"
                    pin.click()
                    page.wait_for_function(
                        "!JSON.parse(localStorage.getItem('lexeditor:pins:ds1-items-armor')||'[]')"
                        ".some(e=>e.key==='defensePhysics')")
                    assert pin.get_attribute("aria-pressed") == "false"
                    assert page.locator(cell).count() == 0
                    box = page.locator(
                        '[data-lex-bottom-search="ds1-records-search"]')
                    box.fill("13")
                    expect(page.locator(".lex-column-list .lex-list-row[data-key]")).to_have_count(1, timeout=10000)
                    box.fill("")
                    expect(page.locator(".lex-column-list .lex-list-row[data-key]")).to_have_count(3, timeout=10000)
                    # A pinned header follows the detail field's rename: the
                    # rename resolves under the bare label both show, then the
                    # unit suffix re-attaches, so the two never diverge.
                    page.evaluate("navigate('items','weapons')")
                    page.wait_for_function("state.sub==='weapons' && state.row")
                    page.locator(".lex-tabbed-panel [role=tab]",
                                 has_text="Defense").first.click()
                    page.wait_for_function("state.itemTab==='defense'")
                    label = page.locator(
                        '//*[@data-field-key="poisonGuardResist"]'
                        '/ancestor::*[contains(concat(" ", @class, " "), " lex-detail-field ")][1]'
                        '//*[contains(@class,"lex-detail-field-label-text")]')
                    expect(label).to_have_text("Poison guard")
                    pin = page.locator(
                        "[data-lex-auto-pin][data-lex-pin-column='poisonGuardResist']")
                    pin.click()
                    heads = page.locator(".lex-column-list-head-cell")
                    match = heads.filter(has_text="Poison guard (%)")
                    assert match.count() >= 1
                    assert "Poison guard (%)" in match.first.inner_text()
                    page.evaluate("""() => {
                      const tab = document.querySelector(
                        ".lex-shell-header nav button.active")?.dataset.tab;
                      const key = `${document.body.dataset.lexPlugin}-${tab}`
                        + ".field.Poison guard.label";
                      localStorage.setItem(key, "Venom");
                      render();
                    }""")
                    page.wait_for_function("state.sub==='weapons' && state.row")
                    expect(label).to_have_text("Venom")
                    match = heads.filter(has_text="Venom (%)")
                    assert match.count() >= 1, heads.all_inner_texts()
                    assert "Venom (%)" in match.first.inner_text()
                    # The reported freeze used 213 spells in six tables, with
                    # attunement slots pinned. A pin must preserve the mounted
                    # detail field, and revisiting the tab must keep its column.
                    page.set_viewport_size({'width': 2560, 'height': 1352})
                    page.evaluate('navigate("items","spells")')
                    page.locator('.lex-tabbed-panel [role=tab]', has_text='Requirements').first.click()
                    page.wait_for_selector('[data-field-key="slotLength"]')
                    assert page.evaluate('state.rows.length') == 213
                    for index in range(5):
                        page.get_by_role('button', name='Increase table barrels', exact=True).evaluate('node=>node.click()')
                        page.wait_for_function('count=>document.querySelectorAll(".lex-barrel-grid .lex-column-list").length===count',
                                               arg=index + 2)
                    page.evaluate('window.originalSlotField=document.querySelector("[data-field-key=slotLength]")')
                    started = time.perf_counter()
                    page.locator('[data-lex-auto-pin][data-lex-pin-column="slotLength"]').click(force=True)
                    page.wait_for_selector('.lex-column-list-cell[data-column-key="pin:slotLength"]')
                    page.evaluate('async()=>{await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)}')
                    assert time.perf_counter() - started < 8, 'Pinning reproduced the reported multi-second freeze'
                    assert page.evaluate('originalSlotField===document.querySelector("[data-field-key=slotLength]")')
                    for _ in range(3):
                        page.evaluate('navigate("items","armor")')
                        started = time.perf_counter()
                        page.evaluate('navigate("items","spells")')
                        page.wait_for_selector('.lex-column-list-cell[data-column-key="pin:slotLength"]')
                        assert time.perf_counter() - started < 8, 'Returning to pinned spells froze the editor'
                        assert page.locator('.lex-barrel-grid .lex-column-list').count() == 6
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 pins passed.")


if __name__ == "__main__":
    main()
