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


def valid_brief():
    return {
        "subject": "gunsmith map marker",
        "style_axis": "vanilla outline versus filled badge",
        "sizes": ["minimap", "pause map"],
        "presentation_state": "draft",
    }


class VariantBriefTests(unittest.TestCase):
    def test_brief_fields_recorded(self):
        self.assertIn("style_axis", mi.variant_brief_fields())
        self.assertIn("presentation_state", mi.variant_brief_fields())

    def test_valid_brief_passes(self):
        self.assertEqual(mi.validate_variant_brief(valid_brief()), [])

    def test_brief_without_subject_is_rejected(self):
        brief = valid_brief()
        del brief["subject"]
        errors = mi.validate_variant_brief(brief)
        self.assertTrue(any("subject" in e for e in errors))

    def test_unseen_approval_state_is_rejected(self):
        brief = valid_brief()
        brief["presentation_state"] = "approved_unseen"
        errors = mi.validate_variant_brief(brief)
        self.assertTrue(any("presentation state" in e for e in errors))

    def test_non_mapping_brief_is_rejected(self):
        self.assertTrue(mi.validate_variant_brief("variant"))


def valid_review_session():
    return {
        "briefs": [
            {
                "subject": "gunsmith",
                "style_axis": "engraved-vs-flat",
                "sizes": "32/64px",
                "presentation_state": "approved",
                "feedback": ["thin the engraving lines"],
                "revisions": ["rev B with thinner lines"],
                "replace": True,
            }
        ]
    }


class ReviewSessionTests(unittest.TestCase):
    def test_valid_review_session_passes(self):
        self.assertEqual(mi.validate_review_session(valid_review_session()), [])

    def test_unrevised_feedback_is_rejected(self):
        session = valid_review_session()
        session["briefs"][0]["revisions"] = []
        errors = mi.validate_review_session(session)
        self.assertTrue(any("revise every feedback" in e for e in errors))

    def test_replacement_before_approval_is_rejected(self):
        session = valid_review_session()
        session["briefs"][0]["presentation_state"] = "presented"
        errors = mi.validate_review_session(session)
        self.assertTrue(any("approved before replacement" in e for e in errors))

    def test_unapproved_non_replacing_brief_passes(self):
        session = valid_review_session()
        session["briefs"][0]["presentation_state"] = "presented"
        session["briefs"][0]["replace"] = False
        self.assertEqual(mi.validate_review_session(session), [])

    def test_brief_missing_field_is_rejected(self):
        session = valid_review_session()
        del session["briefs"][0]["sizes"]
        errors = mi.validate_review_session(session)
        self.assertTrue(any("sizes" in e for e in errors))

    def test_empty_briefs_are_rejected(self):
        self.assertTrue(mi.validate_review_session({"briefs": []}))

    def test_non_mapping_session_is_rejected(self):
        self.assertTrue(mi.validate_review_session("approved"))


if __name__ == "__main__":
    unittest.main()
