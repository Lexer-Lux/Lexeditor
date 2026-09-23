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
_SHARED_UI_ENV=os.environ.get('LEXEDITOR_SHARED_UI_ROOT','').strip()
SHARED_UI_ROOT=Path(_SHARED_UI_ENV).resolve() if _SHARED_UI_ENV else ROOT
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'out'/'data-map-browser'
OUT.mkdir(parents=True,exist_ok=True)
# Derived, never hand-listed: a hardcoded tuple silently skipped ff7r, so its
# Data Map went unchecked from the day the plugin landed. New plugins are
# covered by existing. ff7_2013 is an edition of ff7 rather than its own folder.
GAMES=tuple(sorted({p.name for p in (ROOT/'plugins').iterdir()
                    if (p/'editor.html').is_file()} | {'ff7_2013'}))
if os.environ.get('DATAMAP_GAMES'):
    GAMES=tuple(os.environ['DATAMAP_GAMES'].split(','))
ROWS=[{'id':str(i),'filename':f'file-{i:03}.dat','controls':f'Interface {i:03}',
       'coverage':['structured','view','source','unavailable'][i%4],
       'status':'partial' if i%4<3 else 'not-integrated', 'notes':('Long scoped explanation. '*40),
       'target':'items','dataset':'fixture-data','datasetKey':'fixture-data','openable':i%4<3} for i in range(100)]
ROWS[0]['filename']='same-file.dat';ROWS[4]['filename']='same-file.dat'  # IDs must not collapse sections.
# The injected row must name a target the plugin's real Data Map adapter supports.
# Most plugins route generic item rows; Bannerlord has explicit editor targets.
OPEN_TARGETS={'bannerlord':'skills','stardew_valley':'objects'}

def html_for(game):
    source_game='ff7' if game=='ff7_2013' else game
    game_root=ROOT/'plugins'/source_game
    html=(game_root/'editor.html').read_text(encoding='utf-8')
    # Synthetic set_content() documents otherwise use about:blank, which cannot
    # resolve the shared framework's optional relative assets or push fragment URLs.
    html=html.replace('<head>','<head><base href="http://127.0.0.1:9/">',1)
    stub='''const replace=history.replaceState.bind(history),push=history.pushState.bind(history);
    history.replaceState=(s,u)=>replace(s,u);history.pushState=(s,u)=>push(s,u);
    window.fetch=()=>new Promise(()=>{});
    window.__lexeditorPlugin={id:"'''+game+'''",name:"Fixture edition",edition:"Fixture"};'''
    html=html.replace('<link rel="stylesheet" href="/shared/framework.css">','<style>'+(ROOT/'ui/framework.css').read_text(encoding='utf-8')+'</style>')
    html=html.replace('<script src="/shared/framework.js"></script>','<script>'+stub+'</script><script>'+(ROOT/'ui/framework.js').read_text(encoding='utf-8')+'</script>')
    # A plugin page loads its code and styles from modules beside it. There is
    # no server here, so every one the page names is inlined where it stands,
    # or nothing of the plugin runs and it looks like a plugin that failed to boot.
    folder=ROOT/'plugins'/source_game
    html=re.sub(r'<script src="(?!/shared/)/?([A-Za-z0-9_./-]+\.js)"></script>',
                lambda m:'<script>'+(folder/Path(m[1]).name).read_text(encoding='utf-8').replace('</script','<\\/script')+'</script>',html)
    html=re.sub(r'<link rel="stylesheet" href="(?!/shared/)/?([A-Za-z0-9_./-]+\.css)">',
                lambda m:'<style>'+(folder/Path(m[1]).name).read_text(encoding='utf-8')+'</style>',html)
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
                html=html_for(game)
                if game=='warband':
                    # Warband's shared shell reads sessionStorage during boot.
                    # set_content() uses an opaque/storage-refused document in
                    # Chromium, so give this synthetic fixture a normal in-memory
                    # HTTP origin without opening a loopback server.
                    html=html.replace('http://127.0.0.1:9/','http://warband-data-map.test/')
                    def route_warband_fixture(route):
                        if route.request.resource_type=='document':
                            route.fulfill(status=200,body=html,content_type='text/html')
                        else:
                            route.abort()
                    page.route('http://warband-data-map.test/**',route_warband_fixture)
                    page.goto('http://warband-data-map.test/',wait_until='domcontentloaded')
                else:
                    page.set_content(html,wait_until='domcontentloaded')
                # Most plugins keep one `state` object the map can be seeded
                # into. Palworld keeps its own named globals instead, so it is
                # seeded through those rather than being called broken for not
                # having a variable of that name.
                booted = page.evaluate(
                    'typeof state !== "undefined" || typeof mapRows !== "undefined" '
+ '|| typeof datamap !== "undefined"')
                if not booted and game != 'blank':
                    raise AssertionError((game,width,height,'plugin state missing',errors,page.locator('body').inner_text()[:1200]))
                target=OPEN_TARGETS.get(game,'items')
                fixture_rows=[{**row,'target':target} for row in ROWS]
                if game=='blank':
                    page.evaluate('navigate("datamap")')
                elif game=='terraria':
                    # Terraria maps server rows by file extension; seed one of
                    # each kind so the shared filter sees every status.
                    page.evaluate('''rows=>{
                      const kinds=['.cs','.hjson','.png','.csproj','.txt'];
                      mapRows=rows.map((row,index)=>({path:index===0?'build.txt':
                        'file-'+String(index).padStart(3,'0')+kinds[index%kinds.length],
                        family:'Fixture'}));
                      navigate("datamap");
                    }''',fixture_rows)
                elif game=='project_zomboid':
                    # Zomboid keeps its map rows in a module-level datamap object
                    # keyed by editor label; seed and render through its own path.
                    page.evaluate('''rows=>{
                      datamap.rows=rows.map((row,index)=>({filename:row.filename,notes:row.notes,editor:index%3===0?'Metadata':index%3===1?'Items':'Unmapped'}));
                      renderDatamap();navigate("datamap");
                    }''',fixture_rows)
                elif game=='palworld':
                    page.evaluate('''rows=>{
                      mapRows=rows;
                      model=model||{ModName:"Data map sample",PackageName:"sample"};
                      navigate("datamap");
                    }''',ROWS)
                else:
                    open_target=OPEN_TARGETS.get(game,'items')
                    fixture_rows=[{**row,'target':open_target} for row in ROWS]
                    page.evaluate('''rows=>{
                      const mapPayload={rows};
                      window.fetch=input=>/\/api\/data-?map/.test(String(input))
                        ? Promise.resolve({ok:true,status:200,json:async()=>mapPayload})
                        : new Promise(()=>{});
                      state.dataMap=mapPayload;state.datamap=mapPayload;state.booting=false;
                      if(Object.hasOwn(state,"loaded"))state.loaded=true;
                      state.dashboard={runtime:{installed:true},baseline:{},game:{},manifest:{},paths:{},problems:[]};
                      if(typeof state.data!=="object" || !state.data)state.data={};
                      if(typeof state.config!=="undefined")state.config={datasets:{mine:{readonly:false,label:"My Mod"}}};
                      navigate("datamap");
                    }''',ROWS)
                    page.evaluate('state.busy=false;render();if(typeof refreshShell==="function")refreshShell();else if(typeof shell!=="undefined"&&shell.refresh)shell.refresh();')
                    if game=='warband':
                        page.evaluate('()=>LexeditorUI.finishPluginLoading()')
                        page.wait_for_function('!document.documentElement.classList.contains("lex-loading-live")')
                        page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.wait_for_selector('.lex-data-map-table')
                # Boot never finishes here (its fetches never resolve), so the
                # loading screen would stay over the page and take every click.
                # End it the way a finished boot does.
                page.evaluate('LexeditorUI.finishPluginLoading()')
                page.wait_for_function('!document.documentElement.classList.contains("lex-loading-live")',timeout=15000)
                page.wait_for_timeout(600)
                shared=page.locator('.lex-data-map-table').count()>0
                if not shared:
                    # Chrono Trigger predates the shared Data Map component but
                    # is still a real map and must remain covered by the derived
                    # all-plugin sweep. Exercise its actual renderer/open callback
                    # rather than pretending it has shared filter controls.
                    assert game=='chrono_trigger',(game,'unexpected bespoke Data Map')
                    table=page.locator('.ct-view table').first
                    assert table.locator('tbody tr').count()==len(fixture_rows),(game,'fixture rows missing')
                    page.evaluate('navigate=(target,filters)=>{window.mapOpened={target,filters}}')
                    table.locator('tbody tr').first.click()
                    assert page.evaluate('mapOpened.target')==target,game
                    page.screenshot(path=str(OUT/f'{game}-{width}.png'),full_page=True)
                    assert not errors,(game,errors)
                    results.append({'game':game,'width':width,'height':height,'layout':'plugin-native','status':'passed'})
                    page.close();continue
                # A preview/source/parser does not produce an editable badge.
                page.get_by_role('combobox',name='Filter files by integration',exact=True).select_option('not-integrated')
                page.wait_for_timeout(250)
                assert page.locator('.lex-paged-list-detail').count()==1,game
                assert page.locator('.lex-pager').count()==1,game
                assert 'Structured editable' not in page.locator('.lex-data-map-table').inner_text(),game
                metrics=page.evaluate('''()=>{const list=document.querySelector('.lex-data-map-table'),box=list.getBoundingClientRect(),rows=[...list.querySelectorAll('.lex-column-list-row')];return{body:document.body.scrollHeight,viewport:innerHeight,scroll:list.scrollHeight,height:list.clientHeight,bottom:box.bottom,last:rows.at(-1)?.getBoundingClientRect().bottom,count:rows.length}}''')
                page.screenshot(path=str(OUT/f'{game}-{width}.png'),full_page=True)
                location=page.locator('.lex-data-map-file .lex-data-map-location')
                assert location.count()==1,(game,width,'header file-location control missing')
                location.wait_for(state='visible')
                box=location.bounding_box()
                assert box and box['width']>0 and box['height']>0,(game,width,'header file-location control has no box')
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
                    # A plugin whose map declares no open target - Palworld's
                    # rows point at package files, not at an editor tab - has no
                    # adapter to verify, so only the filter is checked there.
                    opens=page.locator('.lex-data-map-open').count()
                    if opens:
                        if game=='warband':
                            # Warband's completed Data Map opens structured
                            # Module System datasets in Misc., preserving the
                            # dataset identity instead of pretending every row
                            # is an Items record.
                            page.locator('.lex-data-map-open').first.click()
                            assert page.evaluate('state.tab')=='misc',game
                            assert page.evaluate('moduleRecords.active()')=='fixture-data',game
                            page.evaluate('navigate("datamap")')
                            page.get_by_role('combobox',name='Filter files by integration',exact=True).wait_for()
                        else:
                            page.evaluate('navigate=(target,filters)=>{window.mapOpened={target,filters}}')
                            page.locator('.lex-data-map-open').first.click()
                            assert page.evaluate('mapOpened.target')=='items',game
                            if game=='ff9':assert page.evaluate('state.datasetChoice.items')=='fixture-data'
                    page.get_by_role('combobox',name='Filter files by integration',exact=True).select_option('not-integrated')
                    page.wait_for_timeout(200)
                    assert page.locator('.lex-data-map-open').count()==0,game
                if game in ('ff7','ff7_2013'):
                    # Late FFNx discovery must update the explicit coverage contract.
                    for available in (True,False):
                        row=page.evaluate("""available=>{
                          state.dataMap.rows=[{category:"tweaks",coverage:"unavailable",openable:false}];
                          syncConfigMap({available,path:"FFNx.toml",message:"Fixture"});
                          return state.dataMap.rows[0];
                        }""",available)
                        assert row['coverage']==('structured' if available else 'unavailable'),game
                        assert row['openable']==available,game
                assert not errors,(game,errors)
                results.append({'game':game,'width':width,'height':height,'layout':metrics,'status':'passed'})
                page.close()
    finally:
        browser.close()
(OUT/('results-'+('-'.join(GAMES))+'.json')).write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
