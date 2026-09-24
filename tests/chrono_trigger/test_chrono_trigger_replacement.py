from __future__ import annotations

import gzip
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from plugins.chrono_trigger.archive import ArchiveError, ResourcesBin, _decode
from plugins.chrono_trigger.animation_data import load_chip_animations, save_chip_animations
from plugins.chrono_trigger.field_data import load_exits, load_treasure, save_exits, save_treasure
from plugins.chrono_trigger.mod_support import ChronoCtpAdapter, OWNED_NAMESPACE
from core.mod_library import ModLibrary, file_tree
from plugins.chrono_trigger.palette_data import load_palette, save_palette
from plugins.chrono_trigger.project import OverlayStore
from plugins.chrono_trigger.scene_data import load_scenes, save_scene
from plugins.chrono_trigger.scene_map_data import (load_scene_map, save_scene_map, load_scene_properties, save_scene_properties,
    load_scene_render_settings, save_scene_render_settings)
from plugins.chrono_trigger.sprite_data import load_sprite_headers, save_sprite_header
from plugins.chrono_trigger.sprite_assembly_data import load_sprite_assemblies, save_sprite_assembly
from plugins.chrono_trigger.text_data import load_messages, save_messages
from plugins.chrono_trigger.tileset_data import load_graphics_sets, save_graphics_set, load_tile_assemblies, save_tile_assembly
from plugins.chrono_trigger.world_data import (
    BANK_PATH, HEADER_OFFSET, HEADER_SIZE, WORLD_COUNT, load_worlds, save_worlds,
)
from plugins.chrono_trigger.world_navigation import load_world_navigation, save_world_navigation
from plugins.chrono_trigger.world_map_data import (
    load_world_tiles, save_world_tiles, load_world_properties, save_world_properties,
    load_world_music, save_world_music, load_world_colors, save_world_colors,
)


def build_archive(path: Path, resources: list[tuple[str, bytes]]) -> None:
    offset = 16
    blocks = []
    rows = []
    for name, payload in resources:
        plain = len(payload).to_bytes(4, "big") + gzip.compress(payload, mtime=0)
        encoded = _decode(offset, plain)
        blocks.append(encoded)
        rows.append((name, offset, len(encoded)))
        offset += len(encoded)
    table_size = 4 + len(rows) * 12
    strings = bytearray()
    name_offsets = []
    for name, _, _ in rows:
        name_offsets.append(table_size + len(strings))
        strings.extend(name.encode() + b"\0")
    index = bytearray(struct.pack("<I", len(rows)))
    for name_offset, (_, entry_offset, size) in zip(name_offsets, rows):
        index.extend(struct.pack("<III", name_offset, entry_offset, size))
    index.extend(strings)
    plain_index = len(index).to_bytes(4, "big") + gzip.compress(bytes(index), mtime=0)
    encoded_index = _decode(offset, plain_index)
    total = offset + len(encoded_index)
    header = _decode(0, b"ARC1" + struct.pack("<III", total, offset, len(encoded_index)))
    path.write_bytes(header + b"".join(blocks) + encoded_index)


class FreshChronoTriggerTests(unittest.TestCase):
    def fixture(self, root: Path):
        archive = root / "resources.bin"
        palette = b"\x12\x34" + struct.pack("<H", 0x801F) + (b"\x00\x00" * 255) + b"\xCC"
        bank = bytearray(b"\xA5" * (HEADER_OFFSET + WORLD_COUNT * HEADER_SIZE + 3))
        bank[HEADER_OFFSET:HEADER_OFFSET + HEADER_SIZE] = bytes(range(HEADER_SIZE))
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
        build_archive(archive, [
            ("Localize/en/msg/item.txt", b"0000,Sword\r\n0001,Armor\r\n0002,Mail\r\n"),
            ("Localize/en/msg/cmes0.txt", b"FLD_1,Hello, traveler\r\nFLD_2,World\r\n"),
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
            ("Game/field/Mapinfo/mapinfo_1.dat", struct.pack("<10H4B", 10, 1, 2, 3, 4, 5, 6, 7, 8, 0xBEEF, 0, 1, 14, 15) + b"\xAA\xBB"),
            ("Game/field/palette_bin/plt4.bin", palette),
            ("Game/common/MapJumpOffsetTbl.dat", struct.pack("<IHH", 2, 0, 1)),
            ("Game/common/MapJumpDataTbl.dat", b"HEAD" + struct.pack("<BBBBHBB", 2, 3, 1, 0xA5, 7, 8, 9)),
            ("Game/common/TakaraOffsetTbl.dat", struct.pack("<IHH", 2, 0, 1)),
            ("Game/common/TakaraDataTbl.dat", b"HEAD" + struct.pack("<BBHH", 4, 5, 0x1002, 0xCAFE)),
            (BANK_PATH, bytes(bank)),
        ])
        source = ResourcesBin(archive)
        store = OverlayStore(source, root / "project")
        return archive, store

    def test_arc1_validates_declared_file_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, _ = self.fixture(root)
            payload = bytearray(archive.read_bytes())
            header = bytearray(_decode(0, payload[:16]))
            struct.pack_into("<I", header, 4, len(payload) + 1)
            payload[:16] = _decode(0, bytes(header))
            archive.write_bytes(payload)
            with self.assertRaises(ArchiveError):
                ResourcesBin(archive)

    def test_text_edit_preserves_key_commas_and_crlf(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, store = self.fixture(Path(tmp))
            data = load_messages(store, "Localize/en/msg/cmes0.txt")
            self.assertEqual(data["rows"][0]["text"], "Hello, traveler")
            saved = save_messages(store, data["path"], data["sha256"], [{"line": 0, "key": "FLD_1", "text": "Changed, still one record"}])
            self.assertEqual(saved["rows"][0]["text"], "Changed, still one record")
            raw, source = store.read(data["path"])
            self.assertEqual(source, "project")
            self.assertIn(b"FLD_1,Changed, still one record\r\n", raw)

    def test_scene_edit_preserves_unknown_word_trailing_bytes_and_vanilla(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original = archive.read_bytes()
            scenes = load_scenes(store, language="en")
            row = scenes["rows"][0]
            self.assertEqual((row["id"], row["name"], row["unknownWord"], row["trailingBytes"]), (1, "Millennial Fair", 0xBEEF, 2))
            saved = save_scene(store, row["id"], row["sha256"], {"musicIndex": 42, "cameraUnbounded": True}, "en")
            self.assertEqual(saved["musicIndex"], 42)
            self.assertTrue(saved["cameraUnbounded"])
            self.assertEqual(saved["unknownWord"], 0xBEEF)
            self.assertEqual(saved["trailingBytes"], 2)
            project_bytes, _ = store.read(row["path"], "mine")
            self.assertEqual(project_bytes[-2:], b"\xAA\xBB")
            self.assertEqual(archive.read_bytes(), original)

    def test_palette_edit_preserves_prefix_high_bit_trailing_and_vanilla(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original = archive.read_bytes()
            path = "Game/field/palette_bin/plt4.bin"
            data = load_palette(store, path)
            self.assertEqual((data["rows"][0]["hex"], data["prefixHex"], data["trailingBytes"]), ("#FF0000", "1234", 1))
            self.assertTrue(data["rows"][0]["preservedBit15"])
            saved = save_palette(store, path, data["sha256"], [{"token": "0", "hex": "#00FF00"}])
            self.assertEqual(saved["rows"][0]["hex"], "#00FF00")
            self.assertTrue(saved["rows"][0]["preservedBit15"])
            raw, _ = store.read(path, "mine")
            self.assertEqual(raw[:2], b"\x12\x34")
            self.assertEqual(raw[-1:], b"\xCC")
            self.assertTrue(struct.unpack_from("<H", raw, 2)[0] & 0x8000)
            self.assertEqual(archive.read_bytes(), original)

    def test_exit_edit_preserves_unknown_bits_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original = archive.read_bytes()
            data = load_exits(store)
            row = data["rows"][0]
            self.assertEqual(row["unknownFacingBits"], 0xA0)
            saved = save_exits(store, data["dataSha256"], data["offsetSha256"], [{"token": row["token"], "values": {"destinationId": 0x1F0, "facing": 2, "halfTileLeft": False}}])
            updated = saved["rows"][0]
            self.assertEqual(updated["destinationKind"], "world")
            self.assertEqual(updated["unknownFacingBits"], 0xA0)
            self.assertEqual(archive.read_bytes(), original)

    def test_treasure_edit_preserves_trailing_word_and_rejects_alias_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, store = self.fixture(Path(tmp))
            data = load_treasure(store)
            row = data["rows"][0]
            self.assertEqual(row["trailingWord"], 0xCAFE)
            saved = save_treasure(store, data["dataSha256"], data["offsetSha256"], [{"token": row["token"], "values": {"kind": "gold", "gold": 200}}])
            self.assertEqual(saved["rows"][0]["gold"], 200)
            self.assertEqual(saved["rows"][0]["trailingWord"], 0xCAFE)
            with self.assertRaises(ValueError):
                save_treasure(store, saved["dataSha256"], saved["offsetSha256"], [{"token": row["token"], "values": {"xTile": 0, "yTile": 0}}])

    def test_world_header_edit_changes_only_selected_documented_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            data = load_worlds(store)
            row = data["rows"][0]
            self.assertEqual((row["paletteIndex"], row["paletteAnimationIndex"], row["mapIndex"], row["scriptIndex"]),
                             (10, 11, 17, 22))
            before, _ = store.read(BANK_PATH, "mine")
            saved = save_worlds(store, data["sha256"], [{
                "token": "0", "values": {"paletteIndex": 200, "mapIndex": 201, "scriptIndex": 202},
            }])
            self.assertEqual((saved["rows"][0]["paletteIndex"], saved["rows"][0]["mapIndex"], saved["rows"][0]["scriptIndex"]),
                             (200, 201, 202))
            self.assertEqual(saved["rows"][0]["paletteAnimationIndex"], 11)
            after, origin = store.read(BANK_PATH, "mine")
            self.assertEqual(origin, "project")
            changed = [index for index, (left, right) in enumerate(zip(before, after)) if left != right]
            self.assertEqual(changed, [HEADER_OFFSET + 10, HEADER_OFFSET + 17, HEADER_OFFSET + 22])
            self.assertEqual(archive.read_bytes(), original_archive)
            with self.assertRaises(ValueError):
                save_worlds(store, saved["sha256"], [{"token": "0", "values": {"paletteAnimationIndex": 3}}])

    def test_scene_map_tile_edit_preserves_header_rle_properties_and_tile_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            path = "Game/field/MapTable/MapTable_0006.dat"
            data = load_scene_map(store, path)
            self.assertEqual((data["layer1Width"], data["layer1Height"], data["layer2Width"],
                              data["layer2Height"], data["layer3Enabled"], data["propertyBytes"]),
                             (16, 16, 16, 16, False, 7))
            layer1 = next(row for row in data["rows"] if row["token"] == "6:1:0")
            layer2 = next(row for row in data["rows"] if row["token"] == "6:2:0")
            self.assertEqual((layer1["storedTile"], layer1["upperBank"], layer1["tileIndex"]), (3, True, 259))
            self.assertEqual((layer2["storedTile"], layer2["upperBank"], layer2["tileIndex"]), (4, False, 4))
            before, _ = store.read(path, "mine")
            saved = save_scene_map(store, path, data["sha256"], [
                {"token": layer1["token"], "values": {"tileIndex": 300}},
                {"token": layer2["token"], "values": {"tileIndex": 9}},
            ])
            by_token = {row["token"]: row for row in saved["rows"]}
            self.assertEqual((by_token[layer1["token"]]["tileIndex"], by_token[layer2["token"]]["tileIndex"]), (300, 9))
            after, origin = store.read(path, "mine")
            self.assertEqual(origin, "project")
            self.assertEqual(after[:6], before[:6])
            self.assertEqual(after[data["propertyOffset"]:], before[data["propertyOffset"]:])
            changed = [index for index, (left, right) in enumerate(zip(before, after)) if left != right]
            self.assertEqual(changed, [6, 6 + 16 * 16])
            self.assertEqual(archive.read_bytes(), original_archive)
            with self.assertRaisesRegex(ValueError, "existing 256-511 bank"):
                save_scene_map(store, path, saved["sha256"], [
                    {"token": layer1["token"], "values": {"tileIndex": 9}},
                ])

    def test_scene_render_settings_preserve_dimension_byte_and_unknown_effect_bit(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            path = "Game/field/MapTable/MapTable_0006.dat"
            data = load_scene_render_settings(store, path)
            self.assertEqual((data["scrollL2XCode"], data["scrollL2YCode"], data["scrollL2XSpeed"],
                              data["scrollL3XCode"], data["scrollL3YCode"]),
                             (1, 2, 3.75, 3, 4))
            self.assertEqual((data["layer1Main"], data["layer2Main"], data["spritesMain"],
                              data["layer1Sub"], data["layer3Sub"]),
                             (False, True, True, True, True))
            self.assertTrue(data["unknownEffectBit3"])
            self.assertEqual((data["preservedBitsByte"], data["scrollModeBits"], data["layer3Enabled"]), (0, 0, False))
            before, _ = store.read(path, "mine")
            saved = save_scene_render_settings(store, path, data["sha256"], {
                "scrollL2XCode": 7, "scrollL2YCode": 15,
                "scrollL3XCode": 8, "scrollL3YCode": 1,
                "layer1Main": True, "layer2Main": False, "layer3Main": True, "spritesMain": False,
                "layer1Sub": True, "layer2Sub": False, "layer3Sub": True, "spritesSub": False,
                "effectLayer1": False, "effectLayer2": True, "effectLayer3": True,
                "effectSprites": True, "effectDefaultColor": False,
                "effectHalfIntensity": True, "effectSubtract": False,
            })
            self.assertEqual((saved["scrollL2XSpeed"], saved["scrollL2YSpeed"],
                              saved["scrollL3XSpeed"], saved["scrollL3YSpeed"]),
                             (240.0, -240.0, -0.0, 3.75))
            self.assertTrue(saved["unknownEffectBit3"])
            after, origin = store.read(path, "mine")
            self.assertEqual(origin, "project")
            self.assertEqual(after[:2], before[:2])
            self.assertEqual(after[6:], before[6:])
            self.assertTrue(after[5] & 0x08)
            self.assertEqual(after[4], 0x55)
            self.assertEqual(after[5], 0x5E)
            self.assertEqual(archive.read_bytes(), original_archive)

    def test_scene_property_run_edit_preserves_rle_repeat_and_unknown_bits(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            path = "Game/field/MapTable/MapTable_0006.dat"
            data = load_scene_properties(store, path)
            self.assertEqual((data["expectedTiles"], data["expandedTiles"], data["trailingPropertyBytes"]),
                             (256, 256, 0))
            row = next(value for value in data["rows"] if value["token"] == "6:prop:1")
            self.assertEqual((row["compressed"], row["repeatCount"], row["startTile"], row["endTile"],
                              row["unknownSecondBit5"], row["unknownThirdBit4"]),
                             (True, 255, 1, 255, True, True))
            before, _ = store.read(path, "mine")
            saved = save_scene_properties(store, path, data["sha256"], [{
                "token": row["token"], "values": {
                    "collisionCode": 30, "moveDirection": 3, "moveSpeed": 2,
                    "doorTrigger": True, "priorityTop": True, "npcCollisionBattle": True,
                    "zPlane": 2, "collisionIgnoreZ": True, "collisionInverted": True,
                    "zNeutral": True, "priorityBottom": True, "npcCollision": True,
                },
            }])
            updated = next(value for value in saved["rows"] if value["token"] == row["token"])
            self.assertEqual((updated["collisionCode"], updated["collisionName"], updated["moveDirectionName"],
                              updated["moveSpeed"], updated["zPlane"]),
                             (30, "Ladder", "West", 2, 2))
            after, origin = store.read(path, "mine")
            self.assertEqual(origin, "project")
            self.assertEqual(after[:row["byteOffset"]], before[:row["byteOffset"]])
            self.assertEqual(after[row["byteOffset"] + 3:], before[row["byteOffset"] + 3:])
            self.assertTrue(after[row["byteOffset"]] & 0x80)
            self.assertTrue(after[row["byteOffset"] + 1] & 0x20)
            self.assertTrue(after[row["byteOffset"] + 2] & 0x10)
            self.assertEqual(after[row["byteOffset"] + 3], 255)
            self.assertEqual(archive.read_bytes(), original_archive)
            with self.assertRaisesRegex(ValueError, "documented code 0 through 30"):
                save_scene_properties(store, path, saved["sha256"], [{
                    "token": row["token"], "values": {"collisionCode": 31},
                }])

    def test_sprite_assembly_edit_preserves_counts_weird_bit_unknown_flags_and_other_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            data = load_sprite_assemblies(store)
            row = next(value for value in data["rows"] if value["token"] == "5:0:0")
            meta = data["files"][0]
            self.assertEqual((meta["frameCount"], meta["headerWord"], meta["prefixHex"], meta["trailingBytes"]),
                             (2, 0xBEEF, "AABBCC", 1))
            self.assertEqual((row["frameTileCount"], row["chipIndex"], row["weirdSourceBit"],
                              row["x"], row["y"], row["isTop"], row["flipHorizontal"], row["unknownFlags"]),
                             (2, 300, True, -5, -25, True, True, 0xA0))
            before, _ = store.read(row["path"], "mine")
            saved = save_sprite_assembly(store, row["path"], row["sha256"], [{
                "token": row["token"],
                "values": {"chipIndex": 511, "x": 7, "y": -10, "flipHorizontal": False},
            }])
            updated = next(value for value in saved["rows"] if value["token"] == row["token"])
            self.assertEqual((updated["chipIndex"], updated["weirdSourceBit"], updated["x"], updated["y"],
                              updated["flipHorizontal"], updated["unknownFlags"]),
                             (511, True, 7, -10, False, 0xA0))
            after, origin = store.read(row["path"], "mine")
            self.assertEqual(origin, "project")
            self.assertEqual(after[:8], before[:8])
            self.assertEqual(after[13:], before[13:])
            self.assertTrue(struct.unpack_from("<H", after, 8)[0] & 0x0008)
            self.assertEqual(after[12], 0xA0)
            self.assertEqual(archive.read_bytes(), original_archive)
            with self.assertRaisesRegex(ValueError, "Unsupported sprite assembly"):
                save_sprite_assembly(store, row["path"], saved["sha256"], [{
                    "token": row["token"], "values": {"weirdSourceBit": False},
                }])

    def test_sprite_descriptor_edit_preserves_pc_ignored_references_and_unknown_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            data = load_sprite_headers(store)
            row = next(value for value in data["rows"] if value["id"] == 5)
            self.assertEqual((row["storedBitmapIndex"], row["storedAssemblyIndex"], row["storedPaletteIndex"]),
                             (9, 8, 7))
            self.assertEqual((row["sizeGroupCode"], row["primaryEnemy"], row["unknownSizeFlags"],
                              row["animationIndex"], row["unknownFlags"]), (0, True, 0xA4, 5, 0xD2))
            self.assertEqual((row["enemyDescriptor"], row["handX"], row["handY"],
                              row["enemyUnknown1"], row["enemyUnknown2"], row["enemyUnknown3"],
                              row["trailingBytes"]), (True, -2, 3, 0x11, 0x22, 0x33, 1))
            before, _ = store.read(row["path"], "mine")
            saved = save_sprite_header(store, row["path"], row["sha256"], {
                "sizeGroupCode": 2, "primaryEnemy": False, "animationIndex": 9,
                "handX": -8, "handY": 12,
            })
            self.assertEqual((saved["sizeGroupCode"], saved["primaryEnemy"], saved["animationIndex"],
                              saved["handX"], saved["handY"], saved["unknownSizeFlags"]),
                             (2, False, 9, -8, 12, 0xA4))
            after, origin = store.read(row["path"], "mine")
            self.assertEqual(origin, "project")
            self.assertEqual(after[:3], before[:3])
            self.assertEqual(after[3], 0xA6)
            self.assertEqual(after[4], 9)
            self.assertEqual(after[5], before[5])
            self.assertEqual(after[8:], before[8:])
            self.assertEqual(archive.read_bytes(), original_archive)
            with self.assertRaisesRegex(ValueError, "Unsupported sprite descriptor"):
                save_sprite_header(store, row["path"], saved["sha256"], {"enemyUnknown1": 0})

    def test_graphics_set_edit_preserves_sentinel_shape_trailing_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            data = load_graphics_sets(store)
            row = data["rows"][0]
            self.assertEqual(([row[f"graphicsSet{i}"] for i in range(8)], row["trailingBytes"]),
                             ([1, 2, 3, 4, 5, 6, 7, 255], 1))
            before, _ = store.read(row["path"], "mine")
            saved = save_graphics_set(store, row["path"], row["sha256"], {
                "graphicsSet0": 9, "graphicsSet7": 8,
            })
            self.assertEqual((saved["graphicsSet0"], saved["graphicsSet7"], saved["trailingBytes"]),
                             (9, 8, 1))
            after, origin = store.read(row["path"], "mine")
            self.assertEqual(origin, "project")
            self.assertEqual(after[1:7], before[1:7])
            self.assertEqual(after[-1:], b"\xDD")
            self.assertEqual(len(after), len(before))
            self.assertEqual(archive.read_bytes(), original_archive)

    def test_tile_assembly_edit_preserves_unknown_priority_bits_and_other_corners(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            data = load_tile_assemblies(store)
            self.assertEqual({(file["kind"], file["tileCount"]) for file in data["files"]},
                             {("layer12", 512), ("layer3", 256)})
            row = next(value for value in data["rows"] if value["token"] == "layer12:4:0:0")
            self.assertEqual((row["chipIndex"], row["paletteIndex"], row["flipHorizontal"],
                              row["flipVertical"], row["priority"], row["unknownPriorityBits"],
                              row["fileTrailingBytes"]), (300, 5, True, False, True, 0xA0, 1))
            before, _ = store.read(row["path"], "mine")
            saved = save_tile_assembly(store, row["path"], row["sha256"], [{
                "token": row["token"], "values": {
                    "chipIndex": 511, "paletteIndex": 6, "flipHorizontal": False,
                    "flipVertical": True, "priority": False,
                },
            }])
            updated = saved["rows"][0]
            self.assertEqual((updated["chipIndex"], updated["paletteIndex"], updated["flipHorizontal"],
                              updated["flipVertical"], updated["priority"], updated["unknownPriorityBits"]),
                             (511, 6, False, True, False, 0xA0))
            after, origin = store.read(row["path"], "mine")
            self.assertEqual(origin, "project")
            self.assertEqual(after[3:], before[3:])
            self.assertEqual(after[-1:], b"\xCC")
            self.assertEqual(len(after), len(before))
            self.assertEqual(archive.read_bytes(), original_archive)

    def test_chip_animation_edit_preserves_counts_low_nibbles_and_later_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            data = load_chip_animations(store)
            self.assertEqual(len(data["rows"]), 2)
            row = data["rows"][0]
            meta = data["files"][0]
            self.assertEqual((row["frameCount"], row["destinationChip"], row["durationCode0"],
                              row["durationLowBits0"], row["sourceChip1"]), (2, 2, 0x10, 0x0A, 4))
            self.assertEqual((meta["declaredCount"], meta["parsedCount"], meta["trailingBytes"]), (2, 2, 1))
            before, _ = store.read(row["path"], "mine")
            saved = save_chip_animations(store, row["path"], row["sha256"], [{
                "token": row["token"],
                "values": {"destinationChip": 7, "durationCode0": 0x20, "sourceChip1": 9},
            }])
            updated = saved["rows"][0]
            self.assertEqual((updated["destinationChip"], updated["durationCode0"],
                              updated["durationTicks0"], updated["durationLowBits0"],
                              updated["sourceChip1"]), (7, 0x20, 12, 0x0A, 9))
            after, origin = store.read(row["path"], "mine")
            self.assertEqual(origin, "project")
            self.assertEqual(after[4] & 0x0F, before[4] & 0x0F)
            self.assertEqual(after[10:], before[10:])
            self.assertEqual(len(after), len(before))
            self.assertEqual(archive.read_bytes(), original_archive)
            with self.assertRaises(ValueError):
                save_chip_animations(store, row["path"], saved["sha256"], [{
                    "token": row["token"], "values": {"durationCode0": 0x30},
                }])

    def test_world_map_tile_edit_changes_only_selected_layer_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            path = "Game/world/Map/Map_0000.dat"
            data = load_world_tiles(store, path)
            layer1 = data["rows"][0]
            layer2 = data["rows"][96 * 64]
            self.assertEqual((layer1["tileIndex"], layer2["tileIndex"], data["trailingBytes"]), (3, 260, 1))
            before, _ = store.read(path, "mine")
            saved = save_world_tiles(store, path, data["sha256"], [
                {"token": layer1["token"], "values": {"tileIndex": 9}},
                {"token": layer2["token"], "values": {"tileIndex": 300}},
            ])
            self.assertEqual((saved["rows"][0]["tileIndex"], saved["rows"][96 * 64]["tileIndex"]), (9, 300))
            after, origin = store.read(path, "mine")
            self.assertEqual(origin, "project")
            changed = [index for index, (left, right) in enumerate(zip(before, after)) if left != right]
            self.assertEqual(changed, [0, 96 * 64])
            self.assertEqual(after[-1:], b"\xFA")
            self.assertEqual(archive.read_bytes(), original_archive)
            with self.assertRaises(ValueError):
                save_world_tiles(store, path, saved["sha256"], [
                    {"token": layer2["token"], "values": {"tileIndex": 255}},
                ])

    def test_world_property_edit_preserves_other_nibbles_and_trailing(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            path = "Game/world/Id/Id_0000.dat"
            data = load_world_properties(store, path)
            row = data["rows"][0]
            self.assertEqual((row["topLeft"], row["topRight"], row["bottomLeft"], row["bottomRight"],
                              data["trailingBytes"]), (1, 2, 3, 4, 1))
            before, _ = store.read(path, "mine")
            saved = save_world_properties(store, path, data["sha256"], [{
                "token": row["token"], "values": {"topLeft": 4},
            }])
            self.assertEqual((saved["rows"][0]["topLeft"], saved["rows"][0]["topRight"],
                              saved["rows"][0]["bottomLeft"], saved["rows"][0]["bottomRight"]),
                             (4, 2, 3, 4))
            after, _ = store.read(path, "mine")
            self.assertEqual(after[0], 0x42)
            self.assertEqual(after[1:], before[1:])
            self.assertEqual(after[-1:], b"\xFB")
            self.assertEqual(archive.read_bytes(), original_archive)
            with self.assertRaises(ValueError):
                save_world_properties(store, path, saved["sha256"], [{
                    "token": row["token"], "values": {"topLeft": 7},
                }])

    def test_world_music_edit_preserves_other_nibble_and_trailing(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            path = "Game/world/SeId/SeId_0000.dat"
            data = load_world_music(store, path)
            row = data["rows"][0]
            self.assertEqual((row["xTile"], row["yTile"], row["leftMusic"], row["rightMusic"],
                              data["trailingBytes"]), (0, 0, 10, 5, 1))
            before, _ = store.read(path, "mine")
            saved = save_world_music(store, path, data["sha256"], [{
                "token": row["token"], "values": {"rightMusic": 9},
            }])
            self.assertEqual((saved["rows"][0]["leftMusic"], saved["rows"][0]["rightMusic"]), (10, 9))
            after, _ = store.read(path, "mine")
            self.assertEqual(after[0], 0xA9)
            self.assertEqual(after[1:], before[1:])
            self.assertEqual(after[-1:], b"\xFC")
            self.assertEqual(archive.read_bytes(), original_archive)

    def test_world_animation_color_edit_preserves_bit15_and_odd_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            path = "Game/world/colanim_bin/0_colanim.bin"
            data = load_world_colors(store, path)
            self.assertEqual((data["rows"][0]["hex"], data["rows"][0]["preservedBit15"],
                              data["trailingBytes"]), ("#FF0000", True, 1))
            saved = save_world_colors(store, path, data["sha256"], [{
                "token": "0", "hex": "#00FF00",
            }])
            self.assertEqual((saved["rows"][0]["hex"], saved["rows"][0]["preservedBit15"]),
                             ("#00FF00", True))
            raw, _ = store.read(path, "mine")
            self.assertTrue(struct.unpack_from("<H", raw, 0)[0] & 0x8000)
            self.assertEqual(raw[-1:], b"\xFD")
            self.assertEqual(archive.read_bytes(), original_archive)

    def test_world_navigation_edit_preserves_semantics_unknown_blocks_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, store = self.fixture(Path(tmp))
            original_archive = archive.read_bytes()
            data = load_world_navigation(store, language="en")
            self.assertEqual(len(data["rows"]), 3)
            normal = next(row for row in data["rows"] if row["token"] == "4:exit:0")
            scripted = next(row for row in data["rows"] if row["token"] == "4:exit:1")
            trigger = next(row for row in data["rows"] if row["token"] == "4:trigger:0")
            meta = data["files"][0]
            self.assertEqual((normal["name"], normal["unknownYBits"], normal["unknownFacingBits"]),
                             ("Truce Canyon", 0xC0, 0xA1))
            self.assertEqual((scripted["scripted"], scripted["scriptAddressIndex"]), (True, 1))
            self.assertEqual((meta["storedTriggerCount"], meta["triggerCount"], meta["unknownCount"],
                              meta["scriptAddressCount"], meta["trailingBytes"]), (2, 1, 1, 2, 2))
            before, _ = store.read(normal["path"], "mine")
            saved = save_world_navigation(store, normal["path"], normal["sha256"], [
                {"token": normal["token"], "values": {
                    "destinationScene": 33, "facing": 1, "halfTileLeft": False, "yTile": 6,
                }},
                {"token": trigger["token"], "values": {
                    "enabled": False, "scriptAddressIndex": 1,
                }},
            ], "en")
            by_token = {row["token"]: row for row in saved["rows"]}
            self.assertEqual((by_token[normal["token"]]["destinationScene"], by_token[normal["token"]]["facing"]),
                             (33, 1))
            self.assertEqual((by_token[normal["token"]]["unknownYBits"], by_token[normal["token"]]["unknownFacingBits"]),
                             (0xC0, 0xA1))
            self.assertFalse(by_token[trigger["token"]]["enabled"])
            self.assertEqual(by_token[trigger["token"]]["scriptAddressIndex"], 1)
            after, origin = store.read(normal["path"], "mine")
            self.assertEqual(origin, "project")
            # Sentinel, unknown third block, script addresses and trailing bytes are outside editable records.
            self.assertEqual(after[21:], before[21:])
            self.assertEqual(len(after), len(before))
            self.assertEqual(archive.read_bytes(), original_archive)
            with self.assertRaises(ValueError):
                save_world_navigation(store, normal["path"], saved["sha256"], [
                    {"token": normal["token"], "values": {"destinationScene": 0x1FF}},
                ], "en")
            with self.assertRaises(ValueError):
                save_world_navigation(store, normal["path"], saved["sha256"], [
                    {"token": scripted["token"], "values": {"destinationScene": 3}},
                ], "en")

    def test_shared_mod_library_reads_chrono_adapter_active_ids(self):
        from core.desktop_host import HostApi
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "library"
            mod = library_root / "chrono-trigger" / "Enabled"
            mod.mkdir(parents=True)
            (mod / "mod.json").write_text('{"name":"Enabled","version":"1"}\n', encoding="utf-8")
            calls = []
            adapter = SimpleNamespace(active_mod_ids=lambda game: calls.append(Path(game)) or ["Enabled"])
            host = HostApi.__new__(HostApi)
            host._plugins = {"chrono-trigger": SimpleNamespace(mod_adapter=adapter, managed_mod=None)}
            host._installations = SimpleNamespace(snapshot=lambda _plugin: {"root": str(root / "game")})
            host.mod_library_status = lambda _plugin: {
                "root": str(library_root), "verified": False, "canManage": True,
                "authorTest": True, "message": "fixture", "packageTypes": ["ctp"],
            }
            host._managed_mod_results = {}
            host._github = SimpleNamespace(visible_repository=lambda _repo: False)
            result = host.mod_library_entries("chrono-trigger")
            self.assertEqual(calls, [root / "game"])
            self.assertEqual([(row["name"], row["enabled"]) for row in result["entries"]],
                             [("Enabled", True)])

    def test_real_ctp_extension_import_becomes_editable_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "Example.ctp"
            replacement = b"0000,Imported Sword\r\n"
            with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("Localize/en/msg/item.txt", replacement)
            adapter = ChronoCtpAdapter()
            library = ModLibrary(root / "library")
            target = library.import_mod("chrono-trigger", package, adapter, "Imported", prepare_editable=True)
            self.assertEqual((target / "Localize/en/msg/item.txt").read_bytes(), replacement)
            self.assertTrue((target / "lexeditor-chrono-trigger.json").is_file())
            self.assertFalse(any(target.glob("*.ctp")))
            self.assertTrue(package.is_file())
            report = adapter.inspect(target, file_tree(target))
            self.assertTrue(report["valid"], report)
            self.assertEqual(report["resources"], ["Localize/en/msg/item.txt"])

    def test_ctext_adapter_orders_conflicts_preserves_external_entries_and_removes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            game.mkdir()
            (game / "Chrono Trigger.exe").write_bytes(b"fixture")
            (game / "ctext.dll").write_bytes(b"fixture")
            build_archive(game / "resources.bin", [
                ("Game/common/Test.dat", b"vanilla"),
                ("Localize/en/msg/item.txt", b"0000,Sword\r\n"),
            ])
            original_archive = (game / "resources.bin").read_bytes()
            config = {
                "misc": {"keep": "untouched"},
                "mods": {"enabled": True, "enable_ctp_loading": True,
                         "load_order": ["External"]},
            }
            (game / "ctext.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            mods = []
            for name, value in (("one", b"first"), ("two", b"second")):
                mod = root / name
                target = mod / "Game/common/Test.dat"
                target.parent.mkdir(parents=True)
                target.write_bytes(value)
                (mod / "mod.json").write_text(json.dumps({"name": name}) + "\n", encoding="utf-8")
                mods.append(mod)

            adapter = ChronoCtpAdapter()
            plan = adapter.activate(mods, game)
            self.assertEqual(plan["modIds"], ["one", "two"])
            self.assertEqual(plan["conflicts"], [{
                "path": "Game/common/Test.dat", "lower": "one", "higher": "two",
            }])
            self.assertEqual(plan["priority"],
                             "low-to-high; later selected Lexeditor CTP wins whole-resource conflicts")
            deployed = game / "mods" / OWNED_NAMESPACE
            with zipfile.ZipFile(deployed / "one.ctp") as archive:
                self.assertEqual(archive.read("Game/common/Test.dat"), b"first")
            with zipfile.ZipFile(deployed / "two.ctp") as archive:
                self.assertEqual(archive.read("Game/common/Test.dat"), b"second")
            active_config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            self.assertEqual(active_config["misc"], {"keep": "untouched"})
            self.assertEqual(active_config["mods"]["load_order"], [
                "External", f"{OWNED_NAMESPACE}/one", f"{OWNED_NAMESPACE}/two",
            ])
            self.assertEqual(adapter.active_mod_ids(game), ["one", "two"])

            # An external CTExt entry added later is preserved; Lexeditor's selected
            # CTPs are re-appended in explicit low-to-high priority order.
            active_config["mods"]["load_order"].append("UserLater")
            (game / "ctext.json").write_text(json.dumps(active_config, indent=2) + "\n", encoding="utf-8")
            narrowed = adapter.activate([mods[1]], game)
            self.assertEqual(narrowed["externalEntries"], ["External", "UserLater"])
            narrowed_config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            self.assertEqual(narrowed_config["mods"]["load_order"], [
                "External", "UserLater", f"{OWNED_NAMESPACE}/two",
            ])

            # Externally modifying a managed package blocks removal instead of
            # deleting somebody else's changes.
            managed = deployed / "two.ctp"
            original_managed = managed.read_bytes()
            managed.write_bytes(original_managed + b"external")
            with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                adapter.activate([], game)
            managed.write_bytes(original_managed)

            removed = adapter.activate([], game)
            self.assertEqual(removed["modIds"], [])
            final_config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            self.assertEqual(final_config["mods"]["load_order"], ["External", "UserLater"])
            self.assertEqual(adapter.active_mod_ids(game), [])
            self.assertEqual((game / "resources.bin").read_bytes(), original_archive)

    def test_ctp_rejects_paths_not_present_in_resources_bin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, store = self.fixture(root)
            added = root / "project" / "Game" / "common" / "NotARealResource.dat"
            added.parent.mkdir(parents=True, exist_ok=True)
            added.write_bytes(b"custom")
            with self.assertRaisesRegex(ValueError, "ignore unknown paths"):
                store.export_ctp(root / "project" / "build" / "invalid.ctp")

    def test_ctp_is_deterministic_and_excludes_redundant_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, store = self.fixture(root)
            message = load_messages(store, "Localize/en/msg/cmes0.txt")
            save_messages(store, message["path"], message["sha256"], [{"line": 1, "key": "FLD_2", "text": "Changed"}])
            first = store.export_ctp(root / "project" / "build" / "one.ctp")
            second = store.export_ctp(root / "project" / "build" / "two.ctp")
            self.assertTrue(first["replacementOnly"])
            self.assertEqual(Path(first["path"]).read_bytes(), Path(second["path"]).read_bytes())
            with zipfile.ZipFile(first["path"]) as archive:
                self.assertEqual(archive.namelist(), ["Localize/en/msg/cmes0.txt"])
                self.assertIn(b"FLD_2,Changed", archive.read("Localize/en/msg/cmes0.txt"))


if __name__ == "__main__":
    unittest.main()
