"use strict";
const {el,detailPanel,detailSection,detailField,readonlyField,infoHelp,pagedListDetail,columnList,subtabBar,
  actionRow,confirmAction,modLoaderSection,tabbedPanel,hoverable,curveEditor}=LexeditorUI;
const state={tab:"items",sub:"consumables",tabs:[],enemyTabs:[],attackTabs:[],rows:[],selected:null,row:null,dirty:0,pending:0,
  readOnly:true,query:"",page:0,pageSize:20,sort:{key:"name",dir:1},error:"",deployment:null,deployBusy:false,
  monsterTab:"resistances",monsterAttacks:null,tweaks:null,tweakBusy:false,tweaksNeedRebuild:false,
  effectTabs:[],statsTabs:[],animTabs:[],worldTabs:[],animScope:{level:"chars"},nativeRules:null,bandForm:null,bandBusy:false,taeForm:null,taeBusy:false,rowBusy:false,
  assetTabs:[{id:"overrides",label:"Mod files"},{id:"game",label:"Installed game"}],assetDetail:null,assetBusy:false,assetUpload:null,
  assetKind:"models",assetFiles:[],
  dataMap:{rows:[]},mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1],mapView:null,
  mapId:null,mapList:[],mapTab:"maps",mapSelected:null,mapInfo:null,mapCollision:true,mapBusy:false,mapOfferOpen:false,mapGizmo:"move",mapClipboard:null};
let edits=Promise.resolve(),navigation=0,recordsRequest=0,selectVisibleRecord=null,viewportCtl=null;
const attackPreviews=new Map();
const key=row=>`${row.table}:${row.id}`;
const assetKinds=[
  {id:"models",label:"Models",help:"What you see and bump into: character, object and map geometry. Model packages (.chrbnd, .objbnd, .partsbnd), single meshes (.flver) and collision (.hkx)."},
  {id:"textures",label:"Textures",help:"The images on the models: texture packages (.tpf), single images (.dds, .png) and font faces."},
  {id:"sound",label:"Sound effects",help:"FMOD sound banks (.fev, .fsb): swings, hits, footsteps, voices, everything audible but the music. The sfx folder holds particle effects, which are visual and live under Other files."},
  {id:"music",label:"Music",help:"FMOD music banks: area themes and boss music."},
  {id:"other",label:"Other files",help:"Movies, menu interface, scripts, shaders, materials and visual effects: game files no structured editor owns."}];
const assetRows=files=>(files||[]).filter(file=>(file.kind||"other")===state.assetKind)
  .map(file=>({table:"Asset",id:file.relative,name:file.relative,values:{size:file.size}}));
async function setAssetKind(id){
  if(state.assetKind===id)return;
  state.assetKind=id;state.query="";state.page=0;
  state.rows=assetRows(state.assetFiles);
  state.selected=state.rows[0]?key(state.rows[0]):null;
  await loadDetail().catch(notify);render();
}
async function api(path,body){
  const response=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const result=await response.json();
  if(!response.ok||result.error)throw new Error(result.error||response.statusText);
  if("tweaksNeedRebuild" in result)state.tweaksNeedRebuild=result.tweaksNeedRebuild;
  return result;
}
const notify=error=>LexeditorUI.showAlert({title:"Dark Souls",message:error.message||String(error)});
const failMount=(status,text)=>error=>{status.textContent=text;notify(error);};
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
      let refresh=false;
      for(const edit of entry.edits||[entry]){
        const result=await api("/api/edit",{table:edit.table,id:edit.id,field:edit.field,value:edit[side],sub:state.sub});
        state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
        if(state.row&&state.row.table===edit.table&&state.row.id===edit.id)state.row=result.row;
        patchRowValues(edit.table,edit.id,result.values,result.display);
        refresh=refresh||result.refreshRows===true;
      }
      if(refresh)await loadItems();
      // An undone viewport move must move the scene part back too; the
      // reload re-reads the map and restores the selection and gizmo.
      if(state.tab==="maps"&&state.mapView)await reloadViewport(state.mapView.map,state.mapSelected);
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
  host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ds1",name:"Dark Souls Remastered",themeName:"ds1",theme:{accent:"#a4824c","accent-text":"#141210"}},
  tabs:[{id:"items",label:"Items",help:"Edit item properties in the selected mod. Vanilla is read-only. Unknown fields stay protected. Saves do not install a mod."},
    {id:"enemies",label:"Enemies",help:"Edit reviewed monster stats: health, defense, drops, effects and AI links. Behaviors holds action costs and what each behavior calls. AI holds enemy senses, distances and goals. A monster's Attacks tab lists the attack records its parameters reference. Vanilla is read-only. Save changes the mod project."},
    {id:"attacks",label:"Attacks",help:"Edit enemy and player attack damage and hitboxes. The Attacks list holds enemy attacks, Player attacks holds yours, and Projectiles holds flying attacks: arrows, spells and breath. One attack record can serve several monsters or several player moves, so an edit changes every use of it. Vanilla is read-only. Save changes the mod project."},
    {id:"maps",label:"Maps",help:"Browse maps in 3D and move enemy and object placements. Pick a map from the Maps list, click a placement to select it, drag its arrows to move it. Map buttons appear over the picture. Wire boxes mark collision and navigation parts; they show where those parts sit, not their shapes. Vanilla is read-only. Save changes the mod project."},
    {id:"animations",label:"Animations",help:"Edit animation event timing and settings. Pick a character, then an animation, then an event. Add inserts a documented event, and Remove deletes the selected one. Events that share a timestamp change together. Character files this version cannot open are skipped. Vanilla is read-only, and Save changes the mod project."},
    {id:"effects",label:"Effects",help:"Edit buffs, debuffs and equipment passives. A shared effect changes every item or ability using it. Unknown properties stay protected."},
    {id:"stats",label:"Stats",help:"Stat scaling for the Stats Rework. Scaling curves holds the 39 scaling graphs: weapon paths, Max HP, Max MP, defense, resistances, level-up cost and level sync. Weapon upgrades and Armor upgrades hold each upgrade level's multipliers. Full records stay in Items, and no scaling graph here covers stamina recovery or attunement slots."},
    {id:"encumbrance",label:"Encumbrance",help:"Add or merge load ranges. Each band has a movement profile and its own recovery percentage. The last band has no upper limit. Save and Apply to use your rules."},
    {id:"levelup",label:"Level-up gains",help:"Edit what each level-up adds to defense. Each defense grows with your stats and humanity. 0 removes a gain. Vanilla is read-only. Save and Apply to use your values."},
    {id:"world",label:"World",help:"Edit what the world gives you. Drops holds enemy and corpse drops with their rates. Shops holds each merchant's stock and prices. Treasure holds how treasure chests and pickups behave. Vanilla is read-only. Save changes the mod project."},
    {id:"assets",label:"Assets",help:"Replace game files with your own: textures, sounds, movies and models. Mod files holds the replacements the mod carries, and Installed game holds the files it can replace. A preview shows the file the game would load. Replace and Remove save at once. Vanilla is read-only."},
    {id:"misc",label:"Misc."},
    {id:"tweaks",label:"Tweaks",help:"Each tweak is a mod in the library. Switch them in the Mods tab and change their settings here. Changed tweaks rebuild when you save. Restore original removes them from the game."}],
  activeTab:()=>state.tab,navigate:tab=>navigate(tab),
  info:()=>navigate("info"),infoActive:()=>state.tab==="info",
  help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open Dark Souls Data Map",
  readonly:()=>state.readOnly,dirtyCount:()=>state.dirty+state.pending+(state.tweaksNeedRebuild?1:0),
  pendingChanges:()=>[...(state.changes||[]),...(state.tweaksNeedRebuild?[{label:"Installed tweaks",before:"Last build",after:"Rebuilt"}]:[])],
  save,discard,history:fieldHistory
});
const subtabsFor=tab=>tab==="enemies"?state.enemyTabs:tab==="attacks"?state.attackTabs:tab==="animations"?state.animTabs:tab==="effects"?state.effectTabs:
  tab==="stats"?state.statsTabs:
  tab==="world"?state.worldTabs:
  tab==="assets"?state.assetTabs:
  tab==="encumbrance"?[{id:"encumbrance",label:"Bands"},{id:"encumbrance-overrides",label:"Overrides"}]:tab==="levelup"?[{id:"levelup",label:"Gains"}]:state.tabs;
async function refreshState(){
  const result=await api("/api/state");
  state.tabs=result.tabs;state.enemyTabs=result.enemyTabs;state.attackTabs=result.attackTabs;
  state.effectTabs=result.effectTabs||[];state.statsTabs=result.statsTabs||[];state.animTabs=result.animTabs||[];state.worldTabs=result.worldTabs||[];state.nativeRules=result.nativeRules;
  state.readOnly=result.readOnly;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
}
function sortedRows(){
  const query=state.query.toLowerCase();
  const filtered=state.rows.filter(row=>(row.id+" "+row.name+" "+(row.range||"")).toLowerCase().includes(query));
  if(state.tab==="encumbrance"||state.tab==="levelup"||(state.tab==="animations"&&state.animScope.level==="events"))return filtered;
  // The game's own order (by record) breaks ties.
  return filtered.sort((a,b)=>LexeditorUI.compareRecords(a,b,state.sort)||a.id-b.id);
}
const isDrillRow=row=>state.tab==="animations"&&(String(row.id).startsWith("char:")||String(row.id).startsWith("anim:"));
async function drillAnimations(row){
  const previous=state.animScope;
  if(String(row.id).startsWith("char:")){
    state.animScope={level:"anims",binder:row.table,charName:row.name};
  }else{
    const rest=String(row.id).slice(5),pipe=rest.lastIndexOf("|");
    state.animScope={level:"events",binder:row.table,tae:rest.slice(0,pipe),anim:rest.slice(pipe+1),
      charName:state.animScope.charName||row.table,animName:row.name};
  }
  state.query="";state.page=0;state.selected=null;state.row=null;
  try{await loadItems();}
  catch(error){state.animScope=previous;await loadItems();throw error;}
  render();
}
async function loadItems(){
  const request=++recordsRequest;
  const sub=state.sub;
  let url="/api/table?tab="+encodeURIComponent(sub);
  if(state.tab==="animations"&&state.sub!=="playback"){
    const scope=state.animScope;
    url=`/api/table?tab=animations&scope=${scope.level}&binder=${encodeURIComponent(scope.binder||"")}&tae=${encodeURIComponent(scope.tae||"")}&anim=${scope.anim??""}`;
  }
  else if(state.tab==="assets")url="/api/assets?scope="+(sub==="game"?"game":"overrides");
  const result=await api(url);
  if(request!==recordsRequest||state.sub!==sub)return;
  if(state.tab==="assets"){state.assetFiles=result.files;state.rows=assetRows(result.files);}
  else state.rows=result.rows;
  state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
  if(!state.rows.some(row=>key(row)===state.selected))state.selected=state.rows[0]?key(state.rows[0]):null;
  await loadDetail();
}
async function loadDetail(){
  const row=state.rows.find(row=>key(row)===state.selected);
  if(!row||isDrillRow(row)){state.row=null;state.monsterAttacks=null;state.assetDetail=null;return;}
  if(row.table==="Asset"){
    state.assetDetail=null;
    const detail=await api(`/api/assets?scope=textures&side=${state.sub==="game"?"game":"mod"}&file=${encodeURIComponent(row.id)}`);
    if(state.selected!==key(row))return;
    state.row={table:"Asset",id:row.id,name:row.name};state.assetDetail=detail;state.monsterAttacks=null;return;
  }
  if(row.table==="MapView"){
    state.mapView=null;
    const detail=await api(`/api/map/view?map=${encodeURIComponent(row.id)}`);
    if(state.selected!==key(row))return;
    state.row={table:"MapView",id:row.id,name:row.name};state.mapView=detail;state.monsterAttacks=null;return;
  }
  if(row.table==="EnemyModel"){
    state.chrView=null;
    const detail=await api(`/api/chr/view?npc=${row.id}`);
    if(state.selected!==key(row))return;
    state.row={table:"EnemyModel",id:row.id,name:row.name};state.chrView=detail;state.monsterAttacks=null;return;
  }
  if(row.table==="AnimPlayback"){
    state.animView=null;
    const detail=await api(`/api/anim/list?chr=${encodeURIComponent(row.id)}`);
    if(state.selected!==key(row))return;
    state.row={table:"AnimPlayback",id:row.id,name:row.name};state.animView=detail;state.monsterAttacks=null;return;
  }
  const [result,attacks]=await Promise.all([api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}&sub=${encodeURIComponent(state.sub)}`),
    row.table==="NpcParam"?api(`/api/attacks?monster=${row.id}`):null]);
  if(state.selected!==key(row))return;
  state.row=result.row;state.monsterAttacks=attacks;
}
async function loadTweaks(){
  state.tweaks=await api("/api/tweaks");
  state.tweaksNeedRebuild=!!state.tweaks.needsRebuild;
}
async function loadDeployment(){
  state.deployment=await api("/api/deployment");
}
async function navigate(tab,sub=state.sub,selected=null){
  const token=++navigation;await edits;
  const changedTab=tab!==state.tab;state.tab=tab;state.bandForm=null;state.taeForm=null;
  if(tab==="enemies"&&!state.enemyTabs.some(entry=>entry.id===sub))sub="monsters";
  else if(tab==="attacks"&&!state.attackTabs.some(entry=>entry.id===sub))sub="attacks";
  else if(tab==="maps")sub="placements";
  else if(tab==="animations"&&!state.animTabs.some(entry=>entry.id===sub))sub="animations";
  else if(tab==="effects"&&!state.effectTabs.some(entry=>entry.id===sub))sub="effects-all";
  // Without the curve table, Stats opens on the first list with rows instead of an error.
  else if(tab==="stats"&&!state.statsTabs.some(entry=>entry.id===sub))sub=(state.statsTabs.find(entry=>entry.id==="curves")||{}).count?"curves":((state.statsTabs.find(entry=>entry.count)||{}).id||"curves");
  else if(tab==="encumbrance"&&!["encumbrance","encumbrance-overrides"].includes(sub))sub="encumbrance";
  else if(tab==="levelup")sub="levelup";
  else if(tab==="misc")sub="misc";
  else if(tab==="world"&&!state.worldTabs.some(entry=>entry.id===sub))sub="drops";
  else if(tab==="assets"&&!state.assetTabs.some(entry=>entry.id===sub))sub="overrides";
  else if(tab==="items"&&!state.tabs.some(entry=>entry.id===sub))sub="consumables";
  if(tab==="animations"&&changedTab)state.animScope={level:"chars"};
  if(sub!==state.sub||changedTab||selected){state.sub=sub;state.selected=selected;state.query="";state.page=0;}
  try{
    if(["items","enemies","attacks","maps","animations","effects","stats","encumbrance","levelup","misc","world","assets"].includes(tab))await loadItems();
    if(tab==="maps")await loadMaps();
    else if(tab==="datamap")state.dataMap=await api("/api/data-map");else if(tab==="info")await loadDeployment();else if(tab==="tweaks")await loadTweaks();
    if(token!==navigation)return;
    // A link lands on the page that holds its record, not on page one.
    if(tab==="maps"&&selected)state.mapTab="placements";
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
    apply:{title:"Apply this mod to the installed game?",message:"Lexeditor installs the saved parameter archive, map files and character files and composes this project's native rules with enabled library tweaks. Each original is preserved once. Close the game first and test native changes offline.",confirmLabel:"Apply"},
    disable:{title:"Restore the original installed files?",message:"Lexeditor restores its owned parameter, map, character and executable changes. Project values and library tweak switches remain unchanged.",confirmLabel:"Restore original"}
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
  try{
    const result=await api("/api/save",{});attackPreviews.clear();await refreshState();
    if(state.tab==="tweaks"){await loadTweaks();render();}else shell.refresh();
    if(result.tweaksError)LexeditorUI.showAlert({title:"Tweaks were not rebuilt",message:result.tweaksError});
    else if(result.tweaksDeferred)LexeditorUI.showToast("Changes saved. Close the game, then save again to rebuild the tweaks.");
    else if(result.tweaksRebuilt)LexeditorUI.showToast("Changes saved and tweaks rebuilt.");
    else LexeditorUI.showToast("Changes saved to the mod project.");
  }
  catch(error){notify(error);throw error;}
}
async function discard(){
  await edits;state.bandForm=null;state.taeForm=null;
  try{await api("/api/discard",{});attackPreviews.clear();fieldHistory.clear();await refreshState();
    if(["info","tweaks","datamap"].includes(state.tab))await navigate(state.tab);
    else{await loadItems();if(state.tab==="maps")await loadMaps();render();}}catch(error){notify(error);}
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
function patchRowValues(table,id,values,display){
  const target=state.rows.find(row=>row.table===table&&row.id===id);
  if(!target||!values)return;
  target.values=values;target.display=display||{};
}function syncDetailControl(propertyKey,value,control){
  // Computed fields (Effective HP, absorption) move when their inputs do;
  // their detail controls repaint in place, sliders included.
  for(const other of state.pagedView?.querySelectorAll(`[data-field-key="${CSS.escape(propertyKey)}"]`)??[]){
    if(other===control||other===document.activeElement)continue;
    if(other.type==="checkbox")other.checked=!!value;
    else if("value" in other){
      other.value=(other.disabled&&other.readOnly&&typeof value==="number")?LexeditorUI.formatNumber(value):String(value);
      other.__lexValueSliderPaint?.();
    }
  }
}
function commit(row,field,value,control){
  if(state.readOnly||!field.editable)return;
  state.pending++;shell.refresh();
  edits=edits.then(async()=>{
    // The value before this edit, as the record now stands (an earlier edit
    // may have changed it since the page drew).
    const live=state.row&&key(state.row)===key(row)?state.row:row;
    const before=live.fields?.find(item=>item.key===field.key)?.value??live.values?.[field.key];
    try{
      const result=await api("/api/edit",{table:row.table,id:row.id,field:field.key,value,sub:state.sub});
      const after=result.row.fields.find(item=>item.key===field.key)?.value;
      const done=[{table:row.table,id:row.id,field:field.key,before,after}];
      let latest=result;
      const updates=[{id:row.id,result}];
      // The other selected records of this table get the same value.
      for(const other of (state.selection||[]).filter(k=>k!==key(row)&&k.startsWith(row.table+":"))){
        const id=Number(other.slice(row.table.length+1));
        const prior=(await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${id}&sub=${encodeURIComponent(state.sub)}`)).row.fields.find(item=>item.key===field.key)?.value;
        const changed=await api("/api/edit",{table:row.table,id,field:field.key,value,sub:state.sub});
        latest=changed;
        updates.push({id,result:changed});
        done.push({table:row.table,id,field:field.key,before:prior,after:changed.row.fields.find(item=>item.key===field.key)?.value});
      }
      fieldHistory.record(done.length>1?{edits:done}:done[0]);
      // The count and the list come from the last edit made, which saw them all.
      state.dirty=latest.dirtyCount;state.changes=latest.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;attackPreviews.delete(row.id);
      if(state.row&&key(state.row)===key(row)){
        const priorValues=new Map(state.row.fields.map(item=>[item.key,item.value]));
        state.row=result.row;
        for(const item of result.row.fields){
          if(item.key===field.key||priorValues.get(item.key)===item.value)continue;
          syncDetailControl(item.key,item.value,control);
        }
      }
      const changed=result.row.fields.find(item=>item.key===field.key);
      if(control?.isConnected){if(field.type==="bool")control.checked=!!changed.value;else control.value=String(changed.value);}
      syncDetailControl(field.key,changed.value,control);
      if(row.table==="NativeRules"||["goodsType","weaponCategory"].includes(field.key)){await loadItems();render();}
      else{
        for(const update of updates)patchRowValues(row.table,update.id,update.result.values,update.result.display);
        if(updates.some(update=>update.result.refreshRows))await loadItems().then(render);
        else if(field.key.startsWith("residentSpEffectId")||["refId","refCategory","replaceSpEffectId","cycleOccurrenceSpEffectId","atkOccurrenceSpEffectId"].includes(field.key))render();
        else if(String(state.sort?.key||"").startsWith("pin:"))render();
        else state.pagedView?.refreshValues?.();
      }
    }catch(error){
      notify(error);
      const result=await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}&sub=${encodeURIComponent(state.sub)}`);
      const original=result.row.fields.find(item=>item.key===field.key);
      if(control?.isConnected){if(field.type==="bool")control.checked=!!original.value;else control.value=String(original.value);}
    }finally{state.pending--;if(row.table==="NativeRules")render();else shell.refresh();}
  }).catch(notify);
}
function describePinnedCell(propertyKey){
  // Field shape is per table, not per row: effect options are global and
  // bounds come from the schema, so the open record describes every row.
  const field=(state.row?.fields||[]).find(item=>item.key===propertyKey);
  if(!field||!field.editable||field.type==="longtext")return null;
  const entries=field.type==="enum"?Object.entries(field.enum||{}):null;
  return {editable:true,type:field.type,numeric:field.type==="number",
    minimum:field.minimum,maximum:field.maximum,
    step:field.step??(/^(f|angle)/.test(field.dtype||"")?"any":1),
    choices:entries&&entries.length?entries:field.type==="bool"?[[1,"Yes"],[0,"No"]]:null};
}
function commitPinnedCell(record,propertyKey,value){
  const meta=(state.row?.fields||[]).find(item=>item.key===propertyKey)||{};
  const field={key:propertyKey,editable:true,label:meta.label||propertyKey,type:meta.type||"text"};
  commit({table:record.table,id:record.id},field,field.type==="text"?value:Number(value),null);
}
const PERCENT=/\s*\(%\)$/;
const shownLabel=field=>field.label.replace(PERCENT,"");
function controlFor(row,field){
  const plain=plainControlFor(row,field);
  const control=PERCENT.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"%"):plain;
  if(!field.editable||field.vanilla===null||field.vanilla===undefined||field.type==="text"||field.type==="longtext")return control;
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
    maxlength:field.maxLength||48,required:field.required??true,onchange:event=>{
      const input=event.target;
      if(field.required!==false&&!input.value.trim()||!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,input.value,input);
    }});
  if(field.type==="longtext")return el("textarea",{...attrs,value:field.value,rows:6,
    maxlength:field.maxLength||2000,"aria-multiline":"true",onchange:event=>{
      const input=event.target;
      if(!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,input.value,input);
    }});
  if(field.type==="enum"){
    const choices=Object.entries(field.enum);
    if(!choices.some(([value])=>value===String(field.value)))choices.unshift([String(field.value),`Unknown (${field.value})`]);
    const control=el("select",{...attrs,onchange:event=>commit(row,field,Number(event.target.value),event.target)});
    const fill=()=>{control.replaceChildren(...choices.map(([value,label])=>el("option",{value,disabled:!(value in field.enum)},label)));const live=state.row?.fields?.find(item=>item.key===field.key)?.value;control.value=String(live??field.value);};
    if(choices.length>200){
      // A 4,000-effect dropdown built on every render freezes the pane;
      // it shows its value now and fills when first scrolled into view.
      control.replaceChildren(el("option",{value:String(field.value)},field.enum[String(field.value)]||`Unknown (${field.value})`));
      const show=()=>{fill();observer?.disconnect();};
      const observer=("IntersectionObserver" in window)?new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting))show();}):null;
      if(observer)observer.observe(control);else fill();
      control.addEventListener("focus",show,{once:true});
    }else fill();
    return control;
  }
  return el("input",{...attrs,type:"number",value:field.value,min:field.minimum,max:field.maximum,
    step:field.step??(/^(f|angle)/.test(field.dtype)?"any":1),onchange:event=>{
      const input=event.target;if(!input.value.trim()||!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,Number(input.value),input);
    }});
}
const GROUP_ORDER=["Description","Basics","Defense","Absorption","Combat","Requirements & costs","Thresholds","Growth","Curve shape","Level-up cost","Effects & references","Upgrades",
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
  const tabs=[{id:"resistances",label:"Stats"},{id:"attacks",label:"Attacks",help:attackHelp}];
  if(effects)tabs.push({id:"effects",label:"Effects",help:"Effects this monster carries. Changing a shared effect changes every use of it."});
  const active=state.monsterTab==="effects"&&!effects?"resistances":state.monsterTab;
  return tabbedPanel({label:"Monster details",active,tabs,
    change:id=>{state.monsterTab=id;render();},
    content:active==="attacks"?monsterAttacksSection()
      :active==="effects"?[detailSection({title:"Effects",body:effects})]
      :[...groups].map(([title,body])=>detailSection({title,body}))});
}
function formatAssetSize(size){
  if(!(size>=0))return "Unknown size";
  if(size<1024)return size+" B";
  const units=["KB","MB","GB"];
  let value=size/1024,unit=0;
  while(value>=1024&&unit<units.length-1){value/=1024;unit++;}
  return (value>=100?Math.round(value):Math.round(value*10)/10)+" "+units[unit];
}
function bytesToBase64(buffer){
  const bytes=new Uint8Array(buffer);
  let text="";
  for(let index=0;index<bytes.length;index+=8192)
    text+=String.fromCharCode.apply(null,bytes.subarray(index,index+8192));
  return btoa(text);
}
function renderAssetDetail(){
  const row=state.rows.find(row=>key(row)===state.selected);
  if(!row)return detailPanel({title:"File",body:[LexeditorUI.detailNote("Select a file.")]});
  if(!state.row||key(state.row)!==state.selected||!state.assetDetail)
    return detailPanel({title:row.name,body:[LexeditorUI.loadingPanel({label:"Loading file"})]});
  const info=state.assetDetail;
  const fromMod=info.source==="mod";
  const busy=state.assetBusy;
  const locked=state.readOnly||busy;
  const picker=el("input",{type:"file",style:"display:none","aria-hidden":"true",tabindex:"-1",
    onchange:event=>{const file=event.target.files[0];event.target.value="";if(file)void uploadAsset(row.id,file);}});
  const progress=state.assetUpload?`Uploading ${formatAssetSize(state.assetUpload.received)} of ${formatAssetSize(state.assetUpload.total)}`:"";
  const textures=(info.textures||[]).map(texture=>{
    const url=`/api/assets/preview?side=${info.source}&file=${encodeURIComponent(row.id)}&member=${encodeURIComponent(texture.member||"")}&index=${texture.index}`;
    return detailField({label:texture.name,
      control:el("img",{src:url,alt:texture.name,style:"max-width:100%;height:auto",loading:"lazy"}),
      help:infoHelp(`${texture.width} by ${texture.height}, ${texture.format}. Preview of the ${fromMod?"mod":"installed game"} file, shrunk to fit.`)});
  });
  return detailPanel({title:row.name,meta:fromMod?"Mod file":"Installed game file",
    help:"Replace carries your file in the mod under this same path; the installed game is untouched until Apply. Remove drops the mod's copy, so the game file shows again. Both save at once.",
    body:[
      detailSection({title:"FILE",body:[
        detailField({label:"SOURCE",control:readonlyField(fromMod?"Mod file":"Installed game file"),
          help:infoHelp(fromMod?"The mod carries this file. The game loads it once the mod is applied.":"No mod file replaces this yet. The game loads its own copy.")}),
        detailField({label:"SIZE",control:readonlyField(formatAssetSize(info.size))}),
        detailField({label:"ACTIONS",control:LexeditorUI.stack(
          el("span",{style:"display:flex;gap:8px;flex-wrap:wrap"},
            el("button",{type:"button","data-asset-action":"replace",disabled:locked,onclick:()=>picker.click(),
              title:state.readOnly?"Open a mod project to replace files":"Replace this file with one from your disk"},"Replace…"),
            fromMod?el("button",{type:"button","data-asset-action":"remove",disabled:locked,onclick:()=>removeAssetOverride(row.id)},"Remove override"):null),
          picker,
          progress?el("span",{role:"status"},progress):null),
          help:infoHelp("Replace keeps your file's bytes as they are. It must open as the same kind of file it replaces.")})]}),
      detailSection({title:"PREVIEW",body:textures.length?textures:[
        detailField({label:"TEXTURES",control:readonlyField("No preview"),
          help:infoHelp("Only textures preview. Sounds, movies and models still replace as whole files.")})]})]});
}
async function uploadAsset(target,file){
  if(state.assetBusy)return;
  if(!file.size){notify(new Error("That file is empty."));return;}
  if(file.size>512*1024*1024){notify(new Error("That file is too large to carry as an override."));return;}
  const id=crypto.randomUUID();
  const piece=768*1024;
  let offset=0,files=null;
  state.assetBusy=true;state.assetUpload={received:0,total:file.size};render();
  try{
    while(offset<file.size){
      const end=Math.min(offset+piece,file.size);
      const data=bytesToBase64(await file.slice(offset,end).arrayBuffer());
      const result=await api("/api/assets/upload",{id,relative:target,total:file.size,offset,data,final:end>=file.size});
      offset=result.upload.received??result.upload.size??file.size;files=result.files;
      state.assetUpload={received:offset,total:file.size};render();
    }
    state.assetBusy=false;state.assetUpload=null;
    if(files){state.assetFiles=files;const entry=files.find(file=>file.relative===target);
      if(entry)state.assetKind=entry.kind||"other";state.rows=assetRows(files);}
    // An upload from Installed game lands in Mod files, where it now lives.
    if(state.sub==="game")state.sub="overrides";
    state.selected=`Asset:${target}`;
    await loadDetail();render();
  }
  catch(error){state.assetBusy=false;state.assetUpload=null;render();notify(error);}
}
async function removeAssetOverride(target){
  if(state.assetBusy)return;
  if(!await confirmAction({title:"Remove this override?",message:"The mod stops carrying this file, and the installed game file shows again.",confirmLabel:"Remove",cancelLabel:"Cancel"}))return;
  state.assetBusy=true;render();
  try{
    const result=await api("/api/assets/remove",{relative:target});
    state.assetFiles=result.files;state.rows=assetRows(result.files);
    state.selected=state.rows[0]?key(state.rows[0]):null;state.row=null;state.assetDetail=null;
    await loadDetail();
  }
  catch(error){notify(error);}
  finally{state.assetBusy=false;render();}
}
function rowActionButtons(kind){
  const locked=state.readOnly||state.rowBusy;
  const playerStart=kind==="placement"&&state.row.kind==="Player";
  const nouns=kind==="placement"?["placement","map"]:["record","table"];
  return [el("button",{type:"button","data-row-action":"duplicate","data-row-kind":kind,disabled:locked,
      title:state.readOnly?`Open a mod project to add ${nouns[0]}s`:`Copy this ${nouns[0]} under the next free ID`,
      onclick:()=>duplicateRow(kind)},"Duplicate"),
    el("button",{type:"button","data-row-action":"remove","data-row-kind":kind,disabled:locked||playerStart,
      title:playerStart?"The player start cannot be removed":state.readOnly?`Open a mod project to remove ${nouns[0]}s`:`Remove this ${nouns[0]} from its ${nouns[1]}`,
      onclick:()=>removeRow(kind)},"Remove")];
}
async function refreshMapsAfterStructure(){
  const current=state.rows.find(row=>key(row)===state.selected);
  if(current)state.mapId=current.table;
  state.mapList=(await api("/api/table?tab=viewport")).rows;
  state.mapView=state.mapId?await api(`/api/map/view?map=${encodeURIComponent(state.mapId)}`):null;
  clampMapSelection();
}
async function duplicateRow(kind){
  if(state.rowBusy||!state.row)return;
  const placement=kind==="placement";
  state.rowBusy=true;render();
  try{
    const result=placement?await api("/api/placements/add",{map:state.row.table,id:state.row.id})
      :await api("/api/rows/add",{table:state.row.table,id:state.row.id});
    state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
    await loadItems();
    state.selected=key(result.row);
    const index=sortedRows().findIndex(row=>key(row)===state.selected);
    if(index>=0)state.page=Math.floor(index/state.pageSize);
    await loadDetail();
    if(placement&&state.tab==="maps")await refreshMapsAfterStructure();
  }
  catch(error){notify(error);}
  finally{state.rowBusy=false;render();}
}
async function removeRow(kind){
  if(state.rowBusy||!state.row)return;
  const placement=kind==="placement";
  const impact=!placement&&state.tab==="attacks"&&state.row.impact
    ?` It is reached by ${state.row.impact.variants.length} NPC variants and ${state.row.impact.behaviors.length} behaviors.`:"";
  if(!await confirmAction({title:placement?"Remove this placement?":"Remove this record?",
    message:(placement?"The placement leaves the map. Its bytes stay in the file, unused."
      :"The record leaves its table. Anything that points at it will point at nothing.")+impact,
    confirmLabel:"Remove",cancelLabel:"Cancel"}))return;
  state.rowBusy=true;render();
  try{
    const result=placement?await api("/api/placements/remove",{map:state.row.table,id:state.row.id})
      :await api("/api/rows/remove",{table:state.row.table,id:state.row.id});
    state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
    await loadItems();
    state.selected=state.rows[0]?key(state.rows[0]):null;state.row=null;
    await loadDetail();
    if(placement&&state.tab==="maps")await refreshMapsAfterStructure();
  }
  catch(error){notify(error);}
  finally{state.rowBusy=false;render();}
}
// Between stages the game blends with a power shaped by the left stage's
// Curve shape value: a positive shape is the exponent, a negative shape
// inverts it (a fast start instead of a slow one), and 1 draws straight.
// Zero is plotted straight: the only vanilla zero-shape rows are the
// level-up cost row, whose stages are unused, and row 150, whose shaping
// is undocumented. Checked against the published hit-point chart (level
// 5 vitality reads 471, level 40 reads 1325) within rounding.
function curveExponent(shape){
  if(!(shape>0))return shape<0?-1/shape:1;
  return shape;
}
function curveDetail(actions,groups){
  const row=state.row;
  const at=key=>Number(row.fields.find(item=>item.key===key)?.value??0);
  const stages=[0,1,2,3,4].map(i=>at(`stageMaxVal${i}`));
  if(stages.every(value=>value===0)){
    // The level-up cost row has no stages to plot, and its soul price
    // comes from the four cost fields by an undocumented formula, so it
    // keeps the plain field list.
    return detailPanel({title:row.name,help:row.help,actions,
      body:[...groups].map(([title,body])=>detailSection({title,body}))});
  }
  const host=el("div",{class:"ds1-curve-host"});
  let graph=null;
  const live=key=>{
    const input=host.querySelector(`input[data-field-key="${key}"]`);
    const value=input?Number(input.value):NaN;
    return Number.isFinite(value)?value:at(key);
  };
  const evaluate=x=>{
    const points=[0,1,2,3,4].map(i=>[live(`stageMaxVal${i}`),live(`stageMaxGrowVal${i}`)]);
    if(!(x>points[0][0]))return points[0][1];
    for(let i=0;i<4;i++){
      const [lo,loValue]=points[i],[hi,hiValue]=points[i+1];
      if(x>hi&&i<3)continue;
      const raw=hi>lo?(x-lo)/(hi-lo):1;
      const t=Math.min(1,Math.max(0,raw));
      return loValue+(hiValue-loValue)*Math.pow(t,curveExponent(live(`adjPt_maxGrowVal${i}`)));
    }
    return points[4][1];
  };
  const variables=row.fields.map(field=>{
    const digit=Number(field.key.slice(-1));
    const short=field.key.startsWith("stageMaxVal")?`T${digit+1}`
      :field.key.startsWith("stageMaxGrowVal")?`V${digit+1}`
      :field.key.startsWith("adjPt_maxGrowVal")?`S${digit+1}`
      :field.key==="init_inclination_soul"?"C1":field.key==="adjustment_value"?"C2"
      :field.key==="boundry_inclination_soul"?"C3":"C4";
    const control=plainControlFor(row,field);
    if(control instanceof Element&&field.label)control.title=field.label;
    control.addEventListener?.("change",()=>{edits.then(()=>{graph?.refreshCurve?.();});});
    return {label:short,control};
  });
  const ends=[0,1,2,3,4].map(i=>at(`stageMaxGrowVal${i}`));
  const floor=Math.min(0,...ends),ceil=Math.max(...ends);
  graph=curveEditor({title:row.name,overlayExtrema:true,variables,
    domain:{min:stages[0],max:stages[4]>stages[0]?stages[4]:stages[0]+1},
    range:{min:floor,max:ceil>floor?ceil:floor+1},
    graphLabel:`${row.name} from ${stages[0]} to ${stages[4]}`,evaluate});
  graph.dataset.curveRow=String(row.id);
  graph.curveEvaluate=evaluate;
  host.append(graph);
  return detailPanel({title:row.name,help:row.help,actions,
    body:[detailSection({title:"GRAPH",
      help:infoHelp("The line passes exactly through every stage point; between stages it blends with the left stage's Curve shape value. A shape of 1 draws straight, a higher shape starts slow, and a negative shape starts fast. T1-T5 are the stage thresholds, V1-V5 their values, S1-S5 the shaping, C1-C4 the level-up cost fields. Edit every value from the variables drawer over the graph."),
      body:[host]})]});
}
function detail(){
  const impact=state.row?.impact;
  // A record's heading is its name, on every tab. An attack's sharing is
  // said under it, never in its place.
  const noun=state.tab==="attacks"?(state.sub==="projectiles"?"Projectile":"Attack"):state.tab==="enemies"?(state.sub==="behaviors"?"Behavior":state.sub==="ai"?"AI record":"Monster"):state.tab==="maps"?"Placement":state.tab==="animations"?(state.animScope.level==="chars"?"Character":state.animScope.level==="anims"?"Animation":"Event"):state.tab==="effects"?"Effect":state.tab==="encumbrance"?"Load band":state.tab==="levelup"?"Defense":state.tab==="stats"?(state.sub==="curves"?"Curve":state.sub==="upgrade-materials"?"Material set":"Upgrade"):state.tab==="world"?(state.sub==="shops"?"Shop entry":state.sub==="treasure"?"Treasure":"Drop"):"Item";
  const drillRow=state.tab==="animations"&&!state.row?state.rows.find(row=>key(row)===state.selected):null;
  if(drillRow&&isDrillRow(drillRow)){
    const opening=String(drillRow.id).startsWith("char:");
    const sub=opening?"Character file: "+drillRow.values.binder:`${drillRow.values.tae} · animation ${drillRow.values.animId} · ${drillRow.values.events} events`;
    return detailPanel({title:drillRow.name,meta:sub,body:[
      detailSection({title:opening?"CHARACTER":"ANIMATION",body:[
        detailField({label:opening?"CHARACTER":"ANIMATION",control:el("button",{type:"button","data-anim-open":drillRow.id,
          onclick:()=>drillAnimations(drillRow).catch(notify)},opening?"Open character":"Open animation"),
          help:infoHelp(opening?"List this character's animations.":"List this animation's events.")})]})]});
  }
  if(state.tab==="assets")return renderAssetDetail();
  if(!state.row){
    if(state.tab==="animations"&&state.animScope.level==="events")
      return detailPanel({title:"Event",actions:taeActions().slice(0,1),
        body:[LexeditorUI.detailNote(state.rows.length?"Select an event, or add one.":"This animation has no events yet. Add the first one.")]});
    return detailPanel({title:noun,body:[LexeditorUI.detailNote("Select a record.")]});
  }
  if(key(state.row)!==state.selected)return detailPanel({title:noun,body:[LexeditorUI.loadingPanel({label:"Loading record"})]});
  if(state.bandForm&&state.bandForm.id===state.row.id)return renderBandForm();
  if(state.taeForm&&state.tab==="animations"&&state.animScope.level==="events"&&state.taeForm.tae===state.animScope.tae&&String(state.taeForm.anim)===String(state.animScope.anim))return renderTaeForm();
  const title=state.row.name;
  const meta=state.tab==="attacks"&&impact?(impact.variants.length>1?"Shared attack damage":impact.variants.length===0?"Unresolved attack ownership":"Attack damage"):state.tab==="maps"&&state.row?`${state.row.map} · model ${state.row.model}`:state.tab==="animations"&&state.row?`${state.row.binder} · ${state.row.tae} · ${state.row.animName}`:"";
  const groups=fieldSections(state.row);
  const eventRowEarly=state.tab==="animations"&&state.animScope.level==="events"&&String(state.row.id||"").startsWith("ev:");
  const tableEarly=String(state.row.table||"");
  const msbRowEarly=tableEarly.endsWith(".msb");
  const paramRowEarly=!msbRowEarly&&!tableEarly.endsWith(".anibnd.dcx")&&state.row.table!=="NativeRules"&&state.row.table!=="Asset"&&state.row.table!=="MenuText";
  const rowActionsEarly=state.row.band?bandActions():eventRowEarly?taeActions():msbRowEarly?rowActionButtons("placement"):paramRowEarly?rowActionButtons("record"):[];
  if(state.row.table==="NpcParam")return detailPanel({title:state.row.name,actions:rowActionsEarly,body:[monsterDetail(groups)]});
  if(state.tab==="stats"&&state.sub==="curves"&&paramRowEarly)return curveDetail(rowActionsEarly,groups);
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
  return detailPanel({title,meta,help,actions:rowActionsEarly,
    body:[...groups].map(([title,body])=>detailSection({title,body}))});
}
function taeActions(){
  const disabled=state.readOnly||state.taeBusy||state.pending>0;
  return [
    el("button",{type:"button",disabled,"data-tae-action":"add",onclick:()=>beginTaeForm().catch(notify)},"Add event"),
    el("button",{type:"button",disabled,"data-tae-action":"remove",onclick:()=>removeTaeEvent().catch(notify)},"Remove event")
  ];
}
let taeEventTypes=null;
async function beginTaeForm(){
  if(state.readOnly||state.taeBusy||state.pending||state.tab!=="animations"||state.animScope.level!=="events")return;
  const scope=state.animScope;
  if(taeEventTypes===null)taeEventTypes=(await api("/api/table?tab=animations&scope=eventTypes")).types;
  const field=key=>state.row?.fields.find(item=>item.key===key)?.value;
  state.taeForm={binder:scope.binder,tae:scope.tae,anim:scope.anim,type:"66",
    start:String(field("start")??0),end:String(field("end")??1)};
  render();
}
function renderTaeForm(){
  const form=state.taeForm;
  const type=el("select",{"aria-label":"Event type","data-tae-input":"type",disabled:state.taeBusy,
    onchange:event=>{form.type=event.target.value;render();}},
    ...taeEventTypes.map(entry=>el("option",{value:String(entry.type)},entry.label)));
  type.value=form.type;
  const start=el("input",{type:"number","aria-label":"Start (s)","data-tae-input":"start",step:"any",value:form.start,disabled:state.taeBusy,
    oninput:event=>{form.start=event.target.value;}});
  const end=el("input",{type:"number","aria-label":"End (s)","data-tae-input":"end",step:"any",value:form.end,disabled:state.taeBusy,
    oninput:event=>{form.end=event.target.value;}});
  return detailPanel({title:"Add event",
    actions:[
      el("button",{type:"button",disabled:state.taeBusy,
        onclick:()=>{
          if([start,end].some(input=>!input.value.trim()||!input.checkValidity())){
            [start,end].forEach(input=>input.reportValidity());return;
          }
          submitTaeForm(form);
        }},"Create event"),
      el("button",{type:"button",disabled:state.taeBusy,onclick:()=>{state.taeForm=null;render();}},"Cancel")],
    body:[detailSection({title:"Event",body:[
      detailField({label:"Event type",control:type,
        help:infoHelp("Which documented event to add. Its values start at 0, so set them after. Only documented types can be added.")}),
      detailField({label:"Start (s)",control:start}),
      detailField({label:"End (s)",control:end})]})]});
}
function submitTaeForm(form){
  if(state.taeBusy||state.readOnly||state.taeForm!==form)return;
  state.taeBusy=true;state.pending++;render();
  edits=edits.then(async()=>{
    try{
      const result=await api("/api/tae/add",{table:form.binder,tae:form.tae,anim:form.anim,
        type:Number(form.type),start:Number(form.start),end:Number(form.end)});
      state.rows=result.events;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
      state.taeForm=null;state.selected=key(result.row);state.query="";
      await loadItems();
      const index=sortedRows().findIndex(row=>key(row)===state.selected);
      state.page=Math.max(0,Math.floor(index/state.pageSize));
    }catch(error){
      state.taeForm=null;await refreshState();await loadItems();notify(error);
    }finally{
      state.pending--;state.taeBusy=false;render();revealSelection();
    }
  }).catch(notify);
}
async function removeTaeEvent(){
  if(state.readOnly||state.taeBusy||state.pending||!state.row)return;
  const ok=await confirmAction({title:`Remove ${state.row.name}?`,
    message:"The event leaves the animation at once. Save keeps the removal in the mod project.",
    confirmLabel:"Remove event",cancelLabel:"Cancel"});
  if(!ok)return;
  state.taeBusy=true;state.pending++;render();
  try{
    const [table,id]=[state.row.table,state.row.id];
    const result=await api("/api/tae/remove",{table,id});
    state.rows=result.events;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
    state.selected=null;state.row=null;state.query="";
    await loadItems();
  }catch(error){await refreshState();await loadItems();notify(error);}
  finally{state.taeBusy=false;state.pending--;render();revealSelection();}
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
  return detailPanel({title:form.action==="add"?"Add band":"Delete band",
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
  if(state.tab==="maps")return renderMaps();
  if(state.tab==="enemies"&&state.sub==="model")return renderModel();
  if(state.tab==="animations"&&state.sub==="playback")return renderPlayback();
  const encumbrance=state.tab==="encumbrance";
  const noun=encumbrance?(state.sub==="encumbrance"?"bands":"overrides"):state.tab==="levelup"?"gains":state.tab==="effects"?"effects":state.tab==="attacks"?(state.sub==="projectiles"?"projectiles":"attacks"):state.tab==="animations"?(state.animScope.level==="chars"?"characters":state.animScope.level==="anims"?"animations":"events"):state.tab==="enemies"?(state.sub==="behaviors"?"behaviors":state.sub==="ai"?"AI records":"monsters"):state.tab==="stats"?(state.sub==="curves"?"curves":state.sub==="upgrade-materials"?"material sets":"upgrades"):state.tab==="world"?(state.sub==="shops"?"shop entries":state.sub==="treasure"?"treasure":"drops"):state.tab==="assets"?"files":"items";
  const label=encumbrance?"Encumbrance":state.tab==="levelup"?"Level-up gains":state.tab==="effects"?"Effects":state.tab==="attacks"?"Attacks":state.tab==="animations"?"Animations":state.tab==="enemies"?"Enemies":state.tab==="stats"?"Stats":state.tab==="assets"?"Assets":"Items";
  // sortedRows owns this list's order (filter, name sort, meaningful-order tabs); the framework yields.
  const view=pagedListDetail({className:"ds1-records",rows:sortedRows(),key,selected:state.selected,slots:false,order:"given",noun,
    page:state.page,pageSize:state.pageSize,defaultSplit:32,minLeft:230,minRight:380,splitKey:"ds1-items",rowsKey:"ds1-items-"+state.sub,
    search:{key:"ds1-records-search",value:state.query,label:"Search "+noun,change:value=>{state.query=value;state.page=0;render();}},
    sync:next=>{
      state.page=next.page;state.pageSize=next.pageSize;state.selection=next.selection||[];
      if(state.selected!==next.selected){state.selected=next.selected;void loadDetail().then(render).catch(notify);}
    },
    change:next=>{state.page=next.page;state.pageSize=next.pageSize;if(next.reason==="pins"&&state.pagedView?.refreshMaster)state.pagedView.refreshMaster();else render();},
    master:({rows:listed,selected,select})=>{
      selectVisibleRecord=select;
      return columnList({rows:listed,key,selected,sortState:state.sort,
      sort:column=>{if(encumbrance||state.tab==="levelup")return;state.sort={key:column,dir:state.sort.key===column?-state.sort.dir:1};render();},
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
    // have only reference names. Placements cannot be renamed either:
    // names: map files store names at fixed offsets, so renaming would
    // move every byte after them.
    // names: animation events have no stored names; animation names are
    // HKX file references and character names come from map placements.
    // names: asset files keep the game's own paths; replacing swaps the
    // bytes under a path, never the path itself.
    // names: level-up gains cover the game's four fixed defenses, which
    // have no stored names to change.
    // names: a material set is named by what it spends; the name follows
    // the contents, so there is nothing to rename.
    renamable:row=>state.tab==="stats"?!["CalcCorrectGraph","EquipMtrlSetParam"].includes(row.table):state.tab==="items"&&!(state.sub==="spells"&&row.table!=="Magic"),
    describePinnedCell,commitPinnedCell,
    detail,emptyDetail:()=>detailPanel({title:"No matching "+noun,body:[LexeditorUI.detailNote("Change the search to find a record.")]})});
  state.pagedView=view;
  const subtabs=subtabsFor(state.tab);
  // Enemies names its one list (Monsters) so the category reads; Attacks
  // under Attacks would only repeat the tab.
  const strip=subtabBar({tabs:subtabs,showSingle:state.tab==="enemies",active:state.sub,label,change:id=>navigate(state.tab,id)});
  if(state.tab==="assets")return LexeditorUI.stack(strip,subtabBar({tabs:assetKinds,active:state.assetKind,
    label:"Asset kinds",order:"given",shortcuts:false,change:setAssetKind}),view);
  if(state.tab!=="animations"||state.animScope.level==="chars")return LexeditorUI.stack(strip,view);
  const scope=state.animScope;
  const crumbs=[el("button",{type:"button","data-anim-crumb":"chars",
    onclick:async()=>{state.animScope={level:"chars"};state.query="";state.page=0;state.selected=null;state.row=null;await loadItems().catch(notify);render();}},"Characters")];
  const here=el("span",{className:"lex-anim-crumb-here"});
  if(scope.level==="anims"){here.textContent=scope.charName||scope.binder||"";
    crumbs.push(el("span",{className:"lex-anim-crumb-sep"}," › "),here);}
  else{crumbs.push(el("button",{type:"button","data-anim-crumb":"anims",
    onclick:async()=>{state.animScope={level:"anims",binder:scope.binder,charName:scope.charName};state.query="";state.page=0;state.selected=null;state.row=null;await loadItems().catch(notify);render();}},scope.charName||scope.binder||""));
    here.textContent=`${scope.tae||""} · ${scope.animName||""}`;
    crumbs.push(el("span",{className:"lex-anim-crumb-sep"}," › "),here);}
  return LexeditorUI.stack(strip,el("div",{className:"lex-anim-crumbs"},...crumbs),view);
}
function viewportHooks(){
  return {readOnly:state.readOnly,showCollision:state.mapCollision,
    onSelect:(key,info)=>{state.mapSelected=key;state.mapInfo=info||null;refreshViewportBar();
    if(!key||!state.mapView)return;
    const placementKey=`${state.mapView.map}:${key}`;
    if(placementKey!==state.selected)selectPlacement(placementKey,true);},
    onMove:(key,pos)=>viewportMove(state.mapView.map,key,pos),
    onRotate:(key,rot)=>viewportRotate(state.mapView.map,key,rot),
    requestMod:()=>viewportRequestMod()};
}
function refreshViewportBar(){
  const buttons=[...document.querySelectorAll("[data-viewport-action]")];
  if(!buttons.length)return;
  const movable=!!(state.mapInfo&&state.mapInfo.movable);
  const playerStart=state.mapInfo?.kind==="Player";
  for(const button of buttons){
    const action=button.dataset.viewportAction;
    if(action==="collision"){
      button.disabled=false;
      button.setAttribute("aria-pressed",String(state.mapCollision));
      button.textContent=state.mapCollision?"Hide collision":"Show collision";
    }else if(action==="duplicate"){
      button.disabled=state.readOnly||state.mapBusy||!movable;
      button.title=state.readOnly?"Open a mod project to add placements"
        :!state.mapSelected?"Select a placement in the viewport first"
        :!movable?"Only enemy, object and player-start placements can be duplicated"
        :"Copy this placement under the next free ID";
    }else if(action==="remove"){
      button.disabled=state.readOnly||state.mapBusy||!movable||playerStart;
      button.title=playerStart?"The player start cannot be removed"
        :state.readOnly?"Open a mod project to remove placements"
        :!state.mapSelected?"Select a placement in the viewport first"
        :!movable?"Only enemy, object and player-start placements can be removed"
        :"Remove this placement from its map";
    }else if(action==="add"){
      button.disabled=state.readOnly||state.mapBusy;
      button.title=state.readOnly?"Open a mod project to add placements"
        :"Place a new copy of one of this map's models where the camera looks";
    }else if(action==="copy"){
      button.disabled=state.readOnly||state.mapBusy||!movable;
      button.title=state.readOnly?"Open a mod project to copy placements"
        :!state.mapSelected?"Select a placement in the viewport first"
        :!movable?"Only enemy, object and player-start placements can be copied"
        :"Copy this placement";
    }else if(action==="paste"){
      button.disabled=state.readOnly||state.mapBusy||!state.mapClipboard;
      button.title=state.readOnly?"Open a mod project to paste placements"
        :!state.mapClipboard?"Copy a placement first"
        :"Paste the copied placement where the camera looks";
    }else if(action==="rotate"){
      button.disabled=false;
      const spinning=state.mapGizmo==="rotate";
      button.setAttribute("aria-pressed",String(spinning));
      button.textContent=spinning?"Move":"Rotate";
      button.title=spinning?"Drag the gizmo to move placements"
        :"Drag the gizmo to turn placements";
    }
  }
}
async function viewportRequestMod(){
  // The shared shell offers this for its own controls; the canvas is the
  // plugin's own, so it asks with the shell's own words and call.
  if(!state.readOnly||state.mapOfferOpen)return;
  state.mapOfferOpen=true;
  try{
    const agreed=await confirmAction({title:"Create a mod to edit?",
      message:"This is the game's own data, so Lexeditor shows it read-only. Create a mod to make your own editable version.",
      confirmLabel:"Create a mod",cancelLabel:"Cancel"});
    if(!agreed)return;
    await LexeditorUI.createModProject("ds1",{pluginName:"Dark Souls Remastered"});
  }catch(error){notify(error);}
  finally{state.mapOfferOpen=false;}
}
// A drag in the picture edits the same rows the side panel shows,
// so the move lands in the list, the detail and its visible inputs.
function syncPlacementRow(map,partKey,names,afters){
  if(state.row&&state.row.table===map&&state.row.id===partKey){
    for(let i=0;i<3;i++){const field=state.row.fields.find(item=>item.key===names[i]);if(field)field.value=afters[i];}
  }
  const entry=state.rows.find(row=>row.table===map&&row.id===partKey);
  if(entry)for(let i=0;i<3;i++)entry.values[names[i]]=afters[i];
  if(state.tab!=="maps"||state.mapTab!=="selection")return;
  for(let i=0;i<3;i++){
    const input=document.querySelector(`[data-maps-side] [data-field-key="${names[i]}"]`);
    if(input&&input.isConnected)input.value=String(afters[i]);
  }
}
function viewportMove(map,key,pos){
  if(state.readOnly||state.mapBusy||!state.mapView)return Promise.resolve(false);
  const names=["posX","posY","posZ"];
  const before=state.mapView.parts.find(part=>part.key===key)?.pos||[0,0,0];
  state.mapBusy=true;state.pending++;shell.refresh();refreshViewportBar();
  viewportCtl?.moveTo(key,pos);
  let settle=null;
  const outcome=new Promise(resolve=>{settle=resolve;});
  edits=edits.then(async()=>{
    try{
      const done=[];
      let latest=null;
      for(let index=0;index<3;index++){
        const result=await api("/api/edit",{table:map,id:key,field:names[index],value:pos[index],sub:state.sub});
        latest=result;
        done.push({table:map,id:key,field:names[index],before:before[index],
          after:result.row.fields.find(item=>item.key===names[index])?.value});
      }
      fieldHistory.record({edits:done});
      state.dirty=latest.dirtyCount;state.changes=latest.changes||state.changes;state.nativeRules=latest.nativeRules||state.nativeRules;
      const part=state.mapView.parts.find(entry=>entry.key===key);
      if(part)part.pos=[done[0].after,done[1].after,done[2].after];
      viewportCtl?.moveTo(key,part?part.pos:pos);
      syncPlacementRow(map,key,names,[done[0].after,done[1].after,done[2].after]);
      settle(true);
    }catch(error){notify(error);settle(false);}
    finally{state.pending--;state.mapBusy=false;refreshViewportBar();shell.refresh();}
  }).catch(notify);
  return outcome;
}
function viewportRotate(map,key,rot){
  if(state.readOnly||state.mapBusy||!state.mapView)return Promise.resolve(false);
  const names=["rotX","rotY","rotZ"];
  const before=state.mapView.parts.find(part=>part.key===key)?.rot||[0,0,0];
  state.mapBusy=true;state.pending++;shell.refresh();refreshViewportBar();
  viewportCtl?.turnTo(key,rot);
  let settle=null;
  const outcome=new Promise(resolve=>{settle=resolve;});
  edits=edits.then(async()=>{
    try{
      const done=[];
      let latest=null;
      for(let index=0;index<3;index++){
        const result=await api("/api/edit",{table:map,id:key,field:names[index],value:rot[index],sub:state.sub});
        latest=result;
        done.push({table:map,id:key,field:names[index],before:before[index],
          after:result.row.fields.find(item=>item.key===names[index])?.value});
      }
      fieldHistory.record({edits:done});
      state.dirty=latest.dirtyCount;state.changes=latest.changes||state.changes;state.nativeRules=latest.nativeRules||state.nativeRules;
      const part=state.mapView.parts.find(entry=>entry.key===key);
      if(part)part.rot=[done[0].after,done[1].after,done[2].after];
      viewportCtl?.turnTo(key,part?part.rot:rot);
      syncPlacementRow(map,key,names,[done[0].after,done[1].after,done[2].after]);
      settle(true);
    }catch(error){notify(error);settle(false);}
    finally{state.pending--;state.mapBusy=false;refreshViewportBar();shell.refresh();}
  }).catch(notify);
  return outcome;
}
async function reloadViewport(map,selectKey){
  state.mapView=await api(`/api/map/view?map=${encodeURIComponent(map)}`);
  state.mapList=(await api("/api/table?tab=viewport")).rows;
  state.mapSelected=null;state.mapInfo=null;
  if(selectKey)state.selected=`${map}:${selectKey}`;
  await loadItems();
  clampMapSelection();
  await loadDetail().catch(notify);
  refreshMapSide();
  const host=document.querySelector("[data-viewport-host]");
  const status=document.querySelector("[data-viewport-status]");
  if(host&&status&&state.tab==="maps"){
    viewportCtl=null;
    viewportCtl=await Ds1Viewport.mount(host,map,state.mapView,status,viewportHooks()).catch(failMount(status,"Could not load the map."));
    viewportCtl?.setGizmoMode?.(state.mapGizmo);
    if(selectKey&&viewportCtl)viewportCtl.select(selectKey);
  }
  refreshViewportBar();
}
async function viewportDuplicate(map){
  if(state.mapBusy||!state.mapSelected||state.readOnly)return;
  state.mapBusy=true;refreshViewportBar();
  try{
    const result=await api("/api/placements/add",{map,id:state.mapSelected});
    state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
    await reloadViewport(map,`${result.row.type}:${result.row.partId}`);
  }catch(error){notify(error);}
  finally{state.mapBusy=false;refreshViewportBar();}
}
async function viewportRemove(map){
  if(state.mapBusy||!state.mapSelected||state.readOnly)return;
  const name=state.mapInfo?.name||"This placement";
  if(!await confirmAction({title:"Remove this placement?",
    message:`${name} leaves the map. Its bytes stay in the file, unused.`,
    confirmLabel:"Remove",cancelLabel:"Cancel"}))return;
  state.mapBusy=true;refreshViewportBar();
  try{
    const result=await api("/api/placements/remove",{map,id:state.mapSelected});
    state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
    await reloadViewport(map,null);
  }catch(error){notify(error);}
  finally{state.mapBusy=false;refreshViewportBar();}
}
async function viewportAdd(map,anchor){
  if(state.readOnly||state.mapBusy||!state.mapView)return;
  const counts=new Map();
  for(const part of state.mapView.parts){
    if(part.kind!=="Enemy"&&part.kind!=="Dummy enemy"&&part.kind!=="Object")continue;
    if(!part.model)continue;
    counts.set(part.model,(counts.get(part.model)||0)+1);
  }
  const models=[...counts.entries()].sort((a,b)=>a[0].localeCompare(b[0]));
  if(!models.length){notify(new Error("This map has no enemy or object models to place."));return;}
  LexeditorUI.choicePopover({label:"Model",
    choices:models.map(([name,count])=>({label:`${name} (${count})`,value:name})),
    select:async model=>{
      state.mapBusy=true;refreshViewportBar();
      try{
        const at=viewportCtl?.aim?.()||[0,0,0];
        const result=await api("/api/placements/create",{map,model,pos:at,rot:[0,0,0]});
        state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
        await reloadViewport(map,`${result.row.type}:${result.row.partId}`);
      }catch(error){notify(error);}
      finally{state.mapBusy=false;refreshViewportBar();}
    }}).openFor(anchor);
}
async function viewportCopy(map){
  if(state.readOnly||state.mapBusy||!state.mapSelected)return;
  state.mapBusy=true;refreshViewportBar();
  try{
    const row=(await api(`/api/row?table=${encodeURIComponent(map)}&id=${encodeURIComponent(state.mapSelected)}&sub=viewport`)).row;
    const at=key=>row.fields.find(item=>item.key===key)?.value??0;
    state.mapClipboard={model:row.model,pos:[at("posX"),at("posY"),at("posZ")],rot:[at("rotX"),at("rotY"),at("rotZ")],
      npc:row.fields.find(item=>item.key==="npcId")?.value??null};
  }catch(error){notify(error);}
  finally{state.mapBusy=false;refreshViewportBar();}
}
async function viewportPaste(map){
  const clip=state.mapClipboard;
  if(state.readOnly||state.mapBusy||!clip)return;
  state.mapBusy=true;refreshViewportBar();
  try{
    const at=viewportCtl?.aim?.()||clip.pos;
    const result=await api("/api/placements/create",{map,model:clip.model,pos:at,rot:clip.rot,npc:clip.npc});
    state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
    await reloadViewport(map,`${result.row.type}:${result.row.partId}`);
  }catch(error){notify(error);}
  finally{state.mapBusy=false;refreshViewportBar();}
}
const VIEWPORT_STYLE="position:relative;width:100%;height:520px;flex:1 0 auto;min-height:320px;";
async function loadMaps(){
  state.mapList=(await api("/api/table?tab=viewport")).rows;
  if(!state.mapList.some(row=>row.id===state.mapId))state.mapId=state.mapList[0]?.id||null;
  state.mapView=state.mapId?await api(`/api/map/view?map=${encodeURIComponent(state.mapId)}`):null;
  state.mapSelected=null;state.mapInfo=null;
  clampMapSelection();
  await loadDetail();
}
// The selected placement always belongs to the open map: switching maps,
// adding or removing placements re-points it instead of stranding it.
function clampMapSelection(){
  const here=state.rows.filter(row=>row.table===state.mapId);
  if(!here.some(row=>key(row)===state.selected))state.selected=here[0]?key(here[0]):null;
  const row=state.rows.find(row=>key(row)===state.selected);
  state.mapSelected=row?row.id:null;
}
async function chooseMap(id){
  if(!id||id===state.mapId)return;
  state.mapId=id;state.mapView=null;state.mapSelected=null;state.mapInfo=null;state.page=0;
  try{state.mapView=await api(`/api/map/view?map=${encodeURIComponent(id)}`);}
  catch(error){notify(error);return;}
  clampMapSelection();
  await loadDetail().catch(notify);
  render();
}
// Selection never rebuilds the whole screen: a full render remounts the
// 3D scene, so picking a placement only swaps the side panel's content.
async function selectPlacement(placementKey,fromCanvas){
  const row=state.rows.find(row=>key(row)===placementKey);
  if(!row)return;
  if(placementKey===state.selected&&state.mapTab==="selection"&&state.row&&key(state.row)===placementKey)return;
  state.selected=placementKey;state.mapSelected=row.id;state.mapTab="selection";
  if(!fromCanvas&&viewportCtl)viewportCtl.select(state.mapSelected);
  await loadDetail().catch(notify);
  refreshMapSide();
}
function refreshMapSide(){
  if(state.tab!=="maps")return;
  const side=document.querySelector("[data-maps-side]");
  if(!side){render();return;}
  side.replaceChildren(mapsStrip(),mapsPane());
}
function mapsStrip(){
  return LexeditorUI.tabStrip({tabs:[{id:"maps",label:"Maps"},{id:"placements",label:"Placements"},{id:"selection",label:"Selection"}],
    active:state.mapTab,label:"Map views",change:id=>{state.mapTab=id;refreshMapSide();}});
}
function mapsPane(){
  if(state.mapTab==="placements")return placementsPane();
  if(state.mapTab==="selection")return detail();
  return mapsListPane();
}
function mapsListPane(){
  selectVisibleRecord=null;
  return LexeditorUI.stack(
    columnList({rows:state.mapList,key:row=>row.id,selected:state.mapId,select:row=>chooseMap(row.id),
      columns:[
        {key:"name",label:"Name",sortable:true,grow:1},
        {key:"parts",label:"Parts",sortable:true,numeric:true,sortValue:row=>row.values.parts,render:row=>String(row.values.parts)},
        {key:"models",label:"Models",sortable:true,numeric:true,sortValue:row=>row.values.models,render:row=>String(row.values.models)},
        {key:"collision",label:"Collision",sortable:true,numeric:true,sortValue:row=>row.values.collision,render:row=>String(row.values.collision)},
        {key:"navigation",label:"Navigation",sortable:true,numeric:true,sortValue:row=>row.values.navigation,render:row=>String(row.values.navigation)}]}));
}
function placementsPane(){
  const here=sortedRows().filter(row=>row.table===state.mapId);
  const pages=Math.max(1,Math.ceil(here.length/state.pageSize));
  if(state.page>pages-1)state.page=pages-1;
  const shown=here.slice(state.page*state.pageSize,(state.page+1)*state.pageSize);
  const select=(row,event)=>{
    if(event&&(event.shiftKey||event.ctrlKey||event.metaKey))return;
    selectPlacement(key(row),false);
  };
  selectVisibleRecord=select;
  return LexeditorUI.stack(
    LexeditorUI.bottomSearch({key:"maps-placements",value:state.query,label:"Search placements",
      change:value=>{state.query=value;state.page=0;
        // Filtering picks its first match, as the old list did, but
        // stays on this tab: the reader asked to search, not to leave.
        const matches=sortedRows().filter(row=>row.table===state.mapId);
        if(matches.length&&!matches.some(row=>key(row)===state.selected)){
          state.selected=key(matches[0]);state.mapSelected=matches[0].id;
          if(viewportCtl)viewportCtl.select(state.mapSelected);
          void loadDetail().catch(notify);
        }
        refreshMapSide();}}),
    columnList({rows:shown,key,selected:state.selected,select,
      columns:[{key:"name",label:"Name",grow:1}]}),
    LexeditorUI.pager({pages,page:state.page,total:here.length,pageSize:state.pageSize,
      change:value=>{state.page=value;refreshMapSide();}}));
}
function renderMaps(){
  if(!state.mapList.length)return LexeditorUI.notice({tone:"warning",message:"No map files found."});
  const current=state.mapList.find(row=>row.id===state.mapId)||state.mapList[0];
  const collide=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"collision",
    title:"Show where collision and navigation parts sit. Markers show placement, not shape.",
    onclick:()=>{state.mapCollision=!state.mapCollision;viewportCtl?.setShowCollision(state.mapCollision);refreshViewportBar();}},"Hide collision");
  const duplicate=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"duplicate",
    onclick:()=>viewportDuplicate(current.id)},"Duplicate");
  const remove=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"remove",
    onclick:()=>viewportRemove(current.id)},"Remove");
  const add=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"add",
    onclick:event=>viewportAdd(current.id,event.currentTarget)},"Add");
  const copy=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"copy",
    onclick:()=>viewportCopy(current.id)},"Copy");
  const paste=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"paste",
    onclick:()=>viewportPaste(current.id)},"Paste");
  const rotate=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"rotate",
    onclick:()=>{state.mapGizmo=state.mapGizmo==="rotate"?"move":"rotate";viewportCtl?.setGizmoMode?.(state.mapGizmo);refreshViewportBar();}},"Rotate");
  const status=el("div",{class:"lex-viewport-status","data-viewport-status":"",style:"flex:0 0 auto"},LexeditorUI.loadingStatus("Loading map"));
  const host=el("div",{class:"lex-viewport-host","data-viewport-host":"",style:VIEWPORT_STYLE});
  requestAnimationFrame(()=>{
    viewportCtl=null;refreshViewportBar();
    Ds1Viewport.mount(host,current.id,state.mapView,status,viewportHooks()).then(ctl=>{
      viewportCtl=ctl;
      viewportCtl?.setGizmoMode?.(state.mapGizmo);
      if(state.mapSelected&&viewportCtl)viewportCtl.select(state.mapSelected);
      refreshViewportBar();
    }).catch(failMount(status,"Could not load the map."));
  });
  // The buttons hover over the picture, not in a bar above it. They hang
  // on a wrapper: mounting clears the host itself for its canvas.
  const wrap=el("div",{style:"position:relative;min-width:0;"},host);
  LexeditorUI.hoverActions(wrap,{label:"Map actions",
    actions:[{node:collide},{node:duplicate},{node:remove},{node:add},{node:copy},{node:paste},{node:rotate}]});
  const viewPane=el("div",{style:"flex:1 1 65%;min-width:0;display:flex;flex-direction:column;"},wrap,status);
  const side=el("div",{"data-maps-side":"",style:"flex:0 0 400px;min-width:0;display:flex;flex-direction:column;"},mapsStrip(),mapsPane());
  return el("div",{style:"display:flex;gap:8px;align-items:flex-start;"},viewPane,side);
}
function renderPlayback(){
  const strip=subtabBar({tabs:subtabsFor("animations"),active:state.sub,label:"Animations",change:id=>navigate("animations",id)});
  const cast=state.rows.filter(row=>row.table==="AnimPlayback");
  if(!cast.length)return LexeditorUI.stack(strip,LexeditorUI.notice({tone:"warning",message:"No animation binders found."}));
  const current=cast.find(row=>key(row)===state.selected)||cast[0];
  const choose=async id=>{const row=cast.find(entry=>entry.id===id);if(!row||key(row)===state.selected)return;state.selected=key(row);state.page=0;state.animFile=null;await loadDetail().catch(notify);render();};
  const picker=el("button",{type:"button",class:"lex-viewport-picker","aria-label":"Character","aria-haspopup":"listbox",
    onclick:event=>{LexeditorUI.choicePopover({label:"Character",
      choices:cast.map(row=>({label:row.name,value:row.id})),select:choose}).openFor(event.currentTarget);}},
    `Character: ${current.name}`);
  const view=state.animView;
  const motions=(view&&view.anims)||[];
  if(!motions.some(motion=>motion.file===state.animFile))state.animFile=motions.length?motions[0].file:null;
  const motion=motions.find(entry=>entry.file===state.animFile);
  const pickMotion=id=>{if(id===state.animFile)return;state.animFile=id;render();};
  const motionPicker=el("button",{type:"button",class:"lex-viewport-picker","aria-label":"Animation","aria-haspopup":"listbox",
    onclick:event=>{LexeditorUI.choicePopover({label:"Animation",
      choices:motions.map(entry=>({label:entry.available===false?`${entry.file} (unreadable)`:entry.file,value:entry.file})),select:pickMotion}).openFor(event.currentTarget);}},
    `Animation: ${motion?motion.file+(motion.available===false?" (unreadable)":""):"none"}`);
  const status=el("div",{class:"lex-viewport-status","data-anim-status":"",style:"flex:0 0 auto"},LexeditorUI.loadingStatus("Loading animation"));
  const host=el("div",{class:"lex-viewport-host","data-anim-host":"",style:VIEWPORT_STYLE});
  const timeline=el("div",{class:"lex-anim-timeline","data-anim-timeline":""});
  requestAnimationFrame(()=>{Ds1Anim.mount(host,current.id,motion||null,timeline,status).catch(failMount(status,"Could not load the animation."));});
  return LexeditorUI.stack(strip,el("div",{class:"lex-viewport-bar"},picker,motionPicker),host,timeline,status);
}
function renderModel(){
  const strip=subtabBar({tabs:subtabsFor("enemies"),active:state.sub,label:"Enemies",change:id=>navigate("enemies",id)});
  const foes=state.rows.filter(row=>row.table==="EnemyModel");
  if(!foes.length)return LexeditorUI.stack(strip,LexeditorUI.notice({tone:"warning",message:"No reviewed monsters found."}));
  const current=foes.find(row=>key(row)===state.selected)||foes[0];
  // Buttons, not selects: switching the viewed enemy or attack edits
  // nothing, and a select would ask Vanilla readers to create a mod
  // before looking around.
  const choose=async id=>{const row=foes.find(entry=>entry.id===id);if(!row||key(row)===state.selected)return;state.selected=key(row);state.page=0;state.chrAttack=null;await loadDetail().catch(notify);render();};
  const picker=el("button",{type:"button",class:"lex-viewport-picker","aria-label":"Enemy","aria-haspopup":"listbox",
    onclick:event=>{LexeditorUI.choicePopover({label:"Enemy",
      choices:foes.map(row=>({label:row.name,value:row.id})),select:choose}).openFor(event.currentTarget);}},
    `Enemy: ${current.name}`);
  const view=state.chrView;
  const attacks=(view&&view.attacks)||[];
  if(!attacks.some(attack=>attack.id===state.chrAttack))state.chrAttack=attacks.length?attacks[0].id:null;
  const attack=attacks.find(entry=>entry.id===state.chrAttack);
  const pickAttack=async id=>{if(id===state.chrAttack)return;state.chrAttack=id;render();};
  const attackPicker=el("button",{type:"button",class:"lex-viewport-picker","aria-label":"Attack","aria-haspopup":"listbox",
    onclick:event=>{LexeditorUI.choicePopover({label:"Attack",
      choices:attacks.map(entry=>({label:entry.name,value:entry.id})),select:pickAttack}).openFor(event.currentTarget);}},
    `Attack: ${attack?attack.name:"none"}`);
  const status=el("div",{class:"lex-viewport-status","data-chr-status":"",style:"flex:0 0 auto"},LexeditorUI.loadingStatus("Loading model"));
  const host=el("div",{class:"lex-viewport-host","data-chr-host":"",style:VIEWPORT_STYLE});
  requestAnimationFrame(()=>{Ds1Viewport.mountChr(host,view,state.chrAttack,status).catch(failMount(status,"Could not load the model."));});
  return LexeditorUI.stack(strip,el("div",{class:"lex-viewport-bar"},picker,attackPicker),host,status);
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
  if(deploy.changedExternally)return LexeditorUI.detailNote("An installed file changed outside Lexeditor. Apply and Restore refuse to continue until it is restored or verified by hand.");
  if(deploy.pendingRecovery)return LexeditorUI.detailNote("A previous Apply or Restore was interrupted before it finished. Click Apply or Restore original to complete it safely.");
  if(deploy.everApplied&&!deploy.backupOk)return LexeditorUI.detailNote("The preserved original copy is missing or has changed. Apply and Restore refuse to continue until it is restored by hand.");
  return null;
}
function renderInfo(){
  const deploy=state.deployment||{};
  const upToDate=deploy.enabled&&deploy.thisProjectActive?(deploy.stale?"No, reapply after the latest save":"Yes"):"-";
  return detailPanel({className:"lex-information-panel",title:"Information",body:[
    detailSection({title:"ITEMS",body:[detailField({label:"EDITION",control:readonlyField("Dark Souls Remastered / Steam")}),
      detailField({label:"SUPPORT",control:readonlyField("Items, effects, native rules, monster stats, enemy attacks, placements, animation events and assets"),help:infoHelp("Edit documented item properties, reviewed monster stats, enemy attack damage, map placements and animation event timing, or replace whole asset files. Names are reference labels. Unknown fields and padding stay unchanged. Saves go to the selected mod project.")})]}),
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
      output:"Apply replaces the installed parameter archive, map, animation and asset files with the mod project's saved copies, after preserving each original once.",
      order:"One complete parameter archive and the project's map files. Separate projects are not merged; applying a different project replaces what is currently installed.",
      safety:"Apply composes enabled library tweaks and project native rules before replacing the executable, parameter archive and map files. Outside changes are refused.",
      removal:"Restore original restores all owned files. The project and library tweak settings stay unchanged."})]});
}
// Tweaks are library mods: a switch saves at once, and changed tweaks
// rebuild when the mod project saves.
async function tweakRequest(path,body,failure){
  if(state.tweakBusy)return;
  state.tweakBusy=true;render();
  try{state.tweaks=await api(path,body);state.tweaksNeedRebuild=!!state.tweaks.needsRebuild;}
  catch(error){LexeditorUI.showAlert({title:failure,message:error.message||String(error)});await loadTweaks().catch(()=>{});}
  finally{state.tweakBusy=false;render();}
}
async function restoreTweaks(){
  const ok=await confirmAction({title:"Restore the original executable?",message:"Close the game first. The tweaks' switches stay as they are.",confirmLabel:"Restore original",cancelLabel:"Cancel"});
  if(!ok)return;
  await tweakRequest("/api/tweaks/restore",{},"Could not restore the executable");
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
    help:"Save combines every enabled tweak into lexeditor-ds1-patch.bin, which Lexeditor's loader (dinput8.dll in the game folder) applies in memory each time the game starts. DarkSoulsRemastered.exe itself is never changed. When a tweak adds menu rows, the menu layout file is rebuilt too, keeping one copy of its original. Restore original removes the loader and puts the layout back. Tweaks install when you press Play.",
    body:[detailField({label:"APPLIED",control:readonlyField(applied)}),
      // Debug mode: the game runs offline with Arxan off, so a debugger
      // (Cheat Engine's "find what writes", x64dbg) can attach (#742).
      detailField({label:"DEBUG MODE",dataType:"BOOL",
        help:infoHelp("For finding things in the running game with a debugger. Save or Play installs a loader that switches the game's anti-debug protection (Arxan) off with dearxan, so Cheat Engine or x64dbg can attach without the game closing itself. The game has no network access while it is on: it cannot go online. Turn it off and save again for normal play."),
        control:el("input",{type:"checkbox",checked:!!status.debugMode,disabled:busy,"aria-label":"Debug mode",
          onchange:event=>tweakRequest("/api/tweaks/debug",{on:event.target.checked},"Could not switch debug mode")})}),
      !!status.debugMode!==!!status.debugInstalled?LexeditorUI.detailNote(state.readOnly
        ?(status.debugMode?"Debug mode is on. Close the game, then press Play to install it.":"Debug mode is off. Close the game, then press Play to put the normal loader back.")
        :(status.needsRebuild
          ?(status.debugMode?"Debug mode is on. Save to install it.":"Debug mode is off. Save to put the normal loader back.")
          :(status.debugMode?"Debug mode is on. It installs when you press Play.":"Debug mode is off. The normal loader returns when you press Play."))):null,
      (status.staleMods||[]).length?LexeditorUI.detailNote(state.readOnly
        ?"The enabled tweaks changed since the last build. Close the game, then press Play to rebuild them."
        :"The enabled tweaks changed since the last build. Save to rebuild them."):null,
      status.state==="vanilla"&&!status.problem&&!status.needsRebuild&&(status.tweaks||[]).some(row=>row.enabled)?LexeditorUI.detailNote("These tweaks are on but not installed yet. Press Play to install them."):null,
      status.loaderMessage?detailField({label:"LAST GAME START",control:readonlyField(status.loaderMessage),
        help:infoHelp("What the loader reported the last time the game started. If the game was updated or another tool changed it, the loader changes nothing and says so here.")}):null,
      empty?missingMods:null,
      status.builtIntoExecutable?LexeditorUI.detailNote("An earlier Lexeditor built tweaks into DarkSoulsRemastered.exe. Restore original puts the original executable back; tweaks then load from dinput8.dll."):null,
      status.problem?LexeditorUI.detailNote(status.problem):null,
      actionRow(el("button",{type:"button",disabled:busy||!status.windows||status.state!=="tweaked",onclick:restoreTweaks},"Restore original"))].filter(Boolean)});
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
window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&(state.dirty||state.pending||state.tweaksNeedRebuild))event.preventDefault();});
boot();
