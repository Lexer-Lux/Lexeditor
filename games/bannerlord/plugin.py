"""Bannerlord plugin lifecycle for the shared Lexeditor host."""

from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import urllib.request

from plugin_api import GameInstallSpec, GamePlugin, GitHubRepository, ModProjectSpec
from service_session import LocalPluginSession, request_json

from . import paths
from .game_launch import BannerlordGameController
from .project_template import initialize_project


def check() -> list[str]:
    """Static plugin preflight; selected roots are validated by host descriptors/session."""
    return []


class BannerlordSession(LocalPluginSession):
    """One host-owned Bannerlord editor service bound to explicit selected roots."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {"LEXEDITOR_BANNERLORD_PROJECT": str(paths.project_root())}
        environment.update(extra_env or {})
        project = Path(environment["LEXEDITOR_BANNERLORD_PROJECT"])
        game = Path(environment.get("LEXEDITOR_BANNERLORD_ROOT", str(paths.game_root())))
        super().__init__(
            module="games.bannerlord.server",
            plugin_id="bannerlord",
            app_root=paths.LEXEDITOR_ROOT,
            check=lambda: paths.check(project=project, game=game),
            port_env="LEXEDITOR_BANNERLORD_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host

    return run_host({"bannerlord": PLUGIN}, "bannerlord")


def smoke() -> list[str]:
    """Boot the real Bannerlord service against isolated generated fixtures."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-bannerlord-") as temp_name:
        root = Path(temp_name)
        project = root / "Smoke Module"
        shutil.copytree(paths.PLUGIN_ROOT / "template", project)
        initialize_project(project)

        game = root / "game"
        executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"")
        (game / "Modules").mkdir()

        with BannerlordSession({
            "LEXEDITOR_BANNERLORD_PROJECT": str(project),
            "LEXEDITOR_BANNERLORD_ROOT": str(game),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("windowHost") != "webview2":
                raise RuntimeError("Bannerlord plugin did not report the shared WebView2 host")
            if Path(identity.get("editorRoot", "")).resolve() != paths.PLUGIN_ROOT.resolve():
                raise RuntimeError("Bannerlord service did not run from its packaged plugin root")

            with urllib.request.urlopen(session.url, timeout=10) as response:
                html = response.read().decode("utf-8")
            if ('id="lexeditor-shell"' not in html or
                    '/shared/framework.js' not in html or
                    "Lexeditor - Bannerlord" not in html):
                raise RuntimeError("Bannerlord plugin did not serve the shared editor interface")

            module = request_json(session.url + "api/module")
            if module.get("id") != "SmokeModule":
                raise RuntimeError("Generated Bannerlord fixture did not expose its module ID")
            project_data = request_json(session.url + "api/project")
            if project_data.get("projectFile", {}).get("name") != "SmokeModule.csproj":
                raise RuntimeError("Generated Bannerlord project was not discovered by the service")
            data_map = request_json(session.url + "api/datamap")
            descriptor_row = next((row for row in data_map.get("rows", [])
                                   if row.get("filename") == "SubModule.xml"), None)
            if not descriptor_row or descriptor_row.get("coverage") != "structured":
                raise RuntimeError("Bannerlord Data Map did not expose structured module metadata")

            saved = request_json(session.url + "api/module/save", {
                "metadata": {"name": "Smoke Module Edited"}
            })
            if saved.get("saved", 0) < 1 or saved.get("module", {}).get("name") != "Smoke Module Edited":
                raise RuntimeError("Bannerlord temporary module metadata did not save")
            if not (project / "SubModule.xml.lexeditor.bak").is_file():
                raise RuntimeError("Bannerlord temporary metadata save did not create a backup")
            if request_json(session.url + "api/module-data-files").get("files") != []:
                raise RuntimeError("Clean Bannerlord template unexpectedly contains ModuleData files")
            if request_json(session.url + "api/gauntlet-files").get("files") != []:
                raise RuntimeError("Clean Bannerlord template unexpectedly contains Gauntlet prefabs")

        if not session.process or session.process.poll() is None:
            raise RuntimeError("Bannerlord child service still runs after host shutdown")
        if not session.wait_closed():
            raise RuntimeError("Bannerlord child service port is still open after host shutdown")

    return [
        "clean Bannerlord template generated in an isolated project",
        "selected project/game roots passed through session preflight",
        "Bannerlord service identity and shared WebView2 interface confirmed",
        "generated C# project and structured Data Map discovered",
        "temporary module metadata saved with a backup",
        "host-owned Bannerlord child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="bannerlord",
    name="Mount & Blade II: Bannerlord",
    subtitle="BANNERLORD",
    description="Edit Bannerlord modules, C# projects, Gauntlet UI, and ModuleData.",
    accent="#8d2f25",
    check=check,
    launch=launch,
    smoke=smoke,
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
        template_root=paths.PLUGIN_ROOT / "template",
        initialize=initialize_project,
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
