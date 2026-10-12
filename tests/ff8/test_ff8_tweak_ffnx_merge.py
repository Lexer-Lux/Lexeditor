"""Each FFNx.toml key is its own tweak merge unit: different keys compose."""
import json
from pathlib import Path
import tempfile
import unittest

from plugins.ff8 import tweak_mods


class TweakFfnxMergeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.library = self.root / "library"
        self.library.mkdir()

    def mod(self, name, code, order):
        root = self.library / name
        (root / "script").mkdir(parents=True)
        (root / "mod.json").write_text(json.dumps({
            "id": name, "name": name, "enabled": True, "order": order,
            "script": {"version": 1}}), encoding="utf-8")
        (root / "script/__init__.py").write_text("", encoding="utf-8")
        (root / "script/tweak.py").write_text(code, encoding="utf-8")
        (root / "settings.schema.json").write_text(json.dumps({}), encoding="utf-8")
        return root

    def build(self):
        return tweak_mods.build_enabled(
            self.project, self.library, self.root / "game", self.root / "baseline")

    def test_different_keys_compose(self):
        self.mod("a", "def build(settings, context):\n"
                      "    context.ffnx('enable_ff8_xp_bars', True)\n"
                      "    return {}\n", 0)
        self.mod("b", "def build(settings, context):\n"
                      "    context.ffnx('enable_ff8_hp_bars', True)\n"
                      "    return {}\n", 1)
        built = self.build()
        self.assertEqual(built["ffnx"], {"enable_ff8_xp_bars": True,
                                         "enable_ff8_hp_bars": True})
        self.assertEqual(built["ffnx_conflicts"], [])

    def test_disagreement_names_winner_and_claimants(self):
        self.mod("a", "def build(settings, context):\n"
                      "    context.ffnx('ff8_modern_controls_camera_speed', 1.0)\n"
                      "    return {}\n", 0)
        self.mod("b", "def build(settings, context):\n"
                      "    context.ffnx('ff8_modern_controls_camera_speed', 2.0)\n"
                      "    return {}\n", 1)
        built = self.build()
        self.assertEqual(built["ffnx"], {"ff8_modern_controls_camera_speed": 2.0})
        self.assertEqual(built["ffnx_conflicts"], [{
            "unit": "FFNx.toml:ff8_modern_controls_camera_speed",
            "key": "ff8_modern_controls_camera_speed",
            "winner": "b", "claimants": ["a", "b"]}])

    def test_agreement_is_not_a_conflict(self):
        code = ("def build(settings, context):\n"
                "    context.ffnx('enable_ff8_fast_start', True)\n"
                "    return {}\n")
        self.mod("a", code, 0)
        self.mod("b", code, 1)
        built = self.build()
        self.assertEqual(built["ffnx"], {"enable_ff8_fast_start": True})
        self.assertEqual(built["ffnx_conflicts"], [])


if __name__ == "__main__":
    unittest.main()
