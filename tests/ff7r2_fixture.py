from __future__ import annotations

import struct


def _serialized_name(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([(len(raw) >> 8) & 0x7F, len(raw) & 0xFF]) + raw


def fixture() -> bytes:
    records = ["Cloud", "Tifa"] + [f"TestCharacter{index:02d}" for index in range(3, 25)]
    properties = ["HPMax", "MPMax", "Strength", "Spilit", "Mode"]
    names = ["None", *records, *properties, "ModeA", "ModeB"]
    name_index = {name: index for index, name in enumerate(names)}

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
    blob += struct.pack("<iI", name_index["None"], 0)
    blob += struct.pack("<i", 0)
    archive = len(blob)
    blob += b"\0" * 12
    frozen_start = len(blob)

    root = bytearray(b"\0" * 88)
    keys_at = 88
    properties_at = keys_at + len(records) * 20
    entries_at = properties_at + len(properties) * 12
    struct.pack_into("<Qii", root, 0, (keys_at << 1) | 1, len(records), len(records))
    struct.pack_into("<Qii", root, 40, 0, 0, 0)
    prop_header = 56
    struct.pack_into("<Qii", root, prop_header,
                     ((properties_at - prop_header) << 1) | 1,
                     len(properties), len(properties))
    entry_header = 72
    struct.pack_into("<Qii", root, entry_header,
                     ((entries_at - entry_header) << 1) | 1,
                     len(records), len(records))
    blob += root

    key_positions = []
    for index, _name in enumerate(records):
        key_positions.append(len(blob) - frozen_start)
        blob += b"\0" * 8 + struct.pack("<iiI", index, -1, 1)

    prop_types = [7, 7, 5, 5, 11]
    prop_positions = []
    for type_id in prop_types:
        prop_positions.append(len(blob) - frozen_start)
        blob += b"\0" * 8 + struct.pack("<i", type_id)

    mode_positions = []
    for index, _name in enumerate(records):
        if index == 0:
            row = (1000, 50, 30, 22)
        elif index == 1:
            row = (900, 60, 25, 30)
        else:
            row = (800 + index * 25, 40 + index, 20 + index, 18 + index)
        blob += struct.pack("<iihh", *row)
        mode_positions.append(len(blob) - frozen_start)
        blob += b"\0" * 8  # Frozen NameProperty placeholder.

    frozen_size = len(blob) - frozen_start
    struct.pack_into("<IIHH", blob, archive, frozen_size, frozen_size, 0, 0)

    offset_groups: dict[int, list[int]] = {}
    def add_name_offset(serialized_name_index: int, offset: int) -> None:
        offset_groups.setdefault(serialized_name_index, []).append(offset)

    for record_name, offset in zip(records, key_positions):
        add_name_offset(name_index[record_name], offset)
    for property_name, offset in zip(properties, prop_positions):
        add_name_offset(name_index[property_name], offset)
    for index, offset in enumerate(mode_positions):
        add_name_offset(name_index["ModeA" if index % 2 == 0 else "ModeB"], offset)

    blob += struct.pack("<iii", 0, 0, len(offset_groups))
    for serialized_name_index, offsets in offset_groups.items():
        blob += struct.pack("<iII", serialized_name_index, 0, len(offsets))
        for offset in offsets:
            blob += struct.pack("<I", offset)

    struct.pack_into(
        "<9i", blob, 24,
        names_offset, names_size, hashes_offset, hashes_size,
        import_offset, export_offset, bundles_offset, graph_offset, graph_size,
    )
    assert inner == graph_offset + graph_size
    return bytes(blob)


def battle_item_possession_fixture() -> bytes:
    """Synthetic array fixture; property storage types are test-only, not live schema claims."""
    record = "EnemyTest"
    properties = [
        ("NormalItemName_Array", 11),
        ("NormalItemPercent_Array", 7),
        ("RareItemName_Array", 11),
        ("RareItemPercent_Array", 7),
        ("StealItemName_Array", 11),
        ("StealItemQuantity_Array", 2),
        ("StealFaildCountArrayIndex", 7),
    ]
    arrays = {
        "NormalItemName_Array": ["Potion", "HiPotion"],
        "NormalItemPercent_Array": [25, 75],
        "RareItemName_Array": ["Ether"],
        "RareItemPercent_Array": [10],
        "StealItemName_Array": ["Potion", "Ether"],
        "StealItemQuantity_Array": [1, 2],
    }
    extra_names = ["Potion", "HiPotion", "Ether"]
    names = ["None", record, *[name for name, _type in properties], *extra_names]
    name_index = {name: index for index, name in enumerate(names)}

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
    blob += struct.pack("<iI", name_index["None"], 0)
    blob += struct.pack("<i", 0)
    archive = len(blob)
    blob += b"\0" * 12
    frozen_start = len(blob)

    root = bytearray(b"\0" * 88)
    keys_at = 88
    properties_at = keys_at + 20
    entries_at = properties_at + len(properties) * 12
    struct.pack_into("<Qii", root, 0, (keys_at << 1) | 1, 1, 1)
    struct.pack_into("<Qii", root, 40, 0, 0, 0)
    prop_header = 56
    struct.pack_into(
        "<Qii", root, prop_header,
        ((properties_at - prop_header) << 1) | 1,
        len(properties), len(properties),
    )
    entry_header = 72
    struct.pack_into("<Qii", root, entry_header,
                     ((entries_at - entry_header) << 1) | 1, 1, 1)
    blob += root

    key_position = len(blob) - frozen_start
    blob += b"\0" * 8 + struct.pack("<iiI", 0, -1, 1)

    prop_positions = []
    for _name, type_id in properties:
        prop_positions.append(len(blob) - frozen_start)
        blob += b"\0" * 8 + struct.pack("<i", type_id)

    def align(boundary: int) -> None:
        while (len(blob) - frozen_start) % boundary:
            blob.append(0)

    array_headers: dict[str, int] = {}
    for name, type_id in properties:
        if name.endswith("_Array"):
            align(8)
            array_headers[name] = len(blob)
            blob += b"\0" * 16
        else:
            align(4)
            assert type_id == 7
            blob += struct.pack("<i", 3)

    array_name_offsets: list[tuple[str, int]] = []
    for name, type_id in properties:
        if not name.endswith("_Array"):
            continue
        values = arrays[name]
        entry_align = 1 if type_id in (1, 2, 3) else 2 if type_id in (4, 5) else 4
        align(entry_align)
        target = len(blob)
        if type_id == 11:
            for value in values:
                align(4)
                array_name_offsets.append((value, len(blob) - frozen_start))
                blob += b"\0" * 8
        elif type_id == 7:
            for value in values:
                align(4)
                blob += struct.pack("<i", value)
        elif type_id == 2:
            blob += bytes(values)
        else:
            raise AssertionError(f"Unsupported synthetic array type {type_id}")
        header = array_headers[name]
        struct.pack_into(
            "<Qii", blob, header,
            ((target - header) << 1) | 1,
            len(values), len(values),
        )

    frozen_size = len(blob) - frozen_start
    struct.pack_into("<IIHH", blob, archive, frozen_size, frozen_size, 0, 0)

    offset_groups: dict[int, list[int]] = {}
    def add_name_offset(serialized_name_index: int, offset: int) -> None:
        offset_groups.setdefault(serialized_name_index, []).append(offset)

    add_name_offset(name_index[record], key_position)
    for (property_name, _type_id), offset in zip(properties, prop_positions):
        add_name_offset(name_index[property_name], offset)
    for value, offset in array_name_offsets:
        add_name_offset(name_index[value], offset)

    blob += struct.pack("<iii", 0, 0, len(offset_groups))
    for serialized_name_index, offsets in offset_groups.items():
        blob += struct.pack("<iII", serialized_name_index, 0, len(offsets))
        for offset in offsets:
            blob += struct.pack("<I", offset)

    struct.pack_into(
        "<9i", blob, 24,
        names_offset, names_size, hashes_offset, hashes_size,
        import_offset, export_offset, bundles_offset, graph_offset, graph_size,
    )
    assert inner == graph_offset + graph_size
    return bytes(blob)

