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
      {id:"global",game:"Global",global:true,quotes:2,
       copiedLines:null,copiedRecorded:null,copiedOver:false},
      {id:"ff8",game:"Final Fantasy 8",
       quotes:10,
       copiedLines:4,copiedRecorded:4,copiedOver:false},
      {id:"ff9",game:"Final Fantasy 9",
       quotes:0,
       copiedLines:null,copiedRecorded:null,copiedOver:false},
    ],
    quotesTotal:12,globalQuotes:2,quotedPlugins:2,
    sharedUi:{files:[{file:"plugins/ff8/party.js",sharedSelectors:3,recordedSelectors:3,
      handBuiltRows:1,recordedRows:1,over:false}],totalShared:3,totalHand:1},
    workflowColors:{actionable:"#0e8a16",untested:"#fbca04",waiting:"#e87924",unfeasible:"#b60205"},
  }}),
  developer_issue_board:async()=>({colors:{waiting:"#123456"},games:{
    global:{subissues:{editor:null,ux:null,modloader:null,theme:null,reshade:null},
      counts:{actionable:7,untested:0,waiting:3,unfeasible:0,none:0}},
    ff8:{subissues:{editor:{number:21,closed:false,status:"waiting"},ux:{number:612,closed:true,status:null},
      modloader:{number:100,closed:false,status:"untested",blocked:true},theme:{number:613,closed:false,status:null},reshade:null},
      counts:{actionable:21,untested:22,waiting:5,unfeasible:0,none:1}},
    ff9:{subissues:{editor:null,ux:null,modloader:null,theme:null,reshade:null},
      counts:{actionable:0,untested:0,waiting:0,unfeasible:0,none:0}}}}),
  open_developer_issues:async(...args)=>{window.__opened.push(args);return{opened:true};},
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
                page.add_init_script("window.__opened=[];" + STUB)
                page.goto(f"http://127.0.0.1:{server.server_port}/ui/chooser.html")
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.get_by_role("button", name="Open helper versions", exact=True).click()
                table = page.locator("#lexer-dev-table .lex-column-list")
                table.wait_for(timeout=10000)
                headers = table.locator('[role="columnheader"]').all_inner_texts()
                assert [h.strip().upper() for h in headers] == [
                    "GAME", "EDITOR", "UX", "MODLOADER", "THEME", "RESHADE",
                    "", "", "", "", "✕", "QUOTES", "COPIED LINES"]
                assert page.locator("#lexer-dev-table .lex-column-list").count() == 1
                assert table.locator('.lex-column-list-row').count() == 3
                first = table.locator('.lex-column-list-row').first
                assert first.inner_text().startswith("Global")
                body = table.inner_text()
                assert "Final Fantasy 8" in body and "Final Fantasy 9" in body
                ff8 = table.locator('.lex-column-list-row').filter(has_text="Final Fantasy 8")
                ff8.locator('.lexer-dev-closed').wait_for(timeout=10000)
                # A closed subissue is a tick, a missing one a warning, an open
                # one a dot in its label's GitHub colour.
                assert ff8.locator('[title^="#612 UX: closed"] .lexer-dev-closed').count() == 1
                assert ff8.locator('.lexer-dev-missing').count() == 1
                editor = ff8.locator('[title^="#21 EDITOR: waiting"] .lexer-dev-dot')
                assert editor.evaluate("n=>getComputedStyle(n).backgroundColor") == "rgb(18, 52, 86)"
                assert ff8.locator('[title^="#613 THEME: no status"] .lexer-dev-dot.none').count() == 1
                # Only the blocked subissue wears the blocked badge, and it is not clipped.
                assert ff8.locator('.lexer-dev-blocked').count() == 1
                badge = ff8.locator('[title="#100 MODLOADER: needs testing, blocked"] .lexer-dev-blocked')
                inside = badge.evaluate('''(n)=>{const b=n.getBoundingClientRect(),
                  c=n.closest('.lex-column-list-cell').getBoundingClientRect();
                  return b.right<=c.right&&b.bottom<=c.bottom&&b.left>=c.left&&b.top>=c.top;}''')
                assert inside
                assert table.locator('.lex-column-list-row').filter(
                    has_text="Final Fantasy 9").locator('.lexer-dev-missing').count() == 5
                ff8.locator('[title^="#21 EDITOR"]').click()
                ff8.locator('button[title^="Final Fantasy 8: 5 open waiting"]').click()
                # Global tracks its own issues but has no plugin subissues to miss.
                assert first.locator('.lexer-dev-missing, .lexer-dev-dot').count() == 0
                first.locator('button[title^="Global: 7 open actionable"]').click()
                assert page.evaluate("window.__opened") == [
                    ["ff8", 21, None], ["ff8", None, "waiting"], ["global", None, "actionable"]]
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
