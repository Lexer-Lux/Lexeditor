"""Final Fantasy X/X-2 HD Remaster Steam collection plugin lifecycle."""
from __future__ import annotations

import hashlib
import struct
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
import zlib

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession, request_json

from . import paths
from .vbf import BLOCK_SIZE


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return paths.check()


def _initialize_project(root: Path) -> None:
    paths.ensure_project(root)


class FFXX2Session(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {
            "LEXEDITOR_FFX_X2_ROOT": str(paths.GAME_ROOT),
            "LEXEDITOR_FFX_X2_PROJECT": str(paths.PROJECT_ROOT),
        }
        environment.update(extra_env or {})
        super().__init__(
            module="games.ffx_x2.server",
            plugin_id="ffx-x2",
            app_root=LEXEDITOR_ROOT,
            check=check,
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"ffx-x2": PLUGIN}, "ffx-x2")


def _write_fixture_vbf(target: Path, files: list[tuple[str, bytes]]) -> None:
    """Build a tiny deterministic VBF solely for the non-proprietary smoke fixture."""
    name_table = bytearray()
    entry_meta = []
    all_descriptors: list[int] = []
    all_raw_blocks: list[list[bytes]] = []
    start_block = 0
    for archive_path, data in files:
        name_offset = len(name_table)
        name_table.extend(archive_path.encode("ascii") + b"\0")
        descriptors: list[int] = []
        raw_blocks: list[bytes] = []
        for offset in range(0, len(data), BLOCK_SIZE):
            block = data[offset:offset + BLOCK_SIZE]
            compressed = zlib.compress(block)
            if len(compressed) < len(block):
                descriptors.append(len(compressed)); raw_blocks.append(compressed)
            elif len(block) < BLOCK_SIZE:
                descriptors.append(len(block)); raw_blocks.append(block)
            else:
                descriptors.append(0); raw_blocks.append(block)
        entry_meta.append((archive_path, data, name_offset, start_block, descriptors, raw_blocks))
        start_block += len(descriptors)
        all_descriptors.extend(descriptors)
        all_raw_blocks.append(raw_blocks)

    file_count = len(files)
    header_length = 16 + file_count * 48 + 4 + len(name_table) + len(all_descriptors) * 2
    data_offsets: list[int] = []
    next_offset = header_length
    for raw_blocks in all_raw_blocks:
        data_offsets.append(next_offset)
        next_offset += sum(map(len, raw_blocks))

    header = bytearray()
    header.extend(b"SRYK")
    header.extend(struct.pack("<I", header_length))
    header.extend(struct.pack("<Q", file_count))
    for archive_path, *_ in entry_meta:
        header.extend(hashlib.md5(archive_path.encode("ascii")).digest())
    for data_offset, (_, data, name_offset, entry_start_block, _, _) in zip(data_offsets, entry_meta):
        header.extend(struct.pack("<IIQQQ", entry_start_block, 0, len(data), data_offset, name_offset))
    header.extend(struct.pack("<I", len(name_table) + 4))
    header.extend(name_table)
    if all_descriptors:
        header.extend(struct.pack(f"<{len(all_descriptors)}H", *all_descriptors))
    if len(header) != header_length:
        raise AssertionError("synthetic VBF header size mismatch")

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as stream:
        stream.write(header)
        for raw_blocks in all_raw_blocks:
            for block in raw_blocks:
                stream.write(block)
        stream.write(hashlib.md5(header).digest())


def smoke() -> list[str]:
    """Exercise the VBF -> project -> Fahrenheit path on synthetic data only."""
    fixture_path = "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin"
    fixture_data = (b"LEXEDITOR-FFX-" * 6000) + b"tail"
    with tempfile.TemporaryDirectory(prefix="lexeditor-ffx-x2-plugin-") as temp_name:
        root = Path(temp_name)
        game = root / "game"
        project = root / "project"
        for relative in ("FFX&X-2_LAUNCHER.exe", "FFX.exe", "FFX-2.exe", "fahrenheit/bin/fhstage0.exe"):
            target = game / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture")
        (game / "fahrenheit" / "mods").mkdir(parents=True, exist_ok=True)
        (game / "fahrenheit" / "mods" / "loadorder").write_text("other-mod\n", encoding="utf-8")
        _write_fixture_vbf(game / "data" / "FFX_Data.vbf", [(fixture_path, fixture_data)])
        _write_fixture_vbf(game / "data" / "FFX2_Data.vbf", [
            ("FFX2_Data/ffx_ps2/ffx2/master/test.bin", b"X2 fixture")
        ])

        with FFXX2Session({
            "LEXEDITOR_FFX_X2_ROOT": str(game),
            "LEXEDITOR_FFX_X2_PROJECT": str(project),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "ffx-x2" or "vbf-index" not in identity.get("capabilities", []):
                raise RuntimeError("FFX/X-2 plugin returned the wrong managed identity")
            data_map = request_json(session.url + "api/datamap")
            if sum(row.get("status") == "integrated" for row in data_map.get("rows", [])) < 3:
                raise RuntimeError("FFX/X-2 Data Map did not expose both VBFs and deployment")
            catalog = request_json(session.url + "api/archive?game=x&q=takara&limit=10")
            if catalog.get("total") != 1 or catalog["entries"][0]["path"] != fixture_path:
                raise RuntimeError("FFX VBF catalog did not return the fixture entry")
            extracted = request_json(session.url + "api/project/extract", {
                "game": "x", "path": fixture_path, "headerMd5": catalog["headerMd5"],
            })
            project_file = project / "efl" / "x" / Path(*fixture_path.split("/"))
            if not extracted.get("created") or project_file.read_bytes() != fixture_data:
                raise RuntimeError("FFX VBF entry did not extract byte-exactly to the project overlay")
            deployed = request_json(session.url + "api/deployment/deploy", {})
            deployed_file = game / "fahrenheit" / "mods" / "lexeditor-ffx-x2" / "efl" / "x" / Path(*fixture_path.split("/"))
            loadorder = game / "fahrenheit" / "mods" / "loadorder"
            if not deployed.get("deployed") or deployed_file.read_bytes() != fixture_data:
                raise RuntimeError("Lexeditor project did not deploy to the Fahrenheit EFL mod")
            if loadorder.read_text(encoding="utf-8").splitlines() != ["other-mod", "lexeditor-ffx-x2"]:
                raise RuntimeError("Fahrenheit loadorder was not preserved and extended correctly")
            reverted = request_json(session.url + "api/deployment/revert", {})
            if reverted.get("deployed") or deployed_file.exists() or loadorder.read_text(encoding="utf-8").splitlines() != ["other-mod"]:
                raise RuntimeError("Fahrenheit deployment did not revert cleanly")

            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(session.url, timeout=5) as response:
                        html = response.read().decode("utf-8")
                    break
                except (urllib.error.URLError, TimeoutError, OSError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.25)
            if ('id="lexeditor-shell"' not in html or '/shared/framework.js' not in html
                    or "Final Fantasy X / X-2" not in html):
                raise RuntimeError("FFX/X-2 plugin did not serve the shared editor shell")
        if not session.wait_closed():
            raise RuntimeError("FFX/X-2 child port is still open after host shutdown")
    return [
        "FFX and FFX-2 Steam collection identity confirmed on synthetic layout",
        "VBF header validation, search and compressed extraction passed",
        "byte-exact project overlay extraction passed",
        "file-only Fahrenheit EFL deploy/loadorder/revert path passed",
        "shared editor shell served and child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="ffx-x2",
    name="Final Fantasy X/X-2 HD Remaster",
    process_names=("FFX.exe", "FFX-2.exe", "FFX&X-2_LAUNCHER.exe"),
    subtitle="FFX / FFX-2 Steam collection",
    description="Reads both VBF archives, stages safe project overlays, and deploys file replacements through Fahrenheit.",
    accent="#5f8fd3",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=FFXX2Session,
    projects=ModProjectSpec(
        root_env="LEXEDITOR_FFX_X2_PROJECT",
        default_root=paths.PROJECT_ROOT,
        required_paths=("efl",),
        template_root=paths.PLUGIN_ROOT / "project-template",
        initialize=_initialize_project,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_FFX_X2_ROOT",
        required_paths=(
            "FFX&X-2_LAUNCHER.exe", "FFX.exe", "FFX-2.exe",
            "data/FFX_Data.vbf", "data/FFX2_Data.vbf",
        ),
        launch_path="FFX&X-2_LAUNCHER.exe",
        steam_app_id="359870",
        install_dir_names=("FINAL FANTASY FFX&FFX-2 HD Remaster",),
        default_roots=(
            Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster"),
        ),
    ),
)
