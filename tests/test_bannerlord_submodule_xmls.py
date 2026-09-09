from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_data import read_submodule, save_module


BASE = '''<?xml version="1.0" encoding="utf-8"?>
<Module>
  <Name value="Test" />
  <Id value="Test" />
  <Version value="v1.0.0" />
  <SingleplayerModule value="true" />
  <SubModules />
{xmls}</Module>
'''


class BannerlordSubmoduleXmlRegistrationTests(unittest.TestCase):
    def write(self, root: Path, xmls: str) -> Path:
        path = root / "SubModule.xml"
        path.write_text(BASE.format(xmls=xmls), encoding="utf-8")
        return path

    def test_reads_and_edits_modern_xmlname_registration_without_converting_shape(self):
        with tempfile.TemporaryDirectory() as name:
            path = self.write(Path(name), '''  <Xmls>
    <XmlNode>
      <XmlName id="Items" path="items" Future="keep" />
      <IncludedGameTypes><GameType value="Campaign" /></IncludedGameTypes>
    </XmlNode>
  </Xmls>
''')
            module = read_submodule(path)
            self.assertEqual(module["xmls"][0]["id"], "Items")
            self.assertEqual(module["xmls"][0]["path"], "items")
            result = save_module(path, {"xmls": [{
                **module["xmls"][0],
                "path": "items_custom",
                "includedGameTypes": [
                    {"index": 0, "value": "Campaign"},
                    {"index": None, "value": "CampaignStoryMode"},
                ],
            }]})
            self.assertEqual(result["module"]["xmls"][0]["path"], "items_custom")
            rewritten = path.read_text(encoding="utf-8")
            self.assertIn('<XmlName id="Items" path="items_custom" Future="keep"', rewritten)
            self.assertNotIn('<Id value="Items"', rewritten)
            self.assertNotIn('<Path value="items_custom"', rewritten)

    def test_new_registration_uses_current_xmlname_shape(self):
        with tempfile.TemporaryDirectory() as name:
            path = self.write(Path(name), "")
            result = save_module(path, {"xmls": [{
                "index": None,
                "id": "Items",
                "path": "items",
                "includedGameTypes": [{"index": None, "value": "Campaign"}],
            }]})
            self.assertEqual(result["module"]["xmls"][0]["id"], "Items")
            rewritten = path.read_text(encoding="utf-8")
            self.assertIn('<XmlName id="Items" path="items"', rewritten)
            self.assertIn("<IncludedGameTypes>", rewritten)

    def test_legacy_id_path_and_include_game_types_remain_compatible(self):
        with tempfile.TemporaryDirectory() as name:
            path = self.write(Path(name), '''  <Xmls>
    <XmlNode>
      <Id value="Items" />
      <Path value="items" />
      <IncludeGameTypes><GameType value="Campaign" /></IncludeGameTypes>
    </XmlNode>
  </Xmls>
''')
            module = read_submodule(path)
            self.assertEqual(module["xmls"][0]["id"], "Items")
            self.assertEqual(module["xmls"][0]["includedGameTypes"][0]["value"], "Campaign")
            save_module(path, {"xmls": [{**module["xmls"][0], "path": "legacy_items"}]})
            rewritten = path.read_text(encoding="utf-8")
            self.assertIn('<Id value="Items"', rewritten)
            self.assertIn('<Path value="legacy_items"', rewritten)
            self.assertIn("<IncludeGameTypes>", rewritten)
            self.assertNotIn("<XmlName", rewritten)


if __name__ == "__main__":
    unittest.main()
