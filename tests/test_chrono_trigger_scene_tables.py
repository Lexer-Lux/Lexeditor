from __future__ import annotations

import gzip
from pathlib import Path
import struct
import tempfile
import unittest

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.resources import ResourceArchive
from games.chrono_trigger.scene_tables import (
    EXIT_DATA,
    TREASURE_DATA,
    load_exits,
    load_treasure,
    save_exit,
    save_treasure,
)


def _build_archive(path: Path, resources: list[tuple[str, bytes]]) -> None:
    offset = 16
    blocks = []
    records = []
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
    path.write_bytes(
        ResourceArchive.decode(header, 0)
        + b"".join(blocks)
        + ResourceArchive.decode(encoded_index, index_offset)
    )


def _fixture(root: Path) -> OverlayStore:
    exit_offsets = struct.pack("<IHH", 2, 0, 1)
    exit_data = b"HEAD" + struct.pack("<BBBBHBB", 2, 3, 0x82, 0x0B, 7, 8, 9) + struct.pack(
        "<BBBBHBB", 10, 11, 0x00, 0x01, 12, 13, 14
    )
    treasure_offsets = struct.pack("<IHHH", 3, 0, 1, 2)
    treasure_data = b"HEAD" + struct.pack("<BBHH", 4, 5, 0x800A, 0x1234) + struct.pack(
        "<BBHH", 6, 7, 0x3002, 0x5678
    )
    archive_path = root / "resources.bin"
    _build_archive(archive_path, [
        ("Game/common/MapJumpOffsetTbl.dat", exit_offsets),
        ("Game/common/MapJumpDataTbl.dat", exit_data),
        ("Game/common/TakaraOffsetTbl.dat", treasure_offsets),
        ("Game/common/TakaraDataTbl.dat", treasure_data),
    ])
    return OverlayStore(archive_path, root / "project")


class SceneTableTests(unittest.TestCase):
    def test_pc_exit_record_decodes_trigger_and_destination(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-scene-") as temp_name:
            store = _fixture(Path(temp_name))
            data = load_exits(store, 0)
            self.assertEqual(len(data["rows"]), 1)
            row = data["rows"][0]
            self.assertEqual(row["values"]["destination"], 7)
            self.assertEqual(row["derived"]["orientation"], "vertical")
            self.assertEqual(row["derived"]["spanTiles"], 3)
            self.assertEqual(row["derived"]["facing"], "Right")
            self.assertEqual(row["derived"]["shiftX"], 0)
            self.assertEqual(row["derived"]["shiftY"], -8)

    def test_exit_edit_writes_only_project_data_table(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-scene-") as temp_name:
            root = Path(temp_name)
            store = _fixture(root)
            opened = load_exits(store, 0)
            saved = save_exit(
                store, 0, 0, opened["offsetSha256"], opened["dataSha256"],
                {"destination": 99, "tileX": 20},
            )
            self.assertEqual(saved["source"], "project")
            self.assertEqual(saved["rows"][0]["values"]["destination"], 99)
            self.assertTrue((root / "project" / EXIT_DATA).is_file())
            vanilla = load_exits(store, 0, "vanilla")
            self.assertEqual(vanilla["rows"][0]["values"]["destination"], 7)

    def test_pc_treasure_decodes_gold_and_item_categories(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-scene-") as temp_name:
            store = _fixture(Path(temp_name))
            gold = load_treasure(store, 0)["rows"][0]
            accessory = load_treasure(store, 1)["rows"][0]
            self.assertEqual(gold["derived"]["kind"], "gold")
            self.assertEqual(gold["derived"]["gold"], 20)
            self.assertEqual(accessory["derived"]["kind"], "accessory")
            self.assertEqual(accessory["derived"]["itemId"], 202)

    def test_treasure_edit_writes_only_project_data_table(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-scene-") as temp_name:
            root = Path(temp_name)
            store = _fixture(root)
            opened = load_treasure(store, 1)
            saved = save_treasure(
                store, 1, 0, opened["offsetSha256"], opened["dataSha256"],
                {"contents": 0x8014, "unknown": 0xABCD},
            )
            row = saved["rows"][0]
            self.assertEqual(row["derived"]["kind"], "gold")
            self.assertEqual(row["derived"]["gold"], 40)
            self.assertEqual(row["values"]["unknown"], 0xABCD)
            self.assertTrue((root / "project" / TREASURE_DATA).is_file())
            vanilla = load_treasure(store, 1, "vanilla")["rows"][0]
            self.assertEqual(vanilla["derived"]["kind"], "accessory")

    def test_fixed_count_saves_reject_stale_shared_tables(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-scene-") as temp_name:
            root = Path(temp_name)
            store = _fixture(root)
            opened = load_exits(store, 0)
            target = root / "project" / EXIT_DATA
            target.parent.mkdir(parents=True)
            target.write_bytes(store.read(EXIT_DATA, "vanilla")[0] + b"changed")
            with self.assertRaises(RuntimeError):
                save_exit(
                    store, 0, 0, opened["offsetSha256"], opened["dataSha256"],
                    {"destination": 9},
                )


if __name__ == "__main__":
    unittest.main()
