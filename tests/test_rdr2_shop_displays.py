"""Hermetic checks for the issue-140 shop-display contract (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import shop_displays as sd


def valid_plan():
    return {
        "claim": "representative stock layouts",
        "elements": {
            "representative_layouts": True,
            "stated_limits": True,
            "category_level_consistency": True,
            "signature_item_binding": True,
        },
    }


class ShopDisplaysTests(unittest.TestCase):
    def test_scope_recorded(self):
        self.assertIn("representative_layouts", sd.required_elements())
        self.assertIn("streaming", sd.manager_checks())

    def test_valid_plan_passes(self):
        self.assertEqual(sd.validate_display_plan(valid_plan()), [])

    def test_full_mirroring_is_rejected(self):
        plan = valid_plan()
        plan["claim"] = "automatic_full_mirroring everywhere"
        errors = sd.validate_display_plan(plan)
        self.assertTrue(any("automatic_full_mirroring" in e for e in errors))

    def test_one_to_one_shelving_is_rejected(self):
        plan = valid_plan()
        plan["claim"] = "one_to_one_shelving"
        errors = sd.validate_display_plan(plan)
        self.assertTrue(any("one_to_one_shelving" in e for e in errors))

    def test_missing_limit_is_rejected(self):
        plan = valid_plan()
        del plan["elements"]["stated_limits"]
        errors = sd.validate_display_plan(plan)
        self.assertTrue(any("stated_limits" in e for e in errors))

    def test_manager_without_checks_is_rejected(self):
        plan = valid_plan()
        plan["claim"] = "runtime_display_manager"
        plan["manager_checks"] = {"collision": True}
        errors = sd.validate_display_plan(plan)
        self.assertTrue(any("navmesh" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(sd.validate_display_plan("shelves"))


if __name__ == "__main__":
    unittest.main()
