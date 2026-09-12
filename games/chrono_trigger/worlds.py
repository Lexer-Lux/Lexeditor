"""Structured Chrono Trigger Steam overworld headers.

CTViewer documents eight PC overworld records stored inside
``Game/common/bankc6.bin`` at ``0xFD10 + world_index * 23``.  Every field in
that 23-byte record is an unsigned byte, so existing headers can be edited
without relocating any data in the shared bank file.
"""

from __future__ import annotations

from dataclasses import dataclass

from .data import OverlayStore, sha256


WORLD_BANK = "Game/common/bankc6.bin"
WORLD_NAMES = "Localize/en/msg/w_map.txt"
WORLD_COUNT = 8
WORLD_HEADER_OFFSET = 0xFD10
WORLD_HEADER_SIZE = 23
WORLD_NAME_LINES = (106, 107, 108, 109, 110, 110, 110, 111)


@dataclass(frozen=True)
class WorldField:
    key: str
    label: str
    offset: int


WORLD_FIELDS = (
    WorldField("chipL12_0", "Layer 1/2 Chip 0", 0),
    WorldField("chipL12_1", "Layer 1/2 Chip 1", 1),
    WorldField("chipL12_2", "Layer 1/2 Chip 2", 2),
    WorldField("chipL12_3", "Layer 1/2 Chip 3", 3),
    WorldField("chipL12_4", "Layer 1/2 Chip 4", 4),
    WorldField("chipL12_5", "Layer 1/2 Chip 5", 5),
    WorldField("chipL12_6", "Layer 1/2 Chip 6", 6),
    WorldField("chipL12_7", "Layer 1/2 Chip 7", 7),
    WorldField("chipL3_0", "Layer 3 Chip 0", 8),
    WorldField("chipL3_1", "Layer 3 Chip 1", 9),
    WorldField("palette", "Palette", 10),
    WorldField("paletteAnimationsStored", "Stored Palette Animation", 11),
    WorldField("spriteSet0", "Sprite Set 0", 12),
    WorldField("spriteSet1", "Sprite Set 1", 13),
    WorldField("spriteSet2", "Sprite Set 2", 14),
    WorldField("spriteSet3", "Sprite Set 3", 15),
    WorldField("assemblyL12", "Layer 1/2 Assembly", 16),
    WorldField("map", "Map", 17),
    WorldField("mapProperties", "Map Properties", 18),
    WorldField("musicProperties", "Music Properties", 19),
    WorldField("assemblyL3", "Layer 3 Assembly", 20),
    WorldField("exits", "Exit/Trigger Table", 21),
    WorldField("script", "World Script", 22),
)


def _world_names(store: OverlayStore, source: str) -> list[str]:
    try:
        raw, _origin = store.read(WORLD_NAMES, source)
        lines = raw.decode("utf-8-sig").splitlines()
    except (KeyError, UnicodeDecodeError):
        return [f"World {index}" for index in range(WORLD_COUNT)]
    names = []
    for index, line_index in enumerate(WORLD_NAME_LINES):
        if line_index >= len(lines):
            names.append(f"World {index}")
            continue
        line = lines[line_index]
        names.append(line.split(",", 1)[1] if "," in line else line)
    return names


def _record(raw: bytes, world_id: int) -> dict[str, int]:
    start = WORLD_HEADER_OFFSET + int(world_id) * WORLD_HEADER_SIZE
    end = start + WORLD_HEADER_SIZE
    if len(raw) < end:
        raise ValueError(
            f"Chrono Trigger world header {world_id} is outside bankc6.bin "
            f"({len(raw)} bytes; need at least {end})"
        )
    data = raw[start:end]
    return {field.key: data[field.offset] for field in WORLD_FIELDS}


def load_worlds(store: OverlayStore, source: str = "mine") -> dict:
    raw, origin = store.read(WORLD_BANK, source)
    names = _world_names(store, source)
    rows = [
        {
            "id": world_id,
            "name": names[world_id],
            "source": origin,
            "readOnly": source == "vanilla",
            "values": _record(raw, world_id),
            "derived": {
                # CTViewer notes that PC ignores the stored palette-animation
                # byte and selects the animation set by world index instead.
                "effectivePaletteAnimations": world_id,
            },
        }
        for world_id in range(WORLD_COUNT)
    ]
    return {
        "kind": "world-headers",
        "path": WORLD_BANK,
        "source": origin,
        "readOnly": source == "vanilla",
        "sha256": sha256(raw),
        "headerOffset": WORLD_HEADER_OFFSET,
        "recordSize": WORLD_HEADER_SIZE,
        "fields": [
            {"key": field.key, "label": field.label, "kind": "integer", "min": 0, "max": 255}
            for field in WORLD_FIELDS
        ],
        "rows": rows,
    }


def save_world(store: OverlayStore, world_id: int, expected_sha256: str,
               values: dict) -> dict:
    world_id = int(world_id)
    if not 0 <= world_id < WORLD_COUNT:
        raise ValueError(f"World index must be between 0 and {WORLD_COUNT - 1}")
    raw, _origin = store.read(WORLD_BANK, "mine")
    if sha256(raw) != expected_sha256:
        raise RuntimeError("bankc6.bin changed since the world headers were opened; reload before saving")
    fields = {field.key: field for field in WORLD_FIELDS}
    unknown = set(values) - set(fields)
    if unknown:
        raise ValueError(f"Unknown world fields: {', '.join(sorted(unknown))}")
    output = bytearray(raw)
    start = WORLD_HEADER_OFFSET + world_id * WORLD_HEADER_SIZE
    if len(output) < start + WORLD_HEADER_SIZE:
        raise ValueError(f"World {world_id} is outside bankc6.bin")
    for key, value in values.items():
        number = int(value)
        if not 0 <= number <= 255:
            raise ValueError(f"{fields[key].label} must be between 0 and 255")
        output[start + fields[key].offset] = number
    store.write(WORLD_BANK, bytes(output))
    return load_worlds(store, "mine")
