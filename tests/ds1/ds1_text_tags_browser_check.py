"""The text tab's tag buttons insert the game's codes at the caret.

Lexer: the text tab shows <?tags?> with no word on what they are. FMG
text and menu labels now edit above tag buttons, grouped by family,
each naming what it puts in. Clicking one inserts at the caret and
commits like a typed edit; a lookup parks the caret for its id.
"""
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def pinned(page, table, row_id):
    page.wait_for_function(
        f'state.selected === "{table}:{row_id}" && state.row && state.row.table === "{table}"'
        f' && state.row.id === {row_id} && document.querySelector(".lex-detail-panel-name")'
        "?.textContent?.includes(state.row.name)")


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-text-tags-') as folder:
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
                    page.goto(session.url, timeout=120000)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('button[data-tab="text"]').click()
                    page.wait_for_function('state.tab === "text" && !state.error')
                    page.locator('[data-subtab="fmg-dialogue"]').click()
                    page.wait_for_function('state.sub === "fmg-dialogue" && state.rows.length === 2')
                    page.locator('.lex-column-list .lex-list-row', has_text='Yes.').click()
                    pinned(page, 'Dialogue_.fmg', 10)
                    # Six families under the textarea, the first one open.
                    bar = page.locator('.lex-ds1-text-editor .lex-tag-bar')
                    assert bar.count() == 1
                    names = bar.locator('.lex-tag-group-name').evaluate_all(
                        'nodes => nodes.map(node => node.textContent.trim())')
                    assert names == ['Names', 'Values', 'Buttons', 'Lookups',
                                     'Soapstone', 'Forge'], names
                    assert bar.locator('.lex-tag-group').nth(0).evaluate(
                        'node => node.open') is True
                    # Every button says what it puts in.
                    assert bar.locator('.lex-tag-button[title=""]').count() == 0
                    # A name tag inserts at the caret and commits the edit.
                    area = page.locator('textarea[data-field-key="text"]')
                    # A placed caret, not a click: focusing selects the
                    # whole box a frame later, which would replace instead
                    # of insert. The caret lands after that selection does.
                    area.evaluate('node => node.focus()')
                    page.wait_for_timeout(300)
                    area.evaluate('node => node.setSelectionRange('
                                  'node.value.length, node.value.length)')
                    bar.locator('.lex-tag-button', has_text='deadName').click()
                    assert area.input_value() == 'Yes.<?deadName?>'
                    page.wait_for_function('state.pending === 0 && state.dirty > 0')
                    # A lookup parks the caret for its id.
                    bar.locator('.lex-tag-group', has_text='Lookups').locator(
                        '.lex-tag-group-name').click()
                    bar.locator('.lex-tag-button', has_text='sysmsg@id').click()
                    assert area.input_value() == 'Yes.<?deadName?><?sysmsg@?>'
                    caret = area.evaluate('node => node.selectionStart')
                    assert caret == len('Yes.<?deadName?><?sysmsg@'), caret
                    # Menu labels get the same buttons on one line.
                    page.locator('[data-subtab="menu-labels"]').click()
                    page.wait_for_function('state.sub === "menu-labels" && state.rows.length === 3')
                    page.locator('.lex-column-list .lex-list-row', has_text='Magic defense label').click()
                    pinned(page, 'MenuText', 102204)
                    assert page.locator('.lex-ds1-text-editor input[data-field-key="label"]').count() == 1
                    control = page.locator('input[data-field-key="label"]')
                    control.evaluate('node => node.focus()')
                    page.wait_for_timeout(300)
                    control.evaluate('node => node.setSelectionRange('
                                     'node.value.length, node.value.length)')
                    page.locator('.lex-ds1-text-editor .lex-tag-group', has_text='Values').locator(
                        '.lex-tag-group-name').click()
                    page.locator('.lex-ds1-text-editor .lex-tag-button',
                                 has_text=re.compile(r'^souls$')).click()
                    assert control.input_value() == 'MagDEF<?souls?>'
                    if output:
                        page.screenshot(path=str(output / 'text-tags.png'))
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty === 0 && state.pending === 0')
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    saved = texts.MenuDocument((mod / texts.MENU_RELATIVE).read_bytes())
                    assert saved.text('Dialogue_.fmg', 10) == 'Yes.<?deadName?><?sysmsg@?>'
                    assert saved.label('magicDefense') == 'MagDEF<?souls?>'
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('DS1 text tags passed.')


if __name__ == '__main__':
    main()
