"""Fail-closed contracts for the FF8 GF/Enemy shared curve layouts.

This intentionally checks the shipped editor/framework source rather than game files.
The Chromium regression job supplies the visual/interaction layer separately.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from plugin_ui import plugin_ui
EDITOR = plugin_ui('ff8')
FRAMEWORK = (ROOT / "ui/framework.js").read_text(encoding="utf-8")
STYLES = (ROOT / "ui/framework.css").read_text(encoding="utf-8")


def require(source: str, needle: str, contract: str) -> None:
    if needle not in source:
        raise AssertionError(f"FF8 editor contract regressed: {contract}")


# #32 — active GF detail is Compatibility / General / Abilities, and the five
# curve coefficients are consumed by General's shared stat-growth controls.
require(EDITOR, 'const layout=panelLayout(panels,"gf-three-panel",{layoutKey:"ff8-gfs",defaultSizes:[.9,1.05,1.4],minSizes:[230,245,470],stackAt:1000});', "GF three-panel layout")
require(EDITOR, 'table.dataset.gfPanel="compatibility"', "GF Compatibility panel marker")
require(EDITOR, 'attrs:{"data-gf-panel":"abilities"}', "GF Abilities panel marker")
require(EDITOR, 'const growth=className==="general"?gfStatGrowth(curveFields,row.id):null;', "GF curves routed through General/shared controls")
require(EDITOR, 'const GF_CURVE_FIELDS=["gf_hp_modifier_1","gf_hp_modifier_2","gf_hp_modifier_3","gf_level_modifier_1","gf_level_modifier_2"]', "all five GF curve coefficients")

# #39 — Enemy Stats/AI/Battle Text share the dedicated leading pane. Stats uses
# shared stat-growth instead of the obsolete black curve prototype.
require(EDITOR, 'function enemyLeadingPanel(row){return enemyAiPanel(row)}', "Enemy dedicated AI panel")
require(EDITOR, "label:'Enemy details'", "Enemy detail tabs")
require(EDITOR, "else if(tab==='text')body=[enemyBattleTextPanel(row,prefs)]", "Enemy text tab")
require(EDITOR, "enemyStatGrowth(row.fields.filter(field=>field.group==='Stat curves'),row.id)", "Enemy shared stat-growth graph")
require(EDITOR, '{leadingPanel:enemyLeadingPanel,minLeading:460,panelSizes:[48,18,34],minLeft:220,minRight:430}', "Enemy paged layout attachment")

# #60 — no white prototype fill; heading, variables, plot and formula are
# separate grid rows; the title is centered and pointer-safe; shared hover
# re-evaluates the current curve rather than a stale preview.
require(EDITOR, '--lex-curve-fill:#aa243266;', "FF8 game-coloured curve fill")
require(FRAMEWORK, 'class: "lex-curve-heading-formula"', "accessible curve formula")
require(STYLES, '.lex-curve-heading', "shared curve heading")
require(FRAMEWORK, 'const curveEditor = (options = {}) => {', "shared live curve editor")
require(FRAMEWORK, 'root.addEventListener("pointermove", event => {', "shared curve hover")
require(FRAMEWORK, 'const raw = options.evaluate?.(x);', "live curve evaluation")

print("PASS FF8 GF/Enemy shared curve layout and presentation contracts")
