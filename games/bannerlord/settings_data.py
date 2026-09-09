"""Structured MCM default-setting editor for LexerSkillTweaks."""

from __future__ import annotations

import math
from pathlib import Path
import re
import shutil


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?[fFdDmM]?"
_STRING = r'"(?:\\.|[^"\\])*"'
_FIELD = re.compile(
    rf"(?m)^(?P<indent>[ \t]*)private\s+(?P<type>bool|float|int)\s+(?P<name>_[A-Za-z0-9_]+)"
    rf"(?:[ \t]*=[ \t]*(?P<value>[^;\r\n]+?))?[ \t]*;[ \t]*$"
)
_SETTING_HEADER = re.compile(
    rf"(?P<attribute>\[SettingProperty(?P<kind>Bool|FloatingInteger|Integer)\("
    rf"(?P<label>{_STRING})(?P<args>.*?)\)\]\s*)"
    rf"(?P<group>\[SettingPropertyGroup\((?P<groupName>{_STRING})(?P<groupArgs>.*?)\)\]\s*)"
    rf"public\s+(?P<type>bool|float|int)\s+(?P<property>[A-Za-z0-9_]+)\s*\{{",
    re.DOTALL,
)
_GETTER = re.compile(r"get\s*\{\s*return\s+(?P<field>_[A-Za-z0-9_]+)\s*;\s*\}", re.DOTALL)
_RESTART = re.compile(r"\bRequireRestart\s*=\s*(true|false)\b", re.IGNORECASE)
_ORDER = re.compile(r"\bOrder\s*=\s*(-?\d+)\b")
_GROUP_ORDER = re.compile(r"\bGroupOrder\s*=\s*(-?\d+)\b")
_HINT = re.compile(rf"\bHintText\s*=\s*(?P<value>{_STRING})", re.DOTALL)
_FLOAT_ARGS = re.compile(rf"^\s*,\s*(?P<min>{_NUMBER})\s*,\s*(?P<max>{_NUMBER})\s*,\s*(?P<format>{_STRING})", re.DOTALL)
_INT_ARGS = re.compile(r"^\s*,\s*(?P<min>-?\d+)\s*,\s*(?P<max>-?\d+)", re.DOTALL)


def _unquote(token: str) -> str:
    # MCM labels/hints in this file use normal escaped C# strings. Decode the
    # escapes we need without pretending to be a general C# parser.
    value = token[1:-1]
    return bytes(value, "utf-8").decode("unicode_escape")


def _number(token: str) -> float:
    token = token.strip()
    if token[-1:].casefold() in {"f", "d", "m"}:
        token = token[:-1]
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("Setting bound/default must be finite")
    return value


def _default_value(field_type: str, expression: str | None):
    if expression is None or not expression.strip():
        return False if field_type == "bool" else 0
    expression = expression.strip()
    if field_type == "bool":
        if expression.casefold() not in {"true", "false"}:
            raise ValueError(f"Unsupported bool default expression: {expression}")
        return expression.casefold() == "true"
    if field_type == "int":
        if not re.fullmatch(r"[-+]?\d+", expression):
            raise ValueError(f"Unsupported int default expression: {expression}")
        return int(expression)
    # Support the literal and literal/literal expressions actually used by the
    # project (for example 5f / 7f) without evaluating arbitrary C#.
    pieces = [piece.strip() for piece in expression.split("/")]
    if len(pieces) == 1 and re.fullmatch(_NUMBER, pieces[0]):
        return _number(pieces[0])
    if len(pieces) == 2 and all(re.fullmatch(_NUMBER, piece) for piece in pieces):
        denominator = _number(pieces[1])
        if denominator == 0:
            raise ValueError("Setting default divides by zero")
        return _number(pieces[0]) / denominator
    raise ValueError(f"Unsupported float default expression: {expression}")


def _literal(kind: str, value) -> str:
    if kind == "bool":
        return "true" if bool(value) else "false"
    if kind == "int":
        return str(int(value))
    number = float(value)
    text = format(number, ".9g")
    if "e" not in text.casefold() and "." not in text:
        text += ".0"
    return text + "f"


def _field_rows(text: str) -> dict[str, dict]:
    rows = {}
    for match in _FIELD.finditer(text):
        rows[match.group("name")] = {
            "type": match.group("type"),
            "expression": (match.group("value") or "").strip() or None,
            "span": match.span(),
            "indent": match.group("indent"),
        }
    return rows


def _matching_brace(text: str, open_index: int) -> int:
    depth = 0
    cursor = open_index
    while cursor < len(text):
        char = text[cursor]
        if char == '"':
            cursor += 1
            while cursor < len(text):
                if text[cursor] == "\\":
                    cursor += 2
                    continue
                if text[cursor] == '"':
                    cursor += 1
                    break
                cursor += 1
            continue
        if text.startswith("//", cursor):
            newline = text.find("\n", cursor + 2)
            cursor = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("/*", cursor):
            end = text.find("*/", cursor + 2)
            if end < 0:
                raise ValueError("Unterminated block comment in settings source")
            cursor = end + 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    raise ValueError("Unterminated property body in settings source")


def _parse_settings(text: str) -> list[dict]:
    fields = _field_rows(text)
    rows = []
    group_orders: dict[str, int] = {}
    for index, match in enumerate(_SETTING_HEADER.finditer(text)):
        open_index = match.end() - 1
        close_index = _matching_brace(text, open_index)
        body = text[open_index + 1:close_index]
        getter = _GETTER.search(body)
        if not getter:
            continue
        field_name = getter.group("field")
        field = fields.get(field_name)
        if not field:
            continue
        declared_type = match.group("type")
        if declared_type != field["type"]:
            continue
        kind_name = match.group("kind")
        if kind_name == "Bool":
            kind = "bool"
            minimum = maximum = None
            number_format = ""
        elif kind_name == "Integer":
            kind = "int"
            args = _INT_ARGS.match(match.group("args"))
            if not args:
                continue
            minimum, maximum = int(args.group("min")), int(args.group("max"))
            number_format = "0"
        else:
            kind = "float"
            args = _FLOAT_ARGS.match(match.group("args"))
            if not args:
                continue
            minimum, maximum = _number(args.group("min")), _number(args.group("max"))
            number_format = _unquote(args.group("format"))
        group_name = _unquote(match.group("groupName"))
        group_order_match = _GROUP_ORDER.search(match.group("groupArgs"))
        if group_order_match:
            group_orders[group_name] = int(group_order_match.group(1))
        restart_match = _RESTART.search(match.group("args"))
        order_match = _ORDER.search(match.group("args"))
        hint_match = _HINT.search(match.group("args"))
        default = _default_value(kind, field["expression"])
        rows.append({
            "index": index,
            "property": match.group("property"),
            "field": field_name,
            "label": _unquote(match.group("label")),
            "group": group_name,
            "groupOrder": group_orders.get(group_name, 999),
            "order": int(order_match.group(1)) if order_match else 0,
            "kind": kind,
            "min": minimum,
            "max": maximum,
            "format": number_format,
            "requireRestart": bool(restart_match and restart_match.group(1).casefold() == "true"),
            "hint": _unquote(hint_match.group("value")) if hint_match else "",
            "default": default,
            "defaultExpression": field["expression"] or "",
            "_fieldSpan": field["span"],
            "_indent": field["indent"],
        })
    rows.sort(key=lambda row: (row["groupOrder"], row["group"], row["order"], row["property"]))
    return rows


def read_mcm_defaults(project: Path) -> dict:
    path = project / "src" / "LexerSkillTweaksSettings.cs"
    if not path.is_file():
        return {"available": False, "path": str(path), "settings": [], "groups": []}
    text = path.read_text(encoding="utf-8-sig")
    rows = _parse_settings(text)
    if not rows:
        raise ValueError("LexerSkillTweaksSettings.cs has no supported typed MCM settings")
    public = [{key: value for key, value in row.items() if not key.startswith("_")} for row in rows]
    groups = []
    seen = set()
    for row in public:
        if row["group"] in seen:
            continue
        seen.add(row["group"])
        groups.append({"name": row["group"], "order": row["groupOrder"]})
    return {"available": True, "path": str(path), "settings": public, "groups": groups}


def save_mcm_defaults(project: Path, edits: list[dict]) -> dict:
    path = project / "src" / "LexerSkillTweaksSettings.cs"
    if not path.is_file():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8-sig")
    rows = _parse_settings(text)
    by_property = {row["property"]: row for row in rows}
    replacements: list[tuple[int, int, str]] = []
    changed = set()
    for edit in edits:
        property_name = str(edit.get("property") or "")
        row = by_property.get(property_name)
        if not row:
            raise ValueError(f"Unsupported MCM setting: {property_name}")
        incoming = edit.get("value")
        if row["kind"] == "bool":
            if not isinstance(incoming, bool):
                raise ValueError(f"{property_name} requires a boolean")
            value = incoming
        elif row["kind"] == "int":
            if isinstance(incoming, bool):
                raise ValueError(f"{property_name} requires an integer")
            numeric = float(incoming)
            if not math.isfinite(numeric) or not numeric.is_integer():
                raise ValueError(f"{property_name} requires an integer")
            value = int(numeric)
        else:
            value = float(incoming)
            if not math.isfinite(value):
                raise ValueError(f"{property_name} requires a finite number")
        if row["min"] is not None and value < row["min"]:
            raise ValueError(f"{property_name} cannot be below {row['min']}")
        if row["max"] is not None and value > row["max"]:
            raise ValueError(f"{property_name} cannot exceed {row['max']}")
        if value == row["default"]:
            continue
        left, right = row["_fieldSpan"]
        replacement = f"{row['_indent']}private {row['kind']} {row['field']} = {_literal(row['kind'], value)};"
        replacements.append((left, right, replacement))
        changed.add(property_name)

    candidate = text
    for left, right, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:left] + replacement + candidate[right:]
    check = _parse_settings(candidate)
    if [row["property"] for row in check] != [row["property"] for row in rows]:
        raise ValueError("Saving changed the supported MCM setting schema; refusing the write")

    backup = path.with_name(path.name + ".lexeditor.bak")
    if changed:
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        temporary.write_text(candidate, encoding="utf-8")
        temporary.replace(path)
    result = read_mcm_defaults(project)
    result.update({"saved": len(changed), "backup": str(backup) if changed else ""})
    return result
