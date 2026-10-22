"""Formation table checkboxes are sized to their cells, not fixed 18px.

The framework draws every checkbox through one custom rule; table cells
are ~64px tall with ~20px text, so an 18px box reads tiny. Cell boxes
must scale with the cell font instead of parking at a fixed pixel size.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-cb-size-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1500, "height": 900})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("state.encountersTab='formations';navigate('encounters')")
            page.wait_for_selector(".lex-column-list-row[data-key]", timeout=180000)
            page.locator(".lex-column-list-row[data-key]").nth(0).click()
            page.wait_for_function(
                "() => document.querySelector('.lex-column-list-cell input[type=\"checkbox\"]')",
                timeout=60000)
            sizes = page.evaluate("""() => [...document.querySelectorAll(
              '.lex-column-list-cell input[type="checkbox"]')].map(box => ({
                w: box.offsetWidth, h: box.offsetHeight,
                font: parseFloat(getComputedStyle(box).fontSize)}))""")
            assert sizes, "no Formation checkboxes rendered"
            for box in sizes:
                assert box["w"] >= 24 and box["h"] >= 24, \
                    f"checkbox stuck tiny: {box['w']}x{box['h']}px"
                assert box["w"] >= box["font"] * 1.4, \
                    f"checkbox {box['w']}px smaller than 1.4x cell font {box['font']}px"
            browser.close()
            print(f"Formation checkboxes sized to cells ({len(sizes)} boxes).")


if __name__ == "__main__":
    main()
