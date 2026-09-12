from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import zedscript


class ProjectZomboidZedScriptTests(unittest.TestCase):
    def test_inventory_finds_current_top_level_build42_families_only(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            scripts = root / "42" / "media" / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "mixed.txt").write_text(
                '''module LexTest\n{\n'''
                '''  item Hammer { ItemType = base:weapon, Weight = 1.0, }\n'''
                '''  craftRecipe MakeThing { tags = AnySurfaceCraft, inputs { } }\n'''
                '''  evolvedrecipe Sandwich { BaseItem = Base.BreadSlices, MaxItems = 4, }\n'''
                '''  fixing RepairHammer { Require : Hammer, ConditionModifier = 1.0, }\n'''
                '''  fluid CustomWater { color = 1, }\n'''
                '''  mannequin StoreDisplay { female = true, }\n'''
                '''  model FancyModel { mesh = WorldItems/Hammer, }\n'''
                '''  sound TestSound { category = Item, }\n'''
                '''  timedAction Making { anim = Craft, }\n'''
                '''  vehicle TestCar { mechanicType = 1, }\n'''
                '''  item Container { component Nested { craftRecipe Fake { } } }\n'''
                '''}\n''',
                encoding="utf-8",
            )
            result = zedscript.inventory(root)
            names = {(row["kind"], row["name"]) for row in result["rows"]}
            self.assertIn(("item", "Hammer"), names)
            self.assertIn(("craftRecipe", "MakeThing"), names)
            self.assertIn(("evolvedrecipe", "Sandwich"), names)
            self.assertIn(("fixing", "RepairHammer"), names)
            self.assertIn(("fluid", "CustomWater"), names)
            self.assertIn(("mannequin", "StoreDisplay"), names)
            self.assertIn(("model", "FancyModel"), names)
            self.assertIn(("sound", "TestSound"), names)
            self.assertIn(("timedAction", "Making"), names)
            self.assertIn(("vehicle", "TestCar"), names)
            self.assertIn(("item", "Container"), names)
            self.assertNotIn(("craftRecipe", "Fake"), names)
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["counts"]["craftRecipe"], 1)
            for editable_name in ("Hammer", "Sandwich", "MakeThing", "RepairHammer", "CustomWater", "TestCar", "TestSound", "FancyModel", "StoreDisplay"):
                with self.subTest(editable_name=editable_name):
                    self.assertTrue(next(row for row in result["rows"] if row["name"] == editable_name)["editable"])

    def test_comments_strings_and_nested_blocks_do_not_create_records(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            scripts = root / "common" / "media" / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "comments.txt").write_text(
                '''module LexTest\n{\n'''
                '''  // craftRecipe Commented { }\n'''
                '''  item Note { DisplayCategory = "craftRecipe StringFake { }", }\n'''
                '''  /* vehicle BlockComment { } */\n'''
                '''}\n''',
                encoding="utf-8",
            )
            result = zedscript.inventory(root)
            self.assertEqual(
                [(row["kind"], row["name"]) for row in result["rows"]],
                [("item", "Note")],
            )


if __name__ == "__main__":
    unittest.main()
