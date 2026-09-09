"""Structured editors for LexerSkillTweaks perks and XP-source defaults."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import shutil

from .paths import clear_write_helper, contained_project_path


_STRING = r'"(?:\\.|[^"\\])*"'
_NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?[fFdDmM]?'

_PERK_CALL = re.compile(
    rf"\bPerk\s*\(\s*"
    rf"(?P<skillId>{_STRING})\s*,\s*"
    rf"(?P<level>\d+)\s*,\s*"
    rf"(?P<name>{_STRING})\s*,\s*"
    rf"(?P<description>{_STRING})"
    rf"(?:\s*,\s*(?P<implemented>true|false))?\s*\)",
    re.MULTILINE | re.IGNORECASE,
)

_XP_SOURCE_CALL = re.compile(
    rf"\bSource\s*\(\s*"
    rf"(?P<skillId>{_STRING})\s*,\s*"
    rf"(?P<label>{_STRING})\s*,\s*"
    rf"(?P<defaultAmount>{_NUMBER})\s*\)",
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
        raise ValueError("Value must be finite")
    return value


def _float_literal(value) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Value must be finite")
    if abs(number) > 1_000_000_000:
        raise ValueError("Value magnitude is too large")
    text = format(number, ".9g")
    if "e" not in text.casefold() and "." not in text:
        text += ".0"
    return text + "f"


def _public(row: dict) -> dict:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _perk_records(text: str) -> list[dict]:
    rows = []
    for index, match in enumerate(_PERK_CALL.finditer(text)):
        skill_id = _decode_string(match.group("skillId"))
        rows.append(
            {
                "index": index,
                "line": text.count("\n", 0, match.start()) + 1,
                # Index is part of the editor identity because multiple perks can
                # share a skill and level (Athletics intentionally does).
                "id": f"{skill_id}.{index}",
                "skillId": skill_id,
                "level": int(match.group("level")),
                "name": _decode_string(match.group("name")),
                "description": _decode_string(match.group("description")),
                "implemented": (match.group("implemented") or "true").casefold() == "true",
                "_spans": {
                    "level": match.span("level"),
                    "description": match.span("description"),
                },
            }
        )
    return rows


def read_perk_definitions(project: Path) -> dict:
    path = _source_path(project, "CustomSkillPerks.cs")
    if not path.is_file():
        return {"available": False, "path": str(path), "perks": []}
    text = path.read_text(encoding="utf-8-sig")
    rows = _perk_records(text)
    if not rows:
        raise ValueError(
            "CustomSkillPerks.cs does not match the supported Perk(skill, level, name, description, implemented) shape"
        )
    return {"available": True, "path": str(path), "perks": [_public(row) for row in rows]}


def save_perk_definitions(project: Path, edits: list[dict]) -> dict:
    """Edit only balance-safe perk fields; lookup identity remains stable."""
    path = _source_path(project, "CustomSkillPerks.cs", require_file=True)
    text = path.read_text(encoding="utf-8-sig")
    rows = _perk_records(text)
    by_index = {row["index"]: row for row in rows}
    replacements: list[tuple[int, int, str]] = []
    changed_records: set[int] = set()
    for edit in edits:
        index = int(edit.get("index", -1))
        row = by_index.get(index)
        if row is None:
            raise ValueError(f"Perk {index} no longer exists")
        original_id = str(edit.get("originalId") or "")
        if original_id and original_id != row["id"]:
            raise ValueError(f"Perk {index} changed identity; reload before saving")
        fields = dict(edit.get("fields") or {})
        unknown = set(fields) - {"level", "description"}
        if unknown:
            raise ValueError(f"Unsupported perk fields: {', '.join(sorted(unknown))}")
        if "level" in fields:
            level = int(fields["level"])
            if not 0 <= level <= 100:
                raise ValueError("Perk level must be between 0 and 100")
            if level != row["level"]:
                left, right = row["_spans"]["level"]
                replacements.append((left, right, str(level)))
                changed_records.add(index)
        if "description" in fields:
            description = str(fields["description"])
            if description != row["description"]:
                left, right = row["_spans"]["description"]
                replacements.append((left, right, _encode_string(description)))
                changed_records.add(index)

    candidate = text
    for left, right, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:left] + replacement + candidate[right:]
    check = _perk_records(candidate)
    stable = lambda values: [
        (row["skillId"], row["name"], row["implemented"])
        for row in values
    ]
    if len(check) != len(rows) or stable(check) != stable(rows):
        raise ValueError("Saving changed perk identities/implementation flags; refusing the write")

    backup = path.with_name(path.name + ".lexeditor.bak")
    if changed_records:
        clear_write_helper(backup)
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        clear_write_helper(temporary)
        temporary.write_text(candidate, encoding="utf-8")
        temporary.replace(path)
    result = read_perk_definitions(project)
    result.update({"saved": len(changed_records), "backup": str(backup) if changed_records else ""})
    return result


def _xp_source_records(text: str) -> list[dict]:
    rows = []
    for index, match in enumerate(_XP_SOURCE_CALL.finditer(text)):
        skill_id = _decode_string(match.group("skillId"))
        label = _decode_string(match.group("label"))
        rows.append(
            {
                "index": index,
                "line": text.count("\n", 0, match.start()) + 1,
                "id": skill_id + "." + label.replace(" ", ""),
                "skillId": skill_id,
                "label": label,
                "defaultAmount": _float_value(match.group("defaultAmount")),
                "_spans": {"defaultAmount": match.span("defaultAmount")},
            }
        )
    return rows


def read_xp_source_definitions(project: Path) -> dict:
    path = _source_path(project, "CustomSkillXpSourcesConfig.cs")
    if not path.is_file():
        return {"available": False, "path": str(path), "sources": []}
    text = path.read_text(encoding="utf-8-sig")
    rows = _xp_source_records(text)
    if not rows:
        raise ValueError(
            "CustomSkillXpSourcesConfig.cs does not match the supported Source(skill, label, defaultAmount) shape"
        )
    return {"available": True, "path": str(path), "sources": [_public(row) for row in rows]}


def save_xp_source_definitions(project: Path, edits: list[dict]) -> dict:
    """Edit fallback XP awards while keeping source lookup keys stable."""
    path = _source_path(project, "CustomSkillXpSourcesConfig.cs", require_file=True)
    text = path.read_text(encoding="utf-8-sig")
    rows = _xp_source_records(text)
    by_index = {row["index"]: row for row in rows}
    replacements: list[tuple[int, int, str]] = []
    changed_records: set[int] = set()
    for edit in edits:
        index = int(edit.get("index", -1))
        row = by_index.get(index)
        if row is None:
            raise ValueError(f"XP source {index} no longer exists")
        original_id = str(edit.get("originalId") or "")
        if original_id and original_id != row["id"]:
            raise ValueError(f"XP source {index} changed identity; reload before saving")
        fields = dict(edit.get("fields") or {})
        unknown = set(fields) - {"defaultAmount"}
        if unknown:
            raise ValueError(f"Unsupported XP source fields: {', '.join(sorted(unknown))}")
        if "defaultAmount" not in fields:
            continue
        amount = float(fields["defaultAmount"])
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("XP source amount must be a finite non-negative number")
        if amount > 1_000_000_000:
            raise ValueError("XP source amount is too large")
        if amount != row["defaultAmount"]:
            left, right = row["_spans"]["defaultAmount"]
            replacements.append((left, right, _float_literal(amount)))
            changed_records.add(index)

    candidate = text
    for left, right, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:left] + replacement + candidate[right:]
    check = _xp_source_records(candidate)
    if len(check) != len(rows) or [row["id"] for row in check] != [row["id"] for row in rows]:
        raise ValueError("Saving changed XP source identities; refusing the write")

    backup = path.with_name(path.name + ".lexeditor.bak")
    if changed_records:
        clear_write_helper(backup)
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        clear_write_helper(temporary)
        temporary.write_text(candidate, encoding="utf-8")
        temporary.replace(path)
    result = read_xp_source_definitions(project)
    result.update({"saved": len(changed_records), "backup": str(backup) if changed_records else ""})
    return result


STRUCTURED_SOURCE_ROWS = {
    "src/CustomSkillPerks.cs": {
        "area": "Perks",
        "controls": "Custom skill perk levels, descriptions, and implementation status",
        "target": "perks",
        "notes": "Structured editor for safe perk fields; lookup identity and implementation status stay fixed.",
    },
    "src/CustomSkillXpSourcesConfig.cs": {
        "area": "XP Sources",
        "controls": "Custom skill XP source fallback award amounts",
        "target": "xp",
        "notes": "Structured editor for Source(...) default XP amounts while source identities stay fixed.",
    },
    "src/LexerSkillTweaksSettings.cs": {
        "area": "Settings",
        "controls": "Typed MCM boolean, integer, and floating-point source defaults",
        "target": "settings",
        "notes": "Structured editor derives types, bounds, restart requirements, groups, labels, and hints from MCM attributes.",
    },
}


def augment_data_map(payload: dict) -> dict:
    """Promote only C# files for which this module exposes real structured editors."""
    rows = [dict(row) for row in payload.get("rows", [])]
    for row in rows:
        spec = STRUCTURED_SOURCE_ROWS.get(row.get("filename"))
        if not spec:
            continue
        row.update(
            {
                "area": spec["area"],
                "controls": spec["controls"],
                "coverage": "structured",
                "status": "integrated",
                "target": spec["target"],
                "targets": [spec["target"]],
                "openable": True,
                "sourceOpenable": True,
                "notes": spec["notes"],
            }
        )
    return {"rows": rows}
