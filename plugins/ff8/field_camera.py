"""Fail-closed FF8 field camera (.ca) reader and editor.

Record layout follows Deling's ``CaFile`` struct: three s16 axis vectors, a
padding copy of the third vector's Z, three s32 position words, a blank word,
and the u16 zoom with its padding copy (40 bytes per camera).  Deling also
accepts one 38-byte legacy camera without the final zoom copy.  Writes patch
only proved scalars and refresh the padding copies, exactly as Deling's save
does.  Sizes follow the observed game files; anything else fails closed.
"""

from __future__ import annotations

import struct

RECORD_SIZE = 40
LEGACY_SIZE = 38
_AXIS_OFFSETS = (0, 6, 12)
_POSITION_OFFSET = 20
_ZOOM_OFFSET = 36
_AXES = ("x", "y", "z")


def _count(raw: bytes) -> int:
    size = len(raw)
    if size == LEGACY_SIZE:
        return 1
    if size == 0 or size % RECORD_SIZE:
        raise ValueError(f"Unsupported field camera size: {size}")
    return size // RECORD_SIZE


def read(raw: bytes) -> dict:
    """Parse every camera setup; reject sizes Deling cannot open."""
    count = _count(raw)
    cameras = []
    for index in range(count):
        base = index * RECORD_SIZE
        axis = []
        for vector in range(3):
            x, y, z = struct.unpack_from("<hhh", raw, base + _AXIS_OFFSETS[vector])
            axis.append({"x": x, "y": y, "z": z})
        position = struct.unpack_from("<iii", raw, base + _POSITION_OFFSET)
        zoom = struct.unpack_from("<H", raw, base + _ZOOM_OFFSET)[0]
        cameras.append({
            "id": index,
            "axis": axis,
            "position": {"x": position[0], "y": position[1], "z": position[2]},
            "zoom": zoom,
        })
    return {"cameraCount": count, "cameras": cameras}


def _units(count: int) -> dict[tuple, tuple[int, str, int, int]]:
    """Every editable camera scalar by identity: offset, struct format, min, max."""
    units: dict[tuple, tuple[int, str, int, int]] = {}
    for index in range(count):
        base = index * RECORD_SIZE
        for vector in range(3):
            for axis_index, axis in enumerate(_AXES):
                units[("camera", index, f"axis{vector}", axis)] = (
                    base + _AXIS_OFFSETS[vector] + axis_index * 2, "h", -32768, 32767)
        for axis_index, axis in enumerate(_AXES):
            units[("camera", index, "position", axis)] = (
                base + _POSITION_OFFSET + axis_index * 4, "i", -2**31, 2**31 - 1)
        # Zoom 0 would divide by zero in the game projection, so it is rejected.
        units[("camera", index, "zoom")] = (base + _ZOOM_OFFSET, "H", 1, 0xFFFF)
    return units


def _refresh_padding(raw: bytearray, count: int) -> None:
    for index in range(count):
        base = index * RECORD_SIZE
        axis_z = struct.unpack_from("<h", raw, base + _AXIS_OFFSETS[2] + 4)[0]
        struct.pack_into("<h", raw, base + _AXIS_OFFSETS[2] + 6, axis_z)
        zoom = struct.unpack_from("<H", raw, base + _ZOOM_OFFSET)[0]
        struct.pack_into("<H", raw, base + _ZOOM_OFFSET + 2, zoom)


def apply_edits(raw: bytes, edits: list[dict]) -> tuple[bytes, int]:
    """Patch camera scalars in place; the legacy 38-byte camera grows to 40."""
    count = _count(raw)
    result = bytearray(raw)
    if len(result) == LEGACY_SIZE:
        result += b"\x00\x00"
    units = _units(count)
    seen = set()
    for edit in edits:
        camera = int(edit.get("camera", -1))
        field = str(edit.get("field", ""))
        if field == "zoom":
            identity = ("camera", camera, "zoom")
        else:
            identity = ("camera", camera, field, str(edit.get("axis", "")))
        if identity in seen or identity not in units:
            raise ValueError("Invalid or duplicate field camera edit")
        seen.add(identity)
        offset, fmt, minimum, maximum = units[identity]
        value = int(edit.get("value"))
        if not minimum <= value <= maximum:
            raise ValueError(f"Field camera value must be {minimum} to {maximum}")
        struct.pack_into("<" + fmt, result, offset, value)
    _refresh_padding(result, count)
    parsed = read(bytes(result))
    if parsed["cameraCount"] != count:
        raise ValueError("Field camera structure changed during save")
    return bytes(result), len(edits)


def merge(vanilla: bytes, mods: list[tuple[str, bytes]], path: str
          ) -> tuple[bytes | None, list[dict], str]:
    """Merge proved camera scalars, or return a visible whole-file fallback."""
    try:
        baseline = read(vanilla)
    except ValueError as error:
        return None, [], f"vanilla {path} is unsupported: {error}"
    # Padding copies carry no data and Deling rewrites them on save, so the
    # merge compares normalized bytes: a zoom edit must not read as a change
    # to the padding copy sitting beside it.
    normalized_vanilla = bytearray(vanilla)
    if len(normalized_vanilla) == LEGACY_SIZE:
        normalized_vanilla += b"\x00\x00"
    _refresh_padding(normalized_vanilla, baseline["cameraCount"])
    vanilla = bytes(normalized_vanilla)
    units = _units(baseline["cameraCount"])
    claims: dict[tuple, list[tuple[str, bytes]]] = {}
    for mod_id, source in mods:
        try:
            parsed = read(source)
        except ValueError as error:
            return None, [], f"{mod_id} is not a supported {path}: {error}"
        if parsed["cameraCount"] != baseline["cameraCount"]:
            return None, [], f"{mod_id} changes the camera structure of {path}"
        normalized = bytearray(source)
        if len(normalized) == LEGACY_SIZE:
            normalized += b"\x00\x00"
        _refresh_padding(normalized, baseline["cameraCount"])
        source = bytes(normalized)
        reconstructed = bytearray(vanilla)
        for identity, (offset, fmt, _minimum, _maximum) in units.items():
            size = struct.calcsize("<" + fmt)
            value = source[offset:offset + size]
            if value != vanilla[offset:offset + size]:
                claims.setdefault(identity, []).append((mod_id, value))
                reconstructed[offset:offset + size] = value
        _refresh_padding(reconstructed, baseline["cameraCount"])
        if bytes(reconstructed) != source:
            return None, [], f"{mod_id} contains changes outside proved camera units"
    output = bytearray(vanilla)
    conflicts = []
    for identity, values in claims.items():
        offset, fmt, _minimum, _maximum = units[identity]
        size = struct.calcsize("<" + fmt)
        output[offset:offset + size] = values[-1][1]
        if len(values) > 1 and len({value for _, value in values}) > 1:
            conflicts.append({"unit": f"{path}:{':'.join(map(str, identity))}",
                              "winner": values[-1][0],
                              "claimants": [mod_id for mod_id, _ in values]})
    _refresh_padding(output, baseline["cameraCount"])
    merged = bytes(output)
    if read(merged)["cameraCount"] != baseline["cameraCount"]:
        return None, [], f"merged {path} changed the camera structure"
    return merged, conflicts, ""
