from __future__ import annotations

import gzip
from pathlib import Path
import struct
import tempfile
import unittest

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.resources import ResourceArchive
from games.chrono_trigger.world_tables import (
    load_world_table,
    parse_world_table,
    save_world_exit,
    save_world_script_address,
    save_world_trigger,
)
from games.chrono_trigger.worlds import WORLD_BANK, WORLD_HEADER_OFFSET, WORLD_HEADER_SIZE


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
    path.write_bytes(ResourceArchive.decode(header, 0) + b"".join(blocks) + ResourceArchive.decode(encoded_index, index_offset))


def _event_table() -> bytes:
    data = bytearray()
    data.append(2)
    data.extend(struct.pack("<BBBHBBB", 0x81, 0x42, 3, 5, 0x0A, 8, 9))
    data.extend(struct.pack("<BBBHBBB", 0x04, 0x05, 7, 0x1FF, 0x06, 10, 11))
    data.append(2)
    data.extend(bytes((4, 5, 1)))
    data.extend(bytes((0, 0, 0)))
    data.append(1)
    data.extend(bytes((9, 8, 7)))
    data.append(2)
    data.extend(struct.pack("<HH", 0x0400, 0x0450))
    return bytes(data)


def _fixture(root: Path) -> OverlayStore:
    bank = bytearray(WORLD_HEADER_OFFSET + 8 * WORLD_HEADER_SIZE + 16)
    bank[WORLD_HEADER_OFFSET + 21] = 2
    archive = root / "resources.bin"
    _build_archive(archive, [
        (WORLD_BANK, bytes(bank)),
        ("Game/world/EventTable/EventTable_0002.dat", _event_table()),
    ])
    return OverlayStore(archive, root / "project")


class WorldEventTableTests(unittest.TestCase):
    def test_parses_pc_exits_triggers_unknowns_and_script_addresses(self):
        parsed = parse_world_table(_event_table())
        self.assertEqual(parsed["exitCount"], 2)
        self.assertEqual(parsed["exits"][0]["derived"]["tileX"], 1)
        self.assertTrue(parsed["exits"][0]["derived"]["available"])
        self.assertEqual(parsed["exits"][0]["derived"]["tileY"], 2)
        self.assertEqual(parsed["exits"][0]["derived"]["facing"], "Down")
        self.assertEqual(parsed["exits"][0]["derived"]["shiftX"], -8)
        self.assertTrue(parsed["exits"][1]["derived"]["scripted"])
        self.assertEqual(parsed["exits"][1]["derived"]["scriptAddressIndex"], 3)
        self.assertEqual(len(parsed["triggers"]), 1)
        self.assertEqual(parsed["nullTrigger"]["index"], 1)
        self.assertEqual(parsed["unknownRecords"]["hex"], "09 08 07")
        self.assertEqual(parsed["scriptAddresses"][0]["derived"]["scriptOffset"], 0)
        self.assertEqual(parsed["scriptAddresses"][1]["derived"]["scriptOffset"], 0x50)

    def test_world_header_selects_event_table_path(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-world-table-") as temp_name:
            data = load_world_table(_fixture(Path(temp_name)), 0)
            self.assertEqual(data["tableId"], 2)
            self.assertEqual(data["path"], "Game/world/EventTable/EventTable_0002.dat")
            self.assertEqual(data["source"], "archive")

    def test_existing_world_records_save_to_project_with_hash_chaining(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-world-table-") as temp_name:
            root = Path(temp_name)
            store = _fixture(root)
            opened = load_world_table(store, 0)
            after_exit = save_world_exit(store, 0, 0, opened["sha256"], {"sceneIndex": 99, "tileX": 20})
            after_trigger = save_world_trigger(store, 0, 0, after_exit["sha256"], {"scriptAddressIndex": 2})
            after_address = save_world_script_address(store, 0, 1, after_trigger["sha256"], {"storedAddress": 0x0480})
            self.assertEqual(after_address["source"], "project")
            self.assertEqual(after_address["exits"][0]["values"]["sceneIndex"], 99)
            self.assertEqual(after_address["exits"][0]["values"]["tileX"], 20)
            self.assertEqual(after_address["triggers"][0]["values"]["scriptAddressIndex"], 2)
            self.assertEqual(after_address["scriptAddresses"][1]["derived"]["scriptOffset"], 0x80)
            self.assertTrue((root / "project/Game/world/EventTable/EventTable_0002.dat").is_file())
            vanilla = load_world_table(store, 0, "vanilla")
            self.assertEqual(vanilla["exits"][0]["values"]["sceneIndex"], 5)

    def test_count_layout_is_never_exposed_as_editable(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-world-table-") as temp_name:
            store = _fixture(Path(temp_name))
            opened = load_world_table(store, 0)
            with self.assertRaises(ValueError):
                save_world_exit(store, 0, 0, opened["sha256"], {"exitCount": 9})

    def test_stale_world_event_write_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-world-table-") as temp_name:
            store = _fixture(Path(temp_name))
            opened = load_world_table(store, 0)
            save_world_exit(store, 0, 0, opened["sha256"], {"sceneIndex": 99})
            with self.assertRaises(RuntimeError):
                save_world_trigger(store, 0, 0, opened["sha256"], {"scriptAddressIndex": 2})


if __name__ == "__main__":
    unittest.main()
