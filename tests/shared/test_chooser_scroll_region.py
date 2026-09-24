"""G1: the main menu scrolls exactly once, and edge handles stay viewport-fixed."""
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))

EDITOR_HTML = """<!doctype html><html><body><h1>Stub editor</h1><script>
let id = 0;
const pending = new Map();
addEventListener('message', e => {
  if (e.data?.type === 'lexeditor-host-result' && pending.has(e.data.id)) {
    pending.get(e.data.id)(e.data); pending.delete(e.data.id);
  }
});
function call(method, args=[]) {
  return new Promise(resolve => {
    const mid = ++id; pending.set(mid, resolve);
    parent.postMessage({type:'lexeditor-host-call', method, id:mid, args}, '*');
  });
}
(async () => { await call('editor_ready'); })();
window.__goHome = () => call('return_to_main_menu');
</script></body></html>"""


def make_plugins(count):
    statuses = ['added', 'added', 'warning', 'added', 'broken', 'not-added']
    rows = []
    for i in range(count):
        status = statuses[i % len(statuses)]
        rows.append({'id': f'game{i}', 'name': f'Game {i}', 'status': status,
                     'canOpen': status == 'added',
                     'problems': ['Something is missing'] if status in ('warning', 'broken') else [],
                     'statusText': 'Something is missing' if status in ('warning', 'broken') else '',
                     'coverArt': {'state': 'none'}})
    return rows


def stub_script(plugins):
    settings = dict(BASE, developerMode=True, developerAuthorized=True,
                    developerLogin='Lexer-Lux', viewPreferences={},
                    defaultValues=dict(BASE), loadingTransitionMinimumSeconds=0,
                    updateCheckChoices=[{'value': 'monthly', 'label': 'Monthly'}])
    return (f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
            f"plugins:async()=>({json.dumps(plugins)}),"
            "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
            "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
            "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
            "open_plugin:async()=>({url:window.__editorUrl}),"
            "project_info:async()=>({canCreate:false,projects:[]})},{get:(t,k)=>t[k]||(async()=>false)})};")


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_GET(self):
        if self.path.split('?')[0] == '/stub-editor.html':
            body = EDITOR_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()


@pytest.fixture
def base():
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def load_menu(page, base, count):
    page.add_init_script(stub_script(make_plugins(count)))
    page.goto(base + '/ui/chooser.html')
    page.evaluate("dispatchEvent(new Event('pywebviewready'))")
    page.wait_for_selector('.game', timeout=8000)
    page.wait_for_selector('#loading-screen', state='hidden', timeout=8000)


@pytest.mark.parametrize('count, expect_gutter', [(19, True), (4, False)])
def test_scrollbar_only_when_overflowing(base, count, expect_gutter):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True, ignore_default_args=['--hide-scrollbars'])
        try:
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            load_menu(page, base, count)
            assert not errors
            assert page.locator('.game').count() == count
            metrics = page.evaluate('''()=>({
              gutter: window.innerWidth - document.documentElement.clientWidth,
              hOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
              bodyScroller: document.body.scrollHeight > document.body.clientHeight + 1 &&
                getComputedStyle(document.body).overflowY !== 'visible',
              winScrolls: document.documentElement.scrollHeight > document.documentElement.clientHeight + 1,
            })''')
            assert metrics['gutter'] > 0 if expect_gutter else metrics['gutter'] == 0, metrics
            assert not metrics['hOverflow'], metrics
            # Viewport propagation owns the one scroll; the body must not
            # keep a second, competing scroller.
            assert metrics['bodyScroller'] == metrics['winScrolls'] or not metrics['bodyScroller'], metrics
            page.evaluate('window.scrollTo(0, 99999)')
            page.wait_for_timeout(200)
            assert page.evaluate('''()=>{const cards=[...document.querySelectorAll(".game")];
              const r=cards[cards.length-1].getBoundingClientRect();return r.bottom<=innerHeight+2;}''')
        finally:
            browser.close()


def test_edge_handles_stay_fixed_after_home(base):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True, ignore_default_args=['--hide-scrollbars'])
        try:
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            load_menu(page, base, 19)
            page.evaluate(f'window.__editorUrl={json.dumps(base + "/stub-editor.html")}')
            page.evaluate('window.__lexChooser.activate(document.querySelector(".game")._plugin)')
            page.wait_for_selector('#lexeditor-editor', timeout=8000)
            page.wait_for_function(
                'document.querySelector("#chooser-surface").inert === true', timeout=8000)
            page.evaluate('(()=>{document.querySelector("#lexeditor-editor").contentWindow.__goHome().catch(()=>{});})()')
            page.wait_for_selector('#lexeditor-editor', state='detached', timeout=8000)
            page.wait_for_timeout(400)
            assert not errors
            assert page.evaluate(
                '()=>document.querySelector("#chooser-surface").style.transform') == ''
            page.evaluate('window.scrollTo(0, 300)')
            page.wait_for_timeout(200)
            assert page.evaluate(
                '()=>document.querySelector("#lexer-handle").getBoundingClientRect().top') == 0
        finally:
            browser.close()
