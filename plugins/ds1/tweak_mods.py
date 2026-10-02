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
MAX_MANIFEST = 64 * 1024


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
    root = Path(root or mods_root())
    rows = []
    if root.is_dir():
        for folder in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.casefold()):
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


def _valid_entry(entry) -> bool:
    return (isinstance(entry, dict)
            and isinstance(entry.get("sha256"), str)
            and len(entry["sha256"]) == 64
            and all(char in "0123456789abcdef" for char in entry["sha256"])
            and isinstance(entry.get("mods"), list)
            and all(isinstance(name, str) and name for name in entry["mods"]))


def _manifest(game_root: Path) -> dict:
    path = checked(Path(game_root) / MANIFEST_FILE)
    if not path.exists():
        return {}
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST:
        raise TweakError("The executable tweak manifest is missing or too large")
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST:
        raise TweakError("The executable tweak manifest grew beyond its limit")
    data = json.loads(raw)
    if (not _valid_entry(data) or type(data.get("version")) is not int or data["version"] != 1
            or (data.get("pending") is not None and not _valid_entry(data["pending"]))):
        raise TweakError("The executable tweak manifest is damaged")
    return data


def _matching_entry(current: bytes, manifest: dict) -> dict | None:
    if is_vanilla(current):
        return {"sha256": _sha(current), "mods": []}
    digest = _sha(current)
    for entry in (manifest.get("pending"), manifest):
        if entry and entry.get("sha256") == digest:
            return entry
    return None


def _save_manifest(game_root: Path, value: dict) -> None:
    raw = (json.dumps(value, indent=2) + "\n").encode("utf-8")
    if len(raw) > MAX_MANIFEST:
        raise TweakError("The executable tweak manifest exceeds its size limit")
    atomic_write(checked(Path(game_root) / MANIFEST_FILE), raw)


def _finish_manifest(game_root: Path, current: bytes, mods: list[str]) -> None:
    if is_vanilla(current):
        checked(Path(game_root) / MANIFEST_FILE).unlink(missing_ok=True)
    else:
        _save_manifest(game_root, {"version": 1, "sha256": _sha(current), "mods": mods})


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
    return _matching_entry(current, manifest) is not None


def _write(game_root: Path, before: bytes, after: bytes, mods: list[str]) -> None:
    game_root = checked(Path(game_root))
    live = checked(game_root / exe_patches.EXECUTABLE)
    backup = checked(game_root / BACKUP_FILE)
    if not backup.exists():
        # Read the original before creating the copy: the new, still empty
        # file must not be mistaken for a damaged one.
        original = _original(game_root, before, {})
        # Exclusive creation cannot overwrite an unmanaged file or a link.
        with backup.open("xb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if not is_vanilla(_read(backup)):
            raise TweakError("The original executable backup did not verify")
    ensure_game_closed()
    # Check again immediately before replacing; atomic replacement also fails
    # on a running Windows image's file lock.
    if _read(live) != before:
        raise TweakError("The executable changed while the tweaks were being prepared")
    _original(game_root, before, _manifest(game_root))
    entry = _matching_entry(before, _manifest(game_root))
    if entry is None:
        raise TweakError("Executable ownership changed before replacement")
    # Journal first. A crash before or after replacement leaves one of these
    # two complete, known images; neither an arbitrary hash nor a partial file
    # is accepted. Restore uses the same protocol.
    _save_manifest(game_root, {"version": 1, "sha256": _sha(before),
                               "mods": list(entry["mods"]),
                               "pending": {"sha256": _sha(after), "mods": mods}})
    ensure_game_closed()
    if _read(live) != before:
        raise TweakError("The executable changed before replacement")
    atomic_write(live, after)
    if _read(live) != after:
        raise TweakError("Executable verification failed; the original backup was kept")
    _finish_manifest(game_root, after, mods)


def apply(game_root: Path, root: Path | None = None) -> dict:
    """Combine every enabled tweak onto the original executable and install it."""
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        return _apply_locked(game_root, root)


def _apply_locked(game_root: Path, root: Path | None) -> dict:
    current = _read(game_root / exe_patches.EXECUTABLE)
    manifest = _manifest(game_root)
    if not _owned(current, manifest):
        raise TweakError("The installed executable was changed outside Lexeditor; restore it before applying tweaks")
    specs = build_specs(root)
    original = _original(game_root, current, manifest)
    try:
        after = exe_patches.compose(original, specs)
    except exe_patches.PatchError as error:
        raise TweakError(str(error)) from error
    mods = [spec["owner"] for spec in specs
            if spec["islands"] or spec["hooks"] or spec["sectionVirtualSize"]]
    if after != current:
        _write(game_root, current, after, mods)
    elif manifest.get("pending"):
        # The preceding process finished the bytes but not the journal.
        if _read(game_root / exe_patches.EXECUTABLE) != current:
            raise TweakError("The executable changed during recovery")
        _finish_manifest(game_root, current, mods)
    return status(game_root, root)


def restore(game_root: Path, root: Path | None = None) -> dict:
    """Put the original executable back; the mods' switches are unchanged."""
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        return _restore_locked(game_root, root)


def _restore_locked(game_root: Path, root: Path | None) -> dict:
    current = _read(game_root / exe_patches.EXECUTABLE)
    manifest = _manifest(game_root)
    if not _owned(current, manifest):
        raise TweakError("The installed executable was changed outside Lexeditor; it was left alone")
    if not is_vanilla(current):
        _write(game_root, current, _original(game_root, current, manifest), [])
    elif manifest:
        if _read(game_root / exe_patches.EXECUTABLE) != current:
            raise TweakError("The executable changed during recovery")
        _finish_manifest(game_root, current, [])
    return status(game_root, root)


def status(game_root: Path, root: Path | None = None) -> dict:
    """What is installed now, without building or changing anything."""
    result = {"applied": [], "state": "unknown", "backupOk": False, "problem": "",
              "pendingRecovery": False,
              "windows": os.name == "nt", "modsRoot": str(Path(root or mods_root()))}
    try:
        result["tweaks"] = tweak_rows(root)
        current = _read(Path(game_root) / exe_patches.EXECUTABLE)
        manifest = _manifest(Path(game_root))
        backup = checked(Path(game_root) / BACKUP_FILE)
        result["backupOk"] = backup.is_file() and is_vanilla(_read(backup))
        result["pendingRecovery"] = bool(manifest.get("pending"))
        entry = _matching_entry(current, manifest)
        if is_vanilla(current):
            result["state"] = "vanilla"
        elif entry:
            result["state"] = "tweaked"
            result["applied"] = list(entry["mods"])
            if not result["backupOk"]:
                result["problem"] = "The preserved original executable is missing or changed"
        else:
            result["problem"] = "The installed executable was changed outside Lexeditor"
    except (ValueError, OSError) as error:
        result.setdefault("tweaks", [])
        result["problem"] = str(error)
    return result
