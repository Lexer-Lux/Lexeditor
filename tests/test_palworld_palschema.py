from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from games.palworld.palschema import (
    PatchValidationError,
    RawPatchDocument,
    ReadOnlyPatchError,
    StalePatchError,
    discover_raw_patches,
    patch_payload,
    resolve_discovered_patch,
    validate_raw_patch,
)


class PalSchemaRawPatchTests(unittest.TestCase):
    def info(self) -> dict:
        return {
            "PackageName": "FixtureMod",
            "InstallRule": [{"Type": "PalSchema", "Targets": ["./PalSchema/"]}],
        }

    def test_scalar_edit_round_trip_preserves_unmodeled_values_and_backup(self):
        fixture = {
            "DT_PalMonsterParameter": {
                "Kitsunebi": {
                    "WorkSuitability_EmitFlame": 3,
                    "Price": 10.5,
                    "Enabled": True,
                    "Label": "Foxparks",
                    "Nested": {"Keep": [1, 2, 3]},
                }
            },
            "FutureTable": {"FutureRow": {"Future": {"Nested": True}}},
        }
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "balance.json"
            raw = (json.dumps(fixture, separators=(",", ":")) + "\n").encode()
            path.write_bytes(raw)
            doc = RawPatchDocument.load(path)
            changed = doc.apply_edits([
                {"table": "DT_PalMonsterParameter", "row": "Kitsunebi", "field": "WorkSuitability_EmitFlame", "value": 4},
                {"table": "DT_PalMonsterParameter", "row": "Kitsunebi", "field": "Price", "value": 12},
            ])
            self.assertEqual(2, changed)
            new_sha = doc.save()
            reread = json.loads(path.read_text("utf-8"))
            self.assertEqual(4, reread["DT_PalMonsterParameter"]["Kitsunebi"]["WorkSuitability_EmitFlame"])
            self.assertEqual(12.0, reread["DT_PalMonsterParameter"]["Kitsunebi"]["Price"])
            self.assertEqual({"Keep": [1, 2, 3]}, reread["DT_PalMonsterParameter"]["Kitsunebi"]["Nested"])
            self.assertEqual({"Nested": True}, reread["FutureTable"]["FutureRow"]["Future"])
            self.assertEqual(raw, (path.parent / "balance.json.lexeditor.bak").read_bytes())
            self.assertEqual(new_sha, RawPatchDocument.load(path).source_sha256)

    def test_generated_schema_controls_types_enums_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            schema_root = root / "schemas"
            (schema_root / "raw").mkdir(parents=True)
            (schema_root / "raw" / "DT_Test.schema.json").write_text(json.dumps({
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "IntValue": {"type": "integer", "description": "IntProperty"},
                        "FloatValue": {"type": "number", "description": "FloatProperty"},
                        "Mode": {
                            "type": "string",
                            "description": "EnumProperty",
                            "$ref": "../enums.schema.json#/definitions/ETestMode",
                        },
                        "Nested": {"type": "object", "description": "StructProperty", "properties": {}},
                    },
                },
            }), encoding="utf-8")
            (schema_root / "enums.schema.json").write_text(json.dumps({
                "definitions": {
                    "ETestMode": {"type": "string", "enum": ["ModeA", "ModeB"]}
                }
            }), encoding="utf-8")

            path = root / "typed.json"
            path.write_text(json.dumps({
                "DT_Test": {
                    "Row": {
                        "IntValue": 1,
                        "FloatValue": 2,
                        "Mode": "ModeA",
                        "Nested": {"Keep": True},
                        "UnknownField": 9,
                    }
                }
            }), encoding="utf-8")
            doc = RawPatchDocument.load(path, schema_root=schema_root)
            records = {row["field"]: row for row in doc.records()}
            self.assertEqual("integer", records["IntValue"]["schemaType"])
            self.assertEqual("int", records["IntValue"]["kind"])
            self.assertTrue(records["IntValue"]["writable"])
            self.assertEqual("number", records["FloatValue"]["schemaType"])
            self.assertEqual("float", records["FloatValue"]["kind"])
            self.assertEqual(["ModeA", "ModeB"], records["Mode"]["enumValues"])
            self.assertTrue(records["Mode"]["writable"])
            self.assertFalse(records["Nested"]["writable"])
            self.assertEqual("field-missing", records["UnknownField"]["schemaState"])
            self.assertFalse(records["UnknownField"]["writable"])

            doc.apply_edits([
                {"table": "DT_Test", "row": "Row", "field": "IntValue", "value": 2},
                {"table": "DT_Test", "row": "Row", "field": "FloatValue", "value": 2.5},
                {"table": "DT_Test", "row": "Row", "field": "Mode", "value": "ModeB"},
            ])
            self.assertEqual(2.5, doc.data["DT_Test"]["Row"]["FloatValue"])
            self.assertEqual("ModeB", doc.data["DT_Test"]["Row"]["Mode"])
            with self.assertRaises(ValueError):
                doc.apply_edits([{"table": "DT_Test", "row": "Row", "field": "Mode", "value": "ModeC"}])
            with self.assertRaises(ValueError):
                doc.apply_edits([{"table": "DT_Test", "row": "Row", "field": "UnknownField", "value": 10}])

    def test_noop_json_save_is_byte_exact(self):
        raw = b'{"DT_Test":{"Row":{"Value":1}}}\n'
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "test.json"
            path.write_bytes(raw)
            doc = RawPatchDocument.load(path)
            doc.save()
            self.assertEqual(raw, path.read_bytes())
            self.assertFalse(path.with_name(path.name + ".lexeditor.bak").exists())

    def test_jsonc_comments_parse_and_noop_preserves_bytes_but_changed_write_is_blocked(self):
        raw = b'''{
  // table comment
  "DT_Test": {
    "Row": {
      "Value": 1, /* keep this comment */
      "Text": "http://example.invalid/*still-string*/"
    }
  }
}
'''
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "commented.jsonc"
            path.write_bytes(raw)
            doc = RawPatchDocument.load(path)
            self.assertEqual(1, doc.data["DT_Test"]["Row"]["Value"])
            self.assertEqual("http://example.invalid/*still-string*/", doc.data["DT_Test"]["Row"]["Text"])
            doc.save()
            self.assertEqual(raw, path.read_bytes())
            doc.apply_edits([{"table": "DT_Test", "row": "Row", "field": "Value", "value": 2}])
            with self.assertRaises(ReadOnlyPatchError):
                doc.save()
            self.assertEqual(raw, path.read_bytes())

    def test_loader_mechanics_validation(self):
        data = {
            "DT_Bad": {
                "Rows": [{"Name": "Bad"}],
                "*": {"$Filters": {"FieldName": "Type"}, "Value": 3},
                "DeleteMe": None,
            },
            "DT_NotObject": [],
        }
        issues = validate_raw_patch(data)
        errors = {issue.code for issue in issues if issue.severity == "error"}
        warnings = {issue.code for issue in issues if issue.severity == "warning"}
        self.assertEqual({"row.fmodel-wrapper", "filters.array", "table.object"}, errors)
        self.assertIn("row.delete", warnings)

    def test_scalar_type_is_preserved_without_generated_schemas(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "types.json"
            path.write_text(json.dumps({"DT_Test": {"Row": {"Bool": True, "Int": 1, "Float": 1.5, "Text": "x", "Nested": {}}}}), encoding="utf-8")
            doc = RawPatchDocument.load(path)
            with self.assertRaises(ValueError):
                doc.apply_edits([{"table": "DT_Test", "row": "Row", "field": "Bool", "value": 1}])
            with self.assertRaises(ValueError):
                doc.apply_edits([{"table": "DT_Test", "row": "Row", "field": "Int", "value": 1.5}])
            with self.assertRaises(ValueError):
                doc.apply_edits([{"table": "DT_Test", "row": "Row", "field": "Nested", "value": {}}])
            doc.apply_edits([
                {"table": "DT_Test", "row": "Row", "field": "Float", "value": 2},
                {"table": "DT_Test", "row": "Row", "field": "Text", "value": "y"},
            ])
            self.assertIsInstance(doc.data["DT_Test"]["Row"]["Float"], float)
            self.assertEqual("y", doc.data["DT_Test"]["Row"]["Text"])

    def test_stale_patch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "test.json"
            path.write_text('{"DT_Test":{"Row":{"Value":1}}}\n', encoding="utf-8")
            doc = RawPatchDocument.load(path)
            doc.apply_edits([{"table": "DT_Test", "row": "Row", "field": "Value", "value": 2}])
            path.write_text('{"DT_Test":{"Row":{"Value":9}}}\n', encoding="utf-8")
            external = path.read_bytes()
            with self.assertRaises(StalePatchError):
                doc.save()
            self.assertEqual(external, path.read_bytes())

    def test_invalid_patch_never_writes(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "bad.json"
            raw = b'{"DT_Test":{"Rows":[],"Row":{"Value":1}}}\n'
            path.write_bytes(raw)
            doc = RawPatchDocument.load(path)
            doc.apply_edits([{"table": "DT_Test", "row": "Row", "field": "Value", "value": 2}])
            with self.assertRaises(PatchValidationError):
                doc.save()
            self.assertEqual(raw, path.read_bytes())

    def test_official_target_and_non_recursive_discovery(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = Path(temp_name)
            raw = project / "PalSchema" / "MyBalance" / "raw"
            raw.mkdir(parents=True)
            (raw / "one.json").write_text('{"DT_Test":{"Row":{"Value":1}}}\n', encoding="utf-8")
            (raw / "two.jsonc").write_text('// c\n{"DT_Test":{"Row":{"Value":2}}}\n', encoding="utf-8")
            nested = raw / "nested"
            nested.mkdir()
            (nested / "ignored.json").write_text('{"DT_Test":{"Row":{"Value":3}}}\n', encoding="utf-8")
            outside = project / "Outside" / "Other" / "raw"
            outside.mkdir(parents=True)
            (outside / "ignored.json").write_text('{"DT_Test":{"Row":{"Value":4}}}\n', encoding="utf-8")

            rows = discover_raw_patches(project, self.info())
            self.assertEqual(["PalSchema/MyBalance/raw/one.json", "PalSchema/MyBalance/raw/two.jsonc"], [row["path"] for row in rows])
            self.assertEqual([True, False], [row["writable"] for row in rows])

            payload = patch_payload(project, self.info(), rows[0]["path"])
            self.assertEqual(1, len(payload["records"]))
            self.assertTrue(payload["writable"])
            with self.assertRaises(ValueError):
                resolve_discovered_patch(project, self.info(), "Outside/Other/raw/ignored.json")

    def test_malformed_patch_stays_catalogued_without_hiding_valid_file(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = Path(temp_name)
            raw = project / "PalSchema" / "MyBalance" / "raw"
            raw.mkdir(parents=True)
            (raw / "aaa_bad.json").write_text('{"DT_Test":', encoding="utf-8")
            (raw / "good.json").write_text('{"DT_Test":{"Row":{"Value":1}}}\n', encoding="utf-8")
            rows = discover_raw_patches(project, self.info())
            self.assertEqual(["aaa_bad.json", "good.json"], [row["name"] for row in rows])
            self.assertEqual(1, rows[0]["errors"])
            self.assertFalse(rows[0]["writable"])
            payload = patch_payload(project, self.info(), rows[1]["path"])
            self.assertEqual(1, len(payload["records"]))


if __name__ == "__main__":
    unittest.main()
