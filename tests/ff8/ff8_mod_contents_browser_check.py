"""Saved enemy edits and changed-value highlighting."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
def main():
 source=plugin_ui('ff8')
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);page=browser.new_page()
  page.route('http://fixture/',lambda r:r.fulfill(body='<main></main>',content_type='text/html'));page.goto('http://fixture/')
  page.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  page.add_script_tag(content="""
const signature=JSON.stringify,editableDatasets=['enemies','enemyTables'];
const state={modOnly:true,activeSource:'mine',data:{enemies:{rows:[{id:1},{id:2},{id:3}]},enemyTables:{rows:[{id:1,percent:50},{id:2,percent:100},{id:3,percent:100}]}},vanilla:{enemies:{rows:[{id:1},{id:2},{id:3}]},enemyTables:{rows:[{id:1,percent:100},{id:2,percent:100},{id:3,percent:100}]}}};
state.base=structuredClone(state.data);
"""+source[source.index('  function modOnlySpec(view)'):source.index('  function dirtyCount()')])
  assert page.evaluate("state.data.enemies.rows.filter(modOnlySpec('enemies').changed).map(r=>r.id)")==[1]
  page.evaluate('state.data.enemyTables.rows[1].percent=80')
  assert page.evaluate("state.data.enemies.rows.filter(modOnlySpec('enemies').changed).map(r=>r.id)")==[1,2]
  page.evaluate("""()=>{window.value=80;window.control=LexeditorUI.provenanceControl({control:LexeditorUI.el('input',{value:80}),current:()=>value,vanilla:100,apply:v=>value=v});document.querySelector('main').append(control)}""")
  assert page.locator('.lex-value-modified').count()==1
  page.evaluate('value=100;control.refreshReference()')
  assert page.locator('.lex-value-modified').count()==0
  page.evaluate("""()=>{
    state.pages={weapons:0};state.modOnly=false;
    state.data.weapons={rows:[{id:0,name:'Revolver',fields:[{field:'hit_rate',value:100}]},
      {id:1,name:'Valiant',fields:[{field:'hit_rate',value:90}]}]};
    state.vanilla.weapons=structuredClone(state.data.weapons);
    state.data.weapons.rows[0].fields[0].value=110;
    state.base.weapons=structuredClone(state.data.weapons.rows);
    document.documentElement.style.setProperty('--lex-accent-ink','#ee2277');
    document.querySelector('main').style.cssText='height:600px;display:flex';
    window.render=()=>{const U=LexeditorUI;document.querySelector('main').replaceChildren(U.pagedListDetail({
      rows:state.data.weapons.rows,key:r=>r.id,slots:true,pageSize:10,selected:0,
      modOnly:modOnlySpec('weapons'),splitKey:'weapon-mod-test',
      master:view=>U.columnList({rows:view.rows,key:r=>r.id,selected:view.selected,select:view.select,
        columns:[{key:'id',label:'ID'},{key:'name',label:'Name'}]}),
      detail:row=>U.detailPanel({title:row.name,body:'Weapon properties'})}))};render();
  }""")
  modified=page.locator('.lex-list-row.lex-record-modified')
  assert modified.count()==1
  assert modified.get_attribute('data-key')=='0'
  assert modified.locator('.lex-column-cell-content').last.evaluate('n=>getComputedStyle(n).color')=='rgb(238, 34, 119)'
  page.get_by_role('checkbox',name='Mod contents only',exact=True).check()
  assert page.locator('.lex-list-row').count()==1
  page.get_by_role('checkbox',name='Mod contents only',exact=True).uncheck()
  page.wait_for_function("document.querySelectorAll('.lex-list-row').length===2")
  page.evaluate('state.data.weapons.rows[1].fields[0].value=95;LexeditorUI.refreshReferences()')
  assert modified.count()==2
  import tempfile
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-weapon-mod-highlights.png'))
  page.evaluate('state.data.weapons.rows[0].fields[0].value=100;LexeditorUI.refreshReferences()')
  assert modified.count()==1 and modified.get_attribute('data-key')=='1'
  page.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  page.add_script_tag(content="""
const {el,detailSection,infoHelp,unitField}=LexeditorUI;
const conceptIcon=()=>null,enemyTableSource=control=>control,shell={refresh:()=>{}};
state.data.enemyTables.choices={statuses:[{id:0,name:'Haste'},{id:1,name:'Reflect'}]};
"""+source[source.index('  const enemyDefencePrevious='):source.index('  const enemyScanElementNames=')])
  page.evaluate("""()=>{document.querySelector('main').style.cssText='display:block;width:360px';document.querySelector('main').replaceChildren(enemyDefenceSection({tables:{statusDefence:[{slot:0,percent:0},{slot:1,percent:0}]}},'statusDefence','STATUS DEFENCE'));}""")
  page.wait_for_timeout(200)
  assert page.locator('.enemy-status-fallback').all_text_contents()==['\u25a7','\u25a7']
  # Defence tiles are the shared iconValue: its toggle sits inside its tile,
  # and the section does not overflow a narrow panel.
  assert page.locator('.lex-icon-value-toggle').first.evaluate('''e=>{const t=e.closest('.lex-icon-value').getBoundingClientRect(),r=e.getBoundingClientRect();
    return r.height>0&&r.top>=t.top-1&&r.bottom<=t.bottom+1}''')
  assert page.locator('.lex-detail-section').first.evaluate('e=>e.scrollWidth<=e.clientWidth+2')
  import tempfile
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-defence-layout.png'))
  browser.close()
 print('Saved and unsaved enemy-table edits match vanilla comparison; reverted values lose the modified highlight.')
if __name__=='__main__':main()
