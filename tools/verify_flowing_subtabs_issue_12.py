from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RDR2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require(RDR2.count('class:"subtabs') >= 8,
        "RDR2 pages must continue to share the standard subtab class")
require(re.search(r"\.subtabs\s*\{[^}]*background\s*:\s*var\(--accent\)", RDR2, re.S),
        "the complete shared subtab strip must use the RDR2 accent surface")
require(re.search(r"\.subtabs button\s*\{[^}]*background\s*:\s*transparent", RDR2, re.S),
        "child tabs must remain transparent inside the continuous strip")
require(re.search(r"\.subtabs button\.active\s*\{[^}]*background\s*:\s*transparent", RDR2, re.S),
        "the active child must not become another red block")
require(re.search(r"\.subtabs button\.active::after\s*\{[^}]*background\s*:\s*var\(--text\)", RDR2, re.S),
        "the active child must have a light underline marker")
require(".subtabs button:focus-visible" in RDR2,
        "keyboard focus must remain visible on the red strip")
require(".subtabs button.active { color:#fff; background:var(--accent); }" not in RDR2,
        "the old independent active-child block must be removed")

print("flowing RDR2 subtabs issue 12 source contract passed")
