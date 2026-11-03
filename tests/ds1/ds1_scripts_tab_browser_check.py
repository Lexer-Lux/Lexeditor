"""DS1 Scripts tab: scopes list states, one state reads its commands."""
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from drb_fixture import make_dcx
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from esd_fixture import build_esd, make_bnd
from plugins.ds1 import texts
from plugins.ds1.esd import Esd, State
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-scripts-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        menu = game / 'menu'
        menu.mkdir(parents=True, exist_ok=True)
        (menu / 'ingame.menuesdbnd.dcx').write_bytes(
            make_dcx(make_bnd({'i02-00.esd': build_esd().to_bytes()})))
        (menu / 'common.menuesdbnd.dcx').write_bytes(
            make_dcx(make_bnd({'c00-00.esd': Esd({1: {2: State(2, [], [], [], [])}},
                                                None, 1, True, (0, 0, 0, 0)).to_bytes()})))
        talk = game / 'script' / 'talk'
        talk.mkdir(parents=True)
        (talk / 't01-00_00_00.talkesdbnd.dcx').write_bytes(
            make_dcx(make_bnd({'t01-00_00_00.esd': build_esd().to_bytes()})))
        (talk / 'm14_02_00_00.talkesdbnd.dcx').write_bytes(b'')
        mod.mkdir()
        (mod / MARKER).touch()
        with DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                         'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate("navigate('scripts','ingame')")
                    page.wait_for_function("state.tab==='scripts'&&state.rows&&state.rows.length===3")
                    row = page.locator('.lex-list-row[data-key="ScriptState:ingame/i02-00.esd/0/0"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    page.wait_for_function(
                        "state.row && state.row.table==='ScriptState' && state.scriptDetail")
                    logs = page.locator('.lex-detail .lex-log')
                    assert logs.count() == 2
                    commands = logs.nth(0).inner_text()
                    assert 'entry:' in commands and '1:3  "Ins_X", 1' in commands
                    assert 'exit:' in commands and 'while:' in commands
                    assert 'i32(1004)' in commands and 'f64(-2.0)' in commands
                    conditions = logs.nth(1).inner_text()
                    assert 'if f22() == 1 -> state 0' in conditions
                    assert '1:29  "hi"' in conditions
                    assert 'if r0 != 0' in conditions
                    assert 'if 1 -> state 0' in conditions
                    page.evaluate("navigate('scripts','common')")
                    page.wait_for_function("state.tab==='scripts'&&state.sub==='common'&&state.rows&&state.rows.length===1")
                    page.evaluate("navigate('scripts','talk')")
                    page.wait_for_function("state.tab==='scripts'&&state.sub==='talk'&&state.rows&&state.rows.length===3")
                    assert not page.locator('.lex-notice').count()
                    page.evaluate("navigate('datamap')")
                    page.wait_for_selector('.lex-data-map-table')
                    page.evaluate('''filename=>{state.mapQuery=filename;state.mapPage=0;render()}''', 'ingame.menuesdbnd.dcx')
                    page.locator('.lex-data-map-table .lex-column-list-row').filter(has_text='menu/ingame.menuesdbnd.dcx').click()
                    page.locator('.lex-data-map-open').click()
                    page.wait_for_function(
                        "state.tab==='scripts'&&state.sub==='ingame'&&state.rows.length>0&&!state.error")
                finally:
                    browser.close()
    print('DS1 Scripts tab: scopes list states, one state reads its commands passed.')


if __name__ == '__main__':
    main()
