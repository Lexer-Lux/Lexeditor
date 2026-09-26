"""Source contract for the global numbered-ID column rule.

This read `plugins/ff8/editor.html` for the FF8 side of every requirement, and
that file is the page shell now: the lists moved into `plugins/ff8/*.js`. Every
assertion about FF8 therefore failed on a source that no longer exists, so the
check could not run at all. The requirements are the same; they are read from
the files that hold the code.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK = ROOT / "ui" / "framework.js"
FRAMEWORK_CSS = ROOT / "ui" / "framework.css"
FF8_DIR = ROOT / "plugins" / "ff8"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def ff8_sources() -> str:
    return "\n".join(path.read_text(encoding="utf-8")
                     for path in sorted(FF8_DIR.glob("*.js")))


def rule_body(css: str, selector: str) -> str:
    """The declarations of one CSS rule, whatever shape its whitespace is."""
    start = css.find(selector + " {")
    require(start >= 0, f"the shared stylesheet has no {selector} rule")
    end = css.find("}", start)
    require(end > start, f"the {selector} rule is never closed")
    return css[start:end]


def main() -> int:
    framework = FRAMEWORK.read_text(encoding="utf-8")
    css = FRAMEWORK_CSS.read_text(encoding="utf-8")
    ff8 = ff8_sources()

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
    # The shared rule paints an ID darker than body text. A plugin that
    # overrode it in its own stylesheet would undo the whole point.
    id_rule = rule_body(css, ".lex-record-id")
    require("color-mix(in srgb, var(--lex-text) 62%, var(--lex-panel))" in id_rule,
            "the shared stylesheet must own the darker ID colour")
    for stylesheet in sorted(FF8_DIR.glob("*.css")):
        text = stylesheet.read_text(encoding="utf-8")
        require("lex-record-id" not in text,
                f"{stylesheet.name} overrides the shared numbered-ID presentation")
    require('replace(/^#/, "")' in framework,
            "the shared helper must prevent duplicate ID prefixes")
    # An identity that is already a record id must not be wrapped again: a
    # numbered cell that renders U.recordId itself printed "##0".
    require('value.classList.contains("lex-record-id")' in framework,
            "the shared helper must not prefix an identity that is already drawn")
    require("const preferredColumns = options.columnPreferences?.active?.();" in framework
            and "const columns = preferredColumns" in framework
            # No closing paren: the helper gained a fourth argument, which does
            # not change the requirement that it is fed the PREFERRED columns.
            and "withEnabledColumn(preferredColumns, options.rows, options.enabledChange" in framework
            and "numberedIdColumns(" in framework,
            "columnList must apply the global ID order after column preferences")
    require("numberedColumn(column) ? \"start\"" in framework and
            "justify-content:flex-start" in rule_body(css, ".lex-numbered-id-cell .lex-record-id"),
            "numbered table IDs must align their # prefixes on one left edge")
    require("sortState =" in framework and "sortState.key === column.key" in framework,
            "display order must not replace the requested sort state")
    # A column may now declare numberedId itself, falling back to the id
    # convention; the fallback is the part this contract is about.
    require('numberedId:column.numberedId??column.key==="id"' in ff8
            or 'numberedId:column.key==="id"' in ff8,
            "FF8 numeric ID columns must remain stable when a filtered list is empty")
    require("recordId(row.id)" in ff8 and "recordId(active?.id)" in ff8,
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
    # The default sort for each numeric list is Name, ascending, and it lives
    # in one table now rather than one declaration per list.
    for view in ("items", "shops", "weapons", "magic", "gfs"):
        require(f'{view}:["name",1]' in ff8,
                f"FF8 {view} must keep Name as the default ascending sort")
    print("Shared numbered-ID order and FF8 Name-sort contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
