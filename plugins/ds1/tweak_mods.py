"""DS1 tweak mods: build the enabled ones and apply them to the executable.

A DS1 tweak mod (see core/script_mods.py) builds `native/<id>.json`, a patch
description that exe_patches.py combines with every other enabled tweak's
onto the vanilla executable. Applying writes that one combined executable;
Restore puts the preserved original back.

The game folder keeps one original copy, an ownership journal and a one-byte
OS lock file. The journal records replacement intent before the executable is
written, so an interrupted Apply or Restore can be retried without trusting
unknown bytes. Outside modifications are refused, never overwritten.
"""
from __future__ import annotations

from contextlib import contextmanager
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
LOCK_FILE = "DarkSoulsRemastered.exe.lexeditor-tweaks.lock"
MAX_MANIFEST = 1024 * 1024


@contextmanager
def _exclusive(game_root: Path):
    """Serialize cooperating editor processes; closing releases the OS lock."""
    path = checked(Path(game_root) / LOCK_FILE)
    if path.exists() and (not path.is_file() or path.stat().st_size > 1):
        raise TweakError("The executable tweak lock file is invalid")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"0")
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        # Do not unlink: a waiting process must lock the same inode.
        os.close(descriptor)


class TweakError(ValueError):
    """A tweak operation failed; the message identifies any recovery needed."""


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


def locked(game_root: Path):
    """Hold the executable lock across a whole prepare, commit and rollback."""
    return _exclusive(checked(Path(game_root)))


def _digest(value) -> bool:
    return (type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _mod_names(value) -> bool:
    return type(value) is list and all(type(name) is str and name for name in value)


def _project(value):
    if value is None:
        return None
    if (type(value) is not dict or set(value) != {"path", "settingsHash", "spec"}
            or type(value["path"]) is not str or not value["path"]
            or not _digest(value["settingsHash"])):
        raise TweakError("The saved native project description is damaged")
    try:
        exe_patches.validate(value["spec"], "Project native rules")
    except (ValueError, exe_patches.PatchError) as error:
        raise TweakError("The saved native project description is damaged") from error
    return value


def _manifest(game_root: Path) -> dict:
    """The ownership record: version 1 (library tweaks) or 2 (plus project rules).

    Read with a hard bound, and refuse anything damaged, including a damaged
    pending entry: a journal is only trusted when every hash in it is real.
    """
    path = checked(Path(game_root) / MANIFEST_FILE)
    if not path.exists():
        return {}
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST:
        raise TweakError("The executable tweak manifest is missing or too large")
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST:
        raise TweakError("The executable tweak manifest grew beyond its limit")
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise TweakError("The executable tweak manifest is damaged") from error
    if (type(data) is not dict or type(data.get("version")) is not int or data["version"] not in (1, 2)
            or not _digest(data.get("sha256")) or not _mod_names(data.get("mods"))):
        raise TweakError("The executable tweak manifest is damaged")
    keys = {"sha256", "mods"} | ({"project"} if data["version"] == 2 else set())
    pending = data.get("pending")
    if pending is not None and (type(pending) is not dict or set(pending) != keys
                                or not _digest(pending["sha256"]) or not _mod_names(pending["mods"])):
        raise TweakError("The executable tweak manifest is damaged")
    if data["version"] == 2:
        _project(data.get("project"))
        if pending is not None:
            _project(pending["project"])
    return data


def _original(game_root: Path, current: bytes, manifest: dict) -> bytes:
    """The verified vanilla bytes: the preserved copy, or the live file itself."""
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
        return {"version": 2, "sha256": pending["sha256"], "mods": list(pending["mods"]),
                "project": pending.get("project"), "pending": None}
    return {"version": 2, "sha256": _sha(current),
            "mods": [] if is_vanilla(current) else list(manifest.get("mods", [])),
            "project": None if is_vanilla(current) else manifest.get("project"),
            "pending": None}


def _save_manifest(game_root: Path, value: dict) -> None:
    raw = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_MANIFEST:
        raise TweakError("The executable tweak manifest exceeds its size limit")
    atomic_write(checked(Path(game_root) / MANIFEST_FILE), raw)


def _finish_manifest(game_root: Path, current: bytes, mods: list[str], project=None) -> None:
    if is_vanilla(current) and not mods and project is None:
        checked(Path(game_root) / MANIFEST_FILE).unlink(missing_ok=True)
    else:
        _save_manifest(game_root, {"version": 2, "sha256": _sha(current), "mods": list(mods),
                                   "project": project, "pending": None})


def _write(game_root: Path, before: bytes, after: bytes, mods: list[str], project=None) -> None:
    """Journal one expected-image replacement; keep the original plus the latest intent."""
    game_root = checked(Path(game_root))
    live = checked(game_root / exe_patches.EXECUTABLE)
    backup = checked(game_root / BACKUP_FILE)
    old = _manifest(game_root)
    if not _owned(before, old) or _read(live) != before:
        raise TweakError("The executable changed while the tweaks were being prepared")
    original = _original(game_root, before, old)
    project = _project(project)
    desired = {"sha256": _sha(after), "mods": list(mods), "project": project}
    journal = {**_current_manifest(before, old), "pending": desired}
    # Check the bound before creating a backup or replacing anything.
    if len(json.dumps(journal, allow_nan=False).encode("utf-8")) > MAX_MANIFEST - 1024:
        raise TweakError("The executable tweak manifest exceeds its size limit")
    if after == before and not old and not mods and project is None:
        return
    if not backup.exists():
        # Exclusive creation cannot overwrite an unmanaged file or a link.
        with backup.open("xb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if not is_vanilla(_read(backup)):
            raise TweakError("The original executable backup did not verify")
    # Journal first. A crash before or after replacement leaves one of these
    # two complete, known images; neither an arbitrary hash nor a partial file
    # is accepted. Restore uses the same protocol.
    _save_manifest(game_root, journal)
    ensure_game_closed()
    if _read(live) != before:
        raise TweakError("The executable changed before replacement")
    if after != before:
        atomic_write(live, after)
    if _read(live) != after:
        raise TweakError("Executable verification failed; the original and pending intent were kept")
    _finish_manifest(game_root, after, mods, project)


def prepare(game_root: Path, root: Path | None = None, *, project=_KEEP_PROJECT) -> dict:
    """Build and validate everything before the caller changes installed files.

    Hold locked(game_root) from here through commit or rollback.
    """
    ensure_game_closed()
    game_root = checked(Path(game_root))
    current = _read(game_root / exe_patches.EXECUTABLE)
    manifest = _manifest(game_root)
    if not _owned(current, manifest):
        raise TweakError("The installed executable was changed outside Lexeditor; restore it before applying tweaks")
    previous = _current_manifest(current, manifest)
    original = _original(game_root, current, manifest)
    # A project contribution can depend on verified original instruction bytes.
    chosen = previous.get("project") if project is _KEEP_PROJECT else (
        project(original) if callable(project) else project)
    chosen = _project(chosen)
    specs = build_specs(root)
    if chosen is not None:
        specs.append(exe_patches.validate(chosen["spec"], "Project native rules"))
    try:
        after = exe_patches.compose(original, specs)
    except exe_patches.PatchError as error:
        raise TweakError(str(error)) from error
    # Only mods that change something are recorded as applied.
    mods = [spec["owner"] for spec in specs[:len(specs) - (chosen is not None)]
            if spec["islands"] or spec["hooks"] or spec["sectionVirtualSize"]]
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
    """Combine every enabled tweak and the project's rules onto the original executable."""
    # A running game stops everything before any write, the lock file included.
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        commit(game_root, prepare(game_root, root, project=project))
    return status(game_root, root)


def restore(game_root: Path, root: Path | None = None) -> dict:
    """Put the original executable back; the mods' switches are unchanged."""
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        current = _read(game_root / exe_patches.EXECUTABLE)
        manifest = _manifest(game_root)
        if not _owned(current, manifest):
            raise TweakError("The installed executable was changed outside Lexeditor; it was left alone")
        if not is_vanilla(current) or manifest:
            _write(game_root, current, _original(game_root, current, manifest), [], None)
    return status(game_root, root)


def status(game_root: Path, root: Path | None = None) -> dict:
    """What is installed now, without building or changing anything."""
    result = {"applied": [], "state": "unknown", "backupOk": False, "problem": "",
              "pendingRecovery": False, "project": None,
              "windows": os.name == "nt", "modsRoot": str(Path(root or mods_root()))}
    try:
        result["tweaks"] = tweak_rows(root)
        current = _read(Path(game_root) / exe_patches.EXECUTABLE)
        manifest = _manifest(Path(game_root))
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
