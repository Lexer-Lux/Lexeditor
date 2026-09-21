from __future__ import annotations

import gzip
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from games.chrono_trigger.archive import ArchiveError, ResourcesBin, _decode
from games.chrono_trigger.animation_data import load_chip_animations, save_chip_animations
from games.chrono_trigger.field_data import load_exits, load_treasure, save_exits, save_treasure
from games.chrono_trigger.palette_data import load_palette, save_palette
from games.chrono_trigger.project import OverlayStore
from games.chrono_trigger.scene_data import load_scenes, save_scene
from games.chrono_trigger.text_data import load_messages, save_messages
from games.chrono_trigger.world_data import (
    BANK_PATH, HEADER_OFFSET, HEADER_SIZE, WORLD_COUNT, load_worlds, save_worlds,
)
from games.chrono_trigger.world_navigation import load_world_navigation, save_world_navigation


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
        chip_animation = (
            bytes([2, 2]) + struct.pack("<H", 64) + bytes([0x1A, 0x4B])
            + struct.pack("<HH", 96, 128)
            + bytes([1]) + struct.pack("<H", 160) + bytes([0x80]) + struct.pack("<H", 192)
            + b"\xEE"
        )
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
            ("Game/world/EventTable/EventTable_0004.dat", world_event),
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
