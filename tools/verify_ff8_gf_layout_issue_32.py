"""Source and schema contract for Lexeditor issue 32.

The GF screen is not a second data model.  It must render the existing live
kernel section 3 rows and keep the shared typed/provenance control path.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "games" / "ff8" / "editor.html"
GF_SCHEMA = ROOT / "games" / "ff8" / "schema" / "gforce.json"
KERNEL_SCHEMA = ROOT / "games" / "ff8" / "schema" / "kernel_section_fields.json"

EXPECTED_GF_NAMES = [
    "Quezacotl", "Shiva", "Ifrit", "Siren", "Brothers", "Diablos",
    "Carbuncle", "Leviathan", "Pandemona", "Cerberus", "Alexander",
    "Doomtrain", "Bahamut", "Cactuar", "Tonberry King", "Eden",
]
PANEL_ORDER = ["GF Compatibility", "General", "Abilities"]
EXPECTED_FIELD_COUNTS = {
    "GF Compatibility": 16,
    "General": 22,
    "Abilities": 84,
}
EXPECTED_EDITABLE_COUNTS = {
    "GF Compatibility": 16,
    "General": 21,
    "Abilities": 64,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    editor = EDITOR.read_text(encoding="utf-8")
    gforce = json.loads(GF_SCHEMA.read_text(encoding="utf-8"))["gforce"]
    section = json.loads(KERNEL_SCHEMA.read_text(encoding="utf-8"))["3"]
    fields = section["fields"]

    # The shipped section has one row per standard, junctionable GF.  The UI
    # must derive its tabs from these live rows instead of copying this list.
    require([row["id"] for row in gforce] == list(range(16)),
            "gforce.json must contain the 16 unique GF ids 0 through 15")
    require([row["name"] for row in gforce] == EXPECTED_GF_NAMES,
            "gforce.json GF names or order changed")
    require(section["entry_names"] == EXPECTED_GF_NAMES,
            "kernel section 3 names must match the GF lookup")
    require(len(set(section["entry_names"])) == 16,
            "kernel section 3 must expose 16 unique GF names")

    # A single group-based routing pass is safe only when every schema field
    # has a unique identity and belongs to exactly one of the three panels.
    names = [field["name"] for field in fields]
    require(len(fields) == 122 and len(set(names)) == len(fields),
            "kernel section 3 must have 122 uniquely named fields")
    require(Counter(field.get("group") for field in fields) == EXPECTED_FIELD_COUNTS,
            "every kernel section 3 field must route once to Compatibility, General, or Abilities")
    editable = [field for field in fields if not field.get("readonly")]
    require(Counter(field["group"] for field in editable) == EXPECTED_EDITABLE_COUNTS,
            "the 101 editable section 3 fields changed groups")
    require(len(fields) - len(editable) == 21,
            "the schema must retain 21 read-only fields outside the editing control path")

    require('const gfPanelOrder=["GF Compatibility","General","Abilities"]' in editor,
            "GF panels must be ordered Compatibility, General, Abilities")
    require("function renderGFs()" in editor,
            "the GF screen needs its own renderer")
    require("const rows=[...state.data.gfs.rows].sort" in editor
            and "function portraitTabs(view,rows,selected,detailId,select)" in editor
            and "...ordered.map(row=>" in editor,
            "GF subtabs must be generated alphabetically from the 16 live section 3 rows")
    require("state.selected.gfs" in editor,
            "GF subtab selection must use the existing selected-GF state")
    require("gfPanelOrder.map" in editor,
            "the three panels must use the single ordered routing table")
    require("function gfFieldsByPanel(row)" in editor
            and "for(const field of row.fields)" in editor
            and "routed.get(field.group).push(field)" in editor,
            "each live section 3 field must route once by its schema group")
    require("seen.has(field.field)||!routed.has(field.group)" in editor
            and "seen.size!==row.fields.length" in editor,
            "GF routing must reject duplicate, unknown, or omitted fields")
    require('fieldSourceControl(field,"gfs",row.id)' in editor,
            "GF fields must retain the shared typed and provenance control path")
    require('field.formula==="gf_compat"' in editor,
            "GF Compatibility fields must use their player-facing modifier control")
    require("function gfCompatibilityControl(field)" in editor
            and "field.value=Math.round(bounded*10+100)" in editor,
            "GF Compatibility input must convert the decimal player value back to its scaled stored byte")
    require('Math.max(-10,Math.min(15.5' in editor
            and 'type:"text",inputmode:"decimal",value:gfCompatibilityFormat(field.value)' in editor,
            "GF Compatibility input must be a bounded signed decimal modifier")
    require('editable:true' in editor and 'sort:key=>sortGfTable("compatibility",key)' in editor
            and 'sort:key=>sortGfTable("abilities",key)' in editor,
            "GF Compatibility and Abilities must be editable sortable table panels")
    require("gf-compat-sign" not in editor,
            "GF Compatibility must not use a detached plus-sign overlay")
    require("function gfCompatibilityFormat(value)" in editor
            and 'const modifier=(Number(value)-100)/10' in editor,
            "Compatibility values must hide the internal times-ten byte scale")
    require('format=compatibility?gfCompatibilityFormat:' in editor,
            "Vanilla and reference Compatibility values must not expose raw stored bytes")
    require('portraitTabs("gfs",rows,row.id,"gf-detail"' in editor
            and 'role:"tab"' in editor
            and '"aria-selected":String(row.id===selected)' in editor,
            "the 16 GF portrait selectors must be accessible subtabs")
    require('panelLayout(panels,"gf-three-panel"' in editor and 'className:`gf-panel ${className}`' in editor,
            "the GF detail must use the shared three-panel composer")
    require('role:"tabpanel"' in editor,
            "each GF panel must identify itself as a tab panel")

    # Assert the behavior, not the exact helper signature. Shared controls can
    # gain options without invalidating the GF provenance contract.
    require('const compatibility=field.formula==="gf_compat"' in editor
            and 'control=compatibility?gfCompatibilityControl(field):fieldControl(field)' in editor,
            "GF provenance must choose the signed Compatibility control or the existing typed control")
    require("return sourceControl(control,()=>read(field.value),read(vanillaField?.value),references" in editor
            and "format=compatibility?gfCompatibilityFormat:" in editor,
            "GF fields must preserve player-facing current, vanilla, and reference values")
    require('gfs:()=>renderKernel("gfs","GFs")' not in editor,
            "the old generic two-panel GF renderer must not remain active")

    print(json.dumps({
        "gfs": len(EXPECTED_GF_NAMES),
        "panels": PANEL_ORDER,
        "section3Fields": len(fields),
        "fieldsByPanel": dict(Counter(field["group"] for field in fields)),
        "editableRoutedFields": len(editable),
        "editableFieldsByPanel": dict(Counter(field["group"] for field in editable)),
        "preservedReadOnlyFields": len(fields) - len(editable),
        "liveSelection": "state.selected.gfs",
        "controlPath": "fieldSourceControl -> fieldControl + provenanceControl",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
