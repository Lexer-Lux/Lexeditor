"""Drops go-to lands on the open map's own dropper, never another viewport.

Lot 100 drops in both fixture maps. With the second map open, go-to used
to jump to the first alphabetical map and mount its whole viewport as a
side effect; on a large real map that froze the UI. It now prefers the
open map and focuses in place. A lot nothing drops toasts briefly
instead of navigating. Every wait carries a timeout, so a hang fails
the test instead of wedging the runner.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from msb_fixture import build_msb  # noqa: E402
from plugins.ds1.msb import MAP_DIR  # noqa: E402
from plugins.ds1.store import RELATIVE  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

MAP_A = 'm10_00_00_00.msb'
MAP_B = 'm10_01_00_00.msb'
FOE = 120000


def test_drops_goto_prefers_the_open_map():
    errors = []
    raw = make_archive(field_values={'NpcParam': {FOE: {'itemLotId_1': 100}}})
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-drops-goto-') as temp:
        game = Path(temp) / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / MAP_A).write_bytes(build_msb(parts=(('enemy', 2, 0, 0, FOE),)))
        (game / MAP_DIR / MAP_B).write_bytes(build_msb(parts=(('enemy', 2, 7, 0, FOE),)))
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.locator('button[data-tab="maps"]').click()
                    page.wait_for_function(
                        'state.tab==="maps" && state.mapView && state.rows.length>0 && !state.error',
                        timeout=60000)
                    assert page.evaluate('state.mapId') == MAP_A
                    # Without a preferred map the first alphabetical dropper wins.
                    first = page.evaluate(
                        "fetch('/api/world/locate?table=ItemLotParam&id=100')"
                        '.then(r => r.json()).then(j => j.map)')
                    assert first == MAP_A, first
                    preferred = page.evaluate(
                        f"fetch('/api/world/locate?table=ItemLotParam&id=100&map={MAP_B}')"
                        '.then(r => r.json()).then(j => j.map + ":" + j.key)')
                    assert preferred == f'{MAP_B}:2:7', preferred
                    # Open the second map: go-to must stay on it, not jump maps.
                    page.locator('[data-maps-side] .lex-list-row', has_text=MAP_B).click()
                    page.wait_for_function(f'state.mapId==="{MAP_B}" && !!state.mapView',
                                           timeout=60000)
                    page.wait_for_function('!!viewportCtl', timeout=60000)
                    assert page.evaluate('state.dirTab') == 'drops'
                    page.locator('[data-maps-dir] [data-goto="ItemLotParam:100"]').click()
                    page.wait_for_function(f'state.selected==="{MAP_B}:2:7"', timeout=30000)
                    assert page.evaluate('state.mapId') == MAP_B
                    assert page.evaluate('1+1') == 2
                    # A lot nothing drops toasts briefly instead of navigating.
                    page.locator('[data-maps-dir] [data-goto="ItemLotParam:101"]').click()
                    page.wait_for_selector('.lex-toast-stack .lex-toast', timeout=30000)
                    assert 'drops' in page.locator(
                        '.lex-toast-stack .lex-toast').last.inner_text().lower()
                    assert page.locator('.lex-important-dialog').count() == 0
                    assert page.evaluate('state.mapId') == MAP_B
                    assert page.evaluate('state.selected') == f'{MAP_B}:2:7'
                    assert page.evaluate('1+1') == 2
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    assert errors == []
