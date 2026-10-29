"""Render the Text tab and follow armor defense links into it.

Menu labels are menu text with in-game names; armor defense fields link
to the label that names them. Every other menu FMG gets its own subtab
with one record per filled entry. Edits save into the mod project like
any other record.
"""
import sys
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.formats import ItemDocument
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright

def pinned(page, table, row_id):
    """Wait until selection, record and heading all name one row."""
    page.wait_for_function(
        f'state.selected === "{table}:{row_id}" && state.row && state.row.table === "{table}"'
        f' && state.row.id === {row_id} && document.querySelector(".lex-detail-panel-name")'
        "?.textContent?.includes(state.row.name)")


LINKS = (('Magic defense', 102204, 'MagDEF'), ('Fire defense', 102205, 'FireDEF'),
         ('Lightning defense', 102206, 'LitngDEF'))


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-text-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive(
            extra={'Dialogue_.fmg': {10: 'Yes.', 11: 'No.\nReally not.'}}))
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
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    # The Text tab opens on the three labels under their slot names.
                    page.locator('button[data-tab="text"]').click()
                    page.wait_for_function('state.tab === "text" && state.rows.length === 3 && !state.error')
                    # State lands before the rows render: wait for text.
                    page.wait_for_function(
                        'document.querySelector(".lex-column-list .lex-list-row")'
                        '.textContent.replace(/\u200b/g, "").trim() !== ""')
                    subs = page.locator('[data-subtab]').evaluate_all(
                        'nodes => nodes.map(node => node.getAttribute("data-subtab"))')
                    assert subs == ['fmg-dialogue', 'menu-labels', 'fmg-menu-text'], subs
                    names = page.locator('.lex-column-list .lex-list-row').evaluate_all(
                        'rows => rows.map(row => row.textContent.replace(/\\u200b/g, "").trim()).filter(Boolean)')
                    assert names == ['Fire defense label', 'Lightning defense label',
                                      'Magic defense label'], names
                    # Every FMG lists its filled entries named by first line.
                    page.locator('[data-subtab="fmg-dialogue"]').click()
                    page.wait_for_function('state.sub === "fmg-dialogue" && state.rows.length === 2')
                    # Non-empty is not enough here: the previous subtab's
                    # rows are still rendered (and non-empty) until the
                    # re-render lands, so wait for the new first row.
                    page.wait_for_function(
                        'document.querySelector(".lex-column-list .lex-list-row")'
                        '?.querySelector("[data-column-key=name] .lex-column-cell-text")'
                        '?.textContent.trim() === "No."')
                    spoken = page.locator('.lex-column-list .lex-list-row').evaluate_all(
                        'rows => rows.map(row => row.querySelector("[data-column-key=name] .lex-column-cell-text")?.textContent.trim()).filter(Boolean)')
                    assert spoken == ['No.', 'Yes.'], spoken
                    # Every armor defense label links to its menu label.
                    for label, text_id, _text in LINKS:
                        page.locator('button[data-tab="items"]').click()
                        page.wait_for_function('state.tab === "items" && state.rows.length > 0')
                        page.locator('[data-subtab="armor"]').click()
                        pinned(page, 'EquipParamProtector', 100)
                        page.locator('.lex-tabbed-panel [data-subtab="defense"]').click()
                        page.wait_for_function('state.itemTab === "defense"')
                        selector = '.lex-hoverable[data-hover-target-id="%s"]' % text_id
                        page.wait_for_function(
                            'sel => document.querySelectorAll(sel).length === 1',
                            arg=selector)
                        link = page.locator(selector)
                        assert link.count() == 1, label
                        assert link.inner_text().strip() == label
                        link.click()
                        pinned(page, 'MenuText', text_id)
                        heading = page.locator('.lex-detail-panel-name').inner_text()
                        assert page.evaluate('state.row.id') == text_id, heading
                        assert page.evaluate('state.tab') == 'text'
                    # Hovering previews the label without leaving the armor.
                    page.locator('button[data-tab="items"]').click()
                    page.wait_for_function('state.tab === "items" && state.rows.length > 0')
                    page.locator('[data-subtab="armor"]').click()
                    pinned(page, 'EquipParamProtector', 100)
                    page.locator('.lex-tabbed-panel [data-subtab="defense"]').click()
                    page.wait_for_function('state.itemTab === "defense"')
                    page.locator('.lex-hoverable[data-hover-target-id="102204"]').hover()
                    preview = page.locator('.lex-hover-preview')
                    preview.wait_for(timeout=5000)
                    assert 'MagDEF' in preview.inner_text()
                    # Dialogue edits in a textarea, saves and reloads.
                    page.locator('button[data-tab="text"]').click()
                    page.wait_for_function('state.tab === "text" && !state.error')
                    page.locator('[data-subtab="fmg-dialogue"]').click()
                    page.wait_for_function('state.sub === "fmg-dialogue" && state.rows.length === 2')
                    page.locator('.lex-column-list .lex-list-row', has_text='Yes.').click()
                    pinned(page, 'Dialogue_.fmg', 10)
                    area = page.locator('textarea[data-field-key="text"]')
                    assert area.input_value() == 'Yes.'
                    area.fill('Yes, kindling.')
                    area.press('Tab')
                    page.wait_for_function('state.pending === 0 && state.dirty > 0')
                    # Labels edit, save and reload like any other record.
                    page.locator('[data-subtab="menu-labels"]').click()
                    page.wait_for_function('state.sub === "menu-labels" && state.rows.length === 3')
                    page.locator('.lex-column-list .lex-list-row', has_text='Magic defense label').click()
                    pinned(page, 'MenuText', 102204)
                    control = page.locator('input[data-field-key="label"][type="text"]')
                    control.fill('MagAbsorb')
                    control.press('Tab')
                    page.wait_for_function(
                        'state.pending === 0 && state.row.fields.find(f=>f.key==="label").value'
                        ' === "MagAbsorb"')
                    row = request_json(session.url + 'api/row?table=MenuText&id=102204')['row']
                    assert row['name'] == 'Magic defense label'
                    assert next(f['value'] for f in row['fields'] if f['key'] == 'label') == 'MagAbsorb'
                    if output:
                        page.screenshot(path=str(output / 'text.png'))
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty === 0 && state.pending === 0')
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    saved = texts.MenuDocument((mod / texts.MENU_RELATIVE).read_bytes())
                    assert saved.label('magicDefense') == 'MagAbsorb'
                    assert saved.text('Dialogue_.fmg', 10) == 'Yes, kindling.'
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('DS1 text tab passed.')


if __name__ == '__main__':
    main()
