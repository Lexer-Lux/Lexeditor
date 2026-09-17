"""Remove declarations that can never apply, from one stylesheet.

    python tools/css_dead_code.py ui/framework.css [--write]

A declaration is dead when a later rule, in a context that holds whenever
the earlier one does, sets the same property for the same selector with at
least the same importance. The later one always wins the cascade, so the
earlier one is text that only misleads the next person reading the file.

Removal is exact: comments and every other byte are kept. A rule left with no
declarations is removed with its own text. Run tools/visual_snapshot.py
--styles before and after, and tools/style_compare.py, to prove nothing
changed on screen.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Shorthand -> the longhands it resets. A later shorthand kills an earlier
# longhand; an earlier shorthand is only partly overridden by a later
# longhand, so it is never removed for that.
SIDES = ("top", "right", "bottom", "left")
SHORTHANDS = {
    "margin": {f"margin-{s}" for s in SIDES},
    "padding": {f"padding-{s}" for s in SIDES},
    "inset": set(SIDES),
    "border-width": {f"border-{s}-width" for s in SIDES},
    "border-style": {f"border-{s}-style" for s in SIDES},
    "border-color": {f"border-{s}-color" for s in SIDES},
    "border-radius": {f"border-{v}-{h}-radius" for v in ("top", "bottom") for h in ("left", "right")},
    "overflow": {"overflow-x", "overflow-y"},
    "gap": {"row-gap", "column-gap"},
    "flex": {"flex-grow", "flex-shrink", "flex-basis"},
    "outline": {"outline-width", "outline-style", "outline-color"},
}
for side in SIDES:
    SHORTHANDS[f"border-{side}"] = {f"border-{side}-width", f"border-{side}-style", f"border-{side}-color"}
SHORTHANDS["border"] = set().union(*(SHORTHANDS[f"border-{s}"] for s in SIDES)) | {
    "border-width", "border-style", "border-color", *(f"border-{s}" for s in SIDES)}


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


def blank_comments(css: str) -> str:
    """Same length, comments turned to spaces, so offsets stay true."""
    return re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), css, flags=re.S)


def matching_brace(text: str, start: int) -> int:
    """Index just past the '}' that closes the '{' at start."""
    depth, i, quote = 0, start, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced braces")


@dataclass
class Declaration:
    name: str
    important: bool
    start: int   # span of the text to delete, including its ';'
    end: int


@dataclass
class Rule:
    context: tuple
    selectors: tuple
    start: int   # whole rule text span
    end: int
    declarations: list = field(default_factory=list)


def split_declarations(text: str, offset: int, body_start: int, body_end: int):
    out = []
    i = body_start
    depth, quote, begin = 0, None, body_start
    while i <= body_end:
        c = text[i] if i < body_end else ";"
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == ";" and depth == 0:
            chunk = text[begin:i]
            if ":" in chunk and chunk.strip():
                name, value = chunk.split(":", 1)
                end = i + 1 if i < body_end else i
                out.append(Declaration(name.strip().lower(), "!important" in value.replace(" ", "").lower(),
                                       begin, end))
            begin = i + 1
        i += 1
    return out


def parse(text: str, start: int = 0, end: int | None = None, context: tuple = ()):
    end = len(text) if end is None else end
    i = start
    while i < end:
        brace = text.find("{", i, end)
        if brace < 0:
            return
        prelude_raw = text[i:brace]
        prelude = prelude_raw.strip()
        if prelude.startswith("@") and ";" in prelude:
            prelude = prelude[prelude.rfind(";") + 1:].strip()
        close = matching_brace(text, brace)
        if prelude.startswith("@"):
            if prelude.startswith(("@media", "@container", "@supports", "@layer")):
                yield from parse(text, brace + 1, close - 1, context + (" ".join(prelude.split()),))
        elif prelude:
            rule_start = i + (len(prelude_raw) - len(prelude_raw.lstrip()))
            selectors = tuple(split_selectors(prelude))
            rule = Rule(context, selectors, rule_start, close)
            rule.declarations = split_declarations(text, 0, brace + 1, close - 1)
            yield rule
        i = close


def dead_spans(css: str):
    text = blank_comments(css)
    rules = list(parse(text))
    dead = []
    for index, rule in enumerate(rules):
        later = [r for r in rules[index + 1:] if r.context == rule.context[:len(r.context)]]
        for position, declaration in enumerate(rule.declarations):
            def overridden(selector):
                # A later declaration in the same rule counts too.
                for other in rule.declarations[position + 1:]:
                    if beats(other, declaration):
                        return True
                for other_rule in later:
                    if selector not in other_rule.selectors:
                        continue
                    if any(beats(other, declaration) for other in other_rule.declarations):
                        return True
                return False
            if all(overridden(selector) for selector in rule.selectors):
                dead.append((rule, declaration))
    return rules, dead


def beats(later: Declaration, earlier: Declaration) -> bool:
    if earlier.important and not later.important:
        return False
    return later.name == earlier.name or earlier.name in SHORTHANDS.get(later.name, ())


def remove(css: str) -> tuple[str, int, int]:
    rules, dead = dead_spans(css)
    by_rule = {}
    for rule, declaration in dead:
        by_rule.setdefault(id(rule), (rule, []))[1].append(declaration)
    cuts = []
    emptied = 0
    for rule, declarations in by_rule.values():
        if len(declarations) == len(rule.declarations):
            cuts.append((rule.start, rule.end))
            emptied += 1
        else:
            cuts.extend((d.start, d.end) for d in declarations)
    out = css
    for start, end in sorted(cuts, reverse=True):
        # Take the whitespace the removed text stood on, so no gaps are left.
        while start > 0 and out[start - 1] in " \t":
            start -= 1
        if end < len(out) and out[end] == "\n" and (start == 0 or out[start - 1] == "\n"):
            end += 1
        out = out[:start] + out[end:]
    return out, len(dead), emptied


def main() -> int:
    path = Path(sys.argv[1])
    css = path.read_text(encoding="utf-8")
    out, removed, emptied = remove(css)
    print(f"{path}: {removed} dead declarations, {emptied} rules left empty and removed")
    if "--write" in sys.argv:
        path.write_text(out, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
