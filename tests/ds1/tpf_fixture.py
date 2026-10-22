"""Tiny TPF/DDS builders: Pillow-decodable textures for geometry tests."""
import struct


def make_dds_rgba(width, height, pixels):
    """Uncompressed RGBA DDS Pillow decodes: pixels row-major (r, g, b, a)."""
    assert len(pixels) == width * height
    head = bytearray(128)
    head[0:4] = b'DDS '
    struct.pack_into('<I', head, 4, 124)
    struct.pack_into('<I', head, 8, 0x1 | 0x2 | 0x4 | 0x1000)
    struct.pack_into('<2I', head, 12, height, width)
    struct.pack_into('<I', head, 20, width * 4)
    struct.pack_into('<I', head, 28, 1)
    struct.pack_into('<I', head, 76, 32)
    struct.pack_into('<I', head, 80, 0x41)
    struct.pack_into('<I', head, 88, 32)
    struct.pack_into('<4I', head, 92, 0xFF0000, 0xFF00, 0xFF, 0xFF000000)
    struct.pack_into('<I', head, 108, 0x1000)
    body = bytearray()
    for red, green, blue, alpha in pixels:
        body += bytes((blue, green, red, alpha))
    return bytes(head) + bytes(body)


def make_tpf(entries):
    """entries: [(name, dds bytes)]."""
    names = [name.encode('shift_jis') + bytes((0,)) for name, _ in entries]
    table_end = 16 + len(entries) * 20
    name_base = table_end
    blob_base = name_base + sum(map(len, names))
    head = bytearray(16)
    head[0:4] = b'TPF' + bytes((0,))
    struct.pack_into('<I', head, 8, len(entries))
    out = bytes(head)
    name_off, blob_off = name_base, blob_base
    records = []
    for (_, blob), encoded in zip(entries, names):
        records.append(struct.pack('<5I', blob_off, len(blob), 0, name_off, 0))
        name_off += len(encoded)
        blob_off += len(blob)
    out += b''.join(records) + b''.join(names)
    out += b''.join(blob for _, blob in entries)
    return out
