"""Fail-closed contracts for the FF8 GF/Enemy shared curve layouts.

This intentionally checks the shipped editor/framework source rather than game files.
The Chromium regression job supplies the visual/interaction layer separately.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
FRAMEWORK = (ROOT / "ui/framework.js").read_text(encoding="utf-8")


def require(source: str, needle: str, contract: str) -> None:
    if needle not in source:
        raise AssertionError(f"FF8 editor contract regressed: {contract}")


# #32 — the active GF renderer is a three-pane layout, not the old two-column
# prototype. Compatibility stays left, General (including shared curves) stays
# center, and Abilities stays right.
require(
    EDITOR,
    'const layout=panelLayout(panels,"gf-three-panel",{layoutKey:"ff8-gfs",defaultSizes:[.9,1.05,1.4],minSizes:[230,245,470],stackAt:1000});',
    "GF detail must use the three-panel Compatibility / General / Abilities layout",
)
require(EDITOR, 'attrs:{"data-gf-panel":"compatibility"}', "GF Compatibility panel marker")
require(EDITOR, 'attrs:{"data-gf-panel":"abilities"}', "GF Abilities panel marker")
require(
    EDITOR,
    'const growth=className==="general"?gfStatGrowth(curveFields,row.id):null;',
    "GF stat curves must be rendered through the General panel's shared curve controls",
)
require(
    EDITOR,
    'const GF_CURVE_FIELDS=["gf_hp_modifier_1","gf_hp_modifier_2","gf_hp_modifier_3","gf_level_modifier_1","gf_level_modifier_2"]',
    "all five GF curve coefficients must remain routed through the shared curve controls",
)

# #39 — Enemy Stats/AI/Battle Text occupy the dedicated leading pane while
# the ordinary enemy detail remains the second pane. The stats tab specifically
# contains the shared stat-growth graph; AI/text use the same pane rather than
# creating the obsolete black prototype panel.
require(EDITOR, 'function enemyLeadingPanel(row,prefs)', "Enemy dedicated leading panel")
require(EDITOR, 'className:"enemy-tabbed-column"', "Enemy Stats/AI/Battle Text tabbed pane")
require(EDITOR, 'contentClassName:state.enemyPanelTab==="stats"?"enemy-curve-column":""', "Enemy curve pane marker")
require(
    EDITOR,
    'row.available?enemyStatGrowth(row.fields.filter(field=>field.group==="Stat curves"),row.id)',
    "Enemy Stats tab must render the shared stat-growth graph",
)
require(
    EDITOR,
    'showPaged("enemies",rows,columns,enemyDetail,"74px minmax(180px,1fr)",{leadingPanel:enemyLeadingPanel,minLeading:340,defaultLeadingWidth:30,minLeft:260,minRight:430})',
    "Enemy page must attach the tabbed curve/AI/text pane through the shared paged layout",
)

# #60 — the old white block-fill prototype and overlapping title/formula are
# explicitly forbidden. FF8 uses a translucent game-red fill, a centered
# pointer-safe title row, and the equation is not laid over the chart/title.
# Live graph hover evaluation is provided by the shared framework curve editor.
require(EDITOR, '--lex-curve-fill:#aa243266;', "FF8 curve fill must remain game-coloured rather than white")
require(EDITOR, '.curve-editor-formula{display:none;}', "curve equation must not overlap the chart/title")
require(
    EDITOR,
    '.level-curve-panel .detail-subtitle{position:relative;z-index:2;margin:0 auto;text-align:center;pointer-events:none;',
    "curve title must remain centered and pointer-safe above the chart",
)
require(FRAMEWORK, 'const curveEditor = (options = {}) => {', "shared live curve editor")
require(FRAMEWORK, 'root.addEventListener("pointermove", event => {', "shared curve hover must update live")
require(FRAMEWORK, 'const y = Number(options.evaluate?.(x));', "shared curve hover must evaluate current edited coefficients")

print("PASS FF8 GF/Enemy shared curve layout and presentation contracts")
