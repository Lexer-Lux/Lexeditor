import struct

import pytest

from plugins.ff8 import effect_surface


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
