"""DS1 tweak mods: build the enabled ones and apply them to the game.

A DS1 tweak mod (see core/script_mods.py) builds `native/<id>.json`, a patch
description that exe_patches.py combines with every other enabled tweak's
onto the vanilla executable, and optionally `layout/<id>.json`, text nodes
menu_layout.py adds to the vanilla menu layout. Applying writes the combined
files; Restore puts the preserved originals back.

Each managed file gets exactly two Lexeditor files beside it: the one
original copy, kept from the first Apply that changed it, and a manifest
naming the bytes Lexeditor last wrote. Any other version is refused, never
overwritten. The menu layout is only touched when a tweak asks for nodes or
an earlier Apply changed it.
"""
from __future__ import annotations

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


@dataclass(frozen=True)
class Managed:
    """One game file tweaks rewrite, with its preserved original and manifest."""
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


EXECUTABLE = Managed(exe_patches.EXECUTABLE, "executable", 128 * 1024 * 1024, lambda data: is_vanilla(data))
LAYOUT = Managed(menu_layout.RELATIVE.as_posix(), "menu layout", 16 * 1024 * 1024,
                 lambda data: menu_layout.is_vanilla(data))


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


def _read(path: Path, managed: Managed = EXECUTABLE) -> bytes:
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
    """Build every enabled tweak mod and read back its executable patches."""
    return build_all(root)[0]


def build_all(root: Path | None = None) -> tuple[list[dict], list[dict]]:
    """Build every enabled tweak mod: its executable and its layout patches."""
    rows = [row for row in tweak_rows(root) if row["enabled"]]
    context = BuildContext({row["id"]: Path(row["path"]) for row in rows})
    script_mods.build_batch(rows, context, allowed_roots=ALLOWED_ROOTS, error=TweakError)
    native, layout = [], []
    for row in rows:
        for folder, specs, check in (("native", native, exe_patches.validate),
                                     ("layout", layout, menu_layout.validate)):
            target = Path(row["path"]) / folder / f"{row['id']}.json"
            if not target.is_file():
                continue  # A tweak with nothing to patch here at its current settings.
            try:
                specs.append(check(json.loads(target.read_text(encoding="utf-8")), row["name"]))
            except (ValueError, exe_patches.PatchError) as error:
                raise TweakError(f"{row['name']}: {error}") from error
    return native, layout


def ensure_game_closed() -> None:
    if os.name != "nt":
        raise TweakError("Executable tweaks can only be applied on Windows")
    if live_processes([exe_patches.EXECUTABLE]):
        raise TweakError("Close Dark Souls Remastered before changing its executable")


def _manifest(game_root: Path, managed: Managed = EXECUTABLE) -> dict:
    path = checked(managed.manifest(game_root))
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("mods"), list):
        raise TweakError(f"The {managed.label} tweak manifest is damaged")
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
    return managed.vanilla(current) or (bool(manifest) and _sha(current) == manifest.get("sha256"))


def _write(game_root: Path, before: bytes, after: bytes, mods: list[str], managed: Managed = EXECUTABLE) -> None:
    game_root = checked(Path(game_root))
    live = checked(managed.live(game_root))
    backup = checked(managed.backup(game_root))
    if not backup.exists():
        # Read the original before creating the copy: the new, still empty
        # file must not be mistaken for a damaged one.
        original = _original(game_root, before, {}, managed)
        # Exclusive creation cannot overwrite an unmanaged file or a link.
        with backup.open("xb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if not managed.vanilla(_read(backup, managed)):
            raise TweakError(f"The original {managed.label} backup did not verify")
    ensure_game_closed()
    # Check again immediately before replacing; atomic replacement also fails
    # on a running Windows image's file lock.
    if _read(live, managed) != before:
        raise TweakError(f"The {managed.label} changed while the tweaks were being prepared")
    atomic_write(live, after)
    if _read(live, managed) != after:
        raise TweakError(f"{managed.label.capitalize()} verification failed; the original backup was kept")
    manifest = checked(managed.manifest(game_root))
    if mods:
        atomic_write(manifest, (json.dumps({"version": 1, "sha256": _sha(after), "mods": mods}, indent=2) + "\n").encode("utf-8"))
    else:
        manifest.unlink(missing_ok=True)


def _installed(game_root: Path, managed: Managed, action: str) -> tuple[bytes, dict]:
    current = _read(managed.live(game_root), managed)
    manifest = _manifest(game_root, managed)
    if not _owned(current, manifest, managed):
        raise TweakError(f"The installed {managed.label} was changed outside Lexeditor; {action}")
    return current, manifest


def _layout_in_use(game_root: Path) -> bool:
    """The layout is managed once a tweak changed it, until it is restored."""
    return checked(LAYOUT.manifest(game_root)).is_file() or checked(LAYOUT.backup(game_root)).exists()


def apply(game_root: Path, root: Path | None = None) -> dict:
    """Combine every enabled tweak onto the original game files and install them."""
    ensure_game_closed()
    game_root = Path(game_root)
    current, manifest = _installed(game_root, EXECUTABLE, "restore it before applying tweaks")
    native, layout = build_all(root)
    plan = []  # (file, bytes now, bytes to write, manifest mods now, manifest mods after)
    original = _original(game_root, current, manifest)
    try:
        after = exe_patches.compose(original, native)
    except exe_patches.PatchError as error:
        raise TweakError(str(error)) from error
    plan.append((EXECUTABLE, current, after, manifest.get("mods", []),
                 [spec["owner"] for spec in native] if after != original else []))
    if layout or _layout_in_use(game_root):
        layout_current, layout_manifest = _installed(game_root, LAYOUT, "restore it before applying tweaks")
        layout_original = _original(game_root, layout_current, layout_manifest, LAYOUT)
        try:
            layout_after = menu_layout.compose(layout_original, layout)
        except ValueError as error:
            raise TweakError(str(error)) from error
        plan.append((LAYOUT, layout_current, layout_after, layout_manifest.get("mods", []),
                     [spec["owner"] for spec in layout] if layout_after != layout_original else []))
    # Everything is built and checked before the first write. If a later file
    # fails, the files already written go back to what they were.
    done = []
    try:
        for managed, before, after, mods_before, mods_after in plan:
            if after != before:
                _write(game_root, before, after, mods_after, managed)
                done.append((managed, before, after, mods_before))
            elif not mods_after:
                checked(managed.manifest(game_root)).unlink(missing_ok=True)
    except Exception:
        for managed, before, after, mods_before in reversed(done):
            try:
                _write(game_root, after, before, mods_before, managed)
            except Exception:
                pass  # status() reports what each file is now
        raise
    return status(game_root, root)


def restore(game_root: Path, root: Path | None = None) -> dict:
    """Put the original game files back; the mods' switches are unchanged."""
    ensure_game_closed()
    game_root = Path(game_root)
    current, manifest = _installed(game_root, EXECUTABLE, "it was left alone")
    targets = [(EXECUTABLE, current, manifest)]
    if _layout_in_use(game_root):
        targets.append((LAYOUT, *_installed(game_root, LAYOUT, "it was left alone")))
    originals = [(managed, current, _original(game_root, current, manifest, managed))
                 for managed, current, manifest in targets]
    for managed, current, original in originals:
        if current != original:
            _write(game_root, current, original, [], managed)
        else:
            checked(managed.manifest(game_root)).unlink(missing_ok=True)
    return status(game_root, root)


def _file_status(game_root: Path, managed: Managed) -> dict:
    current = _read(managed.live(game_root), managed)
    manifest = _manifest(game_root, managed)
    backup = checked(managed.backup(game_root))
    result = {"backupOk": backup.is_file() and managed.vanilla(_read(backup, managed)),
              "state": "unknown", "applied": [], "problem": ""}
    if managed.vanilla(current):
        result["state"] = "vanilla"
    elif manifest and _sha(current) == manifest.get("sha256"):
        result["state"] = "tweaked"
        result["applied"] = list(manifest["mods"])
        if not result["backupOk"]:
            result["problem"] = f"The preserved original {managed.label} is missing or changed"
    else:
        result["problem"] = f"The installed {managed.label} was changed outside Lexeditor"
    return result


def status(game_root: Path, root: Path | None = None) -> dict:
    """What is installed now, without building or changing anything."""
    result = {"applied": [], "state": "unknown", "backupOk": False, "problem": "",
              "windows": os.name == "nt", "modsRoot": str(Path(root or mods_root()))}
    try:
        result["tweaks"] = tweak_rows(root)
        files = [_file_status(Path(game_root), EXECUTABLE)]
        if _layout_in_use(Path(game_root)):
            files.append(_file_status(Path(game_root), LAYOUT))
        result["backupOk"] = all(item["backupOk"] for item in files if item["state"] == "tweaked") and files[0]["backupOk"]
        states = {item["state"] for item in files}
        result["state"] = ("unknown" if "unknown" in states else "tweaked" if "tweaked" in states else "vanilla")
        result["applied"] = list(dict.fromkeys(name for item in files for name in item["applied"]))
        result["problem"] = next((item["problem"] for item in files if item["problem"]), "")
    except (ValueError, OSError) as error:
        result.setdefault("tweaks", [])
        result["problem"] = str(error)
    return result
