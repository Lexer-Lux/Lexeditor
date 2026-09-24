from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

import plugins.ds3.server as ds3_server
from plugins.ds3.plugin import PLUGIN, check as plugin_check
from plugins.ds3.server import _data_map, _path_within
from core.plugin_api import validate_plugin
from plugins.ds3.formats import (
    BND4View,
    DS3FormatError,
    RegulationDocument,
    TARGET_TABLES,
    _TYPE_SIZE,
    decrypt_regulation,
    encrypt_regulation,
    load_schema,
)

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "plugins" / "ds3" / "metadata"


def _row_ids(table: str) -> tuple[int, int]:
    data = json.loads((METADATA / "row_names" / f"{table}.json").read_text("utf-8-sig"))
    ids = []
    for entry in data.get("Entries", []):
        try:
            row_id = int(entry["ID"])
        except (KeyError, TypeError, ValueError):
            continue
        if row_id not in ids:
            ids.append(row_id)
        if len(ids) == 2:
            return ids[0], ids[1]
    raise AssertionError(f"{table} metadata does not contain two row IDs")


def _param(table: str) -> bytes:
    schema = load_schema(METADATA, table)
    first, second = _row_ids(table)
    row_count = 2
    header_size = 0x30
    row_headers_size = row_count * 12
    data_start = header_size + row_headers_size
    total = data_start + schema.row_size * row_count
    out = bytearray(total)
    struct.pack_into("<I", out, 0x00, total)
    struct.pack_into("<H", out, 0x04, data_start)
    struct.pack_into("<h", out, 0x06, 0)
    struct.pack_into("<h", out, 0x08, schema.data_version)
    struct.pack_into("<H", out, 0x0A, row_count)
    encoded = schema.param_type.encode("ascii")
    if len(encoded) > 0x1F:
        raise AssertionError(schema.param_type)
    out[0x0C:0x0C + len(encoded)] = encoded
    out[0x2C] = 0
    out[0x2D] = 0
    out[0x2E] = 0
    out[0x2F] = 0
    for index, row_id in enumerate((first, second)):
        row_header = header_size + index * 12
        row_data = data_start + index * schema.row_size
        struct.pack_into("<iII", out, row_header, row_id, row_data, 0)
    return bytes(out)


def _reverse_bits(value: int) -> int:
    return int(f"{value:08b}"[::-1], 2)


def _align(value: int, boundary: int = 0x10) -> int:
    return (value + boundary - 1) // boundary * boundary


def _bnd4(*, compressed_first: bool = False) -> bytes:
    members = [(table, _param(table)) for table in TARGET_TABLES]
    count = len(members)
    binder_format = 0x02 | 0x04 | 0x08 | 0x20  # IDs, names, compression-size slot
    raw_format = _reverse_bits(binder_format)
    file_header_size = 0x24
    headers_end = 0x40 + count * file_header_size

    names = []
    cursor = headers_end
    for table, _member in members:
        encoded = f"param/GameParam/{table}.param".encode("utf-16-le") + b"\0\0"
        names.append((cursor, encoded))
        cursor += len(encoded)
    data_cursor = _align(cursor)

    placements = []
    for index, (table, member) in enumerate(members):
        data_cursor = _align(data_cursor)
        placements.append((index, table, member, data_cursor))
        data_cursor += len(member)

    out = bytearray(data_cursor)
    out[:4] = b"BND4"
    out[9] = 0
    out[10] = 1  # stored inverse of bitBigEndian
    struct.pack_into("<i", out, 0x0C, count)
    struct.pack_into("<q", out, 0x10, 0x40)
    out[0x18:0x20] = b"00000000"
    struct.pack_into("<q", out, 0x20, file_header_size)
    struct.pack_into("<q", out, 0x28, _align(cursor))
    out[0x30] = 1
    out[0x31] = raw_format
    out[0x32] = 0
    struct.pack_into("<q", out, 0x38, 0)

    for (name_offset, encoded), (index, _table, member, data_offset) in zip(names, placements):
        out[name_offset:name_offset + len(encoded)] = encoded
        pos = 0x40 + index * file_header_size
        logical_flags = 0x02 | (0x01 if compressed_first and index == 0 else 0)
        out[pos] = _reverse_bits(logical_flags)
        struct.pack_into("<i", out, pos + 4, -1)
        struct.pack_into("<q", out, pos + 8, len(member))
        struct.pack_into("<q", out, pos + 16, len(member))
        struct.pack_into("<I", out, pos + 24, data_offset)
        struct.pack_into("<i", out, pos + 28, index)
        struct.pack_into("<I", out, pos + 32, name_offset)
        out[data_offset:data_offset + len(member)] = member
    return bytes(out)


def _field_value(document: RegulationDocument, table: str, row_id: int, key: str):
    row = document.read_row(table, row_id)
    return next(field["value"] for field in row["fields"] if field["key"] == key)


class DS3FormatTests(unittest.TestCase):
    def test_pinned_metadata_source_record_and_plugin_descriptor(self):
        source = json.loads((METADATA / "SOURCE.json").read_text("utf-8"))
        self.assertEqual(source["revision"], "43f9b49a022260b6a76b1adcbe20cc0989ccff95")
        self.assertEqual(source["license"], "MIT")
        self.assertEqual(set(source["tables"]), set(TARGET_TABLES))
        self.assertEqual(plugin_check(), [])
        validate_plugin(PLUGIN)
        self.assertFalse(PLUGIN.mods_load)
        self.assertFalse(PLUGIN.can_launch)

    def test_project_save_is_isolated_and_reopens_export(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ds3-save-") as name:
            root = Path(name).resolve()
            project = root / "project"
            game = root / "game"
            source = root / "installed-Data0.bdt"
            project.mkdir()
            game.mkdir()
            (project / ".lexeditor-ds3-project").write_text(
                '{"schema":1,"game":"Dark Souls III"}\n', encoding="utf-8"
            )
            source.write_bytes(encrypt_regulation(_bnd4(), iv=b"\x44" * 16))
            source_before = source.read_bytes()
            saved_globals = (
                ds3_server.PROJECT, ds3_server.GAME_ROOT, ds3_server.SOURCE_OVERRIDE,
                ds3_server._DOCUMENT, ds3_server._SOURCE_PATH,
                ds3_server._SOURCE_HASH, ds3_server._OUTPUT_HASH_AT_LOAD,
            )
            try:
                ds3_server.PROJECT = project
                ds3_server.GAME_ROOT = game
                ds3_server.SOURCE_OVERRIDE = str(source)
                ds3_server._DOCUMENT = None
                ds3_server._SOURCE_PATH = None
                document = ds3_server._document()
                row_id, _ = _row_ids("EquipParamWeapon")
                document.edit("EquipParamWeapon", row_id, "atkBasePhysics", 321)
                external_output = project / "Data0.bdt"
                external_output.write_bytes(encrypt_regulation(_bnd4(), iv=b"\x45" * 16))
                with self.assertRaisesRegex(ValueError, "created externally"):
                    ds3_server._save()
                external_output.unlink()
                result = ds3_server._save()
                self.assertTrue(result["saved"])
                exported = project / "Data0.bdt"
                self.assertTrue(exported.is_file())
                self.assertEqual(source.read_bytes(), source_before)
                self.assertEqual(Path(result["source"]).resolve(), exported.resolve())
                reopened = RegulationDocument(exported.read_bytes(), METADATA)
                self.assertEqual(
                    _field_value(reopened, "EquipParamWeapon", row_id, "atkBasePhysics"), 321
                )
                live = ds3_server._document()
                live.edit("EquipParamWeapon", row_id, "atkBaseMagic", 123)
                exported.write_bytes(exported.read_bytes() + b"external")
                with self.assertRaisesRegex(ValueError, "source Data0.bdt changed"):
                    ds3_server._save()
            finally:
                (
                    ds3_server.PROJECT, ds3_server.GAME_ROOT, ds3_server.SOURCE_OVERRIDE,
                    ds3_server._DOCUMENT, ds3_server._SOURCE_PATH,
                    ds3_server._SOURCE_HASH, ds3_server._OUTPUT_HASH_AT_LOAD,
                ) = saved_globals

    def test_project_boundary_rejects_game_install_subfolders(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ds3-boundary-") as name:
            root = Path(name).resolve()
            game = root / "game"
            outside = root / "mods"
            self.assertTrue(_path_within(game, game))
            self.assertTrue(_path_within(game / "mods" / "test", game))
            self.assertFalse(_path_within(outside, game))

    def test_data_map_uses_real_installed_file_paths(self):
        rows = _data_map()["rows"]
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertTrue(all(row["filename"] == "Game/Data0.bdt" for row in rows))
        integrated = [row for row in rows if row["status"] == "integrated"]
        self.assertEqual(len(integrated), len(TARGET_TABLES))
        self.assertTrue(all(row.get("targets") for row in integrated))

    def test_all_pinned_schemas_parse(self):
        for table in TARGET_TABLES:
            schema = load_schema(METADATA, table)
            self.assertGreater(schema.row_size, 0, table)
            self.assertGreater(len(schema.fields), 20, table)
            self.assertTrue(schema.param_type, table)
            self.assertTrue(schema.row_names, table)

    def test_aes_roundtrip_is_exact(self):
        plain = _bnd4()
        encrypted = encrypt_regulation(plain, iv=b"\x11" * 16)
        reopened, was_encrypted = decrypt_regulation(encrypted)
        self.assertTrue(was_encrypted)
        self.assertEqual(reopened, plain)

    def test_real_row_identity_uses_pinned_names(self):
        doc = RegulationDocument(_bnd4(), METADATA)
        first_id, _ = _row_ids("Magic")
        rows = doc.list_rows("Magic")
        match = next(row for row in rows if row["id"] == first_id)
        expected_raw = json.loads((METADATA / "row_names" / "Magic.json").read_text("utf-8-sig"))
        expected = next(
            str(entry["Entries"][0]).strip()
            for entry in expected_raw["Entries"]
            if int(entry["ID"]) == first_id and entry.get("Entries") and str(entry["Entries"][0]).strip()
        )
        self.assertEqual(match["name"], expected)

    def test_edit_export_reopen_preserves_every_other_byte(self):
        source = encrypt_regulation(_bnd4(), iv=b"\x22" * 16)
        doc = RegulationDocument(source, METADATA)
        row_id, _ = _row_ids("EquipParamWeapon")
        schema = doc.schemas["EquipParamWeapon"]
        field = schema.field("atkBasePhysics")
        self.assertIsNone(field.bit_size)
        before = doc.plaintext()
        doc.edit("EquipParamWeapon", row_id, "atkBasePhysics", 321)
        self.assertEqual(_field_value(doc, "EquipParamWeapon", row_id, "atkBasePhysics"), 321)
        after = doc.plaintext()

        entry = BND4View(before).find_param("EquipParamWeapon")
        param = doc.params["EquipParamWeapon"]
        row = param.row(row_id)
        start = entry.data_offset + row.data_offset + field.offset
        allowed = set(range(start, start + _TYPE_SIZE[field.dtype]))
        changed = {index for index, (a, b) in enumerate(zip(before, after)) if a != b}
        self.assertTrue(changed)
        self.assertTrue(changed <= allowed, (changed - allowed))

        exported = doc.export(iv=b"\x33" * 16)
        reopened = RegulationDocument(exported, METADATA)
        self.assertEqual(_field_value(reopened, "EquipParamWeapon", row_id, "atkBasePhysics"), 321)

    def test_bit_edit_preserves_other_bits_and_reverting_clears_dirty(self):
        doc = RegulationDocument(_bnd4(), METADATA)
        row_id, _ = _row_ids("EquipParamWeapon")
        schema = doc.schemas["EquipParamWeapon"]
        field = schema.field("rightHandEquipable")
        self.assertIsNotNone(field.bit_size)
        before = doc.plaintext()
        doc.edit("EquipParamWeapon", row_id, field.key, 1)
        after = doc.plaintext()
        entry = doc.entries["EquipParamWeapon"]
        row = doc.params["EquipParamWeapon"].row(row_id)
        absolute = entry.data_offset + row.data_offset + field.offset
        changed = [index for index, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertEqual(changed, [absolute])
        self.assertEqual(doc.dirty_count, 1)
        doc.edit("EquipParamWeapon", row_id, field.key, 0)
        self.assertEqual(doc.plaintext(), before)
        self.assertEqual(doc.dirty_count, 0)

    def test_enum_rejects_values_not_in_pinned_metadata(self):
        doc = RegulationDocument(_bnd4(), METADATA)
        row_id, _ = _row_ids("Magic")
        schema = doc.schemas["Magic"]
        field = schema.field("ezStateBehaviorType")
        self.assertTrue(field.enum)
        self.assertTrue(schema.enums[field.enum])
        with self.assertRaises(DS3FormatError):
            doc.edit("Magic", row_id, field.key, 999999)

    def test_compressed_target_member_fails_closed(self):
        binder = BND4View(_bnd4(compressed_first=True))
        with self.assertRaisesRegex(DS3FormatError, "compressed"):
            binder.find_param("EquipParamWeapon")


if __name__ == "__main__":
    unittest.main()
