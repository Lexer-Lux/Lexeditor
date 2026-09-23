"""Structured editing for Final Fantasy X ``item_shop.bin`` inventories."""
from __future__ import annotations

from dataclasses import dataclass

from .ffx_table import parse_table
from .shop_table import RECORD_SIZE, SLOT_COUNT, ShopTableError, apply_slot_edits, parse_shops
from .treasures import sha256_bytes


ARCHIVE_PATH = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_shop.bin"
ItemShopError = ShopTableError


@dataclass(frozen=True)
class ItemShopRecord:
    record_id: int
    legacy_rate: int
    item_ids: tuple[int, ...]

    @property
    def occupied_slots(self) -> int:
        return sum(item_id != 0 for item_id in self.item_ids)


def parse_item_shops(data: bytes) -> tuple[ItemShopRecord, ...]:
    return tuple(ItemShopRecord(row.record_id, row.legacy_rate, row.slot_ids)
                 for row in parse_shops(data, "item_shop.bin"))


def apply_edits(data: bytes, edits: list[dict]) -> bytes:
    """Patch selected inventory slots, preserving the unused rate and all other bytes."""
    return apply_slot_edits(
        data, edits, filename="item_shop.bin", value_key="itemId", value_label="Item ID"
    )


def payload(data: bytes) -> dict:
    rows = parse_item_shops(data)
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
            "itemIds": list(row.item_ids),
        } for row in rows],
    }
