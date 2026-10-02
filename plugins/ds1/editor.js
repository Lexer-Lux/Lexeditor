"use strict";
const {el,detailPanel,detailSection,detailField,readonlyField,infoHelp,pagedListDetail,columnList,subtabBar,
  actionRow,confirmAction,modLoaderSection,tabbedPanel,hoverable}=LexeditorUI;
const state={tab:"items",sub:"consumables",tabs:[],enemyTabs:[],attackTabs:[],rows:[],selected:null,row:null,dirty:0,pending:0,
  readOnly:true,query:"",page:0,pageSize:20,sort:{key:"id",dir:1},error:"",deployment:null,deployBusy:false,
  monsterTab:"resistances",monsterAttacks:null};
let edits=Promise.resolve(),navigation=0,recordsRequest=0;
const attackPreviews=new Map();
const key=row=>`${row.table}:${row.id}`;
async function api(path,body){
  const response=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const result=await response.json();
  if(!response.ok||result.error)throw new Error(result.error||response.statusText);
  return result;
}
const notify=error=>LexeditorUI.showAlert({title:"Dark Souls",message:error.message||String(error)});
const shell=LexeditorUI.mountShell({
  host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ds1",name:"Dark Souls Remastered"},
  tabs:[{id:"items",label:"Items",help:"Edit item properties in the selected mod. Vanilla is read-only. Unknown fields stay protected. Saves do not install a mod."},
    {id:"enemies",label:"Enemies",help:"Edit reviewed monster resistances. A monster's Attacks tab lists the attack records its parameters reference. Vanilla is read-only. Save changes the mod project."},
    {id:"attacks",label:"Attacks",help:"Edit enemy attack damage. One attack record can be shared by several monsters, bosses and NPCs, so an edit changes every use of it. Vanilla is read-only. Save changes the mod project."}],
  activeTab:()=>state.tab,navigate:tab=>navigate(tab),
  info:()=>navigate("info"),infoActive:()=>state.tab==="info",
  readonly:()=>state.readOnly,dirtyCount:()=>state.dirty+state.pending,save,discard
});
const subtabsFor=tab=>tab==="enemies"?state.enemyTabs:tab==="attacks"?state.attackTabs:state.tabs;
async function refreshState(){
  const result=await api("/api/state");
  state.tabs=result.tabs;state.enemyTabs=result.enemyTabs;state.attackTabs=result.attackTabs;
  state.readOnly=result.readOnly;state.dirty=result.dirtyCount;
}
function sortedRows(){
  const query=state.query.toLowerCase();
  return state.rows.filter(row=>(row.id+" "+row.name).toLowerCase().includes(query)).sort((a,b)=>{
    const left=a[state.sort.key],right=b[state.sort.key];
    return state.sort.dir*(typeof left==="number"?left-right:String(left).localeCompare(String(right),undefined,{numeric:true}));
  });
}
async function loadItems(){
  const request=++recordsRequest;
  const sub=state.sub;
  const result=await api("/api/table?tab="+encodeURIComponent(sub));
  if(request!==recordsRequest||state.sub!==sub)return;
  state.rows=result.rows;state.dirty=result.dirtyCount;
  if(!state.rows.some(row=>key(row)===state.selected))state.selected=state.rows[0]?key(state.rows[0]):null;
  await loadDetail();
}
async function loadDetail(){
  const row=state.rows.find(row=>key(row)===state.selected);
  if(!row){state.row=null;state.monsterAttacks=null;return;}
  const [result,attacks]=await Promise.all([api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}`),
    row.table==="NpcParam"?api(`/api/attacks?monster=${row.id}`):null]);
  if(state.selected!==key(row))return;
  state.row=result.row;state.monsterAttacks=attacks;
}
async function loadDeployment(){
  state.deployment=await api("/api/deployment");
}
async function navigate(tab,sub=state.sub,selected=null){
  const token=++navigation;await edits;
  const changedTab=tab!==state.tab;state.tab=tab;
  if(tab==="enemies")sub="monsters";
  else if(tab==="attacks")sub="attacks";
  else if(tab==="items"&&!state.tabs.some(entry=>entry.id===sub))sub="consumables";
  if(sub!==state.sub||changedTab||selected){state.sub=sub;state.selected=selected;state.query="";state.page=0;}
  try{
    if(tab==="items"||tab==="enemies"||tab==="attacks")await loadItems();else if(tab==="info")await loadDeployment();
    if(token!==navigation)return;
    // A link lands on the page that holds its record, not on page one.
    if(selected){const index=sortedRows().findIndex(row=>key(row)===selected);if(index>=0)state.page=Math.floor(index/state.pageSize);}
    state.error="";render();
  }
  catch(error){if(token===navigation){state.error=error.message;render();}}
}
const openAttack=id=>navigate("attacks","attacks",`AtkParam_Npc:${id}`);
async function deploymentAction(action){
  if(state.deployBusy)return;
  if(state.dirty+state.pending){LexeditorUI.showAlert({title:"Save project changes first",message:"Applying installs the archive already saved to the mod project."});return;}
  const confirmations={
    apply:{title:"Apply this mod to the installed game?",message:"Lexeditor keeps one backup of the original param archive the first time you apply, then replaces the installed copy with this project's saved edits.",confirmLabel:"Apply"},
    disable:{title:"Restore the original installed param archive?",message:"Lexeditor copies its preserved original bytes back over the installed file. The mod project itself is unchanged.",confirmLabel:"Restore original"}
  };
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
  await edits;
  try{await api("/api/discard",{});attackPreviews.clear();await refreshState();await loadItems();render();}catch(error){notify(error);}
}
function commit(row,field,value,control){
  if(state.readOnly||!field.editable)return;
  state.pending++;shell.refresh();
  edits=edits.then(async()=>{
    try{
      const result=await api("/api/edit",{table:row.table,id:row.id,field:field.key,value});
      state.dirty=result.dirtyCount;attackPreviews.delete(row.id);
      if(state.row&&key(state.row)===key(row))state.row=result.row;
      const changed=result.row.fields.find(item=>item.key===field.key);
      if(control.isConnected){if(field.type==="bool")control.checked=!!changed.value;else control.value=String(changed.value);}
      if(["goodsType","weaponCategory"].includes(field.key)){await loadItems();render();}
    }catch(error){
      notify(error);
      const result=await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}`);
      const original=result.row.fields.find(item=>item.key===field.key);
      if(control.isConnected){if(field.type==="bool")control.checked=!!original.value;else control.value=String(original.value);}
    }finally{state.pending--;shell.refresh();}
  }).catch(notify);
}
function controlFor(row,field){
  if(!field.editable)return readonlyField(field.value,{"aria-label":field.label});
  const attrs={"aria-label":field.label,"data-field-key":field.key,disabled:state.readOnly};
  // The shared shell still catches an edit attempt here and offers Create a
  // mod; disabling the control too matches the greyed-out, cursor:default
  // read-only look every other plugin's own fields already use instead of a
  // control that looks editable but shows a blocked cursor.
  if(field.type==="bool")return el("input",{...attrs,type:"checkbox",checked:!!field.value,
    onchange:event=>commit(row,field,event.target.checked?1:0,event.target)});
  if(field.type==="enum"){
    const choices=Object.entries(field.enum);
    if(!choices.some(([value])=>value===String(field.value)))choices.unshift([String(field.value),`Unknown (${field.value})`]);
    const control=el("select",{...attrs,onchange:event=>commit(row,field,Number(event.target.value),event.target)},
      ...choices.map(([value,label])=>el("option",{value,disabled:!(value in field.enum)},label)));
    control.value=String(field.value);return control;
  }
  return el("input",{...attrs,type:"number",value:field.value,min:field.minimum,max:field.maximum,
    step:/^(f|angle)/.test(field.dtype)?"any":1,onchange:event=>{
      const input=event.target;if(!input.value.trim()||!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,Number(input.value),input);
    }});
}
function groupFor(field){
  if(field.group)return field.group;
  const name=field.key.toLowerCase();
  if(/icon|model|sort|menu|visual|sfx|material/.test(name))return "Appearance";
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
  for(const field of row.fields){
    const group=groupFor(field);if(!groups.has(group))groups.set(group,[]);
    let help=field.description.trim();
    if(!field.editable)help="This property is preserved. Its choices or behavior are not sufficiently documented for editing.";
    if(help.replace(/[.\s]/g,"").toLowerCase()===field.label.replace(/[.\s]/g,"").toLowerCase())help="";
    groups.get(group).push(detailField({label:field.label,property:field.key,control:controlFor(row,field),
      help:help?infoHelp(help):null,dataType:field.dtype.toUpperCase(),min:field.minimum,max:field.maximum}));
  }
  return groups;
}
// A linked attack previews its damage so several can be compared from the
// monster without leaving it. Values come from the live document, so an
// unsaved edit shows here too.
async function attackPreview(id){
  if(!attackPreviews.has(id))attackPreviews.set(id,api(`/api/row?table=AtkParam_Npc&id=${id}`).then(result=>result.row,
    error=>{attackPreviews.delete(id);throw error;}));
  const row=await attackPreviews.get(id);
  const users=row.impact.variants.length;
  return el("div",{class:"ds1-attack-preview"},el("strong",{},`${row.name} #${row.id}`),
    el("dl",{},...row.fields.flatMap(field=>[el("dt",{},field.label),
      el("dd",{},field.type==="enum"?(field.enum[String(field.value)]||`Unknown (${field.value})`):LexeditorUI.formatNumber(field.value))])),
    el("p",{},users===1?"Used by 1 NPC variant.":`Shared by ${users} NPC variants.`));
}
function monsterAttacksSection(){
  const links=state.monsterAttacks;
  if(!links)return LexeditorUI.loadingPanel({label:"Loading attacks"});
  if(!links.rows.length)return LexeditorUI.detailNote("No attack link was resolved for this monster. The Attacks tab lists every attack record.");
  return detailSection({title:"Referenced attacks",body:links.rows.map(attack=>detailField({label:attack.name,
    control:hoverable({content:`#${attack.id} · ${attack.route}`,targetType:"ds1-attack",targetId:attack.id,
      targetLabel:`${attack.name} in Attacks`,preview:()=>attackPreview(attack.id),activate:()=>openAttack(attack.id)})}))});
}
function monsterDetail(groups){
  const links=state.monsterAttacks;
  const attackHelp=links?`Attack records reached from behavior variation ${links.variation} across ${links.behaviorCount} behavior records. `+
    `Direct means a behavior calls the attack; Projectile means a projectile or child projectile does. ${links.unresolved.length} references remain unresolved or lead to effects. `+
    "These are parameter links; they do not prove an animation uses the attack. Hover an attack to preview its damage, and click it to edit it in Attacks.":
    "Attack records reached from this monster's behavior parameters.";
  return tabbedPanel({label:"Monster details",active:state.monsterTab,
    tabs:[{id:"resistances",label:"Resistances"},{id:"attacks",label:"Attacks",help:attackHelp}],
    change:id=>{state.monsterTab=id;render();},
    content:state.monsterTab==="attacks"?monsterAttacksSection():[...groups].map(([title,body])=>detailSection({title,body}))});
}
function detail(){
  const impact=state.row?.impact;
  const title=state.tab==="attacks"?(impact?.variants.length>1?"Shared attack damage":impact?.variants.length===0?"Unresolved attack ownership":"Attack damage"):state.tab==="enemies"?"Monster":"Properties";
  if(!state.row)return detailPanel({title,body:[LexeditorUI.detailNote("Select a record.")]});
  if(key(state.row)!==state.selected)return detailPanel({title,body:[LexeditorUI.loadingPanel({label:"Loading record"})]});
  const groups=fieldSections(state.row);
  if(state.row.table==="NpcParam")return detailPanel({title:state.row.name,body:[monsterDetail(groups)]});
  let help;
  if(impact){
    const examples=impact.variants.slice(0,3).map(n=>`${n.name} #${n.id}`).join(", ");
    help=`Editing this record changes every use of it. Known parameter links reach ${impact.variants.length} NPC variants and ${impact.behaviors.length} behaviors.`+
      (examples?` Examples: ${examples}.`:" Ownership is unresolved.")+
      ` ${impact.bulletReferences.length} projectile records reference this attack ID; player and enemy contexts may differ.`+
      " Animation, script and effect calls are not fully traced, so this is a minimum impact estimate.";
    groups.set("Reference paths",(impact.paths.length?impact.paths:["No behavior link found"]).map((path,index)=>detailField({label:`Path ${index+1}`,control:readonlyField(path),
      help:infoHelp("This parameter link reaches the attack. Projectile paths include child projectiles. It does not prove an animation invokes it.")})));
  }
  return detailPanel({title,help,paginate:{inline:true},
    body:[...groups].map(([title,body])=>detailSection({title,body}))});
}
function renderItems(){
  const noun=state.tab==="attacks"?"attacks":state.tab==="enemies"?"monsters":"items";
  const label=state.tab==="attacks"?"Attacks":state.tab==="enemies"?"Enemies":"Items";
  const view=pagedListDetail({className:"ds1-records",rows:sortedRows(),key,selected:state.selected,slots:false,noun,
    page:state.page,pageSize:state.pageSize,defaultSplit:32,minLeft:230,minRight:380,splitKey:"ds1-items",rowsKey:"ds1-items-"+state.sub,
    search:{key:"ds1-records-search",value:state.query,label:"Search "+noun,change:value=>{state.query=value;state.page=0;render();}},
    sync:next=>{
      state.page=next.page;state.pageSize=next.pageSize;
      if(state.selected!==next.selected){state.selected=next.selected;void loadDetail().then(render).catch(notify);}
    },
    change:next=>{state.page=next.page;state.pageSize=next.pageSize;render();},
    master:({rows:listed,selected,select})=>columnList({rows:listed,key,selected,sortState:state.sort,
      sort:column=>{state.sort={key:column,dir:state.sort.key===column?-state.sort.dir:1};render();},
      select:async row=>{await edits;select(row);state.selected=key(row);await loadDetail();render();},
      columns:[{key:"id",label:"ID",numberedId:true,numeric:true,sortable:true,align:"start"},{key:"name",label:"Name",sortable:true,grow:1}]}),
    detail,emptyDetail:()=>detailPanel({title:"No matching "+noun,body:[LexeditorUI.detailNote("Change the search to find a record.")]})});
  const subtabs=subtabsFor(state.tab);
  // Enemies names its one list (Monsters) so the category reads; Attacks
  // under Attacks would only repeat the tab.
  return el("div",{class:"ds1-items"},subtabBar({tabs:subtabs,showSingle:state.tab==="enemies",order:"given",active:state.sub,label,change:id=>navigate(state.tab,id)}),view);
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
      detailField({label:"SUPPORT",control:readonlyField("Items, monster resistances and enemy attacks"),help:infoHelp("Edit documented item properties, reviewed monster resistances and enemy attack damage. Names are reference labels. Unknown fields and padding stay unchanged. Saves go to the selected mod project.")})]}),
    detailSection({title:"INSTALLED GAME",body:[
      detailField({label:"APPLIED",control:readonlyField(appliedLabel(deploy))}),
      detailField({label:"ORIGINAL PRESERVED",control:readonlyField(deploy.everApplied?(deploy.backupOk?"Yes":"No, needs attention"):"Not yet applied"),
        help:infoHelp("The first Apply keeps one copy of the installed file exactly as it was. Disable always restores that copy.")}),
      detailField({label:"UP TO DATE",control:readonlyField(upToDate),
        help:infoHelp("Apply installs the archive already saved in the mod project. Reapply after every later save that should reach the installed game.")}),
      needsAttentionNote(deploy),
      actionRow(
        el("button",{type:"button",disabled:state.deployBusy||!deploy.isProject||!deploy.sourceReady||deploy.changedExternally,onclick:()=>deploymentAction("apply")},deploy.everApplied?"Reapply":"Apply"),
        el("button",{type:"button",disabled:state.deployBusy||!deploy.everApplied||deploy.changedExternally,onclick:()=>deploymentAction("disable")},"Restore original")
      )].filter(Boolean)}),
    modLoaderSection({loader:deploy.note||"Dark Souls Remastered reads this file as a loose file; no mod loader is installed.",
      output:"Apply replaces the installed param/GameParam/GameParam.parambnd.dcx with the mod project's saved copy, after preserving the original once.",
      order:"One complete parameter archive. Separate projects are not merged; applying a different project replaces what is currently installed.",
      safety:"Apply and Disable touch only param/GameParam/GameParam.parambnd.dcx and refuse to continue if that file changed outside Lexeditor.",
      removal:"Restore original copies the preserved original bytes back over the installed file."})]});
}
function render(){
  document.querySelector("#main").replaceChildren(state.error?LexeditorUI.notice({tone:"warning",message:state.error}):state.tab==="info"?renderInfo():renderItems());
  shell.refresh();
}
async function boot(){
  try{await refreshState();await loadItems();render();}catch(error){state.error=error.message;render();}
  finally{document.body.dataset.ds1Ready=state.error?"error":"true";await LexeditorUI.finishPluginLoading();}
}
window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&(state.dirty||state.pending))event.preventDefault();});
boot();
