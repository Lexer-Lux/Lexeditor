"""Directory locality follows actual activation references, including defaults."""
from pathlib import Path
import os
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).resolve().parent))

from msb_fixture import build_msb
from plugins.ds1.map_store import MapStore
from plugins.ds1.msb import MsbDocument, MAP_DIR
from plugins.ds1.msb_events import activation_parameter


def activation(name, seq, part, parameter):
    return (name,7,seq,0,(-1,-1,-1,0),struct.pack('<iihBBi',-1,part,parameter,0,0,-1))


def map_bytes(events):
    return build_msb(models=(('c1200',0),('o0101',1),('o0202_0000',1)),
                     parts=(('enemy',2,0,0,120000),('object',1,0,1,None),('dummy',9,0,2,None)),
                     events=events)


def test_interactions_resolve_explicit_and_inherited_rows_without_guessing():
    doc = MsbDocument(map_bytes([
        activation('explicit',0,1,100),activation('default',1,1,-1),
        activation('variant',2,2,-1),activation('no object',3,99,102),
        activation('enemy',4,0,-1),activation('invalid sentinel',5,1,-2)]),'m10_00_00_00.msb')
    assert [activation_parameter(doc,item) for item in doc.events] == [100,101,202,None,None,None]


def test_locality_uses_map_events_and_updates_after_an_edit(tmp_path):
    maps = tmp_path/MAP_DIR
    maps.mkdir(parents=True)
    first, second = 'm10_00_00_00.msb','m10_01_00_00.msb'
    originals = {first:map_bytes([activation('explicit',0,1,100)]),
                 second:map_bytes([activation('default',0,1,-1)])}
    for name,raw in originals.items():
        (maps/name).write_bytes(raw)
    store = MapStore(tmp_path)
    assert store.activation_maps() == {100:[first],101:[second]}
    store.get(first).edit(('event7',0),'activationParam',102)
    assert store.activation_maps() == {102:[first],101:[second]}
    # Renaming a row cannot change locality: display names come from the
    # real linked maps, while an unplaced definition has no local match.
    names = store.describe_treasure('misleading reference name',{},[first])
    assert names['mapNames'] == [store.display_name(first)]
    assert store.activation_maps().get(999,[]) == []
    assert {name:(maps/name).read_bytes() for name in originals} == originals


def test_treasure_local_toggle_renders_and_tracks_the_open_map(tmp_path):
    from ds1_fixture import make_archive
    from plugins.ds1.plugin import DS1Session
    from plugins.ds1.store import RELATIVE
    from playwright.sync_api import sync_playwright
    game = tmp_path/'game'
    (game/RELATIVE).parent.mkdir(parents=True)
    (game/RELATIVE).write_bytes(make_archive())
    (game/MAP_DIR).mkdir(parents=True)
    first,second = 'm10_00_00_00.msb','m10_01_00_00.msb'
    (game/MAP_DIR/first).write_bytes(map_bytes([activation('explicit',0,1,100)]))
    (game/MAP_DIR/second).write_bytes(map_bytes([activation('inherited',0,1,-1)]))
    session = DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_NO_MOD':'1',
                          'LEXEDITOR_MOD_READ_ONLY':'1','LEXEDITOR_DS1_MODS':str(tmp_path/'library')})
    session.start()
    errors = []
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width':1440,'height':900})
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]')
                page.locator('[data-tab="maps"]').click()
                page.wait_for_function('state.tab==="maps" && state.rows.length>0 && !state.error')
                page.locator('[data-tabstrip-id="placements"]').click()
                page.locator('[data-maps-dir] .lex-subtab-button',has_text='Treasure').click()
                page.wait_for_function('state.dirTab==="treasure" && state.dirRows.length===3')
                toggle = page.locator('[data-dir-local] input')
                assert toggle.is_enabled()
                toggle.check()
                page.wait_for_function('directoryMatches().map(row=>row.id).join(",")==="100"')
                assert page.locator('[data-maps-dir] .lex-list-row').count() == 1
                page.locator('[data-maps-dir] .lex-list-row').click()
                page.wait_for_function('state.row?.table==="ObjActParam" && state.row.id===100')
                screenshot = Path(os.environ.get('LEXEDITOR_TREASURE_SCREENSHOT',str(tmp_path/'treasure-local.png')))
                page.screenshot(path=str(screenshot))
                page.evaluate('(name)=>chooseMap(name)',second)
                page.wait_for_function('directoryMatches().map(row=>row.id).join(",")==="101"')
                assert page.locator('[data-maps-dir] .lex-list-row').count() == 1
                toggle.uncheck()
                page.wait_for_function('directoryMatches().length===3')
                assert not errors,errors
            finally:
                browser.close()
    finally:
        session.stop()
