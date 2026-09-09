"""Focused checks for Bannerlord perk/XP editing and deployment diagnostics."""
from pathlib import Path
import tempfile
import unittest

PERKS = r'''private static readonly List<CustomSkillPerk> Perks = new List<CustomSkillPerk>{
Perk("Tailoring", 25, "Undershirt Armor", "Civilian armor.", false),
Perk("Tailoring", 50, "Gotta Go Fast", "Speed."),
Perk("Athletics", 25, "Anti-Cavalry", "Headshots dismount.")};'''
XP = r'''private static readonly List<XpSourceDefinition> Definitions = new List<XpSourceDefinition>{
Source("Tailoring", "Light armor damage mitigated", 1f),
Source("Riding", "Mounted movement second", 0.25f)};'''
MODULE = '''<Module><Name value="Mod"/><Id value="Mod"/><Version value="v1"/><SingleplayerModule value="true"/>
<DependedModules><DependedModule Id="Native"/><DependedModule Id="Harmony" DependentVersion="v2"/></DependedModules>
<SubModules><SubModule><Name value="Mod"/><DLLName value="Mod.dll"/><SubModuleClassType value="Mod.SubModule"/></SubModule></SubModules></Module>'''

class BannerlordPerksRuntimeTests(unittest.TestCase):
    def test_perk_and_xp_source_safe_edits(self):
        from games.bannerlord.perk_data import (
            read_perk_definitions, read_xp_source_definitions,
            save_perk_definitions, save_xp_source_definitions,
        )
        with tempfile.TemporaryDirectory() as name:
            project=Path(name);(project/'src').mkdir()
            (project/'src/CustomSkillPerks.cs').write_text(PERKS,encoding='utf-8')
            (project/'src/CustomSkillXpSourcesConfig.cs').write_text(XP,encoding='utf-8')
            perks=read_perk_definitions(project)['perks']
            self.assertFalse(perks[0]['implemented']);self.assertTrue(perks[1]['implemented'])
            saved=save_perk_definitions(project,[{'index':1,'originalId':perks[1]['id'],'fields':{'level':55,'description':'Faster.'}}])
            self.assertEqual(saved['perks'][1]['level'],55);self.assertEqual(saved['perks'][1]['name'],'Gotta Go Fast')
            with self.assertRaises(ValueError):
                save_perk_definitions(project,[{'index':0,'originalId':perks[0]['id'],'fields':{'level':101}}])
            sources=read_xp_source_definitions(project)['sources']
            saved=save_xp_source_definitions(project,[{'index':1,'originalId':sources[1]['id'],'fields':{'defaultAmount':0.5}}])
            self.assertEqual(saved['sources'][1]['defaultAmount'],0.5)
            with self.assertRaises(ValueError):
                save_xp_source_definitions(project,[{'index':0,'originalId':sources[0]['id'],'fields':{'defaultAmount':-1}}])

    def test_deployment_status_runnable_warns_on_version_mismatch_and_blocks_missing_dependency(self):
        from games.bannerlord.runtime_data import deployment_status
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);project=root/'project';game=root/'game';project.mkdir()
            (project/'SubModule.xml').write_text(MODULE,encoding='utf-8')
            (game/'bin/Win64_Shipping_Client').mkdir(parents=True)
            (game/'bin/Win64_Shipping_Client/Bannerlord.exe').write_bytes(b'exe')
            for module_id in ('Native','Harmony'):
                folder=game/'Modules'/module_id;folder.mkdir(parents=True)
                (folder/'SubModule.xml').write_text(f'<Module><Name value="{module_id}"/><Id value="{module_id}"/><Version value="v1"/></Module>',encoding='utf-8')
            deployed=game/'Modules/Mod';deployed.mkdir(parents=True)
            (deployed/'SubModule.xml').write_bytes((project/'SubModule.xml').read_bytes())
            (deployed/'bin/Win64_Shipping_Client').mkdir(parents=True)
            (deployed/'bin/Win64_Shipping_Client/Mod.dll').write_bytes(b'dll')
            (deployed/'ModuleData').mkdir()
            (deployed/'ModuleData/custom_skill_effects.json').write_text('{"x":{"low":1,"high":2}}',encoding='utf-8')
            (deployed/'ModuleData/custom_skill_xp_sources.json').write_text('{"x":3}',encoding='utf-8')
            status=deployment_status(project,game)
            self.assertTrue(status['runnable']);self.assertTrue(status['inSync'])
            self.assertTrue(all(row['installed'] for row in status['dependencies']))
            harmony=next(row for row in status['dependencies'] if row['id']=='Harmony')
            self.assertEqual(harmony['requiredVersion'],'v2')
            self.assertEqual(harmony['installedVersion'],'v1')
            self.assertFalse(harmony['versionMatch'])
            self.assertTrue(any('launcher would warn' in issue and 'Harmony' in issue for issue in status['issues']))
            self.assertEqual(status['runtimeOverrides']['effects']['keys'],1)
            (game/'Modules/Harmony/SubModule.xml').unlink()
            broken=deployment_status(project,game)
            self.assertFalse(broken['runnable'])
            self.assertTrue(any('Harmony' in issue for issue in broken['issues']))

if __name__=='__main__':unittest.main()
