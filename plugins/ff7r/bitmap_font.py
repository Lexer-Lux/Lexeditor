"""Extract FF7R's installed SystemFontNormal bitmap font for editor chrome.

FF7R stores its menu font as a glyph-metrics UEXP plus a 2048x2048 BC5
bitmap atlas.  The byte layouts used here are the narrow, FF7R-specific
formats documented by the MIT-licensed FF7R-font-mod-tools project.  Game
payloads are read only from the user's installed PAKs and the decoded PNG is
written only to Lexeditor's private data cache.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import struct
from typing import Iterable

from .archive import installed_paks
from .tooling import get_file


UNREAL_TAG = b"\xC1\x83\x2A\x9E"
GLYPH_HEAD = b"\x01\x09"
GLYPH_HEAD2 = b"\x01\x02\x01\x05"
FONT_PAGE = 1
ATLAS_WIDTH = 2048
ATLAS_HEIGHT = 2048
ATLAS_UEXP_SIZE = 5_592_960
ATLAS_HEADER_SIZE = 116
ATLAS_FOOTER_SIZE = 412
ATLAS_RAW_SIZE = 5_592_432
ATLAS_MIP_SIZES = (
    4_194_304, 1_048_576, 262_144, 65_536, 16_384, 4_096,
    1_024, 256, 64, 16, 16, 16,
)
GLYPH_SUFFIXES = (
    "End/Content/GameContents/Menu/Resident/Font/JP/SystemFontNormal4K.uexp",
    "End/Content/GameContents/Menu/Resident/Font/JP/SystemFontNormalJP4K.uexp",
)
ATLAS_SUFFIX = "End/Content/GameContents/Menu/Billboard/Common/U_Com_JP_SystemFontNormal4K-01.uexp"
CACHE_SCHEMA = 1


def _u32(stream: io.BytesIO) -> int:
    raw = stream.read(4)
    if len(raw) != 4:
        raise ValueError("Truncated FF7R font UEXP")
    return struct.unpack("<I", raw)[0]


def _glyph(stream: io.BytesIO) -> dict:
    raw = stream.read(18)
    if len(raw) != 18:
        raise ValueError("Truncated FF7R font glyph record")
    codepoint, page, x, y, width, height, x_offset, y_offset, x_advance = struct.unpack(
        "<6H2hH", raw
    )
    if x + width > ATLAS_WIDTH or y + height > ATLAS_HEIGHT:
        raise ValueError("FF7R font glyph falls outside the 2048x2048 atlas")
    return {
        "codepoint": codepoint,
        "page": page,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "xOffset": x_offset,
        "yOffset": y_offset,
        "xAdvance": x_advance,
    }


def parse_glyph_uexp(payload: bytes, *, page: int = FONT_PAGE) -> dict:
    """Parse the fixed FF7R glyph UEXP and return one atlas page's metrics."""
    stream = io.BytesIO(payload)
    head = stream.read(2)
    if head == GLYPH_HEAD:
        header = head
    else:
        stream.seek(0)
        header = stream.read(4)
        if header != GLYPH_HEAD2:
            raise ValueError("Not an FF7R SystemFont glyph UEXP")
    if _u32(stream) != 0:
        raise ValueError("Unexpected FF7R SystemFont glyph header")
    count = _u32(stream)
    if count <= 0 or count > 65_535:
        raise ValueError("Implausible FF7R SystemFont glyph count")
    glyphs = [_glyph(stream) for _index in range(count)]

    if header == GLYPH_HEAD:
        null = stream.read(4)
        if len(null) != 4:
            raise ValueError("Truncated FF7R SystemFont metadata")
        info_count = _u32(stream)
        if info_count > 1024:
            raise ValueError("Implausible FF7R SystemFont metadata count")
        for _index in range(info_count):
            length = _u32(stream)
            if length:
                raw = stream.read(length)
                if len(raw) != length or raw[-1:] != b"\0":
                    raise ValueError("Malformed FF7R SystemFont metadata string")
                raw[:-1].decode("utf-8")
            if len(stream.read(2)) != 2:
                raise ValueError("Truncated FF7R SystemFont metadata record")

    font_size = _u32(stream)
    outline = _u32(stream)
    unknown = stream.read(4)
    footer = stream.read(4)
    if len(unknown) != 4 or footer != UNREAL_TAG or stream.read(1):
        raise ValueError("FF7R SystemFont glyph footer/length did not validate")
    if not 1 <= font_size <= 512 or outline > 64:
        raise ValueError("Implausible FF7R SystemFont metrics")

    selected = [glyph for glyph in glyphs if glyph["page"] == page]
    if not selected:
        raise ValueError(f"FF7R SystemFont contains no glyphs on page {page}")
    return {
        "fontSize": font_size,
        "outline": outline,
        "page": page,
        "glyphCount": len(selected),
        "glyphs": selected,
    }


def _mip_offsets(sizes: Iterable[int]) -> list[int]:
    out: list[int] = []
    position = 0
    for size in sizes:
        out.append(position)
        position += int(size)
    return out


def decode_font_atlas_png(payload: bytes) -> bytes:
    """Validate the known 4K FF7R font atlas UEXP and return a white-alpha PNG."""
    if len(payload) != ATLAS_UEXP_SIZE:
        raise ValueError(
            f"Unexpected FF7R 4K font atlas size: {len(payload)} (expected {ATLAS_UEXP_SIZE})"
        )
    if payload[-4:] != UNREAL_TAG:
        raise ValueError("FF7R 4K font atlas is missing the Unreal footer")
    raw = payload[ATLAS_HEADER_SIZE:ATLAS_UEXP_SIZE - ATLAS_FOOTER_SIZE]
    if len(raw) != ATLAS_RAW_SIZE or sum(ATLAS_MIP_SIZES) != len(raw):
        raise ValueError("FF7R 4K font atlas BC5 mip-chain size did not validate")

    # Imported lazily: normal FF7R parsing/smoke remains usable in minimal test
    # environments, while packaged Lexeditor already depends on texfury+Pillow.
    from PIL import Image, ImageChops
    from texfury import BCFormat, Texture

    texture = Texture.from_raw(
        raw,
        ATLAS_WIDTH,
        ATLAS_HEIGHT,
        BCFormat.BC5,
        len(ATLAS_MIP_SIZES),
        _mip_offsets(ATLAS_MIP_SIZES),
        list(ATLAS_MIP_SIZES),
        "ff7r-system-font-normal",
    )
    rgba, width, height = texture.to_rgba(0)
    if (width, height) != (ATLAS_WIDTH, ATLAS_HEIGHT):
        raise ValueError("Decoded FF7R SystemFont atlas dimensions did not validate")

    image = Image.frombytes("RGBA", (width, height), rgba)
    red, green, _blue, _alpha = image.split()
    # The source is BC5: the font mask lives in the two stored channels. Taking
    # the stronger component preserves fill/outline coverage without inventing
    # color; canvas supplies the editor's current text color.
    mask = ImageChops.lighter(red, green)
    white = Image.new("RGBA", image.size, (255, 255, 255, 0))
    white.putalpha(mask)
    output = io.BytesIO()
    white.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _normalize(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("/")


def _choose_suffix(paths: Iterable[str], suffixes: tuple[str, ...]) -> str | None:
    normalized = {_normalize(path).casefold(): _normalize(path) for path in paths}
    for suffix in suffixes:
        matches = [value for key, value in normalized.items() if key.endswith(suffix.casefold())]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
    return None


def _latest_payload(game_root: Path, internal: str) -> bytes:
    errors: list[str] = []
    for pak in reversed(installed_paks(game_root)):
        try:
            return get_file(pak, internal)
        except Exception as error:
            errors.append(f"{pak.name}: {error}")
    detail = "; ".join(errors[-3:])
    raise FileNotFoundError(f"Installed FF7R asset was indexed but could not be read: {internal}. {detail}")


def _signature(game_root: Path, glyph_path: str, atlas_path: str) -> dict:
    paks = installed_paks(game_root)
    return {
        "paks": [
            [str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns]
            for path in paks
        ],
        "glyph": glyph_path,
        "atlas": atlas_path,
        "decoder": 1,
    }


def bitmap_font_cache_root(data_root: Path) -> Path:
    return Path(data_root).resolve() / "theme-assets"


def bitmap_font_asset_file(data_root: Path) -> Path | None:
    target = bitmap_font_cache_root(data_root) / "font-atlas.png"
    return target.resolve() if target.is_file() else None


def _cached_manifest(root: Path, signature: dict) -> dict | None:
    path = root / "bitmap-font.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if payload.get("schema") != CACHE_SCHEMA or payload.get("signature") != signature:
        return None
    if not (root / "font-atlas.png").is_file():
        return None
    font = payload.get("font")
    return font if isinstance(font, dict) else None


def _write_cache(root: Path, signature: dict, font: dict, png: bytes) -> None:
    root.mkdir(parents=True, exist_ok=True)
    atlas = root / "font-atlas.png"
    temporary_atlas = atlas.with_suffix(".png.tmp")
    temporary_atlas.write_bytes(png)
    temporary_atlas.replace(atlas)
    manifest = root / "bitmap-font.json"
    temporary_manifest = manifest.with_suffix(".json.tmp")
    temporary_manifest.write_text(
        json.dumps({"schema": CACHE_SCHEMA, "signature": signature, "font": font}, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_manifest.replace(manifest)


def ensure_installed_bitmap_font(game_root: Path, data_root: Path, cooked_paths: Iterable[str]) -> dict:
    """Decode the installed normal menu font when both documented source assets exist."""
    paths = list(cooked_paths)
    glyph_path = _choose_suffix(paths, GLYPH_SUFFIXES)
    atlas_path = _choose_suffix(paths, (ATLAS_SUFFIX,))
    base = {
        "available": False,
        "sourceFound": bool(glyph_path and atlas_path),
        "atlasUrl": "",
        "page": FONT_PAGE,
        "glyphs": [],
        "fontSize": 0,
        "outline": 0,
        "glyphPath": glyph_path or "",
        "atlasPath": atlas_path or "",
    }
    if not glyph_path or not atlas_path:
        return {**base, "message": "Installed FF7R SystemFontNormal glyph/atlas pair was not uniquely identified."}

    root = bitmap_font_cache_root(data_root)
    signature = _signature(game_root, glyph_path, atlas_path)
    cached = _cached_manifest(root, signature)
    if cached is not None:
        return {
            **cached,
            "available": True,
            "atlasUrl": "/theme-assets/font-atlas.png",
            "message": "Decoded from the installed FF7R SystemFontNormal atlas.",
        }

    try:
        glyph = parse_glyph_uexp(_latest_payload(game_root, glyph_path))
        png = decode_font_atlas_png(_latest_payload(game_root, atlas_path))
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        return {**base, "message": f"Installed FF7R font sources were found but could not be decoded: {error}"}

    font = {
        **base,
        **glyph,
        "available": True,
        "sourceFound": True,
        "atlasUrl": "/theme-assets/font-atlas.png",
        "message": "Decoded from the installed FF7R SystemFontNormal atlas.",
    }
    _write_cache(root, signature, font, png)
    return font
