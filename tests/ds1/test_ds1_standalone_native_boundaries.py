"""Native artifacts and shared-support conflicts cannot stop healthy data."""
import json
import struct
from pathlib import Path

import pytest

from plugins.ds1 import exe_patches,menu_dim,runtime_mods,standalone_runtime,tweak_mods
from test_ds1_exe_patches import VANILLA,HOOK_A,HOOK_B
from test_ds1_tweak_recovery import game


@pytest.fixture
def world(game,monkeypatch):
    root,library,_ = game
    monkeypatch.setenv(tweak_mods.MODS_ENV,str(library))
    (root/exe_patches.EXECUTABLE).write_bytes(VANILLA)
    healthy = mod(library,'healthy')
    (root/'menu').mkdir();(healthy/'menu').mkdir()
    (root/'menu/fixture.bin').write_bytes(b'original')
    (healthy/'menu/fixture.bin').write_bytes(b'healthy mod')
    return root,library


def mod(library,name):
    folder = library/name;folder.mkdir()
    (folder/'mod.json').write_text(json.dumps({'id':name,'name':name,'enabled':True}))
    return folder


def raw_spec(hook=HOOK_A):
    original = 'e800000000' if hook == HOOK_A else '488d1500000000'
    return {'version':1,'hooks':[{'rva':hook,'original':original,'bytes':'90'*(len(original)//2)}]}


def module(folder,hook=HOOK_A):
    payload = runtime_mods.build(VANILLA,[exe_patches.validate(raw_spec(hook),folder.name)])
    (folder/runtime_mods.FILENAME).write_bytes(payload)
    return payload


@pytest.mark.parametrize('damage',['short','crc','size'])
def test_bad_native_only_payload_is_disabled_and_healthy_data_still_loads(world,damage):
    root,library = world
    bad = mod(library,'bad')
    payload = bytearray(module(bad))
    if damage == 'short':
        (bad/runtime_mods.FILENAME).write_bytes(b'broken')
    elif damage == 'crc':
        payload[-1] ^= 1
        (bad/runtime_mods.FILENAME).write_bytes(payload)
    else:
        with (bad/runtime_mods.FILENAME).open('wb') as stream:
            stream.truncate(runtime_mods.MAX_SIZE+1)
    report = standalone_runtime._run(root,[library],lambda:None)
    assert [row['id'] for row in report['disabled']] == ['bad']
    assert report['loaded'] == ['healthy']
    assert (root/'menu/fixture.bin').read_bytes() == b'healthy mod'
    assert json.loads((bad/'mod.json').read_text())['enabled'] is False


def test_cached_readiness_cannot_hide_a_new_movable_module_conflict(world):
    root,library = world
    support = mod(library,'support');(support/'native-support').mkdir()
    (support/'native-support/support.json').write_text(json.dumps(raw_spec(HOOK_B)))
    opaque = mod(library,'opaque');module(opaque,HOOK_A)
    assert not runtime_mods.inspect(runtime_mods.read(opaque))['fixed']
    first = standalone_runtime._run(root,[library],lambda:None)
    assert set(first['loaded']) == {'healthy','support'}
    assert standalone_runtime._run(root,[library],lambda:None)['reused']
    module(opaque,HOOK_B)
    report = standalone_runtime._run(root,[library],lambda:None)
    assert not report.get('reused')
    assert [row['id'] for row in report['disabled']] == ['support']
    assert report['loaded'] == ['healthy']
    assert (root/tweak_mods.RUNTIME_PATCH).read_bytes() == b''


def test_aggregate_support_conflict_names_its_contributor_and_keeps_healthy_data(world,monkeypatch):
    root,library = world
    dim = mod(library,'dim');(dim/menu_dim.FOLDER).mkdir()
    (dim/menu_dim.FOLDER/'options.json').write_text('{"version":1,"textIds":[100]}')
    opaque = mod(library,'opaque');module(opaque,HOOK_B)
    monkeypatch.setattr(menu_dim,'patch_spec',lambda specs:raw_spec(HOOK_B) if specs else None)
    report = standalone_runtime._run(root,[library],lambda:None)
    assert [row['id'] for row in report['disabled']] == ['dim']
    assert report['loaded'] == ['healthy']


def test_component_local_island_names_do_not_depend_on_display_name(world):
    _root,_library = world
    specs = []
    for hook,value in ((HOOK_A,42),(HOOK_B,77)):
        original = 'e800000000' if hook == HOOK_A else '488d1500000000'
        raw = {'version':1,'islands':[{'name':'payload','code':f'b8{value:02x}000000c3'}],
               'hooks':[{'rva':hook,'original':original,'pad':'90'*((len(original)//2)-5),
                         'branch':{'opcode':'E8','island':'payload'}}]}
        specs.append(exe_patches.validate(raw,'Same display name'))
    data = runtime_mods.inspect(runtime_mods.build(VANILLA,specs))
    block = next(row for row in data['records'] if row[0] == exe_patches.BLOCK)
    for hook,value in ((HOOK_A,42),(HOOK_B,77)):
        record = next(row for row in data['records'] if row[0] == exe_patches.HOOK and row[1] == hook)
        destination = hook+5+struct.unpack_from('<i',record[3],record[2]+1)[0]
        assert block[3][destination-block[1]:destination-block[1]+6] == bytes.fromhex(f'b8{value:02x}000000c3')


def test_combined_source_hook_conflict_is_attributed(world):
    _root,library = world
    first,second = mod(library,'first'),mod(library,'second')
    specs = [exe_patches.validate(raw_spec(),'Same name') for _ in range(2)]
    for spec,folder in zip(specs,(first,second)):
        spec['folder'] = str(folder)
    with pytest.raises(exe_patches.PatchError,match='both patch') as caught:
        exe_patches._layout(VANILLA,specs)
    assert list(caught.value.folders) == [str(second)]


def test_cached_readiness_cannot_hide_new_native_corruption(world):
    root,library = world
    bad = mod(library,'bad');module(bad)
    standalone_runtime._run(root,[library],lambda:None)
    assert standalone_runtime._run(root,[library],lambda:None)['reused']
    (bad/runtime_mods.FILENAME).write_bytes(b'broken')
    report = standalone_runtime._run(root,[library],lambda:None)
    assert [row['id'] for row in report['disabled']] == ['bad']
    assert (root/'menu/fixture.bin').read_bytes() == b'healthy mod'


def test_sparse_fixed_island_is_rejected_before_allocating_its_span(world):
    _root,library = world
    folder = mod(library,'sparse')
    spec = exe_patches.validate({'version':1,'islands':[
        {'name':'far away','rva':0x70000000,'code':'c3'}]},'sparse')
    spec['folder'] = str(folder)
    with pytest.raises(exe_patches.PatchError,match='size limit') as caught:
        runtime_mods.build(VANILLA,[spec])
    assert list(caught.value.folders) == [str(folder)]


def test_repaired_native_only_mod_does_not_retain_a_stale_disabled_report(world):
    root,library = world
    bad = mod(library,'bad');(bad/runtime_mods.FILENAME).write_bytes(b'broken')
    assert standalone_runtime._run(root,[library],lambda:None)['disabled']
    module(bad)
    metadata = bad/'mod.json'
    metadata.write_text(json.dumps({'id':'bad','name':'bad','enabled':True}))
    report = standalone_runtime._run(root,[library],lambda:None)
    assert report['reused']
    assert not report['disabled']
    assert not json.loads((root/standalone_runtime.REPORT).read_text())['disabled']


@pytest.mark.parametrize('key,value',[('targets',None),('loaded',{}),('disabled',[None]),
                                      ('warnings',42),('conflicts',[{}])])
def test_malformed_cached_report_is_discarded(world,key,value):
    root,library = world
    standalone_runtime._run(root,[library],lambda:None)
    path = root/standalone_runtime.REPORT
    prior = json.loads(path.read_text());prior[key] = value
    path.write_text(json.dumps(prior))
    report = standalone_runtime._run(root,[library],lambda:None)
    assert not report.get('reused')
    assert report['loaded'] == ['healthy']


@pytest.mark.parametrize('same_folder',[False,True])
def test_state_ownership_uses_mod_identity_instead_of_display_name(world,same_folder):
    _root,library = world
    first,second = mod(library,'first'),mod(library,'second')
    raw = {'version':1,'sectionVirtualSize':{'.data':0x180},'state':[{'rva':0x2100,'size':16}]}
    specs = [exe_patches.validate(raw,'Same display name') for _ in range(2)]
    specs[0]['folder'] = str(first)
    specs[1]['folder'] = str(first if same_folder else second)
    if same_folder:
        assert runtime_mods.build(VANILLA,specs)
    else:
        with pytest.raises(exe_patches.PatchError,match='both keep state') as caught:
            runtime_mods.build(VANILLA,specs)
        assert list(caught.value.folders) == [str(second)]


def test_legacy_project_conflict_identifies_the_opaque_mod(world):
    _root,library = world
    opaque = mod(library,'opaque')
    payload = module(opaque)
    project = exe_patches.validate(raw_spec(),'Legacy project')
    with pytest.raises(exe_patches.PatchError) as caught:
        runtime_mods.shared_patch(VANILLA,[project],[{'folder':str(opaque),'data':payload}])
    assert list(caught.value.folders) == [str(opaque)]


def test_combined_native_module_budget_is_attributed_without_stopping_healthy_data(world,monkeypatch):
    root,library = world
    first,second = mod(library,'first'),mod(library,'second')
    payload = module(first);module(second,HOOK_B)
    monkeypatch.setattr(runtime_mods,'MAX_TOTAL_SIZE',len(payload))
    report = standalone_runtime._run(root,[library],lambda:None)
    assert [row['id'] for row in report['disabled']] == ['second']
    assert report['loaded'] == ['healthy']
