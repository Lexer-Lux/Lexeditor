"""Filesystem configuration for the Lexeditor RDR2 plugin.

Plugin code and bundled UI resources live in Lexeditor. Editable mod data and
game-specific references live in the selected RDR2 project. Environment
variables allow another project or game installation without changing code.
"""

from __future__ import annotations

import os
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
PRIVATE_DATA_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", LEXEDITOR_ROOT / "out"))
    / "Lexeditor" / "game-data" / "rdr2"
)
PROJECT_ROOT = Path(
    os.environ.get("LEXEDITOR_RDR2_PROJECT", r"C:\RDR2Mod")
).expanduser().resolve()
EDITABLE_MOD_ROOT = Path(
    os.environ.get("LEXEDITOR_MOD_ROOT", PROJECT_ROOT / "MyOverhaul")
).expanduser().resolve()
GAME_ROOT = Path(
    os.environ.get(
        "RDR2_GAME_ROOT",
        r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2",
    )
).expanduser().resolve()
EXTRACT_ROOT = Path(
    os.environ.get(
        "LEXEDITOR_RDR2_EXTRACT_ROOT",
        PRIVATE_DATA_ROOT,
    )
).expanduser().resolve()


def check() -> list[str]:
    required = (
        (PROJECT_ROOT, "RDR2 project"),
        (PLUGIN_ROOT / "server.py", "RDR2 plugin service"),
        (PLUGIN_ROOT / "editor.html", "RDR2 plugin interface"),
        (PLUGIN_ROOT / "settings_schema.json", "RDR2 settings schema"),
        (PLUGIN_ROOT / "assets", "RDR2 plugin assets"),
        (PLUGIN_ROOT / "vendor" / "reddead2blend" / "pylibdrawable.pyd",
         "RDR2 YDR model decoder"),
    )
    return [f"Missing {label}: {path}" for path, label in required if not path.exists()]
