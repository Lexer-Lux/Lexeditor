"""Paths and support checks for the Chrono Trigger Steam plugin."""

from __future__ import annotations

import os
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent
DEFAULT_GAME_ROOT = Path(r"D:\SteamLibrary\steamapps\common\Chrono Trigger")
GAME_ROOT = Path(os.environ.get("LEXEDITOR_CHRONO_TRIGGER_ROOT", str(DEFAULT_GAME_ROOT)))
RESOURCE_PATH = GAME_ROOT / "resources.bin"

PROJECT_MARKER = "lexeditor-project.json"
PROJECT_TEMPLATE_ROOT = PLUGIN_ROOT / "project_template"
PROJECT_ROOT = Path(os.environ.get("LEXEDITOR_CHRONO_TRIGGER_PROJECT", r"C:\ChronoTriggerMod"))
DEFAULT_PROJECT_ROOT = (
    PROJECT_ROOT if (PROJECT_ROOT / PROJECT_MARKER).is_file()
    else PROJECT_TEMPLATE_ROOT
)


def check() -> list[str]:
    """Check the plugin-owned implementation files, not the user's install."""
    problems: list[str] = []
    for relative in (
        "editor.html", "plugin.py", "server.py", "paths.py", "resources.py", "coverage.py",
        "data.py", "events.py", "field_commands.py", "scene_tables.py", "worlds.py",
        "world_tables.py", "world_scripts.py", "changes.py", "ctp.py",
        "ctext_manager.py", "deployment.py", "integrity.py",
    ):
        target = PLUGIN_ROOT / relative
        if not target.is_file():
            problems.append(f"Chrono Trigger plugin file is missing: {target}")
    if not (PROJECT_TEMPLATE_ROOT / PROJECT_MARKER).is_file():
        problems.append(f"Chrono Trigger project template is missing: {PROJECT_TEMPLATE_ROOT / PROJECT_MARKER}")
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


def discover_projects() -> list[Path]:
    """Find CTExt-style loose-file mods beside the selected Steam install."""
    mods = GAME_ROOT / "mods"
    if not mods.is_dir():
        return []
    found = []
    for root in sorted((path for path in mods.iterdir() if path.is_dir()), key=lambda path: path.name.casefold()):
        if ((root / PROJECT_MARKER).is_file() or (root / "Game").is_dir()
                or (root / "Localize").is_dir()):
            found.append(root)
    return found
