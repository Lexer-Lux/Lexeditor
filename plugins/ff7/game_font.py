"""Build a private web font from the player's installed FF7 menu font.

The US menu lettering lives in the installed ``menu_us.lgp`` archive member
``usfont_h.tex``: a 236-byte header, sixteen 16-entry BGRA palettes, and
256x256 8-bit pixels. Glyphs sit in a fixed 12-pixel grid, 21 columns wide,
in FF7 text-code order (``format_codec.TEXT_MAP``): code 0x01 is the top-left
cell, and code 0x00 is the space, which has no cell. Any nonzero pixel index
is not necessarily glyph ink: the darkest nonzero entry is the drop shadow.

Like the FF8 menu font, the generated TTF is written to the player's private
game-data cache only; the atlas never ships with Lexeditor. Character advances
come from WINDOW.BIN, rather than treating the atlas's cell pitch as spacing.
"""

from __future__ import annotations

from pathlib import Path
import gzip
import struct

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from . import paths
from .archives import LGP
from .format_codec import TEXT_MAP


FONT_NAME = "FF7Menu"
FONT_PATH = paths.DATA_ROOT / "generated" / "ff7-menu.ttf"
FONT_REVISION_PATH = paths.DATA_ROOT / "generated" / "ff7-menu.revision"
FONT_REVISION = "2"
FONT_MEMBER = "usfont_h.tex"
CELL = 12
ATLAS_COLUMNS = 21
SCALE = 80
UNITS_PER_EM = 1024
TEX_HEADER = 236
TEX_PALETTES = 16
TEX_ENTRIES = 16


def _font_source(game_root: Path) -> Path:
    candidates = (
        game_root / "ff7" / "workingdir" / "data" / "menu" / "menu_us.lgp",
        game_root / "data" / "menu" / "menu_us.lgp",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("The installed FF7 menu archive was not found")


def _read_pixels(member: bytes) -> tuple[int, int, bytes]:
    if len(member) < TEX_HEADER + TEX_PALETTES * TEX_ENTRIES * 4:
        raise ValueError("FF7 usfont_h.TEX is incomplete")
    offset = TEX_HEADER + TEX_PALETTES * TEX_ENTRIES * 4
    tail = len(member) - offset
    side = int(tail ** 0.5)
    if side * side != tail or side <= 0:
        raise ValueError("FF7 usfont_h.TEX pixel data is not square")
    pixels = member[offset:offset + side * side]
    if any(byte >= TEX_ENTRIES for byte in pixels):
        raise ValueError("FF7 usfont_h.TEX uses an unknown palette entry")
    palette = member[TEX_HEADER:TEX_HEADER + TEX_ENTRIES * 4]
    brightness = [sum(palette[index * 4:index * 4 + 3]) for index in range(TEX_ENTRIES)]
    brightest = max(brightness)
    if not brightest:
        raise ValueError("FF7 usfont_h.TEX has no visible palette ink")
    # White contours must not incorporate the black drop shadow; that filled
    # the counters of small letters and made the web font look unlike the game.
    ink = bytes(int(palette[index * 4 + 3] != 0 and brightness[index] >= brightest / 2)
                for index in range(TEX_ENTRIES))
    return side, side, pixels.translate(ink + bytes(256 - len(ink)))


def _font_metrics(game_root: Path) -> bytes | None:
    # WINDOW.BIN's first type-1 member holds width/kerning bytes, as documented
    # by ff7tools' retrieveMetrics/charWidth. The English atlas needs English
    # metrics, including on the 2026 release's language-specific layout.
    for base in (game_root / 'ff7/workingdir', game_root):
        for relative in ('data/lang-en/kernel/window.bin', 'data/kernel/window.bin'):
            path = base / relative
            if not path.is_file():
                continue
            data, offset = path.read_bytes(), 0
            while offset + 6 <= len(data):
                size, expected, kind = struct.unpack_from('<HHH', data, offset)
                end = offset + 6 + size
                if end > len(data):
                    raise ValueError('FF7 font metrics archive is truncated')
                if kind == 1:
                    raw = gzip.decompress(data[offset + 6:end])
                    if len(raw) != expected or len(raw) < 0xE7:
                        raise ValueError('FF7 font metrics are incomplete')
                    return raw
                offset = end
    return None


def _cell_ink(width: int, pixels: bytes, left: int, top: int) -> list[int] | None:
    """The ink bounds of one grid cell, or None when the cell is empty."""
    found = [x + y * width for y in range(top, top + CELL)
             for x in range(left, left + CELL) if pixels[y * width + x]]
    if not found:
        return None
    xs = [slot % width for slot in found]
    ys = [slot // width for slot in found]
    return [min(xs), min(ys), max(xs), max(ys)]


def extract_glyphs(game_root: Path | None = None) -> dict[str, dict]:
    """Map printable characters to atlas boxes, advances and the baseline.

    Returns ``{"glyphs": {char: {"box": [...], "advance": px,
    "baseline": y}}, "pixels": bytes, "width": int}``. The space has an
    advance but no box. Cells with no ink stay unmapped, so the browser
    falls back to the system font instead of showing the wrong cell.
    """
    root = Path(game_root) if game_root else paths.GAME_ROOT
    archive = LGP(_font_source(root).read_bytes())
    names = [name for name, _start, _size in archive.entries]
    try:
        member = archive.member(names.index(FONT_MEMBER))
    except ValueError:
        raise FileNotFoundError(f"{FONT_MEMBER} is not in the installed menu archive")
    width, height, pixels = _read_pixels(member)
    metrics = _font_metrics(root)
    ordered: dict[str, dict] = {}
    rows: dict[int, list[dict]] = {}
    for code in range(0x01, 0xE7):
        if code >= len(TEXT_MAP) or TEXT_MAP[code] == " ":
            continue
        # Code 0x00 is the blank top-left cell, so cells and codes align.
        row, column = divmod(code, ATLAS_COLUMNS)
        left, top = column * CELL, row * CELL
        if left + CELL > width or top + CELL > height:
            raise ValueError("FF7 usfont_h.TEX is too small for its text codes")
        box = _cell_ink(width, pixels, left, top)
        if box is None:
            continue
        advance = ((metrics[code] & 31) + (metrics[code] >> 5)) if metrics else box[2] - box[0] + 2
        entry = {"box": box, "char": TEXT_MAP[code], "advance": advance,
                 "baseline": 0}
        if TEXT_MAP[code] not in ordered:
            ordered[TEXT_MAP[code]] = entry
            rows.setdefault(row, []).append(entry)
    baselines: dict[int, int] = {}
    for number in sorted(rows):
        caps = sorted(entry["box"][3] for entry in rows[number]
                      if entry["char"].isupper())
        if caps:
            baselines[number] = caps[len(caps) // 2]
        elif number - 1 in baselines:
            baselines[number] = baselines[number - 1] + CELL
    for number in sorted(rows, reverse=True):
        if number not in baselines and baselines:
            known = min(baselines)
            baselines[number] = baselines[known] - CELL * (known - number)
    for number, entries in rows.items():
        for entry in entries:
            entry["baseline"] = baselines[number]
    space = ((metrics[0] & 31) + (metrics[0] >> 5)) if metrics else 3
    ordered[" "] = {"box": None, "char": " ", "advance": space, "baseline": 0}
    return {"glyphs": ordered, "pixels": pixels, "width": width}


def _glyph(width: int, pixels: bytes, box: list[int] | None,
           baseline: int) -> object:
    pen = TTGlyphPen(None)
    if box is None:
        return pen.glyph()
    left, top, right, bottom = box
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            if not pixels[y * width + x]:
                continue
            x0, x1 = (x - left) * SCALE, (x - left + 1) * SCALE
            y1, y0 = (baseline - y) * SCALE, (baseline - y - 1) * SCALE
            pen.moveTo((x0, y0))
            pen.lineTo((x1, y0))
            pen.lineTo((x1, y1))
            pen.lineTo((x0, y1))
            pen.closePath()
    return pen.glyph()


def ensure_font(game_root: Path | None = None) -> Path:
    """Return the generated private TTF, rebuilding it when stale."""
    root = Path(game_root) if game_root else paths.GAME_ROOT
    source = _font_source(root)
    if FONT_PATH.is_file() and FONT_REVISION_PATH.is_file() \
            and FONT_REVISION_PATH.read_text(encoding="ascii").strip() == FONT_REVISION \
            and game_root is None \
            and FONT_PATH.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return FONT_PATH
    if not source.is_file():
        raise FileNotFoundError("The FF7 menu font has not been extracted yet")
    found = extract_glyphs(root)
    pixels, width = found["pixels"], found["width"]
    glyph_order = [".notdef"]
    glyphs = {".notdef": TTGlyphPen(None).glyph()}
    metrics = {".notdef": (8 * SCALE, 0)}
    cmap: dict[int, str] = {}
    for character, entry in sorted(found["glyphs"].items()):
        name = f"uni{ord(character):04X}"
        if name in glyphs:
            continue
        glyph_order.append(name)
        glyphs[name] = _glyph(width, pixels, entry["box"], entry["baseline"])
        metrics[name] = (max(entry["advance"], 2) * SCALE, 0)
        cmap[ord(character)] = name
    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=901, descent=-123)
    builder.setupNameTable({
        "familyName": "FF7 Menu",
        "styleName": "Regular",
        "uniqueFontIdentifier": "Lexeditor FF7 Menu",
        "fullName": "FF7 Menu",
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
