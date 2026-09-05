"""Render FF8 menu icons from the user's privately extracted game assets."""

from __future__ import annotations

import json
from pathlib import Path
import struct

from PIL import Image

from . import paths


ICON_NAMES = {
    0: "Menu pointer",
    216: "Junction ability", 217: "Command ability", 218: "Stat Boost ability",
    219: "Character ability", 220: "Party ability", 221: "GF ability",
    222: "Menu ability",
    223: "Character item", 224: "GF item", 225: "Full restore item",
    226: "Battle item", 227: "Ammo", 228: "Magazine", 229: "Special item",
    288: "Fire", 289: "Ice", 290: "Thunder", 291: "Earth",
    292: "Poison Element", 293: "Wind", 294: "Water", 295: "Holy",
    272: "Death", 273: "Poison", 274: "Petrify", 275: "Darkness",
    276: "Silence", 277: "Berserk", 278: "Zombie", 279: "Sleep",
    280: "Slow", 281: "Stop", 282: "Curse", 283: "Confuse", 284: "Drain",
}
ELEMENT_ICON_IDS = {
    "Fire": 288, "Ice": 289, "Thunder": 290, "Earth": 291,
    "Poison": 292, "Wind": 293, "Water": 294, "Holy": 295,
}
STATUS_ICON_IDS = {name: icon_id for icon_id, name in ICON_NAMES.items() if 272 <= icon_id <= 284}

# FF8_EN.exe byte_B88024 maps the first byte of each four-byte mitem.bin row
# to one of the seven item-type icons at icon.sp1 IDs 223 through 229.
ITEM_TYPE_ICON_TABLE = (
    0, 0, 0, 1, 1, 1, 2, 3, 4, 5, 6, 1,
    3, 3, 3, 3, 6, 1, 1, 6, 6, 0, 0, 0,
)
ITEM_TYPE_ICON_FIRST = 223

PORTRAIT_SHEETS = {
    "characters": {"offset": 0x013000, "size": 0x06800, "count": 11},
    "gfs": {"offset": 0x019800, "size": 0x06800, "count": 16},
}
PORTRAIT_SIZE = (32, 48)


def generated_root(data_root: Path | None = None) -> Path:
    return (data_root or paths.DATA_ROOT) / "generated" / "icons"


def portrait_root(data_root: Path | None = None) -> Path:
    return (data_root or paths.DATA_ROOT) / "generated" / "portraits"


def _psx_alpha(color: int) -> int:
    if color == 0:
        return 0
    return 128 if color & 0x8000 else 255


def _tim_image(raw: bytes) -> Image.Image:
    """Decode the 8-bit TIM format used by the two mngrp face sheets."""
    if len(raw) < 20 or struct.unpack_from("<I", raw, 0)[0] != 0x10:
        raise ValueError("The FF8 portrait section is not a TIM image")
    flags = struct.unpack_from("<I", raw, 4)[0]
    if flags & 0x3 != 1 or not flags & 0x8:
        raise ValueError("The FF8 portrait TIM is not an 8-bit paletted image")
    clut_size = struct.unpack_from("<I", raw, 8)[0]
    clut_width, clut_height = struct.unpack_from("<HH", raw, 16)
    if clut_width != 256 or clut_height < 1:
        raise ValueError("The FF8 portrait TIM has an unsupported palette")
    palette = []
    for index in range(clut_width):
        color = struct.unpack_from("<H", raw, 20 + index * 2)[0]
        palette.append((
            round((color & 0x1F) * 255 / 31),
            round(((color >> 5) & 0x1F) * 255 / 31),
            round(((color >> 10) & 0x1F) * 255 / 31),
            _psx_alpha(color),
        ))
    image_header = 8 + clut_size
    width_words, height = struct.unpack_from("<HH", raw, image_header + 8)
    width = width_words * 2
    pixel_start = image_header + 12
    pixels = raw[pixel_start:pixel_start + width * height]
    if (width, height) != (256, 96) or len(pixels) != width * height:
        raise ValueError("The FF8 portrait TIM has unexpected dimensions")
    rgba = bytearray(width * height * 4)
    for index, pixel in enumerate(pixels):
        rgba[index * 4:index * 4 + 4] = bytes(palette[pixel])
    return Image.frombytes("RGBA", (width, height), bytes(rgba))


def ensure_portraits(data_root: Path | None = None) -> dict:
    """Generate portrait cells from the user's private mngrp.bin baseline."""
    root = portrait_root(data_root)
    manifest_path = root / "manifest.json"
    source = paths.BASELINE_ROOT / "menu" / "mngrp.bin"
    if not source.is_file():
        return {"portraits": {}, "available": False}
    fingerprint = {"size": source.stat().st_size, "mtimeNs": source.stat().st_mtime_ns}
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if existing.get("source") == fingerprint and all(
                    (root / filename).is_file()
                    for group in existing.get("portraits", {}).values()
                    for filename in group.values()):
                return {**existing, "available": True}
        except (OSError, ValueError, TypeError):
            pass
    raw = source.read_bytes()
    root.mkdir(parents=True, exist_ok=True)
    portraits: dict[str, dict[str, str]] = {}
    for kind, section in PORTRAIT_SHEETS.items():
        sheet = _tim_image(raw[section["offset"]:section["offset"] + section["size"]])
        portraits[kind] = {}
        for record_id in range(section["count"]):
            x = (record_id % 8) * PORTRAIT_SIZE[0]
            y = (record_id // 8) * PORTRAIT_SIZE[1]
            filename = f"{kind}-{record_id}.png"
            sheet.crop((x, y, x + PORTRAIT_SIZE[0], y + PORTRAIT_SIZE[1])).save(root / filename)
            portraits[kind][str(record_id)] = filename
    manifest = {"source": fingerprint, "portraits": portraits}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {**manifest, "available": True}


def portrait_path(kind: str, record_id: int) -> Path | None:
    manifest = ensure_portraits()
    filename = manifest.get("portraits", {}).get(kind, {}).get(str(record_id))
    target = portrait_root() / filename if filename else None
    return target if target and target.is_file() else None


def _tex(raw: bytes) -> tuple[int, int, list[list[tuple[int, int, int, int]]], bytes]:
    if len(raw) < 240:
        raise ValueError("icon.tex is too short")
    palettes, entries, _bpp, width, height = struct.unpack_from("<IIIII", raw, 0x30)
    palette_end = 240 + palettes * entries * 4
    pixels = raw[palette_end:palette_end + width * height]
    if len(pixels) != width * height:
        raise ValueError("icon.tex has an incomplete pixel block")
    decoded = []
    for palette in range(palettes):
        colors = []
        base = 240 + palette * entries * 4
        for index in range(entries):
            blue, green, red, alpha = raw[base + index * 4:base + index * 4 + 4]
            colors.append((red, green, blue, 255 if alpha else 0))
        decoded.append(colors)
    return width, height, decoded, pixels


def _atlas_image(width: int, height: int, pixels: bytes,
                 palette: list[tuple[int, int, int, int]]) -> Image.Image:
    rgba = bytearray(width * height * 4)
    for index, pixel in enumerate(pixels):
        color = palette[pixel & 0x0F] if (pixel & 0x0F) < len(palette) else (0, 0, 0, 0)
        rgba[index * 4:index * 4 + 4] = bytes(color)
    return Image.frombytes("RGBA", (width, height), bytes(rgba))


def _render_icon(icon_id: int, sp1: bytes, tex: bytes) -> Image.Image | None:
    count = struct.unpack_from("<I", sp1, 0)[0]
    if not 0 <= icon_id < count:
        return None
    offset, quad_count = struct.unpack_from("<HH", sp1, 4 + icon_id * 4)
    quads = []
    for quad_index in range(quad_count):
        position = offset + quad_index * 8
        dword, = struct.unpack_from("<I", sp1, position)
        quad_width, dx, quad_height, dy = struct.unpack_from("<BbBb", sp1, position + 4)
        quads.append({
            "u": dword & 0xFF, "v": (dword >> 8) & 0xFF,
            "palette": ((dword >> 16) & 0x7FF) >> 6,
            "semi": bool((dword >> 27) & 1),
            "width": quad_width, "height": quad_height, "dx": dx, "dy": dy,
        })
    visible = [quad for quad in quads if quad["width"] and quad["height"]]
    if not visible:
        return None
    min_x = min(quad["dx"] for quad in visible)
    min_y = min(quad["dy"] for quad in visible)
    max_x = max(quad["dx"] + quad["width"] for quad in visible)
    max_y = max(quad["dy"] + quad["height"] for quad in visible)
    tex_width, tex_height, palettes, pixels = _tex(tex)
    canvas = Image.new("RGBA", (max_x - min_x, max_y - min_y), (0, 0, 0, 0))
    atlases: dict[int, Image.Image] = {}
    for quad in visible:
        palette_index = min(quad["palette"], len(palettes) - 1)
        atlas = atlases.setdefault(
            palette_index, _atlas_image(tex_width, tex_height, pixels, palettes[palette_index]))
        crop = atlas.crop((quad["u"], quad["v"], quad["u"] + quad["width"], quad["v"] + quad["height"]))
        if quad["semi"]:
            crop.putalpha(crop.getchannel("A").point(lambda alpha: min(alpha, 128)))
        canvas.alpha_composite(crop, (quad["dx"] - min_x, quad["dy"] - min_y))
    return canvas


def ensure_icons(data_root: Path | None = None) -> dict:
    """Create small PNGs from icon.sp1 and icon.tex. Never copy game assets into the app."""
    root = generated_root(data_root)
    manifest_path = root / "manifest.json"
    source_sp1 = paths.BASELINE_ROOT / "menu" / "icon.sp1"
    source_tex = paths.BASELINE_ROOT / "menu" / "icon.tex"
    if not source_sp1.is_file() or not source_tex.is_file():
        return {"icons": {}, "available": False}
    fingerprint = {
        "sp1Size": source_sp1.stat().st_size,
        "sp1MtimeNs": source_sp1.stat().st_mtime_ns,
        "texSize": source_tex.stat().st_size,
        "texMtimeNs": source_tex.stat().st_mtime_ns,
    }
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected = {str(icon_id) for icon_id in ICON_NAMES}
            if existing.get("source") == fingerprint and expected.issubset(
                    existing.get("icons", {})) and all(
                    (root / filename).is_file() for filename in existing.get("icons", {}).values()):
                return {**existing, "available": True}
        except (OSError, ValueError, TypeError):
            pass
    root.mkdir(parents=True, exist_ok=True)
    sp1, tex = source_sp1.read_bytes(), source_tex.read_bytes()
    icons = {}
    for icon_id, name in ICON_NAMES.items():
        image = _render_icon(icon_id, sp1, tex)
        if image is None:
            continue
        filename = f"{icon_id}.png"
        image.save(root / filename)
        icons[str(icon_id)] = filename
    manifest = {"source": fingerprint, "icons": icons, "names": ICON_NAMES}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {**manifest, "available": True}


def icon_path(icon_id: int) -> Path | None:
    manifest = ensure_icons()
    filename = manifest.get("icons", {}).get(str(icon_id))
    target = generated_root() / filename if filename else None
    return target if target and target.is_file() else None


def item_icon_id(item_id: int) -> int | None:
    """Resolve one item's native menu-type icon from the active mitem.bin."""
    source = paths.DIRECT_ROOT / "menu" / "mitem.bin"
    if not source.is_file():
        source = paths.BASELINE_ROOT / "menu" / "mitem.bin"
    try:
        raw = source.read_bytes()
    except OSError:
        return None
    offset = int(item_id) * 4
    if offset < 0 or offset >= len(raw):
        return None
    type_id = raw[offset]
    if not 0 <= type_id < len(ITEM_TYPE_ICON_TABLE):
        return None
    return ITEM_TYPE_ICON_FIRST + ITEM_TYPE_ICON_TABLE[type_id]


# ff8-decomp card.c::getAbilityCategory and menujnc2.c::renderGfCompatGrid:
# the renderer uses category + 0xD8. IDs are global, not section-local.
ABILITY_TYPES = ("Junction", "Command", "Stat Boost", "Character", "Party", "GF", "Menu")
ABILITY_LIMITS = (20, 39, 58, 78, 83, 92, 116)

def ability_identity(ability_id: int) -> dict:
    value = int(ability_id)
    if 0 <= value < ABILITY_LIMITS[-1]:
        category = next(i for i, limit in enumerate(ABILITY_LIMITS) if value < limit)
        return {"abilityId": value, "abilityType": ABILITY_TYPES[category], "iconId": 216 + category}
    return {"abilityId": value, "abilityType": "Unknown", "iconId": None}
