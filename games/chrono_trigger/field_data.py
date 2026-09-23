"""Fixed-size Steam field exits and treasure records from CTViewer's PC layouts."""
from __future__ import annotations

import struct

from .project import OverlayStore, digest


EXIT_OFFSET_PATH = "Game/common/MapJumpOffsetTbl.dat"
EXIT_DATA_PATH = "Game/common/MapJumpDataTbl.dat"
TREASURE_OFFSET_PATH = "Game/common/TakaraOffsetTbl.dat"
TREASURE_DATA_PATH = "Game/common/TakaraDataTbl.dat"

TREASURE_BASES = {
    "weapon": 0,
    "armor": 111,
    "helmet": 161,
    "accessory": 200,
    "consumable": 259,
    "item": 302,
}
TREASURE_PREFIX = {
    "weapon": 0x0000,
    "armor": 0x1000,
    "helmet": 0x2000,
    "accessory": 0x3000,
    "consumable": 0x4000,
    "item": 0x5000,
}
PREFIX_KIND = {value: key for key, value in TREASURE_PREFIX.items()}


def _offsets(payload: bytes, record_size: int, *, label: str) -> list[int]:
    if len(payload) < 4:
        raise ValueError(f"{label} offset table is truncated")
    count = struct.unpack_from("<I", payload, 0)[0]
    if count < 2 or 4 + count * 2 > len(payload):
        raise ValueError(f"{label} offset table has an invalid count")
    result = [struct.unpack_from("<H", payload, 4 + i * 2)[0] * record_size + 4 for i in range(count)]
    if any(right < left for left, right in zip(result, result[1:])):
        raise ValueError(f"{label} offsets are not monotonic")
    return result


def load_exits(store: OverlayStore, source: str = "mine") -> dict:
    offset_payload, offset_origin = store.read(EXIT_OFFSET_PATH, source)
    data_payload, data_origin = store.read(EXIT_DATA_PATH, source)
    offsets = _offsets(offset_payload, 8, label="MapJump")
    rows = []
    for scene in range(len(offsets)):
        start = offsets[scene]
        end = offsets[scene + 1] if scene + 1 < len(offsets) else len(data_payload)
        if start > end or end > len(data_payload) or (end - start) % 8:
            raise ValueError(f"Scene {scene} exit slice is invalid")
        for index, pos in enumerate(range(start, end, 8)):
            x, y, size_byte, facing_byte, destination, target_x, target_y = struct.unpack_from("<BBBBHBB", data_payload, pos)
            rows.append({
                "token": f"{scene}:{index}", "sceneId": scene, "exitId": index,
                "xTile": x, "yTile": y,
                "lengthTiles": (size_byte & 0x7F) + 1,
                "orientation": "vertical" if size_byte & 0x80 else "horizontal",
                "destinationId": destination, "destinationKind": "world" if 0x1F0 <= destination <= 0x1FF else "scene",
                "facing": facing_byte & 0x03,
                "halfTileLeft": bool(facing_byte & 0x04), "halfTileUp": bool(facing_byte & 0x08),
                "targetX": target_x, "targetY": target_y,
                "unknownFacingBits": facing_byte & 0xF0,
                "byteOffset": pos,
            })
    return {
        "rows": rows, "source": "project" if "project" in {offset_origin, data_origin} else "vanilla",
        "dataSha256": digest(data_payload), "offsetSha256": digest(offset_payload),
    }


def _bounded(name: str, value, low: int, high: int) -> int:
    number = int(value)
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return number


def save_exits(store: OverlayStore, expected_data_sha: str, expected_offset_sha: str, edits: list[dict]) -> dict:
    offset_payload, _ = store.read(EXIT_OFFSET_PATH, "mine")
    data_payload, _ = store.read(EXIT_DATA_PATH, "mine")
    if digest(offset_payload) != expected_offset_sha or digest(data_payload) != expected_data_sha:
        raise RuntimeError("Exit tables changed since they were opened; reload before saving")
    current = {row["token"]: row for row in load_exits(store, "mine")["rows"]}
    output = bytearray(data_payload)
    seen = set()
    for edit in edits:
        token = str(edit["token"])
        if token in seen or token not in current:
            raise ValueError("Invalid or duplicate exit edit")
        seen.add(token)
        row = current[token]
        values = dict(edit.get("values") or {})
        x = _bounded("Exit X", values.get("xTile", row["xTile"]), 0, 255)
        y = _bounded("Exit Y", values.get("yTile", row["yTile"]), 0, 255)
        length = _bounded("Exit length", values.get("lengthTiles", row["lengthTiles"]), 1, 128)
        orientation = str(values.get("orientation", row["orientation"]))
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("Exit orientation must be horizontal or vertical")
        destination = _bounded("Destination", values.get("destinationId", row["destinationId"]), 0, 0x1FF)
        facing = _bounded("Facing", values.get("facing", row["facing"]), 0, 3)
        target_x = _bounded("Destination X", values.get("targetX", row["targetX"]), 0, 255)
        target_y = _bounded("Destination Y", values.get("targetY", row["targetY"]), 0, 255)
        flags = row["unknownFacingBits"] | facing
        if bool(values.get("halfTileLeft", row["halfTileLeft"])):
            flags |= 0x04
        if bool(values.get("halfTileUp", row["halfTileUp"])):
            flags |= 0x08
        size = (length - 1) | (0x80 if orientation == "vertical" else 0)
        struct.pack_into("<BBBBHBB", output, row["byteOffset"], x, y, size, flags, destination, target_x, target_y)
    store.write(EXIT_DATA_PATH, expected_data_sha, bytes(output))
    return load_exits(store, "mine")


def _item_names(store: OverlayStore, language: str, source: str) -> list[str]:
    path = f"Localize/{language}/msg/item.txt"
    if not store.archive.has(path):
        return []
    payload, _ = store.read(path, source)
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return []
    result = []
    for line in text.splitlines():
        _key, sep, value = line.partition(",")
        result.append(value if sep else line)
    return result


def _decode_treasure(contents: int) -> dict:
    if contents & 0x8000:
        return {"kind": "gold", "gold": (contents & 0x7FFF) * 2, "localIndex": None, "globalItemId": None}
    kind = PREFIX_KIND.get(contents & 0xF000)
    if kind is None:
        return {"kind": "unknown", "gold": None, "localIndex": None, "globalItemId": None}
    local = contents & 0x1FF
    return {"kind": kind, "gold": None, "localIndex": local, "globalItemId": TREASURE_BASES[kind] + local}


def load_treasure(store: OverlayStore, source: str = "mine", language: str = "en") -> dict:
    offset_payload, offset_origin = store.read(TREASURE_OFFSET_PATH, source)
    data_payload, data_origin = store.read(TREASURE_DATA_PATH, source)
    offsets = _offsets(offset_payload, 6, label="Takara")
    names = _item_names(store, language, source)
    rows = []
    for scene in range(max(0, len(offsets) - 1)):
        start, end = offsets[scene], offsets[scene + 1]
        if start > end or end > len(data_payload) or (end - start) % 6:
            raise ValueError(f"Scene {scene} treasure slice is invalid")
        for index, pos in enumerate(range(start, end, 6)):
            x, y, contents, trailing = struct.unpack_from("<BBHH", data_payload, pos)
            decoded = _decode_treasure(contents)
            alias = x == 0 and y == 0
            global_id = decoded.get("globalItemId")
            rows.append({
                "token": f"{scene}:{index}", "sceneId": scene, "treasureId": index,
                "xTile": x, "yTile": y, "alias": alias, "aliasScene": contents if alias else None,
                **decoded,
                "itemName": names[global_id] if isinstance(global_id, int) and 0 <= global_id < len(names) else "",
                "trailingWord": trailing, "editable": not alias and decoded["kind"] != "unknown", "byteOffset": pos,
            })
    return {
        "rows": rows, "source": "project" if "project" in {offset_origin, data_origin} else "vanilla",
        "dataSha256": digest(data_payload), "offsetSha256": digest(offset_payload),
        "kinds": list(TREASURE_PREFIX) + ["gold"],
    }


def save_treasure(store: OverlayStore, expected_data_sha: str, expected_offset_sha: str, edits: list[dict], language: str = "en") -> dict:
    offset_payload, _ = store.read(TREASURE_OFFSET_PATH, "mine")
    data_payload, _ = store.read(TREASURE_DATA_PATH, "mine")
    if digest(offset_payload) != expected_offset_sha or digest(data_payload) != expected_data_sha:
        raise RuntimeError("Treasure tables changed since they were opened; reload before saving")
    current = {row["token"]: row for row in load_treasure(store, "mine", language)["rows"]}
    output = bytearray(data_payload)
    seen = set()
    for edit in edits:
        token = str(edit["token"])
        if token in seen or token not in current:
            raise ValueError("Invalid or duplicate treasure edit")
        seen.add(token)
        row = current[token]
        if not row["editable"]:
            raise ValueError("Aliased or unknown treasure records are read-only")
        values = dict(edit.get("values") or {})
        x = _bounded("Treasure X", values.get("xTile", row["xTile"]), 0, 255)
        y = _bounded("Treasure Y", values.get("yTile", row["yTile"]), 0, 255)
        if x == 0 and y == 0:
            raise ValueError("0,0 is a treasure-alias sentinel and cannot be created by the fixed record editor")
        kind = str(values.get("kind", row["kind"]))
        if kind == "gold":
            gold = _bounded("Gold", values.get("gold", row.get("gold") or 0), 0, 65534)
            if gold % 2:
                raise ValueError("Steam treasure gold is stored in increments of 2")
            contents = 0x8000 | (gold // 2)
        elif kind in TREASURE_PREFIX:
            local = _bounded("Treasure item index", values.get("localIndex", row.get("localIndex") or 0), 0, 0x1FF)
            contents = TREASURE_PREFIX[kind] | local
        else:
            raise ValueError("Unknown treasure type")
        struct.pack_into("<BBH", output, row["byteOffset"], x, y, contents)
    store.write(TREASURE_DATA_PATH, expected_data_sha, bytes(output))
    return load_treasure(store, "mine", language)
