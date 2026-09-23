"""Semantic merge units for FF8 world-map editor assets."""

from __future__ import annotations

from . import world_geometry, world_map, world_textures


def _wmset_units(data: bytes) -> list[tuple[str, int, int]]:
    parsed = world_map.parse(data)
    pointers = world_map._pointers(data)
    units = []
    for row in parsed["helpers"]:
        start = pointers[0] + 4 + int(row["id"]) * 4
        units.extend((
            (f"helper:{row['id']}:regionId", start, 1),
            (f"helper:{row['id']}:groundId", start + 1, 1),
            (f"helper:{row['id']}:encounterGroup", start + 2, 2),
        ))
    units.extend((f"region:{row['id']}:regionId", pointers[1] + int(row["id"]), 1)
                 for row in parsed["regions"])
    for row in parsed["groups"]:
        start = pointers[3] + int(row["id"]) * 16
        units.extend((f"group:{row['id']}:encounter:{slot}", start + slot * 2, 2)
                     for slot in range(8))
    for row in parsed["drawPoints"]:
        start = (pointers[world_map.DRAW_SECTION] + world_map.DRAW_HEADER_SIZE
                 + int(row["id"]) * world_map.DRAW_RECORD_SIZE)
        units.extend((
            (f"drawPoint:{row['id']}:x", start, 1),
            (f"drawPoint:{row['id']}:y", start + 1, 1),
            (f"drawPoint:{row['id']}:subId", start + 2, 1),
        ))
    for row in parsed["fieldReturns"]:
        start = (pointers[world_map.FIELD_RETURN_SECTION]
                 + int(row["id"]) * world_map.FIELD_RETURN_RECORD_SIZE)
        units.extend((
            (f"fieldReturn:{row['id']}:x", start, 4),
            (f"fieldReturn:{row['id']}:z", start + 4, 4),
            (f"fieldReturn:{row['id']}:y", start + 8, 2),
        ))
    for row in parsed["skyColors"]:
        start = pointers[world_map.SKY_SECTION] + int(row["recordOffset"])
        units.extend((
            (f"skyColor:{row['id']}:x", start, 4),
            (f"skyColor:{row['id']}:z", start + 4, 4),
            (f"skyColor:{row['id']}:y", start + 8, 4),
        ))
        units.extend((f"skyColor:{row['id']}:{key}", start + offset, 3)
                     for key, offset in world_map.SKY_COLOR_FIELDS)
    return units


def _rail_units(data: bytes) -> list[tuple[str, int, int]]:
    parsed = world_map.parse_rail(data)
    units = []
    for track in parsed["tracks"]:
        start = int(track["id"]) * world_map.RAIL_BLOCK_SIZE
        units.extend(((f"track:{track['id']}:trainStop1", start + 4, 4),
                      (f"track:{track['id']}:trainStop2", start + 8, 4)))
        for point in track["points"]:
            point_start = start + world_map.RAIL_HEADER_SIZE + int(point["id"]) * world_map.RAIL_POINT_SIZE
            units.extend((f"track:{track['id']}:point:{point['id']}:{axis}",
                          point_start + offset, 4)
                         for axis, offset in (("x", 0), ("y", 4), ("z", 8)))
    return units


def _texture_units(data: bytes) -> list[tuple[str, int, int]]:
    world_textures.parse(data)
    units = []
    for texture_id in range(world_textures.TEXTURE_COUNT):
        start = texture_id * world_textures.SLOT_SIZE
        used = world_textures._tim_layout(
            data[start:start + world_textures.SLOT_SIZE])["used"]
        units.append((f"texture:{texture_id}", start, used))
    return units


def _geometry_units(data: bytes) -> list[tuple[str, int, int]]:
    parsed = world_geometry.parse(data)
    return [(f"segment:{row['id']}:groupId",
             int(row["id"]) * world_geometry.SEGMENT_SIZE, 4)
            for row in parsed["segments"]]


UNIT_READERS = {
    "wmset": _wmset_units,
    "rail": _rail_units,
    "textures": _texture_units,
    "geometry": _geometry_units,
}


def merge(vanilla: bytes, mods: list[tuple[str, bytes]], kind: str, path: str
          ) -> tuple[bytes | None, list[dict], str]:
    """Merge editor-owned units or return an explicit opaque fallback reason."""
    if kind not in UNIT_READERS:
        raise ValueError(f"Unknown world merge kind: {kind}")
    try:
        units = UNIT_READERS[kind](vanilla)
    except ValueError as error:
        return None, [], f"vanilla {path} is unsupported: {error}"
    extracted = []
    for mod_id, source in mods:
        if len(source) != len(vanilla):
            return None, [], f"{mod_id} changes the size of {path}"
        try:
            if UNIT_READERS[kind](source) != units:
                return None, [], f"{mod_id} changes the proved structure of {path}"
        except ValueError as error:
            return None, [], f"{mod_id} is not a supported {path}: {error}"
        changes = {}
        reconstructed = bytearray(vanilla)
        for label, start, size in units:
            value = source[start:start + size]
            if value != vanilla[start:start + size]:
                changes[label] = value
                reconstructed[start:start + size] = value
        if bytes(reconstructed) != source:
            return None, [], f"{mod_id} contains changes outside proved {kind} units"
        extracted.append((mod_id, changes))

    unit_locations = {label: (start, size) for label, start, size in units}
    claims: dict[str, list[tuple[str, bytes]]] = {}
    for mod_id, changes in extracted:
        for label, value in changes.items():
            claims.setdefault(label, []).append((mod_id, value))
    output = bytearray(vanilla)
    conflicts = []
    for label, values in claims.items():
        start, size = unit_locations[label]
        output[start:start + size] = values[-1][1]
        if len(values) > 1 and len({value for _, value in values}) > 1:
            conflicts.append({"unit": f"{path}:{label}", "winner": values[-1][0],
                              "claimants": [mod_id for mod_id, _ in values]})
    UNIT_READERS[kind](bytes(output))
    return bytes(output), conflicts, ""
