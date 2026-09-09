"""Structured editors for LexerSkillTweaks custom skills and quantitative ranges."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import shutil

from .paths import clear_write_helper, contained_project_path


_STRING = r'"(?:\\.|[^"\\])*"'
_NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?[fFdDmM]?'

_ATTRIBUTE_CALL = re.compile(
    rf"new\s+AttributeDefinition\s*\(\s*"
    rf"(?P<stringId>{_STRING})\s*,\s*"
    rf"(?P<name>{_STRING})\s*,\s*"
    rf"(?P<abbreviation>{_STRING})\s*,\s*"
    rf"(?P<description>{_STRING})\s*\)",
    re.MULTILINE,
)

_SKILL_CALL = re.compile(
    rf"new\s+SkillDefinition\s*\(\s*"
    rf"(?P<stringId>{_STRING})\s*,\s*"
    rf"(?P<name>{_STRING})\s*,\s*"
    rf"(?P<description>{_STRING})\s*,\s*"
    rf"(?P<howToLearn>{_STRING})\s*,\s*"
    rf"(?P<attributeId>{_STRING})\s*\)",
    re.MULTILINE,
)

_EFFECT_CALL = re.compile(
    rf"\bEffect\s*\(\s*"
    rf"(?P<skillId>{_STRING})\s*,\s*"
    rf"(?P<label>{_STRING})\s*,\s*"
    rf"(?P<defaultLow>{_NUMBER})\s*,\s*"
    rf"(?P<defaultHigh>{_NUMBER})\s*,\s*"
    rf"(?P<suffix>{_STRING})\s*\)",
    re.MULTILINE,
)


def _source_path(project: Path, filename: str, *, require_file: bool = False) -> Path:
    return contained_project_path(project, "src", filename, require_file=require_file)


def _decode_string(token: str) -> str:
    try:
        return json.loads(token)
    except json.JSONDecodeError as error:
        raise ValueError(f"Unsupported C# string literal: {token}") from error


def _encode_string(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _float_value(token: str) -> float:
    token = token.strip()
    if token[-1:].casefold() in {"f", "d", "m"}:
        token = token[:-1]
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("Effect values must be finite numbers")
    return value


def _float_literal(value) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Effect values must be finite numbers")
    if abs(number) > 1_000_000_000:
        raise ValueError("Effect value magnitude is too large")
    text = format(number, ".9g")
    if "e" not in text.casefold() and "." not in text:
        text += ".0"
    return text + "f"


def _definition_records(text: str, pattern: re.Pattern, fields: tuple[str, ...]) -> list[dict]:
    rows = []
    for index, match in enumerate(pattern.finditer(text)):
        row = {
            "index": index,
            "line": text.count("\n", 0, match.start()) + 1,
            "_matchSpan": match.span(),
            "_spans": {},
        }
        for field in fields:
            row[field] = _decode_string(match.group(field))
            row["_spans"][field] = match.span(field)
        rows.append(row)
    return rows


def _public(row: dict) -> dict:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def read_skill_definitions(project: Path) -> dict:
    path = _source_path(project, "CustomSkillDefinitions.cs")
    if not path.is_file():
        return {
            "available": False,
            "path": str(path),
            "attributes": [],
            "skills": [],
        }
    text = path.read_text(encoding="utf-8-sig")
    attributes = _definition_records(
        text,
        _ATTRIBUTE_CALL,
        ("stringId", "name", "abbreviation", "description"),
    )
    skills = _definition_records(
        text,
        _SKILL_CALL,
        ("stringId", "name", "description", "howToLearn", "attributeId"),
    )
    if not attributes or not skills:
        raise ValueError(
            "CustomSkillDefinitions.cs does not match the supported AttributeDefinition/SkillDefinition initializer shape"
        )
    return {
        "available": True,
        "path": str(path),
        "attributes": [_public(row) for row in attributes],
        "skills": [_public(row) for row in skills],
    }


def _apply_string_edits(
    text: str,
    rows: list[dict],
    edits: list[dict],
    allowed: set[str],
    valid_attributes: set[str] | None = None,
) -> tuple[str, int]:
    by_index = {row["index"]: row for row in rows}
    replacements: list[tuple[int, int, str]] = []
    changed_records: set[int] = set()
    for edit in edits:
        index = int(edit.get("index", -1))
        row = by_index.get(index)
        if row is None:
            raise ValueError(f"Definition {index} no longer exists")
        original_id = str(edit.get("originalId") or "")
        if original_id and original_id != row["stringId"]:
            raise ValueError(
                f"Definition {index} changed from {original_id} to {row['stringId']}; reload before saving"
            )
        fields = dict(edit.get("fields") or {})
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unsupported definition fields: {', '.join(sorted(unknown))}")
        for field, incoming in fields.items():
            value = str(incoming)
            if field in {"name", "abbreviation", "attributeId"}:
                value = value.strip()
                if not value:
                    raise ValueError(f"{field} cannot be empty")
            if field == "attributeId" and valid_attributes is not None and value not in valid_attributes:
                raise ValueError(f"Unknown custom attribute: {value}")
            if value == row[field]:
                continue
            left, right = row["_spans"][field]
            replacements.append((left, right, _encode_string(value)))
            changed_records.add(index)
    candidate = text
    for left, right, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:left] + replacement + candidate[right:]
    return candidate, len(changed_records)


def save_skill_definitions(project: Path, payload: dict) -> dict:
    path = _source_path(project, "CustomSkillDefinitions.cs", require_file=True)
    unknown = set(payload) - {"attributes", "skills"}
    if unknown:
        raise ValueError(f"Unsupported skill sections: {', '.join(sorted(unknown))}")

    text = path.read_text(encoding="utf-8-sig")
    attributes = _definition_records(
        text,
        _ATTRIBUTE_CALL,
        ("stringId", "name", "abbreviation", "description"),
    )
    skills = _definition_records(
        text,
        _SKILL_CALL,
        ("stringId", "name", "description", "howToLearn", "attributeId"),
    )
    attribute_ids = {row["stringId"] for row in attributes}

    candidate, attribute_changes = _apply_string_edits(
        text,
        attributes,
        list(payload.get("attributes") or []),
        {"name", "abbreviation", "description"},
    )
    candidate_skills = _definition_records(
        candidate,
        _SKILL_CALL,
        ("stringId", "name", "description", "howToLearn", "attributeId"),
    )
    candidate, skill_changes = _apply_string_edits(
        candidate,
        candidate_skills,
        list(payload.get("skills") or []),
        {"name", "description", "howToLearn", "attributeId"},
        valid_attributes=attribute_ids,
    )

    check_attributes = _definition_records(
        candidate,
        _ATTRIBUTE_CALL,
        ("stringId", "name", "abbreviation", "description"),
    )
    check_skills = _definition_records(
        candidate,
        _SKILL_CALL,
        ("stringId", "name", "description", "howToLearn", "attributeId"),
    )
    if len(check_attributes) != len(attributes) or len(check_skills) != len(skills):
        raise ValueError("Saving changed the number of custom skill definitions; refusing the write")
    if [row["stringId"] for row in check_attributes] != [row["stringId"] for row in attributes]:
        raise ValueError("Saving changed custom attribute IDs; refusing the write")
    if [row["stringId"] for row in check_skills] != [row["stringId"] for row in skills]:
        raise ValueError("Saving changed custom skill IDs; refusing the write")

    changed = attribute_changes + skill_changes
    backup = path.with_name(path.name + ".lexeditor.bak")
    if changed:
        clear_write_helper(backup)
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        clear_write_helper(temporary)
        temporary.write_text(candidate, encoding="utf-8")
        temporary.replace(path)
    result = read_skill_definitions(project)
    result.update({"saved": changed, "backup": str(backup) if changed else ""})
    return result


def _effect_records(text: str) -> list[dict]:
    rows = []
    for index, match in enumerate(_EFFECT_CALL.finditer(text)):
        skill_id = _decode_string(match.group("skillId"))
        label = _decode_string(match.group("label"))
        row = {
            "index": index,
            "line": text.count("\n", 0, match.start()) + 1,
            "id": skill_id + "." + label.replace(" ", ""),
            "skillId": skill_id,
            "label": label,
            "defaultLow": _float_value(match.group("defaultLow")),
            "defaultHigh": _float_value(match.group("defaultHigh")),
            "suffix": _decode_string(match.group("suffix")),
            "_spans": {
                "defaultLow": match.span("defaultLow"),
                "defaultHigh": match.span("defaultHigh"),
            },
        }
        rows.append(row)
    return rows


def read_effect_definitions(project: Path) -> dict:
    path = _source_path(project, "CustomSkillEffectRanges.cs")
    if not path.is_file():
        return {"available": False, "path": str(path), "effects": []}
    text = path.read_text(encoding="utf-8-sig")
    rows = _effect_records(text)
    if not rows:
        raise ValueError(
            "CustomSkillEffectRanges.cs does not match the supported Effect(...) initializer shape"
        )
    return {
        "available": True,
        "path": str(path),
        "effects": [_public(row) for row in rows],
    }


def save_effect_definitions(project: Path, edits: list[dict]) -> dict:
    path = _source_path(project, "CustomSkillEffectRanges.cs", require_file=True)
    text = path.read_text(encoding="utf-8-sig")
    rows = _effect_records(text)
    by_index = {row["index"]: row for row in rows}
    replacements: list[tuple[int, int, str]] = []
    changed_records: set[int] = set()

    for edit in edits:
        index = int(edit.get("index", -1))
        row = by_index.get(index)
        if row is None:
            raise ValueError(f"Effect {index} no longer exists")
        original_id = str(edit.get("originalId") or "")
        if original_id and original_id != row["id"]:
            raise ValueError(
                f"Effect {index} changed from {original_id} to {row['id']}; reload before saving"
            )
        fields = dict(edit.get("fields") or {})
        unknown = set(fields) - {"defaultLow", "defaultHigh"}
        if unknown:
            raise ValueError(f"Unsupported effect fields: {', '.join(sorted(unknown))}")
        for field, incoming in fields.items():
            value = float(incoming)
            if not math.isfinite(value):
                raise ValueError("Effect values must be finite")
            if value == row[field]:
                continue
            left, right = row["_spans"][field]
            replacements.append((left, right, _float_literal(value)))
            changed_records.add(index)

    candidate = text
    for left, right, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:left] + replacement + candidate[right:]
    check = _effect_records(candidate)
    if len(check) != len(rows) or [row["id"] for row in check] != [row["id"] for row in rows]:
        raise ValueError("Saving changed quantitative effect identities; refusing the write")

    backup = path.with_name(path.name + ".lexeditor.bak")
    if changed_records:
        clear_write_helper(backup)
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        clear_write_helper(temporary)
        temporary.write_text(candidate, encoding="utf-8")
        temporary.replace(path)
    result = read_effect_definitions(project)
    result.update(
        {
            "saved": len(changed_records),
            "backup": str(backup) if changed_records else "",
        }
    )
    return result
