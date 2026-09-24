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
      const GF_CURVE_FIELDS=["gf_hp_modifier_1","gf_hp_modifier_2","gf_hp_modifier_3","gf_level_modifier_1","gf_level_modifier_2"];
      function gfPanel(title,fields,row,kind){return el('div',{'data-gf-panel':kind},...fields.map(field=>
        LexeditorUI.detailField({label:field.label,control:el('input',{type:'number',value:field.value,
          'aria-label':field.label,onchange:e=>field.value=Number(e.target.value)})})));}
      function gfStatGrowth(fields,rowId){
        const card=(title,names)=>el('div',{class:'lex-curve-editor','data-curve':title},
          ...names.map((name,index)=>{const field=row.fields.find(f=>f.field===name);
            return el('label',{},`${title} variable ${'ABC'[index]}`,
              el('input',{type:'number',value:field.value,'aria-label':`${title} variable ${'ABC'[index]}`,
                onchange:e=>field.value=Number(e.target.value)}))}));
        return LexeditorUI.curveGrid({columns:1},card('HP',GF_CURVE_FIELDS.slice(0,3)),card('XP',GF_CURVE_FIELDS.slice(3)));
      }
      const startingFields=()=>el('div',{},'Initial GF state');
      function renderGFs(){document.querySelector('main').replaceChildren(gfCenterPanel(row,gfFieldsByPanel(row),{fields:[],id:0}));}
    '''.replace('ROWS',json.dumps(rows))+routing+panel+'renderGFs();')
    assert page.get_by_role('tab',name=re.compile('^Leveling',re.I)).count()==1
    assert page.get_by_role('tab',name=re.compile('^Properties',re.I)).count()==0
    assert page.locator('.lex-curve-editor').count()==2
    assert page.get_by_text('LEVEL CURVES').count()==0
    assert page.locator('main .lex-detail-section').count()==0
    assert 'repeat(1,minmax(0,1fr))' in (page.locator('[data-gf-panel="general"]').get_attribute('style') or '')
    assert page.get_by_role('spinbutton',name='GF power',exact=True).count()==0
    assert page.get_by_role('spinbutton',name='Boost phase 1 length (x15)',exact=True).count()==0
    assert page.get_by_role('spinbutton',name='Boost total window (x15)',exact=True).count()==0
    hp_var=page.get_by_role('spinbutton',name='HP variable A',exact=True)
    hp_var.fill('7');hp_var.blur()
    page.get_by_role('tab',name=re.compile('^Attack',re.I)).click()
    assert page.get_by_role('spinbutton',name='GF HP modifier 1',exact=True).count()==0
    assert page.get_by_role('spinbutton',name='GF summon status acc.',exact=True).count()==1
    assert page.get_by_role('spinbutton',name='Boost phase 1 length (x15)',exact=True).count()==1
    assert page.get_by_role('spinbutton',name='Boost total window (x15)',exact=True).count()==1
    power=page.get_by_role('spinbutton',name='GF power',exact=True)
    power.fill('45');power.blur()
    boost=page.get_by_role('spinbutton',name='Boost phase 1 length (x15)',exact=True)
    boost.fill('9');boost.blur()
    page.get_by_role('tab',name=re.compile('^Leveling',re.I)).click()
    assert page.get_by_role('spinbutton',name='HP variable A',exact=True).input_value()=='7'
    page.get_by_role('tab',name=re.compile('^Defaults',re.I)).click()
    page.get_by_text('Initial GF state',exact=True).wait_for()
    page.get_by_role('tab',name=re.compile('^Attack',re.I)).click()
    assert power.input_value()=='45'
    assert boost.input_value()=='9'
    assert page.evaluate('''()=>{
      const routed=gfFieldsByPanel(row),all=[...routed.values()].flat();
      return all.length===row.fields.length && new Set(all).size===all.length &&
        !routed.get('Abilities').some(f=>f.field==='ability1_unlocker') &&
        routed.get('Attack').some(f=>f.field==='boost_param_1') &&
        routed.get('Attack').some(f=>f.field==='boost_param_2');
    }''')
