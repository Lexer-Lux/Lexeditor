import struct

import pytest

from plugins.ff8.effect_textures import read_descriptor, resource_bytes


def descriptor():
    data = bytearray(50)
    struct.pack_into('<8I', data, 0, 32, 40, 48, 49, 50, 0, 50, 50)
    struct.pack_into('<4h', data, 32, 384, 256, 64, 128)
    struct.pack_into('<4h', data, 40, 320, 224, 16, 1)
    data[48:50] = bytes((130, 1))
    return data


def test_descriptor_separates_depth_from_file_slot():
    result = read_descriptor(descriptor(), 0)
    assert result['textures'][0]['slot'] == 2
    assert result['textures'][0]['depth'] == 8
    assert result['cluts'][0]['slot'] == 1


def test_descriptor_rejects_rectangle_outside_vram():
    data = descriptor()
    struct.pack_into('<h', data, 32, 1000)
    with pytest.raises(ValueError, match='VRAM'):
        read_descriptor(data, 0)


def test_descriptor_retains_rectangles_without_a_packed_file_source():
    data = descriptor()
    data[48:50] = bytes((127, 255))
    result = read_descriptor(data, 0)
    assert result['textures'][0]['slot'] is None
    assert result['cluts'][0]['slot'] is None


def test_resource_masks_flags_and_requires_complete_pixels():
    data = bytearray(56)
    struct.pack_into('<I', data, 20, 48)
    struct.pack_into('<I', data, 48, 0x80000004)
    data[52:56] = b'rgba'
    row = {'id': 0, 'rect': (0, 0, 2, 1)}
    assert resource_bytes(data, row, texture=True) == b'rgba'
    with pytest.raises(ValueError, match='truncated'):
        resource_bytes(data[:-1], row, texture=True)
    struct.pack_into('<I', data, 48, 0)
    with pytest.raises(ValueError, match='absent'):
        resource_bytes(data, row, texture=True)
