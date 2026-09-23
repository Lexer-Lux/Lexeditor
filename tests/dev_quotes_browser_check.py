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
            page.evaluate("""window.pywebview.api.developer_overview=async()=>({
              games: [], sharedUi: [], sharedCode: [],
              quotes: {global: 2, plugins: {ff8: 10, ff9: 0}},
            });void 0""")
            dev.click()
            table = page.locator('#lexer-dev-quotes')
            table.wait_for()
            body = table.inner_text()
            assert 'PLUGIN' in body and 'QUOTES' in body, body
            assert 'Global (shared)' in body, body
            assert 'ff8' in body and 'ff9' in body, body
            assert '2 plugins + shared' in body, body
            assert '12' in body.split('2 plugins + shared')[1], body
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print('PASS: Developer page lists loading quotes per plugin plus the shared pool')


if __name__ == '__main__':
    main()
