"""FLVER2 model reading on synthetic models; no proprietary game bytes."""
import struct
import math
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flver_fixture import build_flver
from plugins.ds1.flver import FlverDocument, FlverError


def rigid_model():
    doc = FlverDocument(build_flver())
    doc.meshes[0]['dynamic'] = False
    doc.bones.append({**doc.bones[0], 'name': 'decal', 'pos': (10., 20., 30.)})
    doc.meshes[0]['default_bone'] = 1
    doc.meshes[0]['bone_list'] = [1]
    return doc


def test_rigid_default_bone_moves_static_decal_without_mutating_source_vertices():
    doc = rigid_model()
    raw = list(doc.meshes[0]['positions'])
    assert doc.meshes[0]['normal_w'] == [127] * 4
    expected = [(x+10., y+20., z+30.) for x,y,z in raw]
    assert doc.mesh_data(0)['positions'] == expected
    assert doc.mesh_data(0)['positions'] == expected
    assert doc.meshes[0]['positions'] == raw


def test_rigid_vertex_indices_resolve_the_mesh_bone_list():
    doc = rigid_model()
    doc.meshes[0]['default_bone'] = 0
    doc.meshes[0]['bone_ids'] = [(0,0,0,0)] * 4
    assert doc.mesh_data(0)['positions'][0] == (10., 20., 30.)


def test_rigid_normal_w_indices_choose_global_bones_per_vertex():
    doc = rigid_model()
    doc.meshes[0]['normal_w'] = [0,1,0,1]
    actual = doc.mesh_data(0)['positions']
    assert actual[0] == (0.,0.,0.)
    assert actual[1] == (11.,20.,30.)
    assert actual[2] == (1.,1.,0.)
    assert actual[3] == (10.,21.,30.)


def test_rigid_parent_rotation_and_scale_transform_positions_and_normals():
    doc = rigid_model()
    doc.bones[0].update(pos=(10.,0.,0.), rot=(0.,0.,math.pi/2))
    doc.bones[1].update(pos=(0.,2.,0.), rot=(0.,math.pi/2,0.),
                        scale=(2.,1.,1.), parent=0)
    doc.meshes[0]['normals'] = [(0.,0.,1.)] * 4
    mesh = doc.mesh_data(0)
    assert mesh['positions'][1] == pytest.approx((8.,0.,-2.))
    assert mesh['normals'][1] == pytest.approx((0.,1.,0.))


def test_rigid_nonuniform_scale_uses_inverse_scale_for_normals():
    doc = rigid_model()
    doc.bones[1]['scale'] = (2.,1.,1.)
    doc.meshes[0]['normals'] = [(1.,1.,0.)] * 4
    assert doc.mesh_data(0)['normals'][0] == pytest.approx((1/math.sqrt(5),2/math.sqrt(5),0.))


def test_dynamic_mesh_stays_in_model_space_for_skinning():
    doc = rigid_model()
    doc.meshes[0]['dynamic'] = True
    assert doc.mesh_data(0)['positions'] == doc.meshes[0]['positions']


@pytest.mark.parametrize('damage', ['bone', 'parent', 'cycle', 'mesh-index'])
def test_invalid_rigid_binding_is_a_model_error(damage):
    doc = rigid_model()
    if damage == 'bone':
        doc.meshes[0]['default_bone'] = 99
    elif damage == 'parent':
        doc.bones[1]['parent'] = 99
    elif damage == 'cycle':
        doc.bones[1]['parent'] = 1
    else:
        doc.meshes[0]['bone_ids'] = [(99,0,0,0)] * 4
    with pytest.raises(FlverError, match='bone'):
        doc.mesh_data(0)


def test_header_counts_and_names():
    doc = FlverDocument(build_flver())
    assert doc.version == 0x2000C
    assert len(doc.dummies) == len(doc.materials) == len(doc.bones) == 1
    assert len(doc.meshes) == 1
    assert doc.materials[0]['name'] == 'mat0'
    assert doc.materials[0]['mat_def'] == 'M[D].mtd'
    assert doc.materials[0]['textures'] == [{'path': 'tex0', 'type': 'g_Diffuse',
                                             'scale': (1.0, 1.0)}]
    assert doc.bones[0]['name'] == 'root'
    assert doc.bones[0]['parent'] == -1
    assert doc.bones[0]['scale'] == (1.0, 1.0, 1.0)
    assert doc.dummies[0]['pos'] == (1.0, 2.0, 3.0)
    assert doc.dummies[0]['ref_id'] == 100
    assert doc.notes == []


def test_mesh_data_values():
    mesh = FlverDocument(build_flver()).mesh_data(0)
    assert mesh['positions'] == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                                 (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    assert mesh['triangles'] == [(0, 2, 1), (0, 3, 2)]
    assert mesh['uvs'] == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for normal in mesh['normals']:
        assert normal == pytest.approx((0.0, 0.0, 1.0))
    assert mesh['bbox'] == ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))
    assert mesh['dynamic'] is True
    assert mesh['cull'] is True
    assert mesh['bone_list'] == [0]


def test_strip_triangulation_flips_winding():
    mesh = FlverDocument(build_flver(strip=True)).mesh_data(0)
    assert mesh['triangles'] == [(0, 1, 2), (3, 2, 1)]


def test_qloc_layout_repaired_from_mtd(caplog):
    with caplog.at_level('DEBUG',logger='plugins.ds1.flver'):
        doc = FlverDocument(build_flver(qloc=True))
    assert 'Repaired QLOC' in caplog.text
    assert doc.notes == []
    mesh = doc.mesh_data(0)
    assert mesh['positions'][2] == (1.0, 1.0, 0.0)
    assert mesh['bone_ids'] == [(0, 0, 0, 0)] * 4
    assert mesh['uvs'][1] == (1.0, 0.0)


def _mutate(offset, size, fmt, value):
    raw = bytearray(build_flver())
    struct.pack_into(fmt, raw, offset, value)
    return bytes(raw)


def test_rejects_garbage():
    with pytest.raises(FlverError):
        FlverDocument(b'nope')
    with pytest.raises(FlverError):
        FlverDocument(build_flver()[:64])
    with pytest.raises(FlverError):  # DS2 version
        FlverDocument(_mutate(8, 4, '<I', 0x20010))
    with pytest.raises(FlverError):  # big-endian
        FlverDocument(b'FLVER\0B\0' + build_flver()[8:])
    with pytest.raises(FlverError):  # face index past the vertices
        raw = bytearray(build_flver())
        data_at = struct.unpack_from('<I', raw, 12)[0]
        struct.pack_into('<H', raw, data_at, 9)
        FlverDocument(bytes(raw)).mesh_data(0)


def test_dcx_wrapped_model_parses():
    plain = build_flver()
    header = bytearray(76)
    header[:4] = b'DCX\0'
    header[4:24] = bytes.fromhex('000100000000001800000024000000240000002c')
    header[24:28] = b'DCS\0'
    header[36:40] = b'DCP\0'
    header[40:44] = b'DFLT'
    header[68:76] = b'DCA\0\0\0\0\x08'
    payload = zlib.compress(plain, 9)
    struct.pack_into('>II', header, 28, len(plain), len(payload))
    doc = FlverDocument(bytes(header) + payload)
    assert doc.mesh_data(0)['triangles'] == [(0, 2, 1), (0, 3, 2)]


def test_mesh_data_bad_index():
    doc = FlverDocument(build_flver())
    with pytest.raises(FlverError, match='out of range'):
        doc.mesh_data(9)
    with pytest.raises(FlverError, match='out of range'):
        doc.mesh_data(-1)


def test_corrupt_dcx_wrapped_as_model_error():
    with pytest.raises(FlverError, match='unreadable'):
        FlverDocument(b'DCX\0' + b'\0' * 100)
