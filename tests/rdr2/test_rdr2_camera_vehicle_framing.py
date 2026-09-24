"""Hermetic checks for the issue-108 camera/framing contract (no game)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.rdr2 import camera_vehicle_framing as cvf


def valid_plan():
    return {
        "claim": "binary vehicle framing",
        "profiles": {
            "standing": {"fields": ["offset", "distance"]},
            "crouched": {"fields": ["offset", "distance"]},
            "prone": {"fields": ["offset", "distance"]},
            "horseback": {"fields": ["offset", "distance"]},
            "vehicle": {
                "fields": ["offset", "distance"],
                "framing_states": ["LOW", "NORMAL"],
            },
            "aim": {"fields": ["offset", "distance"]},
            "crouched_aim": {"fields": ["offset", "distance"]},
            "armed": {"fields": ["offset", "distance"]},
            "crouched_armed": {"fields": ["offset", "distance"]},
        },
        "authoring_gated_by_developer_mode": True,
        "vehicle_handoff_owner": "#220",
    }


class CameraVehicleFramingTests(unittest.TestCase):
    def test_profiles_recorded(self):
        self.assertIn("vehicle", cvf.profiles())
        self.assertIn("prone", cvf.profiles())
        self.assertEqual(len(cvf.profiles()), 9)

    def test_framing_states_binary(self):
        self.assertEqual(cvf.vehicle_framing_states(), ["LOW", "NORMAL"])

    def test_valid_plan_passes(self):
        self.assertEqual(cvf.validate_framing_plan(valid_plan()), [])

    def test_continuous_y_claim_is_rejected(self):
        plan = valid_plan()
        plan["claim"] = "continuous_y_positioning per profile"
        errors = cvf.validate_framing_plan(plan)
        self.assertTrue(any("continuous_y_positioning" in e for e in errors))

    def test_unproven_vehicle_state_is_rejected(self):
        plan = valid_plan()
        plan["profiles"]["vehicle"]["framing_states"] = ["LOW", "HIGH"]
        errors = cvf.validate_framing_plan(plan)
        self.assertTrue(any("HIGH" in e for e in errors))

    def test_missing_profile_is_rejected(self):
        plan = valid_plan()
        del plan["profiles"]["prone"]
        errors = cvf.validate_framing_plan(plan)
        self.assertTrue(any("prone" in e for e in errors))

    def test_ungated_authoring_is_rejected(self):
        plan = valid_plan()
        plan["authoring_gated_by_developer_mode"] = False
        errors = cvf.validate_framing_plan(plan)
        self.assertTrue(any("developer mode" in e for e in errors))

    def test_handoff_owner_must_stay_220(self):
        plan = valid_plan()
        plan["vehicle_handoff_owner"] = "this plan"
        errors = cvf.validate_framing_plan(plan)
        self.assertTrue(any("#220" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(cvf.validate_framing_plan("low"))


def valid_preset_apply():
    return {
        "profile": "horseback",
        "values": {"offset": 0.4, "distance": 2.5},
        "requires_developer_mode": False,
    }


class PresetApplyTests(unittest.TestCase):
    def test_valid_preset_apply_passes(self):
        self.assertEqual(cvf.validate_preset_apply(valid_preset_apply()), [])

    def test_every_kept_profile_applies(self):
        for profile in cvf.profiles():
            request = valid_preset_apply()
            request["profile"] = profile
            self.assertEqual(cvf.validate_preset_apply(request), [], profile)

    def test_unknown_profile_is_rejected(self):
        request = valid_preset_apply()
        request["profile"] = "submarine"
        self.assertTrue(cvf.validate_preset_apply(request))

    def test_apply_must_not_require_developer_mode(self):
        request = valid_preset_apply()
        request["requires_developer_mode"] = True
        errors = cvf.validate_preset_apply(request)
        self.assertTrue(any("developer mode" in e for e in errors))

    def test_apply_without_values_is_rejected(self):
        request = valid_preset_apply()
        request["values"] = {}
        self.assertTrue(cvf.validate_preset_apply(request))

    def test_rejected_claim_is_rejected(self):
        request = valid_preset_apply()
        request["claim"] = "continuous_y_positioning preset"
        errors = cvf.validate_preset_apply(request)
        self.assertTrue(any("continuous_y_positioning" in e for e in errors))

    def test_non_mapping_request_is_rejected(self):
        self.assertTrue(cvf.validate_preset_apply("apply"))


if __name__ == "__main__":
    unittest.main()
