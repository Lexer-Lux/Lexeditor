"""DS1 tweak mods: build the enabled ones and apply them to the executable.

A DS1 tweak mod (see core/script_mods.py) builds `native/<id>.json`, a patch
description that exe_patches.py combines with every other enabled tweak's
onto the vanilla executable. Applying writes that one combined executable;
Restore puts the preserved original back.

The game folder holds exactly two Lexeditor files besides the executable:
the one original copy, kept from the first Apply, and a manifest naming the
bytes Lexeditor last wrote. Any other executable is refused, never
overwritten.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

from core import script_mods
from core.plugin_files import atomic_write
from core.process_probe import live_processes

from . import exe_patches

ALLOWED_ROOTS = ("native",)
BACKUP_FILE = "DarkSoulsRemastered.exe.lexeditor-original"
MANIFEST_FILE = "DarkSoulsRemastered.exe.lexeditor-tweaks.json"
MODS_ENV = "LEXEDITOR_DS1_MODS_ROOT"


class TweakError(ValueError):
    """A tweak could not be built or applied; nothing was changed."""


def mods_root() -> Path:
    override = os.environ.get(MODS_ENV)
    if override:
        return Path(override)
    from core.mod_library import default_user_library_root
    return default_user_library_root() / "ds1"


def checked(path: Path) -> Path:
    """Refuse links and junctions on a protected path before following it."""
    path = Path(os.path.abspath(path))
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise TweakError("A protected tweak path contains a symlink or junction")
        if entry == path and stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise TweakError("A protected tweak file has more than one hard link")
    return path


def _read(path: Path) -> bytes:
    path = checked(path)
    if not path.is_file():
        raise TweakError(f"{path.name} is missing")
    if path.stat().st_size > 128 * 1024 * 1024:
        raise TweakError(f"{path.name} is too large to be the Remastered executable")
    return path.read_bytes()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_vanilla(data: bytes) -> bool:
    return len(data) == exe_patches.VANILLA_SIZE and _sha(data) == exe_patches.VANILLA_SHA256


def tweak_rows(root: Path | None = None) -> list[dict]:
    """Every tweak mod in the DS1 library, in load order."""
    root = checked(Path(root or mods_root()))
    rows = []
    if root.is_dir():
        for folder in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
            checked(folder)
            if not folder.is_dir():
                continue
            checked(folder / "mod.json")
            checked(folder / script_mods.VALUES_FILE)
            if not script_mods.is_script_mod(folder):
                continue
            metadata = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
            row = script_mods.catalog_row(folder)
            row.update({"id": str(metadata.get("id") or folder.name), "name": str(metadata.get("name") or folder.name),
                        "enabled": metadata.get("enabled") is True, "order": int(metadata.get("order", 1000))})
            rows.append(row)
    ids = [row["id"].casefold() for row in rows]
    if len(ids) != len(set(ids)):
        raise TweakError("Two DS1 tweak mods share an id")
    return sorted(rows, key=lambda row: (row["order"], row["name"].casefold()))


def save(changes: dict, root: Path | None = None) -> list[dict]:
    """Store switches and values for several tweak mods, all or none."""
    rows = {row["id"]: row for row in tweak_rows(root)}
    if not isinstance(changes, dict):
        raise TweakError("Send tweak ids mapped to their changes")
    for mod_id, change in changes.items():
        if mod_id not in rows:
            raise TweakError(f"There is no DS1 tweak mod {mod_id}")
        if not isinstance(change, dict) or set(change) - {"enabled", "values"}:
            raise TweakError(f"{mod_id}: send enabled and values only")
        if "enabled" in change and type(change["enabled"]) is not bool:
            raise TweakError(f"{rows[mod_id]['name']} must be on or off")
    touched = [Path(rows[mod_id]["path"]) / name for mod_id in changes
               for name in ("mod.json", script_mods.VALUES_FILE)]
    before = {path: path.read_bytes() if path.is_file() else None for path in touched}
    try:
        for mod_id, change in changes.items():
            folder = Path(rows[mod_id]["path"])
            if "values" in change:
                script_mods.save_values(folder, change["values"])
            if "enabled" in change:
                metadata = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
                metadata["enabled"] = change["enabled"]
                atomic_write(folder / "mod.json", (json.dumps(metadata, indent=2) + "\n").encode("utf-8"))
    except Exception:
        for path, content in before.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, content)
        raise
    return tweak_rows(root)


class BuildContext:
    """What a DS1 tweak script gets from Lexeditor."""

    def __init__(self, enabled: dict[str, Path]):
        self._enabled = enabled
        self.current = ""

    def enabled(self, mod_id: str) -> bool:
        return mod_id in self._enabled

    def settings(self, mod_id: str) -> dict | None:
        root = self._enabled.get(mod_id)
        return script_mods.values(root) if root else None


def build_specs(root: Path | None = None) -> list[dict]:
    """Build every enabled tweak mod and read back its patch description."""
    rows = [row for row in tweak_rows(root) if row["enabled"]]
    context = BuildContext({row["id"]: Path(row["path"]) for row in rows})
    script_mods.build_batch(rows, context, allowed_roots=ALLOWED_ROOTS, error=TweakError)
    specs = []
    for row in rows:
        target = Path(row["path"]) / "native" / f"{row['id']}.json"
        checked(target)
        if not target.is_file():
            continue  # A tweak with nothing to patch at its current settings.
        try:
            specs.append(exe_patches.validate(json.loads(target.read_text(encoding="utf-8")), row["name"]))
        except (ValueError, exe_patches.PatchError) as error:
            raise TweakError(f"{row['name']}: {error}") from error
    return specs


def ensure_game_closed() -> None:
    if os.name != "nt":
        raise TweakError("Executable tweaks can only be applied on Windows")
    if live_processes([exe_patches.EXECUTABLE]):
        raise TweakError("Close Dark Souls Remastered before changing its executable")


# No project argument means retain the last explicitly applied project rules.
# Passing None removes that contribution, without disabling library tweak mods.
_KEEP_PROJECT = object()
MANIFEST_LIMIT = 1024 * 1024


def _project(value):
    if value is None:
        return None
    if (type(value) is not dict or set(value) != {"path", "settingsHash", "spec"}
            or type(value["path"]) is not str or not value["path"]
            or type(value["settingsHash"]) is not str or len(value["settingsHash"]) != 64):
        raise TweakError("The saved native project description is damaged")
    exe_patches.validate(value["spec"], "Project native rules")
    return value


def _manifest(game_root: Path) -> dict:
    path = checked(Path(game_root) / MANIFEST_FILE)
    if not path.exists():
        return {}
    if not path.is_file() or path.stat().st_size > MANIFEST_LIMIT:
        raise TweakError("The executable tweak manifest is damaged or too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (type(data) is not dict or type(data.get("version")) is not int
            or data["version"] not in (1, 2) or type(data.get("mods")) is not list
            or any(type(name) is not str for name in data["mods"])
            or type(data.get("sha256")) is not str or len(data["sha256"]) != 64):
        raise TweakError("The executable tweak manifest is damaged")
    if data["version"] == 2:
        _project(data.get("project"))
        pending = data.get("pending")
        if pending is not None:
            if (type(pending) is not dict or set(pending) != {"sha256", "mods", "project"}
                    or type(pending["sha256"]) is not str or len(pending["sha256"]) != 64
                    or type(pending["mods"]) is not list
                    or any(type(name) is not str for name in pending["mods"])):
                raise TweakError("The pending executable operation is damaged")
            _project(pending["project"])
    return data


def _original(game_root: Path, current: bytes, manifest: dict) -> bytes:
    backup = checked(Path(game_root) / BACKUP_FILE)
    if backup.exists():
        original = _read(backup)
        if not is_vanilla(original):
            raise TweakError("The preserved original executable changed; refusing to continue")
        return original
    if is_vanilla(current):
        return current
    raise TweakError("The preserved original executable is missing; refusing to continue")


def _owned(current: bytes, manifest: dict) -> bool:
    if is_vanilla(current):
        return True
    digest = _sha(current)
    return bool(manifest) and digest in (
        manifest.get("sha256"), (manifest.get("pending") or {}).get("sha256"))


def _current_manifest(current: bytes, manifest: dict) -> dict:
    """Which recipe produced the bytes, including a write interrupted before completion."""
    pending = manifest.get("pending")
    if pending and _sha(current) == pending["sha256"]:
        return {"version": 2, **pending, "pending": None}
    return {"version": 2, "sha256": _sha(current),
            "mods": [] if is_vanilla(current) else manifest.get("mods", []),
            "project": None if is_vanilla(current) else manifest.get("project"),
            "pending": None}


def _write_manifest(path: Path, value: dict) -> None:
    raw = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MANIFEST_LIMIT:
        raise TweakError("The executable ownership record is too large")
    atomic_write(checked(path), raw)


def _write(game_root: Path, before: bytes, after: bytes, mods: list[str],
           project=None) -> None:
    """Journal one expected-image replacement; retain the original plus the latest intent."""
    game_root = checked(Path(game_root))
    live, backup = checked(game_root / exe_patches.EXECUTABLE), checked(game_root / BACKUP_FILE)
    manifest_path = checked(game_root / MANIFEST_FILE)
    old = _manifest(game_root)
    if not _owned(before, old) or _read(live) != before:
        raise TweakError("The executable changed while the tweaks were being prepared")
    original = _original(game_root, before, old)
    desired = {"sha256": _sha(after), "mods": list(mods), "project": _project(project)}
    journal = {**_current_manifest(before, old), "pending": desired}
    # Check serializability and the bound before creating a backup or replacing anything.
    if len(json.dumps(journal, allow_nan=False).encode("utf-8")) > MANIFEST_LIMIT - 1024:
        raise TweakError("The executable ownership record is too large")
    ensure_game_closed()
    if after == before and not old and not mods and project is None:
        return
    if not backup.exists():
        with checked(backup).open("xb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if not is_vanilla(_read(backup)):
            raise TweakError("The original executable backup did not verify")
    _write_manifest(manifest_path, journal)
    ensure_game_closed()
    if _read(live) != before:
        raise TweakError("The executable changed while the tweaks were being prepared")
    if after != before:
        atomic_write(checked(live), after)
    if _read(live) != after:
        raise TweakError("Executable verification failed; the original and pending intent were retained")
    if mods or project is not None:
        _write_manifest(manifest_path, {"version": 2, **desired, "pending": None})
    else:
        checked(manifest_path).unlink(missing_ok=True)


def prepare(game_root: Path, root: Path | None = None, *, project=_KEEP_PROJECT):
    """Build and validate everything before the caller changes installed files."""
    ensure_game_closed()
    game_root = checked(Path(game_root))
    current = _read(game_root / exe_patches.EXECUTABLE)
    manifest = _manifest(game_root)
    if not _owned(current, manifest):
        raise TweakError("The installed executable was changed outside Lexeditor; it was left alone")
    previous = _current_manifest(current, manifest)
    original = _original(game_root, current, manifest)
    # A project contribution can depend on verified original instruction bytes.
    chosen = previous.get("project") if project is _KEEP_PROJECT else (
        project(original) if callable(project) else project)
    chosen = _project(chosen)
    specs = build_specs(root)
    mods = [spec["owner"] for spec in specs]
    if chosen is not None:
        specs.append(exe_patches.validate(chosen["spec"], "Project native rules"))
    try:
        after = exe_patches.compose(original, specs)
    except exe_patches.PatchError as error:
        raise TweakError(str(error)) from error
    return {"before": current, "after": after, "mods": mods, "project": chosen,
            "previous": previous}


def commit(game_root: Path, plan: dict) -> None:
    _write(game_root, plan["before"], plan["after"], plan["mods"], plan["project"])


def rollback(game_root: Path, plan: dict) -> None:
    """Never undo a file changed by somebody else after the prepared operation."""
    previous = plan["previous"]
    _write(game_root, plan["after"], plan["before"],
           previous.get("mods", []), previous.get("project"))


def apply(game_root: Path, root: Path | None = None, *, project=_KEEP_PROJECT) -> dict:
    plan = prepare(game_root, root, project=project)
    commit(game_root, plan)
    return status(game_root, root)


def restore(game_root: Path, root: Path | None = None) -> dict:
    ensure_game_closed()
    game_root = checked(Path(game_root))
    current = _read(game_root / exe_patches.EXECUTABLE)
    manifest = _manifest(game_root)
    if not _owned(current, manifest):
        raise TweakError("The installed executable was changed outside Lexeditor; it was left alone")
    if not is_vanilla(current) or manifest:
        _write(game_root, current, _original(game_root, current, manifest), [], None)
    return status(game_root, root)


def status(game_root: Path, root: Path | None = None) -> dict:
    result = {"applied": [], "state": "unknown", "backupOk": False, "problem": "",
              "pendingRecovery": False, "project": None,
              "windows": os.name == "nt", "modsRoot": str(Path(root or mods_root()))}
    try:
        result["tweaks"] = tweak_rows(root)
        current = _read(Path(game_root) / exe_patches.EXECUTABLE)
        manifest = _manifest(game_root)
        backup = checked(Path(game_root) / BACKUP_FILE)
        result["backupOk"] = backup.is_file() and is_vanilla(_read(backup))
        if not _owned(current, manifest):
            result["problem"] = "The installed executable was changed outside Lexeditor"
        else:
            active = _current_manifest(current, manifest)
            result["state"] = "vanilla" if is_vanilla(current) else "tweaked"
            result["applied"] = list(active["mods"])
            result["project"] = active.get("project")
            result["pendingRecovery"] = bool(manifest.get("pending"))
            if not is_vanilla(current) and not result["backupOk"]:
                result["problem"] = "The preserved original executable is missing or changed"
    except (ValueError, OSError) as error:
        result.setdefault("tweaks", [])
        result["problem"] = str(error)
    return result
