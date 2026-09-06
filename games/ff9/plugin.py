"""Final Fantasy IX Steam/Memoria plugin lifecycle."""

from __future__ import annotations

import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession, request_json

from . import memoria_manager, paths


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return paths.check()


class FF9Session(LocalPluginSession):
    """One host-owned FF9 scaffold service."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {
            "LEXEDITOR_FF9_ROOT": str(paths.GAME_ROOT),
            "LEXEDITOR_FF9_DATA_ROOT": str(paths.DATA_ROOT),
            "LEXEDITOR_FF9_PROJECT": str(paths.PROJECT_ROOT),
        }
        environment.update(extra_env or {})
        super().__init__(
            module="games.ff9.server",
            plugin_id="ff9",
            app_root=LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_FF9_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"ff9": PLUGIN}, "ff9")


def smoke() -> list[str]:
    """Exercise real Memoria CSV read and project-overlay save behavior."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff9-plugin-") as temp_name:
        root = Path(temp_name)
        game = root / "game"
        for relative in (
            "FF9_Launcher.exe", "x64/FF9.exe",
            "x64/FF9_Data/Managed/Assembly-CSharp.dll", "StreamingAssets/p0data2.bin",
        ):
            target = game / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture")
        items = game / "StreamingAssets" / "Data" / "Items" / "Items.csv"
        items.parent.mkdir(parents=True, exist_ok=True)
        items.write_text(
            "# Id;Price;Usable\n# Int32;UInt32;Bit\n0;250;1;# 000 - Hammer\n",
            encoding="utf-8",
        )
        with FF9Session({
            "LEXEDITOR_FF9_ROOT": str(game),
            "LEXEDITOR_FF9_DATA_ROOT": str(root / "data"),
            "LEXEDITOR_FF9_PROJECT": str(root / "project"),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "ff9" or identity.get("windowHost") != "webview2":
                raise RuntimeError("FF9 plugin returned the wrong managed identity")
            if identity.get("capabilities") != ["data-map", "memoria-csv", "read", "save"]:
                raise RuntimeError("FF9 plugin advertised the wrong capabilities")
            data_map = request_json(session.url + "api/datamap")
            rows = data_map.get("rows", [])
            if not rows or not any(row.get("status") == "integrated" for row in rows):
                raise RuntimeError("FF9 Data Map did not report its available Memoria dataset")
            dataset = request_json(session.url + "api/dataset?key=items")
            if dataset["rows"][0]["values"]["Price"] != 250:
                raise RuntimeError("FF9 Memoria CSV did not load its stored price")
            saved = request_json(session.url + "api/save", {
                "key": "items", "sha256": dataset["sha256"],
                "changes": [{"line": dataset["rows"][0]["line"], "values": {"Price": 300}}],
            })
            if saved["rows"][0]["values"]["Price"] != 300 or saved["source"] != "project":
                raise RuntimeError("FF9 Memoria project overlay did not save and reload")
            if "0;300;1;# 000 - Hammer" not in (root / "project" / "StreamingAssets" / "Data" / "Items" / "Items.csv").read_text(encoding="utf-8"):
                raise RuntimeError("FF9 project overlay did not preserve the CSV record")
            # A single 10s attempt fails whenever the machine is busy - the
            # local server is simply still starting - and reports it as a
            # timeout, which reads like a broken plugin rather than a slow
            # host. Retry to a deadline instead, and re-raise the real error
            # if the whole window passes.
            deadline = time.monotonic() + 60
            while True:
                try:
                    with urllib.request.urlopen(session.url, timeout=10) as response:
                        html = response.read().decode("utf-8")
                    break
                except (urllib.error.URLError, TimeoutError, OSError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.5)
            if ('id="lexeditor-shell"' not in html or '/shared/framework.js' not in html
                    or "Lexeditor - Final Fantasy 9" not in html):
                raise RuntimeError("FF9 plugin did not serve the shared editor shell")
        if not session.wait_closed():
            raise RuntimeError("FF9 child port is still open after host shutdown")
    return [
        "FF9 managed plugin identity and Unity layout confirmed",
        "Memoria CSV schema and record loaded",
        "bounded field edit saved to a project overlay and reloaded",
        "shared editor shell and evidence-based Data Map served",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="ff9",
    name="Final Fantasy 9",
    process_names=("FF9.exe", "FF9_Launcher.exe"),
    helper_name="Memoria",
    helper_install=lambda: memoria_manager.install(paths.GAME_ROOT),
    helper_status=lambda: memoria_manager.status(paths.GAME_ROOT),
    helper_upstream=memoria_manager.upstream_release,
    subtitle="FFIX",
    description="Steam editor for proved Memoria and Hades Workshop CSV exports.",
    accent="#6e54b5",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=FF9Session,
    projects=ModProjectSpec(
        root_env="LEXEDITOR_FF9_PROJECT",
        default_root=paths.DEFAULT_PROJECT_ROOT,
        required_paths=("StreamingAssets/Data",),
        template_root=paths.PROJECT_TEMPLATE_ROOT,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_FF9_ROOT",
        data_env="LEXEDITOR_FF9_DATA_ROOT",
        required_paths=("FF9_Launcher.exe", "x64/FF9.exe", "StreamingAssets/p0data2.bin"),
        # #73: use Memoria's existing settings UI on every Play, rather than
        # recreating it in Lexeditor or bypassing it with the game executable.
        launch_path="FF9_Launcher.exe",
        steam_app_id="377840",
        install_dir_names=("FINAL FANTASY IX",),
        default_roots=(
            Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY IX"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY IX"),
        ),
    ),
)
