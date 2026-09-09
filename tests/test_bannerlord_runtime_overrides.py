from pathlib import Path
import json
import tempfile
import unittest

from games.bannerlord.runtime_overrides import read_runtime_overrides, save_runtime_overrides


EFFECTS = r'''private static readonly List<EffectDefinition> Definitions = new List<EffectDefinition>{Effect("Tailoring","Light armor encumbrance",150f,50f,"%"),Effect("Medicine","Ally heal rate",2.5f,5f,"%")};'''
XP = r'''private static readonly List<SourceDefinition> Definitions = new List<SourceDefinition>{Source("Tailoring","Craft cloth",12f),Source("Medicine","Heal ally",4.5f)};'''


def write_module(root: Path, module_id: str) -> Path:
    module = root / "Modules" / module_id
    module.mkdir(parents=True, exist_ok=True)
    (module / "SubModule.xml").write_text(
        f'<Module><Name value="{module_id}"/><Id value="{module_id}"/><DependedModules/></Module>',
        encoding="utf-8",
    )
    return module


class BannerlordRuntimeOverrideTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        project = root / "project"
        game = root / "game"
        (project / "src").mkdir(parents=True)
        (project / "SubModule.xml").write_text(
            '<Module><Id value="LexerSkillTweaks"/></Module>', encoding="utf-8"
        )
        (project / "src" / "CustomSkillEffectRanges.cs").write_text(EFFECTS, encoding="utf-8")
        (project / "src" / "CustomSkillXpSourcesConfig.cs").write_text(XP, encoding="utf-8")
        deployed = write_module(game, "LexerSkillTweaks")
        return temporary, project, game, deployed

    def test_missing_files_fall_back_to_source_defaults(self):
        temporary, project, game, deployed = self.fixture()
        try:
            data = read_runtime_overrides(project, game)
            self.assertTrue(data["available"])
            self.assertEqual(data["deployedRoot"], str(deployed))
            self.assertFalse(data["effects"][0]["overridden"])
            self.assertEqual(data["effects"][0]["low"], 150)
            self.assertEqual(data["effects"][0]["high"], 50)
            self.assertFalse(data["xpSources"][0]["overridden"])
            self.assertEqual(data["xpSources"][0]["amount"], 12)
        finally:
            temporary.cleanup()

    def test_save_create_readback_and_revert_preserve_unknown_keys(self):
        temporary, project, game, deployed = self.fixture()
        try:
            module_data = deployed / "ModuleData"
            module_data.mkdir()
            effects_path = module_data / "custom_skill_effects.json"
            xp_path = module_data / "custom_skill_xp_sources.json"
            effects_path.write_text(json.dumps({"Future.Effect": {"low": 9, "high": 10}}), encoding="utf-8")
            xp_path.write_text(json.dumps({"Future.XP": 99}), encoding="utf-8")

            current = read_runtime_overrides(project, game)
            effect = current["effects"][0]
            xp = current["xpSources"][0]
            saved = save_runtime_overrides(project, {
                "effects": [{"id": effect["id"], "overridden": True, "low": 125, "high": 75}],
                "xpSources": [{"id": xp["id"], "overridden": True, "amount": 22.5}],
            }, game)
            self.assertEqual(saved["saved"], 2)
            self.assertTrue(Path(saved["backups"]["effects"]).is_file())
            self.assertTrue(Path(saved["backups"]["xpSources"]).is_file())
            self.assertEqual(saved["effects"][0]["low"], 125)
            self.assertEqual(saved["xpSources"][0]["amount"], 22.5)
            self.assertIn("Future.Effect", json.loads(effects_path.read_text()))
            self.assertIn("Future.XP", json.loads(xp_path.read_text()))

            reverted = save_runtime_overrides(project, {
                "effects": [{"id": effect["id"], "overridden": False}],
                "xpSources": [{"id": xp["id"], "overridden": False}],
            }, game)
            self.assertFalse(reverted["effects"][0]["overridden"])
            self.assertEqual(reverted["effects"][0]["low"], 150)
            self.assertFalse(reverted["xpSources"][0]["overridden"])
            self.assertEqual(reverted["xpSources"][0]["amount"], 12)
            self.assertIn("Future.Effect", json.loads(effects_path.read_text()))
            self.assertIn("Future.XP", json.loads(xp_path.read_text()))
        finally:
            temporary.cleanup()

    def test_unknown_edit_id_and_negative_xp_are_rejected(self):
        temporary, project, game, _deployed = self.fixture()
        try:
            with self.assertRaisesRegex(ValueError, "Unknown runtime effect ID"):
                save_runtime_overrides(project, {
                    "effects": [{"id": "Nope", "overridden": True, "low": 1, "high": 2}]
                }, game)
            source = read_runtime_overrides(project, game)["xpSources"][0]
            with self.assertRaisesRegex(ValueError, "cannot be negative"):
                save_runtime_overrides(project, {
                    "xpSources": [{"id": source["id"], "overridden": True, "amount": -1}]
                }, game)
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
