"""Fail-closed contracts for the FF8 GF/Enemy shared curve layouts.

This intentionally checks the shipped editor/framework source rather than game files.
The Chromium regression job supplies the visual/interaction layer separately.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
FRAMEWORK = (ROOT / "ui/framework.js").read_text(encoding="utf-8")
STYLES = (ROOT / "ui/framework.css").read_text(encoding="utf-8")


def require(source: str, needle: str, contract: str) -> None:
    if needle not in source:
        raise AssertionError(f"FF8 editor contract regressed: {contract}")


# #32 — active GF detail is Compatibility / General / Abilities, and the five
# curve coefficients are consumed by General's shared stat-growth controls.
require(EDITOR, 'const layout=panelLayout(panels,"gf-three-panel",{layoutKey:"ff8-gfs",defaultSizes:[.9,1.05,1.4],minSizes:[230,245,470],stackAt:1000});', "GF three-panel layout")
require(EDITOR, 'attrs:{"data-gf-panel":"compatibility"}', "GF Compatibility panel marker")
require(EDITOR, 'attrs:{"data-gf-panel":"abilities"}', "GF Abilities panel marker")
require(EDITOR, 'const growth=className==="general"?gfStatGrowth(curveFields,row.id):null;', "GF curves routed through General/shared controls")
require(EDITOR, 'const GF_CURVE_FIELDS=["gf_hp_modifier_1","gf_hp_modifier_2","gf_hp_modifier_3","gf_level_modifier_1","gf_level_modifier_2"]', "all five GF curve coefficients")

# #39 — Enemy Stats/AI/Battle Text share the dedicated leading pane. Stats uses
# shared stat-growth instead of the obsolete black curve prototype.
require(EDITOR, 'function enemyLeadingPanel(row,prefs)', "Enemy dedicated leading panel")
require(EDITOR, 'className:"enemy-tabbed-column"', "Enemy Stats/AI/Battle Text tabbed pane")
require(EDITOR, 'contentClassName:state.enemyPanelTab==="stats"?"enemy-curve-column":""', "Enemy curve pane marker")
require(EDITOR, 'row.available?enemyStatGrowth(row.fields.filter(field=>field.group==="Stat curves"),row.id)', "Enemy shared stat-growth graph")
require(EDITOR, 'showPaged("enemies",rows,columns,enemyDetail,"74px minmax(180px,1fr)",{leadingPanel:enemyLeadingPanel,minLeading:340,defaultLeadingWidth:30,minLeft:260,minRight:430})', "Enemy paged layout attachment")

# #60 — no white prototype fill; heading, variables, plot and formula are
# separate grid rows; the title is centered and pointer-safe; shared hover
# re-evaluates the current curve rather than a stale preview.
require(EDITOR, '--lex-curve-fill:#aa243266;', "FF8 game-coloured curve fill")
require(STYLES, 'grid-template-areas:\n    "heading"\n    "variables"\n    "plot"\n    "formula"\n    "status";', "curve heading/formula separated into distinct rows")
require(EDITOR, '.ff8-character-curve .lex-curve-heading{', "FF8 curve heading override")
require(EDITOR, 'display:flex;justify-content:center;', "centered FF8 curve heading")
require(EDITOR, 'pointer-events:none;', "pointer-safe FF8 curve presentation")
require(FRAMEWORK, 'const curveEditor = (options = {}) => {', "shared live curve editor")
require(FRAMEWORK, 'root.addEventListener("pointermove", event => {', "shared curve hover")
require(FRAMEWORK, 'const y = Number(options.evaluate?.(x));', "live curve evaluation")

print("PASS FF8 GF/Enemy shared curve layout and presentation contracts")
