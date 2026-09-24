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


def valid_template():
    return {
        "shop_type": "gunsmith",
        "display_slots": ["counter rack", "wall pegs"],
        "category_assignment": "long arms on rack, sidearms on pegs",
        "signature_items": ["engraved Schofield"],
        "stated_limits": "menu lists more variants than slots hold",
    }


class LayoutTemplateTests(unittest.TestCase):
    def test_template_fields_recorded(self):
        self.assertIn("signature_items", sd.layout_template_fields())
        self.assertIn("stated_limits", sd.layout_template_fields())

    def test_valid_template_passes(self):
        self.assertEqual(sd.validate_layout_template(valid_template()), [])

    def test_template_without_limits_is_rejected(self):
        template = valid_template()
        del template["stated_limits"]
        errors = sd.validate_layout_template(template)
        self.assertTrue(any("stated_limits" in e for e in errors))

    def test_empty_slots_are_rejected(self):
        template = valid_template()
        template["display_slots"] = []
        errors = sd.validate_layout_template(template)
        self.assertTrue(any("display slot" in e for e in errors))

    def test_mirroring_template_is_rejected(self):
        template = valid_template()
        template["claim"] = "one_to_one_shelving"
        errors = sd.validate_layout_template(template)
        self.assertTrue(any("one_to_one_shelving" in e for e in errors))

    def test_non_mapping_template_is_rejected(self):
        self.assertTrue(sd.validate_layout_template("layout"))


def valid_shop_layout():
    return {
        "shop_type": "gunsmith",
        "display_slots": [
            {"slot": "wall-rack-1", "category": "revolvers"},
            {"slot": "counter-case", "signature_item": "Calloway Schofield"},
        ],
        "category_assignment": "revolvers on wall rack",
        "signature_items": "Calloway Schofield in counter case",
        "stated_limits": "two slots only; longarms not represented",
        "removed_unsold_displays": True,
    }


class ShopLayoutTests(unittest.TestCase):
    def test_valid_shop_layout_passes(self):
        self.assertEqual(sd.validate_shop_layout(valid_shop_layout()), [])

    def test_unassigned_slot_is_rejected(self):
        layout = valid_shop_layout()
        layout["display_slots"][0] = {"slot": "wall-rack-1"}
        errors = sd.validate_shop_layout(layout)
        self.assertTrue(any("category or signature_item" in e for e in errors))

    def test_missing_unsold_removal_is_rejected(self):
        layout = valid_shop_layout()
        layout["removed_unsold_displays"] = False
        errors = sd.validate_shop_layout(layout)
        self.assertTrue(any("unsold categories" in e for e in errors))

    def test_missing_template_field_is_rejected(self):
        layout = valid_shop_layout()
        del layout["stated_limits"]
        errors = sd.validate_shop_layout(layout)
        self.assertTrue(any("stated_limits" in e for e in errors))

    def test_rejected_claim_is_rejected(self):
        layout = valid_shop_layout()
        layout["claim"] = "automatic_full_mirroring for gunsmiths"
        errors = sd.validate_shop_layout(layout)
        self.assertTrue(any("automatic_full_mirroring" in e for e in errors))

    def test_non_mapping_layout_is_rejected(self):
        self.assertTrue(sd.validate_shop_layout("gunsmith shelves"))


if __name__ == "__main__":
    unittest.main()
