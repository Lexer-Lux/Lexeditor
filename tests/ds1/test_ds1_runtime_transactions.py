"""Native installation restores exact known files, not a reconstructed recipe."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from plugins.ds1 import exe_patches,tweak_mods
from test_ds1_tweak_recovery import game
from test_ds1_exe_patches import VANILLA,HOOK_A

NAMES = (tweak_mods.RUNTIME_DLL,tweak_mods.RUNTIME_PATCH,tweak_mods.RUNTIME_CONFIG,
         tweak_mods.RUNTIME_RECORD,tweak_mods.RUNTIME_LOG)
BUILD_SPECS = tweak_mods.build_specs


@pytest.fixture
def installed(game,monkeypatch):
    root,library,_ = game
    monkeypatch.setenv(tweak_mods.MODS_ENV,str(library))
    (root/exe_patches.EXECUTABLE).write_bytes(VANILLA)
    from core import mods_service
    mods_service.set_enabled(tweak_mods.ensure_loader_mod(library),True)
    monkeypatch.setattr(tweak_mods,'build_specs',lambda *_args,**_kwargs:[])
    spec = {'version':1,'hooks':[{'rva':HOOK_A,'original':'e800000000','bytes':'9090909090'}]}
    old = {'path':str(root.parent/'external-project'),'settingsHash':hashlib.sha256(b'old settings').hexdigest(),'spec':spec}
    patch = exe_patches.runtime_patch(VANILLA,[exe_patches.validate(spec,'Old project')])
    tweak_mods._write_runtime(root,patch,['Old project'],old,library=library)
    # A previously shipped debug loader and opaque metadata extensions must
    # survive rollback byte-for-byte, even while Apply targets the online DLL.
    dll = tweak_mods.loader_bytes(debug=True)
    (root/tweak_mods.RUNTIME_DLL).write_bytes(dll)
    record_path = root/tweak_mods.RUNTIME_RECORD
    record = json.loads(record_path.read_bytes())
    record.update(dllSha256=hashlib.sha256(dll).hexdigest(),extension={'keep':'exactly'})
    record_path.write_text(json.dumps(record,indent=4)+'\n')
    (root/tweak_mods.RUNTIME_CONFIG).write_bytes(b'[Mods]\r\nLibrary=previous\r\n[Custom]\r\nkeep=yes\r\n')
    (root/tweak_mods.RUNTIME_LOG).write_bytes(b'previous diagnostics')
    new = {**old,'settingsHash':hashlib.sha256(b'new settings').hexdigest(),
           'spec':{'version':1,'hooks':[{'rva':HOOK_A,'original':'e800000000','bytes':'cccccccccc'}]}}
    after = exe_patches.runtime_patch(VANILLA,[exe_patches.validate(new['spec'],'New project')])
    assert tweak_mods._runtime(root)['active']
    return root,library,old,new,after


def files(root):
    return {name:(root/name).read_bytes() if (root/name).exists() else None for name in NAMES}


def source_mod(game,monkeypatch,*,scripted=True):
    from test_ds1_tweak_mods import SPECS,TWEAK,enable_loader
    root,library,_ = game
    monkeypatch.setattr(tweak_mods,'build_specs',BUILD_SPECS)
    monkeypatch.setenv(tweak_mods.MODS_ENV,str(library))
    (root/exe_patches.EXECUTABLE).write_bytes(VANILLA)
    folder = library/'alpha';folder.mkdir()
    metadata = {'id':'alpha','name':'Alpha','enabled':True}
    if scripted:
        metadata['script'] = {'version':1}
        (folder/'script').mkdir();(folder/'script/__init__.py').touch()
        (folder/'script/tweak.py').write_text(TWEAK % ('alpha',repr(SPECS['alpha'])))
    (folder/'mod.json').write_text(json.dumps(metadata))
    enable_loader(library)
    return root,library,folder


@pytest.mark.parametrize('oversized',[False,True])
def test_corrupt_generated_module_cache_rebuilds_without_disabling_source_mod(game,monkeypatch,oversized):
    from plugins.ds1 import runtime_mods
    root,library,folder = source_mod(game,monkeypatch)
    target = folder/runtime_mods.FILENAME
    with target.open('wb') as stream:
        if oversized:
            stream.truncate(runtime_mods.MAX_SIZE+1)
        else:
            stream.write(b'damaged generated module')
    plan = tweak_mods.prepare(root,library)
    tweak_mods.commit(root,plan)
    assert runtime_mods.inspect(runtime_mods.read(folder))['records']
    assert json.loads((folder/'mod.json').read_text())['enabled'] is True
    assert not tweak_mods.needs_rebuild(root,library)['needed']


def test_oversized_opaque_module_is_attributed_to_its_owner(game,monkeypatch):
    from plugins.ds1 import runtime_mods
    root,library,folder = source_mod(game,monkeypatch,scripted=False)
    with (folder/runtime_mods.FILENAME).open('wb') as stream:
        stream.truncate(runtime_mods.MAX_SIZE+1)
    with pytest.raises(tweak_mods.TweakError,match='size') as caught:
        tweak_mods.prepare(root,library)
    assert list(caught.value.folders) == [folder]
    assert not (root/tweak_mods.RUNTIME_DLL).exists()


def test_module_that_grows_after_prepare_is_not_read_or_falsely_rolled_back(game,monkeypatch):
    from plugins.ds1 import runtime_mods
    root,library,folder = source_mod(game,monkeypatch)
    plan = tweak_mods.prepare(root,library)
    target = folder/runtime_mods.FILENAME
    with target.open('wb') as stream:
        stream.truncate(runtime_mods.MAX_SIZE+1)
    original = Path.open
    def bounded(path,*args,**kwargs):
        assert path != target or not args or args[0] != 'rb','The oversized module must not be read'
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',bounded)
    with pytest.raises(tweak_mods.TweakError,match='prebuilt mod changed') as caught:
        tweak_mods.commit(root,plan)
    assert 'rollback failed' not in str(caught.value)
    assert target.stat().st_size == runtime_mods.MAX_SIZE+1
    assert not (root/tweak_mods.RUNTIME_DLL).exists()


@pytest.mark.parametrize('name',NAMES[:4])
@pytest.mark.parametrize('after_write',[False,True])
def test_install_failure_at_every_phase_restores_exact_previous_files(installed,monkeypatch,name,after_write):
    root,library,old,new,patch = installed
    before = files(root)
    atomic,failed = tweak_mods.atomic_write,False
    def interrupted(path,data):
        nonlocal failed
        if Path(path).name == name and not failed:
            failed = True
            if after_write:
                atomic(path,data)
            raise OSError('injected runtime write failure')
        return atomic(path,data)
    monkeypatch.setattr(tweak_mods,'atomic_write',interrupted)
    with pytest.raises(OSError,match='injected runtime'):
        tweak_mods._write_runtime(root,patch,['New project'],new,library=library)
    assert files(root) == before
    assert tweak_mods.runtime_record(root)[0]['project'] == old


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('after_remove',[False,True])
def test_removal_failure_restores_every_previous_runtime_file(installed,monkeypatch,name,after_remove):
    root,library,_old,_new,_patch = installed
    before = files(root)
    unlink,failed = Path.unlink,False
    def interrupted(path,*args,**kwargs):
        nonlocal failed
        if path == root/name and not failed:
            failed = True
            if after_remove:
                unlink(path,*args,**kwargs)
            raise OSError('injected runtime removal failure')
        return unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',interrupted)
    with pytest.raises(OSError,match='runtime removal'):
        tweak_mods._write_runtime(root,None,[],None,library=library)
    assert files(root) == before


def test_later_data_failure_restores_exact_previous_native_generation(installed):
    root,library,_old,new,_patch = installed
    before = files(root)
    plan = tweak_mods.prepare(root,library,project=lambda _:new)
    tweak_mods.commit(root,plan)
    assert files(root) != before
    tweak_mods.rollback(root,plan)
    assert files(root) == before


def test_later_failure_does_not_lose_a_valid_project_recipe_when_old_patch_was_bad(installed):
    root,library,old,_new,_patch = installed
    (root/tweak_mods.RUNTIME_PATCH).write_bytes(b'previous damaged cache')
    before = files(root)
    plan = tweak_mods.prepare(root,library)
    assert plan['runtime']['project'] == old
    tweak_mods.commit(root,plan)
    tweak_mods.rollback(root,plan)
    assert files(root) == before
    assert tweak_mods.runtime_record(root)[0]['project'] == old
    assert tweak_mods.needs_rebuild(root,library)['needed']


@pytest.mark.parametrize('name',[tweak_mods.RUNTIME_RECORD,tweak_mods.RUNTIME_PATCH,tweak_mods.RUNTIME_DLL])
def test_missing_runtime_component_is_reported_as_needing_rebuild(installed,name):
    root,library,_old,_new,_patch = installed
    (root/name).unlink()
    assert tweak_mods.needs_rebuild(root,library)['needed']
    assert not tweak_mods._runtime(root)['active']


@pytest.mark.parametrize('phase',NAMES[:4])
def test_abrupt_termination_rebuilds_shared_patch_and_preserves_committed_selection(installed,phase):
    from ds1_fixture import make_archive
    from plugins.ds1 import standalone_runtime
    from plugins.ds1.formats import ItemDocument
    from plugins.ds1.store import RELATIVE
    root,library,old,new,patch = installed
    target = root/RELATIVE
    target.parent.mkdir(parents=True);target.write_bytes(make_archive())
    healthy = library/'healthy'
    (healthy/RELATIVE).parent.mkdir(parents=True)
    (healthy/'mod.json').write_text('{"id":"healthy","name":"Healthy","enabled":true}')
    document = ItemDocument(target.read_bytes());document.edit('EquipParamGoods',100,'sellValue',63)
    (healthy/RELATIVE).write_bytes(document.export())
    request = root.parent/'interruption.json'
    request.write_text(json.dumps({'patch':patch.hex(),'project':new}))
    result = subprocess.run([sys.executable,str(Path(__file__).with_name('runtime_interruption_worker.py')),
        str(root),str(library),phase,str(request)],capture_output=True,text=True,timeout=15,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert result.returncode == 37,result
    chosen = new if phase == tweak_mods.RUNTIME_RECORD else old
    assert tweak_mods.runtime_record(root)[0]['project'] == chosen
    report = standalone_runtime._run(root,[library],lambda:None)
    assert report['loaded'] == ['healthy'] and not report['disabled']
    assert ItemDocument(target.read_bytes()).value('EquipParamGoods',100,'sellValue') == 63
    decoded = exe_patches.read_runtime_patch((root/tweak_mods.RUNTIME_PATCH).read_bytes())
    hook = next(row for row in decoded['records'] if row[0] == exe_patches.HOOK)
    assert hook[3][hook[2]:] == bytes.fromhex(chosen['spec']['hooks'][0]['bytes'])
    # A subsequent editor Apply also repairs the interrupted DLL/record pair.
    tweak_mods.apply(root,library)
    assert tweak_mods._runtime(root)['active']
    assert tweak_mods.runtime_record(root)[0]['project'] == chosen
    assert (root/exe_patches.EXECUTABLE).read_bytes() == VANILLA


@pytest.mark.parametrize('delete',[False,True])
def test_external_change_during_rollback_is_preserved_and_other_files_restore(installed,delete):
    root,library,_old,new,_patch = installed
    before = files(root)
    plan = tweak_mods.prepare(root,library,project=lambda _:new)
    tweak_mods.commit(root,plan)
    config = root/tweak_mods.RUNTIME_CONFIG
    if delete:
        config.unlink()
    else:
        config.write_bytes(b'an external configuration change')
    with pytest.raises(tweak_mods.TweakError,match='changed during runtime rollback'):
        tweak_mods.rollback(root,plan)
    assert not config.exists() if delete else config.read_bytes() == b'an external configuration change'
    for name in NAMES:
        if name != tweak_mods.RUNTIME_CONFIG:
            assert (root/name).read_bytes() == before[name]


def test_runtime_change_after_prepare_is_not_overwritten(installed):
    root,library,_old,new,_patch = installed
    plan = tweak_mods.prepare(root,library,project=lambda _:new)
    (root/tweak_mods.RUNTIME_CONFIG).write_bytes(b'external change before commit')
    before = files(root)
    with pytest.raises(tweak_mods.TweakError,match='changed while the mods were being prepared'):
        tweak_mods.commit(root,plan)
    assert files(root) == before


def test_failed_replacement_restores_a_file_that_had_to_be_moved_aside(installed,monkeypatch):
    root,_library,_old,_new,_patch = installed
    before = files(root)
    def denied(*_args,**_kwargs):
        raise PermissionError('injected pinned file')
    monkeypatch.setattr(tweak_mods,'atomic_write',denied)
    with pytest.raises(PermissionError,match='pinned file'):
        tweak_mods._put(root,root/tweak_mods.RUNTIME_DLL,b'new DLL bytes')
    assert files(root) == before


def test_oversized_patch_rollback_keeps_valid_project_metadata_and_requires_rebuild(installed,monkeypatch):
    root,library,old,new,patch = installed
    target = root/tweak_mods.RUNTIME_PATCH
    with target.open('wb') as stream:
        stream.truncate(tweak_mods.MAX_RUNTIME+1)
    original_open,atomic = Path.open,tweak_mods.atomic_write
    def bounded(path,*args,**kwargs):
        if path == target and args and args[0] == 'rb':
            assert path.stat().st_size <= tweak_mods.MAX_RUNTIME, 'An oversized cache must not be read'
        return original_open(path,*args,**kwargs)
    failed = False
    def interrupted(path,data):
        nonlocal failed
        if Path(path).name == tweak_mods.RUNTIME_RECORD and not failed:
            failed = True
            raise OSError('record failure')
        return atomic(path,data)
    monkeypatch.setattr(Path,'open',bounded)
    monkeypatch.setattr(tweak_mods,'atomic_write',interrupted)
    with pytest.raises(OSError,match='record failure'):
        tweak_mods._write_runtime(root,patch,['New project'],new,library=library)
    assert tweak_mods.runtime_record(root)[0]['project'] == old
    assert target.stat().st_size < 100
    assert tweak_mods._runtime(root)['problem']
    assert tweak_mods.needs_rebuild(root,library)['needed']


@pytest.mark.parametrize('phase',['data','menu','loader'])
def test_restore_failure_preserves_data_menus_and_loader_as_one_operation(installed,monkeypatch,phase):
    from ds1_fixture import make_archive
    from plugins.ds1 import deployment,esd
    from plugins.ds1.formats import ItemDocument
    from plugins.ds1.native_rules import NativeRules
    from plugins.ds1.store import RELATIVE,MARKER
    from test_ds1_menu_scripts import archive,build_script
    root,library,_old,_new,_patch = installed
    baseline = make_archive()
    target = root/RELATIVE
    target.parent.mkdir(parents=True);target.write_bytes(baseline)
    project = root.parent/'data-project';(project/RELATIVE).parent.mkdir(parents=True)
    (project/MARKER).touch();(project/'mod.json').write_text('{"name":"Data project"}')
    document = ItemDocument(baseline);document.edit('EquipParamGoods',100,'sellValue',57)
    (project/RELATIVE).write_bytes(document.export())
    deployment.apply(root,project)
    managed = tweak_mods.ESD_INGAME
    menu_base = archive({'fixture.esd':build_script().to_bytes()})
    changed = build_script();changed.state_groups[0][1].entry_commands = [esd.Command(1,50,[esd.assemble('123')])]
    menu_mod = archive({'fixture.esd':changed.to_bytes()})
    managed.live(root).parent.mkdir(parents=True,exist_ok=True)
    managed.live(root).write_bytes(menu_base)
    tweak_mods._write(root,menu_base,menu_mod,['Menu mod'],managed)
    from test_ds1_menu_ownership import legacy_data_marker
    legacy_data_marker(root,menu_base,menu_mod,project)
    before = files(root)
    data_before = target.read_bytes()
    rules = NativeRules(root,project,False)
    failed = False
    atomic,copy,unlink = tweak_mods.atomic_write,deployment._atomic_copy,Path.unlink
    def fail_data(source,destination):
        nonlocal failed
        if phase == 'data' and destination == target and not failed:
            failed = True
            copy(source,destination)
            raise OSError('restore data failure')
        return copy(source,destination)
    def fail_menu(path,content):
        nonlocal failed
        if phase == 'menu' and Path(path) == managed.live(root) and not failed:
            failed = True
            raise OSError('restore menu failure')
        return atomic(path,content)
    def fail_loader(path,*args,**kwargs):
        nonlocal failed
        if phase == 'loader' and path == root/tweak_mods.RUNTIME_CONFIG and not failed:
            failed = True
            raise OSError('restore loader failure')
        return unlink(path,*args,**kwargs)
    monkeypatch.setattr(deployment,'_atomic_copy',fail_data)
    monkeypatch.setattr(tweak_mods,'atomic_write',fail_menu)
    monkeypatch.setattr(Path,'unlink',fail_loader)
    with pytest.raises(OSError,match='restore .* failure'):
        rules.restore()
    assert target.read_bytes() == data_before
    assert managed.live(root).read_bytes() == menu_mod
    assert files(root) == before
    assert not deployment._marker_path(root,Path(managed.relative)).exists()
    rules.restore()
    assert target.read_bytes() == baseline
    assert managed.live(root).read_bytes() == menu_base
    assert not (root/tweak_mods.RUNTIME_DLL).exists()
    assert (root/exe_patches.EXECUTABLE).read_bytes() == VANILLA
