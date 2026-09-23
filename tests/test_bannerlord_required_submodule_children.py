from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from games.bannerlord.module_data import save_module


class BannerlordRequiredSubModuleChildrenTests(unittest.TestCase):
    def test_new_submodule_with_empty_lists_gets_required_containers(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('<Module><Name value="Example"/><Id value="Example"/><Version value="v1.0.0"/></Module>', encoding="utf-8")
            save_module(path, {"submodules": [{
                "index": None,
                "name": "Example",
                "dllName": "Example.dll",
                "classType": "Example.SubModule",
                "assemblies": [],
                "tags": [],
            }]})
            sub = ET.parse(path).getroot().find("./SubModules/SubModule")
            self.assertIsNotNone(sub.find("Assemblies"))
            self.assertIsNotNone(sub.find("Tags"))
            tags = [child.tag for child in sub]
            self.assertLess(tags.index("SubModuleClassType"), tags.index("Assemblies"))
            self.assertLess(tags.index("Assemblies"), tags.index("Tags"))

    def test_existing_legacy_submodule_without_containers_is_not_normalized_by_unrelated_save(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('''<Module><Name value="Example"/><Id value="Example"/><Version value="v1.0.0"/><SubModules><SubModule><Name value="Example"/><DLLName value="Example.dll"/><SubModuleClassType value="Example.SubModule"/></SubModule></SubModules></Module>''', encoding="utf-8")
            save_module(path, {
                "metadata": {"name": "Example Renamed"},
                "submodules": [{
                    "index": 0,
                    "name": "Example",
                    "dllName": "Example.dll",
                    "classType": "Example.SubModule",
                    "assemblies": [],
                    "tags": [],
                }],
            })
            sub = ET.parse(path).getroot().find("./SubModules/SubModule")
            self.assertIsNone(sub.find("Assemblies"))
            self.assertIsNone(sub.find("Tags"))

    def test_packaged_template_contains_required_assemblies_before_tags(self):
        template = Path("games/bannerlord/template/SubModule.xml")
        sub = ET.parse(template).getroot().find("./SubModules/SubModule")
        self.assertIsNotNone(sub.find("Assemblies"))
        self.assertIsNotNone(sub.find("Tags"))
        tags = [child.tag for child in sub]
        self.assertLess(tags.index("SubModuleClassType"), tags.index("Assemblies"))
        self.assertLess(tags.index("Assemblies"), tags.index("Tags"))


if __name__ == "__main__":
    unittest.main()
