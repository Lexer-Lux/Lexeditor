"""Tweak mods: a library mod that carries its own build script and settings.

A tweak used to be code inside Lexeditor. Now it is an ordinary library mod:

    <mod>/mod.json               {"script": {"version": 1}, ...}
    <mod>/script/__init__.py     the mod's own Python package
    <mod>/script/tweak.py        build(settings, context) -> {path: text|bytes}
    <mod>/settings.schema.json   the fields the Tweaks page shows
    <mod>/settings.json          the reader's values

When a game applies its enabled mods, it builds each enabled tweak mod first:
the script runs with the reader's values and returns the files it wants in
the mod (a Hext patch, an INI section, a data file). Those files then deploy
exactly like a hand-made mod's files, through the game's own loader.

Running a script runs code, so only trusted mods build. Trust is the reader's
explicit choice, kept in Lexeditor's own data folder rather than in the
library, and it is bound to a hash of the script: a changed script, such as an
update to a downloaded mod, stops building until it is trusted again.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import sys
import threading
from typing import Any, Callable

from core.plugin_files import atomic_write

SCRIPT_VERSION = 1
SCRIPT_FOLDER = "script"
ENTRY_MODULE = "tweak"
SCHEMA_FILE = "settings.schema.json"
VALUES_FILE = "settings.json"
MANIFEST_FILE = ".lexeditor-generated.json"
TRUST_ENV = "LEXEDITOR_SCRIPT_TRUST_FILE"
# The files a tweak mod owns besides its game files. A loader that validates
# mod contents accepts these for a tweak mod, and only for one.
OWN_FILES = frozenset({SCHEMA_FILE, VALUES_FILE, MANIFEST_FILE})
FIELD_TYPES = frozenset({"bool", "int", "number", "enum", "sound", "intList"})
_IMPORT_LOCK = threading.Lock()


class ScriptModError(ValueError):
    """A tweak mod's metadata, settings or build result is not acceptable."""


# --- discovery -------------------------------------------------------------

def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise ScriptModError(f"{path.name} is not readable JSON: {error}") from error


def is_script_mod(root: Path) -> bool:
    """True when the folder declares itself a tweak mod."""
    data = _read_json(Path(root) / "mod.json") if Path(root).is_dir() else None
    return isinstance(data, dict) and isinstance(data.get("script"), dict)


def owns(relative: str | Path) -> bool:
    """True for a file that belongs to the tweak-mod format, not to the game."""
    parts = PurePosixPath(str(relative).replace("\\", "/")).parts
    return bool(parts) and (parts[0] == SCRIPT_FOLDER or (len(parts) == 1 and parts[0] in OWN_FILES))


def spec(root: Path) -> dict:
    data = _read_json(Path(root) / "mod.json")
    script = data.get("script") if isinstance(data, dict) else None
    if not isinstance(script, dict) or script.get("version") != SCRIPT_VERSION:
        raise ScriptModError("This mod has no supported build script")
    entry = Path(root) / SCRIPT_FOLDER / f"{ENTRY_MODULE}.py"
    if not entry.is_file():
        raise ScriptModError(f"Missing {SCRIPT_FOLDER}/{ENTRY_MODULE}.py")
    return {"id": str(data.get("id") or Path(root).name), "name": str(data.get("name") or Path(root).name)}


# --- settings --------------------------------------------------------------

def schema(root: Path) -> dict:
    """Validated settings schema; a mod without one has no settings."""
    data = _read_json(Path(root) / SCHEMA_FILE) or {}
    if not isinstance(data, dict):
        raise ScriptModError(f"{SCHEMA_FILE} must be an object")
    fields = data.get("fields", [])
    if not isinstance(fields, list):
        raise ScriptModError(f"{SCHEMA_FILE} fields must be a list")
    keys = set()
    for field in fields:
        if not isinstance(field, dict) or not isinstance(field.get("key"), str) or not field["key"]:
            raise ScriptModError("Every setting needs a key")
        if field["key"] in keys:
            raise ScriptModError(f"Setting {field['key']} is listed twice")
        keys.add(field["key"])
        if field.get("type") not in FIELD_TYPES:
            raise ScriptModError(f"Setting {field['key']} has an unknown type")
        if field["type"] == "enum" and not field.get("choices"):
            raise ScriptModError(f"Setting {field['key']} needs choices")
        _coerce(field, field.get("default"))
    for key in ("requires", "conflicts"):
        if not isinstance(data.get(key, []), list) or not all(isinstance(item, str) for item in data.get(key, [])):
            raise ScriptModError(f"{SCHEMA_FILE} {key} must list mod ids")
    return {"title": str(data.get("title") or ""), "help": str(data.get("help") or ""),
            "blocker": str(data.get("blocker") or ""), "requires": list(data.get("requires", [])),
            "conflicts": list(data.get("conflicts", [])), "needsDriver": data.get("needsDriver") is True,
            "fields": fields}


def _coerce(field: dict, value: Any) -> Any:
    kind, key = field["type"], field["key"]
    if kind == "bool":
        if type(value) is not bool:
            raise ScriptModError(f"{key} must be on or off")
        return value
    if kind == "enum":
        allowed = [choice["value"] for choice in field["choices"]]
        if value not in allowed:
            raise ScriptModError(f"{key} must be one of the listed choices")
        return value
    if kind == "intList":
        length = field.get("length")
        if not isinstance(value, list) or (length is not None and len(value) != length):
            raise ScriptModError(f"{key} must list {length} whole numbers")
        return [_bounded(field, item, integer=True) for item in value]
    return _bounded(field, value, integer=kind in ("int", "sound"))


def _bounded(field: dict, value: Any, *, integer: bool) -> int | float:
    if type(value) is bool or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ScriptModError(f"{field['key']} must be a number")
    if integer:
        if value != int(value):
            raise ScriptModError(f"{field['key']} must be a whole number")
        value = int(value)
    low, high = field.get("min"), field.get("max")
    if (low is not None and value < low) or (high is not None and value > high):
        raise ScriptModError(f"{field['key']} must be between {low} and {high}")
    return value


def values(root: Path) -> dict:
    """The reader's values over the schema defaults, each one validated.

    A stored value the schema no longer accepts falls back to its default
    instead of failing the whole mod: settings outlive schema revisions.
    """
    fields = schema(root)["fields"]
    stored = _read_json(Path(root) / VALUES_FILE) or {}
    stored = stored.get("values", {}) if isinstance(stored, dict) else {}
    result = {}
    for field in fields:
        try:
            result[field["key"]] = _coerce(field, stored[field["key"]])
        except (KeyError, ScriptModError):
            result[field["key"]] = _coerce(field, field.get("default"))
    return result


def save_values(root: Path, changes: dict) -> dict:
    """Validate and store changed values; unknown keys are refused."""
    fields = {field["key"]: field for field in schema(root)["fields"]}
    if not isinstance(changes, dict):
        raise ScriptModError("Settings must be an object")
    unknown = sorted(set(changes) - set(fields))
    if unknown:
        raise ScriptModError("Unknown settings: " + ", ".join(unknown))
    current = values(root)
    current.update({key: _coerce(fields[key], value) for key, value in changes.items()})
    atomic_write(Path(root) / VALUES_FILE,
                 (json.dumps({"values": current}, indent=2) + "\n").encode("utf-8"))
    return current


# --- trust -----------------------------------------------------------------

def _trust_path() -> Path:
    override = os.environ.get(TRUST_ENV)
    if override:
        return Path(override)
    from core.runtime_bootstrap import user_data_dir
    return user_data_dir() / "trusted-script-mods.json"


def _key(root: Path) -> str:
    return os.path.normcase(str(Path(root).resolve()))


def script_hash(root: Path) -> str:
    """Hash every file the script package holds, names included."""
    digest = hashlib.sha256()
    package = Path(root) / SCRIPT_FOLDER
    for path in sorted((item for item in package.rglob("*")
                        if item.is_file() and "__pycache__" not in item.parts),
                       key=lambda item: item.relative_to(package).as_posix()):
        digest.update(path.relative_to(package).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _trusted() -> dict:
    data = _read_json(_trust_path()) or {}
    mods = data.get("mods") if isinstance(data, dict) else None
    return mods if isinstance(mods, dict) else {}


def trust_state(root: Path) -> str:
    """'trusted', 'changed' (trusted once, script edited since) or 'untrusted'."""
    entry = _trusted().get(_key(root))
    if not isinstance(entry, dict):
        return "untrusted"
    return "trusted" if entry.get("sha256") == script_hash(root) else "changed"


def set_trusted(root: Path, trusted: bool) -> str:
    mods = _trusted()
    if trusted:
        spec(root)
        mods[_key(root)] = {"sha256": script_hash(root)}
    else:
        mods.pop(_key(root), None)
    target = _trust_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(target, (json.dumps({"version": 1, "mods": mods}, indent=2) + "\n").encode("utf-8"))
    return trust_state(root)


# --- running ---------------------------------------------------------------

def _package_name(root: Path) -> str:
    return "lexeditor_tweak_" + hashlib.sha1(_key(root).encode("utf-8")).hexdigest()[:16]


def _load(root: Path):
    """Import the mod's script package under a name no other mod shares."""
    package_dir = Path(root) / SCRIPT_FOLDER
    name = _package_name(root)
    with _IMPORT_LOCK:
        for loaded in [key for key in sys.modules if key == name or key.startswith(name + ".")]:
            del sys.modules[loaded]
        init = package_dir / "__init__.py"
        package_spec = importlib.util.spec_from_file_location(
            name, init, submodule_search_locations=[str(package_dir)])
        if package_spec is None or package_spec.loader is None:
            raise ScriptModError("The mod's script package cannot be loaded")
        package = importlib.util.module_from_spec(package_spec)
        sys.modules[name] = package
        package_spec.loader.exec_module(package)
        entry_spec = importlib.util.spec_from_file_location(
            f"{name}.{ENTRY_MODULE}", package_dir / f"{ENTRY_MODULE}.py")
        module = importlib.util.module_from_spec(entry_spec)
        sys.modules[entry_spec.name] = module
        entry_spec.loader.exec_module(module)
    return module


def import_module(root: Path, name: str):
    """One module from a mod's script package, for that mod's own tests.

    Running a mod's tests is the developer's explicit act, so this does not
    ask for trust; Lexeditor itself only ever runs a script through build().
    """
    package = _package_name(Path(root))
    # One test may import several modules from the same mod; they must share
    # one copy of their siblings, so an already loaded package is reused.
    if package not in sys.modules:
        _load(Path(root))
    return importlib.import_module(f"{package}.{name}")


def load_trusted(root: Path):
    """The mod's entry module, or an error naming why it may not run."""
    spec(root)
    state = trust_state(root)
    if state != "trusted":
        raise ScriptModError("Its script changed since it was trusted; trust it again to build it"
                             if state == "changed" else "It is not trusted to run its script")
    return _load(root)


def describe(root: Path, context: Any) -> dict:
    """Optional extra data a trusted mod offers the editor, such as a table."""
    module = load_trusted(root)
    function: Callable | None = getattr(module, "describe", None)
    result = function(values(root), context) if function else {}
    if not isinstance(result, dict):
        raise ScriptModError("describe() must return an object")
    json.dumps(result)
    return result


def _safe_output(relative: str, allowed_roots: tuple[str, ...]) -> PurePosixPath:
    path = PurePosixPath(str(relative).replace("\\", "/"))
    if (path.is_absolute() or not path.parts or any(part in ("", ".", "..") or ":" in part for part in path.parts)
            or owns(path) or path.name == "mod.json"):
        raise ScriptModError(f"A tweak may not write {relative}")
    if not any(path.parts[0].casefold() == root.casefold() for root in allowed_roots):
        raise ScriptModError(f"{relative} is outside {', '.join(allowed_roots)}")
    return path


def build(root: Path, context: Any, *, allowed_roots: tuple[str, ...]) -> dict:
    """Run a trusted tweak mod's script and write what it returns into the mod.

    Only files this build or an earlier one generated are replaced or
    removed: a file the reader put in the mod by hand is never overwritten.
    """
    root = Path(root)
    module = load_trusted(root)
    function: Callable | None = getattr(module, "build", None)
    if function is None:
        raise ScriptModError("The script has no build() function")
    current = values(root)
    outputs = function(current, context)
    if not isinstance(outputs, dict):
        raise ScriptModError("build() must return {path: contents}")
    manifest_path = root / MANIFEST_FILE
    previous = (_read_json(manifest_path) or {}).get("files", {})
    planned: dict[str, bytes] = {}
    for relative, contents in outputs.items():
        path = _safe_output(relative, allowed_roots)
        if isinstance(contents, str):
            contents = contents.encode("utf-8")
        if not isinstance(contents, (bytes, bytearray)):
            raise ScriptModError(f"{relative} must be text or bytes")
        key = path.as_posix()
        if key.casefold() in {item.casefold() for item in planned}:
            raise ScriptModError(f"{relative} is returned twice")
        target = root / Path(*path.parts)
        if target.exists() and key not in previous:
            raise ScriptModError(f"{relative} already exists and was not generated by this mod")
        planned[key] = bytes(contents)
    written, removed = [], []
    for key, contents in planned.items():
        target = root / Path(*PurePosixPath(key).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_bytes() != contents:
            atomic_write(target, contents)
            written.append(key)
    for key in sorted(set(previous) - set(planned)):
        target = root / Path(*PurePosixPath(key).parts)
        if target.is_file():
            target.unlink()
            removed.append(key)
    manifest = {"version": 1, "files": {key: hashlib.sha256(data).hexdigest() for key, data in planned.items()}}
    atomic_write(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return {"files": sorted(planned), "written": written, "removed": removed}


def clear(root: Path) -> list[str]:
    """Remove everything an earlier build generated, as when the mod is off."""
    root = Path(root)
    manifest_path = root / MANIFEST_FILE
    previous = (_read_json(manifest_path) or {}).get("files", {})
    removed = []
    for key in sorted(previous):
        target = root / Path(*PurePosixPath(key).parts)
        if target.is_file():
            target.unlink()
            removed.append(key)
    if manifest_path.exists():
        manifest_path.unlink()
    return removed


def catalog_row(root: Path) -> dict:
    """What the Tweaks page needs about one tweak mod, without running it."""
    row = {"path": str(Path(root).resolve()), "trust": "untrusted", "error": ""}
    try:
        row.update(spec(root))
        row["schema"] = schema(root)
        row["values"] = values(root)
        row["trust"] = trust_state(root)
    except ScriptModError as error:
        row["error"] = str(error)
    return row
