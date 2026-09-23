"""Chrono Trigger Steam installation/project paths."""
from __future__ import annotations

import os
from pathlib import Path

from runtime_bootstrap import user_data_dir


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
GAME_ROOT = Path(os.environ.get("LEXEDITOR_CHRONO_TRIGGER_ROOT", r"D:\SteamLibrary\steamapps\common\Chrono Trigger"))
PROJECT_ROOT = Path(os.environ.get("LEXEDITOR_CHRONO_TRIGGER_PROJECT", user_data_dir() / "projects" / "chrono-trigger"))


def check_paths(game_root: Path, project_root: Path) -> list[str]:
    problems = []
    if not (game_root / "Chrono Trigger.exe").is_file():
        problems.append(f"Chrono Trigger.exe was not found under {game_root}")
    if not (game_root / "resources.bin").is_file():
        problems.append(f"resources.bin was not found under {game_root}")
    try:
        game = game_root.resolve()
        project = project_root.resolve()
        if project == game or game in project.parents:
            problems.append("The Chrono Trigger project must be outside the installed game folder")
    except OSError:
        pass
    return problems


def check() -> list[str]:
    return check_paths(GAME_ROOT, PROJECT_ROOT)
