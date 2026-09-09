from __future__ import annotations

import gzip
from pathlib import Path
import struct
import tempfile
import unittest

from games.chrono_trigger.resources import ResourceArchive, ResourceArchiveError


def _build_archive(path: Path, resources: list[tuple[str, bytes]]) -> None:
    offset = 16
    encoded_blocks: list[bytes] = []
    records: list[tuple[str, int, int]] = []
    for resource_path, payload in resources:
        decoded = len(payload).to_bytes(4, "big") + gzip.compress(payload, mtime=0)
        encoded_blocks.append(ResourceArchive.decode(decoded, offset))
        records.append((resource_path, offset, len(decoded)))
        offset += len(decoded)

    table_size = 4 + len(records) * 12
    string_table = bytearray()
    path_offsets: list[int] = []
    for resource_path, _data_offset, _stored_size in records:
        path_offsets.append(table_size + len(string_table))
        string_table.extend(resource_path.encode("utf-8") + b"\x00")

    index = bytearray(struct.pack("<I", len(records)))
    for path_offset, (_resource_path, data_offset, stored_size) in zip(path_offsets, records):
        index.extend(struct.pack("<III", path_offset, data_offset, stored_size))
    index.extend(string_table)
    decoded_index = len(index).to_bytes(4, "big") + gzip.compress(bytes(index), mtime=0)
    index_offset = offset
    index_stored_size = len(decoded_index)
    file_size = index_offset + index_stored_size
    decoded_header = b"ARC1" + struct.pack("<III", file_size, index_offset, index_stored_size)

    path.write_bytes(
        ResourceArchive.decode(decoded_header, 0)
        + b"".join(encoded_blocks)
        + ResourceArchive.decode(decoded_index, index_offset)
    )


class ResourceArchiveTests(unittest.TestCase):
    def test_lists_and_extracts_synthetic_archive(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-trigger-") as temp_name:
            archive_path = Path(temp_name) / "resources.bin"
            expected = [
                ("Game/common/example.txt", b"Crono\nMarle\nLucca\n"),
                ("Game/battle/sample.dat", bytes(range(64))),
            ]
            _build_archive(archive_path, expected)

            archive = ResourceArchive(archive_path)

            self.assertEqual(archive.declared_size, archive.file_size)
            self.assertEqual([entry.path for entry in archive.entries], [item[0] for item in expected])
            self.assertEqual(archive.read(expected[0][0]), expected[0][1])
            self.assertEqual(archive.read(archive.entries[1]), expected[1][1])
            self.assertEqual([entry.path for entry in archive.matching("BATTLE")], [expected[1][0]])

    def test_rejects_non_arc1_file(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-trigger-") as temp_name:
            archive_path = Path(temp_name) / "resources.bin"
            archive_path.write_bytes(b"not a chrono trigger archive")
            with self.assertRaises(ResourceArchiveError):
                ResourceArchive(archive_path)


if __name__ == "__main__":
    unittest.main()
