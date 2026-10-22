"""DS1 descriptions use the auto-fit textarea: no scrollbars beside space.

An item's Full description builds through the shared textArea, which
sizes to its content. Short text shows no scrollbar, and longer text
grows the box instead of scrolling inside a fixed one.
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


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-description-autofit-') as folder:
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
                    row = page.locator('.lex-list-row[data-key="EquipParamGoods:100"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    page.wait_for_function(
                        "state.row && `${state.row.table}:${state.row.id}` === 'EquipParamGoods:100'")
                    page.locator('.lex-tabbed-panel [data-subtab="description"]').click()
                    box = page.locator('.lex-text-area')
                    page.wait_for_function(
                        "document.querySelector('.lex-text-area') && "
                        "document.querySelector('.lex-text-area').value.includes('souls safe')")
                    short = box.evaluate('''n => ({client: n.clientHeight, scroll: n.scrollHeight,
                        box: n.getBoundingClientRect().height})''')
                    assert short['scroll'] <= short['client'] + 1, \
                        f"short text scrolls inside a fixed box: {short}"
                    box.fill('\n'.join(f'Line {index} of the saga' for index in range(12)))
                    page.wait_for_function(
                        "document.querySelector('.lex-text-area').getBoundingClientRect().height"
                        f" > {short['box']}")
                    tall = box.evaluate('n => ({client: n.clientHeight, scroll: n.scrollHeight})')
                    assert tall['scroll'] <= tall['client'] + 1, \
                        f"long text scrolls instead of growing the box: {tall}"
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 description autofit: textareas size to content passed.')


if __name__ == '__main__':
    main()
