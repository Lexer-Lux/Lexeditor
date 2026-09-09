"""Explicit FFX/X-2 launch helpers for Fahrenheit Stage 0."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess


TARGETS = {
    "x": "FFX.exe",
    "x2": "FFX-2.exe",
}


class LaunchError(RuntimeError):
    """Raised when a collection title cannot be launched safely through Fahrenheit."""


def game_key(value: str) -> str:
    key = str(value).casefold()
    if key not in TARGETS:
        raise ValueError("game must be 'x' or 'x2'")
    return key


def status(game_root: Path) -> dict:
    root = Path(game_root)
    bin_root = root / "fahrenheit" / "bin"
    stage0 = bin_root / "fhstage0.exe"
    stage1 = bin_root / "fhstage1.dll"
    games = {
        key: {
            "executable": str(root / filename),
            "ready": (root / filename).is_file(),
        }
        for key, filename in TARGETS.items()
    }
    return {
        "stage0": str(stage0),
        "stage1": str(stage1),
        "stage0Ready": stage0.is_file(),
        "stage1Ready": stage1.is_file(),
        "ready": stage0.is_file() and stage1.is_file(),
        "games": games,
    }


def command(game_root: Path, game: str) -> tuple[list[str], Path]:
    """Return the exact Stage 0 argv/cwd contract without launching anything."""
    root = Path(game_root)
    key = game_key(game)
    bin_root = root / "fahrenheit" / "bin"
    stage0 = bin_root / "fhstage0.exe"
    stage1 = bin_root / "fhstage1.dll"
    target = root / TARGETS[key]
    if not stage0.is_file():
        raise LaunchError(f"Fahrenheit Stage 0 is missing: {stage0}")
    if not stage1.is_file():
        raise LaunchError(f"Fahrenheit Stage 1 is missing: {stage1}")
    if not target.is_file():
        raise LaunchError(f"Game executable is missing: {target}")

    # Fahrenheit Stage 0 loads fhstage1.dll by relative name, so cwd must be its
    # bin directory. Fahrenheit's own docs launch FFX as ..\..\FFX.exe from here.
    # Keeping the target relative also avoids spaces in the Steam install path.
    relative_target = f"..\\..\\{TARGETS[key]}"
    return [str(stage0), relative_target], bin_root


def launch(game_root: Path, game: str) -> dict:
    """Start one collection title through Fahrenheit and return immediately."""
    if os.name != "nt":
        raise LaunchError("Fahrenheit game launch is available only on Windows")
    key = game_key(game)
    argv, cwd = command(game_root, key)
    process = subprocess.Popen(argv, cwd=str(cwd), close_fds=True)
    return {
        "launched": True,
        "game": key,
        "pid": process.pid,
        "stage0": argv[0],
        "target": TARGETS[key],
        "workingDirectory": str(cwd),
    }
