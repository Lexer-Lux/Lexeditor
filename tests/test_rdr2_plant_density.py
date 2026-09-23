"""Hermetic checks for the issue-229 plant-density boundary (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import plant_density as pd


def valid_candidate():
    return {
        "mechanism": "spawn_table_thinning",
        "density_reduction": "30 percent fewer spawns",
        "pickability_proof": "pick every remaining spawn in the test region",
        "open_unknowns": ["engine placement research"],
    }


class PlantDensityTests(unittest.TestCase):
    def test_valid_candidate_passes(self):
        self.assertEqual(pd.validate_density_candidate(valid_candidate()), [])

    def test_scenario_only_disable_is_rejected(self):
        candidate = valid_candidate()
        candidate["mechanism"] = "scenario_point_disable_only"
        errors = pd.validate_density_candidate(candidate)
        self.assertTrue(any("stays rejected" in e for e in errors))

    def test_animal_multiplier_is_rejected(self):
        candidate = valid_candidate()
        candidate["mechanism"] = "animal_density_multiplier"
        errors = pd.validate_density_candidate(candidate)
        self.assertTrue(any("not plants" in e for e in errors))

    def test_missing_mechanism_is_rejected(self):
        candidate = valid_candidate()
        candidate["mechanism"] = ""
        errors = pd.validate_density_candidate(candidate)
        self.assertTrue(any("mechanism" in e for e in errors))

    def test_missing_pickability_proof_is_rejected(self):
        candidate = valid_candidate()
        candidate["pickability_proof"] = ""
        errors = pd.validate_density_candidate(candidate)
        self.assertTrue(any("pickable" in e for e in errors))

    def test_missing_reduction_is_rejected(self):
        candidate = valid_candidate()
        del candidate["density_reduction"]
        errors = pd.validate_density_candidate(candidate)
        self.assertTrue(any("density reduction" in e for e in errors))

    def test_non_mapping_candidate_is_rejected(self):
        self.assertTrue(pd.validate_density_candidate("fewer plants"))


def valid_field_survey():
    return {
        "mechanism": "placement_budget_scaling",
        "areas": [
            {"area": "heartlands-1", "plants_before": 120, "plants_after": 60},
            {"area": "heartlands-2", "plants_before": 90, "plants_after": 90},
        ],
        "pickability_spot_checks": [True, True, True],
    }


class FieldSurveyTests(unittest.TestCase):
    def test_valid_field_survey_passes(self):
        self.assertEqual(pd.validate_field_survey(valid_field_survey()), [])

    def test_no_reduction_is_rejected(self):
        survey = valid_field_survey()
        survey["areas"][0]["plants_after"] = 120
        errors = pd.validate_field_survey(survey)
        self.assertTrue(any("fewer plants" in e for e in errors))

    def test_failed_spot_check_is_rejected(self):
        survey = valid_field_survey()
        survey["pickability_spot_checks"][1] = False
        errors = pd.validate_field_survey(survey)
        self.assertTrue(any("unpickable" in e for e in errors))

    def test_rejected_mechanism_is_rejected(self):
        survey = valid_field_survey()
        survey["mechanism"] = "scenario_point_disable_only"
        errors = pd.validate_field_survey(survey)
        self.assertTrue(any("stays rejected" in e for e in errors))

    def test_missing_counts_are_rejected(self):
        survey = valid_field_survey()
        del survey["areas"][0]["plants_after"]
        errors = pd.validate_field_survey(survey)
        self.assertTrue(any("before/after plant counts" in e for e in errors))

    def test_empty_areas_are_rejected(self):
        survey = valid_field_survey()
        survey["areas"] = []
        self.assertTrue(pd.validate_field_survey(survey))

    def test_non_mapping_survey_is_rejected(self):
        self.assertTrue(pd.validate_field_survey("fewer plants"))


if __name__ == "__main__":
    unittest.main()
