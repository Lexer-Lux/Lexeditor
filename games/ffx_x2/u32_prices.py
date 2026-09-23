"""Shared fixed-u32 gil-price table mechanics for proved FFX kernel files."""
from __future__ import annotations

from dataclasses import dataclass
import struct

from .ffx_table import FFXTableError, parse_table


RECORD_SIZE = 4


@dataclass(frozen=True)
class U32PriceRecord:
    record_id: int
    ordinal: int
    target_id: int
    gil_price: int


def _error(error_type, message: str):
    return error_type(message)


def parse_prices(data: bytes, *, filename: str, target_base: int, error_type) -> tuple[U32PriceRecord, ...]:
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise _error(error_type, str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise _error(
            error_type,
            f"{filename} record size does not match the proved {RECORD_SIZE}-byte layout: {table.record_size}",
        )
    return tuple(
        U32PriceRecord(
            record_id=record_id,
            ordinal=ordinal,
            target_id=target_base + ordinal,
            gil_price=struct.unpack_from("<I", table.record(record_id), 0)[0],
        )
        for ordinal, record_id in enumerate(range(table.min_index, table.max_index + 1))
    )


def _bounded(value, minimum: int, maximum: int, label: str, error_type) -> int:
    if isinstance(value, bool):
        raise _error(error_type, f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise _error(error_type, f"{label} must be an integer") from error
    if not minimum <= parsed <= maximum:
        raise _error(error_type, f"{label} must be between {minimum} and {maximum}")
    return parsed


def apply_price_edits(data: bytes, edits: list[dict], *, filename: str, edit_label: str, error_type) -> bytes:
    if not isinstance(edits, list) or not edits:
        raise _error(error_type, f"At least one {edit_label} edit is required")
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise _error(error_type, str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise _error(
            error_type,
            f"{filename} record size does not match the proved {RECORD_SIZE}-byte layout: {table.record_size}",
        )

    output = bytearray(table.data)
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise _error(error_type, f"Each {edit_label} edit must be an object")
        record_id = _bounded(edit.get("id"), table.min_index, table.max_index, "Price record ID", error_type)
        if record_id in seen:
            raise _error(error_type, f"Duplicate {edit_label} edit: {record_id}")
        seen.add(record_id)
        gil_price = _bounded(edit.get("gilPrice"), 0, 0xFFFFFFFF, "Gil price", error_type)
        struct.pack_into("<I", output, table.record_offset(record_id), gil_price)
    return bytes(output)
