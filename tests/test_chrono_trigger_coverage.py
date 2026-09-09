from __future__ import annotations

from types import SimpleNamespace
import unittest

from games.chrono_trigger.coverage import augment_data_map, resource_override


class CoverageTests(unittest.TestCase):
    def test_world_resources_are_classified_as_structured(self):
        self.assertEqual(resource_override("Game/common/bankc6.bin")["target"], "worlds")
        self.assertEqual(
            resource_override("Game/world/EventTable/EventTable_0007.dat")["status"],
            "integrated",
        )
        self.assertIsNone(resource_override("Game/world/esl/Event_0007.dat"))

    def test_data_map_includes_world_headers_and_navigation_tables(self):
        store = SimpleNamespace(archive=SimpleNamespace(entries=[
            SimpleNamespace(path="Game/common/bankc6.bin"),
            SimpleNamespace(path="Game/world/EventTable/EventTable_0001.dat"),
            SimpleNamespace(path="Game/world/EventTable/EventTable_0002.dat"),
        ]))
        base = {
            "rows": [
                {"filename": "resources.bin"},
                {"filename": "Game/world/esl/Event_*.dat"},
            ],
            "counts": {"resources": 3},
        }
        mapped = augment_data_map(store, base)
        filenames = [row["filename"] for row in mapped["rows"]]
        self.assertIn("Game/common/bankc6.bin", filenames)
        self.assertIn("Game/world/EventTable/EventTable_*.dat", filenames)
        self.assertEqual(mapped["counts"]["worldHeaders"], 8)
        self.assertEqual(mapped["counts"]["worldEventTables"], 2)


if __name__ == "__main__":
    unittest.main()
