"""Project-local settings for the independently toggleable sprint tweak."""
from __future__ import annotations

import json
import os
from pathlib import Path

from core.plugin_files import atomic_write

FILE = ".lexeditor-ds1-sprint.json"
MARKER = ".lexeditor-ds1-project"
TABLE = "LexeditorSprint"
LABEL = "Out-of-combat sprint"
HELP = (
    "Sprinting is free until an enemy targets you in its battle state. "
    "Other actions keep their stamina costs. Save, then use Apply sprint in Information."
)


def checked(path: Path) -> Path:
    """Reject symlinks and Windows reparse points, including parent components."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and
                getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Linked or redirected paths are not supported for the sprint tweak.")
    return path


def read_settings(path: Path | None) -> tuple[bool, bytes | None]:
    if path is None:
        return False, None
    path = checked(path)
    if not path.exists():
        return False, None
    if not path.is_file() or path.stat().st_size > 512:
        raise ValueError("The sprint settings file is invalid or too large.")
    raw = path.read_bytes()
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {"version", "enabled"} or
            type(value["version"]) is not int or value["version"] != 1 or
            type(value["enabled"]) is not bool):
        raise ValueError("The sprint settings must contain version 1 and a boolean enabled value.")
    return value["enabled"], raw


class SprintSettings:
    def __init__(self, game_root, project=None, read_only=True):
        self.game_root = Path(os.path.abspath(game_root))
        self.project = Path(os.path.abspath(project)) if project else None
        self.read_only = bool(read_only or self.project is None)
        self.path = self.project / FILE if self.project else None
        # No project means Vanilla. A read-only reference mod still shows its own values.
        self.enabled, self.baseline = read_settings(self.path)
        self.saved_enabled = self.enabled

    @property
    def dirty_count(self):
        return int(self.enabled != self.saved_enabled)

    def writable(self):
        if self.read_only:
            raise PermissionError("Create or select a writable mod before editing Vanilla.")
        game, project = checked(self.game_root), checked(self.project)
        if game == project or game in project.parents or project in game.parents:
            raise ValueError("The sprint mod project must be separate from the game installation.")
        if not checked(project / MARKER).is_file():
            raise ValueError("Select a valid Dark Souls mod project.")
        checked(self.path)

    def row(self, row_id=0):
        if type(row_id) is not int or row_id != 0:
            raise ValueError("Unknown sprint tweak record.")
        return {"table": TABLE, "id": 0, "name": LABEL, "fields": [
            {"key": "enabled", "label": "Enabled", "type": "bool", "dtype": "bool",
             "value": int(self.enabled), "original": 0, "editable": True,
             "minimum": 0, "maximum": 1, "group": "Traversal", "description": HELP}
        ]}

    def edit(self, row_id, field, value):
        self.writable()
        self.row(row_id)
        if field != "enabled" or not (type(value) is bool or
                type(value) is int and value in (0, 1)):
            raise ValueError("The sprint enabled setting must be a checkbox value.")
        self.enabled = bool(value)
        return self.row()

    def prepare_save(self):
        self.writable()
        if read_settings(self.path)[1] != self.baseline:
            raise ValueError("The sprint settings changed outside Lexeditor. Discard or reopen before saving.")

    def save(self):
        self.prepare_save()
        if self.dirty_count:
            atomic_write(self.path, (json.dumps({"version": 1, "enabled": self.enabled}) + "\n").encode())
        self.enabled, self.baseline = read_settings(self.path)
        self.saved_enabled = self.enabled

    def discard(self):
        self.enabled, self.baseline = read_settings(self.path)
        self.saved_enabled = self.enabled
