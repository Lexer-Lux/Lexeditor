"""The shared UI stays shared: a plugin may not reach further into it than it does today.

Two things drift a plugin away from the shared framework:

  * a selector naming a shared class (.lex-...), which is a plugin changing a
    shared component's geometry instead of the component gaining an option;
  * a hand-built row, table or list, instead of the shared list.

Neither can be banned outright yet - Chrono Trigger and RDR2 are unfinished and
FF8 predates most of the framework - so this is a ratchet. Every count is
recorded in ui/shared-ui-budget.json. A count may fall, and the file it belongs
to may disappear. Nothing may rise, and a new file starts at zero.

Run with --update after converting something, to bank the win.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUDGET = ROOT / "ui" / "shared-ui-budget.json"
SHARED_CLASS = re.compile(r"\.lex-[a-z0-9-]+")
HAND_BUILT = re.compile(r"""el\(\s*["'](?:table|thead|tbody|tr|td|th)["']|"""
                        r"""element\(\s*["'](?:table|thead|tbody|tr|td|th)["']|"""
                        r"""createElement\(\s*["'](?:table|thead|tbody|tr|td|th)["']""")


def counts() -> dict[str, dict[str, int]]:
    found: dict[str, dict[str, int]] = {}
    for path in sorted((ROOT / "plugins").rglob("*")):
        if path.suffix.lower() not in (".html", ".js", ".css") or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        row = {"sharedSelectors": len(SHARED_CLASS.findall(text)),
               "handBuiltRows": len(HAND_BUILT.findall(text))}
        if any(row.values()):
            found[path.relative_to(ROOT).as_posix()] = row
    return found


def listing(pattern: str = "") -> int:
    """Every hand-built row and shared-class selector, with its line.

    The conversion list: `--list rows` or `--list selectors`, worst file first.
    """
    wanted = {"rows": (HAND_BUILT,), "selectors": (SHARED_CLASS,)}.get(
        pattern, (HAND_BUILT, SHARED_CLASS))
    total = 0
    for name, row in sorted(counts().items(), key=lambda item: -sum(item[1].values())):
        lines = []
        text = (ROOT / name).read_text(encoding="utf-8", errors="replace").splitlines()
        for number, line in enumerate(text, 1):
            hits = sum(len(expression.findall(line)) for expression in wanted)
            if hits:
                lines.append(f"  {name}:{number}  {hits}x  {line.strip()[:110]}")
        if not lines:
            continue
        total += len(lines)
        print(f"{name}: {len(lines)} lines")
        print("\n".join(lines))
    print(f"{total} lines to convert.")
    return 0


def check() -> int:
    recorded = json.loads(BUDGET.read_text(encoding="utf-8"))["files"] if BUDGET.is_file() else {}
    current = counts()
    problems = []
    for name, row in sorted(current.items()):
        allowed = recorded.get(name, {"sharedSelectors": 0, "handBuiltRows": 0})
        for kind, label in (("sharedSelectors", "selectors naming a shared class"),
                            ("handBuiltRows", "hand-built table or row elements")):
            if row[kind] > allowed.get(kind, 0):
                problems.append(f"{name}: {row[kind]} {label}, up from {allowed.get(kind, 0)}. "
                                "Add the option to the shared component instead, or run "
                                "tests/shared/verify_shared_ui_budget.py --update if this is a deliberate step.")
    for problem in problems:
        print(problem)
    if problems:
        return 1
    banked = sum(sum(row.values()) for row in recorded.values()) - sum(sum(row.values()) for row in current.values())
    print(f"Shared UI budget holds across {len(current)} files"
          + (f"; {banked} fewer than recorded - run --update to bank it." if banked > 0 else "."))
    return 0


def update() -> int:
    BUDGET.write_text(json.dumps({
        "note": "Counts may fall, never rise. See tests/shared/verify_shared_ui_budget.py.",
        "files": counts()}, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(counts())} files in {BUDGET.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--list", nargs="?", const="all", choices=["all", "rows", "selectors"],
                        help="print every line to convert, worst file first")
    arguments = parser.parse_args()
    raise SystemExit(update() if arguments.update
                     else listing(arguments.list) if arguments.list else check())
