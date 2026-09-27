"""Contract for RDO inventory icon resolution and explicit failure states."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from rdr2_editor_source import editor_source
SOURCE = editor_source()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require(
    "ui_textures_mp/inventory_items_mp/${id}.png" in SOURCE,
    "RDO icons must use the actual Femga ui_textures_mp dictionary family",
)
require(
    "const inventoryIconLoads=new Map()" in SOURCE and "function loadInventoryIcon(texture)" in SOURCE,
    "one cached preflight result must drive both the detail icon and dialog",
)
require(
    'LexeditorUI.noImage("Inventory icon is unavailable")' in SOURCE,
    "missing inventory art must use the accessible shared placeholder",
)
require(
    "img.dataset.remoteTried" not in SOURCE,
    "the old split thumbnail-only fallback must not return",
)
require(
    "https://femga.com:8080/images/samples/ui_textures_no_bg/${dict.toLowerCase()}/${id}.png" in SOURCE,
    "existing satchel and other dictionary behavior must remain available",
)

print("RDR2 item icon issue #33 contract: PASS")
