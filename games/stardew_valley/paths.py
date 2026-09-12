"""Filesystem locations used by the Stardew Valley plugin."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent
PROJECT_TEMPLATE_ROOT = PLUGIN_ROOT / "project_template"


def _user_data_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        value = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        base = value if value.is_absolute() else Path.home() / ".local" / "share"
    return (base / "Lexeditor").resolve()


DEFAULT_PROJECT_ROOT = (_user_data_root() / "projects" / "stardew-valley").resolve()
GAME_ROOT = Path(os.environ.get(
    "LEXEDITOR_STARDEW_ROOT",
    r"C:\Program Files (x86)\Steam\steamapps\common\Stardew Valley",
)).expanduser()
PROJECT_ROOT = Path(os.environ.get(
    "LEXEDITOR_STARDEW_PROJECT", str(DEFAULT_PROJECT_ROOT)
)).expanduser().resolve()


def check() -> list[str]:
    problems: list[str] = []
    for relative in ("editor.html", "server.py", "project_template/manifest.json", "project_template/content.json"):
        if not (PLUGIN_ROOT / relative).is_file():
            problems.append(f"Missing Stardew Valley plugin file: {relative}")
    return problems


def game_problems(root: Path | None = None) -> list[str]:
    root = Path(root or GAME_ROOT)
    problems: list[str] = []
    if not root.is_dir():
        return [f"Stardew Valley directory does not exist: {root}"]
    for relative in ("Stardew Valley.exe", "Content"):
        if not (root / relative).exists():
            problems.append(f"Missing required Stardew Valley file or folder: {relative}")
    return problems
