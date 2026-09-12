"""Check GF HP Casting in the complete FF8 editor without saving any changes."""
import sys,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from games.ff8.server import create_server
from playwright.sync_api import sync_playwright
server=create_server(0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.route('**/api/**',lambda route:route.abort() if route.request.method!='GET' else route.continue_())
  page.goto(f'http://127.0.0.1:{server.server_port}/')
  page.wait_for_function("!document.body.innerText.includes('Preparing Final Fantasy VIII')")
  page.locator('nav [data-tab="settings"]').click()
  toggle=page.get_by_label('GF HP Casting',exact=True);toggle.wait_for()
  page.get_by_label('Monogamy',exact=True).check();page.get_by_label('No Magic Consumption',exact=True).check();toggle.check()
  page.locator('nav [data-tab="magic"]').click()
  field=page.get_by_role('spinbutton',name='GF HP cost for Aero');field.wait_for();field.fill('321');assert field.input_value()=='321'
  page.locator('nav [data-tab="settings"]').click();page.get_by_label('Monogamy',exact=True).uncheck()
  assert toggle.is_disabled() and not toggle.is_checked()
  page.get_by_label('No Magic Consumption',exact=True).uncheck();page.get_by_label('Monogamy',exact=True).check();assert toggle.is_disabled()
  page.get_by_label('No Magic Consumption',exact=True).check();assert not toggle.is_disabled() and toggle.is_checked()
  page.locator('nav [data-tab="magic"]').click();assert page.get_by_role('spinbutton',name='GF HP cost for Aero').input_value()=='321'
  assert not errors,errors
  browser.close()
 print('Full FF8 editor: cost control, retained values and both dependencies passed; no writes sent')
finally:
 server.shutdown();server.server_close();thread.join()
