"""Separate plugin identity for Final Fantasy VII (2013)."""

from __future__ import annotations

import tempfile
import os
import json
import shutil
import urllib.request
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession, request_json
from games.ff7.plugin import prepare_product, kernel_save_payload
from games.ff7.kernel import Kernel, resolve_kernel


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
SHARED_PLUGIN_ROOT = LEXEDITOR_ROOT / "games" / "ff7"
DEFAULT_ROOT = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VII")
LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Lexeditor"
DEFAULT_DATA = LOCAL_DATA / "game-data" / "ff7-2013"
DEFAULT_PROJECT = Path(os.environ.get(
    "LEXEDITOR_FF7_2013_PROJECT",
    str(LOCAL_DATA / "mods" / "ff7-2013" / "My Mod"),
))
PROJECT_TEMPLATE = DEFAULT_DATA / "project-template"
PROJECT_KERNEL_PATH = Path("data/lang-en/kernel/KERNEL.BIN")


def check() -> list[str]:
    required = (
        SHARED_PLUGIN_ROOT / "editor.html",
        SHARED_PLUGIN_ROOT / "kernel.py",
        SHARED_PLUGIN_ROOT / "server.py",
    )
    return [f"Shared FF7 plugin file is missing: {target}" for target in required if not target.is_file()]


def prepare(game_root: Path, data_root: Path, progress) -> dict:
    return prepare_product(
        game_root, data_root, progress,
        PROJECT_TEMPLATE, DEFAULT_PROJECT,
    )


class FF7LegacySession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {
            "LEXEDITOR_FF7_ROOT": os.environ.get("LEXEDITOR_FF7_2013_ROOT", str(DEFAULT_ROOT)),
            "LEXEDITOR_FF7_DATA_ROOT": os.environ.get("LEXEDITOR_FF7_2013_DATA_ROOT", str(DEFAULT_DATA)),
            "LEXEDITOR_FF7_PROJECT": str(DEFAULT_PROJECT),
            "LEXEDITOR_FF7_PLUGIN_ID": "ff7-2013",
            "LEXEDITOR_FF7_PLUGIN_NAME": "Final Fantasy 7 (Remaster)",
            "LEXEDITOR_FF7_EDITION": "2013 Steam release",
            "LEXEDITOR_FF7_EXECUTABLE": "ff7_en.exe",
        }
        supplied = dict(extra_env or {})
        selected_project = supplied.pop("LEXEDITOR_FF7_2013_PROJECT", None)
        environment.update(supplied)
        if selected_project:
            environment["LEXEDITOR_FF7_PROJECT"] = selected_project
        super().__init__(module="games.ff7.server", plugin_id="ff7-2013",
            app_root=LEXEDITOR_ROOT, check=check, port_env="LEXEDITOR_FF7_2013_PORT",
            extra_env=environment)


def launch() -> int:
    from desktop_host import run_host
    return run_host({"ff7-2013": PLUGIN}, "ff7-2013")


def smoke() -> list[str]:
    source, relative = resolve_kernel(DEFAULT_ROOT)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7-2013-") as name:
        root = Path(name)
        game = root / "game"
        target = game / relative
        target.parent.mkdir(parents=True)
        shutil.copy2(source, target)
        (game / "ff7_en.exe").write_bytes(b"test")
        with FF7LegacySession({"LEXEDITOR_FF7_ROOT": str(game),
                "LEXEDITOR_FF7_DATA_ROOT": str(root / "data"),
                "LEXEDITOR_FF7_PROJECT": str(root / "project")}) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "ff7-2013":
                raise RuntimeError("The legacy FF7 product returned the wrong identity")
            if identity.get("capabilities") != ["data-map", "kernel-data", "save"]:
                raise RuntimeError("The legacy FF7 product did not expose the proved editor capabilities")
            data = request_json(session.url + "api/data")
            expected_counts = {"items": 128, "weapons": 128, "armor": 32, "accessories": 32, "materia": 96}
            if {key: len(data["records"][key]) for key in expected_counts} != expected_counts:
                raise RuntimeError("The legacy FF7 product did not decode the proved kernel records")
            original = data["records"]["armor"][0]["values"]["defense"]
            changed = original + 1 if original < 255 else original - 1
            data["records"]["armor"][0]["values"]["defense"] = changed
            request = urllib.request.Request(session.url + "api/save",
                data=json.dumps(kernel_save_payload(data)).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=10) as response:
                saved = json.loads(response.read().decode("utf-8"))
            saved_path = Path(saved["path"])
            if not saved_path.is_file() or Kernel(saved_path).records("armor")[0]["values"]["defense"] != changed:
                raise RuntimeError("The legacy FF7 project save did not survive binary readback")
        if not session.wait_closed():
            raise RuntimeError("The legacy FF7 child service stayed open")
    return [
        "legacy FF7 product identity and editor capabilities confirmed",
        "416 English KERNEL.BIN records decoded",
        "bounded armor edit saved to the legacy project and survived binary readback",
    ]


PLUGIN = GamePlugin(
    plugin_id="ff7-2013",
    name="Final Fantasy 7 (Remaster)",
    subtitle="FFVII 2013",
    description="Edits character, battle, encounter, shop and text data for the 2013 Steam product.",
    accent="#3155b7",
    cover_art=LEXEDITOR_ROOT / "assets" / "covers" / "ff7-remaster.png",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=FF7LegacySession,
    process_names=("ff7_en.exe", "ff7.exe", "FF7_Launcher.exe"),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_FF7_2013_PROJECT",
        default_root=DEFAULT_PROJECT,
        required_paths=(PROJECT_KERNEL_PATH.as_posix(),),
        template_root=PROJECT_TEMPLATE,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_FF7_2013_ROOT",
        data_env="LEXEDITOR_FF7_2013_DATA_ROOT",
        required_paths=("ff7_en.exe", "data/lang-en/kernel/KERNEL.BIN"),
        steam_app_id="39140",
        install_dir_names=("FINAL FANTASY VII",),
        default_roots=(DEFAULT_ROOT, Path(r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY VII")),
        prepare=prepare,
    ),
)
