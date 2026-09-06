"""Rendered fixture checks. No installed game assets or personal mod data used."""
from __future__ import annotations
import base64
import io
import os
import json
from pathlib import Path
import sys
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from games.warband import server

ARTIFACTS=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'out'/'warband-browser'
ARTIFACTS.mkdir(parents=True,exist_ok=True)

def png(color):
    out=io.BytesIO();Image.new('RGBA',(32,32),color).save(out,'PNG');return out.getvalue()
TEXTURE=png((200,150,70,255));ICON=png((150,110,60,255))
positions=[[-.3,-.15,-1],[.3,-.15,-1],[.3,-.15,1],[-.3,-.15,1],[-.3,.15,-1],[.3,.15,-1],[.3,.15,1],[-.3,.15,1]]
triangles=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[3,2,6],[3,6,7],[1,5,6],[1,6,2],[0,3,7],[0,7,4]]
MODEL={'cacheKey':'a'*64,'mesh':'fixture_sword','material':'fixture_steel','resource':'fixture.brf','texture':'/fixture-texture.png','summary':{'vertices':8,'triangles':12},'geometry':{'positions':positions,'normals':[[0,-1,0]]*8,'texCoords':[[0,0],[1,0],[1,1],[0,1]]*2,'triangles':triangles,'bounds':{'min':[-.3,-.15,-1],'max':[.3,.15,1]}}}
TROOPS=[{'id':id,'name':name,'faction':faction,'level':level,'flags':'tf_guarantee_armor','line':i+1,'status':'active','plural':name+'s'} for i,(id,name,faction,level) in enumerate([
    ('recruit','Recruit','fac_north',1),('footman','Footman','fac_north',10),('archer','Archer','fac_north',10),('knight','Knight','fac_north',20),('guard','Guard','fac_north',20),('militia','Militia','fac_north',2),('elite_militia','Elite militia','fac_north',12),('horseman','Horseman','fac_south',10),('rider','Rider','fac_south',20)])]
UPGRADES=[{'fromId':a,'toId':b} for a,b in [('recruit','footman'),('recruit','archer'),('footman','knight'),('footman','guard'),('militia','elite_militia'),('horseman','rider')]]
ITEMS=[{'id':f'fixture_{i:03}','name':f'Fixture sword {i:03}','type':'one_handed_wpn','meshes':['fixture_sword'],'inventoryMesh':'fixture_sword','line':i+1} for i in range(65)]
ITEMS.append({'id':'broken','name':'Missing texture fixture','type':'goods','meshes':['broken'],'inventoryMesh':'broken','line':100})


def main():
    with tempfile.TemporaryDirectory() as temp:
        project=Path(temp);module=project/'ModuleSystem';module.mkdir();(project/'Module').mkdir();(project/'Module'/'module.ini').write_text('')
        (project/'settings.ini').write_text('[Test]\nenabled=1\n')
        for records in server.DATA_CATALOG.values():
            for filename,_ in records:
                if filename.endswith('.py'):(module/filename).write_text('# fixture source\n')
        server.PROJECT=project;server.MODULE_SYSTEM=module;server.SETTINGS=project/'settings.ini'
        errors=[];results=[]
        with sync_playwright() as p:
            import shutil
            browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,headless=True,args=['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            try:
                for width,height in [(1200,800),(900,620),(1600,1000)]:
                    page=browser.new_page(viewport={'width':width,'height':height});page.on('pageerror',lambda e:errors.append(str(e)))
                    # In-memory fixtures avoid browser policies that disallow loopback HTTP.
                    fixtures={'/api/items':{'rows':ITEMS},'/api/troops':{'rows':TROOPS},'/api/upgrades':{'rows':UPGRADES},'/api/modules':{'modules':[]},'/api/warband-font':{'available':False},'/api/dashboard':{'paths':{},'problems':[]},'/api/settings':{'rows':server.settings_rows()},'/api/datamap':server.data_map_rows()}
                    model={**MODEL,'texture':'data:image/png;base64,'+base64.b64encode(TEXTURE).decode()}
                    stub='const replaceState=history.replaceState.bind(history);history.replaceState=(state,unused)=>replaceState(state,unused);window.fetch=async function(input){const path=String(input);const fixtures='+json.dumps(fixtures)+';if(path.startsWith("/api/item-preview?")){return new Response(JSON.stringify(path.includes("broken")?{error:"Missing diffuse texture fixture"}:'+json.dumps(model)+'),{status:path.includes("broken")?422:200});}if(path.startsWith("/api/item-icon?")){if(path.includes("broken"))return new Response(JSON.stringify({error:"Missing diffuse texture fixture"}),{status:422});const bytes=Uint8Array.from(atob("'+base64.b64encode(ICON).decode()+'"),c=>c.charCodeAt(0));return new Response(bytes,{headers:{"Content-Type":"image/png"}});}return new Response(JSON.stringify(fixtures[path]||{}));};'
                    html=(ROOT/'games/warband/editor.html').read_text()
                    # Synthetic set_content pages need a hierarchical base for shared optional asset URLs.
                    html=html.replace('<head>','<head><base href="http://127.0.0.1:9/">',1)
                    html=html.replace('<link rel="stylesheet" href="/shared/framework.css">','<style>'+(ROOT/'ui/framework.css').read_text()+'</style>')
                    html=html.replace('<script src="/shared/framework.js"></script>','<script>'+stub+'</script><script>'+(ROOT/'ui/framework.js').read_text()+'</script>')
                    html=html.replace('<script src="/warband/troop_trees.js"></script>','<script>'+(ROOT/'games/warband/troop_trees.js').read_text()+'</script>')
                    page.set_content(html,wait_until='domcontentloaded');page.wait_for_function('!state.booting')
                    page.wait_for_function('document.querySelector(".warband-item-thumbnail img")?.naturalWidth>0')
                    assert page.locator('.warband-item-thumbnail canvas').count()==0
                    assert page.locator('.warband-preview-stage canvas').count()==0
                    assert page.locator('.lex-model-preview-drawer').is_hidden()
                    assert not page.evaluate('window.__warbandPreview?.length')
                    page.get_by_role('button',name='Open model preview',exact=True).click()
                    page.wait_for_function('window.__warbandPreview?.length===1 || document.querySelector(".warband-preview-message")?.textContent.includes("cannot start the WebGL")')
                    assert page.locator('.warband-preview-stage canvas').count()==1
                    webgl=page.evaluate('window.__warbandPreview?.length===1')
                    if os.environ.get('WARBAND_REQUIRE_WEBGL')=='1':assert webgl,'WebGL fixture rendering required by CI'
                    if webgl:
                        page.get_by_role('button',name='Close model preview',exact=True).click()
                        assert page.locator('.lex-model-preview-drawer').is_hidden()
                        assert not page.evaluate('window.__warbandPreview?.length')
                        page.get_by_role('button',name='Open model preview',exact=True).click()
                        page.wait_for_function('window.__warbandPreview?.length===1')
                    else:
                        assert page.locator('.warband-preview-message').is_visible()
                    page.screenshot(path=str(ARTIFACTS/f'items-{width}.png'),full_page=True)
                    page.evaluate('navigate("datamap")');page.wait_for_timeout(600)
                    assert page.locator('.lex-paged-list-detail').count()==1
                    page.get_by_role('combobox',name='Filter files by coverage',exact=True).select_option('source')
                    page.wait_for_timeout(400)
                    assert 'Source only' in page.locator('#main').inner_text()
                    assert 'Structured editable' not in page.locator('.warband-record-list').inner_text()
                    metrics=page.evaluate('''() => {
                      const list=document.querySelector('.warband-record-list'), box=list.getBoundingClientRect();
                      const rows=[...list.querySelectorAll('.lex-column-list-row')].map(r=>r.getBoundingClientRect());
                      return {viewport:innerHeight,bodyHeight:document.body.scrollHeight,listHeight:list.clientHeight,listScroll:list.scrollHeight,last:rows.at(-1)?.bottom,boxBottom:box.bottom,rowCount:rows.length};
                    }''')
                    page.screenshot(path=str(ARTIFACTS/f'datamap-{width}.png'),full_page=True)
                    if metrics['bodyHeight']>height+2:
                        print(page.evaluate("() => [...document.querySelectorAll('body,#main,#toolbar,.lex-paged-list-detail,.lex-data-map-detail,.lex-pager,.lex-panel-layout')].map(e=>({tag:e.tagName,cls:e.className,id:e.id,height:e.getBoundingClientRect().height,top:e.getBoundingClientRect().top,bottom:e.getBoundingClientRect().bottom,scroll:e.scrollHeight,css:({padding:getComputedStyle(e).padding,overflow:getComputedStyle(e).overflow,display:getComputedStyle(e).display})}))"))
                    assert metrics['bodyHeight']<=height+2,metrics
                    assert metrics['listScroll']<=metrics['listHeight']+2,metrics
                    assert metrics['last']<=metrics['boxBottom']+1,metrics
                    page.screenshot(path=str(ARTIFACTS/f'datamap-{width}.png'),full_page=True)
                    page.evaluate('navigate("upgrades")');page.get_by_role('combobox',name='Troop tree faction',exact=True).select_option('fac_north')
                    # Select the recruit component rather than the independent militia tree.
                    page.select_option('select[aria-label="Troop tree"]',label='Recruit')
                    page.locator('button[data-troop="knight"]').click()
                    assert 'Knight' in page.locator('.warband-tree-detail').inner_text()
                    assert 'knight' in page.locator('.warband-tree-detail').inner_text()
                    assert page.evaluate("() => {const title=document.querySelector('.warband-tree-detail h2').getBoundingClientRect();const body=document.querySelector('.warband-tree-detail .lex-detail-panel-body').getBoundingClientRect();return title.bottom<=body.top+1;}")
                    coords=page.evaluate('''() => Object.fromEntries([...document.querySelectorAll('[data-troop]')].map(n=>[n.dataset.troop,n.getBoundingClientRect().y]))''')
                    assert coords['recruit']>coords['footman']>coords['knight'],coords
                    page.screenshot(path=str(ARTIFACTS/f'trees-{width}.png'),full_page=True)
                    page.get_by_role('combobox',name='Troop tree faction',exact=True).select_option('fac_south')
                    assert page.locator('[data-troop="horseman"]').count()==1
                    assert page.locator('[data-troop="recruit"]').count()==0
                    # Missing dependencies never enable the preview action.
                    page.evaluate('state.filters.items="Missing texture fixture";navigate("items")')
                    page.get_by_role('button',name='Open model preview',exact=True).click()
                    page.wait_for_function('document.querySelector(".warband-preview-message")?.textContent.includes("Missing diffuse")')
                    assert page.locator('.lex-model-preview-drawer').is_visible()
                    assert page.evaluate('!window.__warbandPreview')
                    results.append({'width':width,'height':height,'dataMap':metrics,'webglAvailable':webgl,'status':'passed'})
                    page.close()
            finally:browser.close()
        (ARTIFACTS/'results.json').write_text(json.dumps({'fixtureOnly':True,'results':results,'errors':errors},indent=2))
        assert not errors,errors
        print(json.dumps(results,indent=2))

if __name__=='__main__':main()
