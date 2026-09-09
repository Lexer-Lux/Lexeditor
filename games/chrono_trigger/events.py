"""Read-only structural parser for Chrono Trigger Steam field event scripts.

Temporal Redux establishes that PC ``Atel_*.dat`` uses the original event
layout directly: one object-count byte followed by 16 little-endian function
pointers per object and then event bytecode.  Lexeditor uses that proven
container structure here without pretending to understand commands it has not
integrated yet.
"""

from __future__ import annotations

from pathlib import PurePosixPath
import re
import struct

from .data import OverlayStore, sha256


_FIELD_EVENT_RE = re.compile(r"^Game/field/atel/Atel_(\d+)\.dat$", re.IGNORECASE)
FUNCTION_NAMES = (
    "Startup", "Activate", "Touch",
    "Arbitrary 0", "Arbitrary 1", "Arbitrary 2", "Arbitrary 3", "Arbitrary 4",
    "Arbitrary 5", "Arbitrary 6", "Arbitrary 7", "Arbitrary 8", "Arbitrary 9",
    "Arbitrary A", "Arbitrary B", "Arbitrary C",
)


def event_entries(store: OverlayStore) -> list[tuple[int, str]]:
    rows = []
    for entry in store.archive.entries:
        match = _FIELD_EVENT_RE.match(entry.path)
        if match:
            rows.append((int(match.group(1)), entry.path))
    return sorted(rows)


def parse_event(raw: bytes) -> dict:
    """Decode the object/function pointer table, leaving bytecode opaque."""
    if not raw:
        raise ValueError("Chrono Trigger field event is empty")
    object_count = raw[0]
    if object_count > 0x40:
        raise ValueError(f"Chrono Trigger field event has invalid object count: {object_count}")
    data = raw[1:]
    pointer_table_bytes = object_count * 32
    if pointer_table_bytes > len(data):
        raise ValueError("Chrono Trigger field event pointer table is truncated")

    slot_count = object_count * 16
    starts = [struct.unpack_from("<H", data, index * 2)[0] for index in range(slot_count)]
    for index, start in enumerate(starts):
        if not pointer_table_bytes <= start <= len(data):
            raise ValueError(
                f"Chrono Trigger event function pointer {index} is outside bytecode: {start}"
            )

    ends = [len(data)] * slot_count
    for index in range(slot_count - 2, -1, -1):
        ends[index] = starts[index + 1] if starts[index + 1] != starts[index] else ends[index + 1]

    objects = []
    for object_id in range(object_count):
        functions = []
        for function_id in range(16):
            index = object_id * 16 + function_id
            start, end = starts[index], ends[index]
            if end < start or end > len(data):
                raise ValueError(
                    f"Chrono Trigger event function {object_id}:{function_id} has invalid bounds"
                )
            payload = data[start:end]
            functions.append({
                "id": function_id,
                "name": FUNCTION_NAMES[function_id],
                "start": start,
                "end": end,
                "length": len(payload),
                "preview": payload[:32].hex(" ").upper(),
                "truncatedPreview": len(payload) > 32,
            })
        object_start = starts[object_id * 16] if functions else pointer_table_bytes
        object_end = (starts[(object_id + 1) * 16]
                      if object_id + 1 < object_count else len(data))
        objects.append({
            "id": object_id,
            "start": object_start,
            "end": object_end,
            "functions": functions,
        })

    unique_bounds = len(set(zip(starts, ends)))
    return {
        "objectCount": object_count,
        "functionSlots": slot_count,
        "uniqueFunctionBounds": unique_bounds,
        "pointerTableBytes": pointer_table_bytes,
        "bytecodeBytes": max(0, len(data) - pointer_table_bytes),
        "objects": objects,
    }


def load_event(store: OverlayStore, event_id: int, virtual_path: str,
               source: str = "mine", include_objects: bool = True) -> dict:
    raw, origin = store.read(virtual_path, source)
    parsed = parse_event(raw)
    result = {
        "id": int(event_id),
        "name": f"Field Event {int(event_id):04d}",
        "path": PurePosixPath(virtual_path).as_posix(),
        "source": origin,
        "readOnly": True,
        "sha256": sha256(raw),
        **parsed,
    }
    if not include_objects:
        result.pop("objects", None)
    return result


def load_events(store: OverlayStore, source: str = "mine", query: str = "",
                offset: int = 0, limit: int = 100) -> dict:
    needle = query.strip().casefold()
    entries = [(event_id, path) for event_id, path in event_entries(store)
               if not needle or needle in str(event_id).casefold() or needle in path.casefold()]
    offset = max(0, min(int(offset), len(entries)))
    limit = max(1, min(int(limit), 250))
    rows = [load_event(store, event_id, path, source, include_objects=False)
            for event_id, path in entries[offset:offset + limit]]
    return {
        "kind": "field-events",
        "readOnly": True,
        "matchCount": len(entries),
        "offset": offset,
        "limit": limit,
        "rows": rows,
    }


def get_event(store: OverlayStore, event_id: int, source: str = "mine") -> dict:
    matches = {number: path for number, path in event_entries(store)}
    event_id = int(event_id)
    if event_id not in matches:
        raise ValueError(f"Unknown Chrono Trigger field event: {event_id}")
    return load_event(store, event_id, matches[event_id], source, include_objects=True)
