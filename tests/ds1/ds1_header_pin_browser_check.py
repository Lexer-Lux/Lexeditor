"""The header thumbnail carries a pin that adds the Icon column.

Hovering the detail header's icon reveals its pin ghost; clicking it
pins the record's own picture as a table column through the same
toggle as any property.
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.formats import ItemDocument  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main():
    errors = []
    document = ItemDocument(make_archive({'EquipParamGoods': [100, 101, 102, 103]}))
    raw = document.export()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-hdrpin-') as temp:
        temp = Path(temp)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
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
                    page.wait_for_function(
                        'document.querySelector(".lex-plugin-loading-screen") === null',
                        timeout=30000)
                    page.wait_for_function('state.pending === 0', timeout=30000)
                    page.locator('.lex-list-row[data-key="EquipParamGoods:100"]').click()
                    page.wait_for_function(
                        '`${state.row.table}:${state.row.id}` === "EquipParamGoods:100"')
                    icon = page.locator(
                        '.lex-detail-panel-heading .lex-detail-panel-icon')
                    pin = icon.locator(':scope > .lex-column-pin')
                    assert pin.count() == 1, 'header pin attached'
                    assert 'pin:icon' not in page.evaluate(
                        '''() => [...document.querySelectorAll(
                            '.lex-column-list-head-cell')].map(
                            h => h.getAttribute('data-column-key'))''')
                    icon.hover()
                    page.wait_for_function(
                        '''() => getComputedStyle(document.querySelector(
                            '.lex-detail-panel-icon > .lex-column-pin')).opacity === "0.75"''',
                        timeout=5000)
                    pin.click()
                    page.wait_for_function(
                        '''() => [...document.querySelectorAll(
                            '.lex-column-list-head-cell')].some(
                            h => h.getAttribute('data-column-key') === "pin:icon")''',
                        timeout=10000)
                    cells = page.locator(
                        '.lex-column-list-cell[data-column-key="pin:icon"]')
                    assert cells.count() > 0, 'icon cells render'
                    assert not errors, errors
                    print('DS1 header pin browser check passed')
                finally:
                    browser.close()
        finally:
            session.stop()


if __name__ == '__main__':
    main()
