"""Synthetic DS1-shaped models; no proprietary game bytes."""
import struct
import zlib

DCX_HEADER = bytes.fromhex(
    '44435800000100000000001800000024000000240000002c44435300000000000000000044435000'
    '44464c540000002009000000000000000000000000000000000101004443410000000008')


def make_chrbnd(flver_bytes, stem='c1200', extra=(), dcx=True):
    """A synthetic .chrbnd.dcx: the flver plus extra (name, bytes)
    members, such as the model's TPF textures. dcx=False leaves the
    raw binder, like the game's unwrapped FaceGen archive."""
    blobs = [(stem + '.flver', flver_bytes)] + list(extra)
    directory_end = 32 + 24 * len(blobs)
    names_end = directory_end + sum(len(name.encode('ascii')) + 1 for name, _ in blobs)
    plain = bytearray(names_end)
    plain[:4] = b'BND3'
    plain[4:12] = b'TEST0000'
    plain[12] = 0x74
    struct.pack_into('<II', plain, 16, len(blobs), names_end)
    data_offset = len(plain)
    name_at = directory_end
    for index, (name, blob) in enumerate(blobs):
        member = name.encode('ascii') + bytes((0,))
        struct.pack_into('<6I', plain, 32 + index * 24, 0x40, len(blob), data_offset, 0,
                         name_at, len(blob))
        plain[name_at:name_at + len(member)] = member
        name_at += len(member)
        data_offset += len(blob)
    for _, blob in blobs:
        plain.extend(blob)
    if not dcx:
        return bytes(plain)
    compressed = zlib.compress(bytes(plain), 9)
    header = bytearray(DCX_HEADER)
    struct.pack_into('>II', header, 28, len(plain), len(compressed))
    return bytes(header) + compressed


def build_flver(strip=False, qloc=False, bones=None, skin=None,
                pos_offset=(0.0, 0.0, 0.0), bone_list=None, second_uv=False,
                light_tex=None, mesh_count=1, tex_name='tex0'):
    """A minimal FLVER2 0x2000C: mesh_count quads, 1 material, N bones, 1 dummy.

    `strip` stores the faces as a triangle strip; `qloc` writes a lying
    DS1R layout (M[D].mtd with undeclared tangent bytes) for repair tests.
    `bones` is [(name, parent, pos, rot, scale)] (default one root bone at
    the origin); `skin` is per-vertex (ids, weights) with ids indexing
    `bone_list` (default every model bone in order); `pos_offset` shifts
    the quad. `mesh_count` is 1 or 0 (a skeleton-only rig, like the
    player base); `tex_name` is the diffuse texture's path.
    """
    if bones is None:
        bones = [('root', -1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0))]
    if bone_list is None:
        bone_list = list(range(len(bones)))
    if qloc and (len(bones) != 1 or skin is not None):
        raise ValueError('qloc covers the single-bone unskinned layout only')
    if second_uv and (qloc or skin is not None):
        raise ValueError('second_uv covers the plain unskinned layout only')
    if mesh_count not in (0, 1):
        raise ValueError('mesh_count is 1 or 0')
    if not mesh_count and (strip or qloc or skin is not None or second_uv):
        raise ValueError('mesh shaping needs the mesh')
    ox, oy, oz = pos_offset
    out = bytearray()
    out.extend(b'\0' * 128)  # header

    out.extend(struct.pack('<3f', 1.0, 2.0, 3.0))  # dummy
    out.extend(bytes((255, 128, 64, 32)))
    out.extend(struct.pack('<3f', 0.0, 0.0, 1.0))
    out.extend(struct.pack('<2h', 100, 0))
    out.extend(struct.pack('<3f', 0.0, 1.0, 0.0))
    out.extend(struct.pack('<h2B', 0, 1, 1))
    out.extend(struct.pack('<2I', 0, 0) + bytes(8))

    mat_at = len(out)  # material
    out.extend(bytes(32))

    bone_at = len(out)  # bones
    for _name, parent, pos, rot, scale in bones:
        out.extend(struct.pack('<3f', *pos))
        out.extend(bytes(4))  # name offset
        out.extend(struct.pack('<3f', *rot))
        out.extend(struct.pack('<2h', parent, -1))
        out.extend(struct.pack('<3f', *scale))
        out.extend(struct.pack('<2h', -1, -1))
        out.extend(struct.pack('<3f', 0.0, 0.0, 0.0))
        out.extend(struct.pack('<I', 3))
        out.extend(struct.pack('<3f', 1.0, 1.0, 0.0))
        out.extend(bytes(52))

    mesh_at = face_at = array_at = layout_at = None
    if mesh_count:
        mesh_at = len(out)  # mesh
        out.extend(bytes(48))

        face_at = len(out)  # face set
        out.extend(bytes(32))

        array_at = len(out)  # vertex array header
        out.extend(bytes(32))

        layout_at = len(out)  # layout
        out.extend(bytes(16))

    tex_at = len(out)  # texture
    out.extend(bytes(32))
    tex2_at = None
    if light_tex is not None:
        tex2_at = len(out)
        out.extend(bytes(32))

    def place(blob):
        at = len(out)
        out.extend(blob)
        return at

    members = [(0, 0x02, 0), (3, 0x13, 0), (5, 0x15, 0)]
    if qloc:
        members = [(0, 0x02, 0), (2, 0x11, 0), (3, 0x13, 0), (10, 0x13, 0), (5, 0x15, 0)]
    elif skin is not None:
        members = [(0, 0x02, 0), (3, 0x13, 0), (2, 0x11, 0), (1, 0x13, 0), (5, 0x15, 0)]
    if second_uv:
        members = members + [(5, 0x15, 0)]
    members_at = None
    if mesh_count:
        members_at = place(b''.join(struct.pack('<5I', 0, 0, fmt, semantic, inst)
                                    for semantic, fmt, inst in members))

    mat_name = place(b'mat0\0')
    mtd = place(b'M[D].mtd\0')
    bone_names = [place(name.encode('ascii') + b'\0') for name, *_ in bones]
    tex_path = place(tex_name.encode('ascii') + b'\0')
    tex_type = place(b'g_Diffuse\0')
    if light_tex is not None:
        light_path = place(light_tex.encode('ascii') + b'\0')
        light_type = place(b'g_Lightmap\0')
    box_at = place(struct.pack('<6f', ox, oy, oz, ox + 1.0, oy + 1.0, oz))
    bone_list_at = place(struct.pack('<%di' % len(bone_list), *bone_list))

    data_len = 0
    if mesh_count:
        face_idx_at = place(struct.pack('<i', 0))
        array_idx_at = place(struct.pack('<i', 0))

        while len(out) % 16:
            out.append(0)
        data_at = len(out)
        if strip:
            indices = struct.pack('<4H', 0, 1, 2, 3)
        else:
            # Clockwise, like real DS1 files (DirectX front faces).
            indices = struct.pack('<6H', 0, 2, 1, 0, 3, 2)
        idx_at = place(indices)
        verts = bytearray()
        for num, (x, y) in enumerate(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
            verts.extend(struct.pack('<3f', x + ox, y + oy, oz))
            if qloc:
                verts.extend(bytes((0, 0, 0, 0)))
                verts.extend(bytes((127, 127, 254, 127)))
                verts.extend(bytes(4))  # undeclared tangent bytes
                verts.extend(bytes((255, 255, 255, 255)))
            else:
                verts.extend(bytes((127, 127, 254, 127)))
            if skin is not None:
                ids, weights = skin[num]
                verts.extend(bytes(ids))
                verts.extend(bytes(round(min(max(w, 0.0), 1.0) * 255) for w in weights))
            verts.extend(struct.pack('<2h', round(x * 1024), round(y * 1024)))
            if second_uv:
                verts.extend(struct.pack('<2h', round((x + 10) * 1024), round((y + 20) * 1024)))
        vtx_at = place(bytes(verts))
        stride = 32 if qloc else (28 if skin is not None else (24 if second_uv else 20))
        data_len = len(out) - data_at
    else:
        while len(out) % 16:
            out.append(0)
        data_at = len(out)

    struct.pack_into('<6s2sI', out, 0, b'FLVER\0', b'L\0', 0x2000C)
    struct.pack_into('<7I', out, 12, data_at, data_len, 1, 1, len(bones),
                     mesh_count, mesh_count)
    struct.pack_into('<6f', out, 40, ox, oy, oz, ox + 1.0, oy + 1.0, oz)
    struct.pack_into('<2I', out, 64, 2, 2)
    struct.pack_into('<3B', out, 72, 16, 0, 0)
    struct.pack_into('<I', out, 76, 0)
    struct.pack_into('<3I', out, 80, mesh_count, mesh_count,
                     2 if light_tex is not None else 1)
    struct.pack_into('<I', out, 104, 0)
    struct.pack_into('<7I', out, mat_at, mat_name, mtd, 2 if light_tex is not None else 1,
                     0, 0, 0, 0)
    for index, name_at in enumerate(bone_names):
        struct.pack_into('<I', out, bone_at + index * 128 + 12, name_at)
    if mesh_count:
        struct.pack_into('<B3xI8x8I', out, mesh_at, 1, 0, 0, len(bone_list), box_at,
                         bone_list_at, 1, face_idx_at, 1, array_idx_at)
        struct.pack_into('<3x3Bh3I4xI4x', out, face_at, 0, 1 if strip else 0, 1, 0,
                         len(indices) // 2, idx_at - data_at, len(indices), 16)
        struct.pack_into('<4I8x2I', out, array_at, 0, 0, stride, 4, len(verts),
                         vtx_at - data_at)
        struct.pack_into('<I8xI', out, layout_at, len(members), members_at)
    struct.pack_into('<2I2fBB2x3f', out, tex_at, tex_path, tex_type, 1.0, 1.0,
                     0, 0, 0.0, 0.0, 0.0)
    if light_tex is not None:
        struct.pack_into('<2I2fBB2x3f', out, tex2_at, light_path, light_type, 1.0, 1.0,
                         0, 0, 0.0, 0.0, 0.0)
    return bytes(out)
