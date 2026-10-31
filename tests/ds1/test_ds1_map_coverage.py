"""Map categories remain editable, round-trip, and keep links after removals."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from msb_fixture import build_msb
from plugins.ds1.msb import MsbDocument, MsbError
from plugins.ds1.map_store import MapStore
from plugins.ds1.store import MARKER


def collision_fixture(monkeypatch):
    import hkx_fixture as fixture
    from plugins.ds1 import hkx, map_collision
    extra = [('class', map_collision.MESH_TYPE, 8, [('vertices', 0, 'A_Vector'), ('indices16', 4, 'A_i16')]),
             ('array', 'A_Vector', 'hkVector4f')]
    types = fixture.TYPES + extra
    monkeypatch.setattr(fixture, 'TYPES', types)
    monkeypatch.setattr(fixture, 'TIDS', {entry[1]: index+1 for index, entry in enumerate(types)})
    source = fixture.build_tag0()
    root, _ = hkx._section(source, 0)
    table = hkx._peek_tables(source)
    item_count = len(table)
    parts = []
    mesh_at = vertex_at = index_at = None
    for section in root['subs']:
        raw = source[section['pos']:section['pos']+section['length']]
        if section['sig'] == 'DATA':
            mesh_at = len(raw)
            vertex_at, index_at = mesh_at+8, mesh_at+8+48
            raw += struct.pack('<2i', item_count+1, item_count+2)
            raw += struct.pack('<12f', 0,0,0,0, 1,0,0,0, 0,0,1,0)
            raw += struct.pack('<4h', 0,1,2,999)  # Fourth index is face metadata.
        elif section['sig'] == 'INDX':
            chunks = []
            for child in section['subs']:
                payload = source[child['pos']:child['pos']+child['length']]
                if child['sig'] == 'ITEM':
                    payload += struct.pack('<3I', fixture.TIDS[map_collision.MESH_TYPE], mesh_at, 1)
                    payload += struct.pack('<3I', fixture.TIDS['hkVector4f'], vertex_at, 3)
                    payload += struct.pack('<3I', fixture.TIDS['hkInt16'], index_at, 4)
                chunks.append(fixture._section(child['sig'].encode(), payload, False))
            raw = b''.join(chunks)
        parts.append(fixture._section(section['sig'].encode(), raw, bool(section['subs'])))
    return fixture._section(b'TAG0', b''.join(parts), True)


def test_collision_triangles_and_one_broken_layer(monkeypatch, tmp_path):
    import base64
    from plugins.ds1 import map_collision
    source = collision_fixture(monkeypatch)
    mesh = map_collision.meshes(source)[0]
    assert struct.unpack('<3I', base64.b64decode(mesh['indices'])) == (0,1,2)
    folder = tmp_path/'map/m10_02_00_00'
    folder.mkdir(parents=True)
    (folder/'h0000.hkx').write_bytes(source)
    (folder/'l0000.hkx').write_bytes(b'Broken low collision')
    result = map_collision.geometry(tmp_path, None, 'm10_02_00_00.msb', 'h0000')
    assert [mesh['layer'] for mesh in result['meshes']] == ['collisionHigh']
    assert len(result['notes']) == 1 and result['notes'][0].startswith('collisionLow:')
    # The integrated editor preview must retain loose and older storage
    # variants even when the authoring writer cannot modify that shape.
    store = MapStore(tmp_path,None,True)
    integrated = store.model_geometry('m10_02_00_00.msb',{'type':5,'name':'h0000'})
    assert [mesh['layer'] for mesh in integrated['meshes']] == ['collisionHigh']
    assert integrated['meshes'][0]['positions'] == result['meshes'][0]['positions']
    with pytest.raises(ValueError):
        store.collisions.view('m10_02_00_00.msb','h0000','high',0,'vertices')


def test_navigation_binary_geometry_validates_indices():
    import base64
    from plugins.ds1.map_navigation import geometry
    from plugins.ds1.formats import FormatError
    data = bytearray(128)
    struct.pack_into('<5i', data, 0, 1, 3, 128, 1, 164)
    data += struct.pack('<9f', 0,0,0, 1,0,0, 0,0,1)
    data += struct.pack('<7i', 0,1,2,-1,-1,-1,0)
    mesh = geometry(data)['meshes'][0]
    assert struct.unpack('<3I', base64.b64decode(mesh['indices'])) == (0,1,2)
    struct.pack_into('<i', data, 164, 100)
    with pytest.raises(FormatError):
        geometry(data)


def test_split_archive_texture_members_keep_their_original_names():
    from plugins.ds1 import bhf
    data = bytearray(76)
    data[:12] = bhf.MAGIC
    struct.pack_into('<6I', data, 28, 0, 64, 128, 16, 0, 76)
    data += b'\\wall_diffuse.dds\x00'
    assert bhf.parse_bhf(data) == {'wall_diffuse.dds': (16, 128)}
    assert bhf.parse_bhf(data, suffix='.hkx') == {}


def test_creation_distinguishes_placement_kinds_sharing_one_model():
    doc = MsbDocument(build_msb())
    for kind, expected in ((0, 'Map piece'), (1, 'Object')):
        row = doc.create_placement('m10piece', [0, 0, 0], [0, 0, 0], part_type=kind)
        assert row['type'] == kind and row['kind'] == expected
    before = doc.export()
    with pytest.raises(MsbError, match='placement kind'):
        doc.create_placement('m10piece', [0, 0, 0], [0, 0, 0], part_type=True)
    assert doc.export() == before


def test_event_parameter_links_use_catalog_names_and_survive_missing_archive(tmp_path):
    from types import SimpleNamespace
    from plugins.ds1.formats import FormatError
    store = MapStore(tmp_path)
    choices = {'-1': 'None', '100': 'Chest treasure'}
    store.item_store = SimpleNamespace(get=lambda: SimpleNamespace(link_choices=lambda kind, table: choices))
    fields = [{'key': 'itemLot1', 'value': 100}, {'key': 'activationParam', 'value': 100}]
    links = store._event_param_links(fields)
    assert all(field['type'] == 'enum' and field['enum']['100'] == 'Chest treasure' for field in fields)
    assert links[0]['kind'] == 'drop' and links[0]['resolved']
    assert links[1]['tab'] == 'maps' and links[1]['sub'] == 'treasure'

    def broken():
        raise FormatError('Broken parameter archive')

    store.item_store.get = broken
    links = store._event_param_links(fields)
    assert not links[0]['resolved'] and links[0]['name'] == 'Missing record (100)'
    assert fields[0]['enum'] == {'-1': 'None'}


def document():
    return MsbDocument(build_msb(parts=(('piece', 0, 0, 0, None), ('hit', 5, 0, 1, None),
                                         ('nav', 8, 0, 2, None)),
                                 models=(('m0000', 0), ('h0000', 5), ('n0000', 6)),
                                 points=(('Trigger', (1., 2., 3.)), ('Destination', (4., 5., 6.))),
                                 events=(('Sound', 1, 0, 0, (2, 1, -1, 0), struct.pack('<2i', 0, 100)),)), 'm10_02_00_00.msb')


def test_new_categories_roundtrip_and_keep_other_bytes():
    doc = document()
    assert {'Map piece', 'Collision', 'Navigation', 'Region', 'Sound'} <= {row['kind'] for row in doc.placements()}
    doc.edit((5, 0), 'hitFilter', 15)
    doc.edit((5, 0), 'startsDisabled', True)
    doc.edit((5, 0), 'posY', -50.)
    doc.edit(('event1', 0), 'soundId', 200)
    for key, field, value in ((('region', 0), 'rotY', 45.), (('region', 0), 'shapeType', 5),
                              (('region', 0), 'width', 12.)):
        doc.edit(key, field, value)
    after = MsbDocument(doc.export())
    assert after._by_id[(5, 0)]['pos'][1] == -50
    collision = {f['key']: f['value'] for f in after.read_placement((5, 0))['fields']}
    assert collision['hitFilter'] == 15 and collision['startsDisabled'] is True
    assert after.points[0]['dimensions']['width'] == 12
    assert after.points[0]['rot'][1] == 45
    assert after.read_placement(('event1', 0))['fields'][-1]['value'] == 200


def test_region_duplicate_and_remove_retarget_event_indices():
    doc = document()
    new = doc.add_placement(('region', 0))
    doc.edit(('region', new['partId']), 'posX', 99.)
    assert doc.points[0]['pos'][0] == 1
    doc.remove_placement(('region', 0))
    after = MsbDocument(doc.export())
    assert after.events[0]['point'] == 0
    assert after.points[0]['name'] == 'Destination'
    assert after.points[1]['pos'][0] == 99


def test_part_delete_keeps_event_attached_to_same_record():
    doc = document()
    doc.remove_placement((0, 0))
    after = MsbDocument(doc.export())
    assert after.events[0]['area'] == 1
    assert after.parts[after.events[0]['area']]['name'] == 'nav0'


def test_event_duplicate_does_not_share_entity_identity():
    doc = document()
    row = doc.add_placement(('event1', 0))
    doc.edit(('event1', row['partId']), 'soundId', 300)
    after = MsbDocument(doc.export())
    assert len(after.events) == 2
    assert [e['seq'] for e in after.events] == [0, 1]
    assert after.read_placement(('event1', 0))['fields'][-1]['value'] == 100
    after.remove_placement(('event1', 1))
    assert len(MsbDocument(after.export()).events) == 1


def test_existing_message_creation_keeps_its_new_region_browsable():
    doc = MsbDocument(build_msb(events=(('Activation', 7, 0, 0, (-1,-1,-1,0), bytes(16)),)))
    doc.create_message(10, (1.,2.,3.))
    region = next(row for row in doc.placements() if row['kind'] == 'Region')
    detail = doc.read_placement(('region', region['partId']))
    assert all(field['vanilla'] is None for field in detail['fields'])
    MsbDocument(doc.export()).read_placement(('region', region['partId']))


def test_create_all_supported_event_kinds_and_light_lifecycle():
    from plugins.ds1 import msb_events
    doc = document()
    for kind in msb_events.SPECS:
        row = doc.create_placement(f'@event:{kind}', (1., 2., 3.), (0., 0., 0.))
        assert row['kind'] == msb_events.LABELS[kind]
        MsbDocument(doc.export())
    doc.edit(('event4', 0), 'inChest', 1)
    assert next(field['value'] for field in doc.read_placement(('event4', 0))['fields'] if field['key'] == 'inChest') is True
    light = doc.lights()[0]
    clone = msb_events.duplicate(doc, ('event0', light['seq']))
    doc.edit_light(('light', int(clone['key'].split(':')[1])), 'posX', 42.)
    assert doc.read_light(('light', int(clone['key'].split(':')[1])))['fields'][0]['value'] == 42
    assert doc.read_light(('light', light['seq']))['fields'][0]['value'] == 1
    msb_events.remove(doc, ('event0', int(clone['key'].split(':')[1])))
    assert len(MsbDocument(doc.export()).lights()) == 1


@pytest.mark.parametrize('key,field,value', [((5, 0), 'hitFilter', 24), ((5, 0), 'startsDisabled', 2),
    (('region', 0), 'shapeType', 6), (('event1', 0), 'attachedRegion', 99)])
def test_invalid_edits_leave_document_unchanged(key, field, value):
    doc = document()
    before = doc.export()
    with pytest.raises(MsbError):
        doc.edit(key, field, value)
    assert doc.export() == before


def test_save_reload_in_private_project_leaves_game_untouched(tmp_path):
    game, project = tmp_path/'game', tmp_path/'mod'
    maps = game/'map/MapStudio'
    maps.mkdir(parents=True)
    project.mkdir()
    (project/'mod.json').write_text('{"name":"Fixture"}')
    (project/MARKER).touch()
    raw = document().export()
    name = 'm10_02_00_00.msb'
    (maps/name).write_bytes(raw)
    store = MapStore(game, project, False)
    store.edit(name, '5:0', 'hitFilter', 15)
    store.edit(name, 'region:0', 'shapeType', 5)
    store.edit(name, 'region:0', 'width', 20.)
    store.save()
    assert (maps/name).read_bytes() == raw
    loaded = MapStore(game, project, False)
    assert loaded.get(name).points[0]['dimensions']['width'] == 20


@pytest.mark.parametrize('read_only', [False, True])
def test_map_layers_and_edits_in_rendered_editor(tmp_path, read_only):
    import base64
    import json
    import os
    from ds1_fixture import make_archive
    from plugins.ds1.store import RELATIVE
    from plugins.ds1.plugin import DS1Session
    from playwright.sync_api import sync_playwright

    game, mod = tmp_path/'game', tmp_path/'mod'
    (game/RELATIVE).parent.mkdir(parents=True)
    (game/RELATIVE).write_bytes(make_archive())
    (game/'map/MapStudio').mkdir(parents=True)
    doc = document()
    doc.edit((5, 0), 'hitFilter', 15)
    doc.edit(('region', 0), 'shapeType', 5)
    doc.edit(('region', 0), 'width', 5.)
    (game/'map/MapStudio/m10_02_00_00.msb').write_bytes(doc.export())
    mod.mkdir()
    (mod/MARKER).touch()
    encode = lambda values, dtype: base64.b64encode(struct.pack(f'<{len(values)}{dtype}', *values)).decode()
    mesh = {'positions': encode([-4., 0., -4., 4., 0., -4., 4., 0., 4., -4., 0., 4.], 'f'),
            'indices': encode([0, 1, 2, 0, 2, 3], 'I'), 'normals': '', 'mat_def': '', 'cull': False}
    errors, requests, held = [], [], []
    delayed = [False]
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                          'LEXEDITOR_NO_MOD': '1' if read_only else '0',
                          'LEXEDITOR_MOD_READ_ONLY': '1' if read_only else '0',
                          'LEXEDITOR_DS1_MODS_ROOT':str(tmp_path/'library')})
    session.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1600, 'height': 1000})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('request', lambda request: requests.append(request.url))

                def view(route):
                    response = route.fetch()
                    data = response.json()
                    for model in data['models'].values():
                        model['available'] = True
                    route.fulfill(response=response, json=data)

                def geometries(route):
                    from urllib.parse import parse_qs, urlparse
                    names = parse_qs(urlparse(route.request.url).query)['models'][0].split(',')
                    items = {}
                    for name in names:
                        layers = ['collisionHigh', 'collisionLow'] if name.startswith('h') else ['navigation'] if name.startswith('n') else [None]
                        items[name] = {'meshes': [dict(mesh, **({'layer': layer} if layer else {})) for layer in layers], 'notes': []}
                    if names == ['m0000'] and not delayed[0]:
                        delayed[0] = True
                        held.append((route, items))
                        return
                    route.fulfill(json={'items': items})

                page.route('**/api/map/view?*', view)
                page.route('**/api/map/geometries?*', geometries)
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                with page.expect_request(lambda request: '/api/map/geometries?' in request.url and 'models=m0000' in request.url):
                    page.locator('[data-tab="maps"]').click()
                assert not any('models=h0000' in url or 'models=n0000' in url for url in requests)
                page.locator('[data-viewport-host]').hover()
                page.get_by_role('checkbox', name='Navigation', exact=True).check()
                page.get_by_role('checkbox', name='Regions', exact=True).check()
                assert held, 'The initial geometry request must be held while layer controls change'
                for route, items in held:
                    route.fulfill(json={'items': items})
                page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=30000)
                page.locator('[data-view-mode="wireframe"]').click()
                page.locator('[data-viewport-host]').hover()
                page.get_by_role('checkbox', name='High collision', exact=True).check()
                page.get_by_role('checkbox', name='Low collision', exact=True).check()
                page.get_by_role('checkbox', name='Navigation', exact=True).check()
                page.get_by_role('checkbox', name='Regions', exact=True).check()
                page.wait_for_function('''() => {
                    const scene=document.querySelector('[data-viewport-host]')._viewportScene;
                    const layers=[];scene.traverse(node=>{if(node.userData.collisionLayer)layers.push(node.userData.collisionLayer)});
                    return ['collisionHigh','collisionLow','navigation'].every(layer=>layers.includes(layer));
                }''')
                assert page.evaluate('''() => {
                    const scene=document.querySelector('[data-viewport-host]')._viewportScene;
                    let okay=true;scene.traverse(node=>{if(node.userData.collisionLayer&&!node.material.wireframe)okay=false});return okay;
                }''')
                page.locator('[data-view-mode="regular"]').click()
                page.locator('[data-tabstrip-id="placements"]').click()
                page.evaluate('selectPlacement("m10_02_00_00.msb:5:0",false)')
                page.wait_for_selector('[data-field-key="hitFilter"]:visible')
                assert page.locator('[data-field-key="startsDisabled"]:visible').get_attribute('type') == 'checkbox'
                screenshot = os.environ.get('LEXEDITOR_MAP_REVIEW_SCREENSHOT')
                if screenshot:
                    target = Path(screenshot)
                    page.screenshot(path=str(target.with_stem(target.stem+('-readonly' if read_only else '-editable'))))
                if read_only:
                    assert page.locator('[data-field-key="startsDisabled"]:visible').is_disabled()
                    assert not errors, errors
                    return
                page.locator('[data-field-key="startsDisabled"]:visible').check()
                page.wait_for_function('state.pending===0 && state.row.fields.find(f=>f.key==="startsDisabled").value===true')
                original_map = (game/'map/MapStudio/m10_02_00_00.msb').read_bytes()
                page.locator('[data-row-action="duplicate"][data-row-kind="placement"]').click()
                page.wait_for_function('!state.rowBusy && state.row?.id==="5:1"')
                assert page.locator('[data-field-key="hitFilter"]:visible').input_value() == '15'
                height = page.locator('[data-field-key="posY"]:visible')
                height.fill('-30');height.press('Tab')
                page.wait_for_function('state.pending===0 && state.row.fields.find(f=>f.key==="posY").value===-30')
                page.evaluate('api("/api/save",{})')
                saved = MsbDocument((mod/'map/MapStudio/m10_02_00_00.msb').read_bytes())
                assert saved._by_id[(5,1)]['pos'][1] == -30
                assert next(field['value'] for field in saved.read_placement((5,1))['fields'] if field['key']=='hitFilter') == 15
                page.locator('[data-row-action="remove"][data-row-kind="placement"]').click()
                page.get_by_role('button',name='Remove',exact=True).click()
                page.wait_for_function('!state.rowBusy && !state.mapView.parts.some(part=>part.key==="5:1")')
                page.evaluate('api("/api/save",{})')
                assert (5,1) not in MsbDocument((mod/'map/MapStudio/m10_02_00_00.msb').read_bytes())._by_id
                assert (game/'map/MapStudio/m10_02_00_00.msb').read_bytes() == original_map
                page.evaluate('selectPlacement("m10_02_00_00.msb:region:0",false)')
                page.wait_for_selector('[data-field-key="width"]:visible')
                control = page.locator('[data-field-key="width"]:visible')
                control.fill('10')
                control.press('Tab')
                page.wait_for_function('state.pending===0 && state.row.fields.find(f=>f.key==="width").value===10')
                page.evaluate('fieldHistory.undo()')
                page.wait_for_function('state.pending===0 && state.row.fields.find(f=>f.key==="width").value===5')
                created = page.evaluate('api("/api/placements/create",{map:"m10_02_00_00.msb",model:"@event:0",pos:[0,1,0],rot:[0,0,0]})')
                page.evaluate('(id)=>reloadViewport("m10_02_00_00.msb",id)', created['row']['id'])
                page.wait_for_function('state.row?.kind==="Light" && state.selected.endsWith("light:0")')
                page.locator('[data-row-action="duplicate"][data-row-kind="light"]').click()
                page.wait_for_function('!state.rowBusy')
                assert page.evaluate('state.row?.id') == 'light:1', page.evaluate('({selected:state.selected,row:state.row,body:document.body.innerText.slice(-1800)})')
                invasion = page.evaluate('api("/api/placements/create",{map:"m10_02_00_00.msb",model:"@event:12",pos:[0,1,0],rot:[0,0,0]})')
                invasion_id = invasion['row']['id']
                edited = page.evaluate('(id)=>api("/api/edit",{table:"m10_02_00_00.msb",id,field:"activationItem",value:100})', invasion_id)
                page.evaluate('(id)=>reloadViewport("m10_02_00_00.msb",id)', invasion_id)
                face = page.locator('.ds1-reference-face[data-field-key="activationItem"]')
                face.wait_for()
                name = next(link['name'] for link in edited['row']['recordLinks'] if link['field'] == 'activationItem')
                assert face.inner_text() == name
                assert face.locator('[data-lex-hoverable]').count() or face.locator('button').count()
                if screenshot:
                    page.screenshot(path=screenshot)
                assert not errors, errors
            finally:
                browser.close()
    finally:
        session.stop()
