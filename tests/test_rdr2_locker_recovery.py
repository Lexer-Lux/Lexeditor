"""Hermetic checks for the issue-165 locker-recovery boundary (no game data)."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import locker_recovery as lr


def valid_plan():
    return {
        "steps": [
            {
                "case": "VIKING_HATCHET",
                "route": "locker_list",
                "unequipped": True,
                "dedupe_check": True,
            },
        ],
        "open_unknowns": [
            "Safe solution to the native melee/throwable locker-list filter.",
        ],
    }


class LockerRecoveryTests(unittest.TestCase):
    def test_evidenced_cases_recorded(self):
        cases = {case["case"]: case for case in lr.lost_cases()}
        self.assertIn("VIKING_HATCHET", cases)
        self.assertIn("UNIQUE_HATCHET", cases)
        self.assertIn("UNIQUE_TOMAHAWK", cases)

    def test_cases_returns_an_independent_copy(self):
        first = lr.lost_cases()
        first.append({"case": "X"})
        self.assertEqual(len(lr.lost_cases()), 3)

    def test_valid_plan_passes(self):
        self.assertEqual(lr.validate_recovery_plan(valid_plan()), [])

    def test_recover_action_alone_is_rejected(self):
        plan = valid_plan()
        plan["steps"][0]["route"] = "recover_action"
        errors = lr.validate_recovery_plan(plan)
        self.assertTrue(any("ordinary locker list" in e for e in errors))

    def test_equipped_return_is_rejected(self):
        plan = valid_plan()
        plan["steps"][0]["unequipped"] = False
        errors = lr.validate_recovery_plan(plan)
        self.assertTrue(any("unequipped" in e for e in errors))

    def test_missing_dedupe_check_is_rejected(self):
        plan = valid_plan()
        plan["steps"][0]["dedupe_check"] = False
        errors = lr.validate_recovery_plan(plan)
        self.assertTrue(any("duplication" in e for e in errors))

    def test_unknown_case_is_rejected(self):
        plan = valid_plan()
        plan["steps"][0]["case"] = "GOLDEN_REVOLVER"
        errors = lr.validate_recovery_plan(plan)
        self.assertTrue(any("unknown case" in e for e in errors))

    def test_empty_plan_is_rejected(self):
        self.assertTrue(lr.validate_recovery_plan({}))
        self.assertTrue(lr.validate_recovery_plan({"steps": []}))

    def test_filter_must_stay_owned_as_unknown(self):
        plan = valid_plan()
        plan["open_unknowns"] = ["Everything is solved."]
        errors = lr.validate_recovery_plan(plan)
        self.assertTrue(any("filter" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
