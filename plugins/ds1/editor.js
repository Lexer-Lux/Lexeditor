"use strict";
const {el,detailPanel,detailSection,detailField,readonlyField,infoHelp,pagedListDetail,columnList,subtabBar,
  actionRow,confirmAction,modLoaderSection,tabbedPanel,applyFieldTabOverrides,hoverable,curveEditor,soundPreview,audioColumn}=LexeditorUI;
const state={tab:"items",sub:"consumables",tabs:[],enemyTabs:[],aiTabs:[],attackTabs:[],rows:[],selected:null,row:null,dirty:0,pending:0,
  readOnly:true,query:"",modOnly:false,page:0,pageSize:20,sort:{key:"name",dir:1},error:"",deployment:null,deployBusy:false,
  monsterTab:"basics",itemTab:"",effectTab:"",monsterAttacks:null,thinkRow:null,monsterBehaviors:null,behaviorQuery:"",behaviorPage:0,tweaks:null,tweakBusy:false,tweaksNeedRebuild:false,
  effectTabs:[],statsTabs:[],animTabs:[],worldTabs:[],textTabs:[],npcTabs:[],miscTabs:[],animScope:{level:"anims"},nativeRules:null,bandForm:null,bandBusy:false,taeForm:null,taeBusy:false,rowBusy:false,
  animChars:[],animCharId:null,animCharQuery:"",animCharPage:0,animQuery:"",animPage:0,animCharFit:null,animFit:null,animEventFit:null,
  assetTabs:[{id:"files",label:"Files"}],soundTabs:[{id:"sfx",label:"Sound effects"},{id:"music",label:"Music"},{id:"files",label:"Files"}],assetDetail:null,assetBusy:false,assetUpload:null,
  assetFiles:[],
  dataMap:{rows:[]},mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1],mapView:null,
  mapId:null,mapList:[],mapTab:"maps",mapSelected:null,mapInfo:null,mapBusy:false,mapOfferOpen:false,mapGizmo:"move",
  dirTab:"drops",dirRows:[],dirQuery:"",dirPage:0,dirLocal:false,mapFocus:null};
let edits=Promise.resolve(),navigation=0,recordsRequest=0,selectVisibleRecord=null,viewportCtl=null,viewportMount=0,animMount=0;
const attackPreviews=new Map();
const key=row=>`${row.table}:${row.id}`;
// File tabs share one browser: each tab id is the file kind it lists.
const ASSET_TABS=new Set(["models","textures","sound"]);
const ASSET_LABELS={models:"Models",textures:"Textures",sound:"Sound"};
const assetRows=files=>(files||[]).filter(file=>state.tab==="sound"?file.kind==="sound"||file.kind==="music":(file.kind||"other")===state.tab)
  .map(file=>{const kind=state.tab==="textures"?(file.archive?"archive":"textures"):null;
    return {table:"Asset",id:file.relative,name:file.relative,
      values:{size:file.size,...(kind?{kind}:{})},
      ...(kind?{display:{kind:kind==="archive"?"Split archive":"Textures"}}:{}),
      created:file.status==="new",modified:file.status==="modified"};});
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
  async undo(){await edits;const entry=this.undoStack.pop();if(!entry)return false;this.redoStack.push(entry);await this.apply(entry,"before");return true;},
  async redo(){await edits;const entry=this.redoStack.pop();if(!entry)return false;this.undoStack.push(entry);await this.apply(entry,"after");return true;},
  async apply(entry,side){
    this.applying=true;
    try{
      await edits;
      let refresh=false;
      for(const edit of entry.edits||[entry]){
        const result=await api("/api/edit",{table:edit.table,id:edit.id,field:edit.field,value:edit[side],sub:state.sub});
        state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
        if(state.row&&state.row.table===edit.table&&state.row.id===edit.id)state.row=result.row;
        patchRowValues(edit.table,edit.id,result.values,result.display,result.name,result.modified);
        refresh=refresh||result.refreshRows===true;
      }
      if(refresh)await loadItems();
      if(state.row&&state.row.table==="NpcParam"&&(entry.edits||[entry]).some(edit=>edit.table==="ShopLineupParam"))state.npcShop=await api(`/api/shop?npc=${state.row.id}`);
      if(state.row&&state.row.table==="NpcParam"&&(entry.edits||[entry]).some(edit=>edit.table==="NpcParam"&&(edit.field==="aiThinkId"||edit.field==="behaviorVariationId")))await refreshMonsterPanels();
      // An undone viewport move moves only its own scene part back.
      // Re-reading the whole map (and remounting the viewport, which
      // render would do) for one undone drag is what made undo feel
      // like a reload.
      if(state.tab==="maps"&&state.mapView)await refreshMapsAfterUndo(entry);
      else render();
    }catch(error){notify(error);}
    finally{this.applying=false;shell.refresh();}
  },
  clear(){this.undoStack=[];this.redoStack=[];shell.refresh();}};
document.addEventListener("keydown",event=>{
  if(!(event.ctrlKey||event.metaKey)||event.altKey)return;
  const pressed=event.key.toLowerCase();
  if(pressed!=="z"&&pressed!=="y")return;
  if(pressed==="z"&&!(event.target instanceof HTMLElement&&event.target.matches("input:not([type='checkbox']),textarea,select,[contenteditable='true']")))return;  if(event.target.closest?.("textarea,input[type=text]:not([data-field-key])"))return;
  event.preventDefault();
  document.activeElement?.blur?.();
  setTimeout(()=>pressed==="y"||event.shiftKey?fieldHistory.redo():fieldHistory.undo(),0);
},true);
const shell=LexeditorUI.mountShell({
  host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ds1",name:"Dark Souls Remastered",themeName:"ds1",theme:{accent:"#a4824c","accent-text":"#141210"}},
  tabs:[{id:"items",label:"Items",help:"Edit item properties in the selected mod. Vanilla is read-only. Unknown fields stay protected. Saves do not install a mod."},
    {id:"text",label:"Text",help:"Edit the game's menu text: NPC dialogue, event and system messages, help and menu labels. Item names and descriptions edit on the item."},
    {id:"enemies",label:"Enemies",help:"Edit reviewed monster stats: health, defense, drops and effects. A monster's Attacks tab lists the attack records its parameters reference; its brains live in the AI tab. Vanilla is read-only. Save changes the mod project."},
    {id:"npcs",label:"NPCs",help:"Edit friendly characters: merchants, blacksmiths and quest givers. Health, souls and defense work the same as on monsters. Each merchant's Shop tab holds their stock and prices. Vanilla is read-only. Save changes the mod project."},
    {id:"drops",label:"Drops",help:"Edit enemy and corpse drop tables: what each lot drops and at what rates. One lot may serve several enemies. Vanilla is read-only. Save changes the mod project."},
    {id:"attacks",label:"Attacks",help:"Edit enemy and player attack damage and hitboxes. The Attacks list holds enemy attacks, Player attacks holds yours, and Projectiles holds flying attacks: arrows, spells and breath. One attack record can serve several monsters or several player moves, so an edit changes every use of it. Vanilla is read-only. Save changes the mod project."},
    {id:"ai",label:"AI",help:"Enemy brains. AI tables are how enemies sense and answer the player; behaviors are the moves each one can choose from. Vanilla is read-only. Save changes the mod project."},
    {id:"maps",label:"Maps",help:"Browse maps in 3D and move enemy and object placements. Pick a map from the Maps list, click a placement to select it, drag its arrows to move it. Map buttons appear over the picture. Wire boxes mark collision and navigation parts; they show where those parts sit, not their shapes. Vanilla is read-only. Save changes the mod project."},
    {id:"animations",label:"Animations",help:"Edit animation event timing and settings. Pick a character, then an animation, then an event. Add inserts a documented event, and Remove deletes the selected one. Events that share a timestamp change together. Character files this version cannot open are skipped. Vanilla is read-only, and Save changes the mod project."},
    {id:"effects",label:"Effects",help:"Edit buffs, debuffs and equipment passives. A shared effect changes every item or ability using it. Unknown properties stay protected."},
    {id:"stats",label:"Stats",help:"Stat scaling for the Stats Rework. Scaling curves holds the 39 scaling graphs: weapon paths, Max HP, Max MP, defense, resistances, level-up cost and level sync. Weapon upgrades and Armor upgrades hold each upgrade level's multipliers. Level-up gains holds what each level-up adds to defense. Full records stay in Items, and no scaling graph here covers stamina recovery or attunement slots."},
    {id:"models",label:"Models",help:"What you see and bump into: character, object and map geometry. Tinted names replace an installed file; a pen nib marks files only the mod carries. A preview shows the file the game would load. Add and Remove save at once. Vanilla is read-only."},
    {id:"textures",label:"Textures",help:"The images on the models. Tinted names replace an installed file; a pen nib marks files only the mod carries. A preview shows the file the game would load. Add and Remove save at once. Vanilla is read-only."},
    {id:"sound",label:"Sound",help:"Every sound effect and music track, listed one by one. The streams live inside bank files. Files holds those banks, and Add and Remove replace them. Tinted names replace an installed file. A pen nib marks files only the mod carries. Vanilla is read-only."},
    {id:"misc",label:"Misc.",help:"Load ranges, base stamina recovery and effect overrides. Save and Apply to use your rules."},
    {id:"tweaks",label:"Tweaks",help:"Each tweak is a mod in the library. Switch them in the Mods tab and change their settings here. Changed tweaks rebuild when you save. Restore original removes them from the game."}],
  activeTab:()=>state.tab,navigate:tab=>navigate(tab),
  info:()=>navigate("info"),infoActive:()=>state.tab==="info",
  help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open Dark Souls Data Map",
  readonly:()=>state.readOnly,dirtyCount:()=>state.dirty+state.pending+(state.tweaksNeedRebuild?1:0),
  pendingChanges:()=>[...(state.changes||[]),...(state.tweaksNeedRebuild?[{label:"Installed tweaks",before:"Last build",after:"Rebuilt"}]:[])],
  save,discard,history:fieldHistory
});
const subtabsFor=tab=>tab==="enemies"?state.enemyTabs:tab==="ai"?state.aiTabs:tab==="npcs"?state.npcTabs:tab==="drops"?state.worldTabs.filter(entry=>entry.id==="drops"):tab==="attacks"?state.attackTabs:tab==="animations"?state.animTabs:tab==="effects"?state.effectTabs:tab==="text"?state.textTabs:
  tab==="stats"?state.statsTabs.map(entry=>entry.id==="levelup"?{...entry,help:"What each level-up adds to defense. 0 removes a gain. Save and Apply to use your values."}:entry):
  tab==="sound"?state.soundTabs:ASSET_TABS.has(tab)?state.assetTabs:
  tab==="misc"?state.miscTabs.map(entry=>entry.id==="encumbrance"?{...entry,help:"Add or merge load ranges. Each band has a movement profile and its own recovery percentage. The last band has no upper limit. Save and Apply to use your rules."}:entry.id==="misc"?{...entry,help:"Base stamina recovery before effects and load penalties. Save and Apply to use your value."}:entry.id==="encumbrance-overrides"?{...entry,help:"Special conditions that replace band recovery. They take priority over load ranges and do not create another range. Save and Apply to use your rules."}:entry):state.tabs;
async function refreshState(){
  const result=await api("/api/state");
  state.tabs=result.tabs;state.enemyTabs=result.enemyTabs;state.aiTabs=result.aiTabs;state.attackTabs=result.attackTabs;
  state.effectTabs=result.effectTabs||[];state.statsTabs=result.statsTabs||[];state.animTabs=result.animTabs||[];state.worldTabs=result.worldTabs||[];state.textTabs=result.textTabs||[];state.npcTabs=result.npcTabs||[];state.miscTabs=result.miscTabs||[];state.nativeRules=result.nativeRules;
  state.readOnly=result.readOnly;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
  if(result.theme&&result.theme.sounds)LexeditorUI.configureThemeSounds(result.theme.sounds.rows||[]);
}
function sortedRows(){
  const query=state.query.toLowerCase();
  // The search reads the whole row: names, ids, ranges and every
  // property value, raw and formatted. A behavior that costs 5 stamina
  // answers '5' even when no name holds a 5.
  const haystack=row=>{
    const parts=[row.id,row.name,row.range||""];
    for(const source of [row.values,row.display]){
      if(!source||typeof source!=="object")continue;
      for(const value of Object.values(source)){
        if(value===null||value===undefined||typeof value==="object")continue;
        parts.push(value);
      }
    }
    return parts.join(" ").toLowerCase();
  };
  const filtered=state.rows.filter(row=>haystack(row).includes(query));
  if(state.tab==="misc"||(state.tab==="stats"&&state.sub==="levelup")||(state.tab==="animations"&&state.animScope.level==="events"))return filtered;
  // The game's own order (by record) breaks ties.
  return filtered.sort((a,b)=>LexeditorUI.compareRecords(a,b,state.sort)||a.id-b.id);
}
async function loadAnims(request){
  if(state.animScope.level==="events"){await loadAnimEvents(request);return;}
  await loadAnimChars(request);
}
async function loadAnimChars(request){
  const result=await api("/api/table?tab=playback");
  if(request!==recordsRequest||state.tab!=="animations")return;
  state.animChars=result.rows;
  state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
  if(!state.animChars.some(row=>key(row)===state.animCharId))state.animCharId=state.animChars[0]?key(state.animChars[0]):null;
  await loadAnimView(request);
}
async function loadAnimView(request){
  const row=state.animChars.find(row=>key(row)===state.animCharId);
  state.animView=null;
  if(!row){state.rows=[];state.selected=null;state.row=null;return;}
  const detail=await api(`/api/anim/list?chr=${encodeURIComponent(row.id)}`);
  if(request!==recordsRequest||state.animCharId!==key(row))return;
  state.animView=detail;
  state.animScope={level:"anims",binder:`${row.id}.anibnd.dcx`,charName:row.name};
  state.rows=animMotionRows(detail);
  const playable=state.rows.find(row=>row.motion.file)||state.rows[0];
  state.selected=playable?key(playable):null;
  state.row=null;
}
function animMotionRows(view){
  const motions=(view.anims||[]).map(motion=>({table:"AnimMotion",
    id:motion.file||`tae:${motion.tae}|${motion.taeIndex}`,
    name:motion.file?motion.file+(motion.available===false?" (unreadable)":""):motion.name||"(animation)",
    values:{},motion}));
  const orphans=(view.orphans||[]).map(entry=>({table:"AnimMotion",
    id:`tae:${entry.tae}|${entry.taeIndex}`,name:entry.name,values:{},
    motion:{file:null,name:entry.name,binder:entry.binder,tae:entry.tae,taeIndex:entry.taeIndex,
      available:false,reason:"This animation has events but no playable motion."}}));
  return [...motions,...orphans].sort((a,b)=>String(a.name).localeCompare(String(b.name),undefined,{numeric:true,sensitivity:"base"}));
}
async function loadAnimEvents(request){
  const scope=state.animScope;
  const result=await api(`/api/table?tab=animations&scope=events&binder=${encodeURIComponent(scope.binder||"")}&tae=${encodeURIComponent(scope.tae||"")}&anim=${scope.anim??""}`);
  if(request!==recordsRequest||state.tab!=="animations")return;
  state.rows=result.rows;
  state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
  if(!state.rows.some(row=>key(row)===state.selected))state.selected=state.rows[0]?key(state.rows[0]):null;
  await loadDetail();
}
async function reloadAnimRows(){
  if(state.animScope.level!=="events")return;
  const scope=state.animScope;
  const result=await api(`/api/table?tab=animations&scope=events&binder=${encodeURIComponent(scope.binder||"")}&tae=${encodeURIComponent(scope.tae||"")}&anim=${scope.anim??""}`);
  state.rows=result.rows;
  state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
}
async function loadItems(){
  const request=++recordsRequest;
  if(state.tab==="animations"){await loadAnims(request);return;}
  const sub=state.sub;
  const wantSounds=state.tab==="sound"&&(sub==="sfx"||sub==="music");
  let url="/api/table?tab="+encodeURIComponent(sub);
  if(wantSounds)url="/api/sounds?kind="+sub;
  else if(ASSET_TABS.has(state.tab))url="/api/assets?scope=all";
  const result=await api(url);
  if(request!==recordsRequest||state.sub!==sub)return;
  if(wantSounds)state.rows=(result.rows||[]).map(row=>({...row,values:{bank:row.bank,length:formatSoundLength(row.duration||0),size:row.size}}));
  else if(ASSET_TABS.has(state.tab)){state.assetFiles=result.files;state.rows=assetRows(result.files);}
  else state.rows=result.rows;
  if(state.tab==="maps")await loadDirectory();
  state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
  const pool=state.tab==="maps"?[...state.rows,...state.dirRows]:state.rows;
  if(!pool.some(row=>key(row)===state.selected))state.selected=pool[0]?key(pool[0]):null;
  await loadDetail();
}
const thinkIdOf=row=>((row.fields||[]).find(item=>item.key==="aiThinkId")||{}).value;
async function thinkRowFor(row){
  const thinkId=thinkIdOf(row);
  return thinkId>0?api(`/api/row?table=NpcThinkParam&id=${thinkId}`).then(result=>result.row).catch(()=>null):null;
}
async function refreshMonsterPanels(){
  if(!state.row||state.row.table!=="NpcParam")return;
  const [attacks,think,behaviors]=await Promise.all([api(`/api/attacks?monster=${state.row.id}`),
    thinkRowFor(state.row),api(`/api/behaviors?monster=${state.row.id}`)]);
  state.monsterAttacks=attacks;state.thinkRow=think;state.monsterBehaviors=behaviors;
}
async function loadDetail(){
  let row=state.rows.find(row=>key(row)===state.selected);
  let sub=state.sub;
  if(!row&&state.tab==="maps"){
    row=state.dirRows.find(row=>key(row)===state.selected);
    if(row)sub=state.dirTab;
  }
  if(!row||row.table==="AnimMotion"){state.row=null;state.monsterAttacks=null;state.npcShop=null;state.thinkRow=null;state.monsterBehaviors=null;state.assetDetail=null;return;}
  if(row.table==="Asset"){
    state.assetDetail=null;state.assetSounds=null;
    const detail=await api(`/api/assets?scope=textures&side=mod&file=${encodeURIComponent(row.id)}`);
    if(state.selected!==key(row))return;
    state.row={table:"Asset",id:row.id,name:row.name};state.assetDetail=detail;state.monsterAttacks=null;state.npcShop=null;state.thinkRow=null;state.monsterBehaviors=null;
    if(state.tab==="sound"&&/\.fsb$/i.test(row.id)){
      if(state.assetStreamFile!==row.id){state.assetStreamFile=row.id;state.assetStream=null;state.assetPage=0;}
      try{
        const sounds=await api(`/api/sound/bank?file=${encodeURIComponent(row.id)}`);
        if(state.selected!==key(row))return;
        state.assetSounds=sounds;
        if(!state.assetStream&&sounds.streams.length)state.assetStream=sounds.streams[0].name;
      }catch(error){state.assetSounds={file:row.id,streams:[],error:String(error?.message||error)};}
    }
    return;
  }
  if(row.table==="SoundStream"){
    state.row={table:"SoundStream",id:row.id,name:row.name,bank:row.bank,duration:row.duration,size:row.size};
    state.assetDetail=null;state.assetSounds=null;state.monsterAttacks=null;state.npcShop=null;state.thinkRow=null;state.monsterBehaviors=null;return;
  }
  if(row.table==="MapView"){
    state.mapView=null;
    const detail=await api(`/api/map/view?map=${encodeURIComponent(row.id)}`);
    if(state.selected!==key(row))return;
    state.row={table:"MapView",id:row.id,name:row.name};state.mapView=detail;state.monsterAttacks=null;state.npcShop=null;state.thinkRow=null;state.monsterBehaviors=null;return;
  }
  if(row.table==="AnimPlayback"){
    state.animView=null;
    const detail=await api(`/api/anim/list?chr=${encodeURIComponent(row.id)}`);
    if(state.selected!==key(row))return;
    state.row={table:"AnimPlayback",id:row.id,name:row.name};state.animView=detail;state.monsterAttacks=null;state.npcShop=null;state.thinkRow=null;state.monsterBehaviors=null;return;
  }
  const detail=await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}&sub=${encodeURIComponent(sub)}`);
  if(state.selected!==key(row))return;
  const isMonster=row.table==="NpcParam";
  const [attacks,shop,think,behaviors,chrView]=await Promise.all([
    isMonster?api(`/api/attacks?monster=${row.id}`):null,
    isMonster?api(`/api/shop?npc=${row.id}`):null,
    thinkRowFor(detail.row),
    isMonster?api(`/api/behaviors?monster=${row.id}`):null,
    isMonster?api(`/api/chr/view?npc=${row.id}`).catch(()=>null):null]);
  if(state.selected!==key(row))return;
  state.row=detail.row;state.monsterAttacks=attacks;state.npcShop=shop;state.thinkRow=think;state.monsterBehaviors=behaviors;state.chrView=chrView;state.chrAttack=null;
}
async function loadTweaks(){
  state.tweaks=await api("/api/tweaks");
  state.tweaksNeedRebuild=!!state.tweaks.needsRebuild;
}
async function loadDeployment(){
  state.deployment=await api("/api/deployment");
}
async function navigate(tab,sub=state.sub,selected=null){
  // Subtabs bypass the shell, so the switch announces itself here too:
  // old content out, throbber in, before the first await.
  document.querySelector("#main")?.replaceChildren(LexeditorUI.loadingPanel({label:`Loading ${sub}`}));

  const token=++navigation;await edits;
  const changedTab=tab!==state.tab;state.tab=tab;state.bandForm=null;state.taeForm=null;
  if(tab==="enemies"&&!state.enemyTabs.some(entry=>entry.id===sub))sub="monsters";
  else if(tab==="ai"&&!state.aiTabs.some(entry=>entry.id===sub))sub="ai";
  else if(tab==="npcs"&&!state.npcTabs.some(entry=>entry.id===sub))sub="npcs";
  else if(tab==="drops"&&!state.worldTabs.some(entry=>entry.id===sub))sub="drops";
    else if(tab==="attacks"&&!state.attackTabs.some(entry=>entry.id===sub))sub="attacks";
  else if(tab==="maps"){if(DIRECTORY_TABS.includes(sub))state.dirTab=sub;sub="placements";}
  else if(tab==="animations"&&!state.animTabs.some(entry=>entry.id===sub))sub="animations";
  else if(tab==="effects"&&!state.effectTabs.some(entry=>entry.id===sub))sub="effects-all";
  // Without the curve table, Stats opens on the first list with rows instead of an error.
  else if(tab==="stats"&&!state.statsTabs.some(entry=>entry.id===sub))sub=(state.statsTabs.find(entry=>entry.id==="curves")||{}).count?"curves":((state.statsTabs.find(entry=>entry.count)||{}).id||"curves");
  else if(tab==="misc"&&!state.miscTabs.some(entry=>entry.id===sub))sub="encumbrance";
  else if(tab==="sound"&&!state.soundTabs.some(entry=>entry.id===sub))sub="sfx";
  else if(tab!=="sound"&&ASSET_TABS.has(tab)&&!state.assetTabs.some(entry=>entry.id===sub))sub="files";
  else if(tab==="items"&&!state.tabs.some(entry=>entry.id===sub))sub="consumables";
  else if(tab==="text"&&!state.textTabs.some(entry=>entry.id===sub))sub="menu-labels";
  if(tab==="animations"&&changedTab)state.animScope={level:"anims"};
  if(sub!==state.sub||changedTab||selected){state.sub=sub;state.selected=selected;state.query="";state.page=0;}
  try{
    if(["items","enemies","npcs","drops","attacks","ai","maps","animations","effects","stats","misc","models","textures","sound","text"].includes(tab))await loadItems();
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
const TEXT_LABEL_LINKS={defenseMagic:102204,defenseFire:102205,defenseThunder:102206};
const openTextLabel=id=>navigate("text","menu-labels",`MenuText:${id}`);
const textLabelPreviews=new Map();
async function textLabelPreview(id){
  if(!textLabelPreviews.has(id))textLabelPreviews.set(id,api(`/api/row?table=MenuText&id=${id}`).then(result=>result.row,
    error=>{textLabelPreviews.delete(id);throw error;}));
  const row=await textLabelPreviews.get(id);
  const label=row.fields.find(field=>field.key==="label")?.value||"";
  return LexeditorUI.stack({fill:false,compact:true},el("strong",{},row.name),el("span",{},label||"(empty)"));
}
const openAttack=id=>navigate("attacks","attacks",`AtkParam_Npc:${id}`);
const openBehavior=id=>navigate("ai","behaviors",`BehaviorParam:${id}`);
const LINK_TAB_LABELS={effect:"Effects",attack:"Attacks",goods:"Items",catalog:"Items",ai:"AI",drop:"Drops"};
const recordRows=new Map();
async function recordRow(table,id){
  const cacheKey=`${table}:${id}`;
  if(!recordRows.has(cacheKey))recordRows.set(cacheKey,
    api(`/api/row?table=${encodeURIComponent(table)}&id=${id}`).then(result=>result.row,
      error=>{recordRows.delete(cacheKey);throw error;}));
  return recordRows.get(cacheKey);
}
function catalogSub(table,row){
  const value=search=>row.fields?.find(field=>field.key===search)?.value;
  if(table==="EquipParamGoods"){
    const category=value("goodsType");
    return category===1?"keys":category===2?"upgrades":[5,6,7].includes(category)?"spells":"consumables";
  }
  if(table==="EquipParamWeapon")return [13,14].includes(value("weaponCategory"))?"ammo":"weapons";
  if(table==="EquipParamProtector")return "armor";
  if(table==="EquipParamAccessory")return "rings";
  if(table==="Magic")return "spells";
  return "consumables";
}
async function openCatalog(table,id){
  try{
    const row=await recordRow(table,id);
    await navigate("items",catalogSub(table,row),`${table}:${id}`);
  }catch(error){notify(error);}
}
function openRecord(link){
  if(link.kind==="effect")return openEffect(link);
  if(link.kind==="attack")return openAttack(link.id);
  if(link.kind==="ai")return navigate("ai","ai",`${link.table}:${link.id}`);
  if(link.kind==="npc")return navigate(link.tab||"enemies",link.sub||"monsters",`${link.table}:${link.id}`);
  if(link.kind==="drop")return navigate("drops","drops",`${link.table}:${link.id}`);
  if(link.kind==="asset")return openAsset(link);
  return openCatalog(link.table,link.id);
}
function openAsset(link){
  navigate(link.tab==="textures"?"textures":"models","files",`Asset:${link.id}`);
}
// The thing finder opens the same list the face opens: the target tab's
// rows become hold-to-choose candidates (see the master list's
// decorateRow), and the source tab, sub and selection are captured when
// the finder opens so the way back survives browsing.
const LINK_NOUNS={effect:"effect",attack:"attack",goods:"item",ai:"AI table",npc:"NPC",drop:"drop table"};
const NPC_TAB_LABELS={enemies:"Enemies",npcs:"NPCs"};
const CATALOG_NOUNS={EquipParamWeapon:"weapon",EquipParamProtector:"armor piece",EquipParamAccessory:"accessory",Magic:"spell"};
const CATALOG_SUBS={EquipParamWeapon:"weapons",EquipParamProtector:"armor",EquipParamAccessory:"rings",Magic:"spells",EquipParamGoods:"consumables"};
function linkNoun(link){return link.kind==="catalog"?(CATALOG_NOUNS[link.table]||"record"):LINK_NOUNS[link.kind]||"record";}
async function finderTarget(link,value){
  if(link.kind==="effect")return ["effects","effects-all"];
  if(link.kind==="attack")return ["attacks","attacks"];
  if(link.kind==="ai")return ["ai","ai"];
  if(link.kind==="npc")return [link.tab||"enemies",link.sub||"monsters"];
  if(link.kind==="drop")return ["drops","drops"];
  try{return ["items",catalogSub(link.table,await recordRow(link.table,value))];}
  catch(error){return ["items",CATALOG_SUBS[link.table]||"consumables"];}
}
async function recordPreview(link){
  const row=await recordRow(link.table,link.id);
  const parts=[el("strong",{},row.name)];
  if(ds1IconTables.has(link.table)){
    const picture=el("img",{src:`/api/icon?table=${encodeURIComponent(link.table)}&id=${encodeURIComponent(link.id)}`,
      alt:"",draggable:"false",style:"width:40px;height:40px;","data-lex-no-image":"off"});
    picture.addEventListener("error",()=>{if(picture.isConnected)picture.remove();},{once:true});
    parts.push(picture);
  }
  for(const field of (row.fields||[]).filter(shown=>shown.type!=="longtext"&&shown.key!=="description"&&shown.key!=="longDescription").slice(0,6)){
    const shown=field.type==="enum"?(field.enum[String(field.value)]||`Unknown (${field.value})`)
      :typeof field.value==="number"?LexeditorUI.formatNumber(field.value):String(field.value);
    parts.push(detailField({label:field.label,control:readonlyField(shown,{format:false})}));
  }
  return LexeditorUI.stack({fill:false,compact:true},...parts);
}
// An asset link previews what the ID resolves to: the menu icon picture,
// or the worn model's first available mesh. Failures show why, never throw.
async function assetPreview(row,entry){
  if(entry.tab!=="models"){
    const picture=el("img",{src:`/api/icon?table=${encodeURIComponent(row.table)}&id=${encodeURIComponent(row.id)}`,
      alt:"",draggable:"false",style:"width:40px;height:40px;","data-lex-no-image":"off"});
    picture.addEventListener("error",()=>{if(picture.isConnected)picture.remove();},{once:true});
    return picture;
  }
  const view=await api(`/api/parts/view?table=${encodeURIComponent(row.table)}&id=${row.id}`).catch(()=>null);
  const models=((view&&view.models)||[]).filter(item=>item.available);
  if(!models.length)return el("div",{},(view&&view.reason)||"The model file is not installed.");
  if(!window.Ds1Preview)return el("div",{},`${row.name} model`);
  const first=models[0];
  return window.Ds1Preview.thumbnail({url:`/api/parts/geometry?table=${encodeURIComponent(row.table)}&id=${row.id}&variant=${encodeURIComponent(first.variant||"")}`,label:`${row.name} model`});
}
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
  // A pending tweak rebuild is deployment drift, not an unsent edit:
  // it must not keep Exit Without Saving from reaching zero. Every
  // server reply re-sets it, so this runs after the last one; the
  // drift itself stays on disk for the next save to rebuild.
  state.tweaksNeedRebuild=false;
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
      for(const listed of state.rows||[])if(key(listed)===key(row)){listed.name=result.row.name;if(result.modified!==undefined)listed.modified=result.modified;}
    }catch(error){notify(error);}
    finally{state.pending--;render();}
  });
}
function patchRowValues(table,id,values,display,name,modified){
  const target=state.rows.find(row=>row.table===table&&row.id===id)||state.dirRows.find(row=>row.table===table&&row.id===id);
  if(!target||!values)return;
  target.values=values;target.display=display||{};
  if(name!==undefined&&name!==null)target.name=name;
  if(modified!==undefined)target.modified=modified;
}
// Mod contents only is the shared table toggle: the server marks every
// record row it changed this session, so the filter is one comparison.
function modOnlySpec(){
  return {available:!state.readOnly,value:state.modOnly===true,
    changed:row=>row.modified===true,
    change:value=>{state.modOnly=value;state.page=0;render();}};
}function syncDetailControl(propertyKey,value,control){
  // Computed fields (Effective HP, absorption) move when their inputs do;
  // their detail controls repaint in place, sliders included.
  for(const other of state.pagedView?.querySelectorAll(`[data-field-key="${CSS.escape(propertyKey)}"]`)??[]){
    if(other===control||other===document.activeElement)continue;
    if(other.hasAttribute("data-lex-dialog")){
      const dialog=(state.row?.dialogLinks||[]).find(entry=>entry.field===propertyKey);
      const text=dialog?(dialog.text||`(no dialog text ${dialog.id})`):"";
      if("value" in other)other.value=text;else other.textContent=text;
      other.title=dialog?.text||"";
      continue;
    }
    if(other.type==="checkbox")other.checked=!!value;
    else if("value" in other){
      other.value=(other.disabled&&other.readOnly&&typeof value==="number")?LexeditorUI.formatNumber(value):String(value);
      other.__lexValueSliderPaint?.();
    }
  }
}
function commit(row,field,value,control,beforeOverride){
  if(state.readOnly||!field.editable)return;
  state.pending++;shell.refresh();
  edits=edits.then(async()=>{
    // The value before this edit, as the record now stands (an earlier edit
    // may have changed it since the page drew).
    const live=state.row&&key(state.row)===key(row)?state.row:row;
    const before=beforeOverride??live.fields?.find(item=>item.key===field.key)?.value??live.values?.[field.key];
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
      if(changed){if(control?.isConnected){if(field.type==="bool")control.checked=!!changed.value;else control.value=String(changed.value);}
      syncDetailControl(field.key,changed.value,control);}
      // A link appearing or disappearing swaps the control itself (a
      // picker becomes a record face, or back), so the panel rebuilds
      // the way it does when an edit changes another control's shape.
      const hadLink=(row.recordLinks||[]).some(entry=>entry.field===field.key);
      const hasLink=(latest.row.recordLinks||[]).some(entry=>entry.field===field.key);
      if(row.table==="NativeRules"||["goodsType","weaponCategory"].includes(field.key)||hadLink!==hasLink){await loadItems();render();}
      else{
        for(const update of updates)patchRowValues(row.table,update.id,update.result.values,update.result.display,update.result.name,update.result.modified);
        if(row.table.endsWith(".msb")&&state.tab==="maps"&&state.mapView&&["posX","posY","posZ","rotX","rotY","rotZ"].includes(field.key)){
          // A typed move or turn moves the scene part too; only the
          // gizmo did, so typed edits left the mesh standing behind.
          const fresh=updates[updates.length-1].result.values||{};
          if(row.table===state.mapView.map){
            const part=state.mapView.parts.find(entry=>entry.key===row.id);
            const pos=[fresh.posX,fresh.posY,fresh.posZ],rot=[fresh.rotX,fresh.rotY,fresh.rotZ],scale=[fresh.scaleX,fresh.scaleY,fresh.scaleZ];
            if(part){part.pos=pos;part.rot=rot;part.scale=scale;}
            viewportCtl?.moveTo?.(row.id,pos);
            viewportCtl?.turnTo?.(row.id,rot);
            viewportCtl?.scaleTo?.(row.id,scale);
          }
        }
        if(row.table.endsWith(".msb")&&field.key==="npcId"&&state.tab==="maps"){
          // An enemy swap can move a placement between the NPC and
          // enemy directory and change the map\u2019s own counts.
          state.mapList=(await api("/api/table?tab=viewport")).rows;
          await loadDirectory().catch(notify);
          refreshMapSide();refreshDirectory();
        }
        if(updates.some(update=>update.result.refreshRows))await loadItems().then(render);
        else if(state.tab==="animations"){await reloadAnimRows().catch(notify);refreshAnimList();}
        else if(field.key.startsWith("residentSpEffectId")||["refId","refCategory","replaceSpEffectId","cycleOccurrenceSpEffectId","atkOccurrenceSpEffectId"].includes(field.key))render();
        else if(field.key==="aiThinkId"||field.key==="behaviorVariationId"){await refreshMonsterPanels();render();}
        else if(String(state.sort?.key||"").startsWith("pin:"))render();
        else state.pagedView?.refreshValues?.();
      }
    }catch(error){
      notify(error);
      const result=await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}&sub=${encodeURIComponent(state.sub)}`);
      const original=result.row.fields.find(item=>item.key===field.key);
      if(original&&control?.isConnected){if(field.type==="bool")control.checked=!!original.value;else control.value=String(original.value);}
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
const TIMES=/\s*\(x\)$/;
const RATE=/\s*\(([A-Za-z]+\/second)\)$/;
const SECONDS=/\s*\(seconds?\)$/;
const MS=/\s*\(ms\)$/;
const POINTS=/\s*\(points\)$/;
const shownLabel=field=>field.label.replace(PERCENT,"").replace(TIMES,"").replace(RATE,"").replace(SECONDS,"").replace(MS,"").replace(POINTS,"");
// Think distances say "In metres" in their help, not their labels, so no
// label suffix can wire them. The fifteen distance fields of NpcThinkParam
// (eleven annotated plus the four battle distances, the same family).
const THINK_METRES=new Set(["nearDist","midDist","farDist","outDist","eye_dist","ear_dist","ear_soundcut_dist","nose_dist","maxBackhomeDist","backhomeDist","backhomeBattleDist","BackHome_LookTargetDist","BattleStartDist","callHelp_CallValidMinDistTarget","callHelp_CallValidRange"]);
function controlFor(row,field){
  const plain=plainControlFor(row,field);
  const control=PERCENT.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"%")
    :TIMES.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"\u00d7")
    // The quantity names the row already; the unit only says per second.
    :RATE.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"/sec")
    :SECONDS.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"s")
    :MS.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"ms")
    :POINTS.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"pts")
    :row.table==="NpcThinkParam"&&THINK_METRES.has(field.key)&&field.type==="number"?LexeditorUI.unitField(plain,"m")
    :row.table&&String(row.table).endsWith(".msb")&&/^Rotation [XYZ]$/.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"\u00b0"):plain;
  if(!field.editable||field.vanilla===null||field.vanilla===undefined||field.type==="text"||field.type==="longtext")return control;
  const input=plain;
  const current=()=>field.type==="bool"?(input.checked?1:0):Number(String(input.value).replace(/,/g,""));
  return LexeditorUI.provenanceControl({control,current,vanilla:field.type==="bool"?Number(field.vanilla):field.vanilla,
    internal:true,
    format:field.type==="enum"?value=>field.enum[String(value)]||String(value):undefined,
    same:(left,right)=>Number(left)===Number(right),
    apply:value=>commit(row,field,value,input)});
}
// A record link is a hoverable face: it names the linked record, previews
// it on hover and opens it on click. The finder button that picks another
// target joins it outside the provenance wrapper, where the reference
// rail cannot cover it. The face carries a value property like the select
// it replaces, so commits, provenance and detail sync treat it the same way.
function referenceFace(row,field){
  const face=el("span",{class:"ds1-reference-face","data-field-key":field.key});
  const paint=()=>{
    const live=state.row&&key(state.row)===key(row)?state.row:row;
    const entry=(live.recordLinks||[]).find(item=>item.field===field.key);
    const value=live.fields?.find(item=>item.key===field.key)?.value??field.value;
    const label=entry?entry.name:(field.enum[String(value)]||`Unknown (${value})`);
    face.replaceChildren(entry&&entry.resolved?hoverable({content:label,targetType:`ds1-${entry.kind}`,
      targetId:entry.id,targetLabel:`${entry.name} in ${LINK_TAB_LABELS[entry.kind]||"Items"}`,
      preview:()=>recordPreview(entry),activate:()=>openRecord(entry)})
      :el("span",{class:"lex-readonly-field"},label));
  };
  let current=String(field.value);
  Object.defineProperty(face,"value",{configurable:true,
    get:()=>current,
    set:next=>{current=String(next);paint();}});
  paint();
  const live=state.row?.fields?.find(item=>item.key===field.key)?.value;
  if(live!==undefined&&String(live)!==current)face.value=String(live);
  return face;
}
function referencePicker(row,field,face,knownLink){
  const link=knownLink||(row.recordLinks||[]).find(entry=>entry.field===field.key);
  const source={};
  const value=()=>{const live=state.row&&key(state.row)===key(row)?state.row:row;
    return live.fields?.find(item=>item.key===field.key)?.value??field.value;};
  return LexeditorUI.thingFinderButton({class:"ds1-find-reference",label:`Change ${field.label}`,
    disabled:state.readOnly||field.disabled||!link,type:`ds1-${link?.table||"record"}`,
    prompt:link?`Choose the ${linkNoun(link)} for ${row.name}.`:"Choose a record.",
    target:async()=>{Object.assign(source,{tab:state.tab,sub:state.sub,selected:state.selected,selection:state.selection});
      const [tab,sub]=await finderTarget(link,value());await navigate(tab,sub);},
    origin:()=>navigate(source.tab,source.sub,source.selected),
    accept:picked=>{state.selection=source.selection;commit(row,field,Number(picked),face);face.value=String(picked);}});
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
  if(field.type==="longtext")return LexeditorUI.textArea({...attrs,value:field.value,rows:6,
    maxlength:field.maxLength||2000,"aria-multiline":"true",onchange:event=>{
      const input=event.target;
      if(!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,input.value,input);
    }});
  if(field.type==="enum"){
    const link=(row.recordLinks||[]).find(entry=>entry.field===field.key);
    if(link&&link.kind!=="npc")return referenceFace(row,field);
    const choices=Object.entries(field.enum);
    if(!choices.some(([value])=>value===String(field.value)))choices.unshift([String(field.value),`Unknown (${field.value})`]);
    const control=el("select",{...attrs,onchange:event=>commit(row,field,Number(event.target.value),event.target)});
    control.replaceChildren(...choices.map(([value,label])=>el("option",{value,disabled:!(value in field.enum)},label)));
    const live=state.row?.fields?.find(item=>item.key===field.key)?.value;
    control.value=String(live??field.value);
    return control;
  }
  return el("input",{...attrs,type:"number",value:field.value,min:field.minimum,max:field.maximum,
    step:field.step??(/^(f|angle)/.test(field.dtype)?"any":1),onchange:event=>{
      const input=event.target;if(!input.value.trim()||!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,Number(input.value),input);
    }});
}
const GROUP_ORDER=["Description","Basics","Starting gear","Starting spells","Starting items","Body & gestures","Defense","Absorption","Combat","Requirements & costs","Thresholds","Growth","Curve shape","Level-up cost","Effects & references","Upgrades",
  "Use behavior","Value & rewards","Appearance","Logic & goals","Battle distances","Return home","Senses","Call for help","Team tactics","Movement","Properties"];
// Every property that decides what an item becomes as it is reinforced:
// its upgrade path, materials, reinforcement cost and ascension options.
// Buffable flags and presentation materials are not upgrades.
const UPGRADE_KEYS={EquipParamWeapon:new Set(["materialSetId","reinforceTypeId","basicPrice","isCustom","disableBaseChangeReset","baseChangeCategory",
  ...Array.from({length:16},(_,index)=>index?"originEquipWep"+index:"originEquipWep")]),
  EquipParamProtector:new Set(["materialSetId","reinforceTypeId","basicPrice",
  ...Array.from({length:16},(_,index)=>index?"originEquipPro"+index:"originEquipPro")])};
function groupFor(field,table){
  if(field.group)return field.group;
  if(table&&UPGRADE_KEYS[table]&&UPGRADE_KEYS[table].has(field.key))return "Upgrades";
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
  // A field that is itself a record link opens that record from its own row;
  // only links with no editable field on the page are listed separately.
  // Asset links serve through the field label below: a face would replace the
  // number input and a picked file could never write back into it, so neither
  // joins them here or in the Linked records group.
  const links=new Map((row.recordLinks||[]).filter(entry=>entry.kind!=="asset").map(entry=>[entry.field,entry]));
  const dialogs=new Map((row.dialogLinks||[]).map(entry=>[entry.field,entry]));
  const shownLinks=new Set();
  // Placement coordinates ride one row per vector: Position, then
  // Rotation in degrees, then Scale. Detection is by field, not by
  // tab, so any record carrying a coordinate triple renders the same way.
  const byKey=new Map((row.fields||[]).map(field=>[field.key,field]));
  const vectored=new Set();
  for(const [keys,label] of [[["posX","posY","posZ"],"Position"],[["rotX","rotY","rotZ"],"Rotation"],[["scaleX","scaleY","scaleZ"],"Scale"]]){
    if(!keys.every(key=>byKey.has(key)))continue;
    keys.forEach(key=>vectored.add(key));
    const entries=keys.map(key=>{
      const field=byKey.get(key);
      return {label:key.slice(-1),control:controlFor(row,field),title:field.label,
        help:field.description&&field.description.trim()?infoHelp(field.description.trim()):null};
    });
    const group=groupFor(byKey.get(keys[0]),row.table);
    if(!groups.has(group))groups.set(group,[]);
    groups.get(group).push(detailField({label,control:LexeditorUI.multiNumberRow(entries,{columns:3,nowrap:true})}));
  }
  for(const field of row.fields){
    if(vectored.has(field.key))continue;
    const group=groupFor(field,row.table);if(!groups.has(group))groups.set(group,[]);
    let help=field.description.trim();
    if(!field.editable)help=field.protectedReason||"This property is preserved. Its choices or behavior are not sufficiently documented for editing.";
    if(help.replace(/[.\s]/g,"").toLowerCase()===field.label.replace(/[.\s]/g,"").toLowerCase())help="";
    const link=field.editable&&links.get(field.key);
    let control=controlFor(row,field);
    if(link){
      shownLinks.add(field.key);
      const face=control.matches?.(".ds1-reference-face")?control
        :control.querySelector?.(".ds1-reference-face")??control;
      control=el("span",{class:"ds1-reference-field"},control,referencePicker(row,field,face));
    }
    const dialog=dialogs.get(field.key);
    if(dialog)control=el("span",{class:"ds1-dialog-row"},control,
      readonlyField(dialog.text||`(no dialog text ${dialog.id})`,
        {"aria-label":`${field.label} text`,"data-field-key":field.key,"data-lex-dialog":"",
          title:dialog.text||"",format:false}));
    const shown=shownLabel(field);
    const textLink=row.table==="EquipParamProtector"?TEXT_LABEL_LINKS[field.key]:null;
    const assetLink=!textLink?(row.recordLinks||[]).find(entry=>entry.kind==="asset"&&entry.field===field.key&&entry.resolved):null;
    const npcLink=!textLink&&!assetLink?(row.recordLinks||[]).find(entry=>entry.kind==="npc"&&entry.field===field.key&&entry.resolved):null;
    const label=textLink?hoverable({content:shown,targetType:"ds1-text",targetId:textLink,
      targetLabel:`${shown} in Text`,preview:()=>textLabelPreview(textLink),activate:()=>openTextLabel(textLink)})
      :assetLink?hoverable({content:shown,targetType:"ds1-asset",targetId:assetLink.id,
      targetLabel:`${assetLink.name} in ${assetLink.tab==="textures"?"Textures":"Models"}`,
      preview:()=>assetPreview(row,assetLink),activate:()=>openRecord(assetLink)})
      :npcLink?hoverable({content:shown,targetType:"ds1-npc",targetId:npcLink.id,
      targetLabel:`${npcLink.name} in ${NPC_TAB_LABELS[npcLink.tab]||"Enemies"}`,
      preview:()=>recordPreview(npcLink),activate:()=>openRecord(npcLink)}):shown;
    groups.get(group).push(detailField({label,property:field.key,control,icon:field.icon||null,
      // A flag is stored as a u8 bit but edited as a boolean; naming the
      // storage type here kept the checkbox out of the boolean field layout.
      help:help?infoHelp(help):null,dataType:field.type==="bool"?"BOOL":field.dtype.toUpperCase(),min:field.minimum,max:field.maximum,
      sliderMin:field.sliderMin,sliderMax:field.sliderMax}));
  }
  const unlisted=(row.recordLinks||[]).filter(entry=>!shownLinks.has(entry.field)&&entry.kind!=="asset");
  if(unlisted.length){
    groups.set("Linked records",unlisted.map(entry=>detailField({
      label:row.fields.find(field=>field.key===entry.field)?.label||entry.field,
      control:entry.resolved?hoverable({content:entry.name,targetType:`ds1-${entry.kind}`,
        targetId:entry.id,targetLabel:`${entry.name} in ${LINK_TAB_LABELS[entry.kind]||"Items"}`,
        preview:()=>recordPreview(entry),activate:()=>openRecord(entry)}):readonlyField(entry.name,{format:false}),
      help:infoHelp("Open this record's linked record. Changing a shared record changes every use of it.")})));
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
function shopNumberControl(line,shopKey,label){
  const input=el("input",{type:"number",value:String(line[shopKey]),"aria-label":`${line.name} ${label}`});
  input.addEventListener("change",()=>{
    if(state.readOnly)return;
    const row={table:"ShopLineupParam",id:line.id,name:line.name,values:{value:line.value,sellQuantity:line.sellQuantity}};
    commit(row,{key:shopKey,label,editable:true},Number(input.value),input);
    // The shop list is a cache, not the record: re-read the line once the
    // edit lands so a rejected value cannot linger here.
    edits.then(async()=>{
      try{
        const fresh=await api(`/api/row?table=ShopLineupParam&id=${line.id}`);
        for(const item of fresh.row.fields){
          if(item.key==="value"||item.key==="sellQuantity")line[item.key]=item.value;
        }
        if(input.isConnected&&document.activeElement!==input)input.value=String(line[shopKey]);
      }catch(error){notify(error);}
    });
  });
  return input;
}
async function toggleShopLine(line,full){
  // The item name opens the rest of the shop line under the table:
  // price and stock already edit on the line itself, so only the other
  // fields render here, with the same controls a full record shows.
  // Clicking the open line closes it; clicking another line swaps to it.
  if(full.dataset.line===String(line.id)){full.replaceChildren();delete full.dataset.line;return;}
  full.dataset.line=String(line.id);
  full.replaceChildren(LexeditorUI.loadingStatus("Reading shop line"));
  try{
    const result=await api(`/api/row?table=ShopLineupParam&id=${line.id}`);
    const row={table:"ShopLineupParam",id:line.id,name:line.name,
      fields:(result.row.fields||[]).filter(field=>field.key!=="value"&&field.key!=="sellQuantity"),
      recordLinks:result.row.recordLinks||[],dialogLinks:result.row.dialogLinks||[]};
    if(!row.fields.length){full.replaceChildren(LexeditorUI.detailNote("This shop line holds nothing else."));return;}
    full.replaceChildren(...[...fieldSections(row)].map(([title,body])=>detailSection({title,body})));
  }catch(error){full.replaceChildren(LexeditorUI.detailNote("Could not read the shop line."));notify(error);}
}
function shopIconCell(line){
  // The sold item's menu picture; a line that names no known item table
  // leaves its cell empty rather than guessing.
  if(!line.item||!ds1IconTables.has(line.item.table))return "";
  const picture=el("img",{class:"lex-ds1-shop-icon",
    src:`/api/icon?table=${encodeURIComponent(line.item.table)}&id=${encodeURIComponent(line.item.id)}`,
    alt:"",draggable:"false","data-lex-no-image":"off"});
  picture.addEventListener("error",()=>{if(picture.isConnected)picture.remove();},{once:true});
  return picture;
}
// A master-list row's menu picture, like the shop table's icon column:
// Humanity rows show the wisp, weapons their blades. Rows without a
// picture leave the cell empty; without game files every cell is empty.
function recordIconCell(row){
  if(!row||!ds1IconTables.has(row.table))return "";
  const id=Number(row.id);
  if(!Number.isInteger(id))return "";
  const picture=el("img",{class:"lex-ds1-shop-icon",loading:"lazy",
    src:`/api/icon?table=${encodeURIComponent(row.table)}&id=${id}`,
    alt:"",draggable:"false","data-lex-no-image":"off"});
  picture.addEventListener("error",()=>{if(picture.isConnected)picture.remove();},{once:true});
  return picture;
}
function textureIconCell(row){
  if(!row||row.table!=="Asset")return "";
  if(row.values&&row.values.kind==="archive")return "";
  const picture=el("img",{class:"lex-ds1-shop-icon",loading:"lazy",
    src:`/api/assets/preview?file=${encodeURIComponent(row.id)}`,
    alt:"",draggable:"false","data-lex-no-image":"off"});
  picture.addEventListener("error",()=>{if(picture.isConnected)picture.remove();},{once:true});
  return picture;
}
function npcShopSection(){
  const full=el("div",{class:"lex-shop-line-full"});
  const rows=state.npcShop.rows.map(line=>({key:String(line.id),
    icon:shopIconCell(line),
    name:hoverable({content:line.name,
      targetType:"ds1-shoprow",targetId:line.id,targetLabel:`${line.name} (shop line)`,
      preview:()=>el("div",{},"Price "+line.value+" - Stock "+line.sellQuantity),
      activate:()=>toggleShopLine(line,full)}),
    price:shopNumberControl(line,"value","price"),
    stock:shopNumberControl(line,"sellQuantity","stock")}));
  return [detailSection({title:"Stock",body:[columnList({rows,key:row=>row.key,
    columns:[{key:"icon",label:"",width:"36px"},{key:"name",label:"Item",grow:1,align:"start"},
      {key:"price",label:"Price",numeric:true},{key:"stock",label:"Stock",numeric:true}]}),full]})];
}
function monsterThinkSection(){
  const aiField=(state.row.fields||[]).find(item=>item.key==="aiThinkId");
  if(!aiField)return [LexeditorUI.detailNote("This enemy names no AI table.")];
  const face=referenceFace(state.row,aiField);
  const body=[];
  if(!state.thinkRow){
    const thinkId=Number(aiField.value)||0;
    body.push(detailSection({title:"Think record",body:[thinkId>0?LexeditorUI.loadingPanel({label:"Loading AI table"})
      :LexeditorUI.detailNote("No AI table is assigned. Use the finder to give this enemy a brain.")]}));
  }else{
    const frozen={...state.thinkRow,fields:state.thinkRow.fields.map(item=>({...item,editable:false}))};
    for(const [title,fields] of fieldSections(frozen))body.push(detailSection({title,body:fields}));
  }
  return [detailPanel({label:"Think record",paginate:{unpaged:true},titleControl:face,actions:[referencePicker(state.row,aiField,face,
    // The panel always swaps the enemy's think record, even when none
    // is assigned yet and the value has no link entry of its own.
    {kind:"ai",table:"NpcThinkParam",field:aiField.key})],body})];
}
function behaviorVariationControl(variation){
  const input=el("input",{type:"number",value:String(variation),"aria-label":"Behaviors ID"});
  input.addEventListener("change",()=>{
    if(state.readOnly)return;
    commit(state.row,{key:"behaviorVariationId",label:"Behaviors ID",editable:true},Number(input.value),input,variation);
    edits.then(()=>{
      if(input.isConnected&&document.activeElement!==input)
        input.value=String(state.monsterBehaviors?state.monsterBehaviors.variation:variation);
    }).catch(()=>{});
  });
  return input;
}
function behaviorMatches(){
  const query=(state.behaviorQuery||"").toLowerCase();
  const rows=state.monsterBehaviors?.rows||[];
  if(!query)return rows;
  return rows.filter(move=>(move.id+" "+move.name+" "+(move.target.name||"")+" "+(move.target.detail||"")).toLowerCase().includes(query));
}
function monsterBehaviorsSection(){
  const data=state.monsterBehaviors;
  if(!data)return LexeditorUI.loadingPanel({label:"Loading behaviors"});
  const head=detailField({label:"Behaviors ID",control:behaviorVariationControl(data.variation),
    help:infoHelp("The behavior set this enemy uses. Every behavior in the set is one move it can choose. Only existing sets are accepted.")});
  if(!data.rows.length)return [detailSection({title:`Behavior set ${data.variation}`,body:[head,
    LexeditorUI.detailNote(`Behavior set ${data.variation} holds no behaviors. This enemy cannot act.`)]})];
  const here=behaviorMatches();
  const size=state.pageSize;
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.behaviorPage>pages-1)state.behaviorPage=pages-1;
  const shown=here.slice(state.behaviorPage*size,(state.behaviorPage+1)*size);
  const rows=shown.map(move=>({key:String(move.id),
    behavior:hoverable({content:move.name,targetType:"ds1-behavior",targetId:move.id,
      targetLabel:`${move.name} in AI`,preview:()=>recordPreview({kind:"behavior",table:"BehaviorParam",id:move.id}),
      activate:()=>openBehavior(move.id)}),
    calls:move.target.table?hoverable({content:move.target.name,targetType:`ds1-${move.target.kind}`,targetId:move.target.id,
      targetLabel:`${move.target.name} in ${LINK_TAB_LABELS[move.target.kind]||"Items"}`,
      preview:()=>move.target.kind==="attack"?attackPreview(move.target.id):recordPreview({kind:move.target.kind,table:move.target.table,id:move.target.id}),
      activate:()=>move.target.kind==="attack"?openAttack(move.target.id):openEffect({id:move.target.id})})
      :move.target.detail}));
  return [detailSection({title:`Behavior set ${data.variation}`,body:[head,
    LexeditorUI.bottomSearch({key:"monster-behaviors",value:state.behaviorQuery,label:"Search behaviors",
      change:value=>{state.behaviorQuery=value;state.behaviorPage=0;render();}}),
    columnList({rows,key:row=>row.key,
      columns:[{key:"behavior",label:"Behavior",grow:1},{key:"calls",label:"Calls",grow:1}]}),
    LexeditorUI.pager({inline:true,stacked:true,pages,page:state.behaviorPage,total:here.length,pageSize:size,
      change:value=>{state.behaviorPage=value;render();}})]})];
}
function monsterAttacksSection(){
  const links=state.monsterAttacks;
  if(!links)return LexeditorUI.loadingPanel({label:"Loading attacks"});
  if(!links.rows.length)return LexeditorUI.detailNote("No attack link was resolved for this monster. The Attacks tab lists every attack record.");
  const rows=links.rows.map(attack=>({key:`${attack.table}:${attack.id}`,
    name:hoverable({content:attack.name,targetType:"ds1-attack",targetId:attack.id,
      targetLabel:`${attack.name} in Attacks`,preview:()=>attackPreview(attack.id),activate:()=>openAttack(attack.id)}),
    route:attack.route}));
  return detailSection({title:"Referenced attacks",body:[columnList({rows,key:row=>row.key,
    columns:[{key:"name",label:"Attack",grow:1},{key:"route",label:"Route"}]})]});
}
function monsterDetail(groups){
  const links=state.monsterAttacks;
  const attackHelp=links?`Attack records reached from behavior variation ${links.variation} across ${links.behaviorCount} behavior records. `+
    `Direct means a behavior calls the attack; Projectile means a projectile or child projectile does. ${links.unresolved.length} references remain unresolved or lead to effects. `+
    "Attacks are shared records: edit them in the Attacks tab, where one record can serve several enemies. This panel only shows which ones this enemy can reach, and parameter links do not prove an animation uses the attack. Hover an attack to preview its damage, and click it to edit it in Attacks.":
    "Attack records reached from this monster's behavior parameters.";
  const effects=groups.get("Linked effects");
  groups.delete("Linked effects");
  // Every section is a tab; the tab is the header, so a section tab
  // shows its fields with no repeated section title.
  const tabId=title=>title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"");
  const tabs=[...groups].map(([title])=>({id:tabId(title),label:title,
    help:title==="Blocking"?"How much damage and buildup this monster blocks while it guards. Each value is a percentage off the hit. Nothing here applies to a hit it does not block.":null}));
  const accept=tabs.map(tab=>tab.id);
  const shape=applyFieldTabOverrides(groups,tabs,{accept,callerShape:`${state.row.table}:${state.sub}`});
  tabs.push({id:"attacks",label:"Attacks",help:attackHelp});
  if(effects)tabs.push({id:"effects",label:"Effects",help:"Effects this monster carries. Changing a shared effect changes every use of it."});
  if(state.row.table==="NpcParam"&&state.npcShop&&state.npcShop.rows.length)tabs.push({id:"shop",label:"Shop",help:"Everything this merchant sells, in shop order. Price and stock edit here; the item name opens the rest of the line below it. -1 stock means unlimited."});
  tabs.push({id:"ai",label:"AI",help:"The think record driving this enemy: senses, distances and goals. Swap it with the finder; think records are edited in the AI tab."});
  tabs.push({id:"behaviors",label:"Behaviors",help:"The behavior set this enemy uses. Every behavior in the set is one move it can choose; each move calls one attack, projectile or effect."});
  // No model, no Model tab: an NPC without a placed, loadable character
  // model showed an empty black stage here.
  if(state.chrView&&(state.chrView.chrs||[]).some(entry=>entry.available))tabs.push({id:"model",label:"Model",help:"Character model, attacks and hitboxes. Pick an attack to see its hitboxes."});
  const active=tabs.some(tab=>tab.id===state.monsterTab)?state.monsterTab:tabs[0].id;
  const section=tabs.find(tab=>tab.id===active);
  const content=active==="attacks"?monsterAttacksSection()
    :active==="effects"?[detailSection({title:"Effects",body:effects})]
    :active==="shop"?npcShopSection()
    :active==="ai"?monsterThinkSection()
    :active==="behaviors"?monsterBehaviorsSection()
    :active==="model"?monsterModelSection()
    :groups.get(section.label);
  return tabbedPanel({label:"Monster details",active,tabs,paginate:{unpaged:true},fieldTabs:{shape,accept},
    change:id=>{state.monsterTab=id;render();},content});
}
// Ammo's Defense tab reads its guard block under three headers: the guard's
// own settings, the damage it absorbs, the statuses it resists. Weapons
// share the table but keep the one flat list. A field the table gains
// later lands in Properties with the other settings.
const AMMO_DEFENSE_HEADERS=[
  ["Properties",["guardAngle","staminaGuardDef","guardmotionCategory","defenseBaseParry","guardBaseRepel","guardCutCancelRate","guardLevel","enableGuard"]],
  ["Defenses",["physGuardCutRate","magGuardCutRate","fireGuardCutRate","thunGuardCutRate","slashGuardCutRate","blowGuardCutRate","thrustGuardCutRate"]],
  ["Resistances",["poisonGuardResist","diseaseGuardResist","bloodGuardResist","curseGuardResist"]]];
function ammoDefenseSections(fields){
  const buckets=AMMO_DEFENSE_HEADERS.map(([title])=>[title,[]]);
  for(const field of fields){
    const at=AMMO_DEFENSE_HEADERS.findIndex(([,keys])=>keys.includes(field.dataset?.lexLayoutField));
    buckets[at<0?0:at][1].push(field);
  }
  return buckets.filter(([,body])=>body.length).map(([title,body])=>detailSection({title,body}));
}
function itemDetail(groups){
  // Every section is a tab; the tab is the header, so a section tab
  // shows its fields with no repeated section title.
  const tabId=title=>title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"");
  const tabs=[...groups].map(([title])=>({id:tabId(title),label:title,
    help:title==="Upgrades"?"What this item becomes as it is reinforced: its upgrade path, materials, reinforcement cost and ascension.":null}));
  const active=tabs.some(tab=>tab.id===state.itemTab)?state.itemTab:tabs[0].id;
  const section=tabs.find(tab=>tab.id===active);
  const accept=tabs.map(tab=>tab.id);
  const shape=applyFieldTabOverrides(groups,tabs,{accept,callerShape:`${state.row.table}:${state.sub}`});
  const body=groups.get(section.label);
  const content=section.label==="Defense"&&state.row&&catalogSub(state.row.table,state.row)==="ammo"
    ?ammoDefenseSections(body):body;
  return tabbedPanel({label:"Item details",active,tabs,paginate:{unpaged:true},fieldTabs:{shape,accept},
    change:id=>{state.itemTab=id;render();},content});
}
function effectDetail(groups){
  // Every section is a tab; the tab is the header, so a section tab
  // shows its fields with no repeated section title.
  const tabId=title=>title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"");
  const tabs=[...groups].map(([title])=>({id:tabId(title),label:title}));
  const active=tabs.some(tab=>tab.id===state.effectTab)?state.effectTab:tabs[0].id;
  const section=tabs.find(tab=>tab.id===active);
  const accept=tabs.map(tab=>tab.id);
  const shape=applyFieldTabOverrides(groups,tabs,{accept,callerShape:`${state.row.table}:${state.sub}`});
  return tabbedPanel({label:"Effect details",active,tabs,paginate:{unpaged:true},fieldTabs:{shape,accept},
    change:id=>{state.effectTab=id;render();},content:groups.get(section.label)});
}
function msbDetail(row,groups){
  // Identity first: the placement's own facts above its coordinates.
  const identity=[
    // (no Name row: the heading owns the name, like every other record)
    detailField({label:"Kind",control:readonlyField(row.kind,{format:false})}),
    detailField({label:"Part",control:readonlyField(row.id,{format:false}),
      help:infoHelp("This placement's identity. The type comes first, then the part ID.")}),
    detailField({label:"Model",control:readonlyField(row.model,{format:false})})];
  if(row.think!==null&&row.think!==undefined)identity.push(
    detailField({label:"AI table",control:readonlyField(row.think,{format:false}),
      help:infoHelp("Which AI table drives this enemy.")}));
  const ordered=new Map([["Placement",[...identity,...(groups.get("Placement")||[])]]]);
  for(const [title,body] of groups)if(title!=="Placement")ordered.set(title,body);
  return [...ordered].map(([title,body])=>detailSection({title,body}));
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
function assetSoundPanel(row,info,body){
  const help="Add this file to the mod with + in the list. The game loads the mod's copy once applied. Remove drops the mod's copy.";
  const sounds=state.assetSounds;
  const note=text=>detailSection({title:"PREVIEW",body:[soundPreview({note:text,
    help:infoHelp("Audio plays in the game. It has no picture to show.")})]});
  if(!/\.fsb$/i.test(row.id)){body.push(note("No preview"));return{help,audio:null};}
  if(!sounds||state.assetStreamFile!==row.id){body.push(LexeditorUI.loadingPanel({label:"Loading sounds"}));return{help,audio:null};}
  if(sounds.error||!sounds.streams.length){body.push(note(sounds.error?`This bank could not be read (${sounds.error}).`:"This bank holds no sounds."));return{help,audio:null};}
  const file=row.id,selected=state.assetStream||sounds.streams[0].name;
  const url=name=>`/api/sound/stream?file=${encodeURIComponent(file)}&stream=${encodeURIComponent(name)}`;
  const size=state.pageSize,pages=Math.max(1,Math.ceil(sounds.streams.length/size));
  const page=Math.min(state.assetPage||0,pages-1);state.assetPage=page;
  const shown=sounds.streams.slice(page*size,(page+1)*size);
  body.push(detailSection({title:"SOUNDS",body:[columnList({rows:shown,key:stream=>stream.name,
    selected,select:name=>{state.assetStream=name;render();},
    columns:[audioColumn({src:stream=>url(stream.name),name:stream=>stream.name}),
      {key:"name",label:"Sound",grow:1,align:"start"},
      {key:"duration",label:"Length",render:stream=>`${stream.duration.toFixed(2)} s`},
      {key:"size",label:"Size",render:stream=>formatAssetSize(stream.size)}]}),
    LexeditorUI.pager({inline:true,stacked:true,pages,page,total:sounds.streams.length,pageSize:size,
      change:value=>{state.assetPage=value;render();}})],
    help:infoHelp("Every stream the bank holds. Play one from its row, or click the row and play it from the heading.")}));
  return{help,audio:{src:url(selected),label:selected}};
}
const formatSoundLength=seconds=>`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,"0")}`;
function renderSoundDetail(row){
  const bank=row.bank||"",stream=row.name||"";
  const body=[
    detailSection({title:"SOUND",body:[
      detailField({label:"BANK",control:readonlyField(bank)}),
      detailField({label:"LENGTH",control:readonlyField(formatSoundLength(row.duration||0))}),
      detailField({label:"SIZE",control:readonlyField(formatAssetSize(row.size||0))})]}),
    detailSection({title:"ACTIONS",body:[detailField({label:"",control:actionRow(
      el("button",{type:"button",onclick:()=>navigate("sound","files",`Asset:${bank}`)},"Show in Files"))})]})];
  return detailPanel({title:row.name,meta:formatSoundLength(row.duration||0),
    help:"Streams live inside bank files. Show in Files opens this stream's bank, and replacing the bank replaces its sounds.",
    audio:{src:`/api/sound/stream?file=${encodeURIComponent(bank)}&stream=${encodeURIComponent(stream)}`,label:stream},
    paginate:{unpaged:true},body});
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
  const progress=state.assetUpload?`Uploading ${formatAssetSize(state.assetUpload.received)} of ${formatAssetSize(state.assetUpload.total)}`:"";
  const previewUrl=texture=>`/api/assets/preview?side=${info.source}&file=${encodeURIComponent(row.id)}&member=${encodeURIComponent(texture.member||"")}&index=${texture.index}`;
  const textureHelp=texture=>infoHelp(`${texture.width} by ${texture.height}, ${texture.format}. Preview of the ${fromMod?"mod":"installed game"} file, shrunk to fit.`);
  // Vanilla-vs-mod already shows in the list (tinted names, pen nibs), so
  // the panel carries no SOURCE row; files join the mod through the
  // list's add button, never a Replace action.
  const body=[];
  let icon=null,preview=null,help="",audio=null;
  if(state.tab==="models")({icon,preview,help}=assetModelPanel(row,info,body,previewUrl,textureHelp));
  else if(state.tab==="textures")({icon,preview,help}=assetTexturePanel(row,info,body,previewUrl,textureHelp));
  else if(state.tab==="sound")({help,audio}=assetSoundPanel(row,info,body));
  else{
    help="Add this file to the mod with + in the list. The game loads the mod's copy once applied. Remove drops the mod's copy.";
    body.push(detailSection({title:"PREVIEW",body:[soundPreview({note:"No preview",
      help:infoHelp("Files play in the game. They have no picture to show.")})]}));
  }
  const actions=[
    fromMod?el("button",{type:"button","data-asset-action":"remove",disabled:locked,onclick:()=>removeAssetOverride(row.id)},"Remove override"):null,
    progress?el("span",{role:"status"},progress):null].filter(Boolean);
  if(actions.length)body.push(detailSection({title:"ACTIONS",body:[detailField({label:"",control:actionRow(...actions)})]}));
  return detailPanel({title:row.name,meta:formatAssetSize(info.size),icon,help,modelPreview:preview,paginate:{unpaged:true},audio,body});
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
    if(files){state.assetFiles=files;state.rows=assetRows(files);}
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
    state.selected=`Asset:${target}`;state.row=null;state.assetDetail=null;
    await loadDetail();
  }
  catch(error){notify(error);}
  finally{state.assetBusy=false;render();}
}
// A model file's counts, FF8's GEOMETRY row in DS1 terms: object
// binders count their member objects, rigged models count bones, and
// static meshes count neither. Whatever does not apply stays off.
function assetModelCounts(model){
  if(!model||!model.previewable)return null;
  const parts=[];
  if(model.objects!=null)parts.push({label:"OBJECTS",control:readonlyField(LexeditorUI.formatNumber(model.objects))});
  parts.push({label:"MESHES",control:readonlyField(LexeditorUI.formatNumber(model.meshes))});
  if(model.bones>0)parts.push({label:"BONES",control:readonlyField(LexeditorUI.formatNumber(model.bones))});
  return LexeditorUI.controlGroup(parts,{columns:parts.length,stacked:true});
}
const ASSET_MODEL_INFO={
  collision:["Collision data","Collision files shape where the player can walk. They hold no visible mesh."],
  "no-mesh":["No model mesh","This file holds no model mesh to preview. It still replaces as a whole file."],
  unreadable:["Unreadable model","This file does not open as a model. It still replaces as a whole file."]};
// One shared thumbnail strip for the Models and Textures tabs: the
// file's textures as squares in a wrapping row, each named under its
// picture, instead of a vertical stack of label-plus-image rows.
function assetPreviewStrip(textures,previewUrl,textureHelp){
  return el("div",{class:"ds1-texture-strip",role:"list"},
    ...textures.map(texture=>el("figure",{class:"ds1-texture-tile",role:"listitem"},
      el("img",{src:texture.png||previewUrl(texture),alt:texture.name,class:"lex-asset-thumbnail",loading:"lazy"}),
      el("div",{class:"ds1-texture-caption"},
        el("span",{class:"ds1-texture-name",title:texture.name},texture.name),
        el("span",{class:"ds1-texture-help"},textureHelp(texture))))));
}
function assetModelPanel(row,info,body,previewUrl,textureHelp){
  const model=info.model;
  const counts=assetModelCounts(model);
  if(counts)body.push(detailSection({title:"GEOMETRY",body:[counts]}));
  else if(model&&model.reason&&ASSET_MODEL_INFO[model.reason]){
    const [value,tip]=ASSET_MODEL_INFO[model.reason];
    body.push(detailSection({title:"GEOMETRY",body:[
      detailField({label:"INFO",control:readonlyField(value),help:infoHelp(tip)})]}));
  }
  const textures=info.textures||[];
  if(textures.length)body.push(detailSection({title:"PREVIEW",body:[assetPreviewStrip(textures,previewUrl,textureHelp)]}));
  else body.push(detailSection({title:"PREVIEW",body:[
    detailField({label:"TEXTURES",control:readonlyField("None found"),
      help:infoHelp("Model textures live in companion archives.")})]}));
  const previewable=!!(model&&model.previewable);
  const icon=LexeditorUI.iconSlot({content:previewable
    ?window.Ds1Preview.thumbnail({url:assetGeometryUrl(row.id,info.source,model.member),label:row.name})
    :LexeditorUI.noThumbnail("ds1")});
  return {icon,
    preview:previewable?{label:`${row.name} model`,
      openLabel:`View ${row.name} model`,closeLabel:`Close ${row.name} model`,
      content:()=>assetModelContent(row,info),
      onClose:drawer=>{window.Ds1Preview.stop(drawer);drawer.replaceChildren();delete window.__lexPreview;}}:null,
    help:"Add this file to the mod with + in the list. The game loads the mod's copy once applied. The magnifier opens the 3D model. Remove drops the mod's copy."};
}
function assetTexturePanel(row,info,body,previewUrl,textureHelp){
  const textures=info.textures||[];
  if(textures.length){
    body.push(detailSection({title:"PREVIEW",body:[assetPreviewStrip(textures,previewUrl,textureHelp)]}));
    const first=textures[0];
    return {icon:LexeditorUI.iconSlot({content:el("img",{src:previewUrl(first),alt:row.name,loading:"lazy"})}),
      preview:{label:`${row.name} textures`,
        openLabel:`View ${row.name} textures`,closeLabel:`Close ${row.name} textures`,
        content:()=>LexeditorUI.stack(...textures.map(texture=>detailField({label:texture.name,
          control:el("img",{src:previewUrl(texture),alt:texture.name,style:"max-width:100%;height:auto"}),
          help:textureHelp(texture)}))),
        onClose:drawer=>drawer.replaceChildren()},
      help:"Add this file to the mod with + in the list. The game loads the mod's copy once applied. The magnifier shows every texture full-size. Remove drops the mod's copy."};
  }
  if(info.reason==="split-archive")body.push(detailSection({title:"PREVIEW",body:[
    detailField({label:"ARCHIVE",control:readonlyField("Split archive"),
      help:infoHelp("Many textures packed into one whole-file archive. It replaces as a whole file and has no per-texture preview; single .tpf and .dds files do.")})]}));
  else if(info.reason==="unreadable")body.push(detailSection({title:"PREVIEW",body:[
    detailField({label:"TEXTURES",control:readonlyField("No preview"),
      help:infoHelp("This file does not open as textures. It still replaces as a whole file.")})]}));
  else body.push(detailSection({title:"PREVIEW",body:[
    detailField({label:"TEXTURES",control:readonlyField("No preview"),
      help:infoHelp("Only TPF containers and DDS files preview.")})]}));
  return {icon:LexeditorUI.iconSlot({content:LexeditorUI.noThumbnail("ds1")}),preview:null,
    help:"Add this file to the mod with + in the list. The game loads the mod's copy once applied. Remove drops the mod's copy."};
}
function assetGeometryUrl(file,side,member){
  return `/api/assets/geometry?side=${side}&file=${encodeURIComponent(file)}&member=${encodeURIComponent(member||"")}`;
}
// The drawer's 3D stage for one Models-tab file; an object binder's
// members share it through a picker, like armor fits do.
function assetModelContent(row,info){
  const stage=LexeditorUI.modelStage({message:`Loading ${row.name}…`});
  const message=stage.lexMessage;
  const show=member=>{
    message.replaceChildren(`Loading ${row.name}…`);
    message.className="lex-model-stage-message";
    window.Ds1Preview.mount(stage,assetGeometryUrl(row.id,info.source,member)).then(task=>{
      if(!stage.isConnected)return;
      message.replaceChildren(el("span",{},"Drag to rotate · Wheel to zoom"));
      message.className="lex-model-stage-hint";
      if(task)window.__lexPreview={target:row.name,canvas:task.canvas};
    }).catch(error=>{
      if(stage.isConnected)message.replaceChildren(error.message||String(error));
    });
  };
  const members=(info.model&&info.model.members)||[];
  if(members.length<2){show(info.model.member||"");return stage;}
  let picked=info.model.member||members[0];
  const picker=el("button",{type:"button","aria-label":"Model member","aria-haspopup":"listbox",
    onclick:event=>{LexeditorUI.choicePopover({label:"Model member",
      choices:members.map(name=>({label:name,value:name})),
      select:value=>{picked=value;
        picker.replaceChildren(`Member: ${picked}`);
        show(picked);
      }}).openFor(event.currentTarget);}},`Member: ${picked}`);
  const wrap=el("div",{class:"lex-preview-variant-wrap"},picker,stage);
  show(picked);
  return wrap;
}
let assetPicker=null;
function assetFilePicker(){
  if(!assetPicker){
    assetPicker=el("input",{type:"file",id:"ds1-asset-picker",style:"display:none","aria-hidden":"true",tabindex:"-1"});
    assetPicker.onchange=event=>{const file=event.target.files[0];assetPicker.value="";
      if(!file)return;
      const target=state.rows.find(row=>key(row)===state.selected);
      if(target)void uploadAsset(target.id,file);};
    document.body.append(assetPicker);
  }
  return assetPicker;
}
function assetAddUpload(){
  if(state.assetBusy||state.readOnly)return;
  const target=state.rows.find(row=>key(row)===state.selected);
  if(!target){LexeditorUI.showToast("Select a file in the list to add it to the mod.");return;}
  assetFilePicker().click();
}
function targetIcon(){
  const namespace="http://www.w3.org/2000/svg";
  const svg=document.createElementNS(namespace,"svg");
  svg.setAttribute("viewBox","0 0 16 16");
  svg.setAttribute("aria-hidden","true");
  svg.setAttribute("class","lex-goto-icon");
  const ring=document.createElementNS(namespace,"circle");
  ring.setAttribute("cx","8");ring.setAttribute("cy","8");ring.setAttribute("r","5.5");
  ring.setAttribute("fill","none");ring.setAttribute("stroke","currentColor");ring.setAttribute("stroke-width","1.6");
  const dot=document.createElementNS(namespace,"circle");
  dot.setAttribute("cx","8");dot.setAttribute("cy","8");dot.setAttribute("r","1.4");dot.setAttribute("fill","currentColor");
  const ticks=document.createElementNS(namespace,"path");
  ticks.setAttribute("d","M8 0v3M8 13v3M0 8h3M13 8h3");
  ticks.setAttribute("stroke","currentColor");ticks.setAttribute("stroke-width","1.6");
  svg.append(ring,dot,ticks);
  return svg;
}
function goToCell(label,resolve){
  return {key:"goto",label:"Go to",sortable:false,render:row=>
    el("button",{type:"button",class:"lex-goto-button","data-goto":key(row),
      title:label(row),"aria-label":label(row),
      onclick:event=>{event.stopPropagation();void resolve(row);}},targetIcon())};
}
// The camera flies to the placement, across maps when needed. Plain row
// clicks only select; only go-to moves the camera.
async function goToPlacement(map,placementKey){
  const row=state.rows.find(entry=>key(entry)===placementKey&&entry.table===map);
  if(!row){notify(new Error("That placement is not in the open maps."));return;}
  state.mapTab="selection";
  if(map!==state.mapId){
    state.selected=placementKey;state.mapFocus=row.id;
    await chooseMap(map);
    return;
  }
  await selectPlacement(placementKey,false);
  if(viewportCtl)viewportCtl.focus(row.id);
  else state.mapFocus=row.id;
}
async function goToDrop(lotId){
  const found=await api(`/api/world/locate?table=ItemLotParam&id=${lotId}`).catch(notify);
  if(!found)return;
  if(!found.map){notify(new Error("No placed enemy drops this lot."));return;}
  await goToPlacement(found.map,`${found.map}:${found.key}`);
}
function mapsNoun(){
  const table=state.row?.table||"";
  if(table==="ItemLotParam")return "Drop";
  if(table==="ShopLineupParam")return "Shop entry";
  if(table==="ObjActParam")return "Treasure";
  return "Placement";
}
function rowActionButtons(kind){
  const locked=state.readOnly||state.rowBusy;
  const playerStart=kind==="placement"&&state.row.kind==="Player";
  const nouns=kind==="placement"?["placement","map"]:["record","table"];
  const goTo=kind==="placement"
    ?[el("button",{type:"button",class:"lex-header-icon","data-row-action":"goto","data-row-kind":kind,
      title:"Show this placement in the map viewport","aria-label":"Show this placement in the map viewport",
      onclick:()=>goToPlacement(state.row.table,key(state.row))},targetIcon())]
    :kind==="record"&&state.tab==="maps"&&state.row.table==="ItemLotParam"
    ?[el("button",{type:"button",class:"lex-header-icon","data-row-action":"goto","data-row-kind":kind,
      title:"Show where this drops in the map viewport","aria-label":"Show where this drops in the map viewport",
      onclick:()=>goToDrop(state.row.id)},targetIcon())]
    :[];
  const duplicateTitle=state.readOnly?`Open a mod project to add ${nouns[0]}s`:`Copy this ${nouns[0]} under the next free ID`;
  const removeTitle=playerStart?"The player start cannot be removed":state.readOnly?`Open a mod project to remove ${nouns[0]}s`:`Remove this ${nouns[0]} from its ${nouns[1]}`;
  return [...goTo,el("button",{type:"button",class:"lex-header-icon","data-row-action":"duplicate","data-row-kind":kind,disabled:locked,
      title:duplicateTitle,"aria-label":duplicateTitle,
      onclick:()=>duplicateRow(kind)},LexeditorUI.copyIcon()),
    el("button",{type:"button",class:"lex-header-icon","data-row-action":"remove","data-row-kind":kind,disabled:locked||playerStart,
      title:removeTitle,"aria-label":removeTitle,
      onclick:()=>removeRow(kind)},LexeditorUI.removeIcon())];
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
    const removedDirRow=!placement&&state.tab==="maps"&&state.row&&!state.rows.some(entry=>key(entry)===key(state.row));
    await loadItems();
    const firstDir=removedDirRow?directoryMatches()[0]:null;
    state.selected=firstDir?key(firstDir):state.rows[0]?key(state.rows[0]):null;state.row=null;
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
    return detailPanel({title:row.name,help:row.help,actions,paginate:{unpaged:true},
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
  return detailPanel({title:row.name,help:row.help,actions,paginate:{unpaged:true},
    body:[detailSection({title:"GRAPH",
      help:infoHelp("The line passes exactly through every stage point; between stages it blends with the left stage's Curve shape value. A shape of 1 draws straight, a higher shape starts slow, and a negative shape starts fast. T1-T5 are the stage thresholds, V1-V5 their values, S1-S5 the shaping, C1-C4 the level-up cost fields. Edit every value from the variables drawer over the graph."),
      body:[host]})]});
}
function detail(){
  const impact=state.row?.impact;
  // A record's heading is its name, on every tab. An attack's sharing
  // lives in its help bubble, never under it.
  const noun=state.tab==="npcs"?(state.sub==="unowned-shops"?"Shop entry":"NPC"):state.tab==="drops"?"Drop":state.tab==="attacks"?(state.sub==="projectiles"?"Projectile":"Attack"):state.tab==="enemies"?(state.sub==="behaviors"?"Behavior":state.sub==="ai"?"AI record":"Monster"):state.tab==="maps"?mapsNoun():state.tab==="animations"?"Event":state.tab==="effects"?"Effect":state.tab==="misc"?(state.sub==="encumbrance"?"Load band":state.sub==="encumbrance-overrides"?"Override":"Stamina"):state.tab==="text"?"Label":state.tab==="stats"?(state.sub==="levelup"?"Defense":state.sub==="curves"?"Curve":state.sub==="upgrade-materials"?"Material set":state.sub==="starting-classes"?"Class":state.sub==="starting-gifts"?"Gift":"Upgrade"):state.tab==="sound"?"Sound":"Item";
  if(state.tab==="sound"&&state.row?.table==="SoundStream"){
    const soundRow=state.rows.find(row=>key(row)===state.selected);
    if(soundRow)return renderSoundDetail(soundRow);
  }
  if(ASSET_TABS.has(state.tab))return renderAssetDetail();
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
  const tableEarly=String(state.row.table||"");
  const msbRowEarly=tableEarly.endsWith(".msb");
  const meta=state.tab==="maps"&&state.row&&msbRowEarly?`model ${state.row.model}`:state.tab==="animations"&&state.row?`${state.row.binder} · ${state.row.tae} · ${state.row.animName}`:"";
  const groups=fieldSections(state.row);
  const eventRowEarly=state.tab==="animations"&&state.animScope.level==="events"&&String(state.row.id||"").startsWith("ev:");
  const paramRowEarly=!msbRowEarly&&!tableEarly.endsWith(".anibnd.dcx")&&state.row.table!=="NativeRules"&&state.row.table!=="Asset"&&state.row.table!=="MenuText";
  const rowActionsEarly=state.row.band?bandActions():eventRowEarly?taeActions():msbRowEarly?rowActionButtons("placement"):paramRowEarly?rowActionButtons("record"):[];
  if(state.row.table==="NpcParam")return armDs1Preview(detailPanel({title:state.row.name,actions:rowActionsEarly,body:[monsterDetail(groups)]}),state.row.table,state.row.id);
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
  // The selection heading names the enemy only; the map it stands
  // in stays on the row and in the lists, never in the heading.
  if(msbRowEarly)return armDs1Preview(detailPanel({title:state.row.shortName||title,meta,help,actions:rowActionsEarly,paginate:{unpaged:true},body:msbDetail(state.row,groups)}),state.row.table,state.row.id);
  // Every items subtab renders through the same panel tabs: weapons,
  // armor, rings, spells and every kind of goods.
  if(state.tab==="items"&&(state.row.table==="EquipParamWeapon"||state.row.table==="EquipParamProtector"||state.row.table==="EquipParamAccessory"||state.row.table==="Magic"||state.row.table==="EquipParamGoods"))
    return armDs1Preview(detailPanel({title,meta,help,actions:rowActionsEarly,body:[itemDetail(groups)]}),state.row.table,state.row.id);
  // Effects render through the same panel tabs: one tab per SpEffect
  // section, with its own remembered tab.
  if(state.tab==="effects"&&state.row.table==="SpEffectParam")
    return armDs1Preview(detailPanel({title,meta,help,actions:rowActionsEarly,body:[effectDetail(groups)]}),state.row.table,state.row.id);
  return armDs1Preview(detailPanel({title,meta,help,actions:rowActionsEarly,paginate:{unpaged:true},
    body:[...groups].map(([title,body])=>detailSection({title,body}))}),state.row.table,state.row.id);
}
const ds1PreviewAvailability=new Map();
// Label kinds with equipment-screen art (icons.py); anything else keeps the
// shared fallback glyph.
const ds1LabelKinds=new Set(["physical","magic","fire","lightning","critical",
  "physicalDef","magicDef","fireDef","lightningDef",
  "str","dex","int","faith","weight","durability",
  "poison","toxic","bleed","curse","poise",
  "vit","att","end","res","souls","slot","humanity","hp","stamina",
  "divine","occult"]);const ds1IconTables=new Set(["EquipParamWeapon","EquipParamProtector","EquipParamAccessory",
  "EquipParamGoods","Magic","SpEffectParam"]);
function ds1LabelArt(panel){
  if(!(panel instanceof Element))return;
  for(const field of panel.querySelectorAll("[data-lex-icon]")){
    const kind=field.getAttribute("data-lex-icon");
    if(!ds1LabelKinds.has(kind))continue;
    if(field.querySelector(":scope > .lex-detail-field-label > img.lex-ds1-label-art"))continue;
    const art=el("img",{class:"lex-ds1-label-art",src:`/api/label?name=${encodeURIComponent(kind)}`,
      alt:"",draggable:"false","aria-hidden":"true","data-lex-no-image":"off"});
    const label=field.querySelector(":scope > .lex-detail-field-label");
    const glyph=label&&label.querySelector(":scope > .lex-type-glyph");
    if(glyph){
      const spare=glyph.cloneNode(true);
      art.addEventListener("error",()=>art.replaceWith(spare),{once:true});
      glyph.replaceWith(art);
    }else{
      art.addEventListener("error",()=>art.remove(),{once:true});
      if(label)label.prepend(art);
    }
  }
}
// A model that exists but has no still picture, in Dark Souls dress: UI
// chrome drawn here, never game art.
LexeditorUI.registerNoThumbnail("ds1",label=>{
  const namespace="http://www.w3.org/2000/svg";
  const svg=document.createElementNS(namespace,"svg");
  svg.setAttribute("viewBox","0 0 24 24");
  svg.setAttribute("aria-hidden","true");
  const ring=document.createElementNS(namespace,"circle");
  ring.setAttribute("cx","12");ring.setAttribute("cy","12");ring.setAttribute("r","8");
  ring.setAttribute("fill","none");ring.setAttribute("stroke","#8a8f98");ring.setAttribute("stroke-width","2");
  const slash=document.createElementNS(namespace,"path");
  slash.setAttribute("d","M6 18L18 6");
  slash.setAttribute("stroke","#e08a3c");slash.setAttribute("stroke-width","2.4");slash.setAttribute("stroke-linecap","round");
  svg.append(ring,slash);
  return el("span",{class:"lex-ds1-no-thumbnail",role:"img","aria-label":label,title:label},svg);
});
async function ds1PreviewTarget(table,id){
  if(table==="NpcParam"){
    const view=await api(`/api/chr/view?npc=${id}&view=thumb`);
    const chr=(view.chrs||[]).find(entry=>entry.available);
    return chr?{kind:"chr",name:`${view.name} model`,
      url:`/api/chr/geometry?chr=${encodeURIComponent(chr.id)}`}
      :{reason:`${view.name} has no character model.`};
  }
  if(!["EquipParamWeapon","EquipParamProtector","EquipParamGoods","EquipParamAccessory"].includes(table))return null;
  const view=await api(`/api/parts/view?table=${encodeURIComponent(table)}&id=${id}`);
  if(!view.available)return {reason:view.reason||"The model file is not installed."};
  const models=(view.models||[]).filter(entry=>entry.available);
  if(!models.length)return {reason:view.reason||"The model file is not installed."};
  const name=state.row&&state.row.table===table&&Number(state.row.id)===Number(id)?`${state.row.name} model`:"Model";
  if(models.length>1)return {kind:"parts",name,variants:models,table,id};
  const solo=models[0];
  return {kind:"parts",name,stem:solo.stem,
    url:`/api/parts/geometry?table=${encodeURIComponent(table)}&id=${id}&variant=${encodeURIComponent(solo.variant||"")}`};
}
function ds1ThumbUrl(target){
  if(target.url)return target.url;
  const first=target.variants&&target.variants[0];
  if(target.kind!=="parts"||!first)return null;
  return `/api/parts/geometry?table=${encodeURIComponent(target.table)}&id=${target.id}&variant=${encodeURIComponent(first.variant||"")}`;
}
function ds1PreviewReason(panel,table,id,reason){
  const heading=panel.querySelector(':scope > .lex-detail-panel-heading');
  if(!heading||heading.querySelector('.lex-detail-panel-icon'))return;
  // No model to preview, so no magnifier and no drawer: an item shows its
  // inventory picture, anything else the shared placeholder.
  let art=LexeditorUI.noThumbnail("ds1");
  if(ds1IconTables.has(table)){
    const picture=el("img",{class:"lex-ds1-item-icon",alt:"",
      src:`/api/icon?table=${encodeURIComponent(table)}&id=${encodeURIComponent(id)}`,
      draggable:"false","data-lex-no-image":"off"});
    picture.addEventListener("error",()=>{
      if(picture.isConnected)picture.replaceWith(LexeditorUI.noThumbnail("ds1"));
    },{once:true});
    art=picture;
  }
  heading.prepend(el("div",{class:"lex-detail-panel-icon",role:"img","aria-label":reason,title:reason,
    "data-lex-preview-state":"unavailable"},LexeditorUI.iconSlot({content:art})));
  heading.classList.remove("no-icon");
}
function ds1PreviewContent(target){
  const stage=LexeditorUI.modelStage({message:`Loading ${target.name}\u2026`});
  const message=stage.lexMessage;
  let controller=null;
  const show=url=>{
    message.replaceChildren(`Loading ${target.name}\u2026`);
    message.className="lex-model-stage-message";
    window.Ds1Preview.mount(stage,url).then(task=>{
      controller=task;
      if(!stage.isConnected)return;
      message.replaceChildren(el("span",{},"Drag to rotate \u00b7 Wheel to zoom"));
      message.className="lex-model-stage-hint";
      if(task)window.__lexPreview={target:target.name,canvas:task.canvas};
    }).catch(error=>{
      if(stage.isConnected)message.replaceChildren(error.message||String(error));
    });
  };
  if(!target.variants){show(target.url);return stage;}
  let picked=target.variants[0];
  // Dual-gender armor fits exactly two bodies, so the switch is one
  // toggle, not a menu: the male sign while the male model shows, the
  // female sign after one click flips to the female model.
  const GENDER_SIGN={M:"\u2642",F:"\u2640"};
  const GENDER_NAME={M:"male",F:"female"};
  const other=()=>target.variants.find(entry=>entry!==picked)||target.variants[0];
  const sign=entry=>GENDER_SIGN[entry.variant]||entry.variant||"?";
  const genderName=entry=>GENDER_NAME[entry.variant]||"other";
  const action=()=>`Show ${genderName(other())} model`;
  // The gender switch sits with the view-mode buttons, styled like one:
  // no extra row above the stage.
  const picker=el("button",{type:"button",class:"lex-model-view-mode lex-preview-gender-toggle",
    "aria-label":action(),title:action(),
    onclick:()=>{picked=other();
      picker.replaceChildren(sign(picked));
      picker.setAttribute("aria-label",action());picker.title=action();
      show(`/api/parts/geometry?table=${encodeURIComponent(target.table)}&id=${target.id}&variant=${encodeURIComponent(picked.variant)}`);
    }},sign(picked));
  stage.querySelector(":scope > .lex-model-view-modes")?.append(picker);
  show(`/api/parts/geometry?table=${encodeURIComponent(target.table)}&id=${target.id}&variant=${encodeURIComponent(picked.variant)}`);
  return stage;
}
function armDs1Preview(panel,table,id){
  if(!(panel instanceof Element))return panel;
  const cacheKey=`${table}:${id}`;
  let entry=ds1PreviewAvailability.get(cacheKey);
  if(!entry){
    entry={};
    entry.promise=ds1PreviewTarget(table,id).then(target=>entry.settled=target,
      error=>entry.settled={reason:error.message||String(error)});
    ds1PreviewAvailability.set(cacheKey,entry);
  }
  const settle=target=>{
    if(!panel.isConnected||!target)return;
    if(target.reason){ds1PreviewReason(panel,table,id,target.reason);return;}
    const heading=panel.querySelector(':scope > .lex-detail-panel-heading');
    const existing=heading&&heading.querySelector('.lex-detail-panel-icon');
    let art=null;
    if(existing&&existing.hasAttribute("data-lex-preview-state"))art=existing;
    if(heading&&!existing){
      art=el("div",{class:"lex-detail-panel-icon"},LexeditorUI.iconSlot({content:LexeditorUI.noThumbnail("ds1")}));
      heading.prepend(art);
      heading.classList.remove("no-icon");
    }
    if(art){art.removeAttribute("data-lex-preview-state");
      const thumb=ds1ThumbUrl(target);
      art.replaceChildren(LexeditorUI.iconSlot({content:thumb?window.Ds1Preview.thumbnail({url:thumb,label:target.name}):LexeditorUI.noThumbnail("ds1")}));}
    LexeditorUI.attachModelPreview(panel,{plugin:"ds1",label:target.name,
      openLabel:`View ${target.name}`,closeLabel:`Close ${target.name}`,
      content:()=>ds1PreviewContent(target),
      onClose:drawer=>{window.Ds1Preview.stop(drawer);drawer.replaceChildren();delete window.__lexPreview;}});
  };
  // Detail panels mount after detail() returns, so a cached answer settles
  // on a microtask: settling synchronously would find a detached panel.
  if("settled" in entry)queueMicrotask(()=>settle(entry.settled));else entry.promise.then(()=>settle(entry.settled));
  ds1LabelArt(panel);
  return panel;
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
  refreshAnimList();
}
function renderTaeForm(){
  const form=state.taeForm;
  const type=el("select",{"aria-label":"Event type","data-tae-input":"type",disabled:state.taeBusy,
    onchange:event=>{form.type=event.target.value;refreshAnimList();}},
    ...taeEventTypes.map(entry=>el("option",{value:String(entry.type)},entry.label)));
  type.value=form.type;
  const start=el("input",{type:"number","aria-label":"Start (s)","data-tae-input":"start",step:"any",value:form.start,disabled:state.taeBusy,
    oninput:event=>{form.start=event.target.value;}});
  const end=el("input",{type:"number","aria-label":"End (s)","data-tae-input":"end",step:"any",value:form.end,disabled:state.taeBusy,
    oninput:event=>{form.end=event.target.value;}});
  return detailPanel({title:"Add event",paginate:{unpaged:true},
    actions:[
      el("button",{type:"button",disabled:state.taeBusy,
        onclick:()=>{
          if([start,end].some(input=>!input.value.trim()||!input.checkValidity())){
            [start,end].forEach(input=>input.reportValidity());return;
          }
          submitTaeForm(form);
        }},"Create event"),
      el("button",{type:"button",disabled:state.taeBusy,onclick:()=>{state.taeForm=null;refreshAnimList();}},"Cancel")],
    body:[detailSection({title:"Event",body:[
      detailField({label:"Event type",control:type,
        help:infoHelp("Which documented event to add. Its values start at 0, so set them after. Only documented types can be added.")}),
      detailField({label:"Start (s)",control:start}),
      detailField({label:"End (s)",control:end})]})]});
}
function submitTaeForm(form){
  if(state.taeBusy||state.readOnly||state.taeForm!==form)return;
  state.taeBusy=true;state.pending++;refreshAnimList();
  edits=edits.then(async()=>{
    try{
      const result=await api("/api/tae/add",{table:form.binder,tae:form.tae,anim:form.anim,
        type:Number(form.type),start:Number(form.start),end:Number(form.end)});
      state.rows=result.events;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
      state.taeForm=null;state.selected=key(result.row);state.animQuery="";
      await loadItems();
      const index=animListMatches().findIndex(row=>key(row)===state.selected);
      state.animPage=Math.max(0,Math.floor(index/animPaneSize("events")));
    }catch(error){
      state.taeForm=null;await refreshState();await loadItems();notify(error);
    }finally{
      state.pending--;state.taeBusy=false;refreshAnimList();revealSelection();
    }
  }).catch(notify);
}
async function removeTaeEvent(){
  if(state.readOnly||state.taeBusy||state.pending||!state.row)return;
  const ok=await confirmAction({title:`Remove ${state.row.name}?`,
    message:"The event leaves the animation at once. Save keeps the removal in the mod project.",
    confirmLabel:"Remove event",cancelLabel:"Cancel"});
  if(!ok)return;
  state.taeBusy=true;state.pending++;refreshAnimList();
  try{
    const [table,id]=[state.row.table,state.row.id];
    const result=await api("/api/tae/remove",{table,id});
    state.rows=result.events;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
    state.selected=null;state.row=null;state.animQuery="";
    await loadItems();
  }catch(error){await refreshState();await loadItems();notify(error);}
  finally{state.taeBusy=false;state.pending--;refreshAnimList();revealSelection();}
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
  return detailPanel({title:form.action==="add"?"Add band":"Delete band",paginate:{unpaged:true},
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
  if(ASSET_TABS.has(state.tab))assetFilePicker();
  if(state.tab==="maps")return renderMaps();
  if(state.tab==="animations")return renderAnimPanels();
  const misc=state.tab==="misc";
  const noun=misc?(state.sub==="encumbrance"?"bands":state.sub==="encumbrance-overrides"?"overrides":"stamina"):state.tab==="effects"?"effects":state.tab==="attacks"?(state.sub==="projectiles"?"projectiles":"attacks"):state.tab==="npcs"?(state.sub==="unowned-shops"?"shop lines":"NPCs"):state.tab==="drops"?"drops":state.tab==="ai"?(state.sub==="behaviors"?"behaviors":"AI records"):state.tab==="enemies"?(state.sub==="bosses"?"bosses":"monsters"):state.tab==="text"?"labels":state.tab==="stats"?(state.sub==="levelup"?"gains":state.sub==="curves"?"curves":state.sub==="upgrade-materials"?"material sets":state.sub==="starting-classes"?"classes":state.sub==="starting-gifts"?"gifts":"upgrades"):ASSET_TABS.has(state.tab)?"files":"items";
  const label=misc?"Misc.":state.tab==="effects"?"Effects":state.tab==="attacks"?"Attacks":state.tab==="animations"?"Animations":state.tab==="npcs"?"NPCs":state.tab==="drops"?"Drops":state.tab==="ai"?"AI":state.tab==="enemies"?"Enemies":state.tab==="text"?"Text":state.tab==="stats"?"Stats":ASSET_TABS.has(state.tab)?ASSET_LABELS[state.tab]:"Items";
  // sortedRows owns this list's order (filter, name sort, meaningful-order tabs); the framework yields.
  const view=pagedListDetail({className:"ds1-records",rows:sortedRows(),key,selected:state.selected,slots:false,order:"given",noun,modOnly:modOnlySpec(),
    page:state.page,pageSize:state.pageSize,defaultSplit:32,minLeft:230,minRight:380,splitKey:"ds1-"+state.tab+"-"+state.sub,rowsKey:"ds1-"+state.tab+"-"+state.sub,barrelKey:"ds1-"+state.tab+"-"+state.sub,
    search:{key:"ds1-records-search",value:state.query,label:"Search "+noun,change:value=>{state.query=value;state.page=0;render();}},
    // Asset files join the mod through the list's add button: adding at a
    // path the game has replaces it through the loader, so asset tabs
    // need no Replace action of their own.
    add:ASSET_TABS.has(state.tab)?(()=>assetAddUpload()):undefined,
    addTitle:"Add file to mod",
    addDisabled:ASSET_TABS.has(state.tab)&&(state.readOnly||state.assetBusy),
    addDisabledReason:!ASSET_TABS.has(state.tab)?undefined:state.readOnly?"This is the game's own data, shown read-only. Create a mod to add files to it.":state.assetBusy?"An upload is already running.":undefined,
    sync:next=>{
      state.page=next.page;state.pageSize=next.pageSize;state.selection=next.selection||[];
      if(state.selected!==next.selected){state.selected=next.selected;void loadDetail().then(render).catch(notify);}
    },
    change:next=>{state.page=next.page;state.pageSize=next.pageSize;if(next.reason==="pins"&&state.pagedView?.refreshMaster)state.pagedView.refreshMaster();else render();},
    master:({rows:listed,selected,select})=>{
      selectVisibleRecord=select;
      return columnList({rows:listed,key,selected,
      decorateRow:(node,row)=>LexeditorUI.decorateSearchCandidate(node,{type:`ds1-${row.table}`,value:row.id,label:row.name}),
      sortState:state.sort,
      sort:column=>{if(misc||(state.tab==="stats"&&state.sub==="levelup"))return;state.sort={key:column,dir:state.sort.key===column?-state.sort.dir:1};render();},
      // The record is fetched first, then the shared list swaps in its detail
      // pane once. It used to draw the pane with the old record, then render
      // the whole page twice more as two loads of the same row came back.
      select:async(row,event)=>{
        await edits;
        if(!event?.shiftKey&&!event?.ctrlKey&&!event?.metaKey){state.selected=key(row);await loadDetail();}
        select(row,event);shell.refresh();},
      columns:(misc&&state.sub==="encumbrance")?[{key:"range",label:"Load",grow:1},{key:"name",label:"Name",grow:1}]:
        state.tab==="items"?[{key:"icon",label:"",width:"36px",sortable:false,render:row=>recordIconCell(row)},
          {key:"name",label:"Name",sortable:true,grow:1}]:
        state.tab==="textures"?[{key:"icon",label:"",width:"36px",sortable:false,render:row=>textureIconCell(row)},
          {key:"name",label:"Name",sortable:true,grow:1},
          {key:"kind",label:"Kind",sortable:true,render:row=>row.display?.kind??""}]:
        state.tab==="sound"&&(state.sub==="sfx"||state.sub==="music")?[{key:"name",label:"Name",sortable:true,grow:1},
          {key:"bank",label:"Bank",sortable:true,render:row=>row.bank||""},
          {key:"length",label:"Length",sortable:true,render:row=>formatSoundLength(row.duration||0)}]:
        [{key:"name",label:"Name",sortable:true,grow:1}]});
    },
    rename:renameRecord,shippedName:row=>row.shippedName,
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
    // names: starting classes and gifts take fixed reference names;
    // the game stores no name to change.
    // names: behavior and AI rows take fixed reference names; the game stores no name to change.
    // names: a menu label is named by its text; editing the text renames it.
    renamable:row=>state.tab==="text"?false:state.tab==="stats"?!["CalcCorrectGraph","EquipMtrlSetParam","CharaInitParam","NativeRules"].includes(row.table):state.tab==="items"&&!(state.sub==="spells"&&row.table!=="Magic"),
    describePinnedCell,commitPinnedCell,
    detail,emptyDetail:()=>detailPanel({title:"No matching "+noun,body:[LexeditorUI.detailNote("Change the search to find a record.")]})});
  state.pagedView=view;
  const subtabs=subtabsFor(state.tab);
  // Enemies names its one list (Monsters) so the category reads; Attacks
  // under Attacks would only repeat the tab.
  const strip=subtabBar({tabs:subtabs,showSingle:state.tab==="enemies",active:state.sub,label,order:state.tab==="sound"?"given":undefined,change:id=>navigate(state.tab,id)});
  return LexeditorUI.stack(strip,view);
}
function viewportHooks(){
  return {readOnly:state.readOnly,
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
    if(action==="duplicate"){
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
async function refreshMapsAfterUndo(entry){
  const edits=entry.edits||[entry];
  const moved=new Map();
  let namesChanged=false;
  for(const edit of edits){
    if(!String(edit.table).endsWith(".msb"))continue;
    if(edit.field==="npcId")namesChanged=true;
    else if(["posX","posY","posZ","rotX","rotY","rotZ"].includes(edit.field))
      moved.set(edit.table+":"+edit.id,{map:edit.table,id:edit.id});
  }
  for(const {map,id} of moved.values()){
    const row=state.rows.find(entry=>entry.table===map&&entry.id===id);
    if(!row)continue;
    const pos=[row.values.posX,row.values.posY,row.values.posZ];
    const rot=[row.values.rotX,row.values.rotY,row.values.rotZ];
    if(state.mapView&&map===state.mapView.map){
      const part=state.mapView.parts.find(entry=>entry.key===id);
      if(part){part.pos=pos;part.rot=rot;}
      viewportCtl?.moveTo?.(id,pos);
      viewportCtl?.turnTo?.(id,rot);
    }
    syncPlacementRow(map,id,["posX","posY","posZ"],pos);
    syncPlacementRow(map,id,["rotX","rotY","rotZ"],rot);
  }
  if(namesChanged){
    // An enemy swap can move a placement between the NPC and enemy
    // directory and change the map\u2019s own counts.
    state.mapList=(await api("/api/table?tab=viewport")).rows;
    await loadDirectory().catch(notify);
  }
  refreshMapSide();refreshDirectory();
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
  refreshMapSide();refreshDirectory();
  const host=document.querySelector("[data-viewport-host]");
  if(host&&state.tab==="maps"){
    viewportCtl=null;
    const token=++viewportMount;
    const ctl=await Ds1Viewport.mount(host,map,state.mapView,viewportHooks()).catch(failMount(host,"Could not load the map."));
    if(token!==viewportMount){ctl?.dispose?.();return;}
    viewportCtl=ctl;
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
  refreshMapSide();refreshDirectory();
}
function refreshMapSide(){
  if(state.tab!=="maps")return;
  const side=document.querySelector("[data-maps-side]");
  if(!side){render();return;}
  side.replaceChildren(mapsStrip(),mapsPane());
}
const DIRECTORY_PARAM_TABS=new Set(["drops","treasure"]);
const DIRECTORY_TABS=["drops","treasure","npcs","enemies"];
const isDirectoryFoe=row=>(row.values.kind==="Enemy"||row.values.kind==="Dummy enemy")&&row.values.npcType!==2;
const isDirectoryFriend=row=>(row.values.kind==="Enemy"||row.values.kind==="Dummy enemy")&&row.values.npcType===2;
let dirTabRestored=false;
async function loadDirectory(){
  if(!dirTabRestored){dirTabRestored=true;try{const saved=localStorage.getItem("lex-ds1-directory-tab");if(saved)state.dirTab=saved;}catch(_error){}}
  if(!DIRECTORY_TABS.includes(state.dirTab))state.dirTab="drops";
  if(state.dirTab==="npcs")state.dirRows=state.rows.filter(isDirectoryFriend);
  else if(state.dirTab==="enemies")state.dirRows=state.rows.filter(isDirectoryFoe);
  else state.dirRows=(await api("/api/table?tab="+encodeURIComponent(state.dirTab))).rows;
  const pages=Math.max(1,Math.ceil(directoryMatches().length/state.pageSize));
  if(state.dirPage>pages-1)state.dirPage=pages-1;
}
function directoryTabs(){
  return [...state.worldTabs.filter(entry=>DIRECTORY_PARAM_TABS.has(entry.id)),
    {id:"npcs",label:"NPCs",help:"Named characters who do not fight you: merchants, blacksmiths and quest givers. Pick one to see it in the map."},
    {id:"enemies",label:"Enemies",help:"Everything placed that fights you, bosses included. Pick one to see it in the map."}];
}
function directoryMatches(){
  const query=state.dirQuery.toLowerCase();
  let filtered=state.dirRows.filter(row=>(row.id+" "+row.name+" "+(row.range||"")).toLowerCase().includes(query));
  // Local keeps only rows from the open map. Placements name their map;
  // lots resolve through their dropping NPCs. Treasure rows name no
  // map, so the toggle stays off for them.
  if(state.dirLocal){
    if(state.dirTab==="npcs"||state.dirTab==="enemies")filtered=filtered.filter(row=>row.table===state.mapId);
    else if(state.dirTab==="drops")filtered=filtered.filter(row=>(row.values.maps||[]).includes(state.mapId));
  }
  return filtered.sort((a,b)=>LexeditorUI.compareRecords(a,b,state.sort)||(a.id>b.id?1:a.id<b.id?-1:0));
}
function directoryPane(){
  return el("div",{"data-maps-dir":"",style:"display:flex;flex-direction:column;min-height:0;flex:1 1 auto;min-width:0;"},directoryStrip(),...directoryList());
}
function refreshDirectory(){
  if(state.tab!=="maps")return;
  const pane=document.querySelector("[data-maps-dir]");
  if(!pane){render();return;}
  pane.replaceChildren(directoryStrip(),...directoryList());
}
function directoryStrip(){
  return subtabBar({tabs:directoryTabs(),active:state.dirTab,label:"World directory",shortcuts:false,className:"lex-dir-tabs",change:id=>{
    state.dirTab=id;state.dirPage=0;
    try{localStorage.setItem("lex-ds1-directory-tab",id);}catch(_error){}
    void loadDirectory().then(refreshDirectory).catch(notify);
  }});
}
function directoryLocalRow(){
  const supported=state.dirTab==="npcs"||state.dirTab==="enemies"||state.dirTab==="drops";
  const node=LexeditorUI.pagerToggle({label:"Local?",
    title:supported?"Show only rows from the open map":"These rows name no map yet, so Local cannot filter them",
    checked:state.dirLocal,disabled:!supported,
    change:value=>{state.dirLocal=value;state.dirPage=0;refreshDirectory();}});
  node.setAttribute("data-dir-local","");
  node.querySelector("input").setAttribute("data-lex-view-filter","");
  return node;
}
function directoryList(){
  const matches=directoryMatches();
  const pages=Math.max(1,Math.ceil(matches.length/state.pageSize));
  if(state.dirPage>pages-1)state.dirPage=pages-1;
  const shown=matches.slice(state.dirPage*state.pageSize,(state.dirPage+1)*state.pageSize);
  const param=DIRECTORY_PARAM_TABS.has(state.dirTab);
  const select=(row,event)=>{
    if(event&&(event.shiftKey||event.ctrlKey||event.metaKey))return;
    if(param)void selectDirectoryParam(row);
    else void selectPlacement(key(row),false);
  };
  const columns=[{key:"name",label:"Name",grow:1}];
  if(!param)columns.push(goToCell(row=>`Show ${row.name} in the map viewport`,row=>goToPlacement(row.table,key(row))));
  else if(state.dirTab==="drops")columns.push(goToCell(row=>`Show where ${row.name} drops`,row=>goToDrop(row.id)));
  // Search on its own row up top, like the animations panes; the pager
  // below the list only pages and filters.
  return [LexeditorUI.bottomSearch({key:"maps-directory",value:state.dirQuery,label:"Search the world",
      change:value=>{state.dirQuery=value;state.dirPage=0;refreshDirectory();}}),
    LexeditorUI.stack(
      columnList({rows:shown,key,selected:state.selected,select,columns,class:"lex-list-fill"}),
      LexeditorUI.compactPager({pages,page:state.dirPage,total:matches.length,pageSize:state.pageSize,
        filters:[directoryLocalRow()],
        change:value=>{state.dirPage=value;refreshDirectory();}}))];
}
async function selectDirectoryParam(row){
  if(key(row)===state.selected&&state.mapTab==="selection")return;
  state.selected=key(row);state.mapTab="selection";
  await loadDetail().catch(notify);
  refreshMapSide();refreshDirectory();
}
function mapsStrip(){
  return LexeditorUI.tabStrip({tabs:[{id:"maps",label:"Maps"},{id:"placements",label:"Placements"},{id:"selection",label:"Selection"}],
    active:state.mapTab,label:"Map views",change:id=>{state.mapTab=id;refreshMapSide();}});
}
function mapsPane(){
  if(state.mapTab==="placements")return placementsPane();
  if(state.mapTab==="selection"){
    const panel=detail();
    panel.style.flex="1 1 auto";panel.style.minHeight="0";
    return panel;
  }
  return mapsListPane();
}
function mapsListPane(){
  selectVisibleRecord=null;
  return LexeditorUI.stack(
    columnList({rows:state.mapList,key:row=>row.id,selected:state.mapId,select:row=>chooseMap(row.id),
      columns:[
        {key:"name",label:"Name",sortable:true,grow:1},
        {key:"npcs",label:"NPCs",sortable:true,numeric:true,sortValue:row=>row.values.npcs,render:row=>String(row.values.npcs)},
        {key:"drops",label:"Drops",sortable:true,numeric:true,sortValue:row=>row.values.drops,render:row=>String(row.values.drops)},
        {key:"enemies",label:"Enemies",sortable:true,numeric:true,sortValue:row=>row.values.enemies,render:row=>String(row.values.enemies)}]}));
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
    columnList({rows:shown,key,selected:state.selected,select,class:"lex-list-fill",
      columns:[{key:"name",label:"Name",grow:1},
        goToCell(row=>`Show ${row.name} in the map viewport`,row=>goToPlacement(row.table,key(row)))]}),
    LexeditorUI.pager({pages,page:state.page,total:here.length,pageSize:state.pageSize,
      change:value=>{state.page=value;refreshMapSide();}}));
}
function animCharMatches(){
  const needle=state.animCharQuery.trim().toLocaleLowerCase();
  const rows=(state.animChars||[]).filter(row=>!needle||String(row.name||"").toLocaleLowerCase().includes(needle));
  return rows.sort((a,b)=>String(a.name).localeCompare(String(b.name),undefined,{numeric:true,sensitivity:"base"}));
}
function animListMatches(){
  const needle=state.animQuery.trim().toLocaleLowerCase();
  const rows=state.rows.filter(row=>!needle||String(row.name||"").toLocaleLowerCase().includes(needle));
  if(state.animScope.level==="events")return rows;
  return rows.sort((a,b)=>String(a.name).localeCompare(String(b.name),undefined,{numeric:true,sensitivity:"base"}));
}
async function chooseAnimChar(row){
  if(!row||key(row)===state.animCharId)return;
  state.animCharId=key(row);state.animCharPage=0;state.animQuery="";state.animPage=0;
  state.animScope={level:"anims"};state.taeForm=null;
  const request=++recordsRequest;
  await loadAnimView(request).catch(notify);
  refreshAnimChars();refreshAnimList();remountAnim();
}
async function pickAnimMotion(row){
  if(!row||key(row)===state.selected)return;
  state.selected=key(row);
  refreshAnimList();remountAnim();
}
async function pickAnimEvent(row){
  if(!row||key(row)===state.selected)return;
  state.selected=key(row);
  await loadDetail().catch(notify);
  refreshAnimList();
}
async function animDrillEvents(row){
  const motion=row.motion;
  if(!motion||!motion.tae)return;
  state.animScope={level:"events",binder:motion.binder,tae:motion.tae,anim:motion.taeIndex,
    charName:state.animScope.charName,animName:row.name,motionFile:motion.file||null};
  state.animQuery="";state.animPage=0;state.selected=null;state.row=null;state.taeForm=null;
  const request=++recordsRequest;
  await loadAnimEvents(request).catch(notify);
  refreshAnimList();
}
async function animBackToAnims(){
  state.animScope={level:"anims",binder:state.animScope.binder,charName:state.animScope.charName};
  state.animQuery="";state.animPage=0;state.taeForm=null;
  state.rows=state.animView?animMotionRows(state.animView):[];
  const playable=state.rows.find(row=>row.motion.file)||state.rows[0];
  state.selected=playable?key(playable):null;
  state.row=null;
  refreshAnimList();
}
function currentAnimCharId(){
  const row=(state.animChars||[]).find(row=>key(row)===state.animCharId);
  return row?row.id:null;
}
function currentAnimMotion(){
  const scope=state.animScope;
  if(scope.level==="events"){
    if(!scope.motionFile)return {file:null,name:scope.animName,available:false,
      reason:"This animation has events but no playable motion."};
    return (state.animView?.anims||[]).find(motion=>motion.file===scope.motionFile)||null;
  }
  if(scope.level!=="anims")return null;
  const row=state.rows.find(row=>key(row)===state.selected);
  return row&&row.table==="AnimMotion"?row.motion:null;
}
function remountAnim(){
  if(state.tab!=="animations")return;
  const host=document.querySelector("[data-anim-host]");
  const timeline=document.querySelector("[data-anim-timeline]");
  const status=document.querySelector("[data-anim-status]");
  if(!host||!timeline||!status||!host.isConnected){render();return;}
  const token=++animMount;
  Ds1Anim.mount(host,currentAnimCharId(),currentAnimMotion(),timeline,status).catch(error=>{
    if(token!==animMount)return;
    host.querySelector(":scope > .lex-panel-loading")?.remove();
    failMount(status,"Could not load the animation.")(error);
  });
}
// A panel pages only what fits it: the fitted size caps the global
// row count, so a paginated list never grows its own scrollbar.
function animPaneSize(which){
  const fit=which==="char"?state.animCharFit:which==="events"?state.animEventFit:state.animFit;
  return Math.max(1,Math.min(state.pageSize,fit||Infinity));
}
// The fit measures the paged pane (list plus pager), and the wheel turns
// pages through that same pane: fitted lists never scroll.
function fitAnimList(list,which,size,available){
  LexeditorUI.fitListPage({list,available:available||list,pageSize:size,fixedRowHeight:32,
    resize:(fittedHeight,geometry)=>{list.style.setProperty("--lex-fitted-row-height",`${geometry.rowHeight}px`);},
    change:value=>{
      if(which==="char"){if(state.animCharFit===value)return;state.animCharFit=value;}
      else if(which==="events"){if(state.animEventFit===value)return;state.animEventFit=value;}
      else{if(state.animFit===value)return;state.animFit=value;}
      if(state.tab!=="animations")return;
      if(which==="char")refreshAnimChars();else refreshAnimList();
    }});
}
function stopAnimFit(pane){
  pane.querySelector(".lex-column-list")?.__lexFitListObserver?.disconnect?.();
}
// Fitted rows fill to the pager like paged tables: capacity tracks
// stretch the leftover and filler rows square off a short page.
function sizeAnimRows(list,size){
  LexeditorUI.padBarrelTable(list,size);
  list.classList.add("lex-page-sized-table");
  list.style.setProperty("--lex-page-row-count",String(Math.max(size,
    list.querySelectorAll(":scope > .lex-column-list-row").length)));
  list.style.setProperty("--lex-page-font-row-count",String(size));
}
function animCharsPane(){
  const here=animCharMatches();
  const size=animPaneSize("char");
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.animCharPage>pages-1)state.animCharPage=pages-1;
  const shown=here.slice(state.animCharPage*size,(state.animCharPage+1)*size);
  const select=row=>{if(key(row)!==state.animCharId)void chooseAnimChar(row);};
  const list=columnList({rows:shown,key,selected:state.animCharId,select,class:"lex-list-fill",
    columns:[{key:"name",label:"Name",grow:1}]});
  const pager=LexeditorUI.compactPager({pages,page:state.animCharPage,total:here.length,pageSize:size,
    change:value=>{state.animCharPage=value;refreshAnimChars();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizeAnimRows(list,size);
  fitAnimList(list,"char",size,both);
  return el("div",{"data-anim-chars":"",style:"display:flex;flex-direction:column;flex:1 1 auto;min-height:0;"},
    LexeditorUI.bottomSearch({key:"anims-characters",value:state.animCharQuery,label:"Search characters",
      change:value=>{state.animCharQuery=value;state.animCharPage=0;refreshAnimChars();}}),
    both);
}
function animEventsCell(){
  return {key:"events",label:"Events",sortable:false,render:row=>{
    const motion=row.motion;
    if(!motion||!motion.tae)return "";
    return el("button",{type:"button",class:"lex-goto-button","data-anim-events":key(row),
      title:`Edit events of ${row.name}`,"aria-label":`Edit events of ${row.name}`,
      onclick:event=>{event.stopPropagation();void animDrillEvents(row);}},targetIcon());}};
}
function animAnimsPane(){
  const here=animListMatches();
  const size=animPaneSize("anims");
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.animPage>pages-1)state.animPage=pages-1;
  const shown=here.slice(state.animPage*size,(state.animPage+1)*size);
  const select=row=>{if(key(row)!==state.selected)void pickAnimMotion(row);};
  const list=columnList({rows:shown,key,selected:state.selected,select,class:"lex-list-fill",
    columns:[{key:"name",label:"Name",grow:1},animEventsCell()]});
  const pager=LexeditorUI.compactPager({pages,page:state.animPage,total:here.length,pageSize:size,
    change:value=>{state.animPage=value;refreshAnimList();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizeAnimRows(list,size);
  fitAnimList(list,"anims",size,both);
  return [
    LexeditorUI.bottomSearch({key:"anims-list",value:state.animQuery,label:"Search animations",
      change:value=>{state.animQuery=value;state.animPage=0;refreshAnimList();}}),
    both];
}
function animEventsPane(){
  const here=animListMatches();
  const size=animPaneSize("events");
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.animPage>pages-1)state.animPage=pages-1;
  const shown=here.slice(state.animPage*size,(state.animPage+1)*size);
  const select=row=>{if(key(row)!==state.selected)void pickAnimEvent(row);};
  selectVisibleRecord=select;
  const scope=state.animScope;
  const back=el("button",{type:"button","data-anim-back":"",
    onclick:()=>animBackToAnims().catch(notify)},`‹ ${scope.animName||"Animations"}`);
  const list=columnList({rows:shown,key,selected:state.selected,select,class:"lex-list-fill",
    columns:[{key:"name",label:"Name",grow:1}]});
  const pager=LexeditorUI.compactPager({pages,page:state.animPage,total:here.length,pageSize:size,
    change:value=>{state.animPage=value;refreshAnimList();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizeAnimRows(list,size);
  fitAnimList(list,"events",size,both);
  return [back,
    LexeditorUI.bottomSearch({key:"anims-events",value:state.animQuery,label:"Search events",
      change:value=>{state.animQuery=value;state.animPage=0;refreshAnimList();}}),
    both,
    detail()];
}
function animListPane(){
  const level=state.animScope.level;
  return el("div",{"data-anim-list":"",style:"display:flex;flex-direction:column;flex:1 1 auto;min-height:0;"},...(level==="events"?animEventsPane():animAnimsPane()));
}
function refreshAnimChars(){
  if(state.tab!=="animations")return;
  const pane=document.querySelector("[data-anim-chars]");
  if(!pane)return;
  stopAnimFit(pane);
  pane.replaceWith(animCharsPane());
}
function refreshAnimList(){
  if(state.tab!=="animations")return;
  const pane=document.querySelector("[data-anim-list]");
  if(!pane){render();return;}
  stopAnimFit(pane);
  pane.replaceWith(animListPane());
}
function renderMaps(){
  if(!state.mapList.length)return LexeditorUI.notice({tone:"warning",message:"No map files found."});
  const current=state.mapList.find(row=>row.id===state.mapId)||state.mapList[0];
  const duplicate=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"duplicate",
    "aria-label":"Duplicate this placement",
    onclick:()=>viewportDuplicate(current.id)},LexeditorUI.copyIcon());
  const remove=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"remove",
    "aria-label":"Remove this placement",
    onclick:()=>viewportRemove(current.id)},LexeditorUI.removeIcon());
  const add=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"add",
    onclick:event=>viewportAdd(current.id,event.currentTarget)},"Add");
  const rotate=el("button",{type:"button",class:"lex-viewport-picker","data-viewport-action":"rotate",
    onclick:()=>{state.mapGizmo=state.mapGizmo==="rotate"?"move":"rotate";viewportCtl?.setGizmoMode?.(state.mapGizmo);refreshViewportBar();}},"Rotate");
  const host=el("div",{class:"lex-viewport-host","data-viewport-host":"",style:VIEWPORT_STYLE+"height:100%;flex:1 1 auto;"},LexeditorUI.loadingPanel({label:"Loading map"}));
  requestAnimationFrame(()=>{
    viewportCtl=null;refreshViewportBar();
    const token=++viewportMount;
    Ds1Viewport.mount(host,current.id,state.mapView,viewportHooks()).then(ctl=>{
      if(token!==viewportMount)return;
      viewportCtl=ctl;
      viewportCtl?.setGizmoMode?.(state.mapGizmo);
      if(state.mapSelected&&viewportCtl)viewportCtl.select(state.mapSelected);
      if(state.mapFocus&&viewportCtl){viewportCtl.focus(state.mapFocus);state.mapFocus=null;}
      refreshViewportBar();
    }).catch(error=>{if(token===viewportMount)failMount(host,"Could not load the map.")(error);});
  });
  // The buttons hover over the picture, not in a bar above it. They hang
  // on a wrapper: mounting clears the host itself for its canvas.
  const wrap=el("div",{style:"position:relative;min-width:0;flex:1 1 auto;display:flex;flex-direction:column;min-height:520px;"},host);
  LexeditorUI.hoverActions(wrap,{label:"Map actions",
    actions:[{node:duplicate},{node:remove},{node:add},{node:rotate}]});
  const viewPane=el("div",{style:"min-width:0;display:flex;flex-direction:column;"},wrap);
  const side=el("div",{"data-maps-side":"",style:"display:flex;flex-direction:column;min-width:0;min-height:0;"},mapsStrip(),mapsPane());
  const directory=LexeditorUI.collapsiblePanel({label:"Directory",side:"left",viewKey:"ds1-maps-directory",width:"360px",
    className:"ds1-directory",content:[directoryPane()]});
  // The viewport and the side share one remembered divider, like every
  // list-and-detail split: the table sets the floor through minSizes.
  const split=LexeditorUI.panelLayout([viewPane,side],"ds1-maps-view",
    {layoutKey:"ds1-maps-view-side",defaultSizes:[60,40],minSizes:[320,400]});
  split.style.flex="1 1 auto";split.style.minWidth="0";
  return el("div",{style:"display:flex;gap:8px;align-items:stretch;"},directory,split);
}
function renderAnimPanels(){
  const chars=state.animChars||[];
  if(!chars.length)return LexeditorUI.notice({tone:"warning",message:"No animation binders found."});
  const status=el("div",{class:"lex-viewport-status","data-anim-status":"",style:"flex:0 0 auto"},LexeditorUI.loadingStatus("Loading animation"));
  const host=el("div",{class:"lex-viewport-host","data-anim-host":"",style:VIEWPORT_STYLE+"height:100%;flex:1 1 auto;"});
  const timeline=el("div",{class:"lex-anim-timeline","data-anim-timeline":""});
  const wrap=el("div",{style:"position:relative;min-width:0;flex:1 1 auto;display:flex;flex-direction:column;min-height:520px;"},host);
  const viewPane=el("div",{style:"flex:1 1 auto;min-width:0;display:flex;flex-direction:column;"},wrap,timeline,status);
  const token=++animMount;
  requestAnimationFrame(()=>{
    if(token!==animMount)return;
    Ds1Anim.mount(host,currentAnimCharId(),currentAnimMotion(),timeline,status).catch(error=>{
      if(token!==animMount)return;
      host.querySelector(":scope > .lex-panel-loading")?.remove();
      failMount(status,"Could not load the animation.")(error);
    });
  });
  // Plain panels, not collapsible ones: the lists are the page, and
  // collapsing them away only stranded readers. The collapsible
  // component stays global for callers that still want it.
  const characters=el("div",{"data-anim-chars-panel":"",class:"ds1-anim-chars","aria-label":"Characters",
    style:"flex:0 0 300px;min-width:0;min-height:0;display:flex;flex-direction:column;overflow:auto;"},animCharsPane());
  const animations=el("div",{"data-anim-list-panel":"",class:"ds1-anim-list","aria-label":"Animations",
    style:"flex:0 0 360px;min-width:0;min-height:0;display:flex;flex-direction:column;overflow:auto;"},animListPane());
  return el("div",{class:"ds1-anim"},characters,viewPane,animations);
}
function monsterModelSection(){
  const view=state.chrView;
  if(!view)return LexeditorUI.detailNote("The character model could not be loaded.");
  // Buttons, not selects: switching the viewed attack edits
  // nothing, and a select would ask Vanilla readers to create a mod
  // before looking around.
  const attacks=(view&&view.attacks)||[];
  if(!attacks.some(attack=>attack.id===state.chrAttack))state.chrAttack=attacks.length?attacks[0].id:null;
  const attack=attacks.find(entry=>entry.id===state.chrAttack);
  const pickAttack=async id=>{if(id===state.chrAttack)return;state.chrAttack=id;render();};
  const attackPicker=el("button",{type:"button",class:"lex-viewport-picker","aria-label":"Attack","aria-haspopup":"listbox",
    onclick:event=>{LexeditorUI.choicePopover({label:"Attack",
      choices:attacks.map(entry=>({label:entry.name,value:entry.id})),select:pickAttack}).openFor(event.currentTarget);}},
    `Attack: ${attack?attack.name:"none"}`);
  // The stage shows the hitboxes; the Attacks tab edits them. Without
  // this button the viewed attack's slots were reachable only by
  // hunting the Attacks tab by hand.
  const editAttack=attack?el("button",{type:"button",title:`Edit ${attack.name}'s hitboxes in the Attacks tab`,
    onclick:()=>openAttack(attack.id)},"Edit in Attacks"):null;
  const status=el("div",{class:"lex-viewport-status","data-chr-status":"",style:"flex:0 0 auto"},LexeditorUI.loadingStatus("Loading model"));
  const host=el("div",{class:"lex-viewport-host","data-chr-host":"",style:VIEWPORT_STYLE+"height:auto;flex:1 1 auto;"});
  requestAnimationFrame(()=>{Ds1Viewport.mountChr(host,view,state.chrAttack,status).catch(failMount(status,"Could not load the model."));});
  return [el("div",{class:"lex-viewport-bar"},attackPicker,editAttack),host,status];
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
  const empty=!panels.length;
  const missingMods=empty?LexeditorUI.notice({message:!(status.tweaks||[]).length?`No tweak mods are installed. Tweaks live in the mod library (${status.modsRoot}).`
    :(status.tweaks||[]).some(row=>row.enabled)?"The switched-on tweaks have no settings to change."
    :"No tweaks are switched on. Switch one on in the Mods tab to change its settings here."}):null;
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
  document.querySelector("#main").replaceChildren(state.error?LexeditorUI.notice({tone:"warning",message:state.error}):state.tab==="datamap"?renderDataMap():state.tab==="info"?renderInfo():state.tab==="tweaks"?renderTweaks():renderItems());
  shell.refresh();
}
async function boot(){
  try{await refreshState();await loadItems();render();}catch(error){state.error=error.message;render();}
  finally{document.body.dataset.ds1Ready=state.error?"error":"true";await LexeditorUI.finishPluginLoading();}
}
window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&(state.dirty||state.pending||state.tweaksNeedRebuild))event.preventDefault();});
boot();
