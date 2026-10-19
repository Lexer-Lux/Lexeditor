"""Maps right panel hangs on a remembered divider, canvas follows.

The viewport and the Maps/Placements/Selection side share one
panelLayout divider: dragging it resizes both panes, the split
persists to localStorage, and the WebGL canvas tracks its host
without a window resize. Synthetic fixtures only; read-only.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from msb_fixture import build_msb
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

STORAGE_KEY = "lexeditor:panel-layout:ds1-maps-view-side"


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-maps-divider-") as folder:
        game = Path(folder) / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / "map" / "MapStudio").mkdir(parents=True)
        (game / "map" / "MapStudio" / "m10_00_00_00.msb").write_bytes(build_msb())
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1",
                              "LEXEDITOR_MOD_READ_ONLY": "1"})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1400, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function('state.tab === "maps" && !state.error',
                                           timeout=120000)
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]',
                                           timeout=120000)
                    divider = page.locator(".lex-panel-layout-divider")
                    assert divider.count() == 1
                    assert divider.first.is_visible()
                    side = page.locator("[data-maps-side]")
                    before = side.bounding_box()["width"]
                    box = divider.first.bounding_box()
                    assert box["width"] >= 8, box
                    page.mouse.move(box["x"] + box["width"] / 2,
                                    box["y"] + box["height"] / 2)
                    page.mouse.down()
                    page.mouse.move(box["x"] + box["width"] / 2 - 120,
                                    box["y"] + box["height"] / 2, steps=12)
                    page.mouse.up()
                    page.wait_for_timeout(400)
                    after = side.bounding_box()["width"]
                    assert abs((after - before) - 120) < 15, (before, after)
                    stored = page.evaluate(f"localStorage.getItem({STORAGE_KEY!r})")
                    assert stored is not None, "split was not remembered"
                    canvas = page.evaluate(
                        """() => { const host = document.querySelector(
                            '[data-viewport-host]');
                            const view = host.querySelector('canvas');
                            return {backing: view.width, css: host.clientWidth}; }""")
                    assert abs(canvas["backing"] - canvas["css"]) <= 2, canvas
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 maps divider passed.")


if __name__ == "__main__":
    main()
