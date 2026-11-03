"""DS1 UI uses the theme font; loading screens keep Lexend.

The theme declares the serif stack as --lex-font, and body text, field
labels, type rails, the unit multiplier and boolean marks all paint in
it instead of falling back to Lexend.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

SERIF = 'Palatino Linotype'


def family(page, selector):
    return page.locator(selector).first.evaluate('n => getComputedStyle(n).fontFamily')


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-theme-font-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
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
                    page.wait_for_function("state.tab==='items'&&state.rows&&state.rows.length")
                    assert SERIF in family(page, 'body'), family(page, 'body')
                    row = page.locator('.lex-list-row[data-key="EquipParamGoods:100"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    page.wait_for_function(
                        "state.row && `${state.row.table}:${state.row.id}` === 'EquipParamGoods:100'")
                    assert SERIF in family(page, '.lex-detail-field-label'), \
                        family(page, '.lex-detail-field-label')
                    assert SERIF in family(page, '.lex-field-type-name'), \
                        family(page, '.lex-field-type-name')
                    page.evaluate('''() => {
                      const U = LexeditorUI;
                      const host = document.createElement('div');
                      host.id = 'font-probe';
                      host.append(U.unitField(U.el('input', {value: 1}), '×'),
                        U.booleanMark(true));
                      document.querySelector('main').append(host);
                    }''')
                    assert SERIF in family(page, '#font-probe .lex-unit-multiplier'), \
                        family(page, '#font-probe .lex-unit-multiplier')
                    assert SERIF in family(page, '#font-probe .lex-boolean-mark'), \
                        family(page, '#font-probe .lex-boolean-mark')
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 theme font: the UI paints in the serif stack passed.')


if __name__ == '__main__':
    main()
