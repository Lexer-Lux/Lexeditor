"""Conservative Build 42 timedAction editor.

The current schema independently types actionAnim as a string. Other timed-action
properties are references, arrays, marked useless, or insufficiently typed, so this
adapter leaves them read-only and preserves them verbatim.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

from . import core

EDITABLE_FIELDS = ("actionAnim",)


def _blocks(text: str) -> list[tuple[core.Block, core.Block]]:
    masked = core._masked_code(text)
    pattern = re.compile(r"\btimedAction\s+([^\s{]+(?:\s+[^\s{]+)*)\s*\{", re.IGNORECASE)
    result: list[tuple[core.Block, core.Block]] = []
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
            result.append((module, core.Block(
                "timedAction", match.group(1).strip(), match.start(), opened, closed
            )))
            cursor = closed + 1
            body_start = cursor
    return result


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
            rows.append({
                "key": f"{relative}:{module.name}.{block.name}",
                "path": relative,
                "module": module.name,
                "id": block.name,
                "fullType": f"{module.name}.{block.name}",
                "sha256": core.sha256_bytes(data),
                "fields": {"actionAnim": values.get("actionAnim", "")},
                "duplicateKeys": sorted(set(duplicates) & set(EDITABLE_FIELDS)),
            })
    return {"rows": rows, "errors": errors}


def _validate(value: object) -> str:
    clean = core._clean_scalar(value, "actionAnim", allow_empty=False)
    if any(char in clean for char in ",{}"):
        raise core.ProjectZomboidError("actionAnim contains script punctuation")
    return clean


def save(root: Path, relative: str, module_name: str, action_id: str,
         expected_sha256: str, edits: dict) -> dict:
    root = Path(root).resolve()
    path = core._safe_relative(root, relative)
    allowed = {os.path.normcase(str(candidate.resolve())) for candidate in core.script_paths(root)}
    if os.path.normcase(str(path.resolve())) not in allowed:
        raise core.ProjectZomboidError("Script is outside supported Build 42 script roots")
    data, text = core._read_utf8(path)
    if core.sha256_bytes(data) != expected_sha256:
        raise core.ProjectZomboidError("Script changed outside Lexeditor; reload before saving")
    if not isinstance(edits, dict) or set(edits) != {"actionAnim"}:
        raise core.ProjectZomboidError("Save requires only the supported timedAction actionAnim field")

    matches = [(module, block) for module, block in _blocks(text)
               if module.name == module_name and block.name == action_id]
    if len(matches) != 1:
        raise core.ProjectZomboidError("Timed action identity is missing or ambiguous")
    _module, block = matches[0]
    values, duplicates = core._properties(text, block)
    if "actionAnim" in duplicates:
        raise core.ProjectZomboidError("Cannot safely edit duplicated timedAction actionAnim")
    if "actionAnim" not in values:
        raise core.ProjectZomboidError("Writer changes existing properties only; missing: actionAnim")

    validated = _validate(edits["actionAnim"])
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
        if depth == 0 and match.group("key") == "actionAnim":
            replacements.append((
                body_start + match.start("value"),
                body_start + match.end("value"),
                validated,
            ))
    if len(replacements) != 1:
        raise core.ProjectZomboidError("Could not locate actionAnim safely")

    output = text
    for start, end, value in sorted(replacements, reverse=True):
        output = output[:start] + value + output[end:]
    core._atomic_write(path, output.encode("utf-8"))
    return next(row for row in read(root)["rows"]
                if row["path"] == relative and row["module"] == module_name and row["id"] == action_id)
