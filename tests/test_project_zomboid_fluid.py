from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import core, fluid


SCRIPT = """module LexTest
{
    fluid CustomWater
    {
        ColorReference = Azure,
        DisplayName = Fluid_Name_CustomWater,
        Properties
        {
            DisplayName = NestedValue,
            HungerChange = -5,
        }
        Categories
        {
            Beverage,
        }
    }
}
"""


class ProjectZomboidFluidTests(unittest.TestCase):
    def make_project(self, parent: Path, text: str = SCRIPT) -> tuple[Path, Path]:
        root = parent / "Fluid Mod"
        scripts = root / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        path = scripts / "fluids.txt"
        path.write_text(text, encoding="utf-8")
        return root, path

    def test_surgical_edit_preserves_nested_fluid_children(self):
        with tempfile.TemporaryDirectory() as name:
            root, path = self.make_project(Path(name))
            row = fluid.read(root)["rows"][0]
            before = path.read_text(encoding="utf-8")

            saved = fluid.save(
                root,
                row["path"],
                row["module"],
                row["id"],
                row["sha256"],
                {"DisplayName": "Fluid_Name_FreshWater"},
            )

            after = path.read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["DisplayName"], "Fluid_Name_FreshWater")
            self.assertIn("DisplayName = Fluid_Name_FreshWater,", after)
            self.assertIn("DisplayName = NestedValue,", after)
            self.assertIn("HungerChange = -5,", after)
            self.assertIn("Categories\n        {\n            Beverage,\n        }", after)
            self.assertEqual(
                before.replace("DisplayName = Fluid_Name_CustomWater,", "DisplayName = Fluid_Name_FreshWater,"),
                after,
            )

    def test_missing_duplicate_and_stale_edits_fail_closed(self):
        missing_text = """module LexTest
{
    fluid MissingColor
    {
        DisplayName = Fluid_Name_MissingColor,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, path = self.make_project(Path(name), missing_text)
            row = fluid.read(root)["rows"][0]
            with self.assertRaises(core.ProjectZomboidError):
                fluid.save(root, row["path"], row["module"], row["id"], row["sha256"], {"ColorReference": "Azure"})

            path.write_text(path.read_text(encoding="utf-8") + "// external change\n", encoding="utf-8")
            with self.assertRaises(core.ProjectZomboidError):
                fluid.save(root, row["path"], row["module"], row["id"], row["sha256"], {"DisplayName": "Fluid_Name_Changed"})

        duplicate_text = """module LexTest
{
    fluid DuplicateName
    {
        DisplayName = Fluid_Name_One,
        DisplayName = Fluid_Name_Two,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name), duplicate_text)
            row = fluid.read(root)["rows"][0]
            self.assertEqual(row["duplicateKeys"], ["DisplayName"])
            with self.assertRaises(core.ProjectZomboidError):
                fluid.save(root, row["path"], row["module"], row["id"], row["sha256"], {"DisplayName": "Fluid_Name_Three"})

    def test_nested_and_commented_fluid_blocks_are_not_records(self):
        text = """module LexTest
{
    // fluid Commented { DisplayName = Fluid_Name_Commented, }
    item Container
    {
        component Nested
        {
            fluid Fake
            {
                DisplayName = Fluid_Name_Fake,
            }
        }
    }
    fluid Real
    {
        ColorReference = Azure,
        DisplayName = Fluid_Name_Real,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name), text)
            result = fluid.read(root)
            self.assertEqual(result["errors"], [])
            self.assertEqual([(row["module"], row["id"]) for row in result["rows"]], [("LexTest", "Real")])

    def test_scalar_validation_rejects_script_punctuation(self):
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name))
            row = fluid.read(root)["rows"][0]
            for value in ("Azure,Other", "Azure{Other", "Azure}Other"):
                with self.subTest(value=value):
                    with self.assertRaises(core.ProjectZomboidError):
                        fluid.save(root, row["path"], row["module"], row["id"], row["sha256"], {"ColorReference": value})


if __name__ == "__main__":
    unittest.main()
