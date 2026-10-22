"""DS1 Drops tab: drop tables list, edit, and monster lot IDs open them."""
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-drops-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate("navigate('drops','drops')")
                    page.wait_for_function("state.tab==='drops'&&state.rows&&state.rows.length")
                    row = page.locator('.lex-list-row[data-key="ItemLotParam:100"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    page.wait_for_selector('[data-field-key="lotItemId01"]', timeout=60000)
                    field = page.locator('[data-field-key="lotItemId01"]:visible')
                    assert field.count() == 1 and field.is_enabled()
                    assert field.evaluate('n=>n.tagName') == 'SELECT'
                    pair = page.locator('[data-lex-property="lotItemId01"]')
                    assert pair.count() == 1
                    assert pair.locator('input[data-field-key="lotItemNum01"]').count() == 1
                    field.select_option('101')
                    page.wait_for_function('state.pending===0 && state.dirty>0', timeout=60000)
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    merchant = page.locator('.lex-list-row[data-key="NpcParam:251000"]')
                    merchant.scroll_into_view_if_needed()
                    merchant.click()
                    page.wait_for_function(
                        "state.row && `${state.row.table}:${state.row.id}` === 'NpcParam:251000'")
                    page.locator('.lex-detail .lex-tabbed-panel [data-subtab="value-rewards"]').click()
                    page.wait_for_selector('[data-field-key="itemLotId_1"]', timeout=60000)
                    lot = page.locator('[data-field-key="itemLotId_1"]:visible')
                    assert lot.evaluate('n=>n.tagName') == 'SELECT'
                    assert 'Drop 100' in lot.locator('option').all_text_contents()
                    lot.select_option('100')
                    page.wait_for_function(
                        "state.pending===0 && state.row.fields.find("
                        "f=>f.key==='itemLotId_1').value===100",
                        timeout=60000)
                    page.wait_for_selector(
                        '.lex-hoverable[data-hover-target-type="ds1-drop"]',
                        timeout=60000)
                    link = page.locator(
                        '.lex-hoverable[data-hover-target-type="ds1-drop"]').first
                    link.scroll_into_view_if_needed()
                    link.click()
                    page.wait_for_function(
                        "state.tab==='drops'&&state.row&&state.row.table==='ItemLotParam'"
                        "&&state.row.id===100", timeout=60000)
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 Drops tab: drop tables list, edit, and monster lot IDs open them passed.')


if __name__ == '__main__':
    main()
