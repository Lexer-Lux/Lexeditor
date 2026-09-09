"""Chrono Trigger Steam plugin lifecycle."""

from __future__ import annotations

from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession

from . import paths


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return paths.check()


class ChronoTriggerSession(LocalPluginSession):
    """One host-owned Chrono Trigger Steam editor service."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {
            "LEXEDITOR_CHRONO_TRIGGER_ROOT": str(paths.GAME_ROOT),
            "LEXEDITOR_CHRONO_TRIGGER_PROJECT": str(paths.PROJECT_ROOT),
        }
        environment.update(extra_env or {})
        super().__init__(
            module="games.chrono_trigger.server",
            plugin_id="chrono-trigger",
            app_root=LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_CHRONO_TRIGGER_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"chrono-trigger": PLUGIN}, "chrono-trigger")


PLUGIN = GamePlugin(
    plugin_id="chrono-trigger",
    name="Chrono Trigger",
    subtitle="Steam",
    description="Steam resource, localization and scene editor with CTExt-compatible loose-file projects.",
    accent="#d3a348",
    check=check,
    launch=launch,
    session_factory=ChronoTriggerSession,
    process_names=("Chrono Trigger.exe",),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_CHRONO_TRIGGER_PROJECT",
        default_root=paths.DEFAULT_PROJECT_ROOT,
        required_any=(
            (paths.PROJECT_MARKER,),
            ("Game",),
            ("Localize",),
        ),
        template_root=paths.PROJECT_TEMPLATE_ROOT,
        discover=paths.discover_projects,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_CHRONO_TRIGGER_ROOT",
        required_paths=("Chrono Trigger.exe", "resources.bin"),
        launch_path="Chrono Trigger.exe",
        steam_app_id="613830",
        install_dir_names=("Chrono Trigger",),
        default_roots=(
            Path(r"D:\SteamLibrary\steamapps\common\Chrono Trigger"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Chrono Trigger"),
        ),
    ),
)
