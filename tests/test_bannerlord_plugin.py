"""Focused checks for the Bannerlord Lexeditor plugin."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from plugin_api import validate_plugin


SUBMODULE = """<?xml version="1.0" encoding="utf-8"?>
<Module>
  <!-- preserve this module comment -->
  <Name value="Lexer Skill Tweaks"/>
  <Id value="LexerSkillTweaks"/>
  <Version value="v1.2.3"/>
  <DefaultModule value="false"/>
  <SingleplayerModule value="true"/>
  <MultiplayerModule value="false"/>
  <DependedModules>
    <!-- preserve this dependency comment -->
    <DependedModule Id="Native"/>
    <DependedModule Id="Bannerlord.Harmony" DependentVersion="v2.3.3" Mystery="keep"/>
  </DependedModules>
  <IncompatibleModules>
    <IncompatibleModule Id="Bad.Mod"/>
  </IncompatibleModules>
  <SubModules>
    <SubModule>
      <Name value="Lexer Skill Tweaks"/>
      <DLLName value="LexerSkillTweaks.dll"/>
      <SubModuleClassType value="LexerSkillTweaks.SubModule"/>
      <Tags><Tag key="DedicatedServerType" value="none" Mystery="keep"/></Tags>
      <Unknown value="keep"/>
    </SubModule>
  </SubModules>
  <Xmls>
    <XmlNode>
      <Id value="Items"/>
      <Path value="items"/>
      <IncludedGameTypes><GameType value="Campaign"/></IncludedGameTypes>
    </XmlNode>
  </Xmls>
</Module>
"""

CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net472</TargetFramework>
    <LangVersion>latest</LangVersion>
    <Nullable>disable</Nullable>
    <AssemblyName>LexerSkillTweaks</AssemblyName>
    <RootNamespace>LexerSkillTweaks</RootNamespace>
    <BannerlordDir>C:\\Games\\Bannerlord</BannerlordDir>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="TaleWorlds.Core">
      <HintPath>$(GameBin)\\TaleWorlds.Core.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <PackageReference Include="Example.Package" Version="1.2.3" />
  </ItemGroup>
  <Target Name="CopyModuleFiles" AfterTargets="Build">
    <Copy SourceFiles="SubModule.xml" DestinationFolder="$(ModuleDir)" />
  </Target>
</Project>
"""


class BannerlordPluginTests(unittest.TestCase):
    def test_descriptor_is_valid_and_targets_bannerlord(self):
        from games.bannerlord.plugin import PLUGIN

        validate_plugin(PLUGIN)
        self.assertEqual(PLUGIN.plugin_id, "bannerlord")
        self.assertEqual(PLUGIN.installation.steam_app_id, "261550")
        self.assertEqual(
            PLUGIN.installation.launch_path,
            "bin/Win64_Shipping_Client/Bannerlord.exe",
        )

    def test_full_submodule_editing_preserves_unknown_data(self):
        from games.bannerlord.module_data import data_map, read_submodule, save_module

        with tempfile.TemporaryDirectory() as name:
            project = Path(name)
            source = project / "SubModule.xml"
            source.write_text(SUBMODULE, encoding="utf-8")
            (project / "LexerSkillTweaks.csproj").write_text(CSPROJ, encoding="utf-8")
            (project / "src").mkdir()
            (project / "src" / "SubModule.cs").write_text("class SubModule {}", encoding="utf-8")
            (project / "GUI" / "Prefabs").mkdir(parents=True)
            (project / "GUI" / "Prefabs" / "Character.xml").write_text("<Widget/>", encoding="utf-8")

            module = read_submodule(source)
            self.assertEqual(module["id"], "LexerSkillTweaks")
            self.assertFalse(module["defaultModule"])
            self.assertEqual(module["dependencies"][1]["dependentVersion"], "v2.3.3")
            self.assertEqual(module["incompatibleModules"][0]["id"], "Bad.Mod")
            self.assertEqual(module["submodules"][0]["tags"][0]["key"], "DedicatedServerType")
            self.assertEqual(module["xmls"][0]["includedGameTypes"][0]["value"], "Campaign")

            result = save_module(
                source,
                {
                    "metadata": {
                        "name": "Lexer Skill Tweaks Redux",
                        "id": "LexerSkillTweaks",
                        "version": "v2.0.0",
                        "defaultModule": False,
                        "singleplayer": True,
                        "multiplayer": False,
                    },
                    "dependencies": [
                        module["dependencies"][1],
                        {
                            "index": None,
                            "id": "Native",
                            "dependentVersion": "",
                            "optional": True,
                            "attributes": {},
                        },
                    ],
                    "incompatibleModules": [],
                    "submodules": [
                        {
                            **module["submodules"][0],
                            "name": "Lexer Skill Tweaks Redux",
                            "tags": [
                                {
                                    **module["submodules"][0]["tags"][0],
                                    "value": "client",
                                }
                            ],
                        }
                    ],
                    "xmls": [
                        {
                            **module["xmls"][0],
                            "path": "items2",
                            "includedGameTypes": [
                                {"index": 0, "value": "Campaign"},
                                {"index": None, "value": "CustomGame"},
                            ],
                        }
                    ],
                },
            )
            self.assertGreater(result["saved"], 0)
            self.assertTrue(Path(result["backup"]).is_file())
            self.assertEqual(result["module"]["name"], "Lexer Skill Tweaks Redux")
            self.assertEqual(
                [row["id"] for row in result["module"]["dependencies"]],
                ["Bannerlord.Harmony", "Native"],
            )
            self.assertTrue(result["module"]["dependencies"][1]["optional"])
            self.assertEqual(result["module"]["incompatibleModules"], [])
            self.assertEqual(result["module"]["submodules"][0]["name"], "Lexer Skill Tweaks Redux")
            self.assertEqual(result["module"]["xmls"][0]["path"], "items2")
            self.assertEqual(
                [row["value"] for row in result["module"]["xmls"][0]["includedGameTypes"]],
                ["Campaign", "CustomGame"],
            )

            rewritten = source.read_text(encoding="utf-8")
            self.assertIn("preserve this module comment", rewritten)
            self.assertIn("preserve this dependency comment", rewritten)
            self.assertIn('Mystery="keep"', rewritten)
            self.assertIn('<Unknown value="keep"', rewritten)

            rows = {row["filename"]: row for row in data_map(project)["rows"]}
            self.assertEqual(rows["SubModule.xml"]["coverage"], "structured")
            self.assertEqual(rows["LexerSkillTweaks.csproj"]["coverage"], "structured")
            self.assertEqual(rows["src/SubModule.cs"]["coverage"], "source")
            self.assertTrue(rows["GUI/Prefabs/Character.xml"]["sourceOpenable"])

    def test_msbuild_properties_source_and_build_helpers(self):
        from games.bannerlord.project_data import (
            read_project_file,
            read_source,
            run_build,
            save_project_properties,
            save_source,
        )

        with tempfile.TemporaryDirectory() as name:
            project = Path(name)
            csproj = project / "LexerSkillTweaks.csproj"
            csproj.write_text(CSPROJ, encoding="utf-8")
            (project / "src").mkdir()
            source = project / "src" / "Example.cs"
            source.write_text("class Example {}", encoding="utf-8")

            model = read_project_file(csproj)
            self.assertEqual(model["properties"]["TargetFramework"], "net472")
            self.assertEqual(model["references"][0]["include"], "TaleWorlds.Core")
            self.assertEqual(model["packages"][0]["include"], "Example.Package")
            self.assertEqual(model["targets"][0]["name"], "CopyModuleFiles")

            result = save_project_properties(
                csproj,
                {"AssemblyName": "LexerSkillTweaksRedux", "OutputPath": "out\\"},
            )
            self.assertEqual(result["saved"], 2)
            self.assertTrue(Path(result["backup"]).is_file())
            self.assertEqual(
                result["project"]["properties"]["AssemblyName"],
                "LexerSkillTweaksRedux",
            )
            self.assertEqual(result["project"]["properties"]["OutputPath"], "out\\")

            opened = read_source(project, "src/Example.cs")
            self.assertEqual(opened["text"], "class Example {}")
            saved = save_source(project, "src/Example.cs", "class Example { int Value; }")
            self.assertTrue(Path(saved["backup"]).is_file())
            self.assertEqual(saved["text"], "class Example { int Value; }")
            with self.assertRaises(ValueError):
                read_source(project, "../outside.cs")

            completed = subprocess.CompletedProcess(
                ["dotnet"], 0, stdout="Build succeeded.\n", stderr=""
            )
            with patch("games.bannerlord.project_data.subprocess.run", return_value=completed) as runner:
                build = run_build(project, configuration="Release")
            self.assertTrue(build["succeeded"])
            self.assertEqual(build["configuration"], "Release")
            self.assertIn("Build succeeded.", build["output"])
            command = runner.call_args.args[0]
            self.assertEqual(command[0:2], ["dotnet", "build"])
            self.assertIn("--configuration", command)
            self.assertNotIn("shell", runner.call_args.kwargs)
            self.assertFalse(runner.call_args.kwargs.get("shell", False))


if __name__ == "__main__":
    unittest.main()
