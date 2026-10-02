"""The metadata every mod carries, for every game: one `mod.json` in its root.

Lexeditor reads whatever popular mods already ship, so a mod may arrive
without this file. It never stays that way: creating a mod, or adding one to
the library, asks for anything missing before the mod is stored. Only the name
is required; the rest may be blank.

    {"name": "...", "author": "...", "description": "...", "credits": "..."}

Games keep their own keys in the same file (load order, enabled state, a
tweak's script, a bundle's components); writing the standard fields keeps
them untouched. Credits travel with the mod they credit.
"""
from __future__ import annotations

import json
from pathlib import Path

FILE = "mod.json"
FIELDS = ("name", "author", "description", "credits")
LIMITS = {"name": 120, "author": 200, "description": 4000, "credits": 20000}


class MetadataError(ValueError):
    """A mod's metadata is missing its name or is not valid."""


def _stored(root: Path) -> dict:
    path = Path(root) / FILE
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise MetadataError(f"{FILE} is not readable JSON: {error}") from error
    if not isinstance(value, dict):
        raise MetadataError(f"{FILE} must contain an object")
    return value


def clean(values: dict) -> dict:
    """The four standard fields, validated: text, trimmed, bounded, named."""
    if not isinstance(values, dict):
        raise MetadataError("Mod details must be an object")
    result = {}
    for key in FIELDS:
        value = values.get(key, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise MetadataError(f"The mod's {key} must be text")
        value = value.strip()
        if len(value) > LIMITS[key]:
            raise MetadataError(f"The mod's {key} is longer than {LIMITS[key]} characters")
        result[key] = value
    if not result["name"]:
        raise MetadataError("A mod needs a name")
    return result


def read(root: Path) -> dict:
    """The standard fields as stored, and which required ones are missing.

    A mod without a usable name reports it in `missing` and borrows its
    folder name for display only; nothing is written until someone names it.
    """
    stored = _stored(root)
    result = {}
    for key in FIELDS:
        value = stored.get(key, "")
        result[key] = value.strip() if isinstance(value, str) else ""
    missing = [] if result["name"] else ["name"]
    version = stored.get("version", "")
    return {**result, "version": version if isinstance(version, str) else "",
            "missing": missing, "displayName": result["name"] or Path(root).name}


def write(root: Path, values: dict) -> dict:
    """Store the standard fields, keeping every other key the mod has."""
    fields = clean(values)
    stored = _stored(root)
    stored.update(fields)
    path = Path(root) / FILE
    from core.plugin_files import atomic_write
    atomic_write(path, (json.dumps(stored, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return read(root)
