"use strict";
function troopEditKey(row){return troopRowKey(row);}
function newTroopDraft(row){return {recordIndex:row.recordIndex,originalId:row.id,id:row.id,fields:{},stats:{...row.stats},flagValue:row.flagValue};}
function troopDraft(row){return state.troopEdits[troopEditKey(row)]||newTroopDraft(row);}
function troopValue(row,key){return troopDraft(row).fields[key]??row.fields[key];}
function setTroopField(row,key,value){
 const recordKey=troopEditKey(row),draft=state.troopEdits[recordKey] ||= newTroopDraft(row);
 if(value===row.fields[key])delete draft.fields[key];else draft.fields[key]=value;
 const kept=Object.keys(draft.fields).length?draft:null;
 if(!kept)delete state.troopEdits[recordKey];
 shell.refresh();return kept;
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
  body.push(field(key,el("input",{type:"number",min:0,max:255,step:1,disabled,value:troopDraft(row).stats[key],oninput:e=>{
   const n=Number(e.target.value);if(!Number.isInteger(n)||n<0||n>255)return;
   const mask=255n<<BigInt(shift),v=BigInt(n)<<BigInt(shift);
   const draft=setTroopField(row,"attributes",`((${troopValue(row,"attributes")}) & ~0x${mask.toString(16)}) | 0x${v.toString(16)}`);
   if(draft)draft.stats[key]=n;
  }})));
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
function troopEditorPanel(row){return LexeditorUI.detailPanel({title:row.name,identity:row.id,body:troopFields(row)});}
