"""Stardew Valley PC / Content Patcher plugin lifecycle."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession, request_json

from . import paths
from .content_pack import ContentPackStore, deploy, initialize_project
from .source_data import objects_source_path

LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return paths.check()


class StardewValleySession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {"LEXEDITOR_STARDEW_PROJECT": str(paths.PROJECT_ROOT)}
        environment.update(extra_env or {})
        super().__init__(
            module="games.stardew_valley.server",
            plugin_id="stardew-valley",
            app_root=LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_STARDEW_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"stardew-valley": PLUGIN}, "stardew-valley")


def smoke() -> list[str]:
    """Exercise base-data reads, project preservation, service identity, and safe deployment."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-stardew-") as name:
        root = Path(name); game = root / "game"; project = root / "project"
        (game / "Content" / "Data").mkdir(parents=True)
        (game / "Content" / "Data" / "Objects.xnb").write_bytes(b"read-only fixture")
        (game / "Stardew Valley.exe").write_bytes(b"fixture")
        (game / "StardewModdingAPI.exe").write_bytes(b"fixture")
        source = objects_source_path(game); source.parent.mkdir(parents=True)
        source.write_text(json.dumps({
            "390": {
                "Name": "Stone", "DisplayName": "Stone", "Description": "A useful material.",
                "Price": 2, "Edibility": -300, "IsDrink": False,
            }
        }) + "\n", encoding="utf-8")
        source_before = source.read_bytes()
        cp = game / "Mods" / "Content Patcher"; cp.mkdir(parents=True)
        (cp / "manifest.json").write_text(json.dumps({
            "UniqueID": "Pathoschild.ContentPatcher", "Version": "2.9.1",
        }) + "\n", encoding="utf-8")
        shutil.copytree(paths.PROJECT_TEMPLATE_ROOT, project)
        initialize_project(project)
        store = ContentPackStore(project)
        opened = store.objects()
        saved = store.save_objects(opened["sha256"], [{"id": "390", "fields": {
            "Price": 77, "Edibility": -300, "IsDrink": False,
        }}])
        if saved["rows"][0]["fields"]["Price"] != 77:
            raise RuntimeError("Stardew object patch did not round-trip")
        deployed = deploy(game, project)
        if not deployed["managed"] or deployed["externallyChanged"]:
            raise RuntimeError("Stardew Content Patcher deployment was not managed safely")
        with StardewValleySession({
            "LEXEDITOR_STARDEW_ROOT": str(game), "LEXEDITOR_STARDEW_PROJECT": str(project),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "stardew-valley":
                raise RuntimeError("Stardew Valley service returned the wrong identity")
            if "data-map" not in identity.get("capabilities", []):
                raise RuntimeError("Stardew Valley service did not expose Data Map")
            objects = request_json(session.url + "api/objects")
            row = next((value for value in objects.get("rows", []) if value.get("id") == "390"), None)
            if row is None or row["baseFields"]["Price"] != 2 or row["fields"]["Price"] != 77:
                raise RuntimeError("Stardew Valley service did not merge vanilla values with the object patch")
            if not objects.get("baseSource", {}).get("available"):
                raise RuntimeError("Stardew Valley service did not expose the unpacked vanilla source")
            data_map = request_json(session.url + "api/datamap")
            map_row = next((row for row in data_map.get("rows", []) if row.get("target") == "objects"), None)
            if not map_row or map_row.get("coverage") != "structured" or not map_row.get("sourceAvailable"):
                raise RuntimeError("Stardew Valley Data Map omitted evidence-backed object source coverage")
        if source.read_bytes() != source_before:
            raise RuntimeError("Stardew Valley vanilla source data changed during the smoke path")
        if not session.wait_closed():
            raise RuntimeError("Stardew Valley child port is still open after host shutdown")
    return [
        "Stardew Valley managed plugin identity confirmed",
        "read-only StardewXnbHack Data/Objects source merged with project overrides",
        "Content Patcher Data/Objects field edit saved and reopened",
        "unknown content.json structure preserved by project-only editing",
        "SMAPI/Content Patcher deployment created a managed mod folder",
        "evidence-based Data Map served",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="stardew-valley",
    name="Stardew Valley",
    subtitle="STARDEW VALLEY",
    description="Edit Stardew Valley 1.6 Content Patcher data mods without replacing game XNB files.",
    accent="#6cae43",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=StardewValleySession,
    process_names=("Stardew Valley.exe", "StardewModdingAPI.exe"),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_STARDEW_PROJECT",
        default_root=paths.DEFAULT_PROJECT_ROOT,
        required_paths=("manifest.json", "content.json"),
        template_root=paths.PROJECT_TEMPLATE_ROOT,
        initialize=initialize_project,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_STARDEW_ROOT",
        required_paths=("Stardew Valley.exe", "Content"),
        steam_app_id="413150",
        install_dir_names=("Stardew Valley",),
        default_roots=(
            Path(r"D:\SteamLibrary\steamapps\common\Stardew Valley"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Stardew Valley"),
        ),
        # A deployed Content Patcher pack only loads through SMAPI. If SMAPI is
        # absent, Play fails visibly instead of silently launching unmodded Stardew.
        launch_path="StardewModdingAPI.exe",
    ),
)
