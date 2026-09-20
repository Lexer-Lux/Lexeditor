from __future__ import annotations

import gzip
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from games.chrono_trigger.archive import ArchiveError, ResourcesBin, _decode
from games.chrono_trigger.field_data import load_exits, load_treasure, save_exits, save_treasure
from games.chrono_trigger.project import OverlayStore
from games.chrono_trigger.text_data import load_messages, save_messages


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
        build_archive(archive, [
            ("Localize/en/msg/item.txt", b"0000,Sword\r\n0001,Armor\r\n0002,Mail\r\n"),
            ("Localize/en/msg/cmes0.txt", b"FLD_1,Hello, traveler\r\nFLD_2,World\r\n"),
            ("Game/common/MapJumpOffsetTbl.dat", struct.pack("<IHH", 2, 0, 1)),
            ("Game/common/MapJumpDataTbl.dat", b"HEAD" + struct.pack("<BBBBHBB", 2, 3, 1, 0xA5, 7, 8, 9)),
            ("Game/common/TakaraOffsetTbl.dat", struct.pack("<IHH", 2, 0, 1)),
            ("Game/common/TakaraDataTbl.dat", b"HEAD" + struct.pack("<BBHH", 4, 5, 0x1002, 0xCAFE)),
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

    def test_ctp_is_deterministic_and_excludes_redundant_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, store = self.fixture(root)
            message = load_messages(store, "Localize/en/msg/cmes0.txt")
            save_messages(store, message["path"], message["sha256"], [{"line": 1, "key": "FLD_2", "text": "Changed"}])
            first = store.export_ctp(root / "project" / "build" / "one.ctp")
            second = store.export_ctp(root / "project" / "build" / "two.ctp")
            self.assertEqual(Path(first["path"]).read_bytes(), Path(second["path"]).read_bytes())
            with zipfile.ZipFile(first["path"]) as archive:
                self.assertEqual(archive.namelist(), ["Localize/en/msg/cmes0.txt"])
                self.assertIn(b"FLD_2,Changed", archive.read("Localize/en/msg/cmes0.txt"))


if __name__ == "__main__":
    unittest.main()
