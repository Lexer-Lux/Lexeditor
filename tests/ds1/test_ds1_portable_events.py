"""Portable events preserve other authors' records and use shared composition."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from plugins.ds1 import formats,mod_loader,record_edits,runtime_mods,standalone_runtime,tweak_mods
from plugins.ds1.store import ItemStore,RELATIVE
from ds1_fixture import make_archive
from test_ds1_editor_failure_boundaries import event_fixture
from test_ds1_folder_mods import vanilla
from test_ds1_portable_records import setup_library

EVENT = Path('event/common.emevd')


def variant(document,call,identity):
    from plugins.ds1 import emevd
    constructor = replace(document.events[0],instructions=document.events[0].instructions+(call(identity,identity),))
    return replace(document,events=(constructor,*document.events[1:],
                   emevd.Event(identity,(emevd.Instruction(2003,1,str(identity).encode()),))))


@pytest.mark.parametrize('wrapped',[False,True])
def test_portable_events_keep_foreign_constructor_calls_records_and_pools(wrapped):
    emevd,base,call = event_fixture()
    ours,foreign = variant(base,call,1001),variant(base,call,1002)
    foreign = replace(foreign,linked=foreign.linked+(7,),strings=foreign.strings+b'foreign\0')
    wrap = lambda doc:formats.deflate(make_archive(),emevd.write(doc)) if wrapped else emevd.write(doc)
    spec = record_edits.create(EVENT,wrap(base),wrap(ours))
    output = record_edits.materialize(EVENT,wrap(foreign),spec)
    result = emevd.read(formats.inflate(output) if wrapped else output)
    by_id = {event.id:event for event in result.events}
    assert set(by_id) == {0,100,1001,1002}
    assert call(1001,1001) in by_id[0].instructions and call(1002,1002) in by_id[0].instructions
    assert by_id[100] == base.events[1]  # layers, arguments and substitutions
    assert result.linked == foreign.linked and result.strings == foreign.strings
    assert [row['id'] for row in spec['rows']] == [0,1001]


def test_conflicting_event_anchor_is_refused_without_changing_the_input():
    emevd,base,_call = event_fixture()
    ours = replace(base,events=(base.events[0],replace(base.events[1],rest=2)))
    foreign = replace(base,events=(base.events[0],replace(base.events[1],rest=0)))
    raw = emevd.write(foreign)
    spec = record_edits.create(EVENT,emevd.write(base),emevd.write(ours))
    with pytest.raises(ValueError,match='Event 100.*conflicts'):
        record_edits.materialize(EVENT,raw,spec)
    assert emevd.read(raw) == foreign


def test_pool_changes_that_cannot_relocate_opaque_arguments_are_refused():
    emevd,base,call = event_fixture()
    ours = variant(base,call,1001)
    with pytest.raises(ValueError,match='string/link changes'):
        record_edits.create(EVENT,emevd.write(base),emevd.write(replace(ours,strings=b'changed\0')))
    spec = record_edits.create(EVENT,emevd.write(base),emevd.write(ours))
    with pytest.raises(ValueError,match='pool anchor'):
        record_edits.materialize(EVENT,emevd.write(replace(base,strings=b'changed\0')),spec)


def event_library(tmp_path):
    game,mod = setup_library(tmp_path)
    emevd,base,call = event_fixture()
    (game/EVENT).parent.mkdir(parents=True)
    (game/EVENT).write_bytes(emevd.write(base))
    return game,mod,emevd,base,call


def test_export_unifies_existing_parameter_edits_and_new_events(vanilla,tmp_path):
    game,mod,emevd,base,call = event_library(tmp_path)
    (mod/EVENT).parent.mkdir(parents=True)
    (mod/EVENT).write_bytes(emevd.write(variant(base,call,1001)))
    released = runtime_mods.write_release(mod,tmp_path/'release',vanilla,game_root=game)
    assert not (released/EVENT).exists() and not (released/RELATIVE).exists()
    declared = record_edits.decode((released/record_edits.FILENAME).read_bytes())
    assert set(declared) == {EVENT,RELATIVE}
    described = mod_loader.describe_changes(released,game)['changes']
    assert any(change['id']==1001 and change['added'] and change['table'].startswith('Events') for change in described)
    (game/EVENT).write_bytes(emevd.write(variant(base,call,1002)))
    composition = mod_loader.compose_installed(game,[mod_loader.read_mod(released,'Example')])
    assert {event.id for event in emevd.read(composition.files[EVENT]).events} == {0,100,1001,1002}
    assert formats.ItemDocument(composition.files[RELATIVE]).value('EquipParamGoods',100,'sellValue') == 42


def test_item_save_keeps_other_portable_event_contributions(tmp_path):
    game,mod,emevd,base,call = event_library(tmp_path)
    declared = record_edits.decode((mod/record_edits.FILENAME).read_bytes())
    declared[EVENT] = record_edits.create(EVENT,emevd.write(base),emevd.write(variant(base,call,1001)))
    (mod/record_edits.FILENAME).write_bytes(record_edits.encode(declared))
    store = ItemStore(game,mod,False)
    store.edit('EquipParamGoods',100,'sellValue',43)
    store.save()
    after = record_edits.decode((mod/record_edits.FILENAME).read_bytes())
    assert after[EVENT] == declared[EVENT] and after[RELATIVE] != declared[RELATIVE]
    assert not (mod/EVENT).exists()


def test_missing_event_disables_its_owner_and_keeps_healthy_mods(vanilla,tmp_path,monkeypatch):
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    game,source,emevd,base,call = event_library(tmp_path)
    (source/EVENT).parent.mkdir(parents=True)
    (source/EVENT).write_bytes(emevd.write(variant(base,call,1001)))
    released = runtime_mods.write_release(source,tmp_path/'release',vanilla,game_root=game)
    broken = released.parent/'broken'
    broken.mkdir()
    (broken/'mod.json').write_text(json.dumps({'id':'broken','name':'Broken','enabled':True}))
    (broken/'runtime.lxd').write_bytes((released/'runtime.lxd').read_bytes())
    changed = replace(base,events=(base.events[0],replace(base.events[1],rest=2)))
    bad = record_edits.create(EVENT,emevd.write(base),emevd.write(changed))
    (broken/record_edits.FILENAME).write_bytes(record_edits.encode({EVENT:bad}))
    # The foreign mod removed the event only Broken needs to edit.
    (game/EVENT).write_bytes(emevd.write(replace(base,events=base.events[:1])))
    report = standalone_runtime.run(game,[released.parent])
    assert report['loaded'] == ['example']
    assert [row['id'] for row in report['disabled']] == ['broken']
    assert {event.id for event in emevd.read((game/EVENT).read_bytes()).events} == {0,1001}


def test_event_targets_invalidate_installed_editor_cache(tmp_path,monkeypatch):
    from plugins.ds1.mod_support import Ds1ModAdapter
    game,mod,emevd,base,call = event_library(tmp_path)
    declared = record_edits.decode((mod/record_edits.FILENAME).read_bytes())
    declared[EVENT] = record_edits.create(EVENT,emevd.write(base),emevd.write(variant(base,call,1001)))
    (mod/record_edits.FILENAME).write_bytes(record_edits.encode(declared))
    adapter = Ds1ModAdapter()
    monkeypatch.setattr(adapter,'_report_path',lambda:tmp_path/'report.json')
    ordered = [('Example',mod)]
    adapter._save_report(game,ordered,[],installed=True)
    assert adapter._read_report(game,ordered) is not None
    (game/EVENT).write_bytes(emevd.write(variant(base,call,1002)))
    assert adapter._read_report(game,ordered) is None
    assert set(record_edits.targets(mod/record_edits.FILENAME)) == {RELATIVE,EVENT}


def test_malformed_event_records_are_attributed_to_their_mod(tmp_path):
    game,mod,emevd,base,call = event_library(tmp_path)
    spec = record_edits.create(EVENT,emevd.write(base),emevd.write(variant(base,call,1001)))
    spec['rows'][0]['after'] = 'invalid base64'
    (mod/record_edits.FILENAME).write_bytes(record_edits.encode({EVENT:spec}))
    from core.mod_builds import ModBuildError
    with pytest.raises(ModBuildError) as error:
        mod_loader.compose_installed(game,[mod_loader.read_mod(mod,'Example')])
    assert error.value.folders == (mod,)


def test_damaged_installed_event_is_not_attributed_to_a_healthy_mod(tmp_path):
    game,mod,emevd,base,call = event_library(tmp_path)
    spec = record_edits.create(EVENT,emevd.write(base),emevd.write(variant(base,call,1001)))
    (mod/record_edits.FILENAME).write_bytes(record_edits.encode({EVENT:spec}))
    (game/EVENT).write_bytes(b'damaged game file')
    with pytest.raises(formats.FormatError):
        mod_loader.compose_installed(game,[mod_loader.read_mod(mod,'Example')])
    assert json.loads((mod/'mod.json').read_text())['enabled']


def test_target_index_rejects_oversized_paths_before_caching_them(tmp_path):
    records = tmp_path/record_edits.FILENAME
    records.write_text(json.dumps({'version':1,'files':{'event/'+('a'*600)+'.emevd':{}}}))
    with pytest.raises(ValueError,match='path is too long'):
        record_edits.targets(records)
