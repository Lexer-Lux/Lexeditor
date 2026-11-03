"""Preserving player preferences for native source ports, configured by each plugin."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading

from core.plugin_manifest import manifest
from core.process_probe import live_processes

MAX_CONFIG = 2 * 1024 * 1024

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
            key = key.strip().casefold()
            if key in result:
                raise ValueError(f"interface.ini repeats {key}; resolve it in the game before editing")
            result[key] = value.strip()
    return result


def updated_ini(raw: bytes, changes: dict[str, str | None]) -> bytes:
    """Change only requested RecompOne keys; retain unrelated sections and bytes."""
    text = raw.decode("utf-8-sig")
    ini_values(text)
    if not changes:
        return raw
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    begin = next((i for i, line in enumerate(lines) if line.strip() == "[RecompOne]"), None)
    if begin is None:
        additions = "".join(f"{k}={v}{newline}" for k, v in changes.items() if v is not None)
        if not additions:
            return raw
        prefix = "[RecompOne]" + newline + additions
        return (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + (prefix + text).encode("utf-8")
    end = next((i for i in range(begin + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    pending = dict(changes)
    for i in range(begin + 1, end):
        match = re.match(r"^(\s*([^=;#\s]+)\s*=)(.*?)(\r?\n)?$", lines[i])
        if match and match[2].casefold() in pending:
            value = pending.pop(match[2].casefold())
            lines[i] = "" if value is None else match[1] + value + (match[4] or "")
    additions = [f"{k}={v}{newline}" for k, v in pending.items() if v is not None]
    if additions:
        if end and not lines[end - 1].endswith(("\n", "\r")):
            lines[end - 1] += newline
        lines[end:end] = additions
    prefix = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    return prefix + "".join(lines).encode("utf-8")


class NativePortSettings:
    def __init__(self, plugin_file: str, fields: tuple[dict, ...]):
        self.descriptor = manifest(plugin_file)
        self.native = self.descriptor["nativePort"]
        self.fields = fields
        self.lock = threading.RLock()

    def data_root(self) -> Path:
        return Path(os.environ.get(self.native["dataEnv"]) or
                    str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / self.native["dataDirectory"])).expanduser().resolve()

    def game_root(self) -> Path:
        install = self.descriptor["installation"]
        return Path(os.environ.get(install["rootEnv"]) or install["defaultRoots"][0]).expanduser().resolve()

    def ensure_closed(self) -> None:
        if live_processes(tuple(self.descriptor["processNames"])):
            raise ValueError("Close the game before saving settings or changing deployed mods. The running game has not been changed.")

    def installation(self, root: Path) -> dict:
        required = self.descriptor["installation"]["requiredPaths"]
        missing = [relative for relative in required if not (root / relative).is_file()]
        supported = not missing
        if supported:
            config = read_bytes(root / self.native["configPath"]).decode("utf-8-sig")
            supported = all(json.dumps(value) in config for value in self.native["configIdentity"])
        return {"root": str(root), "supported": supported, "missing": missing,
                "dataRoot": str(self.data_root()), "running": bool(live_processes(tuple(self.descriptor["processNames"])))}

    def preferences(self, root: Path) -> dict:
        raw = read_bytes(root / "interface.ini")
        values = ini_values(raw.decode("utf-8-sig"))
        fields = []
        for spec in self.fields:
            text = values.get(spec["key"])
            if text is None:
                value = spec["default"]
            elif spec["kind"] == "boolean":
                encoding = spec.get("encoding", self.native.get("booleanEncoding", "text"))
                if encoding == "positive":
                    number = float(text)
                    if not math.isfinite(number) or not 0 <= number <= spec["nativeMax"]:
                        raise ValueError(f"Unsupported value for {spec['label']}")
                    value = number > 0
                elif encoding == "integer" and text in ("0", "1"):
                    value = text == "1"
                elif encoding == "text" and text.lower() in ("true", "false"):
                    value = text.lower() == "true"
                else:
                    raise ValueError(f"Unsupported value for {spec['label']}: {text}")
            else:
                value = float(text)
                if not math.isfinite(value) or not spec["min"] <= value <= spec["max"]:
                    raise ValueError(f"{spec['label']} is outside the game's supported range")
            fields.append({**spec, "value": value})
        return {"fields": fields, "fingerprint": fingerprint(raw)}

    def save_preferences(self, root: Path, changes: dict, expected: str) -> dict:
        with self.lock:
            self.ensure_closed()
            path = root / "interface.ini"
            raw = read_bytes(path)
            if fingerprint(raw) != expected:
                raise ValueError("Game settings changed since this page opened. Refresh before saving.")
            specs = {row["key"]: row for row in self.fields}
            if not isinstance(changes, dict) or set(changes) - specs.keys():
                raise ValueError("Unrecognized native setting")
            values = ini_values(raw.decode("utf-8-sig"))
            validated = {}
            for key, value in changes.items():
                spec = specs[key]
                if spec["kind"] == "boolean":
                    if not isinstance(value, bool):
                        raise ValueError(f"{spec['label']} must be on or off")
                    if spec.get("encoding") == "positive":
                        existing = float(values.get(key, spec["nativeDefault"]))
                        if not math.isfinite(existing) or not 0 <= existing <= spec["nativeMax"]:
                            raise ValueError(f"Unsupported value for {spec['label']}")
                        validated[key] = format((existing if existing > 0 else spec["nativeDefault"]) if value else 0, ".8g")
                    else:
                        encoding = spec.get("encoding", self.native.get("booleanEncoding", "text"))
                        validated[key] = ("1" if value else "0") if encoding == "integer" else str(value)
                else:
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not spec["min"] <= value <= spec["max"]:
                        raise ValueError(f"{spec['label']} must be between {spec['min']} and {spec['max']}")
                    if value != 0 and value < spec.get("nonzeroMin", spec["min"]):
                        raise ValueError(f"{spec['label']} must be zero or at least {spec['nonzeroMin']}")
                    validated[key] = format(value, ".8g")
            output = updated_ini(raw, validated)
            if output != raw:
                atomic_write(path.with_suffix(".ini.lexeditor-previous"), raw)
                atomic_write(path, output)
            return self.preferences(root)

    read_bytes = staticmethod(read_bytes)
    read_json = staticmethod(read_json)
    fingerprint = staticmethod(fingerprint)
    atomic_write = staticmethod(atomic_write)
    MAX_CONFIG = MAX_CONFIG
