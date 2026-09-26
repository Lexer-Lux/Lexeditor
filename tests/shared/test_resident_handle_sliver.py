"""G8: the back-to-editor handle shows the treated cover, with its affordance.

The handle is the game cover as a texture behind the arrow and the save mark:
blurred and darkened by the developer settings, not a sharp picture. Both
amounts are covered by test_chooser_cover_treatment.py; this check holds the
shipped treatment and the affordance itself.
"""
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_): pass


def test_resident_handle_cover_keeps_its_affordance():
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
                  beforePosition: getComputedStyle(n, '::before').backgroundPosition,
                  handlePosition: getComputedStyle(n).backgroundPosition,
                  afterContent: getComputedStyle(n, '::after').content,
                  afterBackground: getComputedStyle(n, '::after').backgroundColor,
                  position: getComputedStyle(n).position,
                  right: getComputedStyle(n).right,
                })''')
                # Treated cover: blurred, darkened, and covered by the film.
                assert 'blur(8px)' in art['beforeFilter'], art
                assert 'brightness(0.42)' in art['beforeFilter'], art
                assert 'cover' in art['beforeSize'], art
                assert art['beforeImage'] != 'none', art
                # The sliver is the cover's left edge. A centred crop showed the
                # middle of the artwork instead, which is the picture's subject
                # and not the part that stays recognisable at a hand's width.
                assert art['beforePosition'].startswith('0%'), art
                assert art['handlePosition'].startswith('0%'), art
                assert art['afterContent'] == '""', art
                film = art['afterBackground']
                assert float(film[film.index('(') + 1:film.rindex(')')].split(',')[3]) > 0.3, art
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
