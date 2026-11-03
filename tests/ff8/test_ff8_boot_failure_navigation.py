"""A failed data load must stay an error after visiting the shared Mods page."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]

from playwright.sync_api import sync_playwright, expect
from plugins.ff8.plugin import FF8Session
from shot import STUB


def test_missing_data_does_not_turn_into_an_endless_navigation_spinner(tmp_path):
    environment = {
        'LEXEDITOR_FF8_ROOT': str(tmp_path/'game'),
        'LEXEDITOR_FF8_DATA_ROOT': str(tmp_path/'data'),
        'LEXEDITOR_FF8_PROJECT': str(tmp_path/'project'),
        'LEXEDITOR_FF8_LOCAL_DATA': str(tmp_path/'local'),
    }
    with FF8Session(environment) as session, sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width':1280,'height':800})
            page.add_init_script(STUB)
            page.goto(session.url)
            error = page.locator('#main').get_by_text('Failed to load FF8 plugin:', exact=False)
            expect(error).to_be_visible()
            original = error.inner_text()
            for tab in ('abilities','items'):
                page.locator('nav button[data-tab="mods"]').click()
                expect(page.locator('#main .lex-mods-page')).to_be_visible()
                page.locator(f'nav button[data-tab="{tab}"]').click()
                expect(page.locator('#main .lex-panel-loading')).to_have_count(0)
                expect(page.locator('#main')).to_contain_text(original)
            page.screenshot(path=str(tmp_path/'startup-error-after-mods.png'))
        finally:
            browser.close()
