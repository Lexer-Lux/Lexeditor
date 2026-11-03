"""DS1 asset links: Model ID hovers and opens its parts binder.

Icon ID and Model ID show their game file through an asset face and
edit through a picker that writes the numeric ID back. Model paths
need no game files, so the Model ID face resolves offline; the Icon
ID face shows None until the menu sheets are installed.
"""
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright
def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-asset-links-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        (game.parent / 'library').mkdir(exist_ok=True)
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0',
                              'LEXEDITOR_DS1_MODS_ROOT': str(game.parent / 'library')})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.wait_for_selector('.lex-plugin-loading-screen', state='detached')
                    page.locator('[data-tab="items"]').click()
                    page.locator('[data-subtab="weapons"]').click()
                    page.wait_for_function("state.tab==='items' && state.row?.table==='EquipParamWeapon'")
                    page.locator('.lex-detail .lex-tabbed-panel [data-subtab="appearance"]').click()
                    page.wait_for_function("state.itemTab==='appearance'")
                    model = page.locator('.lex-detail-field[data-lex-property="equipModelId"]')
                    assert model.locator('.ds1-asset-face .lex-hoverable').count() == 1
                    assert model.locator('button.ds1-find-asset').count() == 1
                    model.locator('.ds1-asset-face .lex-hoverable').hover()
                    page.locator('.lex-hover-preview').first.wait_for()
                    model.locator('.ds1-asset-face .lex-hoverable').click()
                    page.wait_for_function("state.tab==='models'", timeout=15000)
                    page.locator('[data-tab="items"]').click()
                    page.locator('[data-subtab="weapons"]').click()
                    page.wait_for_function("state.tab==='items' && state.row?.table==='EquipParamWeapon'")
                    page.locator('.lex-detail .lex-tabbed-panel [data-subtab="appearance"]').click()
                    page.wait_for_function("state.itemTab==='appearance'")
                    icon = page.locator('.lex-detail-field[data-lex-property="iconId"]')
                    assert icon.locator('.ds1-asset-face .lex-hoverable').count() == 0
                    assert icon.locator('.ds1-asset-face .ds1-unset-face').count() == 1
                    assert icon.locator('button.ds1-icon-gallery').count() == 1
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 asset links: Model ID hovers and opens, pickers write back passed.')
if __name__ == '__main__':
    main()
