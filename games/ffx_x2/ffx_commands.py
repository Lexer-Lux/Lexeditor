"""Conservative structured editing for FFX ``command.bin`` animation IDs.

The localized FFX command table uses the common FFX fixed-record container.
Independent FFX tooling agrees that player-command records are 0x60 bytes and
that the two animation IDs are little-endian u16 values at record offsets
+0x10 and +0x12.  Lexeditor intentionally leaves every other byte opaque.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import FFXTableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/command.bin"
RECORD_SIZE = 0x60
ANIMATION_1_OFFSET = 0x10
ANIMATION_2_OFFSET = 0x12


class FFXCommandError(ValueError):
    """Raised when researched FFX command data or an edit is invalid."""


@dataclass(frozen=True)
class FFXCommandRecord:
    record_id: int
    animation_1: int
    animation_2: int


def _u16(raw: bytes, offset: int) -> int:
    return raw[offset] | (raw[offset + 1] << 8)


def _table(data: bytes):
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise FFXCommandError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise FFXCommandError(
            f"FFX command.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )
    return table


def parse_commands(data: bytes) -> tuple[FFXCommandRecord, ...]:
    table = _table(data)
    return tuple(
        FFXCommandRecord(
            record_id=record_id,
            animation_1=_u16(table.record(record_id), ANIMATION_1_OFFSET),
            animation_2=_u16(table.record(record_id), ANIMATION_2_OFFSET),
        )
        for record_id in range(table.min_index, table.max_index + 1)
    )


def _u16_value(value, label: str) -> int:
    if isinstance(value, bool):
        raise FFXCommandError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise FFXCommandError(f"{label} must be an integer") from error
    if not 0 <= parsed <= 0xFFFF:
        raise FFXCommandError(f"{label} must be between 0 and 65535")
    return parsed


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch only the two proved animation-ID fields in selected command records."""
    if not isinstance(edits, list) or not edits:
        raise FFXCommandError("At least one FFX command edit is required")
    table = _table(data)
    output = bytearray(table.data)
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise FFXCommandError("Each FFX command edit must be an object")
        if set(edit) != {"id", "animation1", "animation2"}:
            raise FFXCommandError("Each FFX command edit must contain only id, animation1 and animation2")
        try:
            record_id = int(edit["id"])
        except (TypeError, ValueError) as error:
            raise FFXCommandError("Command record ID must be an integer") from error
        if not table.min_index <= record_id <= table.max_index:
            raise FFXCommandError(
                f"Command record ID must be between {table.min_index} and {table.max_index}"
            )
        if record_id in seen:
            raise FFXCommandError(f"Duplicate FFX command edit: {record_id}")
        seen.add(record_id)
        animation_1 = _u16_value(edit["animation1"], "Animation 1")
        animation_2 = _u16_value(edit["animation2"], "Animation 2")
        offset = table.record_offset(record_id)
        output[offset + ANIMATION_1_OFFSET] = animation_1 & 0xFF
        output[offset + ANIMATION_1_OFFSET + 1] = animation_1 >> 8
        output[offset + ANIMATION_2_OFFSET] = animation_2 & 0xFF
        output[offset + ANIMATION_2_OFFSET + 1] = animation_2 >> 8
    return bytes(output)


def payload(data: bytes) -> dict:
    table = _table(data)
    rows = parse_commands(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "animation1": row.animation_1,
            "animation2": row.animation_2,
        } for row in rows],
    }
