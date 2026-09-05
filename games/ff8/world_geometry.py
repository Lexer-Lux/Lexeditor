"""Strict FF8 ``wmx.obj`` parser and byte-preserving segment editor.

Format evidence is Deling's GPLv3 ``game/worldmap/WmxFile.cpp``.  A segment is
0x9000 bytes, starts with a group ID and sixteen block offsets, and contains
fixed block headers, polygon records, vertices, and normals.  Lexeditor patches
only the segment group ID.  Polygon topology and every unknown byte stay
opaque until each additional field has its own proved editor contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

from . import paths, runtime_layout
from .fs_archive import FsArchive


ENTRY = "wmx.obj"
DIRECT_RELATIVE = Path("world/dat/wmx.obj")
BASELINE_RELATIVE = Path("world/wmx.obj")
SEGMENT_SIZE = 0x9000
BASE_SEGMENT_COUNT = 32 * 24
BLOCK_COUNT = 16
POLYGON_SIZE = 16
VECTOR_SIZE = 8


def _archive_prefix() -> Path:
    return paths.GAME_ROOT / "Data" / "lang-en" / "world"


def _fingerprint(prefix: Path) -> dict:
    return {
        suffix: {
            "size": prefix.with_suffix(suffix).stat().st_size,
            "mtimeNs": prefix.with_suffix(suffix).stat().st_mtime_ns,
        }
        for suffix in (".fs", ".fi", ".fl")
    }


def ensure_baseline() -> Path:
    destination = paths.BASELINE_ROOT / BASELINE_RELATIVE
    metadata = destination.with_suffix(destination.suffix + ".source.json")
    prefix = _archive_prefix()
    current = _fingerprint(prefix)
    if destination.is_file() and metadata.is_file():
        try:
            if json.loads(metadata.read_text(encoding="utf-8")) == current:
                parse(destination.read_bytes())
                return destination
        except (OSError, ValueError, TypeError):
            pass
    archive = FsArchive(prefix)
    data = archive.extract(archive.find(ENTRY))
    parse(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    metadata.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return destination


def source_path(dataset: str = "current") -> Path:
    baseline = ensure_baseline()
    if dataset == "vanilla":
        return baseline
    if dataset == "current":
        override = paths.DIRECT_ROOT / DIRECT_RELATIVE
        return override if override.is_file() else baseline
    if dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        root = paths.PROJECT_ROOT / "references" / reference_id
        candidates = (root / "direct" / DIRECT_RELATIVE, root / DIRECT_RELATIVE)
        target = next((candidate for candidate in candidates if candidate.is_file()), None)
        return target if target is not None else baseline
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        candidates = (root / "direct" / DIRECT_RELATIVE, root / DIRECT_RELATIVE)
        return next((candidate for candidate in candidates if candidate.is_file()), baseline)
    raise ValueError(f"Unknown dataset: {dataset}")


def _segment(data: bytes | bytearray, segment_id: int) -> dict:
    start = segment_id * SEGMENT_SIZE
    segment = data[start:start + SEGMENT_SIZE]
    if len(segment) != SEGMENT_SIZE:
        raise ValueError(f"wmx.obj segment {segment_id} is incomplete")
    group_id = struct.unpack_from("<I", segment, 0)[0]
    offsets = struct.unpack_from(f"<{BLOCK_COUNT}I", segment, 4)
    if any(offset % 4 or offset < 4 + BLOCK_COUNT * 4
           or offset + 4 > SEGMENT_SIZE for offset in offsets):
        raise ValueError(f"wmx.obj segment {segment_id} has an invalid block table")
    blocks = []
    polygon_total = 0
    ground_types: set[int] = set()
    for block_id, offset in enumerate(offsets):
        polygon_count, vertex_count, normal_count, padding = struct.unpack_from(
            "<BBBB", segment, offset)
        polygon_start = offset + 4
        vertex_start = polygon_start + polygon_count * POLYGON_SIZE
        normal_start = vertex_start + vertex_count * VECTOR_SIZE
        end = normal_start + normal_count * VECTOR_SIZE
        if end > SEGMENT_SIZE:
            raise ValueError(
                f"wmx.obj segment {segment_id} block {block_id} exceeds its segment")
        for polygon_id in range(polygon_count):
            polygon_offset = polygon_start + polygon_id * POLYGON_SIZE
            vertex_indices = segment[polygon_offset:polygon_offset + 3]
            normal_indices = segment[polygon_offset + 3:polygon_offset + 6]
            if any(index >= vertex_count for index in vertex_indices):
                raise ValueError(
                    f"wmx.obj segment {segment_id} block {block_id} has a bad vertex index")
            if normal_count and any(index >= normal_count for index in normal_indices):
                raise ValueError(
                    f"wmx.obj segment {segment_id} block {block_id} has a bad normal index")
            ground_types.add(segment[polygon_offset + 13])
        blocks.append({
            "id": block_id,
            "polygonCount": polygon_count,
            "vertexCount": vertex_count,
            "normalCount": normal_count,
            "headerPadding": padding,
        })
        polygon_total += polygon_count
    return {
        "id": segment_id,
        "kind": "worldSegment",
        "name": f"World segment {segment_id}",
        "x": segment_id % 32,
        "y": segment_id // 32,
        "groupId": group_id,
        "polygonCount": polygon_total,
        "groundTypes": sorted(ground_types),
        "blocks": blocks,
    }


def parse(data: bytes | bytearray) -> dict:
    if not data or len(data) % SEGMENT_SIZE:
        raise ValueError("wmx.obj is not made of complete 0x9000-byte segments")
    segment_count = len(data) // SEGMENT_SIZE
    if segment_count < BASE_SEGMENT_COUNT:
        raise ValueError("wmx.obj does not contain the 32 by 24 base world map")
    segments = [_segment(data, segment_id) for segment_id in range(segment_count)]
    return {
        "segmentCount": segment_count,
        "baseSegmentCount": BASE_SEGMENT_COUNT,
        "width": 32,
        "height": 24,
        "segments": segments,
    }


def rows(dataset: str = "current") -> dict:
    source = source_path(dataset)
    raw = source.read_bytes()
    parsed = parse(raw)
    return {
        **parsed,
        "source": str(source),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be {minimum} to {maximum}")
    return number


def apply_edits(data: bytes | bytearray, edits: list[dict]) -> bytearray:
    raw = bytearray(data)
    parsed = parse(raw)
    seen = set()
    for edit in edits:
        segment_id = _bounded(
            edit.get("id"), 0, parsed["segmentCount"] - 1, "World segment ID")
        if segment_id in seen:
            raise ValueError(f"Duplicate world segment edit: {segment_id}")
        seen.add(segment_id)
        group_id = _bounded(edit.get("groupId"), 0, 2 ** 32 - 1,
                            "World segment group ID")
        struct.pack_into("<I", raw, segment_id * SEGMENT_SIZE, group_id)
    parse(raw)
    return raw


def save(edits: list[dict]) -> dict:
    if not edits:
        return {"saved": 0, "file": ""}
    raw = apply_edits(source_path("current").read_bytes(), edits)
    destination = paths.DIRECT_ROOT / DIRECT_RELATIVE
    from .world_map import _atomic_write
    _atomic_write(destination, raw)
    return {"saved": len(edits), "file": str(destination)}


def minimap_png(dataset: str = "current") -> bytes:
    """Decode Deling's ``Map::MiniMap`` TIM from wmset section 38.

    Deling stores nine low-resolution textures first.  The third special
    texture is therefore pointer 11 in the section's 36-entry table.
    """
    from io import BytesIO
    from PIL import Image
    from . import world_map

    raw = world_map.source_path(dataset).read_bytes()
    pointers = world_map._pointers(raw)
    section = raw[pointers[37]:pointers[38]]
    offsets = list(struct.unpack_from("<36I", section, 0)) + [len(section)]
    payload = section[offsets[11]:offsets[12]]
    if len(payload) < 32 or struct.unpack_from("<I", payload, 0)[0] != 0x10:
        raise ValueError("The FF8 world minimap TIM is invalid")
    flags = struct.unpack_from("<I", payload, 4)[0]
    if flags != 0x08:
        raise ValueError("The FF8 world minimap is not the proved 4-bit TIM")
    palette_size, _px, _py, palette_width, palette_height = struct.unpack_from(
        "<IHHHH", payload, 8)
    if palette_width != 16 or palette_height < 1:
        raise ValueError("The FF8 world minimap has an invalid palette")
    image_header = 8 + palette_size
    image_size, _ix, _iy, width_words, height = struct.unpack_from(
        "<IHHHH", payload, image_header)
    width = width_words * 4
    if image_size != 12 + width_words * 2 * height:
        raise ValueError("The FF8 world minimap has an invalid image payload")
    colors = []
    for color_id in range(16):
        color = struct.unpack_from("<H", payload, 20 + color_id * 2)[0]
        colors.append((
            round((color & 0x1F) * 255 / 31),
            round(((color >> 5) & 0x1F) * 255 / 31),
            round(((color >> 10) & 0x1F) * 255 / 31),
            0 if color == 0 else 255,
        ))
    packed = payload[image_header + 12:image_header + image_size]
    rgba = bytearray(width * height * 4)
    for byte_id, value in enumerate(packed):
        for nibble, color_id in enumerate((value & 0x0F, value >> 4)):
            target = (byte_id * 2 + nibble) * 4
            rgba[target:target + 4] = bytes(colors[color_id])
    image = Image.frombytes("RGBA", (width, height), bytes(rgba))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
