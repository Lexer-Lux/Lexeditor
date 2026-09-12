from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import zedscript


class ProjectZomboidZedScriptTests(unittest.TestCase):
    def test_inventory_finds_top_level_build42_families_only(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            scripts = root / "42" / "media" / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "mixed.txt").write_text(
                '''module LexTest\n{\n'''
                '''  item Hammer { ItemType = base:weapon, Weight = 1.0, }\n'''
                '''  recipe MakeThing { keep Hammer, Result:Hammer, }\n'''
                '''  fixing RepairHammer { Require : Hammer, }\n'''
                '''  model FancyModel { mesh = WorldItems/Hammer, }\n'''
                '''  sound TestSound { category = Item, }\n'''
                '''  item Container { component Nested { recipe Fake { } } }\n'''
                '''}\n''',
                encoding="utf-8",
            )
            result = zedscript.inventory(root)
            names = {(row["kind"], row["name"]) for row in result["rows"]}
            self.assertIn(("item", "Hammer"), names)
            self.assertIn(("recipe", "MakeThing"), names)
            self.assertIn(("fixing", "RepairHammer"), names)
            self.assertIn(("model", "FancyModel"), names)
            self.assertIn(("sound", "TestSound"), names)
            self.assertIn(("item", "Container"), names)
            self.assertNotIn(("recipe", "Fake"), names)
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["counts"]["recipe"], 1)
            self.assertTrue(next(row for row in result["rows"] if row["name"] == "Hammer")["editable"])
            self.assertFalse(next(row for row in result["rows"] if row["name"] == "MakeThing")["editable"])

    def test_comments_and_strings_do_not_create_blocks(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            scripts = root / "common" / "media" / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "comments.txt").write_text(
                '''module LexTest\n{\n'''
                '''  // recipe Commented { }\n'''
                '''  item Note { DisplayCategory = "recipe StringFake { }", }\n'''
                '''  /* vehicle BlockComment { } */\n'''
                '''}\n''',
                encoding="utf-8",
            )
            result = zedscript.inventory(root)
            self.assertEqual([(row["kind"], row["name"]) for row in result["rows"]], [("item", "Note")])


if __name__ == "__main__":
    unittest.main()
