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
    """Find local test mods and Workshop authoring projects."""
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
        super().__init__(
            module="games.project_zomboid.server",
            plugin_id="project-zomboid",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_PROJECT_ZOMBOID_PORT",
            extra_env=dict(extra_env or {}),
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"project-zomboid": PLUGIN}, "project-zomboid")


def smoke() -> list[str]:
    """Exercise structured Build 42 edit/deploy paths without touching user data."""
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
            "    evolvedrecipe Test Soup\n"
            "    {\n"
            "        BaseItem = Base.PotOfSoup,\n"
            "        ResultItem = Base.PotOfSoup,\n"
            "        MaxItems = 4,\n"
            "        CanAddSpicesEmpty = true,\n"
            "        MinimumWater = 0.0,\n"
            "    }\n"
            "    craftRecipe Make Test Thing\n"
            "    {\n"
            "        AllowBatchCraft = true,\n"
            "        CanWalk = false,\n"
            "        category = General,\n"
            "        Icon = Radio,\n"
            "        ResearchSkillLevel = -1,\n"
            "        tags = InHandCraft,\n"
            "        time = 50,\n"
            "        timedAction = Craft,\n"
            "        inputs { item 1 [Base.Plank], }\n"
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
            required = {"build42-items", "build42-evolvedrecipes", "build42-craftrecipes", "local-deploy"}
            if identity.get("pluginId") != "project-zomboid" or required - set(identity.get("capabilities", [])):
                raise RuntimeError("Project Zomboid service reported an incomplete plugin contract")
            metadata = request_json(session.url + "api/mod-info")
            if metadata.get("fields", {}).get("id") != "Lexeditor_Zomboid_Smoke":
                raise RuntimeError("Synthetic Build 42 mod.info was not initialized")

            items = request_json(session.url + "api/items").get("rows", [])
            if len(items) != 1 or items[0].get("fullType") != "LexSmoke.TestItem":
                raise RuntimeError("Synthetic Build 42 item was not parsed")
            item = items[0]
            saved_item = request_json(session.url + "api/items/save", {
                "path": item["path"], "module": item["module"], "id": item["id"],
                "sha256": item["sha256"], "edits": {"Weight": "0.5"},
            })
            if saved_item.get("fields", {}).get("Weight") != "0.5":
                raise RuntimeError("Synthetic item edit did not read back")

            evolved = request_json(session.url + "api/evolvedrecipes").get("rows", [])
            if len(evolved) != 1:
                raise RuntimeError("Synthetic evolved recipe was not parsed")
            recipe = evolved[0]
            saved_evolved = request_json(session.url + "api/evolvedrecipes/save", {
                "path": recipe["path"], "module": recipe["module"], "id": recipe["id"],
                "sha256": recipe["sha256"], "edits": {"MaxItems": "6"},
            })
            if saved_evolved.get("fields", {}).get("MaxItems") != "6":
                raise RuntimeError("Synthetic evolved recipe edit did not read back")

            crafts = request_json(session.url + "api/craftrecipes").get("rows", [])
            if len(crafts) != 1:
                raise RuntimeError("Synthetic craft recipe was not parsed")
            craft = crafts[0]
            saved_craft = request_json(session.url + "api/craftrecipes/save", {
                "path": craft["path"], "module": craft["module"], "id": craft["id"],
                "sha256": craft["sha256"], "edits": {"time": "75", "AllowBatchCraft": "false"},
            })
            if saved_craft.get("fields", {}).get("time") != "75":
                raise RuntimeError("Synthetic craft recipe edit did not read back")

            text = script.read_text(encoding="utf-8")
            if "UnknownFutureField = KeepMe," not in text or "inputs { item 1 [Base.Plank], }" not in text:
                raise RuntimeError("Structured writes did not preserve unknown/nested script data")
            mapped = request_json(session.url + "api/datamap").get("rows", [])
            mapped_script = next((row for row in mapped if row.get("filename") == "42/media/scripts/smoke.txt"), None)
            if not mapped_script or "Craft Recipes" not in mapped_script.get("editor", ""):
                raise RuntimeError("Data Map omitted structured recipe coverage")
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
        "Project Zomboid plugin identity and structured capabilities confirmed",
        "synthetic Build 42 mod.info initialized",
        "item, evolvedrecipe and craftRecipe edits round-tripped with unknown data preserved",
        "Data Map exposed structured script coverage",
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
