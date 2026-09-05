"""Source contract for the global numbered-ID column rule."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = ROOT / "ui" / "framework.js"
FF8 = ROOT / "games" / "ff8" / "editor.html"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    framework = FRAMEWORK.read_text(encoding="utf-8")
    ff8 = FF8.read_text(encoding="utf-8")
    require("const numberedIdColumns = (columns, rows) =>" in framework,
            "the shared column list must own numbered-ID ordering")
    require("column.numberedId === true" in framework,
            "plugins need an explicit numeric-ID declaration for empty lists")
    require("/^#?\\d+$/.test(String(value).trim())" in framework,
            "automatic detection must accept only unsigned numbered IDs with one optional prefix")
    require("const recordId = (value, attrs = {}) =>" in framework,
            "the shared framework must own numbered-ID presentation")
    require('class: ["lex-record-id", className]' in framework,
            "numbered IDs must use the shared muted ID class")
    require("color:color-mix(in srgb, var(--lex-text) 62%, var(--lex-panel)) !important" in
            (ROOT / "ui" / "framework.css").read_text(encoding="utf-8"),
            "a plugin must not override the shared darker ID color")
    require('replace(/^#/, "")' in framework,
            "the shared helper must prevent duplicate ID prefixes")
    require("const preferredColumns = options.columnPreferences?.active?.();" in framework
            and "const columns = preferredColumns" in framework
            and "withEnabledColumn(preferredColumns, options.rows, options.enabledChange)" in framework
            and "numberedIdColumns(" in framework,
            "columnList must apply the global ID order after column preferences")
    require("numberedColumn(column) ? \"start\"" in framework and
            ".lex-numbered-id-cell .lex-record-id { justify-content:flex-start; }" in
            (ROOT / "ui" / "framework.css").read_text(encoding="utf-8"),
            "numbered table IDs must align their # prefixes on one left edge")
    require("sortState =" in framework and "sortState.key === column.key" in framework,
            "display order must not replace the requested sort state")
    require("numberedId:column.key===\"id\"" in ff8,
            "FF8 numeric ID columns must remain stable when a filtered list is empty")
    require('recordId(row.id)' in ff8 and 'recordId(active?.id,{class:"ff8-portrait-selected-id"})' in ff8,
            "FF8 detail headings must use the shared numbered-ID presentation")
    expected = [
        'columns=[{key:"id",label:"ID"},{key:"name",label:"Item"',
        'showPaged("shops",rows,[{key:"id",label:"ID"},{key:"name",label:"Shop"',
        'base=[{key:"id",label:"ID",width:"58px"},{key:"name",label:"Weapon"',
        'columns=[{key:"id",label:"ID"},{key:"name",label,render:',
        'columns=[{key:"id",label:"ID"},{key:"name",label:"Enemy"',
    ]
    for contract in expected:
        require(contract in ff8, f"FF8 numeric list does not declare ID before Name: {contract}")
    require('sorts:{items:["name",1],shops:["name",1],weapons:["name",1],magic:["name",1]' in ff8,
            "FF8 numbered lists must keep Name as the default ascending sort")
    print("Shared numbered-ID order and FF8 Name-sort contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
