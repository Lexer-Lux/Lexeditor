from __future__ import annotations

import gzip
from pathlib import Path
import struct
import tempfile
import unittest

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.resources import ResourceArchive
from games.chrono_trigger.worlds import (
    WORLD_BANK,
    WORLD_COUNT,
    WORLD_HEADER_OFFSET,
    WORLD_HEADER_SIZE,
    WORLD_NAMES,
    load_worlds,
    save_world,
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
    bank = bytearray(WORLD_HEADER_OFFSET + WORLD_COUNT * WORLD_HEADER_SIZE + 32)
    for world in range(WORLD_COUNT):
        start = WORLD_HEADER_OFFSET + world * WORLD_HEADER_SIZE
        bank[start:start + WORLD_HEADER_SIZE] = bytes((world * 23 + index) & 0xFF for index in range(23))
    lines = [f"{index:04d},Unused {index}" for index in range(112)]
    for line, name in zip(range(106, 112), ("Present", "Middle Ages", "Future", "Prehistory", "Dark Ages", "End of Time")):
        lines[line] = f"{line:04d},{name}"
    archive = root / "resources.bin"
    _build_archive(archive, [
        (WORLD_BANK, bytes(bank)),
        (WORLD_NAMES, ("\n".join(lines) + "\n").encode("utf-8")),
    ])
    return OverlayStore(archive, root / "project")


class WorldHeaderTests(unittest.TestCase):
    def test_loads_eight_fixed_pc_world_headers_and_names(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-world-") as temp_name:
            store = _fixture(Path(temp_name))
            data = load_worlds(store)
            self.assertEqual(len(data["rows"]), 8)
            self.assertEqual(data["recordSize"], 23)
            self.assertEqual(data["rows"][0]["name"], "Present")
            self.assertEqual(data["rows"][4]["name"], "Dark Ages")
            self.assertEqual(data["rows"][5]["name"], "Dark Ages")
            self.assertEqual(data["rows"][6]["name"], "Dark Ages")
            self.assertEqual(data["rows"][7]["name"], "End of Time")
            self.assertEqual(data["rows"][2]["values"]["chipL12_0"], 46)
            self.assertEqual(data["rows"][2]["values"]["script"], 68)
            self.assertEqual(data["rows"][2]["derived"]["effectivePaletteAnimations"], 2)

    def test_world_edit_writes_only_bank_project_overlay(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-world-") as temp_name:
            root = Path(temp_name)
            store = _fixture(root)
            opened = load_worlds(store)
            saved = save_world(store, 3, opened["sha256"], {"map": 99, "script": 101})
            self.assertEqual(saved["source"], "project")
            self.assertEqual(saved["rows"][3]["values"]["map"], 99)
            self.assertEqual(saved["rows"][3]["values"]["script"], 101)
            self.assertTrue((root / "project" / WORLD_BANK).is_file())
            vanilla = load_worlds(store, "vanilla")
            self.assertNotEqual(vanilla["rows"][3]["values"]["map"], 99)
            self.assertNotEqual(vanilla["rows"][3]["values"]["script"], 101)

    def test_sequential_world_edits_use_new_shared_bank_hash(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-world-") as temp_name:
            store = _fixture(Path(temp_name))
            opened = load_worlds(store)
            first = save_world(store, 0, opened["sha256"], {"map": 200})
            second = save_world(store, 1, first["sha256"], {"map": 201})
            self.assertEqual(second["rows"][0]["values"]["map"], 200)
            self.assertEqual(second["rows"][1]["values"]["map"], 201)

    def test_stale_world_save_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-world-") as temp_name:
            store = _fixture(Path(temp_name))
            opened = load_worlds(store)
            save_world(store, 0, opened["sha256"], {"map": 200})
            with self.assertRaises(RuntimeError):
                save_world(store, 1, opened["sha256"], {"map": 201})


if __name__ == "__main__":
    unittest.main()
