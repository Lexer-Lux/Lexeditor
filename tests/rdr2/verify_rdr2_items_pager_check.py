"""The real Items pagination bar carries only what it can paint.

Runs against the installed RDR2 project read-only, because the mangled bar only
appears with a catalogue as large as the game's: its filters are as wide as the
game's own category names. Nothing is written.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.rdr2.plugin import Rdr2Session
from plugins.rdr2.paths import PROJECT_ROOT
from playwright.sync_api import sync_playwright

if not (PROJECT_ROOT / "GameplayTweaks" / "GameplayTweaks.ini").is_file():
    raise FileNotFoundError(f"Missing RDR2 project fixture: {PROJECT_ROOT}")

MEASURE = """() => {
  const bar = document.querySelector('.lex-pager');
  const right = bar.querySelector('.lex-pager-right');
  return {
    savebar: bar.querySelectorAll('.savebar,.dirty').length,
    text: bar.innerText.replace(/\\n/g, '|'),
    bar: [bar.scrollHeight, bar.clientHeight],
    right: [right.scrollHeight, right.clientHeight],
    filterRows: [...new Set([...right.querySelectorAll('select')]
      .map(node => Math.round(node.getBoundingClientRect().top)))].length,
  };
}"""

PENDING = """() => {
  const input = document.querySelector('.lex-detail-panel-heading input');
  input.value = 'Pager probe';
  input.dispatchEvent(new Event('change'));
}"""

with Rdr2Session() as session, sync_playwright() as play:
    browser = play.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(session.url)
    page.wait_for_function("typeof state!=='undefined'&&!state.booting&&!!state.config",
                           timeout=120000)
    page.evaluate("()=>navigate('items')")
    page.wait_for_selector('.lex-pager')
    page.wait_for_timeout(800)
    page.evaluate(PENDING)
    page.wait_for_timeout(600)
    assert page.evaluate('dirtyCount()') >= 1, 'the probe edit did not register'
    measured = page.evaluate(MEASURE)
    assert measured['savebar'] == 0, f"the pager carries the save state: {measured}"
    assert 'unsaved change' not in measured['text'], measured['text'][:200]
    assert measured['bar'][0] <= measured['bar'][1] + 1, measured
    assert measured['right'][0] <= measured['right'][1] + 1, measured
    assert measured['filterRows'] == 1, measured
    assert not errors, errors
    print('PASS: the items pagination bar holds its filters on one row and no save state:',
          measured['bar'], measured['right'])
    browser.close()
