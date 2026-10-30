"""Old collision storage uses packed xyz vertices and three-index faces."""
from copy import deepcopy
import struct

import pytest

from plugins.ds1 import collision_edits,collision_merge,hkx,map_collision
from plugins.ds1.collision_write import CollisionDocument
from test_ds1_collision_write import query
from test_ds1_collision_store import setup,MAP,table


@pytest.fixture
def legacy_source(monkeypatch):
    import hkx_fixture as fixture
    extra=[('prim','T*',8,hkx.PTR),('array','A_Ptr','T*'),('array','A_Float','float'),
      ('array','A_LegacyPart','hkpMeshShape::Subpart'),
      ('class','hkpMeshShape::Subpart',80,[('vertexStriding',8,'hkInt32'),('numVertices',12,'hkInt32'),
        ('indexStriding',28,'hkInt32'),('flipAlternateTriangles',32,'hkInt32'),('numTriangles',36,'hkInt32'),('triangleOffset',72,'hkInt32')]),
      ('class','hkpStorageMeshShape::SubpartStorage',112,[('vertices',16,'A_Float'),('indices16',32,'A_i16'),
        ('indices32',48,'A_u32'),('materialIndices',64,'A_u8'),('materialIndices16',96,'A_i16')]),
      ('class','CustomMeshParameter',72,[('version',16,'hkUint32'),('vertexDataBuffer',24,'A_u8'),
        ('vertexDataStride',40,'hkInt32'),('primitiveDataBuffer',48,'A_u8'),('materialNameData',64,'hkUint32')]),
      ('class','hkpMoppCode::CodeInfo',16,[('offset',0,'hkVector4f')]),
      ('class','hkpMoppCode',32,[('info',0,'hkpMoppCode::CodeInfo'),('data',16,'A_u8')]),
      ('class','CustomParamStorageMeshShape',160,[('scaling',48,'hkVector4f'),('numBitsForSubpartIndex',64,'hkInt32'),
        ('subparts',72,'A_LegacyPart'),('weldingInfo',88,'A_i16'),('radius',108,'float'),('storage',128,'A_Ptr'),('materialArray',144,'A_Ptr')])]
    types=fixture.TYPES+extra
    monkeypatch.setattr(fixture,'TYPES',types)
    monkeypatch.setattr(fixture,'TIDS',{entry[1]:i+1 for i,entry in enumerate(types)})
    base=fixture.build_tag0()
    first=len(hkx._peek_tables(base))
    names=('shape','code','part','storage_refs','material_refs','storage','material','vertices','faces','mopp')
    ids={name:first+i for i,name in enumerate(names)}
    def ref(blob,at,name):struct.pack_into('<i',blob,at,ids[name])
    shape=bytearray(160)
    struct.pack_into('<4f',shape,48,2,1,.5,1)
    struct.pack_into('<i',shape,64,12)
    struct.pack_into('<f',shape,108,.1)
    for at,name in ((72,'part'),(128,'storage_refs'),(144,'material_refs')):ref(shape,at,name)
    code=bytearray(32);ref(code,16,'mopp')
    part=bytearray(80)
    for at,value in ((8,12),(12,3),(28,12),(36,1),(72,-1)):struct.pack_into('<i',part,at,value)
    storage=bytearray(112);ref(storage,16,'vertices');ref(storage,48,'faces')
    material=bytearray(72);struct.pack_into('<I',material,64,21)
    return fixture.append_items(base,[
      ('CustomParamStorageMeshShape',1,shape,[72,128,144]),('hkpMoppCode',1,code,[16]),
      ('hkpMeshShape::Subpart',1,part,[]),('T*',1,struct.pack('<i4x',ids['storage']),[0]),
      ('T*',1,struct.pack('<i4x',ids['material']),[0]),('hkpStorageMeshShape::SubpartStorage',1,storage,[16,48]),
      ('CustomMeshParameter',1,material,[]),('float',9,struct.pack('<9f',0,0,0,1,0,0,0,0,1),[]),
      ('hkUint32',3,struct.pack('<3I',0,1,2),[]),('hkUint8',1,b'\0',[])])


def test_legacy_vertex_face_roundtrip_and_spatial_index(legacy_source):
    document=CollisionDocument(legacy_source)
    assert document.kind=='mesh' and document.meshes[0]['faces']==[[0,1,2,0]]
    assert document.transformed_vertices(0,document.meshes[0]['vertices'])[1]==(2,0,0)
    before=collision_merge._mesh(document,0)
    assert before['flags']==[[],[],[]]
    after=deepcopy(before)
    after['vertices'].append([0,2,0,0]);after['flags'].append([])
    after['faces'].append([3,1,2,0])
    raw=document.export({0:collision_merge._update(before,after)})
    again=CollisionDocument(raw)
    assert collision_merge._mesh(again,0)==after
    assert again._value(again.parts[0])['numTriangles']==2
    assert again._value(again.materials[0])['materialNameData']==21
    code=again._value(again.code)
    assert query(bytes(code['data']),code['info']['offset'],(-1,-1,-1),(3,3,2))=={0,1}
    assert map_collision.preview_meshes(raw)[0]['tris']==2
    assert again.export({})==raw and document.source==legacy_source
    spec=collision_edits.create_state(document,again)
    opened,values=collision_edits.open_member(legacy_source,spec)
    assert values[0]==after


def test_legacy_editor_does_not_invent_vertex_or_face_metadata(legacy_source,tmp_path):
    game,project,store,_pair=setup(tmp_path,legacy_source)
    view=store.collisions.view(MAP,'h0000','high',0,'vertices')
    assert set(view['rows'][0]['values'])=={'posX','posY','posZ'}
    assert {field['key'] for field in store.collisions.read_row(table(store),'f:0')['fields']}=={'vertexA','vertexB','vertexC'}
    with pytest.raises(ValueError,match='no stored face metadata'):
        store.collisions.edit_row(table(store),'f:0','metadata',1)
    store.collisions.edit_row(table(store),'v:0','posX',2)
    store.save()
    from plugins.ds1.map_store import MapStore
    assert MapStore(game,project,False).collisions.read_row(table(store),'v:0')['values']['posX']==2
