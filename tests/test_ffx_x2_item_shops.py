from __future__ import annotations

import struct

import pytest

from games.ffx_x2.item_shops import ItemShopError, apply_edits, parse_item_shops, payload


def _record(rate: int, items: list[int]) -> bytes:
    assert len(items) == 16
    raw = bytearray(0x22)
    struct.pack_into("<H", raw, 0, rate)
    for slot, item_id in enumerate(items):
        struct.pack_into("<H", raw, 2 + slot * 2, item_id)
    return bytes(raw)


def _table(records: list[bytes], min_index: int = 3, trailing: bytes = b"TAIL") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"SHOPDATA"
    struct.pack_into("<HHHH", header, 0x08, min_index, min_index + len(records) - 1, 0x22, 0x22 * len(records))
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + b"".join(records) + trailing


def test_item_shops_parse_fixed_inventory_slots():
    data = _table([
        _record(125, [0, 0x1001, 0x1002] + [0] * 13),
        _record(100, [0x2000] * 16),
    ])
    rows = parse_item_shops(data)
    assert rows[0].record_id == 3
    assert rows[0].legacy_rate == 125
    assert rows[0].item_ids[1:3] == (0x1001, 0x1002)
    assert rows[0].occupied_slots == 2
    assert payload(data)["slotCount"] == 16


def test_item_shop_edits_preserve_unused_rate_other_slots_and_tail():
    original = _table([_record(777, list(range(16)))], min_index=9, trailing=b"opaque")
    edited = apply_edits(original, [{"id": 9, "slots": [
        {"slot": 2, "itemId": 0xBEEF},
        {"slot": 15, "itemId": 0},
    ]}])
    row = parse_item_shops(edited)[0]
    assert row.legacy_rate == 777
    assert row.item_ids[2] == 0xBEEF
    assert row.item_ids[1] == 1
    assert row.item_ids[15] == 0
    assert edited[:0x16] == original[:0x16]  # header plus untouched legacy-rate bytes
    assert edited[-6:] == b"opaque"


def test_item_shop_rejects_wrong_record_size():
    data = bytearray(_table([_record(100, [0] * 16)]))
    struct.pack_into("<H", data, 0x0C, 0x20)
    struct.pack_into("<H", data, 0x0E, 0x20)
    with pytest.raises(ItemShopError, match="record size"):
        parse_item_shops(bytes(data))


def test_item_shop_rejects_duplicate_slots():
    data = _table([_record(100, [0] * 16)])
    with pytest.raises(ItemShopError, match="Duplicate slot"):
        apply_edits(data, [{"id": 3, "slots": [
            {"slot": 1, "itemId": 3}, {"slot": 1, "itemId": 4},
        ]}])
