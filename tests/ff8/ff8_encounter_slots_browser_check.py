"""Headless encounter slot selection, bounds and edit checks."""
import re,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
def main():
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
const row={id:0,slots:Array.from({length:8},(_,slot)=>({slot,enemyName:slot?'Dummy':'G-Soldier',enemyId:0,enabled:slot===0,visible:true,loaded:true,targetable:true,x:1100,y:0,z:-3300,level:255}))};
const renderEncounters=()=>document.querySelector('main').replaceChildren(encounterDetail(row));
const render=renderEncounters;
"""+functions+"renderEncounters();")
  assert page.locator('.lex-column-list-row').count()==8
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
   # The formation's four header bytes are ordinary properties, as the panel
   # below them is: a name on the left, a box on the right, a help bubble beside
   # the name. They were drawn by the shared row component in its stacked form,
   # which put each name over its box and, with no help passed, left the row with
   # no bubbles at all at any width.
   assert page.locator('.lex-detail-parts-stacked').count()==0
   names=page.locator('.lex-tile-grid .lex-detail-field .lex-detail-field-label-text').all_text_contents()
   assert [name.strip() for name in names]==['Stage','Flags','Main camera','Secondary camera'],names
   assert page.locator('.lex-tile-grid .lex-detail-field .lex-info-help').count()==4
   beside=page.evaluate("""() => [...document.querySelectorAll('.lex-tile-grid .lex-detail-field')].map(field => {
     const label=field.querySelector('.lex-detail-field-label').getBoundingClientRect();
     const control=field.querySelector('.lex-detail-field-control').getBoundingClientRect();
     return label.right <= control.left + 1;})""")
   assert all(beside),beside
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-encounter-slots.png'))
  browser.close()
 print('Encounter slots: selection, disabled state, numeric edits, level rules and width bounds passed.')
if __name__=='__main__':main()
