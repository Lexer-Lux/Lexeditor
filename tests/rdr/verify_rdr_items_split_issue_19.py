from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STYLE = (ROOT / "plugins" / "rdr" / "editor.css").read_text(encoding="utf-8")
SOURCE = (ROOT / "plugins" / "rdr" / "editor.js").read_text(encoding="utf-8")
STRINGS = (ROOT / "plugins" / "rdr" / "strings.js").read_text(encoding="utf-8")
RBF = (ROOT / "plugins" / "rdr" / "rbf.js").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require(".lex-" not in STYLE,
        "RDR must not override shared component selectors in its game stylesheet")
require(SOURCE.count("pagedListDetail({") >= 3,
        "RDR Items, Shops, and Missions must keep shared paged Table + Detail views")
require("pagedListDetail({" in STRINGS and "columnList({" in STRINGS,
        "RDR Strings must keep the shared paged Table + Detail view")
for key in ("rdr-items", "rdr-shops", "rdr-missions"):
    require(f'splitKey:"{key}"' in SOURCE,
            f"RDR {key} must keep its own shared two-panel split setting")
require('splitKey:"rdr-strings"' in STRINGS,
        "RDR Strings must keep its own shared two-panel split setting")
require("pagedListDetail({" in RBF and "columnList({" in RBF and 'splitKey:"rdr-rbf"' in RBF,
        "RDR RBF0 Scalars must keep the shared paged Table + Detail view")
require("columnList({" in SOURCE,
        "RDR record tables must use the shared column list")

print("RDR shared Table + Detail paging contract passed")
