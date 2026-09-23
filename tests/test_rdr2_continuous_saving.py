"""Hermetic checks for the issue-121 continuous-saving contract (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import continuous_saving as cs


def valid_plan():
    return {
        "approach": "game_owned_save_with_sequence_machine",
        "sections": {
            "request_acknowledgement_sequencing": True,
            "consequence_coverage": True,
            "death_arrest_checkpoint_handling": True,
            "crash_recovery": True,
            "development_only_recovery_hatch": True,
            "bounded_storage": True,
        },
        "consequences": {
            "buy_sell_craft_consume": "commit_boundary_defined",
            "crime_bounty_honor_reward": "commit_boundary_defined",
            "death": "commit_boundary_defined",
            "arrest": "commit_boundary_defined",
            "mission_checkpoint_retry": "commit_boundary_defined",
            "user_exit": "commit_boundary_defined",
            "crash_or_forced_termination": "commit_boundary_defined",
        },
        "mutates_real_saves": False,
    }


class ContinuousSavingTests(unittest.TestCase):
    def test_sections_recorded(self):
        self.assertIn("crash_recovery", cs.required_sections())
        self.assertIn("bounded_storage", cs.required_sections())
        self.assertIn("death", cs.required_consequences())

    def test_valid_plan_passes(self):
        self.assertEqual(cs.validate_saving_plan(valid_plan()), [])

    def test_periodic_autosave_only_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "periodic_autosave_only"
        errors = cs.validate_saving_plan(plan)
        self.assertTrue(any("periodic_autosave_only" in e for e in errors))

    def test_inventory_replay_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "generic_inventory_difference_replay"
        errors = cs.validate_saving_plan(plan)
        self.assertTrue(any("generic_inventory_difference_replay" in e for e in errors))

    def test_uncorrelated_event_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "uncorrelated_save_complete_event"
        errors = cs.validate_saving_plan(plan)
        self.assertTrue(any("uncorrelated_save_complete_event" in e for e in errors))

    def test_missing_consequence_is_rejected(self):
        plan = valid_plan()
        del plan["consequences"]["death"]
        errors = cs.validate_saving_plan(plan)
        self.assertTrue(any("death" in e for e in errors))

    def test_unapproved_save_mutation_is_rejected(self):
        plan = valid_plan()
        plan["mutates_real_saves"] = True
        errors = cs.validate_saving_plan(plan)
        self.assertTrue(any("Real saves" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(cs.validate_saving_plan("autosave"))


def valid_observer_report():
    return {
        "read_only": True,
        "pairs": [
            {
                "sequence": 1,
                "request": "func_110 save request",
                "completion": "func_506 done",
                "correlated": True,
            },
            {
                "sequence": 2,
                "request": "func_110 save request",
                "completion": "func_506 done",
                "correlated": True,
            },
        ],
    }


class ObserverReportTests(unittest.TestCase):
    def test_valid_observer_report_passes(self):
        self.assertEqual(cs.validate_observer_report(valid_observer_report()), [])

    def test_observer_must_be_read_only(self):
        report = valid_observer_report()
        report["read_only"] = False
        errors = cs.validate_observer_report(report)
        self.assertTrue(any("read-only" in e for e in errors))

    def test_uncorrelated_completion_is_rejected(self):
        report = valid_observer_report()
        report["pairs"][0]["correlated"] = False
        errors = cs.validate_observer_report(report)
        self.assertTrue(any("uncorrelated" in e for e in errors))

    def test_reused_sequence_is_rejected(self):
        report = valid_observer_report()
        report["pairs"][1]["sequence"] = 1
        errors = cs.validate_observer_report(report)
        self.assertTrue(any("one-to-one" in e for e in errors))

    def test_pair_must_carry_request_and_completion(self):
        report = valid_observer_report()
        del report["pairs"][0]["completion"]
        errors = cs.validate_observer_report(report)
        self.assertTrue(any("completion" in e for e in errors))

    def test_empty_pairs_are_rejected(self):
        report = valid_observer_report()
        report["pairs"] = []
        self.assertTrue(cs.validate_observer_report(report))

    def test_non_mapping_report_is_rejected(self):
        self.assertTrue(cs.validate_observer_report("saved"))


if __name__ == "__main__":
    unittest.main()
