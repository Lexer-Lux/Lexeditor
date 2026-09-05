"""Strict reader and writer for FF8 field ``.id`` walkmeshes.

The layout is independently documented by Deling and OpenVIII: a u32 triangle
count, three eight-byte signed vertices per triangle, then three signed i16
adjacent-triangle indexes per triangle.  The fourth vertex word is unresolved
and is therefore preserved but never edited.
"""

from __future__ import annotations

import struct


HEADER_SIZE = 4
VERTICES_PER_TRIANGLE = 3
VERTEX_SIZE = 8
ACCESS_SIZE = 2


def _layout(data: bytes) -> tuple[int, int, int]:
    if len(data) < HEADER_SIZE:
        raise ValueError("Field walkmesh is too small")
    count = struct.unpack_from("<I", data, 0)[0]
    if count > 100_000:
        raise ValueError("Field walkmesh triangle count is unsafe")
    vertex_bytes = count * VERTICES_PER_TRIANGLE * VERTEX_SIZE
    access_offset = HEADER_SIZE + vertex_bytes
    expected = access_offset + count * VERTICES_PER_TRIANGLE * ACCESS_SIZE
    trailing = len(data) - expected
    if trailing not in (0, 2):
        raise ValueError(
            f"Field walkmesh has {len(data)} bytes; expected {expected} or {expected + 2} "
            f"for {count} triangles"
        )
    return count, access_offset, trailing


def read(data: bytes) -> dict:
    """Decode every triangle without assigning meaning to the reserved word."""
    count, access_offset, trailing = _layout(data)
    triangles = []
    for triangle_id in range(count):
        vertices = []
        vertex_base = HEADER_SIZE + triangle_id * VERTICES_PER_TRIANGLE * VERTEX_SIZE
        access_base = access_offset + triangle_id * VERTICES_PER_TRIANGLE * ACCESS_SIZE
        for vertex_id in range(VERTICES_PER_TRIANGLE):
            start = vertex_base + vertex_id * VERTEX_SIZE
            x, y, z, reserved = struct.unpack_from("<hhhh", data, start)
            adjacent = struct.unpack_from("<h", data, access_base + vertex_id * ACCESS_SIZE)[0]
            if adjacent < -1 or adjacent >= count:
                raise ValueError(
                    f"Triangle {triangle_id} edge {vertex_id} has invalid adjacency {adjacent}"
                )
            vertices.append({
                "id": vertex_id, "x": x, "y": y, "z": z,
                "reserved": reserved, "adjacent": adjacent,
            })
        triangles.append({"id": triangle_id, "vertices": vertices})
    return {"triangleCount": count, "triangles": triangles,
            "trailingUnknown": (struct.unpack_from("<h", data, len(data) - 2)[0]
                                if trailing else None)}


def apply_edits(data: bytes, edits: list[dict]) -> tuple[bytes, int]:
    """Patch proved coordinates and adjacency indexes in the original bytes."""
    count, access_offset, _ = _layout(data)
    result = bytearray(data)
    changed = 0
    seen: set[tuple[int, int]] = set()
    allowed = {"triangle", "vertex", "x", "y", "z", "adjacent"}
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) - allowed:
            raise ValueError("Field walkmesh edit has unsupported fields")
        if "triangle" not in edit or "vertex" not in edit:
            raise ValueError("Field walkmesh edit needs triangle and vertex")
        triangle_id = int(edit["triangle"])
        vertex_id = int(edit["vertex"])
        if not 0 <= triangle_id < count or not 0 <= vertex_id < VERTICES_PER_TRIANGLE:
            raise ValueError("Field walkmesh edit identifies an invalid vertex")
        key = (triangle_id, vertex_id)
        if key in seen:
            raise ValueError("Field walkmesh edit repeats a vertex")
        seen.add(key)
        vertex_start = (HEADER_SIZE +
                        (triangle_id * VERTICES_PER_TRIANGLE + vertex_id) * VERTEX_SIZE)
        access_start = (access_offset +
                        (triangle_id * VERTICES_PER_TRIANGLE + vertex_id) * ACCESS_SIZE)
        for field, offset in (("x", 0), ("y", 2), ("z", 4)):
            if field not in edit:
                continue
            value = int(edit[field])
            if not -32768 <= value <= 32767:
                raise ValueError(f"Field walkmesh {field} must be a signed 16-bit value")
            encoded = struct.pack("<h", value)
            start = vertex_start + offset
            if result[start:start + 2] != encoded:
                result[start:start + 2] = encoded
                changed += 1
        if "adjacent" in edit:
            adjacent = int(edit["adjacent"])
            if adjacent < -1 or adjacent >= count:
                raise ValueError("Field walkmesh adjacency must be -1 or an existing triangle")
            encoded = struct.pack("<h", adjacent)
            if result[access_start:access_start + 2] != encoded:
                result[access_start:access_start + 2] = encoded
                changed += 1
    read(bytes(result))
    return bytes(result), changed


def merge(vanilla: bytes, mods: list[tuple[str, bytes]], path: str
          ) -> tuple[bytes | None, list[dict], str]:
    """Merge proved vertex fields or return a visible whole-file fallback."""
    try:
        baseline = read(vanilla)
    except ValueError as error:
        return None, [], f"vanilla {path} is unsupported: {error}"
    units: dict[str, tuple[int, int]] = {}
    count, access_offset, _ = _layout(vanilla)
    for triangle in range(count):
        for vertex in range(VERTICES_PER_TRIANGLE):
            vertex_start = (HEADER_SIZE +
                            (triangle * VERTICES_PER_TRIANGLE + vertex) * VERTEX_SIZE)
            for field, offset in (("x", 0), ("y", 2), ("z", 4)):
                units[f"triangle:{triangle}:vertex:{vertex}:{field}"] = (vertex_start + offset, 2)
            units[f"triangle:{triangle}:edge:{vertex}:adjacent"] = (
                access_offset + (triangle * VERTICES_PER_TRIANGLE + vertex) * ACCESS_SIZE, 2)

    claims: dict[str, list[tuple[str, bytes]]] = {}
    for mod_id, source in mods:
        if len(source) != len(vanilla):
            return None, [], f"{mod_id} changes the size of {path}"
        try:
            parsed = read(source)
        except ValueError as error:
            return None, [], f"{mod_id} is not a supported {path}: {error}"
        if (parsed["triangleCount"] != baseline["triangleCount"] or
                parsed["trailingUnknown"] != baseline["trailingUnknown"]):
            return None, [], f"{mod_id} changes the proved structure of {path}"
        reconstructed = bytearray(vanilla)
        for label, (start, size) in units.items():
            value = source[start:start + size]
            if value != vanilla[start:start + size]:
                claims.setdefault(label, []).append((mod_id, value))
                reconstructed[start:start + size] = value
        if bytes(reconstructed) != source:
            return None, [], f"{mod_id} contains changes outside proved walkmesh units"

    output = bytearray(vanilla)
    conflicts = []
    for label, values in claims.items():
        start, size = units[label]
        output[start:start + size] = values[-1][1]
        if len(values) > 1 and len({value for _, value in values}) > 1:
            conflicts.append({"unit": f"{path}:{label}", "winner": values[-1][0],
                              "claimants": [mod_id for mod_id, _ in values]})
    read(bytes(output))
    return bytes(output), conflicts, ""
