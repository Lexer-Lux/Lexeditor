"""Rendered fixture checks. No installed game assets or personal mod data used."""
from __future__ import annotations
import base64
import io
import os
import json
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_ui import inline_modules
import sys
import tempfile

from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from plugins.warband import server

ARTIFACTS=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'out'/'warband-browser'
ARTIFACTS.mkdir(parents=True,exist_ok=True)

def png(color):
    out=io.BytesIO();Image.new('RGBA',(32,32),color).save(out,'PNG');return out.getvalue()
TEXTURE=png((200,150,70,255));ICON=png((150,110,60,255))
positions=[[-.3,-.15,-1],[.3,-.15,-1],[.3,-.15,1],[-.3,-.15,1],[-.3,.15,-1],[.3,.15,-1],[.3,.15,1],[-.3,.15,1]]
triangles=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[3,2,6],[3,6,7],[1,5,6],[1,6,2],[0,3,7],[0,7,4]]
MODEL={'cacheKey':'a'*64,'mesh':'fixture_sword','material':'fixture_steel','resource':'fixture.brf','texture':'/fixture-texture.png','summary':{'vertices':8,'triangles':12},'geometry':{'positions':positions,'normals':[[0,-1,0]]*8,'texCoords':[[0,0],[1,0],[1,1],[0,1]]*2,'triangles':triangles,'bounds':{'min':[-.3,-.15,-1],'max':[.3,.15,1]}}}
TROOPS=[{'recordIndex':i,'id':id,'name':name,'faction':faction,'level':level,'flags':'tf_guarantee_armor','line':i+1,'status':'active','plural':name+'s'} for i,(id,name,faction,level) in enumerate([
    ('recruit','Recruit','fac_north',1),('footman','Footman','fac_north',10),('archer','Archer','fac_north',10),('knight','Knight','fac_north',20),('guard','Guard','fac_north',20),('militia','Militia','fac_north',2),('elite_militia','Elite militia','fac_north',12),('horseman','Horseman','fac_south',10),('rider','Rider','fac_south',20)])]
for row in TROOPS:
    row.update(fields={'name':row['name'],'plural':row['plural'],'faction':row['faction'],'attributes':'0','flags':'0','inventory':'[]'},stats={},flagValue=None)
UPGRADES=[{'fromId':a,'toId':b} for a,b in [('recruit','footman'),('recruit','archer'),('footman','knight'),('footman','guard'),('militia','elite_militia'),('horseman','rider')]]
def fixture_item(i,mesh='fixture_sword'):
    item_id=f'fixture_{i:03}';name=f'Fixture sword {i:03}'
    fields={'id':item_id,'name':name,'meshes':f'[(\"{mesh}\", 0)]','flags':'itp_type_one_handed_wpn|itp_merchandise','capabilities':'itc_longsword','value':'120','stats':'weight(1.5)|spd_rtng(97)|weapon_length(90)','modifierBits':'imodbits_sword'}
    return {'recordIndex':i,'id':item_id,'name':name,'type':'one_handed_wpn','value':'120','weight':'1.5','meshes':[mesh],'inventoryMesh':mesh,'line':i+1,'fields':fields,'fieldOrder':list(fields)}
ITEMS=[fixture_item(i) for i in range(65)]
broken=fixture_item(100,'broken');broken.update({'id':'broken','name':'Missing texture fixture','type':'goods'});broken['fields'].update({'id':'broken','name':'Missing texture fixture','flags':'itp_type_goods','capabilities':'0'});ITEMS.append(broken)

RECORD_SOURCES={
    'module_skills.py':'skills=[("power_strike","Power Strike",sf_base_att_str,10,"Hit harder."),("trainer","Trainer",sf_base_att_int,5,"Train allies.")]\n',
    'module_quests.py':'quests=[("hunt","Hunt bandits",qf_random_quest,"Find and defeat the bandits.")]\n',
    'module_strings.py':'strings=[]\n',
    'module_info_pages.py':'info_pages=[("rules","Rules","Fixture manual text.")]\n',
    'module_music.py':'tracks=[("travel","travel.ogg",mtf_sit_travel,mtf_sit_travel)]\n',
    'module_sounds.py':'sounds=[("click",0,["click.ogg"])]\n',
    'module_meshes.py':'meshes=[("panel",render_order_plus_1,"panel_mesh",0,0,0,0,0,0,1,1,1)]\n',
    'module_factions.py':'factions=[("kingdom","Kingdom",0,0.9,[("outlaws",-0.5)],[],0xFF00FF)]\n',
    'module_postfx.py':'postfx_params=[("default",0,3,[1,2,3,4],[5,6,7,8],[9,10,11,12])]\n',
    'module_party_templates.py':'party_templates=[("bandits","Bandits",icon_gray_knight,0,fac_outlaws,bandit_personality,[(trp_bandit,3,7)])]\n',
    'module_parties.py':'parties=[("town","Town",pf_is_static,0,pt_none,fac_neutral,0,ai_bhvr_hold,0,(1.5,2.5),[],90)]\n',
    'module_map_icons.py':'map_icons=[("player",0,"player",0.15,snd_footstep,0.1,0.2,0)]\n',
    'module_scenes.py':'scenes=[("arena",sf_generate,"none","none",(-10,-20),(10,20),-1.0,"0x0",[],[],"outer_terrain_plain")]\n',
    'module_scene_props.py':'scene_props=[("door",spr_use_time(1),"door_mesh","bo_door",[(ti_on_scene_prop_use,[])])]\n',
    'module_mission_templates.py':'mission_templates=[("battle",mtf_battle_mode,-1,"Battle",[],[])]\n',
    'module_game_menus.py':'game_menus=[("camp",0,"Camp","none",[],[("leave",[],"Leave",[])])]\n',
    'module_presentations.py':'presentations=[("sheet",0,mesh_load_window,[])]\n',
    'module_tableau_materials.py':'tableaus=[("shield",0,"sample",512,256,-128,0,128,256,[])]\n',
    'module_skins.py':'skins=[("man",0,"body","calf","hand","head",face_keys,["hair"],[],["hair_tex"],[],[],[],"skel_human",1.0)]\n',
    'module_particle_systems.py':'particle_systems=[("dust",psf_billboard_3d,"dust",5,2.0,10,0.05,10.0,39.0,(0.2,0.5),(1,0),(0,1),(1,1),(0,0.9),(1,0.9),(0,0.78),(1,0.78),(0,2),(1,3.5),(0.2,0.3,0.2),(0,0,3.9),0.5,130,0.5)]\n',
}
# Enough real source records to prove the shared fitted pager, not a one-page demo.
RECORD_SOURCES['module_skills.py']='skills=[\n'+',\n'.join(
    ('("power_strike","Power Strike",sf_base_att_str,10,"Hit harder.")' if i==0 else
     f'("skill_{i:03}","Skill {i:03}",sf_base_att_int,10,"Fixture skill {i:03}.")')
    for i in range(45)
)+'\n]\n'


def main():
    with tempfile.TemporaryDirectory() as temp:
        project=Path(temp);module=project/'ModuleSystem';module.mkdir();(project/'Module').mkdir();(project/'Module'/'module.ini').write_text('')
        (project/'settings.ini').write_text('[Test]\nenabled=1\n')
        for records in server.DATA_CATALOG.values():
            for filename,_ in records:
                if filename.endswith('.py'):(module/filename).write_text(RECORD_SOURCES.get(filename,'# fixture source\n'))
        server.PROJECT=project;server.MODULE_SYSTEM=module;server.SETTINGS=project/'settings.ini'
        errors=[];results=[]
        with sync_playwright() as p:
            import shutil
            browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,headless=True,args=['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            try:
                for width,height in [(1200,800),(900,620),(1600,1000)]:
                    page=browser.new_page(viewport={'width':width,'height':height});page.on('pageerror',lambda e:errors.append(str(e)))
                    # Route one synthetic HTTP origin entirely in memory. set_content() leaves
                    # Chromium on an opaque/storage-refused document, while the shared shell
                    # legitimately uses sessionStorage during boot; that made the fixture die
                    # before Warband's scripts could render anything.
                    fixtures={'/api/items':{'rows':ITEMS,'sha256':'fixture-items'},'/api/troops':{'rows':TROOPS,'items':[],'factions':[],'sha256':'fixture-troops','types':{},'flags':{}},'/api/upgrades':{'rows':UPGRADES},'/api/modules':{'modules':[]},'/api/warband-font':{'available':False},'/api/dashboard':{'paths':{},'problems':[]},'/api/settings':{'rows':server.settings_rows()},'/api/datamap':server.data_map_rows()}
                    record_fixtures={key:server.dataset_data(module,key) for key in server.MODULE_RECORD_SCHEMAS}
                    model={**MODEL,'texture':'data:image/png;base64,'+base64.b64encode(TEXTURE).decode()}
                    stub='const replaceState=history.replaceState.bind(history);history.replaceState=(state,unused)=>replaceState(state,unused);const recordFixtures='+json.dumps(record_fixtures)+';let failSound=true;window.fetch=async function(input,options={}){const path=String(input);const fixtures='+json.dumps(fixtures)+';if(path.startsWith("/api/module-records?")){const key=new URL(path,"http://fixture").searchParams.get("dataset");if(key==="sounds"&&failSound){failSound=false;return new Response(JSON.stringify({error:"Synthetic sound parse failure"}),{status:400});}await new Promise(r=>setTimeout(r,80));return new Response(JSON.stringify(recordFixtures[key]||{error:"Unknown fixture dataset"}));}if(path==="/api/module-records/save"){const body=JSON.parse(options.body||"{}"),data=recordFixtures[body.dataset];for(const edit of body.edits||[]){const row=data.rows.find(r=>r.recordIndex===edit.recordIndex);Object.assign(row.fields,edit.fields||{});if(Object.hasOwn(edit.fields||{},"name"))row.name=edit.fields.name;}data.sha256="saved-"+Date.now();return new Response(JSON.stringify({saved:(body.edits||[]).length,sha256:data.sha256}));}if(path==="/api/build/start")return new Response(JSON.stringify({started:true}));if(path.startsWith("/api/build/status"))return new Response(JSON.stringify({cursor:1,lines:["Build verified: fixture\\n"],running:false,returnCode:0}));if(path.startsWith("/api/item-preview?")){return new Response(JSON.stringify(path.includes("broken")?{error:"Missing diffuse texture fixture"}:'+json.dumps(model)+'),{status:path.includes("broken")?422:200});}if(path.startsWith("/api/item-icon?")){if(path.includes("broken"))return new Response(JSON.stringify({error:"Missing diffuse texture fixture"}),{status:422});const bytes=Uint8Array.from(atob("'+base64.b64encode(ICON).decode()+'"),c=>c.charCodeAt(0));return new Response(bytes,{headers:{"Content-Type":"image/png"}});}return new Response(JSON.stringify(fixtures[path]||{}));};'
                    html=(ROOT/'plugins/warband/editor.html').read_text(encoding="utf-8")
                    # Synthetic set_content pages need a hierarchical base for shared optional asset URLs.
                    html=html.replace('<head>','<head><base href="http://warband-fixture.test/">',1)
                    html=html.replace('<link rel="stylesheet" href="/shared/framework.css">','<style>'+(ROOT/'ui/framework.css').read_text(encoding="utf-8")+'</style>')
                    html=html.replace('<script src="/shared/framework.js"></script>','<script>'+stub+'</script><script>'+(ROOT/'ui/framework.js').read_text(encoding="utf-8")+'</script>')
                    html=inline_modules('warband',html)
                    def route_fixture(route):
                        if route.request.resource_type=='document':
                            route.fulfill(status=200,body=html,content_type='text/html')
                        else:
                            route.abort()
                    page.route('http://warband-fixture.test/**',route_fixture)
                    page.goto('http://warband-fixture.test/',wait_until='domcontentloaded')
                    assert page.evaluate('sessionStorage.setItem("warband-fixture","1");sessionStorage.getItem("warband-fixture")')=='1'
                    try:
                        page.locator('.warband-item-detail').wait_for(state='visible',timeout=10000)
                    except PlaywrightTimeoutError as error:
                        raise AssertionError({'pageErrors':errors,'main':page.locator('#main').inner_text(),'url':page.url}) from error
                    page.wait_for_function('document.querySelector(".warband-item-thumbnail img")?.naturalWidth>0')
                    assert page.locator('.warband-item-detail [data-lex-property="id"] input').count()==1
                    assert page.locator('.warband-item-detail [data-lex-property="id"] input').is_disabled()
                    assert page.locator('.warband-item-detail [data-lex-property="name"] input').count()==1
                    assert page.locator('.warband-item-detail [data-lex-property="flags"] textarea').count()==1
                    assert page.locator('.warband-item-detail [data-lex-property="stats"] textarea').count()==1
                    # The heading icon is the shared 3D viewer control. It used
                    # to be absent, so the renderer was there and unreachable.
                    assert page.locator('.lex-model-preview-drawer').count()==1
                    icon=page.locator('.warband-item-detail .lex-detail-panel-icon')
                    assert icon.count()==1
                    icon.click();page.wait_for_timeout(250)
                    assert page.locator('.warband-item-detail.lex-model-preview-open').count()==1
                    assert page.locator('.lex-model-preview-drawer .warband-preview-stage').count()==1
                    page.locator('.lex-model-preview-drawer .warband-preview-stage canvas').wait_for(state='visible')
                    assert page.evaluate('window.__warbandPreview?.length===1')
                    page.locator('.warband-item-detail .lex-model-preview-close').click()
                    page.wait_for_timeout(250)
                    assert page.locator('.warband-item-detail.lex-model-preview-open').count()==0
                    name_field=page.locator('.warband-item-detail [data-lex-property="name"] input')
                    name_field.fill('Edited fixture name')
                    assert page.evaluate('itemDirtyCount()')==1
                    assert page.evaluate('Object.values(state.itemEdits)[0].fields.name')=='Edited fixture name'
                    name_field.fill('Fixture sword 000')
                    assert page.evaluate('itemDirtyCount()')==0
                    page.screenshot(path=str(ARTIFACTS/f'items-{width}.png'),full_page=True)
                    page.evaluate('navigate("datamap")');page.wait_for_timeout(600)
                    assert page.evaluate('window.__warbandPreview===undefined')
                    assert page.locator('.lex-paged-list-detail').count()==1
                    page.get_by_role('combobox',name='Filter files by integration',exact=True).select_option('not-integrated')
                    page.wait_for_timeout(400)
                    assert 'module.ini' in page.locator('#main').inner_text()
                    assert 'Resource/*.brf' not in page.locator('#main').inner_text()
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
                    coverage_filter=page.get_by_role('combobox',name='Filter files by integration',exact=True)
                    coverage_filter.select_option('')
                    page.wait_for_function("document.querySelector('[aria-label=\"Filter files by integration\"]')?.value===''")
                    # Resetting the filter causes the fitted Data Map to rebuild.
                    # Let that render settle before typing into the replacement
                    # search input, or a late fit callback can discard the query.
                    page.wait_for_timeout(300)
                    search_box=page.get_by_role('searchbox',name='Search the data map',exact=True)
                    search_box.fill('module_skills.py')
                    page.wait_for_function("document.querySelector('[aria-label=\"Search the data map\"]')?.value==='module_skills.py'")
                    skill_row=page.locator('.lex-column-list-row').filter(has_text='module_skills.py')
                    skill_row.wait_for(state='visible')
                    skill_row.click()
                    page.get_by_role('button',name='Open misc',exact=True).click()
                    page.locator('.warband-module-detail').wait_for(state='visible')
                    assert page.locator('.warband-module-detail [data-lex-property="id"] input').is_disabled()
                    max_level=page.locator('.warband-module-detail [data-lex-property="maxLevel"] input')
                    assert max_level.get_attribute('type')=='number'
                    assert page.locator('.warband-module-detail [data-lex-property="description"] textarea').count()==1
                    assert page.locator('.warband-module-detail [data-lex-property="flags"] textarea').count()==1
                    assert page.get_by_role('button',name='Next page',exact=True).is_enabled()
                    page.get_by_role('button',name='Next page',exact=True).click()
                    assert page.locator('.lex-page-number').input_value()=='2'
                    page.get_by_role('button',name='Previous page',exact=True).click()
                    assert page.locator('.lex-page-number').input_value()=='1'
                    cell=page.locator('.warband-record-list .lex-column-list-row').first.locator('[data-column-key="maxLevel"]')
                    cell.dblclick();cell.locator('input').fill('12');cell.locator('input').press('Enter')
                    assert page.locator('.warband-module-detail [data-lex-property="maxLevel"] input').input_value()=='12'
                    page.get_by_role('button',name='Discard changes',exact=True).click()
                    assert page.locator('.warband-module-detail [data-lex-property="maxLevel"] input').input_value()=='10'
                    max_level=page.locator('.warband-module-detail [data-lex-property="maxLevel"] input');max_level.fill('11')
                    assert page.evaluate('moduleRecords.dirtyCount()')==1
                    page.locator('.lex-save-icon').click()
                    page.wait_for_function('document.body.classList.contains("lex-save-busy")')
                    page.wait_for_function('!document.body.classList.contains("lex-save-busy")')
                    assert page.locator('.lex-dialog').filter(has_text='Save failed').count()==0
                    page.get_by_role('button',name='Items',exact=True).click()
                    page.get_by_role('button',name='Misc.',exact=True).click()
                    page.locator('.warband-module-detail').wait_for(state='visible')
                    assert page.locator('.warband-module-detail [data-lex-property="maxLevel"] input').input_value()=='11'
                    page.screenshot(path=str(ARTIFACTS/f'module-data-{width}.png'),full_page=True)
                    page.get_by_role('combobox',name='Warband Module System dataset',exact=True).select_option('strings')
                    page.wait_for_function('document.querySelector(".warband-module-state")?.textContent.includes("No strings records")')
                    page.get_by_role('combobox',name='Warband Module System dataset',exact=True).select_option('sounds')
                    page.wait_for_function('document.querySelector(".warband-module-state")?.textContent.includes("Synthetic sound parse failure")')
                    page.get_by_role('button',name='Retry',exact=True).click()
                    page.locator('.warband-module-detail').wait_for(state='visible')
                    page.get_by_role('combobox',name='Warband Module System dataset',exact=True).select_option('particle-systems')
                    page.locator('.warband-module-detail').wait_for(state='visible')
                    assert page.locator('.warband-module-detail [data-lex-property="emitBox"] input[type="number"]').count()==3
                    assert page.locator('.warband-module-detail [data-lex-property="rotationSpeed"] input[type="number"]').count()==1
                    page.evaluate('navigate("upgrades")');page.get_by_role('combobox',name='Troop tree faction',exact=True).select_option('fac_north')
                    # Each tree is a subtab now. Select the recruit component
                    # rather than the independent militia tree.
                    page.get_by_role('tab',name='Recruit',exact=True).click()
                    page.locator('button[data-node="knight"]').click()
                    assert 'Knight' in page.locator('.warband-tree-detail').inner_text()
                    assert 'knight' in page.locator('.warband-tree-detail').inner_text()
                    assert page.evaluate("() => {const title=document.querySelector('.warband-tree-detail h2').getBoundingClientRect();const body=document.querySelector('.warband-tree-detail .lex-detail-panel-body').getBoundingClientRect();return title.bottom<=body.top+1;}")
                    coords=page.evaluate('''() => Object.fromEntries([...document.querySelectorAll('[data-node]')].map(n=>[n.dataset.node,n.getBoundingClientRect().y]))''')
                    assert coords['recruit']>coords['footman']>coords['knight'],coords
                    page.screenshot(path=str(ARTIFACTS/f'trees-{width}.png'),full_page=True)
                    page.get_by_role('combobox',name='Troop tree faction',exact=True).select_option('fac_south')
                    assert page.locator('[data-node="horseman"]').count()==1
                    assert page.locator('[data-node="recruit"]').count()==0
                    # A missing render dependency affects only the thumbnail; the actual item editor remains usable.
                    page.evaluate('state.filters.items="Missing texture fixture";navigate("items")')
                    page.wait_for_function('document.querySelector(".warband-item-thumbnail .lex-icon-slot-message")?.textContent.includes("Icon unavailable")')
                    assert page.locator('.warband-item-detail [data-lex-property="name"] input').is_enabled()
                    assert page.locator('.warband-item-detail [data-lex-property="stats"] textarea').is_enabled()
                    assert page.get_by_role('button',name='Open model preview',exact=True).count()==0
                    results.append({'width':width,'height':height,'dataMap':metrics,'status':'passed'})
                    page.close()
            finally:browser.close()
        (ARTIFACTS/'results.json').write_text(json.dumps({'fixtureOnly':True,'results':results,'errors':errors},indent=2))
        assert not errors,errors
        print(json.dumps(results,indent=2))

if __name__=='__main__':main()