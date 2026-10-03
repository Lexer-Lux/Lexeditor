"""Dataset failures identify the failed request and do not publish a partial project."""
import threading
from playwright.sync_api import sync_playwright, expect
from plugins.project_zomboid import server
from verify_project_zomboid_ui import write_fixture


def test_failed_and_malformed_inventory_response_then_real_reload(tmp_path, monkeypatch):
    project = tmp_path / 'Fixture'
    write_fixture(project)
    monkeypatch.setenv('LEXEDITOR_PROJECT_ZOMBOID_PROJECT', str(project))
    monkeypatch.setenv('LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT', str(tmp_path / 'user'))
    monkeypatch.setenv('LEXEDITOR_MOD_READ_ONLY', '0')
    monkeypatch.setenv('LEXEDITOR_NO_MOD', '0')
    http = server.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1500, 'height': 950})
                url = f'http://127.0.0.1:{http.server_port}'
                page.route(url + '/api/zedscript', lambda route: route.fulfill(status=500,
                           body='{"error":"Inventory temporarily unavailable"}', content_type='application/json'))
                page.goto(url)
                expect(page.locator('.pz-error-message')).to_have_text('/api/zedscript: Inventory temporarily unavailable')
                assert page.evaluate('items.rows.length+scripts.rows.length') == 0
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.unroute(url + '/api/zedscript')
                page.reload()
                page.wait_for_function('items.rows.length>0&&scripts.rows.length>0')
                assert page.locator('.pz-error-message').count() == 0
                page.route(url + '/api/zedscript', lambda route: route.fulfill(status=200,
                           body='not JSON', content_type='application/json'))
                page.reload()
                expect(page.locator('.pz-error-message')).to_have_text('/api/zedscript: Invalid JSON response')
                assert page.evaluate('items.rows.length+scripts.rows.length') == 0
                page.unroute(url + '/api/zedscript')
                page.route(url + '/api/zedscript', lambda route: route.abort('failed'))
                page.reload()
                expect(page.locator('.pz-error-message')).to_contain_text('/api/zedscript:')
                assert page.evaluate('items.rows.length+scripts.rows.length') == 0
                page.unroute(url + '/api/zedscript')
                page.reload()
                page.wait_for_function('items.rows.length>0&&scripts.rows.length>0')
                assert page.locator('.pz-error-message').count() == 0
            finally:
                browser.close()
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
