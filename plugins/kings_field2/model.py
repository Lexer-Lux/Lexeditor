"""Verdite2's existing installation and player configuration; no disc writes."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading

from core.process_probe import live_processes

LOCK = threading.RLock()
MAX_CONFIG = 2 * 1024 * 1024

# Bounds are the installed Verdite2 MousePage and AnalogPage's actual controls.
FIELDS = (
    {"key": "kf2.mouse.turn", "label": "Mouse turn sensitivity", "kind": "number", "min": .1, "max": 5, "step": .1, "default": 1},
    {"key": "kf2.mouse.look", "label": "Mouse look sensitivity", "kind": "number", "min": .1, "max": 5, "step": .1, "default": 1},
    {"key": "kf2.mouse.inverty", "label": "Invert mouse look", "kind": "boolean", "default": False},
    {"key": "kf2.analog.turn", "label": "Stick turn sensitivity", "kind": "number", "min": .1, "max": 3, "step": .1, "default": 1},
    {"key": "kf2.analog.pitch", "label": "Stick look sensitivity", "kind": "number", "min": .1, "max": 3, "step": .1, "default": 1},
)


def data_root() -> Path:
    return Path(os.environ.get("LEXEDITOR_KF2_DATA") or os.environ.get("VERDITE2_DATA") or
                str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Verdite2")).expanduser().resolve()


def game_root() -> Path:
    return Path(os.environ.get("LEXEDITOR_KF2_ROOT") or "D:/Programs/Verdite2").expanduser().resolve()


def ensure_closed() -> None:
    if live_processes(("Verdite2.exe",)):
        raise ValueError("Close Verdite2 before saving settings or changing deployed mods. Your running game has not been changed.")


def read_bytes(path: Path) -> bytes:
    if not path.exists():
        return b""
    if path.is_symlink() or path.stat().st_size > MAX_CONFIG:
        raise ValueError(f"{path.name} is linked or exceeds the 2 MiB limit")
    return path.read_bytes()


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict:
    raw = read_bytes(path)
    value = json.loads(raw.decode("utf-8-sig")) if raw else {}
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def ini_values(text: str) -> dict[str, str]:
    section = ""
    result = {}
    seen = False
    for line in text.splitlines():
        if line.strip().startswith("["):
            section = line.strip()
            if section == "[RecompOne]":
                if seen:
                    raise ValueError("interface.ini contains duplicate RecompOne sections")
                seen = True
        elif section == "[RecompOne]" and "=" in line and not line.lstrip().startswith((";", "#")):
            key, value = line.split("=", 1)
            key = key.strip()
            if key in result:
                raise ValueError(f"interface.ini repeats {key}; resolve it in the game before editing")
            result[key] = value.strip()
    return result


def updated_ini(raw: bytes, changes: dict[str, str]) -> bytes:
    """Change only requested RecompOne keys; retain unrelated sections and bytes."""
    text = raw.decode("utf-8-sig")
    ini_values(text)
    if not changes:
        return raw
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    begin = next((i for i, line in enumerate(lines) if line.strip() == "[RecompOne]"), None)
    if begin is None:
        prefix = "[RecompOne]" + newline + "".join(f"{k}={v}{newline}" for k, v in changes.items())
        return (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + (prefix + text).encode("utf-8")
    end = next((i for i in range(begin + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    pending = dict(changes)
    for i in range(begin + 1, end):
        match = re.match(r"^(\s*([^=;#\s]+)\s*=)(.*?)(\r?\n)?$", lines[i])
        if match and match[2] in pending:
            lines[i] = match[1] + pending.pop(match[2]) + (match[4] or "")
    if pending:
        if end and not lines[end - 1].endswith(("\n", "\r")):
            lines[end - 1] += newline
        lines[end:end] = [f"{k}={v}{newline}" for k, v in pending.items()]
    prefix = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    return prefix + "".join(lines).encode("utf-8")


def preferences(root: Path) -> dict:
    raw = read_bytes(root / "interface.ini")
    values = ini_values(raw.decode("utf-8-sig"))
    fields = []
    for spec in FIELDS:
        value = values.get(spec["key"])
        if value is None:
            parsed = spec["default"]
        elif spec["kind"] == "boolean":
            if value.lower() not in ("true", "false"):
                raise ValueError(f"Unsupported value for {spec['label']}: {value}")
            parsed = value.lower() == "true"
        else:
            parsed = float(value)
            if not math.isfinite(parsed) or not spec["min"] <= parsed <= spec["max"]:
                raise ValueError(f"{spec['label']} is outside the game's supported range")
        fields.append({**spec, "value": parsed})
    return {"fields": fields, "fingerprint": fingerprint(raw)}


def save_preferences(root: Path, changes: dict, expected: str) -> dict:
    with LOCK:
        ensure_closed()
        path = root / "interface.ini"
        raw = read_bytes(path)
        if fingerprint(raw) != expected:
            raise ValueError("Verdite2 settings changed since this page opened. Refresh before saving.")
        specs = {row["key"]: row for row in FIELDS}
        if not isinstance(changes, dict) or set(changes) - specs.keys():
            raise ValueError("Unrecognized Verdite2 setting")
        validated = {}
        for key, value in changes.items():
            spec = specs[key]
            if spec["kind"] == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(f"{spec['label']} must be on or off")
                validated[key] = str(value)
            else:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not spec["min"] <= value <= spec["max"]:
                    raise ValueError(f"{spec['label']} must be between {spec['min']} and {spec['max']}")
                validated[key] = format(value, ".8g")
        output = updated_ini(raw, validated)
        if output != raw:
            # Exactly one previous settings file, overwritten rather than accumulated.
            atomic_write(path.with_suffix(".ini.lexeditor-previous"), raw)
            atomic_write(path, output)
        return preferences(root)


def installation(root: Path) -> dict:
    required = ("bin/Verdite2.exe", "bin/RecompOne.Runtime.dll", "content/config/kf2.json")
    missing = [relative for relative in required if not (root / relative).is_file()]
    supported = not missing
    if supported:
        config = (root / "content/config/kf2.json").read_text(encoding="utf-8-sig")
        supported = '"SLUS-00158"' in config and '"KingsField2"' in config
    return {"root": str(root), "supported": supported, "missing": missing,
            "dataRoot": str(data_root()), "running": bool(live_processes(("Verdite2.exe",)))}
