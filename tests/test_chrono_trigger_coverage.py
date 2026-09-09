from __future__ import annotations

from types import SimpleNamespace
import unittest

from games.chrono_trigger.coverage import augment_data_map, resource_override


class CoverageTests(unittest.TestCase):
    def test_world_resources_use_current_structured_classification(self):
        world = resource_override("Game/common/bankc6.bin")
        self.assertEqual(world["target"], "worlds")
        self.assertEqual(world["coverage"], "structured + raster")
        self.assertEqual(
            resource_override("Game/world/EventTable/EventTable_0007.dat")["status"],
            "integrated",
        )
        script = resource_override("Game/world/esl/Event_0007.dat")
        self.assertEqual(script["status"], "partial")
        self.assertEqual(script["coverage"], "structural")
        self.assertEqual(script["target"], "worlds")

    def test_scene_map_reports_desktop_raster_and_animation_diagnostics(self):
        scene_map = resource_override("Game/field/MapTable/MapTable_0020.dat")
        self.assertEqual(scene_map["status"], "integrated")
        self.assertEqual(scene_map["coverage"], "structural + raster")
        self.assertEqual(scene_map["target"], "scenes")
        animation = resource_override("Game/field/BGAnime/bganimeinfo_9.dat")
        self.assertEqual(animation["kind"], "scene-chip-animation")
        self.assertEqual(animation["coverage"], "structural")
        self.assertEqual(animation["status"], "partial")
        self.assertEqual(animation["target"], "scenes")
        l3_graphics = resource_override("Game/field/weather_bin/cg9.bin")
        self.assertEqual(l3_graphics["kind"], "scene-l3-graphics")
        self.assertEqual(l3_graphics["coverage"], "raster")
        l3_assembly = resource_override("Game/field/ChipTable/ChipTableBg3_0020.dat")
        self.assertEqual(l3_assembly["kind"], "scene-l3-assembly")
        self.assertEqual(l3_assembly["target"], "scenes")

    def test_field_events_report_fixed_width_write_coverage(self):
        event = resource_override("Game/field/atel/Atel_0020.dat")
        self.assertEqual(event["status"], "partial")
        self.assertEqual(event["coverage"], "structural + fixed-write")
        self.assertEqual(event["target"], "events")

    def test_data_map_includes_world_headers_navigation_and_scripts(self):
        store = SimpleNamespace(archive=SimpleNamespace(entries=[
            SimpleNamespace(path="Game/common/bankc6.bin"),
            SimpleNamespace(path="Game/world/EventTable/EventTable_0001.dat"),
            SimpleNamespace(path="Game/world/EventTable/EventTable_0002.dat"),
            SimpleNamespace(path="Game/world/esl/Event_0003.dat"),
        ]))
        base = {
            "rows": [
                {"filename": "resources.bin"},
                {"filename": "Game/world/esl/Event_*.dat", "status": "partial"},
            ],
            "counts": {"resources": 4},
        }
        mapped = augment_data_map(store, base)
        filenames = [row["filename"] for row in mapped["rows"]]
        self.assertIn("Game/common/bankc6.bin", filenames)
        self.assertIn("Game/world/EventTable/EventTable_*.dat", filenames)
        script_row = next(row for row in mapped["rows"] if row["filename"] == "Game/world/esl/Event_*.dat")
        self.assertEqual(script_row["coverage"], "structural")
        self.assertEqual(script_row["target"], "worlds")
        world_row = next(row for row in mapped["rows"] if row["filename"] == "Game/common/bankc6.bin")
        self.assertEqual(world_row["coverage"], "structured + raster")
        self.assertIn("desktop", world_row["controls"])
        self.assertIn("isolated L1/L2", world_row["notes"])
        self.assertEqual(mapped["counts"]["worldHeaders"], 8)
        self.assertEqual(mapped["counts"]["worldEventTables"], 2)
        self.assertEqual(mapped["counts"]["worldScripts"], 1)

    def test_data_map_describes_desktop_named_event_editing(self):
        store = SimpleNamespace(archive=SimpleNamespace(entries=[
            SimpleNamespace(path="Game/field/atel/Atel_0020.dat"),
        ]))
        base = {
            "rows": [{"filename": "Game/field/atel/Atel_*.dat", "status": "partial"}],
            "counts": {"resources": 1},
        }
        mapped = augment_data_map(store, base)
        event_row = next(row for row in mapped["rows"] if row["filename"] == "Game/field/atel/Atel_*.dat")
        self.assertEqual(event_row["coverage"], "structural + fixed-write")
        self.assertIn("named fixed-width", event_row["controls"])
        self.assertIn("bit", event_row["controls"])
        self.assertIn("call", event_row["controls"])
        self.assertIn("movement/follow", event_row["controls"])
        self.assertIn("0x12–0x15", event_row["notes"])
        self.assertIn("0x63/64/69/6B/6F", event_row["notes"])
        self.assertIn("0x02–0x07", event_row["notes"])
        self.assertIn("0x0A/7C/7D", event_row["notes"])
        self.assertIn("D9/E7/F4", event_row["notes"])
        self.assertIn("coordinate bytes", event_row["notes"])
        self.assertIn("Odd doubled targets", event_row["notes"])
        self.assertIn("0x16/67/6E/8D/8E/9E/9F", event_row["notes"])
        self.assertIn("decoded command boundary", event_row["notes"])

    def test_data_map_describes_gameplay_research_inventory_and_probe_boundaries(self):
        store = SimpleNamespace(archive=SimpleNamespace(entries=[]))
        mapped = augment_data_map(store, {"rows": [], "counts": {"resources": 0}})
        row = next(item for item in mapped["rows"] if item["filename"] == "Actual resources.bin path families")
        self.assertEqual(row["coverage"], "research")
        self.assertIn("bounded", row["controls"])
        self.assertIn("selected-family/path", row["controls"])
        self.assertIn("four-byte declared payload-size", row["notes"])
        self.assertIn("before decompression", row["notes"])
        self.assertIn("No gameplay-stat editor", row["notes"])

    def test_data_map_describes_scene_render_diagnostics_without_playback_claim(self):
        store = SimpleNamespace(archive=SimpleNamespace(entries=[
            SimpleNamespace(path="Game/field/MapTable/MapTable_0000.dat"),
            SimpleNamespace(path="Game/field/BGAnime/bganimeinfo_4.dat"),
            SimpleNamespace(path="Game/field/weather_bin/cg9.bin"),
            SimpleNamespace(path="Game/field/ChipTable/ChipTableBg3_0000.dat"),
        ]))
        mapped = augment_data_map(store, {"rows": [], "counts": {"resources": 4}})
        row = next(item for item in mapped["rows"] if str(item["filename"]).startswith("Game/field/MapTable/"))
        self.assertEqual(row["coverage"], "structural + raster")
        self.assertIn("L1/L2/L3", row["controls"])
        self.assertIn("render diagnostics", row["controls"])
        self.assertIn("weather_bin", row["notes"])
        self.assertIn("ChipTableBg3", row["notes"])
        self.assertIn("MapTable main/sub/effect", row["notes"])
        self.assertIn("PrioMap", row["notes"])
        self.assertIn("BGAnime", row["notes"])
        self.assertIn("unsupported", row["notes"])

        animation_row = next(item for item in mapped["rows"] if str(item["filename"]).startswith("Game/field/BGAnime/"))
        self.assertEqual(animation_row["coverage"], "structural")
        self.assertEqual(animation_row["status"], "partial")
        self.assertIn("offset/32", animation_row["notes"])
        self.assertIn("upper nibble", animation_row["notes"])
        self.assertIn("initial-frame", animation_row["notes"])
        self.assertIn("unsupported", animation_row["notes"])

        self.assertEqual(mapped["counts"]["sceneChipAnimations"], 1)
        self.assertEqual(mapped["counts"]["sceneL3Graphics"], 1)
        self.assertEqual(mapped["counts"]["sceneL3Assemblies"], 1)


if __name__ == "__main__":
    unittest.main()
