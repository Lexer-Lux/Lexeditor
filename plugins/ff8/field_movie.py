"""Fail-closed FF8 field movie camera (.msk) reader and editor.

Layout follows Deling's ``MskFile``: a u32 frame count followed by that many
24-byte frames, each holding four s16 vertices.  Writes patch only proved
vertex scalars in place; frames are never added or removed, so the file size
is preserved exactly.
"""

from __future__ import annotations

import struct

FRAME_SIZE = 24
POINTS_PER_FRAME = 4
_AXES = ("x", "y", "z")


def _count(raw: bytes) -> int:
    if len(raw) < 4:
        raise ValueError(f"Field movie camera file is too small: {len(raw)}")
    count = struct.unpack_from("<I", raw, 0)[0]
    if len(raw) != 4 + count * FRAME_SIZE:
        raise ValueError(
            f"Field movie camera declares {count} frames but holds {len(raw)} bytes")
    return count


def read(raw: bytes) -> dict:
    """Parse every movie camera frame; reject count/size mismatches."""
    count = _count(raw)
    frames = []
    for index in range(count):
        base = 4 + index * FRAME_SIZE
        points = []
        for point in range(POINTS_PER_FRAME):
            x, y, z = struct.unpack_from("<hhh", raw, base + point * 6)
            points.append({"x": x, "y": y, "z": z})
        frames.append({"id": index, "points": points})
    return {"frameCount": count, "frames": frames}


def _units(count: int) -> dict[tuple, tuple[int, int, int]]:
    """Every editable movie scalar by identity: offset, min, max."""
    units: dict[tuple, tuple[int, int, int]] = {}
    for index in range(count):
        for point in range(POINTS_PER_FRAME):
            for axis_index, axis in enumerate(_AXES):
                units[("movie", index, point, axis)] = (
                    4 + index * FRAME_SIZE + point * 6 + axis_index * 2,
                    -32768, 32767)
    return units


def apply_edits(raw: bytes, edits: list[dict]) -> tuple[bytes, int]:
    """Patch movie frame vertices in place; the frame count never changes."""
    count = _count(raw)
    result = bytearray(raw)
    units = _units(count)
    seen = set()
    for edit in edits:
        identity = ("movie", int(edit.get("frame", -1)),
                    int(edit.get("point", -1)), str(edit.get("axis", "")))
        if identity in seen or identity not in units:
            raise ValueError("Invalid or duplicate field movie camera edit")
        seen.add(identity)
        offset, minimum, maximum = units[identity]
        value = int(edit.get("value"))
        if not minimum <= value <= maximum:
            raise ValueError(f"Field movie camera value must be {minimum} to {maximum}")
        struct.pack_into("<h", result, offset, value)
    if read(bytes(result))["frameCount"] != count:
        raise ValueError("Field movie camera structure changed during save")
    return bytes(result), len(edits)


def merge(vanilla: bytes, mods: list[tuple[str, bytes]], path: str
          ) -> tuple[bytes | None, list[dict], str]:
    """Merge proved movie scalars, or return a visible whole-file fallback."""
    try:
        baseline = read(vanilla)
    except ValueError as error:
        return None, [], f"vanilla {path} is unsupported: {error}"
    units = _units(baseline["frameCount"])
    claims: dict[tuple, list[tuple[str, bytes]]] = {}
    for mod_id, source in mods:
        try:
            parsed = read(source)
        except ValueError as error:
            return None, [], f"{mod_id} is not a supported {path}: {error}"
        if parsed["frameCount"] != baseline["frameCount"]:
            return None, [], f"{mod_id} changes the movie structure of {path}"
        reconstructed = bytearray(vanilla)
        for identity, (offset, _minimum, _maximum) in units.items():
            value = source[offset:offset + 2]
            if value != vanilla[offset:offset + 2]:
                claims.setdefault(identity, []).append((mod_id, value))
                reconstructed[offset:offset + 2] = value
        if bytes(reconstructed) != source:
            return None, [], f"{mod_id} contains changes outside proved movie units"
    output = bytearray(vanilla)
    conflicts = []
    for identity, values in claims.items():
        offset, _minimum, _maximum = units[identity]
        output[offset:offset + 2] = values[-1][1]
        if len(values) > 1 and len({value for _, value in values}) > 1:
            conflicts.append({"unit": f"{path}:{':'.join(map(str, identity))}",
                              "winner": values[-1][0],
                              "claimants": [mod_id for mod_id, _ in values]})
    merged = bytes(output)
    if read(merged)["frameCount"] != baseline["frameCount"]:
        return None, [], f"merged {path} changed the movie structure"
    return merged, conflicts, ""
