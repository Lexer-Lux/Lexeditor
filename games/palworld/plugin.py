"""Palworld official mod-package plugin lifecycle."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from runtime_bootstrap import user_data_dir
from service_session import LocalPluginSession, request_json

from .package import default_info


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
DEFAULT_PROJECT = user_data_dir() / "projects" / "palworld"
DISPLAY_NAME = "Palworld"


def check() -> list[str]:
    # GameInstallSpec validates the selected installation. The first slice has
    # no mandatory third-party runtime/helper of its own.
    return []


class PalworldSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {"LEXEDITOR_PALWORLD_PROJECT": str(DEFAULT_PROJECT)}
        environment.update(extra_env or {})
        super().__init__(
            module="games.palworld.server",
            plugin_id="palworld",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_PALWORLD_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"palworld": PLUGIN}, "palworld")


def smoke() -> list[str]:
    """Exercise the real managed service without touching an installed game."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-palworld-") as temp_name:
        temp = Path(temp_name)
        game = temp / "Palworld"
        (game / "Pal" / "Content" / "Paks").mkdir(parents=True)
        (game / "Palworld.exe").write_bytes(b"")

        project = temp / "project"
        project.mkdir()
        fixture = default_info("LexeditorSmoke")
        fixture["FuturePocketpairField"] = {"preserve": True}
        (project / "Info.json").write_text(
            json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with PalworldSession({
            "LEXEDITOR_PALWORLD_ROOT": str(game),
            "LEXEDITOR_PALWORLD_PROJECT": str(project),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "palworld" or identity.get("hosted") is not True:
                raise RuntimeError("Palworld service returned the wrong managed identity")
            if "official-package-info" not in identity.get("capabilities", []):
                raise RuntimeError("Palworld service did not advertise package metadata editing")

            info = request_json(session.url + "api/info")
            if info.get("data", {}).get("PackageName") != "LexeditorSmoke":
                raise RuntimeError("Palworld service did not read the selected project Info.json")
            result = request_json(session.url + "api/info/save", {
                "sourceSha256": info["sourceSha256"],
                "changes": {"Version": "0.2.0", "DebugMode": False},
            })
            if result.get("data", {}).get("Version") != "0.2.0":
                raise RuntimeError("Palworld service edit did not survive readback")
            reread = request_json(session.url + "api/info")
            if reread.get("data", {}).get("FuturePocketpairField") != {"preserve": True}:
                raise RuntimeError("Palworld service did not preserve an unknown Info.json field")
            if not (project / "Info.json.lexeditor.bak").is_file():
                raise RuntimeError("Palworld service changed Info.json without creating a backup")

        if not session.wait_closed():
            raise RuntimeError("Palworld child port is still open after host shutdown")

    return [
        "managed Palworld service identified the selected package project",
        "official Info.json edit survived save/readback",
        "unknown future package metadata survived the structured edit",
        "changed Info.json write created a backup",
        "host-owned Palworld child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="palworld",
    name=DISPLAY_NAME,
    subtitle="Official mod packages",
    description="Create and edit Palworld v0.7+ official mod-package metadata while keeping installed game data read-only.",
    accent="#55c7d9",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=PalworldSession,
    process_names=("Palworld.exe", "Palworld-Win64-Shipping.exe"),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_PALWORLD_PROJECT",
        default_root=DEFAULT_PROJECT,
        required_paths=("Info.json",),
        template_root=PLUGIN_ROOT / "template",
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_PALWORLD_ROOT",
        required_paths=("Palworld.exe", "Pal/Content/Paks"),
        steam_app_id="1623730",
        install_dir_names=("Palworld",),
        default_roots=(Path(r"C:\Program Files (x86)\Steam\steamapps\common\Palworld"),),
        launch_path="Palworld.exe",
    ),
)
