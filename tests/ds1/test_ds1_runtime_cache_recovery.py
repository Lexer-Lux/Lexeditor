"""Disposable runtime state cannot prevent healthy folder contributions loading."""
import hashlib
import json

import pytest

from plugins.ds1 import exe_patches, standalone_runtime, tweak_mods
from test_ds1_tweak_recovery import game
from test_ds1_exe_patches import VANILLA, HOOK_A


@pytest.mark.parametrize('damage',[b'{', b'[]', b'\xff', b'{"version":1}', b'['*1100])
def test_broken_runtime_record_does_not_block_editor_rebuild(game,damage):
    root,library,_ = game
    (root/exe_patches.EXECUTABLE).write_bytes(VANILLA)
    tweak_mods._write_runtime(root,b'',[],None,library=library)
    (root/tweak_mods.RUNTIME_RECORD).write_bytes(damage)
    assert 'legacy Project' in tweak_mods._runtime_status(root)['problem']
    result = tweak_mods.apply(root,library)
    assert result['state'] == 'tweaked'
    # Recovery must not erase the warning about an unavailable project-only
    # contribution just because folder mods now have a fresh cache.
    assert 'legacy Project' in result['problem']
    assert tweak_mods._runtime(root)['active']
    assert (root/exe_patches.EXECUTABLE).read_bytes() == VANILLA


def test_corrupt_record_does_not_let_the_editor_replace_a_foreign_loader(game):
    root,library,_ = game
    (root/exe_patches.EXECUTABLE).write_bytes(VANILLA)
    (root/tweak_mods.RUNTIME_RECORD).write_bytes(b'{')
    dll = root/tweak_mods.RUNTIME_DLL
    dll.write_bytes(b'another loader')
    with pytest.raises(tweak_mods.TweakError,match="Another mod's"):
        tweak_mods.apply(root,library)
    assert dll.read_bytes() == b'another loader'


def test_valid_looking_cache_cannot_claim_ownership_of_a_foreign_dll(game):
    root,library,_ = game
    dll = root/tweak_mods.RUNTIME_DLL
    dll.write_bytes(b'another loader')
    record = {'version':1,'mods':[],'project':None,'patchSha256':hashlib.sha256(b'').hexdigest(),
              'dllSha256':hashlib.sha256(dll.read_bytes()).hexdigest()}
    (root/tweak_mods.RUNTIME_RECORD).write_text(json.dumps(record))
    (root/tweak_mods.RUNTIME_PATCH).write_bytes(b'')
    assert tweak_mods._runtime(root)['foreignDll']
    tweak_mods.restore(root,library)
    assert dll.read_bytes() == b'another loader'


def test_matching_hash_does_not_turn_a_broken_patch_into_a_valid_rollback(game):
    root,library,_ = game
    tweak_mods._write_runtime(root,b'',[],None,library=library)
    broken = b'LXD1PAT\0'+b'\x01\x00\x00\x00'*4
    (root/tweak_mods.RUNTIME_PATCH).write_bytes(broken)
    path = root/tweak_mods.RUNTIME_RECORD
    record = json.loads(path.read_text())
    record['patchSha256'] = hashlib.sha256(broken).hexdigest()
    path.write_text(json.dumps(record))
    runtime = tweak_mods._runtime(root)
    assert not runtime['active'] and runtime['patch'] is None and runtime['problem']


@pytest.mark.parametrize('damage',[b'{',b'[]',b'\xff',b'['*1100])
def test_standalone_loads_healthy_data_and_reports_damaged_runtime_record(game,monkeypatch,damage):
    root,library,built = game
    good = library/'good'
    good.mkdir();(good/'mod.json').write_text('{"id":"good","name":"Good","enabled":true}')
    (root/'menu').mkdir();(good/'menu').mkdir()
    (root/'menu/example.bin').write_bytes(b'original data')
    (good/'menu/example.bin').write_bytes(b'healthy data')
    (root/tweak_mods.RUNTIME_RECORD).write_bytes(damage)
    rows = [{'id':'good','name':'Good','path':good,'enabled':True,'prebuilt':True}]
    monkeypatch.setattr(standalone_runtime,'discover',lambda *_:rows)
    report = standalone_runtime._run(root,[],lambda:None)
    assert report['loaded'] == ['good'] and not report['disabled']
    assert 'legacy Project' in report['warnings'][0]
    assert (root/'menu/example.bin').read_bytes() == b'healthy data'
    assert (root/exe_patches.EXECUTABLE).read_bytes() == built
    # Reuse keeps the warning, and a second metadata change invalidates reuse.
    assert standalone_runtime._run(root,[],lambda:None)['reused']
    (root/tweak_mods.RUNTIME_RECORD).write_bytes(b'{"version":0}')
    assert not standalone_runtime._run(root,[],lambda:None).get('reused')


def test_bad_shared_patch_preserves_valid_legacy_project_recipe(game,monkeypatch):
    root,library,_ = game
    (root/exe_patches.EXECUTABLE).write_bytes(VANILLA)
    spec = {'version':1,'hooks':[{'rva':HOOK_A,'original':'e800000000','bytes':'9090909090'}]}
    project = {'path':str(library/'project'),'settingsHash':hashlib.sha256(b'settings').hexdigest(),'spec':spec}
    patch = exe_patches.runtime_patch(VANILLA,[exe_patches.validate(spec,'Project native rules')])
    tweak_mods._write_runtime(root,patch,[],project,library=library)
    (root/tweak_mods.RUNTIME_PATCH).write_bytes(b'broken shared patch')
    monkeypatch.setattr(tweak_mods,'build_specs',lambda *_args,**_kwargs:[])
    monkeypatch.setattr(tweak_mods,'loader_mod_state',lambda *_:(True,True))
    plan = tweak_mods.prepare(root,library)
    assert plan['runtime']['project'] == project
    assert plan['runtime']['previous']['patch'] is None
    assert exe_patches.read_runtime_patch(plan['runtime']['patch'])['records']
    tweak_mods.commit(root,plan)
    assert tweak_mods._runtime(root)['active']
    assert not tweak_mods._runtime_status(root)['problem']


def test_oversized_runtime_record_is_not_read(game,monkeypatch):
    root,_library,_ = game
    record = root/tweak_mods.RUNTIME_RECORD
    record.write_bytes(b'large')
    monkeypatch.setattr(tweak_mods,'MAX_MANIFEST',4)
    original = type(record).open
    def guarded(self,*args,**kwargs):
        assert self != record, 'An oversized record must be rejected before opening'
        return original(self,*args,**kwargs)
    monkeypatch.setattr(type(record),'open',guarded)
    value,warning = tweak_mods.runtime_record(root)
    assert value is None and warning
