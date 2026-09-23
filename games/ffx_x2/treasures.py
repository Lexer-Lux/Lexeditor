"""Structured editing for Final Fantasy X ``takara.bin`` treasure rewards."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

from .ffx_table import FFXTableError, parse_table


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin"
KIND_NAMES = {
    0x00: "Gil",
    0x02: "Item",
    0x05: "Gear",
    0x0A: "Key Item",
}


class TreasureError(ValueError):
    """Raised when treasure data or an edit is invalid."""


@dataclass(frozen=True)
class TreasureRecord:
    record_id: int
    kind: int
    quantity: int
    type_id: int

    @property
    def kind_name(self) -> str:
        return KIND_NAMES.get(self.kind, f"Unknown 0x{self.kind:02X}")

    @property
    def summary(self) -> str:
        if self.kind == 0x00:
            return f"{self.quantity * 100} gil"
        if self.kind == 0x02:
            return f"{self.quantity} × command/item 0x{self.type_id:04X}"
        if self.kind == 0x05:
            return f"gear pickup 0x{self.type_id:04X} × {self.quantity}"
        if self.kind == 0x0A:
            return f"key item 0x{self.type_id:04X}"
        return f"kind 0x{self.kind:02X}, quantity {self.quantity}, type 0x{self.type_id:04X}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_treasures(data: bytes) -> tuple[TreasureRecord, ...]:
    """Read all reward records while preserving unknown record tail bytes."""
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise TreasureError(str(error)) from error
    if table.record_size < 4:
        raise TreasureError(f"takara.bin record size is too small: {table.record_size}")
    rows = []
    for record_id in range(table.min_index, table.max_index + 1):
        raw = table.record(record_id)
        rows.append(TreasureRecord(
            record_id=record_id,
            kind=raw[0],
            quantity=raw[1],
            type_id=raw[2] | (raw[3] << 8),
        ))
    return tuple(rows)


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool):
        raise TreasureError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise TreasureError(f"{label} must be an integer") from error
    if not minimum <= parsed <= maximum:
        raise TreasureError(f"{label} must be between {minimum} and {maximum}")
    return parsed


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch only the proved four treasure bytes in explicitly selected records."""
    if not isinstance(edits, list) or not edits:
        raise TreasureError("At least one treasure edit is required")
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise TreasureError(str(error)) from error
    if table.record_size < 4:
        raise TreasureError(f"takara.bin record size is too small: {table.record_size}")

    output = bytearray(table.data)
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise TreasureError("Each treasure edit must be an object")
        record_id = _bounded(edit.get("id"), table.min_index, table.max_index, "Treasure ID")
        if record_id in seen:
            raise TreasureError(f"Duplicate treasure edit: {record_id}")
        seen.add(record_id)
        kind = _bounded(edit.get("kind"), 0, 0xFF, "Reward kind")
        quantity = _bounded(edit.get("quantity"), 0, 0xFF, "Quantity")
        type_id = _bounded(edit.get("typeId"), 0, 0xFFFF, "Type ID")
        offset = table.record_offset(record_id)
        output[offset] = kind
        output[offset + 1] = quantity
        output[offset + 2] = type_id & 0xFF
        output[offset + 3] = type_id >> 8
    return bytes(output)


def payload(data: bytes) -> dict:
    rows = parse_treasures(data)
    table = parse_table(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "kind": row.kind,
            "kindName": row.kind_name,
            "quantity": row.quantity,
            "typeId": row.type_id,
            "summary": row.summary,
        } for row in rows],
    }


def atomic_write(path: Path, data: bytes) -> None:
    """Replace one project file atomically after the caller performs stale-data checks."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".lexeditor.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
