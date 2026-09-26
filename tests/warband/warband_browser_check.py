"""Rendered fixture checks. No installed game assets or personal mod data used."""
from __future__ import annotations
# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import base64
import io
import os
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import inline_modules  # noqa: E402

from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from plugins.warband import server

ARTIFACTS=Path(sys.argv[1]) if len(sys.argv)>1 else DEV_CACHE /'warband-browser'
ARTIFACTS.mkdir(parents=True,exist_ok=True)

def png(color):
    out=io.BytesIO();Image.new('RGBA',(32,32),color).save(out,'PNG');return out.getvalue()
TEXTURE=png((200,150,70,255));ICON=png((150,110,60,255))
positions=[[-.3,-.15,-1],[.3,-.15,-1],[.3,-.15,1],[-.3,-.15,1],[-.3,.15,-1],[.3,.15,-1],[.3,.15,1],[-.3,.15,1]]
triangles=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[3,2,6],[3,6,7],[1,5,6],[1,6,2],[0,3,7],[0,7,4]]
MODEL={'cacheKey':'a'*64,'mesh':'fixture_sword','material':'fixture_steel','resource':'fixture.brf','texture':'/fixture-texture.png','summary':{'vertices':8,'triangles':12},'geometry':{'positions':positions,'normals':[[0,-1,0]]*8,'texCoords':[[0,0],[1,0],[1,1],[0,1]]*2,'triangles':triangles,'bounds':{'min':[-.3,-.15,-1],'max':[.3,.15,1]}}}
# A stand-in for the installed Warband atlas: the same shape the plugin reads
# out of Data/font_data.xml, so the checks can prove the game font is used for
# headings without an installed game.
FONT={'available':True,'width':100,'height':100,'fontSize':70,'lineSpacing':100,
      'characters':{str(ord(character)):{'u':10,'v':10,'w':50,'h':50,'preshift':0,'yadjust':48,'postshift':40}
                    for character in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,:;_-()[]/'\""}}
TROOPS=[{'recordIndex':i,'id':id,'name':name,'faction':faction,'level':level,'flags':'tf_guarantee_armor','line':i+1,'status':'active','plural':name+'s'} for i,(id,name,faction,level) in enumerate([
    ('recruit','Recruit','fac_north',1),('footman','Footman','fac_north',10),('archer','Archer','fac_north',10),('knight','Knight','fac_north',20),('guard','Guard','fac_north',20),('militia','Militia','fac_north',2),('elite_militia','Elite militia','fac_north',12),('horseman','Horseman','fac_south',10),('rider','Rider','fac_south',20)])]
for row in TROOPS:
    row.update(fields={'name':row['name'],'plural':row['plural'],'faction':row['faction'],'attributes':'0','flags':'0','inventory':'[]'},stats={},flagValue=None)
# A troop that carries equipment is the case where its heading can show a
# preview: the equipment is what resolves to meshes.
equipped=[row for row in TROOPS if row['id']=='knight'][0]
equipped['items']=['itm_fixture_000']
equipped['fields']['inventory']='[itm_fixture_000]'
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
# A Module System ships one header_<area>.py beside each module_*.py, and that
# is where the named flags, item types and modifier bits come from. The fixture
# carries them so the checks exercise the same finite sets a real project has.
HEADER_SOURCES={
    'header_items.py':('itp_type_horse = 0\n'
                       'itp_type_one_handed_wpn = 1\n'
                       'itp_type_shield = 6\n'
                       'itp_type_goods = 10\n'
                       'itp_merchandise = 0x00000002\n'
                       'itp_civilian = 0x00000010\n'
                       'itp_unique = 0x00000020\n'
                       'imodbits_sword_low = 0x00000001\n'
                       'imodbits_sword_med = 0x00000002\n'
                       'imodbits_sword = imodbits_sword_low|imodbits_sword_med\n'
                       'def weight(x): return x\n'
                       'def spd_rtng(x): return x\n'
                       'def weapon_length(x): return x\n'),
    'header_meshes.py':'render_order_plus_1 = 0x00000010\n',
    'header_skills.py':'sf_base_att_str = 0x00000100\nsf_base_att_int = 0x00000200\n',
    'header_quests.py':'qf_random_quest = 0x00000001\n',
    'header_music.py':'mtf_sit_travel = 0x00000001\nmtf_sit_town = 0x00000002\n',
    'header_sounds.py':'sf_priority_4 = 0x00000004\nsf_looping = 0x00000020\n',
    'header_particle_systems.py':'psf_billboard_3d = 0x00000001\n',
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
        for filename,text in HEADER_SOURCES.items():
            (module/filename).write_text(text)
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
                    fixtures={'/api/items':{'rows':ITEMS,'sha256':'fixture-items','choices':server.item_choices(ITEMS)},'/api/troops':{'rows':TROOPS,'items':[],'factions':[],'sha256':'fixture-troops','types':{},'flags':{}},'/api/upgrades':{'rows':UPGRADES},'/api/modules':{'modules':[]},'/api/warband-font':FONT,'/api/dashboard':{'paths':{},'problems':[]},'/api/settings':{'rows':server.settings_rows()},'/api/datamap':server.data_map_rows()}
                    record_fixtures={key:server.dataset_data(module,key) for key in server.MODULE_RECORD_SCHEMAS}
                    model={**MODEL,'texture':'data:image/png;base64,'+base64.b64encode(TEXTURE).decode()}
                    stub='const replaceState=history.replaceState.bind(history);history.replaceState=(state,unused)=>replaceState(state,unused);const recordFixtures='+json.dumps(record_fixtures)+';let failSound=true;const fontOn=location.search.includes("font=1");const fontOnFixture='+json.dumps(FONT)+';const fontOffFixture={"available":false};window.fetch=async function(input,options={}){const path=String(input);const fixtures='+json.dumps(fixtures)+';if(path==="/api/warband-font")return new Response(JSON.stringify(fontOn?fontOnFixture:fontOffFixture));if(path.startsWith("/api/module-records?")){const key=new URL(path,"http://fixture").searchParams.get("dataset");if(key==="sounds"&&failSound){failSound=false;return new Response(JSON.stringify({error:"Synthetic sound parse failure"}),{status:400});}await new Promise(r=>setTimeout(r,80));return new Response(JSON.stringify(recordFixtures[key]||{error:"Unknown fixture dataset"}));}if(path==="/api/module-records/save"){const body=JSON.parse(options.body||"{}"),data=recordFixtures[body.dataset];for(const edit of body.edits||[]){const row=data.rows.find(r=>r.recordIndex===edit.recordIndex);Object.assign(row.fields,edit.fields||{});if(Object.hasOwn(edit.fields||{},"name"))row.name=edit.fields.name;}data.sha256="saved-"+Date.now();return new Response(JSON.stringify({saved:(body.edits||[]).length,sha256:data.sha256}));}if(path==="/api/build/start")return new Response(JSON.stringify({started:true}));if(path.startsWith("/api/build/status"))return new Response(JSON.stringify({cursor:1,lines:["Build verified: fixture\\n"],running:false,returnCode:0}));if(path.startsWith("/api/item-preview?")){return new Response(JSON.stringify(path.includes("broken")?{error:"Missing diffuse texture fixture"}:'+json.dumps(model)+'),{status:path.includes("broken")?422:200});}if(path.startsWith("/api/item-icon?")){if(path.includes("broken"))return new Response(JSON.stringify({error:"Missing diffuse texture fixture"}),{status:422});const bytes=Uint8Array.from(atob("'+base64.b64encode(ICON).decode()+'"),c=>c.charCodeAt(0));return new Response(bytes,{headers:{"Content-Type":"image/png"}});}return new Response(JSON.stringify(fixtures[path]||{}));};'
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
                    # The restore glyph's back square is filled with the button's
                    # own surface. Filling it with the panel colour left a bright
                    # patch on Warband's dark shell button and read as one square
                    # "filled in" for no reason.
                    assert page.evaluate('''(() => {
                      document.body.dataset.windowMaximized = "true";
                      const button = document.querySelector(
                        '[data-window-action="maximize"]');
                      const icon = button.querySelector('.lex-window-icon');
                      return getComputedStyle(icon, '::after').backgroundColor
                        === getComputedStyle(button).backgroundColor;
                    })()''') is True
                    assert page.locator('.warband-item-detail [data-lex-property="id"] input').count()==1
                    assert page.locator('.warband-item-detail [data-lex-property="id"] input').is_disabled()
                    assert page.locator('.warband-item-detail [data-lex-property="name"] input').count()==1
                    # The type, the flags, the modifier bits, the stats and the
                    # meshes each offer the finite set the project's own
                    # header_items.py and module_items.py name, instead of a
                    # text box a typo can brick the game in.
                    item_type=page.locator('.warband-item-detail [data-lex-property="type"] select')
                    assert item_type.count()==1
                    assert item_type.input_value()=='one_handed_wpn'
                    assert sorted(value for value in item_type.locator('option').all_inner_texts()
                                  if value in {'horse','one_handed_wpn','shield','goods'})==['goods','horse','one_handed_wpn','shield']
                    assert page.locator('.warband-item-detail [data-lex-property="itp_merchandise"] input[type="checkbox"]').is_checked()
                    assert not page.locator('.warband-item-detail [data-lex-property="itp_civilian"] input[type="checkbox"]').is_checked()
                    assert page.locator('.warband-item-detail [data-lex-property="imodbits_sword_med"] input[type="checkbox"]').count()==1
                    assert page.locator('.warband-item-detail [data-lex-property="stat-spd_rtng"] input[type="number"]').count()==1
                    mesh_select=page.locator('.warband-item-detail [data-lex-property="inventoryMesh"] select')
                    assert mesh_select.count()==1
                    assert mesh_select.input_value()=='fixture_sword'
                    assert page.locator('.warband-item-detail [data-lex-property="mesh-1"] select').count()==1
                    # A flag box writes the project's own constant name back.
                    page.locator('.warband-item-detail [data-lex-property="itp_civilian"] input[type="checkbox"]').check()
                    assert page.evaluate('Object.values(state.itemEdits)[0].fields.flags')=='itp_type_one_handed_wpn|itp_merchandise|itp_civilian'
                    page.locator('.warband-item-detail [data-lex-property="itp_civilian"] input[type="checkbox"]').uncheck()
                    assert page.evaluate('itemDirtyCount()')==0
                    # Every one of those sets is a named section of the panel,
                    # and each is reachable by scrolling the panel body.
                    titles=page.evaluate('''() => [...document.querySelectorAll('.warband-item-detail .lex-detail-section-title')]
                        .map(node=>node.textContent.replace(/\\s|\\?/g,''))''')
                    assert titles[:5]==['Item','Stats','Flags','Modifierbits','Meshes'],titles
                    # What is left is only what this editor does not interpret.
                    assert titles[5:]==['ModuleSystemfields'],titles
                    page.evaluate('''() => {const body=document.querySelector('.warband-item-detail .lex-detail-panel-body');
                        body.scrollTop=body.scrollHeight;}''')
                    page.wait_for_timeout(250)
                    page.screenshot(path=str(ARTIFACTS/f'items-flags-{width}.png'),full_page=True)
                    page.evaluate('''() => {const body=document.querySelector('.warband-item-detail .lex-detail-panel-body');
                        body.scrollTop=0;}''')
                    page.wait_for_timeout(150)
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
                    # The open drawer covers the editing surface, so the field
                    # help pips on that surface must be underneath it. They
                    # used to stay on top (z-index 5 over the drawer's 3) and a
                    # row of "?" marks floated over the model.
                    assert page.evaluate('''(() => {
                      const drawer = document.querySelector(
                        '.warband-item-detail .lex-model-preview-drawer');
                      const r = drawer.getBoundingClientRect();
                      return [...document.querySelectorAll(
                        '.warband-item-detail .lex-field-help')].filter(pip => {
                        const b = pip.getBoundingClientRect();
                        const overlaps = !(b.right < r.left || b.left > r.right
                          || b.bottom < r.top || b.top > r.bottom);
                        if (!overlaps) return false;
                        const hit = document.elementFromPoint(
                          b.left + b.width / 2, b.top + b.height / 2);
                        return hit && hit.closest('.lex-field-help') === pip;
                      }).length;
                    })()''') == 0
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
                    # Skills is a page tab of its own now, so the Data Map
                    # names the page the record actually opens on.
                    page.get_by_role('button',name='Open skills',exact=True).click()
                    page.locator('.warband-module-detail').wait_for(state='visible')
                    assert page.locator('.warband-module-detail [data-lex-property="id"] input').is_disabled()
                    max_level=page.locator('.warband-module-detail [data-lex-property="maxLevel"] input')
                    assert max_level.get_attribute('type')=='number'
                    assert page.locator('.warband-module-detail [data-lex-property="description"] textarea').count()==1
                    # A flag field offers the names header_skills.py declares,
                    # as boxes, and writes them back as the same constants.
                    flag_box='.warband-module-detail [data-lex-property="sf_base_att_int"] input[type="checkbox"]'
                    assert page.locator('.warband-module-detail [data-lex-property="sf_base_att_str"] input[type="checkbox"]').is_checked()
                    page.locator(flag_box).check()
                    assert page.evaluate('moduleRecords.snapshot().edits.skills[0].fields.flags')=='sf_base_att_str|sf_base_att_int'
                    page.locator(flag_box).uncheck()
                    assert page.evaluate('moduleRecords.dirtyCount()')==0
                    assert page.get_by_role('button',name='Next page',exact=True).is_enabled()
                    page.get_by_role('button',name='Next page',exact=True).click()
                    assert page.locator('.lex-page-number').input_value()=='2'
                    page.get_by_role('button',name='Previous page',exact=True).click()
                    assert page.locator('.lex-page-number').input_value()=='1'
                    cell=page.locator('.warband-record-list .lex-column-list-row').first.locator('[data-column-key="maxLevel"]')
                    cell.dblclick();cell.locator('input').fill('12');cell.locator('input').press('Enter')
                    assert page.locator('.warband-module-detail [data-lex-property="maxLevel"] input').input_value()=='12'
                    # The shell's own Undo is the only revert in the editor; the
                    # view keeps no second Save or Discard beside it.
                    page.get_by_role('button',name='Undo',exact=True).click()
                    assert page.locator('.warband-module-detail [data-lex-property="maxLevel"] input').input_value()=='10'
                    max_level=page.locator('.warband-module-detail [data-lex-property="maxLevel"] input');max_level.fill('11')
                    assert page.evaluate('moduleRecords.dirtyCount()')==1
                    page.locator('.lex-save-icon').click()
                    page.wait_for_function('document.body.classList.contains("lex-save-busy")')
                    page.wait_for_function('!document.body.classList.contains("lex-save-busy")')
                    assert page.locator('.lex-dialog').filter(has_text='Save failed').count()==0
                    page.get_by_role('button',name='Items',exact=True).click()
                    page.get_by_role('button',name='Skills',exact=True).click()
                    page.locator('.warband-module-detail').wait_for(state='visible')
                    assert page.locator('.warband-module-detail [data-lex-property="maxLevel"] input').input_value()=='11'
                    page.screenshot(path=str(ARTIFACTS/f'module-data-{width}.png'),full_page=True)
                    # Misc. keeps its remaining areas behind a subtab bar.
                    page.get_by_role('button',name='Misc.',exact=True).click()
                    # The view keeps no Save, Discard or unsaved-field counter of
                    # its own: the shell's Save and History own that.
                    assert page.locator('#toolbar').inner_text().strip()==''
                    assert page.get_by_role('button',name='Discard changes',exact=True).count()==0
                    page.get_by_role('tab',name='Strings',exact=True).click()
                    page.wait_for_function('document.querySelector(".warband-module-state")?.textContent.includes("No strings records")')
                    page.get_by_role('button',name='Music',exact=True).click()
                    page.locator('.warband-module-detail').wait_for(state='visible')
                    heading=page.evaluate('''() => {
                      const panel=document.querySelector('.warband-module-detail');
                      const title=panel.querySelector('.lex-detail-panel-title');
                      const bitmap=title.querySelector('.lex-bitmap-text');
                      return {title:bitmap?bitmap.getAttribute('aria-label')
                                :title.textContent.replace('?','').trim(),
                              subtitles:[...panel.querySelectorAll('.lex-detail-panel-id,.lex-detail-panel-meta')].map(node=>node.textContent)};
                    }''')
                    # A record whose name is its own ID prints that ID once: not
                    # as a heading and a second subtitle, and not with coverage
                    # as a third line. Coverage and the source caveat are the
                    # panel's own help bubble.
                    assert heading['title']=='travel',heading
                    assert heading['subtitles']==[],heading
                    page.get_by_role('button',name='Sounds',exact=True).click()
                    page.wait_for_function('document.querySelector(".warband-module-state")?.textContent.includes("Synthetic sound parse failure")')
                    page.get_by_role('button',name='Retry',exact=True).click()
                    page.locator('.warband-module-detail').wait_for(state='visible')
                    # Every property in the right panel carries the shared pin,
                    # and pinning one adds that property to the table.
                    assert page.locator('.warband-module-detail .lex-column-pin').count()>=3
                    assert page.locator('.warband-record-list [data-column-key="samples"]').count()>=1
                    pin=page.locator('.warband-module-detail [data-lex-pin-column="samples"]')
                    pin.click()
                    page.wait_for_timeout(400)
                    assert page.locator('.warband-record-list [data-column-key="samples"]').count()==0
                    page.locator('.warband-module-detail [data-lex-pin-column="samples"]').click()
                    page.wait_for_timeout(400)
                    assert page.locator('.warband-record-list .lex-column-list-row [data-column-key="samples"]').count()==1
                    page.screenshot(path=str(ARTIFACTS/f'sounds-pin-{width}.png'),full_page=True)
                    page.get_by_role('button',name='Misc.',exact=True).click()
                    page.get_by_role('tab',name='Particle systems',exact=True).click()
                    page.locator('.warband-module-detail').wait_for(state='visible')
                    assert page.locator('.warband-module-detail [data-lex-property="emitBox"] input[type="number"]').count()==3
                    assert page.locator('.warband-module-detail [data-lex-property="rotationSpeed"] input[type="number"]').count()==1
                    page.evaluate('navigate("upgrades")');page.get_by_role('combobox',name='Troop tree faction',exact=True).select_option('fac_north')
                    # Each tree is a subtab now. Select the recruit component
                    # rather than the independent militia tree.
                    page.get_by_role('tab',name='Recruit',exact=True).click()
                    page.locator('button[data-node="knight"]').click()
                    # The heading is the game's own font, so its text is the
                    # glyph string's label; the record's own fields carry the
                    # values that the source holds.
                    troop_heading=page.evaluate('''() => {
                      const panel=document.querySelector('.warband-tree-detail');
                      const title=panel.querySelector('.lex-detail-panel-title'),bitmap=title.querySelector('.lex-bitmap-text');
                      return {title:bitmap?bitmap.getAttribute('aria-label'):title.textContent,
                              values:[...panel.querySelectorAll('input')].map(node=>node.value)};
                    }''')
                    assert troop_heading['title'].startswith('Knight'),troop_heading
                    assert 'Knight' in troop_heading['values'],troop_heading
                    assert 'knight' in page.locator('.warband-tree-detail').inner_text()
                    # A troop tree node's thumbnail is a preview, not a door:
                    # opening it keeps the reader in Troop Trees.
                    drawer='.warband-tree-detail .lex-model-preview-drawer'
                    assert page.locator('.warband-tree-detail .lex-detail-panel-icon').count()==1
                    page.locator('.warband-tree-detail .lex-detail-panel-icon').click()
                    page.wait_for_timeout(400)
                    assert page.locator('.warband-tree-detail.lex-model-preview-open').count()==1
                    assert page.locator(f'{drawer} .lex-figure-grid').count()==1
                    assert page.evaluate('state.tab')=='upgrades'
                    page.locator('.warband-tree-detail .lex-model-preview-close').click()
                    page.wait_for_timeout(300)
                    assert page.locator('.warband-tree-detail.lex-model-preview-open').count()==0
                    assert page.evaluate('state.tab')=='upgrades'
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
                    assert page.locator('.warband-item-detail [data-lex-property="stat-spd_rtng"] input[type="number"]').is_enabled()
                    assert page.get_by_role('button',name='Open model preview',exact=True).count()==0
                    # Panel headings come from the installed game's own font.
                    # The fixture carries a stand-in atlas for the glyph metrics
                    # Warband ships, so the headings can be read back by label.
                    if width==1200:
                        font_page=browser.new_page(viewport={'width':width,'height':height})
                        font_page.on('pageerror',lambda e:errors.append(str(e)))
                        font_page.route('http://warband-fixture.test/**',route_fixture)
                        font_page.goto('http://warband-fixture.test/?font=1',wait_until='domcontentloaded')
                        font_page.locator('.warband-item-detail').wait_for(state='visible')
                        font_page.wait_for_function('document.querySelector(".warband-item-detail .lex-detail-panel-title .lex-bitmap-text")')
                        headings=font_page.evaluate('''() => {
                          const label=node=>node?.querySelector('.lex-bitmap-text')?.getAttribute('aria-label')||null;
                          return {item:label(document.querySelector('.warband-item-detail .lex-detail-panel-title')),
                                  tab:document.querySelector('nav button.active')?.getAttribute('aria-label')};
                        }''')
                        assert headings['item']=='Fixture sword 000',headings
                        assert headings['tab']=='Items',headings
                        font_page.get_by_role('button',name='Music',exact=True).click()
                        font_page.locator('.warband-module-detail').wait_for(state='visible')
                        font_page.wait_for_function('document.querySelector(".warband-module-detail .lex-detail-panel-title .lex-bitmap-text")')
                        assert font_page.evaluate('''() => document.querySelector('.warband-module-detail .lex-detail-panel-title .lex-bitmap-text').getAttribute('aria-label')''')=='travel'
                        font_page.evaluate('navigate("upgrades")')
                        font_page.get_by_role('combobox',name='Troop tree faction',exact=True).select_option('fac_north')
                        font_page.get_by_role('tab',name='Recruit',exact=True).click()
                        font_page.locator('button[data-node="knight"]').click()
                        font_page.wait_for_function('document.querySelector(".warband-tree-detail .lex-detail-panel-title .lex-bitmap-text")')
                        assert font_page.evaluate('''() => document.querySelector('.warband-tree-detail .lex-detail-panel-title .lex-bitmap-text').getAttribute('aria-label')''')=='Knight'
                        font_page.screenshot(path=str(ARTIFACTS/'font-headings.png'),full_page=True)
                        font_page.close()
                    results.append({'width':width,'height':height,'dataMap':metrics,'status':'passed'})
                    page.close()
            finally:browser.close()
        (ARTIFACTS/'results.json').write_text(json.dumps({'fixtureOnly':True,'results':results,'errors':errors},indent=2))
        assert not errors,errors
        print(json.dumps(results,indent=2))

if __name__=='__main__':main()
