"""What stylesheets do beyond theme tokens.

    python tools/css_audit.py [--list PLUGIN]

A plugin's stylesheet may set theme tokens (custom properties such as
--lex-panel) and declare fonts. Everything else - a rule that sets a real
property - is layout or styling the framework should own, and is counted
here. ui/framework.css is counted too: selectors defined more than once in
the same context, and !important declarations.

tests/shared/test_css_budget.py holds these counts to a budget that may only fall.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def split_selectors(prelude: str) -> list[str]:
    """A selector list's members; commas inside :is(), :not() and the like do
    not separate members."""
    parts, depth, start = [], 0, 0
    for index, char in enumerate(prelude):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(prelude[start:index])
            start = index + 1
    parts.append(prelude[start:])
    return [" ".join(part.split()) for part in parts if part.strip()]


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def rules(css: str, context: tuple[str, ...] = ()):
    """Yield (context, selector, declarations) for every style rule, nested
    at-rules included. Strings and comments do not contain braces here."""
    css = strip_comments(css)
    i, n = 0, len(css)
    while i < n:
        brace = css.find("{", i)
        if brace < 0:
            return
        prelude = css[i:brace].strip()
        # Statements such as @import end at ';' before the block.
        if ";" in prelude and prelude.lstrip().startswith("@"):
            prelude = prelude[prelude.rfind(";") + 1:].strip()
        depth, j = 1, brace + 1
        while j < n and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        body = css[brace + 1:j - 1]
        if prelude.startswith("@"):
            if prelude.startswith(("@media", "@container", "@supports", "@layer")):
                yield from rules(body, context + (" ".join(prelude.split()),))
            else:
                yield context, prelude, None  # @font-face, @keyframes: not style rules
        else:
            yield context, " ".join(prelude.split()), body
        i = j


def declarations(body: str):
    for part in body.split(";"):
        if ":" in part:
            name, value = part.split(":", 1)
            yield name.strip().lower(), value.strip()


def plugin_counts(path: Path) -> dict:
    real = []
    for context, selector, body in rules(path.read_text(encoding="utf-8")):
        if body is None:
            continue
        props = [name for name, _ in declarations(body) if not name.startswith("--")]
        if props:
            real.append((context, selector, props))
    return {"rules": real, "important": path.read_text(encoding="utf-8").count("!important")}


def framework_counts(path: Path) -> dict:
    seen = collections.Counter()
    for context, selector, body in rules(path.read_text(encoding="utf-8")):
        if body is None:
            continue
        for one in split_selectors(selector):
            seen[(context, one)] += 1
    duplicates = {key: count for key, count in seen.items() if count > 1}
    return {"duplicates": duplicates, "extra": sum(c - 1 for c in duplicates.values()),
            "important": path.read_text(encoding="utf-8").count("!important")}


def plugin_sheets() -> dict[str, list[Path]]:
    sheets = collections.defaultdict(list)
    for path in sorted((ROOT / "plugins").glob("*/*.css")):
        sheets[path.parent.name].append(path)
    return dict(sheets)


def summary() -> dict:
    out = {}
    for plugin, paths in plugin_sheets().items():
        counts = [plugin_counts(path) for path in paths]
        out[plugin] = {"rules": sum(len(c["rules"]) for c in counts),
                       "important": sum(c["important"] for c in counts)}
    framework = framework_counts(ROOT / "ui" / "framework.css")
    out["framework"] = {"duplicates": framework["extra"], "important": framework["important"]}
    return out


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--list"]:
        for path in plugin_sheets()[args[1]]:
            for context, selector, props in plugin_counts(path)["rules"]:
                where = f"{' '.join(context)} " if context else ""
                print(f"{path.name}: {where}{selector[:90]}  [{', '.join(props[:6])}]")
        return 0
    for name, counts in summary().items():
        print(name, counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
