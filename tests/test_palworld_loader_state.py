from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.palworld.loader_state import LoaderSettingsError, parse_settings_bytes, status


class PalworldLoaderStateTests(unittest.TestCase):
    def test_repeated_active_mod_entries_and_global_state(self):
        parsed = parse_settings_bytes(b"""
; Pocketpair loader config fixture
[PalModSettings]
bGlobalEnableMod=True
WorkshopRootDir=C:\\SteamLibrary\\steamapps\\workshop\\content\\1623730
ActiveModList=FirstMod
ActiveModList=TargetMod
ActiveModList=ThirdMod
""")
        self.assertIs(True, parsed["globalEnabled"])
        self.assertEqual(
            r"C:\SteamLibrary\steamapps\workshop\content\1623730",
            parsed["workshopRootDir"],
        )
        self.assertEqual(["FirstMod", "TargetMod", "ThirdMod"], parsed["activeModList"])

    def test_package_is_active_only_when_listed_and_globally_enabled(self):
        with tempfile.TemporaryDirectory() as temp_name:
            game = Path(temp_name) / "Palworld"
            settings = game / "Mods" / "PalModSettings.ini"
            settings.parent.mkdir(parents=True)
            settings.write_text(
                "[PalModSettings]\n"
                "bGlobalEnableMod=True\n"
                "WorkshopRootDir=C:\\Workshop\\1623730\n"
                "ActiveModList=TargetMod\n",
                encoding="utf-8",
            )
            enabled = status(game, "TargetMod")
            self.assertTrue(enabled["available"])
            self.assertTrue(enabled["listed"])
            self.assertTrue(enabled["active"])

            settings.write_text(
                "[PalModSettings]\n"
                "bGlobalEnableMod=False\n"
                "ActiveModList=TargetMod\n",
                encoding="utf-8",
            )
            disabled = status(game, "TargetMod")
            self.assertTrue(disabled["listed"])
            self.assertFalse(disabled["active"])
            self.assertIn("globally disabled", disabled["reason"])

    def test_unlisted_package_is_not_active(self):
        with tempfile.TemporaryDirectory() as temp_name:
            game = Path(temp_name) / "Palworld"
            settings = game / "Mods" / "PalModSettings.ini"
            settings.parent.mkdir(parents=True)
            settings.write_text(
                "[PalModSettings]\n"
                "bGlobalEnableMod=True\n"
                "ActiveModList=OtherMod\n",
                encoding="utf-8",
            )
            state = status(game, "TargetMod")
            self.assertFalse(state["listed"])
            self.assertFalse(state["active"])
            self.assertIn("not listed", state["reason"])

    def test_invalid_global_enable_value_fails_closed(self):
        with self.assertRaises(LoaderSettingsError):
            parse_settings_bytes(b"[PalModSettings]\nbGlobalEnableMod=Maybe\n")

    def test_missing_settings_file_is_reported_without_creating_it(self):
        with tempfile.TemporaryDirectory() as temp_name:
            game = Path(temp_name) / "Palworld"
            game.mkdir()
            state = status(game, "TargetMod")
            self.assertFalse(state["available"])
            self.assertFalse(state["active"])
            self.assertIn("does not exist", state["reason"])
            self.assertFalse((game / "Mods" / "PalModSettings.ini").exists())

    def test_other_ini_sections_are_ignored(self):
        parsed = parse_settings_bytes(
            b"[Other]\nActiveModList=Wrong\n"
            b"[PalModSettings]\nActiveModList=Right\n"
            b"[Another]\nbGlobalEnableMod=True\n"
        )
        self.assertEqual(["Right"], parsed["activeModList"])
        self.assertIsNone(parsed["globalEnabled"])


if __name__ == "__main__":
    unittest.main()
