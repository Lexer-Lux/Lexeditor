"""Animation records combine without losing opaque events or native metadata."""
import struct
import sys
import json
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tae_fixture import build_tae, build_anibnd
from plugins.ds1.tae import TaeDocument, TaeError
from plugins.ds1 import tae_merge, mod_loader
from plugins.ds1.formats import inflate, deflate, members
from test_ds1_tweak_recovery import game
from test_ds1_exe_patches import VANILLA


def variants():
    vanilla = build_tae()
    first, second = TaeDocument(vanilla), TaeDocument(vanilla)
    first.remove_event(0, 3)
    first.edit(0, 0, 'judge', 123)
    opaque = first.anims[0]['events'][2]
    struct.pack_into('<I', first.plain, opaque['data_off']+8, 0x12345678)
    second.add_event(1, 66, .1, .7, {'effect': 42})
    return vanilla, first.export(), second.export()


def added(source, judge=17, key=3400):
    doc = TaeDocument(source)
    data = bytearray(source)
    header = len(data)
    data += bytes(28)
    file = len(data)
    name = b'a\0d\0d\0e\0d\0\0\0'
    data += struct.pack('<6I', 0, file+8, file+24, 0, 0xffffffff, 456)
    data += name
    data += bytes(-len(data) % 4)
    struct.pack_into('<7I', data, header, 0, 0, 0, 0, 0, 0, file)
    locations = {a['id']:a['offset'] for a in doc.anims} | {key:header}
    directory = len(data)
    for key in sorted(locations):
        data += struct.pack('<2I', key, locations[key])
    groups = len(data)
    ranges = tae_merge._ranges(sorted(locations), directory)
    data += struct.pack('<2I',len(ranges),groups+8)
    data += b''.join(struct.pack('<3I',*row) for row in ranges)
    struct.pack_into('<3I', data, 84, len(locations), directory, groups)
    struct.pack_into('<2I', data, 100, len(locations), locations[min(locations)])
    struct.pack_into('<I', data, 12, len(data))
    out = TaeDocument(bytes(data))
    index = next(a['index'] for a in out.anims if a['offset']==header)
    out.add_event(index, 1, .2, .5, {'attackType':0,'attackIndex':0,'judge':judge})
    return out.export()


def test_independent_animation_changes_relocate_events_and_preserve_unknown_payloads():
    vanilla, a, b = variants()
    combined, collisions = tae_merge.compose(vanilla, [('A', a), ('B', b)])
    assert collisions == []
    result = TaeDocument(combined)
    assert result.anims[1]['name'] == 'animation 3301'
    assert [len(anim['events']) for anim in result.anims] == [3, 1]
    assert result.read_event(0, 0)['fields'][-1]['value'] == 123
    assert result.read_event(1, 0)['fields'][-1]['value'] == 42
    opaque = result.anims[0]['events'][2]
    assert struct.unpack_from('<I', combined, opaque['data_off']+8)[0] == 0x12345678
    assert tae_merge._records(combined)[1] == {
        3300: tae_merge._records(a)[1][3300], 3301: tae_merge._records(b)[1][3301]}


def test_same_animation_conflicts_choose_last_and_identical_edits_do_not_conflict():
    vanilla, a, b = variants()
    c = TaeDocument(vanilla)
    c.edit(0, 0, 'judge', 999)
    result, collisions = tae_merge.compose(vanilla, [('A', a), ('B', b), ('C', c.export())])
    assert collisions == [('animation 3300', ['A', 'C'])]
    assert TaeDocument(result).read_event(0, 0)['fields'][-1]['value'] == 999
    assert tae_merge.compose(vanilla, [('A', a), ('B', a)])[1] == []
    assert tae_merge.compose(vanilla, [('A', vanilla)]) == (vanilla, [])


@pytest.mark.parametrize('offset', [32, 80, 168])
def test_uninterpreted_metadata_changes_refuse(offset):
    vanilla, a, _ = variants()
    changed = bytearray(a)
    changed[offset] ^= 1
    with pytest.raises(TaeError):
        tae_merge.compose(vanilla, [('changed', bytes(changed))])


def test_anibnd_composer_uses_animation_records_and_reports_actual_collisions():
    vanilla, a, b = variants()
    binder = lambda data: build_anibnd({'a87.tae': data})
    original = binder(vanilla)
    combined, collisions = mod_loader._compose_anibnd(
        original, [('A', binder(a)), ('B', binder(b))], Path('chr/c0000.anibnd.dcx'))
    assert collisions == []
    plain = inflate(combined)
    entry = members(plain)['a87.tae']
    assert [len(a['events']) for a in TaeDocument(plain[entry.offset:entry.offset+entry.size]).anims] == [3, 1]
    c = TaeDocument(vanilla)
    c.edit(0, 0, 'judge', 9)
    _, collisions = mod_loader._compose_anibnd(
        original, [('A', binder(a)), ('C', binder(c.export()))], Path('chr/c0000.anibnd.dcx'))
    assert len(collisions) == 1
    assert collisions[0].part == 'a87.tae/animation 3300'


@pytest.mark.parametrize('key',[100,3400])
def test_added_animation_keeps_geometry_name_and_events_alongside_existing_edits(key):
    vanilla, a, _ = variants()
    b = added(vanilla,key=key)
    result, conflicts = tae_merge.compose(vanilla,[('A',a),('B',b)])
    assert conflicts == []
    doc = TaeDocument(result)
    new = next(anim for anim in doc.anims if anim['id']==key)
    assert new['name']=='added'
    assert doc.read_event(new['index'],0)['fields'][-1]['value']==17
    descriptor = struct.unpack_from('<I',result,new['offset']+24)[0]
    assert struct.unpack_from('<I',result,descriptor+20)[0]==456
    original = next(anim for anim in doc.anims if anim['id']==3300)
    assert len(original['events'])==3
    assert struct.unpack_from('<I',result,104)[0]==doc.anims[0]['offset']
    _, conflicts = tae_merge.compose(vanilla,[('A',b),('B',added(vanilla,18,key))])
    assert conflicts == [(f'animation {key}',['A','B'])]


def test_directory_growth_keeps_independent_animation_records_and_native_member_order():
    from plugins.ds1 import texts
    vanilla,a,b = variants()
    def binder(data,extra=False):
        source = build_anibnd({'a87.tae':data,'skeleton.hkx':b'skeleton'})
        plain = inflate(source)
        entries = [replace(entry,member_id=100000 if entry.name.endswith('.hkx') else 87)
                   for entry in texts.bnd3_entries(plain)]
        if extra:
            entries.append(replace(entries[0],member_id=88,name='a88.tae',data=vanilla))
        return deflate(source,texts.build_bnd3(plain,entries))
    result,conflicts = mod_loader._compose_anibnd(binder(vanilla),
        [('A',binder(a)),('B',binder(b,True))],Path('chr/c0000.anibnd.dcx'))
    assert not conflicts
    plain = inflate(result)
    entries = texts.bnd3_entries(plain)
    assert [entry.member_id for entry in entries] == [87,88,100000]
    entry = next(entry for entry in entries if entry.name.endswith('a87.tae'))
    assert [len(anim['events']) for anim in TaeDocument(entry.data).anims] == [3,1]


def test_exported_folder_mods_merge_animation_records_without_author_builders(game,tmp_path,monkeypatch):
    from plugins.ds1 import runtime_mods,standalone_runtime,composition_cache
    monkeypatch.setattr(composition_cache,'user_root',lambda:tmp_path/'cache')
    root,library,_built = game
    vanilla,a,b = variants()
    relative = Path('chr/c0000.anibnd.dcx')
    (root/relative).parent.mkdir()
    (root/relative).write_bytes(build_anibnd({'a87.tae':vanilla}))
    for name,data in [('first',a),('second',b)]:
        folder = library/name
        (folder/relative).parent.mkdir(parents=True)
        (folder/relative).write_bytes(build_anibnd({'a87.tae':data}))
        (folder/'mod.json').write_text(json.dumps({'id':name,'name':name,'enabled':True}))
        exported = runtime_mods.write_release(folder,tmp_path/'release',VANILLA,game_root=root)
        assert not (exported/'script').exists()
    report = standalone_runtime._run(root,[tmp_path/'release'],lambda:None)
    assert report['loaded'] == ['first','second'] and not report['disabled']
    plain = inflate((root/relative).read_bytes())
    entry = members(plain)['a87.tae']
    assert [len(anim['events']) for anim in TaeDocument(plain[entry.offset:entry.offset+entry.size]).anims] == [3,1]
    assert standalone_runtime._run(root,[tmp_path/'release'],lambda:None)['reused']
