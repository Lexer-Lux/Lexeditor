"""Source contracts for shared comma-grouped numeric displays."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
    ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    require('const formatNumber = (value, options = {}) =>' in framework,
            "the shared framework must own numeric formatting")
    require('new Intl.NumberFormat("en-US"' in framework and "useGrouping: true" in framework,
            "numeric grouping must use stable comma separators")
    require('const numberValue = (value, attrs = {}) =>' in framework,
            "displayed numeric values need one semantic component")
    require('!column.render && typeof rendered === "number"' in framework
            and 'numberValue(rendered)' in framework,
            "shared tables must group plain numeric cells automatically")
    require('if (typeof value === "number") return formatNumber(value)' in framework,
            "shared reference values must group numeric values automatically")
    require("font-kerning:none" in css and "font-variant-numeric:tabular-nums" in css,
            "the numeric component must stabilize digit spacing")
    require("function gilValue(value){return unitField(numberValue(value)" in ff8,
            "FF8 Gil list values must use the shared numeric component")
    require("sell.value=formatNumber(row.sellPrice)" in ff8,
            "FF8 calculated sell output must keep comma grouping after edits")
    require('.lex-number{font-family:var(--lex-font);font-variant-numeric:normal' in ff8,
            "FF8 numeric displays must use the installed game font")
    require('if character == "1":' in (ROOT / "games" / "ff8" / "game_font.py").read_text(encoding="utf-8"),
            "the generated FF8 font must reproduce the game renderer's narrow digit-one correction")
    require('value=>`${formatNumber(value)} G`' in ff8,
            "FF8 numeric reference values must use comma grouping")
    print("Shared number grouping and FF8 Gil display contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
