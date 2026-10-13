"""DS1 subtabs follow the shared alphabetical rule, like every other game.

Lexer: "THE SUBTABS IN THE DS1 PLUGIN AREN'T ALPHABETICTALLY SORTED."
DS1's editor passed order:"given" to the shared subtabBar, which honours it,
so DS1 showed its own declaration order instead of the alphabetical order
every other plugin gets. Image bars (GF/character portraits) may keep the
game's order; text bars may not opt out.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ORDER_GIVEN = re.compile(r"""order\s*:\s*["']given["']""")
IMAGES = re.compile(r"""images\s*:\s*true""")


def subtab_bar_calls(source: str) -> list[str]:
    """Each `subtabBar(...)` call's text, matched by balanced parens."""
    calls = []
    for match in re.finditer(r"subtabBar\s*\(", source):
        depth, index = 0, match.end() - 1
        quote: str | None = None
        escaped = False
        while index < len(source):
            char = source[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            elif char in ("'", '"', "`"):
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    calls.append(source[match.start():index + 1])
                    break
            index += 1
    return calls


def unjustified_opt_outs() -> list[str]:
    """Every text subtab bar that keeps its given order, by file and call."""
    offenders = []
    for path in sorted((ROOT / "plugins").rglob("*.js")):
        if "vendor" in path.parts or "node_modules" in path.parts:
            continue
        for call in subtab_bar_calls(path.read_text(encoding="utf-8")):
            if ORDER_GIVEN.search(call) and not IMAGES.search(call):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}: {call[:120]}")
    return offenders


def test_no_text_subtab_bar_opts_out_of_alphabetical_order():
    assert unjustified_opt_outs() == []


def test_ds1_editor_does_not_pass_given_order():
    source = (ROOT / "plugins" / "ds1" / "editor.js").read_text(encoding="utf-8")
    assert not ORDER_GIVEN.search(source), "DS1 must sort its subtabs like everywhere else"


def test_ds1_subtab_labels_need_the_shared_sort():
    """The declared order is not alphabetical, so opting out shows."""
    from plugins.ds1.effects import SUBTABS as effect_subtabs
    from plugins.ds1.formats import SUBTABS

    for tabs in (SUBTABS, effect_subtabs):
        labels = [label for _key, label, _table in tabs]
        assert labels != sorted(labels, key=str.lower), labels
