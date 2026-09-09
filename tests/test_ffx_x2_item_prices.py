from __future__ import annotations

import struct

import pytest

from games.ffx_x2.item_prices import ItemPriceError, apply_edits, parse_item_prices, payload


def _table(prices: list[int], min_index: int = 0, trailing: bytes = b"TAIL") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"ITEMRATE"
    struct.pack_into("<HHHH", header, 0x08, min_index, min_index + len(prices) - 1, 4, 4 * len(prices))
    header[0x10:0x14] = b"KEEP"
    records = b"".join(struct.pack("<I", price) for price in prices)
    return bytes(header) + records + trailing


def test_item_prices_map_table_order_to_item_command_ids():
    data = _table([50, 1250, 0x12345678], min_index=7)
    rows = parse_item_prices(data)
    assert [row.record_id for row in rows] == [7, 8, 9]
    assert [row.command_id for row in rows] == [0x2000, 0x2001, 0x2002]
    assert [row.gil_price for row in rows] == [50, 1250, 0x12345678]
    assert payload(data)["commandBase"] == 0x2000


def test_item_price_edit_changes_only_selected_u32_record():
    original = _table([50, 100, 150], min_index=2, trailing=b"opaque")
    edited = apply_edits(original, [{"id": 3, "gilPrice": 999999}])
    rows = parse_item_prices(edited)
    assert [row.gil_price for row in rows] == [50, 999999, 150]
    assert edited[:0x18] == original[:0x18]
    assert edited[0x1C:] == original[0x1C:]
    assert edited[-6:] == b"opaque"


def test_item_prices_reject_wrong_record_size():
    data = bytearray(_table([50]))
    struct.pack_into("<H", data, 0x0C, 2)
    struct.pack_into("<H", data, 0x0E, 2)
    with pytest.raises(ItemPriceError, match="record size"):
        parse_item_prices(bytes(data))


def test_item_prices_reject_duplicates_and_out_of_range_values():
    data = _table([50])
    with pytest.raises(ItemPriceError, match="Duplicate"):
        apply_edits(data, [
            {"id": 0, "gilPrice": 10},
            {"id": 0, "gilPrice": 20},
        ])
    with pytest.raises(ItemPriceError, match="Gil price"):
        apply_edits(data, [{"id": 0, "gilPrice": 0x1_0000_0000}])
