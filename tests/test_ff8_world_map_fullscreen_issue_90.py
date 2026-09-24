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

    def test_filter_cycles_categories_and_keeps_waypoint(self):
        order = ["all"]
        for _ in range(len(world_map_fullscreen.MARKER_FILTERS)):
            order.append(world_map_fullscreen.cycle_filter(order[-1]))
        self.assertEqual(order, ["all", "location", "drawPoint", "quest",
                                 "vehicle", "all"])
        markers = [
            {"id": "location:0", "kind": "location"},
            {"id": "drawPoint:0", "kind": "drawPoint"},
            {"id": "waypoint", "kind": "waypoint"},
        ]
        self.assertEqual(len(world_map_fullscreen.filter_markers(markers)), 3)
        filtered = world_map_fullscreen.filter_markers(markers, "drawPoint")
        self.assertEqual([entry["id"] for entry in filtered],
                         ["drawPoint:0", "waypoint"])
        with self.assertRaises(ValueError):
            world_map_fullscreen.cycle_filter("camp")
        with self.assertRaises(ValueError):
            world_map_fullscreen.filter_markers(markers, "camp")

    def test_viewport_pan_zoom_and_center(self):
        viewport = world_map_fullscreen.blank_viewport()
        moved = world_map_fullscreen.pan_viewport(viewport, 10, -4)
        self.assertEqual((moved["centerX"], moved["centerY"]), (10.0, -4.0))
        self.assertEqual(moved["zoom"], world_map_fullscreen.DEFAULT_ZOOM)
        # The input is untouched: helpers return a new viewport.
        self.assertEqual(viewport["centerX"], 0.0)
        zoomed = world_map_fullscreen.zoom_viewport(moved, 2.0, 10.0, -4.0)
        self.assertEqual(zoomed["zoom"], 2.0)
        # Zooming around the current center keeps the center fixed.
        self.assertEqual((zoomed["centerX"], zoomed["centerY"]), (10.0, -4.0))
        off_center = world_map_fullscreen.zoom_viewport(
            world_map_fullscreen.blank_viewport(), 2.0, 8.0, 0.0)
        self.assertEqual((off_center["centerX"], off_center["centerY"]), (4.0, 0.0))
        clamped = world_map_fullscreen.zoom_viewport(
            world_map_fullscreen.blank_viewport(), 100.0, 0.0, 0.0)
        self.assertEqual(clamped["zoom"], world_map_fullscreen.MAX_ZOOM)
        centered = world_map_fullscreen.center_on_player(zoomed, 3.0, 5.0)
        self.assertEqual((centered["centerX"], centered["centerY"]), (3.0, 5.0))
        self.assertEqual(centered["zoom"], 2.0)
        with self.assertRaises(ValueError):
            world_map_fullscreen.zoom_viewport(viewport, 0.0, 0.0, 0.0)
        with self.assertRaises(ValueError):
            world_map_fullscreen.pan_viewport(viewport, True, 0.0)

    def test_confirm_selection_describes_marker(self):
        marker = {"id": "location:0", "kind": "location",
                  "name": "Field return 0", "x": 100, "y": 200}
        plain = world_map_fullscreen.describe_marker(marker)
        self.assertEqual(plain, {"title": "Field return 0", "detail": "location"})
        quest = world_map_fullscreen.describe_marker(
            marker, quest_stage="White Seed ship: find Edea's house")
        self.assertEqual(quest["title"], "Field return 0")
        self.assertIn("location", quest["detail"])
        self.assertIn("Edea's house", quest["detail"])
        with self.assertRaises(ValueError):
            world_map_fullscreen.describe_marker({"kind": "camp", "name": "x"})
        with self.assertRaises(ValueError):
            world_map_fullscreen.describe_marker(marker, quest_stage="")


if __name__ == "__main__":
    unittest.main()
