from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import core
from games.project_zomboid import evolvedrecipe


class ProjectZomboidEvolvedRecipeTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        project = root / "mod"
        scripts = project / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        (project / "42" / "mod.info").write_text("name=Test\nid=Test\n", encoding="utf-8")
        (scripts / "evolved.txt").write_text(
            '''module Base\n{\n'''
            '''  evolvedrecipe Sandwich\n  {\n'''
            '''    BaseItem = Base.BreadSlices,\n'''
            '''    MaxItems = 4,\n'''
            '''    ResultItem = Base.Sandwich,\n'''
            '''    Name = Make Sandwich,\n'''
            '''    CanAddSpicesEmpty = true,\n'''
            '''    AddIngredientIfCooked = false,\n'''
            '''    MinimumWater = 0.0,\n'''
            '''    Cookable = true,\n'''
            '''    Template = Sandwich,\n'''
            '''    FutureField = KeepMe,\n'''
            '''    component Nested { MaxItems = 99, }\n'''
            '''  }\n}\n''',
            encoding="utf-8",
        )
        return project

    def test_surgical_edit_preserves_unknown_and_nested_data(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            row = evolvedrecipe.read(root)["rows"][0]
            saved = evolvedrecipe.save(
                root, row["path"], row["module"], row["id"], row["sha256"],
                {"MaxItems": "6", "CanAddSpicesEmpty": "false", "MinimumWater": "2.5"},
            )
            text = (root / row["path"]).read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["MaxItems"], "6")
            self.assertEqual(saved["fields"]["CanAddSpicesEmpty"], "false")
            self.assertEqual(saved["fields"]["MinimumWater"], "2.5")
            self.assertIn("FutureField = KeepMe,", text)
            self.assertIn("component Nested { MaxItems = 99, }", text)
            self.assertEqual(text.count("MaxItems = 6,"), 1)

    def test_schema_validation_and_stale_write(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            row = evolvedrecipe.read(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "MaxItems"):
                evolvedrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"MaxItems": "0"})
            with self.assertRaisesRegex(core.ProjectZomboidError, "Cookable"):
                evolvedrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"Cookable": "false"})
            with self.assertRaisesRegex(core.ProjectZomboidError, "full item type"):
                evolvedrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"BaseItem": "Bread"})
            script = root / row["path"]
            script.write_text(script.read_text(encoding="utf-8") + "// external\n", encoding="utf-8")
            with self.assertRaisesRegex(core.ProjectZomboidError, "changed outside Lexeditor"):
                evolvedrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"MaxItems": "5"})

    def test_missing_field_is_not_inserted(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            script = root / "42" / "media" / "scripts" / "evolved.txt"
            script.write_text(script.read_text(encoding="utf-8").replace("    Template = Sandwich,\n", ""), encoding="utf-8")
            row = evolvedrecipe.read(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "missing: Template"):
                evolvedrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"Template": "Other"})


if __name__ == "__main__":
    unittest.main()
