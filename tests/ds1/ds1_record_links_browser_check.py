"""Record links render hoverable faces with finder buttons.

A goods row with an item, a spell and a dialog reference shows a
hoverable face plus a picker button for each record link (clicking the
face opens the linked record; the button changes it), and the dialog
line beside its number. An accessory's effect link opens the Effects
tab from its face.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive, make_menu_archive  # noqa: E402
from plugins.ds1 import texts  # noqa: E402
from plugins.ds1.formats import ItemDocument  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from plugins.ds3.formats import write_field  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def poke(document, table, row_id, key, value):
    _, start, row = document._row(table, row_id)
    field = next(item['spec'] for item in document.schemas[table]['fields']
                 if item['spec'].key == key)
    document.plain[start:start + len(row)] = write_field(row, field, value, '<')


def select(page, table, row_id):
    row = page.locator(f'.lex-list-row[data-key="{table}:{row_id}"]')
    row.wait_for()
    row.scroll_into_view_if_needed()
    row.click()
    page.wait_for_function('(key) => state.row && `${state.row.table}:${state.row.id}` === key',
                           arg=f'{table}:{row_id}')


def face(page, key):
    return page.locator(f'.ds1-reference-face[data-field-key="{key}"]:visible')


def main():
    errors = []
    document = ItemDocument(make_archive({'SpEffectParam': [100, 101, 102]}))
    poke(document, 'EquipParamGoods', 100, 'replaceItemId', 101)
    poke(document, 'EquipParamGoods', 100, 'magicId', 102)
    poke(document, 'EquipParamGoods', 100, 'yesNoDialogMessageId', 10010710)
    poke(document, 'EquipParamAccessory', 100, 'refCategory', 2)
    poke(document, 'EquipParamAccessory', 100, 'refId', 101)
    raw = document.export()
    menu = make_menu_archive(extra={'Event_text_.fmg': {10010710: 'Use it? Yes or no?'}})
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-links-') as temp:
        temp = Path(temp)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / texts.MENU_RELATIVE).parent.mkdir(parents=True)
        (game / texts.MENU_RELATIVE).write_bytes(menu)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1280, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    select(page, 'EquipParamGoods', 100)
                    # Each record link is a hoverable face plus a finder button.
                    for key in ('replaceItemId', 'magicId'):
                        assert face(page, key).count() == 1, key
                        assert page.locator(
                            '.ds1-reference-field .ds1-find-reference:visible').count() >= 1
                    assert face(page, 'replaceItemId').locator('.lex-hoverable').count() == 1
                    # Hovering previews the linked record; clicking opens it.
                    face(page, 'magicId').locator('.lex-hoverable').hover()
                    page.locator('.lex-hover-preview').first.wait_for()
                    face(page, 'magicId').locator('.lex-hoverable').click()
                    page.wait_for_function(
                        'state.tab === "items" && state.sub === "spells"'
                        ' && state.row?.table === "Magic" && state.row?.id === 102')
                    # The picker button changes the target like any other edit.
                    page.locator('[data-subtab="consumables"]').click()
                    page.wait_for_function('state.sub === "consumables" && !state.pending')
                    select(page, 'EquipParamGoods', 100)
                    field = face(page, 'replaceItemId')
                    field.scroll_into_view_if_needed()
                    before = page.evaluate(
                        'state.row.fields.find(item => item.key === "replaceItemId").value')
                    page.locator(
                        '.ds1-reference-field:has(.ds1-reference-face[data-field-key="replaceItemId"])'
                        ' .ds1-find-reference').click()
                    search = page.locator('.lex-choice-popover-search')
                    search.wait_for()
                    target = page.evaluate('''() => {
                      const current = document.querySelector(
                        '.ds1-reference-face[data-field-key="replaceItemId"]').textContent;
                      const labels = [...document.querySelectorAll('.lex-choice-popover > button')]
                        .map(node => node.getAttribute('aria-label'));
                      return labels.find(label => label !== current);
                    }''')
                    assert target, 'picker shows no alternative choice'
                    search.fill(target)
                    choice = page.locator('.lex-choice-popover > button:not([hidden])').first
                    picked = choice.get_attribute('aria-label')
                    wanted = page.evaluate(
                        '''label => Object.entries(state.row.fields
                          .find(item => item.key === "replaceItemId").enum)
                          .find(([, name]) => name === label)[0]''', arg=picked)
                    assert str(before) != str(wanted)
                    choice.click()
                    page.wait_for_function(
                        '(want) => state.pending === 0 && String(state.row.fields'
                        '.find(item => item.key === "replaceItemId").value) === want',
                        arg=str(wanted))
                    assert picked in face(page, 'replaceItemId').inner_text()
                    assert page.locator('.lex-choice-popover').count() == 0
                    # The dialog line reads beside its number.
                    dialog = page.locator(
                        '.ds1-dialog-row [data-field-key="yesNoDialogMessageId"][data-lex-dialog]')
                    assert dialog.count() == 1
                    assert dialog.input_value() == 'Use it? Yes or no?'
                    # An effect face opens the Effects tab.
                    page.locator('[data-subtab="rings"]').click()
                    page.wait_for_function('state.sub === "rings" && state.row && !state.pending')
                    select(page, 'EquipParamAccessory', 100)
                    assert face(page, 'refId').count() == 1
                    face(page, 'refId').locator('.lex-hoverable').click()
                    page.wait_for_function(
                        'state.tab === "effects" && state.row?.table === "SpEffectParam"'
                        ' && state.row?.id === 101')
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('record links browser check passed')


if __name__ == '__main__':
    main()
