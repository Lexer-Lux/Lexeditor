"""G12: the dev drawer is one per-game table through the shared Table."""
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_): pass


STUB = """window.pywebview={api:new Proxy({
  lexeditor_settings:async()=>({developerMode:true,residentHandleWidthPercent:5,
    mainMenuHeightPercent:9,absentGameDesaturationPercent:40}),
  plugins:async()=>([]),
  loading_quote:async()=>({text:"",game:""}),
  app_update_status:async()=>({available:false}),
  window_state:async()=>({maximized:false}),
  developer_overview:async()=>({table:{
    rows:[
      {id:"ff8",game:"Final Fantasy 8",modState:"Loads mods",modWorks:true,
       tasks:[{label:"ReShade defaults set",done:true}],quotes:10,
       copiedLines:4,copiedRecorded:4,copiedOver:false,rest:"Ready · Test loader"},
      {id:"ff9",game:"Final Fantasy 9",modState:"Not yet",modWorks:false,
       tasks:[{label:"ReShade defaults set",done:false}],quotes:0,
       copiedLines:null,copiedRecorded:null,copiedOver:false,rest:"Ready · No loader declared."},
    ],
    quotesTotal:12,globalQuotes:2,quotedPlugins:2,
    sharedUi:{files:[{file:"plugins/ff8/party.js",sharedSelectors:3,recordedSelectors:3,
      handBuiltRows:1,recordedRows:1,over:false}],totalShared:3,totalHand:1},
  }}),
},{get:(t,k)=>t[k]||(async()=>false)})};"""


def test_drawer_mounts_one_shared_table_with_per_game_rows():
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1600, "height": 900})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.add_init_script(STUB)
                page.goto(f"http://127.0.0.1:{server.server_port}/ui/chooser.html")
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.get_by_role("button", name="Open helper versions", exact=True).click()
                table = page.locator("#lexer-dev-table .lex-column-list")
                table.wait_for(timeout=10000)
                headers = table.locator('[role="columnheader"]').all_inner_texts()
                assert [h.strip().upper() for h in headers] == [
                    "GAME", "MOD LOADING", "TASKS", "QUOTES", "COPIED LINES", "REST"]
                assert page.locator("#lexer-dev-table .lex-column-list").count() == 1
                assert table.locator('.lex-column-list-row').count() == 2
                body = table.inner_text()
                assert "Final Fantasy 8" in body and "Final Fantasy 9" in body
                assert "Loads mods" in body and "Not yet" in body
                assert "✓ ReShade defaults set" in body and "○ ReShade defaults set" in body
                assert "Ready · Test loader" in body
                summary = page.locator("#lexer-dev-summary").inner_text()
                assert "2 games" in summary and "12 loading quotes" in summary
                assert "Global (shared): 2" in summary
                assert "3 selectors" in summary and "1 hand-built rows" in summary
                page.locator("#lexer-dev-files-wrap summary").click()
                files = page.locator("#lexer-dev-files").inner_text()
                assert "plugins/ff8/party.js" in files
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
