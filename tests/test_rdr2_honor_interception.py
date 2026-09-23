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


if __name__ == "__main__":
    unittest.main()
