from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from games.palworld.palschema import field_schema
from games.palworld.palschema_fields import schema_scalar_writable
from games.palworld.server import validate_schema_edits


class PalSchemaConstraintTests(unittest.TestCase):
    def test_referenced_constraints_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_name:
            schemas = Path(temp_name) / "schemas"
            (schemas / "raw").mkdir(parents=True)
            (schemas / "raw" / "DT_Test.schema.json").write_text(json.dumps({
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "Plain": {"type": "string", "description": "FString"},
                        "ObjectPath": {
                            "type": "string",
                            "$ref": "../utility.schema.json#/definitions/ObjectPathRegex",
                        },
                        "MissingEnum": {
                            "type": "string",
                            "$ref": "../enums.schema.json#/definitions/EMissing",
                        },
                    },
                },
            }), encoding="utf-8")
            (schemas / "enums.schema.json").write_text(json.dumps({"definitions": {}}), encoding="utf-8")

            self.assertEqual((True, "Generated PalSchema scalar schema matched."),
                             schema_scalar_writable(field_schema(schemas, "DT_Test", "Plain")))
            object_allowed, object_reason = schema_scalar_writable(field_schema(schemas, "DT_Test", "ObjectPath"))
            self.assertFalse(object_allowed)
            self.assertIn("referenced constraint", object_reason)
            enum_allowed, enum_reason = schema_scalar_writable(field_schema(schemas, "DT_Test", "MissingEnum"))
            self.assertFalse(enum_allowed)
            self.assertIn("enum reference", enum_reason)

            validate_schema_edits([
                {"table": "DT_Test", "row": "Row", "field": "Plain", "value": "ok"},
            ], schemas)
            with self.assertRaises(ValueError):
                validate_schema_edits([
                    {"table": "DT_Test", "row": "Row", "field": "ObjectPath", "value": "/Game/Foo"},
                ], schemas)
            with self.assertRaises(ValueError):
                validate_schema_edits([
                    {"table": "DT_Test", "row": "Row", "field": "MissingEnum", "value": "Anything"},
                ], schemas)


if __name__ == "__main__":
    unittest.main()
