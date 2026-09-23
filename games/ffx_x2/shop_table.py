"""Shared fixed-record logic for FFX 16-slot shop tables."""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import FFXTableError, parse_table


RECORD_SIZE = 0x22
SLOT_COUNT = 0x10


class ShopTableError(ValueError):
    """Raised when a proved FFX shop table or requested slot edit is invalid."""


@dataclass(frozen=True)
class SlotShopRecord:
    record_id: int
    legacy_rate: int
    slot_ids: tuple[int, ...]

    @property
    def occupied_slots(self) -> int:
        return sum(value != 0 for value in self.slot_ids)


def _u16(raw: bytes, offset: int) -> int:
    return raw[offset] | (raw[offset + 1] << 8)


def _table(data: bytes, filename: str):
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise ShopTableError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise ShopTableError(
            f"{filename} record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )
    return table


def parse_shops(data: bytes, filename: str) -> tuple[SlotShopRecord, ...]:
    table = _table(data, filename)
    rows = []
    for record_id in range(table.min_index, table.max_index + 1):
        raw = table.record(record_id)
        rows.append(SlotShopRecord(
            record_id=record_id,
            legacy_rate=_u16(raw, 0),
            slot_ids=tuple(_u16(raw, 2 + slot * 2) for slot in range(SLOT_COUNT)),
        ))
    return tuple(rows)


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool):
        raise ShopTableError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ShopTableError(f"{label} must be an integer") from error
    if not minimum <= parsed <= maximum:
        raise ShopTableError(f"{label} must be between {minimum} and {maximum}")
    return parsed


def apply_slot_edits(data: bytes, edits: list[dict], *, filename: str,
                     value_key: str, value_label: str) -> bytes:
    """Patch selected 16-bit slots and leave the leading legacy field untouched."""
    if not isinstance(edits, list) or not edits:
        raise ShopTableError(f"At least one {filename} edit is required")
    table = _table(data, filename)
    output = bytearray(table.data)
    seen_records: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise ShopTableError(f"Each {filename} edit must be an object")
        record_id = _bounded(edit.get("id"), table.min_index, table.max_index, "Shop ID")
        if record_id in seen_records:
            raise ShopTableError(f"Duplicate shop edit: {record_id}")
        seen_records.add(record_id)
        slots = edit.get("slots")
        if not isinstance(slots, list) or not slots:
            raise ShopTableError(f"Shop {record_id} must include at least one slot edit")
        seen_slots: set[int] = set()
        record_offset = table.record_offset(record_id)
        for slot_edit in slots:
            if not isinstance(slot_edit, dict):
                raise ShopTableError("Each shop slot edit must be an object")
            slot = _bounded(slot_edit.get("slot"), 0, SLOT_COUNT - 1, "Shop slot")
            if slot in seen_slots:
                raise ShopTableError(f"Duplicate slot {slot} in shop {record_id}")
            seen_slots.add(slot)
            value = _bounded(slot_edit.get(value_key), 0, 0xFFFF, value_label)
            offset = record_offset + 2 + slot * 2
            output[offset] = value & 0xFF
            output[offset + 1] = value >> 8
    return bytes(output)
