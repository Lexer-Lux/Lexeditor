from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from tools.terraria_acceptance import _representative_content, populate_acceptance_project


class TerrariaAcceptanceHarnessTests(unittest.TestCase):
    def test_representative_set_covers_every_managed_family_once(self):
        rows = _representative_content()
        kinds = [row[0] for row in rows]
        self.assertEqual(len(rows), 20)
        self.assertEqual(len(set(kinds)), 20)
        self.assertEqual(
            set(kinds),
            {
                "item", "npc", "projectile", "buff", "tile", "wall",
                "globalItem", "globalNPC", "globalProjectile", "globalBuff", "globalTile", "globalWall",
                "prefix", "rarity", "biome", "config", "command", "sceneEffect", "dust", "recipe",
            },
        )

    def test_generate_only_project_contains_native_smoke_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "LexeditorAcceptance"
            created = populate_acceptance_project(project)
            self.assertEqual(len(created), 20)
            self.assertTrue((project / "build.txt").is_file())
            self.assertTrue((project / "LexeditorAcceptance.csproj").is_file())
            self.assertTrue((project / "LexeditorAcceptance.cs").is_file())
            self.assertTrue((project / "Content" / "Items" / "AcceptanceItem.cs").is_file())
            self.assertTrue((project / "Content" / "Biomes" / "AcceptanceBiome.cs").is_file())
            self.assertTrue((project / "Content" / "Dusts" / "AcceptanceDust.cs").is_file())
            command = (project / "Common" / "Commands" / "AcceptanceCommand.cs").read_text(encoding="utf-8")
            recipe = (project / "Common" / "Recipes" / "AcceptanceRecipe.cs").read_text(encoding="utf-8")
            self.assertIn('Command => "lexaccept";', command)
            self.assertIn('Lexeditor Terraria acceptance mod loaded.', command)
            self.assertIn("AcceptanceItem", recipe)
            self.assertIn("recipe.AddIngredient(2, 1);", recipe)


if __name__ == "__main__":
    unittest.main()
