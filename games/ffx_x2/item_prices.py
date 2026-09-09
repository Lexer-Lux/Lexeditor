"""Structured editing for Final Fantasy X ``item_rate.bin`` gil prices."""
from __future__ import annotations

from dataclasses import dataclass
import struct

from .ffx_table import FFXTableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_rate.bin"
RECORD_SIZE = 4
ITEM_COMMAND_BASE = 0x2000


class ItemPriceError(ValueError):
    """Raised when item-price data or an edit is invalid."""


@dataclass(frozen=True)
class ItemPriceRecord:
    record_id: int
    ordinal: int
    command_id: int
    gil_price: int


def parse_item_prices(data: bytes) -> tuple[ItemPriceRecord, ...]:
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise ItemPriceError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise ItemPriceError(
            f"item_rate.bin record size does not match the proved {RECORD_SIZE}-byte layout: {table.record_size}"
        )
    rows = []
    for ordinal, record_id in enumerate(range(table.min_index, table.max_index + 1)):
        rows.append(ItemPriceRecord(
            record_id=record_id,
            ordinal=ordinal,
            command_id=ITEM_COMMAND_BASE + ordinal,
            gil_price=struct.unpack_from("<I", table.record(record_id), 0)[0],
        ))
    return tuple(rows)


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool):
        raise ItemPriceError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ItemPriceError(f"{label} must be an integer") from error
    if not minimum <= parsed <= maximum:
        raise ItemPriceError(f"{label} must be between {minimum} and {maximum}")
    return parsed


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch only selected 32-bit gil-price records."""
    if not isinstance(edits, list) or not edits:
        raise ItemPriceError("At least one item-price edit is required")
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise ItemPriceError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise ItemPriceError(
            f"item_rate.bin record size does not match the proved {RECORD_SIZE}-byte layout: {table.record_size}"
        )

    output = bytearray(table.data)
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise ItemPriceError("Each item-price edit must be an object")
        record_id = _bounded(edit.get("id"), table.min_index, table.max_index, "Price record ID")
        if record_id in seen:
            raise ItemPriceError(f"Duplicate item-price edit: {record_id}")
        seen.add(record_id)
        gil_price = _bounded(edit.get("gilPrice"), 0, 0xFFFFFFFF, "Gil price")
        struct.pack_into("<I", output, table.record_offset(record_id), gil_price)
    return bytes(output)


def payload(data: bytes) -> dict:
    rows = parse_item_prices(data)
    table = parse_table(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "commandBase": ITEM_COMMAND_BASE,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "ordinal": row.ordinal,
            "commandId": row.command_id,
            "gilPrice": row.gil_price,
        } for row in rows],
    }
