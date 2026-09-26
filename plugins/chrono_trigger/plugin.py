"""Fresh Chrono Trigger Steam plugin lifecycle."""
from __future__ import annotations

import gzip
import json
import struct
import tempfile
import zipfile
from pathlib import Path

from core.plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from core.plugin_manifest import install_spec, plugin_defaults, project_spec
from core.service_session import LocalPluginSession, request_json

from . import paths
from .archive import _decode
from .project import PROJECT_MARKER, initialize_project
from .mod_support import ChronoCtpAdapter
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
        super().__init__(module="plugins.chrono_trigger.server", plugin_id="chrono-trigger", app_root=ROOT,
                         check=session_check, port_env="LEXEDITOR_CHRONO_TRIGGER_PORT", extra_env=environment)


def launch() -> int:
    from core.desktop_host import run_host
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
        scene_map = bytearray(bytes([0, 0, 0x21, 0x43, 0x5A, 0xCB]) + bytes(16 * 16 * 2))
        scene_map[6] = 3
        scene_map[6 + 16 * 16] = 4
        scene_map.extend(bytes([0x01, 0, 0, 0x80, 0x20, 0x10, 255]))
        sprite_descriptor = bytes([9, 8, 7, 0xAC, 5, 0xD2, 0xFE, 0x03, 0x11, 0x22, 0x33, 0xEE])
        sprite_cell = bytearray(b"\xAA\xBB\xCC" + struct.pack("<HH", 2, 0xBEEF))
        sprite_cell.extend(bytes([2]))
        sprite_cell.extend(struct.pack("<HbbB", 0x025C, -5, -25, 0xA1))
        sprite_cell.extend(struct.pack("<HbbB", 0x0000, 1, 2, 0x02))
        sprite_cell.extend(bytes([1]))
        sprite_cell.extend(struct.pack("<HbbB", 0x0020, 3, 4, 0x80))
        sprite_cell.extend(b"\xEE")
        graphics_sets = bytes([1, 2, 3, 4, 5, 6, 7, 0xFF]) + b"\xDD"
        assembly_l12 = bytearray(512 * 4 * 3 + 1)
        struct.pack_into("<HB", assembly_l12, 0, 300 | 0x0400 | (5 << 12), 0xA1)
        assembly_l12[-1] = 0xCC
        assembly_l3 = bytearray(256 * 4 * 3)
        struct.pack_into("<HB", assembly_l3, 0, 77 | 0x0800 | (3 << 12), 0x41)
        chip_animation = (
            bytes([2, 2]) + struct.pack("<H", 64) + bytes([0x1A, 0x4B])
            + struct.pack("<HH", 96, 128)
            + bytes([1]) + struct.pack("<H", 160) + bytes([0x80]) + struct.pack("<H", 192)
            + b"\xEE"
        )
        world_map = bytearray(96 * 64 * 2 + 1)
        world_map[0] = 3
        world_map[96 * 64] = 4
        world_map[-1] = 0xFA
        world_props = bytearray(512 + 1)
        world_props[0:2] = b"\x12\x34"
        world_props[-1] = 0xFB
        world_music = bytearray((96 * 64 // 2) + 1)
        world_music[0] = 0xA5
        world_music[-1] = 0xFC
        world_colors = struct.pack("<HHH", 0x801F, 0x03E0, 0x7C00) + b"\xFD"
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
            ("Game/world/Map/Map_0000.dat", bytes(world_map)),
            ("Game/world/Id/Id_0000.dat", bytes(world_props)),
            ("Game/world/SeId/SeId_0000.dat", bytes(world_music)),
            ("Game/world/colanim_bin/0_colanim.bin", world_colors),
            ("Game/world/EventTable/EventTable_0004.dat", world_event),
            ("Game/chara/dat/c005.dat", sprite_descriptor),
            ("Game/chara/cell/c005.cel", bytes(sprite_cell)),
            ("Game/field/MapTable/MapTable_0006.dat", bytes(scene_map)),
            ("Game/field/BGSetTable/bgsettable_4.dat", graphics_sets),
            ("Game/field/ChipTable/ChipTable_0004.dat", bytes(assembly_l12)),
            ("Game/field/ChipTable/ChipTableBg3_0002.dat", bytes(assembly_l3)),
            ("Game/field/BGAnime/bganimeinfo_4.dat", chip_animation),
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
            scene_map_files_result = request_json(session.url + "api/scene-map-files")
            scene_map_path = scene_map_files_result["rows"][0]["path"]
            scene_map_data = request_json(session.url + "api/scene-map?path=" + scene_map_path.replace("/", "%2F"))
            layer1_tile = next(row for row in scene_map_data["rows"] if row["token"] == "6:1:0")
            layer2_tile = next(row for row in scene_map_data["rows"] if row["token"] == "6:2:0")
            saved_scene_map = request_json(session.url + "api/scene-map/save", {
                "path": scene_map_path, "sha256": scene_map_data["sha256"],
                "edits": [
                    {"token": layer1_tile["token"], "values": {"tileIndex": 300}},
                    {"token": layer2_tile["token"], "values": {"tileIndex": 9}},
                ],
            })
            saved_scene_by_token = {row["token"]: row for row in saved_scene_map["rows"]}
            if (saved_scene_by_token["6:1:0"]["tileIndex"] != 300
                    or saved_scene_by_token["6:2:0"]["tileIndex"] != 9
                    or saved_scene_map["propertyBytes"] != 7):
                raise RuntimeError("Scene map tile edits did not preserve header/property boundaries")
            scene_props = request_json(session.url + "api/scene-properties?path=" + scene_map_path.replace("/", "%2F"))
            prop_run = next(row for row in scene_props["rows"] if row["token"] == "6:prop:1")
            saved_scene_props = request_json(session.url + "api/scene-properties/save", {
                "path": scene_map_path, "sha256": scene_props["sha256"],
                "edits": [{"token": prop_run["token"], "values": {
                    "collisionCode": 30, "moveDirection": 3, "moveSpeed": 2,
                    "priorityTop": True, "npcCollision": True,
                }}],
            })
            saved_prop = next(row for row in saved_scene_props["rows"] if row["token"] == "6:prop:1")
            if (saved_prop["collisionCode"] != 30 or saved_prop["repeatCount"] != 255
                    or not saved_prop["unknownSecondBit5"] or not saved_prop["unknownThirdBit4"]):
                raise RuntimeError("Scene property-run edit did not preserve RLE/unknown metadata")
            scene_render = request_json(session.url + "api/scene-render-settings?path=" + scene_map_path.replace("/", "%2F"))
            saved_scene_render = request_json(session.url + "api/scene-render-settings/save", {
                "path": scene_map_path, "sha256": scene_render["sha256"],
                "values": {"scrollL2XCode": 7, "scrollL2YCode": 15,
                           "layer1Main": True, "layer2Main": False,
                           "effectLayer1": False, "effectLayer2": True},
            })
            if (saved_scene_render["scrollL2XCode"] != 7
                    or saved_scene_render["scrollL2YCode"] != 15
                    or not saved_scene_render["unknownEffectBit3"]
                    or saved_scene_render["preservedBitsByte"] != 0):
                raise RuntimeError("Scene render settings edit did not preserve unknown/dimension bits")
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
            map_files = request_json(session.url + "api/world-files?kind=tiles")
            map_path = map_files["rows"][0]["path"]
            world_tiles = request_json(session.url + "api/world-map?path=" + map_path.replace("/", "%2F"))
            saved_tiles = request_json(session.url + "api/world-map/save", {
                "path": map_path, "sha256": world_tiles["sha256"],
                "edits": [{"token": "0:1:0", "values": {"tileIndex": 9}},
                          {"token": "0:2:0", "values": {"tileIndex": 300}}],
            })
            if (saved_tiles["rows"][0]["tileIndex"] != 9
                    or saved_tiles["rows"][96 * 64]["tileIndex"] != 300
                    or saved_tiles["trailingBytes"] != 1):
                raise RuntimeError("World map tile edits did not preserve fixed layer shape")
            prop_files = request_json(session.url + "api/world-files?kind=properties")
            prop_path = prop_files["rows"][0]["path"]
            world_props_data = request_json(session.url + "api/world-properties?path=" + prop_path.replace("/", "%2F"))
            saved_props = request_json(session.url + "api/world-properties/save", {
                "path": prop_path, "sha256": world_props_data["sha256"],
                "edits": [{"token": "0:0", "values": {"topLeft": 4}}],
            })
            if saved_props["rows"][0]["topLeft"] != 4 or saved_props["rows"][0]["topRight"] != 2:
                raise RuntimeError("World property edit did not preserve adjacent nibbles")
            music_files = request_json(session.url + "api/world-files?kind=music")
            music_path = music_files["rows"][0]["path"]
            world_music_data = request_json(session.url + "api/world-music?path=" + music_path.replace("/", "%2F"))
            saved_music = request_json(session.url + "api/world-music/save", {
                "path": music_path, "sha256": world_music_data["sha256"],
                "edits": [{"token": "0:0", "values": {"rightMusic": 9}}],
            })
            if saved_music["rows"][0]["leftMusic"] != 10 or saved_music["rows"][0]["rightMusic"] != 9:
                raise RuntimeError("World music edit did not preserve the adjacent nibble")
            color_files = request_json(session.url + "api/world-files?kind=colors")
            color_path = color_files["rows"][0]["path"]
            world_color_data = request_json(session.url + "api/world-colors?path=" + color_path.replace("/", "%2F"))
            saved_colors = request_json(session.url + "api/world-colors/save", {
                "path": color_path, "sha256": world_color_data["sha256"],
                "edits": [{"token": "0", "hex": "#00FF00"}],
            })
            if (saved_colors["rows"][0]["hex"] != "#00FF00"
                    or not saved_colors["rows"][0]["preservedBit15"]
                    or saved_colors["trailingBytes"] != 1):
                raise RuntimeError("World palette-animation color edit did not preserve bit 15/tail")
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
            animations = request_json(session.url + "api/chip-animations")
            animation = animations["rows"][0]
            saved_animation = request_json(session.url + "api/chip-animations/save", {
                "path": animation["path"], "sha256": animation["sha256"],
                "edits": [{"token": animation["token"], "values": {
                    "destinationChip": 7, "durationCode0": 0x20, "sourceChip1": 9,
                }}],
            })
            if (saved_animation["rows"][0]["destinationChip"] != 7
                    or saved_animation["rows"][0]["durationLowBits0"] != 0x0A
                    or saved_animation["rows"][0]["sourceChip1"] != 9
                    or saved_animation["trailingBytes"] != 1):
                raise RuntimeError("Chip animation edit did not preserve fixed frame metadata")
            sprites = request_json(session.url + "api/sprite-headers")
            sprite = next(row for row in sprites["rows"] if row["id"] == 5)
            saved_sprite = request_json(session.url + "api/sprite-headers/save", {
                "path": sprite["path"], "sha256": sprite["sha256"],
                "values": {"sizeGroupCode": 2, "primaryEnemy": False, "animationIndex": 9,
                           "handX": -8, "handY": 12},
            })
            if (saved_sprite["sizeGroupCode"] != 2 or saved_sprite["primaryEnemy"]
                    or saved_sprite["animationIndex"] != 9 or saved_sprite["handX"] != -8
                    or saved_sprite["handY"] != 12 or saved_sprite["unknownSizeFlags"] != 0xA4
                    or saved_sprite["unknownFlags"] != 0xD2):
                raise RuntimeError("Sprite descriptor edit did not preserve PC-ignored/unknown fields")
            sprite_assemblies = request_json(session.url + "api/sprite-assemblies")
            sprite_tile = next(row for row in sprite_assemblies["rows"] if row["token"] == "5:0:0")
            saved_sprite_assembly = request_json(session.url + "api/sprite-assemblies/save", {
                "path": sprite_tile["path"], "sha256": sprite_tile["sha256"],
                "edits": [{"token": sprite_tile["token"], "values": {
                    "chipIndex": 511, "x": 7, "y": -10, "flipHorizontal": False,
                }}],
            })
            saved_sprite_tile = next(row for row in saved_sprite_assembly["rows"] if row["token"] == "5:0:0")
            if (saved_sprite_tile["chipIndex"] != 511 or not saved_sprite_tile["weirdSourceBit"]
                    or saved_sprite_tile["unknownFlags"] != 0xA0
                    or saved_sprite_assembly["headerWord"] != 0xBEEF
                    or saved_sprite_assembly["trailingBytes"] != 1):
                raise RuntimeError("Sprite assembly edit did not preserve counts/unknown metadata")
            graphics = request_json(session.url + "api/graphics-sets")
            graphics_row = graphics["rows"][0]
            saved_graphics = request_json(session.url + "api/graphics-sets/save", {
                "path": graphics_row["path"], "sha256": graphics_row["sha256"],
                "values": {"graphicsSet0": 9, "graphicsSet7": 8},
            })
            if (saved_graphics["graphicsSet0"] != 9 or saved_graphics["graphicsSet7"] != 8
                    or saved_graphics["trailingBytes"] != 1):
                raise RuntimeError("Tileset graphics references did not preserve fixed table shape")
            assemblies = request_json(session.url + "api/tile-assemblies")
            assembly = next(row for row in assemblies["rows"] if row["token"] == "layer12:4:0:0")
            saved_assembly = request_json(session.url + "api/tile-assemblies/save", {
                "path": assembly["path"], "sha256": assembly["sha256"],
                "edits": [{"token": assembly["token"], "values": {
                    "chipIndex": 511, "paletteIndex": 6, "flipHorizontal": False,
                    "flipVertical": True, "priority": False,
                }}],
            })
            updated_corner = saved_assembly["rows"][0]
            if (updated_corner["chipIndex"] != 511 or updated_corner["paletteIndex"] != 6
                    or updated_corner["unknownPriorityBits"] != 0xA0
                    or saved_assembly["trailingBytes"] != 1):
                raise RuntimeError("Tile assembly edit did not preserve unknown priority bits")
            exported = request_json(session.url + "api/export", {})
            if not exported.get("replacementOnly"):
                raise RuntimeError("CTP export did not assert replacement-only loader compatibility")
            with zipfile.ZipFile(exported["path"]) as ctp:
                if set(ctp.namelist()) != {"Localize/en/msg/cmes0.txt", "Game/chara/dat/c005.dat", "Game/chara/cell/c005.cel", "Game/field/Mapinfo/mapinfo_1.dat", "Game/field/MapTable/MapTable_0006.dat", "Game/field/palette_bin/plt4.bin", "Game/field/BGAnime/bganimeinfo_4.dat", "Game/field/BGSetTable/bgsettable_4.dat", "Game/field/ChipTable/ChipTable_0004.dat", "Game/common/MapJumpDataTbl.dat", "Game/common/TakaraDataTbl.dat", BANK_PATH, "Game/world/Map/Map_0000.dat", "Game/world/Id/Id_0000.dat", "Game/world/SeId/SeId_0000.dat", "Game/world/colanim_bin/0_colanim.bin", "Game/world/EventTable/EventTable_0004.dat"}:
                    raise RuntimeError("CTP export did not contain exactly the changed resources")
        if (game / "resources.bin").read_bytes() != original_archive:
            raise RuntimeError("Fresh Chrono Trigger plugin modified resources.bin")
    return [
        "read-only ARC1 source archive validated",
        "keyed Steam text edit survived project-overlay readback",
        "fixed 24-byte area settings edit preserved the unmodelled word and trailing bytes",
        "scene map tile edits preserved the header, RLE property stream and existing tile banks",
        "scene RLE property-run edit preserved compression, repeat counts and unknown bits",
        "scene render settings edit preserved dimensions, scroll-mode bits and the unknown effect bit",
        "256-color RGB555 palette edit preserved prefix, bit 15 and trailing bytes",
        "fixed-size area exit edit preserved unknown flag bits",
        "treasure edit preserved the unknown trailing word",
        "fixed 23-byte world header edit preserved the PC-unused palette-animation byte and surrounding bank data",
        "fixed world map layers preserved layer ranges and trailing bytes",
        "world property/music nibble edits preserved adjacent values and file shape",
        "world palette-animation color edit preserved RGB555 bit 15 and trailing bytes",
        "fixed-size world exit/trigger edits preserved semantics, unknown bits and non-editable blocks",
        "fixed-count chip animation edit preserved unknown duration bits and trailing bytes",
        "sprite descriptor edit preserved PC-ignored references and unknown bytes",
        "sprite assembly edit preserved frame/tile counts, weird source bit and unknown flags",
        "fixed tileset graphics references preserved sentinels and trailing bytes",
        "fixed tile assembly edit preserved unknown priority bits and trailing bytes",
        "deterministic CTP export contained only changed archive-relative resources",
        "installed resources.bin remained byte-identical",
    ]


PLUGIN = GamePlugin(
    **plugin_defaults(__file__),
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=ChronoTriggerSession,
    mod_adapter=ChronoCtpAdapter(),
    projects=project_spec(__file__, default_root=paths.PROJECT_ROOT, initialize=initialize_project),
    installation=install_spec(__file__),
)
