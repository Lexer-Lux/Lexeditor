from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from games.palworld.full_server import _validate_schema_edits_with_utility
from games.palworld.palschema import field_schema
from games.palworld.palschema_fields import schema_scalar_writable
from games.palworld.palschema_utility import (
    apply_existing_utility_policy,
    resolve_utility_constraint,
    validate_utility_value,
)


class PalSchemaUtilityConstraintTests(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        schemas = root / "schemas"
        (schemas / "raw").mkdir(parents=True)
        (schemas / "raw" / "DT_Test.schema.json").write_text(json.dumps({
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "Plain": {"type": "string", "description": "FString"},
                    "ObjectPath": {
                        "type": "string",
                        "description": "ObjectProperty",
                        "$ref": "../utility.schema.json#/definitions/ObjectPathRegex",
                    },
                    "ClassPath": {
                        "type": "string",
                        "description": "ClassProperty",
                        "$ref": "../utility.schema.json#/definitions/ClassPathRegex",
                    },
                    "UnknownUtility": {
                        "type": "string",
                        "$ref": "../utility.schema.json#/definitions/FutureConstraint",
                    },
                },
            },
        }, indent=2) + "\n", encoding="utf-8")
        (schemas / "utility.schema.json").write_text(json.dumps({
            "definitions": {
                "ObjectPathRegex": {
                    "description": "Object Path",
                    "pattern": r"^/Game(?:/[^/]+)*/([A-Za-z0-9_]+)\.\1$",
                },
                "ClassPathRegex": {
                    "description": "Class Path",
                    "pattern": r"^/Game(?:/[^/]+)*/([A-Za-z0-9_]+)\.\1_C$",
                },
            },
        }, indent=2) + "\n", encoding="utf-8")
        (schemas / "enums.schema.json").write_text('{"definitions":{}}\n', encoding="utf-8")
        return schemas

    def test_known_generated_utility_refs_resolve_and_validate(self):
        with tempfile.TemporaryDirectory() as temp_name:
            schemas = self.fixture(Path(temp_name))
            object_ref = str(field_schema(schemas, "DT_Test", "ObjectPath")["reference"])
            class_ref = str(field_schema(schemas, "DT_Test", "ClassPath")["reference"])

            object_constraint = resolve_utility_constraint(schemas, object_ref)
            class_constraint = resolve_utility_constraint(schemas, class_ref)
            self.assertTrue(object_constraint["resolved"])
            self.assertEqual("ObjectPathRegex", object_constraint["name"])
            self.assertTrue(class_constraint["resolved"])
            self.assertEqual("ClassPathRegex", class_constraint["name"])

            self.assertEqual(
                "/Game/Others/T_Test.T_Test",
                validate_utility_value(schemas, object_ref, "/Game/Others/T_Test.T_Test"),
            )
            self.assertEqual(
                "/Game/Pal/BP_Test.BP_Test_C",
                validate_utility_value(schemas, class_ref, "/Game/Pal/BP_Test.BP_Test_C"),
            )
            with self.assertRaises(ValueError):
                validate_utility_value(schemas, object_ref, "/Game/Others/T_Test.Other")
            with self.assertRaises(ValueError):
                validate_utility_value(schemas, class_ref, "/Game/Pal/BP_Test.BP_Test")

    def test_existing_utility_fields_are_enabled_but_invalid_values_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_name:
            schemas = self.fixture(Path(temp_name))
            payload = {
                "writable": True,
                "records": [
                    {
                        "table": "DT_Test",
                        "row": "Row",
                        "field": "ObjectPath",
                        "value": "/Game/Others/T_Test.T_Test",
                        "kind": "string",
                        "writable": False,
                        "schemaState": "constraint-unresolved",
                        "reason": "blocked",
                    },
                    {
                        "table": "DT_Test",
                        "row": "Row",
                        "field": "ClassPath",
                        "value": "/Game/Pal/BP_Test.Wrong_C",
                        "kind": "string",
                        "writable": False,
                        "schemaState": "constraint-unresolved",
                        "reason": "blocked",
                    },
                ],
            }
            result = apply_existing_utility_policy(payload, schemas)
            object_record, class_record = result["records"]
            self.assertTrue(object_record["writable"])
            self.assertEqual("matched", object_record["schemaState"])
            self.assertEqual("ObjectPathRegex", object_record["utilityConstraint"])
            self.assertFalse(class_record["writable"])
            self.assertEqual("value-mismatch", class_record["schemaState"])

    def test_save_validation_accepts_valid_existing_paths_and_rejects_bad_or_unknown_refs(self):
        with tempfile.TemporaryDirectory() as temp_name:
            schemas = self.fixture(Path(temp_name))
            _validate_schema_edits_with_utility([
                {
                    "table": "DT_Test",
                    "row": "Row",
                    "field": "ObjectPath",
                    "value": "/Game/New/T_New.T_New",
                },
                {
                    "table": "DT_Test",
                    "row": "Row",
                    "field": "ClassPath",
                    "value": "/Game/New/BP_New.BP_New_C",
                },
                {"table": "DT_Test", "row": "Row", "field": "Plain", "value": "ok"},
            ], schemas)

            with self.assertRaises(ValueError):
                _validate_schema_edits_with_utility([
                    {
                        "table": "DT_Test",
                        "row": "Row",
                        "field": "ObjectPath",
                        "value": "/Game/New/T_New.Wrong",
                    },
                ], schemas)
            with self.assertRaises(ValueError):
                _validate_schema_edits_with_utility([
                    {
                        "table": "DT_Test",
                        "row": "Row",
                        "field": "UnknownUtility",
                        "value": "anything",
                    },
                ], schemas)

    def test_utility_refs_remain_non_addable_without_asset_identity(self):
        with tempfile.TemporaryDirectory() as temp_name:
            schemas = self.fixture(Path(temp_name))
            object_spec = field_schema(schemas, "DT_Test", "ObjectPath")
            allowed, reason = schema_scalar_writable(object_spec)
            self.assertFalse(allowed)
            self.assertIn("referenced constraint", reason)


if __name__ == "__main__":
    unittest.main()
