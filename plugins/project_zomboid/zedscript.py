"""Build 42 ZedScript inventory and explicit template-based record creation.

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
_EDITABLE = {
    "animationsMesh", "item", "evolvedrecipe", "craftRecipe", "fixing", "fluid",
    "vehicle", "sound", "model", "mannequin", "timedAction",
}


def create_copy(root: Path, relative: str, module_name: str, kind: str,
                source_name: str, name: str, expected_sha256: str) -> dict:
    """Append an explicit copy inside its source module, preserving the body."""
    if not isinstance(kind, str) or kind not in _EDITABLE or not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise core.ProjectZomboidError("Choose a supported record and an identifier using letters, digits and underscores")
    path = core._safe_relative(root, relative)
    if path not in core.script_paths(root):
        raise core.ProjectZomboidError("Script is outside supported Build 42 script roots")
    data, text = core._read_utf8(path)
    if core.sha256_bytes(data) != expected_sha256:
        raise core.ProjectZomboidError("Script changed outside Lexeditor; reload before creating a record")
    catalog = inventory(root)
    if catalog["errors"]:
        raise core.ProjectZomboidError("Repair unreadable scripts before creating a record")
    same_kind = [row for row in catalog["rows"] if row["module"] == module_name and row["kind"] == kind]
    if any(row["name"] == name for row in same_kind):
        raise core.ProjectZomboidError("A record with that name already exists in this module")
    matches = [row for row in same_kind if row["name"] == source_name and row["path"] == relative]
    if len(matches) != 1:
        raise core.ProjectZomboidError("Source record is missing or ambiguous")
    source = matches[0]
    modules = [block for block in core._top_level_blocks(text, "module")
               if block.name == module_name and block.open_brace < source["start"] < block.close_brace]
    if len(modules) != 1:
        raise core.ProjectZomboidError("Source module is missing or ambiguous")
    masked = core._masked_code(text)
    match = _BLOCK_RE.match(masked, source["start"])
    if match is None:
        raise core.ProjectZomboidError("Source record header changed")
    copied = text[source["start"]:match.start("name")] + name + text[match.end("name"):source["end"]]
    newline = "\r\n" if "\r\n" in text else "\n"
    position = modules[0].close_brace
    output = (text[:position] + newline + copied + newline + text[position:]).encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        output = b"\xef\xbb\xbf" + output
    if core.sha256_file(path) != expected_sha256:
        raise core.ProjectZomboidError("Script changed before creating a record; reload first")
    core._atomic_write(path, output)
    return next(row for row in inventory_file(path, root)["rows"]
                if row["module"] == module_name and row["kind"] == kind and row["name"] == name)


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
                    "editable": kind in _EDITABLE,
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
