"""Bounded Chrono Trigger Steam overworld map-data editing.

Current-PC world data uses fixed layouts documented by CTViewer:
- Map_<index>.dat: two stored 96x64 tile layers (one byte per tile).
- Id_<index>.dat: 256 two-byte tile-property entries, one nibble per corner.
- SeId_<index>.dat: 3072 bytes, two 4-bit music indexes per byte.
- <index>_colanim.bin: a flat sequence of RGB555 colors.

Lexeditor never resizes these resources and preserves trailing bytes and color
bit 15.
"""
from __future__ import annotations

import re
import struct

from .project import OverlayStore, digest, validate_resource_path


MAP_RE = re.compile(r"^Game/world/Map/Map_(\d+)\.dat$", re.IGNORECASE)
PROPS_RE = re.compile(r"^Game/world/Id/Id_(\d+)\.dat$", re.IGNORECASE)
MUSIC_RE = re.compile(r"^Game/world/SeId/SeId_(\d+)\.dat$", re.IGNORECASE)
COLORS_RE = re.compile(r"^Game/world/colanim_bin/(\d+)_colanim\.bin$", re.IGNORECASE)

MAP_WIDTH = 96
MAP_HEIGHT = 64
LAYER_BYTES = MAP_WIDTH * MAP_HEIGHT
MAP_BYTES = LAYER_BYTES * 2
PROPERTY_COUNT = 256
PROPERTY_BYTES = PROPERTY_COUNT * 2
MUSIC_BYTES = LAYER_BYTES // 2

PROPERTY_NAMES = {
    0: "Nothing",
    1: "Blocks walking",
    2: "Blocks landing",
    3: "Blocks flying",
    4: "Exit / trigger",
}


def _source(source: str) -> str:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    return source


def world_files(store: OverlayStore, kind: str) -> list[dict]:
    specs = {
        "tiles": ("Game/world/Map/", MAP_RE, "World map"),
        "properties": ("Game/world/Id/", PROPS_RE, "World properties"),
        "music": ("Game/world/SeId/", MUSIC_RE, "World music"),
        "colors": ("Game/world/colanim_bin/", COLORS_RE, "World colors"),
    }
    if kind not in specs:
        raise ValueError("Unknown world data family")
    prefix, pattern, label = specs[kind]
    rows = []
    for path in store.archive.paths(prefix):
        match = pattern.match(path)
        if match:
            index = int(match.group(1))
            rows.append({"path": path, "id": index, "label": f"{label} {index}"})
    return sorted(rows, key=lambda row: (row["id"], row["path"]))


def load_world_tiles(store: OverlayStore, path: str, source: str = "mine") -> dict:
    source = _source(source)
    path = validate_resource_path(path)
    match = MAP_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/world/Map/Map_*.dat files use this editor")
    payload, origin = store.read(path, source)
    if len(payload) < MAP_BYTES:
        raise ValueError(f"{path} is shorter than the two fixed 96x64 Steam world layers")
    map_id = int(match.group(1))
    rows = []
    for layer in (1, 2):
        start = (layer - 1) * LAYER_BYTES
        add = 0 if layer == 1 else 256
        for index in range(LAYER_BYTES):
            rows.append({
                "token": f"{map_id}:{layer}:{index}",
                "mapId": map_id,
                "layer": layer,
                "index": index,
                "xTile": index % MAP_WIDTH,
                "yTile": index // MAP_WIDTH,
                "tileIndex": payload[start + index] + add,
            })
    return {
        "path": path, "mapId": map_id, "source": origin, "sha256": digest(payload),
        "width": MAP_WIDTH, "height": MAP_HEIGHT, "rows": rows,
        "trailingBytes": len(payload) - MAP_BYTES,
    }


def save_world_tiles(store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]) -> dict:
    current = load_world_tiles(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    output = bytearray(payload)
    seen = set()
    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate world-map tile edit")
        seen.add(token)
        values = dict(edit.get("values") or {})
        if set(values) - {"tileIndex"}:
            raise ValueError("Only the world-map tile index is editable")
        row = by_token[token]
        value = int(values.get("tileIndex", row["tileIndex"]))
        low, high = ((0, 255) if row["layer"] == 1 else (256, 511))
        if not low <= value <= high:
            raise ValueError(f"Layer {row['layer']} tile index must be between {low} and {high}")
        offset = (row["layer"] - 1) * LAYER_BYTES + row["index"]
        output[offset] = value - (256 if row["layer"] == 2 else 0)
    store.write(path, expected_sha256, bytes(output))
    return load_world_tiles(store, path, "mine")


def load_world_properties(store: OverlayStore, path: str, source: str = "mine") -> dict:
    source = _source(source)
    path = validate_resource_path(path)
    match = PROPS_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/world/Id/Id_*.dat files use this editor")
    payload, origin = store.read(path, source)
    if len(payload) < PROPERTY_BYTES:
        raise ValueError(f"{path} is shorter than the fixed 512-byte Steam world property table")
    file_id = int(match.group(1))
    rows = []
    for index in range(PROPERTY_COUNT):
        first, second = payload[index * 2:index * 2 + 2]
        values = ((first >> 4) & 0x0F, first & 0x0F, (second >> 4) & 0x0F, second & 0x0F)
        rows.append({
            "token": f"{file_id}:{index}", "fileId": file_id, "tileIndex": 256 + index,
            "topLeft": values[0], "topRight": values[1],
            "bottomLeft": values[2], "bottomRight": values[3],
        })
    return {
        "path": path, "fileId": file_id, "source": origin, "sha256": digest(payload),
        "rows": rows, "trailingBytes": len(payload) - PROPERTY_BYTES,
    }


def save_world_properties(store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]) -> dict:
    current = load_world_properties(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    output = bytearray(payload)
    allowed = {"topLeft", "topRight", "bottomLeft", "bottomRight"}
    seen = set()
    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate world property edit")
        seen.add(token)
        values = dict(edit.get("values") or {})
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported world property fields: {', '.join(sorted(unknown))}")
        row = by_token[token]
        merged = {key: int(values.get(key, row[key])) for key in allowed}
        for key, value in merged.items():
            if key in values and value not in PROPERTY_NAMES:
                raise ValueError("Edited world property values must be documented codes 0 through 4")
            if not 0 <= value <= 0x0F:
                raise ValueError("World property nibble must be between 0 and 15")
        offset = (row["tileIndex"] - 256) * 2
        output[offset] = (merged["topLeft"] << 4) | merged["topRight"]
        output[offset + 1] = (merged["bottomLeft"] << 4) | merged["bottomRight"]
    store.write(path, expected_sha256, bytes(output))
    return load_world_properties(store, path, "mine")


def load_world_music(store: OverlayStore, path: str, source: str = "mine") -> dict:
    source = _source(source)
    path = validate_resource_path(path)
    match = MUSIC_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/world/SeId/SeId_*.dat files use this editor")
    payload, origin = store.read(path, source)
    if len(payload) < MUSIC_BYTES:
        raise ValueError(f"{path} is shorter than the fixed Steam world music-transition table")
    file_id = int(match.group(1))
    rows = []
    for index in range(MUSIC_BYTES):
        value = payload[index]
        rows.append({
            "token": f"{file_id}:{index}", "fileId": file_id, "index": index,
            "xTile": (index * 2) % MAP_WIDTH, "yTile": (index * 2) // MAP_WIDTH,
            "leftMusic": (value >> 4) & 0x0F, "rightMusic": value & 0x0F,
        })
    return {
        "path": path, "fileId": file_id, "source": origin, "sha256": digest(payload),
        "rows": rows, "trailingBytes": len(payload) - MUSIC_BYTES,
    }


def save_world_music(store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]) -> dict:
    current = load_world_music(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    output = bytearray(payload)
    seen = set()
    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate world music edit")
        seen.add(token)
        values = dict(edit.get("values") or {})
        if set(values) - {"leftMusic", "rightMusic"}:
            raise ValueError("Only the two stored world music indexes are editable")
        row = by_token[token]
        left = int(values.get("leftMusic", row["leftMusic"]))
        right = int(values.get("rightMusic", row["rightMusic"]))
        if not 0 <= left <= 15 or not 0 <= right <= 15:
            raise ValueError("World music index must be between 0 and 15")
        output[row["index"]] = (left << 4) | right
    store.write(path, expected_sha256, bytes(output))
    return load_world_music(store, path, "mine")


def _component8(value5: int) -> int:
    return round(value5 * 255 / 31)


def _component5(value8: int) -> int:
    return round(value8 * 31 / 255)


def _decode_color(index: int, raw: int) -> dict:
    red5, green5, blue5 = raw & 31, (raw >> 5) & 31, (raw >> 10) & 31
    red, green, blue = map(_component8, (red5, green5, blue5))
    return {
        "token": str(index), "index": index, "hex": f"#{red:02X}{green:02X}{blue:02X}",
        "red5": red5, "green5": green5, "blue5": blue5,
        "preservedBit15": bool(raw & 0x8000),
    }


def load_world_colors(store: OverlayStore, path: str, source: str = "mine") -> dict:
    source = _source(source)
    path = validate_resource_path(path)
    match = COLORS_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/world/colanim_bin/*_colanim.bin files use this editor")
    payload, origin = store.read(path, source)
    count = len(payload) // 2
    rows = [_decode_color(index, struct.unpack_from("<H", payload, index * 2)[0])
            for index in range(count)]
    return {
        "path": path, "fileId": int(match.group(1)), "source": origin,
        "sha256": digest(payload), "rows": rows, "trailingBytes": len(payload) % 2,
    }


def save_world_colors(store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]) -> dict:
    current = load_world_colors(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    output = bytearray(payload)
    seen = set()
    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate world color edit")
        seen.add(token)
        value = str(edit.get("hex", "")).strip()
        if len(value) != 7 or not value.startswith("#"):
            raise ValueError("World animation color must be #RRGGBB")
        try:
            red, green, blue = (int(value[offset:offset + 2], 16) for offset in (1, 3, 5))
        except ValueError as error:
            raise ValueError("World animation color must be #RRGGBB") from error
        row = by_token[token]
        raw = 0x8000 if row["preservedBit15"] else 0
        raw |= _component5(red) | (_component5(green) << 5) | (_component5(blue) << 10)
        struct.pack_into("<H", output, row["index"] * 2, raw)
    store.write(path, expected_sha256, bytes(output))
    return load_world_colors(store, path, "mine")
