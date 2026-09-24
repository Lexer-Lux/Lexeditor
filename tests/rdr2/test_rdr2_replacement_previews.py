"""Hermetic checks for the issue-111 replacement preview gate (no game, no art)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
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


def valid_pickup_check():
    return {
        "full_restart": True,
        "families": {
            "pistol_casings": {
                "satchel_icon_visible": True,
                "acquisition_card_visible": True,
                "matches_preview": True,
            },
            "empty_bottle": {
                "satchel_icon_visible": True,
                "acquisition_card_visible": True,
                "matches_preview": True,
            },
        },
    }


class PickupCheckTests(unittest.TestCase):
    def test_valid_pickup_check_passes(self):
        self.assertEqual(rp.validate_pickup_check(valid_pickup_check()), [])

    def test_blank_acquisition_card_is_rejected(self):
        check = valid_pickup_check()
        check["families"]["pistol_casings"]["acquisition_card_visible"] = False
        errors = rp.validate_pickup_check(check)
        self.assertTrue(any("acquisition_card_visible" in e for e in errors))

    def test_fallback_family_cannot_match_preview(self):
        check = valid_pickup_check()
        check["families"]["shotgun_hulls"] = {
            "satchel_icon_visible": True,
            "acquisition_card_visible": True,
            "matches_preview": True,
        }
        errors = rp.validate_pickup_check(check)
        self.assertTrue(any("vanilla_fallback" in e for e in errors))

    def test_check_requires_full_restart(self):
        check = valid_pickup_check()
        check["full_restart"] = False
        errors = rp.validate_pickup_check(check)
        self.assertTrue(any("full restart" in e for e in errors))

    def test_unknown_family_is_rejected(self):
        check = valid_pickup_check()
        check["families"]["saddle_soap"] = {"satchel_icon_visible": True}
        errors = rp.validate_pickup_check(check)
        self.assertTrue(any("not a tracked replacement" in e for e in errors))

    def test_non_mapping_check_is_rejected(self):
        self.assertTrue(rp.validate_pickup_check("icons look fine"))


if __name__ == "__main__":
    unittest.main()
