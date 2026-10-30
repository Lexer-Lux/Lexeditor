"""Duplicate and remove records and placements in the browser, never game files."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_text_archive
from msb_fixture import build_msb
from plugins.ds1 import texts
from plugins.ds1.formats import ItemDocument
from plugins.ds1.msb import MAP_DIR, MsbDocument
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

MAP = "m10_00_00_00.msb"


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    raw = make_archive()
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-add-remove-") as folder:
        temp = Path(folder)
        game, mod = temp / "game", temp / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / MAP_DIR / MAP).parent.mkdir(parents=True)
        (game / MAP_DIR / MAP).write_bytes(build_msb())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0", "LEXEDITOR_MOD_READ_ONLY": "0"})
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
                    # Items: duplicate a goods row, save, reload, remove.
                    page.locator(".lex-list-row").first.click()
                    page.wait_for_function("!!state.row && !state.error")
                    page.locator('[data-row-action="duplicate"]').click()
                    page.wait_for_function(
                        'state.selected==="EquipParamGoods:103" && state.row?.id===103 && !state.rowBusy && !state.error')
                    assert page.evaluate("state.rows.some(r=>r.id===103)")
                    if output:
                        page.screenshot(path=str(output / "add-remove-items.png"))
                    page.locator("#global-save").click()
                    page.wait_for_function("state.dirty===0 && state.pending===0")
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.wait_for_function('state.rows.some(r=>r.id===103)')
                    assert ItemDocument((mod / RELATIVE).read_bytes()).value(
                        "EquipParamGoods", 103, "sellValue") == ItemDocument(raw).value(
                        "EquipParamGoods", 100, "sellValue")
                    # Consumables shows goods 100 plus the duplicate, ID order.
                    page.wait_for_function("document.querySelectorAll('.lex-list-row:not(.lex-filler-row)').length===2")
                    page.locator('.lex-list-row[data-key="EquipParamGoods:103"]').click()
                    page.wait_for_function("state.row?.id===103 && !state.error")
                    page.locator('[data-row-action="remove"]').click()
                    page.locator(".lex-dialog").get_by_role("button", name="Remove").click()
                    page.wait_for_function("!state.rows.some(r=>r.id===103) && !state.rowBusy && !state.error")
                    page.locator("#global-save").click()
                    page.wait_for_function("state.dirty===0 && state.pending===0")
                    # Maps: duplicate a placement, move it, save, reload, remove.
                    page.locator('[data-tab="maps"]').click()
                    page.locator('[data-tabstrip-id="placements"]').click()
                    page.wait_for_function('state.mapTab==="placements"')
                    page.wait_for_function(
                        'state.tab==="maps" && state.rows.some(r=>r.id==="2:0") && !state.error')
                    page.wait_for_function("document.querySelectorAll('[data-maps-side] .lex-list-row').length===4")
                    first = page.locator('.lex-list-row[data-key="%s:2:0"]' % MAP)
                    assert first.inner_text().split() == ["Rat"]
                    first.click()
                    page.wait_for_function('state.row?.id==="2:0" && !state.error')
                    page.locator('[data-row-action="duplicate"]').click()
                    page.wait_for_function(
                        'state.selected==="m10_00_00_00.msb:2:1" && state.row?.id==="2:1" && !state.rowBusy && !state.error')
                    if output:
                        page.screenshot(path=str(output / "add-remove-maps.png"))
                    page.locator("#global-save").click()
                    page.wait_for_function("state.dirty===0 && state.pending===0")
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="maps"]').click()
                    page.locator('[data-tabstrip-id="placements"]').click()
                    page.wait_for_function('state.mapTab==="placements"')
                    page.wait_for_function(
                        'state.tab==="maps" && state.rows.some(r=>r.id==="2:1") && !state.error')
                    assert len(MsbDocument((mod / MAP_DIR / MAP).read_bytes()).placements()) == 5
                    page.wait_for_function("document.querySelectorAll('[data-maps-side] .lex-list-row').length===5")
                    dupe = page.locator('.lex-list-row[data-key="%s:2:1"]' % MAP)
                    assert dupe.inner_text().split() == ["Rat"]
                    dupe.click()
                    page.wait_for_function('state.row?.id==="2:1" && !state.error')
                    page.locator('[data-row-action="remove"]').click()
                    page.locator(".lex-dialog").get_by_role("button", name="Remove").click()
                    page.wait_for_function(
                        '!state.rows.some(r=>r.id==="2:1") && !state.rowBusy && !state.error')
                    page.locator("#global-save").click()
                    page.wait_for_function("state.dirty===0 && state.pending===0")
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="maps"]').click()
                    page.locator('[data-tabstrip-id="placements"]').click()
                    page.wait_for_function('state.mapTab==="placements"')
                    page.wait_for_function(
                        'state.tab==="maps" && !state.rows.some(r=>r.id==="2:1") && !state.error')
                    assert not errors, errors
                finally:
                    browser.close()
            assert (game / RELATIVE).read_bytes() == raw
            assert (game / MAP_DIR / MAP).read_bytes() == build_msb()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 record and placement add/remove passed.")


if __name__ == "__main__":
    main()
