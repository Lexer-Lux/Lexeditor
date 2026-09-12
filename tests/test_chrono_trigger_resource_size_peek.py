from __future__ import annotations

import gzip
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from games.chrono_trigger.resources import ResourceArchive, ResourceArchiveError


def build_archive(path: Path, resources: list[tuple[str, bytes]]) -> None:
    offset = 16
    encoded_blocks: list[bytes] = []
    records: list[tuple[str, int, int]] = []
    for resource_path, payload in resources:
        decoded = len(payload).to_bytes(4, "big") + gzip.compress(payload, mtime=0)
        encoded_blocks.append(ResourceArchive.decode(decoded, offset))
        records.append((resource_path, offset, len(decoded)))
        offset += len(decoded)

    table_size = 4 + len(records) * 12
    strings = bytearray()
    path_offsets: list[int] = []
    for resource_path, _data_offset, _stored_size in records:
        path_offsets.append(table_size + len(strings))
        strings.extend(resource_path.encode("utf-8") + b"\x00")

    index = bytearray(struct.pack("<I", len(records)))
    for path_offset, (_resource_path, data_offset, stored_size) in zip(path_offsets, records):
        index.extend(struct.pack("<III", path_offset, data_offset, stored_size))
    index.extend(strings)
    decoded_index = len(index).to_bytes(4, "big") + gzip.compress(bytes(index), mtime=0)
    index_offset = offset
    file_size = index_offset + len(decoded_index)
    header = b"ARC1" + struct.pack("<III", file_size, index_offset, len(decoded_index))

    path.write_bytes(
        ResourceArchive.decode(header, 0)
        + b"".join(encoded_blocks)
        + ResourceArchive.decode(decoded_index, index_offset)
    )


class DeclaredPayloadSizeTests(unittest.TestCase):
    def test_reads_only_four_byte_declared_size_without_inflating_resource(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-size-peek-") as temp_name:
            archive_path = Path(temp_name) / "resources.bin"
            payload = bytes(range(200))
            build_archive(archive_path, [("Game/enemy/Enemy_0001.dat", payload)])
            archive = ResourceArchive(archive_path)
            entry = archive.entries[0]

            with patch("games.chrono_trigger.resources.gzip.decompress", side_effect=AssertionError("resource inflated")):
                self.assertEqual(archive.declared_payload_size(entry), len(payload))
                self.assertEqual(archive.declared_payload_size(entry.path), len(payload))

    def test_peek_does_not_depend_on_compressed_stored_size(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-size-peek-") as temp_name:
            archive_path = Path(temp_name) / "resources.bin"
            resources = [
                ("Game/enemy/Enemy_0001.dat", b"A" * 1024),
                ("Game/enemy/Enemy_0002.dat", bytes(range(256)) * 4),
            ]
            build_archive(archive_path, resources)
            archive = ResourceArchive(archive_path)

            self.assertNotEqual(archive.entries[0].stored_size, archive.entries[1].stored_size)
            self.assertEqual(archive.declared_payload_size(archive.entries[0]), 1024)
            self.assertEqual(archive.declared_payload_size(archive.entries[1]), 1024)

    def test_rejects_entry_shorter_than_four_byte_size_prefix(self):
        archive = object.__new__(ResourceArchive)
        archive.path = Path("resources.bin")
        archive.file_size = 3
        archive._by_path = {}
        entry = type("Entry", (), {"path": "Game/enemy/bad.dat", "offset": 0, "stored_size": 3})()

        with self.assertRaisesRegex(ResourceArchiveError, "shorter than its size prefix"):
            archive.declared_payload_size(entry)


if __name__ == "__main__":
    unittest.main()
