"""Conservative structured editing for FFX-2 ``job.bin`` ability trees.

Fahrenheit, HeartlessSeph's public 010 template, and the independent FFX-2
randomizer agree that each 0xE4-byte dressphere record stores sixteen
``(requirement, ability)`` u16 pairs at +0x3C..+0x7B. Lexeditor deliberately
writes only those pairs. Stat-growth coefficients, weapons, creature data,
text references, flags, and trailing strings remain byte-identical.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

from .ffx2_table import FFX2TableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/job.bin"
RECORD_SIZE = 0xE4
ABILITY_OFFSET = 0x3C
ABILITY_COUNT = 16
ABILITY_PAIR_SIZE = 4


class FFX2JobError(ValueError):
    """Raised when researched FFX-2 dressphere data or an edit is invalid."""


@dataclass(frozen=True)
class JobAbility:
    requirement_id: int
    ability_id: int


@dataclass(frozen=True)
class JobRecord:
    record_id: int
    name_offset: int
    name_key: int
    help_offset: int
    help_key: int
    icon: int
    berserk_action: int
    abilities: tuple[JobAbility, ...]


def _table(data: bytes):
    try:
        table = parse_table(data)
    except FFX2TableError as error:
        raise FFX2JobError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise FFX2JobError(
            f"FFX-2 job.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )
    return table


def _u16(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<H", raw, offset)[0]


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool):
        raise FFX2JobError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise FFX2JobError(f"{label} must be an integer") from error
    if not minimum <= parsed <= maximum:
        raise FFX2JobError(f"{label} must be between {minimum} and {maximum}")
    return parsed


def parse_jobs(data: bytes) -> tuple[JobRecord, ...]:
    table = _table(data)
    rows = []
    for record_id in range(table.min_index, table.max_index + 1):
        raw = table.record(record_id)
        abilities = tuple(
            JobAbility(
                requirement_id=_u16(raw, ABILITY_OFFSET + slot * ABILITY_PAIR_SIZE),
                ability_id=_u16(raw, ABILITY_OFFSET + slot * ABILITY_PAIR_SIZE + 2),
            )
            for slot in range(ABILITY_COUNT)
        )
        rows.append(JobRecord(
            record_id=record_id,
            name_offset=_u16(raw, 0x00),
            name_key=_u16(raw, 0x02),
            help_offset=_u16(raw, 0x04),
            help_key=_u16(raw, 0x06),
            icon=raw[0x0B],
            berserk_action=_u16(raw, 0x0C),
            abilities=abilities,
        ))
    return tuple(rows)


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch only selected dressphere requirement/ability pairs."""
    if not isinstance(edits, list) or not edits:
        raise FFX2JobError("At least one dressphere edit is required")
    table = _table(data)
    output = bytearray(table.data)
    seen_records: set[int] = set()

    for edit in edits:
        if not isinstance(edit, dict):
            raise FFX2JobError("Each dressphere edit must be an object")
        if set(edit) - {"id", "abilities"}:
            raise FFX2JobError("Dressphere edits may contain only id and abilities")
        record_id = _bounded(edit.get("id"), table.min_index, table.max_index, "Dressphere record ID")
        if record_id in seen_records:
            raise FFX2JobError(f"Duplicate dressphere edit: {record_id}")
        seen_records.add(record_id)

        abilities = edit.get("abilities")
        if not isinstance(abilities, list) or not abilities:
            raise FFX2JobError(f"Dressphere {record_id} must edit at least one ability slot")
        seen_slots: set[int] = set()
        record_offset = table.record_offset(record_id)
        for ability_edit in abilities:
            if not isinstance(ability_edit, dict):
                raise FFX2JobError("Each dressphere ability edit must be an object")
            if set(ability_edit) != {"slot", "requirementId", "abilityId"}:
                raise FFX2JobError(
                    "Dressphere ability edits must contain exactly slot, requirementId, and abilityId"
                )
            slot = _bounded(ability_edit.get("slot"), 0, ABILITY_COUNT - 1, "Dressphere ability slot")
            if slot in seen_slots:
                raise FFX2JobError(f"Duplicate ability slot {slot} in dressphere {record_id}")
            seen_slots.add(slot)
            requirement_id = _bounded(
                ability_edit.get("requirementId"), 0, 0xFFFF, "Required ability ID"
            )
            ability_id = _bounded(ability_edit.get("abilityId"), 0, 0xFFFF, "Ability ID")
            offset = record_offset + ABILITY_OFFSET + slot * ABILITY_PAIR_SIZE
            struct.pack_into("<HH", output, offset, requirement_id, ability_id)

    return bytes(output)


def payload(data: bytes) -> dict:
    table = _table(data)
    rows = parse_jobs(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "abilityCount": ABILITY_COUNT,
        "abilityOffset": ABILITY_OFFSET,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "nameOffset": row.name_offset,
            "nameKey": row.name_key,
            "helpOffset": row.help_offset,
            "helpKey": row.help_key,
            "icon": row.icon,
            "berserkAction": row.berserk_action,
            "abilities": [{
                "requirementId": ability.requirement_id,
                "abilityId": ability.ability_id,
            } for ability in row.abilities],
        } for row in rows],
    }
