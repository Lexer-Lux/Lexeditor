"""DS1 enemy drawer: the viewed attack's hitboxes open for editing in Attacks."""
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
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-drawer-edit-') as folder:
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
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    row = page.locator('.lex-list-row[data-key="NpcParam:251000"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    page.wait_for_function(
                        "state.row && `${state.row.table}:${state.row.id}` === 'NpcParam:251000'")
                    page.locator('.lex-detail-panel-heading .lex-model-preview-trigger').click()
                    page.wait_for_selector('.lex-chr-viewer-stage[data-ready="true"]', timeout=60000)
                    attack = page.evaluate(
                        "fetch('/api/chr/view?npc=251000').then(r=>r.json()).then(v=>v.attacks[0].id)")
                    assert attack, 'the drawer lists no attack'
                    edit = page.locator('.lex-chr-viewer-fields').get_by_role(
                        'button', name='in Attacks')
                    assert edit.count() == 1
                    edit.click()
                    page.wait_for_function(
                        "(id) => state.tab === 'attacks' && state.row && "
                        "state.row.table === 'AtkParam_Npc' && state.row.id === id",
                        arg=attack, timeout=60000)
                    page.wait_for_selector('[data-field-key="hit0_Radius"]', timeout=60000)
                    field = page.locator('[data-field-key="hit0_Radius"]:visible')
                    assert field.count() == 1
                    assert field.evaluate('n=>n.tagName') == 'INPUT'
                    assert field.is_enabled()
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 enemy drawer: the viewed attack opens for editing in Attacks passed.')


if __name__ == '__main__':
    main()
