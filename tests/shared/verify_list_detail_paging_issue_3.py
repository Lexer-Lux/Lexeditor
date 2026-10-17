"""Static contract for Lexeditor issue 3 list-detail pagination."""

from pathlib import Path
from plugin_ui import plugin_ui


ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
RDR2 = plugin_ui("rdr2")
RDR = plugin_ui("rdr")
WARBAND = plugin_ui("warband")
ITEMS = RDR2[RDR2.index("function renderItems()") : RDR2.index("async function createNewItem")]
CRAFTING = RDR2[RDR2.index("function renderCrafting()") : RDR2.index("function priceQtyInput")]
LOOT = RDR2[RDR2.index("async function renderLoot()") : RDR2.index("function markLootDirty")]
WEAPONS = RDR2[RDR2.index("async function renderWeapons()") : RDR2.index("function renderProjectileSpeeds")]
PAGED_PRESET = FRAMEWORK[FRAMEWORK.index("const pagedListDetail") : FRAMEWORK.index("const integrationStatus")]
WHEEL_PAGES = FRAMEWORK[FRAMEWORK.index("const wheelPages ="):FRAMEWORK.index("const pagedSectionMemory =")]
WARBAND_ITEMS = WARBAND.split("function renderItems(){",1)[1].split("function warbandEyeIcon(){",1)[0]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("const listDetail" in FRAMEWORK, "shared list-detail component name is missing")
require("const fitListPage" in FRAMEWORK, "shared fitted-page measurement is missing")
require("const pagedListDetail" in FRAMEWORK, "complete shared paged list-detail preset is missing")
require("pagedListDetail," in FRAMEWORK, "paged list-detail preset is not exported")
require("new ResizeObserver" in FRAMEWORK, "fitted pages do not react to layout resizing")
require("clientHeight" in FRAMEWORK, "fitted pages do not measure the real list height")
require("getBoundingClientRect" in FRAMEWORK, "fitted pages do not measure rendered rows")
require('getPropertyValue("--lex-fitted-row-height")' in FRAMEWORK,
        "fitted pages cannot use a page-independent CSS row height")
require("rows.slice(0, 8)" not in FRAMEWORK,
        "fitted page size still depends on the rows on the current page")
require("lex-fitted-page" in FRAMEWORK_CSS, "fitted list overflow contract is missing")
require("overflow-y: hidden" in FRAMEWORK_CSS, "fitted list can still show a vertical scrollbar")
require("--lex-page-position-size: min(20px, calc(var(--lex-pager-bar-height, 6vh) * .5));" in FRAMEWORK_CSS,
        "the shared page-number size must retain its 20px ceiling and fit the pager height")
page_position_css = FRAMEWORK_CSS[FRAMEWORK_CSS.index(".lex-page-position {"):FRAMEWORK_CSS.index(".lex-page-number {")]
require("font-size: var(--lex-page-position-size);" in page_position_css and "line-height: 1;" in page_position_css,
        "the enlarged page number must keep a compact stable line box")
require(".lex-pager .lex-page-position input.lex-page-number {" in FRAMEWORK_CSS,
        "the shared page input selector must outrank plugin toolbar input styling")
page_number_css = FRAMEWORK_CSS[FRAMEWORK_CSS.index(".lex-pager .lex-page-position input.lex-page-number {"):
                                FRAMEWORK_CSS.index(".lex-pager .lex-page-position input.lex-page-number:hover")]
require("font-size: var(--lex-page-position-size);" in page_number_css and "line-height: 1;" in page_number_css,
        "the editable current-page input must not fall back to the small form-control size")
require("const barrelSize = pageSize * barrels" in PAGED_PRESET
        and "records.slice(groupStart + index * pageSize" in PAGED_PRESET,
        "paged list-detail preset does not own its consecutive barrel page slices")
require("records.slice(start, start + pageSize)" not in PAGED_PRESET,
        "the obsolete single-master page slice remains")
require("listDetail(masterNode, detailNode" in PAGED_PRESET,
        "paged list-detail preset does not construct the list-detail view")
require("if (pages > 1 || hasBottomTools) {" in PAGED_PRESET and "const pagerNode = pager(" in PAGED_PRESET,
        "paged list-detail does not keep searchable one-page views in the shared bottom bar")
require("\n    root.append(pager(" not in PAGED_PRESET,
        "paged list-detail still appends the pager unconditionally")
require("fitListPage({" in PAGED_PRESET,
        "paged list-detail preset does not own fitted capacity")
require('change("page"' in PAGED_PRESET and 'change("resize"' in PAGED_PRESET,
        "paged list-detail preset does not own navigation and resize state")
require('wheelPages(masterNode, direction => changePage(page + direction))' in PAGED_PRESET
        and 'node.addEventListener("wheel"' in WHEEL_PAGES and "{passive:false}" in WHEEL_PAGES,
        "paged list-detail does not own cancellable wheel paging")
require("wheelLocked" in WHEEL_PAGES and "wheelQuietTimer" in WHEEL_PAGES,
        "one high-resolution wheel gesture can change several pages")
require("Math.abs(wheelDelta) < 24" in WHEEL_PAGES and "setTimeout" in WHEEL_PAGES,
        "wheel paging does not accumulate small deltas and wait for a quiet boundary")
require('event.target.closest?.("input,select,textarea,[contenteditable=true]")' in WHEEL_PAGES,
        "wheel paging steals gestures from editable controls")
require("step(wheelDelta > 0 ? 1 : -1)" in WHEEL_PAGES,
        "wheel direction is not routed through the shared clamped page change")
require("change: changePage" in PAGED_PRESET,
        "pager buttons and wheel gestures do not use the same page-change path")
require("pageSize=100" not in ITEMS, "RDR2 Items still pins the old 100-row page size")
require("itemPageSize" in ITEMS, "RDR2 Items does not retain its measured page size")
require("LexeditorUI.pagedListDetail" in ITEMS, "RDR2 Items bypasses the shared paged preset")
require("LexeditorUI.fitListPage" not in ITEMS and "LexeditorUI.listDetail" not in ITEMS,
        "RDR2 Items still assembles paging itself")
require("LexeditorUI.pagedListDetail" in LOOT, "RDR2 Loot Tables bypasses the shared paged preset")
require("LexeditorUI.masterDetail" not in LOOT and "scrollTop" not in LOOT,
        "RDR2 Loot Tables still uses its old scrolling list-detail path")
require("lootPageSize" in RDR2, "RDR2 Loot Tables does not retain its measured page size")
require("LexeditorUI.pagedListDetail" in CRAFTING, "RDR2 Crafting bypasses the shared paged preset")
require("LexeditorUI.masterDetail" not in CRAFTING and "previousScroll" not in CRAFTING,
        "RDR2 Crafting still uses its old scrolling list-detail path")
require("craftPageSize" in RDR2, "RDR2 Crafting does not retain its measured page size")
require("Math.max(32, Number(options.fit?.minRowHeight) || 0)" in PAGED_PRESET
        and "const pageSize = Math.min(requestedPageSize, fitCapacity?.capacity || requestedPageSize)" in PAGED_PRESET,
        "shared list masters must bound capacity using a readable minimum row height")
require(".lex-list.lex-fitted-page[data-lex-fixed-rows] > .lex-list-row" in FRAMEWORK_CSS
        and "height:var(--lex-fitted-row-height)" in FRAMEWORK_CSS,
        "all shared fitted list masters must apply their measured row height")
require("master:({rows,selected,select})=>craftingOutputList(" in CRAFTING
        and "return columnList({rows:groups,key:group=>group.key,selected,select," in RDR2,
        "RDR2 Crafting must use the shared column-list sizing contract")
require("LexeditorUI.pagedListDetail({" in WEAPONS and "weaponPageSize" in WEAPONS,
        "RDR2 Weapons still uses the scrolling master-detail path")
require(RDR.count("pagedListDetail({") >= 3,
        "RDR Items, Shops, and Missions must inherit shared fitted paging")
require("masterDetail(master,itemDetail" not in RDR
        and "masterDetail(master,shopDetail" not in RDR
        and "masterDetail(master,missionDetail" not in RDR,
        "RDR still assembles scrolling list-detail views")
# The option order inside the call is not the contract; passing the filtered
# rows to the shared preset is. Matching "pagedListDetail({rows:" pinned the
# first key, so adding any option ahead of it broke a check about paging.
require("pagedListDetail({" in WARBAND_ITEMS and "rows:filtered" in WARBAND_ITEMS
        and "pageSize:state.pageSizes.items" in WARBAND_ITEMS
        and "pageSizes:{items:20,troops:20,upgrades:20," in WARBAND,
        "Warband Items must inherit shared fitted paging")
require('splitKey:`warband-${view}`' in WARBAND and "pageSize:200" not in WARBAND,
        "Warband Troops and Upgrades must not retain the old 200-row scrolling table")

print("PASS: Lexeditor #3 uses one shared, resize-aware paged list-detail preset")
