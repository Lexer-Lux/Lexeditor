"""Bounded Chrono Trigger Steam field chip-animation editing.

Current-PC BGAnime files begin with an animation count. Each existing animation
stores a frame count, a destination chip-data offset, one duration byte per
frame, then one source chip-data offset per frame. Lexeditor never changes
animation/frame counts. Duration low nibbles, terminators and trailing bytes are
preserved.
"""
from __future__ import annotations

import re
import struct

from .project import OverlayStore, digest, validate_resource_path


ANIMATION_RE = re.compile(r"^Game/field/BGAnime/bganimeinfo_(\d+)\.dat$", re.IGNORECASE)
KNOWN_DURATION_CODES = {0x10: 16, 0x20: 12, 0x40: 8, 0x80: 4}
MAX_CHIP_INDEX = 0xFFFF // 32


def _parse_file(store: OverlayStore, path: str, source: str) -> dict:
    path = validate_resource_path(path)
    match = ANIMATION_RE.match(path)
    if not match:
        raise ValueError("Only Steam Game/field/BGAnime/bganimeinfo_*.dat files use this editor")
    payload, origin = store.read(path, source)
    if not payload:
        raise ValueError(f"{path} is empty")
    file_id = int(match.group(1))
    declared_count = payload[0]
    pos = 1
    rows = []
    stopped_by_terminator = False
    terminator_offset = None

    for animation_id in range(declared_count):
        if pos >= len(payload):
            raise ValueError(f"{path} ends before animation {animation_id}")
        record_start = pos
        frame_count = payload[pos]
        pos += 1
        if frame_count in {0, 0x80}:
            stopped_by_terminator = True
            terminator_offset = record_start
            break
        if pos + 2 > len(payload):
            raise ValueError(f"{path} animation {animation_id} is missing its destination offset")
        destination_offset = struct.unpack_from("<H", payload, pos)[0]
        pos += 2
        duration_start = pos
        duration_end = duration_start + frame_count
        source_start = duration_end
        source_end = source_start + frame_count * 2
        if source_end > len(payload):
            raise ValueError(f"{path} animation {animation_id} is truncated")
        durations = payload[duration_start:duration_end]
        sources = [struct.unpack_from("<H", payload, source_start + index * 2)[0]
                   for index in range(frame_count)]
        pos = source_end
        aligned = destination_offset % 32 == 0 and all(value % 32 == 0 for value in sources)
        row = {
            "token": f"{file_id}:{animation_id}",
            "fileId": file_id,
            "animationId": animation_id,
            "path": path,
            "sha256": digest(payload),
            "source": origin,
            "byteOffset": record_start,
            "frameCount": frame_count,
            "destinationChip": destination_offset // 32,
            "destinationOffsetRemainder": destination_offset % 32,
            "editable": aligned,
        }
        for frame_index, (duration, source_offset) in enumerate(zip(durations, sources)):
            code = duration & 0xF0
            row[f"durationCode{frame_index}"] = code
            row[f"durationTicks{frame_index}"] = KNOWN_DURATION_CODES.get(code)
            row[f"durationLowBits{frame_index}"] = duration & 0x0F
            row[f"sourceChip{frame_index}"] = source_offset // 32
            row[f"sourceOffsetRemainder{frame_index}"] = source_offset % 32
        rows.append(row)

    trailing_bytes = len(payload) - pos
    for row in rows:
        row["fileTrailingBytes"] = trailing_bytes
        row["declaredAnimationCount"] = declared_count
    return {
        "path": path,
        "fileId": file_id,
        "source": origin,
        "sha256": digest(payload),
        "declaredCount": declared_count,
        "parsedCount": len(rows),
        "stoppedByTerminator": stopped_by_terminator,
        "terminatorOffset": terminator_offset,
        "trailingBytes": trailing_bytes,
        "rows": rows,
    }


def load_chip_animations(store: OverlayStore, source: str = "mine") -> dict:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    rows = []
    files = []
    for path in store.archive.paths("Game/field/BGAnime/"):
        if not ANIMATION_RE.match(path):
            continue
        parsed = _parse_file(store, path, source)
        rows.extend(parsed.pop("rows"))
        files.append(parsed)
    rows.sort(key=lambda row: (row["fileId"], row["animationId"]))
    files.sort(key=lambda row: row["fileId"])
    return {"rows": rows, "files": files, "source": source}


def _chip(name: str, value) -> int:
    number = int(value)
    if not 0 <= number <= MAX_CHIP_INDEX:
        raise ValueError(f"{name} must be between 0 and {MAX_CHIP_INDEX}")
    return number


def save_chip_animations(store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]) -> dict:
    current = _parse_file(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    by_token = {row["token"]: row for row in current["rows"]}
    output = bytearray(payload)
    seen = set()

    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate chip-animation edit")
        seen.add(token)
        row = by_token[token]
        if not row["editable"]:
            raise ValueError("Misaligned chip offsets are preserved read-only")
        values = dict(edit.get("values") or {})
        allowed = {"destinationChip"}
        for frame_index in range(row["frameCount"]):
            allowed.add(f"durationCode{frame_index}")
            allowed.add(f"sourceChip{frame_index}")
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported chip-animation fields: {', '.join(sorted(unknown))}")

        record_start = row["byteOffset"]
        if "destinationChip" in values:
            struct.pack_into("<H", output, record_start + 1,
                             _chip("Destination chip", values["destinationChip"]) * 32)
        duration_start = record_start + 3
        source_start = duration_start + row["frameCount"]
        for frame_index in range(row["frameCount"]):
            duration_key = f"durationCode{frame_index}"
            if duration_key in values:
                code = int(values[duration_key])
                if code not in KNOWN_DURATION_CODES:
                    raise ValueError("Frame duration must use a documented Steam duration code")
                output[duration_start + frame_index] = code | row[f"durationLowBits{frame_index}"]
            source_key = f"sourceChip{frame_index}"
            if source_key in values:
                struct.pack_into("<H", output, source_start + frame_index * 2,
                                 _chip("Source chip", values[source_key]) * 32)

    store.write(path, expected_sha256, bytes(output))
    return _parse_file(store, path, "mine")
