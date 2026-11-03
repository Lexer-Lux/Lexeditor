"""Home menu game search: a shared search box filters the covers by name.

The free strip below the top menu bar holds the shared bottomSearch control,
aligned right. Typing filters the displayed games by name (case-insensitive);
clearing restores every game. A query with no matches shows an empty result
state instead of a bare grid. Card geometry, selection and cover updates are
the existing chooser renderer's, unchanged.
"""
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))

PLUGINS = [
    {'id': 'ff7', 'name': 'Final Fantasy VII', 'status': 'added', 'canOpen': True,
     'coverArt': {'state': 'none'}},
    {'id': 'ff8', 'name': 'Final Fantasy VIII', 'status': 'added', 'canOpen': True,
     'coverArt': {'state': 'none'}},
    {'id': 'ds1', 'name': 'Dark Souls', 'status': 'not-added', 'canOpen': False,
     'coverArt': {'state': 'none'}},
    {'id': 'kf1', 'name': "King's Field I", 'status': 'added', 'canOpen': True,
     'coverArt': {'state': 'none'}},
]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_): pass


def stub_script(plugins):
    settings = dict(BASE, developerMode=False, developerAuthorized=False,
                    viewPreferences={}, defaultValues=dict(BASE),
                    loadingTransitionMinimumSeconds=0, updateCheckChoices=[])
    return (f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
            f"plugins:async()=>({json.dumps(plugins)}),"
            "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
            "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
            "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
            "project_info:async()=>({canCreate:false,projects:[]})},{get:(t,k)=>t[k]||(async()=>false)})};")


def load_menu(page, base, viewport=None):
    page.add_init_script(stub_script(PLUGINS))
    page.goto(base + '/ui/chooser.html')
    page.evaluate("dispatchEvent(new Event('pywebviewready'))")
    page.wait_for_selector('.game', timeout=8000)
    page.wait_for_selector('#loading-screen', state='hidden', timeout=8000)


def run_at(viewport, probe):
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport=viewport)
                page.set_default_timeout(5000)
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                load_menu(page, base)
                probe(page)
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def visible_names(page):
    return page.locator('.game').evaluate_all(
        'nodes=>nodes.map(n=>n.querySelector(".game-name-text").textContent)')


def test_search_filters_by_name_case_insensitive_and_restores(tmp_path):
    def probe(page):
        # The shared search box lives in the strip below the menu bar and
        # above the covers, aligned right.
        box = page.locator('#home-search .lex-pager-search input[type="search"]')
        assert box.count() == 1
        assert box.get_attribute('aria-label') == 'Search games'
        geometry = page.evaluate("""()=>{const strip=document.querySelector('#home-search-strip'),
          search=document.querySelector('#home-search'),header=document.querySelector('header'),
          games=document.querySelector('#games');
          const s=strip.getBoundingClientRect(),b=search.getBoundingClientRect(),
            h=header.getBoundingClientRect(),g=games.getBoundingClientRect();
          return {justify:getComputedStyle(strip).justifyContent,
            belowHeader:s.top>=h.bottom-1, aboveGames:s.bottom<=g.top+1,
            rightAligned:Math.abs(s.right-b.right-parseFloat(getComputedStyle(strip).paddingRight))<=2, searchWidth:b.width};}""")
        assert geometry['justify'] == 'flex-end', geometry
        assert geometry['belowHeader'] and geometry['aboveGames'], geometry
        assert geometry['rightAligned'], geometry
        assert page.locator('#home-empty').is_hidden()
        assert visible_names(page) == [row['name'] for row in PLUGINS]
        page.screenshot(path=str(tmp_path/'home-game-search.png'))

        box.fill('final')
        assert visible_names(page) == ['Final Fantasy VII', 'Final Fantasy VIII']
        assert page.locator('#home-empty').is_hidden()

        box.fill('DARK')
        assert visible_names(page) == ['Dark Souls']

        # Selection still works through the filter: the not-added card opens
        # its existing locate dialog, not the editor.
        page.locator('.game[data-plugin="ds1"]').click()
        page.wait_for_selector('#modal:not([hidden])', timeout=4000)
        assert 'Dark Souls' in page.locator('#dialog-message').inner_text()
        page.get_by_role('button', name='NO', exact=True).click()
        page.get_by_role('button', name='close', exact=True).click()
        page.wait_for_selector('#modal', state='hidden', timeout=4000)

        box.fill('zzz-no-such-game')
        assert page.locator('.game').count() == 0
        empty = page.locator('#home-empty')
        assert not empty.is_hidden()
        assert empty.inner_text().strip(), 'the empty result state says nothing'

        box.fill('')
        assert visible_names(page) == [row['name'] for row in PLUGINS]
        assert page.locator('#home-empty').is_hidden()

    run_at({'width': 1600, 'height': 900}, probe)


def test_search_stays_usable_at_a_narrow_viewport():
    def probe(page):
        box = page.locator('#home-search .lex-pager-search input[type="search"]')
        assert box.count() == 1
        metrics = page.evaluate("""()=>{const box=document.querySelector('#home-search input[type="search"]').getBoundingClientRect();
          return {hOverflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,
            boxLeft:box.left, boxRight:box.right, innerWidth:window.innerWidth};}""")
        assert not metrics['hOverflow'], metrics
        assert metrics['boxLeft'] >= 0 and metrics['boxRight'] <= metrics['innerWidth'] + 1, metrics
        box.fill('final')
        assert visible_names(page) == ['Final Fantasy VII', 'Final Fantasy VIII']
        box.fill('zzz-no-such-game')
        assert page.locator('.game').count() == 0
        assert not page.locator('#home-empty').is_hidden()
        box.fill('')
        assert page.locator('.game').count() == 4

    run_at({'width': 360, 'height': 700}, probe)
