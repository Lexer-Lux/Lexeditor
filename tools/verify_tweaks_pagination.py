"""Headless reachability checks for the shared Tweaks pager."""
from pathlib import Path
import re
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 page=browser.new_page()
 page.route("http://fixture/**",lambda route:route.fulfill(body="<html></html>",content_type="text/html"))
 page.goto("http://fixture/")
 css=(root/"ui/framework.css").read_text(encoding="utf-8")
 rdr=(root/"plugins/rdr2/editor.html").read_text(encoding="utf-8")
 page.set_content('<style>'+re.search(r'<style>(.*?)</style>',rdr,re.S)[1]+css+'</style><header class="lex-shell-header" style="height:130px;flex-shrink:0">Tweaks</header><main></main>')
 page.add_script_tag(path=str(root/"ui/framework.js"))
 page.evaluate("""() => {const u=LexeditorUI;document.querySelector('main').append(u.settingsColumns(Array.from({length:19},(_,i)=>u.el('section',{'data-card':i},u.el('h2',{},'Group '+i),u.el('div',{style:'height:900px'},'Tall group'),u.el('input',{'aria-label':'Setting '+i,value:i})))))}""")
 for width,height,zoom in [(1280,720,1),(800,600,1),(800,600,1.5),(1920,1080,.75)]:
  page.set_viewport_size({'width':width,'height':height});page.evaluate('(z)=>{document.body.style.zoom=z;document.body.style.height=`${100/z}dvh`}',zoom)
  page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
  first=page.get_by_role('button',name='First page',exact=True)
  if first.is_enabled():first.click()
  page.get_by_label('Setting 0',exact=True).fill('changed')
  seen=[]
  while True:
   seen+=page.locator('[data-card]:visible').evaluate_all('(nodes)=>nodes.map(n=>+n.dataset.card)')
   field=page.locator('[data-card]:visible input').last
   field.scroll_into_view_if_needed()
   box=field.bounding_box();assert box['y']>=0 and box['y']+box['height']<=height,(width,height,zoom,box)
   pager=page.locator('.lex-tweaks-pages').bounding_box();assert pager['y']+pager['height']<=height+1,(zoom,pager)
   if not page.get_by_role('button',name='Next page',exact=True).is_enabled():break
   page.get_by_role('button',name='Next page',exact=True).click()
  assert seen==list(range(19)),seen
  assert page.get_by_label('Setting 0',exact=True).input_value()=='changed'
 print('PASS: every group, tall final controls, and pager reachable at four viewport/scale combinations')
 browser.close()
