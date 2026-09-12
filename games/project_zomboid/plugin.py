"""Project Zomboid Build 42 plugin lifecycle."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession, request_json


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = PLUGIN_ROOT / "template"
USER_ZOMBOID_ROOT = Path(os.environ.get("LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT", Path.home() / "Zomboid"))
DEFAULT_PROJECT_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Lexeditor" / "projects" / "project-zomboid"


def _project_id(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "", name.replace(" ", "_"))
    return value or "LexeditorZomboidMod"


def initialize_project(root: Path) -> None:
    """Finish the Build 42 package skeleton after the template is copied."""
    for relative in (
        "common/media",
        "42/media/scripts",
        "42/media/lua/shared",
        "42/media/lua/client",
        "42/media/lua/server",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)

    info = root / "42" / "mod.info"
    text = info.read_text(encoding="utf-8")
    text = text.replace("__LEXEDITOR_NAME__", root.name)
    text = text.replace("__LEXEDITOR_ID__", _project_id(root.name))
    info.write_text(text, encoding="utf-8")


def _looks_like_mod(root: Path) -> bool:
    return any((root / relative).is_file() for relative in (
        "42/mod.info", "common/mod.info", "mod.info"
    ))


def discover_projects() -> list[Path]:
    """Find local test mods and authoring projects without touching Workshop downloads."""
    found: list[Path] = []
    local_mods = USER_ZOMBOID_ROOT / "mods"
    if local_mods.is_dir():
        found.extend(path for path in local_mods.iterdir() if path.is_dir() and _looks_like_mod(path))

    workshop = USER_ZOMBOID_ROOT / "Workshop"
    if workshop.is_dir():
        for project in workshop.iterdir():
            mods = project / "Contents" / "mods"
            if not mods.is_dir():
                continue
            found.extend(path for path in mods.iterdir() if path.is_dir() and _looks_like_mod(path))
    return sorted(set(found), key=lambda value: str(value).casefold())


def check() -> list[str]:
    return []


class ProjectZomboidSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = dict(extra_env or {})
        super().__init__(
            module="games.project_zomboid.server",
            plugin_id="project-zomboid",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_PROJECT_ZOMBOID_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"project-zomboid": PLUGIN}, "project-zomboid")


def smoke() -> list[str]:
    """Exercise one synthetic Build 42 edit/deploy slice without touching user data."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-project-zomboid-") as temp_name:
        temp = Path(temp_name)
        project = temp / "Lexeditor Zomboid Smoke"
        shutil.copytree(TEMPLATE_ROOT, project)
        initialize_project(project)
        script = project / "42" / "media" / "scripts" / "smoke.txt"
        script.write_text(
            "module LexSmoke\n"
            "{\n"
            "    item TestItem\n"
            "    {\n"
            "        DisplayCategory = Tool,\n"
            "        ItemType = base:normal,\n"
            "        Weight = 0.3,\n"
            "        Icon = Radio,\n"
            "        UnknownFutureField = KeepMe,\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        user_root = temp / "Zomboid"
        environment = {
            "LEXEDITOR_PROJECT_ZOMBOID_PROJECT": str(project),
            "LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT": str(user_root),
        }
        with ProjectZomboidSession(environment) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "project-zomboid":
                raise RuntimeError("Project Zomboid service reported the wrong plugin identity")
            metadata = request_json(session.url + "api/mod-info")
            if metadata.get("fields", {}).get("id") != "Lexeditor_Zomboid_Smoke":
                raise RuntimeError("Synthetic Build 42 mod.info was not initialized")
            items = request_json(session.url + "api/items").get("rows", [])
            if len(items) != 1 or items[0].get("fullType") != "LexSmoke.TestItem":
                raise RuntimeError("Synthetic Build 42 item was not parsed")
            row = items[0]
            saved = request_json(session.url + "api/items/save", {
                "path": row["path"],
                "module": row["module"],
                "id": row["id"],
                "sha256": row["sha256"],
                "edits": {"Weight": "0.5"},
            })
            if saved.get("fields", {}).get("Weight") != "0.5":
                raise RuntimeError("Synthetic item edit did not read back")
            if "UnknownFutureField = KeepMe," not in script.read_text(encoding="utf-8"):
                raise RuntimeError("Synthetic item edit did not preserve unknown script data")
            mapped = request_json(session.url + "api/datamap").get("rows", [])
            if not any(row.get("filename") == "42/media/scripts/smoke.txt" for row in mapped):
                raise RuntimeError("Project Zomboid Data Map omitted the synthetic script")
            deployed = request_json(session.url + "api/deploy", {})
            target = Path(deployed.get("target", ""))
            if not deployed.get("owned") or not (target / "42" / "mod.info").is_file():
                raise RuntimeError("Synthetic local mod deployment was not owned and readable")
            removed = request_json(session.url + "api/undeploy", {})
            if removed.get("deployed") or target.exists():
                raise RuntimeError("Synthetic local mod deployment was not removed")
        if not session.process or session.process.poll() is None:
            raise RuntimeError("Project Zomboid child service still runs after host shutdown")
        if not session.wait_closed():
            raise RuntimeError("Project Zomboid child port is still open after host shutdown")
    return [
        "Project Zomboid plugin identity confirmed",
        "synthetic Build 42 mod.info initialized",
        "Build 42 item parsed, edited and reopened with unknown data preserved",
        "Data Map exposed the representative script",
        "local native-mod deployment and ownership-safe revert succeeded",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="project-zomboid",
    name="Project Zomboid",
    subtitle="BUILD 42",
    description="Create, inspect, edit, and locally deploy Project Zomboid Build 42 mods.",
    accent="#708057",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=ProjectZomboidSession,
    process_names=("ProjectZomboid64.exe",),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_PROJECT_ZOMBOID_PROJECT",
        default_root=DEFAULT_PROJECT_ROOT,
        required_any=(("42/mod.info",), ("common/mod.info",)),
        template_root=TEMPLATE_ROOT,
        initialize=initialize_project,
        discover=discover_projects,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_PROJECT_ZOMBOID_ROOT",
        required_paths=("ProjectZomboid64.exe", "media/scripts"),
        steam_app_id="108600",
        install_dir_names=("ProjectZomboid", "Project Zomboid"),
        default_roots=(Path(r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid"),),
        launch_path="ProjectZomboid64.exe",
    ),
)
