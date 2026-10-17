"""NPCs tab renders, an unowned shop line edit saves and reloads, no Shops tab."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive
from msb_fixture import build_msb
from plugins.ds1.formats import ItemDocument
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import MARKER, RELATIVE
from playwright.sync_api import sync_playwright

MAP = 'm10_00_00_00.msb'


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    output.mkdir(parents=True, exist_ok=True)
    raw = make_archive()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-npcshop-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / MAP).write_bytes(build_msb())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        session.start()
        errors = []
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="npcs"]').click()
                    page.wait_for_function('state.tab==="npcs" && state.rows.length===2 && state.rows[0].table==="NpcParam" && !state.error')
                    names = page.evaluate('state.rows.map(r=>r.name)')
                    assert names, names
                    assert page.locator('button[data-tab="shops"]').count() == 0
                    subs = page.evaluate('state.npcTabs.map(t=>t.id)')
                    assert subs == ['npcs', 'unowned-shops'], subs
                    page.locator('[data-subtab="unowned-shops"]').click()
                    page.wait_for_function('state.sub==="unowned-shops" && state.rows.length===3 && state.rows.every(r=>r.table==="ShopLineupParam") && !state.error')
                    page.locator('.lex-list-row').first.click()
                    page.wait_for_function('!!state.row && !state.error')
                    control = page.locator('[data-field-key="value"]').first
                    old = int(float(control.input_value().replace(',', '')))
                    control.fill(str(old + 50))
                    control.press('Tab')
                    identity = page.evaluate('({table:state.row.table,id:state.row.id})')
                    page.wait_for_function('state.dirty>0')
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    document = ItemDocument((mod / RELATIVE).read_bytes())
                    assert document.value(identity['table'], identity['id'], 'value') == old + 50
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            session.wait_closed()
    print('DS1 NPCs tab and unowned shops passed.')


if __name__ == '__main__':
    main()
