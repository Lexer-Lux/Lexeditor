"""Private Triple Triad previews decoded from the supported English executable.

FFNx src/ff8_data.cpp resolves the embedded cards TIM through 00534640+11B.
Its src/ff8/vram.cpp uses a 28x4 cell grid with 128 colours per card, two
palette columns. The ID-to-cell order also matches schema/card.json.
Source reference: FFNx c056db2783f376a340fcefa6a48cc33618998876.

Only PNG bytes generated from the user's installed game are served. No game
art or executable data belongs in the repository or release bundle.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import struct

from PIL import Image

from . import executable_text, paths

TIM_OFFSET = 0x7A9B10
CARD_COUNT = 110
CELL_SIZE = 64
# FFNx src/ff8_data.cpp resolves this TIM through 00534640+125.
# Each element has four 16x16 animation frames; the card uses the first.
ICONS_TIM_OFFSET = 0x796A90
ELEMENT_CELLS = {1: (0, 16, 3), 2: (64, 16, 6), 4: (128, 16, 9),
                 8: (192, 16, 12), 16: (0, 32, 15), 32: (64, 32, 18),
                 64: (128, 32, 21), 128: (192, 32, 24)}


def _read_atlas(exe: bytes) -> tuple[tuple[tuple[int, int, int, int], ...], bytes]:
    executable_text._validate_executable(exe)
    if len(exe) < TIM_OFFSET + 20:
        raise ValueError("Incomplete card TIM")
    magic, flags, clut_size, _, _, pal_width, pal_height = struct.unpack_from(
        '<IIIHHHH', exe, TIM_OFFSET)
    if (magic, flags, pal_width, pal_height) != (0x10, 9, 256, 56):
        raise ValueError("Unsupported card palette layout")
    if clut_size != 12 + pal_width * pal_height * 2:
        raise ValueError("Invalid card palette length")
    image_header = TIM_OFFSET + 8 + clut_size
    image_size, _, _, width_words, height = struct.unpack_from('<IHHHH', exe, image_header)
    width = width_words * 2
    if (width, height) != (28 * CELL_SIZE, 4 * CELL_SIZE) or image_size != 12 + width * height:
        raise ValueError("Unsupported card atlas dimensions")
    start = image_header + 12
    pixels = exe[start:start + width * height]
    if len(pixels) != width * height:
        raise ValueError("Incomplete card image pixels")
    palette = []
    for index in range(pal_width * pal_height):
        color = struct.unpack_from('<H', exe, TIM_OFFSET + 20 + index * 2)[0]
        channels = tuple(((color >> shift & 31) << 3) + ((color >> shift & 31) >> 2) for shift in (0, 5, 10))
        palette.append((*channels, 0 if color == 0 else 255))
    return tuple(palette), pixels


def _render_card(card_id: int, palette: tuple, pixels: bytes) -> bytes:
    if isinstance(card_id, bool) or not isinstance(card_id, int) or not 0 <= card_id < CARD_COUNT:
        raise ValueError("Card artwork ID must be 0 to 109")
    x = (card_id // 8 * 2 + card_id % 2) * CELL_SIZE
    y = (card_id % 8 // 2) * CELL_SIZE
    palette_start = card_id * 128
    rgba = bytearray()
    for row in range(CELL_SIZE):
        start = (y + row) * (28 * CELL_SIZE) + x
        for pixel in pixels[start:start + CELL_SIZE]:
            rgba.extend(palette[palette_start + pixel])
    image = Image.frombytes('RGBA', (CELL_SIZE, CELL_SIZE), bytes(rgba))
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


@lru_cache(maxsize=2)
def _cached_cards(exe_path: str, size: int, mtime_ns: int) -> tuple[bytes, ...]:
    # Fingerprint keys invalidate the in-memory cache if the installed EXE
    # changes. Validate the supported hash before reading any fixed offsets.
    palette, pixels = _read_atlas(Path(exe_path).read_bytes())
    return tuple(_render_card(card, palette, pixels) for card in range(CARD_COUNT))


def png_bytes(card_id: int, game_root: Path | None = None) -> bytes:
    if isinstance(card_id, bool) or not isinstance(card_id, int) or not 0 <= card_id < CARD_COUNT:
        raise ValueError("Card artwork ID must be 0 to 109")
    exe = ((game_root or paths.GAME_ROOT) / 'FF8_EN.exe').resolve()
    stat = exe.stat()
    return _cached_cards(str(exe), stat.st_size, stat.st_mtime_ns)[card_id]


def _render_elements(exe: bytes) -> dict[int, bytes]:
    executable_text._validate_executable(exe)
    start = ICONS_TIM_OFFSET
    magic, flags, clut_size, _, _, pw, ph = struct.unpack_from('<III4H', exe, start)
    if (magic, flags, clut_size, pw, ph) != (16, 8, 3084, 48, 32):
        raise ValueError('Unsupported Triple Triad icon palette')
    header = start + 8 + clut_size
    length, _, _, words, height = struct.unpack_from('<I4H', exe, header)
    if (length, words, height) != (73740, 192, 192) or header + length > len(exe):
        raise ValueError('Unsupported Triple Triad icon image')
    pixels = exe[header + 12:header + length]
    images = {}
    for element, (x, y, palette) in ELEMENT_CELLS.items():
        colors = []
        for index in range(16):
            color = struct.unpack_from('<H', exe, start + 20 + (palette * 16 + index) * 2)[0]
            colors.append(tuple(round((color >> shift & 31) * 255 / 31)
                                for shift in (0, 5, 10)) + (0 if color == 0 else 255,))
        rgba = bytearray()
        for row in range(y, y + 16):
            for column in range(x, x + 16):
                packed = pixels[row * words * 2 + column // 2]
                rgba.extend(colors[(packed >> (4 * (column % 2))) & 15])
        image = Image.frombytes('RGBA', (16, 16), bytes(rgba))
        output = BytesIO()
        image.save(output, format='PNG')
        images[element] = output.getvalue()
    return images


@lru_cache(maxsize=2)
def _cached_elements(exe_path: str, size: int, mtime_ns: int) -> dict[int, bytes]:
    return _render_elements(Path(exe_path).read_bytes())


def element_png_bytes(element: int, game_root: Path | None = None) -> bytes:
    if isinstance(element, bool) or not isinstance(element, int) or element not in ELEMENT_CELLS:
        raise ValueError('Unknown Triple Triad element')
    exe = ((game_root or paths.GAME_ROOT) / 'FF8_EN.exe').resolve()
    stat = exe.stat()
    return _cached_elements(str(exe), stat.st_size, stat.st_mtime_ns)[element]
