from pathlib import Path
from PIL import Image
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EDITOR = (ROOT / "plugins" / "warband" / "editor.js").read_text(encoding="utf-8")
SERVER = (ROOT / "plugins" / "warband" / "server.py").read_text(encoding="utf-8")
PREVIEW = (ROOT / "plugins" / "warband" / "model_preview.py").read_text(encoding="utf-8")
FONT = (ROOT / "plugins" / "warband" / "game_font.py").read_text(encoding="utf-8")

from plugins.warband.game_font import FONT_TEXTURE, atlas_path  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require('"inventoryMesh": meshes[0] if meshes else ""' in SERVER,
        "Warband items must expose the first native inventory mesh")
require('/api/item-preview' in SERVER and '/api/item-preview/texture' in SERVER,
        "the Warband service must expose real mesh and texture preview endpoints")
require('/api/warband-font' in SERVER and '/api/warband-font/atlas' in SERVER,
        "the Warband service must expose its installed bitmap font")
require('BRF_SYNC = LEXEDITOR_ROOT / "tools" / "brf-sync" / "bin" / "brf_sync.exe"' in PREVIEW,
        "Warband preview extraction must use the bundled headless BRF tool")
require("font_data.xml" in FONT and '"font.dds"' in FONT,
        "Warband typography must use the installed game atlas and metrics")
require('rgba.getchannel("A")' in FONT and "luminance.point" not in FONT,
        "Warband glyph opacity must preserve the installed DDS alpha")
require(".ttf" not in FONT.casefold() and ".otf" not in FONT.casefold(),
        "Warband typography must not invent a desktop font substitute")
require("loadWarbandIcon" in EDITOR and "loadWarbandModel" in EDITOR and
        "createWarbandRenderer" in EDITOR,
        "the Items detail panel must load both its still icon and turnable model")
require("/api/item-preview?mesh=" in EDITOR and
        "encodeURIComponent(item.inventoryMesh)" in EDITOR and
        "createWarbandRenderer(canvas,data,true)" in EDITOR,
        "the model drawer must fetch installed geometry and instantiate the WebGL renderer")
require('detailPanel({className:"warband-item-detail",icon:thumbnail' in EDITOR,
        "Warband Items must use the shared Detail heading icon slot")
require('modelPreview:item.inventoryMesh?' in EDITOR and
        'content:()=>warbandPreviewStage(item)' in EDITOR,
        "the Items heading icon must open the shared lazy model-preview drawer")
require("/api/item-icon" in EDITOR and "thumbnailCanvas" not in EDITOR,
        "the heading icon must be a cached PNG, not a second live model canvas")
require("bitmapText(item.name,24)" in EDITOR and "applyInstalledWarbandFont" in EDITOR,
        "prominent Warband labels must use the installed bitmap-font path")
require('filename in {"Resource/*.brf", "Textures/*.dds"}' in SERVER,
        "the data map must report read-only BRF and DDS preview integration as partial")
require((ROOT / "tools" / "brf-sync" / "bin" / "brf_sync.exe").is_file(),
        "the bundled BRF preview tool is missing")
require((ROOT / "tools" / "brf-sync" / "LICENSE").is_file(),
        "the bundled BRF tool license is missing")
require((ROOT / "tools" / "brf-sync" / "SOURCE.md").is_file(),
        "the bundled BRF tool source record is missing")

# Proprietary installed font data is absent on generic CI. When a local Warband
# install supplies it, retain the stronger byte-for-byte alpha check; otherwise
# installed appearance remains the human acceptance step.
if FONT_TEXTURE.is_file():
    generated = atlas_path()
    require(generated is not None and generated.is_file(), "the Warband alpha atlas was not generated")
    with Image.open(FONT_TEXTURE) as source, Image.open(generated) as converted:
        require(source.convert("RGBA").getchannel("A").tobytes() ==
                converted.convert("RGBA").getchannel("A").tobytes(),
                "the generated Warband atlas changed the source glyph alpha")

print("Warband item preview issue 20 source contract passed")
