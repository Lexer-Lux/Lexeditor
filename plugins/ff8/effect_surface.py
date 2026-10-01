"""Bounded animated surface meshes from battle-effect files.

The object table and Siren quad records were identified by Maki:
https://forums.qhimm.com/index.php?topic=16283.0
Each object stores vertex frames followed by eight counted primitive groups.
"""
import struct


def parse(data: bytes) -> list[dict]:
    if not 12 <= len(data) <= 16 * 1024 * 1024:
        raise ValueError('Effect surface size is outside the supported bounds')
    count, end = struct.unpack_from('<2I', data)
    if not 1 <= count <= 256 or not 8 + count * 4 < end <= len(data):
        raise ValueError('Invalid effect surface table')
    offsets = list(struct.unpack_from(f'<{count}I', data, 8))
    if offsets[0] != 8 + count * 4 or any(a >= b for a, b in zip(offsets, offsets[1:] + [end])):
        raise ValueError('Invalid effect surface offsets')
    result = []
    total_vertices = total_faces = 0
    for object_id, (start, stop) in enumerate(zip(offsets, offsets[1:] + [end])):
        if stop - start < 28:
            raise ValueError('Truncated effect surface object')
        faces_at, vertices, frames = struct.unpack_from('<3I', data, start)
        total_vertices += vertices * frames
        if not 1 <= vertices <= 65536 or not 1 <= frames <= 4096 or total_vertices > 500000:
            raise ValueError('Effect surface exceeds the vertex budget')
        if faces_at != 12 + vertices * frames * 8 or start + faces_at + 16 > stop:
            raise ValueError('Invalid effect surface vertex frames')
        cursor = start + faces_at
        faces = []
        for corners, stride, command, textured in ((3, 12, 0x20, False), (4, 16, 0x28, False),
                                                   (3, 20, 0x24, True), (4, 24, 0x2c, True),
                                                   (3, 20, 0x30, False), (4, 24, 0x38, False),
                                                   (3, 28, 0x34, True), (4, 36, 0x3c, True)):
            if cursor + 4 > stop:
                raise ValueError('Truncated effect surface face count')
            amount, = struct.unpack_from('<I', data, cursor)
            cursor += 4
            total_faces += amount
            if total_faces > 500000 or cursor + amount * stride > stop:
                raise ValueError('Effect surface faces exceed their object')
            for _ in range(amount):
                if data[cursor + 3] & 0xfc != command:
                    raise ValueError('Unsupported effect surface primitive command')
                refs = struct.unpack_from(f'<{corners}H', data, cursor + 4)
                if any(ref % 2 or ref // 2 >= vertices for ref in refs):
                    raise ValueError('Effect surface face references an absent vertex')
                face = {'indices': [ref // 2 for ref in refs], 'color': list(data[cursor:cursor + 3])}
                face['colors'] = [face['color']] * corners
                if command & 0x10:
                    extra = (20 if corners == 3 else 24) if textured else 12
                    face['colors'] = [face['color']] + [list(data[cursor + extra + i * 4:cursor + extra + i * 4 + 3])
                                                       for i in range(corners - 1)]
                if textured:
                    uv_at = cursor + (10 if corners == 3 else 12)
                    face['uv'] = [struct.unpack_from('<2B', data, uv_at),
                                  struct.unpack_from('<2B', data, uv_at + 4),
                                  struct.unpack_from('<2B', data, uv_at + 8)]
                    if corners == 4:
                        face['uv'].append(struct.unpack_from('<2B', data, uv_at + 10))
                    face['clut'], = struct.unpack_from('<H', data, uv_at + 2)
                    face['tpage'], = struct.unpack_from('<H', data, uv_at + 6)
                faces.append(face)
                cursor += stride
        if cursor != stop:
            raise ValueError('Unsupported effect surface object trailer')
        result.append({'id': object_id, 'offset': start, 'size': stop - start,
                       'frameCount': frames, 'vertexCount': vertices,
                       'positions': [struct.unpack_from('<3h', data, start + 12 + i * 8) for i in range(vertices)],
                       'faces': faces})
    return result
