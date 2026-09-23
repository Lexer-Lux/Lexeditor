"""Reject FF7 presentation drift from the current Blank/shared neutral UI contract."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FF7 = ROOT / "games" / "ff7" / "editor.html"
FF7_JS_MODULES = ("editor.js", "controls.js", "details.js", "workspace.js")
BLANK = ROOT / "games" / "blank" / "editor.html"
BLANK_CSS = ROOT / "games" / "blank" / "editor.css"
BLANK_JS = ROOT / "games" / "blank" / "editor.js"
NEUTRAL = ROOT / "ui" / "neutral.css"


def compact(value: str) -> str:
    return "".join(value.split())


def main() -> None:
    ff7 = FF7.read_text(encoding="utf-8")
    ff7_js = "\n".join((ROOT / "games" / "ff7" / name).read_text(encoding="utf-8") for name in FF7_JS_MODULES)
    ff7_code = ff7 + "\n" + ff7_js
    blank = BLANK.read_text(encoding="utf-8")
    blank_css = BLANK_CSS.read_text(encoding="utf-8")
    blank_js = BLANK_JS.read_text(encoding="utf-8")
    neutral = NEUTRAL.read_text(encoding="utf-8")

    # FF7 consumes the shared neutral presentation and owns no stylesheet.
    if "<style" in ff7.casefold() or "style=" in ff7.casefold() or "style=" in ff7_js.casefold():
        raise AssertionError("FF7 contains local CSS/style overrides")
    for marker in (
        '<link rel="stylesheet" href="/shared/framework.css">',
        '<link rel="stylesheet" href="/shared/neutral.css">',
        '<body class="lex-neutral-ui">',
        '<script src="editor.js"></script>',
    ):
        if marker not in ff7:
            raise AssertionError(f"FF7 is not consuming the shared neutral/module contract: {marker}")

    # Blank is now modular too. Keep the benchmark tied to its current files,
    # not to stale CSS that used to live inline in editor.html.
    for marker in (
        '<link rel="stylesheet" href="/shared/framework.css">',
        '<link rel="stylesheet" href="editor.css">',
        '<script src="/shared/framework.js"></script>',
        '<script src="/shared/component-catalog.js"></script>',
        '<script src="editor.js"></script>',
    ):
        if marker not in blank:
            raise AssertionError(f"Blank benchmark module contract changed: {marker}")

    lower_neutral = neutral.casefold()
    for token in (".ff7-", "#ff7-", ".blank-", "#blank-"):
        if token in lower_neutral:
            raise AssertionError(f"Shared neutral stylesheet contains plugin-specific selector {token}")

    # Blank also owns gallery-only command/nav tokens. Compare only the
    # presentation tokens neutral.css deliberately shares with FF7.
    def token(css: str, name: str) -> str | None:
        value = compact(css)
        marker = name + ":"
        if marker not in value:
            return None
        tail = value.split(marker, 1)[1]
        return tail.split(";", 1)[0].split("}", 1)[0]

    for name in ("--lex-accent", "--lex-accent-text", "--lex-highlight"):
        blank_value = token(blank_css, name)
        neutral_value = token(neutral, name)
        if blank_value is None or neutral_value is None or blank_value != neutral_value:
            raise AssertionError(
                f"Blank/neutral shared theme token drifted: {name} "
                f"(Blank={blank_value!r}, neutral={neutral_value!r})"
            )

    # Compare both callers to the current shared two-panel benchmark rather
    # than hard-coding obsolete inline Blank markup.
    blank_layout = (
        "slots:false",
        "pageSize=12",
        "defaultSplit:50",
        "minLeft:320",
        "minRight:360",
    )
    missing_blank = [value for value in blank_layout if value not in compact(blank_js)]
    if missing_blank:
        raise AssertionError("Blank two-panel benchmark changed: " + ", ".join(missing_blank))

    ff7_layout = (
        "slots:false",
        "pageSize:state.pageSize[group]||12",
        "defaultSplit:50",
        "minLeft:320",
        "minRight:360",
    )
    missing_ff7 = [value for value in ff7_layout if value not in compact(ff7_code)]
    if missing_ff7:
        raise AssertionError("FF7 master/detail geometry drifted from Blank: " + ", ".join(missing_ff7))

    for legacy in (
        'class:"lex-subtab-bar ff7-subtabs"',
        'class:"lex-subtab-button"',
        'class:"ff7-map-controls"',
        'class:"ff7-tweak-panel"',
    ):
        if legacy in ff7_code:
            raise AssertionError(f"FF7 still hand-builds shared UI markup: {legacy}")

    required_helpers = (
        "subtabBar", "tabbedPanel", "detailPanel", "detailSection", "detailField",
        "columnList", "pagedListDetail", "readonlyField", "infoIcon",
    )
    missing_ff7_helpers = [name for name in required_helpers if name not in ff7_code]
    if missing_ff7_helpers:
        raise AssertionError("FF7 stopped using required shared UI helpers: " + ", ".join(missing_ff7_helpers))

    print("FF7 Blank UI contract: zero local CSS, shared neutral presentation, current Blank geometry")


if __name__ == "__main__":
    main()
