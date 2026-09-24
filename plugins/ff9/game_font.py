"""Build private web fonts from the player's installed FF9 font bundle.

Memoria installs ``FF9_Data/EmbeddedAsset/FA/p_fa.mpc``: an uncompressed
Unity asset bundle ("UnityRaw") whose first and last 1024 bytes are swapped
(Memoria ``Assembly-CSharp/Global/Byte/ByteEncryption.cs``, MIT). The bundle
embeds TrueType fonts as raw ``Font`` asset bytes, among them "Alexandria"
(Teaito's recreation of the PlayStation FF9 lettering) and "Garnet" (a
heavier companion face).

Like the FF7 and FF8 menu fonts, the faces are copied into the player's
private game-data cache only and served from the loopback editor. Nothing
from the bundle ships with Lexeditor. When the install or the bundle is
missing, :func:`ensure_font` raises and the page keeps its fallback stack.
"""

from __future__ import annotations

import io
from pathlib import Path
import re
import struct

from fontTools.ttLib import TTFont

from . import paths


FONT_REVISION = "1"
BLOCK = 1024
GENERATED = paths.DATA_ROOT / "generated"
# Served name -> family name inside the installed bundle.
FACES = {
    "ff9-menu.ttf": "Alexandria",
    "ff9-heading.ttf": "Garnet",
}
_SFNT = re.compile(re.escape(b"\x00\x01\x00\x00"))
_TAG = re.compile(rb"[A-Za-z0-9/ ]{4}")


def font_source(game_root: Path | None = None) -> Path:
    root = paths.GAME_ROOT if game_root is None else game_root
    for candidate in (root / "FF9_Data" / "EmbeddedAsset" / "FA" / "p_fa.mpc",
                      root / "x64" / "FF9_Data" / "EmbeddedAsset" / "FA" / "p_fa.mpc"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("The installed FF9 font bundle (Memoria p_fa.mpc) was not found")


def decrypt(raw: bytes) -> bytes:
    """Undo Memoria's block swap: the last block belongs at the front."""
    if len(raw) < 2 * BLOCK:
        raise ValueError("The FF9 font bundle is incomplete")
    data = raw[-BLOCK:] + raw[BLOCK:-BLOCK]
    if not data.startswith(b"UnityRaw"):
        raise ValueError("The FF9 font bundle is not an uncompressed Unity bundle")
    return data


def _sfnt_at(data: bytes, offset: int) -> bytes | None:
    if offset + 12 > len(data):
        return None
    count = struct.unpack_from(">H", data, offset + 4)[0]
    if not 4 <= count <= 40 or offset + 12 + 16 * count > len(data):
        return None
    tags, end = set(), 0
    for index in range(count):
        tag, _checksum, table_offset, length = struct.unpack_from(">4sIII", data, offset + 12 + 16 * index)
        if not _TAG.fullmatch(tag):
            return None
        tags.add(tag)
        end = max(end, table_offset + length)
    if not {b"cmap", b"glyf", b"head", b"name"} <= tags or offset + end > len(data):
        return None
    return data[offset:offset + end]


def carve_fonts(data: bytes) -> dict[str, bytes]:
    """Return {family: TrueType bytes} for every font embedded in the bundle."""
    found: dict[str, bytes] = {}
    for hit in _SFNT.finditer(data):
        blob = _sfnt_at(data, hit.start())
        if blob is None:
            continue
        try:
            family = TTFont(io.BytesIO(blob), lazy=True)["name"].getDebugName(1)
        except Exception:  # A false signature inside other asset bytes.
            continue
        if family and family not in found:
            found[family] = blob
    return found


def _fresh(source: Path) -> bool:
    revision = GENERATED / "ff9-fonts.revision"
    if not revision.is_file() or revision.read_text(encoding="ascii").strip() != FONT_REVISION:
        return False
    stamp = source.stat().st_mtime_ns
    return all((GENERATED / name).is_file() and (GENERATED / name).stat().st_mtime_ns >= stamp
               for name in FACES)


def ensure_font(name: str = "ff9-menu.ttf") -> Path:
    """Return a private copy of one installed FF9 face, extracting it once."""
    if name not in FACES:
        raise FileNotFoundError(f"Unknown FF9 font: {name}")
    source = font_source()
    if not _fresh(source):
        fonts = carve_fonts(decrypt(source.read_bytes()))
        missing = [family for family in FACES.values() if family not in fonts]
        if missing:
            raise FileNotFoundError("The FF9 font bundle has no " + ", ".join(missing) + " face")
        GENERATED.mkdir(parents=True, exist_ok=True)
        for served, family in FACES.items():
            temporary = GENERATED / (served + ".tmp")
            temporary.write_bytes(fonts[family])
            temporary.replace(GENERATED / served)
        (GENERATED / "ff9-fonts.revision").write_text(FONT_REVISION + "\n", encoding="ascii")
    return GENERATED / name
