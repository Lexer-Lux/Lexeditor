"""Shared multi-panel composition contract for Lexeditor issue 46."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
rdr2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")
blank = (ROOT / "games" / "blank" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("const panelLayout = (panels" in framework,
        "the shared framework needs one panel-layout composer")
require('class: "lex-panel-layout-divider"' in framework,
        "the composer must insert shared dividers")
require("nodes.length" in framework and "nodes.length - 1" in framework,
        "the composer must support every multi-panel count")
require("panelLayout([listNode, detail]" in framework,
        "the compatibility list-detail wrapper must delegate")
require("panelLayout([issueList, editor, commentsPanel]" in framework,
        "the GitHub three-panel layout must use the composer")
require('panelLayout(panels,"gf-three-panel"' in ff8,
        "FF8 GF panels must use the composer")
require('panelLayout([buys,picker,sells],"shop-workspace"' in rdr2,
        "RDR2 Shop panels must use the composer")
for required in (
    'panelLayout([galleryPanel()],"blank-layout"',
    'pagedListDetail({rows:records',
    'panelLayout([tablePanel(),recordPanel(),inspectorPanel()],"blank-layout"',
    'panelLayout([subtabPanel()],"blank-layout"',
):
    require(required in blank, "Blank Game must demonstrate every shared panel count")
require("const subtabBar = (options" in framework and "subtabBar," in framework,
        "nested navigation must use one exported shared subtab control")
require("const tabbedPanel = (options" in framework and "tabbedPanel," in framework,
        "tabbed panels must have one exported shared component")
require('tabbedPanel({className:"blank-subtab-panel"' in blank,
        "Blank Game must demonstrate the shared tabbed panel")
require('label:"Tabbed Panel"' in blank,
        "Blank Game must name the tabbed-panel example clearly")
require(".lex-panel-layout" in css and ".lex-panel-layout-divider" in css,
        "shared CSS must own layout and divider appearance")
require(".lex-subtab-bar" in css and ".lex-subtab-button.active" in css,
        "shared CSS must own nested navigation appearance")
for plugin in (ff8, rdr2, blank):
    require("lex-panel-layout-divider" not in plugin,
            "plugins must not create or style divider markup")

print("Shared multi-panel layout issue 46 contract passed")
