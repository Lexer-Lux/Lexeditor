"""Paths and support checks for the Chrono Trigger Steam plugin."""

from __future__ import annotations

import os
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent
DEFAULT_GAME_ROOT = Path(r"D:\SteamLibrary\steamapps\common\Chrono Trigger")
GAME_ROOT = Path(os.environ.get("LEXEDITOR_CHRONO_TRIGGER_ROOT", str(DEFAULT_GAME_ROOT)))
RESOURCE_PATH = GAME_ROOT / "resources.bin"


def check() -> list[str]:
    """Check the plugin-owned implementation files, not the user's install."""
    problems: list[str] = []
    for relative in ("editor.html", "plugin.py", "server.py", "paths.py", "resources.py"):
        target = PLUGIN_ROOT / relative
        if not target.is_file():
            problems.append(f"Chrono Trigger plugin file is missing: {target}")
    return problems


def game_problems(root: Path | None = None) -> list[str]:
    """Check the minimum Steam layout needed for archive browsing."""
    game_root = Path(root or GAME_ROOT)
    required = ("Chrono Trigger.exe", "resources.bin")
    return [
        f"Chrono Trigger Steam file is missing: {game_root / relative}"
        for relative in required
        if not (game_root / relative).is_file()
    ]
