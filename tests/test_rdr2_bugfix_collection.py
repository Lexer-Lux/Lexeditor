"""Hermetic checks for the issue-159 bugfix manifest (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import bugfix_collection as bc


def valid_plan():
    return {
        "ships_independently": True,
        "entries": {
            "wickiup_map_artwork": {
                "problem": "misnamed minimap artwork",
                "verification": "minimap comparison",
                "permission": "credited reuse allowed",
            },
            "dreamcatcher_cleanup": {
                "problem": "completed entry remains",
                "verification": "completion flow check",
                "permission": "recreated from current assets",
            },
        },
    }


class BugfixCollectionTests(unittest.TestCase):
    def test_first_targets_recorded(self):
        self.assertIn("wickiup_map_artwork", bc.first_targets())
        self.assertIn("dreamcatcher_cleanup", bc.first_targets())

    def test_valid_plan_passes(self):
        self.assertEqual(bc.validate_bugfix_collection(valid_plan()), [])

    def test_toggle_preference_is_rejected(self):
        plan = valid_plan()
        plan["entries"]["run_walk_toggle_preference"] = True
        errors = bc.validate_bugfix_collection(plan)
        self.assertTrue(any("run_walk_toggle_preference" in e for e in errors))

    def test_monolithic_patch_is_rejected(self):
        plan = valid_plan()
        plan["entries"]["monolithic_combined_patch"] = True
        errors = bc.validate_bugfix_collection(plan)
        self.assertTrue(any("monolithic_combined_patch" in e for e in errors))

    def test_missing_permission_is_rejected(self):
        plan = valid_plan()
        del plan["entries"]["wickiup_map_artwork"]["permission"]
        errors = bc.validate_bugfix_collection(plan)
        self.assertTrue(any("permission" in e for e in errors))

    def test_clothing_without_comparison_is_rejected(self):
        plan = valid_plan()
        plan["entries"]["nexus_4909_clothing_physics"] = {
            "problem": "physics assets",
            "verification": "wear check",
            "permission": "recreated",
        }
        errors = bc.validate_bugfix_collection(plan)
        self.assertTrue(any("asset regression comparison" in e for e in errors))

    def test_combined_shipping_is_rejected(self):
        plan = valid_plan()
        plan["ships_independently"] = False
        errors = bc.validate_bugfix_collection(plan)
        self.assertTrue(any("independently" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(bc.validate_bugfix_collection("fixes"))


def valid_manifests():
    return {
        "wickiup_map_artwork": {
            "problem": "misnamed minimap artwork",
            "verification": "minimap comparison",
            "permission": "credited reuse allowed",
        },
        "dreamcatcher_cleanup": {
            "problem": "completed entry remains",
            "verification": "completion flow check",
            "permission": "recreated from current assets",
        },
    }


class FirstTargetManifestTests(unittest.TestCase):
    def test_shipped_manifests_cover_both_first_targets(self):
        manifests = {e["entry"]: e for e in bc.first_target_manifests()}
        self.assertEqual(
            bc.validate_first_target_manifests(manifests), []
        )

    def test_valid_manifests_pass(self):
        self.assertEqual(
            bc.validate_first_target_manifests(valid_manifests()), []
        )

    def test_missing_dreamcatcher_manifest_is_rejected(self):
        manifests = valid_manifests()
        del manifests["dreamcatcher_cleanup"]
        errors = bc.validate_first_target_manifests(manifests)
        self.assertTrue(any("dreamcatcher_cleanup" in e for e in errors))

    def test_manifest_without_permission_is_rejected(self):
        manifests = valid_manifests()
        del manifests["wickiup_map_artwork"]["permission"]
        errors = bc.validate_first_target_manifests(manifests)
        self.assertTrue(any("permission" in e for e in errors))

    def test_later_fix_is_not_a_first_target(self):
        manifests = valid_manifests()
        manifests["nexus_4909_clothing_physics"] = {
            "problem": "physics assets",
            "verification": "wear check",
            "permission": "recreated",
        }
        errors = bc.validate_first_target_manifests(manifests)
        self.assertTrue(any("not a first target" in e for e in errors))

    def test_non_mapping_manifests_are_rejected(self):
        self.assertTrue(bc.validate_first_target_manifests("manifests"))


def valid_delivery_record():
    return {
        "entry": "wickiup_map_artwork",
        "built_from": "credited Nexus 2953 fix",
        "verification": "corrected YTD name checked against current files",
        "ships_independently": True,
    }


class DeliveryRecordTests(unittest.TestCase):
    def test_valid_delivery_record_passes(self):
        self.assertEqual(bc.validate_delivery_record(valid_delivery_record()), [])

    def test_excluded_entry_is_rejected(self):
        record = valid_delivery_record()
        record["entry"] = "run_walk_toggle_preference"
        errors = bc.validate_delivery_record(record)
        self.assertTrue(any("must not ship" in e for e in errors))

    def test_missing_verification_is_rejected(self):
        record = valid_delivery_record()
        del record["verification"]
        errors = bc.validate_delivery_record(record)
        self.assertTrue(any("verification" in e for e in errors))

    def test_comparison_candidate_needs_comparison(self):
        record = valid_delivery_record()
        record["entry"] = "nexus_4909_clothing_physics"
        errors = bc.validate_delivery_record(record)
        self.assertTrue(any("asset regression comparison" in e for e in errors))

    def test_unnamed_entry_is_rejected(self):
        record = valid_delivery_record()
        del record["entry"]
        errors = bc.validate_delivery_record(record)
        self.assertTrue(any("name its collection entry" in e for e in errors))

    def test_non_mapping_record_is_rejected(self):
        self.assertTrue(bc.validate_delivery_record("wickiup fixed"))


if __name__ == "__main__":
    unittest.main()
