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


def test_create_all_supported_event_kinds_and_light_lifecycle():
    from plugins.ds1 import msb_events
    doc = document()
    for kind in msb_events.SPECS:
        row = doc.create_placement(f'@event:{kind}', (1., 2., 3.), (0., 0., 0.))
        assert row['kind'] == msb_events.LABELS[kind]
        MsbDocument(doc.export())
    light = doc.lights()[0]
    clone = msb_events.duplicate(doc, ('event0', light['seq']))
    doc.edit_light(('light', int(clone['key'].split(':')[1])), 'posX', 42.)
    assert doc.read_light(('light', int(clone['key'].split(':')[1])))['fields'][0]['value'] == 42
    assert doc.read_light(('light', light['seq']))['fields'][0]['value'] == 1
    msb_events.remove(doc, ('event0', int(clone['key'].split(':')[1])))
    assert len(MsbDocument(doc.export()).lights()) == 1


@pytest.mark.parametrize('key,field,value', [((5, 0), 'hitFilter', 24), ((5, 0), 'startsDisabled', 1),
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


def test_map_layers_and_edits_in_rendered_editor(tmp_path):
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
    errors, requests = [], []
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                          'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
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
                    route.fulfill(json={'items': items})

                page.route('**/api/map/view?*', view)
                page.route('**/api/map/geometries?*', geometries)
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                page.locator('[data-tab="maps"]').click()
                page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=30000)
                assert not any('models=h0000' in url or 'models=n0000' in url for url in requests)
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
                page.locator('[data-tabstrip-id="placements"]').click()
                page.evaluate('selectPlacement("m10_02_00_00.msb:5:0",false)')
                page.wait_for_selector('[data-field-key="hitFilter"]:visible')
                assert page.locator('[data-field-key="startsDisabled"]:visible').get_attribute('type') == 'checkbox'
                screenshot = os.environ.get('LEXEDITOR_MAP_REVIEW_SCREENSHOT')
                if screenshot:
                    page.screenshot(path=screenshot)
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
                assert not errors, errors
            finally:
                browser.close()
    finally:
        session.stop()
