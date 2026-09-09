from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_data import read_submodule
from games.bannerlord.plugin import PLUGIN
from games.bannerlord.project_data import primary_project_file, read_project_file
from games.bannerlord.project_template import module_id_from_name
from project_manager import ProjectManager


class BannerlordProjectTemplateTests(unittest.TestCase):
    def test_module_id_generation_is_safe_and_predictable(self):
        self.assertEqual(module_id_from_name("My Cool Mod"), "MyCoolMod")
        self.assertEqual(module_id_from_name("123 test"), "Mod123Test")
        self.assertEqual(module_id_from_name("---"), "BannerlordMod")
        self.assertEqual(module_id_from_name("already_Camel"), "AlreadyCamel")

    def test_project_manager_creates_clean_bannerlord_module(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            parent = root / "mods"
            parent.mkdir()
            manager = ProjectManager({"bannerlord": PLUGIN}, path=root / "projects.json")

            before = manager.snapshot("bannerlord")
            self.assertTrue(before["canCreate"])

            snapshot = manager.create("bannerlord", str(parent), "My Cool Mod")
            project = (parent / "My Cool Mod").resolve()
            self.assertEqual(Path(snapshot["current"]).resolve(), project)
            self.assertTrue((project / "SubModule.xml").is_file())
            self.assertTrue((project / "src" / "SubModule.cs").is_file())
            self.assertTrue((project / "MyCoolMod.csproj").is_file())
            self.assertFalse((project / "BannerlordModule.csproj").exists())

            module = read_submodule(project / "SubModule.xml")
            self.assertEqual(module["name"], "My Cool Mod")
            self.assertEqual(module["id"], "MyCoolMod")
            self.assertTrue(module["singleplayer"])
            self.assertFalse(module["multiplayer"])
            self.assertEqual([row["id"] for row in module["dependencies"]], ["Native", "SandBoxCore", "Sandbox"])
            self.assertEqual(module["submodules"][0]["dllName"], "MyCoolMod.dll")
            self.assertEqual(module["submodules"][0]["classType"], "MyCoolMod.SubModule")

            source = (project / "src" / "SubModule.cs").read_text(encoding="utf-8")
            self.assertIn("namespace MyCoolMod", source)
            self.assertIn("MBSubModuleBase", source)
            self.assertNotIn("{{MODULE_", source)

            project_file = primary_project_file(project)
            self.assertEqual(project_file.name, "MyCoolMod.csproj")
            parsed = read_project_file(project_file)
            self.assertEqual(parsed["properties"]["TargetFramework"], "net472")
            self.assertEqual(parsed["properties"]["AssemblyName"], "MyCoolMod")
            self.assertEqual(parsed["properties"]["ModuleDir"], "$(BannerlordDir)\\Modules\\MyCoolMod")
            self.assertTrue(any(row["include"] == "TaleWorlds.MountAndBlade" for row in parsed["references"]))
            self.assertTrue(any(row["name"] == "CopyModuleFiles" for row in parsed["targets"]))

            combined = "\n".join(path.read_text(encoding="utf-8") for path in project.rglob("*") if path.is_file())
            self.assertNotIn("LexerSkillTweaks", combined)
            self.assertNotIn("{{MODULE_NAME}}", combined)
            self.assertNotIn("{{MODULE_ID}}", combined)

    def test_numeric_project_name_gets_valid_namespace_and_module_id(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            parent = root / "mods"
            parent.mkdir()
            manager = ProjectManager({"bannerlord": PLUGIN}, path=root / "projects.json")
            manager.create("bannerlord", str(parent), "123 test")
            project = parent / "123 test"
            module = read_submodule(project / "SubModule.xml")
            self.assertEqual(module["id"], "Mod123Test")
            self.assertTrue((project / "Mod123Test.csproj").is_file())
            self.assertIn("namespace Mod123Test", (project / "src" / "SubModule.cs").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
