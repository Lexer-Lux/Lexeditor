"""Hermetic checks for the issue-202 Viking Comb measurement contract (no game)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.rdr2 import viking_comb_criteria as vcc


def valid_plan():
    return {
        "interaction": "Greet a stranger (known +2 social gain)",
        "readings": {"before": 100, "after": 104},
        "cases": [
            {"amount": 2, "social": True, "mission": False, "expected": 4},
            {"amount": 25, "social": True, "mission": False, "expected": 25},
            {"amount": 5, "social": True, "mission": True, "expected": 5},
            {"amount": -10, "social": True, "mission": False, "expected": -10},
        ],
        "open_unknowns": ["Honor-event interception before identity loss is unproven."],
    }


class EligibilityTests(unittest.TestCase):
    def test_small_positive_social_gain_is_eligible(self):
        self.assertTrue(vcc.is_eligible_gain(2, True, False))
        self.assertTrue(vcc.is_eligible_gain(20, True, False))

    def test_missions_losses_and_large_gains_are_excluded(self):
        self.assertFalse(vcc.is_eligible_gain(21, True, False))
        self.assertFalse(vcc.is_eligible_gain(5, True, True))
        self.assertFalse(vcc.is_eligible_gain(-5, True, False))
        self.assertFalse(vcc.is_eligible_gain(0, True, False))
        self.assertFalse(vcc.is_eligible_gain(5, False, False))

    def test_non_numeric_amounts_are_excluded(self):
        self.assertFalse(vcc.is_eligible_gain("5", True, False))
        self.assertFalse(vcc.is_eligible_gain(True, True, False))


class MeasurementPlanTests(unittest.TestCase):
    def test_valid_plan_passes(self):
        self.assertEqual(vcc.validate_measurement(valid_plan()), [])

    def test_interaction_and_readings_required(self):
        plan = valid_plan()
        del plan["interaction"]
        plan["readings"] = {"before": "high"}
        errors = vcc.validate_measurement(plan)
        self.assertTrue(any("interaction" in e for e in errors))
        self.assertTrue(any("readings" in e for e in errors))

    def test_wrong_expectation_is_rejected(self):
        plan = valid_plan()
        plan["cases"][0]["expected"] = 2
        self.assertTrue(any("must expect 4" in e for e in vcc.validate_measurement(plan)))

    def test_excluded_gain_must_not_double(self):
        plan = valid_plan()
        plan["cases"][1]["expected"] = 50
        self.assertTrue(any("must expect 25" in e for e in vcc.validate_measurement(plan)))

    def test_doubled_case_required(self):
        plan = valid_plan()
        plan["cases"] = [c for c in plan["cases"] if c["expected"] == c["amount"]]
        self.assertTrue(any("doubled eligible" in e for e in vcc.validate_measurement(plan)))

    def test_excluded_case_required(self):
        plan = valid_plan()
        plan["cases"] = [plan["cases"][0]]
        self.assertTrue(any("excluded gain" in e for e in vcc.validate_measurement(plan)))

    def test_interception_unknown_must_be_owned(self):
        plan = valid_plan()
        plan["open_unknowns"] = ["Nothing pending."]
        self.assertTrue(any("interception" in e for e in vcc.validate_measurement(plan)))


if __name__ == "__main__":
    unittest.main()
