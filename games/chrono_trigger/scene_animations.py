"""Read-only Chrono Trigger Steam scene chip-animation diagnostics.

CTViewer documents the PC ``BGAnime/bganimeinfo_<index>.dat`` layout separately
from the SNES pointer table: byte 0 declares the animation count, then each
animation describes a four-chip destination, per-frame duration bytes and
four-chip source offsets.  Lexeditor decodes those records for inspection only;
it does not infer runtime phase, initial-frame selection, or playback timing.
"""

from __future__ import annotations

import struct

from .data import OverlayStore, load_scene, sha256


_DURATION_TICKS = {0x10: 16, 0x20: 12, 0x40: 8, 0x80: 4}


def parse_scene_chip_animations(raw: bytes, *, source_chip_count: int | None = None) -> dict:
    """Decode one PC BGAnime descriptor without simulating it."""
    if not raw:
        raise ValueError("Chrono Trigger PC BGAnime descriptor is empty")

    declared = raw[0]
    cursor = 1
    animations = []
    terminator = None
    unknown_duration_frames = 0

    for animation_index in range(declared):
        if cursor >= len(raw):
            raise ValueError("Chrono Trigger PC BGAnime descriptor ends before the declared animation count")
        frame_count = raw[cursor]
        cursor += 1
        if frame_count in {0x00, 0x80}:
            terminator = {"animationIndex": animation_index, "marker": frame_count}
            break
        if cursor + 2 > len(raw):
            raise ValueError(f"Chrono Trigger PC BGAnime animation {animation_index} has no destination offset")

        destination_offset = struct.unpack_from("<H", raw, cursor)[0]
        cursor += 2
        if cursor + frame_count > len(raw):
            raise ValueError(f"Chrono Trigger PC BGAnime animation {animation_index} duration table is truncated")
        duration_bytes = raw[cursor:cursor + frame_count]
        cursor += frame_count
        if cursor + frame_count * 2 > len(raw):
            raise ValueError(f"Chrono Trigger PC BGAnime animation {animation_index} source table is truncated")

        frames = []
        for frame_index, duration_raw in enumerate(duration_bytes):
            source_offset = struct.unpack_from("<H", raw, cursor + frame_index * 2)[0]
            source_chip = source_offset // 32
            duration_ticks = _DURATION_TICKS.get(duration_raw & 0xF0)
            if duration_ticks is None:
                unknown_duration_frames += 1
            source_range_valid = None
            if source_chip_count is not None:
                source_range_valid = source_chip + 3 < source_chip_count
            frames.append({
                "index": frame_index,
                "durationRaw": duration_raw,
                "durationUpperNibble": duration_raw & 0xF0,
                "durationLowerNibble": duration_raw & 0x0F,
                "durationTicks": duration_ticks,
                "sourceOffset": source_offset,
                "sourceChip": source_chip,
                "sourceOffsetAligned": source_offset % 32 == 0,
                "sourceChipRange": [source_chip, source_chip + 3],
                "sourceRangeValid": source_range_valid,
            })
        cursor += frame_count * 2

        destination_chip = destination_offset // 32
        animations.append({
            "index": animation_index,
            "frameCount": frame_count,
            "destinationOffset": destination_offset,
            "destinationChip": destination_chip,
            "destinationOffsetAligned": destination_offset % 32 == 0,
            "destinationChipRange": [destination_chip, destination_chip + 3],
            "frames": frames,
        })

    return {
        "declaredAnimationCount": declared,
        "decodedAnimationCount": len(animations),
        "animations": animations,
        "terminator": terminator,
        "terminatedBeforeDeclaredCount": terminator is not None and len(animations) < declared,
        "unknownDurationFrames": unknown_duration_frames,
        "bytesConsumed": cursor,
        "trailingBytes": len(raw) - cursor,
        "format": "pc-bganime-fixed-four-chip-groups",
        "playbackEmulated": False,
    }


def _animated_source_sheet(store: OverlayStore, tileset_index: int, source: str) -> dict:
    bgset_path = f"Game/field/BGSetTable/bgsettable_{tileset_index}.dat"
    if not store.exists(bgset_path, source):
        return {"bgSetPath": bgset_path, "present": False, "chipset": None, "path": None, "chipCount": None}
    raw, _origin = store.read(bgset_path, source)
    if len(raw) < 8:
        return {"bgSetPath": bgset_path, "present": True, "valid": False,
                "error": "BGSetTable is shorter than 8 bytes", "chipset": None, "path": None, "chipCount": None}
    chipset = raw[6]
    if chipset == 0xFF:
        return {"bgSetPath": bgset_path, "present": False, "valid": True,
                "chipset": chipset, "path": None, "chipCount": 0}
    path = f"Game/field/map_bin/cg{chipset}.bin"
    if not store.exists(path, source):
        return {"bgSetPath": bgset_path, "present": False, "valid": False,
                "chipset": chipset, "path": path, "chipCount": None,
                "error": "BGSetTable animation slot references a missing cg sheet"}
    sheet, _sheet_origin = store.read(path, source)
    if len(sheet) < 4:
        return {"bgSetPath": bgset_path, "present": True, "valid": False,
                "chipset": chipset, "path": path, "chipCount": None,
                "error": "Animated cg sheet is shorter than its four-byte header"}
    pixel_bytes = (len(sheet) - 4) * 2
    chip_count = pixel_bytes // 64 if pixel_bytes % 64 == 0 else None
    return {
        "bgSetPath": bgset_path,
        "present": True,
        "valid": chip_count is not None,
        "chipset": chipset,
        "path": path,
        "packedBytes": len(sheet) - 4,
        "pixelBytes": pixel_bytes,
        "chipCount": chip_count,
    }


def load_scene_chip_animations(store: OverlayStore, scene_id: int, source: str = "mine") -> dict:
    """Load the scene-referenced PC animation descriptor and source-sheet facts."""
    entries = {number: path for number, path in store.scene_entries()}
    scene_id = int(scene_id)
    if scene_id not in entries:
        raise ValueError(f"Unknown Chrono Trigger scene: {scene_id}")
    scene = load_scene(store, scene_id, entries[scene_id], source)
    values = scene["values"]
    animation_index = int(values["chipAnimations"])
    path = f"Game/field/BGAnime/bganimeinfo_{animation_index}.dat"
    source_sheet = _animated_source_sheet(store, int(values["tilesetL12"]), source)
    base = {
        "kind": "scene-chip-animations",
        "sceneId": scene_id,
        "animationIndex": animation_index,
        "path": path,
        "readOnly": True,
        "sourceSheet": source_sheet,
        "playbackEmulated": False,
        "playbackNote": "Descriptor bytes are decoded, but runtime phase and initial-frame behavior are intentionally not inferred.",
    }
    if not store.exists(path, source):
        return {**base, "present": False, "valid": True, "source": None,
                "declaredAnimationCount": 0, "decodedAnimationCount": 0, "animations": []}

    raw, origin = store.read(path, source)
    source_chip_count = source_sheet.get("chipCount") if source_sheet.get("valid") else None
    try:
        parsed = parse_scene_chip_animations(raw, source_chip_count=source_chip_count)
    except ValueError as error:
        return {**base, "present": True, "valid": False, "source": origin,
                "sha256": sha256(raw), "byteLength": len(raw), "error": str(error), "animations": []}
    return {
        **base,
        "present": True,
        "valid": True,
        "source": origin,
        "sha256": sha256(raw),
        "byteLength": len(raw),
        **parsed,
    }
