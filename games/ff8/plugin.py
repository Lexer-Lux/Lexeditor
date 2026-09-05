"""Final Fantasy VIII plugin lifecycle for the shared Lexeditor host."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession, request_json

from . import ffnx_manager, gameplay_settings, paths
from .extractor import plugin_prepare


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent


def check() -> list[str]:
    return paths.check()


class FF8Session(LocalPluginSession):
    """One host-owned FF8 editor service."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        requested = dict(extra_env or {})
        self._test_roots: list[tempfile.TemporaryDirectory[str]] = []
        requested_project = Path(requested.get(
            "LEXEDITOR_FF8_PROJECT", str(paths.PROJECT_ROOT)
        )).resolve()
        # A temporary editor project must never compose into the player's live
        # runtime. Render and mutation checks routinely save their scratch mods;
        # give those sessions private runtime and managed-mod roots by default.
        if (requested_project != paths.PROJECT_ROOT.resolve()
                and "LEXEDITOR_FF8_RUNTIME_ROOT" not in requested):
            runtime = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-runtime-")
            mods = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-mods-")
            self._test_roots.extend((runtime, mods))
            requested["LEXEDITOR_FF8_RUNTIME_ROOT"] = runtime.name
            requested["LEXEDITOR_FF8_MODS_ROOT"] = mods.name
        environment = {
            "LEXEDITOR_FF8_ROOT": str(paths.GAME_ROOT),
            "LEXEDITOR_FF8_DATA_ROOT": str(paths.DATA_ROOT),
            "LEXEDITOR_FF8_PROJECT": str(paths.PROJECT_ROOT),
        }
        environment.update(requested)
        super().__init__(
            module="games.ff8.server",
            plugin_id="ff8",
            app_root=LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_FF8_PORT",
            extra_env=environment,
        )

    def stop(self) -> None:
        super().stop()
        while self._test_roots:
            self._test_roots.pop().cleanup()


def launch() -> int:
    from desktop_host import run_host
    return run_host({"ff8": PLUGIN}, "ff8")


def smoke() -> list[str]:
    """Exercise identity, data APIs, and a temporary item-price save."""
    baseline = paths.BASELINE_ROOT / "menu" / "price.bin"
    if not baseline.is_file():
        raise RuntimeError(f"Missing FF8 baseline: {baseline}")
    live_hash = hashlib.sha256(baseline.read_bytes()).hexdigest()
    kernel_baseline = paths.BASELINE_ROOT / "main" / "kernel.bin"
    kernel_hash = hashlib.sha256(kernel_baseline.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-project-") as temp_name:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": temp_name}) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("windowHost") != "webview2" or Path(identity["editorRoot"]).resolve() != PLUGIN_ROOT:
                raise RuntimeError("FF8 plugin did not report the shared WebView2 host")
            for endpoint, key in (("api/items", "rows"), ("api/shops", "rows"),
                                  ("api/weapons", "rows"), ("api/kernel?section=2", "rows"),
                                  ("api/kernel?section=3", "rows"), ("api/kernel?section=7", "rows"),
                                  ("api/text", "rows"),
                                  ("api/enemies", "rows"), ("api/init", "general"),
                                  ("api/datamap", "rows")):
                if not request_json(session.url + endpoint).get(key):
                    raise RuntimeError(f"FF8 {endpoint} returned no {key}")
            before = request_json(session.url + "api/items")["rows"][1]
            price = 20 if before["buyPrice"] != 20 else 30
            saved = request_json(session.url + "api/items/save", {
                "edits": [{"id": 1, "buyPrice": price,
                           "sellMultiplier": before["sellMultiplier"]}]
            })
            if saved.get("saved") != 1:
                raise RuntimeError("FF8 item save did not update one temporary record")
            after = request_json(session.url + "api/items")["rows"][1]
            if after["buyPrice"] != price:
                raise RuntimeError("FF8 item save did not read back")
            text_row = request_json(session.url + "api/text")["rows"][0]
            text_value = text_row["value"] + " TEST"
            text_saved = request_json(session.url + "api/text/save", {"edits": [{
                "sectionId": text_row["sectionId"], "recordId": text_row["recordId"],
                "slot": text_row["slot"], "value": text_value,
            }]})
            if text_saved.get("saved") != 1:
                raise RuntimeError("FF8 kernel text save did not update one temporary record")
            text_after = next(row for row in request_json(session.url + "api/text")["rows"]
                              if row["sectionId"] == text_row["sectionId"] and
                              row["recordId"] == text_row["recordId"] and
                              row["slot"] == text_row["slot"])
            if text_after["value"] != text_value:
                raise RuntimeError("FF8 kernel text save did not read back")
            enemy = request_json(session.url + "api/enemies")["rows"][1]
            scan_description = enemy["scanDescription"] + " TEST"
            scan_saved = request_json(session.url + "api/enemies/save", {
                "edits": [{"id": enemy["id"], "field": "scan_description",
                           "value": scan_description}]
            })
            if scan_saved.get("saved") != 1:
                raise RuntimeError("FF8 Scan save did not update one temporary record")
            scan_after = request_json(session.url + "api/enemies")["rows"][1]
            if scan_after["scanDescription"] != scan_description:
                raise RuntimeError("FF8 Scan description did not read back")
            starting = request_json(session.url + "api/init")
            gil_field = next(field for field in starting["general"]["fields"] if field["field"] == "gil")
            gil = 123456 if gil_field["value"] != 123456 else 123455
            init_saved = request_json(session.url + "api/init/save", {
                "edits": [{"kind": "general", "id": 0, "field": "gil", "value": gil}]
            })
            if init_saved.get("saved") != 1:
                raise RuntimeError("FF8 starting-data save did not update one temporary field")
            init_after = request_json(session.url + "api/init")
            if next(field for field in init_after["general"]["fields"]
                    if field["field"] == "gil")["value"] != gil:
                raise RuntimeError("FF8 starting-data save did not read back")
        if not session.wait_closed():
            raise RuntimeError("FF8 child port is still open after host shutdown")
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != live_hash:
        raise RuntimeError("FF8 smoke test changed the extracted baseline")
    if hashlib.sha256(kernel_baseline.read_bytes()).hexdigest() != kernel_hash:
        raise RuntimeError("FF8 text smoke test changed the extracted kernel baseline")
    return [
        "FF8 plugin identity and shared WebView2 host confirmed",
        "items, shops, weapons, magic, GFs, characters, kernel text, enemies, starting data, and Data Map APIs served",
        "temporary data, kernel text, starting data, and FFNx Scan overrides saved and read back",
        "private extracted baseline remained unchanged",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="ff8",
    name="Final Fantasy 8",
    process_names=("FF8_EN.exe", "FF8_Launcher.exe"),
    helper_name="FFNx",
    helper_install=lambda: ffnx_manager.ensure_ffnx(paths.GAME_ROOT, paths.RUNTIME_DIRECT_ROOT),
    helper_status=lambda: ffnx_manager.status(paths.GAME_ROOT),
    helper_upstream=ffnx_manager.upstream_release,
    subtitle="FFVIII",
    description="Edit gameplay data for the original 2013 Steam release.",
    accent="#366bc2",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=FF8Session,
    projects=ModProjectSpec(
        root_env="LEXEDITOR_FF8_PROJECT",
        default_root=paths.PROJECT_ROOT,
        required_paths=("direct",),
        template_root=paths.PROJECT_ROOT,
        initialize=gameplay_settings.initialize_project,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_FF8_ROOT",
        data_env="LEXEDITOR_FF8_DATA_ROOT",
        required_paths=(
            "FF8_EN.exe",
            "Data/lang-en/main.fs", "Data/lang-en/main.fi", "Data/lang-en/main.fl",
            "Data/lang-en/menu.fs", "Data/lang-en/menu.fi", "Data/lang-en/menu.fl",
            "Data/lang-en/battle.fs", "Data/lang-en/battle.fi", "Data/lang-en/battle.fl",
            "Data/lang-en/world.fs", "Data/lang-en/world.fi", "Data/lang-en/world.fl",
        ),
        # FF8_Launcher.exe draws the seizure/health warning with the language
        # picker on EVERY start - the string lives in the launcher and NOT in
        # FF8_EN.exe, so nothing inside the game can suppress it. Starting the
        # game directly skips it. That already happened by accident, because
        # the host falls back to the first .exe in required_paths, but naming
        # it means reordering that list cannot silently reintroduce the
        # launcher.
        launch_path="FF8_EN.exe",
        steam_app_id="39150",
        install_dir_names=("FINAL FANTASY VIII",),
        default_roots=(
            Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY VIII"),
        ),
        prepare=plugin_prepare,
    ),
)
