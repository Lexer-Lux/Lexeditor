"""Clicking field maps marks nothing changed.

Opening a map lazy-loads its detail into the row; the loaded row still
serializes exactly like its vanilla and base copies, so no master row
takes the modified highlight and the save count stays zero.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def red_rows(page):
    return page.locator("#main .lex-column-list-row.lex-record-modified").count()


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-field-clean-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("navigate('fields')")
            page.wait_for_selector(".lex-column-list-row[data-key]", timeout=180000)
            rows = page.locator(".lex-column-list-row[data-key]")
            assert rows.count() >= 3
            for index in range(3):
                rows.nth(index).click()
                page.wait_for_function(
                    "() => (state.data.fields.rows.filter(r => r._loaded).length > 0)",
                    timeout=180000)
                page.wait_for_timeout(1000)
                assert red_rows(page) == 0, f"row {index} reads modified"
            match = page.evaluate("""() => state.data.fields.rows.filter(r => r._loaded)
              .every(row => {
                const vanilla = state.vanilla.fields.rows.find(r => r.key === row.key);
                const base = state.base.fields.find(r => r.key === row.key);
                return JSON.stringify(row) === JSON.stringify(vanilla) &&
                       JSON.stringify(row) === JSON.stringify(base);
              })""")
            assert match is True
            browser.close()
            print("Browsing field maps leaves every row unmodified.")


if __name__ == "__main__":
    main()
