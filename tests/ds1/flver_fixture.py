"""Synthetic DS1-shaped models; no proprietary game bytes."""
import struct
import zlib

DCX_HEADER = bytes.fromhex(
    '44435800000100000000001800000024000000240000002c44435300000000000000000044435000'
    '44464c540000002009000000000000000000000000000000000101004443410000000008')


def make_chrbnd(flver_bytes, stem='c1200', extra=()):
    """A synthetic .chrbnd.dcx: the flver plus extra (name, bytes)
    members, such as the model's TPF textures."""
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
    compressed = zlib.compress(bytes(plain), 9)
    header = bytearray(DCX_HEADER)
    struct.pack_into('>II', header, 28, len(plain), len(compressed))
    return bytes(header) + compressed


def build_flver(strip=False, qloc=False):
    """A minimal FLVER2 0x2000C: 1 mesh (a quad), 1 material, 1 bone, 1 dummy.

    `strip` stores the faces as a triangle strip; `qloc` writes a lying
    DS1R layout (M[D].mtd with undeclared tangent bytes) for repair tests.
    """
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

    bone_at = len(out)  # bone
    out.extend(struct.pack('<3f', 0.0, 0.0, 0.0))
    out.extend(bytes(4))  # name offset
    out.extend(struct.pack('<3f', 0.0, 0.0, 0.0))
    out.extend(struct.pack('<2h', -1, -1))
    out.extend(struct.pack('<3f', 1.0, 1.0, 1.0))
    out.extend(struct.pack('<2h', -1, -1))
    out.extend(struct.pack('<3f', 0.0, 0.0, 0.0))
    out.extend(struct.pack('<I', 3))
    out.extend(struct.pack('<3f', 1.0, 1.0, 0.0))
    out.extend(bytes(52))

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

    def place(blob):
        at = len(out)
        out.extend(blob)
        return at

    members = [(0, 0x02, 0), (3, 0x13, 0), (5, 0x15, 0)]
    if qloc:
        members = [(0, 0x02, 0), (2, 0x11, 0), (3, 0x13, 0), (10, 0x13, 0), (5, 0x15, 0)]
    members_at = place(b''.join(struct.pack('<5I', 0, 0, fmt, semantic, inst)
                                for semantic, fmt, inst in members))

    mat_name = place(b'mat0\0')
    mtd = place(b'M[D].mtd\0')
    bone_name = place(b'root\0')
    tex_path = place(b'tex0\0')
    tex_type = place(b'g_Diffuse\0')
    box_at = place(struct.pack('<6f', 0.0, 0.0, 0.0, 1.0, 1.0, 0.0))
    bone_list_at = place(struct.pack('<i', 0))
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
    for x, y in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)):
        verts.extend(struct.pack('<3f', x, y, 0.0))
        if qloc:
            verts.extend(bytes((0, 0, 0, 0)))
            verts.extend(bytes((127, 127, 254, 127)))
            verts.extend(bytes(4))  # undeclared tangent bytes
            verts.extend(bytes((255, 255, 255, 255)))
        else:
            verts.extend(bytes((127, 127, 254, 127)))
        verts.extend(struct.pack('<2h', round(x * 1024), round(y * 1024)))
    vtx_at = place(bytes(verts))
    stride = 32 if qloc else 20

    struct.pack_into('<6s2sI', out, 0, b'FLVER\0', b'L\0', 0x2000C)
    struct.pack_into('<7I', out, 12, data_at, len(out) - data_at, 1, 1, 1, 1, 1)
    struct.pack_into('<6f', out, 40, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0)
    struct.pack_into('<2I', out, 64, 2, 2)
    struct.pack_into('<3B', out, 72, 16, 0, 0)
    struct.pack_into('<I', out, 76, 0)
    struct.pack_into('<3I', out, 80, 1, 1, 1)
    struct.pack_into('<I', out, 104, 0)
    struct.pack_into('<7I', out, mat_at, mat_name, mtd, 1, 0, 0, 0, 0)
    struct.pack_into('<I', out, bone_at + 12, bone_name)
    struct.pack_into('<B3xI8x8I', out, mesh_at, 1, 0, 0, 1, box_at, bone_list_at,
                     1, face_idx_at, 1, array_idx_at)
    struct.pack_into('<3x3Bh3I4xI4x', out, face_at, 0, 1 if strip else 0, 1, 0,
                     len(indices) // 2, idx_at - data_at, len(indices), 16)
    struct.pack_into('<4I8x2I', out, array_at, 0, 0, stride, 4, len(verts),
                     vtx_at - data_at)
    struct.pack_into('<I8xI', out, layout_at, len(members), members_at)
    struct.pack_into('<2I2fBB2x3f', out, tex_at, tex_path, tex_type, 1.0, 1.0,
                     0, 0, 0.0, 0.0, 0.0)
    return bytes(out)
