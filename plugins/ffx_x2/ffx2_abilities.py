"""Conservative structured editing for FFX-2 ``command.bin`` animation IDs."""
from __future__ import annotations

from dataclasses import dataclass

from .ffx2_table import FFX2TableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/command.bin"
RECORD_SIZE = 0x8C


class FFX2AbilityError(ValueError):
    """Raised when researched FFX-2 ability data or an edit is invalid."""


@dataclass(frozen=True)
class FFX2AbilityRecord:
    record_id: int
    name_offset: int
    name_key: int
    description_offset: int
    description_key: int
    animation_1: int
    animation_2: int


def _u16(raw: bytes, offset: int) -> int:
    return raw[offset] | (raw[offset + 1] << 8)


def parse_abilities(data: bytes) -> tuple[FFX2AbilityRecord, ...]:
    try:
        table = parse_table(data)
    except FFX2TableError as error:
        raise FFX2AbilityError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise FFX2AbilityError(
            f"FFX-2 command.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )
    rows = []
    for record_id in range(table.min_index, table.max_index + 1):
        raw = table.record(record_id)
        rows.append(FFX2AbilityRecord(
            record_id=record_id,
            name_offset=_u16(raw, 0x00),
            name_key=_u16(raw, 0x02),
            description_offset=_u16(raw, 0x04),
            description_key=_u16(raw, 0x06),
            animation_1=_u16(raw, 0x08),
            animation_2=_u16(raw, 0x0A),
        ))
    return tuple(rows)


def _u16_value(value, label: str) -> int:
    if isinstance(value, bool):
        raise FFX2AbilityError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise FFX2AbilityError(f"{label} must be an integer") from error
    if not 0 <= parsed <= 0xFFFF:
        raise FFX2AbilityError(f"{label} must be between 0 and 65535")
    return parsed


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch only the two proved animation-ID fields in selected ability records."""
    if not isinstance(edits, list) or not edits:
        raise FFX2AbilityError("At least one FFX-2 ability edit is required")
    try:
        table = parse_table(data)
    except FFX2TableError as error:
        raise FFX2AbilityError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise FFX2AbilityError(
            f"FFX-2 command.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )

    output = bytearray(table.data)
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise FFX2AbilityError("Each FFX-2 ability edit must be an object")
        try:
            record_id = int(edit.get("id"))
        except (TypeError, ValueError) as error:
            raise FFX2AbilityError("Ability record ID must be an integer") from error
        if not table.min_index <= record_id <= table.max_index:
            raise FFX2AbilityError(
                f"Ability record ID must be between {table.min_index} and {table.max_index}"
            )
        if record_id in seen:
            raise FFX2AbilityError(f"Duplicate FFX-2 ability edit: {record_id}")
        seen.add(record_id)
        animation_1 = _u16_value(edit.get("animation1"), "Animation 1")
        animation_2 = _u16_value(edit.get("animation2"), "Animation 2")
        offset = table.record_offset(record_id)
        output[offset + 0x08] = animation_1 & 0xFF
        output[offset + 0x09] = animation_1 >> 8
        output[offset + 0x0A] = animation_2 & 0xFF
        output[offset + 0x0B] = animation_2 >> 8
    return bytes(output)


def payload(data: bytes) -> dict:
    rows = parse_abilities(data)
    table = parse_table(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "nameOffset": row.name_offset,
            "nameKey": row.name_key,
            "descriptionOffset": row.description_offset,
            "descriptionKey": row.description_key,
            "animation1": row.animation_1,
            "animation2": row.animation_2,
        } for row in rows],
    }
