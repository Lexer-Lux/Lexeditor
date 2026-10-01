"""Bounded animated surface meshes from battle-effect files.

The object table and Siren quad records were identified by Maki:
https://forums.qhimm.com/index.php?topic=16283.0
Each object stores vertex frames followed by eight counted primitive groups.
"""
import struct
import base64

PRIMITIVES = ((3, 12, 0x20, False), (4, 12, 0x28, False),
              (3, 20, 0x24, True), (4, 24, 0x2c, True),
              (3, 20, 0x30, False), (4, 24, 0x38, False),
              (3, 28, 0x34, True), (4, 36, 0x3c, True))


def parse(data: bytes) -> list[dict]:
    if 8 <= len(data) <= 16 * 1024 * 1024:
        faces_at, vertices = struct.unpack_from('<2I', data)
        if vertices and faces_at == 8 + vertices * 8:
            if faces_at + 12 <= len(data):
                count, end, first = struct.unpack_from('<3I', data, faces_at)
                if 1 <= count <= 256 and first == 8 + count * 4 and first < end <= len(data) - faces_at:
                    return _composite_objects(data, faces_at)
            return _direct_objects(data)
    return _parse_table(data)


def _track_table_end(data: bytes, start: int) -> int:
    """Bound the keyframe tracks between Quezacotl's surface tables.

    Field meanings are not interpreted. Mask bits select streams of timestamped
    records; bit 9 uses 12 bytes, bit 13 uses 20, and other known bits use 16.
    Each stream ends with a single 0xffffffff word at a record boundary.
    """
    if start + 8 > len(data):
        raise ValueError('Truncated surface track table')
    count, duration = struct.unpack_from('<2I', data, start)
    if not 1 <= count <= 256 or not 1 <= duration <= 4096 or start + 8 + count * 4 > len(data):
        raise ValueError('Invalid surface track table')
    offsets = struct.unpack_from(f'<{count}I', data, start + 8)
    if offsets[0] != 8 + count * 4 or any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError('Invalid surface track offsets')
    cursor = start + offsets[0]
    for offset in offsets:
        if start + offset != cursor or cursor + 8 > len(data):
            raise ValueError('Surface tracks are not contiguous')
        base = cursor
        mask, = struct.unpack_from('<I', data, base + 4)
        if not mask or mask & ~0x3fff:
            raise ValueError('Unsupported surface track fields')
        bits = [bit for bit in range(14) if mask & (1 << bit)]
        header = 8 + len(bits) * 4
        if base + header > len(data):
            raise ValueError('Truncated surface track fields')
        fields = struct.unpack_from(f'<{len(bits)}I', data, base + 8)
        cursor = base + header
        for bit, field in zip(bits, fields):
            if base + field != cursor:
                raise ValueError('Invalid surface track field offset')
            stride = {9: 12, 13: 20}.get(bit, 16)
            previous = -1
            while True:
                if cursor + 4 > len(data):
                    raise ValueError('Truncated surface keyframe')
                timestamp, = struct.unpack_from('<I', data, cursor)
                if timestamp == 0xffffffff:
                    cursor += 4
                    break
                if not previous < timestamp <= duration or cursor + stride > len(data):
                    raise ValueError('Invalid surface keyframe timestamp')
                previous = timestamp
                cursor += stride
    return cursor


def _composite_objects(data: bytes, start: int) -> list[dict]:
    """A vertex block followed by alternating surface and keyframe tables."""
    objects = []
    while start < len(data):
        if start + 8 > len(data):
            raise ValueError('Truncated composite surface table')
        size, = struct.unpack_from('<I', data, start + 4)
        if not 12 <= size <= len(data) - start:
            raise ValueError('Invalid composite surface size')
        group = _parse_table(data[start:start + size])
        for obj in group:
            obj['offset'] += start
            obj['id'] = len(objects)
            objects.append(obj)
        if len(objects) > 256 or sum(obj['vertexCount'] * obj['frameCount'] for obj in objects) > 500000 or sum(len(obj['faces']) for obj in objects) > 500000:
            raise ValueError('Composite surface exceeds decoding budget')
        start = _track_table_end(data, start + size)
    return objects


def _direct_objects(data: bytes) -> list[dict]:
    """Diablos stores consecutive single-frame objects without an offset table."""
    start, blocks, spans = 0, [], []
    tail = []
    while start < len(data):
        if len(blocks) >= 256 or start + 8 > len(data):
            raise ValueError('Invalid direct surface object sequence')
        faces_at, vertices = struct.unpack_from('<2I', data, start)
        if not 1 <= vertices <= 65536 or faces_at != 8 + vertices * 8:
            tail = _parse_table(data[start:])
            for obj in tail:
                obj['offset'] += start
            break
        cursor = start + faces_at
        for _, stride, _, _ in PRIMITIVES:
            if cursor + 4 > len(data):
                raise ValueError('Truncated direct surface face count')
            count, = struct.unpack_from('<I', data, cursor)
            cursor += 4 + count * stride
            if cursor > len(data):
                raise ValueError('Direct surface faces exceed their file')
        blocks.append(struct.pack('<3I', faces_at + 4, vertices, 1) + data[start + 8:cursor])
        spans.append((start, cursor - start))
        start = cursor
    header_size = 8 + 4 * len(blocks)
    offsets, end = [], header_size
    for block in blocks:
        offsets.append(end)
        end += len(block)
    normalized = struct.pack(f'<{len(blocks) + 2}I', len(blocks), end, *offsets) + b''.join(blocks)
    objects = _parse_table(normalized)
    for obj, (offset, size) in zip(objects, spans):
        obj.update(offset=offset, size=size, vertexOffset=8)
    objects.extend(tail)
    if len(objects) > 256 or sum(obj['vertexCount'] * obj['frameCount'] for obj in objects) > 500000 or sum(len(obj['faces']) for obj in objects) > 500000:
        raise ValueError('Composite surface exceeds decoding budget')
    for index, obj in enumerate(objects):
        obj['id'] = index
    return objects


def _parse_table(data: bytes) -> list[dict]:
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
        for corners, stride, command, textured in PRIMITIVES:
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


def inventory(data: bytes) -> list[dict]:
    return [{key: obj[key] for key in ('id', 'offset', 'size', 'frameCount')} |
            {'vertices': obj['vertexCount'],
             'triangles': sum(len(face['indices']) == 3 for face in obj['faces']),
             'quads': sum(len(face['indices']) == 4 for face in obj['faces'])}
            for obj in parse(data)]


def scene(filename: str, data: bytes, dataset: str, object_id: int | None = None, frame: int = 0) -> dict:
    from . import assets, effect_model_textures as materials
    objects = parse(data)
    selected = 0 if object_id is None else object_id
    if not 0 <= selected < len(objects):
        raise ValueError('Unknown surface object')
    obj = objects[selected]
    if not 0 <= frame < obj['frameCount']:
        raise ValueError('Unknown surface frame')
    start = obj['offset'] + obj.get('vertexOffset', 12) + frame * obj['vertexCount'] * 8
    positions = [(x, -y, -z) for x, y, z in
                 (struct.unpack_from('<3h', data, start + i * 8) for i in range(obj['vertexCount']))]
    images = materials.sources(filename, dataset)
    regions = {name: materials.tim_region(image) for name, image in images.items()}
    textures, keys, triangles = [], {}, []
    missing = 0
    for face in obj['faces']:
        texture, uv = -0xffffff - 2, [(0, 0)] * len(face['indices'])
        if 'uv' in face:
            matches = [(name, materials.match_material(region, face['tpage'], face['clut'], face['uv']))
                       for name, region in regions.items()]
            matches = [(name, match) for name, match in matches if match is not None]
            if len(matches) == 1:
                name, (palette, uv) = matches[0]
                key = name, palette
                if key not in keys:
                    if len(keys) >= 128:
                        raise ValueError('Surface exceeds material limit')
                    keys[key] = len(textures)
                    textures.append('data:image/png;base64,' + base64.b64encode(
                        assets.tim_png_bytes(images[name], palette=palette)).decode('ascii'))
                texture = keys[key]
            else:
                missing += 1
        for corners in (((0, 1, 2),) if len(face['indices']) == 3 else ((0, 1, 2), (1, 3, 2))):
            triangles.append({'indices': [face['indices'][i] for i in corners],
                              'uv': [uv[i] for i in corners], 'texture': texture,
                              'colors': [[value / (128 if 'uv' in face else 255) for value in face['colors'][i]]
                                         for i in corners]})
    return {'file': filename, 'objectId': selected, 'frame': frame, 'frameCount': obj['frameCount'],
            'positions': positions, 'triangles': triangles, 'textures': list(range(len(textures))),
            'textureImages': textures, 'unmappedFaces': missing, 'bones': 0}
