"""Contracts for FF8 Better HP Colors, GitHub #481."""
from pathlib import Path
import tempfile, unittest
from plugins.ff8 import gameplay_settings
ROOT=Path(__file__).resolve().parents[2]
class BetterHpColorsTests(unittest.TestCase):
    def test_default_is_off_and_tweak_is_registered(self):
        self.assertFalse(gameplay_settings.DEFAULT_BETTER_HP_COLORS)
        self.assertIn("betterHpColors", gameplay_settings.ACCEPTED_TWEAKS)
    def test_runtime_config_can_enable_then_restore_vanilla(self):
        with tempfile.TemporaryDirectory(prefix="ff8-hp-colors-") as d:
            p=Path(d)/"FFNx.toml";p.write_text("preserve_me = 17\n",encoding="utf-8")
            common=dict(xp_bars=False,hp_bars=False,better_targeting=False)
            gameplay_settings._set_ffnx_runtime_tweaks(p,better_hp_colors=True,**common)
            enabled=p.read_text();self.assertIn("preserve_me = 17",enabled)
            self.assertEqual(enabled.count("enable_ff8_better_hp_colors = true"),1)
            gameplay_settings._set_ffnx_runtime_tweaks(p,better_hp_colors=False,**common)
            disabled=p.read_text();self.assertIn("preserve_me = 17",disabled)
            self.assertNotIn("enable_ff8_better_hp_colors = true",disabled)
            self.assertEqual(disabled.count("enable_ff8_better_hp_colors = false"),1)
    def test_editor_exposes_control_and_semantics(self):
        editor=(ROOT/"plugins/ff8/boot.js").read_text()
        self.assertIn('"aria-label":"Better HP Colors"',editor)
        self.assertIn('row("BETTER HP COLORS"',editor)
        for phrase in ("white at full HP","yellow at 50%","orange at 25%","KO"):self.assertIn(phrase,editor)
    def test_merged_toggles_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'FFNx.toml'
            config.write_text('',encoding='utf-8')
            for hp,indicator in ((True,True),(False,True),(True,False),(False,False)):
                gameplay_settings._set_ffnx_runtime_tweaks(config,xp_bars=False,hp_bars=False,
                    better_targeting=False,better_hp_colors=hp,interaction_indicators=indicator)
                data=config.read_text()
                self.assertEqual(data.count(f'enable_ff8_better_hp_colors = {str(hp).lower()}'),1)
                self.assertEqual(data.count(f'enable_ff8_interaction_indicators = {str(indicator).lower()}'),1)
    def test_candidate_default_and_disable_dispatch(self):
        prepare=(ROOT/"tools/prepare_ff8_native_build.py").read_text()
        self.assertIn("enable_ff8_better_hp_colors = false",prepare)
        self.assertIn("lexeditor_ff8_hp_colors_requested() ? lexeditor_ff8_hp_colors_draw_paletted2D : common_draw_paletted2D",prepare)
        self.assertNotIn("enable_ff8_better_hp_colors ? lexeditor",prepare)
if __name__=="__main__":unittest.main()
