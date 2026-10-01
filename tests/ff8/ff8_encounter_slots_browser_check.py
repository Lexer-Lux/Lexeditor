"""Headless encounter slot selection, bounds and edit checks."""
import re,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
from plugins.ff8.encounters import apply_edits
from plugins.ff8.plugin import FF8Session
def main():
 raw=bytes([1,2,3,4])+bytes(124)
 header={'id':0,'stageId':9,'flags':2,'cameraMain':3,'cameraSecondary':4}
 saved,count=apply_edits(raw,[header],set())
 assert count==1 and saved==bytes([9])+raw[1:]
 for key in ['flags','cameraMain','cameraSecondary']:
  try: apply_edits(raw,[{**header,key:header[key]+1}],set())
  except ValueError as error: assert 'must remain unchanged' in str(error)
  else: raise AssertionError(f'Unproved {key} edit was accepted')
 source=plugin_ui('ff8')
 # The formation editor ends where battle.js hands the tab over to encounters_ui.js.
 functions=source[source.index('  function encounterLevelRule'):source.index('  // The Encounters tab itself lives in encounters_ui.js')]
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True)
  page=browser.new_page(viewport={'width':1100,'height':900})
  page.on('pageerror',lambda e:print(e));page.route('http://fixture/',lambda route:route.fulfill(body='<html></html>',content_type='text/html'));page.goto('http://fixture/');page.set_content('<main style="width:850px"></main>')
  page.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  page.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  page.add_style_tag(content=':root{--lex-text:#fff;--lex-panel:#626262;--lex-panel-2:#4f4f4f;--lex-border:#929292;--lex-accent:#aa2432;--lex-panel-gap:8px}')
  page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  page.add_script_tag(content="""
const {el,detailField,infoHelp,columnList,detailPanel}=LexeditorUI;
const shell={refresh:()=>{}},enemyDisplayName=v=>v;
const numberControl=(value,min,max,step,change,attrs)=>el('input',{type:'text',inputmode:'decimal',value,min,max,step,...attrs,oninput:e=>change(Number(e.target.value.replaceAll(',','')))});
const encounterSource=control=>control;
const enemySearchControl=(id,label,set)=>el('button',{'aria-label':label},'G-Soldier');
const row={id:0,stageId:1,flags:2,cameraMain:3,cameraSecondary:4,slots:Array.from({length:8},(_,slot)=>({slot,enemyName:slot?'Dummy':'G-Soldier',enemyId:0,enabled:slot===0,visible:true,loaded:true,targetable:true,x:1100,y:0,z:-3300,level:255}))};
const prefs=LexeditorUI.columnPreferences('encounter-fixture',[
 {key:'stageId',label:'Stage',pinned:false},{key:'flags',label:'Flags',pinned:false},
 {key:'cameraMain',label:'Main camera',pinned:false},{key:'cameraSecondary',label:'Secondary camera',pinned:false}],()=>{});
const renderEncounters=()=>document.querySelector('main').replaceChildren(encounterDetail(row,prefs));
const render=renderEncounters;
"""+functions+"renderEncounters();")
  assert page.locator('.lex-column-list-row').count()==8
  assert page.locator('.lex-detail-panel input:not([readonly])').count()==1
  assert page.locator('.lex-detail-panel .lex-readonly-field').count()==3
  page.get_by_label('Slot 1 x',exact=True).fill('1200')
  page.get_by_label('Slot 1 x',exact=True).press('Tab')
  assert page.evaluate('row.slots[0].x')==1200
  assert page.get_by_label('Slot 2 x',exact=True).is_disabled()
  page.get_by_label('Slot 2 enabled',exact=True).check()
  assert page.get_by_label('Slot 2 x',exact=True).is_enabled()
  page.get_by_label('Enemy level rule',exact=True).nth(1).select_option('fixed')
  assert page.evaluate('row.slots[1].level')==1
  for width in [850,600]:
   page.locator('main').evaluate('(e,w)=>e.style.width=w+"px"',width)
   page.wait_for_timeout(150)
   assert page.locator('.lex-detail-panel').count()==1
   assert page.locator('.lex-stack > .lex-column-list').count()==1
   # Every property uses the shared detail row, type rail and column pin.
   assert page.locator('.lex-multi-number').count()==0
   names=page.locator('.lex-detail-field-label').all_text_contents()
   assert [name.rstrip('?').strip() for name in names]==['Stage','Flags','Main camera','Secondary camera'],names
   assert page.locator('.lex-detail-field .lex-info-help').count()==4
   assert page.locator('.lex-detail-field .lex-column-pin').count()==4
   assert page.locator('.lex-detail-field').evaluate_all('fields=>fields.every(f=>f.dataset.lexType==="INT")')
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-encounter-slots.png'))
   assert page.locator('.lex-detail-panel input').evaluate_all('inputs=>inputs.every(input=>input.getBoundingClientRect().right<=input.closest(".lex-detail-panel").getBoundingClientRect().right)')
  dimmed=page.locator('.lex-row-disabled').first.locator('.lex-column-list-cell:not([data-column-key="enabled"])').evaluate_all('(cells)=>cells.map(c=>[c.dataset.columnKey,c.children.length&&getComputedStyle(c.firstElementChild).opacity])')
  assert all(float(opacity)==.45 for key,opacity in dimmed),dimmed
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-encounter-slots.png'))
  with tempfile.TemporaryDirectory(prefix='lexeditor-encounter-properties-') as project, FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
   page.set_viewport_size({'width':1600,'height':950})
   page.goto(session.url)
   page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=90000)
   page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')",timeout=30000)
   page.evaluate("state.encountersTab='formations';navigate('encounters')")
   field=page.locator('.lex-detail-field').filter(has=page.get_by_label('Formation stage',exact=True))
   field.hover()
   field.get_by_role('button',name='Pin Stage column',exact=True).click()
   page.locator('.ff8-record-list .lex-column-list-head-cell[data-column-key="stageId"]').wait_for(timeout=10000)
   field=page.locator('.lex-detail-field').filter(has=page.get_by_label('Formation stage',exact=True))
   field.hover()
   assert field.get_by_role('button',name='Unpin Stage column',exact=True).get_attribute('aria-pressed')=='true'
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-encounter-properties.png'))
  browser.close()
 print('Encounter slots: selection, disabled state, numeric edits, level rules and width bounds passed.')
if __name__=='__main__':main()
