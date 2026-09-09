"""Bannerlord plugin lifecycle for the shared Lexeditor host."""

from __future__ import annotations

from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, GitHubRepository, ModProjectSpec
from service_session import LocalPluginSession

from . import paths
from .game_launch import BannerlordGameController


def check() -> list[str]:
    return paths.check()


class BannerlordSession(LocalPluginSession):
    """One host-owned Bannerlord editor service."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {"LEXEDITOR_BANNERLORD_PROJECT": str(paths.project_root())}
        environment.update(extra_env or {})
        super().__init__(
            module="games.bannerlord.server",
            plugin_id="bannerlord",
            app_root=paths.LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_BANNERLORD_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host

    return run_host({"bannerlord": PLUGIN}, "bannerlord")


PLUGIN = GamePlugin(
    plugin_id="bannerlord",
    name="Mount & Blade II: Bannerlord",
    subtitle="BANNERLORD",
    description="Edit Bannerlord module metadata and progressively integrate module data.",
    accent="#8d2f25",
    check=check,
    launch=launch,
    session_factory=BannerlordSession,
    game_process_factory=BannerlordGameController,
    github=GitHubRepository(
        full_name="Lexer-Lux/Lexers-Mod-For-Bannerlord",
        authorized_logins=("Lexer-Lux",),
    ),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_BANNERLORD_PROJECT",
        default_root=paths.DEFAULT_PROJECT_ROOT,
        required_paths=("SubModule.xml",),
        required_any=(("SubModule.xml",),),
        discover=paths.installed_modules,
        template_root=paths.DEFAULT_PROJECT_ROOT,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_BANNERLORD_ROOT",
        required_paths=(
            "bin/Win64_Shipping_Client/Bannerlord.exe",
            "Modules",
        ),
        steam_app_id="261550",
        install_dir_names=("Mount & Blade II Bannerlord",),
        default_roots=(Path(
            r"C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
        ),),
        launch_path="bin/Win64_Shipping_Client/Bannerlord.exe",
    ),
    process_names=("Bannerlord.exe",),
)
