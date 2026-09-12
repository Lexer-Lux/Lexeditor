"""Terraria plugin lifecycle targeting tModLoader's native source workflow."""

from __future__ import annotations

import os
import re
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = PLUGIN_ROOT / "template"
TMODLOADER_SAVE_ROOT = Path(
    os.environ.get(
        "LEXEDITOR_TERRARIA_SAVE_ROOT",
        Path.home() / "Documents" / "My Games" / "Terraria" / "tModLoader",
    )
)
MOD_SOURCES_ROOT = TMODLOADER_SAVE_ROOT / "ModSources"
DEFAULT_PROJECT_ROOT = MOD_SOURCES_ROOT / "LexeditorTerrariaMod"


def _mod_id(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "", name.replace(" ", "_"))
    if not value:
        value = "LexeditorTerrariaMod"
    if value[0].isdigit():
        value = "Mod_" + value
    return value


def initialize_project(root: Path) -> None:
    """Turn the packaged skeleton into one valid tModLoader source project."""
    mod_id = _mod_id(root.name)
    replacements = {
        "__LEXEDITOR_DISPLAY_NAME__": root.name,
        "__LEXEDITOR_ID__": mod_id,
    }
    for filename in ("build.txt", "LexeditorTerrariaMod.csproj", "LexeditorTerrariaMod.cs"):
        path = root / filename
        text = path.read_text(encoding="utf-8-sig")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    for suffix in (".csproj", ".cs"):
        source = root / f"LexeditorTerrariaMod{suffix}"
        target = root / f"{mod_id}{suffix}"
        if source != target:
            source.replace(target)

    (root / "Content").mkdir(exist_ok=True)
    (root / "Localization").mkdir(exist_ok=True)


def _looks_like_source_mod(root: Path) -> bool:
    if not (root / "build.txt").is_file():
        return False
    return any(path.is_file() for path in root.glob("*.csproj"))


def discover_projects() -> list[Path]:
    if not MOD_SOURCES_ROOT.is_dir():
        return []
    return sorted(
        (path for path in MOD_SOURCES_ROOT.iterdir() if path.is_dir() and _looks_like_source_mod(path)),
        key=lambda value: value.name.casefold(),
    )


def check() -> list[str]:
    return []


class TerrariaSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(
            module="games.terraria.server",
            plugin_id="terraria",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_TERRARIA_PORT",
            extra_env=dict(extra_env or {}),
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"terraria": PLUGIN}, "terraria")


PLUGIN = GamePlugin(
    plugin_id="terraria",
    name="Terraria",
    subtitle="tModLoader 1.4.4",
    description="Create and edit native tModLoader source mods without modifying vanilla Terraria.",
    accent="#77b255",
    check=check,
    launch=launch,
    session_factory=TerrariaSession,
    projects=ModProjectSpec(
        root_env="LEXEDITOR_TERRARIA_PROJECT",
        default_root=DEFAULT_PROJECT_ROOT,
        required_paths=("build.txt",),
        template_root=TEMPLATE_ROOT,
        initialize=initialize_project,
        discover=discover_projects,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_TERRARIA_ROOT",
        required_paths=("start-tModLoader.bat", "tModLoader.dll", "LaunchUtils"),
        steam_app_id="1281930",
        install_dir_names=("tModLoader",),
        default_roots=(Path(r"C:\Program Files (x86)\Steam\steamapps\common\tModLoader"),),
        launch_path="start-tModLoader.bat",
    ),
)
