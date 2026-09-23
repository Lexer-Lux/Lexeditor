"""Pinning a resolved property must retain its visible name."""
import functools, threading, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from global_browser_check import Handler,ThreadingHTTPServer,STUB,ROOT

def main():
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1500,'height':900});page.add_init_script(STUB)
   page.route('**/api/**',lambda route:route.fulfill(json={}))
   page.goto(f'http://127.0.0.1:{server.server_port}/plugins/ff7r/editor.html')
   page.wait_for_function('!!state.error')
   page.evaluate("""()=>{
    state.error='';state.busy=false;state.tab='abilities';state.selected=0;
    state.asset='BattleAbility.uasset';state.catalog={assets:[{asset:state.asset,name:'Abilities'}]};
    state.data={asset:state.asset,properties:[{name:'Name',label:'Name',type:'STRING',editable:false}],records:[{id:0,tag:'GuardScorpion_Search',values:{Name:'$bt_GuardScorpion_Search'}}],textLookup:{'$bt_GuardScorpion_Search':'Target Scanner'}};
    render();
   }""")
   page.get_by_role('button',name='Pin Name column',exact=True).click()
   page.evaluate("curatedPrefs(curatedSpec('abilities')).move('p:Name','tag')")
   page.wait_for_timeout(200)
   table=page.locator('.ff7r-table')
   assert 'Target Scanner' in table.inner_text()
   assert '$bt_GuardScorpion_Search' not in table.inner_text()
   assert page.evaluate("curatedPrefs(curatedSpec('abilities')).active().map(c=>c.key).filter(k=>k!=='enabled').slice(0,2)")==['tag','p:Name']
   assert page.evaluate("propertyCellValue({values:{Name:['$bt_GuardScorpion_Search','Unknown']}},{name:'Name'})")=='Target Scanner, Unknown'
   assert page.evaluate("propertyCellValue({values:{Name:42}},{name:'Name'})")==42
   page.evaluate("state.curatedQuery='Target Scanner'")
   assert page.evaluate("curatedRows(curatedSpec('abilities')).length")==1
   page.evaluate("state.curatedQuery='$bt_GuardScorpion_Search'")
   assert page.evaluate("curatedRows(curatedSpec('abilities')).length")==1
   for font_size in (10,14,18):
    table.evaluate('(e,size)=>e.style.fontSize=`${size}px`',font_size)
    bounds=table.evaluate("""e=>{const head=e.querySelector('.lex-column-list-head-cell[data-column-key="tag"]').getBoundingClientRect();return [...e.querySelectorAll('.lex-column-list-cell[data-column-key="id"]')].map(c=>({head:head.right,row:c.getBoundingClientRect().right}))}""")
    assert bounds and all(abs(b['head']-b['row'])<1 for b in bounds),bounds
   table.evaluate("e=>e.style.removeProperty('font-size')")
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-ff7r-pinned-name.png'))
   page.evaluate("""()=>{
    const row={id:0,tag:'EB0000_00_GuardScorpion_Standard',values:{}};
    state.loot={groups:[]};
    document.querySelector('#main').replaceChildren(lootRecordPanel(row));
   }""")
   assert page.locator('.lex-detail-panel-id').count()==0
   assert 'EB0000_00_GuardScorpion_Standard' in page.locator('#main').inner_text()
   browser.close()
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
 print('Pinned Name shows Target Scanner after the real record key; raw keys remain searchable.')
if __name__=='__main__':main()
