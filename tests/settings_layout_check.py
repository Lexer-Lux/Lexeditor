"""Rendered global settings must remain readable beside shared Tweaks pages."""
import functools
import threading
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from global_browser_check import Handler, ThreadingHTTPServer, STUB, ROOT

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page();page.add_init_script(STUB)
            page.goto(f'http://127.0.0.1:{server.server_port}/ui/chooser.html')
            page.evaluate('LexeditorUI.openSettings()')
            page.wait_for_selector('.lex-global-setting input')
            assert page.get_by_role('checkbox',name='Wrap around at the ends',exact=True).count()==2
            for width,height in [(2048,1080),(900,620),(600,500)]:
                page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(250)
                metrics=page.locator('.lex-global-settings').evaluate("""dialog=>({width:dialog.getBoundingClientRect().width,scroll:dialog.scrollWidth,client:dialog.clientWidth,cards:[...dialog.querySelectorAll('.lex-global-setting:not([hidden])')].map(e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height}})})""")
                assert metrics['scroll']<=metrics['client']+2,metrics
                assert all(c['w']>=190 for c in metrics['cards']),metrics
                cards=metrics['cards']
                for i,a in enumerate(cards):
                    for b in cards[i+1:]:
                        assert min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x'])<=1 or min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y'])<=1,metrics
                page.screenshot(path=str(Path(tempfile.gettempdir())/f'lex-settings-{width}.png'))
            browser.close()
    finally:server.shutdown();server.server_close();thread.join(timeout=2)
    print('Settings cards fit without overlap at 2048, 900 and 600 pixels.')
if __name__=='__main__':main()
