"""Read-only FF9 feature UI integration guard.

Historically this script rewrote editor.html in CI. That made verification depend
on stale source transforms. The UI is now checked as shipped instead.
"""
from pathlib import Path

source = Path("plugins/ff9/editor.js").read_text(encoding="utf-8")
required = (
    "ImprovedInterface", "BetterEat", "XPBars", "HPMPBars", "RowRework",
    "/api/features/save", "/api/deployment/${action}", "LexeditorUI.reshadeSection",
)
missing = [token for token in required if token not in source]
if missing:
    raise SystemExit("FF9 feature UI integration missing: " + ", ".join(missing))
forbidden = ("can't be bothered", "platform-config", "platformConfigView")
present = [token for token in forbidden if token in source]
if present:
    raise SystemExit("obsolete FF9 feature UI integration present: " + ", ".join(present))
print("FF9 feature UI integration: PASS")
