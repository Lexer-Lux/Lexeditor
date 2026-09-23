"""Strict FF8 field encounter formation and rate codecs.

Deling proves the PC layouts in ``MrtFile`` and ``RatFile``:

* ``.mrt`` is exactly four little-endian unsigned 16-bit formation IDs.
* ``.rat`` is exactly four copies of one unsigned 8-bit encounter rate.

The writers below reject structural changes.  The rate writer follows Deling's
``RatFile::save`` contract and writes the selected rate to all four bytes.
"""

from __future__ import annotations

import struct


FORMATION_COUNT = 4
MRT_SIZE = FORMATION_COUNT * 2
RAT_SIZE = 4


def read_mrt(data: bytes) -> dict:
    if len(data) != MRT_SIZE:
        raise ValueError(f"Field MRT must be exactly {MRT_SIZE} bytes")
    formations = list(struct.unpack("<4H", data))
    return {"formations": formations}


def apply_mrt_edits(data: bytes, edits: list[dict]) -> tuple[bytes, int]:
    document = read_mrt(data)
    result = bytearray(data)
    changed = 0
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"slot", "formation"}:
            raise ValueError("Field MRT edit needs only slot and formation")
        slot = int(edit["slot"])
        formation = int(edit["formation"])
        if slot in seen or not 0 <= slot < FORMATION_COUNT:
            raise ValueError("Field MRT edit has an invalid or duplicate slot")
        if not 0 <= formation <= 0xFFFF:
            raise ValueError("Field MRT formation must be an unsigned 16-bit value")
        seen.add(slot)
        if document["formations"][slot] != formation:
            struct.pack_into("<H", result, slot * 2, formation)
            changed += 1
    read_mrt(bytes(result))
    return bytes(result), changed


def read_rat(data: bytes) -> dict:
    if len(data) != RAT_SIZE:
        raise ValueError(f"Field RAT must be exactly {RAT_SIZE} bytes")
    values = list(data)
    return {
        "rate": values[0],
        "storedValues": values,
        "canonical": len(set(values)) == 1,
    }


def apply_rat_edit(data: bytes, rate: int) -> tuple[bytes, int]:
    document = read_rat(data)
    rate = int(rate)
    if not 0 <= rate <= 0xFF:
        raise ValueError("Field RAT rate must be an unsigned 8-bit value")
    encoded = bytes((rate,)) * RAT_SIZE
    return (data, 0) if encoded == data else (encoded, 1)


def merge_mrt(vanilla: bytes, mods: list[tuple[str, bytes]], path: str
              ) -> tuple[bytes | None, list[dict], str]:
    """Merge each formation slot independently in low-to-high mod order."""
    try:
        baseline = read_mrt(vanilla)["formations"]
    except ValueError as error:
        return None, [], f"vanilla {path} is unsupported: {error}"
    claims: dict[int, list[tuple[str, int]]] = {}
    for mod_id, source in mods:
        try:
            values = read_mrt(source)["formations"]
        except ValueError as error:
            return None, [], f"{mod_id} is not a supported {path}: {error}"
        for slot, value in enumerate(values):
            if value != baseline[slot]:
                claims.setdefault(slot, []).append((mod_id, value))
    output = bytearray(vanilla)
    conflicts = []
    for slot, values in claims.items():
        struct.pack_into("<H", output, slot * 2, values[-1][1])
        if len(values) > 1 and len({value for _, value in values}) > 1:
            conflicts.append({
                "unit": f"{path}:formation:{slot}",
                "winner": values[-1][0],
                "claimants": [mod_id for mod_id, _ in values],
            })
    return bytes(output), conflicts, ""


def merge_rat(vanilla: bytes, mods: list[tuple[str, bytes]], path: str
              ) -> tuple[bytes | None, list[dict], str]:
    """Merge the encounter rate as one semantic unit."""
    try:
        baseline = read_rat(vanilla)
    except ValueError as error:
        return None, [], f"vanilla {path} is unsupported: {error}"
    if not baseline["canonical"]:
        return None, [], f"vanilla {path} does not contain four matching rate bytes"
    claims: list[tuple[str, int]] = []
    for mod_id, source in mods:
        try:
            document = read_rat(source)
        except ValueError as error:
            return None, [], f"{mod_id} is not a supported {path}: {error}"
        if not document["canonical"]:
            return None, [], f"{mod_id} changes {path} outside the proved rate unit"
        if document["rate"] != baseline["rate"]:
            claims.append((mod_id, document["rate"]))
    if not claims:
        return vanilla, [], ""
    output = bytes((claims[-1][1],)) * RAT_SIZE
    conflicts = []
    if len(claims) > 1 and len({value for _, value in claims}) > 1:
        conflicts.append({
            "unit": f"{path}:rate",
            "winner": claims[-1][0],
            "claimants": [mod_id for mod_id, _ in claims],
        })
    return output, conflicts, ""
