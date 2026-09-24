"""G2: the main menu renders its cards, covers and fallbacks without errors.

Locks in the healthy menu against the four hypothesized black-menu causes:
blank webview, missing covers, JS error, backend failure. A ready cover must
paint; a missing cover must degrade to legible fallback initials; the loading
screen must lift; no error dialog may appear.
"""
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_): pass


def test_menu_renders_cards_covers_and_fallbacks(plugins_override=None, loading_timeout=8000):
    settings = dict(BASE, developerMode=True, developerAuthorized=True,
                    developerLogin='Lexer-Lux', viewPreferences={},
                    defaultValues=dict(BASE), loadingTransitionMinimumSeconds=0,
                    updateCheckChoices=[{'value': 'monthly', 'label': 'Monthly'}])
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        plugins = plugins_override or [
            {'id': 'with-cover', 'name': 'With Cover', 'status': 'added', 'canOpen': True,
             'coverArt': {'state': 'ready', 'uri': base + '/ui/assets/blank-game-cover.png'}},
            {'id': 'no-cover', 'name': 'No Cover Game', 'status': 'warning', 'canOpen': False,
             'problems': ['Something is missing'], 'statusText': 'Something is missing',
             'coverArt': {'state': 'missing', 'uri': '', 'error': 'gone'}},
        ]
        stub = (f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
                f"plugins:async()=>({json.dumps(plugins)}),"
                "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
                "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
                "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
                "project_info:async()=>({canCreate:false,projects:[]})},{get:(t,k)=>t[k]||(async()=>false)})};")
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1920, 'height': 1080})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.add_init_script(stub)
                page.goto(base + '/ui/chooser.html')
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.wait_for_selector('.game', timeout=8000)
                page.wait_for_selector('#loading-screen', state='hidden', timeout=loading_timeout)
                assert not errors, errors
                if plugins_override:
                    return
                assert page.locator('.game').count() == 2
                assert page.locator('#modal').is_hidden()
                # The ready cover paints real pixels.
                cover = page.locator('.game[data-plugin="with-cover"] .game-cover')
                assert cover.count() == 1
                page.wait_for_function(
                    'document.querySelector(\'.game[data-plugin="with-cover"] .game-cover\').naturalWidth > 0',
                    timeout=8000)
                box = cover.bounding_box()
                assert box['width'] > 100 and box['height'] > 100, box
                # The missing cover degrades to legible initials, not a void.
                fallback = page.locator('.game[data-plugin="no-cover"] .cover-fallback')
                assert fallback.inner_text().strip() == 'NCG'
                assert fallback.evaluate('n=>{const r=n.getBoundingClientRect();'
                                         'return r.width>100&&r.height>100;}')
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_menu_lifts_loading_screen_when_a_cover_never_settles():
    """G2 root cause: one cover stuck "loading" held the black loading screen
    forever. The menu must reveal after its cover-wait cap regardless."""
    stuck = [{'id': 'stuck', 'name': 'Stuck Cover', 'status': 'added', 'canOpen': True,
              'coverArt': {'state': 'loading', 'uri': '', 'error': ''}}]
    test_menu_renders_cards_covers_and_fallbacks(plugins_override=stuck, loading_timeout=10000)
