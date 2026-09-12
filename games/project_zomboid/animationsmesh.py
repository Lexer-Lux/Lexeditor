"""Conservative structured editor for Build 42 module-level animationsMesh records.

Project Zomboid's current Java API types keepMeshAnimations as boolean,
meshFile/postProcess as strings, and animationDirectory/animationPrefix as repeated
string lists. Lexeditor edits only the three single-valued fields and preserves the
repeated lists verbatim.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

from . import core

EDITABLE_FIELDS = ("keepMeshAnimations", "meshFile", "postProcess")
BOOLEAN_FIELDS = {"keepMeshAnimations"}


def _blocks(text: str) -> list[tuple[core.Block, core.Block]]:
    masked = core._masked_code(text)
    pattern = re.compile(r"\banimationsMesh\s+([^\s{]+(?:\s+[^\s{]+)*)\s*\{", re.IGNORECASE)
    rows: list[tuple[core.Block, core.Block]] = []
    for module in core._top_level_blocks(text, "module"):
        cursor = body_start = module.open_brace + 1
        while cursor < module.close_brace:
            match = pattern.search(masked, cursor, module.close_brace)
            if not match:
                break
            depth = 0
            for char in masked[body_start:match.start()]:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
            if depth:
                cursor = match.end()
                continue
            opened = masked.find("{", match.start(), match.end())
            closed = core._matching_brace(masked, opened, module.close_brace)
            rows.append((module, core.Block(
                "animationsMesh", match.group(1).strip(), match.start(), opened, closed,
            )))
            cursor = closed + 1
            body_start = cursor
    return rows


def _repeated_counts(text: str, block: core.Block) -> dict[str, int]:
    return core._top_level_property_counts(
        text, block, ("animationDirectory", "animationPrefix")
    )


def read(root: Path) -> dict:
    root = Path(root).resolve()
    rows, errors = [], []
    for path in core.script_paths(root):
        data, text = core._read_utf8(path)
        relative = path.relative_to(root).as_posix()
        try:
            pairs = _blocks(text)
        except core.ProjectZomboidError as error:
            errors.append({"path": relative, "error": str(error)})
            continue
        for module, block in pairs:
            values, duplicates = core._properties(text, block)
            repeated = _repeated_counts(text, block)
            rows.append({
                "key": f"{relative}:{module.name}.{block.name}",
                "path": relative,
                "module": module.name,
                "id": block.name,
                "fullType": f"{module.name}.{block.name}",
                "sha256": core.sha256_bytes(data),
                "fields": {key: values.get(key, "") for key in EDITABLE_FIELDS},
                "duplicateKeys": sorted(set(duplicates) & set(EDITABLE_FIELDS)),
                "animationDirectoryCount": repeated.get("animationDirectory", 0),
                "animationPrefixCount": repeated.get("animationPrefix", 0),
            })
    return {"rows": rows, "errors": errors}


def _validate(key: str, value: object) -> str:
    clean = core._clean_scalar(value, key)
    if any(char in clean for char in ",{}"):
        raise core.ProjectZomboidError(f"{key} contains script punctuation")
    if key in BOOLEAN_FIELDS:
        lowered = clean.casefold()
        if lowered not in {"true", "false"}:
            raise core.ProjectZomboidError(f"{key} must be true or false")
        return lowered
    return clean


def save(root: Path, relative: str, module_name: str, mesh_id: str,
         expected_sha256: str, edits: dict) -> dict:
    root = Path(root).resolve()
    path = core._safe_relative(root, relative)
    allowed = {os.path.normcase(str(candidate.resolve())) for candidate in core.script_paths(root)}
    if os.path.normcase(str(path.resolve())) not in allowed:
        raise core.ProjectZomboidError("Script is outside supported Build 42 script roots")
    data, text = core._read_utf8(path)
    if core.sha256_bytes(data) != expected_sha256:
        raise core.ProjectZomboidError("Script changed outside Lexeditor; reload before saving")
    if not isinstance(edits, dict) or not edits or set(edits) - set(EDITABLE_FIELDS):
        raise core.ProjectZomboidError("Save contains unsupported animationsMesh fields")

    matches = [(module, block) for module, block in _blocks(text)
               if module.name == module_name and block.name == mesh_id]
    if len(matches) != 1:
        raise core.ProjectZomboidError("Animations mesh identity is missing or ambiguous")
    _module, block = matches[0]
    values, duplicates = core._properties(text, block)
    unsafe = set(duplicates) & set(edits)
    if unsafe:
        raise core.ProjectZomboidError(
            "Cannot safely edit duplicated animationsMesh properties: " + ", ".join(sorted(unsafe))
        )
    missing = set(edits) - set(values)
    if missing:
        raise core.ProjectZomboidError(
            "Writer changes existing properties only; missing: " + ", ".join(sorted(missing))
        )

    validated = {key: _validate(key, value) for key, value in edits.items()}
    body_start = block.open_brace + 1
    body = text[body_start:block.close_brace]
    masked = core._masked_code(body)
    replacements: list[tuple[int, int, str]] = []
    depth = 0
    last = 0
    for match in core._PROPERTY_RE.finditer(body):
        for char in masked[last:match.start()]:
            if char == "{":
                depth += 1
            elif char == "}":
                depth = max(0, depth - 1)
        last = match.end()
        key = match.group("key")
        if depth == 0 and key in validated:
            replacements.append((
                body_start + match.start("value"),
                body_start + match.end("value"),
                validated[key],
            ))
    if len(replacements) != len(validated):
        raise core.ProjectZomboidError("Could not locate every animationsMesh property safely")

    output = text
    for start, end, value in sorted(replacements, reverse=True):
        output = output[:start] + value + output[end:]
    core._atomic_write(path, output.encode("utf-8"))
    return next(row for row in read(root)["rows"]
                if row["path"] == relative and row["module"] == module_name and row["id"] == mesh_id)
