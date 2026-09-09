from __future__ import annotations

import struct

import pytest

from games.ffx_x2.ffx2_abilities import FFX2AbilityError, apply_edits, parse_abilities, payload
from games.ffx_x2.ffx2_table import FFX2TableError, parse_table


def _record(name_offset: int, name_key: int, desc_offset: int, desc_key: int,
            anim1: int, anim2: int, fill: int = 0xCC) -> bytes:
    raw = bytearray([fill] * 0x8C)
    struct.pack_into("<HHHHHH", raw, 0, name_offset, name_key, desc_offset, desc_key, anim1, anim2)
    return bytes(raw)


def _table(records: list[bytes], min_index: int = 0, trailing: bytes = b"STRINGS") -> bytes:
    header = bytearray(0x20)
    header[:0x0C] = b"X2COMMAND!!!"
    struct.pack_into("<IIII", header, 0x0C, min_index, min_index + len(records) - 1, 0x8C, 0x8C * len(records))
    header[0x1C:0x20] = b"KEEP"
    return bytes(header) + b"".join(records) + trailing


def test_ffx2_table_uses_u32_header_and_preserves_tail():
    data = _table([_record(1, 2, 3, 4, 5, 6)], min_index=0x1234, trailing=b"opaque")
    table = parse_table(data)
    assert table.min_index == 0x1234
    assert table.max_index == 0x1234
    assert table.record_size == 0x8C
    assert table.records_end == 0x20 + 0x8C
    assert table.data[table.records_end:] == b"opaque"


def test_ffx2_table_rejects_inconsistent_record_bytes():
    data = bytearray(_table([_record(1, 2, 3, 4, 5, 6)]))
    struct.pack_into("<I", data, 0x18, 0x8B)
    with pytest.raises(FFX2TableError, match="inconsistent"):
        parse_table(bytes(data))


def test_ffx2_ability_parses_proved_header_fields_and_animations():
    data = _table([_record(0x10, 0x11, 0x20, 0x21, 0x1234, 0x5678)], min_index=7)
    row = parse_abilities(data)[0]
    assert row.record_id == 7
    assert (row.name_offset, row.name_key) == (0x10, 0x11)
    assert (row.description_offset, row.description_key) == (0x20, 0x21)
    assert (row.animation_1, row.animation_2) == (0x1234, 0x5678)
    assert payload(data)["recordSize"] == 0x8C


def test_ffx2_ability_edit_changes_only_animation_fields():
    original = _table([
        _record(0x10, 0x11, 0x20, 0x21, 0x1234, 0x5678, fill=0xAA),
        _record(0x30, 0x31, 0x40, 0x41, 0x2222, 0x3333, fill=0xBB),
    ], min_index=4, trailing=b"opaque-strings")
    edited = apply_edits(original, [{"id": 4, "animation1": 0xBEEF, "animation2": 0xCAFE}])
    rows = parse_abilities(edited)
    assert (rows[0].animation_1, rows[0].animation_2) == (0xBEEF, 0xCAFE)
    assert (rows[1].animation_1, rows[1].animation_2) == (0x2222, 0x3333)
    record_start = 0x20
    assert edited[:record_start + 0x08] == original[:record_start + 0x08]
    assert edited[record_start + 0x0C:] == original[record_start + 0x0C:]
    assert edited[-14:] == b"opaque-strings"


def test_ffx2_ability_rejects_wrong_record_size_and_duplicate_edits():
    data = bytearray(_table([_record(1, 2, 3, 4, 5, 6)]))
    struct.pack_into("<I", data, 0x14, 0x8A)
    struct.pack_into("<I", data, 0x18, 0x8A)
    with pytest.raises(FFX2AbilityError, match="record size"):
        parse_abilities(bytes(data))

    valid = _table([_record(1, 2, 3, 4, 5, 6)])
    with pytest.raises(FFX2AbilityError, match="Duplicate"):
        apply_edits(valid, [
            {"id": 0, "animation1": 1, "animation2": 2},
            {"id": 0, "animation1": 3, "animation2": 4},
        ])
