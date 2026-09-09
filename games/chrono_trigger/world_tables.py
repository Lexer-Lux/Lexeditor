"""Structured Steam overworld exit/trigger tables.

Each overworld header points at ``Game/world/EventTable/EventTable_XXXX.dat``.
The PC layout is documented by CTViewer and consists of counted fixed-size
records. Lexeditor edits existing records only; all count bytes and table
layout remain untouched.
"""

from __future__ import annotations

import struct

from .data import OverlayStore, sha256
from .worlds import load_worlds


FACING_NAMES = ("Up", "Down", "Left", "Right")


def _table_path(store: OverlayStore, world_id: int, source: str) -> tuple[int, str]:
    worlds = load_worlds(store, source)
    world_id = int(world_id)
    if not 0 <= world_id < len(worlds["rows"]):
        raise ValueError(f"World index is outside the world table: {world_id}")
    table_id = int(worlds["rows"][world_id]["values"]["exits"])
    return table_id, f"Game/world/EventTable/EventTable_{table_id:04d}.dat"


def _take(raw: bytes, offset: int, length: int, label: str) -> bytes:
    if offset < 0 or offset + length > len(raw):
        raise ValueError(f"Chrono Trigger world table is truncated while reading {label}")
    return raw[offset:offset + length]


def parse_world_table(raw: bytes) -> dict:
    """Parse one PC EventTable while retaining byte offsets for safe edits."""
    if not raw:
        raise ValueError("Chrono Trigger world EventTable is empty")
    cursor = 0

    exit_count = raw[cursor]
    cursor += 1
    exits = []
    for index in range(exit_count):
        record_offset = cursor
        record = _take(raw, cursor, 8, f"exit {index}")
        cursor += 8
        x_raw, y_raw, name_index, scene_index, facing_shift, tile_x, tile_y = struct.unpack(
            "<BBBHBBB", record
        )
        facing = (facing_shift & 0x06) >> 1
        exits.append({
            "id": index,
            "offset": record_offset,
            "values": {
                "xRaw": x_raw,
                "yRaw": y_raw,
                "nameIndex": name_index,
                "sceneIndex": scene_index,
                "facingShift": facing_shift,
                "tileX": tile_x,
                "tileY": tile_y,
            },
            "derived": {
                "tileX": x_raw & 0x7F,
                "tileY": y_raw & 0x3F,
                "available": bool(x_raw & 0x80),
                "unknownYFlags": y_raw & 0xC0,
                "facing": FACING_NAMES[facing],
                "shiftX": -8 if facing_shift & 0x08 else 0,
                "shiftY": -8 if facing_shift & 0x10 else 0,
                "scripted": scene_index == 0x1FF,
                "scriptAddressIndex": facing if scene_index == 0x1FF else None,
            },
        })

    _take(raw, cursor, 1, "trigger count")
    trigger_count = raw[cursor]
    cursor += 1
    triggers = []
    null_trigger = None
    for index in range(trigger_count):
        record_offset = cursor
        record = _take(raw, cursor, 3, f"trigger {index}")
        cursor += 3
        x, y, script_address_index = record
        if x == 0 and y == 0 and script_address_index == 0:
            null_trigger = {"index": index, "offset": record_offset}
            break
        triggers.append({
            "id": index,
            "offset": record_offset,
            "values": {"x": x, "y": y, "scriptAddressIndex": script_address_index},
            "derived": {"xPixels": x * 16, "yPixels": y * 16 - 8},
        })

    _take(raw, cursor, 1, "unknown record count")
    unknown_count = raw[cursor]
    cursor += 1
    unknown_start = cursor
    unknown_bytes = _take(raw, cursor, unknown_count * 3, "unknown records")
    cursor += unknown_count * 3

    _take(raw, cursor, 1, "script address count")
    script_count = raw[cursor]
    cursor += 1
    addresses = []
    for index in range(script_count):
        record_offset = cursor
        record = _take(raw, cursor, 2, f"script address {index}")
        cursor += 2
        stored = struct.unpack("<H", record)[0]
        addresses.append({
            "id": index,
            "offset": record_offset,
            "values": {"storedAddress": stored},
            "derived": {"scriptOffset": stored - 0x400 if stored > 0 else 0},
        })

    return {
        "exitCount": exit_count,
        "triggerCountStored": trigger_count,
        "unknownCount": unknown_count,
        "scriptAddressCount": script_count,
        "parsedBytes": cursor,
        "trailingBytes": len(raw) - cursor,
        "nullTrigger": null_trigger,
        "unknownRecords": {
            "offset": unknown_start,
            "hex": unknown_bytes.hex(" ").upper(),
            "readOnly": True,
        },
        "exits": exits,
        "triggers": triggers,
        "scriptAddresses": addresses,
    }


def load_world_table(store: OverlayStore, world_id: int, source: str = "mine") -> dict:
    table_id, path = _table_path(store, world_id, source)
    raw, origin = store.read(path, source)
    return {
        "kind": "world-event-table",
        "worldId": int(world_id),
        "tableId": table_id,
        "path": path,
        "source": origin,
        "readOnly": source == "vanilla",
        "sha256": sha256(raw),
        "fixedCount": True,
        **parse_world_table(raw),
    }


def _save_record(store: OverlayStore, world_id: int, expected_sha256: str,
                 collection: str, index: int, values: dict) -> dict:
    table_id, path = _table_path(store, world_id, "mine")
    raw, _origin = store.read(path, "mine")
    if sha256(raw) != expected_sha256:
        raise RuntimeError("The overworld EventTable changed since it was opened; reload before saving")
    parsed = parse_world_table(raw)
    rows = parsed[collection]
    index = int(index)
    row = next((item for item in rows if item["id"] == index), None)
    if row is None:
        raise ValueError(f"Unknown {collection} record: {index}")
    output = bytearray(raw)
    if collection == "exits":
        fields = {
            "xRaw": (0, 0xFF), "yRaw": (1, 0xFF), "nameIndex": (2, 0xFF),
            "sceneIndex": (3, 0xFFFF), "facingShift": (5, 0xFF),
            "tileX": (6, 0xFF), "tileY": (7, 0xFF),
        }
    elif collection == "triggers":
        fields = {"x": (0, 0xFF), "y": (1, 0xFF), "scriptAddressIndex": (2, 0xFF)}
    else:
        fields = {"storedAddress": (0, 0xFFFF)}
    unknown = set(values) - set(fields)
    if unknown:
        raise ValueError(f"Unknown {collection} fields: {', '.join(sorted(unknown))}")
    for key, value in values.items():
        byte_offset, maximum = fields[key]
        number = int(value)
        if not 0 <= number <= maximum:
            raise ValueError(f"{key} must be between 0 and {maximum}")
        absolute = row["offset"] + byte_offset
        if maximum == 0xFFFF:
            struct.pack_into("<H", output, absolute, number)
        else:
            output[absolute] = number
    store.write(path, bytes(output))
    result = load_world_table(store, world_id, "mine")
    result["savedTableId"] = table_id
    return result


def save_world_exit(store: OverlayStore, world_id: int, index: int,
                    expected_sha256: str, values: dict) -> dict:
    return _save_record(store, world_id, expected_sha256, "exits", index, values)


def save_world_trigger(store: OverlayStore, world_id: int, index: int,
                       expected_sha256: str, values: dict) -> dict:
    return _save_record(store, world_id, expected_sha256, "triggers", index, values)


def save_world_script_address(store: OverlayStore, world_id: int, index: int,
                              expected_sha256: str, values: dict) -> dict:
    return _save_record(store, world_id, expected_sha256, "scriptAddresses", index, values)
