"""FLVER2 model reading on synthetic models; no proprietary game bytes."""
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flver_fixture import build_flver
from plugins.ds1.flver import FlverDocument, FlverError


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


def test_qloc_layout_repaired_from_mtd():
    doc = FlverDocument(build_flver(qloc=True))
    assert any('Repaired QLOC' in note for note in doc.notes)
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
