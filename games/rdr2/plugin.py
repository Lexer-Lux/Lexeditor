"""RDR2 plugin lifecycle for the Lexeditor desktop shell.

Lexeditor owns this plugin's service, interface, parsers, schemas, assets,
process lifecycle, desktop window, and checks. The selected RDR2 project
supplies only editable mod data and game-specific reference sources.
"""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, GitHubRepository, ModProjectSpec, PluginFont
from service_session import LocalPluginSession, request_json
from .extractor import ensure_rdr2_data
from .paths import EDITABLE_MOD_ROOT, LEXEDITOR_ROOT, PLUGIN_ROOT, PROJECT_ROOT, check as check_paths


def project_root() -> Path:
    return PROJECT_ROOT


def server_path() -> Path:
    return PLUGIN_ROOT / "server.py"


def check() -> list[str]:
    return check_paths()


class Rdr2Session(LocalPluginSession):
    """One host-owned RDR2 editor service."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {"LEXEDITOR_RDR2_PROJECT": str(project_root())}
        environment.update(extra_env or {})
        super().__init__(
            module="games.rdr2.server",
            plugin_id="rdr2",
            app_root=LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_RDR2_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"rdr2": PLUGIN}, "rdr2")


def smoke() -> list[str]:
    """Exercise the host boundary and a safe settings save/readback."""
    project = project_root()
    live_ini = project / "GameplayTweaks" / "GameplayTweaks.ini"
    if not live_ini.is_file():
        raise RuntimeError(f"Missing GameplayTweaks INI: {live_ini}")
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr2-") as temp_name:
        temp = Path(temp_name)
        test_ini = temp / "GameplayTweaks.ini"
        shutil.copy2(live_ini, test_ini)
        with Rdr2Session({
            "LEXEDITOR_GAMEPLAY_INI": str(test_ini),
            "RDR2_GAME_ROOT": str(temp / "empty-game-root"),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if Path(identity["projectRoot"]).resolve() != project:
                raise RuntimeError("RDR2 plugin reported the wrong project root")
            if Path(identity["editorRoot"]).resolve() != PLUGIN_ROOT:
                raise RuntimeError("RDR2 service did not run from the Lexeditor plugin")
            with urllib.request.urlopen(session.url, timeout=10) as response:
                html = response.read().decode("utf-8")
            if ('id="lexeditor-shell"' not in html or
                    '/shared/framework.js' not in html or
                    "Lexeditor - RDR2" not in html):
                raise RuntimeError("RDR2 plugin did not serve the real editor interface")
            config = request_json(session.url + "api/config")
            if "mine" not in config.get("datasets", {}):
                raise RuntimeError("RDR2 plugin did not expose its editable dataset")
            settings = request_json(session.url + "api/settings")
            target = next(
                (row for section in settings.get("sections", [])
                 if section.get("name") == "Minimap"
                 for row in section.get("settings", []) if row.get("key") == "Enabled"),
                None,
            )
            if target is None:
                raise RuntimeError("RDR2 settings API did not expose Minimap/Enabled")
            new_value = "0" if target["value"] != "0" else "1"
            result = request_json(session.url + "api/settings/save", {
                "edits": [{"section": "Minimap", "key": "Enabled", "value": new_value}]
            })
            if result.get("saved") != 1:
                raise RuntimeError("RDR2 settings save did not update one temporary value")
            reread = request_json(session.url + "api/settings")
            saved = next(
                row["value"] for section in reread["sections"]
                if section["name"] == "Minimap"
                for row in section["settings"] if row["key"] == "Enabled"
            )
            if saved != new_value:
                raise RuntimeError("RDR2 settings save did not read back")
        if not session.process or session.process.poll() is None:
            raise RuntimeError("RDR2 child service still runs after host shutdown")
        if not session.wait_closed():
            raise RuntimeError("RDR2 child port is still open after host shutdown")
    return [
        "RDR2 plugin identity confirmed",
        "Lexeditor-owned RDR2 implementation root confirmed",
        "real RDR2 interface and dataset configuration served",
        "temporary GameplayTweaks setting saved and read back",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="rdr2",
    name="Red Dead Redemption 2",
    subtitle="RDR2",
    description="Edit overhaul data, gameplay settings, shops, loot, weapons, AI, and more.",
    accent="#a92b20",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=Rdr2Session,
    github=GitHubRepository(
        full_name="Lexer-Lux/rdr2-overhaul",
        authorized_logins=("Lexer-Lux",),
    ),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_MOD_ROOT",
        default_root=EDITABLE_MOD_ROOT,
        required_paths=("install.xml",),
        template_root=EDITABLE_MOD_ROOT,
    ),
    installation=GameInstallSpec(
        root_env="RDR2_GAME_ROOT",
        data_env="LEXEDITOR_RDR2_EXTRACT_ROOT",
        required_paths=(
            "RDR2.exe", "common_0.rpf", "update_1.rpf", "update_3.rpf", "update_4.rpf",
        ),
        steam_app_id="1174180",
        install_dir_names=("Red Dead Redemption 2",),
        default_roots=(Path(
            r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"
        ),),
        prepare=ensure_rdr2_data,
        prepare_on_scan=True,
    ),
    fonts=(
        PluginFont(
            font_id="redemption",
            name="Redemption",
            destination=PLUGIN_ROOT / "assets" / "fonts" / "Redemption.woff",
            source_url="https://media-rockstargames-com.akamaized.net/mfe6/prod/__common/fonts/d83fe1be4c1e7239c409db49a3850103.woff",
            sha256="a2e7903be5ebbad46801787c5dcb5964603ea4123aca0543786ae640c412fc3e",
            file_format="woff",
            alternatives=(PLUGIN_ROOT / "assets" / "fonts" / "Redemption.ttf",),
        ),
        PluginFont(
            font_id="rdr-lino",
            name="RDR Lino",
            destination=PLUGIN_ROOT / "assets" / "fonts" / "RDRLino-Regular.rockstar.woff2",
            source_url="https://media-rockstargames-com.akamaized.net/mfe6/prod/__common/fonts/593253ebb2f8260c4005859f87ed4ca3.woff2",
            sha256="70ee112972cd7687782551044f872b10b1b787879dcb56b531c5e8977493fc08",
            file_format="woff2",
            alternatives=(PLUGIN_ROOT / "assets" / "fonts" / "RDRLino-Regular.woff2",),
        ),
    ),
)
