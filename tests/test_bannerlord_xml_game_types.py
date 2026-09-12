from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from games.bannerlord.module_data import save_module


class BannerlordXmlGameTypeTests(unittest.TestCase):
    def test_new_xml_registration_requires_at_least_one_game_type(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            original = '<Module><Name value="Example"/><Id value="Example"/><Version value="v1.0.0"/></Module>'
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "at least one included game type"):
                save_module(path, {"xmls": [{"index": None, "id": "Items", "path": "items", "includedGameTypes": []}]})
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertFalse(path.with_name(path.name + ".lexeditor.bak").exists())

    def test_new_xml_registration_with_game_type_uses_modern_schema_shape(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('<Module><Name value="Example"/><Id value="Example"/><Version value="v1.0.0"/></Module>', encoding="utf-8")
            save_module(path, {"xmls": [{
                "index": None,
                "id": "Items",
                "path": "items",
                "includedGameTypes": [{"index": None, "value": "Campaign", "attributes": {}}],
            }]})
            node = ET.parse(path).getroot().find("./Xmls/XmlNode")
            self.assertEqual(node.find("XmlName").attrib, {"id": "Items", "path": "items"})
            self.assertEqual(node.find("./IncludedGameTypes/GameType").attrib.get("value"), "Campaign")

    def test_existing_empty_registration_can_be_preserved_during_unrelated_edit(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('''<Module><Name value="Example"/><Id value="Example"/><Version value="v1.0.0"/><Xmls><XmlNode><XmlName id="Items" path="items"/></XmlNode></Xmls></Module>''', encoding="utf-8")
            save_module(path, {
                "metadata": {"name": "Renamed"},
                "xmls": [{"index": 0, "id": "Items", "path": "items", "includedGameTypes": []}],
            })
            node = ET.parse(path).getroot().find("./Xmls/XmlNode")
            self.assertIsNone(node.find("IncludedGameTypes"))


if __name__ == "__main__":
    unittest.main()
