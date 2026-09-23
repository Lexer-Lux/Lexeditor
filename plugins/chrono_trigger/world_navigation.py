"""Bounded Chrono Trigger Steam overworld exit/trigger editing.

CTViewer documents the current-PC EventTable_<index>.dat layout as four
count-prefixed blocks: 8-byte exits, 3-byte triggers, an unknown 3-byte record
family, and 16-bit world-script addresses. Lexeditor edits existing exits and
live trigger records only. Counts, the unknown block, script addresses,
sentinel records, unmodelled flag bits and trailing bytes are preserved.
"""
from __future__ import annotations

import re
import struct

from .project import OverlayStore, digest, validate_resource_path


EVENT_TABLE_RE = re.compile(r"^Game/world/EventTable/EventTable_(\d+)\.dat$", re.IGNORECASE)


def _exit_names(store: OverlayStore, language: str, source: str) -> list[str]:
    path = f"Localize/{language}/msg/w_map.txt"
    if not store.archive.has(path):
        return []
    payload, _ = store.read(path, source)
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return []
    names = []
    for raw in text.splitlines()[:106]:
        _key, sep, value = raw.partition(",")
        names.append(value if sep else raw)
    return names


def _take_count(payload: bytes, pos: int, width: int, label: str) -> tuple[int, int, int]:
    if pos >= len(payload):
        raise ValueError(f"{label} count is missing")
    count = payload[pos]
    start = pos + 1
    end = start + count * width
    if end > len(payload):
        raise ValueError(f"{label} block is truncated")
    return count, start, end


def _parse_file(store: OverlayStore, path: str, source: str, language: str) -> dict:
    path = validate_resource_path(path)
    match = EVENT_TABLE_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/world/EventTable/EventTable_*.dat files use this editor")
    payload, origin = store.read(path, source)
    names = _exit_names(store, language, source)
    table_id = int(match.group(1))

    exit_count, exit_start, pos = _take_count(payload, 0, 8, "World exit")
    rows = []
    for index in range(exit_count):
        offset = exit_start + index * 8
        x_raw, y_raw, name_index, scene_index, facing_raw, target_x, target_y = struct.unpack_from(
            "<BBBHBBB", payload, offset
        )
        scripted = scene_index == 0x1FF
        pointer_or_facing = (facing_raw & 0x06) >> 1
        rows.append({
            "token": f"{table_id}:exit:{index}",
            "recordType": "exit",
            "tableId": table_id,
            "recordId": index,
            "path": path,
            "sha256": digest(payload),
            "source": origin,
            "byteOffset": offset,
            "xTile": x_raw & 0x7F,
            "enabled": bool(x_raw & 0x80),
            "yTile": y_raw & 0x3F,
            "unknownYBits": y_raw & 0xC0,
            "nameIndex": name_index,
            "name": names[name_index] if 0 <= name_index < len(names) else "",
            "scripted": scripted,
            "destinationScene": None if scripted else scene_index,
            "scriptAddressIndex": pointer_or_facing if scripted else None,
            "facing": None if scripted else pointer_or_facing,
            "halfTileLeft": bool(facing_raw & 0x08),
            "halfTileUp": bool(facing_raw & 0x10),
            "unknownFacingBits": facing_raw & 0xE1,
            "targetX": target_x,
            "targetY": target_y,
        })

    trigger_count, trigger_start, pos = _take_count(payload, pos, 3, "World trigger")
    live_trigger_count = 0
    for index in range(trigger_count):
        offset = trigger_start + index * 3
        x_raw, y, script_index = struct.unpack_from("<BBB", payload, offset)
        if x_raw == 0 and y == 0 and script_index == 0:
            break
        live_trigger_count += 1
        rows.append({
            "token": f"{table_id}:trigger:{index}",
            "recordType": "trigger",
            "tableId": table_id,
            "recordId": index,
            "path": path,
            "sha256": digest(payload),
            "source": origin,
            "byteOffset": offset,
            "xTile": x_raw & 0x7F,
            "enabled": bool(x_raw & 0x80),
            "yTile": y,
            "scriptAddressIndex": script_index,
        })

    unknown_count, _unknown_start, pos = _take_count(payload, pos, 3, "Unknown world navigation")
    if pos >= len(payload):
        raise ValueError("World script-address count is missing")
    script_address_count = payload[pos]
    script_start = pos + 1
    script_end = script_start + script_address_count * 2
    if script_end > len(payload):
        raise ValueError("World script-address block is truncated")
    for row in rows:
        row["scriptAddressCount"] = script_address_count
    return {
        "path": path,
        "tableId": table_id,
        "source": origin,
        "sha256": digest(payload),
        "rows": rows,
        "exitCount": exit_count,
        "triggerCount": live_trigger_count,
        "storedTriggerCount": trigger_count,
        "unknownCount": unknown_count,
        "scriptAddressCount": script_address_count,
        "trailingBytes": len(payload) - script_end,
    }


def load_world_navigation(store: OverlayStore, source: str = "mine", language: str = "en") -> dict:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    rows = []
    files = []
    for path in store.archive.paths("Game/world/EventTable/"):
        if not EVENT_TABLE_RE.match(path):
            continue
        parsed = _parse_file(store, path, source, language)
        rows.extend(parsed.pop("rows"))
        files.append(parsed)
    rows.sort(key=lambda row: (row["tableId"], 0 if row["recordType"] == "exit" else 1, row["recordId"]))
    files.sort(key=lambda row: row["tableId"])
    return {"rows": rows, "files": files, "language": language, "source": source}


def _bounded(name: str, value, low: int, high: int) -> int:
    number = int(value)
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return number


def save_world_navigation(
    store: OverlayStore, path: str, expected_sha256: str, edits: list[dict], language: str = "en"
) -> dict:
    current = _parse_file(store, path, "mine", language)
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    output = bytearray(payload)
    seen = set()

    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate world navigation edit")
        seen.add(token)
        row = by_token[token]
        values = dict(edit.get("values") or {})
        if row["recordType"] == "exit":
            allowed = {
                "xTile", "enabled", "yTile", "nameIndex", "destinationScene",
                "scriptAddressIndex", "facing", "halfTileLeft", "halfTileUp",
                "targetX", "targetY",
            }
            unknown = set(values) - allowed
            if unknown:
                raise ValueError(f"Unsupported world exit fields: {', '.join(sorted(unknown))}")
            x = _bounded("World exit X", values.get("xTile", row["xTile"]), 0, 0x7F)
            if bool(values.get("enabled", row["enabled"])):
                x |= 0x80
            y = row["unknownYBits"] | _bounded("World exit Y", values.get("yTile", row["yTile"]), 0, 0x3F)
            name_index = _bounded("World exit name index", values.get("nameIndex", row["nameIndex"]), 0, 0xFF)
            target_x = _bounded("World exit destination X", values.get("targetX", row["targetX"]), 0, 0xFF)
            target_y = _bounded("World exit destination Y", values.get("targetY", row["targetY"]), 0, 0xFF)
            facing_raw = row["unknownFacingBits"]
            if bool(values.get("halfTileLeft", row["halfTileLeft"])):
                facing_raw |= 0x08
            if bool(values.get("halfTileUp", row["halfTileUp"])):
                facing_raw |= 0x10
            if row["scripted"]:
                if "destinationScene" in values:
                    raise ValueError("A scripted world exit cannot be converted into a destination exit")
                maximum = max(0, min(3, current["scriptAddressCount"] - 1))
                pointer = _bounded(
                    "World script address index",
                    values.get("scriptAddressIndex", row["scriptAddressIndex"]),
                    0, maximum,
                )
                scene_index = 0x1FF
                facing_raw |= pointer << 1
            else:
                if "scriptAddressIndex" in values:
                    raise ValueError("A destination world exit cannot be converted into a scripted exit")
                scene_index = _bounded(
                    "World exit destination scene",
                    values.get("destinationScene", row["destinationScene"]), 0, 0xFFFF,
                )
                if scene_index == 0x1FF:
                    raise ValueError("0x1FF is the scripted-exit sentinel and cannot be created here")
                facing = _bounded("World exit facing", values.get("facing", row["facing"]), 0, 3)
                facing_raw |= facing << 1
            struct.pack_into(
                "<BBBHBBB", output, row["byteOffset"],
                x, y, name_index, scene_index, facing_raw, target_x, target_y,
            )
        else:
            allowed = {"xTile", "enabled", "yTile", "scriptAddressIndex"}
            unknown = set(values) - allowed
            if unknown:
                raise ValueError(f"Unsupported world trigger fields: {', '.join(sorted(unknown))}")
            x = _bounded("World trigger X", values.get("xTile", row["xTile"]), 0, 0x7F)
            enabled = bool(values.get("enabled", row["enabled"]))
            if enabled:
                x |= 0x80
            y = _bounded("World trigger Y", values.get("yTile", row["yTile"]), 0, 0xFF)
            maximum = max(0, current["scriptAddressCount"] - 1)
            script_index = _bounded(
                "World trigger script address index",
                values.get("scriptAddressIndex", row["scriptAddressIndex"]), 0, maximum,
            )
            if x == 0 and y == 0 and script_index == 0:
                raise ValueError("0,0,0 is the world-trigger terminator and cannot be created")
            struct.pack_into("<BBB", output, row["byteOffset"], x, y, script_index)

    store.write(path, expected_sha256, bytes(output))
    return _parse_file(store, path, "mine", language)
