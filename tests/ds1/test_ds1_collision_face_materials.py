"""Face topology carries material values even for indistinguishable triangles."""
from copy import deepcopy
import struct

import pytest

from plugins.ds1 import collision_edits,collision_merge,hkx,hkx_write
from plugins.ds1.collision_write import CollisionDocument
from plugins.ds1.formats import FormatError
from plugins.ds1.map_store import MapStore
from test_ds1_collision_write import collision_source
from test_ds1_collision_store import setup,table,mesh
import hkx_fixture


@pytest.fixture
def material_source(collision_source):
    document=CollisionDocument(collision_source)
    first=len(document.entries)
    storage=bytearray(document.data[document.storage[0][1]:document.storage[0][1]+64])
    struct.pack_into('<i',storage,32,first+1)
    struct.pack_into('<i',storage,48,first+2)
    source=hkx_fixture.append_items(collision_source,[
        ('hkpStorageExtendedMeshShape::MeshSubpartStorage',1,storage,[0,16,32,48]),
        ('hkUint8',1,b'\x07',[]),('hkInt16',1,struct.pack('<H',700),[])])
    document=CollisionDocument(source)
    kind,at=document._field(document.shape,'meshstorage')
    ref=hkx._peek_ref(source,document.entries,kind,at)
    source=hkx_write.replace_items(source,{},[(ref[1],struct.pack('<i',first))])
    document=CollisionDocument(source)
    # Identical triangles deliberately have different material identities.
    return document.export({0:{'faces':[[0,1,2],[0,1,2]],'face_sources':[0,0],
        'face_data':{'materialIndices':[7,9],'materialIndices16':[700,900]}}})


def test_face_delete_duplicate_reorder_save_reload_and_compile(material_source,tmp_path):
    game,project,store,_pair=setup(tmp_path,material_source)
    original=deepcopy(mesh(store))
    assert original['materialIndices']==[[7],[9]]
    after=deepcopy(original)
    for name in ('faces','materialIndices','materialIndices16'):
        after[name].pop(0)
        after[name].append(list(after[name][0]))
    store.collisions.replace_mesh(table(store),after)
    store.save()
    again=MapStore(game,project,False)
    assert mesh(again)==after
    raw=CollisionDocument(material_source).export({0:collision_merge._update(original,after)})
    result=collision_merge._mesh(CollisionDocument(raw),0)
    assert result==after and result['materialIndices16']==[[900],[900]]
    reordered=deepcopy(original)
    for name in ('faces','materialIndices','materialIndices16'):reordered[name].reverse()
    spec=collision_edits.create_state(CollisionDocument(material_source),CollisionDocument(material_source),[reordered,collision_merge._mesh(CollisionDocument(material_source),1)])
    _document,values=collision_edits.open_member(material_source,spec)
    assert values[0]==reordered


def test_material_fields_combine_without_becoming_whole_physics_conflicts(material_source):
    base=CollisionDocument(material_source)
    original=collision_merge._mesh(base,0)
    a,b=deepcopy(original),deepcopy(original)
    a['materialIndices'][0][0]=11
    b['materialIndices16'][1][0]=1200
    variants=[base.export({0:collision_merge._update(original,changed)}) for changed in (a,b)]
    output,conflicts=collision_merge.merge(material_source,list(zip(('A','B'),variants)))
    assert not conflicts
    final=collision_merge._mesh(CollisionDocument(output),0)
    assert final['materialIndices']==[[11],[9]] and final['materialIndices16']==[[700],[1200]]


def test_invalid_or_missing_face_materials_leave_saved_geometry_usable(material_source,tmp_path):
    _game,_project,store,_pair=setup(tmp_path,material_source)
    before=deepcopy(mesh(store))
    for mutate in (lambda value:value.pop('materialIndices'),
                   lambda value:value['materialIndices'].pop(),
                   lambda value:value['materialIndices'][0].__setitem__(0,256)):
        invalid=deepcopy(before)
        mutate(invalid)
        with pytest.raises(FormatError):store.collisions.replace_mesh(table(store),invalid)
        assert mesh(store)==before and store.dirty_count==0
