"""Bounded Chrono Trigger Steam sprite-cell assembly editing.

Current-PC Game/chara/cell/cNNN.cel files have a three-byte prefix, a fixed
frame count and preserved header word, then per-frame fixed tile counts. Each
existing tile is five bytes: encoded chip index, signed X/Y and flags. Lexeditor
does not resize frames or tile lists. The odd stored source bit and all flag
bits except documented flip-X are preserved.
"""
from __future__ import annotations

import re
import struct

from .project import OverlayStore, digest, validate_resource_path


ASSEMBLY_RE = re.compile(r"^Game/chara/cell/c(\d+)\.cel$", re.IGNORECASE)
PREFIX_BYTES = 3
HEADER_BYTES = 7
MAX_CHIP_INDEX = 0x7FFF


def _signed(value: int) -> int:
    return value - 256 if value >= 128 else value


def _signed_byte(name: str, value) -> int:
    number = int(value)
    if not -128 <= number <= 127:
        raise ValueError(f"{name} must be between -128 and 127")
    return number & 0xFF


def _decode_chip(value: int) -> tuple[int, bool]:
    return (value & 0x07) | ((value & 0xFFF0) >> 1), bool(value & 0x0008)


def _encode_chip(chip: int, weird_bit: bool) -> int:
    number = int(chip)
    if not 0 <= number <= MAX_CHIP_INDEX:
        raise ValueError(f"Sprite assembly chip index must be between 0 and {MAX_CHIP_INDEX}")
    return (number & 0x07) | ((number & 0x7FF8) << 1) | (0x08 if weird_bit else 0)


def _parse(store: OverlayStore, path: str, source: str) -> dict:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    path = validate_resource_path(path)
    match = ASSEMBLY_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/chara/cell/c*.cel files use this editor")
    payload, origin = store.read(path, source)
    if len(payload) < HEADER_BYTES:
        raise ValueError(f"{path} is shorter than the current-PC sprite assembly header")
    file_id = int(match.group(1))
    frame_count, header_word = struct.unpack_from("<HH", payload, PREFIX_BYTES)
    pos = HEADER_BYTES
    rows = []
    for frame_id in range(frame_count):
        if pos >= len(payload):
            raise ValueError(f"{path} ends before frame {frame_id}")
        tile_count = payload[pos]
        pos += 1
        if pos + tile_count * 5 > len(payload):
            raise ValueError(f"{path} frame {frame_id} is truncated")
        for tile_id in range(tile_count):
            offset = pos
            raw_value = struct.unpack_from("<H", payload, offset)[0]
            chip, weird = _decode_chip(raw_value)
            x = _signed(payload[offset + 2])
            y = _signed(payload[offset + 3])
            flags = payload[offset + 4]
            rows.append({
                "token": f"{file_id}:{frame_id}:{tile_id}",
                "fileId": file_id, "frameId": frame_id, "tileId": tile_id,
                "path": path, "source": origin, "sha256": digest(payload),
                "byteOffset": offset, "frameTileCount": tile_count,
                "chipIndex": chip, "weirdSourceBit": weird,
                "x": x, "y": y, "isTop": y < -24,
                "flipHorizontal": bool(flags & 0x01),
                "unknownFlags": flags & 0xFE,
            })
            pos += 5
    trailing = len(payload) - pos
    for row in rows:
        row["fileTrailingBytes"] = trailing
        row["frameCount"] = frame_count
        row["headerWord"] = header_word
        row["prefixHex"] = payload[:PREFIX_BYTES].hex().upper()
    return {
        "path": path, "fileId": file_id, "source": origin, "sha256": digest(payload),
        "frameCount": frame_count, "headerWord": header_word,
        "prefixHex": payload[:PREFIX_BYTES].hex().upper(),
        "trailingBytes": trailing, "rows": rows,
    }


def load_sprite_assemblies(store: OverlayStore, source: str = "mine") -> dict:
    rows = []
    files = []
    for path in store.archive.paths("Game/chara/cell/"):
        if not ASSEMBLY_RE.match(path):
            continue
        parsed = _parse(store, path, source)
        rows.extend(parsed.pop("rows"))
        files.append(parsed)
    rows.sort(key=lambda row: (row["fileId"], row["frameId"], row["tileId"]))
    files.sort(key=lambda row: row["fileId"])
    return {"rows": rows, "files": files, "source": source}


def save_sprite_assembly(
    store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]
) -> dict:
    current = _parse(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    output = bytearray(payload)
    seen = set()
    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate sprite assembly edit")
        seen.add(token)
        row = by_token[token]
        values = dict(edit.get("values") or {})
        unknown = set(values) - {"chipIndex", "x", "y", "flipHorizontal"}
        if unknown:
            raise ValueError(f"Unsupported sprite assembly fields: {', '.join(sorted(unknown))}")
        raw_chip = _encode_chip(values.get("chipIndex", row["chipIndex"]), row["weirdSourceBit"])
        flags = row["unknownFlags"] | (0x01 if bool(values.get("flipHorizontal", row["flipHorizontal"])) else 0)
        offset = row["byteOffset"]
        struct.pack_into("<H", output, offset, raw_chip)
        output[offset + 2] = _signed_byte("Sprite X", values.get("x", row["x"]))
        output[offset + 3] = _signed_byte("Sprite Y", values.get("y", row["y"]))
        output[offset + 4] = flags
    store.write(path, expected_sha256, bytes(output))
    return _parse(store, path, "mine")
