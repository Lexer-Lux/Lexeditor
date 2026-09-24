"""Source guards for the issue-108 camera profile boundary (no game, no build).

Issue 108 keeps independent standing, crouched, aiming, horseback, vehicle,
and prone profiles. Continuous vertical positioning is unsupported by the
camera path, so LOW/NORMAL stays binary, and developer mode must gate
editing only, never the application of saved presets. These tests lock the
source facts that carry that boundary: the profile set, the binary low
framing, and the dev-mode gate around authoring input. Vehicle-height
research and the open shoulder/transition defects still need the game.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = (ROOT / "plugins" / "rdr2" / "native_runtime" / "GameplayTweaks"
          / "modules" / "gameplay_camera.cpp")


class CameraBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MODULE.read_text(encoding="utf-8")

    def test_profile_set_covers_required_modes(self):
        for mode in ("Standing", "Crouched", "Prone", "Horseback",
                     "Vehicle", "Aim", "CrouchedAim"):
            self.assertIn(mode, self.source)

    def test_framing_stays_binary_low_normal(self):
        self.assertIn("bool low", self.source)
        self.assertNotIn("vertical slider", self.source.lower())

    def test_authoring_input_is_dev_mode_gated(self):
        self.assertIn("no camera authoring input is", self.source)
        self.assertIn("no profile can be persisted", self.source)
        self.assertRegex(
            self.source,
            r"if\s*\(\s*editorActive\s*&&[^\n]*\)\s*\n\s*calibrateGameplayCamera",
        )

    def test_profile_application_is_not_authoring(self):
        # Saved presets apply through the per-frame profile path, which is a
        # separate statement from the gated calibrate call above: gating the
        # calibrate call must not remove the submit path.
        self.assertIn("submittedHorizontal", self.source)
        calibrate = self.source.count("calibrateGameplayCamera(profile, now)")
        self.assertEqual(calibrate, 1)


if __name__ == "__main__":
    unittest.main()
