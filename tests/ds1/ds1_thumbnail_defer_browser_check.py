"""Model thumbnails below the fold wait off the serial snapshot queue.

Thirty rows each hold a Ds1Preview.thumbnail with a geometry URL that
fails fast. Visible rows join the queue (their failures land as the
shared no-thumbnail marker); rows below the fold keep pending images
with live visibility observers instead of hogging turns. Scrolling
them into view joins and settles them too.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright  # noqa: E402

BUILD = """() => {
  const list = document.createElement('div');
  list.id = 'rows';
  list.style.cssText = 'height:300px;overflow-y:auto;';
  for (let i = 0; i < 30; i++) {
    const row = document.createElement('div');
    row.className = 'probe-row';
    row.style.cssText = 'height:40px;display:flex;align-items:center;';
    row.append(window.Ds1Preview.thumbnail(
      {url: `/api/chr/geometry?chr=c900${i}`, label: `row ${i}`}));
    list.append(row);
  }
  document.querySelector('main').append(list);
}"""

STATE = """() => [...document.querySelectorAll('#rows .probe-row')].map(row => {
  if (row.querySelector('.lex-no-thumbnail')) return 'settled';
  const img = row.querySelector('img.ds1-model-thumbnail');
  if (!img) return 'missing';
  return img._lexVisibility ? 'waiting' : 'begun';
})"""


def main():
    errors = []
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1200, 'height': 500})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('http://fixture/**', lambda r: r.fulfill(
                body='<main></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.add_script_tag(path=str(ROOT / 'plugins/ds1/preview.js'))
            page.evaluate(BUILD)
            page.wait_for_function(
                """() => document.querySelector(
                    '#rows .probe-row .lex-no-thumbnail') !== null""",
                timeout=30000)
            page.wait_for_timeout(2000)
            states = page.evaluate(STATE)
            assert len(states) == 30, states
            assert states[0] == 'settled', states
            waiting = sum(1 for item in states if item == 'waiting')
            assert waiting >= 10, states
            assert 'missing' not in states, states
            # A jump to the bottom skips the middle rows past the
            # viewport, so walk down: every row shows and joins.
            for step in range(1, 8):
                page.evaluate(
                    "document.querySelector('#rows').scrollTo(0, %d)" % (step * 200))
                page.wait_for_timeout(800)
            page.wait_for_function(
                """() => [...document.querySelectorAll(
                    '#rows .probe-row')].every(
                    row => row.querySelector('.lex-no-thumbnail'))""",
                timeout=60000)
            assert not errors, errors
            print('DS1 thumbnail defer browser check passed')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
