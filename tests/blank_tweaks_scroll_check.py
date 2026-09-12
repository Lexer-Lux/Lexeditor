import functools,threading
from playwright.sync_api import sync_playwright
from global_browser_check import Handler,ThreadingHTTPServer,STUB,ROOT

def main():
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True);page=browser.new_page();page.add_init_script(STUB)
   page.goto(f'http://127.0.0.1:{server.server_port}/games/blank/editor.html')
   page.get_by_role('button',name='2 Panels',exact=True).click()
   for width,height in [(2048,1080),(1350,850),(900,550)]:
    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(300)
    gaps=page.evaluate("""()=>{const main=document.querySelector('main'),panel=main.querySelector('.blank-detail'),pager=document.querySelector('.lex-pager');const m=main.getBoundingClientRect(),p=panel.getBoundingClientRect();return {left:parseFloat(getComputedStyle(main).paddingLeft),right:m.right-p.right,bottom:pager.getBoundingClientRect().top-p.bottom}}""")
    assert abs(gaps['left']-gaps['bottom'])<1,gaps
    assert abs(gaps['right']-gaps['bottom'])<1,gaps
   print('Panel bottom and side gaps match at three window sizes.')
   page.get_by_role('button',name='Tweaks',exact=True).click()
   for width,height in [(1350,850),(900,550),(700,450)]:
    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(300)
    metrics=page.evaluate("""()=>({root:[document.documentElement.clientHeight,document.documentElement.scrollHeight],scrolls:[...document.querySelectorAll('body,main,.blank-layout,.blank-detail,.lex-detail-panel-body')].map(e=>({name:e.className||e.tagName,h:e.clientHeight,sh:e.scrollHeight,overflow:getComputedStyle(e).overflowY}))})""")
    assert metrics['root'][0]==metrics['root'][1],metrics
    assert page.evaluate('getComputedStyle(document.documentElement).overflowY')=='hidden'
    scrolling=[e for e in metrics['scrolls'] if e['overflow'] in ('auto','scroll') and e['sh']>e['h']+1]
    assert len(scrolling)==1 and scrolling[0]['name']=='lex-detail-panel-body',metrics
    pane=page.locator('.blank-tweaks > .lex-detail-panel-body')
    pane.evaluate('e=>e.scrollTop=e.scrollHeight')
    assert pane.evaluate('e=>e.scrollTop')>0
    assert pane.locator('.lex-detail-section').last.evaluate('e=>e.getBoundingClientRect().bottom<=e.parentElement.getBoundingClientRect().bottom+1')
   print('One working content scrollbar at 1350, 900 and 700 pixels; no page scrollbar.')
   browser.close()
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
if __name__=='__main__':main()
