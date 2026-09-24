"""World preview geometry retains real topology and material coordinates."""
import struct

import pytest

from plugins.ff8.world_geometry import SEGMENT_SIZE, segment_mesh


def terrain_segment():
    data = bytearray(SEGMENT_SIZE)
    struct.pack_into('<I', data, 0, 42)
    offsets = [68 + block * 48 for block in range(16)]
    struct.pack_into('<16I', data, 4, *offsets)
    for offset in offsets:
        struct.pack_into('<4B', data, offset, 1, 3, 0, 0)
        data[offset + 4:offset + 20] = bytes([0, 1, 2, 0, 0, 0,
                                           1, 2, 3, 4, 5, 6, 0xA3, 7, 8, 9])
        for index, vertex in enumerate([(0, 128, 0), (2048, -1920, 0), (0, 128, -2048)]):
            struct.pack_into('<hhhh', data, offset + 20 + index * 8, *vertex, 0)
    return data


def test_world_mesh_block_placement_and_materials():
    data = terrain_segment()
    original = bytes(data)
    mesh = segment_mesh(data, 0)
    assert mesh['vertices'][:3] == [[0, 0, 0], [1, 1, 0], [0, 0, 1]]
    assert mesh['vertices'][12] == [0, 0, 1]  # Next block row.
    assert mesh['faces'][1]['indices'] == [3, 4, 5]
    assert mesh['faces'][0] == dict(indices=[0, 1, 2], uv=[[1, 2], [3, 4], [5, 6]],
                                   texturePage=10, palette=3, groundType=7,
                                   flags=[8, 9], block=0, polygon=0)
    assert mesh['groupId'] == 42
    assert bytes(data) == original


def test_world_mesh_segment_placement_and_unsigned_height():
    data = terrain_segment() * 34
    struct.pack_into('<h', data, 33 * SEGMENT_SIZE + 90, 129)
    mesh = segment_mesh(data, 33)
    assert mesh['vertices'][0] == [4, 65535 / 2048, 4]


@pytest.mark.parametrize('segment_id', [-1, 1, 0.5, True])
def test_world_mesh_rejects_invalid_segment(segment_id):
    with pytest.raises(ValueError):
        segment_mesh(terrain_segment(), segment_id)


def test_world_mesh_rejects_bad_topology_and_truncation():
    data = terrain_segment()
    data[72] = 3
    with pytest.raises(ValueError, match='bad vertex index'):
        segment_mesh(data, 0)
    with pytest.raises(ValueError, match='complete'):
        segment_mesh(data[:-1], 0)
