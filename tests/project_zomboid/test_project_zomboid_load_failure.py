"""Dataset failures identify the failed request and do not publish a partial project."""
import threading
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError
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
                failed_requests = []
                page_errors = []
                api_errors = []
                page.on('requestfailed', lambda request: failed_requests.append(
                    {'url': request.url, 'failure': request.failure}))
                page.on('pageerror', lambda error: page_errors.append(str(error)))
                page.on('response', lambda response: api_errors.append(
                    {'url': response.url, 'status': response.status})
                    if '/api/' in response.url and not response.ok else None)

                def diagnostics():
                    return {
                        'page': page.evaluate('''()=>({url:location.href,
                          items:items.rows.length,scripts:scripts.rows.length,
                          error:document.querySelector('.pz-error-message')?.textContent,
                          loading:!!document.querySelector('.lex-plugin-loading-screen')})'''),
                        'failedRequests': failed_requests,
                        'apiErrors': api_errors,
                        'pageErrors': page_errors,
                    }

                def expect_recovery(stage):
                    try:
                        page.wait_for_function('items.rows.length>0&&scripts.rows.length>0')
                    except PlaywrightTimeoutError as error:
                        raise AssertionError(f'{stage} did not recover: {diagnostics()!r}') from error
                    assert page.locator('.pz-error-message').count() == 0, diagnostics()

                def clear_diagnostics():
                    failed_requests.clear()
                    api_errors.clear()
                    page_errors.clear()

                def expect_error(text, *, contains=False):
                    try:
                        message = expect(page.locator('.pz-error-message'))
                        if contains:
                            message.to_contain_text(text)
                        else:
                            message.to_have_text(text)
                    except AssertionError as error:
                        raise AssertionError(
                            f'{error}\nLoad diagnostics: {diagnostics()!r}'
                        ) from error

                url = f'http://127.0.0.1:{http.server_port}'
                page.route(url + '/api/zedscript', lambda route: route.fulfill(status=500,
                           body='{"error":"Inventory temporarily unavailable"}', content_type='application/json'))
                page.goto(url)
                expect_error('/api/zedscript: Inventory temporarily unavailable')
                assert page.evaluate('items.rows.length+scripts.rows.length') == 0
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                for target in ('items','metadata','scripts'):
                    page.locator(f'nav button[data-tab="{target}"]').click()
                    expect_error('/api/zedscript: Inventory temporarily unavailable')
                    assert page.locator('#main .lex-panel-loading').count() == 0
                if folder := os.environ.get('LEXEDITOR_NAV_FAILURE_SHOTS'):
                    page.screenshot(path=str(Path(folder)/'zomboid-startup-failure.png'))
                page.unroute(url + '/api/zedscript')
                clear_diagnostics()
                page.get_by_role('button',name='Retry',exact=True).click()
                expect_recovery('HTTP-error reload')
                assert page.evaluate('tab') == 'scripts'
                assert not page_errors, diagnostics()
                page.route(url + '/api/zedscript', lambda route: route.fulfill(status=200,
                           body='not JSON', content_type='application/json'))
                clear_diagnostics()
                page.reload()
                expect_error('/api/zedscript: Invalid JSON response')
                assert page.evaluate('items.rows.length+scripts.rows.length') == 0
                page.locator('nav button[data-tab="items"]').click()
                expect_error('/api/zedscript: Invalid JSON response')
                assert page.locator('#main .lex-panel-loading').count() == 0
                page.unroute(url + '/api/zedscript')
                page.route(url + '/api/zedscript', lambda route: route.abort('failed'))
                clear_diagnostics()
                page.reload()
                expect_error('/api/zedscript:', contains=True)
                assert page.evaluate('items.rows.length+scripts.rows.length') == 0
                page.locator('nav button[data-tab="metadata"]').click()
                expect_error('/api/zedscript:', contains=True)
                assert page.locator('#main .lex-panel-loading').count() == 0
                page.unroute(url + '/api/zedscript')
                clear_diagnostics()
                page.get_by_role('button',name='Retry',exact=True).click()
                expect_recovery('Network-error reload')
            finally:
                browser.close()
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
