"""DS1 maps directory mounts the compact pagination bar, never game files.

The 360px Directory panel shows search on its own row up top, no X-Y/Z
position count, the Local toggle label reading bottom-to-top, and pager
controls plus filters on one shared bottom row. Paging and search keep
working through the new bar.
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


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    raw = make_archive(field_values={"NpcParam": {120000: {"itemLotId_1": 100}}})
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-compact-pager-") as folder:
        temp = Path(folder)
        game = temp / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / MAP_A).write_bytes(build_msb(parts=(("enemy", 2, 0, 0, 120000),
                                                              ("enemy", 2, 1, 0, 120100),
                                                              ("enemy", 2, 2, 0, 120100))))
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
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.locator('button[data-tab="maps"]').click()
                    page.wait_for_function('state.tab==="maps" && state.mapView && state.rows.length>0 && !state.error',
                                           timeout=60000)
                    page.wait_for_selector("[data-maps-dir] .lex-compact-pager", timeout=30000)
                    try:
                        page.wait_for_selector("[data-maps-dir] .lex-compact-pager-search",
                                               timeout=30000)
                    except Exception:
                        print("BAR:", page.evaluate(
                            "document.querySelector('[data-maps-dir] .lex-compact-pager')?.outerHTML?.slice(0, 2000)"))
                        print("DIRCHILDREN:", page.evaluate(
                            "document.querySelector('[data-maps-dir]')?.children.length"))
                        print("ERRORS:", errors)
                        raise
                    bar = page.locator("[data-maps-dir] .lex-compact-pager")
                    assert bar.count() == 1
                    assert page.locator("[data-maps-dir] .lex-page-summary").count() == 0
                    assert page.locator("[data-maps-dir] .lex-pager-stacked").count() == 0
                    search = page.locator("[data-maps-dir] .lex-compact-pager-search").bounding_box()
                    bottom = page.locator("[data-maps-dir] .lex-compact-pager-bottom").bounding_box()
                    assert search["y"] + search["height"] <= bottom["y"] + 1, (search, bottom)
                    label = page.locator("[data-maps-dir] .lex-compact-pager .lex-pager-toggle > span")
                    assert label.count() == 1
                    assert label.evaluate("node => getComputedStyle(node).writingMode") == "vertical-rl"
                    box = label.bounding_box()
                    assert box["width"] < box["height"], box
                    # Two rows per page forces the page controls out; the one
                    # bottom row still holds them beside the toggle.
                    page.evaluate("state.pageSize=2")
                    page.evaluate("state.dirPage=0")
                    page.locator("[data-maps-dir] .lex-subtab-button", has_text="Enemies").click()
                    page.wait_for_function('state.dirTab==="enemies"', timeout=30000)
                    page.wait_for_selector("[data-maps-dir] .lex-pager-controls", timeout=30000)
                    bottom = page.locator("[data-maps-dir] .lex-compact-pager-bottom").bounding_box()
                    boxes = page.locator("[data-maps-dir] .lex-compact-pager-bottom > *").evaluate_all(
                        "nodes => nodes.map(node => { const box = node.getBoundingClientRect();"
                        " return {x: box.x, y: box.y, width: box.width, height: box.height}; })")
                    assert len(boxes) >= 2, boxes
                    midline = bottom["y"] + bottom["height"] / 2
                    for child in boxes:
                        assert child["y"] <= midline <= child["y"] + child["height"], (child, midline)
                    for left, right in zip(boxes, boxes[1:]):
                        assert right["x"] >= left["x"] + left["width"] - 2, (left, right)
                    over = page.evaluate(
                        "document.querySelector('[data-maps-dir]').scrollWidth"
                        " - document.querySelector('[data-maps-dir]').clientWidth")
                    assert over <= 1, over
                    first = page.locator("[data-maps-dir] .lex-list-row").first.inner_text()
                    page.locator("[data-maps-dir]").get_by_role("button", name="Next page").click()
                    page.wait_for_function('state.dirPage===1', timeout=30000)
                    second = page.locator("[data-maps-dir] .lex-list-row").first.inner_text()
                    assert first != second, (first, second)
                    page.locator("[data-maps-dir] .lex-subtab-button", has_text="Drops").click()
                    page.wait_for_function('state.dirTab==="drops"', timeout=30000)
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===2",
                        timeout=30000)
                    page.get_by_role("searchbox", name="Search the world").fill("101")
                    page.wait_for_function(
                        "document.querySelectorAll('[data-maps-dir] .lex-list-row').length===1",
                        timeout=30000)
                    if output:
                        page.wait_for_timeout(300)
                        page.locator("[data-maps-dir]").screenshot(
                            path=str(output / "ds1-directory-compact-pager.png"))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 compact pager passed.")


if __name__ == "__main__":
    main()
