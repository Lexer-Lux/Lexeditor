"""Filesystem configuration for the Lexeditor RDR plugin."""

from __future__ import annotations

import os
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
PROJECT_ROOT = Path(
    os.environ.get("LEXEDITOR_RDR_PROJECT", r"C:\RDRMod")
).expanduser().resolve()
MOD_ROOT = Path(
    os.environ.get("LEXEDITOR_RDR_MOD_ROOT", PROJECT_ROOT / "mod")
).expanduser().resolve()
SETTINGS_FILE = Path(
    os.environ.get("LEXEDITOR_RDR_SETTINGS", PROJECT_ROOT / "LexerRDR.ini")
).expanduser().resolve()
GAME_ROOT = Path(
    os.environ.get(
        "RDR_GAME_ROOT",
        r"D:\SteamLibrary\steamapps\common\Red Dead Redemption",
    )
).expanduser().resolve()
EXTRACT_ROOT = Path(
    os.environ.get(
        "LEXEDITOR_RDR_EXTRACT_ROOT",
        Path(os.environ.get("LOCALAPPDATA", PROJECT_ROOT / "_vanilla"))
        / "Lexeditor" / "game-data" / "rdr",
    )
).expanduser().resolve()
RPF6_TOOL = LEXEDITOR_ROOT / "tools" / "magic-rdr" / "app" / "Rpf6ReadCli.exe"
RPF6_NAMES = (
    LEXEDITOR_ROOT / "tools" / "magic-rdr" / "app"
    / "Settings" / "ImportedFileNames.txt"
)
RDR2_FONT_ROOT = LEXEDITOR_ROOT / "games" / "rdr2" / "assets" / "fonts"


def check() -> list[str]:
    required = (
        (PROJECT_ROOT, "RDR project"),
        (PLUGIN_ROOT / "server.py", "RDR plugin service"),
        (PLUGIN_ROOT / "editor.html", "RDR plugin interface"),
        (PLUGIN_ROOT / "extractor.py", "RDR preparation service"),
        (RPF6_TOOL, "RPF6 read-only bridge"),
        (RPF6_NAMES, "RPF6 filename dictionary"),
    )
    return [
        f"Missing {label}: {path}"
        for path, label in required
        if not path.exists()
    ]
