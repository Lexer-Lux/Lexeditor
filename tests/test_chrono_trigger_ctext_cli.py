from __future__ import annotations

from contextlib import redirect_stdout
import gzip
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

from games.chrono_trigger.resources import ResourceArchive
from games.chrono_trigger.worlds import WORLD_BANK, WORLD_HEADER_OFFSET, WORLD_HEADER_SIZE
from tools.chrono_trigger_ctext import main


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


def _fixture(root: Path) -> tuple[Path, Path]:
    game = root / "game"
    game.mkdir()
    (game / "ctext.dll").write_bytes(b"fixture")
    (game / "sqlite3.dll").write_bytes(b"fixture")
    (game / "ctext.json").write_text(json.dumps({
        "mods": {"enabled": False, "load_order": []},
    }), encoding="utf-8")
    bank = bytearray(WORLD_HEADER_OFFSET + 8 * WORLD_HEADER_SIZE + 16)
    _build_archive(game / "resources.bin", [
        (WORLD_BANK, bytes(bank)),
        ("Game/world/EventTable/EventTable_0000.dat", b"\x00\x00\x00\x00"),
        ("Game/world/esl/Event_0000.dat", b"\x00\x52"),
    ])
    project = root / "CliMod"
    project.mkdir()
    (project / "lexeditor-project.json").write_text("{}\n", encoding="utf-8")
    return game, project


class CTExtCliTests(unittest.TestCase):
    def _run(self, game: Path, project: Path, action: str) -> tuple[int, dict]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--game", str(game), "--project", str(project), action])
        return code, json.loads(output.getvalue())

    def test_status_is_read_only(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-cli-") as temp_name:
            game, project = _fixture(Path(temp_name))
            before = (game / "ctext.json").read_bytes()
            code, payload = self._run(game, project, "status")
            self.assertEqual(code, 0)
            self.assertTrue(payload["installed"])
            self.assertFalse(payload["active"])
            self.assertEqual((game / "ctext.json").read_bytes(), before)

    def test_audit_succeeds_without_deploying(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-cli-") as temp_name:
            game, project = _fixture(Path(temp_name))
            code, payload = self._run(game, project, "audit")
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertFalse((game / "mods").exists())

    def test_deploy_is_explicit_and_activates_project(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-cli-") as temp_name:
            game, project = _fixture(Path(temp_name))
            code, payload = self._run(game, project, "deploy")
            self.assertEqual(code, 0)
            self.assertTrue(payload["audit"]["ok"])
            self.assertTrue(payload["deployment"]["active"])
            self.assertTrue((game / "mods/CliMod/lexeditor-project.json").is_file())

    def test_deactivate_keeps_deployed_files_but_removes_load_order(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-cli-") as temp_name:
            game, project = _fixture(Path(temp_name))
            self._run(game, project, "deploy")
            code, payload = self._run(game, project, "deactivate")
            self.assertEqual(code, 0)
            self.assertFalse(payload["active"])
            self.assertTrue(payload["deployed"])
            self.assertTrue((game / "mods/CliMod/lexeditor-project.json").is_file())

    def test_undeploy_removes_owned_copy_after_deactivation(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-cli-") as temp_name:
            game, project = _fixture(Path(temp_name))
            self._run(game, project, "deploy")
            code, payload = self._run(game, project, "undeploy")
            self.assertEqual(code, 0)
            self.assertTrue(payload["deactivated"])
            self.assertTrue(payload["undeployed"])
            self.assertFalse(payload["active"])
            self.assertFalse((game / "mods/CliMod").exists())


if __name__ == "__main__":
    unittest.main()
