"""Home waits for its whole dashboard and opens absent games' issue workspaces."""
import functools
import os
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_dev_drawer_table import Handler, ROOT, STUB


def test_home_dashboard_loading_helpers_and_cover_shortcut():
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1600, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.add_init_script(STUB + """
                  const api=window.pywebview.api, original=api.developer_issue_board;
                  window.__helperReads=0;
                  api.helper_versions=async()=>{window.__helperReads++;return {helpers:[]};};
                  api.developer_issue_board=()=>new Promise(resolve=>{
                    window.__finishBoard=async()=>resolve(await original());});
                  api.plugins=async()=>[{id:'ff7',name:'Final Fantasy VII',status:'not-added',canOpen:false}];
                  api.github_repository=async()=>({repository:'Lexer-Lux/Lexeditor',issueLabel:'ff7'});
                  api.github_issues=async()=>({issues:[]});
                  api.github_labels=async()=>({labels:[]});
                """)
                # During a parallel shared-UI change, optionally test the real
                # dependency from that checkout without copying it into ours.
                framework = os.environ.get("LEXEDITOR_TEST_FRAMEWORK_ROOT")
                if framework:
                    for name in ("framework.js", "framework.css"):
                        page.route(f"**/ui/{name}", lambda route, request, name=name: route.fulfill(
                            path=str(Path(framework) / "ui" / name)))
                page.goto(f"http://127.0.0.1:{server.server_port}/ui/chooser.html")
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.locator("#loading-screen").wait_for(state="hidden")
                # Every control uses the editor's shared command-row sizes.
                controls = page.locator("#chooser-window-controls button")
                sizes = controls.evaluate_all("ns=>ns.filter(n=>!n.hidden).map(n=>{const r=n.getBoundingClientRect();return [r.width,r.height,r.y]})")
                assert len({tuple(round(x, 1) for x in size) for size in sizes}) == 1, sizes
                page.locator("#lexer-handle").click()
                page.locator('[aria-label="Loading developer overview"]').wait_for()
                assert page.locator("#lexer-dev-table .lex-column-list").count() == 0
                assert page.locator("#lexer-dev-helpers").is_hidden()
                assert page.evaluate("window.__helperReads") == 0
                page.evaluate("window.__finishBoard()")
                page.locator("#lexer-dev-table .lex-column-list").wait_for()
                assert page.locator("#lexer-dev-table .lex-dev-todo").count() == 0
                page.locator("#lexer-helpers-toggle").click()
                assert page.locator("#lexer-dev-helpers").is_visible()
                assert page.evaluate("window.__helperReads") == 1
                page.locator("#lexer-helpers-toggle").click()
                assert page.locator("#lexer-dev-helpers").is_hidden()
                output = os.environ.get("LEXEDITOR_TEST_SHOTS")
                if output:
                    page.screenshot(path=str(Path(output) / "dashboard.png"))
                page.locator("#lexer-panel-close").click()
                page.locator("#lexer-panel").wait_for(state="hidden")
                page.locator('.game[data-plugin="ff7"]').click(button="right")
                page.locator(".lex-github-workspace:not([hidden])").wait_for()
                assert page.locator(".lex-github-standalone-title").inner_text() == "Final Fantasy VII issues"
                assert page.locator("#modal").is_hidden()
                page.locator(".lex-shell-header.lex-github-standalone button").last.click()
                assert page.locator(".lex-github-workspace").count() == 0
                for width, height in ((1600, 900), (800, 600)):
                    page.set_viewport_size({"width": width, "height": height})
                    if output:
                        page.screenshot(path=str(Path(output) / f"home-{width}.png"))
                    assert page.locator("#window-close").bounding_box()["x"] < width
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
