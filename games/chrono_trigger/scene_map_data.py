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


COLLISION_NAMES = [
    "None", "Full",
    "45° NW", "45° NE", "45° SW", "45° SE",
    "30° NW", "30° NE", "30° SW", "30° SE",
    "22° NW", "22° NE", "22° SW", "22° SE",
    "75° NW", "75° NE", "75° SW", "75° SE",
    "75° NW duplicate", "75° NE duplicate", "75° SW duplicate", "75° SE duplicate",
    "Stairs SW-NE", "Stairs SE-NW", "Left half", "Top half",
    "SW", "SE", "NE", "NW", "Ladder",
]
MOVE_NAMES = ["North", "South", "East", "West"]


def _property_start(payload: bytes, dims: dict) -> int:
    count1 = dims["layer1Width"] * dims["layer1Height"]
    count2 = dims["layer2Width"] * dims["layer2Height"]
    count3 = dims["layer3Width"] * dims["layer3Height"] if dims["layer3Enabled"] else 0
    return HEADER_BYTES + count1 + count2 + count3


def _property_runs(payload: bytes, start: int, expected: int, map_id: int) -> tuple[list[dict], int]:
    rows = []
    pos = start
    expanded = 0
    run_id = 0
    scene_width = None
    while pos + 3 <= len(payload):
        record_offset = pos
        first, second, third = payload[pos:pos + 3]
        pos += 3
        compressed = bool(first & 0x80)
        repeat = 1
        if compressed:
            if pos >= len(payload):
                raise ValueError("Scene map RLE property run is missing its repeat byte")
            raw_repeat = payload[pos]
            pos += 1
            repeat = raw_repeat or 256
        collision = (first >> 2) & 0x1F
        rows.append({
            "token": f"{map_id}:prop:{run_id}",
            "mapId": map_id,
            "runId": run_id,
            "byteOffset": record_offset,
            "compressed": compressed,
            "repeatCount": repeat,
            "startTile": expanded,
            "endTile": expanded + repeat - 1,
            "coveredTiles": max(0, min(repeat, expected - expanded)),
            "layer1UpperBank": bool(first & 0x01),
            "layer2UpperBank": bool(first & 0x02),
            "collisionCode": collision,
            "collisionName": COLLISION_NAMES[collision] if collision < len(COLLISION_NAMES) else "Invalid / unknown",
            "moveDirection": second & 0x03,
            "moveDirectionName": MOVE_NAMES[second & 0x03],
            "moveSpeed": (second >> 2) & 0x03,
            "doorTrigger": bool(second & 0x10),
            "unknownSecondBit5": bool(second & 0x20),
            "priorityTop": bool(second & 0x40),
            "npcCollisionBattle": bool(second & 0x80),
            "zPlane": third & 0x03,
            "collisionIgnoreZ": bool(third & 0x04),
            "collisionInverted": bool(third & 0x08),
            "unknownThirdBit4": bool(third & 0x10),
            "zNeutral": bool(third & 0x20),
            "priorityBottom": bool(third & 0x40),
            "npcCollision": bool(third & 0x80),
        })
        expanded += repeat
        run_id += 1
    return rows, pos


def load_scene_properties(store: OverlayStore, path: str, source: str = "mine") -> dict:
    source = _source(source)
    path = validate_resource_path(path)
    match = MAP_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/field/MapTable/MapTable_*.dat files use this editor")
    payload, origin = store.read(path, source)
    dims = _dimensions(payload)
    start = _property_start(payload, dims)
    if start > len(payload):
        raise ValueError(f"{path} is truncated before its RLE property stream")
    width = max(dims["layer1Width"], dims["layer2Width"])
    height = max(dims["layer1Height"], dims["layer2Height"])
    expected = width * height
    rows, parsed_end = _property_runs(payload, start, expected, int(match.group(1)))
    return {
        "path": path, "mapId": int(match.group(1)), "source": origin, "sha256": digest(payload),
        **dims, "width": width, "height": height, "expectedTiles": expected,
        "expandedTiles": sum(row["repeatCount"] for row in rows),
        "propertyOffset": start, "propertyBytes": len(payload) - start,
        "trailingPropertyBytes": len(payload) - parsed_end,
        "rows": rows,
    }


def _bounded(name: str, value, low: int, high: int) -> int:
    number = int(value)
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return number


def save_scene_properties(store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]) -> dict:
    current = load_scene_properties(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    output = bytearray(payload)
    allowed = {
        "layer1UpperBank", "layer2UpperBank", "collisionCode",
        "moveDirection", "moveSpeed", "doorTrigger", "priorityTop", "npcCollisionBattle",
        "zPlane", "collisionIgnoreZ", "collisionInverted", "zNeutral", "priorityBottom", "npcCollision",
    }
    seen = set()
    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate scene property-run edit")
        seen.add(token)
        row = by_token[token]
        values = dict(edit.get("values") or {})
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported scene property fields: {', '.join(sorted(unknown))}")
        collision = _bounded("Collision code", values.get("collisionCode", row["collisionCode"]), 0, 31)
        if "collisionCode" in values and collision >= len(COLLISION_NAMES):
            raise ValueError("Edited collision must use a documented code 0 through 30")
        direction = _bounded("Move direction", values.get("moveDirection", row["moveDirection"]), 0, 3)
        speed = _bounded("Move speed", values.get("moveSpeed", row["moveSpeed"]), 0, 3)
        z_plane = _bounded("Z plane", values.get("zPlane", row["zPlane"]), 0, 3)

        first = (0x80 if row["compressed"] else 0) | (collision << 2)
        if bool(values.get("layer1UpperBank", row["layer1UpperBank"])):
            first |= 0x01
        if bool(values.get("layer2UpperBank", row["layer2UpperBank"])):
            first |= 0x02

        second = (0x20 if row["unknownSecondBit5"] else 0) | direction | (speed << 2)
        if bool(values.get("doorTrigger", row["doorTrigger"])):
            second |= 0x10
        if bool(values.get("priorityTop", row["priorityTop"])):
            second |= 0x40
        if bool(values.get("npcCollisionBattle", row["npcCollisionBattle"])):
            second |= 0x80

        third = (0x10 if row["unknownThirdBit4"] else 0) | z_plane
        if bool(values.get("collisionIgnoreZ", row["collisionIgnoreZ"])):
            third |= 0x04
        if bool(values.get("collisionInverted", row["collisionInverted"])):
            third |= 0x08
        if bool(values.get("zNeutral", row["zNeutral"])):
            third |= 0x20
        if bool(values.get("priorityBottom", row["priorityBottom"])):
            third |= 0x40
        if bool(values.get("npcCollision", row["npcCollision"])):
            third |= 0x80

        offset = row["byteOffset"]
        output[offset:offset + 3] = bytes((first, second, third))
        # The optional fourth RLE repeat byte is deliberately never touched.
    store.write(path, expected_sha256, bytes(output))
    return load_scene_properties(store, path, "mine")


SCROLL_SPEEDS = (0.0, 3.75, 7.5, 15.0, 30.0, 60.0, 120.0, 240.0,
                 -0.0, -3.75, -7.5, -15.0, -30.0, -60.0, -120.0, -240.0)

SCREEN_FIELDS = {
    "layer1Main": 0x01, "layer2Main": 0x02, "layer3Main": 0x04, "spritesMain": 0x08,
    "layer1Sub": 0x10, "layer2Sub": 0x20, "layer3Sub": 0x40, "spritesSub": 0x80,
}
EFFECT_FIELDS = {
    "effectLayer1": 0x01, "effectLayer2": 0x02, "effectLayer3": 0x04,
    "effectSprites": 0x10, "effectDefaultColor": 0x20,
    "effectHalfIntensity": 0x40, "effectSubtract": 0x80,
}


def load_scene_render_settings(store: OverlayStore, path: str, source: str = "mine") -> dict:
    source = _source(source)
    path = validate_resource_path(path)
    match = MAP_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/field/MapTable/MapTable_*.dat files use this editor")
    payload, origin = store.read(path, source)
    dims = _dimensions(payload)
    result = {
        "token": str(int(match.group(1))), "mapId": int(match.group(1)),
        "path": path, "source": origin, "sha256": digest(payload),
        "scrollL2XCode": payload[2] & 0x0F, "scrollL2YCode": (payload[2] >> 4) & 0x0F,
        "scrollL3XCode": payload[3] & 0x0F, "scrollL3YCode": (payload[3] >> 4) & 0x0F,
        "unknownEffectBit3": bool(payload[5] & 0x08),
        "preservedBitsByte": payload[1],
        "layer3Enabled": dims["layer3Enabled"],
        "scrollModeBits": dims["scrollBits"],
    }
    for prefix in ("scrollL2X", "scrollL2Y", "scrollL3X", "scrollL3Y"):
        result[prefix + "Speed"] = SCROLL_SPEEDS[result[prefix + "Code"]]
    for key, mask in SCREEN_FIELDS.items():
        result[key] = bool(payload[4] & mask)
    for key, mask in EFFECT_FIELDS.items():
        result[key] = bool(payload[5] & mask)
    return result


def save_scene_render_settings(
    store: OverlayStore, path: str, expected_sha256: str, values: dict
) -> dict:
    current = load_scene_render_settings(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    allowed = {"scrollL2XCode", "scrollL2YCode", "scrollL3XCode", "scrollL3YCode",
               *SCREEN_FIELDS.keys(), *EFFECT_FIELDS.keys()}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unsupported scene render-setting fields: {', '.join(sorted(unknown))}")
    codes = {}
    for key in ("scrollL2XCode", "scrollL2YCode", "scrollL3XCode", "scrollL3YCode"):
        codes[key] = _bounded(key, values.get(key, current[key]), 0, 15)
    output = bytearray(payload)
    output[2] = codes["scrollL2XCode"] | (codes["scrollL2YCode"] << 4)
    output[3] = codes["scrollL3XCode"] | (codes["scrollL3YCode"] << 4)
    screen = 0
    for key, mask in SCREEN_FIELDS.items():
        if bool(values.get(key, current[key])):
            screen |= mask
    output[4] = screen
    effects = 0x08 if current["unknownEffectBit3"] else 0
    for key, mask in EFFECT_FIELDS.items():
        if bool(values.get(key, current[key])):
            effects |= mask
    output[5] = effects
    # Bytes 0-1 carry map dimensions, L3 enable and scroll-mode bits. Never rewrite them here.
    store.write(path, expected_sha256, bytes(output))
    return load_scene_render_settings(store, path, "mine")
