"""Ammo's Defense panel tab groups its guard block under headers.

Weapons and ammo share the parameter table, but only ammo's Defense tab
subdivides: the guard's own settings under Properties, the absorption
under Defenses, the status guards under Resistances. Weapons keep the
one flat list.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def headers(page):
    return page.locator(
        '.lex-tabbed-panel-content .lex-detail-section-title-text').evaluate_all(
            'ns=>ns.map(n=>n.textContent.trim())')


def open_defense(page, sub):
    page.evaluate(f"navigate('items','{sub}')")
    page.wait_for_function("state.tab==='items'&&state.rows&&state.rows.length")
    page.locator('.lex-list-row').first.click()
    page.wait_for_function("state.row && state.row.fields")
    page.locator('.lex-tabbed-panel-tabs .lex-subtab-button',
                 has_text='Defense').click()
    page.wait_for_timeout(600)


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-ammo-def-') as folder:
        game = Path(folder) / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    open_defense(page, 'weapons')
                    assert headers(page) == [], headers(page)
                    open_defense(page, 'ammo')
                    assert headers(page) == ['Properties', 'Defenses', 'Resistances'], headers(page)
                    fields = page.locator('.lex-tabbed-panel-content .lex-detail-field')
                    assert fields.count() == 19, fields.count()
                finally:
                    browser.close()
        finally:
            session.stop()
        assert errors == [], errors
        print('PASS: ammo Defense headers group the guard block; weapons stay flat')


if __name__ == '__main__':
    main()
