"""Hermetic checks for the issue-227 Dead Eye replacement protocol (no game)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.rdr2 import dead_eye_replacement as der


def valid_plan():
    return {
        "keeps_kill_gains": False,
        "kill_gain_source": "engine kill-gain factor behind the general multiplier",
        "comparison": {
            "situations": list(der.COMPARISON_SITUATIONS),
            "baseline": 1,
            "candidate": 0,
            "multiplier_restored": True,
        },
        "regeneration": {
            "core_empty_yield": 0,
            "item_restoration": True,
            "mission_restoration": True,
            "permanent_progression": True,
        },
        "open_unknowns": ["Kill-gain source and suppression comparison not yet run."],
    }


class ProtocolTests(unittest.TestCase):
    def test_protocol_has_three_ordered_steps(self):
        self.assertEqual([s["id"] for s in der.protocol()], [
            "resolve_kill_gain_source",
            "causal_suppression_comparison",
            "core_scaled_regeneration",
        ])

    def test_protocol_returns_an_independent_copy(self):
        first = der.protocol()
        first.append({"id": "X"})
        self.assertEqual(len(der.protocol()), 3)

    def test_valid_plan_passes(self):
        self.assertEqual(der.validate_replacement(valid_plan()), [])

    def test_keeping_kill_gains_is_rejected(self):
        plan = valid_plan()
        plan["keeps_kill_gains"] = True
        self.assertTrue(any("partial substitute" in e for e in der.validate_replacement(plan)))

    def test_every_comparison_situation_required(self):
        plan = valid_plan()
        plan["comparison"]["situations"] = ["body_kill"]
        errors = der.validate_replacement(plan)
        self.assertTrue(any("headshot_kill" in e for e in errors))
        self.assertTrue(any("eagle_eye" in e for e in errors))

    def test_baseline_candidate_and_restore_required(self):
        plan = valid_plan()
        plan["comparison"]["baseline"] = 2
        plan["comparison"]["multiplier_restored"] = False
        errors = der.validate_replacement(plan)
        self.assertTrue(any("baseline multiplier 1 against candidate 0" in e for e in errors))
        self.assertTrue(any("restore the previous multiplier" in e for e in errors))

    def test_core_empty_must_yield_nothing(self):
        plan = valid_plan()
        plan["regeneration"]["core_empty_yield"] = 5
        self.assertTrue(any("cores are empty" in e for e in der.validate_replacement(plan)))

    def test_restoration_and_progression_preserved(self):
        plan = valid_plan()
        plan["regeneration"]["mission_restoration"] = False
        self.assertTrue(any("mission_restoration" in e for e in der.validate_replacement(plan)))

    def test_source_and_unknowns_required(self):
        plan = valid_plan()
        del plan["kill_gain_source"]
        plan["open_unknowns"] = []
        errors = der.validate_replacement(plan)
        self.assertTrue(any("kill_gain_source" in e for e in errors))
        self.assertTrue(any("open_unknowns" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
