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
from tools.chrono_trigger_palette import main


PALETTE_PATH = "Game/field/palette_bin/plt3.bin"


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


def _fixture(root: Path) -> tuple[Path, Path]:
    game = root / "game"
    game.mkdir()
    palette = bytearray(b"PH" + bytes(512))
    struct.pack_into("<H", palette, 4, 0x001F)
    _build_archive(game / "resources.bin", [(PALETTE_PATH, bytes(palette))])
    project = root / "PaletteMod"
    project.mkdir()
    return game, project


class PaletteCliTests(unittest.TestCase):
    def _run(self, game: Path, project: Path, extra: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main([
                "--game", str(game), "--project", str(project),
                "--kind", "scene", "--palette", "3", *extra,
            ])
        return code, json.loads(output.getvalue())

    def test_show_reads_vanilla_palette_and_returns_sha(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-palette-cli-") as temp_name:
            game, project = _fixture(Path(temp_name))
            code, payload = self._run(game, project, ["show", "--source", "vanilla"])
            self.assertEqual(code, 0)
            self.assertEqual(payload["source"], "archive")
            self.assertEqual(payload["colors"][1]["hex"], "#FF0000")
            self.assertEqual(len(payload["sha256"]), 64)

    def test_rgb_write_creates_overlay_and_leaves_arc1_unchanged(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-palette-cli-") as temp_name:
            game, project = _fixture(Path(temp_name))
            original_archive = (game / "resources.bin").read_bytes()
            _code, shown = self._run(game, project, ["show"])
            code, payload = self._run(game, project, [
                "set", "--index", "1", "--sha256", shown["sha256"],
                "--rgb", "0", "255", "255",
            ])
            self.assertEqual(code, 0)
            self.assertEqual(payload["savedColor"]["hex"], "#00FFFF")
            self.assertEqual(payload["source"], "project")
            self.assertTrue((project / PALETTE_PATH).is_file())
            self.assertEqual((game / "resources.bin").read_bytes(), original_archive)

    def test_raw_write_accepts_hex_notation(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-palette-cli-") as temp_name:
            game, project = _fixture(Path(temp_name))
            _code, shown = self._run(game, project, ["show"])
            code, payload = self._run(game, project, [
                "set", "--index", "1", "--sha256", shown["sha256"], "--raw", "0x03E0",
            ])
            self.assertEqual(code, 0)
            self.assertEqual(payload["savedColor"]["hex"], "#00FF00")

    def test_stale_sha_returns_error_and_no_overlay(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-palette-cli-") as temp_name:
            game, project = _fixture(Path(temp_name))
            code, payload = self._run(game, project, [
                "set", "--index", "1", "--sha256", "0" * 64, "--raw", "1",
            ])
            self.assertEqual(code, 1)
            self.assertIn("changed since", payload["error"])
            self.assertFalse((project / PALETTE_PATH).exists())


if __name__ == "__main__":
    unittest.main()
