"""DS1 NPCs: the magnifier covers previewable models, so the Model tab
is the fallback. A placed NPC with a loadable mesh opens the viewer in
the preview drawer and has no Model tab; an unplaced NPC with no model
at all keeps the tab for attack and hitbox inspection."""
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
def select(page, table, row_id):
    row = page.locator(f'.lex-list-row[data-key="{table}:{row_id}"]')
    row.scroll_into_view_if_needed()
    row.click()
    page.wait_for_function('(key) => state.row && `${state.row.table}:${state.row.id}` === key',
                           arg=f'{table}:{row_id}')
def model_tabs(page):
    return page.locator('.lex-tabbed-panel [data-subtab="model"]')
def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-npc-model-') as folder:
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
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    # A placed NPC with a loadable mesh opens the viewer
                    # in the preview drawer: no Model tab, but a magnifier.
                    select(page, 'NpcParam', 251000)
                    page.wait_for_selector('.lex-model-preview-trigger')
                    assert model_tabs(page).count() == 0
                    # No placement, no preview: the Model tab stays as the
                    # fallback viewer for attacks and hitboxes.
                    select(page, 'NpcParam', 321001)
                    page.wait_for_timeout(400)
                    assert model_tabs(page).count() == 1
                    page.screenshot(path=str(Path(tempfile.gettempdir()) / 'lex-ds1-npc-model.png'))
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 NPC model tab: drawer covers meshes, tab is the fallback passed.')
if __name__ == '__main__':
    main()
