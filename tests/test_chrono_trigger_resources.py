from __future__ import annotations

import gzip
from pathlib import Path
import struct
import tempfile
import unittest

from games.chrono_trigger.data import (
    OverlayStore,
    classify_resource,
    data_map,
    load_message_table,
    load_scenes,
    save_message_table,
    save_scene,
)
from games.chrono_trigger.events import get_event, load_events, parse_event
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


def _scene_header() -> bytes:
    data = bytearray(24)
    for index, value in enumerate(range(10, 20)):
        struct.pack_into("<H", data, index * 2, value)
    data[20:24] = bytes((20, 21, 22, 23))
    return bytes(data)


def _field_event() -> bytes:
    # Two objects, 16 function pointers apiece. Object 0's slots all begin at
    # byte 64 of Event.data; object 1 begins at 67. This mirrors the pointer
    # convention used by the Steam Atel files without needing opcode semantics.
    data = bytearray(64)
    for index in range(16):
        struct.pack_into("<H", data, index * 2, 64)
    for index in range(16, 32):
        struct.pack_into("<H", data, index * 2, 67)
    data.extend(b"\xAA\xBB\xCC\x10\x20\x30")
    return b"\x02" + bytes(data)


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


class StructuredOverlayTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[OverlayStore, Path, Path]:
        archive_path = root / "resources.bin"
        project = root / "My Chrono Mod"
        message = b"0000,Potion\r\n0001,Comma, stays in text\r\n"
        _build_archive(archive_path, [
            ("Localize/en/msg/item.txt", message),
            ("Game/field/Mapinfo/mapinfo_0.dat", _scene_header()),
            ("Game/field/atel/Atel_0000.dat", _field_event()),
            ("Game/world/esl/Event_0000.dat", b"event"),
        ])
        return OverlayStore(archive_path, project), archive_path, project

    def test_message_table_saves_project_overlay_and_preserves_vanilla(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-trigger-data-") as temp_name:
            store, _archive_path, project = self._fixture(Path(temp_name))
            loaded = load_message_table(store, "Localize/en/msg/item.txt")
            self.assertEqual(loaded["source"], "archive")
            self.assertEqual(loaded["rows"][1]["text"], "Comma, stays in text")

            saved = save_message_table(store, loaded["path"], loaded["sha256"], [
                {"id": 0, "text": "Tonic"},
            ])

            self.assertEqual(saved["source"], "project")
            self.assertEqual(saved["rows"][0]["text"], "Tonic")
            self.assertEqual(
                (project / "Localize/en/msg/item.txt").read_bytes(),
                b"0000,Tonic\r\n0001,Comma, stays in text\r\n",
            )
            vanilla = load_message_table(store, "Localize/en/msg/item.txt", "vanilla")
            self.assertEqual(vanilla["rows"][0]["text"], "Potion")

    def test_scene_header_saves_only_known_fields_to_project(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-trigger-data-") as temp_name:
            store, _archive_path, project = self._fixture(Path(temp_name))
            dataset = load_scenes(store)
            row = dataset["rows"][0]
            self.assertEqual(row["values"]["musicIndex"], 10)
            self.assertEqual(row["values"]["scriptIndex"], 18)
            self.assertEqual(row["values"]["scrollBottom"], 23)

            saved = save_scene(store, 0, row["sha256"], {"musicIndex": 99, "scrollBottom": 42})

            self.assertEqual(saved["source"], "project")
            self.assertEqual(saved["values"]["musicIndex"], 99)
            self.assertEqual(saved["values"]["scrollBottom"], 42)
            self.assertTrue((project / "Game/field/Mapinfo/mapinfo_0.dat").is_file())
            vanilla = load_scenes(store, "vanilla")["rows"][0]
            self.assertEqual(vanilla["values"]["musicIndex"], 10)
            self.assertEqual(vanilla["values"]["scrollBottom"], 23)

    def test_field_event_structure_is_parsed_without_guessing_opcodes(self):
        parsed = parse_event(_field_event())
        self.assertEqual(parsed["objectCount"], 2)
        self.assertEqual(parsed["functionSlots"], 32)
        self.assertEqual(parsed["pointerTableBytes"], 64)
        self.assertEqual(parsed["bytecodeBytes"], 6)
        self.assertEqual(parsed["objects"][0]["functions"][0]["name"], "Startup")
        self.assertEqual(parsed["objects"][0]["functions"][0]["preview"], "AA BB CC")
        self.assertEqual(parsed["objects"][1]["functions"][15]["preview"], "10 20 30")

    def test_field_event_dataset_reads_archive_and_project_sources(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-trigger-data-") as temp_name:
            store, _archive_path, project = self._fixture(Path(temp_name))
            listing = load_events(store)
            self.assertEqual(listing["matchCount"], 1)
            self.assertEqual(listing["rows"][0]["objectCount"], 2)
            self.assertNotIn("objects", listing["rows"][0])
            detail = get_event(store, 0)
            self.assertEqual(len(detail["objects"]), 2)
            self.assertEqual(detail["source"], "archive")

            override = project / "Game/field/atel/Atel_0000.dat"
            override.parent.mkdir(parents=True)
            changed = bytearray(_field_event())
            changed[-1] = 0x99
            override.write_bytes(changed)
            self.assertEqual(get_event(store, 0)["source"], "project")
            self.assertTrue(get_event(store, 0)["objects"][1]["functions"][0]["preview"].endswith("99"))
            self.assertEqual(get_event(store, 0, "vanilla")["source"], "archive")

    def test_field_event_rejects_pointer_outside_script(self):
        broken = bytearray(_field_event())
        struct.pack_into("<H", broken, 1, 0xFFFF)
        with self.assertRaises(ValueError):
            parse_event(bytes(broken))

    def test_data_map_and_resource_classification_are_evidence_based(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-trigger-data-") as temp_name:
            store, _archive_path, _project = self._fixture(Path(temp_name))
            mapped = data_map(store)
            self.assertEqual(mapped["counts"]["messages"], 1)
            self.assertEqual(mapped["counts"]["scenes"], 1)
            self.assertEqual(mapped["counts"]["fieldEvents"], 1)
            self.assertEqual(
                classify_resource("Game/field/Mapinfo/mapinfo_0.dat")["coverage"],
                "structured",
            )
            self.assertEqual(
                classify_resource("Game/field/atel/Atel_0000.dat")["status"],
                "partial",
            )

    def test_template_project_is_read_only_until_user_creates_project(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-trigger-data-") as temp_name:
            root = Path(temp_name)
            archive_path = root / "resources.bin"
            template = root / "template"
            template.mkdir()
            _build_archive(archive_path, [("Localize/en/msg/item.txt", b"0000,Potion\n")])
            store = OverlayStore(archive_path, template, template_root=template)
            loaded = load_message_table(store, "Localize/en/msg/item.txt")
            with self.assertRaises(RuntimeError):
                save_message_table(store, loaded["path"], loaded["sha256"], [{"id": 0, "text": "Tonic"}])


if __name__ == "__main__":
    unittest.main()
