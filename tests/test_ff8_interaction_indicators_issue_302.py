"""Contracts for FF8 interaction/card-opponent indicators, GitHub #302."""
from pathlib import Path
import tempfile
import unittest

from plugins.ff8 import gameplay_settings

ROOT = Path(__file__).resolve().parents[1]


class InteractionIndicatorTests(unittest.TestCase):
    def test_default_is_off_and_tweak_is_registered(self):
        self.assertFalse(gameplay_settings.DEFAULT_INTERACTION_INDICATORS)
        self.assertIn("interactionIndicators", gameplay_settings.ACCEPTED_TWEAKS)

    def test_runtime_config_can_enable_then_restore_disabled(self):
        with tempfile.TemporaryDirectory(prefix="ff8-interaction-indicators-") as directory:
            config = Path(directory) / "FFNx.toml"
            config.write_text("preserve_me = 17\n", encoding="utf-8")
            common = dict(xp_bars=False, hp_bars=False, better_targeting=False)
            gameplay_settings._set_ffnx_runtime_tweaks(
                config, interaction_indicators=True, **common
            )
            enabled = config.read_text(encoding="utf-8")
            self.assertIn("preserve_me = 17", enabled)
            self.assertEqual(
                enabled.count("enable_ff8_interaction_indicators = true"), 1
            )

            gameplay_settings._set_ffnx_runtime_tweaks(
                config, interaction_indicators=False, **common
            )
            disabled = config.read_text(encoding="utf-8")
            self.assertIn("preserve_me = 17", disabled)
            self.assertNotIn("enable_ff8_interaction_indicators = true", disabled)
            self.assertEqual(
                disabled.count("enable_ff8_interaction_indicators = false"), 1
            )

    def test_editor_exposes_non_invasive_semantics(self):
        editor = (ROOT / "plugins/ff8/boot.js").read_text(encoding="utf-8")
        self.assertIn('"aria-label":"Interaction Indicators"', editor)
        self.assertIn('row("INTERACTION INDICATORS"', editor)
        self.assertIn("never presses a button", editor)

    def test_candidate_defaults_switch_off(self):
        prepare = (ROOT / "tools/prepare_ff8_native_build.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("enable_ff8_interaction_indicators = false", prepare)
        self.assertIn("lexeditor_ff8_interaction_indicators_draw();", prepare)


if __name__ == "__main__":
    unittest.main()
