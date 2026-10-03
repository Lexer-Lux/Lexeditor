"""Every list-and-detail page decides whether its records can be renamed.

Lexer: "Do we need to make some kind of agents.md change or tester or
something so you start actually making everything that should be editable
also editable in the table, including the names column?"

A page renames its records by passing `rename` to pagedListDetail (the
table's Name cell and the detail heading, by double-click), or says why it
cannot with a `// names: <reason>` comment just above the call. UNDECIDED is
the pages that predate this rule; it may only shrink.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

UNDECIDED = {
    "bannerlord/editor_shared.js": 1, "blank/editor.js": 2, "chrono_trigger/editor.js": 1,
    "ds3/editor.js": 1, "factorio/editor.js": 1, "ff7/workspace.js": 1, "ff7r/editor.js": 2,
    "ff7r2/editor.js": 3, "ff8/cards_ui.js": 2, "ff8/core.js": 1, "ff9/editor.js": 3,
    "ffx_x2/editor.js": 2, "palworld/editor.js": 1, "project_zomboid/editor.js": 2, "rdr/editor.js": 3,
    "rdr/rbf.js": 1, "rdr/strings.js": 1, "rdr2/challenges.js": 1, "rdr2/crafting.js": 1,
    "rdr2/effects.js": 2, "rdr2/items.js": 1, "rdr2/loot.js": 2, "rdr2/weapons.js": 1,
    "stardew_valley/editor.js": 2, "terraria/editor.js": 4, "warband/editor.js": 2,
    "warband/module_records.js": 1,
}


def call_text(source: str, start: int) -> str:
    """The pagedListDetail(...) call that starts at `start`, by bracket depth."""
    depth, index = 0, source.index("(", start)
    for position in range(index, len(source)):
        char = source[position]
        depth += char == "("
        depth -= char == ")"
        if depth == 0:
            return source[start:position + 1]
    return source[start:]


def undecided() -> dict[str, int]:
    found = {}
    for path in sorted((ROOT / "plugins").glob("*/*.js")):
        source = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"pagedListDetail\(", source):
            before = source[:match.start()].splitlines()[-3:]
            if "rename:" in call_text(source, match.start()) or any("// names:" in line for line in before):
                continue
            key = path.relative_to(ROOT / "plugins").as_posix()
            found[key] = found.get(key, 0) + 1
    return found


def test_no_new_list_page_leaves_its_names_undecided():
    found = undecided()
    grown = {key: count for key, count in found.items() if count > UNDECIDED.get(key, 0)}
    assert not grown, ("Pass rename to pagedListDetail so the records' names can be changed in the table "
                       f"and the heading, or say why not with a '// names:' comment above the call: {grown}")


def test_the_undecided_list_only_shrinks():
    found = undecided()
    stale = {key: (count, found.get(key, 0)) for key, count in UNDECIDED.items() if found.get(key, 0) < count}
    assert not stale, f"These pages decided; lower UNDECIDED to match (was, now): {stale}"
