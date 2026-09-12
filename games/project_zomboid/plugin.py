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
    for relative in (
        "common/media", "42/media/scripts", "42/media/lua/shared",
        "42/media/lua/client", "42/media/lua/server",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    info = root / "42" / "mod.info"
    text = info.read_text(encoding="utf-8")
    info.write_text(text.replace("__LEXEDITOR_NAME__", root.name).replace("__LEXEDITOR_ID__", _project_id(root.name)), encoding="utf-8")


def _looks_like_mod(root: Path) -> bool:
    return any((root / relative).is_file() for relative in ("42/mod.info", "common/mod.info", "mod.info"))


def discover_projects() -> list[Path]:
    found: list[Path] = []
    local_mods = USER_ZOMBOID_ROOT / "mods"
    if local_mods.is_dir():
        found.extend(path for path in local_mods.iterdir() if path.is_dir() and _looks_like_mod(path))
    workshop = USER_ZOMBOID_ROOT / "Workshop"
    if workshop.is_dir():
        for project in workshop.iterdir():
            mods = project / "Contents" / "mods"
            if mods.is_dir():
                found.extend(path for path in mods.iterdir() if path.is_dir() and _looks_like_mod(path))
    return sorted(set(found), key=lambda value: str(value).casefold())


def check() -> list[str]:
    return []


class ProjectZomboidSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(module="games.project_zomboid.server", plugin_id="project-zomboid", app_root=ROOT,
                         check=check, port_env="LEXEDITOR_PROJECT_ZOMBOID_PORT",
                         extra_env=dict(extra_env or {}))


def launch() -> int:
    from desktop_host import run_host
    return run_host({"project-zomboid": PLUGIN}, "project-zomboid")


def smoke() -> list[str]:
    """Exercise every structured Build 42 adapter and deployment without user data."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-project-zomboid-") as temp_name:
        temp = Path(temp_name)
        project = temp / "Lexeditor Zomboid Smoke"
        shutil.copytree(TEMPLATE_ROOT, project)
        initialize_project(project)
        script = project / "42" / "media" / "scripts" / "smoke.txt"
        script.write_text(
            "module LexSmoke\n"
            "{\n"
            " animationsMesh TestAnimationMesh\n"
            " {\n"
            "  animationDirectory = media/anims_X/LexSmoke,\n"
            "  animationDirectory = media/anims_X/Common,\n"
            "  animationPrefix = Lex_,\n"
            "  keepMeshAnimations = true,\n"
            "  meshFile = Skinned/LexSmoke,\n"
            "  postProcess = +TRIANGULATE,\n"
            " }\n"
            " item TestItem\n"
            " {\n"
            "  DisplayCategory = Tool,\n"
            "  ItemType = base:normal,\n"
            "  Weight = 0.3,\n"
            "  Icon = Radio,\n"
            "  UnknownFutureField = KeepMe,\n"
            " }\n"
            " evolvedrecipe TestSoup\n"
            " {\n"
            "  BaseItem = Base.PotOfSoup,\n"
            "  ResultItem = Base.PotOfSoup,\n"
            "  MaxItems = 4,\n"
            "  CanAddSpicesEmpty = true,\n"
            "  MinimumWater = 0.0,\n"
            " }\n"
            " craftRecipe MakeTestThing\n"
            " {\n"
            "  AllowBatchCraft = true,\n"
            "  AutoLearnAll = Woodwork:2;Maintenance:1,\n"
            "  AutoLearnAny = Woodwork:5;Carving:4,\n"
            "  CanWalk = false,\n"
            "  category = General,\n"
            "  Icon = Radio,\n"
            "  ResearchSkillLevel = -1,\n"
            "  SkillRequired = Woodwork:3,\n"
            "  Tags = InHandCraft,\n"
            "  Time = 50,\n"
            "  timedAction = Craft,\n"
            "  Tooltip = SmokeRecipeTooltip,\n"
            "  inputs { item 1 [Base.Plank], }\n"
            " }\n"
            " fixing RepairTestThing\n"
            " {\n"
            "  Require = Base.Hammer,\n"
            "  Fixer = Base.DuctTape=2;Woodwork=1,\n"
            "  ConditionModifier = 1.0,\n"
            " }\n"
            " fluid TestFluid\n"
            " {\n"
            "  ColorReference = Azure,\n"
            "  DisplayName = Fluid_Name_TestFluid,\n"
            "  Properties { HungerChange = -5, }\n"
            " }\n"
            " vehicle TestCar\n"
            " {\n"
            "  engineForce = 3000,\n"
            "  engineIdleSpeed = 750,\n"
            "  engineLoudness = 100,\n"
            "  engineQuality = 100,\n"
            "  engineRepairLevel = 4,\n"
            "  engineRPMType = jeep,\n"
            "  gearRatioCount = 5,\n"
            "  hasLighter = true,\n"
            "  isSmallVehicle = false,\n"
            "  part Engine { category = engine, }\n"
            " }\n"
            " sound TestSound\n"
            " {\n"
            "  category = Item,\n"
            "  is3D = true,\n"
            "  loop = false,\n"
            "  master = Primary,\n"
            "  maxInstancesPerEmitter = 2,\n"
            "  clip { file = media/sound/test.ogg, volume = 0.7, }\n"
            " }\n"
            " model TestModel\n"
            " {\n"
            "  cullFace = Back,\n"
            "  invertX = false,\n"
            "  postProcess = +TRIANGULATE,\n"
            "  scale = 1.0,\n"
            "  shader = vehicle,\n"
            "  static = true,\n"
            "  undoCoreScale = false,\n"
            "  mesh = LexSmoke/TestModel,\n"
            "  attachment Grip { offset = 0.0 0.0 0.0, }\n"
            " }\n"
            " mannequin TestMannequin\n"
            " {\n"
            "  animSet = mannequin,\n"
            "  animState = female,\n"
            "  female = true,\n"
            "  model = FemaleBody,\n"
            "  outfit = Casual,\n"
            "  pose = pose01,\n"
            "  texture = FemaleBody01,\n"
            " }\n"
            " timedAction TestTimedAction\n"
            " {\n"
            "  actionAnim = Loot,\n"
            "  completionSound = BuildFence,\n"
            "  muscleStrainParts = Neck;Torso_Upper,\n"
            "  prop1 = Base.HammerModel,\n"
            " }\n"
            "}\n", encoding="utf-8")
        user_root = temp / "Zomboid"
        env = {"LEXEDITOR_PROJECT_ZOMBOID_PROJECT": str(project), "LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT": str(user_root)}
        with ProjectZomboidSession(env) as session:
            identity = request_json(session.url + "api/plugin")
            required = {"build42-animation-meshes", "build42-items", "build42-evolvedrecipes", "build42-craftrecipes", "build42-fixings", "build42-fluids", "build42-vehicles", "build42-sounds", "build42-models", "build42-mannequins", "build42-timedactions", "local-deploy"}
            if identity.get("pluginId") != "project-zomboid" or required - set(identity.get("capabilities", [])):
                raise RuntimeError("Project Zomboid service reported an incomplete plugin contract")
            metadata = request_json(session.url + "api/mod-info")
            if metadata.get("fields", {}).get("id") != "Lexeditor_Zomboid_Smoke":
                raise RuntimeError("Synthetic Build 42 mod.info was not initialized")

            adapters = [
                ("animationmeshes", "animationmeshes/save", {"keepMeshAnimations": "false", "meshFile": "Skinned/LexSmokeV2"}, "meshFile", "Skinned/LexSmokeV2"),
                ("items", "items/save", {"Weight": "0.5"}, "Weight", "0.5"),
                ("evolvedrecipes", "evolvedrecipes/save", {"MaxItems": "6"}, "MaxItems", "6"),
                ("craftrecipes", "craftrecipes/save", {"time": "75", "SkillRequired": "Woodwork:4;Carving:2", "Tooltip": "SmokeRecipeTooltipUpdated"}, "SkillRequired", "Woodwork:4;Carving:2"),
                ("fixings", "fixings/save", {"ConditionModifier": "0.8"}, "ConditionModifier", "0.8"),
                ("fluids", "fluids/save", {"ColorReference": "Red"}, "ColorReference", "Red"),
                ("vehicles", "vehicles/save", {"engineForce": "4200"}, "engineForce", "4200"),
                ("sounds", "sounds/save", {"loop": "true"}, "loop", "true"),
                ("models", "models/save", {"scale": "1.5"}, "scale", "1.5"),
                ("mannequins", "mannequins/save", {"female": "false", "pose": "pose03"}, "pose", "pose03"),
                ("timedactions", "timedactions/save", {"actionAnim": "BuildLow"}, "actionAnim", "BuildLow"),
            ]
            for get_endpoint, save_endpoint, edits, key, expected in adapters:
                rows = request_json(session.url + "api/" + get_endpoint).get("rows", [])
                if len(rows) != 1:
                    raise RuntimeError(f"Synthetic {get_endpoint} record was not parsed")
                row = rows[0]
                saved = request_json(session.url + "api/" + save_endpoint, {
                    "path": row["path"], "module": row["module"], "id": row["id"],
                    "sha256": row["sha256"], "edits": edits,
                })
                if saved.get("fields", {}).get(key) != expected:
                    raise RuntimeError(f"Synthetic {get_endpoint} edit did not read back")

            text = script.read_text(encoding="utf-8")
            for expected_craft in (
                "  Time = 75,",
                "  Tags = InHandCraft,",
                "  SkillRequired = Woodwork:4;Carving:2,",
                "  Tooltip = SmokeRecipeTooltipUpdated,",
                "  AutoLearnAll = Woodwork:2;Maintenance:1,",
                "  AutoLearnAny = Woodwork:5;Carving:4,",
            ):
                if expected_craft not in text:
                    raise RuntimeError("craftRecipe typed edit or documented key preservation failed")
            for preserved in (
                "animationDirectory = media/anims_X/LexSmoke,",
                "animationDirectory = media/anims_X/Common,",
                "animationPrefix = Lex_,",
                "UnknownFutureField = KeepMe",
                "inputs { item 1 [Base.Plank], }",
                "Require = Base.Hammer,",
                "Fixer = Base.DuctTape=2;Woodwork=1,",
                "Properties { HungerChange = -5, }",
                "part Engine { category = engine, }",
                "clip { file = media/sound/test.ogg, volume = 0.7, }",
                "mesh = LexSmoke/TestModel,",
                "attachment Grip { offset = 0.0 0.0 0.0, }",
                "model = FemaleBody,",
                "completionSound = BuildFence,",
                "muscleStrainParts = Neck;Torso_Upper,",
                "prop1 = Base.HammerModel,",
            ):
                if preserved not in text:
                    raise RuntimeError("Structured writes did not preserve unknown/nested script data")
            mapped = request_json(session.url + "api/datamap").get("rows", [])
            mapped_script = next((row for row in mapped if row.get("filename") == "42/media/scripts/smoke.txt"), None)
            expected_editors = {"Animation Meshes", "Items", "Evolved Recipes", "Craft Recipes", "Fixing", "Fluids", "Vehicles", "Sounds", "Models", "Mannequins", "Timed Actions"}
            if not mapped_script or expected_editors - {part.strip() for part in mapped_script.get("editor", "").split(",") if part.strip()}:
                raise RuntimeError("Data Map omitted structured script coverage")
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
        "animationsMesh, item, evolvedrecipe, craftRecipe, fixing, fluid, vehicle, sound, model, mannequin and timedAction edits round-tripped",
        "unknown, repeated and nested Build 42 script data remained intact",
        "Data Map exposed all structured script editors",
        "local native-mod deployment and ownership-safe revert succeeded",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="project-zomboid", name="Project Zomboid", subtitle="BUILD 42",
    description="Create, inspect, edit, and locally deploy Project Zomboid Build 42 mods.",
    accent="#708057", check=check, launch=launch, smoke=smoke,
    session_factory=ProjectZomboidSession, process_names=("ProjectZomboid64.exe",),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_PROJECT_ZOMBOID_PROJECT", default_root=DEFAULT_PROJECT_ROOT,
        required_any=(("42/mod.info",), ("common/mod.info",)), template_root=TEMPLATE_ROOT,
        initialize=initialize_project, discover=discover_projects,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_PROJECT_ZOMBOID_ROOT",
        required_paths=("ProjectZomboid64.exe", "media/scripts", "media/scripts/generated"),
        steam_app_id="108600", install_dir_names=("ProjectZomboid", "Project Zomboid"),
        default_roots=(Path(r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid"),),
        launch_path="ProjectZomboid64.exe",
    ),
)
