"""Render Home owner controls and restart failures without native windows."""
import functools
import threading
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from global_browser_check import ROOT, Handler, STUB, load_page


def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(); errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.add_init_script(STUB)
            load_page(page,f'http://127.0.0.1:{server.server_port}','/ui/chooser.html')
            restart=page.get_by_role('button',name='Restart Lexeditor',exact=True)
            restart.wait_for()
            page.evaluate("window.__restartCalls=0;window.pywebview.api.restart_lexeditor=()=>{__restartCalls++;return new Promise(resolve=>window.__finishRestart=resolve)};void 0")
            restart.click()
            assert restart.is_disabled()
            page.evaluate('restartLexeditor()')
            assert page.evaluate('__restartCalls')==1
            page.evaluate('__finishRestart(null)')
            page.get_by_text('The desktop host did not confirm the restart. Try again.',exact=True).wait_for()
            assert restart.is_enabled()
            page.get_by_role('button',name='CLOSE',exact=True).click()
            page.evaluate("window.pywebview.api.restart_lexeditor=async()=>{throw Error('Test Home restart failure')};void 0")
            restart.click();page.get_by_text('Test Home restart failure',exact=True).wait_for()
            page.get_by_role('button',name='CLOSE',exact=True).click()
            assert restart.is_enabled()
            page.evaluate('applySharedSettings({developerMode:false,developerAuthorized:false})')
            assert restart.is_hidden()
            assert page.get_by_role('button',name='DEV',exact=True).count()==0
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close()
    print('PASS: Home restart pending guard, missing/error recovery, and owner-only visibility')


if __name__=='__main__':main()
