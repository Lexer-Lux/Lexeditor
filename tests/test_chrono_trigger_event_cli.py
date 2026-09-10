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
from tools.chrono_trigger_event import main


EVENT_PATH = "Game/field/atel/Atel_0001.dat"


def _event(bytecode: bytes) -> bytes:
    data = bytearray(32)
    for index in range(16):
        struct.pack_into("<H", data, index * 2, 32)
    data.extend(bytecode)
    return bytes([1]) + bytes(data)


def _build_archive(path: Path, resources: list[tuple[str, bytes]]) -> None:
    offset = 16
    blocks = []
    records = []
    for virtual, payload in resources:
        decoded = len(payload).to_bytes(4, "big") + gzip.compress(payload, mtime=0)
        blocks.append(ResourceArchive.decode(decoded, offset))
        records.append((virtual, offset, len(decoded)))
        offset += len(decoded)
    table_size = 4 + len(records) * 12
    strings = bytearray()
    path_offsets = []
    for virtual, _entry_offset, _stored_size in records:
        path_offsets.append(table_size + len(strings))
        strings.extend(virtual.encode("utf-8") + b"\0")
    index = bytearray(struct.pack("<I", len(records)))
    for path_offset, (_virtual, entry_offset, stored_size) in zip(path_offsets, records):
        index.extend(struct.pack("<III", path_offset, entry_offset, stored_size))
    index.extend(strings)
    encoded_index = len(index).to_bytes(4, "big") + gzip.compress(bytes(index), mtime=0)
    index_offset = offset
    header = b"ARC1" + struct.pack("<III", index_offset + len(encoded_index), index_offset, len(encoded_index))
    path.write_bytes(ResourceArchive.decode(header, 0) + b"".join(blocks) + ResourceArchive.decode(encoded_index, index_offset))


def _fixture(root: Path, bytecode: bytes) -> tuple[Path, Path]:
    game = root / "game"
    game.mkdir()
    _build_archive(game / "resources.bin", [(EVENT_PATH, _event(bytecode))])
    project = root / "EventMod"
    project.mkdir()
    return game, project


class EventCliTests(unittest.TestCase):
    def _run(self, game: Path, project: Path, extra: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        argv = [
            "--game", str(game), "--project", str(project), "--event", "1",
            "--object", "0", "--function", "0", "--command", "0",
            *extra,
        ]
        with redirect_stdout(output):
            code = main(argv)
        return code, json.loads(output.getvalue())

    def test_show_exposes_named_editor_and_current_sha(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-event-cli-") as temp_name:
            game, project = _fixture(Path(temp_name), bytes((0x83, 0x34, 0x12, 0x85, 0x00)))
            code, payload = self._run(game, project, ["show"])
            self.assertEqual(code, 0)
            self.assertEqual(len(payload["sha256"]), 64)
            command = payload["objects"][0]["functions"][0]["commands"][0]
            self.assertEqual(command["opcode"], 0x83)
            self.assertEqual(command["editor"]["values"]["enemyId"], 0x1234)
            self.assertTrue(command["editor"]["values"]["static"])

    def test_named_patch_writes_only_project_overlay(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-event-cli-") as temp_name:
            game, project = _fixture(Path(temp_name), bytes((0x83, 0x34, 0x12, 0x85, 0x00)))
            _code, shown = self._run(game, project, ["show"])
            code, payload = self._run(game, project, [
                "set-fields", "--sha256", shown["sha256"],
                "--values", '{"enemyId":22136,"slot":3}',
            ])
            self.assertEqual(code, 0)
            self.assertEqual(payload["savedCommand"]["argumentsHex"], "78 56 83")
            overlay = project / EVENT_PATH
            self.assertTrue(overlay.is_file())
            self.assertEqual(overlay.read_bytes()[34:37], bytes((0x78, 0x56, 0x83)))
            # Vanilla ARC1 still reports the original bytes when reopened without overlay semantics.
            archive = ResourceArchive(game / "resources.bin")
            self.assertEqual(archive.read(EVENT_PATH)[34:37], bytes((0x34, 0x12, 0x85)))

    def test_raw_patch_requires_exact_fixed_width(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-event-cli-") as temp_name:
            game, project = _fixture(Path(temp_name), bytes((0xEA, 0x05, 0x00)))
            _code, shown = self._run(game, project, ["show"])
            code, payload = self._run(game, project, [
                "set-args", "--sha256", shown["sha256"], "--hex", "2A",
            ])
            self.assertEqual(code, 0)
            self.assertEqual(payload["savedCommand"]["argumentsHex"], "2A")

    def test_stale_sha_fails_without_overwriting_overlay(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-event-cli-") as temp_name:
            game, project = _fixture(Path(temp_name), bytes((0xEA, 0x05, 0x00)))
            code, payload = self._run(game, project, [
                "set-fields", "--sha256", "0" * 64, "--values", '{"id":6}',
            ])
            self.assertEqual(code, 1)
            self.assertIn("changed since", payload["error"])
            self.assertFalse((project / EVENT_PATH).exists())

    def test_decoded_dynamic_command_remains_read_only(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-event-cli-") as temp_name:
            # PC Color Math mode 4 has a proven five-argument boundary, but the
            # raw argument writer deliberately keeps the dynamic opcode family read-only.
            game, project = _fixture(Path(temp_name), bytes((
                0x2E, 0x40, 0x01, 0x02, 0x03, 0x04,
                0x00,
            )))
            _code, shown = self._run(game, project, ["show"])
            command = shown["objects"][0]["functions"][0]["commands"][0]
            self.assertEqual(command["opcode"], 0x2E)
            self.assertEqual(command["argumentBytes"], 5)
            code, payload = self._run(game, project, [
                "set-args", "--sha256", shown["sha256"], "--hex", "40 05 06 07 08",
            ])
            self.assertEqual(code, 1)
            self.assertIn("variable or unresolved", payload["error"])
            self.assertFalse((project / EVENT_PATH).exists())

    def test_unresolved_f1_stops_disassembly_before_cli_edit_selection(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-event-cli-") as temp_name:
            game, project = _fixture(Path(temp_name), bytes((0xF1, 0x21, 0x80, 0x00)))
            code, shown = self._run(game, project, ["show"])
            self.assertEqual(code, 0)
            function = shown["objects"][0]["functions"][0]
            self.assertFalse(function["complete"])
            self.assertEqual(function["commands"], [])
            self.assertEqual(function["problem"]["opcode"], 0xF1)
            self.assertIn("unresolved", function["problem"]["reason"])

            code, payload = self._run(game, project, [
                "set-args", "--sha256", shown["sha256"], "--hex", "22 80",
            ])
            self.assertEqual(code, 1)
            self.assertIn("outside function", payload["error"])
            self.assertFalse((project / EVENT_PATH).exists())


if __name__ == "__main__":
    unittest.main()
