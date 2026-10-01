"""Bounded GF cinematic mesh reader.

Format: https://hobbitdur.github.io/FF8ModdingWiki/technical-reference/battle/gf-cinematic-script/
Only packed Ifrit-family resources are accepted; raw VRAM pages are not meshes.
"""
import struct
import re

FILENAME = re.compile(r'mag(005|200|201|202|203|204|205)_b\.\d+', re.IGNORECASE)


PRIMITIVES = {
    2: (20, (14, 16, 18)), 6: (12, (4, 6, 8)),
    7: (20, (12, 14, 16)), 8: (20, (10, 12, 14)),
    9: (28, (18, 20, 22)), 12: (28, (20, 22, 24, 26)),
    16: (12, (4, 6, 8, 10)), 17: (24, (16, 18, 20, 22)),
    18: (24, (12, 14, 16, 18)), 19: (36, (24, 26, 28, 30)),
}


def objects(data: bytes) -> list[dict]:
    if not 0x30 <= len(data) <= 16 * 1024 * 1024:
        raise ValueError('Effect file size is outside the supported bounds')
    header = struct.unpack_from('<12I', data)
    if header[0] or header[5] != 0x30 or header[10] or header[11]:
        raise ValueError('Not a packed cinematic effect file')
    table = header[3]
    if not 0x30 <= table <= len(data) - 4:
        raise ValueError('Effect object table is outside the file')
    count, = struct.unpack_from('<I', data, table)
    if count > 4096 or table + 4 + 4 * count > len(data):
        raise ValueError('Effect object table is truncated')
    offsets = struct.unpack_from(f'<{count}I', data, table + 4)
    if any(offset and not 4 + 4 * count <= offset < len(data) - table for offset in offsets):
        raise ValueError('Effect object offset is outside its data')
    starts = sorted(set(table + offset for offset in offsets if offset))
    stops = dict(zip(starts, starts[1:] + [len(data)]))
    return [{'id': index, 'offset': table + offset, 'size': stops[table + offset] - table - offset}
            for index, offset in enumerate(offsets) if offset]


def mesh(data: bytes) -> dict:
    if len(data) < 0x30:
        raise ValueError('Effect mesh header is truncated')
    header = struct.unpack_from('<12I', data)
    flags, faces_at, vertices_at, count = header[0], header[2], header[5], header[6]
    if flags & ~7 or not flags & 2 or not 0 < count <= 65536:
        raise ValueError('Object is not a supported effect mesh')
    if vertices_at < 0x30 or vertices_at + count * 8 > len(data):
        raise ValueError('Effect vertices are outside the object')
    vertices = [struct.unpack_from('<3h', data, vertices_at + index * 8) for index in range(count)]
    faces = []
    if flags & 1:
        if not 0x30 <= faces_at <= len(data) - 4:
            raise ValueError('Effect primitive list is outside the object')
        cursor = faces_at
        while True:
            if cursor + 4 > len(data):
                raise ValueError('Effect primitive list has no terminator')
            kind, total = struct.unpack_from('<2H', data, cursor)
            cursor += 4
            if total == 0xFFFF:
                break
            if kind not in PRIMITIVES:
                raise ValueError(f'Unsupported effect primitive {kind}')
            stride, fields = PRIMITIVES[kind]
            if len(faces) + total > 500000 or cursor + total * stride > len(data):
                raise ValueError('Effect primitives extend beyond the object')
            for index in range(total):
                start = cursor + index * stride
                refs = [struct.unpack_from('<H', data, start + field)[0] for field in fields]
                if any(ref % 8 or ref // 8 >= count for ref in refs):
                    raise ValueError('Effect face references a missing vertex')
                face = {'type': kind, 'indices': [ref // 8 for ref in refs]}
                gouraud = kind in (2, 7, 9, 12, 17, 19)
                face['colors'] = [list(data[start + (i * 4 if gouraud else 0):start + (i * 4 if gouraud else 0) + 3])
                                  for i in range(len(fields))]
                textured = {8: (4, 16, 18), 9: (12, 24, 26), 18: (4, 20, 22), 19: (16, 32, 34)}.get(kind)
                if textured:
                    uv_at, clut_at, page_at = textured
                    face['uv'] = [list(struct.unpack_from('<2B', data, start + uv_at + i * 2)) for i in range(len(fields))]
                    face['clut'], = struct.unpack_from('<H', data, start + clut_at)
                    face['tpage'], = struct.unpack_from('<H', data, start + page_at)
                faces.append(face)
            cursor += total * stride
    return {'vertices': vertices, 'faces': faces}


def inventory(data: bytes) -> list[dict]:
    result = []
    summaries = {}
    for obj in objects(data):
        key = (obj['offset'], obj['size'])
        if key not in summaries:
            try:
                decoded = mesh(data[obj['offset']:obj['offset'] + obj['size']])
                summaries[key] = {'vertices': len(decoded['vertices']),
                                  'triangles': sum(len(face['indices']) == 3 for face in decoded['faces']),
                                  'quads': sum(len(face['indices']) == 4 for face in decoded['faces'])}
            except ValueError:
                summaries[key] = None
        if summaries[key] is None:
            continue
        result.append({**obj, **summaries[key]})
    return result


def scene(filename: str, data: bytes, object_id: int | None = None) -> dict:
    candidates = inventory(data)
    if object_id is None:
        chosen = next((obj for obj in candidates if obj['triangles'] or obj['quads']), None)
    else:
        chosen = next((obj for obj in candidates if obj['id'] == object_id), None)
    if chosen is None:
        raise ValueError('No supported effect mesh at this object ID')
    decoded = mesh(data[chosen['offset']:chosen['offset'] + chosen['size']])
    if not decoded['faces']:
        raise ValueError('This morph target contains vertices but no faces')
    triangles = []
    for face in decoded['faces']:
        for corners in (((0, 1, 2),) if len(face['indices']) == 3 else ((0, 1, 2), (1, 3, 2))):
            triangle = {'indices': [face['indices'][i] for i in corners],
                        'uv': [[0, 0]] * 3, 'texture': -0xFFFFFF - 2,
                        'colors': [[value / (128 if 'uv' in face else 255) for value in face['colors'][i]] for i in corners]}
            if 'uv' in face:
                triangle['uv'] = [[value / 256 for value in face['uv'][i]] for i in corners]
                triangle['sourceTexture'] = {'tpage': face['tpage'], 'clut': face['clut']}
            triangles.append(triangle)
    return {'file': filename, 'objectId': chosen['id'],
            'positions': [(x, -y, -z) for x, y, z in decoded['vertices']],
            'triangles': triangles, 'textures': [], 'bones': 0, 'animations': 0}
