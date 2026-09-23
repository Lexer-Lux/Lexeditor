"""Conservative structured editing for proved FFX ability-table animation IDs.

Independent FFX tooling agrees that ``command.bin``, ``item.bin``,
``monmagic1.bin`` and ``monmagic2.bin`` share the same animation-ID fields:
little-endian u16 values at record offsets +0x10 and +0x12. Player command and
item records are 0x60 bytes; monster-magic records omit the four-byte player
extension and are 0x5C bytes. Lexeditor intentionally leaves every other byte
opaque.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import FFXTableError, parse_table
from .treasures import sha256_bytes


ANIMATION_1_OFFSET = 0x10
ANIMATION_2_OFFSET = 0x12


@dataclass(frozen=True)
class FFXAbilityTableSpec:
    key: str
    label: str
    archive_path: str
    record_size: int


TABLES = {
    "command": FFXAbilityTableSpec(
        key="command",
        label="Commands",
        archive_path="FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/command.bin",
        record_size=0x60,
    ),
    "item": FFXAbilityTableSpec(
        key="item",
        label="Items",
        archive_path="FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/item.bin",
        record_size=0x60,
    ),
    "monmagic1": FFXAbilityTableSpec(
        key="monmagic1",
        label="Monster Magic 1",
        archive_path="FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/monmagic1.bin",
        record_size=0x5C,
    ),
    "monmagic2": FFXAbilityTableSpec(
        key="monmagic2",
        label="Monster Magic 2",
        archive_path="FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/monmagic2.bin",
        record_size=0x5C,
    ),
}

# Backward-compatible constants for the original command.bin-only editor/tests.
ARCHIVE_PATH = TABLES["command"].archive_path
RECORD_SIZE = TABLES["command"].record_size


class FFXCommandError(ValueError):
    """Raised when researched FFX ability-table data or an edit is invalid."""


@dataclass(frozen=True)
class FFXCommandRecord:
    record_id: int
    animation_1: int
    animation_2: int


def table_key(value: str) -> str:
    key = str(value).casefold()
    if key not in TABLES:
        raise FFXCommandError("FFX ability table must be command, item, monmagic1 or monmagic2")
    return key


def table_spec(value: str) -> FFXAbilityTableSpec:
    return TABLES[table_key(value)]


def _u16(raw: bytes, offset: int) -> int:
    return raw[offset] | (raw[offset + 1] << 8)


def _table(data: bytes, table: str = "command"):
    spec = table_spec(table)
    try:
        parsed = parse_table(data)
    except FFXTableError as error:
        raise FFXCommandError(str(error)) from error
    if parsed.record_size != spec.record_size:
        raise FFXCommandError(
            f"FFX {spec.archive_path.rsplit('/', 1)[-1]} record size does not match the proved "
            f"0x{spec.record_size:X}-byte layout: {parsed.record_size}"
        )
    return parsed


def parse_commands(data: bytes, table: str = "command") -> tuple[FFXCommandRecord, ...]:
    parsed = _table(data, table)
    return tuple(
        FFXCommandRecord(
            record_id=record_id,
            animation_1=_u16(parsed.record(record_id), ANIMATION_1_OFFSET),
            animation_2=_u16(parsed.record(record_id), ANIMATION_2_OFFSET),
        )
        for record_id in range(parsed.min_index, parsed.max_index + 1)
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


def apply_table_edits(data: bytes, edits: list[dict], table: str = "command") -> bytes:
    """Patch only the two proved animation-ID fields in selected records."""
    spec = table_spec(table)
    if not isinstance(edits, list) or not edits:
        raise FFXCommandError(f"At least one FFX {spec.label.lower()} edit is required")
    parsed = _table(data, spec.key)
    output = bytearray(parsed.data)
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise FFXCommandError("Each FFX animation edit must be an object")
        if set(edit) != {"id", "animation1", "animation2"}:
            raise FFXCommandError("Each FFX animation edit must contain only id, animation1 and animation2")
        try:
            record_id = int(edit["id"])
        except (TypeError, ValueError) as error:
            raise FFXCommandError("FFX ability record ID must be an integer") from error
        if not parsed.min_index <= record_id <= parsed.max_index:
            raise FFXCommandError(
                f"FFX ability record ID must be between {parsed.min_index} and {parsed.max_index}"
            )
        if record_id in seen:
            raise FFXCommandError(f"Duplicate FFX animation edit: {record_id}")
        seen.add(record_id)
        animation_1 = _u16_value(edit["animation1"], "Animation 1")
        animation_2 = _u16_value(edit["animation2"], "Animation 2")
        offset = parsed.record_offset(record_id)
        output[offset + ANIMATION_1_OFFSET] = animation_1 & 0xFF
        output[offset + ANIMATION_1_OFFSET + 1] = animation_1 >> 8
        output[offset + ANIMATION_2_OFFSET] = animation_2 & 0xFF
        output[offset + ANIMATION_2_OFFSET + 1] = animation_2 >> 8
    return bytes(output)


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Backward-compatible command.bin wrapper."""
    return apply_table_edits(data, edits, "command")


def payload_for(data: bytes, table: str = "command") -> dict:
    spec = table_spec(table)
    parsed = _table(data, spec.key)
    rows = parse_commands(data, spec.key)
    return {
        "table": spec.key,
        "label": spec.label,
        "minIndex": parsed.min_index,
        "maxIndex": parsed.max_index,
        "recordSize": parsed.record_size,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "animation1": row.animation_1,
            "animation2": row.animation_2,
        } for row in rows],
    }


def payload(data: bytes) -> dict:
    """Backward-compatible command.bin wrapper."""
    return payload_for(data, "command")
