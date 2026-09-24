"""G8: the back-to-editor handle shows a crisp cover sliver, not blurred art."""
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


def test_resident_handle_crisp_sliver():
    settings = dict(BASE, developerMode=True, developerAuthorized=True,
                    developerLogin='Lexer-Lux', viewPreferences={},
                    defaultValues=dict(BASE), loadingTransitionMinimumSeconds=0,
                    updateCheckChoices=[{'value': 'monthly', 'label': 'Monthly'}])
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        plugins = [{'id': 'game0', 'name': 'Game Zero', 'status': 'added', 'canOpen': True,
                    'resident': True, 'dirtyCount': 0,
                    'coverArt': {'state': 'ready', 'uri': base + '/ui/assets/blank-game-cover.png'}}]
        stub = (f"window.__calls=[];window.pywebview={{api:new Proxy({{"
                f"lexeditor_settings:async()=>({json.dumps(settings)}),"
                f"plugins:async()=>({json.dumps(plugins)}),"
                "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
                "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
                "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
                "resume_plugin:async(id)=>{window.__calls.push(id);return {url:'about:blank'};},"
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
                page.wait_for_selector('#resident-handle:visible', timeout=8000)
                page.wait_for_selector('#loading-screen', state='hidden', timeout=8000)
                assert not errors, errors
                handle = page.locator('#resident-handle')
                art = handle.evaluate('''n => ({
                  beforeFilter: getComputedStyle(n, '::before').filter,
                  beforeSize: getComputedStyle(n, '::before').backgroundSize,
                  beforeImage: getComputedStyle(n, '::before').backgroundImage,
                  afterContent: getComputedStyle(n, '::after').content,
                  position: getComputedStyle(n).position,
                  right: getComputedStyle(n).right,
                })''')
                # Crisp: no blur/darken filter, full-height sliver of the cover.
                assert art['beforeFilter'] == 'none', art
                assert '100%' in art['beforeSize'], art
                assert art['beforeImage'] != 'none', art
                # No darkening overlay anymore.
                assert art['afterContent'] == 'none', art
                # Same affordance: fixed right-edge strip, still clicks through.
                assert art['position'] == 'fixed' and art['right'] == '0px', art
                assert handle.get_attribute('aria-label') == 'Return to Game Zero'
                box_before = handle.bounding_box()
                handle.hover()
                page.wait_for_timeout(200)
                assert handle.bounding_box()['width'] > box_before['width']
                handle.click()
                page.wait_for_function('window.__calls.length > 0', timeout=5000)
                assert page.evaluate('window.__calls') == ['game0']
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
