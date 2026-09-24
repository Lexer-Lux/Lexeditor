"""Non-destructive flat Warband Module System import and preservation tests."""

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from plugins.warband import project_import, server
from plugins.warband.plugin import PLUGIN
from core.project_manager import ProjectManager


# Pinned Persistent World a35fd5d89cbb4e684ddf2fe4a6de9fe5066b9988
# uses this flat shape and one-shot Python build command before its interactive pause.
PERSISTENT_WORLD_BUILD = """@echo off
python -tt build_module.py
@del *.pyc
echo
echo Press any key to exit...
pause>nul
"""

ITEMS = """from header_items import *
items = [
  # keep this comment and every unmodeled expression byte
  ["sword", "Old Sword", [("sword_mesh", 0)], itp_type_one_handed_wpn,
   itc_longsword, 120, weight(1.5)|spd_rtng(97), imodbits_sword],
  ["boots", "Old Boots", [("boot_mesh", 0)], itp_type_foot_armor,
   0, 75, weight(1.0)|leg_armor(12), imodbits_cloth],
]
"""

TROOPS = """troops = [
 ["soldier", "Soldier", "Soldiers", 0, 0, 0, fac_commoners, [], 0, 0, 0, 0],
]
"""


class WarbandFlatProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lexeditor-warband-flat-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.imports = self.root / "imports"
        self.projects_json = self.root / "projects.json"
        self.import_patch = patch.object(project_import, "IMPORT_ROOT", self.imports)
        self.import_patch.start()
        self.addCleanup(self.import_patch.stop)

    def make_flat(self, root: Path) -> Path:
        root.mkdir(parents=True)
        (root / "module_items.py").write_text(ITEMS, encoding="utf-8")
        (root / "module_troops.py").write_text(TROOPS, encoding="utf-8")
        (root / "module_info.py").write_bytes(
            b'export_dir = "../PW/"\r\n\r\n'
            b'def export_path(file_name):\r\n'
            b'    return export_dir + file_name\r\n'
        )
        (root / "build_module.bat").write_text(PERSISTENT_WORLD_BUILD, encoding="utf-8")
        (root / "build_module.py").write_text("print('fixture build')\n", encoding="utf-8")
        return root

    def test_persistent_world_flat_layout_import_is_non_destructive_and_reused(self):
        source = self.make_flat(self.root / "pw_module_system")
        original = {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()}
        manager = ProjectManager({"warband": PLUGIN}, path=self.projects_json)

        selected = manager.select("warband", str(source))
        imported = Path(selected["current"])
        self.assertNotEqual(imported, source)
        self.assertTrue((imported / "ModuleSystem" / "module_items.py").is_file())
        self.assertTrue((imported / "settings.ini").is_file())
        self.assertTrue((imported / "Module").is_dir())
        self.assertEqual(
            original,
            {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()},
        )

        original_info = (source / "module_info.py").read_text(encoding="utf-8")
        managed_info = (imported / "ModuleSystem" / "module_info.py").read_text(encoding="utf-8")
        self.assertIn('export_dir = "../PW/"', original_info)
        self.assertIn('export_dir = "../Module/"', managed_info)

        wrapper = (imported / "build.bat").read_text(encoding="utf-8")
        self.assertIn('call "%LEX_WARBAND_PY%" %LEX_WARBAND_PY_ARGS% -tt build_module.py', wrapper)
        self.assertIn("Build verified: imported Warband Module System", wrapper)
        self.assertNotIn("pause", wrapper.casefold())
        self.assertNotIn("goto", wrapper.casefold())

        managed_source = imported / "ModuleSystem"
        with patch.object(server, "MODULE_SYSTEM", managed_source):
            first = server.item_data()
            result = server.save_item_edits([{
                "recordIndex": 0,
                "originalId": "sword",
                "fields": {"name": "Imported Sword", "value": "250"},
            }], first["sha256"])
            self.assertEqual(result["saved"], 1)
            after_first = (managed_source / "module_items.py").read_bytes()

            second = server.item_data()
            result = server.save_item_edits([{
                "recordIndex": 0,
                "originalId": "sword",
                "fields": {"stats": "weight(2.25)|spd_rtng(91)"},
            }], second["sha256"])
            self.assertEqual(result["saved"], 1)
            rows = server.item_rows()
            self.assertEqual(rows[0]["name"], "Imported Sword")
            self.assertEqual(rows[0]["value"], "250")
            self.assertIn("weight(2.25)", rows[0]["fields"]["stats"])
            self.assertEqual(rows[1]["name"], "Old Boots")
            self.assertIn("keep this comment", (managed_source / "module_items.py").read_text())
            self.assertEqual(
                (managed_source / "module_items.py.lexeditor.bak").read_bytes(),
                after_first,
            )

        # Selecting the unchanged public source again reuses the managed copy,
        # so overlapping Lexeditor edits are never replaced by a fresh import.
        selected_again = manager.select("warband", str(source))
        self.assertEqual(Path(selected_again["current"]), imported)
        self.assertIn(
            "Imported Sword",
            (imported / "ModuleSystem" / "module_items.py").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            original,
            {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()},
        )

    def test_repository_root_can_contain_named_module_system_folder(self):
        repository = self.root / "native-plus"
        source = self.make_flat(repository / "Module System")
        detected = project_import.find_flat_module_system(repository)
        self.assertEqual(detected, source.resolve())
        manager = ProjectManager({"warband": PLUGIN}, path=self.projects_json)
        selected = manager.select("warband", str(repository))
        imported = Path(selected["current"])
        self.assertTrue((imported / "ModuleSystem" / "module_items.py").is_file())
        manifest = json.loads((imported / project_import.MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(Path(manifest["source"]), repository.resolve())
        self.assertEqual(Path(manifest["moduleSystem"]), source.resolve())

    def test_source_change_during_import_is_rejected_without_partial_project(self):
        source = self.make_flat(self.root / "changing")
        original_copy = project_import._copy_source

        def copy_then_change(source_root, destination):
            original_copy(source_root, destination)
            items = source_root / "module_items.py"
            items.write_text(items.read_text(encoding="utf-8") + "# concurrent source change\n", encoding="utf-8")

        manager = ProjectManager({"warband": PLUGIN}, path=self.projects_json)
        with patch.object(project_import, "_copy_source", side_effect=copy_then_change):
            with self.assertRaisesRegex(ValueError, "changed while it was being imported"):
                manager.select("warband", str(source))
        if self.imports.exists():
            self.assertFalse(any(path for path in self.imports.iterdir() if not path.name.startswith(".")))
            self.assertFalse(any(self.imports.glob(".*-*")))

    def test_unknown_build_command_is_rejected_before_copy(self):
        source = self.make_flat(self.root / "unsafe")
        (source / "build_module.bat").write_text(
            "@echo off\ncopy secret.dll C:\\Games\\Warband\\secret.dll\n",
            encoding="utf-8",
        )
        manager = ProjectManager({"warband": PLUGIN}, path=self.projects_json)
        with self.assertRaisesRegex(ValueError, "Unsupported command"):
            manager.select("warband", str(source))
        self.assertFalse(any(self.imports.glob("*")) if self.imports.exists() else True)


if __name__ == "__main__":
    unittest.main()
