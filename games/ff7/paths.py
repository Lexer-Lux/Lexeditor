"""Paths and support checks for the Final Fantasy VII plugin."""

from __future__ import annotations

import os
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
GAME_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF7_ROOT",
    r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VII Steam Edition",
))
DATA_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF7_DATA_ROOT",
    str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Lexeditor" / "game-data" / "ff7"),
))
PROJECT_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF7_PROJECT",
    str(Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "Lexeditor" / "mods" / "ff7" / "My Mod"),
))
PROJECT_TEMPLATE_ROOT = DATA_ROOT / "project-template"
PROJECT_KERNEL_PATH = Path("ff7/workingdir/data/lang-en/kernel/kernel.bin")


def check() -> list[str]:
    """Check the plugin-owned implementation files."""
    problems: list[str] = []
    for relative in ("editor.html", "kernel.py", "server.py", "plugin.py", "paths.py", "THIRD_PARTY.md"):
        target = PLUGIN_ROOT / relative
        if not target.is_file():
            problems.append(f"FF7 plugin file is missing: {target}")
    return problems


def game_problems() -> list[str]:
    """Check the launcher installed by the current Steam edition."""
    executable = GAME_ROOT / "FFVII_LAUNCHER.exe"
    return [] if executable.is_file() else [f"FFVII_LAUNCHER.exe is missing from {GAME_ROOT}"]
