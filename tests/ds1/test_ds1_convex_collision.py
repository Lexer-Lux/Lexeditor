"""Convex editing regenerates derived hulls without losing native metadata."""
from copy import deepcopy
import os
import json
import struct

import pytest

from plugins.ds1 import collision_edits,collision_hull,collision_merge,hkx,map_collision
from plugins.ds1.collision_write import CollisionDocument
from plugins.ds1.map_store import MapStore
from test_ds1_collision_store import setup,MAP,table
from test_ds1_folder_mods import vanilla


@pytest.fixture
def convex_source(monkeypatch):
    import hkx_fixture as fixture
    extra=[('prim','T*',8,hkx.PTR),('fixed','hkMatrix3f',48,'float',12),
        ('array','A_Matrix','hkMatrix3f'),('array','A_Vector','hkVector4f'),
        ('class','hkpConvexVerticesShape',136,[('radius',32,'float'),('aabbHalfExtents',48,'hkVector4f'),
          ('aabbCenter',64,'hkVector4f'),('rotatedVertices',80,'A_Matrix'),('numVertices',96,'hkInt32'),
          ('planeEquations',104,'A_Vector'),('connectivity',120,'T*')]),
        ('class','hkpConvexVerticesConnectivity',48,[('vertexIndices',16,'A_i16'),('numVerticesPerFace',32,'A_u8')])]
    types=fixture.TYPES+extra
    monkeypatch.setattr(fixture,'TYPES',types)
    monkeypatch.setattr(fixture,'TIDS',{entry[1]:i+1 for i,entry in enumerate(types)})
    base=fixture.build_tag0()
    first=len(hkx._peek_tables(base))
    shape=bytearray(136)
    struct.pack_into('<f',shape,32,.05)
    struct.pack_into('<4f',shape,48,1,1,0,0)
    for at,index in ((80,first+1),(104,first+2),(120,first+3)):struct.pack_into('<i',shape,at,index)
    struct.pack_into('<i',shape,96,4)
    connectivity=bytearray(48);struct.pack_into('<i',connectivity,32,first+4)
    planes=[0,0,1,0, 0,0,-1,0, 1,0,0,-1, -1,0,0,-1, 0,1,0,-1, 0,-1,0,-1]
    return fixture.append_items(base,[('hkpConvexVerticesShape',1,shape,[80,104,120]),
        ('hkMatrix3f',1,struct.pack('<12f',-1,1,1,-1, -1,-1,1,1, 0,0,0,0),[]),
        ('hkVector4f',6,struct.pack('<24f',*planes),[]),
        ('hkpConvexVerticesConnectivity',1,connectivity,[32]),('hkUint8',6,bytes(6),[])])


def moved(document,index,axis,value):
    mesh=deepcopy(collision_merge._mesh(document,0))
    mesh['vertices'][index][axis]=value
    mesh['faces']=collision_hull.build(mesh['vertices'])['faces']
    return mesh


def test_convex_write_updates_planes_bounds_and_optional_cache(convex_source):
    document=CollisionDocument(convex_source)
    assert document.kind=='convex' and len(document.meshes[0]['faces'])==2
    mesh=moved(document,3,2,.5)
    raw=document.export({0:collision_merge._update(collision_merge._mesh(document,0),mesh)})
    again=CollisionDocument(raw)
    assert again.meshes[0]['vertices']==mesh['vertices']
    shape=again._value(again.shape)
    assert shape['radius']==pytest.approx(.05)
    assert shape['aabbCenter']==[0,0,.25,0] and shape['aabbHalfExtents']==[1,1,.25,0]
    assert shape['connectivity'] is None
    assert len(shape['planeEquations'])==4
    assert all(sum(plane[i]*vertex[i] for i in range(3))+plane[3]<=1e-7
               for plane in shape['planeEquations'] for vertex in mesh['vertices'])
    assert again.export({})==raw and document.source==convex_source
    assert map_collision.preview_meshes(raw)[0]['tris']==4


def test_convex_vertex_add_remove_resizes_packed_groups(convex_source):
    document=CollisionDocument(convex_source)
    mesh=deepcopy(collision_merge._mesh(document,0))
    mesh['vertices'].append([0,0,1,0]);mesh['flags'].append([])
    mesh['faces']=collision_hull.build(mesh['vertices'])['faces']
    raw=document.export({0:collision_merge._update(collision_merge._mesh(document,0),mesh)})
    added=CollisionDocument(raw)
    assert len(added._value(added.shape)['rotatedVertices'])==2
    assert len(added.meshes[0]['vertices'])==5
    mesh['vertices'].pop(0);mesh['flags'].pop(0)
    mesh['faces']=collision_hull.build(mesh['vertices'])['faces']
    removed=CollisionDocument(added.export({0:collision_merge._update(collision_merge._mesh(added,0),mesh)}))
    assert len(removed._value(removed.shape)['rotatedVertices'])==1
    assert removed.meshes[0]['vertices']==mesh['vertices']


@pytest.mark.parametrize('field,value,offset',[('radius',float('nan'),0),('aabbHalfExtents',float('nan'),0),
    ('planeEquations',float('nan'),0),('aabbHalfExtents',-1.,0),('planeEquations',0.,8)])
def test_invalid_convex_metadata_does_not_poison_a_valid_document(convex_source,field,value,offset):
    document=CollisionDocument(convex_source)
    _kind,at=document._field(document.shape,field)
    if field=='planeEquations':
        index=struct.unpack_from('<i',convex_source,at)[0]
        at=document.entries[index]['pos']
    broken=bytearray(convex_source)
    struct.pack_into('<f',broken,at+offset,value)
    with pytest.raises(ValueError,match='invalid planes or bounds'):
        CollisionDocument(broken)
    assert CollisionDocument(convex_source).export({})==convex_source


def test_convex_bounds_round_outward_and_repeated_edits_do_not_grow_file(convex_source):
    document=CollisionDocument(convex_source)
    mesh=moved(document,0,0,-100000.125)
    mesh['vertices'][1][0]=collision_hull._float32(1.234567)
    mesh['faces']=collision_hull.build(mesh['vertices'])['faces']
    raw=document.export({0:collision_merge._update(collision_merge._mesh(document,0),mesh)})
    sizes=[]
    for i in range(4):
        current=CollisionDocument(raw)
        values=moved(current,0,0,-100000.125-i)
        raw=current.export({0:collision_merge._update(collision_merge._mesh(current,0),values)})
        again=CollisionDocument(raw)
        bounds=again._value(again.shape)
        assert all(bounds['aabbCenter'][axis]-bounds['aabbHalfExtents'][axis]<=v[axis]
                   <=bounds['aabbCenter'][axis]+bounds['aabbHalfExtents'][axis]
                   for v in values['vertices'] for axis in range(3))
        sizes.append(len(raw))
    assert len(set(sizes))==1


def test_convex_portable_records_store_vertices_and_combine_independent_edits(convex_source):
    base=CollisionDocument(convex_source)
    a=moved(base,0,0,-2)
    b=moved(base,1,1,-2)
    records=[collision_edits.create_state(base,base,[mesh]) for mesh in (a,b)]
    assert all(spec['meshes'][0]['counts'][1]==0 for spec in records)
    assert all(field['kind']=='vertices' for spec in records for field in spec['meshes'][0]['fields'])
    states=[(name,*collision_edits.open_member(convex_source,spec)) for name,spec in zip(('A','B'),records)]
    raw,conflicts=collision_merge.merge_states(convex_source,states)
    assert not conflicts
    final=CollisionDocument(raw).meshes[0]['vertices']
    assert final[0][0]==-2 and final[1][1]==-2
    # Rebase over a foreign vertex change even when it changes derived faces.
    foreign=base.export({0:collision_merge._update(collision_merge._mesh(base,0),moved(base,3,2,.5))})
    _document,values=collision_edits.open_member(foreign,records[0])
    assert values[0]['vertices'][0][0]==-2 and values[0]['vertices'][3][2]==.5


def test_convex_editor_atomic_edit_and_save_without_physics_compilation(convex_source,tmp_path,monkeypatch):
    game,project,store,_pair=setup(tmp_path,convex_source)
    view=store.collisions.view(MAP,'h0000','high',0,'faces')
    assert view['derivedFaces']
    assert all(not field['editable'] for field in store.collisions.read_row(table(store),'f:0')['fields'])
    with monkeypatch.context() as scope:
        scope.setattr(CollisionDocument,'export',lambda *a,**k:pytest.fail('Portable Save must not compile physics'))
        store.collisions.edit_row(table(store),'v:0','posX',-2)
        assert store.dirty_count==1
        with pytest.raises(ValueError,match='Convex faces follow'):
            store.collisions.edit_row(table(store),'f:0','vertexA',1)
        store.save()
    again=MapStore(game,project,False)
    assert again.collisions.read_row(table(again),'v:0')['values']['posX']==-2
    before=again.collisions.snapshot(table(again))
    invalid=deepcopy(before)
    invalid['vertices']=[[0,0,0,0]]*4
    with pytest.raises(ValueError):again.collisions.replace_mesh(table(again),invalid)
    assert again.collisions.snapshot(table(again))==before and again.dirty_count==0


def test_convex_release_combines_with_foreign_vertices_without_editor(convex_source,vanilla,tmp_path):
    from plugins.ds1 import collision_archive,record_edits,runtime_mods,standalone_runtime
    from test_ds1_portable_collisions import HEADER,BODY,write_pair
    authored_game,project,_store,pair=setup(tmp_path,convex_source)
    base=CollisionDocument(convex_source)
    def variant(mesh):
        raw=base.export({0:collision_merge._update(collision_merge._mesh(base,0),mesh)})
        return collision_archive.CollisionArchive(*pair).replace({'h0000a10':raw})
    write_pair(project,variant(moved(base,0,0,-2)))
    (project/'mod.json').write_text(json.dumps({'id':'convex','name':'Convex'}))
    player=tmp_path/'player-game'
    write_pair(player,variant(moved(base,1,1,-2)))
    release=runtime_mods.write_release(project,player/'mods',vanilla,game_root=authored_game)
    assert (release/record_edits.FILENAME).is_file() and not (release/HEADER).exists()
    report=standalone_runtime._run(player,[player/'mods'],lambda:None)
    assert report['loaded']==['convex'] and not report['disabled']
    archive=collision_archive.CollisionArchive((player/HEADER).read_bytes(),(player/BODY).read_bytes())
    vertices=CollisionDocument(archive.member('h0000a10')).meshes[0]['vertices']
    assert vertices[0][0]==-2 and vertices[1][1]==-2
    assert archive.member('h0001a10')==convex_source


def test_broken_convex_mod_is_isolated_before_other_mods_compose(convex_source,tmp_path):
    from core.mod_builds import ModBuildError
    from plugins.ds1 import collision_archive,mod_loader
    from test_ds1_portable_collisions import HEADER,BODY
    game,project,_store,pair=setup(tmp_path,convex_source)
    base=CollisionDocument(convex_source)
    _kind,at=base._field(base.shape,'radius')
    broken=bytearray(convex_source);struct.pack_into('<f',broken,at,float('nan'))
    bad_pair=collision_archive.CollisionArchive(*pair).replace({'h0000a10':bytes(broken)})
    good_raw=base.export({0:collision_merge._update(collision_merge._mesh(base,0),moved(base,0,0,-2))})
    good_pair=collision_archive.CollisionArchive(*pair).replace({'h0000a10':good_raw})
    bad=mod_loader.Mod('Broken convex',tmp_path/'bad',dict(zip((HEADER,BODY),bad_pair)))
    good=mod_loader.Mod('Healthy convex',project,dict(zip((HEADER,BODY),good_pair)))
    with pytest.raises(ModBuildError) as caught:
        mod_loader.compose_installed(game,[good,bad])
    assert tuple(caught.value.folders)==(bad.folder,)
    result=mod_loader.compose_installed(game,[good])
    final=collision_archive.CollisionArchive(*(result.files.get(path,raw) for path,raw in zip((HEADER,BODY),pair)))
    assert CollisionDocument(final.member('h0000a10')).meshes[0]['vertices'][0][0]==-2


def test_convex_browser_edits_vertices_and_explains_derived_faces(convex_source,tmp_path):
    from playwright.sync_api import sync_playwright
    from plugins.ds1.plugin import DS1Session
    from plugins.ds1.store import RELATIVE
    from ds1_fixture import make_archive
    from msb_fixture import build_msb
    game,project,_store,pair=setup(tmp_path,convex_source)
    from test_ds1_portable_collisions import HEADER,BODY
    for relative,payload in zip((HEADER,BODY),pair):
        low=relative.with_name('l'+relative.name[1:])
        (game/low).write_bytes(payload.replace(b'h0000a10',b'l0000a10').replace(b'h0001a10',b'l0001a10') if relative==HEADER else payload)
    (game/RELATIVE).parent.mkdir(parents=True,exist_ok=True)
    (game/RELATIVE).write_bytes(make_archive())
    (game/'map/MapStudio'/MAP).write_bytes(build_msb(models=(('h0000',5),),parts=(('collision',5,0,0,None),)))
    with DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(project),
        'LEXEDITOR_DS1_MODS_ROOT':str(tmp_path/'library'),'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0'}) as session:
        with sync_playwright() as play:
            browser=play.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1600,'height':1000})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]')
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.evaluate('navigate("maps")')
                page.locator('[data-tabstrip-id="collision"]').click()
                page.wait_for_selector('.ds1-collision')
                page.wait_for_selector('[data-viewport-host][data-ready="true"]')
                page.wait_for_function('state.collision?.derivedFaces&&state.row?.id==="v:0"')
                page.evaluate('window.convexCanvas=document.querySelector("[data-viewport-host] canvas")')
                page.locator('[data-field-key="posX"]').fill('-2')
                page.locator('[data-field-key="posX"]').press('Tab')
                page.wait_for_function('state.pending===0&&state.row?.values.posX===-2')
                page.get_by_role('button',name='Add collision vertex',exact=True).click()
                page.wait_for_function('state.collision.rows.length===5&&!state.rowBusy')
                page.get_by_role('button',name='Remove collision vertex',exact=True).click()
                page.wait_for_function('state.collision.rows.length===4&&!state.rowBusy')
                page.evaluate('fieldHistory.undo()')
                page.wait_for_function('state.collision.rows.length===5')
                page.evaluate('fieldHistory.redo()')
                page.wait_for_function('state.collision.rows.length===4')
                page.evaluate('save()')
                page.wait_for_function('state.dirty===0')
                page.locator('[data-tabstrip-id="faces"]').click()
                page.wait_for_function('state.row?.id.startsWith("f:")')
                for action in ('Add','Duplicate','Remove'):
                    assert page.get_by_role('button',name=f'{action} collision face',exact=True).is_disabled()
                assert not page.get_by_role('button',name='Change Vertex A',exact=True).count()
                assert 'Convex faces follow' in page.evaluate('state.collision.faceEditReason')
                assert page.evaluate('document.querySelector("[data-viewport-host] canvas")===convexCanvas')
                if os.environ.get('LEX_CONVEX_CAPTURE'):
                    box=page.locator('[data-viewport-host] canvas').bounding_box()
                    page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.4)
                    page.mouse.down()
                    page.mouse.move(box['x']+box['width']*.65,box['y']+box['height']*.5,steps=10)
                    page.mouse.up()
                    page.screenshot(path=os.environ['LEX_CONVEX_CAPTURE'])
                page.locator('.ds1-reference-face').first.click()
                page.wait_for_function('state.collision.kind==="vertices"&&state.row?.id.startsWith("v:")')
                assert not page.locator('.lex-important-backdrop').count()
                assert not errors,errors
            finally:
                browser.close()
