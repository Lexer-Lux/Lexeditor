"""Synthetic stage geometry exercises bounds without proprietary fixtures."""
import struct
import pytest
from plugins.ff8.battle_stage import parse


def stage():
    data=bytearray(0x500)
    data.extend(struct.pack('<II',1,8))
    data.extend(struct.pack('<IH',0x10001,3))
    data.extend(struct.pack('<9h',0,0,0,100,-50,0,0,0,100))
    data.extend(bytes(4))
    data.extend(struct.pack('<HHI',1,0,0))
    data.extend(struct.pack('<3H4BH4B4B',0,1,2,0,0,255,0,960,0,255,2,0,128,128,128,0x24))
    return bytes(data)


def test_geometry_preserves_vertices_uv_and_face_metadata():
    result=parse(stage())
    assert (result['vertices'],result['triangles'],result['quads'])==(3,1,0)
    obj=result['objects'][0]
    assert obj['vertices'][1]==(100,-50,0)
    assert obj['faces'][0]['uv']==((0,0),(255,0),(0,255))
    assert obj['faces'][0]['texture']==2
    assert obj['faces'][0]['palette']==960


@pytest.mark.parametrize('cut',[0,0x508,0x518,-1])
def test_truncated_geometry_is_rejected(cut):
    with pytest.raises(ValueError):
        parse(stage()[:cut])


def test_face_vertex_outside_object_is_rejected():
    data=bytearray(stage())
    struct.pack_into('<H',data,len(data)-20,3)
    with pytest.raises(ValueError,match='missing vertex'):
        parse(data)
