"""DS1 rate units read /sec instead of the full quantity/second.

The row label already names the quantity, so the unit only says per
second - short enough that the value is never cut off.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-rate-unit-') as folder:
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
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    page.set_default_timeout(60000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    row = page.locator('.lex-list-row[data-key="NpcParam:251000"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    page.wait_for_function(
                        "state.row && `${state.row.table}:${state.row.id}` === 'NpcParam:251000'")
                    page.locator('.lex-tabbed-panel [data-subtab="basics"]').click()
                    field = page.locator('[data-lex-property="staminaRecoverBaseVel"]')
                    page.wait_for_selector('[data-lex-property="staminaRecoverBaseVel"]')
                    unit = field.locator('.lex-unit')
                    assert unit.count() == 1
                    assert unit.inner_text() == '/sec', unit.inner_text()
                    visible = field.locator('input').evaluate(
                        'n => n.scrollWidth <= n.clientWidth + 1')
                    assert visible, 'the stamina recovery value is cut off by its unit'
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 rate unit: quantities per second read /sec passed.')


if __name__ == '__main__':
    main()
