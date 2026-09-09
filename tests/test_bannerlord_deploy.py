from pathlib import Path
import json
import tempfile
import unittest

from games.bannerlord.deploy_data import deploy_target, sync_project_assets


PROJECT_SUBMODULE = '''<Module>
  <Name value="Lexer Skill Tweaks" />
  <Id value="LexerSkillTweaks" />
  <Version value="v2.0.0" />
</Module>
'''

OLD_SUBMODULE = '''<Module>
  <Name value="Lexer Skill Tweaks" />
  <Id value="LexerSkillTweaks" />
  <Version value="v1.0.0" />
</Module>
'''


class BannerlordDeployTests(unittest.TestCase):
    def fixture(self, installed=True):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        project = root / "project"
        game = root / "game"
        project.mkdir()
        executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"")
        (game / "Modules").mkdir()
        (project / "SubModule.xml").write_text(PROJECT_SUBMODULE, encoding="utf-8")
        (project / "GUI" / "Prefabs").mkdir(parents=True)
        (project / "GUI" / "Prefabs" / "Test.xml").write_text("<Prefab><Window /></Prefab>\n", encoding="utf-8")
        (project / "ModuleData").mkdir()
        (project / "ModuleData" / "items.xml").write_text("<Items><Item id=\"new\" /></Items>\n", encoding="utf-8")
        (project / "ModuleData" / "custom_skill_effects.json").write_text(json.dumps({"source": {"low": 1, "high": 2}}), encoding="utf-8")
        (project / "ModuleData" / "custom_skill_xp_sources.json").write_text(json.dumps({"source": 10}), encoding="utf-8")

        deployed = game / "Modules" / "LexerSkillTweaks"
        if installed:
            (deployed / "GUI" / "Prefabs").mkdir(parents=True)
            (deployed / "ModuleData").mkdir(parents=True)
            (deployed / "SubModule.xml").write_text(OLD_SUBMODULE, encoding="utf-8")
            (deployed / "GUI" / "Prefabs" / "Test.xml").write_text("<Prefab><Old /></Prefab>\n", encoding="utf-8")
            (deployed / "ModuleData" / "custom_skill_effects.json").write_text(json.dumps({"runtime": {"low": 9, "high": 9}}), encoding="utf-8")
            (deployed / "ModuleData" / "custom_skill_xp_sources.json").write_text(json.dumps({"runtime": 99}), encoding="utf-8")
            (deployed / "keep-me.txt").write_text("unknown deployed file", encoding="utf-8")
        return temporary, project, game, deployed

    def test_sync_is_additive_backed_up_and_preserves_runtime_state(self):
        temporary, project, game, deployed = self.fixture(installed=True)
        try:
            result = sync_project_assets(project, game)
            self.assertTrue(result["existingModule"])
            self.assertIn("SubModule.xml", result["copied"])
            self.assertIn("GUI/Prefabs/Test.xml", result["copied"])
            self.assertIn("ModuleData/items.xml", result["copied"])
            self.assertEqual(result["deleted"], [])
            self.assertTrue((deployed / "SubModule.xml.lexeditor.bak").is_file())
            self.assertTrue((deployed / "GUI" / "Prefabs" / "Test.xml.lexeditor.bak").is_file())
            self.assertEqual((deployed / "keep-me.txt").read_text(), "unknown deployed file")
            self.assertEqual(
                json.loads((deployed / "ModuleData" / "custom_skill_effects.json").read_text()),
                {"runtime": {"low": 9, "high": 9}},
            )
            self.assertEqual(
                json.loads((deployed / "ModuleData" / "custom_skill_xp_sources.json").read_text()),
                {"runtime": 99},
            )
            self.assertEqual(
                (deployed / "ModuleData" / "items.xml").read_text(),
                '<Items><Item id="new" /></Items>\n',
            )

            second = sync_project_assets(project, game)
            self.assertEqual(second["copied"], [])
            self.assertIn("SubModule.xml", second["unchanged"])
            self.assertIn("GUI/Prefabs/Test.xml", second["unchanged"])
            self.assertIn("ModuleData/items.xml", second["unchanged"])
        finally:
            temporary.cleanup()

    def test_first_asset_sync_can_create_only_the_selected_module_folder(self):
        temporary, project, game, deployed = self.fixture(installed=False)
        try:
            module_id, target, existed = deploy_target(project, game)
            self.assertEqual(module_id, "LexerSkillTweaks")
            self.assertEqual(target, deployed.resolve())
            self.assertFalse(existed)
            self.assertFalse(deployed.exists())
            result = sync_project_assets(project, game)
            self.assertFalse(result["existingModule"])
            self.assertTrue((deployed / "SubModule.xml").is_file())
            self.assertTrue((deployed / "ModuleData" / "items.xml").is_file())
        finally:
            temporary.cleanup()

    def test_invalid_game_root_refuses_before_creating_deployment_tree(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            game = root / "not-a-game"
            project.mkdir()
            (project / "SubModule.xml").write_text(PROJECT_SUBMODULE, encoding="utf-8")
            with self.assertRaisesRegex(FileNotFoundError, "Bannerlord executable not found"):
                sync_project_assets(project, game)
            self.assertFalse((game / "Modules").exists())

    def test_unsafe_module_id_is_rejected(self):
        temporary, project, game, _deployed = self.fixture(installed=False)
        try:
            (project / "SubModule.xml").write_text(
                '<Module><Id value="../Escape" /></Module>', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "unsafe"):
                sync_project_assets(project, game)
            self.assertFalse((game / "Escape").exists())
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
