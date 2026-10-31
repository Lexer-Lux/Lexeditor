"""Portable talk/character state edits share the editor's structural merger."""
from copy import deepcopy
from pathlib import Path
import json
import os
import sys

import pytest

from plugins.ds1 import esd,formats,mod_loader,record_edits,script_edits,texts,runtime_mods,standalone_runtime,tweak_mods
from test_ds1_talk_composition import fixture,command
from test_ds1_menu_scripts import archive
from test_ds1_folder_mods import vanilla
from test_ds1_portable_records import setup_library

LOOSE = Path('chr/c0000.esd.dcx')
BINDER = Path('script/talk/test.talkesdbnd.dcx')


@pytest.mark.parametrize('wrapped',[False,True])
@pytest.mark.parametrize('long_format',[False,True])
def test_state_edits_preserve_foreign_conditions_states_and_metadata(wrapped,long_format):
    base = fixture()
    base.long_format = long_format
    ours,foreign = deepcopy(base),deepcopy(base)
    ours.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('7')
    foreign.state_groups[1][0].conditions[0].target_state = 0
    foreign.state_groups[1][333] = esd.State(333,entry_commands=[command(50,2)])
    foreign.name = 'Foreign metadata'
    def data(document):
        raw = document.to_bytes()
        return formats.deflate(archive({'seed.esd':raw}),raw) if wrapped else raw
    spec = record_edits.create(LOOSE,data(base),data(ours))
    output = record_edits.materialize(LOOSE,data(foreign),record_edits.decode(record_edits.encode({LOOSE:spec}))[LOOSE])
    result = script_edits.parse(output)
    assert result.state_groups[1][1] == ours.state_groups[1][1]
    assert result.state_groups[1][0] == foreign.state_groups[1][0]
    assert result.state_groups[1][333] == foreign.state_groups[1][333]
    assert result.name == foreign.name and result.long_format == long_format
    assert [state['id'] for state in spec['groups'][0]['states']] == [1]


def test_edited_state_can_keep_cross_state_transition_targets():
    base,ours = fixture(),fixture()
    ours.state_groups[1][0].entry_commands.append(command(19,723,15000723,-1))
    spec = script_edits.create(base.to_bytes(),ours.to_bytes())
    assert [row['id'] for row in spec['groups'][0]['states']] == [0]
    result = script_edits.parse(script_edits.materialize(base.to_bytes(),spec))
    assert result == ours and result.state_groups[1][0].conditions[0].target_state == 1


def test_same_argument_conflict_is_refused():
    base,ours,foreign = fixture(),fixture(),fixture()
    ours.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('1')
    foreign.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('2')
    spec = script_edits.create(base.to_bytes(),ours.to_bytes())
    with pytest.raises(ValueError,match='state edit conflicts'):
        script_edits.materialize(foreign.to_bytes(),spec)


def test_independent_talk_insertions_and_removals_keep_both_authors():
    base,ours,foreign = fixture(),fixture(),fixture()
    ours.state_groups[1][0].entry_commands.append(command(19,723,15000723,-1))
    foreign.state_groups[1][0].entry_commands.pop()
    spec = script_edits.create(base.to_bytes(),ours.to_bytes())
    result = script_edits.parse(script_edits.materialize(foreign.to_bytes(),spec))
    assert result.state_groups[1][0].entry_commands == [command(19,9,15000005,-1),command(19,723,15000723,-1)]


def test_removing_a_group_cannot_drop_foreign_states():
    base,ours,foreign = fixture(),fixture(),fixture()
    ours.state_groups.clear()
    foreign.state_groups[1][9] = esd.State(9)
    spec = script_edits.create(base.to_bytes(),ours.to_bytes())
    with pytest.raises(ValueError,match='discard installed states'):
        script_edits.materialize(foreign.to_bytes(),spec)


def test_added_groups_can_share_a_foreign_group_without_dropping_states():
    base,ours,foreign = fixture(),fixture(),fixture()
    ours.state_groups[2] = {10:esd.State(10)}
    foreign.state_groups[2] = {11:esd.State(11)}
    spec = script_edits.create(base.to_bytes(),ours.to_bytes())
    result = script_edits.parse(script_edits.materialize(foreign.to_bytes(),spec))
    assert set(result.state_groups[2]) == {10,11}


def repack(original,replace_members=None,*,remove=(),add=()):
    plain = formats.inflate(original)
    base_name = lambda name:name.replace('\\','/').rsplit('/',1)[-1]
    entries = [texts.Entry(e.member_id,e.name,e.flags,(replace_members or {}).get(base_name(e.name),e.data))
               for e in texts.bnd3_entries(plain) if base_name(e.name) not in remove]
    return formats.deflate(original,texts.build_bnd3(plain,entries+list(add)))


def test_binder_edits_keep_unrelated_members_and_foreign_script_changes():
    base,ours,foreign = fixture(),fixture(),fixture()
    ours.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('7')
    foreign.state_groups[1][0].conditions[0].target_state = 0
    original = archive({'bonfire.esd':base.to_bytes(),'keep.bin':b'old','remove.bin':b'remove'})
    authored = repack(original,{'bonfire.esd':ours.to_bytes()},remove=('remove.bin',),
                      add=(texts.Entry(99,'added.esd',0x40,fixture().to_bytes()),))
    installed = repack(original,{'bonfire.esd':foreign.to_bytes(),'keep.bin':b'foreign'},
                       add=(texts.Entry(100,'foreign.bin',0x40,b'foreign addition'),))
    spec = record_edits.create(BINDER,original,authored)
    result = record_edits.materialize(BINDER,installed,spec)
    entries = {entry.name.replace('\\','/').rsplit('/',1)[-1]:entry for entry in texts.bnd3_entries(formats.inflate(result))}
    assert set(entries) == {'bonfire.esd','keep.bin','added.esd','foreign.bin'}
    assert entries['keep.bin'].data == b'foreign' and entries['foreign.bin'].data == b'foreign addition'
    script = esd.parse(entries['bonfire.esd'].data)
    assert script.state_groups[1][0] == foreign.state_groups[1][0]
    assert script.state_groups[1][1] == ours.state_groups[1][1]


def test_binder_opaque_member_conflicts_do_not_clobber_installed_bytes():
    original = archive({'bonfire.esd':fixture().to_bytes(),'keep.bin':b'old'})
    spec = record_edits.create(BINDER,original,repack(original,{'keep.bin':b'ours'}))
    installed = repack(original,{'keep.bin':b'foreign'})
    with pytest.raises(ValueError,match='member anchor conflicts'):
        record_edits.materialize(BINDER,installed,spec)


def test_invalid_state_records_are_bounded_and_typed():
    base,ours = fixture(),fixture()
    ours.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('1')
    spec = script_edits.create(base.to_bytes(),ours.to_bytes())
    spec['groups'][0]['states'][0]['after']['id'] = True
    with pytest.raises(ValueError,match='integer'):
        script_edits.materialize(base.to_bytes(),spec)


def test_removed_state_cannot_leave_a_foreign_transition_dangling():
    base,ours,foreign = fixture(),fixture(),fixture()
    ours.state_groups[1][0].conditions[0].target_state = 0
    del ours.state_groups[1][1]
    foreign.state_groups[1][3] = esd.State(3,conditions=[esd.Condition(1,esd.assemble('1'))])
    spec = script_edits.create(base.to_bytes(),ours.to_bytes())
    with pytest.raises(ValueError,match='target state is missing'):
        script_edits.materialize(foreign.to_bytes(),spec)


def test_exported_binder_uses_records_and_bad_state_only_disables_its_owner(vanilla,tmp_path,monkeypatch):
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    game,source = setup_library(tmp_path)
    base,ours,broken,foreign = fixture(),fixture(),fixture(),fixture()
    ours.state_groups[1][0].entry_commands.append(command(19,723,15000723,-1))
    broken.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('2')
    foreign.state_groups[1][0].conditions[0].target_state = 0
    del foreign.state_groups[1][1]
    original = archive({'bonfire.esd':base.to_bytes()})
    (game/BINDER).parent.mkdir(parents=True)
    (game/BINDER).write_bytes(original)
    (source/BINDER).parent.mkdir(parents=True)
    (source/BINDER).write_bytes(archive({'bonfire.esd':ours.to_bytes()}))
    released = runtime_mods.write_release(source,tmp_path/'release',vanilla,game_root=game)
    assert not (released/BINDER).exists()
    declared = record_edits.decode((released/record_edits.FILENAME).read_bytes())
    assert declared[BINDER]['kind'] == 'binder'
    bad_folder = released.parent/'broken'
    bad_folder.mkdir()
    (bad_folder/'mod.json').write_text(json.dumps({'id':'broken','name':'Broken','enabled':True}))
    (bad_folder/'runtime.lxd').write_bytes((released/'runtime.lxd').read_bytes())
    bad = record_edits.create(BINDER,original,archive({'bonfire.esd':broken.to_bytes()}))
    (bad_folder/record_edits.FILENAME).write_bytes(record_edits.encode({BINDER:bad}))
    (game/BINDER).write_bytes(archive({'bonfire.esd':foreign.to_bytes()}))
    report = standalone_runtime.run(game,[released.parent])
    assert report['loaded'] == ['example'] and [row['id'] for row in report['disabled']] == ['broken']
    plain = formats.inflate((game/BINDER).read_bytes())
    member = formats.members(plain)['bonfire.esd']
    result = esd.parse(plain[member.offset:member.offset+member.size])
    assert result.state_groups[1][0].entry_commands[-1] == command(19,723,15000723,-1)
    assert result.state_groups[1][0].conditions[0].target_state == 0
    assert 1 not in result.state_groups[1]
    assert standalone_runtime.run(game,[released.parent])['reused']


def test_shared_records_view_renders_actual_portable_state_changes(tmp_path):
    from playwright.sync_api import sync_playwright
    from core import mods_service
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root/'tests/shared'))
    from test_mods_tab import HOST
    game,source = setup_library(tmp_path)
    base,ours = fixture(),fixture()
    ours.state_groups[1][1].entry_commands[0].args[0] = esd.assemble('7')
    (game/BINDER).parent.mkdir(parents=True)
    original = archive({'bonfire.esd':base.to_bytes()})
    (game/BINDER).write_bytes(original)
    declared = record_edits.decode((source/record_edits.FILENAME).read_bytes())
    declared[BINDER] = record_edits.create(BINDER,original,archive({'bonfire.esd':ours.to_bytes()}))
    (source/record_edits.FILENAME).write_bytes(record_edits.encode(declared))
    contents = mods_service.mod_files(source)
    contents.update(mod_loader.describe_changes(source,game),canDescribe=True)
    loaded = set(mod_loader.loaded_files(source))
    for row in contents['files']:
        row['loaded'] = row['relative'].casefold() in loaded
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width':1440,'height':900})
            errors = []
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('http://fixture/**',lambda route:route.fulfill(body='<main id="main"></main>',content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(root/'ui/framework.css'))
            page.add_script_tag(path=str(root/'ui/framework.js'))
            page.evaluate('value=>window.__modContents=value',contents)
            page.evaluate(HOST,{'firstRun':False})
            page.locator('[data-tab="mods"]').click()
            page.locator('.lex-mods-page').wait_for()
            page.locator('[data-subtab="records"]').click()
            page.get_by_text('State 1/1',exact=True).wait_for()
            assert page.get_by_text('Entry commands',exact=True).is_visible()
            shot = os.environ.get('LEXEDITOR_SCRIPT_RECORDS_SCREENSHOT')
            if shot:
                Path(shot).parent.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=shot)
            assert not errors,errors
        finally:
            browser.close()
