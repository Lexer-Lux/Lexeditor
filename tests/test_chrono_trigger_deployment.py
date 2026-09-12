from __future__ import annotations

import gzip
import json
from pathlib import Path
import struct
import tempfile
import unittest

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.deployment import deploy_audited_project, deployment_status
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


def _fixture(root: Path) -> tuple[OverlayStore, Path]:
    game = root / "game"
    game.mkdir()
    (game / "ctext.dll").write_bytes(b"fixture")
    (game / "sqlite3.dll").write_bytes(b"fixture")
    (game / "ctext.json").write_text(json.dumps({
        "mods": {"enabled": False, "load_order": []},
    }), encoding="utf-8")

    bank = bytearray(WORLD_HEADER_OFFSET + 8 * WORLD_HEADER_SIZE + 16)
    archive = game / "resources.bin"
    _build_archive(archive, [
        (WORLD_BANK, bytes(bank)),
        ("Game/world/EventTable/EventTable_0000.dat", b"\x00\x00\x00\x00"),
        ("Game/world/esl/Event_0000.dat", b"\x00\x52"),
    ])
    project = root / "SafeMod"
    project.mkdir()
    (project / "lexeditor-project.json").write_text("{}\n", encoding="utf-8")
    return OverlayStore(archive, project), game


class DeploymentOrchestrationTests(unittest.TestCase):
    def test_status_combines_ctext_and_audit_without_mutating(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-deployment-") as temp_name:
            store, game = _fixture(Path(temp_name))
            before = (game / "ctext.json").read_bytes()
            result = deployment_status(store, game)
            self.assertTrue(result["ctext"]["installed"])
            self.assertTrue(result["ctext"]["configValid"])
            self.assertTrue(result["audit"]["ok"])
            self.assertTrue(result["canDeploy"])
            self.assertFalse(result["automatic"])
            self.assertEqual((game / "ctext.json").read_bytes(), before)
            self.assertFalse((game / "mods").exists())

    def test_explicit_deployment_runs_audit_then_activates_project(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-deployment-") as temp_name:
            store, game = _fixture(Path(temp_name))
            result = deploy_audited_project(store, game)
            self.assertTrue(result["audit"]["ok"])
            self.assertTrue(result["deployment"]["deployed"])
            self.assertTrue(result["deployment"]["active"])
            self.assertFalse(result["automatic"])
            self.assertTrue((game / "mods/SafeMod/lexeditor-project.json").is_file())
            config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            self.assertEqual(config["mods"]["load_order"], ["SafeMod"])

    def test_audit_error_blocks_ctext_mutation(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-deployment-") as temp_name:
            root = Path(temp_name)
            store, game = _fixture(root)
            source = root / "outside.dat"
            source.write_bytes(b"outside")
            link = store.project_root / "linked.dat"
            try:
                link.symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            before = (game / "ctext.json").read_bytes()
            with self.assertRaises(RuntimeError):
                deploy_audited_project(store, game)
            self.assertEqual((game / "ctext.json").read_bytes(), before)
            self.assertFalse((game / "mods").exists())


if __name__ == "__main__":
    unittest.main()
