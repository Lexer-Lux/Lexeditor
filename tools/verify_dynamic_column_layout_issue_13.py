from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_JS = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
RDR2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("const dynamicColumnTemplate" in FRAMEWORK_JS,
        "the shared column list must own its dynamic sizing policy")
require('"max-content"' in FRAMEWORK_JS and "minmax(0," in FRAMEWORK_JS,
        "metadata must size to content while a flexible column takes the remainder")
require("style: `--lex-column-list-template:" in FRAMEWORK_JS,
        "the common track template must live on the parent column list")
require(re.search(r"\.lex-column-list\s*\{[^}]*display\s*:\s*grid", FRAMEWORK_CSS, re.S),
        "the complete visible page must participate in one parent grid")
require("grid-template-columns: subgrid" in FRAMEWORK_CSS,
        "headers and every row must share the parent tracks")
require(re.search(r"\.lex-column-list-head-cell,[^}]*\.lex-column-list-cell\s*\{[^}]*text-align\s*:\s*center", FRAMEWORK_CSS, re.S),
        "table headers and cells must center by default")
require("lex-column-align-${" in FRAMEWORK_JS and ".lex-column-align-start" in FRAMEWORK_CSS,
        "long prose columns must have an explicit start-alignment escape hatch")
require('align:"start"' in FRAMEWORK_JS,
        "Data Map must explicitly retain readable start alignment")
require('class:"loot-list loot-table-column-list"' in RDR2 and "LexeditorUI.columnList({" in RDR2,
        "Loot Tables must use the shared column-list component")
require("grid-template-columns:1fr 42px 84px" not in RDR2,
        "the fixed Loot Tables tracks must be removed")

print("dynamic centered column layout issue 13 source contract passed")
