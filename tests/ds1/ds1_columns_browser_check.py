"""The COLUMNS divider control takes DS1 items past the width fit.

An explicit column choice beats the fit: the fit guards the default, never
the maximum. Covers the multi-section fallback (consumables) and the tabbed
detail (weapons). Fails while the increase button is capped at the fit.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

COLUMNS = """() => [...document.querySelectorAll('.lex-tweaks-paged .lex-tweak-column')]
  .filter(column => column.offsetParent && column.childElementCount).length"""

NO_HORIZONTAL_SCROLL = """() => {
  const paged = document.querySelector('.lex-tweaks-paged');
  return paged.scrollWidth <= paged.clientWidth + 1;
}"""


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-columns-') as folder:
        game, mod = Path(folder) / 'game', Path(folder) / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1100, 'height': 800})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="items"]').click()
                    page.wait_for_function('state.tab==="items" && state.rows.length>0 && !state.error')
                    for sub in ('consumables', 'weapons'):
                        page.locator(f'[data-subtab="{sub}"]').click()
                        page.wait_for_function(f'state.sub==="{sub}" && state.row && !state.error')
                        page.wait_for_timeout(600)
                        fitted = page.evaluate(COLUMNS)
                        assert fitted >= 1, (sub, fitted)
                        divider = page.locator('.lex-list-detail-divider')
                        divider.hover(timeout=5000)
                        page.wait_for_timeout(300)
                        control = page.locator('.lex-detail-column-control')
                        assert control.count() == 1
                        increase = control.locator('[aria-label="Increase detail columns"]')
                        assert increase.is_enabled(), (sub, 'increase capped at the fit')
                        increase.click()
                        page.wait_for_timeout(400)
                        assert page.evaluate(COLUMNS) == fitted + 1, sub
                        assert page.evaluate(NO_HORIZONTAL_SCROLL), (sub, 'horizontal scrollbar')
                        control.click(button='right')
                        page.wait_for_timeout(400)
                        assert page.evaluate(COLUMNS) == fitted, (sub, 'right-click did not refit')
                        assert page.locator('[data-lex-detail-columns]').count() == 0, sub
                    if output:
                        page.screenshot(path=str(output / 'columns.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('DS1 columns passed.')


if __name__ == '__main__':
    main()
