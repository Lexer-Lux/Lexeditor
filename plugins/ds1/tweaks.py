"""Project settings and guarded file deployment for DS1 executable tweaks.

Parameter archive deployment stays independent. Saving changes only the mod
project; Apply explicitly patches the closed game's executable. A full-file
fingerprint identifies both allowed states, so an interrupted atomic replace
needs no guessed ownership marker.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

from core.plugin_files import atomic_write
from core.process_probe import live_processes
from . import equip_load_percentage as equip

SETTING_FILE = ".lexeditor-ds1-tweaks.json"
PROJECT_MARKER = ".lexeditor-ds1-project"
BACKUP_FILE = "DarkSoulsRemastered.exe.lexeditor-equip-original"


def checked(path: Path) -> Path:
    """Check lexical ancestry before following any symlink or NTFS junction."""
    path = Path(os.path.abspath(path))
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("A protected tweak path contains a symlink or junction")
        if entry == path and stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise ValueError("A protected tweak file has more than one hard link")
    return path


def read_executable(path: Path) -> bytes:
    path = checked(path)
    if not path.is_file():
        raise ValueError("The installed Remastered executable is missing")
    if path.stat().st_size not in (equip.ORIGINAL_SIZE, equip.PATCHED_SIZE):
        raise equip.UnsupportedBuild("The installed executable size is unsupported")
    value = path.read_bytes()
    equip.identify(value)
    return value


def ensure_game_closed() -> None:
    if os.name != "nt":
        raise ValueError("Executable deployment is currently supported on Windows only")
    if live_processes([equip.EXECUTABLE]):
        raise ValueError("Close Dark Souls Remastered before changing its executable")


def deploy(game_root: Path, enabled: bool) -> None:
    if type(enabled) is not bool:
        raise ValueError("The tweak must be true or false")
    ensure_game_closed()
    game_root = checked(game_root)
    live = checked(game_root / equip.EXECUTABLE)
    backup = checked(game_root / BACKUP_FILE)
    before = read_executable(live)
    current = equip.identify(before)
    if current == "vanilla" and not enabled:
        return
    if backup.exists():
        original = read_executable(backup)
        if equip.identify(original) != "vanilla":
            raise ValueError("The preserved original executable changed; refusing to continue")
    elif current != "vanilla":
        raise ValueError("The preserved original executable is missing; refusing to continue")
    else:
        # Exclusive creation cannot overwrite an unmanaged file or a symlink.
        # The live executable is untouched if backup creation/verification fails.
        original = before
        with backup.open("xb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if read_executable(backup) != original:
            raise ValueError("The original executable backup did not verify")
    after = equip.transform(before, enabled)
    if after == before:
        return
    ensure_game_closed()
    # Check again immediately before replacement. Atomic replacement, rather
    # than in-place writes, also fails on a running Windows image's file lock.
    if read_executable(live) != before:
        raise ValueError("The executable changed while the patch was being prepared")
    atomic_write(live, after)
    if read_executable(live) != after:
        raise RuntimeError("Executable verification failed; the original backup was retained")


class TweakStore:
    def __init__(self, game_root: Path, project: Path | None, read_only: bool):
        self.game_root = Path(game_root)
        self.project = Path(project) if project else None
        self.read_only = bool(read_only or not self.project)
        self.saved = self._read_setting()
        self.enabled = self.saved
        self.live = {"available": False, "applied": None, "problem": "", "backupOk": False}

    def _project_path(self) -> Path:
        if self.project is None:
            raise PermissionError("Select or create a mod before editing tweaks")
        project = checked(self.project)
        game = checked(self.game_root)
        if project == game or project in game.parents or game in project.parents:
            raise ValueError("The mod project must be outside the installed game")
        if not checked(project / PROJECT_MARKER).is_file():
            raise ValueError("Select a valid Remastered mod project")
        return checked(project / SETTING_FILE)

    def _read_setting(self) -> bool:
        if not self.project:
            return equip.DEFAULT_ENABLED
        path = self._project_path()
        if not path.exists():
            return equip.DEFAULT_ENABLED
        if path.stat().st_size > 4096:
            raise ValueError("The tweak settings file is too large")
        value = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or set(value) != {"schema", equip.TWEAK_ID}
                or value["schema"] != 1 or type(value[equip.TWEAK_ID]) is not bool):
            raise ValueError("Unsupported tweak settings; the file was left unchanged")
        return value[equip.TWEAK_ID]

    @property
    def dirty_count(self) -> int:
        return int(self.enabled != self.saved)

    def _editable(self) -> None:
        if self.read_only:
            raise PermissionError("Vanilla and reference mods are read-only")
        self._project_path()

    def edit(self, value: bool) -> dict:
        self._editable()
        if type(value) is not bool:
            raise ValueError("Equip Load Percentage must be true or false")
        self.enabled = value
        return self.snapshot()

    def validate_save(self) -> None:
        if self.dirty_count:
            self._editable()
            # Refuse to overwrite settings edited by another process.
            if self._read_setting() != self.saved:
                raise ValueError("Tweak settings changed outside this editor; discard and reload")

    def save(self) -> dict:
        self.validate_save()
        if self.dirty_count:
            path = self._project_path()
            value = {"schema": 1, equip.TWEAK_ID: self.enabled}
            atomic_write(path, (json.dumps(value, indent=2) + "\n").encode("utf-8"))
            self.saved = self.enabled
        return self.snapshot()

    def discard(self) -> dict:
        self.saved = self._read_setting()
        self.enabled = self.saved
        return self.snapshot()

    def snapshot(self, refresh: bool = False) -> dict:
        if refresh:
            try:
                current = equip.identify(read_executable(self.game_root / equip.EXECUTABLE))
                backup = checked(self.game_root / BACKUP_FILE)
                backup_ok = backup.is_file() and equip.identify(read_executable(backup)) == "vanilla"
                problem = ""
                if current == "enabled" and not backup_ok:
                    problem = "The original executable backup is missing or changed"
                self.live = {"available": not bool(problem), "applied": current == "enabled",
                             "problem": problem, "backupOk": backup_ok}
            except (ValueError, OSError) as error:
                self.live = {"available": False, "applied": None,
                             "problem": str(error), "backupOk": False}
        return {**self.live, "id": equip.TWEAK_ID, "label": equip.LABEL, "help": equip.HELP,
                "enabled": self.enabled, "savedEnabled": self.saved,
                "dirtyCount": self.dirty_count, "readOnly": self.read_only,
                "windows": os.name == "nt", "experimental": True}

    def apply(self) -> dict:
        self._editable()
        if self.dirty_count:
            raise ValueError("Save or discard tweak changes before applying")
        if self._read_setting() != self.saved:
            raise ValueError("Saved tweak settings changed; discard and reload before applying")
        deploy(self.game_root, self.saved)
        return self.snapshot(refresh=True)

    def restore(self) -> dict:
        # Explicit removal is allowed even when Vanilla is selected; it never
        # edits a read-only project's configuration.
        deploy(self.game_root, False)
        return self.snapshot(refresh=True)
