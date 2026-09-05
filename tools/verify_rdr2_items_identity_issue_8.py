from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require('class:"loot-list list-4col"' in SOURCE,
        "Items must select the four-column master layout")
require('el("span",{},"Name / Item"),el("span",{},"ID"),el("span",{},"Group"),el("span",{},"Category")' in SOURCE,
        "Items must declare the requested master-column order")
require('class:"item-list-name"' in SOURCE and 'class:"item-list-id"' in SOURCE,
        "the name and ID must be separate master cells")
require('class:"item-list-group"' in SOURCE and 'class:"item-list-category"' in SOURCE,
        "the group and category must be separate master cells")
require(".loot-list.list-4col" in SOURCE,
        "the four-column master needs an explicit grid contract")
require('class: "detail-field item-name-field"' in SOURCE,
        "the identity segment must have its own full-width detail field")
require('class: "item-meta-line"' in SOURCE,
        "the identity block must have one aligned metadata row")
require('class: "item-meta-taxonomy"' in SOURCE,
        "Group and Category must share the right side of the metadata row")
require('.item-meta-separator::before { content:"\\00B7"; }' in SOURCE,
        "the interpunct must use an ASCII CSS escape outside the RDR Lino glyph map")
require('field("In-game name / item",cells.identity)' not in SOURCE,
        "the redundant identity label must be removed")
require('field("Description",cells.description)' in SOURCE,
        "the description label must use the requested short name")
require(".item-name-field .localized-name" in SOURCE and "var(--rdr-font-display)" in SOURCE,
        "the item name input must use the larger RDR2 display treatment")
require('grid-template-columns:16px minmax(0,1fr)' in SOURCE,
        "every origin-aware name must reserve the same fixed-width marker slot")
require('class:"origin-slot"' in SOURCE and 'class:"origin-name-text"' in SOURCE,
        "origin-aware names must keep the optional marker separate from aligned text")
require('el("span",{class:"origin-slot","aria-hidden":"true"},originMarker(record))' in SOURCE,
        "the marker slot must exist even when a record has no origin icon")
require("grid-template-columns:48px minmax(0,1fr)" not in SOURCE,
        "the item icon must not remain trapped in a fixed 48-pixel column")
require(".item-identity { display:flex" in SOURCE and "align-items:flex-start" in SOURCE,
        "the identity header must keep the square icon aligned with the content top")
require(".item-identity-main { flex:1 1 0; min-width:0; }" in SOURCE,
        "the name and metadata must retain the flexible remainder of the header")
require("--item-icon-size" in SOURCE and "function sizeItemIdentityIcon(identity,main)" in SOURCE,
        "the icon size must follow the rendered identity-content height")
require("Math.max(48,Math.min(96,main.getBoundingClientRect().height))" in SOURCE,
        "the adaptive icon must keep the 48-96 pixel bounds")
require("aspect-ratio:1" in SOURCE and "max-width:96px" in SOURCE and "max-height:96px" in SOURCE,
        "the expanding icon must stay square and keep a safe upper bound")
require("function rdrSearchField({" in SOURCE,
        "RDR2 search fields must share one magnifier/input component")
require("itemSearchText" in SOURCE and 'className:"shop-panel-search"' in SOURCE,
        "Items must search through the shared pager and Shops through rdrSearchField")
require('class:"record-toolbar"' in SOURCE,
        "the Items controls must use the shared record toolbar")
require("item-toolbar-center" not in SOURCE and "item-toolbar-controls" not in SOURCE,
        "the retired three-zone toolbar rules must not return")
require('class:"item-toolbar-filters"' in SOURCE,
        "the three Items dropdown filters must remain one right-aligned group")
require('class:"item-toolbar-meta toolbar-context-slot"' in SOURCE,
        "Items metadata and help must not disrupt the three primary alignment zones")
require("transform:translateY(-1px)" in SOURCE,
        "the magnifier needs the optical vertical correction shown by the reference image")
require('class:"item-identity-actions"' in SOURCE,
        "the item lookup and preview controls must share one vertical action rail")
require('.item-identity-actions { grid-column:3; grid-row:1 / span 2; display:grid; grid-template-rows:repeat(2,26px)' in SOURCE,
        "the item action rail must stack two equal controls vertically")
require('grid-template-columns:18px minmax(0,1fr) 26px' in SOURCE,
        "the item identity grid must reserve one action column, not two side-by-side buttons")

print("RDR2 Items identity issue 8 source contract passed")
