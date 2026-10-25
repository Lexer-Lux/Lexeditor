"""Record links render hoverable faces with thing-finder buttons.

A goods row with an item, a spell and a dialog reference shows a
hoverable face plus a finder button for each record link (clicking the
face opens the linked record; the button opens the shared thing finder
to hold-to-choose another target), and the dialog line as a hoverable
message face with its own finder. An accessory's effect link is picked
from the Effects tab and
opens it from its face. Linked items show their menu icons; a
missing target stays text with no icon.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from drb_fixture import make_dcx, make_drb, sprite_shape  # noqa: E402
from ds1_fixture import make_archive, make_menu_archive  # noqa: E402
from tpf_fixture import make_dds_rgba, make_tpf  # noqa: E402
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


def release_hold(page):
    # Releasing over the candidate's old spot clicks the list row that
    # took its place after navigation and reselects mid-test. The
    # divider swallows a bare click, so release there instead. The DOM
    # rebuilds under us while navigating, so retry until one sticks.
    box = None
    for _ in range(30):
        divider = page.locator('.lex-list-detail-divider').first
        try:
            divider.wait_for(timeout=2000)
        except Exception:
            continue
        box = divider.bounding_box()
        if box:
            break
    assert box, 'no divider to release the hold over'
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.mouse.up()


def show_face(page, key):
    """Click through the record's panel tabs until the link face shows."""
    tabs = page.locator('.lex-tabbed-panel [data-subtab]')
    for index in range(tabs.count()):
        if face(page, key).count():
            return
        tab_id = tabs.nth(index).get_attribute('data-subtab')
        tabs.nth(index).click()
        page.wait_for_function('(id)=>state.itemTab===id', arg=tab_id)
    assert face(page, key).count() == 1, key


def show_field(page, key):
    """Click through the record's panel tabs until the field shows."""
    tabs = page.locator('.lex-tabbed-panel [data-subtab]')
    field = page.locator(f'[data-field-key="{key}"]:visible')
    for index in range(tabs.count()):
        if field.count():
            return
        tab_id = tabs.nth(index).get_attribute('data-subtab')
        tabs.nth(index).click()
        page.wait_for_function('(id)=>state.itemTab===id', arg=tab_id)
    assert field.count() == 1, key


def main():
    errors = []
    document = ItemDocument(make_archive({'SpEffectParam': [100, 101, 102],
                                               'EquipParamGoods': [100, 101, 102, 103]}))
    poke(document, 'EquipParamGoods', 100, 'replaceItemId', 100)
    poke(document, 'EquipParamGoods', 100, 'magicId', 102)
    poke(document, 'EquipParamGoods', 100, 'yesNoDialogMessageId', 10010710)
    poke(document, 'EquipParamAccessory', 100, 'refCategory', 2)
    poke(document, 'EquipParamAccessory', 100, 'refId', 101)
    poke(document, 'EquipParamGoods', 100, 'iconId', 1)
    poke(document, 'Magic', 102, 'iconId', 1)
    poke(document, 'EquipParamGoods', 103, 'magicId', 400)
    raw = document.export()
    menu = make_menu_archive(extra={'Event_text_.fmg': {10010710: 'Use it? Yes or no?',
                                                                 10010711: 'Really use it?'}})
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-links-') as temp:
        temp = Path(temp)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / texts.MENU_RELATIVE).parent.mkdir(parents=True)
        (game / texts.MENU_RELATIVE).write_bytes(menu)
        menu_dir = game / 'menu'
        menu_dir.mkdir(parents=True)
        menu_dir.joinpath('menu.drb').write_bytes(make_drb(['Icon00'], {
            'Icon': [('EquIcon_0001', sprite_shape((0, 0, 0, 0), (83, 1, 163, 91), 0))]}))
        sheet = make_dds_rgba(512, 512, [(0, 255, 0, 255)] * (512 * 512))
        menu_dir.joinpath('menu_0.tpf.dcx').write_bytes(make_dcx(make_tpf([('Icon00', sheet)])))
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
                        show_face(page, key)
                        assert page.locator(
                            '.ds1-reference-field .ds1-find-reference:visible').count() >= 1
                    show_face(page, 'replaceItemId')
                    assert face(page, 'replaceItemId').locator('.lex-hoverable').count() == 1
                    # Linked items show their menu icons once the menu files are installed.
                    for key in ('replaceItemId', 'magicId'):
                        show_face(page, key)
                        icon = face(page, key).locator('.lex-hoverable img.lex-hoverable-icon')
                        assert icon.count() == 1, key
                        assert (icon.get_attribute('src') or '').startswith('/api/icon?table='), key
                        page.wait_for_function('(key) => { const img = document.querySelector(`.ds1-reference-face[data-field-key="${key}"] .lex-hoverable img.lex-hoverable-icon`); return img && img.naturalWidth > 0; }', arg=key)
                    # A missing target stays text: no hoverable, no icon.
                    select(page, 'EquipParamGoods', 103)
                    show_face(page, 'magicId')
                    missing = face(page, 'magicId')
                    assert missing.locator('.lex-hoverable').count() == 0
                    assert missing.locator('img').count() == 0
                    select(page, 'EquipParamGoods', 100)
                    # Hovering previews the linked record; clicking opens it.
                    show_face(page, 'magicId')
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
                    show_face(page, 'replaceItemId')
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
                    release_hold(page)
                    wanted = int(picked[0].split(':')[1])
                    assert wanted != before
                    page.wait_for_function(
                        '(want) => state.sub === "consumables" && state.pending === 0'
                        ' && state.row?.fields?.find(item => item.key === "replaceItemId")?.value === want',
                        arg=wanted)
                    show_face(page, 'replaceItemId')
                    assert picked[1] in face(page, 'replaceItemId').inner_text()
                    # The dialog line is a hoverable message face with a finder.
                    show_field(page, 'yesNoDialogMessageId')
                    dialog = page.locator(
                        '.ds1-dialog-row [data-field-key="yesNoDialogMessageId"][data-lex-dialog]')
                    assert dialog.count() == 1
                    assert 'lex-hoverable' in (dialog.get_attribute('class') or '')
                    assert dialog.inner_text() == 'Use it? Yes or no?'
                    dialog.hover()
                    preview = page.locator('.lex-hover-preview').first
                    preview.wait_for()
                    assert 'Use it? Yes or no?' in preview.inner_text()
                    finder = page.locator(
                        '.ds1-reference-field:has(.ds1-dialog-row) .ds1-find-reference')
                    assert 'lex-thing-finder' in (finder.get_attribute('class') or '')
                    # Clicking the face opens the message in the Text tab.
                    dialog.click()
                    page.wait_for_function('state.tab === "text" && state.sub === "fmg-event-text"'
                        ' && state.row?.table === "Event_text_.fmg" && state.row?.id === 10010710')
                    page.locator('button[data-tab="items"]').click()
                    page.wait_for_function('state.tab === "items" && state.sub === "consumables"'
                        ' && state.row?.table === "EquipParamGoods" && state.row?.id === 100'
                        ' && !state.pending')
                    # The finder holds another message to choose it like any edit.
                    show_field(page, 'yesNoDialogMessageId')
                    page.locator(
                        '.ds1-reference-field:has(.ds1-dialog-row) .ds1-find-reference').click()
                    page.wait_for_function('state.tab === "text" && state.sub === "fmg-event-text"')
                    page.wait_for_function(
                        "document.querySelectorAll('.lex-search-candidate').length >= 2")
                    picked = page.evaluate("""() => {
                      const rows = [...document.querySelectorAll('.lex-search-candidate')];
                      const other = rows.find(row => row.getAttribute('data-key')
                        !== 'Event_text_.fmg:10010710');
                      return other.getAttribute('data-key');
                    }""")
                    assert picked == 'Event_text_.fmg:10010711', picked
                    box = page.locator(f'.lex-search-candidate[data-key="{picked}"]'
                                       ).bounding_box()
                    page.mouse.move(box['x'] + 40, box['y'] + box['height'] / 2)
                    page.mouse.down()
                    page.wait_for_function(
                        'document.querySelector(".lex-searcher-bar") === null', timeout=10000)
                    release_hold(page)
                    page.wait_for_function(
                        'state.sub === "consumables" && state.pending === 0'
                        ' && state.row?.fields?.find(item => item.key === "yesNoDialogMessageId")'
                        '?.value === 10010711')
                    show_field(page, 'yesNoDialogMessageId')
                    assert page.locator(
                        '.ds1-dialog-row [data-field-key="yesNoDialogMessageId"][data-lex-dialog]'
                        ).inner_text() == 'Really use it?'
                    # An effect link is picked from the Effects tab itself.
                    page.locator('[data-subtab="rings"]').click()
                    page.wait_for_function('state.sub === "rings" && state.row && !state.pending')
                    select(page, 'EquipParamAccessory', 100)
                    show_face(page, 'refId')
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
                    release_hold(page)
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
