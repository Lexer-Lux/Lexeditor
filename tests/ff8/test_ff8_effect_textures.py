import struct

import pytest

from plugins.ff8.effect_textures import TextureMemory, read_descriptor, resource_bytes, indexed_rgba


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


@pytest.mark.parametrize('mode,packed', [(0, 0x21), (1, 0x0201)])
def test_texture_pages_use_low_index_first(mode, packed):
    memory = TextureMemory({'textures': [], 'cluts': []}, {})
    memory.write((0, 0, 1, 1), struct.pack('<H', packed))
    palette = [0, 31, 31 << 5] + [0] * 253
    memory.write((320, 224, 256, 1), struct.pack('<256H', *palette))
    result = memory.page_rgba(mode << 7, (224 << 6) | 20)
    assert result[:8] == bytes((255, 0, 0, 255, 0, 255, 0, 255))
    assert result[11] == 0


def test_direct_color_texture_page():
    memory = TextureMemory({'textures': [], 'cluts': []}, {})
    memory.write((0, 0, 1, 1), struct.pack('<H', 31 << 10))
    assert memory.page_rgba(2 << 7, 0)[:4] == bytes((0, 0, 255, 255))


@pytest.mark.parametrize('depth,pixels,width', [(4, b'\x21', 2), (8, b'\x01\x02', 2)])
def test_standalone_resource_palette_selection(depth, pixels, width):
    palette = struct.pack(f'<{1 << depth}H', 0, 31, 31 << 5, *([0] * ((1 << depth) - 3)))
    assert indexed_rgba(pixels, palette, width, 1, depth) == bytes((255, 0, 0, 255, 0, 255, 0, 255))
    with pytest.raises(ValueError, match='incomplete'):
        indexed_rgba(pixels, palette[:-2], width, 1, depth)


def test_replay_overwrites_and_rewinds_raw_uploads():
    rows = {'textures': [{'id': 0, 'slot': None, 'rect': (0, 0, 1, 1)}], 'cluts': []}
    memory = TextureMemory(rows, {2: b'\x1f\x00', 3: b'\xe0\x03'})
    events = [(1, 'raw', (0, 2, 0)), (5, 'raw', (0, 3, 0))]
    assert memory.replay(events, 5).words[0] == 31 << 5
    assert memory.replay(events, 1).words[0] == 31
    assert memory.replay(events, 0).words[0] == 0


def test_raw_upload_rejects_truncated_pixels():
    rows = {'textures': [{'id': 0, 'slot': None, 'rect': (0, 0, 1, 1)}], 'cluts': []}
    with pytest.raises(ValueError, match='incomplete'):
        TextureMemory(rows, {2: b'\x00'}).replay([(1, 'raw', (0, 2, 0))], 1)
