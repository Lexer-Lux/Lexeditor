"""Structured editing for Final Fantasy X ``arms_shop.bin`` gear inventories."""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import parse_table
from .shop_table import RECORD_SIZE, SLOT_COUNT, ShopTableError, apply_slot_edits, parse_shops
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_shop.bin"
GearShopError = ShopTableError


@dataclass(frozen=True)
class GearShopRecord:
    record_id: int
    legacy_rate: int
    gear_ids: tuple[int, ...]

    @property
    def occupied_slots(self) -> int:
        return sum(gear_id != 0 for gear_id in self.gear_ids)


def parse_gear_shops(data: bytes) -> tuple[GearShopRecord, ...]:
    return tuple(GearShopRecord(row.record_id, row.legacy_rate, row.slot_ids)
                 for row in parse_shops(data, "arms_shop.bin"))


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch selected gear slots, preserving the unused rate and all other bytes."""
    return apply_slot_edits(
        data, edits, filename="arms_shop.bin", value_key="gearId", value_label="Gear ID"
    )


def payload(data: bytes) -> dict:
    rows = parse_gear_shops(data)
    table = parse_table(data)
    return {
        "minIndex": table.min_index,
        "maxIndex": table.max_index,
        "recordSize": table.record_size,
        "slotCount": SLOT_COUNT,
        "baselineSha256": sha256_bytes(data),
        "rows": [{
            "id": row.record_id,
            "legacyRate": row.legacy_rate,
            "occupiedSlots": row.occupied_slots,
            "gearIds": list(row.gear_ids),
        } for row in rows],
    }
