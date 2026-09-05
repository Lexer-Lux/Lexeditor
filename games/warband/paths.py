"""
Lexeditor -- Warband plugin paths.

Everything game-specific about where files live belongs here, so the tools
themselves stay portable. When the RDR2 plugin lands it gets its own paths.py
and the core never learns either game's layout.

Override any of these with an environment variable of the same name.
"""

import os

WARBAND_ROOT = os.environ.get(
    "LEXEDITOR_WARBAND_ROOT",
    r"C:\Program Files (x86)\Steam\steamapps\common\MountBlade Warband")

MODULES_DIR = os.path.join(WARBAND_ROOT, "Modules")

# The mod project: where our editable Python source lives.
MOD_PROJECT = os.environ.get("LEXEDITOR_MOD_PROJECT", r"C:\Users\Lexer\Warbandmod")
MODULE_SYSTEM = os.path.join(MOD_PROJECT, "ModuleSystem")
MOD_SETTINGS = os.environ.get(
    "LEXEDITOR_WARBAND_SETTINGS",
    os.path.join(MOD_PROJECT, "settings.ini"))
MOD_BUILD = os.environ.get(
    "LEXEDITOR_WARBAND_BUILD",
    os.path.join(MOD_PROJECT, "build.bat"))

# Where extracted reports and dumps go.
OUT_DIR = os.environ.get(
    "LEXEDITOR_OUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 os.pardir, os.pardir, "out"))


def check():
    """Project validity is checked by the shared project manager."""
    return []
