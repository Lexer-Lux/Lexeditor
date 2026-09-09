"""Chrono Trigger Steam plugin lifecycle."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import struct
import tempfile
import zipfile

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
    offset = 16
    blocks: list[bytes] = []
    records: list[tuple[str, int, int]] = []
    for virtual_path, payload in resources:
        decoded = len(payload).to_bytes(4, "big") + gzip.compress(payload, mtime=0)
        blocks.append(ResourceArchive.decode(decoded, offset))
        records.append((virtual_path, offset, len(decoded)))
        offset += len(decoded)
    table_size = 4 + len(records) * 12
    strings = bytearray()
    path_offsets = []
    for virtual_path, _entry_offset, _stored_size in records:
        path_offsets.append(table_size + len(strings))
        strings.extend(virtual_path.encode("utf-8") + b"\0")
    index = bytearray(struct.pack("<I", len(records)))
    for path_offset, (_virtual_path, entry_offset, stored_size) in zip(path_offsets, records):
        index.extend(struct.pack("<III", path_offset, entry_offset, stored_size))
    index.extend(strings)
    encoded_index = len(index).to_bytes(4, "big") + gzip.compress(bytes(index), mtime=0)
    index_offset = offset
    header = b"ARC1" + struct.pack("<III", index_offset + len(encoded_index), index_offset, len(encoded_index))
    path.write_bytes(ResourceArchive.decode(header, 0) + b"".join(blocks) + ResourceArchive.decode(encoded_index, index_offset))


def _field_event(payload: bytes) -> bytes:
    return bytes([1]) + b"".join(struct.pack("<H", 32) for _ in range(16)) + payload


def _world_labels() -> bytes:
    rows = [f"{index:04d},World Exit {index}" for index in range(106)]
    rows.extend([
        "0106,Present", "0107,Middle Ages", "0108,Future",
        "0109,Prehistory", "0110,Antiquity", "0111,End of Time",
    ])
    return ("\n".join(rows) + "\n").encode("utf-8")


def _scene_map() -> bytes:
    # 16x16 L1/L2, no L3, then one RLE Full-collision prop repeated 256 times.
    return bytes([0, 0, 0, 0, 3, 0x11]) + bytes([1]) * 256 + bytes([2]) * 256 + bytes([0x84, 0, 0, 0])


def smoke() -> list[str]:
    """Exercise the managed service, overlays, inspection/export and deployment."""
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
        struct.pack_into("<H", scene, 12, 0)
        struct.pack_into("<H", scene, 16, 20)
        bank = bytearray(WORLD_HEADER_OFFSET + 8 * WORLD_HEADER_SIZE + 16)
        event = _field_event(bytes([0x83, 0x34, 0x12, 0x80, 0x00]))
        _build_smoke_archive(game / "resources.bin", [
            ("Localize/en/msg/item.txt", b"0000,Potion\r\n0001,Ether\r\n"),
            ("Localize/en/msg/debug_map.txt", b"0000,Millennial Fair\n0001,Guardia Forest\n"),
            ("Localize/en/msg/w_map.txt", _world_labels()),
            ("Localize/en/msg/player.txt", b"0000,Crono\n0001,Marle\n"),
            ("Game/field/Mapinfo/mapinfo_0.dat", bytes(scene)),
            ("Game/field/MapTable/MapTable_0000.dat", _scene_map()),
            ("Game/field/atel/Atel_0020.dat", event),
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
                "resource-index", "resource-preview", "localized-labels", "scene-map-layout",
                "localization-text", "scene-headers", "field-event-disassembly",
                "field-event-fixed-edit", "project-overlay", "project-changes", "ctp-export",
                "ctext-deploy", "world-script-disassembly",
            }
            if identity.get("pluginId") != "chrono-trigger" or not required.issubset(identity.get("capabilities", [])):
                raise RuntimeError("Chrono Trigger service returned the wrong managed capabilities")

            labels = request_json(session.url + "api/labels?source=mine")
            if labels["languages"]["items"] != "en" or labels["worldNames"][0] != "Present":
                raise RuntimeError("Chrono Trigger localized labels did not resolve")

            resource = request_json(session.url + "api/resource?path=Localize%2Fen%2Fmsg%2Fitem.txt&source=mine")
            if resource["previewKind"] != "text" or "Potion" not in resource["preview"]:
                raise RuntimeError("Chrono Trigger resource text preview did not decode")

            message = request_json(session.url + "api/messages?path=Localize%2Fen%2Fmsg%2Fitem.txt&source=mine")
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
            map_data = request_json(session.url + "api/scene-map?scene=0&source=mine")
            if map_data["sceneWidth"] != 16 or map_data["collisionCounts"] != {"Full": 256}:
                raise RuntimeError("Chrono Trigger smoke structural scene map did not decode")

            event_data = request_json(session.url + "api/events?id=20&source=mine")
            if event_data["decodedCommandCount"] != 2 or event_data["problemFunctionBounds"]:
                raise RuntimeError("Chrono Trigger smoke field event commands did not disassemble")
            first_fn = event_data["objects"][0]["functions"][0]
            first_command = first_fn["commands"][0]
            if first_command["name"] != "Load Enemy" or not first_fn["complete"]:
                raise RuntimeError("Chrono Trigger smoke field event command metadata is wrong")
            if first_command.get("editor", {}).get("values") != {"enemyId": 0x1234, "slot": 0, "static": True}:
                raise RuntimeError("Chrono Trigger smoke field event named editor schema is missing")

            saved_event = request_json(session.url + "api/save/event-fields", {
                "eventId": 20, "objectId": 0, "functionId": 0, "commandIndex": 0,
                "sha256": event_data["sha256"], "values": {"enemyId": 0x5678, "slot": 3},
            })
            saved_command = saved_event["objects"][0]["functions"][0]["commands"][0]
            if saved_event["source"] != "project" or saved_command["argumentsHex"] != "78 56 83":
                raise RuntimeError("Chrono Trigger smoke named event edit did not save to project overlay")
            if saved_command.get("editor", {}).get("values", {}).get("enemyId") != 0x5678:
                raise RuntimeError("Chrono Trigger smoke saved event did not refresh named editor values")
            vanilla_event = request_json(session.url + "api/events?id=20&source=vanilla")
            vanilla_command = vanilla_event["objects"][0]["functions"][0]["commands"][0]
            if vanilla_command["argumentsHex"] != "34 12 80":
                raise RuntimeError("Chrono Trigger smoke named event edit modified Vanilla event bytes")

            saved_scene = request_json(session.url + "api/save/scene", {
                "id": first["id"], "sha256": first["sha256"], "values": {"musicIndex": 42},
            })
            if saved_scene["values"]["musicIndex"] != 42 or saved_scene["source"] != "project":
                raise RuntimeError("Chrono Trigger smoke scene overlay did not save")
            vanilla = request_json(session.url + "api/scenes?source=vanilla")
            if vanilla["rows"][0]["values"]["musicIndex"] != 10:
                raise RuntimeError("Chrono Trigger smoke write modified the Vanilla source")

            changes = request_json(session.url + "api/changes")
            changed_paths = {row["path"] for row in changes["rows"]}
            expected_changes = {
                "Localize/en/msg/item.txt", "Game/field/Mapinfo/mapinfo_0.dat",
                "Game/field/atel/Atel_0020.dat",
            }
            if expected_changes - changed_paths:
                raise RuntimeError("Chrono Trigger project change inventory missed saved overlays")

            exported = request_json(session.url + "api/export/ctp", {})
            export_path = Path(exported["path"])
            if exported["fileCount"] != 3 or not export_path.is_file():
                raise RuntimeError("Chrono Trigger CTP export did not contain the project overlays")
            with zipfile.ZipFile(export_path) as archive:
                if set(archive.namelist()) != changed_paths:
                    raise RuntimeError("Chrono Trigger CTP members do not match project resources")

            mapped = request_json(session.url + "api/datamap")
            map_row = next((
                row for row in mapped.get("rows", [])
                if str(row.get("filename", "")).startswith("Game/field/MapTable/MapTable_*.dat")
            ), None)
            if not map_row or map_row.get("status") != "integrated" or "raster" not in str(map_row.get("coverage", "")):
                raise RuntimeError("Chrono Trigger Data Map did not report current scene-map coverage")
            event_row = next((
                row for row in mapped.get("rows", [])
                if str(row.get("filename", "")).startswith("Game/field/atel/Atel_*.dat")
            ), None)
            if not event_row or "fixed" not in str(event_row.get("coverage", "")):
                raise RuntimeError("Chrono Trigger Data Map did not report current event write coverage")

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
            if not (game / "mods/SmokeMod/Game/field/atel/Atel_0020.dat").is_file():
                raise RuntimeError("Chrono Trigger smoke deployment missed the saved event overlay")

        if not session.wait_closed():
            raise RuntimeError("Chrono Trigger child service port is still open after smoke shutdown")
        if (game / "resources.bin").read_bytes() != original_archive:
            raise RuntimeError("Chrono Trigger deployment changed the Vanilla ARC1 archive")
        config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
        if not config["mods"]["enabled"] or "SmokeMod" not in config["mods"]["load_order"]:
            raise RuntimeError("Chrono Trigger deployment did not persist CTExt load order activation")
        if not (game / "ctext.json.lexeditor.bak").is_file():
            raise RuntimeError("Chrono Trigger deployment did not create the CTExt config backup")

    return [
        "managed service and expanded capability contract confirmed",
        "localized labels, bounded resource preview, scene MapTable and field-event commands decoded",
        "named fixed-width event command edited through the managed desktop API with Vanilla unchanged",
        "message, event and scene edits saved to loose overlays while Vanilla stayed unchanged",
        "project change inventory and deterministic CTP export verified",
        "Data Map reflected current scene-map and field-event coverage",
        "CTExt preflight/deployment, config backup and load-order activation verified",
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
        required_any=((paths.PROJECT_MARKER,), ("Game",), ("Localize",)),
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
