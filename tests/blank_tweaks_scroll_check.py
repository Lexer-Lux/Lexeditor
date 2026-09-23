import functools,threading
from playwright.sync_api import sync_playwright
from global_browser_check import Handler,ThreadingHTTPServer,STUB,ROOT

def main():
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True);page=browser.new_page();page.add_init_script(STUB)
   errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
   page.goto(f'http://127.0.0.1:{server.server_port}/plugins/blank/editor.html')
   # Blank's tabs are the component catalogue now; its demonstration views
   # still render and are opened by name.
   page.wait_for_selector('nav button[data-tab=organism]')
   page.evaluate("navigate('two')")
   for width,height in [(2048,1080),(1350,850),(900,550)]:
    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(300)
    gaps=page.evaluate("""()=>{const main=document.querySelector('main'),panel=main.querySelector('.blank-detail'),pager=document.querySelector('.lex-pager');const m=main.getBoundingClientRect(),p=panel.getBoundingClientRect();return {left:parseFloat(getComputedStyle(main).paddingLeft),right:m.right-p.right,bottom:pager.getBoundingClientRect().top-p.bottom}}""")
    assert abs(gaps['left']-gaps['bottom'])<1,gaps
    assert abs(gaps['right']-gaps['bottom'])<1,gaps
   print('Panel bottom and side gaps match at three window sizes.')
   page.evaluate("navigate('tweaks')")
   for width,height in [(1350,850),(900,550),(700,450)]:
    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(300)
    # Settings pages deal their cards into columns and page them rather than
    # scroll: no page scrollbar, nothing scrolling inside, and every card that
    # is shown fits inside the window.
    metrics=page.evaluate("""()=>({root:[document.documentElement.clientHeight,document.documentElement.scrollHeight],
      scrollers:[...document.querySelectorAll('main, main *')].filter(e=>{const s=getComputedStyle(e);
        return ['auto','scroll'].includes(s.overflowY)&&e.scrollHeight>e.clientHeight+1;}).map(e=>e.className||e.tagName),
      cards:[...document.querySelectorAll('.blank-tweaks .lex-detail-section')].filter(e=>e.offsetParent)
        .map(e=>e.getBoundingClientRect().bottom),
      bottom:document.querySelector('main').getBoundingClientRect().bottom})""")
    assert metrics['root'][0]==metrics['root'][1],metrics
    assert page.evaluate('getComputedStyle(document.documentElement).overflowY')=='hidden'
    assert not metrics['scrollers'],metrics
    assert metrics['cards'] and max(metrics['cards'])<=metrics['bottom']+1,metrics
   print('Tweaks pages its cards at 1350, 900 and 700 pixels: no scrollbar, nothing clipped.')
   # Every page fits, not only the one the fit was measured on, and the wheel
   # turns pages because there is nothing to scroll.
   # One column, so Blank's three cards need more than one page and each fits.
   page.set_viewport_size({'width':400,'height':450});page.wait_for_timeout(400)
   pages=page.evaluate("document.querySelector('.lex-tweaks-pages .lex-page-total').textContent")
   assert int(pages)>1,pages
   for number in range(2,int(pages)+1):
    page.hover('.lex-tweaks-scroll');page.mouse.wheel(0,120);page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('.lex-tweaks-pages .lex-page-number').value")==str(number)
    fit=page.evaluate("(s=>[s.scrollHeight,s.clientHeight])(document.querySelector('.lex-tweaks-scroll'))")
    assert fit[0]<=fit[1]+1,(number,fit)
   print('Every tweaks page fits, and the wheel turns them.')
   assert not errors,errors
   browser.close()
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
if __name__=='__main__':main()
