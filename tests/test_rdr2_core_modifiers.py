"""Hermetic checks for the issue-226 core-modifier boundary (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import core_modifiers as cm


def valid_proposal():
    return {
        "engine_routine": "tbd-from-matching-binary",
        "targets": ["tbd-from-matching-binary"],
        "changes_unrelated_rates": False,
        "open_unknowns": ["ownership proof pending", "cadence proof pending"],
    }


class CoreModifierTests(unittest.TestCase):
    def test_forecast_terms_recorded(self):
        terms = {t["term"]: t["value"] for t in cm.forecast_terms()}
        self.assertEqual(terms["perfect_weight"], 0.15)
        self.assertEqual(terms["extreme_weight"], -0.25)
        self.assertEqual(terms["mounted"], 0.25)
        first = cm.forecast_terms()
        first.append({"term": "x"})
        self.assertEqual(len(cm.forecast_terms()), 3)

    def test_valid_proposal_passes(self):
        self.assertEqual(cm.validate_removal_proposal(valid_proposal()), [])

    def test_missing_engine_routine_is_rejected(self):
        proposal = valid_proposal()
        proposal["engine_routine"] = ""
        errors = cm.validate_removal_proposal(proposal)
        self.assertTrue(any("engine core-decrement routine" in e for e in errors))

    def test_forecast_only_target_is_rejected(self):
        proposal = valid_proposal()
        proposal["targets"] = ["func_2976"]
        errors = cm.validate_removal_proposal(proposal)
        self.assertTrue(any("forecast-only" in e for e in errors))

    def test_shared_field_target_is_rejected(self):
        proposal = valid_proposal()
        proposal["targets"] = ["Global_49"]
        errors = cm.validate_removal_proposal(proposal)
        self.assertTrue(any("shared with trinket" in e for e in errors))

    def test_unrelated_rate_change_is_rejected(self):
        proposal = valid_proposal()
        proposal["changes_unrelated_rates"] = True
        errors = cm.validate_removal_proposal(proposal)
        self.assertTrue(any("unrelated core rates" in e for e in errors))

    def test_unowned_cadence_is_rejected(self):
        proposal = valid_proposal()
        proposal["open_unknowns"] = ["ownership proof pending"]
        errors = cm.validate_removal_proposal(proposal)
        self.assertTrue(any("cadence" in e for e in errors))

    def test_non_mapping_proposal_is_rejected(self):
        self.assertTrue(cm.validate_removal_proposal("zero it all"))


def valid_routine_candidate():
    return {
        "routine": "engine_decrement_0x1A2B",
        "binary_fingerprint": "RDR2-1491.50",
        "decrement_behavior": "per-tick core drain",
        "term_inputs": ["weight term", "mounted term"],
        "targets": ["weight term", "mounted term"],
        "open_unknowns": ["ownership proof owed", "cadence proof owed"],
    }


class RoutineCandidateTests(unittest.TestCase):
    def test_valid_routine_candidate_passes(self):
        self.assertEqual(cm.validate_routine_candidate(valid_routine_candidate()), [])

    def test_forecast_routine_is_rejected(self):
        candidate = valid_routine_candidate()
        candidate["routine"] = "func_2976"
        errors = cm.validate_routine_candidate(candidate)
        self.assertTrue(any("forecast-only" in e for e in errors))

    def test_shared_field_target_is_rejected(self):
        candidate = valid_routine_candidate()
        candidate["targets"] = ["Global_49"]
        errors = cm.validate_routine_candidate(candidate)
        self.assertTrue(any("shared with trinket/outfit" in e for e in errors))

    def test_missing_term_inputs_is_rejected(self):
        candidate = valid_routine_candidate()
        del candidate["term_inputs"]
        errors = cm.validate_routine_candidate(candidate)
        self.assertTrue(any("term_inputs" in e for e in errors))

    def test_unowned_cadence_is_rejected(self):
        candidate = valid_routine_candidate()
        candidate["open_unknowns"] = ["ownership proof owed"]
        errors = cm.validate_routine_candidate(candidate)
        self.assertTrue(any("cadence" in e for e in errors))

    def test_non_mapping_candidate_is_rejected(self):
        self.assertTrue(cm.validate_routine_candidate("the drain function"))


if __name__ == "__main__":
    unittest.main()
