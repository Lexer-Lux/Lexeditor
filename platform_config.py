"""Typed, lossless editors for game mod-platform configuration files."""

from __future__ import annotations

import hashlib
import ast
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess

import process_probe
import tempfile


_ASSIGNMENT = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_.-]+)(?P<space>\s*=\s*)(?P<value>.*?)(?P<ending>\r?\n)?$")
_SECTION = re.compile(r"^\s*\[([^]]+)]\s*(?:[;#].*)?$")
_INI_ASSIGNMENT = re.compile(r"^(?P<indent>\s*)(?P<key>[^=;#][^=]*?)(?P<space>\s*=\s*)(?P<value>.*?)(?P<ending>\r?\n)?$")
_HEADING = re.compile(r"^#\[([^]]+)]\s*$")
_GROUP = re.compile(r"^##\s+([^#].*?)\s*$")
_CHOICE = re.compile(r"^[-*]?\s*(-?\d+)\s*[:=]\s*(.+?)\s*$")
_RANGE = re.compile(r"(?<![\d.])(-?\d+(?:\.\d+)?)\s*(?:\.\.|\bto\b)\s*(-?\d+(?:\.\d+)?)", re.I)
_MAX_STRING = 4096


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _title(key: str) -> str:
    return re.sub(r"[_\-.]+", " ", key).strip().title()


def _clean_comments(lines: list[str]) -> list[str]:
    result = []
    for raw in lines:
        text = raw.strip().lstrip("#;").strip()
        if not text or set(text) <= {"~", "#", "-", "="} or _HEADING.match(raw.strip()):
            continue
        result.append(text)
    return result


def _choices(comments: list[str]) -> list[dict]:
    values = []
    for text in _clean_comments(comments):
        match = _CHOICE.match(text)
        if match:
            values.append({"value": int(match.group(1)), "label": match.group(2).strip(" .")})
    unique = {item["value"]: item for item in values}
    return list(unique.values()) if 1 < len(unique) <= 24 else []


def _bounds(comments: list[str], integer: bool) -> tuple[int | float, int | float]:
    for text in _clean_comments(comments):
        match = _RANGE.search(text)
        if match:
            low, high = (float(match.group(1)), float(match.group(2)))
            if low <= high:
                return (int(low), int(high)) if integer else (low, high)
    return (-2147483648, 2147483647) if integer else (-1_000_000_000.0, 1_000_000_000.0)


def _toml_scalar(text: str, key: str):
    value = text.strip()
    lowered = value.casefold()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if re.fullmatch(r"[-+]?\d[\d_]*", value):
        return int(value.replace("_", ""), 10)
    if re.fullmatch(r"[-+]?(?:\d[\d_]*\.\d[\d_]*|\d[\d_]*[eE][-+]?\d+)", value):
        return float(value.replace("_", ""))
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        python_value = re.sub(r"\btrue\b", "True", value, flags=re.I)
        python_value = re.sub(r"\bfalse\b", "False", python_value, flags=re.I)
        parsed = ast.literal_eval(python_value)
        if isinstance(parsed, (str, int, float, bool, list)):
            return parsed
        raise ValueError(f"Unsupported TOML value for {key}")


def _field(field_id: str, section: str, key: str, value, comments: list[str], line: int, fmt: str) -> dict:
    cleaned = _clean_comments(comments)
    label_match = next((_HEADING.match(item.strip()) for item in reversed(comments) if _HEADING.match(item.strip())), None)
    label = label_match.group(1).strip() if label_match else _title(key)
    description = " ".join(text for text in cleaned if text.casefold() != label.casefold())
    choices = _choices(comments)
    if isinstance(value, bool):
        kind, minimum, maximum, step = "boolean", None, None, None
    elif isinstance(value, int) and not isinstance(value, bool):
        minimum, maximum = _bounds(comments, True)
        kind, step = ("enum", None) if choices and value in {choice["value"] for choice in choices} else ("integer", 1)
    elif isinstance(value, float):
        minimum, maximum = _bounds(comments, False)
        kind, step = "number", 0.01
    elif isinstance(value, list):
        kind, minimum, maximum, step = "list", None, None, None
    else:
        kind, minimum, maximum, step = "string", None, None, None
    return {
        "id": field_id, "section": section, "key": key, "label": label,
        "description": description, "kind": kind, "value": value,
        "minimum": minimum, "maximum": maximum, "step": step,
        "choices": choices, "line": line, "format": fmt,
    }


# FFNx.toml states which options belong to one game only, with headings like
# "OPTIONS ONLY FOR FF7". Reading those markers keeps the split correct if
# FFNx moves an option, instead of pinning a list that silently goes stale.
_ONLY_FOR = re.compile(r"^#+\s*OPTIONS ONLY FOR\s+([A-Z0-9]+)\s*$", re.I)


def _toml_fields(text: str) -> list[dict]:
    fields, comments, section = [], [], "General"
    only_for = None
    for index, line in enumerate(text.splitlines(keepends=True)):
        stripped = line.strip()
        if stripped.startswith("#"):
            marker = _ONLY_FOR.match(stripped)
            if marker:
                only_for = marker.group(1).upper()
                comments = []
                continue
            group = _GROUP.match(stripped)
            if group:
                section = group.group(1).strip(" .")
                comments = []
                continue
            if set(stripped.lstrip("#")) == {"#"}:
                comments = []
            else:
                comments.append(stripped)
            continue
        if not stripped:
            continue
        heading = _HEADING.match(stripped)
        if heading:
            comments.append(stripped)
            continue
        match = _ASSIGNMENT.match(line)
        if not match:
            comments = []
            continue
        key = match.group("key")
        try:
            value = _toml_scalar(match.group("value"), key)
        except (ValueError, SyntaxError, TypeError):
            comments = []
            continue
        entry = _field(key, section, key, value, comments, index, "toml")
        entry["onlyFor"] = only_for
        fields.append(entry)
        comments = []
    return fields


def _ini_value(raw: str, key: str, comments: list[str]):
    text = raw.strip()
    lowered = text.casefold()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if re.fullmatch(r"[-+]?\d+", text):
        value = int(text)
        comment = " ".join(_clean_comments(comments)).casefold()
        key_lower = key.casefold()
        if value in {0, 1} and ("enable" in key_lower or "enabled" in comment or "disabled" in comment):
            return bool(value)
        return value
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)", text):
        return float(text)
    return text


def _ini_fields(text: str) -> list[dict]:
    fields, comments, section = [], [], "General"
    for index, line in enumerate(text.splitlines(keepends=True)):
        stripped = line.strip()
        if stripped.startswith((";", "#")):
            comments.append(stripped)
            continue
        if not stripped:
            continue
        section_match = _SECTION.match(line)
        if section_match:
            section, comments = section_match.group(1).strip(), []
            continue
        match = _INI_ASSIGNMENT.match(line)
        if not match:
            comments = []
            continue
        key = match.group("key").strip()
        value = _ini_value(match.group("value"), key, comments)
        fields.append(_field(f"{section}.{key}", section, key, value, comments, index, "ini"))
        comments = []
    return fields


def _sections(fields: list[dict]) -> list[dict]:
    ordered: list[dict] = []
    by_name: dict[str, dict] = {}
    for field in fields:
        section = by_name.get(field["section"])
        if section is None:
            section = {"id": field["section"], "label": field["section"], "fields": []}
            by_name[field["section"]] = section
            ordered.append(section)
        section["fields"].append(field)
    return ordered


def load_config(path: Path, runtime: str, fmt: str, game: str = "") -> dict:
    path = Path(path)
    if not path.is_file():
        return {
            "available": False, "runtime": runtime, "format": fmt, "path": str(path),
            "sha256": None, "sections": [],
            "message": f"{runtime} is not installed here, or {path.name} has not been created yet.",
        }
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    fields = _toml_fields(text) if fmt == "toml" else _ini_fields(text)
    if game:
        # A shared runtime config carries options for other games. Showing
        # them here invites edits that can never take effect.
        wanted = game.strip().upper()
        fields = [field for field in fields
                  if not field.get("onlyFor") or field["onlyFor"] == wanted]
    return {
        "available": True, "runtime": runtime, "format": fmt, "path": str(path),
        "sha256": _sha256(raw), "sections": _sections(fields),
        "message": f"Editing the installed {runtime} configuration. Lexeditor preserves comments and file order.",
    }


def _validate(field: dict, value):
    kind = field["kind"]
    if kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{field['label']} must be true or false")
        return value
    if kind in {"integer", "enum"}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field['label']} must be a whole number")
        if kind == "enum" and value not in {choice["value"] for choice in field["choices"]}:
            raise ValueError(f"{field['label']} is not an available choice")
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{field['label']} must be a finite number")
        value = float(value)
    elif kind == "list":
        if not isinstance(value, list) or len(value) > 256 or any(not isinstance(item, (str, int, float, bool)) for item in value):
            raise ValueError(f"{field['label']} must be a short list of scalar values")
    else:
        if not isinstance(value, str) or len(value) > _MAX_STRING or "\n" in value or "\r" in value:
            raise ValueError(f"{field['label']} must be one line of text")
    minimum, maximum = field.get("minimum"), field.get("maximum")
    if kind in {"integer", "number"} and (value < minimum or value > maximum):
        raise ValueError(f"{field['label']} must be between {minimum} and {maximum}")
    return value


def _toml_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def _ini_text(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _running(executables: tuple[str, ...]) -> bool:
    """Is one of these games genuinely running right now?

    Matching on the image name alone is not enough. Windows keeps listing a
    terminated process for as long as anything holds a handle to it, and those
    entries have no threads and cannot be killed. Counting them as running
    made this refuse every save with "close the game" while no game was open.
    """
    if os.name != "nt":
        return False
    return bool(process_probe.live_processes(executables))


def save_config(path: Path, runtime: str, fmt: str, expected_sha256: str, changes: dict,
                executables: tuple[str, ...] = ()) -> dict:
    path = Path(path)
    if executables and _running(executables):
        raise RuntimeError(f"Close the game before saving {runtime} settings")
    if not path.is_file():
        raise FileNotFoundError(f"{runtime} configuration does not exist: {path}")
    raw = path.read_bytes()
    if not expected_sha256 or _sha256(raw) != expected_sha256:
        raise RuntimeError(f"{path.name} changed outside Lexeditor. Reload Tweaks before saving.")
    if not isinstance(changes, dict) or len(changes) > 512:
        raise ValueError("The platform configuration change set is invalid")
    text = raw.decode("utf-8-sig")
    fields = _toml_fields(text) if fmt == "toml" else _ini_fields(text)
    by_id = {field["id"]: field for field in fields}
    lines = text.splitlines(keepends=True)
    saved = 0
    for field_id, requested in changes.items():
        field = by_id.get(str(field_id))
        if field is None:
            raise ValueError(f"Unknown {runtime} setting: {field_id}")
        value = _validate(field, requested)
        if value == field["value"]:
            continue
        line = lines[field["line"]]
        matcher = _ASSIGNMENT if fmt == "toml" else _INI_ASSIGNMENT
        match = matcher.match(line)
        if not match:
            raise RuntimeError(f"Could not safely update {field['key']}")
        encoded = _toml_text(value) if fmt == "toml" else _ini_text(value)
        lines[field["line"]] = f"{match.group('indent')}{match.group('key')}{match.group('space')}{encoded}{match.group('ending') or ''}"
        saved += 1
    if saved:
        backup = path.with_name(path.name + ".lexeditor.bak")
        shutil.copy2(path, backup)
        updated_text = "".join(lines)
        updated = updated_text.encode("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8")
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        temporary.write_bytes(updated)
        os.replace(temporary, path)
    result = load_config(path, runtime, fmt)
    result["saved"] = saved
    result["backup"] = str(path.with_name(path.name + ".lexeditor.bak")) if saved else None
    return result
