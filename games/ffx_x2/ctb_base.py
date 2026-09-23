"""Structured editing for Final Fantasy X ``ctb_base.bin`` battle timing."""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import FFXTableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/ctb_base.bin"
RECORD_SIZE = 2


class CtbBaseError(ValueError):
    """Raised when CTB base data or an edit is invalid."""


@dataclass(frozen=True)
class CtbBaseRecord:
    record_id: int
    agility: int
    tick_speed: int
    icv_bonus: int

    @property
    def max_icv(self) -> int:
        return self.tick_speed * 3

    @property
    def min_icv(self) -> int:
        return self.max_icv - self.icv_bonus


def parse_ctb_base(data: bytes) -> tuple[CtbBaseRecord, ...]:
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise CtbBaseError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise CtbBaseError(
            f"ctb_base.bin record size does not match the proved {RECORD_SIZE}-byte layout: {table.record_size}"
        )
    rows = []
    for record_id in range(table.min_index, table.max_index + 1):
        raw = table.record(record_id)
        rows.append(CtbBaseRecord(
            record_id=record_id,
            agility=record_id + 1,
            tick_speed=raw[0],
            icv_bonus=raw[1],
        ))
    return tuple(rows)


def _u8(value, label: str) -> int:
    if isinstance(value, bool):
        raise CtbBaseError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise CtbBaseError(f"{label} must be an integer") from error
    if not 0 <= parsed <= 0xFF:
        raise CtbBaseError(f"{label} must be between 0 and 255")
    return parsed


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch only selected tick-speed/ICV-bonus bytes."""
    if not isinstance(edits, list) or not edits:
        raise CtbBaseError("At least one CTB edit is required")
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise CtbBaseError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise CtbBaseError(
            f"ctb_base.bin record size does not match the proved {RECORD_SIZE}-byte layout: {table.record_size}"
        )

    output = bytearray(table.data)
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise CtbBaseError("Each CTB edit must be an object")
        try:
            record_id = int(edit.get("id"))
        except (TypeError, ValueError) as error:
            raise CtbBaseError("CTB record ID must be an integer") from error
        if not table.min_index <= record_id <= table.max_index:
            raise CtbBaseError(
                f"CTB record ID must be between {table.min_index} and {table.max_index}"
            )
        if record_id in seen:
            raise CtbBaseError(f"Duplicate CTB edit: {record_id}")
        seen.add(record_id)
        tick_speed = _u8(edit.get("tickSpeed"), "Tick speed")
        icv_bonus = _u8(edit.get("icvBonus"), "ICV bonus")
        offset = table.record_offset(record_id)
        output[offset] = tick_speed
        output[offset + 1] = icv_bonus
    return bytes(output)


def payload(data: bytes) -> dict:
    rows = parse_ctb_base(data)
    table = parse_table(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "agility": row.agility,
            "tickSpeed": row.tick_speed,
            "icvBonus": row.icv_bonus,
            "minIcv": row.min_icv,
            "maxIcv": row.max_icv,
        } for row in rows],
    }
