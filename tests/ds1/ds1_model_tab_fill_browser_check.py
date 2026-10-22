"""DS1 Model tab: the viewport fills the panel, no blank quarter below."""
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from flver_fixture import build_flver, make_chrbnd
from msb_fixture import build_msb
from plugins.ds1 import texts
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-model-fill-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / 'm0.msb').write_bytes(build_msb(parts=(('enemy', 2, 0, 0, 251000),)))
        (game / 'chr').mkdir(parents=True)
        (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver()))
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 1200})
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    row = page.locator('.lex-list-row[data-key="NpcParam:251000"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    page.wait_for_function(
                        "state.row && `${state.row.table}:${state.row.id}` === 'NpcParam:251000'")
                    page.locator('.lex-tabbed-panel [data-subtab="model"]').click()
                    page.wait_for_selector('[data-chr-host] canvas', timeout=60000)
                    page.wait_for_timeout(500)
                    gap = page.evaluate("""() => {
                      const host = document.querySelector('[data-chr-host]');
                      const panel = document.querySelector('.lex-tabbed-panel-content');
                      return panel.getBoundingClientRect().bottom - host.getBoundingClientRect().bottom;
                    }""")
                    assert gap < 60, f'{gap}px of blank panel below the viewport'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 Model tab: the viewport fills the panel passed.')


if __name__ == '__main__':
    main()
