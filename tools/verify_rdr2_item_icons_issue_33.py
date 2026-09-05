"""Contract for RDO inventory icon resolution and explicit failure states."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


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
    "button.disabled=true;button.onclick=null" in SOURCE,
    "an unavailable icon must not leave a clickable blank preview",
)
require(
    'button.setAttribute("aria-label","Inventory icon is unavailable")' in SOURCE,
    "the unavailable state must be explicit to assistive technology",
)
require(
    "button.replaceChildren(brokenImageIcon())" in SOURCE,
    "the detail must show an intentional broken-image glyph",
)
require(
    "button.onclick=()=>showItemIcon(texture,it,src)" in SOURCE,
    "the dialog must receive only a source that passed image decoding",
)
require(
    "The verified inventory icon became unavailable" in SOURCE,
    "a later network failure in the dialog must have intentional error UI",
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
