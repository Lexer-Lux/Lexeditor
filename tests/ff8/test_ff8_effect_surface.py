import struct

import pytest

from plugins.ff8 import effect_surface
from plugins.ff8 import assets, effect_model_textures, model_geometry


def surface():
    vertices = b''.join(struct.pack('<4h', *point, 0) for point in
                        ((0, 0, 0), (100, 0, 0), (0, 100, 0), (100, 100, 0)))
    groups = []
    for corners, stride, command, textured in ((3, 12, 0x20, False), (4, 16, 0x28, False),
                                               (3, 20, 0x24, True), (4, 24, 0x2c, True),
                                               (3, 20, 0x30, False), (4, 24, 0x38, False),
                                               (3, 28, 0x34, True), (4, 36, 0x3c, True)):
        face = bytearray(stride)
        face[:4] = bytes((128, 64, 32, command))
        struct.pack_into(f'<{corners}H', face, 4, *range(0, corners * 2, 2))
        if textured:
            uv = 10 if corners == 3 else 12
            struct.pack_into('<2BH2BH2B', face, uv, 1, 2, 123, 3, 4, 189, 5, 6)
            if corners == 4:
                face[uv + 10:uv + 12] = bytes((7, 8))
        if command & 0x10:
            extra = (20 if corners == 3 else 24) if textured else 12
            for i in range(corners - 1):
                face[extra + i * 4:extra + i * 4 + 3] = bytes((10 + i, 20, 30))
        groups.append(struct.pack('<I', 1) + face)
    obj = struct.pack('<3I', 12 + len(vertices) * 2, 4, 2) + vertices * 2 + b''.join(groups)
    return struct.pack('<3I', 1, 12 + len(obj), 12) + obj


def test_all_primitive_groups_and_vertex_frames():
    obj, = effect_surface.parse(surface())
    assert obj['frameCount'] == 2 and obj['vertexCount'] == 4
    assert obj['positions'][1] == (100, 0, 0)
    assert len(obj['faces']) == 8
    assert obj['faces'][3]['indices'] == [0, 1, 2, 3]
    assert obj['faces'][3]['uv'] == [(1, 2), (3, 4), (5, 6), (7, 8)]
    assert obj['faces'][6]['clut'] == 123 and obj['faces'][6]['tpage'] == 189
    assert obj['faces'][7]['colors'] == [[128, 64, 32], [10, 20, 30], [11, 20, 30], [12, 20, 30]]


@pytest.mark.parametrize('offset,value', [(0, 257), (8, 16), (12, 999999), (16, 999999), (20, 0)])
def test_invalid_table_and_frames_are_rejected(offset, value):
    data = bytearray(surface())
    struct.pack_into('<I', data, offset, value)
    with pytest.raises(ValueError):
        effect_surface.parse(data)


def test_truncated_or_invalid_primitives_are_rejected():
    raw = surface()
    with pytest.raises(ValueError):
        effect_surface.parse(raw[:-1])
    face = 12 + 12 + 4 * 2 * 8 + 4
    for offset, value in ((face + 3, 255), (face + 4, 7), (face + 4, 8)):
        data = bytearray(raw)
        data[offset] = value
        with pytest.raises(ValueError):
            effect_surface.parse(data)


def test_inventory_and_scene_select_vertex_frames(monkeypatch):
    data = bytearray(surface())
    struct.pack_into('<h', data, 12 + 12 + 4 * 8, 50)
    data = bytes(data)
    monkeypatch.setattr(assets, 'model_dat_bytes', lambda *args: data)
    monkeypatch.setattr(effect_model_textures, 'sources', lambda *args: {})
    info = assets._battle_file_info('mag094_b.1s0', data)
    assert info['kind'] == 'surface'
    assert info['counts'] == {'objects': 1, 'vertices': 4, 'triangles': 4, 'quads': 4}
    first = model_geometry.scene('mag094_b.1s0', frame=0)
    second = model_geometry.scene('mag094_b.1s0', frame=1)
    assert first['positions'][0] == (0, 0, 0)
    assert second['positions'][0] == (50, 0, 0)
    assert len(second['triangles']) == 12
    assert second['unmappedFaces'] == 4
    assert second['triangles'][-1]['colors'][-1] == [11 / 128, 20 / 128, 30 / 128]
    for object_id, frame in ((1, 0), (-1, 0), (0, -1), (0, 2)):
        with pytest.raises(ValueError):
            model_geometry.scene('mag094_b.1s0', object_id=object_id, frame=frame)


def test_direct_mesh_sequence_and_animated_tail_keep_original_offsets(monkeypatch):
    original = surface()
    obj = original[12:]
    faces_at, vertices, _ = struct.unpack_from('<3I', obj)
    direct = struct.pack('<2I', 8 + vertices * 8, vertices) + obj[12:12 + vertices * 8] + obj[faces_at:]
    changed = bytearray(direct)
    struct.pack_into('<h', changed, 8, 75)
    data = direct + changed + original
    objects = effect_surface.parse(data)
    assert [o['offset'] for o in objects] == [0, len(direct), 2 * len(direct) + 12]
    assert [o['frameCount'] for o in objects] == [1, 1, 2]
    monkeypatch.setattr(assets, 'model_dat_bytes', lambda *args: data)
    monkeypatch.setattr(effect_model_textures, 'sources', lambda *args: {})
    assert model_geometry.scene('mag324_h.s00', object_id=1)['positions'][0] == (75, 0, 0)
    assert model_geometry.scene('mag324_h.s00', object_id=2, frame=1)['positions'][0] == (0, 0, 0)
    for invalid in (direct[:-1], direct + b'garbage', direct + original[:-1]):
        with pytest.raises(ValueError):
            effect_surface.parse(invalid)
