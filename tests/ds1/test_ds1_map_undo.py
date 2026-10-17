"""Map undo moves only its own part: no map re-read, no viewport remount.

Moving a placement then undoing used to reload the whole map (fresh view,
fresh rows, fresh mount). Undo now moves the scene part back and patches
the lists; an enemy swap additionally refreshes only the map counts and
the directory it can move rows between.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from msb_fixture import build_msb  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

MAP = 'm10_00_00_00.msb'
PARTS = (('enemy', 2, 0, 0, 120000), ('enemy', 2, 1, 0, 120100),
         ('player', 4, 0, 1, None), ('piece', 0, 0, 1, None),
         ('chest', 1, 0, 1, None))
VIEW_FETCHES = ('/api/map/view', 'tab=viewport')


def heavy_fetches(requests):
    return [url for url in requests
            if any(token in url for token in VIEW_FETCHES)]


def test_map_undo_is_surgical():
    errors = []
    requests = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-undo-') as temp:
        game, mod = Path(temp) / 'game', Path(temp) / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'map' / 'MapStudio').mkdir(parents=True)
        (game / 'map' / 'MapStudio' / MAP).write_bytes(build_msb(parts=PARTS))
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0',
                              'LEXEDITOR_MOD_READ_ONLY': '0'})
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('request', lambda request: requests.append(request.url))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function('state.tab==="maps" && state.mapView', timeout=60000)
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=30000)
                    page.locator('[data-tabstrip-id="placements"]').click()
                    page.wait_for_function('state.mapTab==="placements"')
                    page.get_by_role('searchbox', name='Search placements').fill('Rat')
                    page.wait_for_function(
                        'state.selected.endsWith(":0") && state.row?.name.startsWith("Rat ")')
                    page.locator('[data-tabstrip-id="selection"]').click()
                    field = page.locator('[data-field-key="posX"]:visible')
                    before = field.input_value()
                    field.fill('41.5')
                    field.press('Tab')
                    page.wait_for_function(
                        'state.pending === 0 && fieldHistory.undoStack.length === 1')
                    assert page.evaluate('state.mapView.parts.find(p=>p.key==="2:0").pos[0]') == 41.5
                    mount = page.evaluate('viewportMount')
                    page.evaluate('window.__shotCanvas = document.querySelector("canvas[data-viewport]")')
                    del requests[:]
                    # Undo the move: the part steps back, nothing reloads.
                    page.evaluate('fieldHistory.undo()')
                    page.wait_for_function(
                        'fieldHistory.undoStack.length === 0 && fieldHistory.redoStack.length === 1')
                    page.wait_for_function(
                        '(x) => document.querySelector("[data-maps-side] [data-field-key=\'posX\']").value === x',
                        arg=before)
                    assert page.evaluate('viewportMount') == mount
                    assert page.evaluate(
                        'document.querySelector("canvas[data-viewport]") === window.__shotCanvas')
                    assert page.evaluate(
                        'state.mapView.parts.find(p=>p.key==="2:0").pos[0]') == float(before)
                    assert page.evaluate(
                        'state.rows.find(r=>r.table==="%s" && r.id==="2:0").values.posX' % MAP) == float(before)
                    assert heavy_fetches(requests) == [], heavy_fetches(requests)
                    # Redo steps forward with the same restraint.
                    page.evaluate('fieldHistory.redo()')
                    page.wait_for_function(
                        'fieldHistory.undoStack.length === 1 && fieldHistory.redoStack.length === 0')
                    page.wait_for_function(
                        'document.querySelector("[data-maps-side] [data-field-key=\'posX\']").value === "41.5"')
                    assert page.evaluate('viewportMount') == mount
                    assert heavy_fetches(requests) == [], heavy_fetches(requests)
                    # An enemy swap undo restores the name and counts; the
                    # counts refetch, but the map view and mount stand.
                    npc = page.locator('[data-field-key="npcId"]:visible')
                    npc.select_option('251000')
                    page.wait_for_function('state.pending === 0 && fieldHistory.undoStack.length === 2')
                    swapped = page.evaluate('state.mapList.find(r=>r.id==="%s").values' % MAP)
                    assert (swapped['npcs'], swapped['enemies']) == (1, 1), swapped
                    del requests[:]
                    page.evaluate('fieldHistory.undo()')
                    page.wait_for_function(
                        'fieldHistory.undoStack.length === 1 && fieldHistory.redoStack.length === 1')
                    page.wait_for_function(
                        '(name) => state.mapList.find(r=>r.id===name).values.npcs === 0', arg=MAP)
                    assert page.evaluate('viewportMount') == mount
                    assert page.evaluate(
                        'document.querySelector("canvas[data-viewport]") === window.__shotCanvas')
                    assert [url for url in requests if '/api/map/view' in url] == []
                    assert any('tab=viewport' in url for url in requests), requests
                    title = page.evaluate(
                        'state.rows.find(r=>r.table==="%s" && r.id==="2:0").name' % MAP)
                    assert title.startswith('Rat '), title
                finally:
                    browser.close()
        finally:
            session.stop()
    assert errors == []
