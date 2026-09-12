from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from games.bannerlord.module_data import save_module


class BannerlordSubModuleOrderingTests(unittest.TestCase):
    def test_new_structural_sections_insert_before_later_existing_sections(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('''<Module>
  <Name value="Example"/><Id value="Example"/><Version value="v1.0.0"/>
  <SubModules><SubModule><Name value="Example"/><DLLName value="Example.dll"/><SubModuleClassType value="Example.SubModule"/><Tags/></SubModule></SubModules>
  <Xmls><XmlNode><XmlName id="Items" path="items"/><IncludedGameTypes><GameType value="Campaign"/></IncludedGameTypes></XmlNode></Xmls>
</Module>''', encoding="utf-8")
            save_module(path, {
                "dependencies": [{"index": None, "id": "Native", "dependentVersion": "", "optional": False, "attributes": {}}],
                "modulesToLoadAfterThis": [{"index": None, "id": "After.Mod", "attributes": {}}],
                "incompatibleModules": [{"index": None, "id": "Bad.Mod", "elementTag": "Module", "attributes": {}}],
                "communityDependencies": [{"index": None, "id": "Harmony", "order": "LoadBeforeThis", "optional": True, "incompatible": False, "version": "", "attributes": {}}],
            })
            root = ET.parse(path).getroot()
            tags = [child.tag for child in root]
            expected = ["DependedModules", "ModulesToLoadAfterThis", "IncompatibleModules", "DependedModuleMetadatas", "SubModules", "Xmls"]
            positions = [tags.index(tag) for tag in expected]
            self.assertEqual(positions, sorted(positions))

    def test_missing_submodule_fields_insert_before_existing_assemblies_and_tags(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('''<Module><Name value="Example"/><Id value="Example"/><Version value="v1.0.0"/><SubModules><SubModule><Tags><Tag key="DedicatedServerType" value="none"/></Tags><Unknown value="keep"/></SubModule></SubModules></Module>''', encoding="utf-8")
            save_module(path, {"submodules": [{
                "index": 0,
                "name": "Example",
                "dllName": "Example.dll",
                "classType": "Example.SubModule",
                "assemblies": [{"index": None, "value": "Helper.dll", "attributes": {}}],
                "tags": [{"index": 0, "key": "DedicatedServerType", "value": "none", "attributes": {}}],
            }]})
            sub = ET.parse(path).getroot().find("./SubModules/SubModule")
            tags = [child.tag for child in sub]
            self.assertLess(tags.index("Name"), tags.index("DLLName"))
            self.assertLess(tags.index("DLLName"), tags.index("SubModuleClassType"))
            self.assertLess(tags.index("SubModuleClassType"), tags.index("Assemblies"))
            self.assertLess(tags.index("Assemblies"), tags.index("Tags"))
            self.assertIsNotNone(sub.find("Unknown"))

    def test_existing_known_nodes_are_not_reordered(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('''<Module><Name value="Example"/><Id value="Example"/><Version value="v1.0.0"/><SubModules/><DependedModules/></Module>''', encoding="utf-8")
            save_module(path, {"dependencies": []})
            tags = [child.tag for child in ET.parse(path).getroot()]
            self.assertEqual(tags[-2:], ["SubModules", "DependedModules"])


if __name__ == "__main__":
    unittest.main()
