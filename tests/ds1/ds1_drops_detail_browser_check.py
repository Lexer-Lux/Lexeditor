"""Drops detail reads slot by slot: eight Drop sections plus Lot.

Each slot's item/count pair, category, rate, amount and flags sit under
its own header; the four lot-level settings sit under Lot. No more flat
wall. The pair's item lane keeps the row while the count lane compacts
to a 1-2 digit box with no reference rail or stepper.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

SECTIONS = """() => [...document.querySelectorAll(
  '.lex-detail-panel .lex-detail-section')].map(section => [
    section.querySelector('.lex-detail-section-title-text').textContent.trim(),
    section.querySelectorAll('.lex-detail-field').length])"""


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-drops-') as folder:
        game = Path(folder) / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate("navigate('drops','drops')")
                    page.wait_for_function("state.tab==='drops'&&state.rows&&state.rows.length")
                    page.locator('.lex-list-row').first.click()
                    page.wait_for_function("state.row && state.row.table==='ItemLotParam'")
                    page.wait_for_timeout(800)
                    sections = page.evaluate(SECTIONS)
                    assert [title for title, _ in sections] == (
                        [f'Drop {slot}' for slot in range(1, 9)] + ['Lot']), sections
                    for title, count in sections:
                        assert count == (4 if title == 'Lot' else 7), (title, count)
                    lanes = page.evaluate("""() => [...document.querySelectorAll(
                      '.ds1-item-count-pair')].slice(0, 3).map(pair => {
                      const item = pair.children[0].getBoundingClientRect().width;
                      const count = pair.children[1].getBoundingClientRect().width;
                      const host = pair.children[1].querySelector(
                        '.lex-source-control-internal');
                      const input = pair.children[1].querySelector('input[type=number]');
                      return {item: Math.round(item), count: Math.round(count),
                        compact: host ? host.classList.contains('lex-compact-box') : null,
                        padRight: input ? getComputedStyle(input).paddingRight : null};
                    })""")
                    assert lanes, 'expected item/count pair rows'
                    for lane in lanes:
                        assert lane['compact'], lane
                        assert lane['count'] <= 60, lane
                        assert lane['item'] > lane['count'] * 2, lane
                        assert float(lane['padRight'].replace('px', '')) <= 20, lane
                finally:
                    browser.close()
        finally:
            session.stop()
        assert errors == [], errors
        print('PASS: drops detail groups eight slots plus Lot')


if __name__ == '__main__':
    main()
