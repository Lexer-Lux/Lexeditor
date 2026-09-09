from __future__ import annotations

import struct

import pytest

from games.ffx_x2.ctb_base import CtbBaseError, apply_edits, parse_ctb_base, payload


def _table(rows: list[tuple[int, int]], min_index: int = 0, trailing: bytes = b"TAIL") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"CTBBASE!"
    struct.pack_into("<HHHH", header, 0x08, min_index, min_index + len(rows) - 1, 2, 2 * len(rows))
    header[0x10:0x14] = b"KEEP"
    records = bytes(value for row in rows for value in row)
    return bytes(header) + records + trailing


def test_ctb_base_maps_agility_and_icv_range():
    data = _table([(10, 3), (20, 7)], min_index=4)
    rows = parse_ctb_base(data)
    assert rows[0].record_id == 4
    assert rows[0].agility == 5
    assert rows[0].tick_speed == 10
    assert rows[0].icv_bonus == 3
    assert rows[0].min_icv == 27
    assert rows[0].max_icv == 30
    assert payload(data)["recordSize"] == 2


def test_ctb_edit_changes_only_selected_two_byte_record():
    original = _table([(10, 3), (20, 7), (30, 9)], min_index=1, trailing=b"opaque")
    edited = apply_edits(original, [{"id": 2, "tickSpeed": 44, "icvBonus": 11}])
    rows = parse_ctb_base(edited)
    assert [(row.tick_speed, row.icv_bonus) for row in rows] == [(10, 3), (44, 11), (30, 9)]
    assert edited[:0x16] == original[:0x16]
    assert edited[0x18:] == original[0x18:]
    assert edited[-6:] == b"opaque"


def test_ctb_base_rejects_wrong_record_size():
    data = bytearray(_table([(10, 3)]))
    struct.pack_into("<H", data, 0x0C, 4)
    struct.pack_into("<H", data, 0x0E, 4)
    data[0x14:0x16] = b"\x00\x00"
    with pytest.raises(CtbBaseError, match="record size"):
        parse_ctb_base(bytes(data))


def test_ctb_base_rejects_duplicate_and_out_of_range_edits():
    data = _table([(10, 3)])
    with pytest.raises(CtbBaseError, match="Duplicate"):
        apply_edits(data, [
            {"id": 0, "tickSpeed": 10, "icvBonus": 3},
            {"id": 0, "tickSpeed": 11, "icvBonus": 4},
        ])
    with pytest.raises(CtbBaseError, match="Tick speed"):
        apply_edits(data, [{"id": 0, "tickSpeed": 256, "icvBonus": 3}])
