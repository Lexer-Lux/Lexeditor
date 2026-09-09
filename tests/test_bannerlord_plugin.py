"""Focused checks for the Bannerlord Lexeditor plugin."""
from __future__ import annotations
from pathlib import Path
import os,subprocess,tempfile,unittest
from unittest.mock import patch
from plugin_api import validate_plugin

SUBMODULE='''<?xml version="1.0" encoding="utf-8"?><Module><!-- preserve this module comment --><Name value="Lexer Skill Tweaks"/><Id value="LexerSkillTweaks"/><Version value="v1.2.3"/><DefaultModule value="false"/><SingleplayerModule value="true"/><MultiplayerModule value="false"/><DependedModules><!-- preserve this dependency comment --><DependedModule Id="Native"/><DependedModule Id="Bannerlord.Harmony" DependentVersion="v2.3.3" Mystery="keep"/></DependedModules><IncompatibleModules><IncompatibleModule Id="Bad.Mod"/></IncompatibleModules><SubModules><SubModule><Name value="Lexer Skill Tweaks"/><DLLName value="LexerSkillTweaks.dll"/><SubModuleClassType value="LexerSkillTweaks.SubModule"/><Tags><Tag key="DedicatedServerType" value="none" Mystery="keep"/></Tags><Unknown value="keep"/></SubModule></SubModules><Xmls><XmlNode><Id value="Items"/><Path value="items"/><IncludedGameTypes><GameType value="Campaign"/></IncludedGameTypes></XmlNode></Xmls></Module>'''
CSPROJ='''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net472</TargetFramework><LangVersion>latest</LangVersion><Nullable>disable</Nullable><AssemblyName>LexerSkillTweaks</AssemblyName><RootNamespace>LexerSkillTweaks</RootNamespace><BannerlordDir>C:\\Games\\Bannerlord</BannerlordDir></PropertyGroup><ItemGroup><Reference Include="TaleWorlds.Core"><HintPath>$(GameBin)\\TaleWorlds.Core.dll</HintPath><Private>false</Private></Reference><PackageReference Include="Example.Package" Version="1.2.3" /></ItemGroup><Target Name="CopyModuleFiles" AfterTargets="Build"><Copy SourceFiles="SubModule.xml" DestinationFolder="$(ModuleDir)" /></Target></Project>'''
SKILL_DEFINITIONS=r'''private static readonly List<AttributeDefinition> AttributeDefinitions = new List<AttributeDefinition>{new AttributeDefinition("Sanguis","Sanguis","SNG","Air."),new AttributeDefinition("Phlegma","Phlegma","PHL","Water.")};private static readonly List<SkillDefinition> SkillDefinitions = new List<SkillDefinition>{new SkillDefinition("Tailoring","Tailoring","Creation skill.","Tailoring improves cloth work.","Sanguis"),new SkillDefinition("Medicine","Medicine","Support skill.","Medicine improves healing.","Phlegma")};'''
EFFECT_DEFINITIONS=r'''private static readonly List<EffectDefinition> Definitions = new List<EffectDefinition>{Effect("Tailoring","Light armor encumbrance",150f,50f,"%"),Effect("Medicine","Ally heal rate",2.5f,5f,"%")};'''

class BannerlordPluginTests(unittest.TestCase):
    def test_descriptor_is_valid_and_targets_bannerlord(self):
        from games.bannerlord.plugin import PLUGIN
        validate_plugin(PLUGIN);self.assertEqual(PLUGIN.plugin_id,"bannerlord");self.assertEqual(PLUGIN.installation.steam_app_id,"261550");self.assertEqual(PLUGIN.installation.launch_path,"bin/Win64_Shipping_Client/Bannerlord.exe")
    def test_full_submodule_editing_preserves_unknown_data(self):
        from games.bannerlord.module_data import data_map,read_submodule,save_module
        with tempfile.TemporaryDirectory() as name:
            project=Path(name);source=project/"SubModule.xml";source.write_text(SUBMODULE);(project/"LexerSkillTweaks.csproj").write_text(CSPROJ);(project/"src").mkdir();(project/"src/SubModule.cs").write_text("class SubModule {}");(project/"GUI/Prefabs").mkdir(parents=True);(project/"GUI/Prefabs/Character.xml").write_text("<Widget/>")
            module=read_submodule(source);self.assertEqual(module["dependencies"][1]["dependentVersion"],"v2.3.3");self.assertEqual(module["incompatibleModules"][0]["id"],"Bad.Mod")
            result=save_module(source,{"metadata":{"name":"Lexer Skill Tweaks Redux","id":"LexerSkillTweaks","version":"v2.0.0","defaultModule":False,"singleplayer":True,"multiplayer":False},"dependencies":[module["dependencies"][1],{"index":None,"id":"Native","dependentVersion":"","optional":True,"attributes":{}}],"incompatibleModules":[],"submodules":[{**module["submodules"][0],"name":"Lexer Skill Tweaks Redux","tags":[{**module["submodules"][0]["tags"][0],"value":"client"}]}],"xmls":[{**module["xmls"][0],"path":"items2","includedGameTypes":[{"index":0,"value":"Campaign"},{"index":None,"value":"CustomGame"}]}]})
            self.assertGreater(result["saved"],0);self.assertTrue(Path(result["backup"]).is_file());self.assertEqual([r["id"] for r in result["module"]["dependencies"]],["Bannerlord.Harmony","Native"]);rewritten=source.read_text();self.assertIn("preserve this module comment",rewritten);self.assertIn('Mystery="keep"',rewritten);self.assertIn('<Unknown value="keep"',rewritten);rows={r["filename"]:r for r in data_map(project)["rows"]};self.assertEqual(rows["SubModule.xml"]["coverage"],"structured");self.assertEqual(rows["LexerSkillTweaks.csproj"]["coverage"],"structured");self.assertEqual(rows["src/SubModule.cs"]["coverage"],"source")
    def test_submodule_save_rejects_redirected_descriptor(self):
        from games.bannerlord.module_data import save_module
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);project=root/"project";project.mkdir();source=project/"SubModule.xml";source.write_text(SUBMODULE,encoding="utf-8");outside=root/"outside.xml";outside.write_text(SUBMODULE,encoding="utf-8");outside_resolved=outside.resolve();real_resolve=Path.resolve
            def fake_resolve(path,*args,**kwargs):
                if path==source:return outside_resolved
                return real_resolve(path,*args,**kwargs)
            with patch.object(Path,"resolve",new=fake_resolve):
                with self.assertRaisesRegex(ValueError,"escaped the selected project"):
                    save_module(source,{"metadata":{"name":"Escaped"}})
            self.assertIn('Name value="Lexer Skill Tweaks"',outside.read_text(encoding="utf-8"))
    def test_submodule_write_helpers_do_not_follow_existing_hardlinks(self):
        from games.bannerlord.module_data import read_submodule,save_module
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/"SubModule.xml";source.write_text(SUBMODULE,encoding="utf-8");backup=source.with_name(source.name+".lexeditor.bak");temporary=source.with_name(source.name+".lexeditor.tmp");outside_backup=root/"outside-backup.txt";outside_temporary=root/"outside-temporary.txt";outside_backup.write_text("backup sentinel",encoding="utf-8");outside_temporary.write_text("temporary sentinel",encoding="utf-8");os.link(outside_backup,backup);os.link(outside_temporary,temporary)
            result=save_module(source,{"metadata":{"name":"Lexer Skill Tweaks Hardened"}})
            self.assertEqual(outside_backup.read_text(encoding="utf-8"),"backup sentinel");self.assertEqual(outside_temporary.read_text(encoding="utf-8"),"temporary sentinel");self.assertEqual(read_submodule(backup)["name"],"Lexer Skill Tweaks");self.assertEqual(result["module"]["name"],"Lexer Skill Tweaks Hardened")
    def test_msbuild_properties_source_and_build_helpers(self):
        from games.bannerlord.project_data import read_project_file,read_source,run_build,save_project_properties,save_source
        with tempfile.TemporaryDirectory() as name:
            project=Path(name);csproj=project/"LexerSkillTweaks.csproj";csproj.write_text(CSPROJ);(project/"src").mkdir();source=project/"src/Example.cs";source.write_text("class Example {}");model=read_project_file(csproj);self.assertEqual(model["properties"]["TargetFramework"],"net472");result=save_project_properties(csproj,{"AssemblyName":"LexerSkillTweaksRedux","OutputPath":"out\\"});self.assertEqual(result["saved"],2);opened=read_source(project,"src/Example.cs");self.assertEqual(opened["text"],"class Example {}");saved=save_source(project,"src/Example.cs","class Example { int Value; }");self.assertTrue(Path(saved["backup"]).is_file())
            with self.assertRaises(ValueError):read_source(project,"../outside.cs")
            completed=subprocess.CompletedProcess(["dotnet"],0,stdout="Build succeeded.\n",stderr="")
            with patch("games.bannerlord.project_data.subprocess.run",return_value=completed) as runner:build=run_build(project,configuration="Release")
            self.assertTrue(build["succeeded"]);self.assertEqual(runner.call_args.args[0][0:2],["dotnet","build"]);self.assertFalse(runner.call_args.kwargs.get("shell",False))
    def test_custom_skill_and_effect_source_editors(self):
        from games.bannerlord.module_data import data_map
        from games.bannerlord.skill_data import read_effect_definitions,read_skill_definitions,save_effect_definitions,save_skill_definitions
        with tempfile.TemporaryDirectory() as name:
            project=Path(name);(project/"src").mkdir();skills_path=project/"src/CustomSkillDefinitions.cs";effects_path=project/"src/CustomSkillEffectRanges.cs";skills_path.write_text(SKILL_DEFINITIONS);effects_path.write_text(EFFECT_DEFINITIONS);skills=read_skill_definitions(project);self.assertTrue(skills["available"]);self.assertEqual(skills["skills"][0]["attributeId"],"Sanguis")
            saved_skills=save_skill_definitions(project,{"attributes":[{"index":0,"originalId":"Sanguis","fields":{"name":"Blood","abbreviation":"BLD"}}],"skills":[{"index":0,"originalId":"Tailoring","fields":{"name":"Sewing","attributeId":"Phlegma"}}]});self.assertEqual(saved_skills["attributes"][0]["name"],"Blood");self.assertEqual(saved_skills["skills"][0]["attributeId"],"Phlegma")
            with self.assertRaises(ValueError):save_skill_definitions(project,{"attributes":[],"skills":[{"index":0,"originalId":"Tailoring","fields":{"attributeId":"NotAnAttribute"}}]})
            effects=read_effect_definitions(project);saved_effects=save_effect_definitions(project,[{"index":1,"originalId":effects["effects"][1]["id"],"fields":{"defaultLow":3.25,"defaultHigh":6}}]);self.assertEqual(saved_effects["effects"][1]["defaultLow"],3.25);rows={r["filename"]:r for r in data_map(project)["rows"]};self.assertEqual(rows["src/CustomSkillDefinitions.cs"]["target"],"skills");self.assertEqual(rows["src/CustomSkillEffectRanges.cs"]["target"],"effects")

if __name__=="__main__":unittest.main()
