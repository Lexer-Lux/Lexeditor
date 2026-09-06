"""Render menu card art from the user's local FF8 archive, never bundled images.

Layout sources: OpenVIII Core/Menu/Images/Cards.cs (11 cards per mcNN.tex),
SP2.cs, and Core/Image/Entry.cs::LoadfromStreamSP2. TEX header fields are from
Core/Image/TEX.cs. All reads are bounded; generated PNGs stay in memory.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import struct

from PIL import Image

from . import paths
from .fs_archive import FsArchive


def card_rectangle(index: bytes, card_id: int) -> tuple[int, int, int, int]:
    if not 0 <= card_id < 110:
        raise ValueError("Card image ID must be between 0 and 109")
    if len(index) < 4:
        raise ValueError("Incomplete cardanm.sp2 header")
    count = struct.unpack_from("<I", index)[0]
    slot = card_id % 11
    if not 11 <= count <= 4096 or len(index) < 4 + count * 4:
        raise ValueError("Invalid cardanm.sp2 index")
    offset = struct.unpack_from("<H", index, 4 + slot * 4)[0]
    if offset < 4 + count * 4 or offset + 12 > len(index):
        raise ValueError("Card rectangle is outside cardanm.sp2")
    x, y = index[offset + 4:offset + 6]
    width, height = index[offset + 8], index[offset + 10]
    if not width or not height or index[offset + 6] in (0, 96):
        raise ValueError("Invalid card rectangle")
    return x, y, x + width, y + height


def decode_card(index: bytes, texture: bytes, card_id: int) -> bytes:
    """Decode the indexed FF8 menu texture and crop its SP2 card rectangle."""
    if len(texture) < 240 or struct.unpack_from("<I", texture)[0] != 2:
        raise ValueError("Expected a complete FF8 TEX version 2 header")
    colors = struct.unpack_from("<I", texture, 0x34)[0]
    width, height = struct.unpack_from("<II", texture, 0x3C)
    palette_flag = struct.unpack_from("<I", texture, 0x4C)[0]
    palette_size = struct.unpack_from("<I", texture, 0x58)[0]
    bytes_per_pixel = struct.unpack_from("<I", texture, 0x68)[0]
    if not (palette_flag and bytes_per_pixel == 1 and 1 <= colors <= 256
            and colors <= palette_size <= 65536 and 0 < width <= 4096 and 0 < height <= 4096):
        raise ValueError("Unsupported card TEX layout")
    start = 240 + palette_size * 4
    pixels = texture[start:start + width * height]
    if len(pixels) != width * height or max(pixels, default=0) >= colors:
        raise ValueError("Incomplete card TEX pixels or palette index out of range")
    image = Image.frombytes("P", (width, height), pixels)
    palette = bytearray()
    for pos in range(colors):
        blue, green, red, alpha = texture[240 + pos*4:244 + pos*4]
        palette.extend((red, green, blue, alpha))
    image.putpalette(bytes(palette), rawmode="RGBA")
    rectangle = card_rectangle(index, card_id)
    if rectangle[2] > width or rectangle[3] > height:
        raise ValueError("Card rectangle exceeds its texture")
    output = BytesIO()
    image.convert("RGBA").crop(rectangle).save(output, format="PNG")
    return output.getvalue()


@lru_cache(maxsize=128)
def _archive_card(prefix: str, fingerprint: tuple, card_id: int) -> bytes:
    # The stat fingerprint invalidates cached images when the installation changes.
    archive = FsArchive(Path(prefix))
    index = archive.extract(archive.find("cardanm.sp2"))
    texture = archive.extract(archive.find(f"mc{card_id // 11:02}.tex"))
    return decode_card(index, texture, card_id)


def card_png(card_id: int) -> bytes:
    if not 0 <= card_id < 110:
        raise ValueError("Card image ID must be between 0 and 109")
    prefix = paths.ARCHIVES["menu"]
    fingerprint = tuple((path.stat().st_size, path.stat().st_mtime_ns)
                        for path in (prefix.with_suffix(ext) for ext in (".fs", ".fi", ".fl")))
    return _archive_card(str(prefix.resolve()), fingerprint, card_id)
