"""Lossless reader and bounded writer for FF8 battle/scene.out.

The record layout comes from FF8 Ultimate Editor commit 343d97e9,
FF8GameData.sceneout, including its MSB-first slot masks.
"""

from __future__ import annotations


RECORD_SIZE = 128
SLOT_COUNT = 8
ENEMY_ID_BASE = 0x10


def decode_level(value: int) -> dict:
    """Describe only the scene.out level encodings with proved semantics."""
    value = int(value)
    if not 0 <= value <= 255:
        raise ValueError("Encounter level byte must be 0 to 255")
    if value == 252:
        return {"mode": "ultimecia", "value": None, "raw": value}
    if 1 <= value <= 100:
        return {"mode": "fixed", "value": value, "raw": value}
    if 101 <= value <= 200:
        return {"mode": "maximum", "value": value - 100, "raw": value}
    # 201-251 and 253-255 have special behavior. Existing research does not
    # prove one general formula for all of them, so the editor preserves them.
    return {"mode": "special", "value": None, "raw": value}


def encode_level(mode: str, value: int | None = None) -> int:
    if mode == "ultimecia":
        return 252
    if mode not in {"fixed", "maximum"}:
        raise ValueError("Encounter level mode must be fixed, maximum, or ultimecia")
    try:
        bounded = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Encounter level must be an integer from 1 to 100") from error
    if not 1 <= bounded <= 100:
        raise ValueError("Encounter level must be 1 to 100")
    return bounded if mode == "fixed" else 100 + bounded


def _bit(slot: int) -> int:
    return 0x80 >> slot


def read_rows(data: bytes, enemy_names: dict[int, str]) -> dict:
    if len(data) % RECORD_SIZE:
        raise ValueError("scene.out has a partial encounter record")
    rows = []
    for encounter_id in range(len(data) // RECORD_SIZE):
        record = data[encounter_id * RECORD_SIZE:(encounter_id + 1) * RECORD_SIZE]
        not_visible, not_loaded, not_targetable, enabled = record[4:8]
        slots = []
        for slot in range(SLOT_COUNT):
            bit = _bit(slot)
            base = 0x08 + slot * 6
            position = [
                int.from_bytes(record[base + axis * 2:base + axis * 2 + 2], "little", signed=True)
                for axis in range(3)
            ]
            stored_enemy_id = record[0x38 + slot]
            enemy_id = stored_enemy_id - ENEMY_ID_BASE
            level = record[0x78 + slot]
            slots.append({
                "slot": slot,
                "enemyId": enemy_id,
                "enemyName": enemy_names.get(enemy_id, f"Enemy {enemy_id}"),
                "enabled": bool(enabled & bit),
                "visible": not bool(not_visible & bit),
                "loaded": not bool(not_loaded & bit),
                "targetable": not bool(not_targetable & bit),
                "x": position[0], "y": position[1], "z": position[2],
                "level": level,
                "levelRule": decode_level(level),
            })
        rows.append({
            "id": encounter_id,
            "stageId": record[0],
            "flags": record[1],
            "cameraMain": record[2],
            "cameraSecondary": record[3],
            "slots": slots,
        })
    return {"rows": rows}


def apply_edits(data: bytes, edits: list[dict], enemy_ids: set[int]) -> tuple[bytes, int]:
    if len(data) % RECORD_SIZE:
        raise ValueError("scene.out has a partial encounter record")
    raw = bytearray(data)
    seen: set[tuple] = set()
    changed = 0
    for edit in edits:
        encounter_id = int(edit["id"])
        if not 0 <= encounter_id < len(raw) // RECORD_SIZE:
            raise ValueError(f"Invalid encounter id: {encounter_id}")
        base = encounter_id * RECORD_SIZE
        if "slot" not in edit:
            key = (encounter_id, "header")
            if key in seen:
                raise ValueError("Duplicate encounter header edit")
            seen.add(key)
            values = [int(edit[name]) for name in ("stageId", "flags", "cameraMain", "cameraSecondary")]
            if any(not 0 <= value <= 255 for value in values):
                raise ValueError("Encounter header values must be 0 to 255")
            raw[base:base + 4] = bytes(values)
            changed += 1
            continue

        slot = int(edit["slot"])
        key = (encounter_id, slot)
        if key in seen or not 0 <= slot < SLOT_COUNT:
            raise ValueError("Invalid or duplicate encounter slot edit")
        seen.add(key)
        enemy_id = int(edit["enemyId"])
        if enemy_id not in enemy_ids or not 0 <= enemy_id + ENEMY_ID_BASE <= 255:
            raise ValueError(f"Unknown encounter enemy id: {enemy_id}")
        level = int(edit["level"])
        coordinates = [int(edit[axis]) for axis in ("x", "y", "z")]
        if not 0 <= level <= 255 or any(not -32768 <= value <= 32767 for value in coordinates):
            raise ValueError("Encounter level or position is outside its stored range")
        mask_locations = ((4, "visible", True), (5, "loaded", True),
                          (6, "targetable", True), (7, "enabled", False))
        bit = _bit(slot)
        for relative, name, inverted in mask_locations:
            selected = bool(edit[name])
            set_bit = not selected if inverted else selected
            raw[base + relative] = ((raw[base + relative] | bit) if set_bit
                                    else (raw[base + relative] & ~bit))
        position_base = base + 0x08 + slot * 6
        for axis, value in enumerate(coordinates):
            raw[position_base + axis * 2:position_base + axis * 2 + 2] = value.to_bytes(
                2, "little", signed=True)
        raw[base + 0x38 + slot] = enemy_id + ENEMY_ID_BASE
        raw[base + 0x78 + slot] = level
        changed += 1
    return bytes(raw), changed
