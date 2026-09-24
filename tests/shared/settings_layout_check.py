"""Rendered global settings must remain readable beside shared Tweaks pages."""
import functools
import threading
import tempfile
import os
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
            assert not page.locator('#app-update').is_visible()
            for available in (True,False):
                page.evaluate("value=>{window.pywebview.api.app_update_status=async()=>({available:value});}",available)
                page.evaluate('refreshAppUpdate()')
                assert page.locator('#app-update').is_visible()==available
            page.evaluate("()=>{window.pywebview.api.app_update_status=async()=>{throw Error('offline')};}")
            page.evaluate('refreshAppUpdate().catch(()=>{})')
            assert not page.locator('#app-update').is_visible()
            page.evaluate("activate({id:'palworld',name:'Palworld',status:'not-added'})")
            assert not page.locator('#dialog-title').is_visible()
            assert page.locator('#dialog-actions button').all_text_contents()==['YES','NO']
            widths=page.locator('#dialog-actions button').evaluate_all('nodes=>nodes.map(e=>e.getBoundingClientRect().width)')
            assert abs(widths[0]-widths[1])<1
            page.get_by_role('button',name='NO',exact=True).click()
            assert page.locator('#dialog-message').inner_text()=='why tf u tryna open a Palworld file editor then?????? bruh'
            page.get_by_role('button',name='wait, let me change my answer',exact=True).click()
            assert page.locator('#dialog-actions button').all_text_contents()==['YES','NO']
            page.get_by_role('button',name='NO',exact=True).click()
            page.get_by_role('button',name='close',exact=True).click()
            assert not page.locator('#modal').is_visible()
            page.evaluate('LexeditorUI.openSettings()')
            page.wait_for_selector('.lex-global-setting input')
            font=Path(os.environ['LOCALAPPDATA'])/'Lexeditor/game-data/ff8/generated/ff8-menu.ttf'
            page.route('**/assets/ff8-menu.ttf*',lambda r:r.fulfill(path=str(font)))
            page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
            page.evaluate('document.fonts.ready')
            assert page.get_by_role('checkbox',name='Wrap around at the ends',exact=True).count()==2
            for width,height in [(2048,1080),(900,620),(600,500)]:
                page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(250)
                metrics=page.locator('.lex-global-settings').evaluate("""dialog=>({width:dialog.getBoundingClientRect().width,scroll:dialog.scrollWidth,client:dialog.clientWidth,cards:[...dialog.querySelectorAll('.lex-global-setting:not([hidden])')].map(e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height}})})""")
                assert metrics['scroll']<=metrics['client']+2,metrics
                if width == 2048:
                    assert page.locator('.lex-global-settings').evaluate('n=>n.scrollHeight<=n.clientHeight+1')
                checks=page.locator('.lex-global-setting input[type="checkbox"]').evaluate_all('ns=>ns.map(n=>({w:n.getBoundingClientRect().width,h:n.getBoundingClientRect().height,p:getComputedStyle(n).padding}))')
                assert all(abs(n['w']-n['h'])<1 for n in checks),checks
                assert page.locator('.lex-global-setting input:not([type="checkbox"]),.lex-global-setting select').evaluate_all('ns=>new Set(ns.filter(n=>n.getBoundingClientRect().height).map(n=>Math.round(n.getBoundingClientRect().height))).size===1')
                assert page.locator('.lex-library-setting .lex-readonly-field').count()==1
                assert page.locator('.lex-global-settings > .lex-dialog-status').inner_text()==''
                assert all(c['w']>=190 for c in metrics['cards']),metrics
                cards=metrics['cards']
                for i,a in enumerate(cards):
                    for b in cards[i+1:]:
                        assert min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x'])<=1 or min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y'])<=1,metrics
                page.screenshot(path=str(Path(tempfile.gettempdir())/f'lex-settings-{width}.png'))
                if width == 2048:
                    page.locator('.lex-settings-save-control').hover()
                    page.wait_for_timeout(150)
                    page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-settings-save-preview.png'))
                    page.mouse.move(0,0)
            page.evaluate("""()=>{
                document.querySelector('.lex-global-settings-backdrop').remove();
                const cards=Array.from({length:7},(_,i)=>LexeditorUI.detailSection({title:`Group ${i}`,body:Array.from({length:30},(_,j)=>LexeditorUI.detailField({label:`Property ${j}`,control:LexeditorUI.readonlyField(`Value ${j}`)}))}));
                const main=document.querySelector('#games');
                main.style.cssText='display:block;min-height:0;height:calc(100vh - 100px);padding:8px';
                main.replaceChildren(LexeditorUI.settingsColumns(cards));
            }""")
            for width in (900,2048):
                page.set_viewport_size({'width':width,'height':700});page.wait_for_timeout(300)
                panel=page.locator('.lex-tweaks-scroll')
                metrics=panel.evaluate('e=>({w:e.clientWidth,sw:e.scrollWidth,h:e.clientHeight,sh:e.scrollHeight,fragments:[...e.querySelectorAll(".lex-tweak-column > section")].map(c=>c.getClientRects().length)})')
                # Tweaks are paged, not scrolled (71226ff). Seven groups of
                # thirty rows are taller than a page, so they go on in the next
                # column and on further pages: nothing overflows either way, no
                # section is split mid-row, and there is more than one page.
                assert metrics['sw']<=metrics['w']+1 and metrics['sh']<=metrics['h']+1,metrics
                assert all(n==1 for n in metrics['fragments']),metrics
                pages=page.locator('.lex-tweaks-paged').evaluate('n=>n.lexPaging().starts.length')
                assert pages>1,pages
                assert panel.locator('.lex-detail-field').last.evaluate('(e)=>{const a=e.getBoundingClientRect(),b=e.closest(".lex-tweaks-scroll").getBoundingClientRect();return a.bottom<=b.bottom+1}')
                page.screenshot(path=str(Path(tempfile.gettempdir())/f'lex-tweaks-scroll-{width}.png'))
            browser.close()
    finally:server.shutdown();server.server_close();thread.join(timeout=2)
    print('Settings cards fit without overlap at 2048, 900 and 600 pixels.')
if __name__=='__main__':main()
