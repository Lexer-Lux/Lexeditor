"""Bounded Chrono Trigger Steam scene-map tile editing.

Current-PC MapTable_<index>.dat begins with a six-byte header, then fixed raw
tile bytes for layers 1 and 2 and, when enabled, layer 3. The remaining bytes
are RLE-compressed tile properties. Lexeditor decodes the property stream only
to determine the existing layer-1/layer-2 upper tile-bank flags; it never
rewrites that stream, dimensions, layer-enable bits, or map header.
"""
from __future__ import annotations

import re

from .project import OverlayStore, digest, validate_resource_path


MAP_RE = re.compile(r"^Game/field/MapTable/MapTable_(\d+)\.dat$", re.IGNORECASE)
HEADER_BYTES = 6


def _source(source: str) -> str:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    return source


def _dimensions(payload: bytes) -> dict:
    if len(payload) < HEADER_BYTES:
        raise ValueError("Scene map header is truncated")
    layer12_size, bits, scroll_l2, scroll_l3, screen_flags, effect_flags = payload[:6]
    width1 = (layer12_size & 0x03) * 16 + 16
    height1 = ((layer12_size >> 2) & 0x03) * 16 + 16
    width2 = ((layer12_size >> 4) & 0x03) * 16 + 16
    height2 = ((layer12_size >> 6) & 0x03) * 16 + 16
    width3 = (bits & 0x03) * 16 + 16
    height3 = ((bits >> 2) & 0x03) * 16 + 16
    return {
        "layer1Width": width1, "layer1Height": height1,
        "layer2Width": width2, "layer2Height": height2,
        "layer3Width": width3, "layer3Height": height3,
        "layer3Enabled": bool(bits & 0x80),
        "scrollBits": (bits & 0x70) >> 4,
        "scrollL2": scroll_l2, "scrollL3": scroll_l3,
        "screenFlags": screen_flags, "effectFlags": effect_flags,
    }


def scene_map_files(store: OverlayStore) -> list[dict]:
    rows = []
    for path in store.archive.paths("Game/field/MapTable/"):
        match = MAP_RE.match(path)
        if not match:
            continue
        payload, _ = store.read(path, "vanilla")
        try:
            dims = _dimensions(payload)
        except ValueError:
            continue
        map_id = int(match.group(1))
        rows.append({
            "path": path, "id": map_id, "label": f"Area map {map_id}",
            "layer1": f"{dims['layer1Width']}×{dims['layer1Height']}",
            "layer2": f"{dims['layer2Width']}×{dims['layer2Height']}",
            "layer3": f"{dims['layer3Width']}×{dims['layer3Height']}" if dims["layer3Enabled"] else "disabled",
        })
    return sorted(rows, key=lambda row: (row["id"], row["path"]))


def _property_banks(payload: bytes, start: int, expected: int) -> list[tuple[bool, bool]]:
    banks: list[tuple[bool, bool]] = []
    pos = start
    while pos + 3 <= len(payload):
        first, _second, _third = payload[pos:pos + 3]
        pos += 3
        layer1_high = bool(first & 0x01)
        layer2_high = bool(first & 0x02)
        repeat = 1
        if first & 0x80:
            if pos >= len(payload):
                break
            raw_repeat = payload[pos]
            pos += 1
            repeat = raw_repeat or 256
        banks.extend([(layer1_high, layer2_high)] * repeat)
    if len(banks) < expected:
        banks.extend([(False, False)] * (expected - len(banks)))
    return banks[:expected]


def load_scene_map(store: OverlayStore, path: str, source: str = "mine") -> dict:
    source = _source(source)
    path = validate_resource_path(path)
    match = MAP_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/field/MapTable/MapTable_*.dat files use this editor")
    payload, origin = store.read(path, source)
    dims = _dimensions(payload)
    map_id = int(match.group(1))
    counts = {
        1: dims["layer1Width"] * dims["layer1Height"],
        2: dims["layer2Width"] * dims["layer2Height"],
        3: dims["layer3Width"] * dims["layer3Height"] if dims["layer3Enabled"] else 0,
    }
    starts = {1: HEADER_BYTES, 2: HEADER_BYTES + counts[1], 3: HEADER_BYTES + counts[1] + counts[2]}
    property_start = starts[3] + counts[3]
    if property_start > len(payload):
        raise ValueError(f"{path} is truncated before its fixed scene-map tile layers")
    scene_width = max(dims["layer1Width"], dims["layer2Width"])
    scene_height = max(dims["layer1Height"], dims["layer2Height"])
    banks = _property_banks(payload, property_start, scene_width * scene_height)

    rows = []
    for layer in (1, 2, 3):
        if counts[layer] == 0:
            continue
        width = dims[f"layer{layer}Width"]
        height = dims[f"layer{layer}Height"]
        for index in range(counts[layer]):
            x, y = index % width, index // width
            stored = payload[starts[layer] + index]
            high = False
            if layer in {1, 2}:
                prop_index = y * scene_width + x
                high = banks[prop_index][layer - 1]
            tile_index = stored + (256 if high else 0)
            rows.append({
                "token": f"{map_id}:{layer}:{index}",
                "mapId": map_id, "layer": layer, "index": index,
                "xTile": x, "yTile": y,
                "storedTile": stored, "upperBank": high, "tileIndex": tile_index,
            })
    return {
        "path": path, "mapId": map_id, "source": origin, "sha256": digest(payload),
        **dims, "rows": rows,
        "propertyBytes": len(payload) - property_start,
        "propertyOffset": property_start,
    }


def save_scene_map(store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]) -> dict:
    current = load_scene_map(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    counts = {
        1: current["layer1Width"] * current["layer1Height"],
        2: current["layer2Width"] * current["layer2Height"],
        3: current["layer3Width"] * current["layer3Height"] if current["layer3Enabled"] else 0,
    }
    starts = {1: HEADER_BYTES, 2: HEADER_BYTES + counts[1], 3: HEADER_BYTES + counts[1] + counts[2]}
    output = bytearray(payload)
    seen = set()
    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate scene-map tile edit")
        seen.add(token)
        values = dict(edit.get("values") or {})
        if set(values) - {"tileIndex"}:
            raise ValueError("Only the scene-map tile index is editable")
        row = by_token[token]
        tile = int(values.get("tileIndex", row["tileIndex"]))
        low = 256 if row["upperBank"] else 0
        high = low + 255
        if row["layer"] == 3:
            low, high = 0, 255
        if not low <= tile <= high:
            raise ValueError(
                f"Layer {row['layer']} tile index must stay in its existing {low}-{high} bank; "
                "the RLE property stream is preserved"
            )
        output[starts[row["layer"]] + row["index"]] = tile - low
    # The entire header and compressed property stream remain byte-identical.
    store.write(path, expected_sha256, bytes(output))
    return load_scene_map(store, path, "mine")
