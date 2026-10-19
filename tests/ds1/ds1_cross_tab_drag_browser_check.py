"""NPC guard fields drag between the Blocking and Defense panel tabs.

Dropping a property on another tab's button records a membership
override: the field renders in the target tab from then on, both tabs
keep their own arrangements, and undo restores both sides.
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

ORDER = """() => [...document.querySelectorAll(
  '.lex-tabbed-panel-content .lex-detail-field')]
  .map(n => n.dataset.lexLayoutField)"""

OVERRIDES = """() => Object.fromEntries(Object.entries(localStorage)
  .filter(([k]) => k.includes('.fieldtabs.')))"""


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-crosstab-') as folder:
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
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    page.locator('.lex-list-row[data-key="NpcParam:251000"]').click()
                    page.wait_for_function("state.row && state.row.table==='NpcParam'")
                    page.evaluate("dispatchEvent(new CustomEvent('lexeditor-settings-changed',"
                                  "{detail:{developerMode:true}}))")
                    page.locator('.lex-tabbed-panel-tabs .lex-subtab-button',
                                 has_text='Blocking').click()
                    page.wait_for_timeout(700)
                    before = page.evaluate(ORDER)
                    assert len(before) > 1, before
                    moved, rest = before[0], before[1:]
                    defense = page.locator('.lex-tabbed-panel-tabs .lex-subtab-button',
                                           has_text='Defense')
                    label = page.locator(
                        '.lex-tabbed-panel-content .lex-detail-field-label-text').first
                    label.hover()
                    label.drag_to(defense, target_position={'x': 10, 'y': 4})
                    page.wait_for_timeout(700)
                    active = page.locator(
                        '.lex-tabbed-panel-tabs .lex-subtab-button.active').get_attribute('data-subtab')
                    assert active == 'defense', active
                    got = page.evaluate(ORDER)
                    assert got[-1] == moved, got
                    maps = page.evaluate(OVERRIDES)
                    assert len(maps) == 1, maps
                    page.locator('.lex-tabbed-panel-tabs .lex-subtab-button',
                                 has_text='Blocking').click()
                    page.wait_for_timeout(700)
                    assert page.evaluate(ORDER) == rest
                    page.keyboard.press('Control+z')
                    page.wait_for_timeout(700)
                    assert page.evaluate(ORDER) == before
                finally:
                    browser.close()
        finally:
            session.stop()
        assert errors == [], errors
        print('PASS: NPC fields move between Blocking and Defense, and undo restores them')


if __name__ == '__main__':
    main()
