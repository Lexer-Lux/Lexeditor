"""Structured editing for Final Fantasy X ``item_shop.bin`` inventories."""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import FFXTableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_shop.bin"
RECORD_SIZE = 0x22
SLOT_COUNT = 0x10


class ItemShopError(ValueError):
    """Raised when an FFX item shop table or requested edit is invalid."""


@dataclass(frozen=True)
class ItemShopRecord:
    record_id: int
    legacy_rate: int
    item_ids: tuple[int, ...]

    @property
    def occupied_slots(self) -> int:
        return sum(item_id != 0 for item_id in self.item_ids)


def _u16(raw: bytes, offset: int) -> int:
    return raw[offset] | (raw[offset + 1] << 8)


def parse_item_shops(data: bytes) -> tuple[ItemShopRecord, ...]:
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise ItemShopError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise ItemShopError(
            f"item_shop.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )
    rows = []
    for record_id in range(table.min_index, table.max_index + 1):
        raw = table.record(record_id)
        rows.append(ItemShopRecord(
            record_id=record_id,
            legacy_rate=_u16(raw, 0),
            item_ids=tuple(_u16(raw, 2 + slot * 2) for slot in range(SLOT_COUNT)),
        ))
    return tuple(rows)


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool):
        raise ItemShopError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ItemShopError(f"{label} must be an integer") from error
    if not minimum <= parsed <= maximum:
        raise ItemShopError(f"{label} must be between {minimum} and {maximum}")
    return parsed


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch selected inventory slots, preserving the unused rate and all other bytes."""
    if not isinstance(edits, list) or not edits:
        raise ItemShopError("At least one item-shop edit is required")
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise ItemShopError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise ItemShopError(
            f"item_shop.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )

    output = bytearray(table.data)
    seen_records: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise ItemShopError("Each item-shop edit must be an object")
        record_id = _bounded(edit.get("id"), table.min_index, table.max_index, "Shop ID")
        if record_id in seen_records:
            raise ItemShopError(f"Duplicate item-shop edit: {record_id}")
        seen_records.add(record_id)
        slots = edit.get("slots")
        if not isinstance(slots, list) or not slots:
            raise ItemShopError(f"Shop {record_id} must include at least one slot edit")
        seen_slots: set[int] = set()
        record_offset = table.record_offset(record_id)
        for slot_edit in slots:
            if not isinstance(slot_edit, dict):
                raise ItemShopError("Each item-shop slot edit must be an object")
            slot = _bounded(slot_edit.get("slot"), 0, SLOT_COUNT - 1, "Shop slot")
            if slot in seen_slots:
                raise ItemShopError(f"Duplicate slot {slot} in shop {record_id}")
            seen_slots.add(slot)
            item_id = _bounded(slot_edit.get("itemId"), 0, 0xFFFF, "Item ID")
            offset = record_offset + 2 + slot * 2
            output[offset] = item_id & 0xFF
            output[offset + 1] = item_id >> 8
    return bytes(output)


def payload(data: bytes) -> dict:
    rows = parse_item_shops(data)
    table = parse_table(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "slotCount": SLOT_COUNT,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "legacyRate": row.legacy_rate,
            "occupiedSlots": row.occupied_slots,
            "itemIds": list(row.item_ids),
        } for row in rows],
    }
