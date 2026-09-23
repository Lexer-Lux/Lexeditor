"""Bounded Chrono Trigger Steam sprite-descriptor editing.

Current-PC Game/chara/dat/cNNN.dat headers contain six fixed bytes. CTViewer
documents byte 3's low two size-group bits and primary-enemy bit, byte 4 as the
animation-set index, and (for enemy descriptors) signed hand X/Y bytes. The PC
runtime replaces the stored bitmap/assembly/palette references with the sprite
index; those bytes and all unknown flags/data remain read-only and preserved.
"""
from __future__ import annotations

import re

from .project import OverlayStore, digest, validate_resource_path


SPRITE_RE = re.compile(r"^Game/chara/dat/c(\d+)\.dat$", re.IGNORECASE)


def _signed(value: int) -> int:
    return value - 256 if value >= 128 else value


def _u8_signed(name: str, value) -> int:
    number = int(value)
    if not -128 <= number <= 127:
        raise ValueError(f"{name} must be between -128 and 127")
    return number & 0xFF


def load_sprite_headers(store: OverlayStore, source: str = "mine") -> dict:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    rows = []
    for path in store.archive.paths("Game/chara/dat/"):
        match = SPRITE_RE.match(path)
        if not match:
            continue
        payload, origin = store.read(path, source)
        if len(payload) < 6:
            continue
        if 6 < len(payload) < 11:
            continue
        sprite_id = int(match.group(1))
        size_flags = payload[3]
        row = {
            "token": str(sprite_id), "id": sprite_id, "path": path,
            "source": origin, "sha256": digest(payload),
            "storedBitmapIndex": payload[0],
            "storedAssemblyIndex": payload[1],
            "storedPaletteIndex": payload[2],
            "sizeGroupCode": size_flags & 0x03,
            "primaryEnemy": bool(size_flags & 0x08),
            "unknownSizeFlags": size_flags & 0xF4,
            "animationIndex": payload[4],
            "unknownFlags": payload[5],
            "enemyDescriptor": len(payload) > 6,
            "trailingBytes": max(0, len(payload) - (11 if len(payload) > 6 else 6)),
        }
        if row["enemyDescriptor"]:
            row.update({
                "handX": _signed(payload[6]), "handY": _signed(payload[7]),
                "enemyUnknown1": payload[8], "enemyUnknown2": payload[9], "enemyUnknown3": payload[10],
            })
        else:
            row.update({
                "handX": None, "handY": None,
                "enemyUnknown1": None, "enemyUnknown2": None, "enemyUnknown3": None,
            })
        rows.append(row)
    rows.sort(key=lambda row: row["id"])
    return {"rows": rows, "source": source}


def save_sprite_header(
    store: OverlayStore, path: str, expected_sha256: str, values: dict
) -> dict:
    path = validate_resource_path(path)
    match = SPRITE_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/chara/dat/c*.dat files use this editor")
    payload, _ = store.read(path, "mine")
    if len(payload) < 6 or 6 < len(payload) < 11:
        raise ValueError(f"{path} is not a complete current-PC sprite descriptor")
    if digest(payload) != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    enemy = len(payload) > 6
    allowed = {"sizeGroupCode", "primaryEnemy", "animationIndex"}
    if enemy:
        allowed.update({"handX", "handY"})
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unsupported sprite descriptor fields: {', '.join(sorted(unknown))}")
    size_group = int(values.get("sizeGroupCode", payload[3] & 0x03))
    if not 0 <= size_group <= 3:
        raise ValueError("Sprite size-group code must be between 0 and 3")
    animation = int(values.get("animationIndex", payload[4]))
    if not 0 <= animation <= 255:
        raise ValueError("Sprite animation index must be between 0 and 255")

    output = bytearray(payload)
    size_flags = payload[3] & 0xF4
    size_flags |= size_group
    if bool(values.get("primaryEnemy", bool(payload[3] & 0x08))):
        size_flags |= 0x08
    output[3] = size_flags
    output[4] = animation
    if enemy:
        output[6] = _u8_signed("Hand X", values.get("handX", _signed(payload[6])))
        output[7] = _u8_signed("Hand Y", values.get("handY", _signed(payload[7])))
    store.write(path, expected_sha256, bytes(output))
    refreshed = load_sprite_headers(store, "mine")
    sprite_id = int(match.group(1))
    return next(row for row in refreshed["rows"] if row["id"] == sprite_id)
