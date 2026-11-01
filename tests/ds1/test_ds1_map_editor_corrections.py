"""Map categories, linked chest rewards, and alternate FLVER face sets."""
import struct
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from plugins.ds1.flver import FlverDocument
from plugins.ds1.map_store import MapStore
from plugins.ds1.msb import MAP_DIR, MsbError
from msb_fixture import build_msb


@pytest.mark.parametrize('flags,expected', [([0,1,2,128], [0]), ([1,2,129], [0]),
                                          ([0,0,1,2], [0,1]), ([128], [0])])
def test_mesh_uses_one_lod_without_motion_blur_copies(flags, expected):
    doc=object.__new__(FlverDocument)
    doc.materials=[{'mat_def':'M[D].mtd'}]
    doc._index_list=lambda data,offset,count,total,kind: list(range(len(flags))) if kind=='face set' else []
    faces=[{'flags':flag,'cull':True,'triangles':[(i,i+1,i+2)]} for i,flag in enumerate(flags)]
    header={'material':0,'face_off':0,'face_count':len(flags),'array_off':0,'array_count':0,
            'dynamic':False,'default_bone':-1,'box_off':0,'bone_count':0}
    mesh=doc._mesh(b'',0,header,faces,[])
    assert mesh['triangles']==[faces[index]['triangles'][0] for index in expected]


def chest_map():
    payload=bytearray(52)
    struct.pack_into('<i',payload,4,0)
    for i in range(5):struct.pack_into('<i',payload,8+i*8,100 if i==0 else -1)
    payload[48]=1
    return build_msb(models=(('o0100',1),),
        parts=(('Chest',1,0,0,None),('Door',1,1,0,None)),
        events=(('Chest reward',4,0,0,(-1,-1,-1,0),bytes(payload)),))


def test_chest_reward_edits_the_linked_treasure_and_roundtrips(tmp_path):
    game,mod=tmp_path/'game',tmp_path/'mod'
    (game/MAP_DIR).mkdir(parents=True);mod.mkdir()
    from plugins.ds1.store import MARKER
    (mod/MARKER).touch()
    name='m10_00_00_00.msb'
    (game/MAP_DIR/name).write_bytes(chest_map())
    document=SimpleNamespace(link_choices=lambda kind,table:{'-1':'None','100':'Humanity','101':'Titanite Shard'})
    store=MapStore(game,mod,False,SimpleNamespace(get=lambda:document))
    store._npc=lambda:([],{},{})
    store.place_display_names=lambda:{}
    chest=store.read(name,'1:0')
    reward=next(field for field in chest['fields'] if field['key']=='contents:0:itemLot1')
    assert reward['type']=='enum' and reward['enum']['100']=='Humanity'
    assert reward['group']=='Contents'
    assert any(link['field']==reward['key'] and link['table']=='ItemLotParam' for link in chest['recordLinks'])
    store.edit(name,'1:0',reward['key'],101)
    assert store.row_modified(name,'1:0')
    event=store.get(name).read_placement(('event4',0))
    assert next(field['value'] for field in event['fields'] if field['key']=='itemLot1')==101
    with pytest.raises(MsbError,match='no such treasure'):
        store.edit(name,'1:1',reward['key'],100)
    store.save()
    from plugins.ds1.msb import MsbDocument
    saved=MsbDocument((mod/MAP_DIR/name).read_bytes())
    assert next(field['value'] for field in saved.read_placement(('event4',0))['fields'] if field['key']=='itemLot1')==101
    assert (game/MAP_DIR/name).read_bytes()==chest_map()


def test_flat_map_categories_and_collision_overlay_render(tmp_path):
    import base64
    from ds1_fixture import make_archive
    from plugins.ds1.store import RELATIVE
    from plugins.ds1.plugin import DS1Session
    from playwright.sync_api import sync_playwright
    game=tmp_path/'game'
    (game/RELATIVE).parent.mkdir(parents=True)
    (game/RELATIVE).write_bytes(make_archive())
    (game/MAP_DIR).mkdir(parents=True)
    name='m10_00_00_00.msb'
    raw=chest_map()
    (game/MAP_DIR/name).write_bytes(raw)
    session=DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_NO_MOD':'1',
        'LEXEDITOR_MOD_READ_ONLY':'1','LEXEDITOR_DS1_MODS_ROOT':str(tmp_path/'library')})
    errors=[]
    session.start()
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1600,'height':1000})
                page.on('pageerror',lambda error:errors.append(str(error)))
                def view(route):
                    response=route.fetch();data=response.json()
                    data['models']['h0000']={'type':5,'available':True}
                    data['parts'].append({'key':'5:0','model':'h0000','kind':'Collision','name':'Collision',
                                          'pos':[0,0,0],'rot':[0,0,0],'scale':[1,1,1]})
                    route.fulfill(response=response,json=data)
                def geometry(route):
                    from urllib.parse import parse_qs,urlparse
                    names=parse_qs(urlparse(route.request.url).query)['models'][0].split(',')
                    encode=lambda values,dtype:base64.b64encode(struct.pack(f'<{len(values)}{dtype}',*values)).decode()
                    mesh={'positions':encode([-2.,0.,-2.,2.,0.,-2.,2.,0.,2.,-2.,0.,2.],'f'),
                          'indices':encode([0,1,2,0,2,3],'I'),'normals':'','mat_def':'','cull':False}
                    route.fulfill(json={'items':{name:{'meshes':[dict(mesh,layer='collisionHigh')],
                                                            'notes':[]} for name in names}})
                page.route('**/api/map/view?*',view)
                page.route('**/api/map/geometries?*',geometry)
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]',timeout=60000)
                page.locator('[data-tab="maps"]').click()
                page.wait_for_function('state.tab==="maps" && !!state.mapView && !state.error')
                assert page.locator('[data-tabstrip-id="placements"]').count()==0
                assert page.locator('[data-tabstrip-id="all"]').count()==0
                for category in ('objects','loot','treasure','drops'):
                    page.locator(f'[data-tabstrip-id="{category}"]').click()
                    page.wait_for_function('(id)=>state.mapTab===id',arg=category)
                    assert page.locator('[data-maps-dir] [role="tablist"]').count()==0
                assert page.locator('[data-tabstrip-id="treasure"]').inner_text().casefold()=='interactions'
                page.locator('[data-tabstrip-id="objects"]').click()
                page.locator('[data-maps-dir] .lex-list-row',has_text='Chest').click()
                page.wait_for_function('state.row?.fields.some(f=>f.key==="contents:0:itemLot1")')
                assert page.get_by_text('Contents',exact=True).count()>0
                page.locator('[data-viewport-host]').hover()
                page.get_by_role('checkbox',name='High collision',exact=True).check()
                page.wait_for_function('''()=>{let n=0;document.querySelector('[data-viewport-host]')._viewportScene
                    .traverse(o=>{if(o.userData.collisionLayer==='collisionHigh')n++;});return n===3;}''')
                overlay=page.evaluate('''()=>{const out=[];document.querySelector('[data-viewport-host]')._viewportScene
                    .traverse(o=>{if(o.userData.collisionLayer)out.push({mesh:!!o.isMesh,depth:o.material.depthTest,
                        offset:o.material.polygonOffset,write:o.material.depthWrite});});return out;}''')
                assert any(o['mesh'] and o['offset'] and not o['write'] for o in overlay)
                assert any(not o['mesh'] and not o['depth'] for o in overlay)
                assert page.locator('[aria-label="Map actions"]').evaluate('''node=>{
                    const bar=node.getBoundingClientRect(),host=node.parentElement.getBoundingClientRect();
                    return bar.left>=host.left && bar.right<=host.right;
                }''')
                page.screenshot(path=str(tmp_path/'maps-corrections.png'))
                assert not errors,errors
            finally:browser.close()
    finally:session.stop();session.wait_closed()
