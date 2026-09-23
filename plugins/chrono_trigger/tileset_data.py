"""Bounded Chrono Trigger Steam tileset reference and assembly editing.

Current-PC field tilesets use:
- Game/field/BGSetTable/bgsettable_<index>.dat: eight graphics-set bytes.
- Game/field/ChipTable/ChipTable_<index>.dat: 512 tiles × 4 corners × 3 bytes.
- Game/field/ChipTable/ChipTableBg3_<index>.dat: 256 tiles × 4 corners × 3 bytes.

Lexeditor never resizes these files. Unknown bits in the third assembly byte and
any trailing bytes are preserved.
"""
from __future__ import annotations

import re
import struct

from .project import OverlayStore, digest, validate_resource_path


BGSET_RE = re.compile(r"^Game/field/BGSetTable/bgsettable_(\d+)\.dat$", re.IGNORECASE)
ASSEMBLY_L12_RE = re.compile(r"^Game/field/ChipTable/ChipTable_(\d+)\.dat$", re.IGNORECASE)
ASSEMBLY_L3_RE = re.compile(r"^Game/field/ChipTable/ChipTableBg3_(\d+)\.dat$", re.IGNORECASE)
BGSET_BYTES = 8
CORNER_NAMES = ("Top left", "Top right", "Bottom left", "Bottom right")
ASSEMBLY_SPECS = {
    "layer12": (ASSEMBLY_L12_RE, 512),
    "layer3": (ASSEMBLY_L3_RE, 256),
}


def _source(source: str) -> str:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    return source


def load_graphics_sets(store: OverlayStore, source: str = "mine") -> dict:
    source = _source(source)
    rows = []
    for path in store.archive.paths("Game/field/BGSetTable/"):
        match = BGSET_RE.match(path)
        if not match:
            continue
        payload, origin = store.read(path, source)
        if len(payload) < BGSET_BYTES:
            raise ValueError(f"{path} is shorter than the fixed 8-byte Steam graphics-set table")
        row = {
            "token": str(int(match.group(1))),
            "id": int(match.group(1)),
            "path": path,
            "source": origin,
            "sha256": digest(payload),
            "trailingBytes": len(payload) - BGSET_BYTES,
        }
        for index in range(BGSET_BYTES):
            row[f"graphicsSet{index}"] = payload[index]
        rows.append(row)
    rows.sort(key=lambda row: row["id"])
    return {"rows": rows, "source": source}


def save_graphics_set(
    store: OverlayStore, path: str, expected_sha256: str, values: dict
) -> dict:
    path = validate_resource_path(path)
    match = BGSET_RE.match(path)
    if not match:
        raise ValueError("Only Steam bgsettable_*.dat files use this editor")
    payload, _ = store.read(path, "mine")
    if len(payload) < BGSET_BYTES:
        raise ValueError(f"{path} is shorter than the fixed 8-byte Steam graphics-set table")
    if digest(payload) != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    allowed = {f"graphicsSet{index}" for index in range(BGSET_BYTES)}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unsupported graphics-set fields: {', '.join(sorted(unknown))}")
    output = bytearray(payload)
    for key, value in values.items():
        number = int(value)
        if not 0 <= number <= 0xFF:
            raise ValueError(f"{key} must be between 0 and 255")
        output[int(key.removeprefix("graphicsSet"))] = number
    store.write(path, expected_sha256, bytes(output))
    result = load_graphics_sets(store, "mine")
    return next(row for row in result["rows"] if row["path"] == path)


def _assembly_kind(path: str) -> tuple[str, re.Match[str], int]:
    for kind, (pattern, tile_count) in ASSEMBLY_SPECS.items():
        match = pattern.match(path)
        if match:
            return kind, match, tile_count
    raise ValueError("Only Steam ChipTable_*.dat and ChipTableBg3_*.dat files use this editor")


def _parse_assembly(store: OverlayStore, path: str, source: str) -> dict:
    path = validate_resource_path(path)
    kind, match, tile_count = _assembly_kind(path)
    payload, origin = store.read(path, source)
    expected = tile_count * 4 * 3
    if len(payload) < expected:
        raise ValueError(f"{path} is shorter than its fixed {tile_count}-tile Steam assembly")
    rows = []
    file_id = int(match.group(1))
    for tile_id in range(tile_count):
        for corner in range(4):
            offset = (tile_id * 4 + corner) * 3
            data1, data2 = struct.unpack_from("<HB", payload, offset)
            rows.append({
                "token": f"{kind}:{file_id}:{tile_id}:{corner}",
                "kind": kind,
                "fileId": file_id,
                "tileId": tile_id,
                "corner": corner,
                "cornerName": CORNER_NAMES[corner],
                "path": path,
                "source": origin,
                "sha256": digest(payload),
                "byteOffset": offset,
                "chipIndex": data1 & 0x03FF,
                "flipHorizontal": bool(data1 & 0x0400),
                "flipVertical": bool(data1 & 0x0800),
                "paletteIndex": (data1 >> 12) & 0x0F,
                "priority": bool(data2 & 0x01),
                "unknownPriorityBits": data2 & 0xFE,
                "fileTrailingBytes": len(payload) - expected,
            })
    return {
        "path": path,
        "kind": kind,
        "fileId": file_id,
        "tileCount": tile_count,
        "source": origin,
        "sha256": digest(payload),
        "trailingBytes": len(payload) - expected,
        "rows": rows,
    }


def load_tile_assemblies(store: OverlayStore, source: str = "mine") -> dict:
    source = _source(source)
    files = []
    rows = []
    for path in store.archive.paths("Game/field/ChipTable/"):
        if not (ASSEMBLY_L12_RE.match(path) or ASSEMBLY_L3_RE.match(path)):
            continue
        parsed = _parse_assembly(store, path, source)
        rows.extend(parsed.pop("rows"))
        files.append(parsed)
    rows.sort(key=lambda row: (row["kind"], row["fileId"], row["tileId"], row["corner"]))
    files.sort(key=lambda row: (row["kind"], row["fileId"]))
    return {"rows": rows, "files": files, "source": source}


def save_tile_assembly(
    store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]
) -> dict:
    current = _parse_assembly(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    output = bytearray(payload)
    seen = set()
    allowed = {"chipIndex", "flipHorizontal", "flipVertical", "paletteIndex", "priority"}
    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate tile-assembly edit")
        seen.add(token)
        row = by_token[token]
        values = dict(edit.get("values") or {})
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported tile-assembly fields: {', '.join(sorted(unknown))}")
        chip = int(values.get("chipIndex", row["chipIndex"]))
        palette = int(values.get("paletteIndex", row["paletteIndex"]))
        if not 0 <= chip <= 0x03FF:
            raise ValueError("Chip index must be between 0 and 1023")
        if not 0 <= palette <= 0x0F:
            raise ValueError("Palette index must be between 0 and 15")
        data1 = chip | (palette << 12)
        if bool(values.get("flipHorizontal", row["flipHorizontal"])):
            data1 |= 0x0400
        if bool(values.get("flipVertical", row["flipVertical"])):
            data1 |= 0x0800
        data2 = row["unknownPriorityBits"] | (
            0x01 if bool(values.get("priority", row["priority"])) else 0
        )
        struct.pack_into("<HB", output, row["byteOffset"], data1, data2)
    store.write(path, expected_sha256, bytes(output))
    return _parse_assembly(store, path, "mine")
