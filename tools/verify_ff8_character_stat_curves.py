"""Contracts for the shared curve editor and FF8 character stat curves."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import paths  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from service_session import request_json  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    framework_css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    schema = json.loads((ROOT / "games" / "ff8" / "schema" / "kernel_section_fields.json").read_text(encoding="utf-8"))
    quotes = json.loads((ROOT / "ui" / "loading_quotes.json").read_text(encoding="utf-8"))

    require("const curveEditor = (options = {})" in framework and
            "curveEditor," in framework,
            "the graph, variables, extrema, and formula must belong to one shared curve component")
    require('const ceiling=stat==="HP"?9999:255' in editor and 'domain:{min:1,max:100}' in editor,
            "FF8 character graphs must use 0-9,999 for HP and 0-255 for other stats")
    require('characterCurveOrder=["HP","STR","VIT","MAG","SPR","SPD","LUCK"]' in editor
            and 'title:"XP"' in editor,
            "all seven character stat curves and the XP curve must be separate")
    require("integerDivision(level*A,10)" in editor and "integerDivision(level*level,2*D)" in editor,
            "the standard stat curve must retain the verified truncation points")
    require("level*A+integerDivision(level,B)-integerDivision(level,D)+C" in editor,
            "SPD and LUCK must use their verified linear branch")
    require('label:"ABCD"[index]' in editor and 'label:"AB"[index]' in editor,
            "curve inputs must use player-facing variable names")
    require('statFields.filter(field=>!field.readonly)' in editor and "UNUSED" not in editor,
            "the unused HP D byte must not consume visible curve space")
    require('formulaInTitle:true' not in editor and 'overlayExtrema:true' in editor and
            'XP(L) = 10 * (L - 1) * A + floor((L - 1)^2 * B / 256)' in editor,
            "curve equations must follow the graph and XP must use the verified equation")
    for token in ("lex-curve-tooltip", "lex-curve-variable-overlay", "data-curve-variable",
                  'root.addEventListener("pointermove"', "formulaTokens", "lex-curve-guide",
                  "lex-curve-point-marker", "lex-curve-path-formula", "lex-curve-hover-extrema"):
        require(token in framework, f"the shared curve interaction is missing {token}")
    require('root.querySelectorAll(".lex-curve-path-formula [class]")' in framework and
            "variableKeys.has(key)" in framework,
            "only actual formula variable tokens may receive graph-variable identities")
    import re as _re
    # The exact lift is tuned by eye; what must hold is that it is negative,
    # which is what puts the formula above the line rather than across it.
    require(any(int(value) < 0 for value in
                _re.findall(r'formulaText\.setAttribute\("dy", "(-?\d+)"\)', framework)) and
            'formulaPath.setAttribute("dy"' not in framework and
            "getComputedTextLength" in framework and "getTotalLength" in framework and
            'formulaText.setAttribute("textLength"' not in framework and
            'lengthAdjust' not in framework,
            "curve formulae must sit above the line, shrink to the available path, "
            "and never have their letter spacing stretched to fill it")
    require('root.querySelectorAll("[class*=\'lex-curve-variable-\']")' not in framework and
            'root.querySelectorAll("[class*=\"lex-curve-variable-\"]")' not in framework,
            "helper classes must not make the whole variable drawer highlight")
    require("tooltipBounds.width / 2" in framework and
            "Math.min(innerWidth - inset - halfWidth, event.clientX)" in framework and
            "transform:translate(-50%,-115%)" in framework_css,
            "curve probe labels must center on the pointer and clamp only at the window edge")
    for color in ("#f05b5b", "#63a8ff", "#f1d34f", "#62c66b"):
        require(f"fill:{color}" in framework_css,
                f"SVG formula variables must retain their {color} graph-variable color")
    require('event.target.dispatchEvent(new Event("input",{bubbles:true}))' in editor,
            "number-input ArrowUp and ArrowDown edits must emit the same live input event as typing")
    require("onchange(next);shell.refresh()" not in editor,
            "arrow-key number edits must not bypass the shared live-input redraw path")
    for token in ("translateY(-105%)", "grid-template-columns:repeat(auto-fit,minmax(58px,1fr))",
                  ".ff8-character-curve .lex-curve-path-formula", "border:0!important"):
        require(token in editor, f"the FF8 full-graph presentation is missing {token}")
    require(".character-stat-growth>.lex-detail-section-content{display:flex;min-height:0;flex:1 1 auto;padding:0!important}" in editor and
            ".character-curve-grid{height:auto!important;min-height:0;flex:1 1 auto" in editor,
            "the curve grid must consume the stat panel without reserved top or bottom space")
    require(".ff8-character-curve .lex-curve-axis-bottom{bottom:18px;left:5px}" in editor and
            ".ff8-character-curve .lex-curve-axis-start{bottom:5px;left:30px}" in editor,
            "the bottom Y and left X labels must not collapse into a single corner value")
    hp4 = next(field for field in schema["7"]["fields"] if field["name"] == "hp_4")
    require(hp4.get("readonly") and hp4.get("display_readonly"),
            "HP c4 must remain preserved and non-editable even though the curve UI omits it")
    exact_quotes = {
        "ff8": [">tfw no GF"],
        "rdr": [
            "Billion-dollar idea: RDR spinoff set in the modern day. Who's working on this?",
            "i saw a movie about gay cowboys once",
            "i love rdr1 so much. god i wish mexico was real",
            "i'm eating a bowl of mexican beef rn and it's really really tasty. thank u mexico",
        ],
        "rdr2": [
            "if dutch needed money why didn't they he cook meth? is he stupid?",
            'if arthur just googled "how to treat tuberculosis" he could have saved us all a lot of effort',
            "We'd probably be on RDR4 by now if it weren't for GTA Online. You don't hate microtransactions enough.",
            "If you use freecam to escape the invisible walls you'll see about 2/3rds of the entire world lies outside the playable bounds. I'm not even kidding. It's insane.",
        ],
    }
    for game, expected in exact_quotes.items():
        require(all(line in quotes.get(game, []) for line in expected),
                f"the supplied {game} loading lines must stay exact and editable")

    kernel = paths.BASELINE_ROOT / "main" / "kernel.bin"
    before = digest(kernel)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-character-curves-", ignore_cleanup_errors=True) as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session:
            rows = request_json(session.url + "api/kernel?section=7")["rows"]
            stat_fields = [field for field in rows[0]["fields"] if field["group"] == "Stat coefficients"]
            groups = {name: [field for field in stat_fields if field["subgroup"] == name]
                      for name in ("HP", "STR", "VIT", "MAG", "SPR", "SPD", "LUCK")}
            require(all(len(fields) == 4 for fields in groups.values()),
                    "each curve must expose four stored variables")
            require(groups["HP"][3]["readonly"] and
                    not any(field["readonly"] for fields in groups.values() for field in fields[:3]) and
                    not any(field["readonly"] for fields in list(groups.values())[1:] for field in fields),
                    "only HP c4 may be read-only")
            field = groups["STR"][0]
            changed = field["value"] + 1 if field["value"] < field["maximum"] else field["value"] - 1
            result = request_json(session.url + "api/kernel/save", {
                "section": 7, "edits": [{"id": rows[0]["id"], "field": field["field"], "value": changed}],
            })
            require(result["saved"] == 1, "an edited curve coefficient must save")
            reread = request_json(session.url + "api/kernel?section=7")["rows"][0]["fields"]
            require(next(value for value in reread if value["field"] == field["field"])["value"] == changed,
                    "the edited curve coefficient must read back")
    require(digest(kernel) == before, "the curve test must not change the installed baseline")
    print(json.dumps({
        "curves": [*groups, "XP"],
        "visibleVariables": {"HP": 3, "otherStats": 4, "XP": 2},
        "graphRanges": {"HP": [0, 9999], "other": [0, 255]},
        "levels": [1, 100],
        "roundTrip": field["field"],
        "baselineUnchanged": True,
        "rdrQuotes": len(quotes["rdr"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
