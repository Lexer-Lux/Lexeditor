"""Read-only Build 42 ZedScript structural inventory.

The recognized families mirror the current pz-scripts-data block registry. A family
being recognized here does not make it writable; mutation remains separately gated.
"""
from __future__ import annotations

from pathlib import Path
import re

from . import core

BLOCK_KINDS = (
    "animationsMesh",
    "craftRecipe",
    "entity",
    "evolvedrecipe",
    "fixing",
    "fluid",
    "item",
    "mannequin",
    "model",
    "sound",
    "timedAction",
    "vehicle",
)
_CANONICAL = {value.casefold(): value for value in BLOCK_KINDS}
_BLOCK_RE = re.compile(
    r"\b(?P<kind>animationsMesh|craftRecipe|entity|evolvedrecipe|fixing|fluid|item|mannequin|model|sound|timedAction|vehicle)"
    r"\s+(?P<name>[^\s{]+(?:\s+[^\s{]+)*)\s*\{",
    re.IGNORECASE,
)


def _brace_depth(masked: str, start: int, end: int) -> int:
    depth = 0
    for ch in masked[start:end]:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    return depth


def inventory_file(path: Path, root: Path) -> dict:
    root = root.resolve()
    path = path.resolve()
    data, text = core._read_utf8(path)
    masked = core._masked_code(text)
    rows = []
    errors = []
    try:
        modules = core._top_level_blocks(text, "module")
        for module in modules:
            body_start = module.open_brace + 1
            cursor = body_start
            while cursor < module.close_brace:
                match = _BLOCK_RE.search(masked, cursor, module.close_brace)
                if not match:
                    break
                if _brace_depth(masked, body_start, match.start()) != 0:
                    cursor = match.end()
                    continue
                open_brace = masked.find("{", match.start(), match.end())
                close_brace = core._matching_brace(masked, open_brace, module.close_brace)
                kind = _CANONICAL[match.group("kind").casefold()]
                rows.append({
                    "path": path.relative_to(root).as_posix(),
                    "module": module.name,
                    "kind": kind,
                    "name": match.group("name").strip(),
                    "sha256": core.sha256_bytes(data),
                    "start": match.start(),
                    "end": close_brace + 1,
                    "editable": kind in {"item", "evolvedrecipe", "craftRecipe", "fluid"},
                })
                cursor = close_brace + 1
    except core.ProjectZomboidError as error:
        errors.append(str(error))
    return {"rows": rows, "errors": errors}


def inventory(root: Path) -> dict:
    root = root.resolve()
    rows = []
    errors = []
    for path in core.script_paths(root):
        result = inventory_file(path, root)
        rows.extend(result["rows"])
        errors.extend({"path": path.relative_to(root).as_posix(), "error": value}
                      for value in result["errors"])
    counts = {kind: 0 for kind in BLOCK_KINDS}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    return {"rows": rows, "counts": counts, "errors": errors}
