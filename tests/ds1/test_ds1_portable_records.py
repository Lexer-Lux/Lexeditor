"""Release record edits preserve foreign data in shared editor/runtime paths."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from core.mod_builds import ModBuildError
from plugins.ds1 import mod_loader,record_edits,runtime_mods,texts
from plugins.ds1.formats import ItemDocument
from plugins.ds1.store import ItemStore,MARKER,RELATIVE
from ds1_fixture import make_archive,make_text_archive
from test_ds1_folder_mods import vanilla


def edited(raw,field,value):
    document = ItemDocument(raw)
    document.edit('EquipParamGoods',100,field,value)
    return document.export()


def test_field_edits_keep_unrelated_installed_fields_and_extra_rows():
    base = make_archive()
    ours = edited(base,'sellValue',42)
    spec = record_edits.create(RELATIVE,base,ours)
    foreign = ItemDocument(edited(base,'iconId',77))
    foreign.add_row('EquipParamGoods',100,155)
    installed = foreign.export()
    result = ItemDocument(record_edits.materialize(RELATIVE,installed,spec))
    assert result.value('EquipParamGoods',100,'sellValue') == 42
    assert result.value('EquipParamGoods',100,'iconId') == 77
    assert result.value('EquipParamGoods',155,'iconId') == 77
    # Only the changed row, not the game's archive or unaffected tables, ships.
    assert len(spec['tables']) == 1 and len(spec['tables'][0]['rows']) == 1


def test_a_conflicting_foreign_field_is_refused_with_its_identity():
    base = make_archive()
    spec = record_edits.create(RELATIVE,base,edited(base,'sellValue',42))
    with pytest.raises(ValueError,match='EquipParamGoods.*100.*anchor'):
        record_edits.materialize(RELATIVE,edited(base,'sellValue',43),spec)


def test_added_and_removed_rows_keep_foreign_additions():
    base = make_archive({'EquipParamGoods':[100,101]})
    ours = ItemDocument(base)
    ours.add_row('EquipParamGoods',100,123)
    ours.remove_row('EquipParamGoods',101)
    spec = record_edits.create(RELATIVE,base,ours.export())
    foreign = ItemDocument(base)
    foreign.add_row('EquipParamGoods',100,124)
    result = ItemDocument(record_edits.materialize(RELATIVE,foreign.export(),spec))
    ids = {r['id'] for r in result.list_rows('consumables')}
    assert {100,123,124} <= ids and 101 not in ids


def test_text_edits_keep_other_authors_names_and_descriptions():
    base = make_text_archive(names={'EquipParamGoods':{100:'Original',101:'Other'}})
    ours = texts.TextDocument(base)
    ours.rename('EquipParamGoods',100,'Our name')
    spec = record_edits.create(texts.RELATIVE,base,ours.export())
    foreign = texts.TextDocument(base)
    foreign.rename('EquipParamGoods',101,'Foreign name')
    result = texts.TextDocument(record_edits.materialize(texts.RELATIVE,foreign.export(),spec))
    assert result.name('EquipParamGoods',100) == 'Our name'
    assert result.name('EquipParamGoods',101) == 'Foreign name'


def setup_library(tmp_path):
    game,mod = tmp_path/'game',tmp_path/'library'/'example'
    (game/RELATIVE).parent.mkdir(parents=True)
    (game/RELATIVE).write_bytes(make_archive())
    (game/texts.RELATIVE).parent.mkdir(parents=True)
    (game/texts.RELATIVE).write_bytes(make_text_archive())
    mod.mkdir(parents=True)
    (mod/'mod.json').write_text(json.dumps({'id':'example','name':'Example','enabled':True}))
    (mod/MARKER).touch()
    spec = record_edits.create(RELATIVE,make_archive(),edited(make_archive(),'sellValue',42))
    (mod/record_edits.FILENAME).write_bytes(record_edits.encode({RELATIVE:spec}))
    return game,mod


def test_portable_contributions_use_the_shared_composer_and_conflict_report(tmp_path):
    game,mod = setup_library(tmp_path)
    first = mod_loader.read_mod(mod,'Example')
    second = mod_loader.Mod('Second',tmp_path/'second',{},
        {RELATIVE:record_edits.create(RELATIVE,make_archive(),edited(make_archive(),'sellValue',43))})
    result = mod_loader.compose_installed(game,[first,second])
    assert ItemDocument(result.files[RELATIVE]).value('EquipParamGoods',100,'sellValue') == 43
    assert any(c.mods == ['Example','Second'] for c in result.conflicts)
    assert record_edits.FILENAME.as_posix() in mod_loader.loaded_files(mod)
    assert mod_loader.describe_changes(mod,game)['changes']
    # Bad anchors identify the mod; a baseline or infrastructure error is not
    # incorrectly attributed to every healthy mod in the library.
    (game/RELATIVE).write_bytes(edited(make_archive(),'sellValue',44))
    with pytest.raises(ModBuildError) as error:
        mod_loader.compose_installed(game,[first])
    assert error.value.folders == (mod,)


def test_two_portable_mods_combine_disjoint_fields_and_added_rows(tmp_path):
    game,mod = setup_library(tmp_path)
    first = mod_loader.read_mod(mod,'Example')
    after = ItemDocument(edited(make_archive(),'iconId',77))
    after.add_row('EquipParamGoods',100,123)
    second = mod_loader.Mod('Second',tmp_path/'second',{},
        {RELATIVE:record_edits.create(RELATIVE,make_archive(),after.export())})
    result = mod_loader.compose_installed(game,[first,second])
    doc = ItemDocument(result.files[RELATIVE])
    assert not result.conflicts
    assert doc.value('EquipParamGoods',100,'sellValue') == 42
    assert doc.value('EquipParamGoods',100,'iconId') == 77
    assert doc.value('EquipParamGoods',123,'iconId') == 77


def test_portable_mods_remain_editable_after_import_without_archive_copies(tmp_path):
    game,mod = setup_library(tmp_path)
    store = ItemStore(game,mod,False)
    assert store.get().value('EquipParamGoods',100,'sellValue') == 42
    assert store.get().row_modified('EquipParamGoods',100)
    store.edit('EquipParamGoods',100,'sellValue',45)
    store.add_row('EquipParamGoods',100,155)
    store.get().texts.rename('EquipParamGoods',100,'Portable name')
    store.save()
    assert not (mod/RELATIVE).exists()
    reopened = ItemStore(game,mod,False)
    assert reopened.get().value('EquipParamGoods',100,'sellValue') == 45
    assert reopened.get().row_modified('EquipParamGoods',100)
    assert reopened.get().row_created('EquipParamGoods',155)
    assert reopened.get().texts.name('EquipParamGoods',100) == 'Portable name'
    assert not (mod/texts.RELATIVE).exists()
    portable = mod_loader.read_mod(mod,'Example')
    result = mod_loader.compose_installed(game,[portable])
    assert ItemDocument(result.files[RELATIVE]).value('EquipParamGoods',100,'sellValue') == 45


def test_stale_portable_mod_cannot_overwrite_an_external_edit(tmp_path):
    game,mod = setup_library(tmp_path)
    store = ItemStore(game,mod,False)
    store.get()
    external = (mod/record_edits.FILENAME).read_bytes()+b' '
    (mod/record_edits.FILENAME).write_bytes(external)
    store.edit('EquipParamGoods',100,'sellValue',46)
    with pytest.raises(ValueError,match='record edits changed outside'):
        store.save()
    assert (mod/record_edits.FILENAME).read_bytes() == external


def test_export_ships_sparse_records_and_reexport_preserves_them(vanilla,tmp_path):
    game,source = setup_library(tmp_path)
    (source/record_edits.FILENAME).unlink()
    (source/RELATIVE).parent.mkdir(parents=True)
    (source/RELATIVE).write_bytes(edited(make_archive(),'sellValue',42))
    released = runtime_mods.write_release(source,tmp_path/'release',vanilla,game_root=game)
    assert not (released/RELATIVE).exists()
    assert (released/record_edits.FILENAME).is_file()
    copied = runtime_mods.write_release(released,tmp_path/'copy',vanilla)
    assert (copied/record_edits.FILENAME).read_bytes() == (released/record_edits.FILENAME).read_bytes()
    (game/RELATIVE).write_bytes(edited(make_archive(),'iconId',77))
    result = mod_loader.compose_installed(game,[mod_loader.read_mod(copied,'Example')])
    doc = ItemDocument(result.files[RELATIVE])
    assert doc.value('EquipParamGoods',100,'sellValue') == 42
    assert doc.value('EquipParamGoods',100,'iconId') == 77


def test_standalone_startup_isolates_bad_record_anchors_and_reuses_healthy_output(vanilla,tmp_path,monkeypatch):
    from plugins.ds1 import standalone_runtime,tweak_mods
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    game,source = setup_library(tmp_path)
    released = runtime_mods.write_release(source,tmp_path/'release',vanilla,game_root=game)
    broken = released.parent/'broken'
    broken.mkdir()
    (broken/'mod.json').write_text(json.dumps({'id':'broken','name':'Broken','enabled':True}))
    (broken/'runtime.lxd').write_bytes((released/'runtime.lxd').read_bytes())
    bad = record_edits.decode((released/record_edits.FILENAME).read_bytes())
    bad[RELATIVE]['tables'][0]['name'] = 'missing.param'
    (broken/record_edits.FILENAME).write_bytes(record_edits.encode(bad))
    (game/RELATIVE).write_bytes(edited(make_archive(),'iconId',77))
    report = standalone_runtime.run(game,[released.parent])
    assert report['loaded'] == ['example']
    assert [row['id'] for row in report['disabled']] == ['broken']
    assert not json.loads((broken/'mod.json').read_text())['enabled']
    doc = ItemDocument((game/RELATIVE).read_bytes())
    assert doc.value('EquipParamGoods',100,'sellValue') == 42
    assert doc.value('EquipParamGoods',100,'iconId') == 77
    assert standalone_runtime.run(game,[released.parent])['reused']
    (game/standalone_runtime.REPORT).write_bytes(b'broken cache')
    assert standalone_runtime.run(game,[released.parent])['loaded'] == ['example']


@pytest.mark.parametrize('raw', [b'{"version":1,"version":1,"files":{}}',
    b'{"version":1,"files":{"../escape":{}}}',b'{"version":true,"files":{}}'])
def test_malformed_contributions_are_refused(raw):
    with pytest.raises(ValueError):
        record_edits.decode(raw)


def test_duplicate_record_and_missing_table_anchors_are_refused():
    base = make_archive()
    spec = record_edits.create(RELATIVE,base,edited(base,'sellValue',42))
    duplicate = deepcopy(spec)
    duplicate['tables'][0]['rows'] *= 2
    with pytest.raises(ValueError,match='duplicate record ID'):
        record_edits.materialize(RELATIVE,base,duplicate)
    spec['tables'][0]['name'] = 'missing.param'
    with pytest.raises(ValueError,match='table anchor is missing'):
        record_edits.materialize(RELATIVE,base,spec)


def test_imported_portable_mod_renders_added_and_edited_provenance(tmp_path):
    from plugins.ds1.plugin import DS1Session
    from playwright.sync_api import sync_playwright
    game,mod = setup_library(tmp_path)
    store = ItemStore(game,mod,False)
    store.add_row('EquipParamGoods',100,155)
    store.save()
    with DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(mod),
                     'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0'}) as session:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width':1440,'height':900})
                errors = []
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]')
                page.wait_for_function('!document.documentElement.classList.contains("lex-loading-live")')
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.evaluate('navigate("items","consumables","EquipParamGoods:155")')
                page.wait_for_function('state.row?.id===155 && state.rows.some(r=>r.id===155 && r.created)')
                assert page.get_by_role('img',name='Created in this mod',exact=True).count() >= 1
                assert page.get_by_role('img',name='Changed from vanilla',exact=True).count() >= 1
                shot = os.environ.get('LEXEDITOR_PORTABLE_RECORDS_SCREENSHOT')
                if shot:
                    Path(shot).parent.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=shot)
                assert not errors,errors
            finally:
                browser.close()
