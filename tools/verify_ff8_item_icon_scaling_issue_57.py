"""Source contract for FF8 item-icon text-relative scaling (GitHub #57)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("--ff8-item-icon-size:1.4em" in EDITOR,
        "FF8 item icons do not derive their size from surrounding text")
require("width:var(--ff8-item-icon-size)" in EDITOR and
        "height:var(--ff8-item-icon-size)" in EDITOR,
        "The shared FF8 item-icon slot does not use the relative size token")
require("grid-template-columns:var(--ff8-item-icon-size) minmax(0,1fr)" in EDITOR,
        "FF8 item selectors do not share the relative icon size")
require("width:100%;height:100%;object-fit:contain" in EDITOR,
        "The item bitmap does not fill and preserve the shared relative slot")
require("max-width:22px" not in EDITOR and "max-width:28px" not in EDITOR,
        "A fixed-size FF8 item-icon rule remains")
require(".detail-head .ff8-item-icon-slot" not in EDITOR,
        "The detail heading still owns a private pixel icon override")

print("FF8 item-icon scaling issue #57 source contract passed")
