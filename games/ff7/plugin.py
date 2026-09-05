"""Final Fantasy VII plugin lifecycle for the shared Lexeditor host."""

from __future__ import annotations

import tempfile
import json
import shutil
import urllib.request
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession, request_json

from . import paths
from .kernel import Kernel, resolve_kernel


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent


def check() -> list[str]:
    return paths.check()


def seed_project_layout(game_root: Path, template_root: Path,
                        default_root: Path) -> dict:
    """Seed safe editable projects from the installed product's proved kernel."""
    source, relative = resolve_kernel(game_root)
    expected = relative.as_posix().casefold()
    supported = {
        "ff7/workingdir/data/lang-en/kernel/kernel.bin",
        "data/lang-en/kernel/kernel.bin",
    }
    if expected not in supported:
        raise RuntimeError(f"Unsupported FF7 project kernel path: {relative}")

    template_kernel = template_root / relative
    template_kernel.parent.mkdir(parents=True, exist_ok=True)
    temporary = template_kernel.with_suffix(template_kernel.suffix + ".tmp")
    shutil.copy2(source, temporary)
    Kernel(temporary)
    temporary.replace(template_kernel)
    readme = template_root / "README.txt"
    readme.write_text(
        "Final Fantasy VII Lexeditor mod project\n\n"
        "Lexeditor edits this project's English KERNEL.BIN copy. "
        "The installed game remains unchanged.\n",
        encoding="utf-8",
    )

    default_kernel = default_root / relative
    if not default_kernel.is_file():
        default_kernel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_kernel, default_kernel)
    Kernel(default_kernel)
    return {
        "template": str(template_root),
        "defaultProject": str(default_root),
        "relativePath": relative.as_posix(),
    }


def prepare_product(game_root: Path, data_root: Path, progress,
                    template_root: Path, default_root: Path) -> dict:
    """Prepare proved theme sounds and an editable baseline project."""
    from theme_sounds import ensure_theme_sounds
    progress(0, 2, "Preparing the Final Fantasy VII mod template")
    project = seed_project_layout(game_root, template_root, default_root)
    progress(1, 2, "Preparing Final Fantasy VII interface sounds")
    result = ensure_theme_sounds(game_root, data_root,
        ("data/sound", "ff7/workingdir/data/sound"), {
            "confirm": 1, "move": 1, "back": 4, "exit": 4,
            "save": 2, "launch": None,
        }, format_kind="ff7")
    progress(2, 2, "Final Fantasy VII editor data is ready")
    return {"themeSounds": result, "project": project}


def prepare(game_root: Path, data_root: Path, progress) -> dict:
    return prepare_product(
        game_root, data_root, progress,
        paths.PROJECT_TEMPLATE_ROOT, paths.PROJECT_ROOT,
    )


class FF7Session(LocalPluginSession):
    """One host-owned FF7 editor service."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {
            "LEXEDITOR_FF7_ROOT": str(paths.GAME_ROOT),
            "LEXEDITOR_FF7_DATA_ROOT": str(paths.DATA_ROOT),
            "LEXEDITOR_FF7_PROJECT": str(paths.PROJECT_ROOT),
        }
        environment.update(extra_env or {})
        super().__init__(
            module="games.ff7.server",
            plugin_id="ff7",
            app_root=LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_FF7_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"ff7": PLUGIN}, "ff7")


def smoke() -> list[str]:
    """Read, edit, save, and read back one installed FF7 kernel record."""
    source, relative = resolve_kernel(paths.GAME_ROOT)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7-kernel-") as temp_name:
        root = Path(temp_name)
        game = root / "game"
        target = game / relative
        target.parent.mkdir(parents=True)
        shutil.copy2(source, target)
        (game / "FFVII_LAUNCHER.exe").write_bytes(b"test")
        with FF7Session({
            "LEXEDITOR_FF7_ROOT": str(game),
            "LEXEDITOR_FF7_DATA_ROOT": str(root / "data"),
            "LEXEDITOR_FF7_PROJECT": str(root / "project"),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "ff7" or identity.get("windowHost") != "webview2":
                raise RuntimeError("FF7 editor returned the wrong managed identity")
            if identity.get("capabilities") != ["data-map", "kernel-data", "save"]:
                raise RuntimeError("FF7 editor did not advertise its proved capabilities")
            data_map = request_json(session.url + "api/datamap")
            rows = data_map.get("rows", [])
            if len([row for row in rows if row.get("status") == "integrated"]) != 5:
                raise RuntimeError("FF7 Data Map did not expose the five integrated kernel sections")
            data = request_json(session.url + "api/data")
            expected_counts = {"items": 128, "weapons": 128, "armor": 32, "accessories": 32, "materia": 96}
            if {key: len(data["records"][key]) for key in expected_counts} != expected_counts:
                raise RuntimeError("FF7 kernel record counts did not match the installed English data")
            original = data["records"]["weapons"][0]["values"]["attackStrength"]
            changed = original + 1 if original < 255 else original - 1
            data["records"]["weapons"][0]["values"]["attackStrength"] = changed
            request = urllib.request.Request(session.url + "api/save",
                data=json.dumps({"records": data["records"]}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=10) as response:
                saved = json.loads(response.read().decode("utf-8"))
            saved_path = Path(saved["path"])
            if not saved_path.is_file() or Kernel(saved_path).records("weapons")[0]["values"]["attackStrength"] != changed:
                raise RuntimeError("FF7 project save did not survive binary readback")
            with urllib.request.urlopen(session.url, timeout=10) as response:
                html = response.read().decode("utf-8")
            if ('id="lexeditor-shell"' not in html or '/shared/framework.js' not in html
                    or "Lexeditor - Final Fantasy 7 (Original)" not in html):
                raise RuntimeError("FF7 editor did not serve the shared editor shell")
        if not session.wait_closed():
            raise RuntimeError("FF7 child port is still open after host shutdown")
    return [
        "FF7 managed plugin identity and five kernel sections confirmed",
        "416 installed English records decoded with their names",
        "bounded weapon edit saved to the project and survived binary readback",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="ff7",
    name="Final Fantasy 7 (Original)",
    subtitle="FFVII",
    description="Edits the proved item, equipment, and materia sections of the current Steam release.",
    accent="#3155b7",
    cover_art=LEXEDITOR_ROOT / "assets" / "covers" / "ff7-original.png",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=FF7Session,
    projects=ModProjectSpec(
        root_env="LEXEDITOR_FF7_PROJECT",
        default_root=paths.PROJECT_ROOT,
        required_paths=(paths.PROJECT_KERNEL_PATH.as_posix(),),
        template_root=paths.PROJECT_TEMPLATE_ROOT,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_FF7_ROOT",
        data_env="LEXEDITOR_FF7_DATA_ROOT",
        required_paths=(
            "FFVII_LAUNCHER.exe",
            "ff7/workingdir/data/lang-en/kernel/kernel.bin",
        ),
        steam_app_id="3837340",
        install_dir_names=("FINAL FANTASY VII Steam Edition",),
        default_roots=(
            Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VII Steam Edition"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY VII Steam Edition"),
        ),
        prepare=prepare,
    ),
)
