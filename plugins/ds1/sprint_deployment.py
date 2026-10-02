"""Explicit, closed-game installation of one fingerprinted sprint projection."""
from __future__ import annotations

import os
from pathlib import Path

from core.plugin_files import atomic_write
from . import out_of_combat_sprint as patch
from .sprint_settings import checked

BACKUP = patch.EXECUTABLE + ".lexeditor-sprint-original"


def ensure_game_closed():
    if os.name != "nt":
        raise ValueError("Applying the sprint patch requires Windows.")
    from core.process_probe import live_processes
    if live_processes([patch.EXECUTABLE]):
        raise ValueError("Close Dark Souls Remastered before applying or restoring sprint.")


def read_image(path):
    path = checked(path)
    if not path.is_file() or path.stat().st_size not in (
            patch.ORIGINAL_SIZE, patch.ORIGINAL_SIZE + patch.ADDED_SIZE):
        raise patch.UnsupportedBuild("The supported Remastered executable was not found.")
    image = path.read_bytes()
    patch.identify(image)
    return image


def snapshot(game_root):
    root = checked(Path(game_root))
    live, backup = root / patch.EXECUTABLE, root / BACKUP
    source = read_image(live)
    enabled = patch.identify(source)
    checked(backup)
    original = read_image(backup) if backup.exists() else None
    if original is not None and patch.identify(original):
        raise ValueError("The sprint backup is not the verified original.")
    if enabled and original is None:
        raise ValueError("The original sprint backup is missing. Restore it before continuing.")
    return root, live, backup, source, original


def status(game_root):
    try:
        _, _, _, source, original = snapshot(game_root)
        return {"supported": True, "enabled": patch.identify(source),
                "backupOk": original is not None, "error": ""}
    except (ValueError, OSError) as error:
        return {"supported": False, "enabled": False, "backupOk": False, "error": str(error)}


def apply(game_root, enabled):
    if type(enabled) is not bool:
        raise ValueError("Sprint enabled must be a boolean.")
    ensure_game_closed()
    _, live, backup, source, original = snapshot(game_root)
    if original is None:
        original = source
    target = patch.build(original, enabled)
    if target == source:
        return status(game_root)
    if not backup.exists():
        # One exclusive original. Partial backup writes are removed only by this
        # invocation; an interrupted process leaves a refused backup, not a
        # falsely trusted original. The live image has not been touched yet.
        created = False
        try:
            with backup.open("xb") as stream:
                created = True
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            if read_image(backup) != original:
                raise ValueError("The sprint original backup did not verify.")
        except BaseException:
            if created:
                backup.unlink(missing_ok=True)
            raise
    ensure_game_closed()
    if read_image(live) != source or read_image(backup) != original:
        raise ValueError("The installed executable or sprint backup changed during preparation.")
    # Both accepted full images are independently fingerprinted. If this write
    # is interrupted, retry recognises either complete image; no ownership
    # record needs to guess whether the replacement completed.
    atomic_write(live, target)
    if read_image(live) != target:
        raise RuntimeError("The installed sprint image did not verify; the original backup was retained.")
    return status(game_root)


def restore(game_root):
    return apply(game_root, False)
