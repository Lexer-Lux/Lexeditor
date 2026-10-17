"""Record links render hoverable faces with thing-finder buttons.

A goods row with an item, a spell and a dialog reference shows a
hoverable face plus a finder button for each record link (clicking the
face opens the linked record; the button opens the shared thing finder
to hold-to-choose another target), and the dialog line beside its
number. An accessory's effect link is picked from the Effects tab and
opens it from its face.
"""
import os
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
    document = ItemDocument(make_archive({'SpEffectParam': [100, 101, 102],
                                               'EquipParamGoods': [100, 101, 102, 103]}))
    poke(document, 'EquipParamGoods', 100, 'replaceItemId', 100)
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
                    # The finder button is the shared thing finder: a prompt
                    # up top, the menu bar blocked out, a way back, and
                    # hold-to-choose.
                    page.locator('[data-subtab="consumables"]').click()
                    page.wait_for_function('state.sub === "consumables" && !state.pending')
                    select(page, 'EquipParamGoods', 100)
                    field = face(page, 'replaceItemId')
                    field.scroll_into_view_if_needed()
                    finder = page.locator(
                        '.ds1-reference-field:has(.ds1-reference-face[data-field-key="replaceItemId"])'
                        ' .ds1-find-reference')
                    assert 'lex-thing-finder' in (finder.get_attribute('class') or '')
                    before = page.evaluate(
                        'state.row.fields.find(item => item.key === "replaceItemId").value')
                    finder.click()
                    bar = page.locator('.lex-searcher-bar')
                    bar.wait_for()
                    assert page.locator('.lex-searcher-prompt').inner_text().startswith(
                        'Choose the item for ')
                    assert not page.locator('.lex-nav-frame').is_visible()
                    page.wait_for_function(
                        "document.querySelectorAll('.lex-search-candidate').length >= 2")
                    shots = os.environ.get('LEXEDITOR_TEST_SHOTS')
                    if shots:
                        page.screenshot(path=str(Path(shots) / 'ds1-thing-finder.png'))
                    # The back button shows the source record, locked; a
                    # second press returns to the candidates.
                    page.locator('.lex-searcher-context').click()
                    assert page.locator('#main').evaluate('node => node.inert')
                    assert 'blue return button' in bar.inner_text()
                    page.locator('.lex-searcher-context').click()
                    page.wait_for_function(
                        "document.querySelectorAll('.lex-search-candidate').length >= 2")
                    assert not page.locator('#main').evaluate('node => node.inert')
                    # Cancelling changes nothing and returns to the source.
                    page.get_by_role('button', name='Cancel selection', exact=True).click()
                    page.wait_for_function(
                        'state.sub === "consumables" && !state.pending'
                        ' && document.querySelector(".lex-searcher-bar") === null')
                    assert page.evaluate(
                        'state.row.fields.find(item => item.key === "replaceItemId").value') == before
                    assert page.locator('.lex-nav-frame').is_visible()
                    # Holding another candidate chooses it like any other edit.
                    finder.click()
                    bar.wait_for()
                    page.wait_for_function(
                        "document.querySelectorAll('.lex-search-candidate').length >= 2")
                    picked = page.evaluate("""before => {
                      const rows = [...document.querySelectorAll('.lex-search-candidate')];
                      const other = rows.find(row => row.getAttribute('data-key')
                        !== `EquipParamGoods:${before}`);
                      return [other.getAttribute('data-key'),
                        other.querySelector('[data-column-key="name"]').innerText.trim()];
                    }""", before)
                    assert picked[0], 'finder shows no alternative choice'
                    box = page.locator(f'.lex-search-candidate[data-key="{picked[0]}"]'
                                       ).bounding_box()
                    page.mouse.move(box['x'] + 40, box['y'] + box['height'] / 2)
                    page.mouse.down()
                    page.wait_for_function(
                        'document.querySelector(".lex-searcher-bar") === null', timeout=10000)
                    page.mouse.up()
                    wanted = int(picked[0].split(':')[1])
                    assert wanted != before
                    page.wait_for_function(
                        '(want) => state.sub === "consumables" && state.pending === 0'
                        ' && state.row?.fields?.find(item => item.key === "replaceItemId")?.value === want',
                        arg=wanted)
                    assert picked[1] in face(page, 'replaceItemId').inner_text()
                    # The dialog line reads beside its number.
                    dialog = page.locator(
                        '.ds1-dialog-row [data-field-key="yesNoDialogMessageId"][data-lex-dialog]')
                    assert dialog.count() == 1
                    assert dialog.input_value() == 'Use it? Yes or no?'
                    # An effect link is picked from the Effects tab itself.
                    page.locator('[data-subtab="rings"]').click()
                    page.wait_for_function('state.sub === "rings" && state.row && !state.pending')
                    select(page, 'EquipParamAccessory', 100)
                    assert face(page, 'refId').count() == 1
                    effect_before = page.evaluate(
                        'state.row.fields.find(item => item.key === "refId").value')
                    page.locator(
                        '.ds1-reference-field:has(.ds1-reference-face[data-field-key="refId"])'
                        ' .ds1-find-reference').click()
                    page.wait_for_function('state.tab === "effects" && state.sub === "effects-all"')
                    page.wait_for_function(
                        "document.querySelectorAll('.lex-search-candidate').length >= 2")
                    picked = page.evaluate("""before => {
                      const rows = [...document.querySelectorAll('.lex-search-candidate')];
                      const other = rows.find(row => row.getAttribute('data-key')
                        !== `SpEffectParam:${before}`);
                      return [other.getAttribute('data-key'),
                        other.querySelector('[data-column-key="name"]').innerText.trim()];
                    }""", effect_before)
                    assert picked[0], 'finder shows no alternative effect'
                    box = page.locator(f'.lex-search-candidate[data-key="{picked[0]}"]'
                                       ).bounding_box()
                    page.mouse.move(box['x'] + 40, box['y'] + box['height'] / 2)
                    page.mouse.down()
                    page.wait_for_function(
                        'document.querySelector(".lex-searcher-bar") === null', timeout=10000)
                    page.mouse.up()
                    effect_wanted = int(picked[0].split(':')[1])
                    assert effect_wanted != effect_before
                    page.wait_for_function(
                        '(want) => state.tab === "items" && state.sub === "rings"'
                        ' && state.pending === 0'
                        ' && state.row?.fields?.find(item => item.key === "refId")?.value === want',
                        arg=effect_wanted)
                    assert picked[1] in face(page, 'refId').inner_text()
                    # An effect face opens the Effects tab.
                    face(page, 'refId').locator('.lex-hoverable').click()
                    page.wait_for_function(
                        '(want) => state.tab === "effects" && state.row?.table === "SpEffectParam"'
                        ' && state.row?.id === want',
                        arg=effect_wanted)
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('record links browser check passed')


if __name__ == '__main__':
    main()
