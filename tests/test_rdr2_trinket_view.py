"""Hermetic checks for the issue-136 trinket-view contract (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import trinket_view as tv


def page_plan():
    return {
        "route": "mod_owned_page",
        "claim": "separate owned trinket page",
        "page": {
            "owned_only_membership": True,
            "read_only_no_equip_discard_activate": True,
            "selected_name_and_effect_details": True,
            "keyboard_selection": True,
            "back_request": True,
        },
    }


class TrinketViewTests(unittest.TestCase):
    def test_requirements_recorded(self):
        self.assertIn("owned_only_membership", tv.page_requirements())
        self.assertIn("back_request", tv.page_requirements())
        self.assertIn("focus_and_back_handling", tv.native_tab_requirements())

    def test_valid_page_passes(self):
        self.assertEqual(tv.validate_trinket_proposal(page_plan()), [])

    def test_valid_native_tab_passes(self):
        plan = {
            "route": "native_tab",
            "claim": "tab after probe",
            "probe": {
                "isolated_datastore_injection_probe": True,
                "category_filter_selection_proof": True,
                "focus_and_back_handling": True,
                "sizing_proof": True,
            },
        }
        self.assertEqual(tv.validate_trinket_proposal(plan), [])

    def test_catalog_tab_claim_is_rejected(self):
        plan = page_plan()
        plan["claim"] = "catalog_metadata_adds_tab"
        errors = tv.validate_trinket_proposal(plan)
        self.assertTrue(any("catalog_metadata_adds_tab" in e for e in errors))

    def test_supported_category_claim_is_rejected(self):
        plan = page_plan()
        plan["claim"] = "new_native_category_supported"
        errors = tv.validate_trinket_proposal(plan)
        self.assertTrue(any("new_native_category_supported" in e for e in errors))

    def test_unproven_native_tab_is_rejected(self):
        plan = {"route": "native_tab", "claim": "tab", "probe": {}}
        errors = tv.validate_trinket_proposal(plan)
        self.assertTrue(any("isolated_datastore_injection_probe" in e for e in errors))

    def test_missing_route_is_rejected(self):
        plan = page_plan()
        plan["route"] = ""
        errors = tv.validate_trinket_proposal(plan)
        self.assertTrue(any("must select" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(tv.validate_trinket_proposal("trinkets"))


def valid_probe_result():
    return {
        "checks": {
            "isolated_datastore_injection_probe": True,
            "category_filter_selection_proof": True,
            "focus_and_back_handling": True,
            "sizing_proof": True,
        },
        "verdict": "pass",
        "route": "native_tab",
    }


class InjectionProbeResultTests(unittest.TestCase):
    def test_passing_probe_keeps_native_tab(self):
        self.assertEqual(tv.validate_probe_result(valid_probe_result()), [])

    def test_failing_probe_selects_mod_owned_page(self):
        result = valid_probe_result()
        result["checks"]["sizing_proof"] = False
        result["verdict"] = "fail"
        result["route"] = "mod_owned_page"
        self.assertEqual(tv.validate_probe_result(result), [])

    def test_pass_with_failed_check_is_rejected(self):
        result = valid_probe_result()
        result["checks"]["focus_and_back_handling"] = False
        errors = tv.validate_probe_result(result)
        self.assertTrue(any("cannot pass" in e for e in errors))

    def test_fail_keeping_native_tab_is_rejected(self):
        result = valid_probe_result()
        result["checks"]["sizing_proof"] = False
        result["verdict"] = "fail"
        errors = tv.validate_probe_result(result)
        self.assertTrue(any("mod_owned_page" in e for e in errors))

    def test_unrecorded_check_is_rejected(self):
        result = valid_probe_result()
        del result["checks"]["sizing_proof"]
        errors = tv.validate_probe_result(result)
        self.assertTrue(any("sizing_proof" in e for e in errors))

    def test_non_mapping_result_is_rejected(self):
        self.assertTrue(tv.validate_probe_result("injected"))


if __name__ == "__main__":
    unittest.main()
