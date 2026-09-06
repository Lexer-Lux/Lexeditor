"""Derived RDR1 map-icon fixes built from the installed PC map resources.

The player-horse marker uses native blip ordinal 334, which the audited RDR1 blip
sprite table maps to `allblips-31`.  Modern RDR1 UI mods establish the owning game
resource as `game/mapres.rpf` -> `mapblips.wtd` -> `allblips.dds`.

No Rockstar texture is stored in this repository.  At deploy time we extract the
installed atlas, replace only sprite 31 with a small recreated RDR2-style owned
horse-head silhouette, repack the unchanged-size WTD, unpack it again, and require
byte-for-byte equality with the intended decoded resource.  Every block outside
that atlas cell remains the installed game's original bytes.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import subprocess
import tempfile
import uuid
from pathlib import Path


MAPRES_ARCHIVE_RELATIVE = Path("game") / "mapres.rpf"
MAPBLIPS_NAME = "mapblips.wtd"
ALLBLIPS_NAME = "allblips"
HORSE_SPRITE_ORDINAL = 31
ATLAS_COLUMNS = 16
ATLAS_ROWS = 16
EXPECTED_ATLAS_SIZE = 2048
EXPECTED_TILE_SIZE = 128
GENERATOR_VERSION = 1

_FORMAT_BLOCK_BYTES = {"DXT1": 8, "DXT3": 16, "DXT5": 16}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _ptr(value: int) -> int:
    return value & 0x0FFFFFFF if value >> 28 in (5, 6) else value


def _rsc85_layout(packed: bytes) -> dict:
    if len(packed) < 16 or packed[:4] != b"RSC\x85":
        raise ValueError("Expected an RSC85 map texture resource")
    resource_type, flag1, flag2 = struct.unpack_from("<III", packed, 4)
    if resource_type != 10:
        raise ValueError(f"Expected mapblips.wtd resource type 10, got {resource_type}")
    total_virtual = (flag2 & 0x3FFF) << 12
    total_physical = ((flag2 >> 14) & 0x3FFF) << 12
    start_page = (flag2 >> 28) & 7
    start_size = 4096 << start_page
    page_counts = ((flag1 >> 14) & 3, (flag1 >> 8) & 63, flag1 & 255)
    page_size = 524288
    position = 0
    object_start = None
    remaining = total_virtual
    for tier, count in enumerate(page_counts):
        size = page_size >> tier
        for _ in range(count):
            while size > remaining and size > 0:
                size >>= 1
            if size == start_size and object_start is None:
                object_start = position
            position += size
            remaining -= size
    if object_start is None:
        raise ValueError("Could not resolve the RSC85 object start for mapblips.wtd")
    return {
        "type": resource_type,
        "virtual": total_virtual,
        "physical": total_physical,
        "decoded": total_virtual + total_physical,
        "objectStart": object_start,
    }


def _cstring(data: bytes, position: int) -> str:
    if position <= 0 or position >= len(data):
        raise ValueError(f"Texture name pointer is outside mapblips.wtd: 0x{position:X}")
    end = data.find(b"\x00", position, min(len(data), position + 1024))
    if end < 0:
        raise ValueError("Texture name is not NUL terminated")
    return data[position:end].decode("ascii", errors="strict")


def _canonical_name(value: str) -> str:
    value = value.replace("\\", "/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    if value.casefold().endswith(".dds"):
        value = value[:-4]
    return value.casefold()


def parse_texture_dictionary(decoded: bytes, packed_template: bytes) -> list[dict]:
    """Parse the PC/Switch-style RSC85 texture dictionary used by mapblips.wtd."""
    layout = _rsc85_layout(packed_template)
    if len(decoded) != layout["decoded"]:
        raise ValueError(
            f"Decoded mapblips.wtd length {len(decoded)} != RSC85 allocation {layout['decoded']}"
        )
    base = layout["objectStart"]
    if base + 32 > len(decoded):
        raise ValueError("mapblips.wtd texture dictionary header is truncated")
    hash_ptr = _ptr(struct.unpack_from("<I", decoded, base + 0x10)[0])
    count = struct.unpack_from("<H", decoded, base + 0x14)[0]
    count2 = struct.unpack_from("<H", decoded, base + 0x16)[0]
    list_ptr = _ptr(struct.unpack_from("<I", decoded, base + 0x18)[0])
    count3 = struct.unpack_from("<H", decoded, base + 0x1C)[0]
    count4 = struct.unpack_from("<H", decoded, base + 0x1E)[0]
    if count <= 0 or count > 4096 or count2 != count or count3 != count or count4 != count:
        raise ValueError(
            f"Unexpected mapblips.wtd texture counts: {count}/{count2}/{count3}/{count4}"
        )
    if hash_ptr + count * 4 > len(decoded) or list_ptr + count * 4 > len(decoded):
        raise ValueError("mapblips.wtd texture arrays are outside the decoded resource")

    result = []
    for index in range(count):
        pointer = _ptr(struct.unpack_from("<I", decoded, list_ptr + index * 4)[0])
        if pointer <= 0 or pointer + 0x50 > len(decoded):
            raise ValueError(f"Texture {index} structure pointer is invalid: 0x{pointer:X}")
        size = struct.unpack_from("<I", decoded, pointer + 0x14)[0]
        name_ptr = _ptr(struct.unpack_from("<I", decoded, pointer + 0x18)[0])
        width, height = struct.unpack_from("<HH", decoded, pointer + 0x20)
        format_raw = decoded[pointer + 0x24:pointer + 0x28]
        try:
            format_name = format_raw.decode("ascii").rstrip("\x00")
        except UnicodeDecodeError as error:
            raise ValueError(f"Texture {index} has a non-ASCII format tag") from error
        mipmaps = decoded[pointer + 0x2B]
        data_raw = struct.unpack_from("<I", decoded, pointer + 0x4C)[0]
        data_offset = _ptr(data_raw)
        if data_raw >> 28 == 6:
            data_offset += layout["virtual"]
        name = _cstring(decoded, name_ptr)
        result.append({
            "index": index,
            "name": name,
            "canonical": _canonical_name(name),
            "width": width,
            "height": height,
            "format": format_name,
            "mipmaps": mipmaps,
            "size": size,
            "dataOffset": data_offset,
            "structureOffset": pointer,
        })
    return result


def _point_in_polygon(x: float, y: float, points: tuple[tuple[float, float], ...]) -> bool:
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if ((yi > y) != (yj > y)) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _ellipse(x: float, y: float, cx: float, cy: float, rx: float, ry: float) -> bool:
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def _horse_mask(x: float, y: float) -> bool:
    """Recreated owned-horse head/neck silhouette, inspired by RDR2's map treatment."""
    neck = ((0.53, 0.95), (0.48, 0.58), (0.51, 0.39), (0.68, 0.46), (0.76, 0.95))
    ear_a = ((0.43, 0.22), (0.39, 0.035), (0.52, 0.18))
    ear_b = ((0.55, 0.18), (0.62, 0.025), (0.65, 0.25))
    body = (
        _ellipse(x, y, 0.49, 0.39, 0.245, 0.255)
        or _ellipse(x, y, 0.28, 0.51, 0.205, 0.13)
        or _point_in_polygon(x, y, neck)
        or _point_in_polygon(x, y, ear_a)
        or _point_in_polygon(x, y, ear_b)
    )
    # Cut a small eye and an open underside around the muzzle/neck junction.  The
    # negative space keeps the icon readable when compressed to radar scale.
    if _ellipse(x, y, 0.405, 0.35, 0.028, 0.025):
        return False
    if _ellipse(x, y, 0.25, 0.515, 0.035, 0.022):
        return False
    return body


def _tile_rgba(size: int) -> list[tuple[int, int, int, int]]:
    if size <= 0:
        raise ValueError("Horse icon tile size must be positive")
    result = []
    samples = 4 if size >= 16 else 2
    for py in range(size):
        for px in range(size):
            hits = 0
            for sy in range(samples):
                for sx in range(samples):
                    x = (px + (sx + 0.5) / samples) / size
                    y = (py + (sy + 0.5) / samples) / size
                    if _horse_mask(x, y):
                        hits += 1
            alpha = round(255 * hits / (samples * samples))
            # Warm off-white matches the restrained RDR2 owned-horse treatment
            # while remaining suitable for RDR1's HUD tinting.
            result.append((245, 242, 224, alpha))
    return result


def _rgb565(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return ((r * 31 + 127) // 255 << 11) | ((g * 63 + 127) // 255 << 5) | ((b * 31 + 127) // 255)


def _decode565(value: int) -> tuple[int, int, int]:
    return (((value >> 11) & 31) * 255 // 31,
            ((value >> 5) & 63) * 255 // 63,
            (value & 31) * 255 // 31)


def _colour_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return sum((x - y) * (x - y) for x, y in zip(a, b))


def _bc1_colour_block(pixels: list[tuple[int, int, int, int]], *, transparency: bool) -> bytes:
    opaque = [p for p in pixels if p[3] >= 32]
    if not opaque:
        return struct.pack("<HHI", 0, 0xFFFF if transparency else 0, 0xFFFFFFFF if transparency else 0)
    colors = [(p[0], p[1], p[2]) for p in opaque]
    # A deterministic luminance spread is enough for a two-tone icon and avoids
    # introducing external image/texture dependencies into the editor runtime.
    lo = min(colors, key=lambda c: c[0] * 3 + c[1] * 6 + c[2])
    hi = max(colors, key=lambda c: c[0] * 3 + c[1] * 6 + c[2])
    c_lo, c_hi = _rgb565(lo), _rgb565(hi)
    if c_lo == c_hi:
        c_lo = _rgb565((120, 118, 108))
        c_hi = _rgb565((245, 242, 224))
    if transparency:
        c0, c1 = sorted((c_lo, c_hi))
        p0, p1 = _decode565(c0), _decode565(c1)
        palette = (p0, p1, tuple((a + b) // 2 for a, b in zip(p0, p1)))
    else:
        c0, c1 = sorted((c_lo, c_hi), reverse=True)
        p0, p1 = _decode565(c0), _decode565(c1)
        palette = (p0, p1,
                   tuple((2 * a + b) // 3 for a, b in zip(p0, p1)),
                   tuple((a + 2 * b) // 3 for a, b in zip(p0, p1)))
    indices = 0
    for index, pixel in enumerate(pixels):
        if transparency and pixel[3] < 128:
            chosen = 3
        else:
            rgb = pixel[:3]
            chosen = min(range(len(palette)), key=lambda item: _colour_distance(rgb, palette[item]))
        indices |= chosen << (index * 2)
    return struct.pack("<HHI", c0, c1, indices)


def _dxt3_block(pixels: list[tuple[int, int, int, int]]) -> bytes:
    alpha = 0
    for index, pixel in enumerate(pixels):
        alpha |= ((pixel[3] * 15 + 127) // 255) << (index * 4)
    return alpha.to_bytes(8, "little") + _bc1_colour_block(pixels, transparency=False)


def _dxt5_block(pixels: list[tuple[int, int, int, int]]) -> bytes:
    a0, a1 = 255, 0
    palette = (255, 0, 218, 182, 145, 109, 72, 36)
    bits = 0
    for index, pixel in enumerate(pixels):
        chosen = min(range(8), key=lambda item: abs(pixel[3] - palette[item]))
        bits |= chosen << (index * 3)
    return bytes((a0, a1)) + bits.to_bytes(6, "little") + _bc1_colour_block(pixels, transparency=False)


def _encode_block(format_name: str, pixels: list[tuple[int, int, int, int]]) -> bytes:
    if format_name == "DXT1":
        return _bc1_colour_block(pixels, transparency=True)
    if format_name == "DXT3":
        return _dxt3_block(pixels)
    if format_name == "DXT5":
        return _dxt5_block(pixels)
    raise ValueError(f"Unsupported allblips block format: {format_name!r}")


def patch_owned_horse_sprite(decoded: bytes, texture: dict) -> tuple[bytes, dict]:
    if texture["canonical"] != ALLBLIPS_NAME:
        raise ValueError(f"Expected allblips texture, got {texture['name']!r}")
    if texture["width"] != EXPECTED_ATLAS_SIZE or texture["height"] != EXPECTED_ATLAS_SIZE:
        raise ValueError(
            f"Expected {EXPECTED_ATLAS_SIZE}x{EXPECTED_ATLAS_SIZE} allblips atlas, got "
            f"{texture['width']}x{texture['height']}"
        )
    if texture["format"] not in _FORMAT_BLOCK_BYTES:
        raise ValueError(
            f"allblips uses unsupported {texture['format']!r} data; refusing a guessed texture write"
        )
    if texture["mipmaps"] <= 0 or texture["mipmaps"] > 16:
        raise ValueError(f"Unexpected allblips mip count: {texture['mipmaps']}")
    if EXPECTED_ATLAS_SIZE // ATLAS_COLUMNS != EXPECTED_TILE_SIZE:
        raise RuntimeError("Horse sprite atlas constants are inconsistent")

    output = bytearray(decoded)
    block_bytes = _FORMAT_BLOCK_BYTES[texture["format"]]
    base = texture["dataOffset"]
    cursor = base
    changed_ranges: list[tuple[int, int]] = []
    level_reports = []
    col = HORSE_SPRITE_ORDINAL % ATLAS_COLUMNS
    row = HORSE_SPRITE_ORDINAL // ATLAS_COLUMNS
    if row >= ATLAS_ROWS:
        raise RuntimeError("Horse sprite ordinal is outside the audited allblips atlas")

    for level in range(texture["mipmaps"]):
        width = max(1, texture["width"] >> level)
        height = max(1, texture["height"] >> level)
        blocks_w = max(1, (width + 3) // 4)
        blocks_h = max(1, (height + 3) // 4)
        level_bytes = blocks_w * blocks_h * block_bytes
        if cursor + level_bytes > len(output):
            raise ValueError(f"allblips mip {level} extends outside mapblips.wtd")
        tile_w = width // ATLAS_COLUMNS
        tile_h = height // ATLAS_ROWS
        # Once an atlas cell falls below one complete 4x4 compression block, a
        # block contains multiple neighboring icons. Leave those tiny mips intact
        # rather than damage an adjacent blip.
        if (width % ATLAS_COLUMNS == 0 and height % ATLAS_ROWS == 0 and
                tile_w >= 4 and tile_h >= 4 and tile_w % 4 == 0 and tile_h % 4 == 0):
            rgba = _tile_rgba(tile_w)
            start_x = col * tile_w
            start_y = row * tile_h
            for by in range(0, tile_h, 4):
                for bx in range(0, tile_w, 4):
                    pixels = []
                    for py in range(4):
                        for px in range(4):
                            pixels.append(rgba[(by + py) * tile_w + bx + px])
                    block_x = (start_x + bx) // 4
                    block_y = (start_y + by) // 4
                    position = cursor + (block_y * blocks_w + block_x) * block_bytes
                    encoded = _encode_block(texture["format"], pixels)
                    output[position:position + block_bytes] = encoded
                    changed_ranges.append((position, position + block_bytes))
            level_reports.append({"level": level, "tile": tile_w, "patched": True})
        else:
            level_reports.append({"level": level, "tile": min(tile_w, tile_h), "patched": False})
        cursor += level_bytes

    if not changed_ranges:
        raise RuntimeError("No safe allblips mip level was available for the horse sprite")
    if texture.get("size") and cursor - base > texture["size"]:
        raise ValueError(
            f"Computed allblips mip bytes {cursor - base} exceed texture size {texture['size']}"
        )

    changed = {index for start, end in changed_ranges for index in range(start, end)}
    unexpected = [index for index, (before, after) in enumerate(zip(decoded, output))
                  if before != after and index not in changed]
    if unexpected:
        raise RuntimeError(f"Horse icon transform changed bytes outside target atlas blocks: {unexpected[:8]}")
    if bytes(output) == decoded:
        raise RuntimeError("Horse icon transform produced no byte changes")
    return bytes(output), {
        "texture": texture["name"],
        "spriteOrdinal": HORSE_SPRITE_ORDINAL,
        "grid": f"{ATLAS_COLUMNS}x{ATLAS_ROWS}",
        "cell": {"column": col, "row": row, "size": EXPECTED_TILE_SIZE},
        "format": texture["format"],
        "mipLevels": level_reports,
        "changedBlocks": len(changed_ranges),
        "changedByteCapacity": len(changed_ranges) * block_bytes,
    }


def _run(tool: Path, *args: object, timeout: int = 300) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [str(tool), *(str(value) for value in args)], cwd=str(tool.parent),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"RPF6 bridge failed ({args[0]}): {detail}")
    return result


def _archive_entry(tool: Path, archive: Path) -> str:
    result = _run(tool, "list", archive, f"*{MAPBLIPS_NAME}", timeout=120)
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("path\t") or line.startswith("LISTED\t"):
            continue
        rows.append(line.split("\t", 1)[0].replace("\\", "/"))
    matches = [row for row in rows if row.casefold().endswith("/" + MAPBLIPS_NAME) or
               row.casefold() == "root/" + MAPBLIPS_NAME]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {MAPBLIPS_NAME} in mapres.rpf, found {len(matches)}")
    return matches[0]


def ensure_owned_horse_icon_override(
        game_root: Path, tool: Path, generated_root: Path) -> dict:
    game_root = Path(game_root).resolve()
    tool = Path(tool).resolve()
    generated_root = Path(generated_root).resolve()
    archive = (game_root / MAPRES_ARCHIVE_RELATIVE).resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"Missing RDR map resource archive: {archive}")
    if not tool.is_file():
        raise FileNotFoundError(f"Missing RPF6 bridge: {tool}")
    with archive.open("rb") as stream:
        if stream.read(4) != b"RPF6":
            raise ValueError(f"Expected an RPF6 map resource archive: {archive}")

    source_stat = archive.stat()
    source_fast = {"path": str(archive), "size": source_stat.st_size,
                   "mtimeNs": source_stat.st_mtime_ns}
    manifest = generated_root / ".owned-horse-icon.json"
    try:
        current = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        current = {}
    output_text = current.get("output")
    output = Path(output_text) if isinstance(output_text, str) and output_text else None
    if (current.get("version") == GENERATOR_VERSION and current.get("source") == source_fast and
            output is not None and output.is_file() and
            current.get("outputSha256") == _sha256_file(output)):
        return {"prepared": True, "cached": True, "output": str(output),
                "report": current.get("report", {})}

    before_hash = _sha256_file(archive)
    entry = _archive_entry(tool, archive)
    relative = entry[5:] if entry.casefold().startswith("root/") else entry
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-horse-icon-") as temp_name:
        temp = Path(temp_name)
        packed_root = temp / "packed"
        _run(tool, "extract", archive, packed_root, f"*{MAPBLIPS_NAME}", timeout=180)
        candidates = [path for path in packed_root.rglob(MAPBLIPS_NAME) if path.is_file()]
        if len(candidates) != 1:
            raise RuntimeError(f"RPF6 extraction returned {len(candidates)} {MAPBLIPS_NAME} files")
        template = candidates[0]
        packed = template.read_bytes()
        decoded = temp / "mapblips.decoded"
        _run(tool, "resource-unpack", template, decoded, timeout=120)
        decoded_bytes = decoded.read_bytes()
        textures = parse_texture_dictionary(decoded_bytes, packed)
        matches = [row for row in textures if row["canonical"] == ALLBLIPS_NAME]
        if len(matches) != 1:
            names = ", ".join(row["name"] for row in textures[:20])
            raise RuntimeError(
                f"Expected one allblips texture in mapblips.wtd, found {len(matches)}; textures: {names}"
            )
        patched, report = patch_owned_horse_sprite(decoded_bytes, matches[0])
        decoded.write_bytes(patched)
        candidate = temp / MAPBLIPS_NAME
        _run(tool, "resource-pack", template, decoded, candidate, timeout=180)
        verified = temp / "verified.decoded"
        _run(tool, "resource-unpack", candidate, verified, timeout=120)
        if verified.read_bytes() != patched:
            raise RuntimeError("Repacked mapblips.wtd did not decode to the intended horse-icon bytes")
        payload = candidate.read_bytes()

    after_hash = _sha256_file(archive)
    if after_hash != before_hash:
        raise RuntimeError("Installed mapres.rpf changed while preparing the horse icon override")
    output = generated_root / Path(relative)
    _atomic_bytes(output, payload)
    output_hash = _sha256_file(output)
    manifest_payload = {
        "version": GENERATOR_VERSION,
        "source": source_fast,
        "sourceSha256": before_hash,
        "archiveEntry": entry,
        "output": str(output),
        "outputSha256": output_hash,
        "report": report,
        "visual": "recreated RDR2-style owned horse head; no RDR2 texture bytes bundled",
    }
    _atomic_bytes(manifest, (json.dumps(manifest_payload, indent=2) + "\n").encode("utf-8"))
    return {"prepared": True, "cached": False, "output": str(output), "report": report}
