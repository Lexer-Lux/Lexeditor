"""A curated row shows the name the game shows, or the key the game stores.

PlayerParameter rows carry no name property at all: the installed table keys
them "Cloud01".."Cloud99" and stores six stats and nothing else. PlayerTable is
what names them, so the server resolves that join and sends it as recordNames.
This check drives the rendered Characters tab with such a payload and reads the
result off the page, then does the same for a table that joins nothing, where
the row must keep its own key rather than gain an invented name.
"""
import functools, threading, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from global_browser_check import Handler,ThreadingHTTPServer,STUB,ROOT

PLAYER='End/Content/GameContents/DataObject/Resident/PlayerParameter'
ENEMY='End/Content/GameContents/DataObject/Resident/EnemyParameter'
STAT=[{'name':n,'label':n,'type':'INT32','editable':True,'min':0,'max':9999}
      for n in ('HPMax','MPMax','Strength','Magic','Vitality','Spilit')]

def rows(page,tab):
 return page.evaluate("tab=>curatedRows(curatedSpec(tab)).map(r=>[r.tag,r.name])",tab)

def main():
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1500,'height':900})
   page.add_init_script(STUB)
   page.route('**/api/**',lambda route:route.fulfill(json={}))
   page.goto(f'http://127.0.0.1:{server.server_port}/plugins/ff7r/editor.html')
   page.wait_for_function('!!state.error')
   page.evaluate("()=>localStorage.clear()")

   # Characters: three keys, two characters, every name from PlayerTable.
   page.evaluate("""([asset,props])=>{
    state.error='';state.busy=false;state.tab='characters';state.selected=1;
    state.asset=asset;state.catalog={assets:[{asset,name:'PlayerParameter'}]};
    state.data={asset,properties:props,textLookup:{},recordNames:{Cloud07:'Cloud',RedXIII07:'Red XIII'},
     records:[{id:0,tag:'Cloud07',values:{HPMax:1000,MPMax:100,Strength:50,Magic:40,Vitality:45,Spilit:42}},
              {id:1,tag:'RedXIII07',values:{HPMax:1100,MPMax:90,Strength:55,Magic:35,Vitality:50,Spilit:38}},
              {id:2,tag:'Sonon07',values:{HPMax:900,MPMax:80,Strength:45,Magic:30,Vitality:40,Spilit:35}}]};
    render();}""",[PLAYER,STAT])
   assert rows(page,'characters')==[['Cloud07','Cloud'],['RedXIII07','Red XIII'],['Sonon07','Sonon07']],rows(page,'characters')
   table=page.locator('.ff7r-table').inner_text()
   for wanted in ('Cloud07','Cloud','RedXIII07','Red XIII','Sonon07'):
    assert wanted in table,(wanted,table)
   # The stat is Spirit on screen and Spilit in the data, and the help text
   # says so, so a reader can still match the field to the game's own table.
   main_text=page.locator('#main').inner_text()
   assert 'Spirit' in main_text and 'Spilit' not in main_text,main_text
   assert page.locator('.lex-detail .lex-info-help[aria-label*="Spilit"]').count()==1,main_text
   # The subtitle names the selected record, not the table it was read from.
   meta=page.locator('.lex-detail-panel-meta').first.inner_text()
   assert meta=='Data ID RedXIII07',meta
   assert 'PlayerParameter' not in page.locator('.lex-detail-panel-identity').first.inner_text()
   assert page.locator('.lex-detail-panel-title').first.inner_text()=='Red XIII'
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-ff7r-characters-names.png'),full_page=True)

   # Enemies: the installed table joins no name, so every row keeps its key
   # and no row is dropped for want of one.
   page.evaluate("""([asset,props])=>{
    state.tab='enemies';state.selected=0;state.asset=asset;
    state.catalog={assets:[{asset,name:'EnemyParameter'}]};
    state.data={asset,properties:props,textLookup:{},recordNames:{},
     records:[{id:0,tag:'Boss12',values:{HPMax:9000,BPMax:100,Strength:40,Magic:30,Vitality:50,Spilit:40}},
              {id:1,tag:'Enemy10',values:{HPMax:500,BPMax:20,Strength:10,Magic:5,Vitality:10,Spilit:5}}]};
    render();}""",[ENEMY,STAT])
   assert rows(page,'enemies')==[['Boss12','Boss12'],['Enemy10','Enemy10']],rows(page,'enemies')
   assert page.locator('.lex-detail-panel-meta').first.inner_text()=='Data ID Boss12'
   assert 'EnemyParameter' not in page.locator('.lex-detail-panel-identity').first.inner_text()
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-ff7r-enemies-names.png'),full_page=True)
   browser.close()
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
 print('Characters name every row from PlayerTable; enemy rows with no name keep their own key.')
if __name__=='__main__':main()
