"""Rendered checks for the single integration status and optional Misc. order."""
import functools,json,threading,tempfile,sys
from pathlib import Path
from types import SimpleNamespace
from playwright.sync_api import sync_playwright
from global_browser_check import Handler,ThreadingHTTPServer,STUB,ROOT
sys.path.insert(0,str(ROOT))
from games.chrono_trigger.coverage import augment_data_map

def main():
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
 threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':900});page.add_init_script(STUB)
   def fixture(route):
    response=route.fetch()
    route.fulfill(response=response,body=response.text().replace('{id:"graphs",label:"Graphs"}','{id:"data",label:"Misc."},{id:"graphs",label:"Graphs"}'))
   page.route('**/games/blank/editor.html',fixture)
   page.goto(f'http://127.0.0.1:{server.server_port}/games/blank/editor.html')
   page.wait_for_selector('button[data-tab=data]')
   tabs=page.locator('button[data-tab]').evaluate_all('(es)=>es.map(e=>e.dataset.tab)')
   assert tabs[-2:]==['data','tweaks'],tabs
   store=SimpleNamespace(archive=SimpleNamespace(entries=[SimpleNamespace(path='Game/common/bankc6.bin')]))
   rows=augment_data_map(store,{'rows':[], 'counts':{}})['rows']
   rows += [{'filename':'text.txt','controls':'Dialogue','status':'integrated','coverage':'structured','notes':'Edit all text.'}]
   page.evaluate('''rows=>{let status='';const render=()=>document.querySelector('main').replaceChildren(LexeditorUI.dataMap({rows,status,changeStatus:value=>{status=value;render()}}).content);render()}''',rows)
   assert page.get_by_role('columnheader',name='Coverage',exact=True).count()==0
   assert page.get_by_role('columnheader',name='Integration',exact=True).count()==1
   select=page.get_by_role('combobox',name='Filter files by integration')
   for value in ('integrated','partial','not-integrated'):
    select.select_option(value)
    statuses=page.locator('.lex-data-map-table .lex-integration-status').evaluate_all('(es)=>es.map(e=>e.className)')
    assert statuses and all(e.endswith(' '+value) for e in statuses),statuses
   select.select_option('')
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-human-datamap.png'))
   browser.close()
   print('Single Integration column, all three filters, and Misc. before Tweaks passed.')
 finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
