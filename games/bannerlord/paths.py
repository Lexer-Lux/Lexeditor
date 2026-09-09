"""Filesystem conventions for the Bannerlord plugin."""

from __future__ import annotations

import os
from pathlib import Path


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent

DEFAULT_GAME_ROOT = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
)
DEFAULT_PROJECT_ROOT = Path(r"C:\Bannermod")


def game_root() -> Path:
    return Path(os.environ.get("LEXEDITOR_BANNERLORD_ROOT", str(DEFAULT_GAME_ROOT)))


def project_root() -> Path:
    return Path(
        os.environ.get(
            "LEXEDITOR_BANNERLORD_PROJECT",
            os.environ.get("LEXEDITOR_MOD_ROOT", str(DEFAULT_PROJECT_ROOT)),
        )
    )


def modules_root(root: Path | None = None) -> Path:
    return (root or game_root()) / "Modules"


def installed_modules(root: Path | None = None) -> list[Path]:
    modules = modules_root(root)
    if not modules.is_dir():
        return []
    return sorted(
        entry
        for entry in modules.iterdir()
        if entry.is_dir() and (entry / "SubModule.xml").is_file()
    )


def check() -> list[str]:
    problems: list[str] = []
    game = game_root()
    executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
    if not executable.is_file():
        problems.append(f"Missing Bannerlord executable: {executable}")
    if not modules_root(game).is_dir():
        problems.append(f"Missing Bannerlord Modules directory: {modules_root(game)}")

    project = project_root()
    if not (project / "SubModule.xml").is_file():
        problems.append(f"Missing Bannerlord project SubModule.xml: {project / 'SubModule.xml'}")
    return problems
