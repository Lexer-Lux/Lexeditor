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


def valid_filter_plan():
    return {
        "results": {
            "lost_unique_visible_as_ordinary_locker_entry": True,
            "non_unique_melee_throwables_kept_out": True,
            "return_unequipped": True,
            "no_duplication_on_repeated_visits": True,
        }
    }


class LockerFilterTests(unittest.TestCase):
    def test_criteria_recorded(self):
        self.assertIn("non_unique_melee_throwables_kept_out",
                      lr.filter_acceptance_criteria())

    def test_valid_filter_plan_passes(self):
        self.assertEqual(lr.validate_locker_filter(valid_filter_plan()), [])

    def test_assumed_solution_is_rejected(self):
        plan = valid_filter_plan()
        plan["assumes_filter_solved"] = True
        errors = lr.validate_locker_filter(plan)
        self.assertTrue(any("assume" in e for e in errors))

    def test_leaking_non_uniques_is_rejected(self):
        plan = valid_filter_plan()
        plan["results"]["non_unique_melee_throwables_kept_out"] = False
        errors = lr.validate_locker_filter(plan)
        self.assertTrue(any("non_unique_melee_throwables_kept_out" in e
                            for e in errors))

    def test_duplicating_filter_is_rejected(self):
        plan = valid_filter_plan()
        plan["results"]["no_duplication_on_repeated_visits"] = False
        errors = lr.validate_locker_filter(plan)
        self.assertTrue(any("no_duplication_on_repeated_visits" in e
                            for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(lr.validate_locker_filter("filter"))


def valid_session_result():
    return {
        "outcomes": [
            {
                "case": "VIKING_HATCHET",
                "route": "locker_list",
                "verdict": "pass",
                "unequipped": True,
                "no_duplication": True,
                "evidence": "locker capture reel B",
            }
        ]
    }


class RecoverySessionResultTests(unittest.TestCase):
    def test_valid_session_result_passes(self):
        self.assertEqual(lr.validate_session_result(valid_session_result()), [])

    def test_failed_case_passes_validation(self):
        result = valid_session_result()
        result["outcomes"][0] = {
            "case": "VIKING_HATCHET",
            "route": "locker_list",
            "verdict": "fail",
        }
        self.assertEqual(lr.validate_session_result(result), [])

    def test_recover_action_route_is_rejected(self):
        result = valid_session_result()
        result["outcomes"][0]["route"] = "recover_action"
        errors = lr.validate_session_result(result)
        self.assertTrue(any("ordinary locker list" in e for e in errors))

    def test_pass_without_dupe_check_is_rejected(self):
        result = valid_session_result()
        del result["outcomes"][0]["no_duplication"]
        errors = lr.validate_session_result(result)
        self.assertTrue(any("no_duplication" in e for e in errors))

    def test_unknown_case_is_rejected(self):
        result = valid_session_result()
        result["outcomes"][0]["case"] = "GOLDEN_GUN"
        errors = lr.validate_session_result(result)
        self.assertTrue(any("evidenced lost-weapon case" in e for e in errors))

    def test_empty_outcomes_are_rejected(self):
        self.assertTrue(lr.validate_session_result({"outcomes": []}))

    def test_non_mapping_result_is_rejected(self):
        self.assertTrue(lr.validate_session_result("hatchet back"))


if __name__ == "__main__":
    unittest.main()
