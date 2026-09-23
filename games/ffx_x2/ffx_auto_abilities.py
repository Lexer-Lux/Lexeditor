"""Conservative FFX ``a_ability.bin`` elemental-mask editing.

Independent format references agree on the English/US table's 0x6C-byte
records and the five one-byte elemental fields at +0x11..+0x15.  Only the
known low five element bits are writable.  Upper bits and every other field
remain opaque and are preserved byte-for-byte.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import FFXTableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/a_ability.bin"
RECORD_SIZE = 0x6C
ELEMENT_MASK = 0x1F
UNKNOWN_ELEMENT_MASK = 0xE0

ELEMENTS = (
    (0x01, "fire", "Fire"),
    (0x02, "ice", "Ice"),
    (0x04, "thunder", "Thunder"),
    (0x08, "water", "Water"),
    (0x10, "holy", "Holy"),
)

FIELD_OFFSETS = {
    "strike": 0x11,
    "absorb": 0x12,
    "immune": 0x13,
    "resist": 0x14,
    "weak": 0x15,
}
EDIT_KEYS = {"id", *FIELD_OFFSETS}


class FFXAutoAbilityError(ValueError):
    """Raised when the proved auto-ability layout or an element edit is invalid."""


@dataclass(frozen=True)
class FFXAutoAbilityRecord:
    record_id: int
    strike: int
    absorb: int
    immune: int
    resist: int
    weak: int
    unknown_bits: tuple[int, int, int, int, int]


def _table(data: bytes):
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise FFXAutoAbilityError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise FFXAutoAbilityError(
            f"FFX a_ability.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: "
            f"{table.record_size}"
        )
    return table


def parse_auto_abilities(data: bytes) -> tuple[FFXAutoAbilityRecord, ...]:
    table = _table(data)
    rows = []
    for record_id in range(table.min_index, table.max_index + 1):
        raw = table.record(record_id)
        values = {name: raw[offset] for name, offset in FIELD_OFFSETS.items()}
        rows.append(FFXAutoAbilityRecord(
            record_id=record_id,
            strike=values["strike"] & ELEMENT_MASK,
            absorb=values["absorb"] & ELEMENT_MASK,
            immune=values["immune"] & ELEMENT_MASK,
            resist=values["resist"] & ELEMENT_MASK,
            weak=values["weak"] & ELEMENT_MASK,
            unknown_bits=tuple(values[name] & UNKNOWN_ELEMENT_MASK for name in FIELD_OFFSETS),
        ))
    return tuple(rows)


def _element_mask(value, label: str) -> int:
    if isinstance(value, bool):
        raise FFXAutoAbilityError(f"{label} element mask must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise FFXAutoAbilityError(f"{label} element mask must be an integer") from error
    if not 0 <= parsed <= ELEMENT_MASK:
        raise FFXAutoAbilityError(f"{label} element mask must be between 0 and 31")
    return parsed


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch known element bits while preserving unknown upper bits and all other bytes."""
    if not isinstance(edits, list) or not edits:
        raise FFXAutoAbilityError("At least one FFX auto-ability element edit is required")
    table = _table(data)
    output = bytearray(table.data)
    seen: set[int] = set()

    for edit in edits:
        if not isinstance(edit, dict):
            raise FFXAutoAbilityError("Each FFX auto-ability edit must be an object")
        if set(edit) != EDIT_KEYS:
            raise FFXAutoAbilityError(
                "Each FFX auto-ability edit must contain only id, strike, absorb, immune, resist and weak"
            )
        try:
            record_id = int(edit["id"])
        except (TypeError, ValueError) as error:
            raise FFXAutoAbilityError("FFX auto-ability record ID must be an integer") from error
        if not table.min_index <= record_id <= table.max_index:
            raise FFXAutoAbilityError(
                f"FFX auto-ability record ID must be between {table.min_index} and {table.max_index}"
            )
        if record_id in seen:
            raise FFXAutoAbilityError(f"Duplicate FFX auto-ability edit: {record_id}")
        seen.add(record_id)

        record_offset = table.record_offset(record_id)
        for name, field_offset in FIELD_OFFSETS.items():
            known = _element_mask(edit[name], name.capitalize())
            absolute = record_offset + field_offset
            output[absolute] = (output[absolute] & UNKNOWN_ELEMENT_MASK) | known

    return bytes(output)


def payload(data: bytes) -> dict:
    table = _table(data)
    rows = parse_auto_abilities(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "elementMask": ELEMENT_MASK,
        "elements": [{"bit": bit, "key": key, "label": label} for bit, key, label in ELEMENTS],
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "abilityId": 0x8000 + (row.record_id - table.min_index),
            "strike": row.strike,
            "absorb": row.absorb,
            "immune": row.immune,
            "resist": row.resist,
            "weak": row.weak,
            "unknownBits": {
                name: value for name, value in zip(FIELD_OFFSETS, row.unknown_bits)
            },
        } for row in rows],
    }
