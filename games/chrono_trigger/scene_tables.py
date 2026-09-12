"""Structured Steam scene tables shared across Chrono Trigger locations.

CTViewer documents the PC table indirection and fixed record sizes used by the
Steam port.  Lexeditor edits existing records only: adding/removing records
would require rewriting the corresponding offset table and is deliberately not
part of this first implementation.
"""

from __future__ import annotations

import struct

from .data import OverlayStore, sha256


EXIT_OFFSETS = "Game/common/MapJumpOffsetTbl.dat"
EXIT_DATA = "Game/common/MapJumpDataTbl.dat"
TREASURE_OFFSETS = "Game/common/TakaraOffsetTbl.dat"
TREASURE_DATA = "Game/common/TakaraDataTbl.dat"

FACING_NAMES = ("Up", "Down", "Left", "Right")


def _offsets(store: OverlayStore, virtual_path: str, source: str,
             multiplier: int, bias: int) -> tuple[list[int], bytes, str]:
    raw, origin = store.read(virtual_path, source)
    if len(raw) < 4:
        raise ValueError(f"Chrono Trigger offset table is truncated: {virtual_path}")
    count = struct.unpack_from("<I", raw, 0)[0]
    if count > 4096 or 4 + count * 2 > len(raw):
        raise ValueError(f"Chrono Trigger offset table has invalid count: {virtual_path}")
    offsets = [struct.unpack_from("<H", raw, 4 + index * 2)[0] * multiplier + bias
               for index in range(count)]
    return offsets, raw, origin


def _range(offsets: list[int], scene_id: int, data_length: int,
           *, final_same: bool = False) -> tuple[int, int]:
    scene_id = int(scene_id)
    if not 0 <= scene_id < len(offsets):
        raise ValueError(f"Scene is outside the shared table: {scene_id}")
    start = offsets[scene_id]
    if scene_id + 1 < len(offsets):
        end = offsets[scene_id + 1]
    else:
        end = start if final_same else data_length
    if not 0 <= start <= end <= data_length:
        raise ValueError(f"Scene {scene_id} has invalid table offsets: {start}..{end}")
    return start, end


def _exit_row(scene_id: int, index: int, raw: bytes, absolute_offset: int) -> dict:
    if len(raw) != 8:
        raise ValueError("Chrono Trigger Steam exit record must be 8 bytes")
    x, y, size_bits, facing_shift, destination, tile_x, tile_y = struct.unpack("<BBBBHBB", raw)
    span_tiles = (size_bits & 0x7F) + 1
    vertical = bool(size_bits & 0x80)
    return {
        "id": index,
        "sceneId": int(scene_id),
        "offset": absolute_offset,
        "values": {
            "x": x,
            "y": y,
            "sizeBits": size_bits,
            "facingShift": facing_shift,
            "destination": destination,
            "tileX": tile_x,
            "tileY": tile_y,
        },
        "derived": {
            "facing": FACING_NAMES[facing_shift & 0x3],
            "shiftX": -8 if facing_shift & 0x04 else 0,
            "shiftY": -8 if facing_shift & 0x08 else 0,
            "orientation": "vertical" if vertical else "horizontal",
            "spanTiles": span_tiles,
            "spanPixels": span_tiles * 16,
            "xPixels": x * 16,
            "yPixels": y * 16,
        },
    }


def load_exits(store: OverlayStore, scene_id: int, source: str = "mine") -> dict:
    offsets, offset_raw, offset_origin = _offsets(store, EXIT_OFFSETS, source, 8, 4)
    data_raw, data_origin = store.read(EXIT_DATA, source)
    start, end = _range(offsets, scene_id, len(data_raw))
    if (end - start) % 8:
        raise ValueError(f"Scene {scene_id} exit range is not aligned to 8-byte records")
    rows = [_exit_row(scene_id, index, data_raw[pos:pos + 8], pos)
            for index, pos in enumerate(range(start, end, 8))]
    return {
        "kind": "scene-exits",
        "sceneId": int(scene_id),
        "source": "project" if "project" in {offset_origin, data_origin} else "archive",
        "readOnly": source == "vanilla",
        "offsetPath": EXIT_OFFSETS,
        "dataPath": EXIT_DATA,
        "offsetSha256": sha256(offset_raw),
        "dataSha256": sha256(data_raw),
        "fixedCount": True,
        "rows": rows,
    }


def save_exit(store: OverlayStore, scene_id: int, index: int, offset_sha256: str,
              data_sha256: str, values: dict) -> dict:
    offsets, offset_raw, _origin = _offsets(store, EXIT_OFFSETS, "mine", 8, 4)
    data_raw, _origin = store.read(EXIT_DATA, "mine")
    if sha256(offset_raw) != offset_sha256 or sha256(data_raw) != data_sha256:
        raise RuntimeError("The scene exit tables changed since they were opened; reload before saving")
    start, end = _range(offsets, scene_id, len(data_raw))
    if (end - start) % 8:
        raise ValueError(f"Scene {scene_id} exit range is not aligned to 8-byte records")
    count = (end - start) // 8
    index = int(index)
    if not 0 <= index < count:
        raise ValueError(f"Exit index is outside scene {scene_id}: {index}")
    fields = {
        "x": (0, 0xFF), "y": (1, 0xFF), "sizeBits": (2, 0xFF),
        "facingShift": (3, 0xFF), "destination": (4, 0xFFFF),
        "tileX": (6, 0xFF), "tileY": (7, 0xFF),
    }
    unknown = set(values) - set(fields)
    if unknown:
        raise ValueError(f"Unknown exit fields: {', '.join(sorted(unknown))}")
    output = bytearray(data_raw)
    record = start + index * 8
    for key, value in values.items():
        byte_offset, maximum = fields[key]
        number = int(value)
        if not 0 <= number <= maximum:
            raise ValueError(f"{key} must be between 0 and {maximum}")
        if maximum == 0xFFFF:
            struct.pack_into("<H", output, record + byte_offset, number)
        else:
            output[record + byte_offset] = number
    store.write(EXIT_DATA, bytes(output))
    return load_exits(store, scene_id, "mine")


def _treasure_contents(contents: int) -> dict:
    if contents & 0x8000:
        return {"kind": "gold", "gold": (contents & 0x7FFF) * 2, "itemId": None}
    category = contents & 0xFF00
    base = {0x0000: 0, 0x1000: 111, 0x2000: 161, 0x3000: 200,
            0x4000: 259, 0x5000: 302}.get(category)
    kind = {0x0000: "weapon", 0x1000: "armor", 0x2000: "helmet",
            0x3000: "accessory", 0x4000: "consumable", 0x5000: "item"}.get(category)
    if base is None:
        return {"kind": "unknown", "gold": 0, "itemId": None}
    return {"kind": kind, "gold": 0, "itemId": base + (contents & 0x1FF)}


def _treasure_row(scene_id: int, index: int, raw: bytes, absolute_offset: int) -> dict:
    if len(raw) != 6:
        raise ValueError("Chrono Trigger Steam treasure record must be 6 bytes")
    x, y, contents, unknown = struct.unpack("<BBHH", raw)
    derived = _treasure_contents(contents)
    if x == 0 and y == 0:
        derived = {"kind": "scene-alias", "targetScene": contents, "gold": 0, "itemId": None}
    return {
        "id": index,
        "sceneId": int(scene_id),
        "offset": absolute_offset,
        "values": {"x": x, "y": y, "contents": contents, "unknown": unknown},
        "derived": derived,
    }


def load_treasure(store: OverlayStore, scene_id: int, source: str = "mine") -> dict:
    offsets, offset_raw, offset_origin = _offsets(store, TREASURE_OFFSETS, source, 6, 4)
    data_raw, data_origin = store.read(TREASURE_DATA, source)
    start, end = _range(offsets, scene_id, len(data_raw), final_same=True)
    if (end - start) % 6:
        raise ValueError(f"Scene {scene_id} treasure range is not aligned to 6-byte records")
    rows = [_treasure_row(scene_id, index, data_raw[pos:pos + 6], pos)
            for index, pos in enumerate(range(start, end, 6))]
    return {
        "kind": "scene-treasure",
        "sceneId": int(scene_id),
        "source": "project" if "project" in {offset_origin, data_origin} else "archive",
        "readOnly": source == "vanilla",
        "offsetPath": TREASURE_OFFSETS,
        "dataPath": TREASURE_DATA,
        "offsetSha256": sha256(offset_raw),
        "dataSha256": sha256(data_raw),
        "fixedCount": True,
        "rows": rows,
    }


def save_treasure(store: OverlayStore, scene_id: int, index: int, offset_sha256: str,
                  data_sha256: str, values: dict) -> dict:
    offsets, offset_raw, _origin = _offsets(store, TREASURE_OFFSETS, "mine", 6, 4)
    data_raw, _origin = store.read(TREASURE_DATA, "mine")
    if sha256(offset_raw) != offset_sha256 or sha256(data_raw) != data_sha256:
        raise RuntimeError("The treasure tables changed since they were opened; reload before saving")
    start, end = _range(offsets, scene_id, len(data_raw), final_same=True)
    if (end - start) % 6:
        raise ValueError(f"Scene {scene_id} treasure range is not aligned to 6-byte records")
    count = (end - start) // 6
    index = int(index)
    if not 0 <= index < count:
        raise ValueError(f"Treasure index is outside scene {scene_id}: {index}")
    fields = {"x": (0, 0xFF), "y": (1, 0xFF), "contents": (2, 0xFFFF), "unknown": (4, 0xFFFF)}
    unknown_fields = set(values) - set(fields)
    if unknown_fields:
        raise ValueError(f"Unknown treasure fields: {', '.join(sorted(unknown_fields))}")
    output = bytearray(data_raw)
    record = start + index * 6
    for key, value in values.items():
        byte_offset, maximum = fields[key]
        number = int(value)
        if not 0 <= number <= maximum:
            raise ValueError(f"{key} must be between 0 and {maximum}")
        if maximum == 0xFFFF:
            struct.pack_into("<H", output, record + byte_offset, number)
        else:
            output[record + byte_offset] = number
    store.write(TREASURE_DATA, bytes(output))
    return load_treasure(store, scene_id, "mine")
