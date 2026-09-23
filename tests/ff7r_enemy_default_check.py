"""The enemy editor must open the general table before map-specific tables."""
import functools, threading, json
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright
from global_browser_check import Handler,ThreadingHTTPServer,STUB,ROOT

def main():
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 field='End/Content/GameContents/DataObject/Field/010-MAKO1/EnemyParameter'
 general='End/Content/GameContents/DataObject/Resident/EnemyParameter'
 def route_api(route):
  url=urlparse(route.request.url);payload={}
  if url.path=='/api/catalog':payload={'assets':[{'asset':field,'name':'EnemyParameter'},{'asset':general,'name':'EnemyParameter'}]}
  if url.path=='/api/data':
   asset=parse_qs(url.query)['asset'][0];count=509 if asset==general else 1
   payload={'asset':asset,'properties':[{'name':'HPMax','label':'HP','type':'INT32','editable':False}], 'records':[{'id':i,'tag':f'Enemy {i}' if asset==general else 'Boss12','values':{'HPMax':100}} for i in range(count)]}
  route.fulfill(json=payload)
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True);page=browser.new_page();page.add_init_script(STUB);page.route('**/api/**',route_api)
   page.goto(f'http://127.0.0.1:{server.server_port}/plugins/ff7r/editor.html')
   page.wait_for_function('state.data?.records?.length===1')
   page.get_by_role('button',name='Enemies',exact=True).click()
   page.wait_for_function('state.data?.records?.length===509')
   page.get_by_role('tab',name='General',exact=True).wait_for(state='visible')
   assert '509' in page.locator('.lex-page-summary').inner_text()
   page.get_by_role('tab',name='010-MAKO1',exact=True).click()
   page.wait_for_function('state.data?.records?.length===1')
   assert 'Boss12' in page.locator('.ff7r-table').inner_text()
   page.get_by_role('tab',name='General',exact=True).click()
   page.wait_for_function('state.data?.records?.length===509')
   browser.close()
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
 print('Enemies opens General with 509 rows; map-specific tables remain selectable.')
if __name__=='__main__':main()
