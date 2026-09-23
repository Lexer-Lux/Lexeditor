from pathlib import Path
import tempfile
import unittest

from games.bannerlord.game_launch import module_load_order


class BannerlordAmbiguousCategoryTests(unittest.TestCase):
    def test_module_without_category_or_legacy_sp_flag_is_not_launchable_as_singleplayer(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            module = game / "Modules" / "Ambiguous"
            module.mkdir(parents=True)
            (module / "SubModule.xml").write_text(
                '<Module><Name value="Ambiguous" /><Id value="Ambiguous" /><Version value="v1.0.0" /></Module>',
                encoding="utf-8",
            )
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="Ambiguous" /></Module>', encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "not declared as a single-player module"):
                module_load_order(game, workspace)


if __name__ == "__main__":
    unittest.main()
