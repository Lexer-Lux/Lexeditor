"""Build a private web font from the player's installed FF8 menu font."""

from __future__ import annotations

from pathlib import Path
import struct

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from . import paths


FONT_NAME = "FF8Menu"
FONT_PATH = paths.DATA_ROOT / "generated" / "ff8-menu.ttf"
FONT_REVISION_PATH = paths.DATA_ROOT / "generated" / "ff8-menu.revision"
FONT_REVISION = "4"
GLYPH_SIZE = 12
ATLAS_COLUMNS = 21
FIRST_CODE = 0x20
SCALE = 80
UNITS_PER_EM = 1024

# FF8 does not store its menu font in ASCII order. These are the printable
# single-byte cells used by Lexeditor. Missing characters use the system
# fallback font instead of showing the wrong atlas cell.
CHARACTERS = (
    " 0123456789%/:!?…+-=*&「」()·.,~”“‘#$'_"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
)


def _font_sources() -> tuple[Path, Path]:
    menu = paths.BASELINE_ROOT / "menu"
    return menu / "sysfnt.tex", menu / "sysfnt.tdw"


def _read_texture(path: Path) -> tuple[int, int, bytes, list[int]]:
    data = path.read_bytes()
    if len(data) < 240:
        raise ValueError("FF8 sysfnt.TEX is incomplete")
    palettes = struct.unpack_from("<I", data, 0x30)[0]
    entries = struct.unpack_from("<I", data, 0x34)[0]
    width = struct.unpack_from("<I", data, 0x3C)[0]
    height = struct.unpack_from("<I", data, 0x40)[0]
    pixel_offset = 240 + palettes * entries * 4
    pixels = data[pixel_offset:pixel_offset + width * height]
    if len(pixels) != width * height:
        raise ValueError("FF8 sysfnt.TEX pixel data is incomplete")
    # Palette 7 is the game's normal white menu text. Indices 2 and 3 are
    # the visible glyph; index 1 is its baked dark shadow.
    palette_offset = 240 + min(7, palettes - 1) * entries * 4
    visible = []
    for index in range(entries):
        b, g, r, alpha = data[palette_offset + index * 4:palette_offset + index * 4 + 4]
        visible.append(alpha and max(r, g, b) >= 128)
    return width, height, pixels, visible


def _read_widths(path: Path) -> list[int]:
    packed = path.read_bytes()[8:]
    widths: list[int] = []
    for glyph in range(len(packed) * 2):
        value = packed[glyph >> 1]
        widths.append((value >> 4) & 0xF if glyph & 1 else value & 0xF)
    return widths


def _glyph(width: int, pixels: bytes, visible: list[int], code: int):
    pen = TTGlyphPen(None)
    cell = code - FIRST_CODE
    left = GLYPH_SIZE * (cell % ATLAS_COLUMNS)
    top = GLYPH_SIZE * (cell // ATLAS_COLUMNS)
    for row in range(GLYPH_SIZE):
        column = 0
        while column < GLYPH_SIZE:
            while column < GLYPH_SIZE and not visible[pixels[(top + row) * width + left + column] & 0x0F]:
                column += 1
            start = column
            while column < GLYPH_SIZE and visible[pixels[(top + row) * width + left + column] & 0x0F]:
                column += 1
            if start == column:
                continue
            x0, x1 = start * SCALE, column * SCALE
            # FF8's renderer positions this atlas below a normal TrueType
            # baseline. Apply the correction once to the generated face so
            # tabs, tables, labels, inputs, and help marks share one metric.
            y0, y1 = ((GLYPH_SIZE - row - 1) * SCALE - 211,
                      (GLYPH_SIZE - row) * SCALE - 211)
            pen.moveTo((x0, y0))
            pen.lineTo((x1, y0))
            pen.lineTo((x1, y1))
            pen.lineTo((x0, y1))
            pen.closePath()
    return pen.glyph()


def ensure_font() -> Path:
    """Return a generated TTF. The source atlas stays in the private cache."""
    texture, widths_path = _font_sources()
    if not texture.is_file() or not widths_path.is_file():
        raise FileNotFoundError("The FF8 menu font has not been extracted yet")
    if FONT_PATH.is_file() and FONT_REVISION_PATH.is_file() \
            and FONT_REVISION_PATH.read_text(encoding="ascii").strip() == FONT_REVISION \
            and FONT_PATH.stat().st_mtime_ns >= max(
        texture.stat().st_mtime_ns, widths_path.stat().st_mtime_ns
    ):
        return FONT_PATH

    atlas_width, _atlas_height, pixels, visible = _read_texture(texture)
    advances = _read_widths(widths_path)
    glyph_order = [".notdef"]
    glyphs = {".notdef": TTGlyphPen(None).glyph()}
    metrics = {".notdef": (8 * SCALE, 0)}
    cmap: dict[int, str] = {}
    used_names: set[str] = set()
    for offset, character in enumerate(CHARACTERS):
        code = FIRST_CODE + offset
        name = f"uni{ord(character):04X}"
        if name in used_names:
            continue
        used_names.add(name)
        glyph_order.append(name)
        glyphs[name] = _glyph(atlas_width, pixels, visible, code)
        cell = code - FIRST_CODE
        advance = advances[cell] if cell < len(advances) else 8
        # The game's TDW gives "1" the same cell width as the other digits.
        # The game renderer applies a narrow-glyph correction that a normal TTF
        # renderer does not. Reproduce that correction in the private font.
        if character == "1":
            advance = 4
        metrics[name] = (max(advance, 2) * SCALE, 0)
        cmap[ord(character)] = name

    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=901, descent=-123)
    builder.setupNameTable({
        "familyName": "FF8 Menu",
        "styleName": "Regular",
        "uniqueFontIdentifier": "Lexeditor FF8 Menu",
        "fullName": "FF8 Menu",
        "psName": FONT_NAME,
    })
    builder.setupOS2(
        sTypoAscender=901, sTypoDescender=-123,
        usWinAscent=901, usWinDescent=123,
    )
    builder.setupPost()
    builder.setupMaxp()
    FONT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = FONT_PATH.with_suffix(".tmp")
    builder.save(temporary)
    temporary.replace(FONT_PATH)
    FONT_REVISION_PATH.write_text(FONT_REVISION + "\n", encoding="ascii")
    return FONT_PATH
