"""Weapon-skill catalog authoring, exact assignments, stale-write protection and editor UI."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests/ds1'))
from plugins.ds1.weapon_skills import EMPTY, RELATIVE, WeaponSkills, validate


class SkillCatalogTests(unittest.TestCase):
    def test_readonly_empty_catalog_creates_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            game=Path(temporary)/'game';game.mkdir()
            store=WeaponSkills(game)
            self.assertEqual(store.value,EMPTY)
            with self.assertRaises(PermissionError):store.add()
            store.save();self.assertEqual(list(game.iterdir()),[])

    def test_author_assign_rename_delete_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            game=Path(temporary)/'game';project=Path(temporary)/'project'
            game.mkdir();project.mkdir();s=WeaponSkills(game,project,False)
            a=s.add();s.edit(a['id'],'name','Test Skill');s.edit(a['id'],'fpCost',12)
            s.assign(200000,a['id'],{200000,200001})
            self.assertEqual(s.assignment(200001),0)
            with self.assertRaises(ValueError):s.assign(999999,0,{200000})
            with self.assertRaises(ValueError):s.remove(a['id'])
            s.save();loaded=WeaponSkills(game,project,False)
            self.assertEqual(loaded.value,s.value);self.assertEqual(loaded.dirty_count,0)
            loaded.assign(200000,0,{200000});loaded.remove(a['id']);loaded.discard()
            self.assertEqual(loaded.assignment(200000),a['id'])

    def test_reject_malformed_links_duplicates_and_ranges(self):
        entry={'id':1,'name':'Test','description':'','iconId':None,'fpCost':0,'staminaCost':0}
        good={'version':1,'skills':[entry],'assignments':[{'weaponId':200000,'skillId':1}]}
        validate(good,{200000})
        for key,value in [('fpCost',-1),('staminaCost',65536),('id',True),('iconId',65536),('name','')]:
            bad=deepcopy(good);bad['skills'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(bad)
        for assignments in ([{'weaponId':200000,'skillId':2}],good['assignments']*2):
            bad=deepcopy(good);bad['assignments']=assignments
            with self.assertRaises(ValueError):validate(bad)
        with self.assertRaises(ValueError):validate(good,{200001})

    def test_stale_save_preserves_external_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            game=Path(temporary)/'game';project=Path(temporary)/'project'
            game.mkdir();project.mkdir();a=WeaponSkills(game,project,False);a.add();a.save()
            b=WeaponSkills(game,project,False);a.edit(1,'name','External');a.save()
            b.edit(1,'name','Unsaved')
            with self.assertRaises(ValueError):b.save()
            self.assertEqual(json.loads((project/RELATIVE).read_text())['skills'][0]['name'],'External')

    def test_editor_browser(self):
        from ds1_fixture import make_archive
        from plugins.ds1.store import RELATIVE as PARAM, MARKER
        from plugins.ds1.plugin import DS1Session
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory(prefix='lexeditor-skill-ui-') as temporary:
            folder=Path(temporary);game=folder/'game';project=folder/'project'
            for root in (game,project):
                (root/PARAM).parent.mkdir(parents=True);(root/PARAM).write_bytes(make_archive())
            (project/MARKER).write_text('DS1 project')
            (project/'mod.json').write_text(json.dumps({'name':'Skill Test','game':'ds1'}))
            session=DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(project)})
            errors=[]
            try:
                session.start()
                with sync_playwright() as play:
                    browser=play.chromium.launch(headless=True)
                    try:
                        page=browser.new_page(viewport={'width':1440,'height':900})
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.goto(session.url)
                        page.wait_for_selector('body[data-ds1-ready="true"]',timeout=60000)
                        page.evaluate('navigate("items","ashes-of-war")')
                        page.get_by_role('button',name='Add Ash of War',exact=True).click()
                        page.wait_for_function('state.row?.table==="WeaponSkill"')
                        page.evaluate('renameRecord(state.row,"Test Ash")')
                        page.wait_for_function('state.row?.name==="Test Ash"')
                        page.wait_for_function('state.pending===0')
                        screenshot=Path(os.environ.get('LEXEDITOR_SKILL_SCREENSHOT',str(folder/'skill-editor.png')))
                        page.screenshot(path=str(screenshot))
                        self.assertEqual(page.locator('[data-row-action="duplicate"]').count(),1)
                        self.assertEqual(errors,[])
                        page.evaluate('state.query="not-a-matching-name";render()')
                        self.assertIn('No matching Ashes of War',page.locator('body').inner_text())
                        page.evaluate('state.query="";render()')
                        # Save/discard through HTTP while rebuilding/deployment is
                        # deliberately excluded from this isolated editor fixture.
                        result=page.request.post(session.url+'/api/edit',data={'table':'WeaponSkill','id':1,'field':'fpCost','value':9})
                        self.assertTrue(result.ok,result.text())
                        self.assertEqual(result.json()['row']['fields'][2]['value'],9)
                        weapons=page.request.get(session.url+'/api/table?tab=weapons').json()['rows']
                        weapon=weapons[0]['id']
                        result=page.request.post(session.url+'/api/edit',data={'table':'EquipParamWeapon','id':weapon,'field':'ashOfWar','value':1})
                        self.assertTrue(result.ok,result.text())
                        self.assertGreater(len(result.json()['values']),1)
                        row=page.request.get(session.url+f'/api/row?table=EquipParamWeapon&id={weapon}').json()['row']
                        field=next(f for f in row['fields'] if f['key']=='ashOfWar')
                        self.assertEqual(field['enum']['1'],'Test Ash')
                        self.assertEqual(next(r for r in row['recordLinks'] if r['field']=='ashOfWar')['table'],'WeaponSkill')
                        denied=page.request.post(session.url+'/api/rows/remove',data={'table':'WeaponSkill','id':1})
                        self.assertEqual(denied.status,400)
                    finally:browser.close()
            finally:session.stop()


if __name__=='__main__':unittest.main()
