"""Hermetic checks for the issue-134 horse-feeding mapping (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.rdr2 import horse_feeding as hf


def valid_plan():
    return {
        "approach": "item_aware_magnitude_substitution",
        "surfaces": {
            "func_739_item_identity": True,
            "func_454_checks": True,
            "func_724_eligibility": True,
            "func_789_preferred_selection": True,
        },
        "magnitudes": {
            "substitutes_configured_magnitude": True,
            "keeps_item_hash_through_func_739": True,
        },
    }


class HorseFeedingTests(unittest.TestCase):
    def test_bond_bases_recorded(self):
        self.assertEqual(hf.bond_event_bases()["event13"], 15)
        self.assertEqual(hf.bond_event_bases()["event16"], 5)
        self.assertIn("func_724_eligibility", hf.required_surfaces())

    def test_valid_plan_passes(self):
        self.assertEqual(hf.validate_feed_mapping(valid_plan()), [])

    def test_watcher_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "after_consumption_watcher"
        errors = hf.validate_feed_mapping(plan)
        self.assertTrue(any("after_consumption_watcher" in e for e in errors))

    def test_fixed_amount_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "fixed_amount_substitution"
        errors = hf.validate_feed_mapping(plan)
        self.assertTrue(any("fixed_amount_substitution" in e for e in errors))

    def test_generic_hook_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "generic_attribute_hook"
        errors = hf.validate_feed_mapping(plan)
        self.assertTrue(any("generic_attribute_hook" in e for e in errors))

    def test_missing_surface_is_rejected(self):
        plan = valid_plan()
        del plan["surfaces"]["func_789_preferred_selection"]
        errors = hf.validate_feed_mapping(plan)
        self.assertTrue(any("func_789_preferred_selection" in e for e in errors))

    def test_dropped_item_hash_is_rejected(self):
        plan = valid_plan()
        plan["magnitudes"]["keeps_item_hash_through_func_739"] = False
        errors = hf.validate_feed_mapping(plan)
        self.assertTrue(any("func_739" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(hf.validate_feed_mapping("oats"))


def valid_feed_config():
    return {
        "substitution_point": "func_454_magnitude_only",
        "allowlist_extension": ["HASH_OAT_CAKES", "HASH_HERB_SAGE"],
        "items": {"HASH_OAT_CAKES": 10, "HASH_HERB_SAGE": 5},
    }


class FeedConfigTests(unittest.TestCase):
    def test_valid_feed_config_passes(self):
        self.assertEqual(hf.validate_feed_config(valid_feed_config()), [])

    def test_unlisted_item_is_rejected(self):
        config = valid_feed_config()
        config["items"]["HASH_APPLE"] = 8
        errors = hf.validate_feed_config(config)
        self.assertTrue(any("allowlist" in e for e in errors))

    def test_non_positive_magnitude_is_rejected(self):
        config = valid_feed_config()
        config["items"]["HASH_OAT_CAKES"] = 0
        errors = hf.validate_feed_config(config)
        self.assertTrue(any("positive integer" in e for e in errors))

    def test_wrong_substitution_point_is_rejected(self):
        config = valid_feed_config()
        config["substitution_point"] = "after_consumption_watcher"
        errors = hf.validate_feed_config(config)
        self.assertTrue(any("func_454" in e for e in errors))

    def test_empty_items_are_rejected(self):
        config = valid_feed_config()
        config["items"] = {}
        self.assertTrue(hf.validate_feed_config(config))

    def test_non_mapping_config_is_rejected(self):
        self.assertTrue(hf.validate_feed_config("oats"))


if __name__ == "__main__":
    unittest.main()
