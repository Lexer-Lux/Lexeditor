"""Hermetic checks for the issue-228 bounty cap policy (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import bounty_cap_policy as bc


def valid_config():
    return {
        "build_fingerprint": "1491.50-short_update",
        "maxima": {"bayou": 60000, "grizzlies": 90000},
        "conversion": "1 config dollar = 1 bounty dollar",
        "applies_to": ("engine", "regional_clamp"),
        "on_disable": "preserve",
    }


class BountyCapPolicyTests(unittest.TestCase):
    def test_vanilla_reference_recorded(self):
        self.assertEqual(bc.vanilla_caps(), [30000, 50000, 150000])
        self.assertEqual(bc.NETWORK_CAP, -1)
        first = bc.vanilla_caps()
        first.append(1)
        self.assertEqual(bc.vanilla_caps(), [30000, 50000, 150000])

    def test_valid_config_passes(self):
        self.assertEqual(bc.validate_cap_policy(valid_config()), [])

    def test_missing_fingerprint_is_rejected(self):
        config = valid_config()
        config["build_fingerprint"] = ""
        errors = bc.validate_cap_policy(config)
        self.assertTrue(any("fail closed" in e for e in errors))

    def test_out_of_bounds_maximum_is_rejected(self):
        config = valid_config()
        config["maxima"]["bayou"] = 0
        errors = bc.validate_cap_policy(config)
        self.assertTrue(any("bayou" in e for e in errors))
        config["maxima"]["bayou"] = 2000000
        errors = bc.validate_cap_policy(config)
        self.assertTrue(any("bayou" in e for e in errors))

    def test_fractional_maximum_is_rejected(self):
        config = valid_config()
        config["maxima"]["bayou"] = 60000.5
        errors = bc.validate_cap_policy(config)
        self.assertTrue(any("whole dollars" in e for e in errors))

    def test_missing_conversion_is_rejected(self):
        config = valid_config()
        del config["conversion"]
        errors = bc.validate_cap_policy(config)
        self.assertTrue(any("conversion" in e for e in errors))

    def test_single_layer_application_is_rejected(self):
        config = valid_config()
        config["applies_to"] = ("engine",)
        errors = bc.validate_cap_policy(config)
        self.assertTrue(any("both the engine and the regional clamp" in e for e in errors))

    def test_zeroing_on_disable_is_rejected(self):
        config = valid_config()
        config["on_disable"] = "zero"
        errors = bc.validate_cap_policy(config)
        self.assertTrue(any("preserve existing bounties" in e for e in errors))

    def test_empty_maxima_is_rejected(self):
        config = valid_config()
        config["maxima"] = {}
        errors = bc.validate_cap_policy(config)
        self.assertTrue(any("at least one region" in e for e in errors))


def valid_enforcement_proof():
    return {
        "configured_maximum": 50000,
        "layers": {"engine": 50000, "regional_clamp": 50000},
        "pre_existing_bounties": "preserved",
    }


class EnforcementProofTests(unittest.TestCase):
    def test_valid_enforcement_proof_passes(self):
        self.assertEqual(bc.validate_enforcement_proof(valid_enforcement_proof()), [])

    def test_single_layer_clamp_is_rejected(self):
        proof = valid_enforcement_proof()
        proof["layers"]["regional_clamp"] = 150000
        errors = bc.validate_enforcement_proof(proof)
        self.assertTrue(any("regional_clamp" in e for e in errors))

    def test_zeroed_bounties_are_rejected(self):
        proof = valid_enforcement_proof()
        proof["pre_existing_bounties"] = "zeroed"
        errors = bc.validate_enforcement_proof(proof)
        self.assertTrue(any("preserved" in e for e in errors))

    def test_out_of_bounds_maximum_is_rejected(self):
        proof = valid_enforcement_proof()
        proof["configured_maximum"] = 2000000
        proof["layers"] = {"engine": 2000000, "regional_clamp": 2000000}
        errors = bc.validate_enforcement_proof(proof)
        self.assertTrue(any("1..1000000" in e for e in errors))

    def test_missing_layers_are_rejected(self):
        proof = valid_enforcement_proof()
        del proof["layers"]
        errors = bc.validate_enforcement_proof(proof)
        self.assertTrue(any("both clamp layers" in e for e in errors))

    def test_non_mapping_proof_is_rejected(self):
        self.assertTrue(bc.validate_enforcement_proof("cap works"))


if __name__ == "__main__":
    unittest.main()
