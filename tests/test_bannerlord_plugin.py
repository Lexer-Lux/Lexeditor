"""Focused checks for the initial Bannerlord plugin slice."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from plugin_api import validate_plugin


SUBMODULE = """<?xml version="1.0" encoding="utf-8"?>
<Module>
  <!-- preserve this module comment -->
  <Name value="Lexer Skill Tweaks"/>
  <Id value="LexerSkillTweaks"/>
  <Version value="v1.2.3"/>
  <SingleplayerModule value="true"/>
  <MultiplayerModule value="false"/>
  <DependedModules>
    <DependedModule Id="Native"/>
    <DependedModule Id="Bannerlord.Harmony" DependentVersion="v2.3.3"/>
  </DependedModules>
  <SubModules>
    <SubModule>
      <Name value="Lexer Skill Tweaks"/>
      <DLLName value="LexerSkillTweaks.dll"/>
      <SubModuleClassType value="LexerSkillTweaks.SubModule"/>
      <Tags><Tag key="DedicatedServerType" value="none"/></Tags>
    </SubModule>
  </SubModules>
</Module>
"""


class BannerlordPluginTests(unittest.TestCase):
    def test_descriptor_is_valid_and_targets_bannerlord(self):
        from games.bannerlord.plugin import PLUGIN

        validate_plugin(PLUGIN)
        self.assertEqual(PLUGIN.plugin_id, "bannerlord")
        self.assertEqual(PLUGIN.installation.steam_app_id, "261550")
        self.assertEqual(PLUGIN.installation.launch_path, "bin/Win64_Shipping_Client/Bannerlord.exe")

    def test_submodule_metadata_and_data_map(self):
        from games.bannerlord.module_data import data_map, read_submodule, save_module_metadata

        with tempfile.TemporaryDirectory() as name:
            project = Path(name)
            (project / "SubModule.xml").write_text(SUBMODULE, encoding="utf-8")
            (project / "LexerSkillTweaks.csproj").write_text("<Project/>", encoding="utf-8")
            metadata = read_submodule(project / "SubModule.xml")
            self.assertEqual(metadata["id"], "LexerSkillTweaks")
            self.assertEqual(metadata["version"], "v1.2.3")
            self.assertTrue(metadata["singleplayer"])
            self.assertFalse(metadata["multiplayer"])
            self.assertEqual([row["Id"] for row in metadata["dependencies"]], ["Native", "Bannerlord.Harmony"])
            self.assertEqual(metadata["submodules"][0]["dllName"], "LexerSkillTweaks.dll")

            rows = {row["filename"]: row for row in data_map(project)["rows"]}
            self.assertEqual(rows["SubModule.xml"]["coverage"], "structured")
            self.assertEqual(rows["SubModule.xml"]["status"], "integrated")
            self.assertTrue(rows["SubModule.xml"]["openable"])
            self.assertTrue(rows["*.csproj"]["sourceAvailable"])
            self.assertEqual(rows["src/**/*.cs"]["coverage"], "source")

            result = save_module_metadata(
                project / "SubModule.xml",
                {"name": "Lexer Skill Tweaks Redux", "singleplayer": False},
            )
            self.assertEqual(result["saved"], 2)
            self.assertTrue(Path(result["backup"]).is_file())
            self.assertEqual(result["module"]["name"], "Lexer Skill Tweaks Redux")
            self.assertFalse(result["module"]["singleplayer"])
            rewritten = (project / "SubModule.xml").read_text(encoding="utf-8")
            self.assertIn("preserve this module comment", rewritten)
            self.assertEqual(
                [row["Id"] for row in result["module"]["dependencies"]],
                ["Native", "Bannerlord.Harmony"],
            )


if __name__ == "__main__":
    unittest.main()
