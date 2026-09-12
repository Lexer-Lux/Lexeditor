"""Structured editing for Final Fantasy X ``item_rate.bin`` gil prices."""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import parse_table
from .treasures import sha256_bytes
from .u32_prices import apply_price_edits, parse_prices


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
    rows = parse_prices(
        data, filename="item_rate.bin", target_base=ITEM_COMMAND_BASE, error_type=ItemPriceError,
    )
    return tuple(ItemPriceRecord(
        record_id=row.record_id,
        ordinal=row.ordinal,
        command_id=row.target_id,
        gil_price=row.gil_price,
    ) for row in rows)


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch only selected 32-bit gil-price records."""
    return apply_price_edits(
        data, edits, filename="item_rate.bin", edit_label="item-price", error_type=ItemPriceError,
    )


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
