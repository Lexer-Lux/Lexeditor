from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_JS = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
RDR2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")
WARBAND = (ROOT / "games" / "warband" / "editor.html").read_text(encoding="utf-8")
BLANK = (ROOT / "games" / "blank" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("const columnList = options =>" in FRAMEWORK_JS,
        "the shared framework must own one sortable column-list primitive")
require("const root = list({" in FRAMEWORK_JS and "return root;" in FRAMEWORK_JS and "lex-column-list" in FRAMEWORK_JS,
        "the sortable column list must build on the standard shared list")
require("columnList," in FRAMEWORK_JS,
        "the shared column-list primitive must be exported")
exports = FRAMEWORK_JS.rsplit("window.LexeditorUI = {", 1)[1].split("};", 1)[0]
require("const table = options =>" not in FRAMEWORK_JS and not re.search(r"(?:^|,)\s*table\s*(?:,|$)", exports),
        "the old shared table primitive must be deleted, not deprecated")
require(".lex-table" not in FRAMEWORK_CSS and "lex-table-wrap" not in FRAMEWORK_CSS,
        "the old table component CSS must be deleted")
require("LexeditorUI.table(" not in RDR2 and "craftingOutputTable" not in RDR2,
        "RDR2 must not use the old shared table path")
require("function effectColumnList(" in RDR2 and "function effectDetail(" in RDR2,
        "Effects must be a shared column-list master plus detail editor")
require(RDR2.count("LexeditorUI.pagedListDetail({") >= 5,
        "Effects and Behaviors must join the shared paged list-detail preset")
require("columnList" in WARBAND and "table" not in WARBAND.split("const {", 1)[1].split("}=LexeditorUI", 1)[0],
        "Warband must consume the column-list replacement")
require(re.search(r"const\s+\w+\s*=\s*columnList\(\{[\s\S]*?class:\s*[\"']lex-data-map-table", FRAMEWORK_JS) is not None,
        "Data Map must use the column-list replacement")
require('sort={key:"name",dir:1}' in BLANK and "sortState:sort" in BLANK and "sort:key=>" in BLANK,
        "Blank Game must demonstrate persistent default shared sorting")
require('onclick: event => {\n          if (!sortable || event.target.closest(".lex-info-help,.lex-column-pin")) return;' in FRAMEWORK_JS,
        "the complete visible header cell must activate sorting, except its help and pin controls")
require('title: `Sort by ${typeof column.label === "string" ? column.label : column.key}`,\n          }, label)' in FRAMEWORK_JS,
        "the inner label button must bubble one click to the header instead of owning a second sort handler")

print("column-list unification issue 11 source contract passed")
