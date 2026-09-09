from __future__ import annotations

import gzip
from pathlib import Path
import struct
import tempfile
import unittest

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.integrity import audit_project
from games.chrono_trigger.resources import ResourceArchive
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


def _fixture(root: Path, *, omit_field=False, omit_world_table=False, omit_world_script=False,
             unknown_world_opcode=False) -> OverlayStore:
    scene = bytearray(24)
    struct.pack_into("<H", scene, 16, 2)
    bank = bytearray(WORLD_HEADER_OFFSET + 8 * WORLD_HEADER_SIZE + 16)
    for world_id in range(8):
        start = WORLD_HEADER_OFFSET + world_id * WORLD_HEADER_SIZE
        bank[start + 21] = 3
        bank[start + 22] = 4
    resources = [
        ("Game/field/Mapinfo/mapinfo_0.dat", bytes(scene)),
        (WORLD_BANK, bytes(bank)),
    ]
    if not omit_field:
        resources.append(("Game/field/atel/Atel_0002.dat", b"\x00"))
    if not omit_world_table:
        resources.append(("Game/world/EventTable/EventTable_0003.dat", b"\x00\x00\x00\x00"))
    if not omit_world_script:
        resources.append(("Game/world/esl/Event_0004.dat", b"\x53" if unknown_world_opcode else b"\x00\x52"))
    archive = root / "resources.bin"
    _build_archive(archive, resources)
    return OverlayStore(archive, root / "project")


class IntegrityAuditTests(unittest.TestCase):
    def test_clean_integrated_references_have_no_error_or_warning(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-audit-") as temp_name:
            result = audit_project(_fixture(Path(temp_name)))
            self.assertTrue(result["ok"])
            self.assertEqual(result["counts"]["error"], 0)
            self.assertEqual(result["counts"]["warning"], 0)
            self.assertEqual(result["sceneHeaders"], 1)
            self.assertEqual(result["worldHeaders"], 8)

    def test_missing_scene_and_world_references_are_warnings(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-audit-") as temp_name:
            result = audit_project(_fixture(
                Path(temp_name), omit_field=True, omit_world_table=True, omit_world_script=True,
            ))
            codes = {issue["code"] for issue in result["issues"]}
            self.assertIn("missing-field-script", codes)
            self.assertIn("missing-world-event-table", codes)
            self.assertIn("missing-world-script", codes)
            self.assertGreaterEqual(result["counts"]["warning"], 3)
            self.assertTrue(result["ok"])

    def test_unknown_pc_world_opcode_is_info_not_error(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-audit-") as temp_name:
            result = audit_project(_fixture(Path(temp_name), unknown_world_opcode=True))
            issue = next(item for item in result["issues"] if item["code"] == "partial-world-script-disassembly")
            self.assertEqual(issue["level"], "info")
            self.assertTrue(result["ok"])

    def test_new_loose_resource_is_reported_but_allowed(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-audit-") as temp_name:
            root = Path(temp_name)
            store = _fixture(root)
            target = root / "project/Game/custom/new_resource.dat"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"new")
            result = audit_project(store)
            issue = next(item for item in result["issues"] if item["code"] == "new-loose-resource")
            self.assertEqual(issue["path"], "Game/custom/new_resource.dat")
            self.assertEqual(issue["level"], "info")

    def test_symlink_is_error_when_platform_supports_it(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-audit-") as temp_name:
            root = Path(temp_name)
            store = _fixture(root)
            project = root / "project"
            project.mkdir()
            source = root / "outside.dat"
            source.write_bytes(b"outside")
            link = project / "linked.dat"
            try:
                link.symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            result = audit_project(store)
            self.assertFalse(result["ok"])
            self.assertIn("project-symlink", {issue["code"] for issue in result["issues"]})


if __name__ == "__main__":
    unittest.main()
