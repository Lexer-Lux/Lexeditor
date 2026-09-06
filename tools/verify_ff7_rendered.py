"""Actual FF7 page + shared UI interaction tests with synthetic game data.

Only OS host functions and Audio playback are doubles. The actual DOM helpers,
controls, list/detail, history, save actions, settings, and HTTP handlers run.
This is not an installed-game or audio-selection listening test.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import unittest
from unittest.mock import patch
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_ff7_datasets as fixtures
import verify_ff7_completion as complete
import verify_ff7_extended as extended_fixtures
from games.ff7 import extended as ex, ai
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('FF7_SCREENSHOTS',str(ROOT/'out/ff7-rendered')))

HOST = r'''
window.audioPlayed=[];window.audioPaused=[];
window.Audio=class {
  constructor(url){this.url=url;this.volume=0}
  addEventListener(){}
  play(){audioPlayed.push({url:this.url,volume:this.volume});return Promise.resolve()}
  pause(){audioPaused.push(this.url)}
};
const replace=history.replaceState.bind(history);
history.replaceState=(s,u)=>replace(s,u);
window.pywebview={api:{
  lexeditor_settings:async()=>({soundEnabled:true,soundVolumePercent:50,panelGapPercent:1,tableRowsPerPage:10}),
  default_views:async()=>({views:{}}),mod_projects:async()=>({projects:[]}),
  game_process_status:async()=>({running:false}),window_state:async()=>({})
}};
window.fetch=async(path,options={})=>{
  const r=await window.testRequest(path,options);
  return new Response(r.body,{status:r.status});
};
'''

class RenderedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.driver=sync_playwright().start()
    @classmethod
    def tearDownClass(cls):cls.driver.stop()
    def setUp(self):
        self.backend=fixtures.HttpTests('test_missing_kernel_still_exposes_dashboard_map_and_tweaks')
        self.backend.setUp();self.addCleanup(self.backend.doCleanups)
        self.browser=self.driver.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM') or shutil.which('chromium') or None)
        self.addCleanup(self.browser.close)
        self.page=self.browser.new_page(viewport={'width':1200,'height':800})
        self.page.set_default_timeout(10000);self.errors=[]
        self.page.on('pageerror',lambda error:self.errors.append(str(error)))
        self.page.expose_function('testRequest',self.bridge)
        self.paths={}
    def bridge(self,path,options):
        if not str(path).startswith('/api/'):
            return {'status':404,'body':'{}'}
        data=json.loads(options['body']) if options.get('body') else None
        status,body=self.backend.request(path,data)
        return {'status':status,'body':json.dumps(body)}
    def install(self,prefix=''):
        game=self.backend.game
        kernel=game/(prefix+'data/lang-en/kernel/KERNEL.BIN');fixtures.write_kernel(kernel)
        values={prefix+'data/battle/scene.bin':extended_fixtures.scene_fixture(),
                prefix+'data/lang-en/kernel/kernel2.bin':extended_fixtures.text_fixture(),
                prefix+'data/field/flevel.lgp':complete.lgp_fixture([('maplist',b'list'),('field1',complete.field_fixture())]),
                prefix+'data/wm/world_us.lgp':complete.lgp_fixture([('enc_w.bin',complete.world_fixture()),('other',b'opaque')]),
                'ff7_en.exe':extended_fixtures.exe_fixture()}
        for name,data in values.items():
            path=game/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            self.paths[name]=data
        self.paths[str(kernel.relative_to(game))]=kernel.read_bytes()
        profile=patch.dict(ex.EXE_PROFILES,{hashlib.sha1(values['ff7_en.exe']).hexdigest().upper():0x400})
        profile.start();self.addCleanup(profile.stop)
        (game/'FFNx.toml').write_bytes(fixtures.CONFIG)
    def open(self,edition='ff7'):
        self.page.goto('about:blank')
        html=(ROOT/'games/ff7/editor.html').read_text()
        html=html.replace('<link rel="stylesheet" href="/shared/framework.css">','<style>'+(ROOT/'ui/framework.css').read_text()+'</style>')
        code=HOST+'\nwindow.__lexeditorPlugin='+json.dumps({'id':edition,'name':'FF7 fixture','edition':edition})+';\n'+(ROOT/'ui/framework.js').read_text()
        html=html.replace('<script src="/shared/framework.js"></script>','<script>'+code+'</script>')
        self.page.set_content(html,wait_until='domcontentloaded')
        self.page.wait_for_function('state.loaded === true')
        self.assertEqual(self.errors,[])
    def navigate(self,group):
        self.page.evaluate('(group)=>navigate(group)',group)
        self.page.wait_for_timeout(50)
        self.assertTrue(self.page.locator('.ff7-detail').count()>0,group)
    def control(self,group,key):
        self.navigate(group)
        name=self.page.evaluate('([group,key])=>{const row=state.records[group].find(r=>r.id===state.selected[group]);return state.data.categories.find(c=>c.id===group).fields.find(f=>f.key===key).label+" for "+row.name}',[group,key])
        return self.page.get_by_label(name,exact=True).first
    def save(self):
        self.page.locator('#global-save').click()
        self.page.wait_for_function('!state.saving && dirtyCount() === 0')
        self.assertEqual(self.errors,[])
    def originals_unchanged(self):
        for name,raw in self.paths.items():self.assertEqual((self.backend.game/name).read_bytes(),raw,name)

    def test_all_new_editors_save_reopen_and_real_text_controls(self):
        self.install();self.open()
        edits=(('characterNames','name','Cloudy'),('growthCurves','gradient0','80'),
               ('growthBonuses','bonus0','2'),('characterAI','script1','PUSH8 1\nDROP\nEND'),
               ('enemyAI','script1','PUSH8 2\nDROP\nEND'),('formationAI','script0','END'),
               ('recruits','strength','75'),('defaultNames','name','Default'),
               ('fieldEncounters','battle0','400'),('worldEncounters','battle0','401'),
               ('yuffieEncounters','battle','402'),('chocoboRatings','rating','7'),
               ('texts','text','Rendered text'))
        for group,key,value in edits:
            with self.subTest(group=group):
                control=self.control(group,key)
                # Regression: shared el() sets attributes, not textarea.value.
                original=self.page.evaluate('([g,k])=>state.records[g].find(r=>r.id===state.selected[g]).values[k]',[group,key])
                self.assertEqual(control.input_value(),str(original))
                control.fill(value);self.save()
                selected=self.page.evaluate('(g)=>state.selected[g]',group)
                status,data=self.backend.request('/api/data');self.assertEqual(status,200)
                actual=next(row for row in data['records'][group] if row['id']==selected)['values'][key]
                self.assertEqual(actual,ai.disassemble(ai.assemble(value)) if 'AI' in group else (int(value) if value.isdigit() else value))
        self.originals_unchanged()
        self.open();self.assertEqual(self.control('texts','text').input_value(),'Rendered text')

    def test_both_editions_layout_and_new_dataset_navigation(self):
        self.install(prefix='ff7/workingdir/')
        OUT.mkdir(parents=True,exist_ok=True)
        for edition in ('ff7','ff7-2013'):
            self.open(edition)
            for width,height in ((900,620),(1200,800),(1600,1000)):
                self.page.set_viewport_size({'width':width,'height':height})
                self.navigate('characters')
                self.page.get_by_role('tab',name='Growth curves',exact=True).click()
                self.assertEqual(self.page.evaluate('state.tab'),'growthCurves')
                self.assertEqual(self.page.get_by_role('tab',name='Growth curves',exact=True).get_attribute('aria-selected'),'true')
                self.navigate('characterAI')
                self.page.wait_for_timeout(80)
                metrics=self.page.evaluate('''()=>{const r=document.querySelector('.ff7-detail').getBoundingClientRect();return{body:document.body.scrollHeight,right:r.right,bottom:r.bottom}}''')
                self.assertLessEqual(metrics['body'],height+2,(edition,metrics))
                self.assertLessEqual(metrics['right'],width+2,(edition,metrics))
                self.assertLessEqual(metrics['bottom'],height+2,(edition,metrics))
                cells=self.page.locator('.ff7-table .lex-column-list-row').first.locator('.lex-column-list-cell').evaluate_all('(cells)=>cells.map(c=>({left:c.getBoundingClientRect().left,right:c.getBoundingClientRect().right,width:c.getBoundingClientRect().width}))')
                self.assertTrue(all(c['width']>20 for c in cells),(edition,cells))
                self.assertTrue(all(a['right']<=b['left']+1 for a,b in zip(cells,cells[1:])),(edition,cells))
                self.page.screenshot(path=str(OUT/f'{edition}-{width}.png'))
            self.navigate('fieldEncounters')
            self.assertEqual(self.page.get_by_role('tab',name='Field encounters',exact=True).get_attribute('aria-selected'),'true')
        self.assertEqual(self.errors,[])

    def test_interface_sounds_once_and_sound_off_stops_playback(self):
        self.install();self.open();self.navigate('characters')
        self.page.evaluate('''()=>{LexeditorUI.configureThemeSounds(['move','confirm','save','back'].map(slot=>({slot,available:true,url:'fixture:'+slot})));audioPlayed=[]}''')
        self.page.locator('.ff7-table .lex-list-row[data-key="1"]').click()
        self.assertEqual(self.page.evaluate('audioPlayed.map(a=>a.url)'),['fixture:move'])
        self.page.get_by_role('tab',name='Growth curves',exact=True).click()
        self.assertEqual(self.page.evaluate('audioPlayed.map(a=>a.url)'),['fixture:move','fixture:confirm'])
        self.control('growthCurves','gradient0').fill('81');self.save()
        self.assertEqual(self.page.evaluate('audioPlayed.filter(a=>a.url==="fixture:save").length'),1)
        self.assertTrue(self.page.evaluate('audioPlayed.every(a=>a.volume===0.25)'))
        self.page.evaluate('''()=>{window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{soundEnabled:false,soundVolumePercent:50}}));audioPlayed=[]}''')
        self.assertGreater(self.page.evaluate('audioPaused.length'),0)
        self.page.get_by_role('tab',name='Growth bonuses',exact=True).click()
        self.control('growthBonuses','bonus0').fill('3');self.save()
        self.page.evaluate('LexeditorUI.playThemeSound("back")')
        self.assertEqual(self.page.evaluate('audioPlayed'),[])
        self.originals_unchanged()

if __name__=='__main__':unittest.main(verbosity=2,defaultTest='RenderedTests')
