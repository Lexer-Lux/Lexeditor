"""Empty weapon ingredient slots keep their quantity box and finder place.

An ingredient with no item still renders the number input (empty and
read-only) so its finder button sits exactly where a filled slot's does.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-weapon-ingredient-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("state.selected.weapons=13;navigate('weapons')")
            page.wait_for_selector(".weapon-ingredient-row")
            rows = page.locator(".weapon-ingredient-row")
            assert rows.count() == 4
            filled = rows.nth(0)
            empty = rows.nth(3)
            assert "Nothing" in empty.inner_text()
            box = empty.locator("input[type=number]")
            assert box.count() == 1
            assert box.input_value() == ""
            assert box.evaluate("node=>node.readOnly") is True
            assert box.evaluate("node=>node.disabled") is False
            filled_box = filled.locator("input[type=number]")
            assert filled_box.input_value() == "2"
            assert filled_box.evaluate("node=>node.readOnly") is False
            def finder(row):
                return row.locator("button.lex-thing-finder, button[aria-label^='Select the Item']").first
            empty_x = finder(empty).bounding_box()["x"]
            filled_x = finder(filled).bounding_box()["x"]
            assert abs(empty_x - filled_x) <= 6, (empty_x, filled_x)
            browser.close()
            print("Empty ingredient slots keep an empty read-only quantity and aligned finder.")


if __name__ == "__main__":
    main()
