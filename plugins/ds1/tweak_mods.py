"""DS1 tweak mods: build the enabled ones and apply them to the game.

A DS1 tweak mod (see core/script_mods.py) builds `native/<id>.json`, a patch
description that exe_patches.py combines with every other enabled tweak's
onto the vanilla executable, and optionally `layout/<id>.json`, text nodes
menu_layout.py adds to the vanilla menu layout. Applying writes the combined
files; Restore puts the preserved originals back. The menu layout is only
touched when a tweak asks for nodes or an earlier Apply changed it.

Each managed file keeps one original copy and an ownership journal beside
it, and the game folder holds a one-byte OS lock file. The journal records
replacement intent before a file is written, so an interrupted Apply or
Restore can be retried without trusting unknown bytes. Outside
modifications are refused, never overwritten.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Callable

from core import script_mods
from core.plugin_files import atomic_write
from core.process_probe import live_processes

from . import exe_patches, menu_layout

ALLOWED_ROOTS = ("native", "layout")
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


@dataclass(frozen=True)
class Managed:
    """One game file tweaks rewrite, with its preserved original and journal."""
    relative: str
    label: str
    limit: int
    vanilla: Callable[[bytes], bool]

    def live(self, game_root: Path) -> Path:
        return Path(game_root) / self.relative

    def backup(self, game_root: Path) -> Path:
        return Path(game_root) / (self.relative + ".lexeditor-original")

    def manifest(self, game_root: Path) -> Path:
        return Path(game_root) / (self.relative + ".lexeditor-tweaks.json")


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


def _read(path: Path, managed: "Managed | None" = None) -> bytes:
    managed = managed or EXECUTABLE
    path = checked(path)
    if not path.is_file():
        raise TweakError(f"{path.name} is missing")
    if path.stat().st_size > managed.limit:
        raise TweakError(f"{path.name} is too large to be the Remastered {managed.label}")
    return path.read_bytes()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_vanilla(data: bytes) -> bool:
    return len(data) == exe_patches.VANILLA_SIZE and _sha(data) == exe_patches.VANILLA_SHA256


EXECUTABLE = Managed(exe_patches.EXECUTABLE, "executable", 128 * 1024 * 1024, lambda data: is_vanilla(data))
LAYOUT = Managed(menu_layout.RELATIVE.as_posix(), "menu layout", 16 * 1024 * 1024,
                 lambda data: menu_layout.is_vanilla(data))
assert EXECUTABLE.backup(Path()).name == BACKUP_FILE and EXECUTABLE.manifest(Path()).name == MANIFEST_FILE


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
    """Build every enabled tweak mod and read back its executable patches.

    The same build writes any layout/<id>.json; layout_specs reads those.
    """
    rows = [row for row in tweak_rows(root) if row["enabled"]]
    context = BuildContext({row["id"]: Path(row["path"]) for row in rows})
    script_mods.build_batch(rows, context, allowed_roots=ALLOWED_ROOTS, error=TweakError)
    return _built(rows, "native", exe_patches.validate)


def layout_specs(root: Path | None = None) -> list[dict]:
    """The menu-layout nodes the last build_specs produced."""
    return _built([row for row in tweak_rows(root) if row["enabled"]], "layout", menu_layout.validate)


def _built(rows: list[dict], folder: str, check) -> list[dict]:
    specs = []
    for row in rows:
        target = checked(Path(row["path"]) / folder / f"{row['id']}.json")
        if not target.is_file():
            continue  # A tweak with nothing to patch here at its current settings.
        try:
            specs.append(check(json.loads(target.read_text(encoding="utf-8")), row["name"]))
        except (ValueError, exe_patches.PatchError) as error:
            raise TweakError(f"{row['name']}: {error}") from error
    return specs


STUCK_GAME = ('A closed Dark Souls Remastered is still listed by Windows and keeps DarkSoulsRemastered.exe locked (a crashed game whose process cannot be ended). Close every Lexeditor window; if DarkSoulsRemastered.exe is still in Task Manager after that, restart Windows. Then try again; nothing was lost.')


def ensure_game_closed() -> None:
    if os.name != "nt":
        raise TweakError("Executable tweaks can only be applied on Windows")
    if live_processes([exe_patches.EXECUTABLE]):
        raise TweakError("Close Dark Souls Remastered before changing its executable")
    # A crashed game can stay listed with no threads (a zombie). It is not
    # running, but it keeps the executable locked, so replacing it would fail
    # halfway with a bare "Access is denied". Say so before anything starts.
    from core.process_probe import zombie_processes
    if zombie_processes([exe_patches.EXECUTABLE]):
        raise TweakError(STUCK_GAME)


# No project argument means retain the last explicitly applied project rules.
# Passing None removes that contribution, without disabling library tweak mods.
_KEEP_PROJECT = object()


def locked(game_root: Path):
    """Hold the tweak lock across a whole prepare, commit and rollback."""
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


def _manifest(game_root: Path, managed: Managed = EXECUTABLE) -> dict:
    """A file's ownership record: version 1 (tweaks) or 2 (plus project rules).

    Read with a hard bound, and refuse anything damaged, including a damaged
    pending entry: a journal is only trusted when every hash in it is real.
    """
    path = checked(managed.manifest(game_root))
    if not path.exists():
        return {}
    damaged = f"The {managed.label} tweak manifest is damaged"
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST:
        raise TweakError(f"The {managed.label} tweak manifest is missing or too large")
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST:
        raise TweakError(f"The {managed.label} tweak manifest grew beyond its limit")
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise TweakError(damaged) from error
    if (type(data) is not dict or type(data.get("version")) is not int or data["version"] not in (1, 2)
            or not _digest(data.get("sha256")) or not _mod_names(data.get("mods"))):
        raise TweakError(damaged)
    keys = {"sha256", "mods"} | ({"project"} if data["version"] == 2 else set())
    pending = data.get("pending")
    if pending is not None and (type(pending) is not dict or set(pending) != keys
                                or not _digest(pending["sha256"]) or not _mod_names(pending["mods"])):
        raise TweakError(damaged)
    if data["version"] == 2:
        _project(data.get("project"))
        if pending is not None:
            _project(pending["project"])
    return data


def _original(game_root: Path, current: bytes, manifest: dict, managed: Managed = EXECUTABLE) -> bytes:
    """The verified vanilla bytes: the preserved copy, or the live file itself."""
    backup = checked(managed.backup(game_root))
    if backup.exists():
        original = _read(backup, managed)
        if not managed.vanilla(original):
            raise TweakError(f"The preserved original {managed.label} changed; refusing to continue")
        return original
    if managed.vanilla(current):
        return current
    raise TweakError(f"The preserved original {managed.label} is missing; refusing to continue")


def _owned(current: bytes, manifest: dict, managed: Managed = EXECUTABLE) -> bool:
    if managed.vanilla(current):
        return True
    digest = _sha(current)
    return bool(manifest) and digest in (
        manifest.get("sha256"), (manifest.get("pending") or {}).get("sha256"))


def _current_manifest(current: bytes, manifest: dict, managed: Managed = EXECUTABLE) -> dict:
    """Which recipe produced the bytes, including a write interrupted before completion."""
    pending = manifest.get("pending")
    if pending and _sha(current) == pending["sha256"]:
        return {"version": 2, "sha256": pending["sha256"], "mods": list(pending["mods"]),
                "project": pending.get("project"), "pending": None}
    vanilla = managed.vanilla(current)
    return {"version": 2, "sha256": _sha(current),
            "mods": [] if vanilla else list(manifest.get("mods", [])),
            "project": None if vanilla else manifest.get("project"),
            "pending": None}


def _save_manifest(game_root: Path, value: dict, managed: Managed = EXECUTABLE) -> None:
    raw = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_MANIFEST:
        raise TweakError(f"The {managed.label} tweak manifest exceeds its size limit")
    atomic_write(checked(managed.manifest(game_root)), raw)


def _finish_manifest(game_root: Path, current: bytes, mods: list[str], project=None,
                     managed: Managed = EXECUTABLE) -> None:
    if managed.vanilla(current) and not mods and project is None:
        checked(managed.manifest(game_root)).unlink(missing_ok=True)
    else:
        _save_manifest(game_root, {"version": 2, "sha256": _sha(current), "mods": list(mods),
                                   "project": project, "pending": None}, managed)


def _write(game_root: Path, before: bytes, after: bytes, mods: list[str],
           managed: Managed = EXECUTABLE, project=None) -> None:
    """Journal one expected-image replacement; keep the original plus the latest intent."""
    game_root = checked(Path(game_root))
    live = checked(managed.live(game_root))
    backup = checked(managed.backup(game_root))
    old = _manifest(game_root, managed)
    if not _owned(before, old, managed) or _read(live, managed) != before:
        raise TweakError(f"The {managed.label} changed while the tweaks were being prepared")
    original = _original(game_root, before, old, managed)
    project = _project(project)
    desired = {"sha256": _sha(after), "mods": list(mods), "project": project}
    journal = {**_current_manifest(before, old, managed), "pending": desired}
    # Check the bound before creating a backup or replacing anything.
    if len(json.dumps(journal, allow_nan=False).encode("utf-8")) > MAX_MANIFEST - 1024:
        raise TweakError(f"The {managed.label} tweak manifest exceeds its size limit")
    if after == before and not old and not mods and project is None:
        return
    if not backup.exists():
        # Exclusive creation cannot overwrite an unmanaged file or a link.
        with backup.open("xb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if not managed.vanilla(_read(backup, managed)):
            raise TweakError(f"The original {managed.label} backup did not verify")
    # Journal first. A crash before or after replacement leaves one of these
    # two complete, known images; neither an arbitrary hash nor a partial file
    # is accepted. Restore uses the same protocol.
    _save_manifest(game_root, journal, managed)
    ensure_game_closed()
    if _read(live, managed) != before:
        raise TweakError(f"The {managed.label} changed before replacement")
    if after != before:
        try:
            atomic_write(live, after)
        except PermissionError as error:
            # A game that has closed can stay in Windows' process list while
            # Steam holds it, and it keeps the file locked. The journal above
            # makes the retry safe.
            raise TweakError(f"Windows will not let Lexeditor replace the {managed.label}. {STUCK_GAME}") from error
    if _read(live, managed) != after:
        raise TweakError(f"{managed.label.capitalize()} verification failed; the original and pending intent were kept")
    _finish_manifest(game_root, after, mods, project, managed)


def _installed(game_root: Path, managed: Managed, action: str) -> tuple[bytes, dict]:
    current = _read(managed.live(game_root), managed)
    manifest = _manifest(game_root, managed)
    if not _owned(current, manifest, managed):
        raise TweakError(f"The installed {managed.label} was changed outside Lexeditor; {action}")
    return current, manifest


def _layout_in_use(game_root: Path) -> bool:
    """The layout is managed once a tweak changed it, until it is restored."""
    return checked(LAYOUT.manifest(game_root)).is_file() or checked(LAYOUT.backup(game_root)).exists()


def _changes(specs: list[dict]) -> list[str]:
    """Only mods that change something are recorded as applied."""
    return [spec["owner"] for spec in specs
            if spec.get("islands") or spec.get("hooks") or spec.get("sectionVirtualSize") or spec.get("nodes")]


def prepare(game_root: Path, root: Path | None = None, *, project=_KEEP_PROJECT) -> dict:
    """Build and check every file's new bytes before the caller changes anything.

    Hold locked(game_root) from here through commit or rollback.
    """
    ensure_game_closed()
    game_root = checked(Path(game_root))
    current, manifest = _installed(game_root, EXECUTABLE, "restore it before applying tweaks")
    previous = _current_manifest(current, manifest)
    original = _original(game_root, current, manifest)
    # A project contribution can depend on verified original instruction bytes.
    chosen = previous.get("project") if project is _KEEP_PROJECT else (
        project(original) if callable(project) else project)
    chosen = _project(chosen)
    native = build_specs(root)
    layout = layout_specs(root)
    specs = native + ([exe_patches.validate(chosen["spec"], "Project native rules")] if chosen else [])
    try:
        after = exe_patches.compose(original, specs)
    except exe_patches.PatchError as error:
        raise TweakError(str(error)) from error
    files = [{"managed": EXECUTABLE, "before": current, "after": after, "mods": _changes(native),
              "project": chosen, "previous": previous}]
    if layout or _layout_in_use(game_root):
        layout_current, layout_manifest = _installed(game_root, LAYOUT, "restore it before applying tweaks")
        layout_original = _original(game_root, layout_current, layout_manifest, LAYOUT)
        try:
            layout_after = menu_layout.compose(layout_original, layout)
        except ValueError as error:
            raise TweakError(str(error)) from error
        files.append({"managed": LAYOUT, "before": layout_current, "after": layout_after,
                      "mods": _changes(layout) if layout_after != layout_original else [], "project": None,
                      "previous": _current_manifest(layout_current, layout_manifest, LAYOUT)})
    return {"files": files}


def _undo(game_root: Path, done: list[dict]) -> None:
    """Put files already written back, newest first. Never undo a file changed since."""
    for item in reversed(done):
        previous = item["previous"]
        _write(game_root, item["after"], item["before"], previous.get("mods", []),
               item["managed"], project=previous.get("project"))


def commit(game_root: Path, plan: dict) -> None:
    """Write every file in the plan; if one fails, the ones written go back."""
    done = []
    try:
        for item in plan["files"]:
            _write(game_root, item["before"], item["after"], item["mods"], item["managed"],
                   project=item["project"])
            done.append(item)
    except Exception:
        try:
            _undo(game_root, done)
        except Exception:
            pass  # status() reports what each file is now
        raise


def rollback(game_root: Path, plan: dict) -> None:
    _undo(game_root, plan["files"])


def apply(game_root: Path, root: Path | None = None, *, project=_KEEP_PROJECT) -> dict:
    """Combine every enabled tweak and the project's rules onto the original game files."""
    # A running game stops everything before any write, the lock file included.
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        commit(game_root, prepare(game_root, root, project=project))
    return status(game_root, root)


def restore(game_root: Path, root: Path | None = None) -> dict:
    """Put the original game files back; the mods' switches are unchanged."""
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        managed_files = [EXECUTABLE] + ([LAYOUT] if _layout_in_use(game_root) else [])
        # Every file is checked before any of them is written.
        targets = [(managed, *_installed(game_root, managed, "it was left alone")) for managed in managed_files]
        originals = [(managed, current, manifest, _original(game_root, current, manifest, managed))
                     for managed, current, manifest in targets]
        for managed, current, manifest, original in originals:
            if not managed.vanilla(current) or manifest:
                _write(game_root, current, original, [], managed)
    return status(game_root, root)


def _file_status(game_root: Path, managed: Managed) -> dict:
    current = _read(managed.live(game_root), managed)
    manifest = _manifest(game_root, managed)
    backup = checked(managed.backup(game_root))
    result = {"backupOk": backup.is_file() and managed.vanilla(_read(backup, managed)),
              "state": "unknown", "applied": [], "problem": "", "project": None,
              "pendingRecovery": bool(manifest.get("pending"))}
    if not _owned(current, manifest, managed):
        result["problem"] = f"The installed {managed.label} was changed outside Lexeditor"
        return result
    active = _current_manifest(current, manifest, managed)
    result["state"] = "vanilla" if managed.vanilla(current) else "tweaked"
    result["applied"] = list(active["mods"])
    result["project"] = active.get("project")
    if result["state"] == "tweaked" and not result["backupOk"]:
        result["problem"] = f"The preserved original {managed.label} is missing or changed"
    return result


def status(game_root: Path, root: Path | None = None) -> dict:
    """What is installed now, without building or changing anything."""
    result = {"applied": [], "state": "unknown", "backupOk": False, "problem": "",
              "pendingRecovery": False, "project": None,
              "windows": os.name == "nt", "modsRoot": str(Path(root or mods_root()))}
    try:
        result["tweaks"] = tweak_rows(root)
        game_root = Path(game_root)
        files = [_file_status(game_root, EXECUTABLE)]
        if _layout_in_use(game_root):
            files.append(_file_status(game_root, LAYOUT))
        result["backupOk"] = files[0]["backupOk"] and all(
            item["backupOk"] for item in files[1:] if item["state"] == "tweaked")
        states = {item["state"] for item in files}
        result["state"] = "unknown" if "unknown" in states else "tweaked" if "tweaked" in states else "vanilla"
        result["applied"] = list(dict.fromkeys(name for item in files for name in item["applied"]))
        result["project"] = files[0]["project"]
        result["pendingRecovery"] = any(item["pendingRecovery"] for item in files)
        result["problem"] = next((item["problem"] for item in files if item["problem"]), "")
    except (ValueError, OSError) as error:
        result.setdefault("tweaks", [])
        result["problem"] = str(error)
    return result
