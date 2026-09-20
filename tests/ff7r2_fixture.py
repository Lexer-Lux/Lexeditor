from __future__ import annotations

import struct


def _serialized_name(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([(len(raw) >> 8) & 0x7F, len(raw) & 0xFF]) + raw


def fixture() -> bytes:
    names = ["None", "Cloud", "Tifa", "HPMax", "MPMax", "Strength", "Spilit"]
    blob = bytearray(b"\0" * 64)
    names_offset = len(blob)
    for name in names:
        blob += _serialized_name(name)
    names_size = len(blob) - names_offset
    while len(blob) % 8:
        blob += b"\0"
    hashes_offset = len(blob)
    blob += b"\0\0\x64\xc1\0\0\0\0" + b"\0" * (8 * len(names))
    hashes_size = len(blob) - hashes_offset
    import_offset = len(blob)
    export_offset = import_offset
    blob += b"\0" * 72
    bundles_offset = len(blob)
    blob += struct.pack("<II", 0, 0)
    graph_offset = len(blob)
    blob += struct.pack("<i", 0)
    graph_size = 4

    inner = len(blob)
    blob += struct.pack("<iI", 0, 0)
    blob += struct.pack("<i", 0)
    archive = len(blob)
    blob += b"\0" * 12
    frozen_start = len(blob)

    root = bytearray(b"\0" * 88)
    keys_at = 88
    properties_at = keys_at + 2 * 20
    entries_at = properties_at + 4 * 12
    struct.pack_into("<Qii", root, 0, (keys_at << 1) | 1, 2, 2)
    struct.pack_into("<Qii", root, 40, 0, 0, 0)
    prop_header = 56
    struct.pack_into("<Qii", root, prop_header,
                     ((properties_at - prop_header) << 1) | 1, 4, 4)
    entry_header = 72
    struct.pack_into("<Qii", root, entry_header,
                     ((entries_at - entry_header) << 1) | 1, 2, 2)
    blob += root

    key_positions = []
    for index in range(2):
        key_positions.append(len(blob) - frozen_start)
        blob += b"\0" * 8 + struct.pack("<iiI", index, -1, 1)

    prop_types = [7, 7, 5, 5]
    prop_positions = []
    for type_id in prop_types:
        prop_positions.append(len(blob) - frozen_start)
        blob += b"\0" * 8 + struct.pack("<i", type_id)

    for row in [(1000, 50, 30, 22), (900, 60, 25, 30)]:
        blob += struct.pack("<iihh", *row)

    frozen_size = len(blob) - frozen_start
    struct.pack_into("<IIHH", blob, archive, frozen_size, frozen_size, 0, 0)

    minimal = [
        (1, key_positions[0]), (2, key_positions[1]),
        (3, prop_positions[0]), (4, prop_positions[1]),
        (5, prop_positions[2]), (6, prop_positions[3]),
    ]
    blob += struct.pack("<iii", 0, 0, len(minimal))
    for name_index, offset in minimal:
        blob += struct.pack("<iII", name_index, 0, 1)
        blob += struct.pack("<I", offset)

    struct.pack_into(
        "<9i", blob, 24,
        names_offset, names_size, hashes_offset, hashes_size,
        import_offset, export_offset, bundles_offset, graph_offset, graph_size,
    )
    assert inner == graph_offset + graph_size
    return bytes(blob)
