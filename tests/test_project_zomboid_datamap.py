from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import datamap


class ProjectZomboidDataMapTests(unittest.TestCase):
    def test_script_file_reports_all_structured_editors(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "mod"
            scripts = root / "42" / "media" / "scripts"
            scripts.mkdir(parents=True)
            (root / "42" / "mod.info").write_text("name=Test\nid=Test\n", encoding="utf-8")
            (scripts / "mixed.txt").write_text(
                '''module Base\n{\n'''
                '''  item Hammer { ItemType = base:weapon, Weight = 1, Icon = Hammer, DisplayCategory = Tool, }\n'''
                '''  evolvedrecipe Sandwich { BaseItem = Base.Bread, MaxItems = 4, ResultItem = Base.Sandwich, Name = Sandwich, }\n'''
                '''  craftRecipe SawLogs { tags = InHandCraft, time = 50, inputs { item 1 [Base.Log], } }\n'''
                '''  vehicle Car { mechanicType = 1, }\n'''
                '''}\n''', encoding="utf-8")
            result = datamap.read(root)
            row = next(row for row in result["rows"] if row["filename"] == "42/media/scripts/mixed.txt")
            self.assertEqual(row["status"], "partial")
            self.assertIn("Items", row["editor"])
            self.assertIn("Evolved Recipes", row["editor"])
            self.assertIn("Craft Recipes", row["editor"])
            self.assertIn("unmodeled fields are preserved", row["notes"])


if __name__ == "__main__":
    unittest.main()
