"""The same function, written twice in two plugins, is drift with a compiler.

The shared UI budget catches a plugin drawing its own rows. This catches the
Python version: a plugin writing a helper another plugin already has, which is
how eight servers each grew their own way to send a file.

Functions are compared by shape - the tree of statements, with names and
constants thrown away - so a copy that renamed its arguments still matches.
Counts live in ui/shared-code-budget.json and may fall, never rise.

  --list     every duplicated function, worst first
  --update   bank a lower count after moving something into a shared module
"""
from __future__ import annotations

import argparse
import ast
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUDGET = ROOT / "ui" / "shared-code-budget.json"
SKIP = {"__pycache__", "vendor", "ffnx-src", "ffnx_issue_51", "ffnx_gameplay_extensions"}
# Shorter than this is a signature, not a design worth sharing.
SMALLEST = 6


def _shape(node: ast.AST) -> str:
    return ",".join(type(child).__name__ for child in ast.walk(node))


def duplicates() -> dict[str, list[dict]]:
    """Function shapes that appear in more than one plugin."""
    bodies: dict[str, list[dict]] = defaultdict(list)
    for path in sorted((ROOT / "plugins").rglob("*.py")):
        if SKIP & set(path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            lines = getattr(node, "end_lineno", node.lineno) - node.lineno
            if lines < SMALLEST:
                continue
            bodies[_shape(node)].append({
                "file": path.relative_to(ROOT).as_posix(), "name": node.name,
                "line": node.lineno, "lines": lines, "plugin": path.relative_to(ROOT).parts[1]})
    return {shape: rows for shape, rows in bodies.items()
            if len({row["plugin"] for row in rows}) > 1}


def counts() -> dict[str, int]:
    """Copied lines per plugin: everything after the first copy of a shape."""
    per_plugin: dict[str, int] = defaultdict(int)
    for rows in duplicates().values():
        for row in sorted(rows, key=lambda row: (row["file"], row["line"]))[1:]:
            per_plugin[row["plugin"]] += row["lines"]
    return dict(sorted(per_plugin.items()))


def listing() -> int:
    groups = sorted(duplicates().values(), key=lambda rows: -sum(row["lines"] for row in rows))
    for rows in groups:
        print(f"{sum(row['lines'] for row in rows)} lines, {len(rows)} copies:")
        for row in sorted(rows, key=lambda row: row["file"]):
            print(f"  {row['file']}:{row['line']}  {row['name']} ({row['lines']} lines)")
    print(f"{sum(counts().values())} lines are a second copy of another plugin's function.")
    return 0


def check() -> int:
    recorded = json.loads(BUDGET.read_text(encoding="utf-8"))["plugins"] if BUDGET.is_file() else {}
    current = counts()
    problems = [f"{plugin}: {lines} copied lines, up from {recorded.get(plugin, 0)}. "
                "Move the shared one into a module both plugins import, or run "
                "tools/verify_shared_code_budget.py --update if this is deliberate."
                for plugin, lines in current.items() if lines > recorded.get(plugin, 0)]
    for problem in problems:
        print(problem)
    if problems:
        return 1
    banked = sum(recorded.values()) - sum(current.values())
    print(f"Shared code budget holds: {sum(current.values())} copied lines across {len(current)} plugins"
          + (f"; {banked} fewer than recorded - run --update to bank it." if banked > 0 else "."))
    return 0


def update() -> int:
    BUDGET.write_text(json.dumps({
        "note": "Copied lines per plugin. May fall, never rise. See tools/verify_shared_code_budget.py.",
        "plugins": counts()}, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {sum(counts().values())} copied lines in {BUDGET.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--list", action="store_true")
    arguments = parser.parse_args()
    raise SystemExit(update() if arguments.update else listing() if arguments.list else check())
