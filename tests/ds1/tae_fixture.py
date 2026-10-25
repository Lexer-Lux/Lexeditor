"""Synthetic TAE builder for unit tests (no game data)."""
import struct
import zlib


def _utf16(text):
    return text.encode("utf-16-le") + b"\0\0"


def build_tae():
    """Two animations: anim 3300 with four events (shared start slot,
    unknown type, empty event), anim 3301 with none and no name."""
    out = bytearray()
    out += b"TAE \x00\x00\x00\x00"
    out += struct.pack("<I", 0x1000B)  # version
    size_at = len(out)
    out += b"\0\0\0\0"  # file size, patched later
    out += struct.pack("<4I", 0x40, 1, 0x50, 0x70)
    out += struct.pack("<8I", 0x10002, 0, 0, 0, 0, 0, 0, 0)
    assert len(out) == 64
    out += bytes((1, 0, 1, 2, 2, 0, 1, 1, 1, 0, 0, 0)) + struct.pack("<I", 0)
    assert len(out) == 80
    out += struct.pack("<2I", 2087, 2)  # fileID, animCount
    anims_at = len(out)
    out += b"\0" * 8  # animsOff, groupsOff
    out += struct.pack("<4I", 0x90, 2, 0, 0)  # 0x90, count2, firstAnim, pad
    first_at = len(out) - 8
    assert len(out) == 112
    out += struct.pack("<2I", 1, 0x80) + b"\0" * 8
    assert len(out) == 128
    out += struct.pack("<4I", 2087, 2087, 0x50, 0)
    assert len(out) == 144
    out += struct.pack("<2I", 0, 152)  # unkE00, namesOff
    assert len(out) == 152
    out += struct.pack("<4I", 168, 194, 0, 0)  # skelOff, sibOff, 0, 0
    assert len(out) == 168
    out += _utf16("skeleton.HKX")
    assert len(out) == 194
    out += _utf16("c99900.SIB")

    def align():
        while len(out) % 4:
            out.append(0)

    align()
    anims_off = len(out)
    anim0_at = anims_off + 36
    anim1_at = anim0_at + 28
    out += struct.pack("<4I", 3300, anim0_at, 3301, anim1_at)
    groups_off = len(out)
    out += struct.pack("<2I", 1, groups_off + 8)
    out += struct.pack("<3I", 3300, 3301, anims_off)
    assert len(out) == anim0_at
    times_off = anim1_at + 28
    heads_off = times_off + 16
    data0_off = heads_off + 48
    data1_off = data0_off + 20
    data2_off = data1_off + 12
    data3_off = data2_off + 12
    file0_off = data3_off + 8
    name0_off = file0_off + 24
    name0 = _utf16("a87_3300.HKX")
    file1_off = name0_off + len(name0)
    out += struct.pack("<7I", 4, heads_off, 0, 0, 4, times_off, file0_off)
    out += struct.pack("<7I", 0, 0, 0, 0, 0, 0, file1_off)
    assert len(out) == times_off
    out += struct.pack("<4f", 0.0, 0.5, 1.0, 1.5)
    assert len(out) == heads_off
    # ev1 shares ev0's start slot; ev3 is an empty type-16 event.
    out += struct.pack("<3I", times_off, times_off + 4, data0_off)
    out += struct.pack("<3I", times_off, times_off + 8, data1_off)
    out += struct.pack("<3I", times_off + 12, times_off + 12, data2_off)
    out += struct.pack("<3I", times_off + 4, times_off + 8, data3_off)
    assert len(out) == data0_off
    out += struct.pack("<5i", 1, data0_off + 8, 0, 2, 100)
    assert len(out) == data1_off
    out += struct.pack("<3i", 66, data1_off + 8, 31)
    assert len(out) == data2_off
    out += struct.pack("<iII", 999, data2_off + 8, 0)
    assert len(out) == data3_off
    out += struct.pack("<iI", 16, 0)
    assert len(out) == file0_off
    out += struct.pack("<3I", 0, file0_off + 8, name0_off)
    out += struct.pack("<3i", 0, -1, 0)
    assert len(out) == name0_off
    out += name0
    assert len(out) == file1_off
    # Anim 3301 has no name: its name offset is end of file.
    out += struct.pack("<3I", 0, file1_off + 8, 0)
    out += struct.pack("<3i", 0, 0, 0)
    fno_at = file1_off + 8
    struct.pack_into("<I", out, fno_at, len(out))
    struct.pack_into("<I", out, size_at, len(out))
    struct.pack_into("<2I", out, anims_at, anims_off, groups_off)
    struct.pack_into("<I", out, first_at, anim0_at)
    return bytes(out)


def build_anibnd(members, wide=True):
    """A synthetic .anibnd.dcx: {name: payload} packed uncompressed.

    wide=False writes the older 20-byte records; a list of pairs
    instead of a dict packs duplicate names, like c3471's twin
    event file."""
    pairs = members.items() if isinstance(members, dict) else members
    entries = sorted(pairs)
    stride = 24 if wide else 20
    names = ["N:/FRPG/data/MOTION/" + name for name, _ in entries]
    encoded = [name.encode("shift_jis") + b"\0" for name in names]
    directory_end = 32 + len(entries) * stride
    names_end = directory_end + sum(map(len, encoded))
    plain = bytearray(names_end)
    plain[:4] = b"BND3"
    plain[4:12] = b"TEST0000"
    plain[12] = 0x74 if wide else 0x70
    struct.pack_into("<II", plain, 16, len(entries), names_end)
    name_offset = directory_end
    for (name, payload), raw in zip(entries, encoded):
        plain[name_offset:name_offset + len(raw)] = raw
        name_offset += len(raw)
    while len(plain) % 16:
        plain.append(0)
    name_offset = directory_end
    for index, ((name, payload), raw) in enumerate(zip(entries, encoded)):
        if payload:
            while len(plain) % 16:
                plain.append(0)
        record = 32 + index * stride
        if wide:
            struct.pack_into("<6I", plain, record, 0x40, len(payload),
                             len(plain), index, name_offset, len(payload))
        else:
            struct.pack_into("<5I", plain, record, 0x40, len(payload),
                             len(plain), index, name_offset)
        name_offset += len(raw)
        plain.extend(payload)
    compressed = zlib.compress(bytes(plain), 9)
    header = bytearray.fromhex("44435800000100000000001800000024000000240000002c"
                               "4443530000000000000000004443500044464c5400000020"
                               "090000000000000000000000000000000001010044434100"
                               "00000008")
    struct.pack_into(">II", header, 28, len(plain), len(compressed))
    return bytes(header) + compressed
