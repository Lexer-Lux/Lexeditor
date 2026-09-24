"""Hermetic checks for the issue-133 hunting-tracks protocol (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import hunting_tracks as ht


def valid_plan():
    return {
        "design_choice": "",
        "measurements": {
            "trail_lifetime_after_stream_out": True,
            "trail_lifetime_after_explicit_deletion": True,
            "tagged_animal_identity": True,
            "streaming_conditions": True,
        },
    }


class HuntingTracksTests(unittest.TestCase):
    def test_protocol_recorded(self):
        self.assertIn("trail_lifetime_after_stream_out", ht.required_measurements())
        self.assertIn("hidden_distant_target_ped", ht.viable_designs())
        self.assertIn("custom_signs_with_later_spawn", ht.viable_designs())

    def test_undecided_probe_passes(self):
        self.assertEqual(ht.validate_track_experiment(valid_plan()), [])

    def test_viable_choice_after_probe_passes(self):
        plan = valid_plan()
        plan["design_choice"] = "hidden_distant_target_ped"
        self.assertEqual(ht.validate_track_experiment(plan), [])

    def test_native_choice_without_evidence_is_rejected(self):
        plan = valid_plan()
        plan["design_choice"] = "native_trails_without_evidence"
        errors = ht.validate_track_experiment(plan)
        self.assertTrue(any("native_trails_without_evidence" in e for e in errors))

    def test_vanilla_tracks_under_low_density_is_rejected(self):
        plan = valid_plan()
        plan["design_choice"] = "vanilla_tracks_under_near_zero_density"
        errors = ht.validate_track_experiment(plan)
        self.assertTrue(any("vanilla_tracks_under_near_zero_density" in e for e in errors))

    def test_missing_measurement_is_rejected(self):
        plan = valid_plan()
        del plan["measurements"]["streaming_conditions"]
        errors = ht.validate_track_experiment(plan)
        self.assertTrue(any("streaming_conditions" in e for e in errors))

    def test_unknown_design_is_rejected(self):
        plan = valid_plan()
        plan["design_choice"] = "scent_clouds"
        errors = ht.validate_track_experiment(plan)
        self.assertTrue(any("scent_clouds" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(ht.validate_track_experiment("tracks"))


def valid_probe_result():
    return {
        "measurements": {
            "trail_lifetime_after_stream_out": {
                "value": "180s",
                "conditions": "tagged buck, walked beyond range",
            },
            "trail_lifetime_after_explicit_deletion": {
                "value": "0s",
                "conditions": "tagged doe, deleted via native",
            },
            "tagged_animal_identity": {
                "value": "buck-1/doe-2",
                "conditions": "tagged before observation",
            },
            "streaming_conditions": {
                "value": "range + delete",
                "conditions": "same weather/time",
            },
        },
        "design_decision": "hidden_distant_target_ped",
    }


class ProbeResultTests(unittest.TestCase):
    def test_valid_probe_result_passes(self):
        self.assertEqual(ht.validate_probe_result(valid_probe_result()), [])

    def test_result_without_decision_passes(self):
        result = valid_probe_result()
        del result["design_decision"]
        self.assertEqual(ht.validate_probe_result(result), [])

    def test_missing_measurement_is_rejected(self):
        result = valid_probe_result()
        del result["measurements"]["trail_lifetime_after_stream_out"]
        errors = ht.validate_probe_result(result)
        self.assertTrue(any("trail_lifetime_after_stream_out" in e for e in errors))

    def test_measurement_without_conditions_is_rejected(self):
        result = valid_probe_result()
        del result["measurements"]["streaming_conditions"]["conditions"]
        errors = ht.validate_probe_result(result)
        self.assertTrue(any("conditions" in e for e in errors))

    def test_rejected_decision_is_rejected(self):
        result = valid_probe_result()
        result["design_decision"] = "vanilla_tracks_under_near_zero_density"
        errors = ht.validate_probe_result(result)
        self.assertTrue(any("rejected" in e for e in errors))

    def test_unknown_decision_is_rejected(self):
        result = valid_probe_result()
        result["design_decision"] = "scent_hounds"
        errors = ht.validate_probe_result(result)
        self.assertTrue(any("not one of the viable designs" in e for e in errors))

    def test_non_mapping_result_is_rejected(self):
        self.assertTrue(ht.validate_probe_result("trails last"))


if __name__ == "__main__":
    unittest.main()
