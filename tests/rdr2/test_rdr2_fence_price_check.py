"""Hermetic checks for the issue-204 fence price comparison (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
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


def valid_session_result():
    return {
        "shop_kind": "fence",
        "legs": {
            "low_honor": {"shop": "Emerald fence", "item": "gold watch", "price": 45},
            "high_honor": {"shop": "Emerald fence", "item": "gold watch", "price": 30},
        },
    }


class FenceSessionResultTests(unittest.TestCase):
    def test_valid_session_result_passes(self):
        self.assertEqual(fp.validate_session_result(valid_session_result()), [])

    def test_baseline_repeat_is_rejected(self):
        result = valid_session_result()
        result["legs"]["low_honor"]["price"] = 30
        errors = fp.validate_session_result(result)
        self.assertTrue(any("must beat" in e for e in errors))

    def test_inverted_legs_are_rejected(self):
        result = valid_session_result()
        result["legs"]["low_honor"]["price"] = 20
        errors = fp.validate_session_result(result)
        self.assertTrue(any("baseline failure" in e for e in errors))

    def test_missing_leg_is_rejected(self):
        result = valid_session_result()
        del result["legs"]["high_honor"]
        errors = fp.validate_session_result(result)
        self.assertTrue(any("high_honor" in e for e in errors))

    def test_non_fence_session_is_rejected(self):
        result = valid_session_result()
        result["shop_kind"] = "general_store"
        errors = fp.validate_session_result(result)
        self.assertTrue(any("fence" in e for e in errors))

    def test_unreadable_price_is_rejected(self):
        result = valid_session_result()
        result["legs"]["low_honor"]["price"] = "lots"
        errors = fp.validate_session_result(result)
        self.assertTrue(any("readable numeric price" in e for e in errors))

    def test_non_mapping_result_is_rejected(self):
        self.assertTrue(fp.validate_session_result("cheap at the fence"))


if __name__ == "__main__":
    unittest.main()
