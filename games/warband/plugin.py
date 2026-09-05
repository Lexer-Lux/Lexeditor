"""Warband plugin lifecycle for the shared Lexeditor host."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
import urllib.parse
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, GitHubRepository, ModProjectSpec
from service_session import LocalPluginSession, request_json

from . import paths


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent


def check() -> list[str]:
    return paths.check()


class WarbandSession(LocalPluginSession):
    """One host-owned Warband editor service."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {"LEXEDITOR_MOD_PROJECT": paths.MOD_PROJECT}
        environment.update(extra_env or {})
        super().__init__(
            module="games.warband.server",
            plugin_id="warband",
            app_root=LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_WARBAND_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"warband": PLUGIN}, "warband")


def smoke() -> list[str]:
    """Exercise the Warband service and a temporary settings save."""
    live_settings = Path(paths.MOD_SETTINGS)
    if not live_settings.is_file():
        raise RuntimeError(f"Missing Warband settings: {live_settings}")
    live_hash = hashlib.sha256(live_settings.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="lexeditor-warband-") as temp_name:
        test_settings = Path(temp_name) / "settings.ini"
        shutil.copy2(live_settings, test_settings)
        with WarbandSession({"LEXEDITOR_WARBAND_SETTINGS": str(test_settings)}) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("windowHost") != "webview2":
                raise RuntimeError("Warband plugin did not report the shared WebView2 host")
            if Path(identity["editorRoot"]).resolve() != PLUGIN_ROOT:
                raise RuntimeError("Warband service did not run from its Lexeditor plugin")
            with urllib.request.urlopen(session.url, timeout=10) as response:
                html = response.read().decode("utf-8")
            if ('id="lexeditor-shell"' not in html or
                    '/shared/framework.js' not in html or
                    "Lexeditor - Warband" not in html):
                raise RuntimeError("Warband plugin did not serve the shared editor interface")
            settings = request_json(session.url + "api/settings")
            rows = settings.get("rows", [])
            if not rows:
                raise RuntimeError("Warband settings API returned no editable settings")
            target = rows[0]
            new_value = "0" if target["value"] != "0" else "1"
            result = request_json(session.url + "api/settings/save", {
                "edits": [{"line": target["line"], "value": new_value}]
            })
            if result.get("saved") != 1:
                raise RuntimeError("Warband settings save did not update one temporary value")
            reread = request_json(session.url + "api/settings")
            saved = next(row["value"] for row in reread["rows"] if row["line"] == target["line"])
            if saved != new_value:
                raise RuntimeError("Warband settings save did not read back")
            for endpoint, key in (("api/items", "rows"), ("api/troops", "rows"),
                                  ("api/upgrades", "rows"), ("api/catalog", "areas")):
                if key not in request_json(session.url + endpoint):
                    raise RuntimeError(f"Warband {endpoint} API did not return {key}")
            items = request_json(session.url + "api/items").get("rows", [])
            preview_item = next((row for row in items if row.get("id") == "tutorial_axe"), None)
            if not preview_item:
                raise RuntimeError("Warband items did not expose an inventory mesh")
            preview = request_json(
                session.url + "api/item-preview?mesh="
                + urllib.parse.quote(preview_item["inventoryMesh"])
            )
            if preview.get("summary", {}).get("triangles", 0) < 1 or not preview.get("geometry"):
                raise RuntimeError("Warband item preview did not return real BRF geometry")
            font = request_json(session.url + "api/warband-font")
            if not font.get("available") or not font.get("characters"):
                raise RuntimeError("Warband did not expose its installed bitmap font")
            data_map = request_json(session.url + "api/datamap")
            partial = {row["filename"] for row in data_map.get("rows", []) if row.get("status") == "partial"}
            if {"Resource/*.brf", "Textures/*.dds"} - partial:
                raise RuntimeError("Warband data map did not report read-only preview integration")
        if not session.process or session.process.poll() is None:
            raise RuntimeError("Warband child service still runs after host shutdown")
        if not session.wait_closed():
            raise RuntimeError("Warband child port is still open after host shutdown")
    if hashlib.sha256(live_settings.read_bytes()).hexdigest() != live_hash:
        raise RuntimeError("Warband smoke test changed the live settings file")
    return [
        "Warband plugin identity and WebView2 host confirmed",
        "shared Warband interface and data APIs served",
        "temporary Warband setting saved and read back",
        "native Warband item mesh and bitmap font read successfully",
        "BRF and DDS preview coverage reported as partial integration",
        "live Warband settings remained unchanged",
        "host-owned child service stopped cleanly",
    ]


def installed_modules() -> list[Path]:
    """Every module installed in the game, so all of them can be selected."""
    modules = Path(paths.MODULES_DIR)
    if not modules.is_dir():
        return []
    return sorted(entry for entry in modules.iterdir()
                  if entry.is_dir() and (entry / "module.ini").is_file())


PLUGIN = GamePlugin(
    plugin_id="warband",
    name="Mount & Blade: Warband",
    subtitle="WARBAND",
    description="Edit module data, settings, troops, manuals, and builds.",
    accent="#7a2020",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=WarbandSession,
    github=GitHubRepository(
        full_name="Lexer-Lux/LexersModForWarband",
        authorized_logins=("Lexer-Lux",),
    ),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_MOD_PROJECT",
        default_root=Path(paths.MOD_PROJECT),
        required_paths=("ModuleSystem/module_items.py", "settings.ini", "build.bat"),
        # Two editable shapes: a Module System source project, or any module
        # installed in the game. module.ini is what makes a folder a module.
        required_any=(
            ("ModuleSystem/module_items.py", "settings.ini", "build.bat"),
            ("module.ini",),
        ),
        discover=installed_modules,
        template_root=Path(paths.MOD_PROJECT),
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_WARBAND_ROOT",
        required_paths=("mb_warband.exe", "Modules"),
        steam_app_id="48700",
        install_dir_names=("MountBlade Warband", "Mount & Blade Warband"),
        default_roots=(Path(
            r"C:\Program Files (x86)\Steam\steamapps\common\MountBlade Warband"
        ),),
    ),
)
