"""DS1 Items: every subtab detail uses panel tabs."""
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
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-item-tabs-') as folder:
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
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    for tab in ('spells', 'rings', 'upgrades', 'consumables', 'keys',
                                    'weapons', 'shields', 'armor', 'ammo'):
                        page.locator(f'[data-subtab="{tab}"]').click()
                        page.wait_for_function('(tab)=>state.sub===tab && state.row && !state.error', arg=tab)
                        page.wait_for_timeout(200)
                        tabs = page.locator('.lex-detail .lex-tabbed-panel [data-subtab]')
                        assert tabs.count() >= 2, (tab, tabs.count())
                        names = tabs.evaluate_all('nodes=>nodes.map(n=>n.dataset.subtab)')
                        assert len(set(names)) == len(names), (tab, names)
                    page.screenshot(path=str(Path(tempfile.gettempdir()) / 'lex-ds1-item-tabs.png'))
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 item panel tabs: every subtab passed.')
if __name__ == '__main__':
    main()
