"""One-shot FF7 UI finishing pass; removed automatically after verified landing."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
editor_path=root/'games/ff7/editor.html'
text=editor_path.read_text(encoding='utf-8')
old='''  function recordDetail(row){
    if(state.tab==="growthCurves")return growthCurveDetail(row);
    if(state.tab==="growthBonuses")return growthBonusDetail(row);
    if(state.tab==="materia")return materiaDetail(row);
    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return aiDetail(row);
    if(state.tab==="characters")return characterDetail(row);
    if(["weapons","armor","accessories"].includes(state.tab))return equipmentDetail(row);
    if(state.tab==="enemies")return enemyDetail(row);
    if(state.tab==="encounters")return formationDetail(row);
    if(state.tab==="shops")return shopDetail(row);
    if(["fieldEncounters","worldEncounters"].includes(state.tab))return weightedEncounterDetail(row);
    return conceptPanel(row,ordinarySections(row));
  }
'''
new='''  function settingsConcept(row,entries,label){
    const rows=entries.map(([key,name],index)=>({key:index,field:fieldByKey(key),name})).filter(entry=>entry.field);
    return conceptTable(rows,"minmax(135px,.9fr) minmax(165px,1.25fr)",[
      {key:"setting",label:"Setting",render:entry=>entry.name||entry.field.label},
      {key:"value",label:"Value",render:entry=>semanticControl(row,entry.field)},
    ],label);
  }
  function newGameStateDetail(row){
    const party=[["party1","Slot 1"],["party2","Slot 2"],["party3","Slot 3"]].map(([key,name],index)=>({key:index+1,name,field:fieldByKey(key)}));
    return conceptPanel(row,[
      detailSection({title:"STARTING PARTY",attrs:{"data-concept":"new-game-setup"},help:infoHelp("These character identities are copied into a newly initialized save.  Existing saves are not rewritten."),body:conceptTable(party,"70px minmax(180px,1fr)",[
        {key:"slot",label:"Slot",render:entry=>entry.name},
        {key:"character",label:"Character",render:entry=>semanticControl(row,entry.field)},
      ],"New-game party")}),
      detailSection({title:"STARTING RESOURCES",body:settingsConcept(row,[["gil","Gil"]],"New-game resources")}),
    ]);
  }
  function attackDetail(row){
    const enemy=state.tab==="enemyAttacks";
    const keys=enemy?{
      name:"name",accuracy:"accuracy",cost:"cost",formula:"formula",power:"power",target:"target",condition:"condition",status:"statusChance",statuses:"statuses",elements:"elements",additional:"additionalEffect",modifier:"modifier",special:"specialFlags"
    }:{
      accuracy:"accuracyRate",cost:"mpCost",formula:"damageCalculationId",power:"attackPower",target:"targetData",condition:"conditionSubmenu",status:"statusChange",statuses:"statusFlags",elements:"elementFlags",additional:"additionalEffects",modifier:"additionalEffectsModifier",special:"specialAttackFlags"
    };
    const omit=new Set(Object.values(keys));
    const body=[];
    if(keys.name&&fieldByKey(keys.name))body.push(detailSection({title:"ATTACK NAME",attrs:{"data-concept":"attack-name"},body:el("div",{style:"padding:10px;min-width:0"},semanticControl(row,fieldByKey(keys.name)))}));
    body.push(detailSection({title:"COST & DAMAGE",attrs:{"data-concept":"attack-core"},body:settingsConcept(row,[
      [keys.accuracy,"Accuracy"],[keys.cost,"MP cost"],[keys.formula,"Damage / healing formula"],[keys.power,"Power"],
    ],"Attack cost and damage")}));
    body.push(detailSection({title:"TARGETING & STATUS",attrs:{"data-concept":"attack-effects"},body:settingsConcept(row,[
      [keys.target,"Targeting"],[keys.condition,"Condition"],[keys.status,"Status change"],[keys.statuses,"Statuses affected"],[keys.elements,"Elements"],
    ],"Attack targeting and status")}));
    body.push(detailSection({title:"EXTRA BEHAVIOR",body:settingsConcept(row,[
      [keys.additional,"Additional behavior"],[keys.modifier,"Effect modifier"],[keys.special,"Special properties"],
    ],"Attack extra behavior")}));
    body.push(...ordinarySections(row,omit));
    return conceptPanel(row,body);
  }
  function materiaEquipEffectDetail(row){
    const stats=[["strength","Strength"],["vitality","Vitality"],["magic","Magic"],["spirit","Spirit"],["dexterity","Dexterity"],["luck","Luck"]].map(([key,name],index)=>({key:index,name,field:fieldByKey(key)}));
    const resources=[["hpPercent","HP"],["mpPercent","MP"]].map(([key,name],index)=>({key:index,name,field:fieldByKey(key)}));
    return conceptPanel(row,[
      detailSection({title:"STAT CHANGES",attrs:{"data-concept":"materia-equip-effect"},help:infoHelp("This shared template is selected by Materia equip-effect IDs. Values are the stat changes applied while that Materia is equipped."),body:conceptTable(stats,"minmax(120px,.9fr) minmax(120px,1fr)",[
        {key:"stat",label:"Stat",render:entry=>entry.name},{key:"change",label:"Change",render:entry=>semanticControl(row,entry.field)},
      ],"Materia equip-effect stat changes")}),
      detailSection({title:"HP / MP",body:conceptTable(resources,"minmax(120px,.9fr) minmax(120px,1fr)",[
        {key:"resource",label:"Resource",render:entry=>entry.name},{key:"change",label:"Percent change",render:entry=>semanticControl(row,entry.field)},
      ],"Materia equip-effect HP and MP changes")}),
    ]);
  }
  function recruitDetail(row){
    const body=[];
    const name=fieldByKey("name");if(name)body.push(detailSection({title:"INITIAL NAME",attrs:{"data-concept":"recruit-name"},body:el("div",{style:"padding:10px;min-width:0"},semanticControl(row,name))}));
    body.push(detailSection({title:"STARTING CHARACTER",attrs:{"data-concept":"recruit-loadout"},body:settingsConcept(row,[
      ["storedId","Character identity"],["weaponId","Weapon"],["armorId","Armor"],["accessoryId","Accessory"],["rowByte","Row"],["characterFlags","Battle mood"],
    ],"Recruit starting loadout")}));
    body.push(detailSection({title:"PROGRESSION",body:settingsConcept(row,[["level","Level"],["currentExp","Experience"],["expToNextLevel","EXP to next level"],["levelProgress","Level progress"]],"Recruit progression")}));
    const stats=["strength","vitality","magic","spirit","dexterity","luck"].map((key,index)=>({key:index,name:key[0].toUpperCase()+key.slice(1),value:fieldByKey(key),bonus:fieldByKey(`${key}Bonus`)}));
    body.push(detailSection({title:"CORE STATS",attrs:{"data-concept":"recruit-stats"},body:conceptTable(stats,"minmax(90px,.8fr) minmax(85px,.7fr) minmax(85px,.7fr)",[
      {key:"stat",label:"Stat",render:entry=>entry.name},{key:"start",label:"Start",render:entry=>semanticControl(row,entry.value)},{key:"bonus",label:"Bonus",render:entry=>semanticControl(row,entry.bonus)},
    ],"Recruit core stats")}));
    const resources=[
      {key:"hp",name:"HP",current:fieldByKey("currentHp"),base:fieldByKey("baseHp"),maximum:fieldByKey("maxHp")},
      {key:"mp",name:"MP",current:fieldByKey("currentMp"),base:fieldByKey("baseMp"),maximum:fieldByKey("maxMp")},
    ];
    body.push(detailSection({title:"HP / MP",body:conceptTable(resources,"64px repeat(3,minmax(70px,.8fr))",[
      {key:"resource",label:"Resource",render:entry=>entry.name},{key:"current",label:"Current",render:entry=>semanticControl(row,entry.current)},{key:"base",label:"Base",render:entry=>semanticControl(row,entry.base)},{key:"maximum",label:"Maximum",render:entry=>semanticControl(row,entry.maximum)},
    ],"Recruit HP and MP")}));
    body.push(detailSection({title:"STARTING LIMIT STATE",body:settingsConcept(row,[["limitLevel","Limit level"],["limitBar","Limit gauge"],["learnedLimits","Limits learned"],["killCount","Kill count"],["limit1Uses","Level 1 uses"],["limit2Uses","Level 2 uses"],["limit3Uses","Level 3 uses"]],"Recruit Limit state")}));
    for(const equipment of ["weapon","armor"]){
      const entries=Array.from({length:8},(_,i)=>({key:i+1,materia:fieldByKey(`${equipment}Materia${i}`),ap:fieldByKey(`${equipment}MateriaAp${i}`)}));
      body.push(detailSection({title:`STARTING ${equipment.toUpperCase()} MATERIA`,attrs:{"data-concept":`recruit-${equipment}-materia`},body:conceptTable(entries,"44px minmax(150px,1.3fr) minmax(90px,.7fr)",[
        {key:"slot",label:"Slot",numberedId:true,render:entry=>entry.key},{key:"materia",label:"Materia",render:entry=>semanticControl(row,entry.materia)},{key:"ap",label:"AP",render:entry=>semanticControl(row,entry.ap)},
      ],`Recruit ${equipment} Materia`)}));
    }
    return conceptPanel(row,body);
  }
  function textRecordDetail(row){
    const field=fieldByKey("text"),control=semanticControl(row,field),area=control.matches?.("textarea")?control:control.querySelector?.("textarea");
    control.style.width="100%";if(area){area.rows=10;area.style.width="100%";area.style.minHeight="12rem"}
    const isKernel=state.tab==="texts",section=isKernel?Math.floor(Number(row.id)/65536):null,index=isKernel?(Number(row.id)&0xFFFF):Number(row.id),chars=String(row.values.text||"").length;
    return conceptPanel(row,[
      detailSection({title:"GAME TEXT",attrs:{"data-concept":"text-editor"},help:infoHelp(semanticHelp(field)),body:el("div",{style:"padding:10px;min-width:0"},control)}),
      detailSection({title:"RECORD",body:[
        detailField({label:isKernel?"SECTION / ENTRY":"EXECUTABLE ENTRY",control:readonlyField(isKernel?`${section} / ${index}`:String(index))}),
        detailField({label:"CHARACTERS",control:readonlyField(String(chars))}),
        detailField({label:"STORAGE",control:readonlyField(row.description||"Bounded FF7 text storage; oversized edits are rejected on save.")}),
      ]}),
    ]);
  }
  function recordDetail(row){
    if(state.tab==="growthCurves")return growthCurveDetail(row);
    if(state.tab==="growthBonuses")return growthBonusDetail(row);
    if(state.tab==="materia")return materiaDetail(row);
    if(state.tab==="materiaEquipEffects")return materiaEquipEffectDetail(row);
    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return aiDetail(row);
    if(state.tab==="characters")return characterDetail(row);
    if(state.tab==="recruits")return recruitDetail(row);
    if(state.tab==="initialState")return newGameStateDetail(row);
    if(["playerAttacks","limitBreaks","enemyAttacks"].includes(state.tab))return attackDetail(row);
    if(["weapons","armor","accessories"].includes(state.tab))return equipmentDetail(row);
    if(state.tab==="enemies")return enemyDetail(row);
    if(state.tab==="encounters")return formationDetail(row);
    if(state.tab==="shops")return shopDetail(row);
    if(["fieldEncounters","worldEncounters"].includes(state.tab))return weightedEncounterDetail(row);
    if(["texts","exeText"].includes(state.tab))return textRecordDetail(row);
    return conceptPanel(row,ordinarySections(row));
  }
'''
if text.count(old)!=1: raise SystemExit(f'recordDetail marker count {text.count(old)}')
text=text.replace(old,new)
editor_path.write_text(text,encoding='utf-8')

test_path=root/'tools/verify_ff7_rendered_neutral.py'
tests=test_path.read_text(encoding='utf-8')
marker='target.RenderedTests.open = open_with_neutral\n'
if tests.count(marker)!=1: raise SystemExit(f'test marker count {tests.count(marker)}')
addition='''def test_finished_high_value_detail_views(self):
    self.install(); self.open()

    self.navigate("initialState")
    self.assertEqual(self.page.locator('[data-concept="new-game-setup"]').count(),1)
    self.assertEqual(self.page.get_by_label("New-game party", exact=True).locator("select").count(),3)

    for group in ("playerAttacks","limitBreaks","enemyAttacks"):
        with self.subTest(group=group):
            self.navigate(group)
            self.assertEqual(self.page.locator('[data-concept="attack-core"]').count(),1)
            self.assertEqual(self.page.locator('[data-concept="attack-effects"]').count(),1)

    self.navigate("materiaEquipEffects")
    self.assertEqual(self.page.locator('[data-concept="materia-equip-effect"]').count(),1)
    self.assertEqual(self.page.get_by_label("Materia equip-effect stat changes", exact=True).locator('input[type="number"]').count(),6)

    self.navigate("recruits")
    self.assertEqual(self.page.locator('[data-concept="recruit-loadout"]').count(),1)
    self.assertEqual(self.page.locator('[data-concept="recruit-stats"]').count(),1)
    self.assertEqual(self.page.get_by_label("Recruit core stats", exact=True).locator('input[type="number"]').count(),12)

    for group in ("texts","exeText"):
        with self.subTest(group=group):
            self.navigate(group)
            self.assertEqual(self.page.locator('[data-concept="text-editor"]').count(),1)
            area=self.page.locator('[data-concept="text-editor"] textarea')
            self.assertEqual(area.count(),1)
            self.assertGreaterEqual(int(area.get_attribute("rows")),10)

    self.originals_unchanged()


'''
tests=tests.replace(marker,addition+marker)
assignment='target.RenderedTests.test_refined_master_and_detail_ux = test_refined_master_and_detail_ux\n'
if assignment not in tests: raise SystemExit('assignment marker missing')
tests=tests.replace(assignment,assignment+'target.RenderedTests.test_finished_high_value_detail_views = test_finished_high_value_detail_views\n')
test_path.write_text(tests,encoding='utf-8')
