"""Expose the installed Warband bitmap font atlas without inventing a TTF."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from . import paths


GAME_ROOT = Path(paths.WARBAND_ROOT)
FONT_DATA = GAME_ROOT / "Data" / "font_data.xml"
FONT_TEXTURE = GAME_ROOT / "Textures" / "font.dds"
LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
ATLAS_PNG = LOCAL_DATA / "Lexeditor" / "game-data" / "warband" / "font" / "font-alpha.png"


def manifest() -> dict:
    if not FONT_DATA.is_file() or not FONT_TEXTURE.is_file():
        return {"available": False, "reason": "The installed Warband font atlas is missing."}
    root = ET.parse(FONT_DATA).getroot()
    characters = {}
    details = root.find("FontDetails")
    if details is not None:
        for node in details.findall("character"):
            code = node.get("code", "")
            if not code:
                continue
            characters[code] = {
                key: int(node.get(key, "0"))
                for key in ("u", "v", "w", "h", "preshift", "yadjust", "postshift")
            }
    return {
        "available": True,
        "width": int(root.get("width", "2048")),
        "height": int(root.get("height", "1024")),
        "fontSize": int(root.get("font_size", "70")),
        "lineSpacing": int(root.get("line_spacing", "100")),
        "characters": characters,
    }


def atlas_path() -> Path | None:
    if not FONT_TEXTURE.is_file():
        return None
    if not ATLAS_PNG.is_file() or ATLAS_PNG.stat().st_mtime_ns < FONT_TEXTURE.stat().st_mtime_ns:
        ATLAS_PNG.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(FONT_TEXTURE) as image:
            rgba = image.convert("RGBA")
            # Warband supplies exact glyph coverage in the DDS alpha channel.
            # Transparent texels can still have dark RGB values, so deriving
            # opacity from luminance makes those invisible pixels appear.
            alpha = rgba.getchannel("A")
            mask = Image.new("RGBA", rgba.size, (255, 255, 255, 0))
            mask.putalpha(alpha)
            mask.save(ATLAS_PNG, "PNG", optimize=True)
    return ATLAS_PNG
