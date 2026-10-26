"""DS1 Player behaviors: the AI subtab and the ring behavior link.

The AI tab lists player behaviors in their own subtab with editable
costs, and a ring's Behavior ID renders as a hoverable face plus thing
finder that opens the linked player behavior.
"""
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


def select(page, table, row_id):
    row = page.locator(f'.lex-list-row[data-key="{table}:{row_id}"]')
    row.wait_for()
    row.scroll_into_view_if_needed()
    row.click()
    page.wait_for_function('(key) => state.row && `${state.row.table}:${state.row.id}` === key',
                           arg=f'{table}:{row_id}')


def show_face(page, key):
    """Click through the record's panel tabs until the link face shows."""
    tabs = page.locator('.lex-tabbed-panel [data-subtab]')
    for index in range(tabs.count()):
        if page.locator(f'.ds1-reference-face[data-field-key="{key}"]:visible').count():
            return
        tab_id = tabs.nth(index).get_attribute('data-subtab')
        tabs.nth(index).click()
        page.wait_for_function('(id)=>state.itemTab===id', arg=tab_id)
    assert page.locator(f'.ds1-reference-face[data-field-key="{key}"]:visible').count() == 1, key


def main():
    raw = make_archive(field_values={'EquipParamAccessory': {100: {'behaviorId': 101}}})
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-player-behaviors-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
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
                    page.evaluate("navigate('ai','player-behaviors')")
                    page.wait_for_function("state.tab==='ai'&&state.sub==='player-behaviors'&&state.rows&&state.rows.length===3")
                    select(page, 'BehaviorParam_PC', 101)
                    stamina = page.locator('[data-lex-property="stamina"]:visible')
                    assert stamina.count() == 1
                    assert stamina.locator('input:not([disabled]),select:not([disabled])').count() >= 1
                    page.evaluate("navigate('items','rings')")
                    page.wait_for_function("state.tab==='items'&&state.sub==='rings'&&state.rows&&state.rows.length")
                    select(page, 'EquipParamAccessory', 100)
                    show_face(page, 'behaviorId')
                    face = page.locator('.ds1-reference-face[data-field-key="behaviorId"]:visible')
                    assert face.locator('.lex-hoverable').count() == 1
                    assert 'Behavior 101' in face.inner_text()
                    assert page.locator('.ds1-reference-field .ds1-find-reference:visible').count() >= 1
                    face.locator('.lex-hoverable').click()
                    page.wait_for_function('state.tab==="ai"&&state.sub==="player-behaviors"'
                                           '&&state.row?.table==="BehaviorParam_PC"&&state.row?.id===101')
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 Player behaviors: AI subtab and ring behavior link passed.')


if __name__ == '__main__':
    main()
