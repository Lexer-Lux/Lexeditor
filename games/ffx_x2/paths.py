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
THEME_CACHE_ROOT = Path(os.environ.get(
    "LEXEDITOR_FFX_X2_THEME_CACHE",
    str(_LOCAL / "Lexeditor" / "cache" / "ffx-x2-theme"),
))

ARCHIVES = {
    "x": GAME_ROOT / "data" / "FFX_Data.vbf",
    "x2": GAME_ROOT / "data" / "FFX2_Data.vbf",
}
META_ARCHIVE = GAME_ROOT / "data" / "metamenu.vbf"
GAME_LABELS = {"x": "Final Fantasy X", "x2": "Final Fantasy X-2"}
VIRTUAL_ARCHIVE_ROOTS = {"x": "FFX_Data", "x2": "FFX2_Data"}


def efl_archive_path(game: str, archive_path: str) -> str:
    """Map a raw VBF name to the game-facing path Fahrenheit indexes.

    Community extractors commonly expose raw names such as ``ffx_ps2/...`` while
    Fahrenheit's External File Loader addresses the same file through the game's
    virtual ``FFX_Data/...`` or ``FFX2_Data/...`` root. Accept either spelling so
    real archives and older fixtures both resolve to one canonical EFL path.
    """
    key = str(game).casefold()
    if key not in VIRTUAL_ARCHIVE_ROOTS:
        raise ValueError("game must be 'x' or 'x2'")
    raw = str(archive_path).replace("\\", "/").strip("/")
    if not raw:
        raise ValueError("archive path is empty")
    root = VIRTUAL_ARCHIVE_ROOTS[key]
    if raw.casefold() == root.casefold() or raw.casefold().startswith(root.casefold() + "/"):
        return raw
    return f"{root}/{raw}"


def source_archive_candidates(game: str, archive_path: str) -> tuple[str, ...]:
    """Return virtual and raw spellings that may identify one VBF entry."""
    key = str(game).casefold()
    canonical = efl_archive_path(key, archive_path)
    root = VIRTUAL_ARCHIVE_ROOTS[key]
    raw = canonical[len(root):].lstrip("/")
    values = [str(archive_path).replace("\\", "/").strip("/"), canonical]
    if raw:
        values.append(raw)
    return tuple(dict.fromkeys(value for value in values if value))


def ensure_project(root: Path = PROJECT_ROOT) -> None:
    root = Path(root)
    (root / "efl" / "x").mkdir(parents=True, exist_ok=True)
    (root / "efl" / "x2").mkdir(parents=True, exist_ok=True)


def check() -> list[str]:
    problems: list[str] = []
    for relative in (
        "editor.html", "server.py", "plugin.py", "paths.py", "vbf.py", "deployment.py", "theme.py", "launch.py",
        "verify_install.py", "ffx_table.py", "ffx2_table.py", "shop_table.py", "u32_prices.py", "treasures.py",
        "item_prices.py", "auto_ability_prices.py", "ffx_auto_abilities.py", "ffx_player_stats.py", "ctb_base.py",
        "mix_table.py", "item_shops.py", "gear_shops.py", "ffx_commands.py", "ffx2_abilities.py",
        "ffx2_accessories.py", "project-template/README.md",
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
