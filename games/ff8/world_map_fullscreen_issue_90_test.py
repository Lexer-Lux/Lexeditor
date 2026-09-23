"""Full-screen world-map contract tests. No game install required."""
import json
from pathlib import Path
import tempfile
import unittest

from . import world_map_fullscreen_issue_90 as m
from . import world_map, world_textures


def parsed_world():
    return {
        "fieldReturns": [
            {"id": 0, "name": "Field return 0", "x": 100, "y": 200, "z": 0},
            {"id": 1, "name": "Field return 1", "x": -50, "y": 75, "z": 0},
        ],
        "drawPoints": [
            {"id": 0, "name": "Draw Point 129", "x": 10, "y": 20},
        ],
    }


class BaseLayerTests(unittest.TestCase):
    def test_map_base_matches_proved_texture_slots(self):
        self.assertEqual(m.MAP_TEXTURE_SLOTS, world_textures.TEXTURE_COUNT)
        self.assertEqual(m.MAP_TEXTURE_SLOTS, 20)
        self.assertEqual(m.MAP_TEXTURE_SLOT_SIZE, world_textures.SLOT_SIZE)

    def test_marker_sources_match_proved_sections(self):
        self.assertEqual(m.DRAW_POINT_SECTION, world_map.DRAW_SECTION)
        self.assertEqual(m.EXPECTED_DRAW_POINT_COUNT, world_map.DRAW_POINT_COUNT)
        self.assertEqual(m.FIELD_RETURN_SECTION, world_map.FIELD_RETURN_SECTION)
        self.assertEqual(m.EXPECTED_FIELD_RETURN_COUNT, 64)

    def test_owner_confirmed_bindings(self):
        self.assertEqual((m.MAP_BUTTON, m.JOURNAL_BUTTON), ("R1", "L1"))
        self.assertTrue(m.REQUIRES_MODERN_CONTROLS)


class MarkerTests(unittest.TestCase):
    def test_markers_reuse_parsed_world_data(self):
        markers = m.markers_from_world(parsed_world())
        self.assertEqual(
            [(entry["id"], entry["kind"]) for entry in markers],
            [("location:0", "location"), ("location:1", "location"),
             ("drawPoint:0", "drawPoint")])
        self.assertEqual((markers[0]["x"], markers[0]["y"]), (100, 200))

    def test_markers_reject_missing_sections(self):
        with self.assertRaises(ValueError):
            m.markers_from_world({"fieldReturns": []})
        with self.assertRaises(ValueError):
            m.markers_from_world(None)

    def test_coordinates_alone_reveal_nothing(self):
        markers = m.markers_from_world(parsed_world())
        self.assertEqual(m.visible_markers(markers, m.blank_state()), [])

    def test_visited_and_revealed_labels_become_visible(self):
        markers = m.markers_from_world(parsed_world())
        state = m.mark_visited(m.blank_state(), "location:0")
        state = m.mark_revealed(state, "drawPoint:0")
        visible = m.visible_markers(markers, state,
                                    journal_revealed=("location:1",))
        self.assertEqual(
            sorted(entry["id"] for entry in visible),
            ["drawPoint:0", "location:0", "location:1"])

    def test_journal_reveal_does_not_persist_a_visit(self):
        markers = m.markers_from_world(parsed_world())
        state = m.blank_state()
        self.assertEqual(
            [entry["id"] for entry in m.visible_markers(
                markers, state, journal_revealed=("location:0",))],
            ["location:0"])
        self.assertEqual(state["visited"], [])


class WaypointTests(unittest.TestCase):
    def test_selection_sets_waypoint_only(self):
        before = m.mark_visited(m.blank_state(), "location:0")
        after = m.set_waypoint(
            before, {"id": "location:0", "kind": "location",
                     "x": 100, "y": 200})
        self.assertEqual(after["waypoint"],
                         {"id": "location:0", "kind": "location",
                          "x": 100, "y": 200})
        # Everything else is untouched: no travel, no flag changes.
        self.assertEqual(after["visited"], ["location:0"])
        self.assertEqual(after["revealed"], [])
        self.assertEqual(set(after), {"version", "visited", "revealed", "waypoint"})

    def test_waypoint_clears_and_keeps_discovery(self):
        state = m.set_waypoint(
            m.mark_visited(m.blank_state(), "location:0"),
            {"id": "location:0", "kind": "location", "x": 1, "y": 2})
        cleared = m.clear_waypoint(state)
        self.assertIsNone(cleared["waypoint"])
        self.assertEqual(cleared["visited"], ["location:0"])

    def test_waypoint_rejects_bad_shapes(self):
        for marker in (None, {"id": "", "kind": "location", "x": 1, "y": 2},
                       {"id": "a", "kind": "camp", "x": 1, "y": 2},
                       {"id": "a", "kind": "location", "x": "1", "y": 2}):
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):
                    m.set_waypoint(m.blank_state(), marker)


class StateStoreTests(unittest.TestCase):
    def test_round_trip_and_atomic_write(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "world" / "fullscreen_map_state.json"
            state = m.mark_visited(m.blank_state(), "location:3")
            state = m.set_waypoint(
                state, {"id": "location:3", "kind": "location",
                        "x": 4, "y": 5})
            written = m.save_state(path, state)
            self.assertEqual(m.load_state(path), written)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["version"], m.STATE_VERSION)

    def test_corrupt_or_versioned_state_recovers_to_blank(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(m.load_state(path), m.blank_state())
            path.write_text(json.dumps({"version": 999, "visited": ["x"],
                                        "revealed": [], "waypoint": None}),
                            encoding="utf-8")
            self.assertEqual(m.load_state(path), m.blank_state())
            self.assertEqual(m.load_state(Path(root) / "missing.json"),
                             m.blank_state())

    def test_state_path_is_mod_owned(self):
        path = m.state_path(Path("/tmp/fake-mod"))
        self.assertEqual(path.name, "fullscreen_map_state.json")
        self.assertNotIn("save", str(path).lower())


class GateTests(unittest.TestCase):
    def test_disabled_emits_no_bytes(self):
        self.assertEqual(m.build_hext(False), "")

    def test_requires_modern_controls(self):
        with self.assertRaises(ValueError):
            m.build_hext(True, modern_controls=False)

    def test_fails_closed_without_proved_hooks(self):
        self.assertFalse(m.WORLD_MAP_FULLSCREEN_AVAILABLE)
        self.assertTrue(m.WORLD_MAP_FULLSCREEN_BLOCKER)
        with self.assertRaises(ValueError):
            m.build_hext(True, modern_controls=True)

    def test_non_bool_inputs_rejected(self):
        for enabled, modern in (("yes", True), (True, 1), (None, False)):
            with self.subTest(enabled=enabled, modern=modern):
                with self.assertRaises(ValueError):
                    m.build_hext(enabled, modern_controls=modern)


if __name__ == "__main__":
    unittest.main()
