from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require(".shop-picker-total { color:color-mix(" in SOURCE,
        "the shop total must derive from the active theme accent")
require("var(--accent2)" in SOURCE and "var(--bg)" in SOURCE,
        "the dynamic total color must mix the active accent with the theme background")
require(".shop-picker-row { display:block; padding:7px 10px;" in SOURCE,
        "shop rows must use the requested modestly tighter vertical padding")
require("text-align:center" in SOURCE,
        "the shop picker must center its two row lines")
require(".shop-picker-row .shop-name { display:block; font:400 16px/1.05 var(--rdr-font-display);" in SOURCE,
        "shop names must use the regular display face instead of synthetic heavy text")
require("font-weight:800" not in SOURCE[SOURCE.index(".shop-picker-row .shop-name"):SOURCE.index(".shop-requirement-grid")],
        "the shop picker must not restore synthetic heavy weight")
require("font:400 10.5px/1.15 var(--rdr-font-body)" in SOURCE,
        "shop summaries must be slightly larger and use the regular body face")
require("`${explicit}+ buys · ${row.shop?.items.length||0} sells`" in SOURCE,
        "shop summaries must use X+ buys wording")
require("explicit buys" not in SOURCE,
        "the old explicit-buys wording must not return")
require(".shop-catalogue-tabs { display:grid; grid-template-columns:repeat(var(--shop-tab-count),minmax(0,1fr));" in SOURCE,
        "both SELLS catalogue levels must share the full-width equal-column grid")
require(".shop-catalogue-tabs button { width:100%; min-width:0;" in SOURCE and "text-align:center" in SOURCE,
        "catalogue tabs must fill their equal grid cells and center their labels")
require("style:`--shop-tab-count:${topCount}`" in SOURCE and
        "style:`--shop-tab-count:${secondCount}`" in SOURCE,
        "each catalogue level must set its own dynamic equal-column count")
catalogue_css = SOURCE[SOURCE.index(".shop-catalogue-tabs {"):SOURCE.index(".shop-item-conditions {")]
require("display:flex" not in catalogue_css and "overflow-x:auto" not in catalogue_css,
        "the old left-packed scrolling catalogue-tab layout must not return")

print("RDR2 shop picker issue 15 source contract passed")
