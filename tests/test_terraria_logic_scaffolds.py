from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.terraria.content_wizard import (
    create_mod_player,
    create_mod_system,
    render_mod_player_source,
    render_mod_system_source,
)


class TerrariaLogicScaffoldTests(unittest.TestCase):
    def test_modsystem_template_is_empty_current_api_scaffold(self):
        source = render_mod_system_source("ExampleMod", "WorldTracker")
        self.assertIn("using Terraria.ModLoader;", source)
        self.assertIn("namespace ExampleMod.Common.Systems;", source)
        self.assertIn("public sealed class WorldTracker : ModSystem", source)
        self.assertNotIn("override", source)

    def test_modplayer_template_is_empty_current_api_scaffold(self):
        source = render_mod_player_source("ExampleMod", "ExamplePlayer")
        self.assertIn("using Terraria.ModLoader;", source)
        self.assertIn("namespace ExampleMod.Common.Players;", source)
        self.assertIn("public sealed class ExamplePlayer : ModPlayer", source)
        self.assertNotIn("override", source)

    def test_create_modsystem_and_modplayer_only_create_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ExampleMod"
            root.mkdir()
            system = create_mod_system(root, "WorldTracker")
            player = create_mod_player(root, "ExamplePlayer")

            self.assertEqual(system["kind"], "system")
            self.assertEqual(system["source"]["path"], "Common/Systems/WorldTracker.cs")
            self.assertEqual(player["kind"], "player")
            self.assertEqual(player["source"]["path"], "Common/Players/ExamplePlayer.cs")
            self.assertTrue((root / system["source"]["path"]).is_file())
            self.assertTrue((root / player["source"]["path"]).is_file())
            self.assertFalse((root / "Localization").exists())
            self.assertFalse((root / "Content").exists())

    def test_logic_scaffolds_never_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ExampleMod"
            root.mkdir()
            create_mod_system(root, "WorldTracker")
            with self.assertRaisesRegex(ValueError, "already exists"):
                create_mod_system(root, "WorldTracker")

            create_mod_player(root, "ExamplePlayer")
            with self.assertRaisesRegex(ValueError, "already exists"):
                create_mod_player(root, "ExamplePlayer")


if __name__ == "__main__":
    unittest.main()
