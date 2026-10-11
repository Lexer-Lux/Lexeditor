"use strict";
const {el,detailPanel,detailSection,detailField,readonlyField,infoHelp,pagedListDetail,columnList,subtabBar,
  actionRow,confirmAction,modLoaderSection,tabbedPanel,hoverable}=LexeditorUI;
const state={tab:"items",sub:"consumables",tabs:[],enemyTabs:[],attackTabs:[],rows:[],selected:null,row:null,dirty:0,pending:0,
  readOnly:true,query:"",page:0,pageSize:20,sort:{key:"id",dir:1},error:"",deployment:null,deployBusy:false,
  monsterTab:"resistances",monsterAttacks:null,tweaks:null,tweakBusy:false,
  effectTabs:[],statsTabs:[],nativeRules:null,bandForm:null,bandBusy:false,
  dataMap:{rows:[]},mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1]};
let edits=Promise.resolve(),navigation=0,recordsRequest=0,selectVisibleRecord=null;
const attackPreviews=new Map();
const key=row=>`${row.table}:${row.id}`;
async function api(path,body){
  const response=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const result=await response.json();
  if(!response.ok||result.error)throw new Error(result.error||response.statusText);
  return result;
}
const notify=error=>LexeditorUI.showAlert({title:"Dark Souls",message:error.message||String(error)});
const fieldHistory={undoStack:[],redoStack:[],applying:false,
  get canUndo(){return this.undoStack.length>0;},get canRedo(){return this.redoStack.length>0;},
  record(entry){
    if(this.applying||(!entry.edits&&entry.before===entry.after))return;
    this.undoStack.push(entry);if(this.undoStack.length>200)this.undoStack.shift();
    this.redoStack=[];shell.refresh();
  },
  async undo(){const entry=this.undoStack.pop();if(!entry)return false;this.redoStack.push(entry);await this.apply(entry,"before");return true;},
  async redo(){const entry=this.redoStack.pop();if(!entry)return false;this.undoStack.push(entry);await this.apply(entry,"after");return true;},
  async apply(entry,side){
    this.applying=true;
    try{
      await edits;
      for(const edit of entry.edits||[entry]){
        const result=await api("/api/edit",{table:edit.table,id:edit.id,field:edit.field,value:edit[side],sub:state.sub});
        state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
        if(state.row&&state.row.table===edit.table&&state.row.id===edit.id)state.row=result.row;
      }
      render();
    }catch(error){notify(error);}
    finally{this.applying=false;shell.refresh();}
  },
  clear(){this.undoStack=[];this.redoStack=[];shell.refresh();}};
document.addEventListener("keydown",event=>{
  if(!(event.ctrlKey||event.metaKey)||event.altKey)return;
  const pressed=event.key.toLowerCase();
  if(pressed!=="z"&&pressed!=="y")return;
  if(event.target.closest?.("textarea,input[type=text]:not([data-field-key])"))return;
  event.preventDefault();
  document.activeElement?.blur?.();
  setTimeout(()=>pressed==="y"||event.shiftKey?fieldHistory.redo():fieldHistory.undo(),0);
},true);
const shell=LexeditorUI.mountShell({
  host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ds1",name:"Dark Souls Remastered"},
  tabs:[{id:"items",label:"Items",help:"Edit item properties in the selected mod. Vanilla is read-only. Unknown fields stay protected. Saves do not install a mod."},
    {id:"enemies",label:"Enemies",help:"Edit reviewed monster resistances. A monster's Attacks tab lists the attack records its parameters reference. Vanilla is read-only. Save changes the mod project."},
    {id:"attacks",label:"Attacks",help:"Edit enemy attack damage. One attack record can be shared by several monsters, bosses and NPCs, so an edit changes every use of it. Vanilla is read-only. Save changes the mod project."},
    {id:"effects",label:"Effects",help:"Edit buffs, debuffs and equipment passives. A shared effect changes every item or ability using it. Unknown properties stay protected."},
    {id:"stats",label:"Stats",help:"Stat scaling and requirements for the Stats Rework. Scaling curves holds the 39 scaling graphs: weapon paths, Max HP, defense, resistances, level-up cost and level sync. Weapon scaling holds each weapon's stat requirements and scaling multipliers. A weapon's curve assignment stays read-only because its graph choices are not documented. Spell requirements holds each spell's INT and FTH requirements, slot cost and stamina cost. Full records stay in Items, and no scaling graph here covers stamina recovery or attunement slots."},
    {id:"encumbrance",label:"Encumbrance",help:"Add or merge load ranges. Each band has a movement profile and its own recovery percentage. The last band has no upper limit. Save and Apply to use your rules."},
    {id:"misc",label:"Misc."},
    {id:"tweaks",label:"Tweaks",help:"Executable tweaks are mods in the mod library. Switching one on or off saves at once; Apply then builds every enabled tweak into the installed executable together, and Restore original puts the untouched executable back."}],
  activeTab:()=>state.tab,navigate:tab=>navigate(tab),
  info:()=>navigate("info"),infoActive:()=>state.tab==="info",
  help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open Dark Souls Data Map",
  readonly:()=>state.readOnly,dirtyCount:()=>state.dirty+state.pending,pendingChanges:()=>state.changes||[],save,discard,history:fieldHistory
});
const subtabsFor=tab=>tab==="enemies"?state.enemyTabs:tab==="attacks"?state.attackTabs:tab==="effects"?state.effectTabs:
  tab==="stats"?state.statsTabs:
  tab==="encumbrance"?[{id:"encumbrance",label:"Bands"},{id:"encumbrance-overrides",label:"Overrides"}]:state.tabs;
async function refreshState(){
  const result=await api("/api/state");
  state.tabs=result.tabs;state.enemyTabs=result.enemyTabs;state.attackTabs=result.attackTabs;
  state.effectTabs=result.effectTabs||[];state.statsTabs=result.statsTabs||[];state.nativeRules=result.nativeRules;
  state.readOnly=result.readOnly;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
}
function sortedRows(){
  const query=state.query.toLowerCase();
  const filtered=state.rows.filter(row=>(row.id+" "+row.name+" "+(row.range||"")).toLowerCase().includes(query));
  if(state.tab==="encumbrance")return filtered;
  // The game's own order (by record) breaks ties.
  return filtered.sort((a,b)=>LexeditorUI.compareRecords(a,b,state.sort)||a.id-b.id);
}
async function loadItems(){
  const request=++recordsRequest;
  const sub=state.sub;
  const result=await api("/api/table?tab="+encodeURIComponent(sub));
  if(request!==recordsRequest||state.sub!==sub)return;
  state.rows=result.rows;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
  if(!state.rows.some(row=>key(row)===state.selected))state.selected=state.rows[0]?key(state.rows[0]):null;
  await loadDetail();
}
async function loadDetail(){
  const row=state.rows.find(row=>key(row)===state.selected);
  if(!row){state.row=null;state.monsterAttacks=null;return;}
  const [result,attacks]=await Promise.all([api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}&sub=${encodeURIComponent(state.sub)}`),
    row.table==="NpcParam"?api(`/api/attacks?monster=${row.id}`):null]);
  if(state.selected!==key(row))return;
  state.row=result.row;state.monsterAttacks=attacks;
}
async function loadTweaks(){
  state.tweaks=await api("/api/tweaks");
}
async function loadDeployment(){
  state.deployment=await api("/api/deployment");
}
async function navigate(tab,sub=state.sub,selected=null){
  const token=++navigation;await edits;
  const changedTab=tab!==state.tab;state.tab=tab;state.bandForm=null;
  if(tab==="enemies")sub="monsters";
  else if(tab==="attacks")sub="attacks";
  else if(tab==="effects"&&!state.effectTabs.some(entry=>entry.id===sub))sub="effects-all";
  // Without the curve table, Stats opens on weapon scaling instead of an error.
  else if(tab==="stats"&&!state.statsTabs.some(entry=>entry.id===sub))sub=(state.statsTabs.find(entry=>entry.id==="curves")||{}).count?"curves":"scaling";
  else if(tab==="encumbrance"&&!["encumbrance","encumbrance-overrides"].includes(sub))sub="encumbrance";
  else if(tab==="misc")sub="misc";
  else if(tab==="items"&&!state.tabs.some(entry=>entry.id===sub))sub="consumables";
  if(sub!==state.sub||changedTab||selected){state.sub=sub;state.selected=selected;state.query="";state.page=0;}
  try{
    if(["items","enemies","attacks","effects","stats","encumbrance","misc"].includes(tab))await loadItems();
    else if(tab==="datamap")state.dataMap=await api("/api/data-map");else if(tab==="info")await loadDeployment();else if(tab==="tweaks")await loadTweaks();
    if(token!==navigation)return;
    // A link lands on the page that holds its record, not on page one.
    if(selected){const index=sortedRows().findIndex(row=>key(row)===selected);if(index>=0)state.page=Math.floor(index/state.pageSize);}
    state.error="";render();
    if(selected)revealSelection();
  }
  catch(error){if(token===navigation){state.error=error.message;render();}}
}
function revealSelection(){
  const row=state.rows.find(row=>key(row)===state.selected);
  if(row&&selectVisibleRecord)selectVisibleRecord(row);
}
const openEffect=effect=>navigate("effects","effects-all",`SpEffectParam:${effect.id}`);
const openAttack=id=>navigate("attacks","attacks",`AtkParam_Npc:${id}`);
async function deploymentAction(action){
  if(state.deployBusy)return;
  if(state.dirty+state.pending){LexeditorUI.showAlert({title:"Save project changes first",message:"Applying installs the archive already saved to the mod project."});return;}
  const confirmations={
    apply:{title:"Apply this mod to the installed game?",message:"Lexeditor installs the saved parameter archive and composes this project's native rules with enabled library tweaks. Each original is preserved once. Close the game first and test native changes offline.",confirmLabel:"Apply"},
    disable:{title:"Restore the original installed files?",message:"Lexeditor restores its owned parameter and executable changes. Project values and library tweak switches remain unchanged.",confirmLabel:"Restore original"}
  };
  if(action==="apply"&&state.nativeRules?.migration)confirmations.apply.message+=" "+state.nativeRules.migration;
  const ok=await confirmAction({...confirmations[action],cancelLabel:"Cancel"});
  if(!ok)return;
  state.deployBusy=true;render();
  try{await api("/api/deployment/"+action,{});await loadDeployment();}
  catch(error){notify(error);}
  finally{state.deployBusy=false;render();}
}
async function save(){
  await edits;
  try{await api("/api/save",{});attackPreviews.clear();await refreshState();shell.refresh();LexeditorUI.showToast("Changes saved to the mod project.");}
  catch(error){notify(error);throw error;}
}
async function discard(){
  await edits;state.bandForm=null;
  try{await api("/api/discard",{});attackPreviews.clear();fieldHistory.clear();await refreshState();
    if(["info","tweaks","datamap"].includes(state.tab))await navigate(state.tab);
    else{await loadItems();render();}}catch(error){notify(error);}
}
// An item's in-game name lives in the game's text, which the mod carries
// beside its parameters; the server renames it there.
function renameRecord(row,name){
  if(state.readOnly)return;
  state.pending++;shell.refresh();
  edits=edits.then(async()=>{
    try{
      const result=await api("/api/rename",{table:row.table,id:row.id,name,sub:state.sub});
      state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
      if(state.row&&key(state.row)===key(row))state.row=result.row;
      for(const listed of state.rows||[])if(key(listed)===key(row))listed.name=result.row.name;
    }catch(error){notify(error);}
    finally{state.pending--;render();}
  });
}
function commit(row,field,value,control){
  if(state.readOnly||!field.editable)return;
  state.pending++;shell.refresh();
  edits=edits.then(async()=>{
    // The value before this edit, as the record now stands (an earlier edit
    // may have changed it since the page drew).
    const live=state.row&&key(state.row)===key(row)?state.row:row;
    const before=live.fields.find(item=>item.key===field.key)?.value;
    try{
      const result=await api("/api/edit",{table:row.table,id:row.id,field:field.key,value,sub:state.sub});
      const after=result.row.fields.find(item=>item.key===field.key)?.value;
      const done=[{table:row.table,id:row.id,field:field.key,before,after}];
      let latest=result;
      // The other selected records of this table get the same value.
      for(const other of (state.selection||[]).filter(k=>k!==key(row)&&k.startsWith(row.table+":"))){
        const id=Number(other.slice(row.table.length+1));
        const prior=(await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${id}&sub=${encodeURIComponent(state.sub)}`)).row.fields.find(item=>item.key===field.key)?.value;
        const changed=await api("/api/edit",{table:row.table,id,field:field.key,value,sub:state.sub});
        latest=changed;
        done.push({table:row.table,id,field:field.key,before:prior,after:changed.row.fields.find(item=>item.key===field.key)?.value});
      }
      fieldHistory.record(done.length>1?{edits:done}:done[0]);
      // The count and the list come from the last edit made, which saw them all.
      state.dirty=latest.dirtyCount;state.changes=latest.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;attackPreviews.delete(row.id);
      if(state.row&&key(state.row)===key(row))state.row=result.row;
      const changed=result.row.fields.find(item=>item.key===field.key);
      if(control.isConnected){if(field.type==="bool")control.checked=!!changed.value;else control.value=String(changed.value);}
      if(row.table==="NativeRules"||["goodsType","weaponCategory"].includes(field.key)){await loadItems();render();}
      else if(field.key.startsWith("residentSpEffectId")||["refId","refCategory","replaceSpEffectId","cycleOccurrenceSpEffectId","atkOccurrenceSpEffectId"].includes(field.key))render();
    }catch(error){
      notify(error);
      const result=await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}&sub=${encodeURIComponent(state.sub)}`);
      const original=result.row.fields.find(item=>item.key===field.key);
      if(control.isConnected){if(field.type==="bool")control.checked=!!original.value;else control.value=String(original.value);}
    }finally{state.pending--;if(row.table==="NativeRules")render();else shell.refresh();}
  }).catch(notify);
}
const PERCENT=/\s*\(%\)$/;
const shownLabel=field=>field.label.replace(PERCENT,"");
function controlFor(row,field){
  const plain=plainControlFor(row,field);
  const control=PERCENT.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"%"):plain;
  if(!field.editable||field.vanilla===null||field.vanilla===undefined||field.type==="text")return control;
  const input=plain;
  const current=()=>field.type==="bool"?(input.checked?1:0):Number(String(input.value).replace(/,/g,""));
  return LexeditorUI.provenanceControl({control,current,vanilla:field.type==="bool"?Number(field.vanilla):field.vanilla,
    internal:true,
    format:field.type==="enum"?value=>field.enum[String(value)]||String(value):undefined,
    same:(left,right)=>Number(left)===Number(right),
    apply:value=>commit(row,field,value,input)});
}
function plainControlFor(row,field){
  if(!field.editable)return readonlyField(field.value,{"aria-label":field.label});
  const attrs={"aria-label":field.label,"data-field-key":field.key,disabled:state.readOnly||field.disabled};
  // The shared shell still catches an edit attempt here and offers Create a
  // mod; disabling the control too matches the greyed-out, cursor:default
  // read-only look every other plugin's own fields already use instead of a
  // control that looks editable but shows a blocked cursor.
  if(field.type==="bool")return el("input",{...attrs,type:"checkbox",checked:!!field.value,
    onchange:event=>commit(row,field,event.target.checked?1:0,event.target)});
  if(field.type==="text")return el("input",{...attrs,type:"text",value:field.value,
    maxlength:field.maxLength||48,required:true,onchange:event=>{
      const input=event.target;
      if(!input.value.trim()||!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,input.value,input);
    }});
  if(field.type==="enum"){
    const choices=Object.entries(field.enum);
    if(!choices.some(([value])=>value===String(field.value)))choices.unshift([String(field.value),`Unknown (${field.value})`]);
    const control=el("select",{...attrs,onchange:event=>commit(row,field,Number(event.target.value),event.target)},
      ...choices.map(([value,label])=>el("option",{value,disabled:!(value in field.enum)},label)));
    control.value=String(field.value);return control;
  }
  return el("input",{...attrs,type:"number",value:field.value,min:field.minimum,max:field.maximum,
    step:field.step??(/^(f|angle)/.test(field.dtype)?"any":1),onchange:event=>{
      const input=event.target;if(!input.value.trim()||!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,Number(input.value),input);
    }});
}
const GROUP_ORDER=["Basics","Defense","Absorption","Combat","Requirements & costs","Thresholds","Growth","Curve shape","Level-up cost","Effects & references","Upgrades",
  "Use behavior","Value & rewards","Appearance","Properties"];
function groupFor(field){
  if(field.group)return field.group;
  const name=field.key.toLowerCase();
  if(/^weight$|^durability|^sadurability$/.test(name))return "Basics";
  if(/originequip|reinforcetype|materialset/.test(name))return "Upgrades";
  if(/icon|model|sort|menu|visual|sfx|material|invisibleflag|facescale|headequip|bodyequip|armequip|legequip/.test(name))return "Appearance";
  if(/price|value|trophy|shop|qwc/.test(name))return "Value & rewards";
  if(/guard|defen|resist|damagecut/.test(name))return "Defense";
  if(/attack|damage|correct|reinforce|repa|durability/.test(name))return "Combat";
  if(/ref|speffect|behavior|bullet|replace|magicid/.test(name))return "Effects & references";
  if(/require|proper|slot|consume|stamina|dexterity|humanity|hero/.test(name))return "Requirements & costs";
  if(/motion|anim|spatk|hold/.test(name))return "Use behavior";
  return "Properties";
}
function fieldSections(row){
  const groups=new Map();
  // A field that is itself an effect link opens that effect from its own row;
  // only links with no editable field on the page are listed separately.
  const links=new Map((row.effectLinks||[]).map(effect=>[effect.field,effect]));
  const shownLinks=new Set();
  for(const field of row.fields){
    const group=groupFor(field);if(!groups.has(group))groups.set(group,[]);
    let help=field.description.trim();
    if(!field.editable)help=field.protectedReason||"This property is preserved. Its choices or behavior are not sufficiently documented for editing.";
    if(help.replace(/[.\s]/g,"").toLowerCase()===field.label.replace(/[.\s]/g,"").toLowerCase())help="";
    const link=field.editable&&links.get(field.key);
    let control=controlFor(row,field);
    if(link){
      shownLinks.add(field.key);
      if(link.resolved)control=LexeditorUI.controlGroup([control,el("button",{type:"button",class:"ds1-open-effect",
        title:`Open ${link.name}`,"aria-label":`Open ${link.name}`,onclick:()=>openEffect(link)},"Open")]);
    }
    groups.get(group).push(detailField({label:shownLabel(field),property:field.key,control,
      // A flag is stored as a u8 bit but edited as a boolean; naming the
      // storage type here kept the checkbox out of the boolean field layout.
      help:help?infoHelp(help):null,dataType:field.type==="bool"?"BOOL":field.dtype.toUpperCase(),min:field.minimum,max:field.maximum,
      sliderMin:field.sliderMin,sliderMax:field.sliderMax}));
  }
  const unlisted=(row.effectLinks||[]).filter(effect=>!shownLinks.has(effect.field));
  if(unlisted.length){
    groups.set("Linked effects",unlisted.map(effect=>detailField({
      label:row.fields.find(field=>field.key===effect.field)?.label||effect.field,
      control:effect.resolved?el("button",{type:"button",onclick:()=>openEffect(effect)},effect.name):readonlyField(effect.name),
      help:infoHelp("Open this item's or ability's referenced effect. Changing a shared effect changes every use of it.")})));
  }
  if(row.effectUsage){
    const usage=row.effectUsage;
    groups.set("Usage",[detailField({label:"Direct references",control:readonlyField(usage.length),
      help:infoHelp("Counts references in the supported parameter tables. Scripts and animations can add more uses. "+
        (usage.length?"Examples: "+usage.slice(0,3).map(source=>source.name).join(", ")+".":"No direct reference was found."))})]);
  }
  // Fixed section order, so the same section is in the same place on every record.
  const rank=group=>{const at=GROUP_ORDER.indexOf(group);return at<0?GROUP_ORDER.length:at;};
  return new Map([...groups].sort((a,b)=>rank(a[0])-rank(b[0])));
}
// A linked attack previews its damage so several can be compared from the
// monster without leaving it. Values come from the live document, so an
// unsaved edit shows here too.
async function attackPreview(id){
  if(!attackPreviews.has(id))attackPreviews.set(id,api(`/api/row?table=AtkParam_Npc&id=${id}`).then(result=>result.row,
    error=>{attackPreviews.delete(id);throw error;}));
  const row=await attackPreviews.get(id);
  const users=row.impact.variants.length;
  // The shared label-and-value rows, read-only: a preview is a small panel.
  return LexeditorUI.stack({fill:false,compact:true},el("strong",{},row.name),
    ...row.fields.map(field=>detailField({label:field.label,control:readonlyField(
      field.type==="enum"?(field.enum[String(field.value)]||`Unknown (${field.value})`):LexeditorUI.formatNumber(field.value))})),
    LexeditorUI.detailText(users===1?"Used by 1 NPC variant.":`Shared by ${users} NPC variants.`));
}
function monsterAttacksSection(){
  const links=state.monsterAttacks;
  if(!links)return LexeditorUI.loadingPanel({label:"Loading attacks"});
  if(!links.rows.length)return LexeditorUI.detailNote("No attack link was resolved for this monster. The Attacks tab lists every attack record.");
  return detailSection({title:"Referenced attacks",body:links.rows.map(attack=>detailField({label:attack.name,
    control:hoverable({content:attack.route,targetType:"ds1-attack",targetId:attack.id,
      targetLabel:`${attack.name} in Attacks`,preview:()=>attackPreview(attack.id),activate:()=>openAttack(attack.id)})}))});
}
function monsterDetail(groups){
  const links=state.monsterAttacks;
  const attackHelp=links?`Attack records reached from behavior variation ${links.variation} across ${links.behaviorCount} behavior records. `+
    `Direct means a behavior calls the attack; Projectile means a projectile or child projectile does. ${links.unresolved.length} references remain unresolved or lead to effects. `+
    "These are parameter links; they do not prove an animation uses the attack. Hover an attack to preview its damage, and click it to edit it in Attacks.":
    "Attack records reached from this monster's behavior parameters.";
  const effects=groups.get("Linked effects");
  groups.delete("Linked effects");
  const tabs=[{id:"resistances",label:"Resistances"},{id:"attacks",label:"Attacks",help:attackHelp}];
  if(effects)tabs.push({id:"effects",label:"Effects",help:"Effects this monster carries. Changing a shared effect changes every use of it."});
  const active=state.monsterTab==="effects"&&!effects?"resistances":state.monsterTab;
  return tabbedPanel({label:"Monster details",active,tabs,
    change:id=>{state.monsterTab=id;render();},
    content:active==="attacks"?monsterAttacksSection()
      :active==="effects"?[detailSection({title:"Effects",body:effects})]
      :[...groups].map(([title,body])=>detailSection({title,body}))});
}
function detail(){
  const impact=state.row?.impact;
  // A record's heading is its name, on every tab. An attack's sharing is
  // said under it, never in its place.
  const noun=state.tab==="attacks"?"Attack":state.tab==="enemies"?"Monster":state.tab==="effects"?"Effect":state.tab==="encumbrance"?"Load band":state.tab==="stats"?(state.sub==="curves"?"Curve":state.sub==="scaling"?"Weapon":"Spell"):"Item";
  if(!state.row)return detailPanel({title:noun,body:[LexeditorUI.detailNote("Select a record.")]});
  if(key(state.row)!==state.selected)return detailPanel({title:noun,body:[LexeditorUI.loadingPanel({label:"Loading record"})]});
  if(state.bandForm&&state.bandForm.id===state.row.id)return renderBandForm();
  const title=state.row.name;
  const meta=state.tab==="attacks"&&impact?(impact.variants.length>1?"Shared attack damage":impact.variants.length===0?"Unresolved attack ownership":"Attack damage"):"";
  const groups=fieldSections(state.row);
  if(state.row.table==="NpcParam")return detailPanel({title:state.row.name,body:[monsterDetail(groups)]});
  let help=state.row.help;
  if(impact){
    const examples=impact.variants.slice(0,3).map(n=>n.name).join(", ");
    help=`Editing this record changes every use of it. Known parameter links reach ${impact.variants.length} NPC variants and ${impact.behaviors.length} behaviors.`+
      (examples?` Examples: ${examples}.`:" Ownership is unresolved.")+
      ` ${impact.bulletReferences.length} projectile records reference this attack ID; player and enemy contexts may differ.`+
      " Animation, script and effect calls are not fully traced, so this is a minimum impact estimate.";
    groups.set("Reference paths",(impact.paths.length?impact.paths:["No behavior link found"]).map((path,index)=>detailField({label:`Path ${index+1}`,control:readonlyField(path),
      help:infoHelp("This parameter link reaches the attack. Projectile paths include child projectiles. It does not prove an animation invokes it.")})));
  }
  return detailPanel({title,meta,help,actions:state.row.band?bandActions():[],
    body:[...groups].map(([title,body])=>detailSection({title,body}))});
}
function bandActions(){
  const disabled=state.readOnly||state.bandBusy||state.pending>0;
  return [
    el("button",{type:"button",disabled:disabled||!state.row.band.canAdd,onclick:()=>beginBandForm("add")},"Add band"),
    el("button",{type:"button",disabled:disabled||!state.row.band.canDelete,onclick:()=>beginBandForm("delete")},"Delete band")
  ];
}
function beginBandForm(action){
  if(state.readOnly||state.bandBusy||state.pending||!state.row?.band)return;
  const band=state.row.band;
  if(action==="add"&&!band.canAdd||action==="delete"&&!band.canDelete)return;
  const split=band.upper===null?band.lower+25:(band.lower+band.upper)/2;
  state.bandForm={action,id:state.row.id,revision:state.nativeRules.bandRevision,
    at:Math.min(band.splitMaximum,Math.max(band.splitMinimum,Math.round(split*100)/100)),neighbour:"",keep:""};
  render();
}
function bandRange(lower,upper){
  return (lower===0?"0":">"+lower)+"% to "+(upper===null?"no upper limit":upper+"%");
}
function renderBandForm(){
  const form=state.bandForm,row=state.row,band=row.band;
  const body=[detailField({label:"Selected band",control:readonlyField(row.name)}),
    detailField({label:"Current range",control:readonlyField(bandRange(band.lower,band.upper))})];
  const controls=[];
  if(form.action==="add"){
    const input=el("input",{type:"number","aria-label":"Split at (%)","data-band-input":"at",
      min:band.splitMinimum,max:band.splitMaximum,step:.01,value:form.at,disabled:state.bandBusy,
      oninput:event=>{form.at=event.target.value;}});
    controls.push(input);
    body.push(detailField({label:"Split at (%)",control:input,
      help:infoHelp("The lower band includes the split point. The new upper band copies its name, movement and recovery. This initially preserves gameplay.")}));
  }else{
    const neighbour=el("select",{"aria-label":"Merge into","data-band-input":"neighbour",disabled:state.bandBusy,
      onchange:event=>{form.neighbour=event.target.value;render();}},
      el("option",{value:""},"Choose a neighbouring band"),
      ...band.neighbours.map(n=>el("option",{value:n.id},n.name+" ("+bandRange(n.lower,n.upper)+")")));
    neighbour.value=String(form.neighbour);
    const keep=el("select",{"aria-label":"Properties to keep","data-band-input":"keep",disabled:state.bandBusy,
      onchange:event=>{form.keep=event.target.value;render();}},
      el("option",{value:""},"Choose which properties survive"),
      el("option",{value:"selected"},"Selected band's properties"),
      el("option",{value:"neighbour"},"Neighbour's properties"));
    keep.value=form.keep;
    body.push(detailField({label:"Merge into",control:neighbour}),
      detailField({label:"Properties to keep",control:keep,
        help:infoHelp("The neighbouring identity survives. The chosen band's name, movement and recovery are kept across the combined range.")}));
    const other=band.neighbours.find(n=>String(n.id)===form.neighbour);
    if(other&&form.keep){
      const winner=form.keep==="selected"?{...band,name:row.name}:other;
      const upper=band.upper===null||other.upper===null?null:Math.max(band.upper,other.upper);
      body.push(detailField({label:"Merged range",control:readonlyField(bandRange(Math.min(band.lower,other.lower),upper))}),
        detailField({label:"Resulting name",control:readonlyField(winner.name)}),
        detailField({label:"Resulting movement",control:readonlyField(winner.movement)}),
        detailField({label:"Resulting recovery (%)",control:readonlyField(winner.recovery)}));
    }
  }
  return detailPanel({title:form.action==="add"?"Add band":"Delete band",paginate:{inline:true},
    actions:[
      el("button",{type:"button",disabled:state.bandBusy||(form.action==="delete"&&(!form.neighbour||!form.keep)),
        onclick:()=>{
          if(controls.some(input=>!input.value.trim()||!input.checkValidity())){
            controls.forEach(input=>input.reportValidity());return;
          }
          submitBandForm(form);
        }},form.action==="add"?"Create band":"Merge and delete"),
      el("button",{type:"button",disabled:state.bandBusy,onclick:()=>{state.bandForm=null;render();}},"Cancel")],
    body:[detailSection({title:"Load range",body})]});
}
function submitBandForm(form){
  if(state.bandBusy||state.readOnly||state.bandForm!==form)return;
  const body={id:form.id,revision:form.revision,...(form.action==="add"?
    {at:Number(form.at)}:{neighbour:Number(form.neighbour),keep:form.keep})};
  state.bandBusy=true;state.pending++;render();
  edits=edits.then(async()=>{
    try{
      const result=await api("/api/bands/"+form.action,body);
      state.nativeRules=result.nativeRules;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
      state.bandForm=null;state.selected=key(result.row);state.query="";
      await loadItems();
      const index=sortedRows().findIndex(row=>key(row)===state.selected);
      state.page=Math.max(0,Math.floor(index/state.pageSize));
    }catch(error){
      state.bandForm=null;await refreshState();await loadItems();notify(error);
    }finally{
      state.pending--;state.bandBusy=false;render();revealSelection();
    }
  }).catch(notify);
}

function renderItems(){
  const encumbrance=state.tab==="encumbrance";
  const noun=encumbrance?(state.sub==="encumbrance"?"bands":"overrides"):state.tab==="effects"?"effects":state.tab==="attacks"?"attacks":state.tab==="enemies"?"monsters":state.tab==="stats"?(state.sub==="curves"?"curves":state.sub==="scaling"?"weapons":"spells"):"items";
  const label=encumbrance?"Encumbrance":state.tab==="effects"?"Effects":state.tab==="attacks"?"Attacks":state.tab==="enemies"?"Enemies":state.tab==="stats"?"Stats":"Items";
  const view=pagedListDetail({className:"ds1-records",rows:sortedRows(),key,selected:state.selected,slots:false,noun,
    page:state.page,pageSize:state.pageSize,defaultSplit:32,minLeft:230,minRight:380,splitKey:"ds1-items",rowsKey:"ds1-items-"+state.sub,
    search:{key:"ds1-records-search",value:state.query,label:"Search "+noun,change:value=>{state.query=value;state.page=0;render();}},
    sync:next=>{
      state.page=next.page;state.pageSize=next.pageSize;state.selection=next.selection||[];
      if(state.selected!==next.selected){state.selected=next.selected;void loadDetail().then(render).catch(notify);}
    },
    change:next=>{state.page=next.page;state.pageSize=next.pageSize;render();},
    master:({rows:listed,selected,select})=>{
      selectVisibleRecord=select;
      return columnList({rows:listed,key,selected,sortState:state.sort,
      sort:column=>{if(encumbrance)return;state.sort={key:column,dir:state.sort.key===column?-state.sort.dir:1};render();},
      // The record is fetched first, then the shared list swaps in its detail
      // pane once. It used to draw the pane with the old record, then render
      // the whole page twice more as two loads of the same row came back.
      select:async(row,event)=>{
        await edits;
        if(!event?.shiftKey&&!event?.ctrlKey&&!event?.metaKey){state.selected=key(row);await loadDetail();}
        select(row,event);shell.refresh();},
      columns:encumbrance?[{key:"range",label:"Load",grow:1},{key:"name",label:"Name",grow:1}]:
        [{key:"name",label:"Name",sortable:true,grow:1}]});
    },
    rename:renameRecord,
    // Items have in-game names; monsters, attacks, effects and load bands
    // have only reference names.
    renamable:row=>state.tab==="stats"?row.table!=="CalcCorrectGraph":state.tab==="items"&&!(state.sub==="spells"&&row.table!=="Magic"),
    detail,emptyDetail:()=>detailPanel({title:"No matching "+noun,body:[LexeditorUI.detailNote("Change the search to find a record.")]})});
  const subtabs=subtabsFor(state.tab);
  // Enemies names its one list (Monsters) so the category reads; Attacks
  // under Attacks would only repeat the tab.
  return LexeditorUI.stack(subtabBar({tabs:subtabs,showSingle:state.tab==="enemies",active:state.sub,label,change:id=>navigate(state.tab,id)}),view);
}
function appliedLabel(deploy){
  if(!deploy.everApplied)return "No";
  if(deploy.changedExternally)return "Unknown — installed file changed outside Lexeditor";
  if(deploy.pendingRecovery)return "Unknown — an interrupted operation needs Apply or Restore to finish";
  if(!deploy.backupOk)return "Unknown — the preserved original is missing or changed";
  if(deploy.enabled)return deploy.thisProjectActive?"Yes, this project's edits":"Yes, a different project's edits";
  if(deploy.matchesOriginal)return "No, original restored";
  return "No";
}
function needsAttentionNote(deploy){
  if(deploy.changedExternally)return LexeditorUI.detailNote("The installed param archive changed outside Lexeditor. Apply and Restore refuse to continue until it is restored or verified by hand.");
  if(deploy.pendingRecovery)return LexeditorUI.detailNote("A previous Apply or Restore was interrupted before it finished. Click Apply or Restore original to complete it safely.");
  if(deploy.everApplied&&!deploy.backupOk)return LexeditorUI.detailNote("The preserved original copy is missing or has changed. Apply and Restore refuse to continue until it is restored by hand.");
  return null;
}
function renderInfo(){
  const deploy=state.deployment||{};
  const upToDate=deploy.enabled&&deploy.thisProjectActive?(deploy.stale?"No, reapply after the latest save":"Yes"):"-";
  return detailPanel({className:"lex-information-panel",title:"Information",body:[
    detailSection({title:"ITEMS",body:[detailField({label:"EDITION",control:readonlyField("Dark Souls Remastered / Steam")}),
      detailField({label:"SUPPORT",control:readonlyField("Items, effects, native rules, monster resistances and enemy attacks"),help:infoHelp("Edit documented item properties, reviewed monster resistances and enemy attack damage. Names are reference labels. Unknown fields and padding stay unchanged. Saves go to the selected mod project.")})]}),
    detailSection({title:"INSTALLED GAME",body:[
      detailField({label:"APPLIED",control:readonlyField(appliedLabel(deploy))}),
      detailField({label:"ORIGINAL PRESERVED",control:readonlyField(deploy.everApplied?(deploy.backupOk?"Yes":"No, needs attention"):"Not yet applied"),
        help:infoHelp("The first Apply keeps one copy of the installed file exactly as it was. Disable always restores that copy.")}),
      detailField({label:"UP TO DATE",control:readonlyField(upToDate),
        help:infoHelp("Apply installs the archive already saved in the mod project. Reapply after every later save that should reach the installed game.")}),
      needsAttentionNote(deploy),
      actionRow(
        el("button",{type:"button",disabled:state.deployBusy||!deploy.isProject||!deploy.sourceReady||deploy.changedExternally,onclick:()=>deploymentAction("apply")},deploy.everApplied?"Reapply":"Apply"),
        el("button",{type:"button",disabled:state.deployBusy||(!deploy.everApplied&&!deploy.native?.backupOk&&!deploy.legacyRestoreAvailable)||deploy.changedExternally,onclick:()=>deploymentAction("disable")},"Restore original")
      )].filter(Boolean)}),
    detailSection({title:"NATIVE RULES",body:[
      detailField({label:"APPLIED PROJECT",control:readonlyField(deploy.native?.project?.path||"None"),
        help:infoHelp("Native rules are applied in memory by the same loader as library tweaks, from one patch. Applying library tweaks keeps the last applied project rules. Restore original removes both without changing saved settings.")}),
      deploy.legacyRestoreAvailable?LexeditorUI.detailNote("Restore the earlier draft's native patch before applying the combined rules. Its verified original is available."):
        deploy.native?.problem?LexeditorUI.detailNote(deploy.native.problem):null,
      deploy.native?.pendingRecovery?LexeditorUI.detailNote("An interrupted native operation is recoverable. Retry Apply or Restore original."):null,
      state.nativeRules?.migration?LexeditorUI.detailNote(state.nativeRules.migration):null
    ].filter(Boolean)}),
    modLoaderSection({loader:deploy.note||"Dark Souls Remastered reads this file as a loose file; no mod loader is installed.",
      output:"Apply replaces the installed param/GameParam/GameParam.parambnd.dcx with the mod project's saved copy, after preserving the original once.",
      order:"One complete parameter archive. Separate projects are not merged; applying a different project replaces what is currently installed.",
      safety:"Apply composes enabled library tweaks and project native rules before replacing the executable and parameter archive. Outside changes are refused.",
      removal:"Restore original restores both owned files. The project and library tweak settings stay unchanged."})]});
}
// Tweaks are library mods: a switch saves at once, and Apply builds every
// enabled one into the installed executable together.
async function tweakRequest(path,body,failure){
  if(state.tweakBusy)return;
  state.tweakBusy=true;render();
  try{state.tweaks=await api(path,body);}
  catch(error){LexeditorUI.showAlert({title:failure,message:error.message||String(error)});await loadTweaks().catch(()=>{});}
  finally{state.tweakBusy=false;render();}
}
async function tweakAction(action){
  const spec=action==="apply"?{title:"Apply the enabled tweaks?",
    message:"Close the game first. Lexeditor builds every enabled tweak into one executable, keeps one copy of the original the first time, and refuses an executable changed outside Lexeditor. These tweaks are experimental; test offline.",confirmLabel:"Apply"}
    :{title:"Restore the original executable?",message:"Close the game first. The tweaks' switches stay as they are.",confirmLabel:"Restore original"};
  if(!await confirmAction({...spec,cancelLabel:"Cancel"}))return;
  await tweakRequest("/api/tweaks/"+action,{},action==="apply"?"Could not apply the tweaks":"Could not restore the executable");
}
function renderTweaks(){
  const status=state.tweaks;
  if(!status)return LexeditorUI.loadingPanel({label:"Loading tweaks"});
  const busy=state.tweakBusy;
  const save=row=>tweakRequest("/api/tweaks/save",{tweaks:{[row.id]:{enabled:row.enabled,values:row.values}}},"Could not save the tweak");
  const {panels,bind}=LexeditorUI.tweakModPanels({rows:status.tweaks||[],readOnly:busy,
    change:()=>{const changed=(status.tweaks||[]).find(row=>row.enabled!==row._saved?.enabled||JSON.stringify(row.values)!==JSON.stringify(row._saved?.values));if(changed)save(changed)}});
  for(const row of status.tweaks||[])row._saved={enabled:row.enabled,values:structuredClone(row.values)};
  const empty=!(status.tweaks||[]).length;
  const missingMods=empty?LexeditorUI.notice({message:`No tweak mods are installed. Tweaks live in the mod library (${status.modsRoot}).`}):null;
  const applied=status.applied.length?status.applied.join(", "):status.state==="vanilla"?"None, original game files":"Unknown";
  const installed=detailPanel({title:"INSTALLED GAME",
    help:"Apply combines every enabled tweak into lexeditor-ds1-patch.bin, which Lexeditor's loader (dinput8.dll in the game folder) applies in memory each time the game starts. DarkSoulsRemastered.exe itself is never changed. When a tweak adds menu rows, the menu layout file is rebuilt too, keeping one copy of its original. Restore original removes the loader and puts the layout back.",
    body:[detailField({label:"APPLIED",control:readonlyField(applied)}),
      // Debug mode: the game runs offline with Arxan off, so a debugger
      // (Cheat Engine's "find what writes", x64dbg) can attach (#742).
      detailField({label:"DEBUG MODE",dataType:"BOOL",
        help:infoHelp("For finding things in the running game with a debugger. Apply or Play installs a loader that switches the game's anti-debug protection (Arxan) off with dearxan, so Cheat Engine or x64dbg can attach without the game closing itself. The game has no network access while it is on: it cannot go online. Turn it off and Apply again for normal play."),
        control:el("input",{type:"checkbox",checked:!!status.debugMode,disabled:busy,"aria-label":"Debug mode",
          onchange:event=>tweakRequest("/api/tweaks/debug",{on:event.target.checked},"Could not switch debug mode")})}),
      !!status.debugMode!==!!status.debugInstalled?LexeditorUI.detailNote(status.debugMode?"Debug mode is on: Apply to install it.":"Debug mode is off: Apply to put the normal loader back."):null,
      status.loaderMessage?detailField({label:"LAST GAME START",control:readonlyField(status.loaderMessage),
        help:infoHelp("What the loader reported the last time the game started. If the game was updated or another tool changed it, the loader changes nothing and says so here.")}):null,
      empty?missingMods:null,
      status.builtIntoExecutable?LexeditorUI.detailNote("An earlier Lexeditor built tweaks into DarkSoulsRemastered.exe. Apply or Restore original puts the original executable back; tweaks then load from dinput8.dll."):null,
      status.problem?LexeditorUI.detailNote(status.problem):null,
      actionRow(el("button",{type:"button",disabled:busy||!status.windows||!!status.problem,onclick:()=>tweakAction("apply")},"Apply"),
        el("button",{type:"button",disabled:busy||!status.windows||status.state!=="tweaked",onclick:()=>tweakAction("restore")},"Restore original"))].filter(Boolean)});
  return LexeditorUI.tweaksPage({plugin:"ds1",render,
    pages:[{id:"mods",label:"Mods",body:()=>[installed,...panels],bind,whole:empty?installed:null}]});
}
function renderDataMap(){
  const view=LexeditorUI.dataMap({plugin:"ds1",rows:state.dataMap.rows,page:state.mapPage,query:state.mapQuery,status:state.mapStatus,sort:state.mapSort,
    open:row=>row.target&&navigate(row.target,row.sub),
    changePage:value=>{state.mapPage=value;render()},changeQuery:value=>{state.mapQuery=value;state.mapPage=0;render()},
    changeStatus:value=>{state.mapStatus=value;state.mapPage=0;render()},
    changeSort:key=>{state.mapSort=[key,state.mapSort[0]===key?-state.mapSort[1]:1];render()}});
  state.mapPage=view.page;return view.content;
}
function render(){
  document.querySelector("#main").replaceChildren(state.error?LexeditorUI.notice({tone:"warning",message:state.error}):state.tab==="datamap"?renderDataMap():state.tab==="info"?renderInfo():state.tab==="tweaks"?renderTweaks():state.tab==="misc"?detail():renderItems());
  shell.refresh();
}
async function boot(){
  try{await refreshState();await loadItems();render();}catch(error){state.error=error.message;render();}
  finally{document.body.dataset.ds1Ready=state.error?"error":"true";await LexeditorUI.finishPluginLoading();}
}
window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&(state.dirty||state.pending))event.preventDefault();});
boot();
