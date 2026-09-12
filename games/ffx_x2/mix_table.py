"""Structured editing for Final Fantasy X ``prepare.bin`` Mix result table."""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import FFXTableError, parse_table
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/prepare.bin"
RECORD_SIZE = 0xE0
PARTNER_COUNT = 0x70
ITEM_COMMAND_BASE = 0x2000


class MixTableError(ValueError):
    """Raised when Mix table data or an edit is invalid."""


@dataclass(frozen=True)
class MixRecord:
    record_id: int
    ordinal: int
    origin_command_id: int
    result_command_ids: tuple[int, ...]

    @property
    def defined_results(self) -> int:
        return sum(result != 0 for result in self.result_command_ids)


def _u16(raw: bytes, offset: int) -> int:
    return raw[offset] | (raw[offset + 1] << 8)


def parse_mix_table(data: bytes) -> tuple[MixRecord, ...]:
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise MixTableError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise MixTableError(
            f"prepare.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )
    rows = []
    for ordinal, record_id in enumerate(range(table.min_index, table.max_index + 1)):
        raw = table.record(record_id)
        rows.append(MixRecord(
            record_id=record_id,
            ordinal=ordinal,
            origin_command_id=ITEM_COMMAND_BASE + ordinal,
            result_command_ids=tuple(_u16(raw, slot * 2) for slot in range(PARTNER_COUNT)),
        ))
    return tuple(rows)


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool):
        raise MixTableError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise MixTableError(f"{label} must be an integer") from error
    if not minimum <= parsed <= maximum:
        raise MixTableError(f"{label} must be between {minimum} and {maximum}")
    return parsed


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch selected Mix-result IDs while preserving every other table byte."""
    if not isinstance(edits, list) or not edits:
        raise MixTableError("At least one Mix edit is required")
    try:
        table = parse_table(data)
    except FFXTableError as error:
        raise MixTableError(str(error)) from error
    if table.record_size != RECORD_SIZE:
        raise MixTableError(
            f"prepare.bin record size does not match the proved 0x{RECORD_SIZE:X}-byte layout: {table.record_size}"
        )

    output = bytearray(table.data)
    seen_records: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise MixTableError("Each Mix edit must be an object")
        record_id = _bounded(edit.get("id"), table.min_index, table.max_index, "Mix record ID")
        if record_id in seen_records:
            raise MixTableError(f"Duplicate Mix edit: {record_id}")
        seen_records.add(record_id)
        results = edit.get("results")
        if not isinstance(results, list) or not results:
            raise MixTableError(f"Mix record {record_id} must include at least one result edit")
        seen_partners: set[int] = set()
        record_offset = table.record_offset(record_id)
        for result_edit in results:
            if not isinstance(result_edit, dict):
                raise MixTableError("Each Mix result edit must be an object")
            partner = _bounded(result_edit.get("partner"), 0, PARTNER_COUNT - 1, "Mix partner")
            if partner in seen_partners:
                raise MixTableError(f"Duplicate partner {partner} in Mix record {record_id}")
            seen_partners.add(partner)
            result_id = _bounded(result_edit.get("resultCommandId"), 0, 0xFFFF, "Mix result command ID")
            offset = record_offset + partner * 2
            output[offset] = result_id & 0xFF
            output[offset + 1] = result_id >> 8
    return bytes(output)


def payload(data: bytes) -> dict:
    rows = parse_mix_table(data)
    table = parse_table(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "partnerCount": PARTNER_COUNT,
        "commandBase": ITEM_COMMAND_BASE,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "ordinal": row.ordinal,
            "originCommandId": row.origin_command_id,
            "definedResults": row.defined_results,
            "resultCommandIds": list(row.result_command_ids),
        } for row in rows],
    }
