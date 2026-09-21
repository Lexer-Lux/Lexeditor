"""Fresh Chrono Trigger Steam plugin lifecycle."""
from __future__ import annotations

import gzip
import json
import struct
import tempfile
import zipfile
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession, request_json

from . import paths
from .archive import _decode
from .project import PROJECT_MARKER, initialize_project
from .world_data import BANK_PATH, HEADER_OFFSET, HEADER_SIZE, WORLD_COUNT


ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return paths.check()


class ChronoTriggerSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {
            "LEXEDITOR_CHRONO_TRIGGER_ROOT": str(paths.GAME_ROOT),
            "LEXEDITOR_CHRONO_TRIGGER_PROJECT": str(paths.PROJECT_ROOT),
        }
        environment.update(extra_env or {})
        session_check = lambda: paths.check_paths(
            Path(environment["LEXEDITOR_CHRONO_TRIGGER_ROOT"]),
            Path(environment["LEXEDITOR_CHRONO_TRIGGER_PROJECT"]),
        )
        super().__init__(module="games.chrono_trigger.server", plugin_id="chrono-trigger", app_root=ROOT,
                         check=session_check, port_env="LEXEDITOR_CHRONO_TRIGGER_PORT", extra_env=environment)


def launch() -> int:
    from desktop_host import run_host
    return run_host({"chrono-trigger": PLUGIN}, "chrono-trigger")


def _fixture_archive(path: Path, resources: list[tuple[str, bytes]]) -> None:
    offset = 16
    blocks = []
    records = []
    for virtual, payload in resources:
        encoded = len(payload).to_bytes(4, "big") + gzip.compress(payload, mtime=0)
        block = _decode(offset, encoded)
        blocks.append(block)
        records.append((virtual, offset, len(block)))
        offset += len(block)
    table_size = 4 + len(records) * 12
    names = bytearray()
    name_offsets = []
    for virtual, _entry_offset, _size in records:
        name_offsets.append(table_size + len(names))
        names.extend(virtual.encode("utf-8") + b"\0")
    index = bytearray(struct.pack("<I", len(records)))
    for name_offset, (_virtual, entry_offset, stored_size) in zip(name_offsets, records):
        index.extend(struct.pack("<III", name_offset, entry_offset, stored_size))
    index.extend(names)
    encoded_index_plain = len(index).to_bytes(4, "big") + gzip.compress(bytes(index), mtime=0)
    index_offset = offset
    encoded_index = _decode(index_offset, encoded_index_plain)
    total = index_offset + len(encoded_index)
    header = _decode(0, b"ARC1" + struct.pack("<III", total, index_offset, len(encoded_index)))
    path.write_bytes(header + b"".join(blocks) + encoded_index)


def smoke() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-fresh-") as temp_name:
        root = Path(temp_name)
        game = root / "game"
        game.mkdir()
        (game / "Chrono Trigger.exe").write_bytes(b"fixture")
        exits_offset = struct.pack("<IHH", 2, 0, 1)
        exits_data = b"HEAD" + struct.pack("<BBBBHBB", 2, 3, 1, 0xA5, 7, 8, 9)
        treasure_offset = struct.pack("<IHH", 2, 0, 1)
        treasure_data = b"HEAD" + struct.pack("<BBHH", 4, 5, 0x1002, 0xCAFE)
        scene_header = struct.pack("<10H4B", 10, 1, 2, 3, 4, 5, 6, 7, 8, 0xBEEF, 0, 1, 14, 15) + b"\xAA\xBB"
        palette = b"\x12\x34" + struct.pack("<H", 0x801F) + (b"\x00\x00" * 255) + b"\xCC"
        world_bank = bytearray(b"\xA5" * (HEADER_OFFSET + WORLD_COUNT * HEADER_SIZE + 3))
        world_bank[HEADER_OFFSET:HEADER_OFFSET + HEADER_SIZE] = bytes(range(HEADER_SIZE))
        world_event = (
            bytes([2])
            + struct.pack("<BBBHBBB", 0x85, 0xC7, 0, 12, 0xAD, 9, 10)
            + struct.pack("<BBBHBBB", 0x82, 3, 1, 0x1FF, 0x52, 0, 0)
            + bytes([2, 0x84, 5, 0, 0, 0, 0])
            + bytes([1, 7, 8, 9])
            + bytes([2]) + struct.pack("<HH", 0x400, 0x410)
            + b"\xAA\xBB"
        )
        _fixture_archive(game / "resources.bin", [
            ("Localize/en/msg/item.txt", b"0000,Sword\r\n0001,Armor\r\n0002,Mail\r\n"),
            ("Localize/en/msg/cmes0.txt", b"FLD_001,Hello\r\nFLD_002,World\r\n"),
            ("Localize/en/msg/debug_map.txt", b"0000,Millennial Fair\r\n"),
            ("Localize/en/msg/w_map.txt", b"0000,Truce Canyon\r\n0001,Medina\r\n"),
            ("Game/world/EventTable/EventTable_0004.dat", world_event),
            ("Game/field/Mapinfo/mapinfo_1.dat", scene_header),
            ("Game/field/palette_bin/plt4.bin", palette),
            ("Game/common/MapJumpOffsetTbl.dat", exits_offset),
            ("Game/common/MapJumpDataTbl.dat", exits_data),
            ("Game/common/TakaraOffsetTbl.dat", treasure_offset),
            ("Game/common/TakaraDataTbl.dat", treasure_data),
            (BANK_PATH, bytes(world_bank)),
        ])
        original_archive = (game / "resources.bin").read_bytes()
        project = root / "project"
        with ChronoTriggerSession({"LEXEDITOR_CHRONO_TRIGGER_ROOT": str(game), "LEXEDITOR_CHRONO_TRIGGER_PROJECT": str(project)}) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "chrono-trigger":
                raise RuntimeError("Chrono Trigger service returned the wrong identity")
            message = request_json(session.url + "api/messages?path=Localize%2Fen%2Fmsg%2Fcmes0.txt")
            saved = request_json(session.url + "api/messages/save", {"path": message["path"], "sha256": message["sha256"], "edits": [{"line": 0, "key": "FLD_001", "text": "Changed"}]})
            if saved["rows"][0]["text"] != "Changed":
                raise RuntimeError("Text edit did not survive readback")
            scenes = request_json(session.url + "api/scenes?language=en")
            scene = scenes["rows"][0]
            saved_scene = request_json(session.url + "api/scenes/save", {"id": scene["id"], "sha256": scene["sha256"], "language": "en", "values": {"musicIndex": 42, "cameraUnbounded": True}})
            if saved_scene["musicIndex"] != 42 or saved_scene["unknownWord"] != 0xBEEF or saved_scene["trailingBytes"] != 2:
                raise RuntimeError("Area settings edit did not preserve the unmodelled PC header data")
            palette_files_result = request_json(session.url + "api/palette-files")
            if palette_files_result["rows"][0]["path"] != "Game/field/palette_bin/plt4.bin":
                raise RuntimeError("Palette catalogue did not find the Steam field palette")
            palette_data = request_json(session.url + "api/palette?path=Game%2Ffield%2Fpalette_bin%2Fplt4.bin")
            saved_palette = request_json(session.url + "api/palette/save", {"path": palette_data["path"], "sha256": palette_data["sha256"], "edits": [{"token": "0", "hex": "#00FF00"}]})
            if saved_palette["rows"][0]["hex"] != "#00FF00" or not saved_palette["rows"][0]["preservedBit15"] or saved_palette["prefixHex"] != "1234" or saved_palette["trailingBytes"] != 1:
                raise RuntimeError("Palette edit did not preserve fixed Steam palette metadata")
            exits = request_json(session.url + "api/exits")
            saved_exits = request_json(session.url + "api/exits/save", {"dataSha256": exits["dataSha256"], "offsetSha256": exits["offsetSha256"], "edits": [{"token": "0:0", "values": {"destinationId": 8, "facing": 2}}]})
            if saved_exits["rows"][0]["destinationId"] != 8 or saved_exits["rows"][0]["unknownFacingBits"] != 0xA0:
                raise RuntimeError("Exit edit failed to preserve unknown facing bits")
            treasure = request_json(session.url + "api/treasure")
            saved_treasure = request_json(session.url + "api/treasure/save", {"dataSha256": treasure["dataSha256"], "offsetSha256": treasure["offsetSha256"], "language": "en", "edits": [{"token": "0:0", "values": {"kind": "gold", "gold": 200}}]})
            if saved_treasure["rows"][0]["gold"] != 200 or saved_treasure["rows"][0]["trailingWord"] != 0xCAFE:
                raise RuntimeError("Treasure edit failed to preserve the unknown trailing word")
            worlds = request_json(session.url + "api/worlds")
            saved_worlds = request_json(session.url + "api/worlds/save", {"sha256": worlds["sha256"], "edits": [{"token": "0", "values": {"mapIndex": 42, "scriptIndex": 43}}]})
            if (saved_worlds["rows"][0]["mapIndex"] != 42 or saved_worlds["rows"][0]["scriptIndex"] != 43
                    or saved_worlds["rows"][0]["paletteAnimationIndex"] != 11):
                raise RuntimeError("World header edit did not stay inside the documented Steam record")
            navigation = request_json(session.url + "api/world-navigation?language=en")
            world_exit = next(row for row in navigation["rows"] if row["token"] == "4:exit:0")
            world_trigger = next(row for row in navigation["rows"] if row["token"] == "4:trigger:0")
            saved_navigation = request_json(session.url + "api/world-navigation/save", {
                "path": world_exit["path"], "sha256": world_exit["sha256"], "language": "en",
                "edits": [
                    {"token": world_exit["token"], "values": {"destinationScene": 33, "facing": 1}},
                    {"token": world_trigger["token"], "values": {"scriptAddressIndex": 1}},
                ],
            })
            saved_by_token = {row["token"]: row for row in saved_navigation["rows"]}
            if (saved_by_token["4:exit:0"]["destinationScene"] != 33
                    or saved_by_token["4:exit:0"]["unknownFacingBits"] != 0xA1
                    or saved_by_token["4:trigger:0"]["scriptAddressIndex"] != 1):
                raise RuntimeError("World navigation edit did not preserve fixed-record semantics")
            exported = request_json(session.url + "api/export", {})
            if not exported.get("replacementOnly"):
                raise RuntimeError("CTP export did not assert replacement-only loader compatibility")
            with zipfile.ZipFile(exported["path"]) as ctp:
                if set(ctp.namelist()) != {"Localize/en/msg/cmes0.txt", "Game/field/Mapinfo/mapinfo_1.dat", "Game/field/palette_bin/plt4.bin", "Game/common/MapJumpDataTbl.dat", "Game/common/TakaraDataTbl.dat", BANK_PATH, "Game/world/EventTable/EventTable_0004.dat"}:
                    raise RuntimeError("CTP export did not contain exactly the changed resources")
        if (game / "resources.bin").read_bytes() != original_archive:
            raise RuntimeError("Fresh Chrono Trigger plugin modified resources.bin")
    return [
        "read-only ARC1 source archive validated",
        "keyed Steam text edit survived project-overlay readback",
        "fixed 24-byte area settings edit preserved the unmodelled word and trailing bytes",
        "256-color RGB555 palette edit preserved prefix, bit 15 and trailing bytes",
        "fixed-size area exit edit preserved unknown flag bits",
        "treasure edit preserved the unknown trailing word",
        "fixed 23-byte world header edit preserved the PC-unused palette-animation byte and surrounding bank data",
        "fixed-size world exit/trigger edits preserved semantics, unknown bits and non-editable blocks",
        "deterministic CTP export contained only changed archive-relative resources",
        "installed resources.bin remained byte-identical",
    ]


PLUGIN = GamePlugin(
    plugin_id="chrono-trigger",
    name="Chrono Trigger",
    accent="#d3a348",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=ChronoTriggerSession,
    process_names=("Chrono Trigger.exe",),
    mods_load=False,
    projects=ModProjectSpec(
        root_env="LEXEDITOR_CHRONO_TRIGGER_PROJECT",
        default_root=paths.PROJECT_ROOT,
        required_paths=(PROJECT_MARKER,),
        template_root=ROOT / "games" / "chrono_trigger" / "project_template",
        initialize=initialize_project,
        content_types=(("Steam resource overrides", (".txt", ".dat", ".bin", ".bmp", ".png")),),
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
