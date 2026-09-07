"""Reject FF7-only presentation drift from the shared Blank/UI framework."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FF7 = ROOT / "games" / "ff7" / "editor.html"
BLANK = ROOT / "games" / "blank" / "editor.html"


def main() -> None:
    ff7 = FF7.read_text(encoding="utf-8")
    blank = BLANK.read_text(encoding="utf-8")

    style_match = re.search(r"<style>(.*?)</style>", ff7, re.S)
    if not style_match:
        raise AssertionError("FF7 editor must retain the shared page-frame CSS block")
    style = style_match.group(1)

    # FF7 may own page framing, but not private restyles of shared controls.
    forbidden_style = (
        ".ff7-", "#ff7-", ".lex-detail-", ".lex-column-", ".lex-subtab-",
        ".lex-source-", ".lex-reference-", ".lex-data-map-", ".lex-platform-",
    )
    found = [token for token in forbidden_style if token in style]
    if found:
        raise AssertionError("FF7 contains private shared-control CSS overrides: " + ", ".join(found))

    # The neutral page frame is copied exactly from Blank; only the shared
    # controls beneath it are allowed to determine panel/table/detail styling.
    required_frame = (
        "*{box-sizing:border-box}",
        "body{display:flex;flex-direction:column;height:100vh;margin:0;overflow:hidden;color:var(--lex-text);background:var(--lex-bg);font:15px/1.35 var(--lex-font)}",
        ".lex-shell-command-row{background:#fff}",
        ".lex-nav-frame,.lex-shell-header nav{background:#e5e9ed}",
        "main{flex:1;min-height:0;padding:var(--lex-panel-gap)}",
    )
    for rule in required_frame:
        if rule not in blank:
            raise AssertionError(f"Blank no longer contains canonical page-frame rule: {rule}")
        if rule not in ff7:
            raise AssertionError(f"FF7 does not use Blank's canonical page-frame rule: {rule}")

    # Nested navigation belongs to the shared helpers, not hand-authored bars.
    for legacy in (
        'class:"lex-subtab-bar ff7-subtabs"',
        'class:"lex-subtab-button"',
        'class:"ff7-map-controls"',
        'class:"ff7-tweak-panel"',
    ):
        if legacy in ff7:
            raise AssertionError(f"FF7 still hand-builds shared UI markup: {legacy}")

    required_helpers = (
        "subtabBar", "tabbedPanel", "detailPanel", "detailSection", "detailField",
        "columnList", "pagedListDetail", "readonlyField", "infoIcon",
    )
    missing = [name for name in required_helpers if name not in ff7]
    if missing:
        raise AssertionError("FF7 stopped using required shared UI helpers: " + ", ".join(missing))

    print("FF7 Blank UI contract: no FF7-specific shared-control CSS or private subtab markup")


if __name__ == "__main__":
    main()
