"""Final Fantasy VII Rebirth: presentation only, for now.

A deliberately small plugin. Rebirth's packages have not been read here and no
claim is made about editing them; what this gives you is the shared ReShade
support pointed at a Rebirth installation, which needs nothing game-specific
beyond knowing where the game is and which loader it wants.

Rebirth loads through DXGI. Its Win64 folder already contains a d3d12.dll of
its own - the Agility SDK's - and Lexeditor refuses to overwrite a DLL that is
not ReShade, so choosing that renderer would fail rather than break the game.
"""

from __future__ import annotations

from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from games.ff7r2 import shader_injector
from runtime_bootstrap import user_data_dir
from service_session import LocalPluginSession


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
# Beside the other plugins' mods, in the user's own data folder. Never inside
# the installed application, which is read-only once Lexeditor is installed.
DEFAULT_PROJECT = user_data_dir() / "mods" / "ff7r2" / "My Preset"
# A created project starts as this folder copied. It must be an absolute path:
# the shell validates every plugin at startup and refuses a relative one.
PROJECT_TEMPLATE = PLUGIN_ROOT / "_project_template"

# The loader Rebirth wants. Named here rather than left to the page, because
# picking d3d12 is the one choice that cannot work in this game.
RENDERER = "dxgi"
EXECUTABLE = "End/Binaries/Win64/ff7rebirth_.exe"


def check() -> list[str]:
    return []


class Ff7r2Session(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(module="games.ff7r2.server", plugin_id="ff7r2", app_root=ROOT,
                         check=check, extra_env=extra_env)


def launch() -> int:
    from desktop_host import run_host
    return run_host({"ff7r2": PLUGIN}, "ff7r2")


PLUGIN = GamePlugin(
    plugin_id="ff7r2",
    name="Final Fantasy VII Rebirth",
    subtitle="Presentation",
    description="ReShade presets for Final Fantasy VII Rebirth.",
    accent="#3f7fd0",
    check=check,
    launch=launch,
    session_factory=Ff7r2Session,
    # Shader Injector is this game's bundled helper: installed during first-time
    # setup, listed in the Updates drawer, never updated by itself. The one
    # setup step it can ask for is purging a shader cache older than itself.
    helper_name="Shader Injector",
    helper_pinned=shader_injector.VERSION,
    helper_status_for_root=shader_injector.helper_status,
    helper_install_for_root=shader_injector.helper_install,
    helper_upstream=shader_injector.upstream_release,
    helper_actions={"clear_shader_cache": shader_injector.clear_cache_action},
    projects=ModProjectSpec(
        root_env="LEXEDITOR_FF7R2_PROJECT",
        default_root=DEFAULT_PROJECT,
        # Nothing is required. A preset project starts empty and earns its
        # reshade folder when a preset is saved; demanding one up front only
        # produced a complaint about a folder nobody had made yet.
        required_paths=(),
        template_root=PROJECT_TEMPLATE,
        content_types=(
            ("ReShade presets", (".ini", ".fx")),
        ),
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_FF7R2_ROOT",
        required_paths=(EXECUTABLE, "End/Content/Paks"),
        steam_app_id="2909400",
        install_dir_names=("FINAL FANTASY VII REBIRTH",),
        default_roots=(
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY VII REBIRTH"),
        ),
        # ReShade loads from beside the renderer, not the installation root.
        reshade_root="End/Binaries/Win64",
        launch_path=EXECUTABLE,
    ),
)
