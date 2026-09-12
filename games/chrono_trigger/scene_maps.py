"""Structural scene-map decoder for Chrono Trigger Steam MapTable resources.

This exposes layer dimensions, raw tile indices, scrolling/composition bitfields,
RLE-compressed collision/property data and read-only scene animation descriptors.
Raster composition itself stays deliberately separate until PC render-order and
blend behavior are independently evidenced.
"""

from __future__ import annotations

from collections import Counter

from .data import OverlayStore, load_scene, sha256
from .scene_animations import load_scene_chip_animations


DIRECTIONS = ("North", "South", "East", "West")
COLLISIONS = (
    "None", "Full", "Corner45NW", "Corner45NE", "Corner45SW", "Corner45SE",
    "Corner30NW", "Corner30NE", "Corner30SW", "Corner30SE",
    "Corner22NW", "Corner22NE", "Corner22SW", "Corner22SE",
    "Corner75NW", "Corner75NE", "Corner75SW", "Corner75SE",
    "Corner75NWDup", "Corner75NEDup", "Corner75SWDup", "Corner75SEDup",
    "StairsSWNE", "StairsSENW", "LeftHalf", "TopHalf", "SW", "SE", "NE", "NW",
    "Ladder", "Invalid",
)


def _dimension(nibble: int) -> int:
    return (int(nibble) & 0x3) * 16 + 16


def _scroll(value: int) -> dict:
    speeds = (0.0, 3.75, 7.5, 15.0, 30.0, 60.0, 120.0, 240.0,
              -0.0, -3.75, -7.5, -15.0, -30.0, -60.0, -120.0, -240.0)
    return {"raw": value, "xPixelsPerSecond": speeds[value & 0x0F],
            "yPixelsPerSecond": speeds[(value >> 4) & 0x0F]}


def _screen_targets(value: int) -> dict:
    """Expose CTViewer's PC MapTable bit labels without composing the layers."""
    return {
        "raw": value,
        "main": {
            "layer1": bool(value & 0x01),
            "layer2": bool(value & 0x02),
            "layer3": bool(value & 0x04),
            "sprites": bool(value & 0x08),
        },
        "sub": {
            "layer1": bool(value & 0x10),
            "layer2": bool(value & 0x20),
            "layer3": bool(value & 0x40),
            "sprites": bool(value & 0x80),
        },
    }


def _effect_bits(value: int) -> dict:
    """Expose CTViewer's PC effect-bit names while keeping rendering unclaimed."""
    return {
        "raw": value,
        "targets": {
            "layer1": bool(value & 0x01),
            "layer2": bool(value & 0x02),
            "layer3": bool(value & 0x04),
            "sprites": bool(value & 0x10),
        },
        "unknown08": bool(value & 0x08),
        "defaultColor": bool(value & 0x20),
        "halfIntensity": bool(value & 0x40),
        "subtract": bool(value & 0x80),
    }


def _property(raw: bytes) -> dict:
    if len(raw) != 3:
        raise ValueError("Chrono Trigger scene tile property must be 3 bytes")
    a, b, c = raw
    collision = (a >> 2) & 0x1F
    return {
        "rawHex": raw.hex(" ").upper(),
        "collision": COLLISIONS[collision],
        "collisionIndex": collision,
        "moveDirection": DIRECTIONS[b & 0x03],
        "moveSpeed": (b >> 2) & 0x03,
        "zPlane": c & 0x03,
        "flags": {
            "layer1TileAdd": bool(a & 0x01),
            "layer2TileAdd": bool(a & 0x02),
            "doorTrigger": bool(b & 0x10),
            "unknown1": bool(b & 0x20),
            "spritePriorityTop": bool(b & 0x40),
            "npcCollisionBattle": bool(b & 0x80),
            "collisionIgnoreZ": bool(c & 0x04),
            "collisionInverted": bool(c & 0x08),
            "unknown2": bool(c & 0x10),
            "zNeutral": bool(c & 0x20),
            "spritePriorityBottom": bool(c & 0x40),
            "npcCollision": bool(c & 0x80),
        },
    }


def _properties(data: bytes, expected: int) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    cursor = 0
    encoded_records = 0
    while cursor < len(data):
        if cursor + 3 > len(data):
            raise ValueError("Chrono Trigger scene property stream ends mid-record")
        raw = data[cursor:cursor + 3]
        cursor += 3
        encoded_records += 1
        prop = _property(raw)
        if raw[0] & 0x80:
            if cursor >= len(data):
                raise ValueError("Chrono Trigger scene property RLE record has no repeat byte")
            repeat_raw = data[cursor]
            cursor += 1
            repeat = repeat_raw if repeat_raw else 256
        else:
            repeat = 1
        for _ in range(repeat):
            rows.append({key: (dict(value) if isinstance(value, dict) else value)
                         for key, value in prop.items()})
    decoded_before_normalize = len(rows)
    if len(rows) < expected:
        default = _property(b"\x00\x00\x00")
        rows.extend({key: (dict(value) if isinstance(value, dict) else value)
                     for key, value in default.items()} for _ in range(expected - len(rows)))
    elif len(rows) > expected:
        rows = rows[:expected]
    return rows, {
        "encodedBytes": len(data), "encodedRecords": encoded_records,
        "decodedBeforeNormalize": decoded_before_normalize,
        "expected": expected,
        "padded": max(0, expected - decoded_before_normalize),
        "trimmed": max(0, decoded_before_normalize - expected),
    }


def parse_scene_map(raw: bytes) -> dict:
    if len(raw) < 6:
        raise ValueError("Chrono Trigger scene MapTable is shorter than its 6-byte header")
    layer12_size, bits, scroll_l2, scroll_l3, screen_flags, effect_flags = raw[:6]
    widths = {
        "layer1": _dimension(layer12_size),
        "layer2": _dimension(layer12_size >> 4),
        "layer3": _dimension(bits),
    }
    heights = {
        "layer1": _dimension(layer12_size >> 2),
        "layer2": _dimension(layer12_size >> 6),
        "layer3": _dimension(bits >> 2),
    }
    layer3_enabled = bool(bits & 0x80)
    cursor = 6
    layers = {}
    for key in ("layer1", "layer2", "layer3"):
        count = widths[key] * heights[key]
        enabled = key != "layer3" or layer3_enabled
        if not enabled:
            layers[key] = {"width": widths[key], "height": heights[key], "enabled": False, "tiles": []}
            continue
        if cursor + count > len(raw):
            raise ValueError(f"Chrono Trigger scene {key} tile array is truncated")
        tiles = list(raw[cursor:cursor + count])
        cursor += count
        layers[key] = {"width": widths[key], "height": heights[key], "enabled": True, "tiles": tiles}

    scene_width = max(widths["layer1"], widths["layer2"])
    scene_height = max(heights["layer1"], heights["layer2"])
    props, prop_stats = _properties(raw[cursor:], scene_width * scene_height)

    # Apply the two documented high-bank flags to the effective layer tile IDs.
    for y in range(heights["layer1"]):
        for x in range(widths["layer1"]):
            prop_index = y * scene_width + x
            if props[prop_index]["flags"]["layer1TileAdd"]:
                index = y * widths["layer1"] + x
                layers["layer1"]["tiles"][index] += 256
    for y in range(heights["layer2"]):
        for x in range(widths["layer2"]):
            prop_index = y * scene_width + x
            if props[prop_index]["flags"]["layer2TileAdd"]:
                index = y * widths["layer2"] + x
                layers["layer2"]["tiles"][index] += 256

    collisions = Counter(prop["collision"] for prop in props)
    return {
        "header": {
            "layer12Size": layer12_size, "bits": bits,
            "scrollLayer2": _scroll(scroll_l2), "scrollLayer3": _scroll(scroll_l3),
            "scrollBits": (bits & 0x70) >> 4,
            "screenFlags": screen_flags, "effectFlags": effect_flags,
            "layer3Enabled": layer3_enabled,
        },
        "compositionBits": {
            "screen": _screen_targets(screen_flags),
            "effects": _effect_bits(effect_flags),
            "semantics": "CTViewer PC MapTable bit labels only; Lexeditor does not emulate render order or blending from these flags.",
        },
        "sceneWidth": scene_width, "sceneHeight": scene_height,
        "layers": layers,
        "propertyOffset": cursor,
        "propertyStats": prop_stats,
        "properties": props,
        "collisionCounts": dict(sorted(collisions.items())),
    }


def load_scene_map(store: OverlayStore, scene_id: int, source: str = "mine") -> dict:
    entries = {number: path for number, path in store.scene_entries()}
    scene_id = int(scene_id)
    if scene_id not in entries:
        raise ValueError(f"Unknown Chrono Trigger scene: {scene_id}")
    scene = load_scene(store, scene_id, entries[scene_id], source)
    map_id = int(scene["values"]["mapIndex"])
    path = f"Game/field/MapTable/MapTable_{map_id:04d}.dat"
    raw, origin = store.read(path, source)
    priority_path = f"Game/field/PrioMap/PrioMap{map_id}.dat"
    priorities = None
    if store.exists(priority_path, source):
        priority_raw, _priority_origin = store.read(priority_path, source)
        if len(priority_raw) >= 4:
            priorities = list(priority_raw[:4])
    return {
        "kind": "scene-map-layout", "sceneId": scene_id, "mapId": map_id,
        "path": path, "source": origin, "readOnly": True, "sha256": sha256(raw),
        "layerPriorities": priorities,
        "priorityPath": priority_path if priorities is not None else None,
        "prioritySemanticsKnown": False,
        "chipAnimations": load_scene_chip_animations(store, scene_id, source),
        **parse_scene_map(raw),
    }
