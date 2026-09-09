"""One-shot FF7 master-list information-density polish."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
editor=root/'games/ff7/editor.html'
text=editor.read_text(encoding='utf-8')
old='''  const MASTER_SUMMARY_FIELDS={
    characters:[["level","Lv"],["maxHp","HP"],["maxMp","MP"]],
    recruits:[["level","Lv"],["maxHp","HP"],["maxMp","MP"]],
    commands:[["initialCursorAction","Action"]],
    playerAttacks:[["mpCost","MP"],["attackPower","Power"],["damageCalculationId","Formula"]],
    limitBreaks:[["mpCost","MP"],["attackPower","Power"],["damageCalculationId","Formula"]],
    items:[["attackPower","Power"],["damageCalculationId","Formula"]],
    weapons:[["attackStrength","Attack"],["accuracyRate","Hit"],["growthRate","AP growth"]],
    armor:[["defense","Defense"],["magicDefense","M.Def"],["growthRate","AP growth"]],
    accessories:[["specialEffect","Effect"]],
    materia:[["level5Ap","Master AP"],["materiaType","Behavior"]],
    materiaEquipEffects:[["hpPercent","HP %"],["mpPercent","MP %"]],
    enemies:[["level","Lv"],["hp","HP"],["experience","EXP"]],
    enemyAttacks:[["cost","MP"],["power","Power"],["formula","Formula"]],
    shops:[["type","Type"],["count","Slots"]],
    prices:[["price","Price"]],
    initialState:[["gil","Gil"]],
    initialInventory:[["amount","Qty"]],
    initialMateria:[["ap","AP"]],
    stolenMateria:[["ap","AP"]],
    magicOrder:[["menuGroup","Section"],["position","Pos"]],
    itemSortOrder:[["position","Sort"]],
    materiaPriority:[["priority","Priority"]],
    audioMixing:[["volume","Volume"],["pan","Pan"]],
    apMultiplier:[["multiplier","Multiplier"]],
  };
'''
new='''  const MASTER_SUMMARY_FIELDS={
    characters:[["level","LV"],["maxHp","HP"],["maxMp","MP"]],
    recruits:[["level","LV"],["maxHp","HP"],["maxMp","MP"]],
    commands:[["initialCursorAction","ACTION"]],
    playerAttacks:[["mpCost","MP"],["attackPower","PWR"],["damageCalculationId","CALC"]],
    limitBreaks:[["mpCost","MP"],["attackPower","PWR"],["damageCalculationId","CALC"]],
    items:[["attackPower","PWR"],["damageCalculationId","CALC"]],
    weapons:[["attackStrength","ATK"],["accuracyRate","HIT"],["growthRate","AP"]],
    armor:[["defense","DEF"],["magicDefense","M.DEF"],["growthRate","AP"]],
    accessories:[["specialEffect","FX"]],
    materia:[["level5Ap","M.AP"],["materiaType","TYPE"]],
    materiaEquipEffects:[["hpPercent","HP%"],["mpPercent","MP%"]],
    enemies:[["level","LV"],["hp","HP"],["experience","EXP"]],
    enemyAttacks:[["cost","MP"],["power","PWR"],["formula","CALC"]],
    shops:[["type","TYPE"],["count","SLOTS"]],
    prices:[["price","PRICE"]],
    initialState:[["gil","GIL"]],
    initialInventory:[["amount","QTY"]],
    initialMateria:[["ap","AP"]],
    stolenMateria:[["ap","AP"]],
    magicOrder:[["menuGroup","MENU"],["position","POS"]],
    itemSortOrder:[["position","SORT"]],
    materiaPriority:[["priority","ORDER"]],
    audioMixing:[["volume","VOL"],["pan","PAN"]],
    apMultiplier:[["multiplier","RATE"]],
  };
'''
if text.count(old)!=1: raise SystemExit(f'master summary marker count {text.count(old)}')
text=text.replace(old,new)
old='''  function derivedSummaryColumns(){
    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return[{key:"derived:aiScripts",label:"Scripts",sortable:true,grow:.55,render:row=>`${aiUsedCount(row)}/16`}];
    if(state.tab==="growthCurves")return[{key:"derived:growthKind",label:"Type",sortable:true,grow:.65,render:row=>({primary:"Primary",hp:"HP",mp:"MP",exp:"EXP"}[growthCurveKind(row)])}];
    if(state.tab==="encounters")return[{key:"derived:encounterEnemies",label:"Enemies",sortable:true,grow:.55,render:row=>derivedListValue(row,"derived:encounterEnemies")}];
    if(["texts","exeText"].includes(state.tab))return[{key:"derived:textLength",label:"Chars",sortable:true,grow:.5,render:row=>derivedListValue(row,"derived:textLength")}];
    return[];
  }
  function summaryColumns(){
    const fields=(MASTER_SUMMARY_FIELDS[state.tab]||[]).flatMap(([fieldKey,label],index)=>{
      const field=fieldByKey(fieldKey);if(!field)return[];
      return[{key:`value:${fieldKey}`,label,sortable:true,grow:.65,pinned:index>=2?false:true,render:row=>{const full=semanticListValue(row,field);return el("span",{title:full},compactListValue(full))}}];
    });
'''
new='''  function derivedSummaryColumns(){
    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return[{key:"derived:aiScripts",label:"AI",help:"Battle-AI event scripts used out of the sixteen available hooks.",sortable:true,grow:.42,render:row=>`${aiUsedCount(row)}/16`}];
    if(state.tab==="growthCurves")return[{key:"derived:growthKind",label:"TYPE",help:"What this growth curve controls.",sortable:true,grow:.48,render:row=>({primary:"Primary",hp:"HP",mp:"MP",exp:"EXP"}[growthCurveKind(row)])}];
    if(state.tab==="encounters")return[{key:"derived:encounterEnemies",label:"FOES",help:"Number of non-empty enemy slots in this formation.",sortable:true,grow:.42,render:row=>derivedListValue(row,"derived:encounterEnemies")}];
    if(["texts","exeText"].includes(state.tab))return[{key:"derived:textLength",label:"CHARS",help:"Decoded character count for this text record.",sortable:true,grow:.42,render:row=>derivedListValue(row,"derived:textLength")}];
    return[];
  }
  function summaryColumns(){
    const explained=new Set(["CALC","FX","M.AP","TYPE","MENU","ORDER","RATE"]);
    const fields=(MASTER_SUMMARY_FIELDS[state.tab]||[]).flatMap(([fieldKey,label],index)=>{
      const field=fieldByKey(fieldKey);if(!field)return[];
      return[{key:`value:${fieldKey}`,label,help:explained.has(label)?field.label:null,sortable:true,grow:.48,pinned:index>=2?false:true,render:row=>{const full=semanticListValue(row,field);return el("span",{title:full},compactListValue(full))}}];
    });
'''
if text.count(old)!=1: raise SystemExit(f'summary columns marker count {text.count(old)}')
text=text.replace(old,new)
old='''      ...(category()?.descriptionEditable&&!summaries.length?[{key:"description",label:"Description",sortable:true,grow:3,pinned:false,render:row=>el("span",{title:row.description},row.description)}]:[]),
'''
new='''      ...(category()?.descriptionEditable&&!summaries.length?[{key:"description",label:"DESC",help:"In-game description text",sortable:true,grow:3,pinned:false,render:row=>el("span",{title:row.description},row.description)}]:[]),
'''
if text.count(old)!=1: raise SystemExit(f'description summary marker count {text.count(old)}')
text=text.replace(old,new)
editor.write_text(text,encoding='utf-8')

test=root/'tools/verify_ff7_rendered_neutral.py'
tests=test.read_text(encoding='utf-8')
# This old assertion was intentionally checking the master summary header, not
# the detail label. Keep the contract but expect the compact scan label.
old_formula='self.assertGreaterEqual(self.page.get_by_text("Formula", exact=True).count(), 1)'
new_formula='self.assertGreaterEqual(self.page.get_by_text("CALC", exact=True).count(), 1)'
if tests.count(old_formula)!=1: raise SystemExit(f'old Formula assertion count {tests.count(old_formula)}')
tests=tests.replace(old_formula,new_formula)
marker='target.RenderedTests.open = open_with_neutral\n'
if tests.count(marker)!=1: raise SystemExit('rendered insertion marker missing')
addition='''def test_master_summary_headers_stay_single_line_at_narrow_width(self):
    self.install(); self.open(); self.page.set_viewport_size({"width":900,"height":620})
    for group in ("characters","items","weapons","armor","materia","playerAttacks","enemies","encounters"):
        with self.subTest(group=group):
            self.navigate(group); self.page.wait_for_timeout(40)
            clipped=self.page.locator('.ff7-table .lex-column-list-head-cell .header-label').evaluate_all("""labels=>labels.filter(label=>label.scrollWidth>label.clientWidth+1).map(label=>label.textContent.trim())""")
            self.assertEqual(clipped,[],(group,clipped))
    self.originals_unchanged()


'''
tests=tests.replace(marker,addition+marker)
assign='target.RenderedTests.test_small_fixed_datasets_do_not_stretch_or_overlap = test_small_fixed_datasets_do_not_stretch_or_overlap\n'
if tests.count(assign)!=1: raise SystemExit('assignment marker missing')
tests=tests.replace(assign,assign+'target.RenderedTests.test_master_summary_headers_stay_single_line_at_narrow_width = test_master_summary_headers_stay_single_line_at_narrow_width\n')
test.write_text(tests,encoding='utf-8')
