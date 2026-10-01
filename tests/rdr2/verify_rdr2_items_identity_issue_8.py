"""Render RDR2 item identity through the shared list/detail components."""
from pathlib import Path
import tempfile

from playwright.sync_api import expect, sync_playwright
from rdr2_browser_check import document


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/*", lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')")
            listing = page.locator('#main .lex-column-list')
            expect(listing.locator('[role=columnheader]')).to_have_text(['Name / Item', 'ID', 'Group', 'Category'])
            rows = listing.locator('.lex-list-row')
            expect(rows).to_have_count(3)
            for row in rows.all():
                expect(row.locator('.lex-column-list-cell')).to_have_count(4)
                expect(row.locator('input,select,textarea')).to_have_count(0)
            rows.filter(has_text='CONSUMABLE_BRANDY').click()
            name = page.get_by_role('textbox', name='Item name', exact=True)
            expect(name).to_have_value('Brandy')
            heading = page.locator('.lex-detail-panel-heading').filter(has=name)
            expect(heading).to_contain_text('CONSUMABLE_BRANDY')
            name.fill('Edited brandy')
            name.press('Tab')
            assert page.evaluate("state.localizationEdits.NAME_BRANDY") == 'Edited brandy'
            search = page.get_by_role('searchbox', name='Search items', exact=True)
            search.fill('MOONSHINE')
            search.press('Tab')
            expect(rows).to_have_count(1)
            expect(name).to_have_value('Moonshine')
            search.fill('')
            search.press('Tab')
            expect(rows).to_have_count(3)
            rows.filter(has_text='CONSUMABLE_BRANDY').click()
            expect(name).to_have_value('Edited brandy')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors, errors
            output = Path(tempfile.gettempdir()) / 'lexeditor-dev' / 'rdr2-item-identity.png'
            output.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output))
        finally:
            browser.close()
    print('PASS: four identity columns, detail-only editing, name persistence, and search selection')


if __name__ == '__main__':
    main()
