"""Headless checks for the shared Unreal config editor and catalogue."""
from pathlib import Path
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unreal_config
from unreal_config import (
    ConfigError,
    ExternalEditError,
    apply_settings,
    catalogue,
    discover_config_file,
    game_definition,
    refresh_snapshot,
    reset_all,
    settings_for_game,
    status,
    use_game_default,
)


class CatalogueTests(unittest.TestCase):
    def test_catalogue_has_useful_set_with_help(self):
        entries = catalogue()
        self.assertGreaterEqual(len(entries), 10)
        for entry in entries:
            self.assertTrue(entry["name"], entry["key"])
            self.assertTrue(entry["description"], entry["key"])
            self.assertIn(entry["type"], ("int", "float", "choice"))
            if entry["type"] == "choice":
                self.assertGreaterEqual(len(entry["choices"] or []), 2)
            else:
                self.assertIsNotNone(entry["minimum"])
                self.assertIsNotNone(entry["maximum"])

    def test_evidence_tiers_stay_honest(self):
        for entry in catalogue():
            for game_id, evidence in entry["verification"].items():
                self.assertEqual(
                    set(evidence), {"defined", "accepted", "demonstrated", "tested_version"})
                if evidence["demonstrated"]:
                    self.assertTrue(evidence["tested_version"], entry["key"])

    def test_both_games_registered_with_locations(self):
        for game_id in ("ff7r", "ff7r2"):
            definition = game_definition(game_id)
            self.assertTrue(definition["config_candidates"])
            self.assertTrue(definition["env_override"])
            self.assertTrue(definition["supported"])
        self.assertFalse(game_definition("ff7r2")["config_verified"])

    def test_ff7r_markers_match_legacy_module(self):
        from plugins.ff7r import graphics_tweaks
        self.assertEqual(unreal_config.FF7R_MANAGED_BEGIN, graphics_tweaks.MANAGED_BEGIN)
        self.assertEqual(unreal_config.FF7R_MANAGED_END, graphics_tweaks.MANAGED_END)

    def test_normal_view_excludes_unverified(self):
        normal = settings_for_game("ff7r2")
        advanced = settings_for_game("ff7r2", include_unverified=True)
        self.assertGreater(len(advanced), len(normal))
        for item in advanced:
            if item not in normal:
                self.assertIn("unverified_note", item)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.project = root / "project"
        self.ini = root / "Engine.ini"
        os.environ["LEXEDITOR_FF7R2_ENGINE_INI"] = str(self.ini)
        os.environ["LEXEDITOR_FF7R_ENGINE_INI"] = str(root / "ff7r.ini")
        self.addCleanup(os.environ.pop, "LEXEDITOR_FF7R2_ENGINE_INI")
        self.addCleanup(os.environ.pop, "LEXEDITOR_FF7R_ENGINE_INI")

    def test_apply_status_default_reset_round_trip(self):
        self.ini.write_bytes(b"[SystemSettings]\nr.BloomQuality=5\n")
        report = apply_settings("ff7r2", self.project, {"r.BloomQuality": 3})
        self.assertEqual(report["overrides"], {"r.BloomQuality": "3"})
        self.assertEqual(report["observed"], {"r.BloomQuality": "5"})
        self.assertTrue(report["managedEffectiveAtEnd"])
        report = use_game_default("ff7r2", self.project, "r.BloomQuality")
        self.assertFalse(report["managedPresent"])
        result = reset_all("ff7r2", self.project)
        self.assertIn("r.BloomQuality=5", self.ini.read_bytes().decode("utf-8"))
        self.assertEqual(result["restored"], [])

    def test_external_change_blocks_save_until_reviewed(self):
        apply_settings("ff7r2", self.project, {"r.BloomQuality": 3})
        before = self.ini.read_bytes()
        self.ini.write_bytes(before + b"; outside edit\n")
        with self.assertRaises(ExternalEditError):
            apply_settings("ff7r2", self.project, {"r.MotionBlurQuality": 0})
        self.assertEqual(self.ini.read_bytes(), before + b"; outside edit\n")
        self.assertTrue(status("ff7r2", self.project)["externalChange"])
        reviewed = refresh_snapshot("ff7r2", self.project)
        self.assertFalse(reviewed["externalChange"])

    def test_discovery_finds_env_override_file(self):
        self.ini.write_bytes(b"[SystemSettings]\n")
        self.assertEqual(discover_config_file("ff7r2"), self.ini)

    def test_bad_values_rejected(self):
        with self.assertRaises(ConfigError):
            apply_settings("ff7r2", self.project, {"r.MotionBlurQuality": 99})
        with self.assertRaises(ConfigError):
            apply_settings("ff7r", self.project, {"r.EyeAdaptationQuality": 0})


if __name__ == "__main__":
    unittest.main()
