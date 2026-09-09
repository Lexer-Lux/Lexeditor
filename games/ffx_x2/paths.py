"""Paths and support checks for the FFX/X-2 HD Remaster Steam collection."""
from __future__ import annotations

import os
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
_DEFAULT_GAME_ROOT = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster")
GAME_ROOT = Path(os.environ.get("LEXEDITOR_FFX_X2_ROOT", str(_DEFAULT_GAME_ROOT)))
_LOCAL = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
PROJECT_ROOT = Path(os.environ.get(
    "LEXEDITOR_FFX_X2_PROJECT",
    str(_LOCAL / "Lexeditor" / "projects" / "ffx-x2"),
))

ARCHIVES = {
    "x": GAME_ROOT / "data" / "FFX_Data.vbf",
    "x2": GAME_ROOT / "data" / "FFX2_Data.vbf",
}
GAME_LABELS = {"x": "Final Fantasy X", "x2": "Final Fantasy X-2"}


def ensure_project(root: Path = PROJECT_ROOT) -> None:
    root = Path(root)
    (root / "efl" / "x").mkdir(parents=True, exist_ok=True)
    (root / "efl" / "x2").mkdir(parents=True, exist_ok=True)


def check() -> list[str]:
    problems: list[str] = []
    for relative in (
        "editor.html", "server.py", "plugin.py", "paths.py", "vbf.py", "deployment.py",
        "project-template/README.md",
    ):
        target = PLUGIN_ROOT / relative
        if not target.is_file():
            problems.append(f"FFX/X-2 plugin file is missing: {target}")
    return problems


def game_problems(root: Path = GAME_ROOT) -> list[str]:
    root = Path(root)
    required = (
        "FFX&X-2_LAUNCHER.exe",
        "FFX.exe",
        "FFX-2.exe",
        "data/FFX_Data.vbf",
        "data/FFX2_Data.vbf",
    )
    return [f"FFX/X-2 Steam file is missing: {root / relative}" for relative in required
            if not (root / relative).is_file()]
