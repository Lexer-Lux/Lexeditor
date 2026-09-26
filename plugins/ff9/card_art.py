"""Cut private Tetra Master card faces from the player's installed FF9.

The Steam release keeps every card's art in one 2048x2048 ARGB32 ``Texture2D``
named ``quadmist_image1`` inside ``x64/FF9_Data/sharedassets2.assets``. An
NGUI ``UIAtlas`` MonoBehaviour in the same file, drawn with the material
"QuadMist Image Atlas 1", names each face ``card_00`` .. ``card_99`` and gives
its pixel rectangle (``UISpriteData``: name, x, y, width, height, then eight
border/padding ints; the origin is the texture's top-left corner). The sprite
number is the card id in Memoria's ``TetraMaster/TripleTriad.csv``.

Texture2D layout (Unity 5.2, format 15): name, width, height, complete image
size, texture format, mip count, two readable flags, image count, dimension,
four texture-setting ints, lightmap format and colour space (fourteen ints in
all), then the image-data
length and the pixels, bottom row first. This matches the permissively
licensed UnityPy reader; nothing from it is vendored.

Like the menu fonts, the faces are written only to the player's private
game-data cache and served from the loopback editor. Nothing from the game is
bundled. The cache holds exactly one PNG per card and is rewritten, never
added to, when the installed file changes.
"""

from __future__ import annotations

import io
from pathlib import Path
import re
import struct
import threading

from PIL import Image

from . import paths
from .battle_scene import UnityArchive


ART_REVISION = "1"
TEXTURE_NAME = "quadmist_image1"
MATERIAL_NAME = "QuadMist Image Atlas 1"
ARGB32 = 5
CARD_COUNT = 100
GENERATED = paths.DATA_ROOT / "generated" / "tetra-cards"
_SPRITE = re.compile(r"card_(\d{2})")
_LOCK = threading.Lock()


def art_source(game_root: Path | None = None) -> Path:
    root = paths.GAME_ROOT if game_root is None else game_root
    source = root / "x64" / "FF9_Data" / "sharedassets2.assets"
    if not source.is_file():
        raise FileNotFoundError("The installed FF9 card art (sharedassets2.assets) was not found")
    return source


def _string(data: bytes, pos: int) -> tuple[str, int]:
    length = struct.unpack_from("<I", data, pos)[0]
    if length > 4096 or pos + 4 + length > len(data):
        raise ValueError("Unity string is out of range")
    text = data[pos + 4:pos + 4 + length].decode("utf-8")
    return text, pos + 4 + ((length + 3) & ~3)


def atlas_sprites(archive: UnityArchive) -> dict[int, tuple[int, int, int, int]]:
    """Return {card id: (x, y, width, height)} from the card-face UIAtlas."""
    materials = {obj.info for obj in archive.objects if obj.type_id == 21 and obj.name == MATERIAL_NAME}
    if not materials:
        raise ValueError(f"No '{MATERIAL_NAME}' material in the installed card art")
    for obj in archive.objects:
        # Script-backed objects carry negative class ids in this format.
        if obj.type_id < 0x80000000 and obj.type_id != 114:
            continue
        blob = archive.data[obj.offset:obj.offset + obj.size]
        try:
            _name, pos = _string(blob, 28)
            _file, material = struct.unpack_from("<iq", blob, pos); pos += 12
            if material not in materials:
                continue
            count = struct.unpack_from("<I", blob, pos)[0]; pos += 4
            if count > 10_000:
                continue
            sprites = {}
            for _ in range(count):
                name, pos = _string(blob, pos)
                x, y, width, height = struct.unpack_from("<4i", blob, pos); pos += 48
                match = _SPRITE.fullmatch(name)
                if match:
                    sprites[int(match.group(1))] = (x, y, width, height)
        except (ValueError, UnicodeDecodeError, struct.error):
            continue
        if sprites:
            return sprites
    raise ValueError("No card-face atlas was found in the installed card art")


def texture(archive: UnityArchive, name: str = TEXTURE_NAME) -> Image.Image:
    obj = next((obj for obj in archive.objects if obj.type_id == 28 and obj.name == name), None)
    if obj is None:
        raise ValueError(f"No '{name}' texture in the installed card art")
    data = archive.data
    _name, pos = _string(data, obj.offset)
    width, height, size, fmt = struct.unpack_from("<4i", data, pos)
    if fmt != ARGB32 or not (0 < width <= 8192 and 0 < height <= 8192) or size != width * height * 4:
        raise ValueError(f"'{name}' is not the expected ARGB32 texture")
    length = struct.unpack_from("<i", data, pos + 56)[0]
    start = pos + 60
    if length != size or start + size > obj.offset + obj.size:
        raise ValueError(f"'{name}' pixel data is truncated")
    image = Image.frombytes("RGBA", (width, height), data[start:start + size], "raw", "ARGB")
    return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def cut_cards(archive: UnityArchive) -> dict[int, bytes]:
    """Return {card id: PNG bytes} for every face the atlas names."""
    sheet = texture(archive)
    faces = {}
    for card, (x, y, width, height) in atlas_sprites(archive).items():
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > sheet.width or y + height > sheet.height:
            raise ValueError(f"card_{card:02d} lies outside the card-art texture")
        buffer = io.BytesIO()
        sheet.crop((x, y, x + width, y + height)).save(buffer, format="PNG", optimize=True)
        faces[card] = buffer.getvalue()
    return faces


def _stamp(source: Path) -> str:
    status = source.stat()
    return f"{ART_REVISION}:{status.st_size}:{status.st_mtime_ns}"


def ensure_card(card: int) -> Path:
    """Return the private PNG of one card face, cutting every face once."""
    if not isinstance(card, int) or not 0 <= card < CARD_COUNT:
        raise FileNotFoundError(f"Unknown Tetra Master card: {card}")
    source = art_source()
    marker = GENERATED / "cards.revision"
    target = GENERATED / f"{card:02d}.png"
    with _LOCK:
        fresh = marker.is_file() and marker.read_text(encoding="ascii").strip() == _stamp(source)
        if not fresh:
            faces = cut_cards(UnityArchive(source))
            GENERATED.mkdir(parents=True, exist_ok=True)
            for stale in GENERATED.glob("*.png"):
                stale.unlink()
            for number, png in faces.items():
                temporary = GENERATED / f"{number:02d}.png.tmp"
                temporary.write_bytes(png)
                temporary.replace(GENERATED / f"{number:02d}.png")
            marker.write_text(_stamp(source) + "\n", encoding="ascii")
    if not target.is_file():
        raise FileNotFoundError(f"The installed card art has no face for card {card}")
    return target
