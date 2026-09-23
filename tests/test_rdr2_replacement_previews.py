"""Hermetic checks for the issue-111 replacement preview gate (no game, no art)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import replacement_previews as rp


def valid_plan():
    return {
        "families": {
            "pistol_casings": {"preview_shown": True, "approved": True,
                               "ship": True},
            "shotgun_hulls": {"preview_shown": True, "approved": False,
                              "ship": False},
        }
    }


class ReplacementPreviewTests(unittest.TestCase):
    def test_families_record_hull_fallback(self):
        states = {e["family"]: e["state"] for e in rp.replacement_families()}
        self.assertEqual(states["shotgun_hulls"], "vanilla_fallback")
        self.assertEqual(states["empty_bottle"], "previewed")

    def test_valid_plan_passes(self):
        self.assertEqual(rp.validate_replacement_plan(valid_plan()), [])

    def test_missing_preview_is_rejected(self):
        plan = valid_plan()
        plan["families"]["pistol_casings"]["preview_shown"] = False
        errors = rp.validate_replacement_plan(plan)
        self.assertTrue(any("preview" in e for e in errors))

    def test_unapproved_ship_is_rejected(self):
        plan = valid_plan()
        plan["families"]["pistol_casings"]["approved"] = False
        errors = rp.validate_replacement_plan(plan)
        self.assertTrue(any("approval" in e for e in errors))

    def test_fallback_family_must_not_ship(self):
        plan = valid_plan()
        plan["families"]["shotgun_hulls"]["approved"] = True
        plan["families"]["shotgun_hulls"]["ship"] = True
        errors = rp.validate_replacement_plan(plan)
        self.assertTrue(any("vanilla_fallback" in e for e in errors))

    def test_unknown_family_is_rejected(self):
        plan = {"families": {"saddle_icons": {"preview_shown": True}}}
        errors = rp.validate_replacement_plan(plan)
        self.assertTrue(any("not a tracked replacement" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(rp.validate_replacement_plan("preview"))


if __name__ == "__main__":
    unittest.main()
