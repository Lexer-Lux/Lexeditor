"""Hermetic checks for the issue-138 map-icon review flow (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import map_icons as mi


def valid_plan():
    return {
        "claim": "variants shown then approved",
        "steps": {
            "prepare_candidate_variants": True,
            "present_for_feedback": True,
            "revise_from_feedback": True,
            "explicit_approval": True,
            "replace_existing_artwork": True,
        },
        "step_order": list(mi.review_steps()),
    }


class MapIconsTests(unittest.TestCase):
    def test_steps_recorded(self):
        self.assertEqual(mi.review_steps()[0], "prepare_candidate_variants")
        self.assertEqual(mi.review_steps()[-1], "replace_existing_artwork")

    def test_valid_plan_passes(self):
        self.assertEqual(mi.validate_icon_review(valid_plan()), [])

    def test_unseen_approval_is_rejected(self):
        plan = valid_plan()
        plan["claim"] = "approve_unseen_artwork granted"
        errors = mi.validate_icon_review(plan)
        self.assertTrue(any("approve_unseen_artwork" in e for e in errors))

    def test_unapproved_ship_is_rejected(self):
        plan = valid_plan()
        plan["claim"] = "ship_unapproved_artwork now"
        errors = mi.validate_icon_review(plan)
        self.assertTrue(any("ship_unapproved_artwork" in e for e in errors))

    def test_replacement_before_approval_is_rejected(self):
        plan = valid_plan()
        plan["steps"]["explicit_approval"] = False
        errors = mi.validate_icon_review(plan)
        self.assertTrue(any("before approval" in e for e in errors))

    def test_wrong_order_is_rejected(self):
        plan = valid_plan()
        plan["step_order"] = list(reversed(mi.review_steps()))
        errors = mi.validate_icon_review(plan)
        self.assertTrue(any("order" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(mi.validate_icon_review("icons"))


if __name__ == "__main__":
    unittest.main()
