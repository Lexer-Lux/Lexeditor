"""Downloaded collision records preserve foreign installed geometry and isolate failures."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.mod_builds import ModBuildError
from plugins.ds1 import collision_archive, collision_edits, mod_loader, record_edits, runtime_mods, standalone_runtime
from plugins.ds1.collision_write import CollisionDocument
from test_ds1_collision_write import collision_source, split_fixture
from test_ds1_folder_mods import vanilla

HEADER = Path('map/m10_00_00_00/h10_00_00_00.hkxbhd')
BODY = HEADER.with_suffix('.hkxbdt')


def changed_pair(pair, member='h0000a10', *, x=0, y=0, add=False):
    archive = collision_archive.CollisionArchive(*pair)
    document = CollisionDocument(archive.member(member))
    vertices = [row[:3] for row in document.meshes[0]['vertices']]
    vertices[0] = [x,y,vertices[0][2]]
    update = {'vertices':vertices}
    if add:
        update.update(faces=[[0,1,2],[0,1,2]], face_sources=[0,0])
    return archive.replace({member:document.export({0:update})})


def files(pair):
    return dict(zip((HEADER,BODY),pair))


def write_pair(root, pair):
    (root/HEADER).parent.mkdir(parents=True,exist_ok=True)
    for relative, payload in files(pair).items():
        (root/relative).write_bytes(payload)


def coordinates(pair, member='h0000a10'):
    return CollisionDocument(collision_archive.CollisionArchive(*pair).member(member)).meshes[0]['vertices'][0][:3]


def test_portable_collision_preserves_foreign_fields_and_members(collision_source):
    original = split_fixture(collision_source)
    authored = changed_pair(original,x=2)
    specs = record_edits.create_group(files(original),files(authored))
    encoded = record_edits.encode(specs)
    assert BODY not in record_edits.decode(encoded)
    foreign = changed_pair(changed_pair(original,y=5),member='h0001a10',x=10,y=20)
    archive = collision_archive.CollisionArchive(*foreign)
    output = collision_edits.materialize(*foreign,record_edits.decode(encoded)[HEADER])
    assert coordinates(output) == [2,5,0]
    assert collision_archive.CollisionArchive(*output).member('h0001a10') == archive.member('h0001a10')
    assert collision_edits.materialize(*output,specs[HEADER]) == output
    rows = record_edits.describe(specs)
    assert rows[0]['label'] == 'h0000a10, mesh 1'
    assert rows[0]['fields'] == ['Vertices']


def test_foreign_collision_change_to_same_coordinate_is_an_owner_error(collision_source,tmp_path):
    original = split_fixture(collision_source)
    specs = record_edits.create_group(files(original),files(changed_pair(original,x=2)))
    foreign = changed_pair(original,x=9)
    mod = mod_loader.Mod('Collision',tmp_path/'mod',{},specs)
    with pytest.raises(ModBuildError,match='conflicts with installed data') as caught:
        mod_loader.materialize_mod(mod,files(foreign))
    assert caught.value.folders == (mod.folder,)


def test_portable_collision_topology_anchors_only_its_own_mesh(collision_source):
    original = split_fixture(collision_source)
    changed = changed_pair(original,add=True)
    spec = record_edits.create_group(files(original),files(changed))[HEADER]
    assert 'before' in spec['members'][0]['edits']['meshes'][0]
    foreign = changed_pair(original,member='h0001a10',x=13)
    output = collision_edits.materialize(*foreign,spec)
    document = CollisionDocument(collision_archive.CollisionArchive(*output).member('h0000a10'))
    assert len(document.meshes[0]['faces']) == 2
    assert coordinates(output,'h0001a10') == [13,0,0]
    with pytest.raises(ValueError,match='structural edits conflict'):
        collision_edits.materialize(*changed_pair(original,y=5),spec)


@pytest.mark.parametrize('damage', ['duplicate_member','duplicate_field','bool_count','negative_row','bad_coordinate','out_of_range_face'])
def test_corrupt_portable_collision_is_rejected_without_poisoning_valid_record(collision_source,damage):
    original = split_fixture(collision_source)
    valid = record_edits.create_group(files(original),files(changed_pair(original,x=2)))[HEADER]
    invalid = deepcopy(valid)
    mesh = invalid['members'][0]['edits']['meshes'][0]
    if damage == 'duplicate_member':
        invalid['members'] *= 2
    elif damage == 'duplicate_field':
        mesh['fields'] *= 2
    elif damage == 'bool_count':
        mesh['counts'][0] = True
    elif damage == 'negative_row':
        mesh['fields'][0]['row'] = -1
    elif damage == 'bad_coordinate':
        mesh['fields'][0]['after'] = float('nan')
    else:
        mesh['fields'][0].update(kind='faces',row=0,component=0,after=999)
    with pytest.raises(ValueError):
        collision_edits.materialize(*original,invalid)
    assert coordinates(collision_edits.materialize(*original,valid)) == [2,0,0]


def test_portable_collision_unit_rejects_raw_data_duplicate(collision_source,tmp_path):
    original = split_fixture(collision_source)
    specs = record_edits.create_group(files(original),files(changed_pair(original,x=2)))
    mod = mod_loader.Mod('Duplicate',tmp_path,{BODY:original[1]},specs)
    with pytest.raises(ModBuildError,match='Duplicate archive'):
        mod_loader.materialize_mod(mod,files(original))


def test_released_collisions_run_without_builders_on_foreign_baseline(collision_source,vanilla,tmp_path,monkeypatch):
    from plugins.ds1 import composition_cache
    monkeypatch.setattr(composition_cache,'user_root',lambda:tmp_path/'cache')
    original = split_fixture(collision_source)
    authored, game = tmp_path/'author-game',tmp_path/'game'
    library = game/'mods'
    write_pair(authored,original)
    foreign = changed_pair(original,y=5)
    write_pair(game,foreign)
    release_roots = []
    for name,pair in [('first',changed_pair(original,x=2)),
                      ('second',changed_pair(original,member='h0001a10',x=10))]:
        folder = tmp_path/'sources'/name
        write_pair(folder,pair)
        (folder/'mod.json').write_text(json.dumps({'id':name,'name':name}))
        release = runtime_mods.write_release(folder,library,vanilla,game_root=authored)
        assert not (release/HEADER).exists() and not (release/BODY).exists()
        assert HEADER in record_edits.decode(record_edits.read(release/record_edits.FILENAME))
        release_roots.append(release)
        # Exported records, not any author builder, must drive startup.
        (release/'script').mkdir()
        (release/'script/tweak.py').write_text('raise AssertionError("must not execute")')
    broken = library/'broken'
    broken.mkdir()
    (broken/'mod.json').write_text(json.dumps({'id':'broken','name':'Broken','enabled':True}))
    (broken/'runtime.lxd').write_bytes((release_roots[0]/'runtime.lxd').read_bytes())
    (broken/record_edits.FILENAME).write_bytes(record_edits.encode(record_edits.create_group(
        files(original),files(changed_pair(original,y=9)))))
    result = standalone_runtime._run(game,[library],lambda:None)
    assert set(result['loaded']) == {'first','second'}
    assert [row['id'] for row in result['disabled']] == ['broken']
    assert not json.loads((broken/'mod.json').read_text())['enabled']
    final = ((game/HEADER).read_bytes(),(game/BODY).read_bytes())
    assert coordinates(final) == [2,5,0]
    assert coordinates(final,'h0001a10') == [10,0,0]
    assert standalone_runtime._run(game,[library],lambda:None)['reused']
    # A bounded/unavailable optional identity cannot stop healthy loading or
    # make two missing signatures compare equal on the next launch.
    monkeypatch.setattr(standalone_runtime,'MAX_SIGNATURE_BYTES',1)
    for _ in range(2):
        uncached=standalone_runtime._run(game,[library],lambda:None)
        assert set(uncached['loaded'])=={'first','second'}
        assert not uncached.get('reused') and uncached['signature'] is None
    def unavailable(*args):raise PermissionError('signature read unavailable')
    monkeypatch.setattr(standalone_runtime,'_stamp',unavailable)
    assert set(standalone_runtime._run(game,[library],lambda:None)['loaded'])=={'first','second'}


@pytest.mark.parametrize('relative',[HEADER,BODY])
def test_standalone_signature_watches_both_halves_when_only_body_was_written(collision_source,tmp_path,monkeypatch,relative):
    original = split_fixture(collision_source)
    write_pair(tmp_path,original)
    # Reproduce identical metadata deterministically instead of relying on
    # the filesystem clock advancing between two quick writes on Windows.
    stat=Path.stat
    frozen={tmp_path/path:stat(tmp_path/path) for path in (HEADER,BODY)}
    def unchanged_metadata(path,*args,**kwargs):
        return frozen[path] if path in frozen else stat(path,*args,**kwargs)
    monkeypatch.setattr(Path,'stat',unchanged_metadata)
    first = standalone_runtime._identity([],tmp_path,[BODY.as_posix()])
    changed = bytearray((tmp_path/relative).read_bytes())
    changed[-1] ^= 1
    (tmp_path/relative).write_bytes(changed)
    assert standalone_runtime._identity([],tmp_path,[BODY.as_posix()]) != first
