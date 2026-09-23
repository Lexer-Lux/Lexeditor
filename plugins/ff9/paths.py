"""Paths and support checks for the Final Fantasy IX Steam plugin."""

from __future__ import annotations

import os
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
GAME_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF9_ROOT",
    r"D:\SteamLibrary\steamapps\common\FINAL FANTASY IX",
))
DATA_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF9_DATA_ROOT",
    str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Lexeditor" / "game-data" / "ff9"),
))
PROJECT_ROOT = Path(os.environ.get("LEXEDITOR_FF9_PROJECT", r"C:\FF9Mod"))
PROJECT_TEMPLATE_ROOT = PLUGIN_ROOT / "project_template"
PROJECT_DATA_PATH = Path("StreamingAssets") / "Data"
DEFAULT_PROJECT_ROOT = (
    PROJECT_ROOT if (PROJECT_ROOT / PROJECT_DATA_PATH).is_dir()
    else PROJECT_TEMPLATE_ROOT
)


def check() -> list[str]:
    """Check the plugin-owned implementation files."""
    problems: list[str] = []
    for relative in ("editor.html", "server.py", "plugin.py", "paths.py", "memoria_csv.py"):
        target = PLUGIN_ROOT / relative
        if not target.is_file():
            problems.append(f"FF9 plugin file is missing: {target}")
    if not (PROJECT_TEMPLATE_ROOT / PROJECT_DATA_PATH).is_dir():
        problems.append(
            f"FF9 project template data folder is missing: "
            f"{PROJECT_TEMPLATE_ROOT / PROJECT_DATA_PATH}"
        )
    return problems


def game_problems() -> list[str]:
    """Check the exact Steam Unity layout used by this plugin."""
    required = (
        "FF9_Launcher.exe",
        "x64/FF9.exe",
        "x64/FF9_Data/Managed/Assembly-CSharp.dll",
        "StreamingAssets/p0data2.bin",
    )
    return [f"FF9 Steam file is missing: {GAME_ROOT / relative}" for relative in required
            if not (GAME_ROOT / relative).is_file()]
