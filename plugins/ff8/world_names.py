"""Project labels for world terrain codes that have no in-game name field."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from . import paths, runtime_layout

FILENAME = ".lexeditor-world-names.json"


def _validate(names: dict) -> dict[str, str]:
    if not isinstance(names, dict):
        raise ValueError("Ground names must be an object")
    clean = {}
    for key, name in names.items():
        if not isinstance(key, str) or not key.isdecimal() or not 0 <= int(key) <= 255 or str(int(key)) != key:
            raise ValueError("Ground ID must be a whole number from 0 to 255")
        if not isinstance(name, str) or len(name) > 120 or any(ord(char) < 32 for char in name):
            raise ValueError("Ground names must be one line of at most 120 characters")
        if name.strip():
            clean[key] = name.strip()
    return clean


def load(dataset: str = "current") -> dict[str, str]:
    if dataset == "vanilla":
        return {}
    if dataset == "current":
        root = paths.PROJECT_ROOT
    elif dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
    elif dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        root = paths.PROJECT_ROOT / "references" / reference_id
        if not reference_id or root.resolve().parent != (paths.PROJECT_ROOT / "references").resolve():
            raise ValueError("Invalid reference ID")
    else:
        raise ValueError(f"Unknown dataset: {dataset}")
    target = root / FILENAME
    if not target.exists():
        return {}
    if target.stat().st_size > 150_000:
        raise ValueError("Ground name file is too large")
    return _validate(json.loads(target.read_text(encoding="utf-8")))


def prepare(edits: list[dict]) -> dict[str, str]:
    names = load()
    for edit in edits:
        index = edit.get("id")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index <= 255:
            raise ValueError("Ground ID must be a whole number from 0 to 255")
        key = str(index)
        checked = _validate({key: edit.get("name")})
        if key in checked:
            names[key] = checked[key]
        else:
            names.pop(key, None)
    return names


def encoded(names: dict[str, str]) -> bytes:
    return (json.dumps(_validate(names), ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode('utf-8')


def write(names: dict[str, str]) -> Path:
    names = _validate(names)
    destination = paths.PROJECT_ROOT / FILENAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".world-names-", suffix=".json", dir=destination.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            json.dump(names, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination
