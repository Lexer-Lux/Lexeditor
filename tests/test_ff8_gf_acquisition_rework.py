"""Contracts for the FF8 GF Acquisition Rework, GitHub issue #318."""
from pathlib import Path
import tempfile
import unittest

from games.ff8 import gameplay_settings
from games.ff8 import gf_acquisition_rework

ROOT = Path(__file__).resolve().parents[1]


class GfAcquisitionReworkTests(unittest.TestCase):
    def test_default_is_off_and_tweak_is_registered(self):
        self.assertFalse(gameplay_settings.DEFAULT_GF_ACQUISITION_REWORK)
        self.assertFalse(gf_acquisition_rework.DEFAULT_GF_ACQUISITION_REWORK)
        self.assertEqual(gf_acquisition_rework.TWEAK_NAME, "GF Acquisition Rework")
        self.assertIn("gfAcquisitionRework", gameplay_settings.ACCEPTED_TWEAKS)

    def test_load_defaults_and_forces_off(self):
        with tempfile.TemporaryDirectory(prefix="ff8-gf-acquisition-") as directory:
            project = Path(directory)
            defaults = gameplay_settings.load(project)
            self.assertIs(defaults["gfAcquisitionRework"], False)
            self.assertFalse(defaults["gfAcquisitionReworkAvailable"])
            self.assertIn("no proved battle-victory",
                          defaults["gfAcquisitionReworkBlocker"])
            gameplay_settings.settings_path(project).write_text(
                '{"gfAcquisitionRework": true}',
                encoding="utf-8",
            )
            # No proved hooks: a stored true never loads as enabled.
            self.assertIs(gameplay_settings.load(project)["gfAcquisitionRework"], False)

    def test_disabled_build_emits_no_acquisition_bytes(self):
        patch = gameplay_settings.build_hext(25, False)
        self.assertIn("GF Acquisition Rework is disabled", patch)
        self.assertNotIn("Tri-Point", patch)

    def test_save_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "no proved battle-victory"):
            gf_acquisition_rework.build_hext(True)

    def test_editor_exposes_approved_rule(self):
        editor = (ROOT / "games/ff8/boot.js").read_text(encoding="utf-8")
        self.assertIn('"aria-label":"GF Acquisition Rework"', editor)
        self.assertIn('row("GF ACQUISITION REWORK"', editor)
        self.assertIn("gfAcquisitionRework:state.data.settings.gfAcquisitionRework", editor)
        self.assertIn("instead of through Draw", editor)
        self.assertIn("disabling keeps acquired GFs", editor)

    def test_victory_awards_and_draw_filter(self):
        self.assertEqual(
            gf_acquisition_rework.apply_victory([], "Elvoret"), ["Siren"])
        self.assertEqual(
            gf_acquisition_rework.apply_victory(["Siren"], "Elvoret"), ["Siren"])
        kept = gf_acquisition_rework.filter_draw_entries([
            {"kind": "spell", "id": "Fire"},
            {"kind": "gf", "id": "Siren"},
        ])
        self.assertEqual([entry["id"] for entry in kept], ["Fire"])


if __name__ == "__main__":
    unittest.main()
