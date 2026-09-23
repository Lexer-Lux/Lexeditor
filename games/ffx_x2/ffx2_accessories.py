"""Conservative structured editing for FFX-2 ``accessory.bin``.

The record layout is cross-checked against the public FFX2 010 Editor template.
Lexeditor currently writes only four base ability IDs and the base price; all
other fields, creature-extension data and trailing strings remain byte-identical.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

from .ffx2_table import FFX2TableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/accessory.bin"
RECORD_SIZE = 0x54
ABILITY_OFFSET = 0x18
ABILITY_COUNT = 4
PRICE_OFFSET = 0x20


class FFX2AccessoryError(ValueError):
    """Raised when FFX-2 accessory data or an edit is invalid."""


@dataclass(frozen=True)
class AccessoryRecord:
    record_id: int
    name_offset: int
    name_key: int
    help_offset: int
    help_key: int
    icon: int
    ability_ids: tuple[int, ...]
    price: int


def _u16(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<H", raw, offset)[0]


def _table(data: bytes):
    try:
        table = parse_table(data)
    except FFX2TableError as error:
        raise FFX2AccessoryError(str(error)) from error
    if table.min_index != 0:
        raise FFX2AccessoryError(
            f"accessory.bin does not start at record zero as proved by the template: {table.min_index}"
        )
    if table.record_size != RECORD_SIZE:
        raise FFX2AccessoryError(
            f"accessory.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )
    return table


def parse_accessories(data: bytes) -> tuple[AccessoryRecord, ...]:
    table = _table(data)
    rows = []
    for record_id in range(table.min_index, table.max_index + 1):
        raw = table.record(record_id)
        rows.append(AccessoryRecord(
            record_id=record_id,
            name_offset=_u16(raw, 0x00),
            name_key=_u16(raw, 0x02),
            help_offset=_u16(raw, 0x04),
            help_key=_u16(raw, 0x06),
            icon=raw[0x0B],
            ability_ids=tuple(_u16(raw, ABILITY_OFFSET + slot * 2) for slot in range(ABILITY_COUNT)),
            price=struct.unpack_from("<I", raw, PRICE_OFFSET)[0],
        ))
    return tuple(rows)


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool):
        raise FFX2AccessoryError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise FFX2AccessoryError(f"{label} must be an integer") from error
    if not minimum <= parsed <= maximum:
        raise FFX2AccessoryError(f"{label} must be between {minimum} and {maximum}")
    return parsed


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch selected base ability IDs and prices, preserving every other byte."""
    if not isinstance(edits, list) or not edits:
        raise FFX2AccessoryError("At least one accessory edit is required")
    table = _table(data)
    output = bytearray(table.data)
    seen_records: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise FFX2AccessoryError("Each accessory edit must be an object")
        record_id = _bounded(edit.get("id"), table.min_index, table.max_index, "Accessory record ID")
        if record_id in seen_records:
            raise FFX2AccessoryError(f"Duplicate accessory edit: {record_id}")
        seen_records.add(record_id)
        record_offset = table.record_offset(record_id)

        if "price" in edit:
            price = _bounded(edit.get("price"), 0, 0xFFFFFFFF, "Accessory price")
            struct.pack_into("<I", output, record_offset + PRICE_OFFSET, price)

        abilities = edit.get("abilities", [])
        if not isinstance(abilities, list):
            raise FFX2AccessoryError("Accessory abilities must be a list")
        seen_slots: set[int] = set()
        for ability_edit in abilities:
            if not isinstance(ability_edit, dict):
                raise FFX2AccessoryError("Each accessory ability edit must be an object")
            slot = _bounded(ability_edit.get("slot"), 0, ABILITY_COUNT - 1, "Accessory ability slot")
            if slot in seen_slots:
                raise FFX2AccessoryError(f"Duplicate ability slot {slot} in accessory {record_id}")
            seen_slots.add(slot)
            ability_id = _bounded(ability_edit.get("abilityId"), 0, 0xFFFF, "Ability ID")
            struct.pack_into("<H", output, record_offset + ABILITY_OFFSET + slot * 2, ability_id)

        if "price" not in edit and not abilities:
            raise FFX2AccessoryError(f"Accessory {record_id} has no writable edits")
    return bytes(output)


def payload(data: bytes) -> dict:
    table = _table(data)
    rows = parse_accessories(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "abilityCount": ABILITY_COUNT,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "nameOffset": row.name_offset,
            "nameKey": row.name_key,
            "helpOffset": row.help_offset,
            "helpKey": row.help_key,
            "icon": row.icon,
            "abilityIds": list(row.ability_ids),
            "price": row.price,
        } for row in rows],
    }
