"""FF8 toolbar source-label contract for GitHub issue 38."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
FORMATS = (ROOT / "games" / "ff8" / "formats.py").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


for start, end, name in (
    ("function renderItems()", "function itemDetail", "Items"),
    ("function renderShops()", "function shopDetail", "Shops"),
    ("function renderWeapons()", "function weaponDataField", "Weapons"),
    ("function renderKernel(view,label)", "function matchingTextRow", "generic kernel tabs"),
):
    source = EDITOR[EDITOR.index(start):EDITOR.index(end)]
    require(".source" not in source,
            f"{name} still renders internal dataset source metadata")
    require('class:"count"' not in source,
            f"{name} still reserves a toolbar caption for its dataset source")

require("function sourceControl(" in EDITOR and "LexeditorUI.provenanceControl" in EDITOR,
        "field-level Vanilla/reference provenance was removed with the toolbar labels")
require('"source": source_label(' in FORMATS and '"recipe": source_label(' in FORMATS,
        "backend source metadata was removed instead of only hiding its toolbar caption")

print("PASS: FF8 hides internal dataset sources in toolbars and keeps field provenance")
