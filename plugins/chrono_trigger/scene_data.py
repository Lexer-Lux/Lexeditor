"""Fixed-size Chrono Trigger Steam area-header editing from CTViewer's PC layout."""
from __future__ import annotations

import re
import struct

from .project import OverlayStore, digest


SCENE_RE = re.compile(r"^Game/field/Mapinfo/mapinfo_(\d+)\.dat$", re.IGNORECASE)
HEADER_SIZE = 24
FIELD_NAMES = (
    "musicIndex",
    "layer12TilesetIndex",
    "layer12AssemblyIndex",
    "layer3TilesetIndex",
    "paletteIndex",
    "paletteAnimationIndex",
    "mapIndex",
    "chipAnimationIndex",
    "scriptIndex",
)


def _scene_names(store: OverlayStore, language: str, source: str) -> list[str]:
    path = f"Localize/{language}/msg/debug_map.txt"
    if not store.archive.has(path):
        return [""]
    payload, _ = store.read(path, source)
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [""]
    names = [""]
    for raw in text.splitlines():
        _key, sep, value = raw.partition(",")
        names.append(value if sep else raw)
    return names


def _decode_scene(scene_id: int, path: str, payload: bytes, origin: str, names: list[str]) -> dict:
    if len(payload) < HEADER_SIZE:
        raise ValueError(f"{path} is shorter than the 24-byte Steam scene header")
    values = struct.unpack_from("<10H4B", payload, 0)
    row = {
        "token": str(scene_id),
        "id": scene_id,
        "name": names[scene_id] if 0 <= scene_id < len(names) and names[scene_id] else f"Area {scene_id}",
        "path": path,
        "source": origin,
        "sha256": digest(payload),
        "musicIndex": values[0],
        "layer12TilesetIndex": values[1],
        "layer12AssemblyIndex": values[2],
        "layer3TilesetIndex": values[3],
        "paletteIndex": values[4],
        "paletteAnimationIndex": values[5],
        "mapIndex": values[6],
        "chipAnimationIndex": values[7],
        "scriptIndex": values[8],
        "unknownWord": values[9],
        "cameraUnbounded": values[10] == 0x80,
        "scrollLeft": values[10],
        "scrollTop": values[11],
        "scrollRight": values[12],
        "scrollBottom": values[13],
        "trailingBytes": len(payload) - HEADER_SIZE,
    }
    return row


def load_scenes(store: OverlayStore, source: str = "mine", language: str = "en") -> dict:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    names = _scene_names(store, language, source)
    rows = []
    for path in store.archive.paths("Game/field/Mapinfo/"):
        match = SCENE_RE.match(path)
        if not match:
            continue
        scene_id = int(match.group(1))
        payload, origin = store.read(path, source)
        rows.append(_decode_scene(scene_id, path, payload, origin, names))
    rows.sort(key=lambda row: row["id"])
    return {"rows": rows, "language": language, "source": source}


def _bounded(name: str, value, high: int) -> int:
    number = int(value)
    if not 0 <= number <= high:
        raise ValueError(f"{name} must be between 0 and {high}")
    return number


def save_scene(store: OverlayStore, scene_id: int, expected_sha256: str, values: dict, language: str = "en") -> dict:
    path = f"Game/field/Mapinfo/mapinfo_{int(scene_id)}.dat"
    if not store.archive.has(path):
        raise ValueError(f"Steam area {scene_id} was not found")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    current = _decode_scene(int(scene_id), path, payload, "project" if (store.project_root / path).is_file() else "vanilla",
                            _scene_names(store, language, "mine"))
    output = bytearray(payload)
    u16_values = []
    for key in FIELD_NAMES:
        u16_values.append(_bounded(key, values.get(key, current[key]), 0xFFFF))
    # The 10th u16 is PC-only and still unmodelled; always preserve it.
    unknown = current["unknownWord"]
    unbounded = bool(values.get("cameraUnbounded", current["cameraUnbounded"]))
    left = _bounded("Scroll left", values.get("scrollLeft", current["scrollLeft"]), 0xFF)
    if unbounded:
        left = 0x80
    elif current["cameraUnbounded"] and "scrollLeft" not in values:
        # CTViewer proves 0x80 as the disable sentinel. Zero is the conservative
        # first tile when explicitly switching back to a bounded camera.
        left = 0
    top = _bounded("Scroll top", values.get("scrollTop", current["scrollTop"]), 0xFF)
    right = _bounded("Scroll right", values.get("scrollRight", current["scrollRight"]), 0xFF)
    bottom = _bounded("Scroll bottom", values.get("scrollBottom", current["scrollBottom"]), 0xFF)
    struct.pack_into("<10H4B", output, 0, *u16_values, unknown, left, top, right, bottom)
    store.write(path, expected_sha256, bytes(output))
    names = _scene_names(store, language, "mine")
    saved, origin = store.read(path, "mine")
    return _decode_scene(int(scene_id), path, saved, origin, names)
