"""Hermetic checks for the issue-204 fence price comparison (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import fence_price_check as fp


def valid_plan():
    return {
        "shop_kind": "fence",
        "legs": {
            "low_honor": {"shop": "emerald_ranch_fence", "item": "gold_watch", "price": 45},
            "high_honor": {"shop": "emerald_ranch_fence", "item": "gold_watch", "price": 30},
        },
        "open_unknowns": ["independent shop-modifier correction unbuilt"],
    }


class FencePriceCheckTests(unittest.TestCase):
    def test_valid_plan_passes(self):
        self.assertEqual(fp.validate_price_check(valid_plan()), [])

    def test_missing_high_honor_leg_is_rejected(self):
        plan = valid_plan()
        del plan["legs"]["high_honor"]
        errors = fp.validate_price_check(plan)
        self.assertTrue(any("high_honor" in e for e in errors))

    def test_unreadable_price_is_rejected(self):
        plan = valid_plan()
        plan["legs"]["low_honor"]["price"] = None
        errors = fp.validate_price_check(plan)
        self.assertTrue(any("readable price" in e for e in errors))

    def test_different_shops_are_rejected(self):
        plan = valid_plan()
        plan["legs"]["high_honor"]["shop"] = "saint_denis_fence"
        errors = fp.validate_price_check(plan)
        self.assertTrue(any("same shop" in e for e in errors))

    def test_different_items_are_rejected(self):
        plan = valid_plan()
        plan["legs"]["high_honor"]["item"] = "silver_ring"
        errors = fp.validate_price_check(plan)
        self.assertTrue(any("same item" in e for e in errors))

    def test_normal_store_cannot_prove_fence_correction(self):
        plan = valid_plan()
        plan["shop_kind"] = "general_store"
        errors = fp.validate_price_check(plan)
        self.assertTrue(any("must run at a fence" in e for e in errors))

    def test_correction_must_stay_owned_as_unknown(self):
        plan = valid_plan()
        plan["open_unknowns"] = ["everything works"]
        errors = fp.validate_price_check(plan)
        self.assertTrue(any("shop-modifier" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(fp.validate_price_check("cheap fence"))


if __name__ == "__main__":
    unittest.main()
