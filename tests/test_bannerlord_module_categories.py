from pathlib import Path
import tempfile
import unittest

from games.bannerlord.game_launch import module_load_order
from games.bannerlord.module_data import is_singleplayer_module, read_submodule, save_module


class BannerlordModuleCategoryTests(unittest.TestCase):
    def test_singleplayer_optional_is_singleplayer_and_round_trips(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(
                '<Module><Id value="Example" /><ModuleCategory value="SingleplayerOptional" /></Module>',
                encoding="utf-8",
            )
            module = read_submodule(path)
            self.assertTrue(is_singleplayer_module(module))
            result = save_module(path, {"metadata": {"moduleCategory": "SingleplayerOptional"}})
            self.assertEqual(result["module"]["moduleCategory"], "SingleplayerOptional")

    def test_server_optional_is_not_singleplayer_and_round_trips(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(
                '<Module><Id value="Example" /><ModuleCategory value="ServerOptional" /></Module>',
                encoding="utf-8",
            )
            module = read_submodule(path)
            self.assertFalse(is_singleplayer_module(module))
            result = save_module(path, {"metadata": {"moduleCategory": "ServerOptional"}})
            self.assertEqual(result["module"]["moduleCategory"], "ServerOptional")

    def test_play_accepts_singleplayer_optional_without_legacy_flag(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            module = game / "Modules" / "OptionalSingleplayer"
            module.mkdir(parents=True)
            (module / "SubModule.xml").write_text(
                '''<Module>
  <Name value="Optional Singleplayer" />
  <Id value="OptionalSingleplayer" />
  <Version value="v1.0.0" />
  <ModuleCategory value="SingleplayerOptional" />
</Module>''',
                encoding="utf-8",
            )
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="OptionalSingleplayer" /></Module>', encoding="utf-8"
            )
            self.assertEqual(module_load_order(game, workspace), ["OptionalSingleplayer"])


if __name__ == "__main__":
    unittest.main()
