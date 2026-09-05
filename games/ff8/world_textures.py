"""Validated editor for the 20 fixed world-map TIM textures in texl.obj.

OpenVIII ``Core/World/texl.cs`` and Deling ``TexlFile`` both define twenty
0x12800-byte slots.  Each installed FF8 2013 slot contains one 8-bit indexed
256x256 TIM with sixteen 256-color palettes.  Replacement is deliberately
limited to a TIM with the target slot's exact layout; the unused tail of every
slot and all other slots remain byte-identical.
"""

from __future__ import annotations

import base64
from io import BytesIO
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image

from . import paths, runtime_layout
from .fs_archive import FsArchive


WORLD_PREFIX = "world"
ENTRY = "texl.obj"
DIRECT_RELATIVE = Path("world/dat/texl.obj")
BASELINE_RELATIVE = Path("world/texl.obj")
TEXTURE_COUNT = 20
SLOT_SIZE = 0x12800


def _archive_prefix() -> Path:
    return paths.GAME_ROOT / "Data" / "lang-en" / WORLD_PREFIX


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
        reference_root = paths.PROJECT_ROOT / "references" / reference_id
        candidates = (reference_root / "direct" / DIRECT_RELATIVE,
                      reference_root / DIRECT_RELATIVE)
        target = next((candidate for candidate in candidates if candidate.is_file()), None)
        return target if target is not None else baseline
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        candidates = (root / "direct" / DIRECT_RELATIVE, root / DIRECT_RELATIVE)
        return next((candidate for candidate in candidates if candidate.is_file()), baseline)
    raise ValueError(f"Unknown dataset: {dataset}")


def _tim_layout(slot: bytes | bytearray) -> dict:
    if len(slot) != SLOT_SIZE:
        raise ValueError("A texl.obj texture slot must be exactly 0x12800 bytes")
    magic, flags = struct.unpack_from("<II", slot, 0)
    if magic != 0x10:
        raise ValueError("World texture does not have a PlayStation TIM header")
    if flags != 0x09:
        raise ValueError("World texture is not the proved 8-bit paletted TIM format")
    palette_size, palette_x, palette_y, palette_width, palette_height = struct.unpack_from(
        "<IHHHH", slot, 8)
    if (palette_width != 256 or palette_height == 0
            or palette_size != 12 + palette_width * palette_height * 2):
        raise ValueError("World texture has an unsupported palette layout")
    image_header = 8 + palette_size
    if image_header + 12 > len(slot):
        raise ValueError("World texture has no complete image header")
    image_size, image_x, image_y, width_words, height = struct.unpack_from(
        "<IHHHH", slot, image_header)
    width = width_words * 2
    if width != 256 or height != 256 or image_size != 12 + width * height:
        raise ValueError("World texture is not a 256 by 256 indexed image")
    used = 8 + palette_size + image_size
    if used > len(slot):
        raise ValueError("World texture extends beyond its fixed slot")
    return {
        "flags": flags,
        "paletteSize": palette_size,
        "paletteX": palette_x,
        "paletteY": palette_y,
        "paletteWidth": palette_width,
        "paletteHeight": palette_height,
        "paletteCount": palette_height,
        "imageSize": image_size,
        "imageX": image_x,
        "imageY": image_y,
        "widthWords": width_words,
        "width": width,
        "height": height,
        "depth": 8,
        "used": used,
    }


def parse(data: bytes | bytearray) -> dict:
    if len(data) != TEXTURE_COUNT * SLOT_SIZE:
        raise ValueError("texl.obj must contain exactly twenty fixed texture slots")
    rows = []
    for texture_id in range(TEXTURE_COUNT):
        start = texture_id * SLOT_SIZE
        slot = data[start:start + SLOT_SIZE]
        layout = _tim_layout(slot)
        payload = bytes(slot[:layout["used"]])
        rows.append({
            "id": texture_id,
            "kind": "worldTexture",
            "name": f"World Texture {texture_id + 1}",
            "width": layout["width"],
            "height": layout["height"],
            "depth": layout["depth"],
            "paletteCount": layout["paletteCount"],
            "timBytes": layout["used"],
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    return {"rows": rows, "textures": rows}


def rows(dataset: str = "current") -> dict:
    source = source_path(dataset)
    return {**parse(source.read_bytes()), "source": str(source),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}


def _texture_id(value) -> int:
    try:
        texture_id = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("World texture ID must be an integer") from error
    if not 0 <= texture_id < TEXTURE_COUNT:
        raise ValueError(f"World texture ID must be 0 to {TEXTURE_COUNT - 1}")
    return texture_id


def tim_bytes(texture_id: int, dataset: str = "current") -> bytes:
    texture_id = _texture_id(texture_id)
    raw = source_path(dataset).read_bytes()
    start = texture_id * SLOT_SIZE
    slot = raw[start:start + SLOT_SIZE]
    return bytes(slot[:_tim_layout(slot)["used"]])


def _alpha(color: int) -> int:
    if color == 0:
        return 0
    return 128 if color & 0x8000 else 255


def png_bytes(texture_id: int, palette: int = 0,
              dataset: str = "current") -> bytes:
    payload = tim_bytes(texture_id, dataset)
    layout = _tim_layout(payload + bytes(SLOT_SIZE - len(payload)))
    try:
        palette = int(palette)
    except (TypeError, ValueError) as error:
        raise ValueError("Palette ID must be an integer") from error
    if not 0 <= palette < layout["paletteCount"]:
        raise ValueError(f"Palette ID must be 0 to {layout['paletteCount'] - 1}")
    palette_start = 20 + palette * 256 * 2
    colors = []
    for index in range(256):
        color, = struct.unpack_from("<H", payload, palette_start + index * 2)
        colors.append((
            round((color & 0x1F) * 255 / 31),
            round(((color >> 5) & 0x1F) * 255 / 31),
            round(((color >> 10) & 0x1F) * 255 / 31),
            _alpha(color),
        ))
    pixel_start = 8 + layout["paletteSize"] + 12
    pixels = payload[pixel_start:pixel_start + layout["width"] * layout["height"]]
    rgba = bytearray(len(pixels) * 4)
    for index, pixel in enumerate(pixels):
        rgba[index * 4:index * 4 + 4] = bytes(colors[pixel])
    image = Image.frombytes("RGBA", (layout["width"], layout["height"]), bytes(rgba))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def apply_edits(data: bytes | bytearray, edits: list[dict]) -> bytearray:
    raw = bytearray(data)
    parsed = parse(raw)
    seen = set()
    for edit in edits:
        texture_id = _texture_id(edit.get("id"))
        if texture_id in seen:
            raise ValueError(f"World texture {texture_id} was supplied more than once")
        seen.add(texture_id)
        encoded = edit.get("timBase64")
        if not isinstance(encoded, str) or not encoded:
            raise ValueError(f"World texture {texture_id} needs TIM replacement data")
        try:
            replacement = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError(f"World texture {texture_id} has invalid base64 data") from error
        start = texture_id * SLOT_SIZE
        target_slot = raw[start:start + SLOT_SIZE]
        target_layout = _tim_layout(target_slot)
        if len(replacement) != target_layout["used"]:
            raise ValueError(
                f"World texture {texture_id} TIM must be {target_layout['used']} bytes")
        replacement_slot = replacement + bytes(SLOT_SIZE - len(replacement))
        replacement_layout = _tim_layout(replacement_slot)
        compared = (
            "flags", "paletteSize", "paletteX", "paletteY", "paletteWidth",
            "paletteHeight", "imageSize", "imageX", "imageY", "widthWords",
            "width", "height", "depth", "used",
        )
        if any(replacement_layout[key] != target_layout[key] for key in compared):
            raise ValueError(
                f"World texture {texture_id} replacement must keep its exact TIM layout")
        raw[start:start + target_layout["used"]] = replacement
    parse(raw)
    return raw


def save(edits: list[dict]) -> dict:
    if not edits:
        return {"saved": 0, "file": ""}
    raw = apply_edits(source_path("current").read_bytes(), edits)
    destination = paths.DIRECT_ROOT / DIRECT_RELATIVE
    # Reuse the world editor's backup and same-directory atomic replacement.
    from .world_map import _atomic_write
    _atomic_write(destination, raw)
    return {"saved": len(edits), "file": str(destination)}

