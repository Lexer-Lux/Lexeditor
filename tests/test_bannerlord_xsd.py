from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_xml_data import read_document, save_document
from games.bannerlord.xsd_data import find_schema, parse_schema


SCHEMA = '''<?xml version="1.0" encoding="utf-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" id="Items">
  <xs:simpleType name="ItemTypeEnum">
    <xs:restriction base="xs:string">
      <xs:enumeration value="Weapon" />
      <xs:enumeration value="Armor" />
    </xs:restriction>
  </xs:simpleType>
  <xs:simpleType name="TierType">
    <xs:restriction base="xs:int">
      <xs:minInclusive value="0" />
      <xs:maxInclusive value="6" />
    </xs:restriction>
  </xs:simpleType>
  <xs:complexType name="ItemType">
    <xs:attribute name="id" type="xs:string" use="required" />
    <xs:attribute name="enabled" type="xs:boolean" />
    <xs:attribute name="weight" type="xs:float" />
    <xs:attribute name="Type" type="ItemTypeEnum" />
    <xs:attribute name="tier" type="TierType" />
    <xs:attribute name="fixedValue" type="xs:string" fixed="locked" />
  </xs:complexType>
  <xs:complexType name="ItemsType">
    <xs:sequence>
      <xs:element name="Item" type="ItemType" minOccurs="0" maxOccurs="unbounded" />
    </xs:sequence>
  </xs:complexType>
  <xs:element name="Items" type="ItemsType" />
</xs:schema>
'''

SUBMODULE = '''<Module>
  <Name value="Schema Fixture" />
  <Id value="SchemaFixture" />
  <Xmls>
    <XmlNode>
      <XmlName id="Items" path="items" />
      <IncludedGameTypes><GameType value="Campaign" /></IncludedGameTypes>
    </XmlNode>
  </Xmls>
</Module>
'''

ITEMS = '''<Items>
  <Item id="test_item" enabled="true" weight="0.5" Type="Weapon" tier="2" fixedValue="locked" />
</Items>
'''


class BannerlordXsdTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        project = root / "project"
        game = root / "game"
        (project / "ModuleData").mkdir(parents=True)
        (game / "XmlSchemas").mkdir(parents=True)
        (project / "SubModule.xml").write_text(SUBMODULE, encoding="utf-8")
        source = project / "ModuleData" / "items.xml"
        source.write_text(ITEMS, encoding="utf-8")
        schema = game / "XmlSchemas" / "Items.xsd"
        schema.write_text(SCHEMA, encoding="utf-8")
        return temporary, project, game, source, schema

    def test_schema_discovery_and_attribute_controls(self):
        temporary, project, game, _source, schema_path = self.fixture()
        try:
            parsed = parse_schema(schema_path)
            self.assertEqual(parsed["id"], "Items")
            found = find_schema(game, "Items", "Items")
            self.assertIsNotNone(found)
            self.assertEqual(found["path"], str(schema_path.resolve()))

            document = read_document(project, "ModuleData/items.xml", game)
            self.assertEqual(document["schema"]["id"], "Items")
            self.assertEqual(document["schemaIssueCount"], 0)
            item = next(row for row in document["elements"] if row["tag"] == "Item")
            attrs = {row["name"]: row for row in item["attributes"]}
            self.assertTrue(attrs["id"]["required"])
            self.assertEqual(attrs["enabled"]["kind"], "bool")
            self.assertEqual(attrs["weight"]["kind"], "number")
            self.assertEqual(attrs["Type"]["kind"], "enum")
            self.assertEqual(attrs["Type"]["choices"], ["Weapon", "Armor"])
            self.assertEqual(attrs["tier"]["kind"], "number")
            self.assertTrue(attrs["tier"]["integer"])
            self.assertEqual(attrs["tier"]["min"], 0.0)
            self.assertEqual(attrs["tier"]["max"], 6.0)
            self.assertEqual(attrs["fixedValue"]["fixed"], "locked")
            self.assertEqual(item["schemaIssues"], [])
            self.assertEqual(item["missingRequired"], [])
        finally:
            temporary.cleanup()

    def test_existing_invalid_values_and_missing_required_attributes_are_reported(self):
        temporary, project, game, source, _schema_path = self.fixture()
        try:
            source.write_text(
                '<Items>\n'
                '  <Item enabled="maybe" weight="heavy" Type="Food" tier="7.5" fixedValue="changed" />\n'
                '</Items>\n',
                encoding="utf-8",
            )
            document = read_document(project, "ModuleData/items.xml", game)
            self.assertEqual(document["schemaIssueCount"], 6)
            self.assertEqual(document["records"][0]["schemaIssueCount"], 6)
            item = next(row for row in document["elements"] if row["tag"] == "Item")
            self.assertEqual([row["name"] for row in item["missingRequired"]], ["id"])
            self.assertEqual(item["missingRequired"][0]["kind"], "text")
            issues = "\n".join(item["schemaIssues"])
            self.assertIn("Missing required attribute: id", issues)
            self.assertIn("enabled has value 'maybe'; expected an XML boolean", issues)
            self.assertIn("weight has value 'heavy'; expected float", issues)
            self.assertIn("Type has value 'Food'; expected one of", issues)
            self.assertIn("tier has value '7.5'; expected an integer", issues)
            self.assertIn("fixedValue must equal fixed schema value 'locked'", issues)
            attrs = {row["name"]: row for row in item["attributes"]}
            self.assertIn("schemaIssue", attrs["enabled"])
            self.assertIn("schemaIssue", attrs["weight"])
            self.assertIn("schemaIssue", attrs["Type"])
            self.assertIn("schemaIssue", attrs["tier"])
            self.assertIn("schemaIssue", attrs["fixedValue"])
        finally:
            temporary.cleanup()

    def test_missing_required_attribute_can_be_repaired_surgically(self):
        temporary, project, game, source, _schema_path = self.fixture()
        try:
            source.write_text(
                '<Items>\n'
                '  <Item enabled="true" weight="0.5" Type="Weapon" tier="2" fixedValue="locked" />\n'
                '</Items>\n',
                encoding="utf-8",
            )
            document = read_document(project, "ModuleData/items.xml", game)
            item = next(row for row in document["elements"] if row["tag"] == "Item")
            self.assertEqual(document["schemaIssueCount"], 1)
            saved = save_document(
                project,
                document["relativePath"],
                [{
                    "addRequired": True,
                    "elementPath": item["path"],
                    "tag": "Item",
                    "attribute": "id",
                    "value": "sword & shield",
                }],
                game,
            )
            self.assertEqual(saved["saved"], 1)
            self.assertEqual(saved["schemaIssueCount"], 0)
            self.assertEqual(saved["records"][0]["id"], "sword & shield")
            rewritten = source.read_text(encoding="utf-8")
            self.assertEqual(
                rewritten,
                '<Items>\n'
                '  <Item enabled="true" weight="0.5" Type="Weapon" tier="2" fixedValue="locked" id="sword &amp; shield" />\n'
                '</Items>\n',
            )
            self.assertTrue(Path(saved["backup"]).is_file())

            with self.assertRaisesRegex(ValueError, "already has attribute id"):
                save_document(
                    project,
                    document["relativePath"],
                    [{"addRequired": True, "elementPath": item["path"], "tag": "Item", "attribute": "id", "value": "duplicate"}],
                    game,
                )
            with self.assertRaisesRegex(ValueError, "not a schema-declared missing required attribute"):
                save_document(
                    project,
                    document["relativePath"],
                    [{"addRequired": True, "elementPath": item["path"], "tag": "Item", "attribute": "madeUp", "value": "nope"}],
                    game,
                )
        finally:
            temporary.cleanup()

    def test_schema_constraints_are_enforced_on_surgical_save(self):
        temporary, project, game, source, _schema_path = self.fixture()
        try:
            document = read_document(project, "ModuleData/items.xml", game)
            item = next(row for row in document["elements"] if row["tag"] == "Item")
            path = item["path"]

            for attribute, incoming, message in (
                ("Type", "Food", "must be one of"),
                ("tier", 7, "must be at most"),
                ("tier", 2.5, "must be an integer"),
                ("fixedValue", "changed", "fixed by the XML schema"),
            ):
                original = next(row["value"] for row in item["attributes"] if row["name"] == attribute)
                with self.assertRaisesRegex(ValueError, message):
                    save_document(
                        project,
                        document["relativePath"],
                        [{
                            "elementPath": path,
                            "tag": "Item",
                            "attribute": attribute,
                            "originalValue": original,
                            "value": incoming,
                        }],
                        game,
                    )

            saved = save_document(
                project,
                document["relativePath"],
                [
                    {"elementPath": path, "tag": "Item", "attribute": "Type", "originalValue": "Weapon", "value": "Armor"},
                    {"elementPath": path, "tag": "Item", "attribute": "tier", "originalValue": "2", "value": 3},
                    {"elementPath": path, "tag": "Item", "attribute": "weight", "originalValue": "0.5", "value": 0.75},
                ],
                game,
            )
            self.assertEqual(saved["saved"], 3)
            self.assertEqual(saved["schemaIssueCount"], 0)
            rewritten = source.read_text(encoding="utf-8")
            self.assertIn('Type="Armor"', rewritten)
            self.assertIn('tier="3"', rewritten)
            self.assertIn('weight="0.75"', rewritten)
            self.assertTrue(Path(saved["backup"]).is_file())
        finally:
            temporary.cleanup()

    def test_xml_schema_numeric_boolean_forms_round_trip(self):
        temporary, project, game, source, _schema_path = self.fixture()
        try:
            source.write_text(
                '<Items>\n'
                '  <Item id="test_item" enabled="1" weight="0.5" Type="Weapon" tier="2" fixedValue="locked" />\n'
                '</Items>\n',
                encoding="utf-8",
            )
            document = read_document(project, "ModuleData/items.xml", game)
            self.assertEqual(document["schemaIssueCount"], 0)
            item = next(row for row in document["elements"] if row["tag"] == "Item")
            enabled = next(row for row in item["attributes"] if row["name"] == "enabled")
            self.assertEqual(enabled["kind"], "bool")
            self.assertEqual(enabled["value"], "1")

            saved = save_document(
                project,
                document["relativePath"],
                [{
                    "elementPath": item["path"],
                    "tag": "Item",
                    "attribute": "enabled",
                    "originalValue": "1",
                    "value": "0",
                }],
                game,
            )
            self.assertEqual(saved["saved"], 1)
            self.assertEqual(saved["schemaIssueCount"], 0)
            self.assertIn('enabled="0"', source.read_text(encoding="utf-8"))
        finally:
            temporary.cleanup()

    def test_without_schema_document_remains_conservative(self):
        temporary, project, _game, _source, _schema_path = self.fixture()
        try:
            no_schema_game = Path(temporary.name) / "no-schema-game"
            no_schema_game.mkdir()
            document = read_document(project, "ModuleData/items.xml", no_schema_game)
            self.assertIsNone(document["schema"])
            self.assertEqual(document["schemaIssueCount"], 0)
            item = next(row for row in document["elements"] if row["tag"] == "Item")
            attrs = {row["name"]: row for row in item["attributes"]}
            self.assertEqual(attrs["Type"]["kind"], "text")
            self.assertEqual(attrs["tier"]["kind"], "number")
            self.assertNotIn("max", attrs["tier"])
            self.assertNotIn("schemaIssues", item)
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
