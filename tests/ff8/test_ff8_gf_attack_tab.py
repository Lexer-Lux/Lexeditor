import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from test_shared_ui_feedback import page, framework, ROOT


def test_attack_fields_move_without_losing_edits(page):
    schema=json.loads((ROOT/'plugins/ff8/schema/kernel_section_fields.json').read_text(encoding='utf-8'))
    fields=next(s['fields'] for s in schema.values() if any(f['name']=='gf_hp_modifier_1' for f in s['fields']))
    rows=[{'field':f['name'],'group':f['group'],'label':f.get('label',f['name']),'value':1} for f in fields]
    source=(ROOT/'plugins/ff8/party.js').read_text(encoding='utf-8')
    routing=source[source.index('  const GF_ATTACK_FIELDS'):source.index('  function gfEntityLabel')]
    panel=source[source.index('  function gfCenterPanel'):source.index('  function fieldGroups')]
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.add_script_tag(content='''
      const {tabbedPanel,el}=LexeditorUI;
      const state={};
      const row={id:0,fields:ROWS};
      function gfPanel(title,fields,row,kind){return el('div',{'data-gf-panel':kind},...fields.map(field=>
        LexeditorUI.detailField({label:field.label,control:el('input',{type:'number',value:field.value,
          'aria-label':field.label,onchange:e=>field.value=Number(e.target.value)})})));}
      const startingFields=()=>el('div',{},'Initial GF state');
      function renderGFs(){document.querySelector('main').replaceChildren(gfCenterPanel(row,gfFieldsByPanel(row),{fields:[],id:0}));}
    '''.replace('ROWS',json.dumps(rows))+routing+panel+'renderGFs();')
    assert page.get_by_role('spinbutton',name='GF power',exact=True).count()==0
    assert page.get_by_role('spinbutton',name='GF HP modifier 1',exact=True).count()==1
    page.get_by_role('tab',name=re.compile('^Attack',re.I)).click()
    assert page.get_by_role('spinbutton',name='GF HP modifier 1',exact=True).count()==0
    assert page.get_by_role('spinbutton',name='GF summon status acc.',exact=True).count()==1
    power=page.get_by_role('spinbutton',name='GF power',exact=True)
    power.fill('45');power.blur()
    page.get_by_role('tab',name=re.compile('^Defaults',re.I)).click()
    page.get_by_text('Initial GF state',exact=True).wait_for()
    page.get_by_role('tab',name=re.compile('^Attack',re.I)).click()
    assert power.input_value()=='45'
    assert page.evaluate('''()=>{
      const routed=gfFieldsByPanel(row),all=[...routed.values()].flat();
      return all.length===row.fields.length && new Set(all).size===all.length &&
        !routed.get('Abilities').some(f=>f.field==='ability1_unlocker');
    }''')
