"""Bounded FF8 .x stage geometry reader.

Layout evidence: FFNx src/ff8/battle/stage.cpp and stage.h. Stage geometry
uses offset groups followed by signed XYZ vertices and 20/24-byte faces.
This reader preserves face flags and texture/palette selectors for rendering.
"""
from __future__ import annotations

import struct


def texture_layout(data: bytes) -> dict:
    from .assets import _tim_layout
    offset = data.find(b'\x10\x00\x00\x00', 0x500)
    while offset >= 0:
        if offset % 4 == 0:
            try:
                layout = _tim_layout(data, offset)
                if layout['depth'] == 8 and offset + layout['size'] == len(data):
                    return {**layout, 'offset': offset, 'index': 0}
            except ValueError:
                pass
        offset = data.find(b'\x10\x00\x00\x00', offset + 4)
    raise ValueError('Battle stage has no supported terminal texture atlas')


def scene(filename: str, data: bytes) -> dict:
    geometry, atlas = parse(data), texture_layout(data)
    positions, triangles, palettes = [], [], []
    for obj in geometry['objects']:
        base = len(positions)
        positions.extend((x, -y, -z) for x, y, z in obj['vertices'])
        for face in obj['faces']:
            palette = (face['palette'] >> 6) & 15
            if palette >= atlas['paletteCount']:
                raise ValueError('Battle stage face uses an unavailable palette')
            if palette not in palettes:
                palettes.append(palette)
            # FFNx uses 128-pixel texture-page strides in the 8-bit atlas.
            uv = [((u + (face['texture'] & 15) * 128) / atlas['width'], v / atlas['height'])
                  for u, v in face['uv']]
            for corners in (((0, 1, 2),) if len(face['indices']) == 3 else ((0, 1, 2), (1, 3, 2))):
                triangles.append({'indices': [base + face['indices'][i] for i in corners],
                                  'uv': [uv[i] for i in corners], 'texture': palettes.index(palette)})
    return {'file': filename, 'positions': positions, 'triangles': triangles,
            'textures': [0] * len(palettes), 'texturePalettes': palettes, 'bones': 0, 'animations': 0}


def parse(data: bytes) -> dict:
    if not 0x510 <= len(data) <= 16 * 1024 * 1024:
        raise ValueError("Battle stage size is outside the supported bounds")

    def unpack(fmt, offset):
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(data):
            raise ValueError("Truncated battle stage geometry")
        return struct.unpack_from(fmt, data, offset)

    def group_at(marker):
        for count in range(1, min(4096, marker // 4)):
            start = marker - (count + 1) * 4
            if unpack('<II', start) != (count, (count + 1) * 4):
                continue
            offsets = unpack('<' + 'I' * count, start + 4)
            if all(a < b for a, b in zip(offsets, offsets[1:])) and all(
                    start + value + 10 <= len(data) for value in offsets):
                return start, offsets
        raise ValueError("Battle stage has no valid model offset group")

    marker = data.find(b'\x01\x00\x01\x00', 0x500)
    while marker >= 0:
        if marker % 4 == 0:
            try:
                group = group_at(marker)
                break
            except ValueError:
                pass
        marker = data.find(b'\x01\x00\x01\x00', marker + 1)
    else:
        raise ValueError("Battle stage has no model geometry")

    objects = []
    visited = set()
    vertex_total = face_total = 0
    while group:
        base, offsets = group
        if base in visited or len(visited) >= 256:
            raise ValueError("Invalid battle stage model group chain")
        visited.add(base)
        end = 0
        for offset in offsets:
            start = base + offset
            magic, count = unpack('<IH', start)
            if magic != 0x10001:
                raise ValueError("Invalid battle stage model header")
            vertex_total += count
            if len(objects) >= 4096 or vertex_total > 500_000:
                raise ValueError("Battle stage exceeds the geometry budget")
            vertices = [unpack('<hhh', start + 6 + index * 6) for index in range(count)]
            cursor = start + 6 + count * 6 + 4
            cursor += cursor % 4
            triangles, quads, _unknown = unpack('<HHI', cursor)
            face_total += triangles + quads
            if face_total > 500_000:
                raise ValueError("Battle stage exceeds the face budget")
            cursor += 8
            faces = []
            for corners, total, stride in ((3, triangles, 20), (4, quads, 24)):
                for _ in range(total):
                    record = unpack('<' + 'B' * stride, cursor)
                    indices = unpack('<' + 'H' * corners, cursor)
                    if any(index >= count for index in indices):
                        raise ValueError("Battle stage face references a missing vertex")
                    if corners == 3:
                        uv = ((record[6], record[7]), (record[8], record[9]), (record[12], record[13]))
                        palette, = unpack('<H', cursor + 10)
                        texture, hidden = record[14:16]
                    else:
                        uv = ((record[8], record[9]), (record[12], record[13]),
                              (record[16], record[17]), (record[18], record[19]))
                        palette, = unpack('<H', cursor + 10)
                        texture, hidden = record[14:16]
                    faces.append({'indices': indices, 'uv': uv, 'texture': texture,
                                  'palette': palette, 'hide': hidden,
                                  'color': record[-4:-1], 'instruction': record[-1]})
                    cursor += stride
            objects.append({'offset': start, 'vertices': vertices, 'faces': faces})
            end = cursor
        group = None
        if end + 0x9C <= len(data):
            count, = unpack('<I', end + 0x98)
            marker = end + 0x9C + count * 4
            if 0 < count < 4096 and marker + 4 <= len(data) and unpack('<I', marker)[0] == 0x10001:
                group = group_at(marker)
    return {'objects': objects, 'vertices': sum(len(obj['vertices']) for obj in objects),
            'triangles': sum(len(face['indices']) == 3 for obj in objects for face in obj['faces']),
            'quads': sum(len(face['indices']) == 4 for obj in objects for face in obj['faces'])}
