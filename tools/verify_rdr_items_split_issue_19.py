import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = {name: (ROOT / "games" / "rdr" / f"{name}.js").read_text(encoding="utf-8")
           for name in ("items", "shops", "missions")}
CSS = (ROOT / "games" / "rdr" / "editor.css").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# Items, Shops, and Missions keep the shared paged Table + Detail view: one
# shared pagedListDetail call per module, each with its own split setting, all
# carrying the rdr-split hook the page frame keys off.
for name, source in MODULES.items():
    require(source.count("pagedListDetail({") == 1,
            f"RDR {name} must keep one shared paged Table + Detail view")
    require(f'splitKey:"rdr-{name}"' in source or
            f"splitKey:'rdr-{name}'" in source,
            f"RDR {name} must keep its own shared two-panel split setting")
    require('className:"rdr-split"' in source or "className:'rdr-split'" in source,
            f"RDR {name} must keep the rdr-split view hook")
# Sizing lives in the shared list-detail component now (see the shared editor
# layouts fix): RDR must not replace it with its own two-track grid, in either
# its stylesheet or its view modules.
combined = CSS + "\n".join(MODULES.values())
require("grid-template-columns" not in combined,
        "RDR must not replace the shared list-divider-detail grid with two tracks")

print("RDR Items split issue 19 source contract passed")
