"""DS1 tweak mods: build the enabled ones and apply them to the game.

A DS1 tweak mod (see core/script_mods.py) builds `native/<id>.json`, a patch
description that exe_patches.py combines with every other enabled tweak's,
and optionally `layout/<id>.json`, text nodes menu_layout.py adds to the
vanilla menu layout, and `esd/<id>.json`, commands menu_scripts.py inserts
into the ingame and common menu scripts.

DarkSoulsRemastered.exe is never written. Applying installs Lexeditor's
loader (dinput8.dll) and lexeditor-ds1-patch.bin beside it, and the loader
patches the game in memory as it starts (plugins/ds1/runtime/). Writing the
executable failed whenever a crashed game was still listed by Windows,
which keeps the file locked; FF8 learned the same lesson ("the executable is
never modified"). An executable patched by an earlier Lexeditor is put back
once, by the next Apply or Restore.

The menu layout is a data file and is still replaced, only when a tweak asks
for nodes or an earlier Apply changed it. The ingame and common menu scripts
follow the same rule for command insertions. It keeps one original copy and an
ownership journal beside it; the journal records replacement intent before
the file is written, so an interrupted Apply or Restore can be retried
without trusting unknown bytes. Outside modifications are refused, never
overwritten. The game folder also holds a one-byte OS lock file.
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

from core import mod_requires, script_mods
from core.plugin_files import atomic_write
from core.process_probe import live_processes

from . import exe_patches, menu_layout, menu_scripts

ALLOWED_ROOTS = ("native", "layout", "esd")
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
# The loader DLL in the game folder, read only to tell ours from another mod's.
RUNTIME_FILE = Managed("dinput8.dll", "loader", 64 * 1024 * 1024, lambda data: False)
LAYOUT = Managed(menu_layout.RELATIVE.as_posix(), "menu layout", 16 * 1024 * 1024,
                 lambda data: menu_layout.is_vanilla(data))
ESD_INGAME = Managed(menu_scripts.RELATIVE["ingame"].as_posix(), "ingame menu scripts",
                     16 * 1024 * 1024, lambda data: menu_scripts.is_vanilla(data, "ingame"))
ESD_COMMON = Managed(menu_scripts.RELATIVE["common"].as_posix(), "common menu scripts",
                     16 * 1024 * 1024, lambda data: menu_scripts.is_vanilla(data, "common"))
ESD = (ESD_INGAME, ESD_COMMON)
ESD_ARCHIVE = {ESD_INGAME: "ingame", ESD_COMMON: "common"}
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
    planned = {mod_id: change["enabled"] for mod_id, change in changes.items() if "enabled" in change}
    if planned:
        try:
            mod_requires.check_changes(root or mods_root(), planned)
        except ValueError as error:
            raise TweakError(str(error)) from error
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

    def __init__(self, enabled: dict[str, Path], game_root: Path | None = None,
                 library_root: Path | None = None):
        self._enabled = enabled
        self._game_root = game_root
        self._library_root = library_root
        self._params: bytes | None = None
        self.current = ""

    def game_params(self) -> bytes | None:
        """The game's GameParam.parambnd.dcx as this Apply deploys it: vanilla
        with every active data mod combined over it in load order, so a tweak
        reads what the game will (another mod's curve or cost edits included).
        None outside an Apply, when no game folder is known."""
        if self._game_root is None:
            return None
        if self._params is None:
            from . import deployment, mod_loader
            source = checked(deployment.vanilla_source(Path(self._game_root), mod_loader.RELATIVE))
            if not source.is_file():
                return None
            mods = mod_loader.active_mods(self._library_root or mods_root())
            self._params = mod_loader._compose_params(
                source.read_bytes(),
                [(mod.name, mod.files[mod_loader.RELATIVE]) for mod in mods
                 if mod_loader.RELATIVE in mod.files])[0]
        return self._params

    def enabled(self, mod_id: str) -> bool:
        return mod_id in self._enabled

    def settings(self, mod_id: str) -> dict | None:
        root = self._enabled.get(mod_id)
        return script_mods.values(root) if root else None


def build_specs(root: Path | None = None, game_root: Path | None = None) -> list[dict]:
    """Build every enabled tweak mod and read back its executable patches.

    The same build writes any layout/<id>.json or esd/<id>.json; layout_specs and esd_specs read those.
    """
    try:
        mod_requires.check_enabled(root or mods_root())
    except ValueError as error:
        raise TweakError(str(error)) from error
    rows = [row for row in tweak_rows(root) if row["enabled"]]
    context = BuildContext({row["id"]: Path(row["path"]) for row in rows}, game_root, root)
    script_mods.build_batch(rows, context, allowed_roots=ALLOWED_ROOTS, error=TweakError)
    return _built(rows, "native", exe_patches.validate)


def layout_specs(root: Path | None = None) -> list[dict]:
    """The menu-layout nodes the last build_specs produced."""
    return _built([row for row in tweak_rows(root) if row["enabled"]], "layout", menu_layout.validate)


def esd_specs(root: Path | None = None) -> list[dict]:
    """The menu-script commands the last build_specs produced."""
    return _built([row for row in tweak_rows(root) if row["enabled"]], "esd", menu_scripts.validate)


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


#: A mod's built native descriptions are small; the Mods tab reads them with
#: a bound, without running anything.
MAX_NATIVE_FILES = 64
MAX_NATIVE_BYTES = 1024 * 1024


def native_spans(folder: Path, owner: str) -> dict[str, list[tuple[int, int]]]:
    """(start, end) of every address a mod's built native patches claim, by kind.

    Reads the mod's native/*.json as last built, without running its script:
    a mod that was never built claims nothing here and is still checked when
    it is enabled. Damaged files are skipped; enabling reports them.
    """
    found: dict[str, list[tuple[int, int]]] = {"hooks": [], "state": [], "islands": []}
    try:
        files = sorted((Path(folder) / "native").glob("*.json"))
    except OSError:
        return found
    for path in files[:MAX_NATIVE_FILES]:
        try:
            if path.is_symlink() or path.stat().st_size > MAX_NATIVE_BYTES:
                continue
            spec = exe_patches.validate(json.loads(path.read_text(encoding="utf-8")), owner)
        except (OSError, ValueError):
            continue
        for kind, spans in exe_patches.spans(spec).items():
            found[kind] += spans
    return found


def build_fingerprint(folder: Path) -> str:
    """What the last build of one tweak mod saw, hashed together.

    The switch, load order, name, settings, schema, script and built files:
    anything that changes what the mod builds. The installed record keeps one
    fingerprint per enabled mod; a mod whose fingerprint differs was changed
    since the last build and needs rebuilding. Built files are read post-build,
    so a hand edit to one also asks for a rebuild, which overwrites it from
    the script.
    """
    folder = Path(folder)
    metadata = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
    parts = {"enabled": metadata.get("enabled") is True, "order": metadata.get("order", 1000),
             "name": str(metadata.get("name") or "")}
    for name in (script_mods.VALUES_FILE, script_mods.SCHEMA_FILE):
        path = folder / name
        parts[name] = path.read_bytes().hex() if path.is_file() else None
    scripts = {}
    script_dir = folder / script_mods.SCRIPT_FOLDER
    if script_dir.is_dir():
        for path in sorted(script_dir.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                digest = _sha(path.read_bytes())
            except OSError:
                continue
            scripts[path.relative_to(script_dir).as_posix()] = digest
    parts["scripts"] = scripts
    outputs = {}
    for dirname in ALLOWED_ROOTS:
        out_dir = folder / dirname
        if not out_dir.is_dir():
            continue
        for path in sorted(out_dir.rglob("*.json")):
            if not path.is_file():
                continue
            try:
                digest = _sha(path.read_bytes())
            except OSError:
                continue
            outputs[path.relative_to(folder).as_posix()] = digest
    parts["outputs"] = outputs
    return _sha(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8"))


STUCK_GAME = ('A closed Dark Souls Remastered is still listed by Windows and keeps DarkSoulsRemastered.exe locked (a crashed game whose process cannot be ended). Close every Lexeditor window; if DarkSoulsRemastered.exe is still in Task Manager after that, restart Windows. Then try again; nothing was lost.')


def ensure_game_closed() -> None:
    if os.name != "nt":
        raise TweakError("Executable tweaks can only be applied on Windows")
    if live_processes([exe_patches.EXECUTABLE]):
        raise TweakError("Close Dark Souls Remastered before changing its executable")


def game_closed() -> bool:
    """True when a tweak install may run now: Windows, and the game shut."""
    try:
        ensure_game_closed()
    except TweakError:
        return False
    return True


LOCKED_SUFFIX = ".lexeditor-locked"
# Moved-aside copies kept per file: four of the 50 MB executable, more of the
# small files (every crash pins another copy of the 27 KB loader).
MAX_LOCKED = 4
MAX_LOCKED_SMALL = 64
SMALL_FILE = 1024 * 1024


def _move_aside(game_root: Path, live: Path, error: Exception) -> None:
    """Rename a pinned file out of the way, keeping at most MAX_LOCKED of each.

    A crashed game Windows keeps listed pins every file it had loaded: the
    executable and dinput8.dll alike. Windows refuses to replace or delete
    such a file but lets it be renamed, and the game never loads it by the
    new name.
    """
    _clear_moved_aside(game_root)
    limit = MAX_LOCKED_SMALL if live.is_file() and live.stat().st_size <= SMALL_FILE else MAX_LOCKED
    for index in range(limit):
        target = checked(live.with_name(live.name + LOCKED_SUFFIX + (f"-{index}" if index else "")))
        if target.exists():
            continue
        try:
            os.replace(live, target)
            return
        except OSError:
            break
    raise TweakError(f"Windows will not let Lexeditor replace or move {live.name}. {STUCK_GAME}") from error


def _clear_moved_aside(game_root: Path) -> None:
    """Delete files moved aside earlier, once Windows has let go of them."""
    for path in Path(game_root).glob("*" + LOCKED_SUFFIX + "*"):
        try:
            checked(path).unlink()
        except OSError:
            pass  # still pinned; a later Apply or Restore tries again


def _put(game_root: Path, path: Path, data: bytes) -> None:
    """Write a game-folder file, moving a pinned old copy aside first."""
    try:
        atomic_write(path, data)
    except PermissionError as error:
        _move_aside(game_root, path, error)
        atomic_write(path, data)


def _remove(game_root: Path, path: Path) -> None:
    """Delete a game-folder file, or move it aside when it is pinned."""
    try:
        path.unlink(missing_ok=True)
    except PermissionError as error:
        _move_aside(game_root, path, error)


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
        # A pinned file is moved aside and the new one written in its place;
        # the journal above covers an interruption.
        _put(game_root, live, after)
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


def _esd_in_use(game_root: Path, managed: Managed) -> bool:
    """A menu script archive is managed once a tweak changed it, until restored."""
    return checked(managed.manifest(game_root)).is_file() or checked(managed.backup(game_root)).exists()


def _changes(specs: list[dict]) -> list[str]:
    """Only mods that change something are recorded as applied."""
    return [spec["owner"] for spec in specs
            if spec.get("islands") or spec.get("hooks") or spec.get("sectionVirtualSize")
            or spec.get("nodes") or spec.get("moves") or spec.get("changes")]


# --- The in-memory loader ------------------------------------------------------
#
# Tweaks are never written into DarkSoulsRemastered.exe. Apply puts Lexeditor's
# loader (dinput8.dll, built from plugins/ds1/runtime/) beside it with the
# combined patch description; the game loads the DLL before its own code runs
# and the DLL patches the game in memory. A crashed game Windows keeps listed
# locks only the executable, which is no longer written, and removing these
# files is a full restore. An executable patched by an earlier Lexeditor is put
# back once, by the first Apply or Restore.

RUNTIME_DLL = "dinput8.dll"
RUNTIME_PATCH = "lexeditor-ds1-patch.bin"
RUNTIME_RECORD = "lexeditor-ds1-runtime.json"
RUNTIME_LOG = "lexeditor-ds1-patch.log"
LOADER_PACKAGE = Path(__file__).with_name("runtime") / "package"
MAX_RUNTIME = 16 * 1024 * 1024
# Any of these in the game folder means Lexeditor's tweaks are, or were, installed.
OWNED_FILES = (MANIFEST_FILE, BACKUP_FILE, RUNTIME_RECORD, RUNTIME_PATCH)


def loader_bytes(debug: bool = False) -> bytes:
    """The shipped loader, checked against the hash it was published with.

    The debug loader (runtime/package/debug) blocks the game's network and
    switches Arxan off with dearxan, so a debugger can attach (#742)."""
    package = LOADER_PACKAGE / "debug" if debug else LOADER_PACKAGE
    manifest = json.loads((package / "runtime-manifest.json").read_text(encoding="utf-8"))
    data = (package / RUNTIME_DLL).read_bytes()
    if _sha(data) != manifest.get("sha256"):
        raise TweakError("Lexeditor's DS1 loader does not match its published hash; reinstall Lexeditor")
    return data


# Debug mode is the reader's choice, kept beside the DS1 mod library so Play
# and Apply both follow it.
DEBUG_FILE = ".lexeditor-ds1.json"


def debug_mode(root: Path | None = None) -> bool:
    path = Path(root or mods_root()) / DEBUG_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("debugMode") is True
    except (OSError, ValueError, AttributeError):
        return False


def set_debug_mode(on: bool, root: Path | None = None) -> bool:
    if type(on) is not bool:
        raise TweakError("Debug mode is on or off")
    folder = Path(root or mods_root())
    folder.mkdir(parents=True, exist_ok=True)
    atomic_write(folder / DEBUG_FILE, (json.dumps({"debugMode": on}, indent=2) + "\n").encode("utf-8"))
    return on


def _runtime(game_root: Path) -> dict:
    """What Lexeditor's loader files in the game folder hold now."""
    game_root = Path(game_root)
    record_path, patch_path, dll_path = (checked(game_root / name) for name in (RUNTIME_RECORD, RUNTIME_PATCH, RUNTIME_DLL))
    record = None
    if record_path.exists():
        if not record_path.is_file() or record_path.stat().st_size > MAX_MANIFEST:
            raise TweakError("Lexeditor's loader record is damaged")
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise TweakError("Lexeditor's loader record is damaged") from error
        if (type(record) is not dict or record.get("version") != 1 or not _mod_names(record.get("mods"))
                or not _digest(record.get("patchSha256")) or not _digest(record.get("dllSha256"))):
            raise TweakError("Lexeditor's loader record is damaged")
        _project(record.get("project"))
        built = record.get("built")
        if built is not None and (type(built) is not dict or not all(
                type(key) is str and _digest(value) for key, value in built.items())):
            raise TweakError("Lexeditor's loader record is damaged")
    patch = None
    if patch_path.exists():
        if not patch_path.is_file() or patch_path.stat().st_size > MAX_RUNTIME:
            raise TweakError(f"{RUNTIME_PATCH} is damaged")
        patch = patch_path.read_bytes()
    dll = _sha(_read(dll_path, RUNTIME_FILE)) if dll_path.exists() else None
    ours = {_sha(loader_bytes()), _sha(loader_bytes(debug=True))} | ({record["dllSha256"]} if record else set())
    return {"record": record, "patch": patch, "dll": dll, "foreignDll": dll is not None and dll not in ours,
            "active": bool(record and patch is not None and dll in ours and _sha(patch) == record["patchSha256"])}


def _runtime_status(game_root: Path) -> dict:
    state = _runtime(game_root)
    result = {"applied": list(state["record"]["mods"]) if state["active"] else [],
              "project": state["record"].get("project") if state["active"] else None,
              "problem": "", "loaderMessage": "",
              "debug": bool(state["active"] and state["record"].get("debug") is True)}
    if state["foreignDll"] and (state["record"] or state["patch"] is not None):
        result["problem"] = (f"Another mod's {RUNTIME_DLL} replaced Lexeditor's loader, so the tweaks are not loaded. "
                             "Remove it, then Apply again.")
    log = checked(Path(game_root) / RUNTIME_LOG)
    if log.is_file() and log.stat().st_size <= 4096:
        result["loaderMessage"] = log.read_text(encoding="utf-8", errors="replace").strip()
    return result


def needs_rebuild(game_root: Path, root: Path | None = None) -> dict:
    """Whether the installed tweaks differ from the library, and which mods changed.

    Save rebuilds only what is installed: with no loader record there is
    nothing to rebuild (tweaks first install through the Mods tab's switches
    and Play). Never raises for a damaged record or an unreadable library;
    that is status()'s problem to report, not staleness.
    """
    result: dict = {"needed": False, "stale": [], "debug": False, "set": False}
    try:
        runtime = _runtime(checked(Path(game_root)))
    except (ValueError, OSError):
        return result
    record = runtime["record"]
    if record is None:
        return result
    try:
        rows = [row for row in tweak_rows(root) if row["enabled"]]
    except (ValueError, OSError):
        return result
    built = record.get("built") or {}
    stale = []
    for row in rows:
        try:
            digest = build_fingerprint(Path(row["path"]))
        except (ValueError, OSError):
            digest = None
        if digest is None or built.get(row["id"]) != digest:
            stale.append(row["id"])
    result["stale"] = sorted(stale)
    result["set"] = set(built) != {row["id"] for row in rows}
    result["debug"] = debug_mode(root) != (record.get("debug") is True)
    result["needed"] = bool(stale) or result["set"] or result["debug"]
    return result


def _write_runtime(game_root: Path, patch: bytes | None, mods: list[str], project, debug: bool = False,
                   built: dict | None = None) -> None:
    """Install, replace or remove the loader and its patch description.

    In debug mode the debug loader goes in even with no tweak to apply."""
    game_root = checked(Path(game_root))
    state = _runtime(game_root)
    if patch is None and debug:
        patch = b""
    dll_path, patch_path, record_path = (checked(game_root / name) for name in (RUNTIME_DLL, RUNTIME_PATCH, RUNTIME_RECORD))
    if patch is None:
        # The DLL first: without it the game never reads the rest.
        if state["dll"] is not None and not state["foreignDll"]:
            _remove(game_root, dll_path)
        _remove(game_root, patch_path)
        _remove(game_root, record_path)
        _remove(game_root, checked(game_root / RUNTIME_LOG))
        return
    if state["foreignDll"]:
        raise TweakError(f"Another mod's {RUNTIME_DLL} is in the game folder. Lexeditor's loader needs that name; "
                         "remove or rename the other file, then Apply again. Nothing was changed.")
    loader = loader_bytes(debug)
    record = {"version": 1, "mods": list(mods), "project": _project(project),
              "patchSha256": _sha(patch), "dllSha256": _sha(loader), "debug": bool(debug),
              "built": dict(built or {})}
    raw = (json.dumps(record, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_MANIFEST or len(patch) > MAX_RUNTIME:
        raise TweakError("The combined tweaks are too large")
    # The record names the DLL as Lexeditor's, so it goes last: a DLL write
    # that fails must not leave a record claiming a DLL that is not there.
    if state["dll"] != _sha(loader):
        _put(game_root, dll_path, loader)
    _put(game_root, patch_path, patch)
    _put(game_root, record_path, raw)


def prepare(game_root: Path, root: Path | None = None, *, project=_KEEP_PROJECT) -> dict:
    """Build and check every file's new contents before the caller changes anything.

    Hold locked(game_root) from here through commit or rollback.
    """
    ensure_game_closed()
    game_root = checked(Path(game_root))
    _clear_moved_aside(game_root)
    current, manifest = _installed(game_root, EXECUTABLE, "restore it before applying tweaks")
    original = _original(game_root, current, manifest)
    runtime = _runtime(game_root)
    if runtime["active"]:
        previous = {"mods": list(runtime["record"]["mods"]), "project": runtime["record"].get("project"),
                    "patch": runtime["patch"], "debug": runtime["record"].get("debug") is True,
                    "built": dict(runtime["record"].get("built") or {})}
    else:
        # Before the loader, an earlier Lexeditor kept this in the executable.
        built_in = _current_manifest(current, manifest)
        previous = {"mods": list(built_in["mods"]), "project": built_in.get("project"), "patch": None,
                    "debug": False, "built": {}}
    # A project contribution can depend on verified original instruction bytes.
    chosen = previous.get("project") if project is _KEEP_PROJECT else (
        project(original) if callable(project) else project)
    chosen = _project(chosen)
    native = build_specs(root, game_root)
    # Fingerprinted after the build, so the fingerprint covers the built files too.
    built = {row["id"]: build_fingerprint(Path(row["path"]))
             for row in tweak_rows(root) if row["enabled"]}
    layout = layout_specs(root)
    scripts = esd_specs(root)
    specs = native + ([exe_patches.validate(chosen["spec"], "Project native rules")] if chosen else [])
    try:
        patch = exe_patches.runtime_patch(original, specs)
    except exe_patches.PatchError as error:
        raise TweakError(str(error)) from error
    files = []
    if not is_vanilla(current) or manifest:
        # Put an executable patched by an earlier Lexeditor back, once.
        files.append({"managed": EXECUTABLE, "before": current, "after": original, "mods": [], "project": None,
                      "previous": _current_manifest(current, manifest)})
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
    for managed in ESD:
        targeted = [spec for spec in scripts
                    if any(change["archive"] == ESD_ARCHIVE[managed] for change in spec["changes"])]
        if targeted or _esd_in_use(game_root, managed):
            esd_current, esd_manifest = _installed(game_root, managed, "restore it before applying tweaks")
            esd_original = _original(game_root, esd_current, esd_manifest, managed)
            try:
                esd_after = menu_scripts.compose(esd_original, targeted, ESD_ARCHIVE[managed])
            except ValueError as error:
                raise TweakError(str(error)) from error
            files.append({"managed": managed, "before": esd_current, "after": esd_after,
                          "mods": _changes(targeted) if esd_after != esd_original else [], "project": None,
                          "previous": _current_manifest(esd_current, esd_manifest, managed)})
    if patch is None and not debug_mode(root) and any(
            item.get("managed") in (LAYOUT, *ESD) and not item["managed"].vanilla(item["after"])
            for item in files):
        # No native patches, but a menu file stays managed: keep an empty
        # patch and its record, so later changes still ask for a rebuild.
        patch = b""
    return {"files": files, "executableSha256": _sha(current),
            "runtime": {"patch": patch, "mods": _changes(native) if patch else [],
                        "project": chosen if patch else None, "previous": previous,
                        "debug": debug_mode(root), "built": built}}


def _undo(game_root: Path, done: list[dict]) -> None:
    """Put files already written back, newest first. Never undo a file changed since."""
    for item in reversed(done):
        if item.get("managed") is None:
            previous = item["previous"]
            _write_runtime(game_root, previous["patch"], previous["mods"], previous["project"],
                           previous.get("debug", False), previous.get("built"))
            continue
        previous = item["previous"]
        _write(game_root, item["after"], item["before"], previous.get("mods", []),
               item["managed"], project=previous.get("project"))


def commit(game_root: Path, plan: dict) -> None:
    """Write every file in the plan; if one fails, the ones written go back."""
    # The patch was made for the executable prepare() read; one replaced since
    # would only be caught by the loader as the game starts.
    if _sha(_read(EXECUTABLE.live(checked(Path(game_root))))) != plan["executableSha256"]:
        raise TweakError("The executable changed while the tweaks were being prepared")
    done = []
    try:
        for item in plan["files"]:
            _write(game_root, item["before"], item["after"], item["mods"], item["managed"],
                   project=item["project"])
            done.append(item)
        runtime = plan["runtime"]
        # Counted before it starts: a failure between its files must be taken
        # back too, not only a finished install.
        done.append({"managed": None, "previous": runtime["previous"]})
        _write_runtime(game_root, runtime["patch"], runtime["mods"], runtime["project"], runtime.get("debug", False),
                       runtime.get("built"))
    except Exception:
        try:
            _undo(game_root, done)
        except Exception:
            pass  # status() reports what each file is now
        raise


def rollback(game_root: Path, plan: dict) -> None:
    runtime = plan["runtime"]
    _undo(game_root, [*plan["files"], {"managed": None, "previous": runtime["previous"]}])


def apply(game_root: Path, root: Path | None = None, *, project=_KEEP_PROJECT) -> dict:
    """Combine every enabled tweak and the project's rules, for the loader."""
    # A running game stops everything before any write, the lock file included.
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        commit(game_root, prepare(game_root, root, project=project))
    return status(game_root, root)


def restore(game_root: Path, root: Path | None = None) -> dict:
    """The game as it ships: no loader, and the original files back."""
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        _clear_moved_aside(game_root)
        managed_files = ([EXECUTABLE] + ([LAYOUT] if _layout_in_use(game_root) else [])
                         + [managed for managed in ESD if _esd_in_use(game_root, managed)])
        # Every file is checked before any of them is written.
        targets = [(managed, *_installed(game_root, managed, "it was left alone")) for managed in managed_files]
        originals = [(managed, current, manifest, _original(game_root, current, manifest, managed))
                     for managed, current, manifest in targets]
        _write_runtime(game_root, None, [], None)
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
              "pendingRecovery": False, "project": None, "loaderMessage": "",
              "builtIntoExecutable": False, "debugMode": debug_mode(root), "debugInstalled": False,
              "windows": os.name == "nt", "modsRoot": str(Path(root or mods_root())),
              "needsRebuild": False, "staleMods": []}
    try:
        result["tweaks"] = tweak_rows(root)
        game_root = Path(game_root)
        executable = _file_status(game_root, EXECUTABLE)
        files = [executable]
        if _layout_in_use(game_root):
            files.append(_file_status(game_root, LAYOUT))
        for managed in ESD:
            if _esd_in_use(game_root, managed):
                files.append(_file_status(game_root, managed))
        runtime = _runtime_status(game_root)
        # An executable still patched by an earlier Lexeditor is put back by
        # the next Apply or Restore.
        result["builtIntoExecutable"] = executable["state"] == "tweaked"
        result["backupOk"] = executable["backupOk"] or executable["state"] == "vanilla"
        states = {item["state"] for item in files}
        tweaked = "tweaked" in states or bool(runtime["applied"])
        result["state"] = "unknown" if "unknown" in states else "tweaked" if tweaked else "vanilla"
        names = runtime["applied"] + [name for item in files for name in item["applied"]]
        result["applied"] = list(dict.fromkeys(names))
        result["project"] = runtime["project"] or executable["project"]
        result["pendingRecovery"] = any(item["pendingRecovery"] for item in files)
        result["loaderMessage"] = runtime["loaderMessage"]
        result["debugInstalled"] = runtime["debug"]
        result["problem"] = runtime["problem"] or next((item["problem"] for item in files if item["problem"]), "")
        rebuild = needs_rebuild(game_root, root)
        names = {row["id"]: row.get("name") or row["id"] for row in result["tweaks"]}
        result["needsRebuild"] = rebuild["needed"]
        result["staleMods"] = [names.get(mod_id, mod_id) for mod_id in rebuild["stale"]]
    except (ValueError, OSError) as error:
        result.setdefault("tweaks", [])
        result["problem"] = str(error)
    return result
