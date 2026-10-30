"""External edits refresh clean stores without dropping edits or good data."""
import os
from pathlib import Path

import pytest

from plugins.ds1 import project_refresh, record_edits
from plugins.ds1.store import ItemStore, RELATIVE
from plugins.ds1.native_rules import NativeRules
from plugins.ds1.weapon_skills import WeaponSkills
from plugins.ds1.map_store import MapStore
from plugins.ds1.tae_store import TaeStore
from test_ds1_portable_records import setup_library, edited
from ds1_fixture import make_archive
from msb_fixture import build_msb
from tae_fixture import build_anibnd, build_tae


def stores(tmp_path):
    game,mod = setup_library(tmp_path)
    items = ItemStore(game,mod,False)
    items.get()
    return (items,NativeRules(game,mod,False),MapStore(game,mod,False,items),
            TaeStore(game,mod,False,items),WeaponSkills(game,mod,False))


def change(items,value):
    (items.project/record_edits.FILENAME).write_bytes(record_edits.encode({RELATIVE:
        record_edits.create(RELATIVE,make_archive(),edited(make_archive(),'sellValue',value))}))


def test_clean_external_record_change_can_be_edited_and_saved_without_reopening(tmp_path):
    old = stores(tmp_path)
    change(old[0],43)
    fresh = project_refresh.refresh(*old)
    assert fresh[0].get().value('EquipParamGoods',100,'sellValue') == 43
    assert old[0].get().value('EquipParamGoods',100,'sellValue') == 42
    fresh[0].edit('EquipParamGoods',100,'sellValue',44)
    fresh[0].save()
    assert fresh[0].get().value('EquipParamGoods',100,'sellValue') == 44
    assert fresh[2].item_store is fresh[0] and fresh[3].item_store is fresh[0]


@pytest.mark.parametrize('dirty',['items','rules','skills'])
def test_any_unsaved_unit_defers_refresh_without_touching_existing_state(tmp_path,dirty):
    old = stores(tmp_path)
    if dirty == 'items':
        old[0].edit('EquipParamGoods',100,'sellValue',99)
    elif dirty == 'rules':
        old[1].value['baseRecovery'] += 1
    else:
        old[4].value['skills'].append({'id':'draft'})
    change(old[0],43)
    before = old[0].records_hash
    assert project_refresh.refresh(*old) is None
    assert old[0].records_hash == before
    assert old[0].get().value('EquipParamGoods',100,'sellValue') == (99 if dirty=='items' else 42)


def test_unchanged_project_keeps_existing_objects(tmp_path):
    old = stores(tmp_path)
    assert not project_refresh.changed(*old)
    assert project_refresh.refresh(*old) is None
    change(old[0],43)
    assert project_refresh.changed(*old)
    assert old[0].get().value('EquipParamGoods',100,'sellValue') == 42


def test_builder_notification_does_not_read_archives(tmp_path,monkeypatch):
    old = stores(tmp_path)
    def forbidden(*_):
        pytest.fail('A builder notification must not hash loaded game archives')
    monkeypatch.setattr(project_refresh,'_changed',forbidden)
    assert not project_refresh.changed(*old,paths=['script/tweak.py'])
    assert project_refresh.refresh(*old,paths=['script/tweak.py']) is None


def test_parameter_refresh_retains_unmodified_decoded_animations(tmp_path,monkeypatch):
    old = stores(tmp_path)
    binder = 'c1200.anibnd.dcx'
    (old[0].game_root/'chr').mkdir()
    (old[0].game_root/'chr'/binder).write_bytes(build_anibnd({'a87.tae':build_tae()}))
    decoded = old[3].get(binder)
    change(old[0],43)
    def forbidden(*_):
        pytest.fail('A parameter notification must not reparse unchanged animations')
    monkeypatch.setattr(TaeStore,'_load',forbidden)
    checked = []
    changed = project_refresh._changed
    def capture(path,*args):
        checked.append(path)
        return changed(path,*args)
    monkeypatch.setattr(project_refresh,'_changed',capture)
    fresh = project_refresh.refresh(*old,paths=[record_edits.FILENAME.as_posix()])
    assert fresh[3].get(binder) is decoded
    assert fresh[3].item_store is fresh[0]
    assert set(checked) == {old[0].project/record_edits.FILENAME}


def test_a_second_external_write_during_refresh_does_not_publish_mixed_sources(tmp_path,monkeypatch):
    old = stores(tmp_path)
    change(old[0],43)
    initialize = NativeRules.__init__
    def racing_initialize(self,*args,**kwargs):
        initialize(self,*args,**kwargs)
        change(old[0],44)
    monkeypatch.setattr(NativeRules,'__init__',racing_initialize)
    with pytest.raises(ValueError,match='changed again'):
        project_refresh.refresh(*old)
    assert old[0].get().value('EquipParamGoods',100,'sellValue') == 42


def test_loaded_maps_and_animations_reload_atomically(tmp_path):
    old = stores(tmp_path)
    game,mod = old[0].game_root,old[0].project
    map_name,binder = 'm10_00_00_00.msb','c1200.anibnd.dcx'
    (game/'map/MapStudio').mkdir(parents=True)
    (game/'map/MapStudio'/map_name).write_bytes(build_msb())
    (game/'chr').mkdir()
    (game/'chr'/binder).write_bytes(build_anibnd({'a87.tae':build_tae()}))
    old[2].get(map_name)
    old[3].get(binder)
    (mod/'map/MapStudio').mkdir(parents=True)
    new_map = build_msb(parts=(('enemy',2,0,0,120000,(9.,8.,7.)),))
    (mod/'map/MapStudio'/map_name).write_bytes(new_map)
    fresh = project_refresh.refresh(*old)
    assert fresh[2].get(map_name).export() == new_map
    assert binder in fresh[3].docs
    # A later broken animation must not replace even the already-parsed new
    # parameters: the caller receives no partial set of replacement stores.
    change(fresh[0],45)
    (mod/'chr').mkdir()
    (mod/'chr'/binder).write_bytes(b'broken external binder')
    before = fresh[0].records_hash
    with pytest.raises(ValueError):
        project_refresh.refresh(*fresh)
    assert fresh[0].records_hash == before
    assert fresh[0].get().value('EquipParamGoods',100,'sellValue') == 42


def test_browser_watcher_refreshes_clean_data_and_preserves_unsaved_edit(tmp_path):
    from plugins.ds1.plugin import DS1Session
    from playwright.sync_api import sync_playwright
    game,mod = setup_library(tmp_path)
    with DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(mod),
                     'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0',
                     'LEXEDITOR_DS1_MODS_ROOT':str(mod.parent)}) as session:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width':1440,'height':900})
                errors = []
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]')
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.evaluate('navigate("items","consumables","EquipParamGoods:100")')
                value = 'state.row?.fields.find(f=>f.key==="sellValue")?.value'
                page.wait_for_function(value+'===42')
                page.locator('.lex-tabbed-panel [data-subtab]').filter(has_text='Value').first.click()
                page.wait_for_function('modRevision>=0&&!modPollBusy')
                # Source-only notifications must not interrupt a click or lock
                # an unchanged view while checking for new generated data.
                assert page.evaluate('''async()=>{
                    const original=LexeditorUI.setEditorBusy;
                    let locks=0;
                    LexeditorUI.setEditorBusy=(...args)=>{locks++;return original(...args)};
                    try{
                        modProjectFiles=['script/tweak.py'];modProjectRefreshPending=true;
                        await refreshProjectData();
                        return locks===0&&!modProjectRefreshPending&&!document.body.inert;
                    }finally{LexeditorUI.setEditorBusy=original}
                }''')
                # A different tool updates the currently open release's data.
                before = page.evaluate('modRevision')
                change(ItemStore(game,mod,False),43)
                page.wait_for_function(value+'===43&&!document.body.inert',timeout=15000)
                assert page.evaluate('state.selected') == 'EquipParamGoods:100'
                assert page.evaluate('modRevision') > before
                screenshot = os.environ.get('LEXEDITOR_PROJECT_REFRESH_SCREENSHOT')
                if screenshot:
                    Path(screenshot).parent.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=screenshot)
                page.evaluate('''async()=>{
                    await api('/api/edit',{table:'EquipParamGoods',id:100,field:'sellValue',value:99});
                    await refreshState();await loadItems();
                    fieldHistory.undoStack.push({marker:'keep this unsaved history'});
                }''')
                before = page.evaluate('modRevision')
                change(ItemStore(game,mod,False),44)
                try:
                    page.wait_for_function('(before)=>modRevision>before&&!modPollBusy',arg=before,timeout=15000)
                except Exception:
                    pytest.fail(str({'before':before,'client':page.evaluate('({modRevision,modPollBusy,modPollStopped,dirty:state.dirty})'),
                                     'server':page.request.get(session.url+'/api/mod-changes?since=0').json(),'errors':errors}))
                assert page.evaluate(value) == 99
                assert page.evaluate('state.dirty') > 0
                assert page.evaluate('fieldHistory.undoStack.at(-1).marker') == 'keep this unsaved history'
                page.evaluate('discard()')
                page.wait_for_function(value+'===44')
                assert not errors,errors
            finally:
                browser.close()
