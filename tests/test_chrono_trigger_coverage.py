from __future__ import annotations

from types import SimpleNamespace
import unittest

from games.chrono_trigger.coverage import augment_data_map, resource_override


class CoverageTests(unittest.TestCase):
    def test_world_resources_use_current_structured_classification(self):
        self.assertEqual(resource_override("Game/common/bankc6.bin")["target"], "worlds")
        self.assertEqual(
            resource_override("Game/world/EventTable/EventTable_0007.dat")["status"],
            "integrated",
        )
        script = resource_override("Game/world/esl/Event_0007.dat")
        self.assertEqual(script["status"], "partial")
        self.assertEqual(script["coverage"], "structural")
        self.assertEqual(script["target"], "worlds")

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
        self.assertIn("named fixed-width editing", event_row["controls"])
        self.assertIn("desktop Events view", event_row["notes"])


if __name__ == "__main__":
    unittest.main()
