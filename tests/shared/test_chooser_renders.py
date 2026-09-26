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

ROOT = Path(__file__).resolve().parents[2]
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
                # The home bar is the same chrome as an editor's: a shared
                # border below it, not a bright accent stripe. Lexer: "the main
                # menu still has a fuckton of weird custom styling. like the
                # green bar below the menu bar."
                bar = page.evaluate("""()=>{const header=document.querySelector('header'),
                  cs=getComputedStyle(header), theme=getComputedStyle(document.body),
                  resolve=value=>{const probe=document.createElement('div');
                    probe.style.color=value; document.body.append(probe);
                    const colour=getComputedStyle(probe).color; probe.remove(); return colour;};
                  return {width:cs.borderBottomWidth, colour:cs.borderBottomColor,
                    border:resolve(theme.getPropertyValue('--lex-border')),
                    accent:resolve(theme.getPropertyValue('--lex-accent'))};}""")
                assert bar['width'] == '1px', bar
                assert bar['colour'] == bar['border'], bar
                assert bar['colour'] != bar['accent'], bar
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


def test_hovered_card_title_keeps_room_for_its_descenders():
    """A title's y and its shadow paint below the last line box.

    The clamped title element clips at its own box, so a flush box cut the
    descender's shadow off mid-letter - a screenshot of the hovered FF9 card
    showed the shadow stopping under the y. The element reserves the room now;
    this holds the reservation and the fitter's view of the same height.
    """
    import functools
    import json
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    from playwright.sync_api import sync_playwright
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    settings = dict(BASE, developerMode=False, developerAuthorized=False, viewPreferences={},
                    defaultValues=dict(BASE), loadingTransitionMinimumSeconds=0,
                    updateCheckChoices=[])
    plugin = [{'id': 'ff9', 'name': 'Final Fantasy 9', 'status': 'added', 'canOpen': True,
               'coverArt': {'state': 'none'}}]
    stub = (f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
            f"plugins:async()=>({json.dumps(plugin)}),"
            "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
            "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
            "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
            "project_info:async()=>({canCreate:false,projects:[]})},{get:(t,k)=>t[k]||(async()=>false)})};")

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1357, 'height': 853})
                page.add_init_script(stub)
                page.goto(f'http://127.0.0.1:{server.server_port}/ui/chooser.html')
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.wait_for_selector('.game', timeout=8000)
                page.wait_for_selector('#loading-screen', state='hidden', timeout=8000)
                card = page.locator('.game').first
                card.hover()
                page.wait_for_timeout(400)
                metrics = card.evaluate("""e=>{
                  const text=e.querySelector('.game-name-text'),name=e.querySelector('.game-name');
                  const style=getComputedStyle(text);
                  return {paddingBottom:parseFloat(style.paddingBottom),
                    overflow:style.overflow,
                    textTop:text.getBoundingClientRect().top,
                    textBottom:text.getBoundingClientRect().bottom,
                    boxTop:name.getBoundingClientRect().top,
                    boxBottom:name.getBoundingClientRect().bottom,
                    scrollHeight:text.scrollHeight,boxClient:name.clientHeight,
                    lines:getComputedStyle(name).getPropertyValue('--game-name-lines')}}""")
                assert metrics['overflow'] == 'hidden', metrics
                assert metrics['paddingBottom'] >= 3, metrics
                # The room has to be inside the box the fitter measures.
                assert metrics['textTop'] >= metrics['boxTop'], metrics
                assert metrics['scrollHeight'] <= metrics['boxClient'] + 1, metrics
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
