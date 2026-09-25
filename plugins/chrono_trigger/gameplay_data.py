"""Verified fixed-record Steam gameplay stat tables.

Chrono Trigger's Steam ``resources.bin`` contains real equipment stat tables
(``Game/common/WeaponDataTable.dat``, ``ArmorDataTable.dat``,
``HelmetDataTable.dat``) that no audited open-source project (CTViewer,
ct_nx, ChronoMod, CTExt, Temporal Redux, CTNx) parses for either edition;
CTViewer's own ``party/items.rs`` only sketches an SNES-era data model and is
never actually loaded from a file. This module independently reverse
engineers the Steam PC layout instead, and only claims what two independent
kinds of evidence agree on:

1. Each table starts with a little-endian ``u32`` record count. Reading the
   real installed Steam archive, that count exactly equals the item-name
   category size already used by :mod:`field_data`'s ``TREASURE_BASES``
   boundaries (111 weapons, 50 armor, 39 helmets) -- the same boundaries the
   existing treasure editor relies on to resolve item names.
2. The first stored value of each record (attack for weapons, defense for
   armor/helmets) exactly matches independently published Chrono Trigger
   stats for named items at that same index (Bronze Blade ATK 7, Steel Saber
   ATK 15, Silver Sword ATK 20; Hide Tunic DEF 5, Padded Vest DEF 10, Bronze
   Mail/Armor DEF 16; Hide Cap DEF 3, Bronze Helm DEF 8, Iron Helm DEF 14 --
   see credits.md for sources).

Every other byte in these records (and every byte in the sibling
Accessory/Consumable/Monster/Technic/Shop tables) has no independently
agreed meaning yet and stays opaque and preserved; Lexeditor does not guess
at it. See ``data_map.py`` for the honest per-table breakdown.
"""
from __future__ import annotations

import struct

from .field_data import TREASURE_BASES, item_names
from .project import OverlayStore, digest


WEAPON_PATH = "Game/common/WeaponDataTable.dat"
ARMOR_PATH = "Game/common/ArmorDataTable.dat"
HELMET_PATH = "Game/common/HelmetDataTable.dat"

WEAPON_COUNT = TREASURE_BASES["armor"] - TREASURE_BASES["weapon"]
ARMOR_COUNT = TREASURE_BASES["helmet"] - TREASURE_BASES["armor"]
HELMET_COUNT = TREASURE_BASES["accessory"] - TREASURE_BASES["helmet"]

_SPECS = {
    "weapon": {"path": WEAPON_PATH, "count": WEAPON_COUNT, "record": 5, "statBytes": 2,
               "statField": "attack", "statBound": 0xFFFF, "nameBase": TREASURE_BASES["weapon"]},
    "armor": {"path": ARMOR_PATH, "count": ARMOR_COUNT, "record": 3, "statBytes": 1,
              "statField": "defense", "statBound": 0xFF, "nameBase": TREASURE_BASES["armor"]},
    "helmet": {"path": HELMET_PATH, "count": HELMET_COUNT, "record": 3, "statBytes": 1,
               "statField": "defense", "statBound": 0xFF, "nameBase": TREASURE_BASES["helmet"]},
}


def _source(source: str) -> str:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    return source


def _load_stat_table(store: OverlayStore, kind: str, source: str, language: str) -> dict:
    spec = _SPECS[kind]
    payload, origin = store.read(spec["path"], _source(source))
    if len(payload) < 4:
        raise ValueError(f"{spec['path']} is missing its record-count header")
    count = struct.unpack_from("<I", payload, 0)[0]
    if count != spec["count"]:
        raise ValueError(
            f"{spec['path']} declares {count} records; Lexeditor only recognizes the "
            f"{spec['count']}-record Steam layout independently verified for {kind}s"
        )
    record_size = spec["record"]
    expected_len = 4 + count * record_size
    if len(payload) < expected_len:
        raise ValueError(f"{spec['path']} is shorter than its declared {count} fixed {record_size}-byte records")
    names = item_names(store, language, source)
    stat_bytes = spec["statBytes"]
    stat_field = spec["statField"]
    name_base = spec["nameBase"]
    rows = []
    for index in range(count):
        offset = 4 + index * record_size
        record = payload[offset:offset + record_size]
        stat = int.from_bytes(record[:stat_bytes], "little")
        global_id = name_base + index
        rows.append({
            "token": str(index),
            "id": index,
            "name": names[global_id] if 0 <= global_id < len(names) else "",
            stat_field: stat,
            "unknownBytes": record[stat_bytes:].hex().upper(),
            "byteOffset": offset,
        })
    return {
        "rows": rows, "source": origin, "sha256": digest(payload),
        "path": spec["path"], "recordCount": count, "statField": stat_field,
    }


def _save_stat_table(store: OverlayStore, kind: str, expected_sha256: str, edits: list[dict], language: str) -> dict:
    spec = _SPECS[kind]
    payload, _ = store.read(spec["path"], "mine")
    if digest(payload) != expected_sha256:
        raise RuntimeError(f"{spec['path']} changed since it was opened; reload before saving")
    count = struct.unpack_from("<I", payload, 0)[0]
    if count != spec["count"]:
        raise ValueError(
            f"{spec['path']} declares {count} records; Lexeditor only recognizes the "
            f"{spec['count']}-record Steam layout independently verified for {kind}s"
        )
    record_size = spec["record"]
    stat_bytes = spec["statBytes"]
    stat_field = spec["statField"]
    stat_bound = spec["statBound"]
    output = bytearray(payload)
    seen = set()
    for edit in edits:
        token = str(edit["token"])
        if token in seen:
            raise ValueError(f"Duplicate {kind} edit")
        try:
            index = int(token)
        except ValueError as error:
            raise ValueError(f"Invalid {kind} edit token") from error
        if not 0 <= index < count:
            raise ValueError(f"Invalid {kind} edit token")
        seen.add(token)
        values = dict(edit.get("values") or {})
        unknown = set(values) - {stat_field}
        if unknown:
            raise ValueError(f"Unsupported {kind} fields: {', '.join(sorted(unknown))}")
        if stat_field not in values:
            continue
        value = int(values[stat_field])
        if not 0 <= value <= stat_bound:
            raise ValueError(f"{kind} {stat_field} must be between 0 and {stat_bound}")
        offset = 4 + index * record_size
        output[offset:offset + stat_bytes] = value.to_bytes(stat_bytes, "little")
    store.write(spec["path"], expected_sha256, bytes(output))
    return _load_stat_table(store, kind, "mine", language)


def load_weapons(store: OverlayStore, source: str = "mine", language: str = "en") -> dict:
    return _load_stat_table(store, "weapon", source, language)


def save_weapons(store: OverlayStore, expected_sha256: str, edits: list[dict], language: str = "en") -> dict:
    return _save_stat_table(store, "weapon", expected_sha256, edits, language)


def load_armor(store: OverlayStore, source: str = "mine", language: str = "en") -> dict:
    return _load_stat_table(store, "armor", source, language)


def save_armor(store: OverlayStore, expected_sha256: str, edits: list[dict], language: str = "en") -> dict:
    return _save_stat_table(store, "armor", expected_sha256, edits, language)


def load_helmets(store: OverlayStore, source: str = "mine", language: str = "en") -> dict:
    return _load_stat_table(store, "helmet", source, language)


def save_helmets(store: OverlayStore, expected_sha256: str, edits: list[dict], language: str = "en") -> dict:
    return _save_stat_table(store, "helmet", expected_sha256, edits, language)
