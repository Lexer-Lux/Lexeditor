"""Structured editing for Final Fantasy X ``arms_rate.bin`` auto-ability prices."""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import parse_table
from .treasures import sha256_bytes
from .u32_prices import apply_price_edits, parse_prices


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_rate.bin"
RECORD_SIZE = 4
AUTO_ABILITY_BASE = 0x8000


class AutoAbilityPriceError(ValueError):
    """Raised when auto-ability price data or an edit is invalid."""


@dataclass(frozen=True)
class AutoAbilityPriceRecord:
    record_id: int
    ordinal: int
    ability_id: int
    gil_price: int


def parse_auto_ability_prices(data: bytes) -> tuple[AutoAbilityPriceRecord, ...]:
    rows = parse_prices(
        data, filename="arms_rate.bin", target_base=AUTO_ABILITY_BASE,
        error_type=AutoAbilityPriceError,
    )
    return tuple(AutoAbilityPriceRecord(
        record_id=row.record_id,
        ordinal=row.ordinal,
        ability_id=row.target_id,
        gil_price=row.gil_price,
    ) for row in rows)


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    return apply_price_edits(
        data, edits, filename="arms_rate.bin", edit_label="auto-ability-price",
        error_type=AutoAbilityPriceError,
    )


def payload(data: bytes) -> dict:
    rows = parse_auto_ability_prices(data)
    table = parse_table(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "abilityBase": AUTO_ABILITY_BASE,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "ordinal": row.ordinal,
            "abilityId": row.ability_id,
            "gilPrice": row.gil_price,
        } for row in rows],
    }
