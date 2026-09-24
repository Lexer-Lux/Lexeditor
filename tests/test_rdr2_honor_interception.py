"""Hermetic checks for the issue-161 interception design contract (no game)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import honor_interception as hi


def valid_plan():
    return {
        "approach": "pre_tier_identity_preserving_hook",
        "hook": {
            "fires_before_tier_application": True,
            "preserves_event_identity": True,
            "bounty_dog_only_blocking": True,
        },
        "ui": {
            "no_per_action_amount_fields": True,
            "shared_tier_scope_note_kept": True,
        },
    }


class HonorInterceptionTests(unittest.TestCase):
    def test_hook_properties_recorded(self):
        self.assertIn("preserves_event_identity",
                      hi.required_hook_properties())

    def test_valid_plan_passes(self):
        self.assertEqual(hi.validate_interception_plan(valid_plan()), [])

    def test_post_tier_rewrite_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "post_tier_amount_rewrite"
        errors = hi.validate_interception_plan(plan)
        self.assertTrue(any("post_tier_amount_rewrite" in e for e in errors))

    def test_unproven_identity_is_rejected(self):
        plan = valid_plan()
        plan["hook"]["preserves_event_identity"] = False
        errors = hi.validate_interception_plan(plan)
        self.assertTrue(any("preserves_event_identity" in e for e in errors))

    def test_broad_blocking_is_rejected(self):
        plan = valid_plan()
        plan["hook"]["bounty_dog_only_blocking"] = False
        errors = hi.validate_interception_plan(plan)
        self.assertTrue(any("bounty_dog_only_blocking" in e for e in errors))

    def test_per_action_amount_ui_is_rejected(self):
        plan = valid_plan()
        plan["ui"]["no_per_action_amount_fields"] = False
        errors = hi.validate_interception_plan(plan)
        self.assertTrue(any("no_per_action_amount_fields" in e
                            for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(hi.validate_interception_plan("honor"))


def valid_hook_candidate():
    return {
        "native": "HONOR::_APPLY_HONOR_EVENT",
        "build_fingerprint": "1491.50",
        "evidence": {
            "fires_before_tier_application": {
                "interception_point": "event dispatch hook",
                "observation": "hook fires before tier write in trace",
            },
            "preserves_event_identity": {
                "interception_point": "event dispatch hook",
                "observation": "event hash readable at hook time",
            },
            "bounty_dog_only_blocking": {
                "interception_point": "event dispatch hook",
                "observation": "PoliceDog ped blocked, farm animals pass",
            },
        },
    }


class HookCandidateTests(unittest.TestCase):
    def test_valid_hook_candidate_passes(self):
        self.assertEqual(hi.validate_hook_candidate(valid_hook_candidate()), [])

    def test_unnamed_native_is_rejected(self):
        candidate = valid_hook_candidate()
        del candidate["native"]
        errors = hi.validate_hook_candidate(candidate)
        self.assertTrue(any("researched native" in e for e in errors))

    def test_missing_fingerprint_is_rejected(self):
        candidate = valid_hook_candidate()
        del candidate["build_fingerprint"]
        errors = hi.validate_hook_candidate(candidate)
        self.assertTrue(any("fingerprint" in e for e in errors))

    def test_missing_property_evidence_is_rejected(self):
        candidate = valid_hook_candidate()
        del candidate["evidence"]["preserves_event_identity"]
        errors = hi.validate_hook_candidate(candidate)
        self.assertTrue(any("preserves_event_identity" in e for e in errors))

    def test_evidence_without_observation_is_rejected(self):
        candidate = valid_hook_candidate()
        del candidate["evidence"]["bounty_dog_only_blocking"]["observation"]
        errors = hi.validate_hook_candidate(candidate)
        self.assertTrue(any("observation" in e for e in errors))

    def test_non_mapping_candidate_is_rejected(self):
        self.assertTrue(hi.validate_hook_candidate("some native"))


if __name__ == "__main__":
    unittest.main()
