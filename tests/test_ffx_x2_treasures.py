from __future__ import annotations

import struct

import pytest

from games.ffx_x2.ffx_table import FFXTableError, parse_table
from games.ffx_x2.treasures import TreasureError, apply_edits, parse_treasures, payload


def _table(records: list[bytes], min_index: int = 0x10, trailing: bytes = b"TRAIL") -> bytes:
    assert records
    record_size = len(records[0])
    assert all(len(record) == record_size for record in records)
    header = bytearray(0x14)
    header[:8] = b"KERNEL!!"
    struct.pack_into(
        "<HHHH", header, 0x08,
        min_index, min_index + len(records) - 1,
        record_size, record_size * len(records),
    )
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + b"".join(records) + trailing


def test_common_ffx_table_preserves_trailing_bytes_and_indexes():
    data = _table([b"abcdXX", b"efghYY"], min_index=7, trailing=b"strings")
    table = parse_table(data)
    assert (table.min_index, table.max_index, table.record_size) == (7, 8, 6)
    assert table.record(8) == b"efghYY"
    assert data[table.records_end:] == b"strings"


def test_common_ffx_table_rejects_inconsistent_record_region():
    data = bytearray(_table([b"abcd", b"efgh"]))
    struct.pack_into("<H", data, 0x0E, 7)
    with pytest.raises(FFXTableError, match="record byte count"):
        parse_table(bytes(data))


def test_treasure_parser_maps_proved_reward_fields():
    data = _table([
        bytes([0x00, 50, 0x00, 0x00, 0xAA, 0xBB]),
        bytes([0x02, 3, 0x34, 0x12, 0xCC, 0xDD]),
        bytes([0x0A, 1, 0x2A, 0x00, 0xEE, 0xFF]),
    ], min_index=0x20)
    rows = parse_treasures(data)
    assert rows[0].record_id == 0x20
    assert rows[0].summary == "5000 gil"
    assert (rows[1].kind_name, rows[1].quantity, rows[1].type_id) == ("Item", 3, 0x1234)
    assert rows[2].kind_name == "Key Item"
    assert payload(data)["baselineSha256"]


def test_treasure_edits_change_only_four_proved_bytes():
    original = _table([
        bytes([0x02, 1, 0x10, 0x00, 0xA1, 0xA2]),
        bytes([0x05, 1, 0x20, 0x00, 0xB1, 0xB2]),
    ], min_index=4, trailing=b"opaque strings")
    edited = apply_edits(original, [{"id": 5, "kind": 0, "quantity": 99, "typeId": 0x4321}])
    table = parse_table(edited)
    assert table.record(4) == bytes([0x02, 1, 0x10, 0x00, 0xA1, 0xA2])
    assert table.record(5) == bytes([0x00, 99, 0x21, 0x43, 0xB1, 0xB2])
    assert edited[:0x14] == original[:0x14]
    assert edited[table.records_end:] == b"opaque strings"


def test_treasure_edits_reject_duplicates_and_out_of_range_values():
    data = _table([bytes([0, 1, 0, 0])])
    with pytest.raises(TreasureError, match="Duplicate"):
        apply_edits(data, [
            {"id": 0x10, "kind": 0, "quantity": 1, "typeId": 0},
            {"id": 0x10, "kind": 2, "quantity": 1, "typeId": 1},
        ])
    with pytest.raises(TreasureError, match="Quantity"):
        apply_edits(data, [{"id": 0x10, "kind": 0, "quantity": 256, "typeId": 0}])
