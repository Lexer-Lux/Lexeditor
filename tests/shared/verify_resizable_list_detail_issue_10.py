from pathlib import Path
from plugin_ui import plugin_ui


ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK_JS = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
RDR2 = plugin_ui('rdr2')
WARBAND = plugin_ui('warband')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require('role: "separator"' in FRAMEWORK_JS,
        "the shared list-detail view must own an accessible separator")
require('const panelLayout = (panels' in FRAMEWORK_JS,
        "the shared panel-layout composer must own resizing")
require('class: "lex-panel-layout-divider"' in FRAMEWORK_JS,
        "the shared separator needs one panel-layout class")
require('"aria-orientation": vertical ? "horizontal" : "vertical"' in FRAMEWORK_JS,
        "the separator must expose the orientation matching its layout")
require('pointerdown' in FRAMEWORK_JS and 'setPointerCapture' in FRAMEWORK_JS,
        "the shared controller must own pointer dragging")
require('keydown' in FRAMEWORK_JS and 'ArrowLeft' in FRAMEWORK_JS and 'ArrowRight' in FRAMEWORK_JS,
        "the shared controller must support keyboard resizing")
require('addEventListener("contextmenu"' in FRAMEWORK_JS,
        "the shared controller must reset the split on right-click")
require('divider.addEventListener("dblclick"' not in FRAMEWORK_JS,
        "double-click must not reset the shared split")
require('localStorage' in FRAMEWORK_JS and 'splitKey' in FRAMEWORK_JS,
        "the shared controller must persist a separate split for each view")
require('.lex-panel-layout {' in FRAMEWORK_CSS and '.lex-panel-layout-divider' in FRAMEWORK_CSS,
        "shared CSS must own every multi-panel layout and handle appearance")
require('panelLayout([listNode, detail]' in FRAMEWORK_JS,
        "the deprecated list-detail wrapper must delegate to the panel composer")
require("minimumSplit" in FRAMEWORK_JS and "minimumFractions" in FRAMEWORK_JS,
        "the shared wrapper must preserve caller-defined responsive split minimums")
require(RDR2.count('splitKey:') >= 4,
        "RDR2 list-detail screens must identify their saved split without local resize code")
crafting=RDR2.split('function craftingOutputList(',1)[1].split('function readonlyCraftingField(',1)[0]
require('return columnList({rows:groups,key:group=>group.key,selected,select,' in crafting,
        "Crafting must use the shared selectable-list master, not only the outer helper")
require('columnList=window.LexeditorUI.columnList' in RDR2.replace(' ',''),
        "Crafting must inherit the shared column-list appearance")
require('craftingOutputTable' not in RDR2,
        "the custom Crafting table master bypasses the standard list-detail appearance")
require(WARBAND.count('splitKey:') >= 2,
        "Warband list-detail screens must identify their saved split without local resize code")

for plugin in (RDR2, WARBAND):
    require('lex-panel-layout-divider' not in plugin and 'lex-panel-layout-dragging' not in plugin,
            "plugins must not implement or style their own panel resize controller")

print("resizable list-detail issue 10 source contract passed")
