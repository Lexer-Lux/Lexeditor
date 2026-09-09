"""Chrono Trigger Steam plugin lifecycle."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import struct
import tempfile

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession, request_json

from . import paths
from .resources import ResourceArchive
from .worlds import WORLD_BANK, WORLD_HEADER_OFFSET, WORLD_HEADER_SIZE


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return paths.check()


class ChronoTriggerSession(LocalPluginSession):
    """One host-owned Chrono Trigger Steam editor service."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {
            "LEXEDITOR_CHRONO_TRIGGER_ROOT": str(paths.GAME_ROOT),
            "LEXEDITOR_CHRONO_TRIGGER_PROJECT": str(paths.PROJECT_ROOT),
        }
        environment.update(extra_env or {})
        super().__init__(
            module="games.chrono_trigger.server",
            plugin_id="chrono-trigger",
            app_root=LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_CHRONO_TRIGGER_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"chrono-trigger": PLUGIN}, "chrono-trigger")


def _build_smoke_archive(path: Path, resources: list[tuple[str, bytes]]) -> None:
    """Build the smallest valid ARC1 fixture needed by the managed smoke test."""
    offset = 16
    blocks: list[bytes] = []
    records: list[tuple[str, int, int]] = []
    for virtual_path, payload in resources:
        decoded = len(payload).to_bytes(4, "big") + gzip.compress(payload, mtime=0)
        blocks.append(ResourceArchive.decode(decoded, offset))
        records.append((virtual_path, offset, len(decoded)))
        offset += len(decoded)

    table_size = 4 + len(records) * 12
    string_table = bytearray()
    path_offsets: list[int] = []
    for virtual_path, _entry_offset, _stored_size in records:
        path_offsets.append(table_size + len(string_table))
        string_table.extend(virtual_path.encode("utf-8") + b"\0")

    index = bytearray(struct.pack("<I", len(records)))
    for path_offset, (_virtual_path, entry_offset, stored_size) in zip(path_offsets, records):
        index.extend(struct.pack("<III", path_offset, entry_offset, stored_size))
    index.extend(string_table)
    encoded_index = len(index).to_bytes(4, "big") + gzip.compress(bytes(index), mtime=0)
    index_offset = offset
    header = b"ARC1" + struct.pack(
        "<III", index_offset + len(encoded_index), index_offset, len(encoded_index)
    )
    path.write_bytes(
        ResourceArchive.decode(header, 0)
        + b"".join(blocks)
        + ResourceArchive.decode(encoded_index, index_offset)
    )


def smoke() -> list[str]:
    """Exercise the managed service, overlay writes and explicit deployment safely."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-trigger-plugin-") as temp_name:
        root = Path(temp_name)
        game = root / "game"
        game.mkdir()
        (game / "Chrono Trigger.exe").write_bytes(b"fixture")
        (game / "ctext.dll").write_bytes(b"fixture")
        (game / "sqlite3.dll").write_bytes(b"fixture")
        (game / "ctext.json").write_text(json.dumps({
            "mods": {"enabled": False, "enable_ctp_loading": True, "load_order": []},
        }), encoding="utf-8")

        scene = bytearray(24)
        struct.pack_into("<H", scene, 0, 10)
        struct.pack_into("<H", scene, 16, 20)
        bank = bytearray(WORLD_HEADER_OFFSET + 8 * WORLD_HEADER_SIZE + 16)
        _build_smoke_archive(game / "resources.bin", [
            ("Localize/en/msg/item.txt", b"0000,Potion\r\n0001,Ether\r\n"),
            ("Game/field/Mapinfo/mapinfo_0.dat", bytes(scene)),
            (WORLD_BANK, bytes(bank)),
            ("Game/world/EventTable/EventTable_0000.dat", b"\x00\x00\x00\x00"),
            ("Game/world/esl/Event_0000.dat", b"\x00\x52"),
        ])
        original_archive = (game / "resources.bin").read_bytes()
        project = root / "SmokeMod"

        session = ChronoTriggerSession({
            "LEXEDITOR_CHRONO_TRIGGER_ROOT": str(game),
            "LEXEDITOR_CHRONO_TRIGGER_PROJECT": str(project),
        })
        with session:
            identity = request_json(session.url + "api/plugin")
            required = {
                "resource-index", "localization-text", "scene-headers", "project-overlay",
                "ctext-deploy", "world-script-disassembly",
            }
            if identity.get("pluginId") != "chrono-trigger" or not required.issubset(identity.get("capabilities", [])):
                raise RuntimeError("Chrono Trigger service returned the wrong managed capabilities")

            message = request_json(
                session.url + "api/messages?path=Localize%2Fen%2Fmsg%2Fitem.txt&source=mine"
            )
            if message["rows"][0]["text"] != "Potion" or message["source"] != "archive":
                raise RuntimeError("Chrono Trigger smoke message table did not load from ARC1")
            saved_message = request_json(session.url + "api/save/message", {
                "path": message["path"], "sha256": message["sha256"],
                "changes": [{"id": 0, "text": "Tonic"}],
            })
            if saved_message["rows"][0]["text"] != "Tonic" or saved_message["source"] != "project":
                raise RuntimeError("Chrono Trigger smoke message overlay did not save")

            scenes = request_json(session.url + "api/scenes?source=mine")
            first = scenes["rows"][0]
            if first["values"]["musicIndex"] != 10 or first["values"]["scriptIndex"] != 20:
                raise RuntimeError("Chrono Trigger smoke scene header did not decode")
            saved_scene = request_json(session.url + "api/save/scene", {
                "id": first["id"], "sha256": first["sha256"], "values": {"musicIndex": 42},
            })
            if saved_scene["values"]["musicIndex"] != 42 or saved_scene["source"] != "project":
                raise RuntimeError("Chrono Trigger smoke scene overlay did not save")

            vanilla = request_json(session.url + "api/scenes?source=vanilla")
            if vanilla["rows"][0]["values"]["musicIndex"] != 10:
                raise RuntimeError("Chrono Trigger smoke write modified the Vanilla source")

            mapped = request_json(session.url + "api/datamap")
            if not any(row.get("status") == "integrated" for row in mapped.get("rows", [])):
                raise RuntimeError("Chrono Trigger Data Map did not report integrated coverage")

            deployment = request_json(session.url + "api/deployment")
            if not deployment["ctext"]["installed"] or not deployment["ctext"]["configValid"]:
                raise RuntimeError("Chrono Trigger smoke CTExt status did not detect the fixture runtime")
            if not deployment["canDeploy"] or not deployment["audit"]["ok"]:
                raise RuntimeError("Chrono Trigger smoke project did not pass deployment preflight")
            deployed = request_json(session.url + "api/deployment/deploy", {})
            if not deployed["deployment"]["active"]:
                raise RuntimeError("Chrono Trigger smoke project was not activated in CTExt")
            if not (game / "mods/SmokeMod/Localize/en/msg/item.txt").is_file():
                raise RuntimeError("Chrono Trigger smoke deployment did not mirror project files")

        if not session.wait_closed():
            raise RuntimeError("Chrono Trigger child service port is still open after smoke shutdown")
        if not (project / "Localize/en/msg/item.txt").is_file():
            raise RuntimeError("Chrono Trigger message project overlay was not created")
        if not (project / "Game/field/Mapinfo/mapinfo_0.dat").is_file():
            raise RuntimeError("Chrono Trigger scene project overlay was not created")
        if (game / "resources.bin").read_bytes() != original_archive:
            raise RuntimeError("Chrono Trigger deployment changed the Vanilla ARC1 archive")
        config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
        if not config["mods"]["enabled"] or "SmokeMod" not in config["mods"]["load_order"]:
            raise RuntimeError("Chrono Trigger deployment did not persist CTExt load order activation")
        if not (game / "ctext.json.lexeditor.bak").is_file():
            raise RuntimeError("Chrono Trigger deployment did not create the CTExt config backup")

    return [
        "Chrono Trigger managed service identity confirmed",
        "ARC1 localization and scene data decoded",
        "message and scene edits saved to loose project overlays",
        "Vanilla archive remained unchanged",
        "Data Map served integrated coverage",
        "CTExt deployment preflight passed and explicit deployment activated the project",
        "CTExt config backup and load-order activation verified",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="chrono-trigger",
    name="Chrono Trigger",
    subtitle="Steam",
    description="Steam resource, localization, scene and overworld editor with CTExt-compatible loose-file projects.",
    accent="#d3a348",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=ChronoTriggerSession,
    process_names=("Chrono Trigger.exe",),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_CHRONO_TRIGGER_PROJECT",
        default_root=paths.DEFAULT_PROJECT_ROOT,
        required_any=(
            (paths.PROJECT_MARKER,),
            ("Game",),
            ("Localize",),
        ),
        template_root=paths.PROJECT_TEMPLATE_ROOT,
        discover=paths.discover_projects,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_CHRONO_TRIGGER_ROOT",
        required_paths=("Chrono Trigger.exe", "resources.bin"),
        launch_path="Chrono Trigger.exe",
        steam_app_id="613830",
        install_dir_names=("Chrono Trigger",),
        default_roots=(
            Path(r"D:\SteamLibrary\steamapps\common\Chrono Trigger"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Chrono Trigger"),
        ),
    ),
)
