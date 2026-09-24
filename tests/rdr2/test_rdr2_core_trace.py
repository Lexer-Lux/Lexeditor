"""Hermetic checks for the issue-177 core-trace contract (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.rdr2 import core_trace as ct


def valid_plan():
    return {
        "approach": "synchronized_trace_video",
        "cadence_hz": 30,
        "timebase": "monotonic",
        "video_reference": "capture-01.mp4",
        "sequence": {
            "restoration": "eat cooked venison at 40 stamina core",
            "drain": "sprint until 39 stamina core",
        },
        "open_unknowns": ["recording tool build", "smoothing decision"],
    }


class CoreTraceTests(unittest.TestCase):
    def test_integer_core_bounds_recorded(self):
        self.assertEqual((ct.CORE_MIN, ct.CORE_MAX), (0, 100))

    def test_valid_plan_passes(self):
        self.assertEqual(ct.validate_measurement_plan(valid_plan()), [])

    def test_missing_sequence_leg_is_rejected(self):
        plan = valid_plan()
        del plan["sequence"]["drain"]
        errors = ct.validate_measurement_plan(plan)
        self.assertTrue(any("drain" in e for e in errors))

    def test_non_monotonic_timebase_is_rejected(self):
        plan = valid_plan()
        plan["timebase"] = "wall"
        errors = ct.validate_measurement_plan(plan)
        self.assertTrue(any("monotonic" in e for e in errors))

    def test_bad_cadence_is_rejected(self):
        plan = valid_plan()
        plan["cadence_hz"] = 0
        errors = ct.validate_measurement_plan(plan)
        self.assertTrue(any("cadence" in e for e in errors))

    def test_tween_approach_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "gameplay_tween_smoothing"
        errors = ct.validate_measurement_plan(plan)
        self.assertTrue(any("tween" in e for e in errors))

    def test_overlay_approach_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "hud_overlay_fix"
        errors = ct.validate_measurement_plan(plan)
        self.assertTrue(any("overlay" in e for e in errors))

    def test_openiv_only_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "openiv_only_reinspect"
        errors = ct.validate_measurement_plan(plan)
        self.assertTrue(any("OpenIV" in e for e in errors))

    def test_missing_video_reference_is_rejected(self):
        plan = valid_plan()
        plan["video_reference"] = ""
        errors = ct.validate_measurement_plan(plan)
        self.assertTrue(any("video_reference" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
