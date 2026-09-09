from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_data import is_singleplayer_module, read_submodule, save_module_metadata


MODERN = '''<Module>
  <Name value="Modern Module" />
  <Id value="ModernModule" />
  <Version value="v1.0.0" />
  <ModuleCategory value="Singleplayer" />
  <ModuleType value="Community" />
  <DependedModules />
</Module>
'''


class BannerlordModernMetadataTests(unittest.TestCase):
    def test_modern_category_and_type_round_trip(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(MODERN, encoding="utf-8")

            module = read_submodule(path)
            self.assertEqual(module["moduleCategory"], "Singleplayer")
            self.assertEqual(module["moduleType"], "Community")
            self.assertFalse(module["singleplayer"])
            self.assertTrue(is_singleplayer_module(module))

            saved = save_module_metadata(
                path,
                {"moduleCategory": "Multiplayer", "moduleType": "OfficialOptional"},
            )
            self.assertEqual(saved["saved"], 2)
            self.assertEqual(saved["module"]["moduleCategory"], "Multiplayer")
            self.assertEqual(saved["module"]["moduleType"], "OfficialOptional")
            self.assertFalse(is_singleplayer_module(saved["module"]))
            self.assertTrue(Path(saved["backup"]).is_file())

    def test_modern_category_is_authoritative_over_legacy_flags(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(
                MODERN.replace(
                    '<ModuleCategory value="Singleplayer" />',
                    '<ModuleCategory value="Multiplayer" />\n  <SingleplayerModule value="true" />',
                ),
                encoding="utf-8",
            )
            module = read_submodule(path)
            self.assertTrue(module["singleplayer"])
            self.assertEqual(module["moduleCategory"], "Multiplayer")
            self.assertFalse(is_singleplayer_module(module))

    def test_legacy_flags_and_modern_default_remain_compatible(self):
        self.assertTrue(is_singleplayer_module({"moduleCategory": "", "singleplayer": True, "multiplayer": False}))
        self.assertFalse(is_singleplayer_module({"moduleCategory": "", "singleplayer": False, "multiplayer": True}))
        self.assertTrue(is_singleplayer_module({"moduleCategory": "", "singleplayer": False, "multiplayer": False}))

    def test_optional_modern_metadata_can_be_removed_without_creating_legacy_nodes(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(MODERN, encoding="utf-8")
            saved = save_module_metadata(path, {"moduleCategory": "", "moduleType": ""})
            self.assertEqual(saved["saved"], 2)
            self.assertEqual(saved["module"]["moduleCategory"], "")
            self.assertEqual(saved["module"]["moduleType"], "")
            rewritten = path.read_text(encoding="utf-8")
            self.assertNotIn("ModuleCategory", rewritten)
            self.assertNotIn("ModuleType", rewritten)

    def test_invalid_modern_metadata_enum_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(MODERN, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "moduleCategory must be one of"):
                save_module_metadata(path, {"moduleCategory": "SinglePlayerMaybe"})
            with self.assertRaisesRegex(ValueError, "moduleType must be one of"):
                save_module_metadata(path, {"moduleType": "Officialish"})


if __name__ == "__main__":
    unittest.main()
