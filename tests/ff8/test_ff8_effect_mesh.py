import struct

import pytest

from plugins.ff8 import effect_mesh


def triangle():
    data = bytearray(0x30 + 24 + 4 + 12 + 4)
    struct.pack_into('<I', data, 0, 3)
    struct.pack_into('<I', data, 8, 72)
    struct.pack_into('<2I', data, 20, 48, 3)
    for index, vertex in enumerate(((0, 0, 0), (100, -20, 0), (0, 0, 100))):
        struct.pack_into('<3h', data, 48 + index * 8, *vertex)
    struct.pack_into('<2H', data, 72, 6, 1)
    struct.pack_into('<3H', data, 80, 0, 8, 16)
    struct.pack_into('<2H', data, 88, 0, 0xFFFF)
    return data


def test_mesh_byte_offsets_become_vertex_indices():
    result = effect_mesh.mesh(triangle())
    assert result['vertices'][1] == (100, -20, 0)
    assert result['faces'] == [{'type': 6, 'indices': [0, 1, 2], 'colors': [[0, 0, 0]] * 3}]


def test_textured_triangle_preserves_uv_palette_and_page():
    data = triangle() + bytes(8)
    struct.pack_into('<2H', data, 72, 8, 1)
    data[80:86] = bytes((0, 1, 10, 11, 20, 21))
    struct.pack_into('<5H', data, 86, 0, 8, 16, 14356, 150)
    struct.pack_into('<2H', data, 96, 0, 65535)
    face = effect_mesh.mesh(data)['faces'][0]
    assert face['uv'] == [[0, 1], [10, 11], [20, 21]]
    assert (face['clut'], face['tpage']) == (14356, 150)


@pytest.mark.parametrize('reference', [1, 24, 65535])
def test_mesh_rejects_invalid_vertex_reference(reference):
    data = triangle()
    struct.pack_into('<H', data, 80, reference)
    with pytest.raises(ValueError, match='missing vertex'):
        effect_mesh.mesh(data)


def test_mesh_requires_terminated_primitive_list():
    with pytest.raises(ValueError, match='terminator'):
        effect_mesh.mesh(triangle()[:-4])


def test_sparse_object_table_retains_resource_ids():
    data = bytearray(64) + triangle()
    struct.pack_into('<I', data, 12, 48)
    struct.pack_into('<I', data, 20, 48)
    struct.pack_into('<4I', data, 48, 3, 0, 16, 0)
    assert effect_mesh.objects(data) == [{'id': 1, 'offset': 64, 'size': 92}]
    struct.pack_into('<I', data, 56, 4)
    with pytest.raises(ValueError, match='offset'):
        effect_mesh.objects(data)


def test_raw_texture_page_is_not_a_packed_effect():
    with pytest.raises(ValueError, match='Not a packed'):
        effect_mesh.objects(bytes(32768))


def test_scene_selects_sparse_object_and_rejects_missing_id():
    data = bytearray(64) + triangle()
    struct.pack_into('<I', data, 12, 48)
    struct.pack_into('<I', data, 20, 48)
    struct.pack_into('<4I', data, 48, 3, 0, 16, 0)
    result = effect_mesh.scene('mag005_b.05', data, 1)
    assert result['objectId'] == 1
    assert result['positions'][1] == (100, 20, 0)
    assert result['triangles'][0]['indices'] == [0, 1, 2]
    assert result['textures'] == []
    with pytest.raises(ValueError, match='object ID'):
        effect_mesh.scene('mag005_b.05', data, 0)
