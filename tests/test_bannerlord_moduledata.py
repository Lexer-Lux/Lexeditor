from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_xml_data import (
    augment_data_map,
    list_documents,
    read_document,
    save_document,
)


ITEMS = '''<Items>
  <!-- preserve module-specific data -->
  <Item id="torch" name="{=TorchKey}Torch" weight="0.2" is_merchandise="false" Type="OneHandedWeapon" CustomAttribute="keep">
    <ItemComponent>
      <Weapon swing_damage="6" speed_rating="97" weapon_class="OneHandedAxe">
        <WeaponFlags MeleeWeapon="true" UnknownFlag="keep" />
      </Weapon>
    </ItemComponent>
    <Flags Civilian="true" />
  </Item>
  <CraftedItem id="peasant_maul_t1" name="Sledgehammer" crafting_template="TwoHandedPolearm">
    <Pieces>
      <Piece id="spear_blade_44" Type="Blade" scale_factor="102" />
    </Pieces>
  </CraftedItem>
</Items>
'''


class BannerlordModuleDataTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        project = Path(temporary.name)
        source = project / "ModuleData" / "items.xml"
        source.parent.mkdir(parents=True)
        source.write_text(ITEMS, encoding="utf-8")
        return temporary, project, source

    def test_document_exposes_records_nested_nodes_and_typed_literals(self):
        temporary, project, _source = self.fixture()
        try:
            self.assertEqual(list_documents(project), ["ModuleData/items.xml"])
            value = read_document(project, "ModuleData/items.xml")
            self.assertEqual(value["rootTag"], "Items")
            self.assertEqual(value["recordCount"], 2)
            self.assertEqual(value["records"][0]["id"], "torch")
            self.assertEqual(value["records"][1]["tag"], "CraftedItem")
            item = next(row for row in value["elements"] if row["tag"] == "Item")
            weapon = next(row for row in value["elements"] if row["tag"] == "Weapon")
            item_attributes = {row["name"]: row for row in item["attributes"]}
            weapon_attributes = {row["name"]: row for row in weapon["attributes"]}
            self.assertEqual(item_attributes["weight"]["kind"], "number")
            self.assertEqual(item_attributes["is_merchandise"]["kind"], "bool")
            self.assertEqual(item_attributes["Type"]["kind"], "text")
            self.assertEqual(weapon_attributes["swing_damage"]["kind"], "number")
        finally:
            temporary.cleanup()

    def test_nested_attribute_save_preserves_unknown_data_and_formatting(self):
        temporary, project, source = self.fixture()
        try:
            value = read_document(project, "ModuleData/items.xml")
            weapon = next(row for row in value["elements"] if row["tag"] == "Weapon")
            flag = next(row for row in value["elements"] if row["tag"] == "WeaponFlags")
            result = save_document(
                project,
                value["relativePath"],
                [
                    {
                        "elementPath": weapon["path"],
                        "tag": "Weapon",
                        "attribute": "swing_damage",
                        "originalValue": "6",
                        "value": 8,
                    },
                    {
                        "elementPath": flag["path"],
                        "tag": "WeaponFlags",
                        "attribute": "MeleeWeapon",
                        "originalValue": "true",
                        "value": False,
                    },
                ],
            )
            self.assertEqual(result["saved"], 2)
            self.assertTrue(Path(result["backup"]).is_file())
            rewritten = source.read_text(encoding="utf-8")
            self.assertIn('swing_damage="8"', rewritten)
            self.assertIn('MeleeWeapon="false"', rewritten)
            self.assertIn('UnknownFlag="keep"', rewritten)
            self.assertIn('CustomAttribute="keep"', rewritten)
            self.assertIn("<!-- preserve module-specific data -->", rewritten)
            self.assertEqual(rewritten.count("\n"), ITEMS.count("\n"))
        finally:
            temporary.cleanup()

    def test_stale_write_and_path_escape_are_rejected(self):
        temporary, project, source = self.fixture()
        try:
            value = read_document(project, "ModuleData/items.xml")
            item = next(row for row in value["elements"] if row["tag"] == "Item")
            source.write_text(ITEMS.replace('weight="0.2"', 'weight="0.3"'), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed on disk"):
                save_document(
                    project,
                    value["relativePath"],
                    [{
                        "elementPath": item["path"],
                        "tag": "Item",
                        "attribute": "weight",
                        "originalValue": "0.2",
                        "value": 0.4,
                    }],
                )
            with self.assertRaisesRegex(ValueError, "only opens XML files under ModuleData"):
                read_document(project, "../outside.xml")
        finally:
            temporary.cleanup()

    def test_data_map_only_upgrades_record_documents(self):
        temporary, project, source = self.fixture()
        try:
            empty = project / "ModuleData" / "empty.xml"
            empty.write_text("<Empty />", encoding="utf-8")
            value = augment_data_map(project, {"rows": [
                {"filename": "ModuleData/items.xml", "coverage": "source", "target": "", "sourcePath": str(source)},
                {"filename": "ModuleData/empty.xml", "coverage": "source", "target": "", "sourcePath": str(empty)},
                {"filename": "GUI/Prefabs/Test.xml", "coverage": "source", "target": ""},
            ]})
            items, empty_row, gui = value["rows"]
            self.assertEqual(items["coverage"], "structured")
            self.assertEqual(items["target"], "moduledata")
            self.assertEqual(items["editorPath"], "ModuleData/items.xml")
            self.assertEqual(empty_row["coverage"], "source")
            self.assertEqual(gui["coverage"], "source")
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
