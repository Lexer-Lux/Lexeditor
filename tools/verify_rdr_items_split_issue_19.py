import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "games" / "rdr" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


rule = re.search(r"\.lex-master-detail\.rdr-split\{([^}]*)\}", SOURCE)
require(rule is not None, "RDR list-detail sizing rule is missing")
require("grid-template-columns" not in rule.group(1),
        "RDR must not replace the shared list-divider-detail grid with two tracks")
require(SOURCE.count('pagedListDetail({') >= 3,
        "RDR Items, Shops, and Missions must keep the shared paged Table + Detail view")
require('splitKey:"rdr-items"' in SOURCE,
        "RDR Items must keep its own shared two-panel split setting")

print("RDR Items split issue 19 source contract passed")
