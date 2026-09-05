"""Structured, lossless access to proven FF8 enemy information tables.

Offsets and record layouts come from FF8 Ultimate Editor commit 343d97e9,
FF8GameData.monsterdata.AIData and dat.monsteranalyser.
"""

from __future__ import annotations

import json
from pathlib import Path


TIERS = ("low", "medium", "high")
ABILITY_OFFSETS = {"low": 0x34, "medium": 0x74, "high": 0xB4}
PAIR_OFFSETS = {
    "draw": {"low": 0x104, "medium": 0x10C, "high": 0x114},
    "mug": {"low": 0x11C, "medium": 0x124, "high": 0x12C},
    "drop": {"low": 0x134, "medium": 0x13C, "high": 0x144},
}
CARD_OFFSET = 0xF8
DEVOUR_OFFSET = 0xFB
ELEMENT_DEFENCE_OFFSET = 0x160
STATUS_DEFENCE_OFFSET = 0x168
RENZOKUKEN_OFFSET = 0x150


def _json(schema_root: Path, name: str) -> dict:
    return json.loads((schema_root / name).read_text(encoding="utf-8"))


def choices(schema_root: Path, magic: list[dict], items: list[dict]) -> dict:
    ability_schema = _json(schema_root, "enemy_abilities.json")
    cards = _json(schema_root, "card.json")["card_info"]
    return {
        "abilityTypes": ability_schema["abilities_type"],
        "enemyAbilities": ability_schema["abilities"],
        "magic": magic,
        "items": items,
        "cards": cards,
        # The 20 status-defence bytes are one per status, in this order, so the
        # editor can name the slots instead of numbering them.
        "statuses": _json(schema_root, "status.json")["status"],
    }


def read_tables(raw: bytes, start: int) -> dict:
    def abilities(tier: str) -> list[dict]:
        offset = start + ABILITY_OFFSETS[tier]
        return [{
            "slot": slot,
            "type": raw[offset + slot * 4],
            "animation": raw[offset + slot * 4 + 1],
            "abilityId": int.from_bytes(raw[offset + slot * 4 + 2:offset + slot * 4 + 4], "little"),
        } for slot in range(16)]

    def pairs(kind: str, tier: str) -> list[dict]:
        offset = start + PAIR_OFFSETS[kind][tier]
        return [{"slot": slot, "valueId": raw[offset + slot * 2],
                 "quantity": raw[offset + slot * 2 + 1]} for slot in range(4)]

    return {
        "abilities": {tier: abilities(tier) for tier in TIERS},
        "draw": {tier: pairs("draw", tier) for tier in TIERS},
        "mug": {tier: pairs("mug", tier) for tier in TIERS},
        "drops": {tier: pairs("drop", tier) for tier in TIERS},
        "cards": [{"slot": slot, "cardId": raw[start + CARD_OFFSET + slot]} for slot in range(3)],
        "devour": [{"slot": slot, "devourId": raw[start + DEVOUR_OFFSET + slot]} for slot in range(3)],
        "renzokuken": [{"slot": slot, "value": int.from_bytes(
            raw[start + RENZOKUKEN_OFFSET + slot * 2:start + RENZOKUKEN_OFFSET + slot * 2 + 2], "little")}
            for slot in range(8)],
        "elementDefence": [{"slot": slot, "stored": raw[start + ELEMENT_DEFENCE_OFFSET + slot],
                            "percent": 900 - raw[start + ELEMENT_DEFENCE_OFFSET + slot] * 10}
                           for slot in range(8)],
        "statusDefence": [{"slot": slot, "stored": raw[start + STATUS_DEFENCE_OFFSET + slot],
                           "percent": raw[start + STATUS_DEFENCE_OFFSET + slot] - 100}
                          for slot in range(20)],
    }


def apply_edits(raw: bytearray, start: int, edits: list[dict], schema_root: Path,
                magic_ids: set[int], item_ids: set[int]) -> int:
    ability_schema = _json(schema_root, "enemy_abilities.json")
    valid_types = {int(row["id"]) for row in ability_schema["abilities_type"]}
    enemy_ability_ids = {int(row["id"]) for row in ability_schema["abilities"]}
    card_ids = {int(row["id"]) for row in _json(schema_root, "card.json")["card_info"]}
    seen: set[tuple] = set()
    for edit in edits:
        kind = str(edit["kind"])
        tier = str(edit.get("tier", ""))
        slot = int(edit["slot"])
        key = (kind, tier, slot)
        if key in seen:
            raise ValueError("Duplicate enemy table edit")
        seen.add(key)
        if kind == "ability":
            if tier not in TIERS or not 0 <= slot < 16:
                raise ValueError("Invalid enemy ability slot")
            type_id, animation, ability_id = (int(edit[name]) for name in ("type", "animation", "abilityId"))
            valid_ids = ({0} if type_id == 0 else magic_ids if type_id == 2 else item_ids
                         if type_id == 4 else enemy_ability_ids)
            if type_id not in valid_types or ability_id not in valid_ids or not 0 <= animation <= 255:
                raise ValueError("Invalid enemy ability")
            offset = start + ABILITY_OFFSETS[tier] + slot * 4
            raw[offset:offset + 4] = bytes((type_id, animation)) + ability_id.to_bytes(2, "little")
        elif kind in PAIR_OFFSETS:
            if tier not in TIERS or not 0 <= slot < 4:
                raise ValueError("Invalid enemy item or Draw slot")
            value_id, quantity = int(edit["valueId"]), int(edit["quantity"])
            valid_ids = magic_ids if kind == "draw" else item_ids
            if value_id not in valid_ids or not 0 <= quantity <= 255:
                raise ValueError("Invalid enemy item or Draw value")
            offset = start + PAIR_OFFSETS[kind][tier] + slot * 2
            raw[offset:offset + 2] = bytes((value_id, quantity))
        elif kind == "card":
            card_id = int(edit["cardId"])
            if not 0 <= slot < 3 or card_id not in card_ids:
                raise ValueError("Invalid enemy card")
            raw[start + CARD_OFFSET + slot] = card_id
        elif kind == "devour":
            value = int(edit["devourId"])
            if not 0 <= slot < 3 or not 0 <= value <= 255:
                raise ValueError("Invalid enemy Devour value")
            raw[start + DEVOUR_OFFSET + slot] = value
        elif kind == "renzokuken":
            value = int(edit["value"])
            if not 0 <= slot < 8 or not 0 <= value <= 65535:
                raise ValueError("Invalid Renzokuken value")
            offset = start + RENZOKUKEN_OFFSET + slot * 2
            raw[offset:offset + 2] = value.to_bytes(2, "little")
        elif kind in {"elementDefence", "statusDefence"}:
            count = 8 if kind == "elementDefence" else 20
            stored = int(edit["stored"])
            if not 0 <= slot < count or not 0 <= stored <= 255:
                raise ValueError("Invalid enemy defence value")
            offset = ELEMENT_DEFENCE_OFFSET if kind == "elementDefence" else STATUS_DEFENCE_OFFSET
            raw[start + offset + slot] = stored
        else:
            raise ValueError(f"Unknown enemy table kind: {kind}")
    return len(seen)
