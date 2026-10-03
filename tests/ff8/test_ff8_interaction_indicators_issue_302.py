"""Contracts for FF8 interaction/card-opponent indicators, GitHub #302.

Interaction Indicators is a driver-only tweak mod: enabling it asks for
enable_ff8_interaction_indicators, and the switch is written off again when
no enabled mod asks for it. A fixture library stands in for the reader's.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest

from core import script_mods
from plugins.ff8 import gameplay_settings, paths, tweak_mods

ROOT = Path(__file__).resolve().parents[2]
KEY = "enable_ff8_interaction_indicators"
DRIVER_TWEAK = '''
def build(settings, context):
    context.need_driver()
    context.ffnx(%r, True)
    return {}
'''


class InteractionIndicatorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ff8-interaction-indicators-")
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        previous = os.environ.get(script_mods.TRUST_ENV)
        os.environ[script_mods.TRUST_ENV] = str(self.temp / "trust.json")
        self.addCleanup(lambda: os.environ.pop(script_mods.TRUST_ENV, None) if previous is None
                        else os.environ.__setitem__(script_mods.TRUST_ENV, previous))
        self.project, self.game = self.temp / "project", self.temp / "game"
        self.library = self.project / ".lexeditor-mods"
        self.game.mkdir()
        self.mod = self.library / "Interaction Indicators"
        (self.mod / "script").mkdir(parents=True)
        (self.mod / "script" / "__init__.py").write_text("", encoding="utf-8")
        (self.mod / "script" / "tweak.py").write_text(DRIVER_TWEAK % KEY, encoding="utf-8")
        (self.mod / "settings.schema.json").write_text(json.dumps({
            "title": "INTERACTION INDICATORS", "needsDriver": True, "fields": [],
            "help": "Shows a fixed HUD cue when the field interaction selector has a target. "
                    "It never presses a button or starts the interaction for you."}), encoding="utf-8")
        self._set_enabled(False)
        script_mods.set_trusted(self.mod, True)

    def _set_enabled(self, enabled):
        (self.mod / "mod.json").write_text(json.dumps(
            {"id": "interaction-indicators", "name": "Interaction Indicators", "order": 405,
             "enabled": enabled, "script": {"version": 1}}), encoding="utf-8")

    def _write_config(self, config):
        built = tweak_mods.build_enabled(self.project, self.library, self.game, paths.BASELINE_ROOT)
        gameplay_settings._set_ffnx_keys(config, {**gameplay_settings.FFNX_DEFAULTS, **built["ffnx"]})
        return built

    def test_default_is_off_and_switch_is_managed(self):
        self.assertIs(gameplay_settings.FFNX_DEFAULTS[KEY], False)
        row = next(row for row in gameplay_settings.load(self.project, self.game)["tweaks"]
                   if row["id"] == "interaction-indicators")
        self.assertIs(row["enabled"], False)

    def test_runtime_config_can_enable_then_restore_disabled(self):
        config = self.game / "FFNx.toml"
        config.write_text("preserve_me = 17\n", encoding="utf-8")
        self._set_enabled(True)
        self.assertTrue(self._write_config(config)["driver"])
        enabled = config.read_text(encoding="utf-8")
        self.assertIn("preserve_me = 17", enabled)
        self.assertEqual(enabled.count(f"{KEY} = true"), 1)

        self._set_enabled(False)
        self.assertFalse(self._write_config(config)["driver"])
        disabled = config.read_text(encoding="utf-8")
        self.assertIn("preserve_me = 17", disabled)
        self.assertNotIn(f"{KEY} = true", disabled)
        self.assertEqual(disabled.count(f"{KEY} = false"), 1)

    def test_editor_exposes_non_invasive_semantics(self):
        editor = (ROOT / "plugins/ff8/boot.js").read_text(encoding="utf-8")
        self.assertIn('LexeditorUI.tweakModPanels({rows:settings.tweaks||[]', editor)
        row = next(row for row in gameplay_settings.load(self.project, self.game)["tweaks"]
                   if row["id"] == "interaction-indicators")
        self.assertIn("never presses a button", row["schema"]["help"])
        self.assertIs(row["schema"]["needsDriver"], True)
        mod = Path(paths.MODS_ROOT) / "Interaction Indicators"
        if not script_mods.is_script_mod(mod):
            self.skipTest(f"The Interaction Indicators tweak mod is not installed in {paths.MODS_ROOT}")
        schema = script_mods.schema(mod)
        self.assertEqual(schema["title"], "INTERACTION INDICATORS")
        self.assertIn("never presses a button", schema["help"])
        self.assertIn(f"'{KEY}', True", (mod / "script/tweak.py").read_text(encoding="utf-8"))

    def test_candidate_defaults_switch_off(self):
        prepare = (ROOT / "tools/prepare_ff8_native_build.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("enable_ff8_interaction_indicators = false", prepare)
        self.assertIn("lexeditor_ff8_interaction_indicators_draw();", prepare)


if __name__ == "__main__":
    unittest.main()
