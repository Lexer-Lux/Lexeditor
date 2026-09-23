"""Check GF HP Casting in the complete FF8 editor without saving any changes."""
import sys,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright
server=create_server(0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.route('**/api/**',lambda route:route.abort() if route.request.method!='GET' else route.continue_())
  page.goto(f'http://127.0.0.1:{server.server_port}/')
  page.wait_for_function("!document.body.innerText.includes('Preparing Final Fantasy VIII')")
  page.locator('nav [data-tab="settings"]').click()
  def control(label, exact=True):
   # Page until the control is on screen rather than computing which page it
   # ought to be on. A page holds as many cards as the window can show and the
   # cards are dealt into columns, so neither a fixed count nor the child index
   # of a row says anything about where a control landed.
   field=page.get_by_label(label,exact=exact)
   first=page.get_by_role('button',name='First page',exact=True)
   if first.count() and first.is_enabled():
    first.click();page.wait_for_timeout(120)
   nxt=page.get_by_role('button',name='Next page',exact=True)
   for _ in range(40):
    if field.count() and field.is_visible():
     return field
    if not nxt.count() or not nxt.is_enabled():
     break
    nxt.click();page.wait_for_timeout(120)
   return field
  toggle=control('GF HP Casting');toggle.wait_for()
  control('Monogamy').check();control('No Magic Consumption').check();control('GF HP Casting').check()
  page.locator('nav [data-tab="magic"]').click()
  field=page.get_by_role('spinbutton',name='GF HP cost for Aero');field.wait_for();field.fill('321');assert field.input_value()=='321'
  page.locator('nav [data-tab="settings"]').click();control('Monogamy').uncheck()
  assert toggle.is_disabled() and not toggle.is_checked()
  control('No Magic Consumption').uncheck();control('Monogamy').check();assert toggle.is_disabled()
  control('No Magic Consumption').check();assert not toggle.is_disabled() and toggle.is_checked()
  page.locator('nav [data-tab="magic"]').click();assert page.get_by_role('spinbutton',name='GF HP cost for Aero').input_value()=='321'
  assert not errors,errors
  browser.close()
 print('Full FF8 editor: cost control, retained values and both dependencies passed; no writes sent')
finally:
 server.shutdown();server.server_close();thread.join()
