"""Directory Local filter: only the open map's rows, never game files.

Two maps share one enemy NPC; only map A drops lot 100. Local keeps the
open map's enemies and lots, follows map switches, composes with search,
and stays disabled where rows name no map (shops, treasure).
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ds1"))
from ds1_fixture import make_archive
from msb_fixture import build_msb
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

MAP_A = "m10_00_00_00.msb"
MAP_B = "m10_01_00_00.msb"


def dir_rows(page):
    return page.locator("[data-maps-dir] .lex-list-row").count()


def open_maps(page, session):
    page.goto(session.url)
    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
    page.locator('button[data-tab="maps"]').click()
    page.wait_for_function('state.tab==="maps" && state.mapView && state.rows.length>0 && !state.error',
                          timeout=60000)


def main():
    raw = make_archive(field_values={"NpcParam": {120000: {"itemLotId_1": 100}}})
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-dir-local-") as folder:
        temp = Path(folder)
        game = temp / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / MAP_A).write_bytes(build_msb(parts=(("enemy", 2, 0, 0, 120000),
                                                              ("enemy", 2, 1, 0, 120100))))
        (game / MAP_DIR / MAP_B).write_bytes(build_msb(parts=(("enemy", 2, 0, 0, 120100),)))
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1",
                              "LEXEDITOR_MOD_READ_ONLY": "1"})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    open_maps(page, session)
                    assert page.evaluate("state.mapId") == MAP_A
                    box = page.locator("[data-dir-local] input")
                    assert page.locator(".lex-pager [data-dir-local]").count() == 1
                    assert page.locator("[data-maps-dir] .lex-pager-stacked").count() == 1
                    page.locator("[data-maps-dir] .lex-subtab-button", has_text="Enemies").click()
                    page.wait_for_function('state.dirTab==="enemies"', timeout=30000)
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===3",
                        timeout=30000)
                    assert dir_rows(page) == 3
                    assert not box.is_disabled()
                    box.check()
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===2",
                        timeout=30000)
                    page.locator("[data-maps-side] .lex-list-row", has_text=MAP_B).click()
                    page.wait_for_function(f'state.mapId==="{MAP_B}"', timeout=30000)
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===1",
                        timeout=30000)
                    page.locator("[data-maps-dir] .lex-list-row").click()
                    page.wait_for_function(f'state.selected.startsWith("{MAP_B}")', timeout=30000)
                    page.locator("[data-maps-dir] .lex-subtab-button", has_text="Drops").click()
                    page.wait_for_function('state.dirTab==="drops"', timeout=30000)
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===0",
                        timeout=30000)
                    page.locator("[data-maps-side] .lex-list-row", has_text=MAP_A).click()
                    page.wait_for_function(f'state.mapId==="{MAP_A}"', timeout=30000)
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===1",
                        timeout=30000)
                    page.locator("[data-maps-dir] .lex-list-row").click()
                    page.wait_for_function('state.selected==="ItemLotParam:100" && state.row?.table==="ItemLotParam"',
                                           timeout=30000)
                    page.locator("[data-dir-local] input").uncheck()
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===3",
                        timeout=30000)
                    page.get_by_role("searchbox", name="Search the world").fill("101")
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===1",
                        timeout=30000)
                    page.locator("[data-dir-local] input").check()
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===0",
                        timeout=30000)
                    page.get_by_role("searchbox", name="Search the world").fill("")
                    for tab in ("Treasure",):
                        page.locator("[data-maps-dir] .lex-subtab-button", has_text=tab).click()
                        page.wait_for_function(f'state.dirTab==="{tab.lower()}"', timeout=30000)
                        page.wait_for_function('document.querySelector("[data-dir-local] input").disabled',
                                               timeout=30000)
                    # Two rows per page forces the page controls out on three
                    # rows; the stacked pager still fits the 360px panel.
                    page.evaluate("state.pageSize=2")
                    page.evaluate("state.dirPage=0")
                    page.locator("[data-maps-dir] .lex-subtab-button", has_text="Drops").click()
                    page.wait_for_function('state.dirTab==="drops"', timeout=30000)
                    page.locator("[data-dir-local] input").uncheck()
                    page.wait_for_selector(
                        "[data-maps-dir] .lex-pager-controls", timeout=30000)
                    over = page.evaluate(
                        "document.querySelector('[data-maps-dir]').scrollWidth"
                        " - document.querySelector('[data-maps-dir]').clientWidth")
                    assert over <= 1, over
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 directory Local filter passed.")


if __name__ == "__main__":
    main()
