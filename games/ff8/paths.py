"""Paths and readiness checks for the Final Fantasy VIII plugin."""

from __future__ import annotations

import os
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
GAME_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF8_ROOT",
    r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII",
))
DATA_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF8_DATA_ROOT",
    str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Lexeditor" / "game-data" / "ff8"),
))
PROJECT_ROOT = Path(os.environ.get("LEXEDITOR_FF8_PROJECT", r"C:\FF8Mod"))
BASELINE_ROOT = DATA_ROOT / "baseline" / "en"
DIRECT_ROOT = PROJECT_ROOT / "direct"
LOCAL_DATA_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF8_LOCAL_DATA",
    str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Lexeditor"),
))
# An editable mod is source data. FFNx reads only this composed runtime tree.
# Keeping the two roots separate lets Lexeditor add load order and conflict
# handling without turning one selected project into the game installation.
RUNTIME_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF8_RUNTIME_ROOT",
    str(LOCAL_DATA_ROOT / "runtime" / "ff8" / "active"),
))
RUNTIME_DIRECT_ROOT = RUNTIME_ROOT / "direct"
RUNTIME_HEXT_ROOT = RUNTIME_ROOT / "hext"
MODS_ROOT = Path(os.environ.get(
    "LEXEDITOR_FF8_MODS_ROOT",
    str(LOCAL_DATA_ROOT / "mods" / "ff8"),
))

ARCHIVES = {
    "main": GAME_ROOT / "Data" / "lang-en" / "main",
    "menu": GAME_ROOT / "Data" / "lang-en" / "menu",
    "battle": GAME_ROOT / "Data" / "lang-en" / "battle",
}


def check() -> list[str]:
    """Check plugin support files. The launcher checks the game installation."""
    problems: list[str] = []
    for relative in (
        "editor.html", "server.py", "formats.py", "extractor.py", "game_font.py",
        "gameplay_settings.py", "flat_stat_abilities.py", "max_spell.py",
        "single_gf.py", "game_icons.py",
        "ffnx_issue_51/runtime_config.py", "ffnx_issue_51/runtime_package.py",
        "runtime_layout.py", "iroj_archive.py", "mod_folders.py", "mngrp_merge.py",
        "featured_mods.py", "featured_mods.json",
        "world_map.py", "world_geometry.py", "world_textures.py", "world_data_merge.py", "field_data.py", "field_background.py", "field_dialogue.py", "field_encounters.py", "field_scripts.py", "field_walkmesh.py", "kernel_text.py", "mngrp_text.py", "refine_tables.py",
        "executable_text.py", "cards.py", "cards_ui.js", "card_art.py", "enemies_ui.js", "enemies_ui.css",
        "menu_items.py", "enemy_tables.py", "enemy_ai.py", "enemy_battle_text.py", "encounters.py", "scan_text.py", "init_data.py",
        "schema/item.json", "schema/kernel_bin_data.json", "schema/jsm_opcodes.json",
        "schema/kernel_section_fields.json", "schema/kernel_lookups.json",
        "schema/mitem.json", "schema/card.json", "schema/enemy_abilities.json",
        "schema/status.json",
        "schema/limit_break.json",
        "vendor/ff8ue/lzs.py",
    ):
        target = PLUGIN_ROOT / relative
        if not target.is_file():
            problems.append(f"FF8 plugin file is missing: {target}")
    return problems


def game_problems() -> list[str]:
    problems: list[str] = []
    if not (GAME_ROOT / "FF8_EN.exe").is_file():
        problems.append(f"FF8_EN.exe is missing from {GAME_ROOT}")
    for name, prefix in ARCHIVES.items():
        for suffix in (".fs", ".fi", ".fl"):
            if not prefix.with_suffix(suffix).is_file():
                problems.append(f"The {name}{suffix} archive file is missing")
    world = GAME_ROOT / "Data" / "lang-en" / "world"
    for suffix in (".fs", ".fi", ".fl"):
        if not world.with_suffix(suffix).is_file():
            problems.append(f"The world{suffix} archive file is missing")
    field = GAME_ROOT / "Data" / "lang-en" / "field"
    for suffix in (".fs", ".fi", ".fl"):
        if not field.with_suffix(suffix).is_file():
            problems.append(f"The field{suffix} archive file is missing")
    return problems


def ffnx_status() -> dict:
    """Report the FFNx boundary without changing the installed game."""
    config = GAME_ROOT / "FFNx.toml"
    driver = GAME_ROOT / "AF3DN.P"
    installed = config.is_file() and driver.is_file() and driver.stat().st_size > 1_000_000
    return {
        "installed": installed,
        "config": str(config),
        "loader": str(driver) if installed else "",
        "directRoot": str(RUNTIME_DIRECT_ROOT),
        "projectDirectRoot": str(DIRECT_ROOT),
        "runtimeRoot": str(RUNTIME_ROOT),
        "message": (
            "FFNx is ready to load the project's direct overrides."
            if installed else
            "FFNx is not installed. Lexeditor can edit the project, but the game cannot load these overrides yet."
        ),
    }


ff7nx_status = ffnx_status
