"""Conservative FFX ``ply_save.bin`` base-stat editing.

Two independent references agree on the 0x94-byte record and the base-stat
prefix: name/text metadata occupies +0x00..+0x03, base HP/MP are u32 values at
+0x04/+0x08, and the eight base combat stats are bytes at +0x0C..+0x13.
Lexeditor deliberately leaves every byte from +0x14 onward opaque because the
research sources do not agree uniformly on all later semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

from .ffx_table import FFXTableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/ply_save.bin"
RECORD_SIZE = 0x94
EDIT_KEYS = {
    "id", "baseHp", "baseMp", "strength", "defense", "magic",
    "magicDefense", "agility", "luck", "evasion", "accuracy",
}


class FFXPlayerStatsError(ValueError):
    """Raised when the proved player-stat layout or an edit is invalid."""


@dataclass(frozen=True)
class FFXPlayerStatsRecord:
    record_id: int
    base_hp: int
    base_mp: int
    strength: int
    defense: int
    magic: int
    magic_defense: int
    agility: int
    luck: int
    evasion: int
    accuracy: int


def _table(data: bytes):
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise FFXPlayerStatsError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise FFXPlayerStatsError(
            f"FFX ply_save.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: "
            f"{table.record_size}"
        )
    return table


def parse_player_stats(data: bytes) -> tuple[FFXPlayerStatsRecord, ...]:
    table = _table(data)
    rows = []
    for record_id in range(table.min_index, table.max_index + 1):
        raw = table.record(record_id)
        base_hp, base_mp = struct.unpack_from("<II", raw, 0x04)
        stats = raw[0x0C:0x14]
        rows.append(FFXPlayerStatsRecord(
            record_id=record_id,
            base_hp=base_hp,
            base_mp=base_mp,
            strength=stats[0],
            defense=stats[1],
            magic=stats[2],
            magic_defense=stats[3],
            agility=stats[4],
            luck=stats[5],
            evasion=stats[6],
            accuracy=stats[7],
        ))
    return tuple(rows)


def _integer(value, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FFXPlayerStatsError(f"{label} must be an integer")
    if not 0 <= value <= maximum:
        raise FFXPlayerStatsError(f"{label} must be between 0 and {maximum}")
    return value


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch only the independently agreed base-stat prefix of selected records."""
    if not isinstance(edits, list) or not edits:
        raise FFXPlayerStatsError("At least one FFX player base-stat edit is required")
    table = _table(data)
    output = bytearray(table.data)
    seen: set[int] = set()

    for edit in edits:
        if not isinstance(edit, dict):
            raise FFXPlayerStatsError("Each FFX player base-stat edit must be an object")
        if set(edit) != EDIT_KEYS:
            raise FFXPlayerStatsError(
                "Each FFX player base-stat edit must contain only id, baseHp, baseMp, strength, defense, "
                "magic, magicDefense, agility, luck, evasion and accuracy"
            )
        record_id = edit["id"]
        if isinstance(record_id, bool) or not isinstance(record_id, int):
            raise FFXPlayerStatsError("FFX player-stat record ID must be an integer")
        if not table.min_index <= record_id <= table.max_index:
            raise FFXPlayerStatsError(
                f"FFX player-stat record ID must be between {table.min_index} and {table.max_index}"
            )
        if record_id in seen:
            raise FFXPlayerStatsError(f"Duplicate FFX player-stat edit: {record_id}")
        seen.add(record_id)

        values = {
            "baseHp": _integer(edit["baseHp"], "Base HP", 0xFFFFFFFF),
            "baseMp": _integer(edit["baseMp"], "Base MP", 0xFFFFFFFF),
            "strength": _integer(edit["strength"], "Strength", 0xFF),
            "defense": _integer(edit["defense"], "Defense", 0xFF),
            "magic": _integer(edit["magic"], "Magic", 0xFF),
            "magicDefense": _integer(edit["magicDefense"], "Magic Defense", 0xFF),
            "agility": _integer(edit["agility"], "Agility", 0xFF),
            "luck": _integer(edit["luck"], "Luck", 0xFF),
            "evasion": _integer(edit["evasion"], "Evasion", 0xFF),
            "accuracy": _integer(edit["accuracy"], "Accuracy", 0xFF),
        }
        offset = table.record_offset(record_id)
        struct.pack_into("<II", output, offset + 0x04, values["baseHp"], values["baseMp"])
        output[offset + 0x0C:offset + 0x14] = bytes([
            values["strength"], values["defense"], values["magic"], values["magicDefense"],
            values["agility"], values["luck"], values["evasion"], values["accuracy"],
        ])

    return bytes(output)


def payload(data: bytes) -> dict:
    table = _table(data)
    rows = parse_player_stats(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "baseHp": row.base_hp,
            "baseMp": row.base_mp,
            "strength": row.strength,
            "defense": row.defense,
            "magic": row.magic,
            "magicDefense": row.magic_defense,
            "agility": row.agility,
            "luck": row.luck,
            "evasion": row.evasion,
            "accuracy": row.accuracy,
        } for row in rows],
    }
