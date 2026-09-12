"""Conservative structured editor for current Build 42 craftRecipe scalars.

Only schema fields with explicit primitive types in the current pz-scripts-data
craftRecipe definition are writable here. Nested inputs/outputs and callbacks stay
read-only and byte-preserved.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

from . import core

EDITABLE_FIELDS = (
    "AllowBatchCraft",
    "CanWalk",
    "category",
    "Icon",
    "ResearchSkillLevel",
    "tags",
    "time",
    "timedAction",
)
BOOLEAN_FIELDS = {"AllowBatchCraft", "CanWalk"}
INTEGER_FIELDS = {"ResearchSkillLevel", "time"}


def _module_blocks(text: str) -> list[tuple[core.Block, core.Block]]:
    masked = core._masked_code(text)
    pattern = re.compile(r"\bcraftRecipe\s+([^\s{]+(?:\s+[^\s{]+)*)\s*\{", re.IGNORECASE)
    found: list[tuple[core.Block, core.Block]] = []
    for module in core._top_level_blocks(text, "module"):
        cursor = module.open_brace + 1
        body_start = cursor
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
            if depth != 0:
                cursor = match.end()
                continue
            open_brace = masked.find("{", match.start(), match.end())
            close_brace = core._matching_brace(masked, open_brace, module.close_brace)
            found.append((
                module,
                core.Block("craftRecipe", match.group(1).strip(), match.start(), open_brace, close_brace),
            ))
            cursor = close_brace + 1
            body_start = cursor
    return found


def read(root: Path) -> dict:
    root = root.resolve()
    rows, errors = [], []
    for path in core.script_paths(root):
        data, text = core._read_utf8(path)
        relative = path.relative_to(root).as_posix()
        try:
            pairs = _module_blocks(text)
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
                "fields": {key: values.get(key, "") for key in EDITABLE_FIELDS},
                "duplicateKeys": sorted(set(duplicates) & set(EDITABLE_FIELDS)),
                "hasInputs": bool(re.search(r"\binputs\s*\{", core._masked_code(text[block.open_brace + 1:block.close_brace]), re.IGNORECASE)),
                "hasOutputs": bool(re.search(r"\boutputs\s*\{", core._masked_code(text[block.open_brace + 1:block.close_brace]), re.IGNORECASE)),
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
    if key in INTEGER_FIELDS:
        try:
            number = int(clean)
        except ValueError as error:
            raise core.ProjectZomboidError(f"{key} must be an integer") from error
        return str(number)
    if key == "tags":
        tags = [part.strip() for part in clean.split(";") if part.strip()]
        if not tags:
            raise core.ProjectZomboidError("tags cannot be empty")
        if any(any(ch.isspace() for ch in tag) for tag in tags):
            raise core.ProjectZomboidError("tags entries cannot contain spaces")
        return ";".join(tags)
    return clean


def save(root: Path, relative: str, module_name: str, recipe_id: str,
         expected_sha256: str, edits: dict) -> dict:
    root = root.resolve()
    path = core._safe_relative(root, relative)
    allowed = {os.path.normcase(str(candidate.resolve())) for candidate in core.script_paths(root)}
    if os.path.normcase(str(path.resolve())) not in allowed:
        raise core.ProjectZomboidError("Script is outside supported Build 42 script roots")
    data, text = core._read_utf8(path)
    if core.sha256_bytes(data) != expected_sha256:
        raise core.ProjectZomboidError("Script changed outside Lexeditor; reload before saving")
    if not isinstance(edits, dict) or not edits or set(edits) - set(EDITABLE_FIELDS):
        raise core.ProjectZomboidError("Save contains unsupported craftRecipe fields")

    matches = [(module, block) for module, block in _module_blocks(text)
               if module.name == module_name and block.name == recipe_id]
    if len(matches) != 1:
        raise core.ProjectZomboidError("Craft recipe identity is missing or ambiguous")
    _module, block = matches[0]
    values, duplicates = core._properties(text, block)
    unsafe = set(duplicates) & set(edits)
    if unsafe:
        raise core.ProjectZomboidError("Cannot safely edit duplicated craftRecipe properties: " + ", ".join(sorted(unsafe)))
    missing = set(edits) - set(values)
    if missing:
        raise core.ProjectZomboidError("Writer changes existing properties only; missing: " + ", ".join(sorted(missing)))

    validated = {key: _validate(key, value) for key, value in edits.items()}
    body_start, body_end = block.open_brace + 1, block.close_brace
    body = text[body_start:body_end]
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
            replacements.append((body_start + match.start("value"), body_start + match.end("value"), validated[key]))
    if len(replacements) != len(validated):
        raise core.ProjectZomboidError("Could not locate every craftRecipe property safely")

    output = text
    for start, end, value in sorted(replacements, reverse=True):
        output = output[:start] + value + output[end:]
    core._atomic_write(path, output.encode("utf-8"))
    return next(row for row in read(root)["rows"]
                if row["path"] == relative and row["module"] == module_name and row["id"] == recipe_id)
