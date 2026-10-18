"""The text token toolbar keeps portraits whole and dropdowns in one row.

Character tiles are 2:3 like the game's 32x48 portraits, so no face is
cropped; colour tiles stay square. The Locations/Variables/Keys/Special
dropdowns share one row at desktop width and at a narrow 700px window,
where the group scrolls sideways instead of wrapping.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def toolbar_state(page):
    return page.evaluate("""() => {
      const tiles = [...document.querySelectorAll(
        ".ff8-text-token-group .lex-toolbar-tile-portrait")].map(node => {
          const rect = node.getBoundingClientRect();
          const img = node.querySelector("img");
          const drawn = img ? img.getBoundingClientRect() : null;
          return {w: rect.width, h: rect.height,
                  natural: img ? [img.naturalWidth, img.naturalHeight] : null,
                  drawn: drawn ? [drawn.width, drawn.height] : null,
                  inner: [node.clientWidth, node.clientHeight]};
        });
      const colours = [...document.querySelectorAll(
        ".ff8-text-token-group[aria-label='Text colours'] .lex-toolbar-tile")].map(node => {
          const rect = node.getBoundingClientRect();
          return [rect.width, rect.height];
        });
      const group = document.querySelector(".ff8-text-token-choices");
      const tops = [...group.querySelectorAll("select")].map(node =>
        Math.round(node.getBoundingClientRect().top));
      return {tiles, colours, tops,
              scroll: [group.scrollWidth, group.clientWidth]};
    }""")


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-text-toolbar-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("state.textTab='text';navigate('text')")
            page.wait_for_selector(".ff8-text-token-toolbar", timeout=120000)
            page.wait_for_timeout(1000)
            state = toolbar_state(page)
            portraits = [tile for tile in state["tiles"] if tile["natural"]]
            assert len(portraits) == 11, len(portraits)
            for tile in state["tiles"]:
                assert tile["h"] == tile["w"] * 1.5, tile
            for tile in portraits:
                assert tile["natural"] == [32, 48], tile
                assert tile["drawn"] == tile["inner"], tile
                drawn_ratio = tile["drawn"][0] / tile["drawn"][1]
                assert abs(drawn_ratio - 32 / 48) < 0.03, tile
            for size in state["colours"]:
                assert size[0] == size[1] or size == [26, 28], size
            assert len(set(state["tops"])) == 1, state["tops"]
            page.set_viewport_size({"width": 700, "height": 1000})
            page.wait_for_timeout(1000)
            narrow = toolbar_state(page)
            assert len(set(narrow["tops"])) == 1, narrow["tops"]
            assert narrow["scroll"][0] > narrow["scroll"][1], narrow["scroll"]
            browser.close()
            print("Portraits keep 2:3 uncropped; the four insert dropdowns stay one row.")


if __name__ == "__main__":
    main()
