"use strict";
function troopEditKey(row){return troopRowKey(row);}
function newTroopDraft(row){return {recordIndex:row.recordIndex,originalId:row.id,id:row.id,fields:{},stats:{...row.stats},flagValue:row.flagValue};}
function troopDraft(row){return state.troopEdits[troopEditKey(row)]||newTroopDraft(row);}
function troopValue(row,key){return troopDraft(row).fields[key]??row.fields[key];}
function setTroopField(row,key,value){
 const recordKey=troopEditKey(row),draft=state.troopEdits[recordKey] ||= newTroopDraft(row);
 if(value===row.fields[key])delete draft.fields[key];else draft.fields[key]=value;
 const kept=Object.keys(draft.fields).length||Object.keys(draft.rawStats||{}).length?draft:null;
 if(!kept)delete state.troopEdits[recordKey];
 shell.refresh();return kept;
}
function troopStatIssue(raw){
 const value=Number(raw);
 return String(raw).trim()===""||!Number.isInteger(value)||value<0||value>255?"Enter a whole number from 0 to 255.":"";
}
function setTroopStat(row,key,raw){
 const recordKey=troopEditKey(row),draft=state.troopEdits[recordKey] ||= newTroopDraft(row);
 if(draft.statSource===undefined){draft.statSource=troopValue(row,"attributes");draft.statBase={...draft.stats};}
 draft.rawStats ||= {};
 const issue=troopStatIssue(raw);
 if(!issue&&Number(raw)===draft.statBase[key])delete draft.rawStats[key];else draft.rawStats[key]=raw;
 if(!issue){
  draft.stats[key]=Number(raw);
  let expression=draft.statSource;
  for(const [name,shift] of [["strength",0],["agility",8],["intelligence",16],["charisma",24],["level",32]]){
   if(draft.stats[name]===undefined||draft.stats[name]===draft.statBase[name])continue;
   const mask=255n<<BigInt(shift),value=BigInt(draft.stats[name])<<BigInt(shift);
   expression=`((${expression}) & ~0x${mask.toString(16)}) | 0x${value.toString(16)}`;
  }
  setTroopField(row,"attributes",expression);
 }else shell.refresh();
 return issue;
}
function preflightTroopStats(){
 for(const draft of Object.values(state.troopEdits))for(const [key,raw] of Object.entries(draft.rawStats||{})){
  const issue=troopStatIssue(raw);if(issue)throw new Error(`${draft.originalId} / ${key}: ${issue}`);
 }
}
function troopFields(row){
 if(row.problem)return [el("p",{role:"alert"},row.problem)];
 const disabled=state.activeSource!=="mine",body=[];
 const field=(label,control)=>LexeditorUI.detailField({label,control});
 for(const key of ["name","plural"])body.push(field(key,el("input",{value:troopValue(row,key),disabled,oninput:e=>setTroopField(row,key,e.target.value)})));
 const faction=el("select",{disabled,onchange:e=>setTroopField(row,"faction",e.target.value)},
 ...[...new Set([troopValue(row,"faction"),...(state.troops.factions||[])])].map(id=>el("option",{value:id},id)));
 faction.value=troopValue(row,"faction");body.push(field("Faction",faction));
 for(const [key,shift] of [["strength",0],["agility",8],["intelligence",16],["charisma",24],["level",32]]){
  if(row.stats[key]===undefined)continue;
  const value=troopDraft(row).rawStats?.[key]??troopDraft(row).stats[key];
  const input=el("input",{type:"number",required:true,min:0,max:255,step:1,disabled,value,
   "data-lex-validate-number":"true",oninput:e=>{if(!e.target.disabled)e.target.setCustomValidity(setTroopStat(row,key,e.target.value));}});
  input.setCustomValidity(troopStatIssue(value));body.push(field(key,input));
 }
 if(row.flagValue!==null){
  const setFlag=(mask,on)=>{
   const current=troopValue(row,"flags"),before=troopDraft(row).flagValue;
   const draft=setTroopField(row,"flags",on?`(${current}) | ${mask}`:`(${current}) & ~${mask}`);
   if(draft)draft.flagValue=on?before|mask:before&~mask;
  };
  const type=el("select",{disabled,onchange:e=>{
   const value=Number(e.target.value),before=troopDraft(row).flagValue;
   const draft=setTroopField(row,"flags",`((${troopValue(row,"flags")}) & ~15) | ${value}`);
   if(draft)draft.flagValue=(before&~15)|value;
  }},...Object.entries(state.troops.types||{}).map(([name,value])=>el("option",{value},name.replace("tf_",""))));
  type.value=String(troopDraft(row).flagValue&15);body.push(field("Type",type));
  body.push(LexeditorUI.detailSection({title:"Flags",body:Object.entries(state.troops.flags||{}).map(([name,mask])=>field(name.replace("tf_","").replaceAll("_"," "),el("input",{type:"checkbox",disabled,checked:!!(troopDraft(row).flagValue&mask),onchange:e=>setFlag(mask,e.target.checked)})))}));
 }
 const inventory=String(troopValue(row,"inventory"));
 if(/^\[\s*(?:itm_\w+\s*,?\s*)*\]$/.test(inventory)){
  const items=inventory.match(/itm_\w+/g)||[];
  const saveItems=next=>{setTroopField(row,"inventory",`[${next.join(", ")}]`);render();};
  const equipment=items.map((id,index)=>{
   const select=el("select",{disabled,onchange:e=>{items[index]=e.target.value;saveItems(items);}},...[...new Set([id,...state.troops.items])].map(value=>el("option",{value},value)));
   select.value=id;
   return field(`Slot ${index+1}`,el("div",{style:"display:flex;gap:6px;min-width:0"},select,el("button",{disabled,onclick:()=>saveItems(items.filter((_,i)=>i!==index))},"Remove")));
  });
  equipment.push(el("button",{disabled:disabled||!state.troops.items.length,onclick:()=>saveItems([...items,state.troops.items[0]])},"Add equipment"));
  body.push(LexeditorUI.detailSection({title:"Equipment",body:equipment}));
 }
 const advanced=el("details",{},el("summary",{},"Source expressions"));
 for(const key of ["scene","inventory","attributes","proficiencies","skills","face1","face2","image"]){
  if(row.fields[key]===undefined)continue;
  advanced.append(field(key,el("textarea",{rows:2,disabled,style:"width:100%;box-sizing:border-box",oninput:e=>setTroopField(row,key,e.target.value)},troopValue(row,key))));
 }
 body.push(advanced);return body;
}
function troopEditorPanel(row){return LexeditorUI.detailPanel({title:LexeditorUI.el("h2",{class:"lex-detail-panel-title"},bitmapText(row.name,24)),identity:row.id,body:troopFields(row)});}
