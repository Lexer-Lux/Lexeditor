"""Contracts for FF8 Better HP Colors, GitHub #481.

Better HP Colors is a driver-only tweak mod: enabling it asks for
enable_ff8_better_hp_colors, and every driver switch no enabled mod asks for
is written off. The fixture library below stands in for the reader's library.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest

from core import script_mods
from plugins.ff8 import gameplay_settings, paths, tweak_mods

ROOT = Path(__file__).resolve().parents[2]
DRIVER_TWEAK = '''
def build(settings, context):
    context.need_driver()
    context.ffnx(%r, True)
    return {}
'''
HELP = ("Smoothly blends living HP numbers from white at full HP through yellow at 50% and orange "
        "at 25% toward red near zero. KO keeps FF8's vanilla display.")


class FixtureLibrary:
    """A temporary project whose own .lexeditor-mods holds driver tweak mods."""

    def __enter__(self):
        self._temp = tempfile.TemporaryDirectory(prefix="ff8-hp-colors-")
        temp = Path(self._temp.name)
        self._trust = os.environ.get(script_mods.TRUST_ENV)
        os.environ[script_mods.TRUST_ENV] = str(temp / "trust.json")
        self.project, self.game = temp / "project", temp / "game"
        self.library = self.project / ".lexeditor-mods"
        self.game.mkdir()
        self.library.mkdir(parents=True)
        self.roots = {}
        return self

    def add(self, mod_id, name, ffnx_key, help_text=""):
        root = self.library / name
        (root / "script").mkdir(parents=True)
        (root / "script" / "__init__.py").write_text("", encoding="utf-8")
        (root / "script" / "tweak.py").write_text(DRIVER_TWEAK % ffnx_key, encoding="utf-8")
        (root / "settings.schema.json").write_text(json.dumps(
            {"title": name.upper(), "help": help_text, "needsDriver": True, "fields": []}), encoding="utf-8")
        (root / "mod.json").write_text(json.dumps(
            {"id": mod_id, "name": name, "order": 400 + len(self.roots), "enabled": False,
             "script": {"version": 1}}), encoding="utf-8")
        script_mods.set_trusted(root, True)
        self.roots[mod_id] = root

    def enable(self, **switches):
        for mod_id, on in switches.items():
            path = self.roots[mod_id] / "mod.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["enabled"] = on
            path.write_text(json.dumps(data), encoding="utf-8")

    def write_config(self, config):
        """What gameplay_settings.save writes into FFNx.toml for these switches."""
        built = tweak_mods.build_enabled(self.project, self.library, self.game, paths.BASELINE_ROOT)
        gameplay_settings._set_ffnx_keys(config, {**gameplay_settings.FFNX_DEFAULTS, **built["ffnx"]})
        return built

    def __exit__(self, *exc):
        if self._trust is None:
            os.environ.pop(script_mods.TRUST_ENV, None)
        else:
            os.environ[script_mods.TRUST_ENV] = self._trust
        self._temp.cleanup()


class BetterHpColorsTests(unittest.TestCase):
    def test_default_is_off_and_switch_is_managed(self):
        self.assertIs(gameplay_settings.FFNX_DEFAULTS["enable_ff8_better_hp_colors"], False)

    def test_runtime_config_can_enable_then_restore_vanilla(self):
        with FixtureLibrary() as fixture:
            fixture.add("better-hp-colors", "Better HP Colors", "enable_ff8_better_hp_colors", HELP)
            p = fixture.game / "FFNx.toml"
            p.write_text("preserve_me = 17\n", encoding="utf-8")
            fixture.enable(**{"better-hp-colors": True})
            built = fixture.write_config(p)
            self.assertTrue(built["driver"])
            enabled = p.read_text(encoding="utf-8")
            self.assertIn("preserve_me = 17", enabled)
            self.assertEqual(enabled.count("enable_ff8_better_hp_colors = true"), 1)
            fixture.enable(**{"better-hp-colors": False})
            fixture.write_config(p)
            disabled = p.read_text(encoding="utf-8")
            self.assertIn("preserve_me = 17", disabled)
            self.assertNotIn("enable_ff8_better_hp_colors = true", disabled)
            self.assertEqual(disabled.count("enable_ff8_better_hp_colors = false"), 1)

    def test_editor_exposes_control_and_semantics(self):
        # The Tweaks page draws every tweak mod from its schema: the switch is
        # labelled with the mod's name and the help bubble is the schema help.
        editor = (ROOT / "plugins/ff8/boot.js").read_text(encoding="utf-8")
        self.assertIn('"aria-label":row.name', editor)
        self.assertIn("panel(schema.title||row.name.toUpperCase(),schema.help,toggle,body,blocker)", editor)
        with FixtureLibrary() as fixture:
            fixture.add("better-hp-colors", "Better HP Colors", "enable_ff8_better_hp_colors", HELP)
            row = next(row for row in gameplay_settings.load(fixture.project, fixture.game)["tweaks"]
                       if row["id"] == "better-hp-colors")
            self.assertEqual((row["name"], row["schema"]["title"]), ("Better HP Colors", "BETTER HP COLORS"))
            self.assertIs(row["schema"]["needsDriver"], True)

    def test_library_mod_semantics(self):
        mod = Path(paths.MODS_ROOT) / "Better HP Colors"
        if not script_mods.is_script_mod(mod):
            self.skipTest(f"The Better HP Colors tweak mod is not installed in {paths.MODS_ROOT}")
        schema = script_mods.schema(mod)
        self.assertEqual(schema["title"], "BETTER HP COLORS")
        for phrase in ("white at full HP", "yellow at 50%", "orange at 25%", "KO"):
            self.assertIn(phrase, schema["help"])
        self.assertIn("'enable_ff8_better_hp_colors', True", (mod / "script/tweak.py").read_text(encoding="utf-8"))

    def test_merged_toggles_are_independent(self):
        with FixtureLibrary() as fixture:
            fixture.add("better-hp-colors", "Better HP Colors", "enable_ff8_better_hp_colors")
            fixture.add("interaction-indicators", "Interaction Indicators", "enable_ff8_interaction_indicators")
            config = fixture.game / "FFNx.toml"
            config.write_text("", encoding="utf-8")
            for hp, indicator in ((True, True), (False, True), (True, False), (False, False)):
                fixture.enable(**{"better-hp-colors": hp, "interaction-indicators": indicator})
                fixture.write_config(config)
                data = config.read_text(encoding="utf-8")
                self.assertEqual(data.count(f"enable_ff8_better_hp_colors = {str(hp).lower()}"), 1)
                self.assertEqual(data.count(f"enable_ff8_interaction_indicators = {str(indicator).lower()}"), 1)

    def test_candidate_default_and_disable_dispatch(self):
        prepare = (ROOT / "tools/prepare_ff8_native_build.py").read_text(encoding="utf-8")
        self.assertIn("enable_ff8_better_hp_colors = false", prepare)
        self.assertIn("lexeditor_ff8_hp_colors_requested() ? lexeditor_ff8_hp_colors_draw_paletted2D : common_draw_paletted2D", prepare)
        self.assertNotIn("enable_ff8_better_hp_colors ? lexeditor", prepare)


if __name__ == "__main__":
    unittest.main()
