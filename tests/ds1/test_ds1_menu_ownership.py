"""Raw and declarative menu contributions have one baseline and one writer."""
from pathlib import Path
from dataclasses import replace
import json

import pytest

from plugins.ds1 import deployment, esd, formats, menu_scripts, mod_loader, record_edits, tweak_mods
from test_ds1_menu_scripts import ANCHOR, NEW, archive, build_script, command

MANAGED = tweak_mods.ESD_INGAME
RELATIVE = Path(MANAGED.relative)


@pytest.fixture
def menu(tmp_path):
    game = tmp_path/'game'
    base = archive({'fixture.esd':build_script().to_bytes(),'foreign.bin':b'foreign asset'})
    live = game/RELATIVE
    live.parent.mkdir(parents=True)
    live.write_bytes(base)
    spec = menu_scripts.validate({'version':1,'changes':[
        {'archive':'ingame','script':'fixture.esd','after':ANCHOR,'commands':[NEW]}]},'Commands mod')
    raw_script = build_script()
    raw_script.state_groups[0][1].entry_commands = [esd.Command(1,50,[esd.assemble('123')])]
    raw = archive({'fixture.esd':raw_script.to_bytes(),'foreign.bin':b'foreign asset'})
    folder = tmp_path/'mod'
    folder.mkdir()
    (folder/'mod.json').write_text('{"name":"State mod"}')
    return game,base,spec,raw,folder


def plan(game, specs):
    before,original,manifest = tweak_mods.menu_baseline(game,MANAGED)
    return [{'managed':MANAGED,'before':before,'after':menu_scripts.compose(original,specs,'ingame'),
             'mods':['Commands mod'] if specs else [],'project':None,
             'previous':tweak_mods._current_manifest(before,manifest,MANAGED)}]


def write(game, files):
    for item in files:
        tweak_mods._write(game,item['before'],item['after'],item['mods'],item['managed'],
                          inputs=item.get('inputs'))


def script(game):
    plain = formats.inflate((game/RELATIVE).read_bytes())
    entries = formats.members(plain)
    member = entries['fixture.esd']
    assert plain[entries['foreign.bin'].offset:entries['foreign.bin'].offset+entries['foreign.bin'].size] == b'foreign asset'
    return esd.parse(bytes(plain[member.offset:member.offset+member.size]))


@pytest.mark.parametrize('portable',[False,True])
def test_repeated_composition_preserves_both_mods_without_dual_ownership(menu,portable):
    game,base,spec,raw,folder = menu
    mod = (mod_loader.Mod('State mod',folder,{}, {RELATIVE:record_edits.create(RELATIVE,base,raw)})
           if portable else mod_loader.Mod('State mod',folder,{RELATIVE:raw}))
    for _ in range(3):
        files = plan(game,[spec])
        result = mod_loader.compose_installed(game,[mod],menu_files=files)
        assert not result.files and not result.conflicts
        write(game,files)
        states = script(game).state_groups[0]
        assert states[1].entry_commands == [esd.Command(1,50,[esd.assemble('123')])]
        assert command(NEW) in states[0].conditions[0].pass_commands
        assert MANAGED.backup(game).read_bytes() == base
        assert not deployment._marker_path(game,RELATIVE).exists()
        # The generic restorer must not undo the sole menu writer's output.
        deployment.disable(game)
        assert script(game).state_groups[0] == states
    files = plan(game,[])
    mod_loader.compose_installed(game,[],menu_files=files)
    write(game,files)
    assert (game/RELATIVE).read_bytes() == base


def test_raw_only_then_declarative_only_restore_independently(menu):
    game,base,spec,raw,folder = menu
    files = []
    mod_loader.compose_installed(game,[mod_loader.Mod('State mod',folder,{RELATIVE:raw})],menu_files=files)
    assert len(files) == 1
    write(game,files)
    files = plan(game,[spec])
    mod_loader.compose_installed(game,[],menu_files=files)
    write(game,files)
    assert script(game).state_groups[0][1].entry_commands == []
    assert command(NEW) in script(game).state_groups[0][0].conditions[0].pass_commands
    assert MANAGED.backup(game).read_bytes() == base


def legacy_data_marker(game,base,raw,folder):
    MANAGED.backup(game).write_bytes(base)
    (game/RELATIVE).write_bytes(raw)
    deployment._write_marker(deployment._marker_path(game,RELATIVE),{
        'schema':1,'modId':deployment.MOD_ID,'originalHash':tweak_mods._sha(base),
        'activeHash':tweak_mods._sha(raw),'activeProjectRoot':str(folder),'enabled':True,
        'sourceHash':tweak_mods._sha(raw),'pendingHash':None,'pendingKind':None,'appliedAt':None})


@pytest.mark.parametrize('dual',[False,True])
def test_legacy_journals_transfer_without_writing_game_bytes(menu,dual):
    game,base,spec,raw,folder = menu
    if dual:
        write(game,plan(game,[spec]))
    legacy_data_marker(game,base,raw,folder)
    tweak_mods.claim_menu_files(game)
    assert (game/RELATIVE).read_bytes() == raw
    assert not deployment._marker_path(game,RELATIVE).exists()
    assert tweak_mods._original(game,*tweak_mods._installed(game,MANAGED,'untouched'),MANAGED) == base
    # Repeating transfer is idempotent, and a future composition can restore.
    tweak_mods.claim_menu_files(game)
    write(game,plan(game,[]))
    assert (game/RELATIVE).read_bytes() == base


def test_migration_preserves_unknown_live_bytes_and_both_journals(menu):
    game,base,spec,raw,folder = menu
    write(game,plan(game,[spec]))
    legacy_data_marker(game,base,raw,folder)
    before = MANAGED.manifest(game).read_bytes()
    outsider = b'external change'
    (game/RELATIVE).write_bytes(outsider)
    with pytest.raises(tweak_mods.TweakError,match='outside its recorded writers'):
        tweak_mods.claim_menu_files(game)
    assert (game/RELATIVE).read_bytes() == outsider
    assert MANAGED.manifest(game).read_bytes() == before
    assert deployment._marker_path(game,RELATIVE).is_file()
    assert MANAGED.backup(game).read_bytes() == base


def test_restore_migrates_a_legacy_raw_menu_even_without_native_runtime(menu,monkeypatch):
    game,base,_spec,raw,folder = menu
    legacy_data_marker(game,base,raw,folder)
    executable = replace(tweak_mods.EXECUTABLE,vanilla=lambda data:data==b'fixture exe')
    monkeypatch.setattr(tweak_mods,'EXECUTABLE',executable)
    executable.live(game).write_bytes(b'fixture exe')
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    tweak_mods.restore(game)
    assert (game/RELATIVE).read_bytes() == base
    assert executable.live(game).read_bytes() == b'fixture exe'
    assert not deployment._marker_path(game,RELATIVE).exists()


def test_generic_writer_refuses_menu_before_writing_other_targets(menu):
    game,base,_spec,raw,folder = menu
    with pytest.raises(ValueError,match='shared menu deployment plan'):
        deployment.apply(game,folder,composed={RELATIVE:raw,Path('event/new.emevd'):b'invalid'})
    assert (game/RELATIVE).read_bytes() == base
    assert not MANAGED.backup(game).exists()


def test_writer_rejects_corrupt_combined_output_before_backup_or_journal(menu):
    game,base,_spec,_raw,_folder = menu
    with pytest.raises(tweak_mods.TweakError,match='composed.*invalid'):
        tweak_mods._write(game,base,b'corrupt cached menu',['Bad cache'],MANAGED)
    assert (game/RELATIVE).read_bytes() == base
    assert not MANAGED.backup(game).exists()
    assert not MANAGED.manifest(game).exists()


def contributors(menu):
    game,base,spec,raw,folder = menu
    (folder/RELATIVE).parent.mkdir(parents=True)
    (folder/RELATIVE).write_bytes(raw)
    commands = folder.parent/'commands'
    (commands/'esd').mkdir(parents=True)
    (commands/'mod.json').write_text('{"name":"Commands mod"}')
    (commands/'esd/menu.json').write_text(json.dumps({'version':1,'changes':[
        {'archive':'ingame','script':'fixture.esd','after':ANCHOR,'commands':[NEW]}]}))
    return [{'id':path.name,'name':name,'path':path,'enabled':True,'prebuilt':True}
            for name,path in [('State mod',folder),('Commands mod',commands)]]


def test_standalone_full_startup_reuses_then_independently_removes_contributions(menu,monkeypatch):
    from plugins.ds1 import standalone_runtime
    game,base,_spec,_raw,_folder = menu
    rows = contributors(menu)
    monkeypatch.setattr(standalone_runtime,'discover',lambda *_:rows)
    first = standalone_runtime._run(game,[],lambda:None)
    assert not first.get('reused') and not first['disabled']
    assert command(NEW) in script(game).state_groups[0][0].conditions[0].pass_commands
    assert script(game).state_groups[0][1].entry_commands
    assert standalone_runtime._run(game,[],lambda:None)['reused']
    rows.pop(0)
    assert not standalone_runtime._run(game,[],lambda:None).get('reused')
    assert script(game).state_groups[0][1].entry_commands == []
    assert command(NEW) in script(game).state_groups[0][0].conditions[0].pass_commands
    rows.clear()
    standalone_runtime._run(game,[],lambda:None)
    assert (game/RELATIVE).read_bytes() == base


def test_standalone_isolates_corrupt_raw_menu_without_disabling_healthy_commands(menu,monkeypatch):
    from plugins.ds1 import standalone_runtime
    game,_base,_spec,_raw,folder = menu
    rows = contributors(menu)
    (folder/RELATIVE).write_bytes(archive({'fixture.esd':b'broken script'}))
    monkeypatch.setattr(standalone_runtime,'discover',lambda *_:rows)
    result = standalone_runtime._run(game,[],lambda:None)
    assert [row['id'] for row in result['disabled']] == [folder.name]
    assert command(NEW) in script(game).state_groups[0][0].conditions[0].pass_commands
    assert script(game).state_groups[0][1].entry_commands == []


def test_editor_activation_and_later_data_failure_roll_back_menu(menu,monkeypatch):
    from core import mods_service
    from plugins.ds1 import mod_support
    game,base,spec,_raw,folder = menu
    rows = contributors(menu)
    adapter = mod_support.Ds1ModAdapter()
    adapter.attach_context(library_root=folder.parent)
    monkeypatch.setattr(adapter,'_report_path',lambda:folder.parent/'report.json')
    monkeypatch.setattr(mods_service,'library_rows',lambda *_:[{**row,'path':str(row['path'])} for row in rows])
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    monkeypatch.setattr(tweak_mods,'prepare',lambda *_args,**_kwargs:{'files':plan(game,[spec])})
    monkeypatch.setattr(tweak_mods,'commit',lambda root,p:write(root,p['files']))
    monkeypatch.setattr(tweak_mods,'rollback',lambda root,p:tweak_mods._undo(root,p['files']))
    for _ in range(2):
        adapter.activate([row['path'] for row in rows],game)
        assert command(NEW) in script(game).state_groups[0][0].conditions[0].pass_commands
        assert script(game).state_groups[0][1].entry_commands
    before = (game/RELATIVE).read_bytes()
    # Change a raw state so the next menu result differs. Fail a separate
    # data deployment after that menu commits, then verify complete rollback.
    changed = build_script()
    changed.state_groups[0][1].entry_commands = [esd.Command(1,51,[])]
    (folder/RELATIVE).write_bytes(archive({'fixture.esd':changed.to_bytes(),'foreign.bin':b'foreign asset'}))
    (game/'menu/sibling.bin').write_bytes(b'original sibling')
    (folder/'menu/sibling.bin').write_bytes(b'changed sibling')
    def failed(*_args,**_kwargs):
        raise OSError('later data failure')
    monkeypatch.setattr(deployment,'apply',failed)
    with pytest.raises(OSError,match='later data failure'):
        adapter.activate([row['path'] for row in rows],game)
    assert (game/RELATIVE).read_bytes() == before
    assert MANAGED.backup(game).read_bytes() == base
    assert not deployment._marker_path(game,RELATIVE).exists()
