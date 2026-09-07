"""Reject FF7 presentation drift from the Blank/shared neutral UI contract."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FF7 = ROOT / "games" / "ff7" / "editor.html"
BLANK = ROOT / "games" / "blank" / "editor.html"
NEUTRAL = ROOT / "ui" / "neutral.css"


def compact(value: str) -> str:
    return "".join(value.split())


def main() -> None:
    ff7 = FF7.read_text(encoding="utf-8")
    blank = BLANK.read_text(encoding="utf-8")
    neutral = NEUTRAL.read_text(encoding="utf-8")

    # "Blank UI, no overrides" is literal for FF7: it may supply data/classes
    # for semantics/testing, but it owns no CSS at all.
    if "<style" in ff7.casefold() or "style=" in ff7.casefold():
        raise AssertionError("FF7 contains local CSS/style overrides")
    for marker in (
        '<link rel="stylesheet" href="/shared/framework.css">',
        '<link rel="stylesheet" href="/shared/neutral.css">',
        '<body class="lex-neutral-ui">',
    ):
        if marker not in ff7:
            raise AssertionError(f"FF7 is not consuming the shared neutral UI: {marker}")

    # neutral.css is shared infrastructure, never a disguised FF7/Blank patch.
    lower_neutral = neutral.casefold()
    for token in (".ff7-", "#ff7-", ".blank-", "#blank-"):
        if token in lower_neutral:
            raise AssertionError(f"Shared neutral stylesheet contains plugin-specific selector {token}")

    # These declarations are the existing Blank visual baseline promoted into
    # shared neutral.css. If Blank's benchmark changes, this guard forces the
    # shared neutral contract to be updated rather than letting FF7 drift.
    blank_compact = compact(blank)
    neutral_compact = compact(neutral)
    blank_baseline_declarations = (
        "--lex-accent:#72ff1e;--lex-accent-text:#102008;--lex-highlight:#405247",
        "padding:4px 18px 4px 4px;border-bottom:1px solid var(--lex-border);background:#f1f3f5",
        "display:grid;width:auto;height:100%;aspect-ratio:1;place-items:center;color:var(--lex-accent);border:1px solid var(--lex-border);background:#fff",
        "width:64%;height:64%;fill:none;stroke:currentColor;stroke-width:1.7",
        "width:1em;min-width:1em;height:1em;min-height:1em;flex-basis:1em",
        "width:.95em;height:.95em",
        "right:.35em",
        "margin-right:.08em",
        "padding:10px;gap:10px",
        "flex:1 1 auto",
        "padding:12px",
        "display:flex;flex-direction:column;height:100%;min-height:0;border:1px solid var(--lex-border);background:var(--lex-panel)",
        "display:block;font-size:1.45em;text-align:center",
    )
    for declaration in blank_baseline_declarations:
        normalized = compact(declaration)
        if normalized not in blank_compact:
            raise AssertionError(f"Blank benchmark changed without updating the shared neutral contract: {declaration}")
        if normalized not in neutral_compact:
            raise AssertionError(f"neutral.css does not reproduce Blank's benchmark declaration: {declaration}")

    # FF7's master/detail geometry uses Blank's own paged two-panel defaults.
    layout_contract = (
        "slots:false",
        "pageSize:state.pageSize[group]||12",
        "defaultSplit:50",
        "minLeft:320",
        "minRight:360",
    )
    missing_layout = [value for value in layout_contract if value not in ff7]
    if missing_layout:
        raise AssertionError("FF7 master/detail geometry drifted from Blank: " + ", ".join(missing_layout))

    # Nested navigation and ordinary content must be shared helpers, not local
    # approximations with subtly different DOM/keyboard behavior.
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
    missing_helpers = [name for name in required_helpers if name not in ff7]
    if missing_helpers:
        raise AssertionError("FF7 stopped using required shared UI helpers: " + ", ".join(missing_helpers))

    print("FF7 Blank UI contract: zero local CSS, shared neutral presentation, Blank geometry")


if __name__ == "__main__":
    main()
