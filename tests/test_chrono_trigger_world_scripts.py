from __future__ import annotations

import gzip
from pathlib import Path
import struct
import tempfile
import unittest

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.resources import ResourceArchive
from games.chrono_trigger.world_scripts import disassemble_world_script, load_world_script
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


def _fixture(root: Path, script: bytes) -> OverlayStore:
    bank = bytearray(WORLD_HEADER_OFFSET + 8 * WORLD_HEADER_SIZE + 16)
    bank[WORLD_HEADER_OFFSET + 22] = 3
    archive = root / "resources.bin"
    _build_archive(archive, [
        (WORLD_BANK, bytes(bank)),
        ("Game/world/esl/Event_0003.dat", script),
    ])
    return OverlayStore(archive, root / "project")


class WorldScriptTests(unittest.TestCase):
    def test_decodes_documented_fixed_width_commands(self):
        raw = bytes((
            0x00,
            0x01, 0x07,
            0x05, 0x34, 0x12,
            0x2C, 0x10, 0x00, 0x20, 0x00,
            0x4F, 1, 2, 3, 4, 5, 6, 7, 8,
            0x52,
        ))
        result = disassemble_world_script(raw)
        self.assertTrue(result["complete"])
        self.assertEqual([row["name"] for row in result["commands"]], [
            "initialize", "colofs", "mapjump", "pos", "copymap", "taskend",
        ])
        self.assertEqual(result["commands"][2]["argumentsHex"], "34 12")
        self.assertEqual(result["decodedBytes"], len(raw))

    def test_unknown_pc_ds_opcode_stops_without_guessing_boundary(self):
        result = disassemble_world_script(bytes((0x00, 0x53, 0xAA, 0xBB, 0x52)))
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["commands"]), 1)
        self.assertEqual(result["problem"]["offset"], 1)
        self.assertEqual(result["problem"]["opcode"], 0x53)
        self.assertEqual(result["problem"]["reason"], "unknown-opcode")

    def test_truncated_known_opcode_is_reported(self):
        result = disassemble_world_script(bytes((0x2C, 1, 2)))
        self.assertFalse(result["complete"])
        self.assertEqual(result["problem"]["reason"], "truncated-command")
        self.assertEqual(result["problem"]["expectedSize"], 5)

    def test_world_header_selects_pc_script_resource(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-world-script-") as temp_name:
            store = _fixture(Path(temp_name), bytes((0x00, 0x38, 5, 0x52)))
            loaded = load_world_script(store, 0)
            self.assertEqual(loaded["scriptId"], 3)
            self.assertEqual(loaded["path"], "Game/world/esl/Event_0003.dat")
            self.assertEqual([row["name"] for row in loaded["commands"]], ["initialize", "wait", "taskend"])
            self.assertTrue(loaded["readOnly"])


if __name__ == "__main__":
    unittest.main()
