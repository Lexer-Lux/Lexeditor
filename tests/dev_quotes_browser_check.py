"""Render the developer page quote counter without native windows."""
import functools
import threading
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from global_browser_check import ROOT, Handler, STUB, load_page


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.add_init_script(STUB)
            load_page(page, f'http://127.0.0.1:{server.server_port}', '/ui/chooser.html')
            dev = page.get_by_role('button', name='Open helper versions', exact=True)
            dev.wait_for()
            page.evaluate("""window.pywebview.api.developer_overview=async()=>({table:{
              rows: [
                {id: 'ff8', game: 'Final Fantasy 8', modState: 'Loads mods', modWorks: true,
                 tasks: [], quotes: 10, copiedLines: 0, copiedRecorded: 0, copiedOver: false, rest: 'Ready'},
                {id: 'ff9', game: 'Final Fantasy 9', modState: 'Not yet', modWorks: false,
                 tasks: [], quotes: 0, copiedLines: null, copiedRecorded: null, copiedOver: false, rest: 'Ready'},
              ],
              quotesTotal: 12, globalQuotes: 2, quotedPlugins: 2,
              sharedUi: {files: [], totalShared: 0, totalHand: 0},
            }});void 0""")
            dev.click()
            table = page.locator('#lexer-dev-table .lex-column-list')
            table.wait_for()
            body = table.inner_text()
            assert 'GAME' in body and 'QUOTES' in body and 'COPIED LINES' in body, body
            assert 'Final Fantasy 8' in body and 'Final Fantasy 9' in body, body
            summary = page.locator('#lexer-dev-summary').inner_text()
            assert 'Global (shared)' in summary, summary
            assert '12' in summary and '2 games' in summary, summary
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print('PASS: Developer page lists loading quotes per plugin plus the shared pool')


if __name__ == '__main__':
    main()
