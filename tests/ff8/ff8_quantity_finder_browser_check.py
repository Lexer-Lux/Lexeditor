"""A finder keeps its standard size inside a quantity choice.

Refine recipes pair each ingredient with its count; the finder's width
matches a plain finder elsewhere (weapons), and its glyph fits inside
instead of squeezing to a sliver.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def finder_box(page, selector):
    return page.evaluate(f"""() => {{
      const node = document.querySelector({selector!r});
      const rect = node.getBoundingClientRect();
      const glyph = node.querySelector("svg").getBoundingClientRect();
      const font = parseFloat(getComputedStyle(node).fontSize);
      return {{w: rect.width, em: rect.width / font,
               fits: glyph.width <= rect.width && glyph.height <= rect.height}};
    }}""")


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-quantity-finder-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("state.selected.weapons=13;navigate('weapons')")
            page.wait_for_selector(".weapon-ingredient-row", timeout=120000)
            plain = finder_box(page, ".weapon-ingredient-row button.lex-thing-finder")
            page.evaluate("state.selected.refine=0;navigate('refine')")
            page.wait_for_selector(".lex-recipe-row button.lex-thing-finder", timeout=120000)
            boxed = finder_box(page, ".lex-recipe-row button.lex-thing-finder")
            assert abs(boxed["em"] - 1.8) < 0.05, boxed
            assert abs(boxed["w"] - plain["w"]) <= 1, (boxed, plain)
            assert boxed["fits"] is True, boxed
            browser.close()
            print("Finders keep standard size inside quantities.")


if __name__ == "__main__":
    main()
