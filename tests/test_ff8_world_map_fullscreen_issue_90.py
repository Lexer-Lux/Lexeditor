"""Contracts for the FF8 full-screen world map, GitHub issue #90."""
from pathlib import Path
import tempfile
import unittest

from plugins.ff8 import gameplay_settings
from plugins.ff8 import world_map_fullscreen_issue_90 as world_map_fullscreen

ROOT = Path(__file__).resolve().parents[1]


class WorldMapFullscreenTests(unittest.TestCase):
    def test_default_is_off_and_tweak_is_registered(self):
        self.assertFalse(gameplay_settings.DEFAULT_WORLD_MAP_FULLSCREEN)
        self.assertFalse(world_map_fullscreen.DEFAULT_WORLD_MAP_FULLSCREEN)
        self.assertIn("worldMapFullscreen", gameplay_settings.ACCEPTED_TWEAKS)

    def test_load_defaults_and_forces_off_without_modern_controls(self):
        with tempfile.TemporaryDirectory(prefix="ff8-world-map-fullscreen-") as directory:
            project = Path(directory)
            defaults = gameplay_settings.load(project)
            self.assertIs(defaults["worldMapFullscreen"], False)
            self.assertFalse(defaults["worldMapFullscreenAvailable"])
            self.assertIn("no proved native overlay hooks",
                          defaults["worldMapFullscreenBlocker"])
            gameplay_settings.settings_path(project).write_text(
                '{"worldMapFullscreen": true, "modernControls": true}',
                encoding="utf-8",
            )
            # No proved overlay hooks: a stored true never loads as enabled.
            self.assertIs(gameplay_settings.load(project)["worldMapFullscreen"], False)

    def test_disabled_build_emits_no_overlay_bytes(self):
        patch = gameplay_settings.build_hext(25, False)
        self.assertIn("Full-screen World Map is disabled", patch)
        self.assertNotIn("texl", patch)

    def test_save_fails_closed_in_dependency_order(self):
        with self.assertRaisesRegex(ValueError, "requires Modern Controls"):
            world_map_fullscreen.build_hext(True, modern_controls=False)
        with self.assertRaisesRegex(ValueError, "no proved native overlay hooks"):
            world_map_fullscreen.build_hext(True, modern_controls=True)

    def test_editor_exposes_approved_policy(self):
        editor = (ROOT / "plugins/ff8/boot.js").read_text(encoding="utf-8")
        self.assertIn('"aria-label":"Full-screen World Map"', editor)
        self.assertIn('row("FULL-SCREEN WORLD MAP"', editor)
        self.assertIn("worldMapFullscreen:state.data.settings.worldMapFullscreen", editor)
        self.assertIn("sets a waypoint only", editor)
        self.assertIn("Requires Modern Controls", editor)

    def test_discovery_and_waypoint_state_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="ff8-world-map-fullscreen-") as directory:
            path = Path(directory) / "state.json"
            state = world_map_fullscreen.mark_visited(
                world_map_fullscreen.blank_state(), "location:7")
            state = world_map_fullscreen.set_waypoint(
                state, {"id": "location:7", "kind": "location", "x": 1, "y": 2})
            self.assertEqual(world_map_fullscreen.save_state(path, state)["waypoint"]["id"],
                             "location:7")
            self.assertEqual(world_map_fullscreen.load_state(path), state)


if __name__ == "__main__":
    unittest.main()
