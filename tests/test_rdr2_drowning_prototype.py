"""Hermetic checks for the issue-171 drowning prototype shape (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import drowning_prototype as dp


def valid_plan():
    return {
        "approach": "engine_owned_drowning_time",
        "elements": {
            "irreversible_latch_at_zero_stamina": True,
            "controls_disabled": True,
            "short_struggle_submerge_presentation": True,
            "no_rescue_window": True,
            "no_hud_warning": True,
            "unchanged_death_aftermath": True,
        },
        "fall_through": {
            "shallow_water": "immediate_death",
            "ragdoll": "immediate_death",
            "unsafe_first_person": "immediate_death",
            "mission_forbids_takeover": "immediate_death",
            "clip_refused_control": "immediate_death",
        },
        "recovery_checks": ["shallow entry", "deep entry", "mission active"],
    }


class DrowningPrototypeTests(unittest.TestCase):
    def test_required_shape_recorded(self):
        self.assertIn("no_rescue_window", dp.required_elements())
        self.assertIn("no_hud_warning", dp.required_elements())
        self.assertIn("clip_refused_control", dp.fall_through_conditions())

    def test_valid_plan_passes(self):
        self.assertEqual(dp.validate_drowning_plan(valid_plan()), [])

    def test_zero_second_proposal_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "zero_second_instant_kill"
        errors = dp.validate_drowning_plan(plan)
        self.assertTrue(any("zero_second" in e for e in errors))

    def test_trough_animation_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "trough_animation_reuse"
        errors = dp.validate_drowning_plan(plan)
        self.assertTrue(any("trough_animation" in e for e in errors))

    def test_rescue_window_is_rejected(self):
        plan = valid_plan()
        plan["elements"]["no_rescue_window"] = False
        errors = dp.validate_drowning_plan(plan)
        self.assertTrue(any("no_rescue_window" in e for e in errors))

    def test_hud_warning_is_rejected(self):
        plan = valid_plan()
        plan["elements"]["no_hud_warning"] = False
        errors = dp.validate_drowning_plan(plan)
        self.assertTrue(any("no_hud_warning" in e for e in errors))

    def test_missing_fall_through_is_rejected(self):
        plan = valid_plan()
        del plan["fall_through"]["ragdoll"]
        errors = dp.validate_drowning_plan(plan)
        self.assertTrue(any("ragdoll" in e for e in errors))

    def test_missing_recovery_checks_is_rejected(self):
        plan = valid_plan()
        plan["recovery_checks"] = []
        errors = dp.validate_drowning_plan(plan)
        self.assertTrue(any("recovery checks" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(dp.validate_drowning_plan("swim"))


def valid_session_script():
    return {
        "recovery_checks": ["shore exit bound", "mission state clean"],
        "matrix": {
            "deep_water": {"expected": "presentation_attempt"},
            "shallow_water": {"expected": "immediate_death"},
            "current": {"expected": "presentation_attempt"},
            "first_person": {"expected": "presentation_attempt"},
            "ragdoll": {"expected": "immediate_death"},
            "shore_edge": {"expected": "presentation_attempt"},
            "active_mission": {"expected": "immediate_death"},
        },
    }


class SessionScriptTests(unittest.TestCase):
    def test_valid_session_script_passes(self):
        self.assertEqual(dp.validate_session_script(valid_session_script()), [])

    def test_missing_condition_is_rejected(self):
        script = valid_session_script()
        del script["matrix"]["shore_edge"]
        errors = dp.validate_session_script(script)
        self.assertTrue(any("shore_edge" in e for e in errors))

    def test_missing_recovery_checks_is_rejected(self):
        script = valid_session_script()
        script["recovery_checks"] = []
        errors = dp.validate_session_script(script)
        self.assertTrue(any("recovery checks" in e for e in errors))

    def test_shallow_water_must_expect_immediate_death(self):
        script = valid_session_script()
        script["matrix"]["shallow_water"]["expected"] = "presentation_attempt"
        errors = dp.validate_session_script(script)
        self.assertTrue(any("shallow_water" in e for e in errors))

    def test_ragdoll_must_expect_immediate_death(self):
        script = valid_session_script()
        script["matrix"]["ragdoll"]["expected"] = "presentation_attempt"
        errors = dp.validate_session_script(script)
        self.assertTrue(any("ragdoll" in e for e in errors))

    def test_unknown_outcome_is_rejected(self):
        script = valid_session_script()
        script["matrix"]["current"]["expected"] = "maybe struggle"
        errors = dp.validate_session_script(script)
        self.assertTrue(any("expected outcome" in e for e in errors))

    def test_non_mapping_script_is_rejected(self):
        self.assertTrue(dp.validate_session_script("swim test"))


if __name__ == "__main__":
    unittest.main()
