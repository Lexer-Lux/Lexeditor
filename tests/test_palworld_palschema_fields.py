from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from games.palworld.palschema import RawPatchDocument
from games.palworld.palschema_fields import available_fields, coerce_new_value
from games.palworld.server import apply_additions


class PalSchemaFieldCatalogTests(unittest.TestCase):
    def make_schemas(self, root: Path) -> Path:
        schemas = root / "schemas"
        (schemas / "raw").mkdir(parents=True)
        (schemas / "raw" / "DT_Test.schema.json").write_text(json.dumps({
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "Existing": {"type": "integer", "description": "IntProperty"},
                    "AddInt": {"type": "integer", "description": "IntProperty"},
                    "AddEnum": {
                        "type": "string",
                        "description": "EnumProperty",
                        "$ref": "../enums.schema.json#/definitions/ETest",
                    },
                    "ObjectPath": {
                        "type": "string",
                        "$ref": "../utility.schema.json#/definitions/ObjectPathRegex",
                    },
                    "Nested": {"type": "object", "properties": {}},
                },
            },
        }), encoding="utf-8")
        (schemas / "enums.schema.json").write_text(json.dumps({
            "definitions": {"ETest": {"type": "string", "enum": ["One", "Two"]}}
        }), encoding="utf-8")
        return schemas

    def test_catalog_excludes_present_and_only_enables_resolved_scalars(self):
        with tempfile.TemporaryDirectory() as temp_name:
            schemas = self.make_schemas(Path(temp_name))
            rows = {row["name"]: row for row in available_fields(
                schemas, "DT_Test", present_fields={"Existing"}
            )}
            self.assertNotIn("Existing", rows)
            self.assertTrue(rows["AddInt"]["writable"])
            self.assertEqual(0, rows["AddInt"]["default"])
            self.assertTrue(rows["AddEnum"]["writable"])
            self.assertEqual(["One", "Two"], rows["AddEnum"]["enumValues"])
            self.assertEqual("One", rows["AddEnum"]["default"])
            self.assertFalse(rows["ObjectPath"]["writable"])
            self.assertIn("referenced constraint", rows["ObjectPath"]["reason"])
            self.assertFalse(rows["Nested"]["writable"])

    def test_new_values_are_schema_coerced(self):
        with tempfile.TemporaryDirectory() as temp_name:
            schemas = self.make_schemas(Path(temp_name))
            self.assertEqual(5, coerce_new_value(schemas, "DT_Test", "AddInt", 5))
            self.assertEqual("Two", coerce_new_value(schemas, "DT_Test", "AddEnum", "Two"))
            with self.assertRaises(ValueError):
                coerce_new_value(schemas, "DT_Test", "AddInt", 1.5)
            with self.assertRaises(ValueError):
                coerce_new_value(schemas, "DT_Test", "AddEnum", "Three")
            with self.assertRaises(ValueError):
                coerce_new_value(schemas, "DT_Test", "ObjectPath", "/Game/Foo")

    def test_additions_require_existing_explicit_row_and_are_atomic_until_save(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            schemas = self.make_schemas(root)
            path = root / "patch.json"
            original = b'{"DT_Test":{"Row":{"Existing":1},"*":{"Existing":2}}}\n'
            path.write_bytes(original)
            document = RawPatchDocument.load(path, schema_root=schemas)
            self.assertEqual(1, apply_additions(document, [{
                "table": "DT_Test", "row": "Row", "field": "AddInt", "value": 7,
            }], schemas))
            self.assertEqual(7, document.data["DT_Test"]["Row"]["AddInt"])
            self.assertEqual(original, path.read_bytes())
            with self.assertRaises(ValueError):
                apply_additions(document, [{
                    "table": "DT_Test", "row": "Missing", "field": "AddInt", "value": 1,
                }], schemas)
            with self.assertRaises(ValueError):
                apply_additions(document, [{
                    "table": "DT_Test", "row": "*", "field": "AddInt", "value": 1,
                }], schemas)
            with self.assertRaises(ValueError):
                apply_additions(document, [{
                    "table": "DT_Test", "row": "Row", "field": "Existing", "value": 2,
                }], schemas)


if __name__ == "__main__":
    unittest.main()
