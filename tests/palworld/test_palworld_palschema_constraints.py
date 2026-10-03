from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from plugins.palworld.palschema import RawPatchDocument, field_schema
from plugins.palworld.palschema_fields import available_fields, coerce_new_value, schema_scalar_writable
from plugins.palworld.server import validate_schema_edits


class PalSchemaConstraintTests(unittest.TestCase):
    def test_bounded_edits_additions_and_unknown_constraints_survive_reload(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            schemas = root / "schemas"
            (schemas / "raw").mkdir(parents=True)
            properties = {
                "Count": {"type": "integer", "minimum": 1, "maximum": 4},
                "NewCount": {"type": "integer", "minimum": 2.5, "maximum": 5.5},
                "Negative": {"type": "integer", "maximum": -1},
                "Mode": {"type": "integer", "enum": [1, 3]},
                "Ratio": {"type": "number", "minimum": 0.5, "maximum": 1.5},
                "Unproven": {"type": "string", "pattern": "^[A-Z]+$"},
                "Impossible": {"type": "integer", "minimum": 0.2, "maximum": 0.8},
            }
            (schemas / "raw" / "DT_Test.schema.json").write_text(json.dumps({
                "additionalProperties": {"properties": properties}
            }), encoding="utf-8")
            path = root / "patch.json"
            original = b'{"DT_Test":{"Row":{"Count":2,"Mode":1,"Ratio":1.0,"Unproven":"ABC"}}}\n'
            path.write_bytes(original)
            document = RawPatchDocument.load(path, schema_root=schemas)
            rows = {row["field"]: row for row in document.records()}
            self.assertEqual((1, 4), (rows["Count"]["minimum"], rows["Count"]["maximum"]))
            self.assertEqual([1, 3], rows["Mode"]["enumValues"])
            self.assertFalse(rows["Unproven"]["writable"])
            fields = {row["name"]: row for row in available_fields(schemas, "DT_Test")}
            self.assertEqual(3, fields["NewCount"]["default"])
            self.assertEqual(-1, fields["Negative"]["default"])
            self.assertFalse(fields["Impossible"]["writable"])
            for field, value in [("Count", 0), ("Count", 5), ("Count", 2.5),
                                 ("Mode", 2), ("Ratio", float("inf")), ("Ratio", float("nan")),
                                 ("Ratio", 1.6), ("Unproven", "DEF")]:
                edit = {"table": "DT_Test", "row": "Row", "field": field, "value": value}
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    document.apply_edits([edit])
                self.assertEqual(original, path.read_bytes())
                self.assertEqual(json.loads(original), document.data)
            with self.assertRaises(ValueError):
                coerce_new_value(schemas, "DT_Test", "NewCount", 2)
            document.apply_edits([{"table": "DT_Test", "row": "Row", "field": "Count", "value": 4},
                                  {"table": "DT_Test", "row": "Row", "field": "Mode", "value": 3}])
            document.save()
            reopened = RawPatchDocument.load(path, schema_root=schemas)
            self.assertEqual({"Count": 4, "Mode": 3, "Ratio": 1.0, "Unproven": "ABC"},
                             reopened.data["DT_Test"]["Row"])

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


def test_rendered_schema_controls(tmp_path):
    from playwright.sync_api import sync_playwright

    repo = Path(__file__).resolve().parents[2]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 900, "height": 620})
            page.route("http://fixture/**", lambda route: route.fulfill(
                body='<main id="main"></main>', content_type="text/html"))
            page.goto("http://fixture/")
            page.add_style_tag(path=str(repo / "ui/framework.css"))
            page.add_script_tag(path=str(repo / "ui/framework.js"))
            source = (repo / "plugins/palworld/editor.js").read_text("utf-8")
            assert source.endswith("init();\n")
            page.add_script_tag(content=source.removesuffix("init();\n"))
            page.evaluate("""()=>{
              window.countRecord={kind:'int',writable:true,value:2,minimum:1,maximum:4};
              window.modeRecord={kind:'int',writable:true,value:1,enumValues:[1,3]};
              const U=LexeditorUI;
              document.querySelector('main').append(U.detailPanel({title:'PalSchema',body:[
                U.detailField({label:'Count',control:scalarControl(countRecord)}),
                U.detailField({label:'Mode',control:scalarControl(modeRecord)}),
                U.detailField({label:'Protected',control:scalarControl({kind:'string',writable:false,value:'ABC'})}),
                U.detailField({label:'New count',control:schemaNumberControl(3,{minimum:2.5,maximum:5.5},true,v=>window.added=v)})
              ]}));
            }""")
            number = page.locator('input').first
            assert number.get_attribute("min") == "1"
            assert number.get_attribute("max") == "4"
            number.fill("2.5")
            assert page.evaluate("countRecord.value") == 2
            number.fill("4")
            assert page.evaluate("countRecord.value") == 4
            page.locator('select').select_option("3")
            assert page.evaluate("modeRecord.value === 3")
            protected = page.locator('input.lex-readonly-field')
            assert protected.input_value() == "ABC"
            assert protected.is_disabled()
            assert protected.is_visible()
            assert page.locator('input:not([disabled])').count() == 2
            page.screenshot(path=str(tmp_path / "palworld-schema-controls.png"))
        finally:
            browser.close()
