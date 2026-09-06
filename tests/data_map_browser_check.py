"""Actual plugin Data Map adapters + shared layout, with in-memory data only.

Boot fetches stay unresolved so no installed game or mod filesystem is touched.
The real HTML, plugin CSS, scripts, shell and map callbacks are exercised.
"""
from pathlib import Path
import json
import os
import re
import shutil
import sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'out'/'data-map-browser'
OUT.mkdir(parents=True,exist_ok=True)
GAMES=('ff7','ff7_2013','ff8','ff9','rdr','rdr2','blank')
if os.environ.get('DATAMAP_GAMES'):
    GAMES=tuple(os.environ['DATAMAP_GAMES'].split(','))
ROWS=[{'id':str(i),'filename':f'file-{i:03}.dat','controls':f'Interface {i:03}',
       'coverage':['structured','view','source','unavailable'][i%4],
       'status':'partial' if i%4<3 else 'not-integrated', 'notes':('Long scoped explanation. '*40),
       'target':'items','dataset':'fixture-data','openable':i%4<3} for i in range(100)]
ROWS[0]['filename']='same-file.dat';ROWS[4]['filename']='same-file.dat'  # IDs must not collapse sections.

def html_for(game):
    source_game='ff7' if game=='ff7_2013' else game
    html=(ROOT/'games'/source_game/'editor.html').read_text()
    stub='''const replace=history.replaceState.bind(history);history.replaceState=(s,u)=>replace(s,u);
    window.fetch=()=>new Promise(()=>{});
    window.__lexeditorPlugin={id:"'''+game+'''",name:"Fixture edition",edition:"Fixture"};'''
    html=html.replace('<link rel="stylesheet" href="/shared/framework.css">','<style>'+(ROOT/'ui/framework.css').read_text()+'</style>')
    html=html.replace('<script src="/shared/framework.js"></script>','<script>'+stub+'</script><script>'+(ROOT/'ui/framework.js').read_text()+'</script>')
    html=html.replace('<script src="/cards_ui.js"></script>','<script>'+(ROOT/'games/ff8/cards_ui.js').read_text()+'</script>')
    # No third-party requests are made by these HTML documents in this harness.
    return html

results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
    try:
        for game in GAMES:
            for width,height in [(900,620),(1200,800),(1600,1000)]:
                errors=[]
                page=browser.new_page(viewport={'width':width,'height':height})
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.set_content(html_for(game),wait_until='domcontentloaded')
                if game=='blank':
                    page.evaluate('navigate("datamap")')
                else:
                    page.evaluate('''rows=>{
                      state.dataMap={rows};state.datamap={rows};state.booting=false;
                      state.dashboard={runtime:{installed:true},baseline:{},game:{},manifest:{},paths:{},problems:[]};
                      if(typeof state.data!=="object" || !state.data)state.data={};
                      if(typeof state.config!=="undefined")state.config={datasets:{mine:{readonly:false,label:"My Mod"}}};
                      navigate("datamap");
                    }''',ROWS)
                page.wait_for_selector('.lex-data-map-table')
                page.wait_for_timeout(600)
                # A preview/source/parser does not produce an editable badge.
                page.get_by_role('combobox',name='Filter files by coverage',exact=True).select_option('unavailable' if game=='blank' else 'view')
                page.wait_for_timeout(250)
                assert page.locator('.lex-paged-list-detail').count()==1,game
                assert page.locator('.lex-pager').count()==1,game
                assert 'Structured editable' not in page.locator('.lex-data-map-table').inner_text(),game
                metrics=page.evaluate('''()=>{const list=document.querySelector('.lex-data-map-table'),box=list.getBoundingClientRect(),rows=[...list.querySelectorAll('.lex-column-list-row')];return{body:document.body.scrollHeight,viewport:innerHeight,scroll:list.scrollHeight,height:list.clientHeight,bottom:box.bottom,last:rows.at(-1)?.getBoundingClientRect().bottom,count:rows.length}}''')
                page.screenshot(path=str(OUT/f'{game}-{width}.png'),full_page=True)
                assert metrics['body']<=height+2,(game,metrics)
                assert metrics['scroll']<=metrics['height']+2,(game,metrics)
                if metrics['count']:assert metrics['last']<=metrics['bottom']+1,(game,metrics)
                if game!='blank':
                    # Pager changes must remain stable after fitted-capacity callbacks.
                    first=page.locator('.lex-data-map-table .lex-column-list-row').first.inner_text()
                    page.get_by_role('button',name='Next page',exact=True).click()
                    page.wait_for_timeout(350)
                    second=page.locator('.lex-data-map-table .lex-column-list-row').first.inner_text()
                    assert first!=second,(game,'next page did not advance')
                    page.wait_for_timeout(300)
                    assert page.locator('.lex-data-map-table .lex-column-list-row').first.inner_text()==second,(game,'pager oscillated')
                    page.get_by_role('button',name='Previous page',exact=True).click()
                    page.wait_for_timeout(250)
                    assert page.locator('.lex-data-map-table .lex-column-list-row').first.inner_text()==first,game
                    # Verify this plugin's actual open adapter (including FF9 dataset selection),
                    # without requiring another editor's unrelated fixture data.
                    page.evaluate('navigate=(target,filters)=>{window.mapOpened={target,filters}}')
                    page.locator('.lex-data-map-open').first.click()
                    assert page.evaluate('mapOpened.target')=='items',game
                    if game=='ff9':assert page.evaluate('state.datasetChoice.items')=='fixture-data'
                    page.get_by_role('combobox',name='Filter files by coverage',exact=True).select_option('source')
                    page.wait_for_timeout(200)
                    assert page.locator('.lex-data-map-open').count()==0,game
                assert not errors,(game,errors)
                results.append({'game':game,'width':width,'height':height,'layout':metrics,'status':'passed'})
                page.close()
    finally:
        browser.close()
(OUT/('results-'+('-'.join(GAMES))+'.json')).write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
