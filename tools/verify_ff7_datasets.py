"""Asset-free FF7 dataset and HTTP regressions. Run with Python 3.10+.

The kernel/config fixtures are synthetic. Audio extraction and OS process
probing are test doubles; this does not assert game or visual acceptance.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff7 import kernel as base
from games.ff7.datasets import (
    CATEGORIES, INITIAL_FIELDS, LIMIT_FIELDS, Kernel, load_datasets, save_datasets,
)

# Isolate unrelated host/game services; the real configuration parser/writer
# and the real FF7 HTTP handler run below.
with patch.dict(sys.modules, {
    "theme_sounds": types.SimpleNamespace(ensure_theme_sounds=lambda *a, **k: {"rows": []}, sound_file=lambda *a: None),
    "process_probe": types.SimpleNamespace(live_processes=lambda *a: []),
}):
    from games.ff7 import server
    import platform_config

PATHS = (Path("data/lang-en/kernel/KERNEL.BIN"), Path("ff7/workingdir/data/lang-en/kernel/kernel.bin"))
COUNTS = {"items": 128, "weapons": 128, "armor": 32, "accessories": 32, "materia": 96}
CONFIG = b'''# Synthetic FFNx configuration\r
windowed = true\r
# 0 to 100\r
volume = 60\r
# 0: Fast\r
# 1: Accurate\r
mode = 0\r
scale = 1.5\r
name = "test"\r
paths = ["a", "b"]\r
unknown_table = { kept = true } # preserved\r
### OPTIONS ONLY FOR FF7\r
ff7_option = true\r
### OPTIONS ONLY FOR FF8\r
ff8_option = false\r
'''


def game_text(text):
    return bytes(base.TEXT_MAP_EN.index(char) for char in text) + b"\xff"


def text_table(count, prefix):
    strings = [game_text(f"{prefix}{index}") for index in range(count)]
    offset = count * 2
    pointers = bytearray()
    for value in strings:
        pointers.extend(struct.pack("<H", offset))
        offset += len(value)
    return pointers + b"".join(strings)


def fixture_sections():
    sections = [bytearray([index + 1] * 64) for index in range(27)]
    sections[3] = bytearray(b"\xa5" * (9 * 132 + 700))
    sections[2] = bytearray(b"\x5a" * (0x61C + 2048))
    for slot in range(9):
        for index, field in enumerate(INITIAL_FIELDS):
            data = sections[3][slot * 132:(slot + 1) * 132]
            base._write_field(data, field, (slot + index + 1) * field.scale)
            sections[3][slot * 132:(slot + 1) * 132] = data
        for index, field in enumerate(LIMIT_FIELDS):
            data = sections[2][slot * 56:(slot + 1) * 56]
            base._write_field(data, field, min(field.maximum, 20 + slot + index))
            sections[2][slot * 56:(slot + 1) * 56] = data
        name = game_text(f"Slot{slot}").ljust(12, b"\xff")
        sections[3][slot * 132 + 0x10:slot * 132 + 0x1C] = name
    for key, category in base.CATEGORIES.items():
        sections[category.section - 1] = bytearray(category.record_size * COUNTS[key])
        sections[category.text_name_section - 1] = text_table(COUNTS[key], "Record")
        sections[category.text_description_section - 1] = text_table(COUNTS[key], "Help")
    return sections


def write_kernel(path, sections=None):
    sections = sections if sections is not None else fixture_sections()
    output = bytearray()
    for index, section in enumerate(sections):
        compressed = gzip.compress(bytes(section), mtime=0)
        output.extend(struct.pack("<HHH", len(compressed), len(section), index + 1))
        output.extend(compressed)
    output.extend(b"unchanged-trailer")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output)


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game, self.project = self.root / "game", self.root / "project"
        self.source = self.game / PATHS[0]
        write_kernel(self.source)

    def test_both_product_paths_decode_425_records(self):
        for relative in PATHS:
            with self.subTest(path=relative):
                game = self.root / ("edition" + str(PATHS.index(relative)))
                write_kernel(game / relative)
                data = load_datasets(game, self.project)
                self.assertFalse(data["errors"])
                self.assertEqual(sum(map(len, data["records"].values())), 425)
                self.assertEqual(data["sourceRelativePath"], relative.as_posix())
                self.assertEqual(len(data["records"]["characters"]), 9)

    def test_every_character_field_and_slot_preserves_all_other_bytes(self):
        original = Kernel(self.source)
        for slot in range(9):
            for field in INITIAL_FIELDS + LIMIT_FIELDS:
                with self.subTest(slot=slot, field=field.key):
                    kernel = Kernel(self.source)
                    rows = kernel.records("characters")
                    value = field.maximum
                    rows[slot]["values"][field.key] = value
                    kernel.apply("characters", rows)
                    expected = deepcopy(original.sections)
                    section, stride = (3, 132) if field in INITIAL_FIELDS else (2, 56)
                    record = expected[section][slot * stride:(slot + 1) * stride]
                    base._write_field(record, field, value)
                    expected[section][slot * stride:(slot + 1) * stride] = record
                    self.assertEqual(kernel.sections, expected)
                    target = self.root / "roundtrip.bin"
                    kernel.save(target)
                    restored = Kernel(target)
                    self.assertEqual(restored.sections, expected)
                    self.assertEqual(restored.trailer, original.trailer)
                    self.assertEqual(restored.file_types, original.file_types)

    def test_noop_preserves_all_decoded_bytes(self):
        original = Kernel(self.source)
        for key in CATEGORIES:
            original.apply(key, original.records(key))
        target = self.root / "noop.bin"
        original.save(target)
        self.assertEqual(Kernel(target).sections, Kernel(self.source).sections)

    def test_invalid_character_edits_are_transactional(self):
        cases = [True, -1, 256, 1.5, "3", None]
        for bad in cases:
            with self.subTest(value=bad):
                kernel = Kernel(self.source)
                original = deepcopy(kernel.sections)
                rows = kernel.records("characters")
                rows[0]["values"]["strength"] = 90
                rows[-1]["values"]["level"] = bad
                with self.assertRaises(ValueError):
                    kernel.apply("characters", rows)
                self.assertEqual(kernel.sections, original)

    def test_character_ids_and_schema_rejected(self):
        for mutation in (lambda r: r.pop(), lambda r: r[0].update(id=True),
                         lambda r: r[0].update(id=9), lambda r: r[1].update(id=0),
                         lambda r: r[0]["values"].pop("strength"),
                         lambda r: r[0]["values"].update(invented=1),
                         lambda r: r.__setitem__(0, None)):
            kernel = Kernel(self.source)
            rows = kernel.records("characters")
            mutation(rows)
            with self.assertRaises(ValueError):
                kernel.apply("characters", rows)

    def test_missing_and_bad_container_report_errors_without_creating_data(self):
        for raw in (None, b"garbage", b"\x10\x00\x10\x00\x01\x00\x1f\x8b"):
            if raw is None:
                self.source.unlink()
            else:
                self.source.write_bytes(raw)
            result = load_datasets(self.game, self.project)
            self.assertEqual(set(result["errors"]), set(CATEGORIES))
            self.assertEqual(result["records"], {})
            self.assertFalse(self.project.exists())

    def test_truncated_characters_do_not_hide_equipment(self):
        for section, size in ((2, 503), (3, 1187)):
            sections = fixture_sections()
            sections[section] = sections[section][:size]
            write_kernel(self.source, sections)
            result = load_datasets(self.game, self.project)
            self.assertEqual(set(result["errors"]), {"characters"})
            self.assertEqual(set(result["records"]), set(base.CATEGORIES))

    def test_bad_text_category_isolated_and_preserved_on_other_edits(self):
        sections = fixture_sections()
        sections[19] = bytearray(b"\xff\xff")
        write_kernel(self.source, sections)
        data = load_datasets(self.game, self.project)
        self.assertEqual(set(data["errors"]), {"items"})
        data["records"]["characters"][8]["values"]["strength"] = 77
        saved = save_datasets(self.game, self.project, data)
        result = Kernel(Path(saved["path"]))
        self.assertEqual(result.sections[19], sections[19])
        self.assertEqual(result.records("characters")[8]["values"]["strength"], 77)

    def test_save_readback_backup_and_source_unchanged(self):
        source_bytes = self.source.read_bytes()
        data = load_datasets(self.game, self.project)
        data["records"]["characters"][0]["values"]["strength"] = 70
        saved = save_datasets(self.game, self.project, data)
        first_bytes = Path(saved["path"]).read_bytes()
        data = load_datasets(self.game, self.project)
        self.assertTrue(data["usingProject"])
        self.assertEqual(data["records"]["characters"][0]["values"]["strength"], 70)
        data["records"]["characters"][0]["values"]["strength"] = 80
        saved = save_datasets(self.game, self.project, data)
        self.assertEqual(Path(saved["backup"]).read_bytes(), first_bytes)
        self.assertEqual(self.source.read_bytes(), source_bytes)
        self.assertFalse(list(self.project.rglob("*.tmp")))

    def test_stale_client_cannot_overwrite_newer_save(self):
        data = load_datasets(self.game, self.project)
        first = deepcopy(data)
        first["records"]["characters"][0]["values"]["strength"] = 80
        saved = save_datasets(self.game, self.project, first)
        saved_bytes = Path(saved["path"]).read_bytes()
        with self.assertRaisesRegex(ValueError, "changed outside"):
            save_datasets(self.game, self.project, data)
        self.assertEqual(Path(saved["path"]).read_bytes(), saved_bytes)

    def test_invalid_save_never_creates_project(self):
        data = load_datasets(self.game, self.project)
        for payload in (None, {"records": {}}, {"records": {"invented": []}}):
            with self.assertRaises(ValueError):
                save_datasets(self.game, self.project, payload)
        data["records"]["characters"][8]["values"]["strength"] = 999
        with self.assertRaises(ValueError):
            save_datasets(self.game, self.project, data)
        self.assertFalse(self.project.exists())

    def test_project_cannot_be_installed_source(self):
        original = self.source.read_bytes()
        with self.assertRaisesRegex(ValueError, "installed KERNEL"):
            save_datasets(self.game, self.game, load_datasets(self.game, self.game))
        self.assertEqual(self.source.read_bytes(), original)

    def test_bad_project_is_not_silently_replaced_from_vanilla(self):
        target = self.project / PATHS[0]
        target.parent.mkdir(parents=True)
        target.write_bytes(b"broken project")
        data = load_datasets(self.game, self.project)
        self.assertTrue(data["usingProject"])
        self.assertEqual(data["records"], {})
        with self.assertRaises(ValueError):
            save_datasets(self.game, self.project, data)
        self.assertEqual(target.read_bytes(), b"broken project")


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.project = self.root / "project"
        for name, value in (("GAME_ROOT", self.game), ("PROJECT_ROOT", self.project), ("DATA_ROOT", self.root / "data")):
            context = patch.object(server, name, value)
            context.start()
            self.addCleanup(context.stop)
        self.http = server.create_server(0)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_http)
        self.url = f"http://127.0.0.1:{self.http.server_port}"

    def stop_http(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(3)

    def request(self, path, payload=None):
        request = Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def config(self):
        (self.game / "FFNx.toml").write_bytes(CONFIG)
        return self.request("/api/platform-config")[1]

    def test_missing_kernel_still_exposes_dashboard_map_and_tweaks(self):
        for path in ("/api/dashboard", "/api/datamap", "/api/data", "/api/platform-config"):
            status, data = self.request(path)
            self.assertEqual(status, 200, data)
        data = self.request("/api/datamap")[1]
        rows = {row["category"]: row for row in data["rows"]}
        self.assertEqual(rows["characters"]["status"], "blocked")
        self.assertEqual(rows["tweaks"]["status"], "partial")
        self.assertFalse((self.game / "FFNx.toml").exists())

    def test_map_reports_per_category_proof_and_missing_work(self):
        write_kernel(self.game / PATHS[0])
        rows = self.request("/api/datamap")[1]["rows"]
        self.assertEqual(sum(row["status"] == "integrated" for row in rows), 5)
        for row in rows:
            if row["category"] in ("enemies", "encounters", "shops"):
                self.assertEqual(row["status"], "not-integrated")
                self.assertGreater(len(row["notes"]), 100)
                self.assertFalse(row["openable"])
        character = next(row for row in rows if row["category"] == "characters")
        self.assertTrue(character["openable"])
        self.assertEqual(character["status"], "partial")

    def test_config_appears_without_kernel_and_filters_other_game(self):
        config = self.config()
        fields = {f["id"]: f for s in config["sections"] for f in s["fields"]}
        self.assertIn("ff7_option", fields)
        self.assertNotIn("ff8_option", fields)
        self.assertEqual({f["kind"] for f in fields.values()}, {"boolean", "integer", "enum", "number", "string", "list"})
        status, saved = self.request("/api/platform-config/save", {"sha256": config["sha256"], "changes": {"windowed": False}})
        self.assertEqual(status, 200, saved)
        self.assertNotIn("ff8_option", [f["id"] for s in saved["sections"] for f in s["fields"]])
        self.assertEqual((self.game / "FFNx.toml").read_bytes(), CONFIG.replace(b"windowed = true", b"windowed = false"))
        self.assertEqual(Path(saved["backup"]).read_bytes(), CONFIG)

    def test_config_cannot_write_ff8_keys_invalid_values_or_stale_snapshot(self):
        config = self.config()
        for changes in ({"ff8_option": True}, {"volume": 101}, {"windowed": 1}, {"mode": 9}):
            status, _ = self.request("/api/platform-config/save", {"sha256": config["sha256"], "changes": changes})
            self.assertEqual(status, 400)
            self.assertEqual((self.game / "FFNx.toml").read_bytes(), CONFIG)
        status, _ = self.request("/api/platform-config/save", {"sha256": "stale", "changes": {"volume": 50}})
        self.assertEqual(status, 400)
        self.assertEqual((self.game / "FFNx.toml").read_bytes(), CONFIG)

    def test_game_running_refuses_configuration_write(self):
        config = self.config()
        with patch.object(platform_config, "_running", return_value=True):
            status, result = self.request("/api/platform-config/save", {"sha256": config["sha256"], "changes": {"volume": 50}})
        self.assertEqual(status, 400)
        self.assertIn("Close the game", result["error"])
        self.assertEqual((self.game / "FFNx.toml").read_bytes(), CONFIG)

    def test_http_character_save_roundtrip_for_both_editions(self):
        for relative in PATHS:
            other = PATHS[1 - PATHS.index(relative)]
            (self.game / other).unlink(missing_ok=True)
            write_kernel(self.game / relative)
            status, data = self.request("/api/data")
            self.assertEqual(status, 200)
            data["records"]["characters"][0]["values"]["killsForLimit2"] = 234
            status, saved = self.request("/api/save", data)
            self.assertEqual(status, 200, saved)
            self.assertEqual(Kernel(Path(saved["path"])).records("characters")[0]["values"]["killsForLimit2"], 234)


if __name__ == "__main__":
    unittest.main(verbosity=2)
