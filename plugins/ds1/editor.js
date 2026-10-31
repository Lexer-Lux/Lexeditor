"use strict";
const {el,detailPanel,detailSection,detailField,readonlyField,infoHelp,logView,pagedListDetail,columnList,subtabBar,
  actionRow,confirmAction,modLoaderSection,tabbedPanel,applyFieldTabOverrides,hoverable,curveEditor,soundPreview}=LexeditorUI;
const state={tab:"items",sub:"consumables",tabs:[],enemyTabs:[],aiTabs:[],attackTabs:[],rows:[],selected:null,row:null,dirty:0,pending:0,
  readOnly:true,query:"",modOnly:false,page:0,pageSize:20,sorts:{},error:"",deployment:null,deployBusy:false,
  monsterTab:"basics",itemTab:"",effectTab:"",attackTab:"",monsterAttacks:null,thinkRow:null,monsterBehaviors:null,behaviorQuery:"",behaviorPage:0,tweaks:null,tweakBusy:false,tweaksNeedRebuild:false,
  effectTabs:[],statsTabs:[],animTabs:[],worldTabs:[],textTabs:[],npcTabs:[],miscTabs:[],animScope:{level:"anims"},animLeftTab:"chars",nativeRules:null,bandForm:null,bandBusy:false,taeForm:null,taeBusy:false,rowBusy:false,
  animChars:[],animCharId:null,animCharQuery:"",animCharPage:0,animQuery:"",animPage:0,animCharFit:null,animFit:null,animEventFit:null,animListError:null,animEventError:null,
  assetTabs:[{id:"files",label:"Files"}],soundTabs:[{id:"sfx",label:"Sound effects"},{id:"music",label:"Music"}],scriptTabs:[{id:"ingame",label:"Ingame menus"},{id:"common",label:"Common menus"},{id:"talk",label:"Dialogue"}],scriptDetail:null,assetDetail:null,assetBusy:false,assetUpload:null,
  assetFiles:[],
  dataMap:{rows:[]},mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1],mapView:null,
  mapId:null,mapList:[],mapTab:"maps",mapSelected:null,mapInfo:null,mapBusy:false,mapOfferOpen:false,mapGizmo:"move",mapCollisionHigh:false,mapCollisionLow:false,mapNavigation:false,mapRegions:false,mapPlacementFilter:"all",
  dirTab:"all",dirRows:[],dirQuery:"",dirPage:0,dirLocal:false,mapFocus:null,
  dirFit:null,mapListPage:0,mapListFit:null,mapListSort:null,mapFit:null,collision:null};
let edits=Promise.resolve(),navigation=0,recordsRequest=0,selectVisibleRecord=null,viewportCtl=null,viewportMount=0,animMount=0;
const lastSubByTab={};
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
      created:file.status==="new",modified:file.status==="modified",...(file.modelPick?{modelPick:file.modelPick}:{})};});
// A container's own listing: a multi-texture TPF expands into one row
// per texture (the Textures tab lists textures, not archives), while
// single-texture files, split archives and anything unreadable keep
// their file row. Counts come from the detail route, cached by path,
// size and status, so a tab revisit refetches nothing and an upload
// or removal re-expands on its new bytes.
const textureListCache=new Map();
const textureCacheKey=row=>`${row.id}|${row.values?.size}|${row.created?"new":row.modified?"modified":""}`;
const textureExpandable=row=>row.table==="Asset"&&row.values?.kind!=="archive"
  &&[".tpf",".chrtpfbdt",".tpfbhd"].some(suffix=>String(row.id||"").toLowerCase().replace(/\.dcx$/,"").endsWith(suffix));
function textureRow(fileRow,texture){
  return {table:"AssetTexture",id:`${fileRow.id}#${texture.index}`,name:texture.name,
    file:fileRow.id,member:texture.member||"",index:texture.index,
    width:texture.width,height:texture.height,format:texture.format,
    values:{file:fileRow.id,format:texture.format,width:texture.width,height:texture.height},
    display:{kind:"Textures"},created:fileRow.created,modified:fileRow.modified};
}
async function expandTextureRows(rows){
  const expandable=rows.filter(textureExpandable);
  const missing=[...new Set(expandable.filter(row=>!textureListCache.has(textureCacheKey(row))).map(row=>row.id))];
  // One call lists every missing container: hundreds of round trips kept
  // the tab on its throbber for seconds. A lone file answers in the
  // single-file shape, so both shapes land in the list cache the same way.
  // Files the answer skips keep their file row and retry next open; files
  // it refuses are cached empty under a stamp key uploads invalidate.
  if(missing.length){
    const query=missing.map(relative=>`file=${encodeURIComponent(relative)}`).join("&");
    const result=await api(`/api/assets?scope=textures&side=mod&${query}`);
    const lists=result.lists||(missing.length===1?{[missing[0]]:result}:null)||{};
    for(const relative of missing){
      const row=expandable.find(entry=>entry.id===relative);
      const found=lists[relative];
      if(row&&found)textureListCache.set(textureCacheKey(row),(found.textures||[]).filter(item=>item&&item.name!==undefined));
    }
  }
  return rows.flatMap(row=>{
    if(!textureExpandable(row))return [row];
    const textures=textureListCache.get(textureCacheKey(row))||[];
    if(textures.length<2)return [row];
    return textures.map(texture=>textureRow(row,texture));
  });
}
function remapTextureSelection(){
  if(state.tab!=="textures"||!state.selected?.startsWith("Asset:"))return;
  if(state.rows.some(row=>key(row)===state.selected))return;
  const file=state.selected.slice("Asset:".length);
  const first=state.rows.find(row=>row.table==="AssetTexture"&&row.file===file);
  if(first)state.selected=key(first);
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
  get canUndo(){return !this.applying&&this.undoStack.length>0;},get canRedo(){return !this.applying&&this.redoStack.length>0;},
  record(entry){
    if(this.applying||(!entry.edits&&entry.before===entry.after))return;
    entry.at=LexeditorUI.nextHistoryTick();
    this.undoStack.push(entry);if(this.undoStack.length>200)this.undoStack.shift();
    this.redoStack=[];shell.refresh();
    // Structural mesh edits can dwarf scalar history. Keep retained snapshots
    // within 16 MiB rather than retaining 200 complete collision meshes.
    let bytes=this.undoStack.reduce((sum,item)=>sum+(item.snapshotBytes||0),0);
    while(bytes>16*1024*1024&&this.undoStack.length){bytes-=this.undoStack.shift().snapshotBytes||0;}
  },
  undo(){return this.move('before');},
  redo(){return this.move('after');},
  move(side){
    if(this.applying)return Promise.resolve(false);
    this.applying=true;
    state.pending++;shell.refresh();
    const operation=edits.then(async()=>{
      const source=side==='before'?this.undoStack:this.redoStack;
      const target=side==='before'?this.redoStack:this.undoStack;
      const entry=source.at(-1);
      if(!entry||!await this.apply(entry,side))return false;
      source.pop();target.push(entry);return true;
    }).finally(()=>{this.applying=false;state.pending--;shell.refresh();});
    edits=operation.then(()=>{});
    return operation;
  },
  async apply(entry,side){
    try{
      let refresh=false;
      for(const edit of entry.edits||[entry]){
        if(edit.collision){
          const result=await api('/api/map/collision/state',{table:edit.table,mesh:edit[side]});
          state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
          continue;
        }
        if(edit.rename){
          const renamed=await api("/api/rename",{table:edit.table,id:edit.id,name:edit[side],sub:state.sub});
          state.dirty=renamed.dirtyCount;state.changes=renamed.changes||state.changes;
          if(state.row&&state.row.table===edit.table&&state.row.id===edit.id)state.row=renamed.row;
          for(const listed of state.rows||[])if(key(listed)===`${edit.table}:${edit.id}`){listed.name=renamed.row.name;if(renamed.modified!==undefined)listed.modified=renamed.modified;}
          continue;
        }
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
      // Hitbox edits from the enemy viewer repaint the viewer: a render
      // would close the drawer mid-inspection. Anything else renders.
      else if((entry.edits||[entry]).every(edit=>edit.table==="AtkParam_Npc")&&await refreshChrDrawer()){}
      else render();
      return true;
    }catch(error){notify(error);return false;}
  },
  clear(){this.undoStack=[];this.redoStack=[];shell.refresh();}};
// Ctrl+Z lives in the shell's shortcut dispatcher, which undoes fieldHistory:
// a plugin binding of its own undid twice per press.
const shell=LexeditorUI.mountShell({
  host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ds1",name:"Dark Souls Remastered",themeName:"ds1",theme:{accent:"#a4824c","accent-text":"#141210"}},
  tabs:[{id:"items",label:"Items",help:"Edit item properties in the selected mod. Vanilla is read-only. Unknown fields stay protected. Saves do not install a mod."},
    {id:"text",label:"Text",help:"Edit the game's menu text: NPC dialogue, event and system messages, help and menu labels. Item names and descriptions edit on the item."},
    {id:"scripts",label:"Scripts",help:"How the menus and conversations work, step by step. Pick a script on the left to read one state: the commands it runs and the conditions that move it on. Read-only for now."},
    {id:"enemies",label:"Enemies",help:"Edit reviewed monster stats: health, defense, drops and effects. A monster's Attacks tab lists the attack records its parameters reference; its brains live in the AI tab. Vanilla is read-only. Save changes the mod project."},
    {id:"npcs",label:"NPCs",help:"Edit friendly characters: merchants, blacksmiths and quest givers. Health, souls and defense work the same as on monsters. Each merchant's Shop tab holds their stock and prices. Vanilla is read-only. Save changes the mod project."},
    {id:"drops",label:"Drops",help:"Edit enemy and corpse drop tables: what each lot drops and at what rates. One lot may serve several enemies. Vanilla is read-only. Save changes the mod project."},
    {id:"attacks",label:"Attacks",help:"Edit enemy and player attack damage and hitboxes. The Attacks list holds enemy attacks, Player attacks holds yours, and Projectiles holds flying attacks: arrows, spells and breath. One attack record can serve several monsters or several player moves, so an edit changes every use of it. Vanilla is read-only. Save changes the mod project."},
    {id:"ai",label:"AI",help:"Enemy brains. AI tables are how enemies sense and answer the player; behaviors are the moves each one can choose from. Vanilla is read-only. Save changes the mod project."},
    {id:"maps",label:"Maps",help:"Select a map record to edit its properties, or move and rotate it in the picture. The layer controls show high collision, low collision, navigation meshes and region boundaries. Collision behavior includes kill planes, lethal falls and death cameras. Regions and events also appear in the placements list. Vanilla is read-only. Save writes the mod project."},
    {id:"animations",label:"Animations",help:"Edit animation event timing and settings. Pick a character, then an animation, then an event. Add inserts a documented event, and Remove deletes the selected one. Events that share a timestamp change together. Character files this version cannot open are skipped. Vanilla is read-only, and Save changes the mod project."},
    {id:"effects",label:"Effects",help:"Edit buffs, debuffs and equipment passives. A shared effect changes every item or ability using it. Unknown properties stay protected."},
    {id:"stats",label:"Stats",help:"Stat scaling for the Stats Rework. Scaling curves holds the 39 scaling graphs: weapon paths, Max HP, Max MP, defense, resistances, level-up cost and level sync. Weapon upgrades and Armor upgrades hold each upgrade level's multipliers. Level-up gains holds what each level-up adds to defense. Full records stay in Items, and no scaling graph here covers stamina recovery or attunement slots."},
    {id:"models",label:"Models",help:"What you see and bump into: character, object and map geometry. Tinted names replace an installed file; a pen nib marks files only the mod carries. A preview shows the file the game would load. Add and Remove save at once. Vanilla is read-only."},
    {id:"textures",label:"Textures",help:"The images on the models. Tinted names replace an installed file; a pen nib marks files only the mod carries. A preview shows the file the game would load. Add and Remove save at once. Vanilla is read-only."},
    {id:"sound",label:"Sound",help:"Every sound effect and music track, listed one by one. The Bank row names the file that holds the stream. A stream's actions replace its bank or remove the mod's copy. Vanilla is read-only."},
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
  tab==="sound"?state.soundTabs:tab==="scripts"?state.scriptTabs:ASSET_TABS.has(tab)?state.assetTabs:
  tab==="misc"?state.miscTabs.map(entry=>entry.id==="encumbrance"?{...entry,help:"Add or merge load ranges. Each band has a movement profile and its own recovery percentage. The last band has no upper limit. Save and Apply to use your rules."}:entry.id==="misc"?{...entry,help:"Base stamina recovery before effects and load penalties. Save and Apply to use your value."}:entry.id==="encumbrance-overrides"?{...entry,help:"Special conditions that replace band recovery. They take priority over load ranges and do not create another range. Save and Apply to use your rules."}:entry):state.tabs;
async function refreshState(){
  const result=await api("/api/state");
  state.tabs=result.tabs;state.enemyTabs=result.enemyTabs;state.aiTabs=result.aiTabs;state.attackTabs=result.attackTabs;
  state.effectTabs=result.effectTabs||[];state.statsTabs=result.statsTabs||[];state.animTabs=result.animTabs||[];state.worldTabs=result.worldTabs||[];state.textTabs=result.textTabs||[];state.npcTabs=result.npcTabs||[];state.miscTabs=result.miscTabs||[];state.nativeRules=result.nativeRules;
  state.readOnly=result.readOnly;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
  if(result.theme&&result.theme.sounds)LexeditorUI.configureThemeSounds(result.theme.sounds.rows||[]);
}
// Each tab keeps its own list order: one global sort meant a column
// click in Items re-sorted Drops too, so entering Drops showed some
// other tab's order instead of the alphabetical default. Entering a
// tab restores its own order, alphabetical until the reader picks one.
const sortScope=()=>`${state.tab}-${state.sub}`;
const tabSort=()=>state.sorts[sortScope()]||{key:"name",dir:1};
function sortedRows(){
  const query=state.query.toLowerCase();
  // The search reads the whole row: names, ids, ranges and every
  // property value, raw and formatted. A behavior that costs 5 stamina
  // answers '5' even when no name holds a 5. Placement titles name no
  // map, so their map names join the haystack outright.
  const haystack=row=>{
    const parts=[row.id,row.name,row.range||"",...((row.values?.mapNames)||[])];
    for(const source of [row.values,row.display]){
      if(!source||typeof source!=="object")continue;
      for(const value of Object.values(source)){
        if(value===null||value===undefined||typeof value==="object")continue;
        // "None" marks an empty slot, not content: it sits in every row's
        // display, so it answered "none" with the whole list.
        if(typeof value==="string"&&value.toLowerCase()==="none")continue;
        parts.push(value);
      }
    }
    return parts.join(" ").toLowerCase();
  };
  const filtered=state.rows.filter(row=>haystack(row).includes(query));
  // Script states keep the archive's own order (script, group, state),
  // which a name sort would scramble (state 10 sorts before state 3).
  if(state.tab==="scripts"||state.tab==="misc"||(state.tab==="stats"&&state.sub==="levelup")||(state.tab==="animations"&&state.animScope.level==="events"))return filtered;
  // The game's own order (by record) breaks ties.
  return filtered.sort((a,b)=>LexeditorUI.compareRecords(a,b,tabSort())||a.id-b.id);
}
async function loadAnims(request){
  if(state.animScope.level==="events"){await loadAnimEvents(request);return;}
  await loadAnimChars(request);
  if(state.animLeftTab==="events"){
    const row=(state.rows||[]).find(entry=>key(entry)===state.selected);
    if(row&&row.motion&&row.motion.tae){
      animScopeFor(row);
      state.animQuery="";state.animPage=0;state.selected=null;state.row=null;state.taeForm=null;
      await loadAnimEvents(request);
    }else state.animLeftTab="anims";
  }
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
  let detail;
  try{
    detail=await api(`/api/anim/list?chr=${encodeURIComponent(row.id)}`);
  }catch(error){
    if(request!==recordsRequest||state.animCharId!==key(row))return;
    state.animListError=error.message||String(error);state.rows=[];state.selected=null;state.row=null;return;
  }
  if(request!==recordsRequest||state.animCharId!==key(row))return;
  state.animListError=null;
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
      eventCount:entry.events??0,
      available:false,reason:"This animation has events but no playable motion."}}));
  return [...motions,...orphans].sort((a,b)=>String(a.name).localeCompare(String(b.name),undefined,{numeric:true,sensitivity:"base"}));
}
async function loadAnimEvents(request){
  const scope=state.animScope;
  let result;
  try{
    result=await api(`/api/table?tab=animations&scope=events&binder=${encodeURIComponent(scope.binder||"")}&tae=${encodeURIComponent(scope.tae||"")}&anim=${scope.anim??""}`);
  }catch(error){
    if(request!==recordsRequest||state.tab!=="animations")return;
    state.animEventError=error.message||String(error);state.rows=[];state.selected=null;state.row=null;return;
  }
  if(request!==recordsRequest||state.tab!=="animations")return;
  state.animEventError=null;
  state.rows=result.rows;
  state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
  if(!state.rows.some(row=>key(row)===state.selected))state.selected=state.rows[0]?key(state.rows[0]):null;
  seekAnimEvent((state.rows||[]).find(entry=>key(entry)===state.selected));
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
  else if(state.tab==="scripts")url="/api/scripts?scope="+encodeURIComponent(sub);
  const result=await api(url);
  if(request!==recordsRequest||state.sub!==sub)return;
  if(wantSounds)state.rows=(result.rows||[]).map(row=>({...row,values:{bank:row.bank,length:formatSoundLength(row.duration||0),size:row.size}}));
  else if(ASSET_TABS.has(state.tab)){state.assetFiles=result.files;state.rows=assetRows(result.files);if(state.tab==="textures"){state.rows=await expandTextureRows(state.rows);remapTextureSelection();}}
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
  let row=state.collision?.rows.find(row=>key(row)===state.selected)||state.rows.find(row=>key(row)===state.selected);
  let sub=state.sub;
  if(!row&&state.tab==="maps"){
    row=state.dirRows.find(row=>key(row)===state.selected);
    if(row)sub=state.dirTab;
  }
  if(!row&&state.tab==="maps"&&state.mapView){
    const light=(state.mapView.lights||[]).find(entry=>`${state.mapView.map}:${entry.key}`===state.selected);
    if(light)row={id:light.key,table:state.mapView.map,name:light.name};
    const message=(state.mapView.messages||[]).find(entry=>`${state.mapView.map}:${entry.key}`===state.selected);
    if(message)row={id:message.key,table:state.mapView.map,name:message.name};
  }
  if(!row||row.table==="AnimMotion"){state.row=null;state.monsterAttacks=null;state.npcShop=null;state.thinkRow=null;state.monsterBehaviors=null;state.assetDetail=null;return;}
  if(row.table==="Asset"||row.table==="AssetTexture"){
    state.assetDetail=null;state.assetSounds=null;
    const detail=await api(`/api/assets?scope=textures&side=mod&file=${encodeURIComponent(row.file||row.id)}`);
    if(state.selected!==key(row))return;
    state.row=row.table==="AssetTexture"?{table:"AssetTexture",id:row.id,name:row.name,file:row.file,member:row.member,index:row.index,width:row.width,height:row.height,format:row.format}:{table:"Asset",id:row.id,name:row.name};state.assetDetail=detail;state.monsterAttacks=null;state.npcShop=null;state.thinkRow=null;state.monsterBehaviors=null;
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
  if(row.table==="ScriptState"){
    const detail=await api(`/api/script/state?id=${encodeURIComponent(row.id)}`);
    if(state.selected!==key(row))return;
    state.row={table:"ScriptState",id:row.id,name:row.name};state.scriptDetail=detail.row;state.monsterAttacks=null;state.npcShop=null;state.thinkRow=null;state.monsterBehaviors=null;state.assetDetail=null;
    return;
  }
  const detail=await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}&sub=${encodeURIComponent(sub)}`);
  if(state.selected!==key(row))return;
  const isMonster=row.table==="NpcParam";
  const [attacks,shop,think,behaviors]=await Promise.all([
    isMonster?api(`/api/attacks?monster=${row.id}`):null,
    isMonster?api(`/api/shop?npc=${row.id}`):null,
    thinkRowFor(detail.row),
    isMonster?api(`/api/behaviors?monster=${row.id}`):null]);
  if(state.selected!==key(row))return;
  state.row=detail.row;state.monsterAttacks=attacks;state.npcShop=shop;state.thinkRow=think;state.monsterBehaviors=behaviors;
}
async function loadTweaks(){
  state.tweaks=await api("/api/tweaks");
  state.tweaksNeedRebuild=!!state.tweaks.needsRebuild;
}
async function loadDeployment(){
  state.deployment=await api("/api/deployment");
}
async function navigate(tab,sub=state.sub,selected=null){
  // An attack's viewer link survives its own navigation and no other:
  // anything else the reader opens drops the pending drawer.
  if(!keepViewerPending)pendingViewer=null;
  keepViewerPending=false;
  // Subtabs bypass the shell, so the switch announces itself here too:
  // old content out, throbber in, before the first await.
  document.querySelector("#main")?.replaceChildren(LexeditorUI.loadingPanel({label:`Loading ${sub}`}));

  const token=++navigation;await edits;
  const changedTab=tab!==state.tab;state.tab=tab;state.bandForm=null;state.taeForm=null;
  // A bare tab switch (shell tab strip, history Back) returns to the tab's
  // own last subtab. Without this the previous tab's sub rode along as the
  // default, failed validation, and fell back to consumables.
  if(changedTab&&arguments.length<2&&lastSubByTab[tab])sub=lastSubByTab[tab];
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
  else if(tab==="scripts"&&!state.scriptTabs.some(entry=>entry.id===sub))sub="ingame";
  if(tab==="animations"&&changedTab)state.animScope={level:"anims"};
  if(sub!==state.sub||changedTab||selected){state.sub=sub;state.selected=selected;state.query="";state.page=0;}
  lastSubByTab[tab]=state.sub;
  try{
    if(["items","enemies","npcs","drops","attacks","ai","maps","animations","effects","stats","misc","models","textures","sound","text","scripts"].includes(tab))await loadItems();
    if(tab==="maps")await loadMaps();
    else if(tab==="datamap")state.dataMap=await api("/api/data-map");else if(tab==="info")await loadDeployment();else if(tab==="tweaks")await loadTweaks();
    if(token!==navigation)return;
    // A link lands on the page that holds its record, not on page one.
    if(tab==="maps"&&selected){state.mapTab=String(selected).includes(".msb:message:")?"messages":"placements";if(String(selected).includes(".msb:"))state.dirTab="all";}
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
const openAttack=(id,table="AtkParam_Npc")=>navigate("attacks",table==="AtkParam_Pc"?"player-attacks":"attacks",`${table}:${id}`);
const BEHAVIOR_SUBS={BehaviorParam:"behaviors",BehaviorParam_PC:"player-behaviors"};
const openBehavior=(id,table="BehaviorParam")=>navigate("ai",BEHAVIOR_SUBS[table]||"behaviors",`${table}:${id}`);
const LINK_TAB_LABELS={effect:"Effects",attack:"Attacks",bullet:"Attacks",goods:"Items",catalog:"Items",ai:"AI",drop:"Drops",stat:"Stats",behavior:"AI",sound:"Sound"};
const ATTACK_SUBS={AtkParam_Npc:"attacks",AtkParam_Pc:"player-attacks"};
const STAT_SUBS={EquipMtrlSetParam:"upgrade-materials",ReinforceParamWeapon:"weapon-upgrades",ReinforceParamProtector:"armor-upgrades",CalcCorrectGraph:"curves"};
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
  if(table==="EquipParamWeapon"){const category=value("weaponCategory");return category===12?"shields":[13,14].includes(category)?"ammo":"weapons";}
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
  if(link.kind==='collisionVertex'){
    const [,map,model,layer,mesh]=link.table.split('|');
    const options={model,layer,mesh:Number(mesh),kind:'vertices',selected:`${link.table}:${link.id}`};
    if(state.tab==='maps'&&state.mapTab==='collision'&&state.mapId===map)return chooseCollision(options);
    state.mapId=map;state.mapTab='collision';state.collision={...options,rows:[]};
    return navigate('maps','placements',options.selected);
  }
  if(link.kind==="catalog"&&link.tab)return navigate(link.tab,link.sub,`${link.table}:${link.id}`);
  if(link.kind==="effect")return openEffect(link);
  if(link.kind==="attack")return navigate("attacks",ATTACK_SUBS[link.table]||"attacks",`${link.table}:${link.id}`);
  if(link.kind==="bullet")return navigate("attacks","projectiles",`Bullet:${link.id}`);
  if(link.kind==="ai")return navigate("ai","ai",`${link.table}:${link.id}`);
  if(link.kind==="npc")return navigate(link.tab||"enemies",link.sub||"monsters",`${link.table}:${link.id}`);
  if(link.kind==="drop")return navigate("drops","drops",`${link.table}:${link.id}`);
  if(link.kind==="stat")return navigate("stats",STAT_SUBS[link.table],`${link.table}:${link.id}`);
  if(link.kind==="behavior")return openBehavior(link.id,link.table);
  if(link.kind==="sound")return navigate("sound",link.sub||"sfx",`SoundStream:${link.bank}::${link.stream}`);
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
const LINK_NOUNS={effect:"effect",attack:"attack",bullet:"projectile",goods:"item",ai:"AI table",npc:"NPC",drop:"drop table",behavior:"behavior",sound:"sound"};
const STAT_NOUNS={EquipMtrlSetParam:"material set",ReinforceParamWeapon:"weapon upgrade table",ReinforceParamProtector:"armor upgrade table",CalcCorrectGraph:"scaling curve"};
const NPC_TAB_LABELS={enemies:"Enemies",npcs:"NPCs"};
const CATALOG_NOUNS={EquipParamWeapon:"weapon",EquipParamProtector:"armor piece",EquipParamAccessory:"accessory",Magic:"spell"};
const CATALOG_SUBS={EquipParamWeapon:"weapons",EquipParamProtector:"armor",EquipParamAccessory:"rings",Magic:"spells",EquipParamGoods:"consumables"};
function linkNoun(link){return link.kind==="catalog"?(CATALOG_NOUNS[link.table]||"record"):link.kind==="stat"?STAT_NOUNS[link.table]:LINK_NOUNS[link.kind]||"record";}
async function finderTarget(link,value){
  if(link.kind==="catalog"&&link.tab)return [link.tab,link.sub];
  if(link.kind==="effect")return ["effects","effects-all"];
  if(link.kind==="attack")return ["attacks",ATTACK_SUBS[link.table]||"attacks"];
  if(link.kind==="bullet")return ["attacks","projectiles"];
  if(link.kind==="ai")return ["ai","ai"];
  if(link.kind==="npc")return [link.tab||"enemies",link.sub||"monsters"];
  if(link.kind==="drop")return ["drops","drops"];
  if(link.kind==="stat")return ["stats",STAT_SUBS[link.table]];
  if(link.kind==="behavior")return ["ai",BEHAVIOR_SUBS[link.table]||"behaviors"];
  if(link.kind==="sound")return ["sound",link.sub||"sfx"];
  try{return ["items",catalogSub(link.table,await recordRow(link.table,value))];}
  catch(error){return ["items",CATALOG_SUBS[link.table]||"consumables"];}
}
async function recordPreview(link){
  if(link.kind==="sound")return soundLinkPreview(link);
  if(link.field==="materialSetId"&&Array.isArray(link.path)&&link.path.length){
    const table=el("div",{style:"display:grid;grid-template-columns:auto minmax(0,1fr);gap:1px 10px;"});
    table.replaceChildren(...link.path.flatMap(entry=>[el("span",{style:"white-space:nowrap;opacity:.75;"},`+${entry.level}`),
      el("span",{},entry.description||"Empty set")]));
    return LexeditorUI.stack({fill:false,compact:true},el("strong",{},link.name),table);
  }
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
    const picture=el("img",{src:`/api/icon?table=${encodeURIComponent(row.table)}&id=${encodeURIComponent(row.id)}&key=${encodeURIComponent(entry.field)}`,
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
    apply:{title:"Apply this mod to the installed game?",message:"Lexeditor combines this mod's saved changes with enabled library mods. It preserves the original data and applies native changes in memory. Close the game first.",confirmLabel:"Apply"},
    disable:{title:"Restore the original installed files?",message:"Lexeditor restores owned data files and removes its loader. Saved mod settings and the game executable stay unchanged.",confirmLabel:"Restore original"}
  };
  if(action==="apply"&&state.nativeRules?.migration)confirmations.apply.message+=" "+state.nativeRules.migration;
  const ok=await confirmAction({...confirmations[action],cancelLabel:"Cancel"});
  if(!ok)return;
  state.deployBusy=true;render();
  try{const result=await api("/api/deployment/"+action,{});await loadDeployment();
    if(result.disabledMods?.length)LexeditorUI.showToast(result.disabledMods.map(mod=>`${mod.name} was switched off: ${mod.error}`).join("\n"),{tone:"warning"});}
  catch(error){notify(error);}
  finally{state.deployBusy=false;render();}
}
function reportTweakRebuild(result){
  if(result.tweaksError)LexeditorUI.showToast("Changes saved; deployment failed. " + result.tweaksError,{tone:"warning"});
  else if(result.disabledMods?.length)LexeditorUI.showToast("Changes saved. Other enabled mods rebuilt. " + result.disabledMods.map(mod=>`${mod.name} was switched off: ${mod.error}`).join("\n"),{tone:"warning"});
  else if(result.tweaksDeferred)LexeditorUI.showToast("Changes saved. Close the game, then save again to rebuild the tweaks.");
  else if(result.tweaksRebuilt)LexeditorUI.showToast("Changes saved and tweaks rebuilt.");
  else return false;
  return true;
}
async function save(){
  await edits;
  try{
    const result=await api("/api/save",{});attackPreviews.clear();await refreshState();
    if(state.tab==='maps'&&state.mapTab==='collision')await refreshCollision();
    if(state.tab==="tweaks"){await loadTweaks();render();}else shell.refresh();
    if(!reportTweakRebuild(result))LexeditorUI.showToast("Changes saved to the mod project.");
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
  ignoredModRevision=modRevision;
}
// An item's in-game name lives in the game's text, which the mod carries
// beside its parameters; the server renames it there.
function renameRecord(row,name){
  if(state.readOnly)return;
  state.pending++;shell.refresh();
  edits=edits.then(async()=>{
    try{
      const before=String(row.name??"");
      const result=await api("/api/rename",{table:row.table,id:row.id,name,sub:state.sub});
      state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
      if(state.row&&key(state.row)===key(row))state.row=result.row;
      for(const listed of state.rows||[])if(key(listed)===key(row)){listed.name=result.row.name;if(result.modified!==undefined)listed.modified=result.modified;}
      fieldHistory.record({table:row.table,id:row.id,rename:true,before,after:String(result.row.name??"")});
    }catch(error){notify(error);}
    finally{state.pending--;render();}
  });
}
function patchRowValues(table,id,values,display,name,modified){
  recordRows.delete(`${table}:${id}`);
  const target=state.collision?.rows.find(row=>row.table===table&&row.id===id)||state.rows.find(row=>row.table===table&&row.id===id)||state.dirRows.find(row=>row.table===table&&row.id===id);
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
      const field=state.row?.fields?.find(item=>item.key===propertyKey);
      if(dialog&&field&&other.isConnected)other.replaceWith(dialogFace(state.row,field,dialog));
      else{
        const text=dialog?(dialog.text||`(no dialog text ${dialog.id})`):"";
        if("value" in other)other.value=text;else other.textContent=text;
        other.title=dialog?.text||"";
      }
      continue;
    }
    if(other.hasAttribute("data-lex-sound")){
      const entry=(state.row?.recordLinks||[]).find(item=>item.field===propertyKey&&item.kind==="sound");
      const field=state.row?.fields?.find(item=>item.key===propertyKey);
      if(entry&&field&&other.isConnected)other.replaceWith(soundFace(state.row,field,entry));
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
        const rawId=other.slice(row.table.length+1);
        const id=row.table.startsWith('CollisionMesh|')?rawId:Number(rawId);
        const prior=(await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${id}&sub=${encodeURIComponent(state.sub)}`)).row.fields.find(item=>item.key===field.key)?.value;
        const changed=await api("/api/edit",{table:row.table,id,field:field.key,value,sub:state.sub});
        latest=changed;
        updates.push({id,result:changed});
        done.push({table:row.table,id,field:field.key,before:prior,after:changed.row.fields.find(item=>item.key===field.key)?.value});
      }
      fieldHistory.record(done.length>1?{edits:done}:done[0]);
      // The count and the list come from the last edit made, which saw them all.
      state.dirty=latest.dirtyCount;state.changes=latest.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;attackPreviews.delete(`${row.table}:${row.id}`);
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
      if((row.table==="AtkParam_Npc"||row.table==="AtkParam_Pc")&&hitSlotOf(field.key)!==null)syncHitSlotStatus(result.row);
      // A link appearing or disappearing swaps the control itself (a
      // picker becomes a record face, or back), so the panel rebuilds
      // the way it does when an edit changes another control's shape.
      const hadLink=(row.recordLinks||[]).some(entry=>entry.field===field.key);
      const hasLink=(latest.row.recordLinks||[]).some(entry=>entry.field===field.key);
      if(row.table==="NativeRules"||["goodsType","weaponCategory"].includes(field.key)||hadLink!==hasLink){await loadItems();render();}
      else{
        for(const update of updates)patchRowValues(row.table,update.id,update.result.values,update.result.display,update.result.name,update.result.modified);
        if(row.table.endsWith(".msb")&&state.tab==="maps"&&state.mapView&&["posX","posY","posZ","rotX","rotY","rotZ","scaleX","scaleY","scaleZ"].includes(field.key)){
          // A typed move or turn moves the scene part too; only the
          // gizmo did, so typed edits left the mesh standing behind.
          const fresh=updates[updates.length-1].result.values||{};
          if(row.table===state.mapView.map){
            const lightRow=String(row.id).startsWith("light:");
            const messageRow=String(row.id).startsWith("message:");
            const part=state.mapView.parts.find(entry=>entry.key===row.id)||(lightRow?(state.mapView.lights||[]).find(entry=>entry.key===row.id):messageRow?(state.mapView.messages||[]).find(entry=>entry.key===row.id):null);
            const pos=[fresh.posX,fresh.posY,fresh.posZ];
            if(part)part.pos=pos;
            // Messages stand in no scene: the cached view moves, the viewport does not.
            if(!messageRow)viewportCtl?.moveTo?.(row.id,pos);
            if(!lightRow&&!messageRow){
              const rot=[fresh.rotX,fresh.rotY,fresh.rotZ],scale=[fresh.scaleX,fresh.scaleY,fresh.scaleZ];
              if(part){part.rot=rot;part.scale=scale;}
              viewportCtl?.turnTo?.(row.id,rot);
              viewportCtl?.scaleTo?.(row.id,scale);
            }
          }
        }
        if(row.table.endsWith(".msb")&&state.tab==="maps"&&state.mapView?.map===row.table&&String(row.id).startsWith("region:")&&["shapeType","width","height","depth","radius"].includes(field.key)){
          const part=state.mapView.parts.find(entry=>entry.key===row.id);
          const fresh=updates[updates.length-1].result.row;
          const values=Object.fromEntries((fresh?.fields||[]).map(item=>[item.key,item.value]));
          if(part){
            part.shape=values.shapeType;
            part.dimensions=Object.fromEntries(["width","height","depth","radius"].filter(name=>values[name]!==undefined).map(name=>[name,values[name]]));
            viewportCtl?.updateRegion?.(row.id,part.shape,part.dimensions);
          }
          if(field.key==="shapeType")refreshMapsDetail();
        }
        if(row.table.endsWith(".msb")&&field.key==="hitFilter"&&state.mapView?.map===row.table){
          const hitFilter=updates[updates.length-1].result.row.fields.find(item=>item.key==="hitFilter")?.value;
          const part=state.mapView.parts.find(entry=>entry.key===row.id);
          if(part)part.hitFilter=hitFilter;
          viewportCtl?.updateCollision?.(row.id,hitFilter);
          refreshMapSide();
        }
        if(row.table.endsWith(".msb")&&String(row.id).startsWith("light:")&&state.tab==="maps"&&state.mapView&&row.table===state.mapView.map){
          // The lights list reads the view, not the record lists, so
          // a typed edit refreshes the cached light itself.
          const entry=(state.mapView.lights||[]).find(item=>item.key===row.id);
          const fresh=updates[updates.length-1].result.values||{};
          if(entry){if(fresh.posX!==undefined)entry.pos=[fresh.posX,fresh.posY,fresh.posZ];if(fresh.preset!==undefined)entry.preset=fresh.preset;}
        }
        if(row.table.endsWith(".msb")&&String(row.id).startsWith("message:")&&state.tab==="maps"&&state.mapView&&row.table===state.mapView.map){
          // The messages list reads the view like the lights list, so a
          // typed text edit refreshes the cached message itself.
          const entry=(state.mapView.messages||[]).find(item=>item.key===row.id);
          const fresh=updates[updates.length-1].result.values||{};
          if(entry&&fresh.text!==undefined)entry.textId=fresh.text;
        }
        if(row.table.endsWith(".msb")&&field.key==="npcId"&&state.tab==="maps"){
          // An enemy swap can move a placement between the NPC and
          // enemy directory and change the map\u2019s own counts.
          state.mapList=(await api("/api/table?tab=viewport")).rows;
          await loadDirectory().catch(notify);
          refreshMapSide();refreshDirectory();refreshMapsDetail();
        }
        if(row.table.startsWith('CollisionMesh|'))await refreshCollision();
        else if(updates.some(update=>update.result.refreshRows))await loadItems().then(render);
        else if(state.tab==="animations"){await reloadAnimRows().catch(notify);refreshAnimList();refreshAnimDetail();}
        else if(field.key.startsWith("residentSpEffectId")||["refId","refCategory","replaceSpEffectId","cycleOccurrenceSpEffectId","atkOccurrenceSpEffectId"].includes(field.key))render();
        // An icon or model edit repaints its face (the picture or name beside the number).
        else if(field.key.startsWith("iconId")||field.key==="equipModelId")render();
        else if(field.key==="aiThinkId"||field.key==="behaviorVariationId"){await refreshMonsterPanels();render();}
        else if(String(tabSort().key||"").startsWith("pin:"))render();
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
  const vector={Position:'pos',Rotation:'rot',Scale:'scale'}[propertyKey];
  if(vector)return {label:propertyKey,render:row=>{
    const values=['X','Y','Z'].map(axis=>row.values?.[vector+axis]).filter(value=>value!==undefined);
    return values.map(value=>LexeditorUI.formatNumber(value,{maximumSignificantDigits:7})).join(', ');}};
  if(propertyKey==="icon")return{editable:false,label:"",sortable:false,
    width:"var(--lex-fitted-row-height,36px)",
    render:row=>state.tab==="textures"?textureIconCell(row):recordIconCell(row)};
  // Field shape is per table, not per row: effect options are global and
  // bounds come from the schema, so the open record describes every row.
  const field=(state.row?.fields||[]).find(item=>item.key===propertyKey);
  if(!field||!field.editable||field.type==="longtext")return null;
  const entries=field.type==="enum"?Object.entries(field.enum||{}):null;
  return {editable:true,type:field.type,numeric:field.type==="number",label:shownLabel(field),unit:labelSuffix(field),
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
const DEGREES=/\s*\(degrees?\)$/;
const DEGREES_PER_SEC=/\s*\(degrees\/second\)$/;
const METRES=/\s*\(metres?\)$/;
const VEL=/\s*\(m\/s\)$/;
const ACCEL=/\s*\(m\/s\^2\)$/;
const FRAMES=/\s*\(frames?\)$/;
const KG=/\s*\(kg\)$/;
const CM=/\s*\(cm\)$/;
const SOULS=/\s*\(souls\)$/;
const PCT_PER_SEC=/\s*\(%\/s\)$/;
const PER_LEVEL=/\s*\(per level\)$/;
const shownLabel=field=>field.label.replace(PERCENT,"").replace(TIMES,"").replace(DEGREES_PER_SEC,"").replace(RATE,"").replace(SECONDS,"").replace(MS,"").replace(POINTS,"").replace(DEGREES,"").replace(METRES,"").replace(VEL,"").replace(ACCEL,"").replace(FRAMES,"").replace(KG,"").replace(PCT_PER_SEC,"").replace(PER_LEVEL,"").replace(CM,"").replace(SOULS,"");
// The unit suffix the shown label dropped, derived from it so the two
// cannot drift: pinned headers resolve the same rename, then re-attach it.
const labelSuffix=field=>field.label.slice(shownLabel(field).length);
// Think distances carry their unit suffixes in their labels, like every
// other unit below (fourteen in metres, plus the ear search distance in
// centimetres, the same family).

// Placement coordinates keep their conflict-list labels, so their units
// wire off field keys here instead of label suffixes.
const MSB_UNITS={posX:"m",posY:"m",posZ:"m",rotX:"\u00b0",rotY:"\u00b0",rotZ:"\u00b0",scaleX:"\u00d7",scaleY:"\u00d7",scaleZ:"\u00d7"};
function controlFor(row,field){
  const plain=plainControlFor(row,field);
  const msbUnit=row.table&&String(row.table).endsWith(".msb")?MSB_UNITS[field.key]:null;
  const control=msbUnit&&field.type==="number"?LexeditorUI.unitField(plain,msbUnit)
    :PERCENT.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"%")
    :TIMES.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"\u00d7")
    // Degrees per second keeps its degree; the generic rate below would not.
    :DEGREES_PER_SEC.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"\u00b0/s")
    // The quantity names the row already; the unit only says per second.
    :RATE.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"/sec")    // Level-up gains: defense added per level spent on the stat.
    :PER_LEVEL.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"/level")
    :SECONDS.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"s")
    :MS.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"ms")
    :POINTS.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"pts")
    :DEGREES.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"\u00b0")
    :METRES.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"m")
    :VEL.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"m/s")
    :ACCEL.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"m/s\u00b2")
    :FRAMES.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"frames")
    :KG.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"kg")
    :CM.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"cm")
    :SOULS.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"souls")
    :PCT_PER_SEC.test(field.label)&&field.type==="number"?LexeditorUI.unitField(plain,"%/s"):plain;

  if(!field.editable||field.vanilla===null||field.vanilla===undefined||field.type==="text"||field.type==="longtext")return control;
  const input=plain;
  const current=()=>field.type==="bool"?(input.checked?1:0):Number(String(input.value).replace(/,/g,""));
  return LexeditorUI.provenanceControl({control,current,vanilla:field.type==="bool"?Number(field.vanilla):field.vanilla,
    internal:true,
    format:field.type==="enum"?value=>(field.key==="materialSetId"&&field.vanillaDisplay!==undefined
      &&Number(value)===Number(field.vanilla)?field.vanillaDisplay:field.enum[String(value)]||String(value)):undefined,
    same:(left,right)=>Number(left)===Number(right),
    apply:value=>commit(row,field,value,input)});
}
// A record link is a hoverable face: it names the linked record, previews
// it on hover and opens it on click, with the target's menu icon when its
// table has item art. The finder button that picks another
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
      preview:()=>recordPreview(entry),activate:()=>openRecord(entry),
      icon:ds1IconTables.has(entry.table)?`/api/icon?table=${encodeURIComponent(entry.table)}&id=${encodeURIComponent(entry.id)}`:null})
      :el("span",{class:"ds1-unset-face"},label));
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
  if(link?.kind==='collisionVertex'){
    const source={kind:state.collision.kind,selected:state.selected,selection:[...(state.selection||[])]};
    return LexeditorUI.thingFinderButton({label:`Change ${field.label}`,disabled:state.readOnly,
      type:`ds1-${link.table}`,prompt:`Choose the vertex for ${row.name}.`,
      target:()=>chooseCollision({kind:'vertices'}),origin:()=>chooseCollision(source),
      accept:picked=>{state.selection=source.selection;commit(row,field,Number(String(picked).replace(/^v:/,'')),face);}});
  }
  const clearEntry=Object.entries(field.enum||{}).find(([,label])=>label==="None");
  const source={};
  const value=()=>{const live=state.row&&key(state.row)===key(row)?state.row:row;
    return live.fields?.find(item=>item.key===field.key)?.value??field.value;};
  return LexeditorUI.thingFinderButton({class:"ds1-find-reference",label:`Change ${field.label}`,
    disabled:state.readOnly||field.disabled||!link,type:`ds1-${link?.table||"record"}`,
    clearValue:clearEntry?.[0],clearLabel:clearEntry?.[1],
    prompt:link?`Choose the ${linkNoun(link)} for ${row.name}.`:"Choose a record.",
    target:async()=>{Object.assign(source,{tab:state.tab,sub:state.sub,selected:state.selected,selection:state.selection});
      const [tab,sub]=await finderTarget(link,value());await navigate(tab,sub);},
    origin:()=>navigate(source.tab,source.sub,source.selected),
    accept:picked=>{state.selection=source.selection;commit(row,field,Number(picked),face);face.value=String(picked);}});
}
// A Message Text ID shows its Event text as a hoverable face beside the
// number: hover previews the message, clicking opens it in the Text tab.
// The face carries the dialog sync marks, so an edit rebuilds it with
// the fresh message in place.
function dialogFace(row,field,dialog){
  const marks={"data-field-key":field.key,"data-lex-dialog":""};
  if(!dialog?.text)return readonlyField(dialog?`(no dialog text ${dialog.id})`:"",
    {"aria-label":`${field.label} text`,title:dialog?.text||"",format:false,...marks});
  const first=dialog.text.split("\n",1)[0].slice(0,80);
  const face=hoverable({content:dialog.text,targetType:"ds1-text",
    targetId:`${dialog.table}:${dialog.id}`,targetLabel:`${first} in Text`,
    "aria-label":`${field.label} text: ${first}`,
    preview:()=>el("div",{class:"ds1-dialog-preview"},dialog.text),
    activate:()=>navigate("text",dialog.sub,`${dialog.table}:${dialog.id}`)});
  face.dataset.fieldKey=field.key;
  face.setAttribute("data-lex-dialog","");
  return face;
}
function dialogPicker(row,field,dialog,input){
  const clearEntry=Object.entries(field.enum||{}).find(([,label])=>label==="None");
  const source={};
  return LexeditorUI.thingFinderButton({class:"ds1-find-reference",label:`Change ${field.label}`,
    disabled:state.readOnly||field.disabled,type:`ds1-${dialog.table}`,
    clearValue:clearEntry?.[0],clearLabel:clearEntry?.[1],
    prompt:`Choose the message for ${row.name}.`,
    target:async()=>{Object.assign(source,{tab:state.tab,sub:state.sub,selected:state.selected,selection:state.selection});
      await navigate("text",dialog.sub);},
    origin:()=>navigate(source.tab,source.sub,source.selected),
    accept:picked=>{state.selection=source.selection;commit(row,field,Number(picked),input);}});
}
// The TAE sound ID a stream answers to, mirroring assets.stream_number:
// o7230.wav answers 7230; birds.wav and o1201open.wav answer nothing.
function soundStreamNumber(name){
  const match=/^[A-Za-z]*(\d+)\.wav$/i.exec(String(name||""));
  return match?Number(match[1]):null;
}
// A Play-sound event's sound: the derived bank's stream, playable in
// place, opening in the Sound tab on click. An orphaned player stops
// instead of playing on where no pause button can reach it.
function soundLinkPreview(link){
  const player=el("audio",{controls:true,preload:"none",
    src:`/api/sound/stream?file=${encodeURIComponent(link.bank||"")}&stream=${encodeURIComponent(link.stream||"")}`,
    style:"width:100%;color-scheme:dark;",
    "aria-label":`Play ${link.name||`sound ${link.id}`}`});
  player.addEventListener("timeupdate",()=>{if(!player.isConnected)player.pause();});
  // Detail rows crush in a hover card, so the bank rides one text line.
  const sub=typeof link.duration==="number"&&link.bank?`${link.bank} \u00b7 ${formatSoundLength(link.duration)}`:(link.bank||"");
  return LexeditorUI.stack({fill:false,compact:true},el("strong",{},link.name||`Sound ${link.id}`),
    ...(sub?[el("span",{},sub)]:[]),player);
}
// A Play-sound event's Sound is a number with a face beside it: the face
// names the bank the number derives to, previews the stream on hover and
// opens it in the Sound tab, while the number stays editable. Like a
// reference face it repaints from the live links and carries a value
// property, so commits and detail sync treat it the same way; like a
// dialog face it carries the sync marks, so a typed edit rebuilds it.
function soundFace(row,field,link){
  const face=el("span",{class:"ds1-sound-face ds1-reference-face","data-field-key":field.key,"data-lex-sound":""});
  const paint=()=>{
    const live=state.row&&key(state.row)===key(row)?state.row:row;
    const entry=(live.recordLinks||[]).find(item=>item.field===field.key&&item.kind==="sound")||link;
    const value=live.fields?.find(item=>item.key===field.key)?.value??field.value;
    face.replaceChildren(entry&&entry.resolved?hoverable({content:entry.name,targetType:"ds1-sound",
      targetId:`${entry.bank}::${entry.stream}`,targetLabel:`${entry.name} in Sound`,
      preview:()=>soundLinkPreview(entry),activate:()=>openRecord(entry)})
      :el("span",{class:"ds1-unset-face"},`Unknown sound ${value}`));
  };
  let current=String(field.value);
  Object.defineProperty(face,"value",{configurable:true,
    get:()=>current,
    set:next=>{current=String(next);paint();}});
  paint();
  return face;
}
// A Play-sound event's Sound earns the shared thing finder: the Sound
// tab's numbered streams become hold-to-choose candidates, and the picked
// stream's number writes back into the event. The animations tab cannot
// rebuild its drill from a bare navigate(), so the way back carries the
// source character, scope and selection with it.
function soundPicker(row,field,face,link){
  const source={};
  return LexeditorUI.thingFinderButton({class:"ds1-find-reference",label:`Change ${field.label}`,
    disabled:state.readOnly||field.disabled||!link,type:"ds1-SoundStream",
    prompt:link?`Choose the ${linkNoun(link)} for ${row.name}.`:"Choose a record.",
    target:async()=>{Object.assign(source,{tab:state.tab,sub:state.sub,selected:state.selected,selection:state.selection,
      charId:state.animCharId,leftTab:state.animLeftTab,
      scope:state.animScope?{level:state.animScope.level,binder:state.animScope.binder,tae:state.animScope.tae,
        anim:state.animScope.anim,motionFile:state.animScope.motionFile,charName:state.animScope.charName}:null});
      const [tab,sub]=await finderTarget(link,face.value);await navigate(tab,sub);},
    origin:()=>source.tab!=="animations"?navigate(source.tab,source.sub,source.selected):restoreAnimSource(source),
    accept:picked=>{
      state.selection=source.selection;
      // A picked stream answers by its number (o7230.wav answers 7230):
      // that number is what the event stores. The bank stays derived, so
      // the event's own bank selector is untouched.
      const number=soundStreamNumber(String(picked).split("::").pop());
      if(number===null){notify(new Error("That stream has no number, so no event can play it."));return;}
      commit(row,field,number,face.parentElement?.querySelector("input")??face);
      face.value=String(number);}});
}
// The sound finder returns to the animations tab the way it left it: the
// character, the drilled motion's events and the selected event. A bare
// navigate() resets the scope to the motions list, stranding the reader
// away from the event they just picked a sound for.
async function restoreAnimSource(source){
  await navigate(source.tab||"animations",source.sub);
  state.selection=source.selection;
  if(!(state.animChars||[]).some(entry=>key(entry)===source.charId))return;
  // navigate() preserves the character and loads its motions; only a
  // drilled events list needs rebuilding, the way a timeline cue drills it.
  const scope=source.scope||{};
  if(scope.level==="events"){
    const same=(state.rows||[]).find(entry=>entry.motion&&(entry.motion.file||null)===(scope.motionFile||null)&&
      (entry.motion.tae||null)===(scope.tae||null)&&String(entry.motion.taeIndex??"")===String(scope.anim??""));
    if(same){state.selected=key(same);await animDrillEvents(same);}
  }else if((state.rows||[]).some(entry=>key(entry)===source.selected)){
    state.selected=source.selected;
  }
  state.animLeftTab=source.leftTab||state.animLeftTab;
  const picked=(state.rows||[]).find(entry=>key(entry)===source.selected);
  if(picked&&state.animScope.level==="events"){
    // The drill leaves no row, so the pick always loads, even when the
    // event was already the selection.
    state.selected=null;
    await pickAnimEvent(picked);
    const size=paneSize("events");
    const index=animListMatches().findIndex(entry=>key(entry)===state.selected);
    if(index>=0)state.animPage=Math.floor(index/size);
  }
  refreshAnimLeft();refreshAnimDetail();
  remountAnim();
}
// A Model ID earns the shared thing finder: the Models tab's binders
// of its piece become hold-to-choose candidates, and the binder's
// number writes back into the ID.
function modelPicker(row,field,face,entry){
  const source={};
  return LexeditorUI.thingFinderButton({class:"ds1-find-asset",label:`Choose model for ${row.name}`,
    disabled:state.readOnly||field.disabled,type:entry.pick,
    prompt:`Choose the model for ${row.name}. Hold a file to choose it.`,
    target:async()=>{Object.assign(source,{tab:state.tab,sub:state.sub,selected:state.selected,selection:state.selection});
      await navigate("models","files");},
    origin:()=>navigate(source.tab,source.sub,source.selected),
    accept:picked=>{state.selection=source.selection;commit(row,field,Number(picked),face);face.value=String(picked);}});
}
// Icon IDs choose from a gallery: every menu icon as its own picture,
// since a sheet cell has no row to hold and choose. Escape leaves
// through the Cancel button, like every hand-built dialog.
function iconGalleryButton(row,field,face){
  return el("button",{type:"button",class:"lex-thing-finder ds1-icon-gallery",title:`Choose icon for ${row.name}`,
    "aria-label":`Choose icon for ${field.label}`,disabled:state.readOnly||field.disabled,
    onclick:event=>{event.preventDefault();event.stopPropagation();void openIconGallery(row,field,face);}},
    LexeditorUI.selectionIcon());
}
async function openIconGallery(row,field,face){
  let ids;
  try{ids=(await api("/api/icon-catalog")).icons||[];}
  catch(error){notify(error);return;}
  const live=state.row&&key(state.row)===key(row)?state.row.fields?.find(item=>item.key===field.key)?.value:field.value;
  const backdrop=el("div",{class:"lex-dialog-backdrop"});
  const close=()=>{loader?.disconnect();backdrop.remove();};
  const grid=el("div",{class:"ds1-icon-gallery-grid",role:"listbox","aria-label":`Icons for ${field.label}`});
  // Eight hundred cells each fetching its art at once buried the
  // server lanes an edit needs, so pictures load as their cells near
  // the view instead. The buttons keep their size meanwhile.
  const loader="IntersectionObserver" in window?new IntersectionObserver(entries=>{
    for(const entry of entries){
      if(!entry.isIntersecting)continue;
      const picture=entry.target;loader.unobserve(picture);
      picture.src=picture.dataset.src;delete picture.dataset.src;
    }
  },{root:grid,rootMargin:"200px"}):null;
  const watch=picture=>{if(loader)loader.observe(picture);else picture.src=picture.dataset.src;};
  for(const id of ids){
    const current=id===live;
    const picture=el("img",{alt:"",draggable:"false","data-lex-no-image":"off","data-src":`/api/icon-art?icon=${id}`});
    watch(picture);
    grid.append(el("button",{type:"button",class:"ds1-icon-choice"+(current?" current":""),role:"option",
      "aria-selected":current?"true":"false",title:`Icon ${id}`,onclick:()=>{
        commit(row,field,id,face);face.value=String(id);close();}},
      picture));
  }
  const dialog=el("section",{class:"lex-dialog ds1-icon-gallery",role:"dialog","aria-modal":"true","aria-label":`Choose icon for ${field.label}`},
    el("h2",{},`Choose icon for ${field.label}`),grid,
    el("div",{class:"lex-dialog-actions"},
      ...(field.emptyValue!==undefined?[el("button",{type:"button",class:"lex-dialog-action",onclick:()=>{
        commit(row,field,field.emptyValue,face);face.value=String(field.emptyValue);close();}},"Clear icon")]:[]),
      el("button",{type:"button",class:"lex-dialog-action",onclick:close},"Cancel")));
  backdrop.append(dialog);
  backdrop.addEventListener("click",event=>{if(event.target===backdrop)close();});
  document.body.append(backdrop);
  dialog.querySelector(".ds1-icon-choice.current")?.scrollIntoView({block:"nearest"});
  dialog.querySelector(".lex-dialog-action")?.focus();
}
function assetChoiceButton(row,field,face,entry){
  if(entry.tab==="models"&&entry.pick)return modelPicker(row,field,face,entry);
  if(entry.tab==="textures")return iconGalleryButton(row,field,face);
  return null;
}
// An asset face replaces its ID's number box, the way a record face
// replaces its select: the menu picture and its number, or the parts
// binder name. Hover previews it (the icon larger, the model as the
// Models tab would); clicking opens the containing file. The finder
// beside it picks another one visually. A face whose target cannot
// resolve says so instead of pointing nowhere.
function assetFaceControl(row,field,entry){
  const face=el("span",{class:"ds1-asset-face","data-field-key":field.key});
  const paint=()=>{
    const live=state.row&&key(state.row)===key(row)?state.row:row;
    const current=(live.recordLinks||[]).find(item=>item.field===field.key)||entry;
    const value=live.fields?.find(item=>item.key===field.key)?.value??field.value;
    face.replaceChildren();
    if(!current||current.resolved===false||!current.id){
      face.append(el("span",{class:"ds1-unset-face"},current&&current.name||"None"));
      return;
    }
    const isIcon=current.tab!=="models";
    const src=`/api/icon?table=${encodeURIComponent(row.table)}&id=${row.id}&key=${encodeURIComponent(field.key)}&v=${value}`;
    const hover=hoverable({label:isIcon?`Icon ${value}`:current.name,
      targetType:"ds1-asset",targetId:current.id,
      targetLabel:`${current.name} in ${isIcon?"Textures":"Models"}`,
      icon:isIcon?src:null,
      preview:isIcon?()=>el("img",{src,alt:"",draggable:"false",style:"width:80px;height:80px;object-fit:contain;","data-lex-no-image":"off"}):()=>assetPreview(row,current),
      activate:()=>openRecord(current)});
    face.append(hover);
    // The icon face shows its picture; the model face shows only the
    // binder name until the parts view says a mesh is installed, then
    // the same snapshot the Models tab uses. No mesh, no picture.
    if(!isIcon&&window.Ds1Preview)api(`/api/parts/view?table=${encodeURIComponent(row.table)}&id=${row.id}`).then(view=>{
      const models=((view&&view.models)||[]).filter(item=>item.available);
      if(!models.length||!hover.isConnected)return;
      const thumb=window.Ds1Preview.thumbnail({url:`/api/parts/geometry?table=${encodeURIComponent(row.table)}&id=${row.id}&variant=${encodeURIComponent(models[0].variant||"")}`,label:`${row.name} model`});
      thumb.classList.add("lex-hoverable-icon");
      hover.prepend(thumb);
    }).catch(()=>{});
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
// The text tab's <?tags?>, curated from the 873 the installed FMGs use
// (codex/ds1/text-tags.md): the names, numbers, buttons and lookups a mod
// author actually inserts. Titles say what each puts in, in player terms.
const DS1_TEXT_TAG_GROUPS=[
 {label:"Names",tags:[
  {label:"deadName",insert:"<?deadName?>",title:"The name of the phantom that died."},
  {label:"joinName",insert:"<?joinName?>",title:"The name of the phantom that joined."},
  {label:"hostName",insert:"<?hostName?>",title:"The name of the world owner."},
  {label:"leaveName",insert:"<?leaveName?>",title:"The name of the phantom that left."},
  {label:"itemName",insert:"<?itemName?>",title:"The name of the item this event is about."},
  {label:"itemNum",insert:"<?itemNum?>",title:"How many of the item this event is about."},
  {label:"pcName",insert:"<?pcName?>",title:"The player character's name."},
  {label:"mapName",insert:"<?mapName?>",title:"The name of the current map."}]},
 {label:"Values",tags:[
  {label:"souls",insert:"<?souls?>",title:"The soul count the player holds now."},
  {label:"demandSoul",insert:"<?demandSoul?>",title:"The price the shop asks, in souls."},
  {label:"sellSouls",insert:"<?sellSouls?>",title:"The souls selling gives."},
  {label:"getSoulNum",insert:"<?getSoulNum?>",title:"The souls just gained."},
  {label:"evntAcquittalPrice",insert:"<?evntAcquittalPrice?>",title:"The absolution price, in souls."},
  {label:"playTime",insert:"<?playTime?>",title:"How long this character has played."}]},
 {label:"Buttons",tags:[
  {label:"attackR",insert:"<?attackR?>",title:"The right-hand attack button glyph."},
  {label:"attackL",insert:"<?attackL?>",title:"The left-hand attack button glyph."},
  {label:"subAttackR",insert:"<?subAttackR?>",title:"The right strong-attack button glyph."},
  {label:"subAttackL",insert:"<?subAttackL?>",title:"The left strong-attack button glyph."},
  {label:"selectUD",insert:"<?selectUD?>",title:"The scroll up and down glyph."},
  {label:"selectLR",insert:"<?selectLR?>",title:"The move left and right glyph."},
  {label:"selectAll",insert:"<?selectAll?>",title:"The move in any direction glyph."},
  {label:"conclusion",insert:"<?conclusion?>",title:"The confirm button glyph."},
  {label:"cancel",insert:"<?cancel?>",title:"The back button glyph."},
  {label:"spin",insert:"<?spin?>",title:"The rotate glyph."},
  {label:"spinLR",insert:"<?spinLR?>",title:"The rotate left and right glyph."},
  {label:"commando",insert:"<?commando?>",title:"The toggle-display button glyph."},
  {label:"viewChange",insert:"<?viewChange?>",title:"The switch-view button glyph."},
  {label:"changeArmR",insert:"<?changeArmR?>",title:"The switch right-hand gear glyph."},
  {label:"changeArmL",insert:"<?changeArmL?>",title:"The switch left-hand gear glyph."},
  {label:"changeMagic",insert:"<?changeMagic?>",title:"The switch spell glyph."},
  {label:"cameraMove",insert:"<?cameraMove?>",title:"The move-camera glyph."},
  {label:"playerMove",insert:"<?playerMove?>",title:"The move-character glyph."},
  {label:"keyboardEnter",insert:"<?keyboardEnter?>",title:"The keyboard confirm glyph."},
  {label:"keyboardEsc",insert:"<?keyboardEsc?>",title:"The keyboard back glyph."},
  {label:"pageUp",insert:"<?pageUp?>",title:"The page-up glyph."},
  {label:"pageDown",insert:"<?pageDown?>",title:"The page-down glyph."},
  {label:"scrollUp",insert:"<?scrollUp?>",title:"The scroll-one-line-up glyph."},
  {label:"scrollDown",insert:"<?scrollDown?>",title:"The scroll-one-line-down glyph."}]},
 {label:"Lookups",tags:[
  {label:"sysmsg@id",insert:"<?sysmsg@?>",
   title:"Another system message, by its id. 1 is OK.",caretBack:2},
  {label:"platmsg@id",insert:"<?platmsg@?>",
   title:"The platform's own button for an action id.",caretBack:2},
  {label:"gdsparam@id",insert:"<?gdsparam@?>",
   title:"A value the running event supplies, by its id.",caretBack:2},
  {label:"goodsNameId@id",insert:"<?goodsNameId@?>",
   title:"An item's name, by its goods id.",caretBack:2}]},
 {label:"Soapstone",tags:[
  {label:"bmsg",insert:"<?bmsg?>",title:"The message word the player picked."},
  {label:"upr",insert:"<?upr?>",title:"The word's upper position."},
  {label:"low",insert:"<?low?>",title:"The word's lower position."}]},
 {label:"Forge",tags:[
  {label:"itemNameBeforeForge",insert:"<?itemNameBeforeForge?>",title:"The gear's name before reinforcing."},
  {label:"itemNameAfterForge",insert:"<?itemNameAfterForge?>",title:"The gear's name after reinforcing."}]}];
function plainControlFor(row,field){
  if(!field.editable){
    // A protected link still names its record where the field is: the
    // face previews and opens it, with no finder to change it. Nothing
    // is left for a Linked-records ghetto, so the tab is gone.
    const stuck=(row.recordLinks||[]).find(entry=>entry.field===field.key);
    if(stuck&&stuck.kind!=="npc")return referenceFace(row,field);
    return readonlyField(field.value,{"aria-label":field.label});
  }
  const attrs={"aria-label":field.label,"data-field-key":field.key,disabled:state.readOnly||field.disabled};
  // The shared shell still catches an edit attempt here and offers Create a
  // mod; disabling the control too matches the greyed-out, cursor:default
  // read-only look every other plugin's own fields already use instead of a
  // control that looks editable but shows a blocked cursor.
  if(field.type==="bool")return el("input",{...attrs,type:"checkbox",checked:!!field.value,
    onchange:event=>commit(row,field,event.target.checked?1:0,event.target)});
  if(field.type==="text"){
    const input=el("input",{...attrs,type:"text",value:field.value,
      maxlength:field.maxLength||48,required:field.required??true,onchange:event=>{
        const box=event.target;
        if(field.required!==false&&!box.value.trim()||!box.checkValidity()){box.reportValidity();return;}
        commit(row,field,box.value,box);
      }});
    if(row.table==="MenuText")
      return el("div",{class:"lex-ds1-text-editor"},input,LexeditorUI.tagBar({
        target:node=>node.parentElement?.querySelector("textarea,input"),
        groups:DS1_TEXT_TAG_GROUPS,
        help:infoHelp("Tag buttons insert the game's codes at the caret. Each button names what it puts in.")}));
    return input;
  }
  if(field.type==="longtext"){
    const area=LexeditorUI.textArea({...attrs,value:field.value,rows:6,
      maxlength:field.maxLength||2000,"aria-multiline":"true",onchange:event=>{
        const input=event.target;
        if(!input.checkValidity()){input.reportValidity();return;}
        commit(row,field,input.value,input);
      }});
    if(row.table==="MenuText"||/\.fmg$/.test(row.table||""))
      return el("div",{class:"lex-ds1-text-editor"},area,LexeditorUI.tagBar({
        target:node=>node.parentElement?.querySelector("textarea,input"),
        groups:DS1_TEXT_TAG_GROUPS,
        help:infoHelp("Tag buttons insert the game's codes at the caret. Each button names what it puts in.")}));
    return area;
  }
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
  const assetLink=(row.recordLinks||[]).find(entry=>entry.kind==="asset"&&entry.field===field.key);
  if(assetLink)return assetFaceControl(row,field,assetLink);
  return el("input",{...attrs,type:"number",value:field.value,min:field.minimum,max:field.maximum,
    step:field.step??(/^(f|angle)/.test(field.dtype)?"any":1),onchange:event=>{
      const input=event.target;if(!input.value.trim()||!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,Number(input.value),input);
    }});
}
const GROUP_ORDER=["Description","Basics","Starting gear","Starting spells","Starting items","Body & gestures","Body","Defense","Absorption","Combat","Requirements & costs","Thresholds","Growth","Curve shape","Level-up cost","Effects & references","Upgrades",
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
  if(/require|proper|slot|consume|stamina|dexterity|humanity|hero|vowtype/.test(name))return "Requirements & costs";
  if(/motion|anim|spatk|hold/.test(name))return "Use behavior";
  return "Properties";
}
// Starting kits, upgrade materials and drop slots keep each item and its
// count in parallel fields; the detail shows them as one pair row through
// the same controlGroup the FF8 weapon upgrade editor uses for its
// materials, instead of two rows far apart. The row is keyed by the item,
// pin included, like the flat rows it replaces.
const ITEM_COUNT_PAIRS={
  CharaInitParam:{match:/^item_(\d+)$/,count:number=>`itemNum_${number}`,
    singles:{equip_Arrow:"arrowNum",equip_Bolt:"boltNum",equip_SubArrow:"subArrowNum",equip_SubBolt:"subBoltNum"}},
  EquipMtrlSetParam:{match:/^materialId(\d+)$/,count:number=>`itemNum${number}`},
  ItemLotParam:{match:/^lotItemId(\d+)$/,count:number=>`lotItemNum${number}`}};
function pairCountKey(table,itemKey){
  const spec=ITEM_COUNT_PAIRS[table];
  if(!spec)return null;
  if(spec.singles&&spec.singles[itemKey])return spec.singles[itemKey];
  const found=spec.match?spec.match.exec(itemKey):null;
  return found?spec.count(found[1]):null;
}
function fieldSections(row){
  const groups=new Map();
  // A field that is itself a record link opens that record from its own row;
  // only links with no editable field on the page are listed separately.
  // Asset links serve through the field label below: a face would replace the
  // number input beside it, with its own choice button. A model pick
  // writes the binder's number back; an icon pick comes from the gallery.
  const links=new Map((row.recordLinks||[]).filter(entry=>entry.kind!=="asset").map(entry=>[entry.field,entry]));
  const dialogs=new Map((row.dialogLinks||[]).map(entry=>[entry.field,entry]));
  // Placement coordinates ride one row per vector: Position, then
  // Rotation in degrees, then Scale. Detection is by field, not by
  // tab, so any record carrying a coordinate triple renders the same way.
  // One help bubble serves the whole row: three copies of the same text,
  // one per axis, squeezed the numbers they describe.
  const byKey=new Map((row.fields||[]).map(field=>[field.key,field]));
  // An item/count pair renders as one row at the item's place; the count
  // field is consumed and skipped when its own turn comes.
  const pairedCounts=new Set();
  const pairFor=field=>{
    if(field.type!=="enum")return null;
    const countKey=pairCountKey(row.table,field.key);
    if(!countKey||pairedCounts.has(countKey))return null;
    const count=byKey.get(countKey);
    if(!count||count.type!=="number")return null;
    // Anything beyond a plain link plus a number stays two rows: a dialog
    // line, an asset face or a label link has no place in the pair.
    if(dialogs.has(field.key)||dialogs.has(countKey))return null;
    const exotic=key=>(row.recordLinks||[]).some(entry=>entry.field===key&&(entry.kind==="asset"||entry.kind==="npc"));
    if(exotic(field.key)||exotic(countKey))return null;
    return count;
  };
  const vectored=new Set();
  for(const [keys,label] of [[["posX","posY","posZ"],"Position"],[["rotX","rotY","rotZ"],"Rotation"],[["scaleX","scaleY","scaleZ"],"Scale"]]){
    if(!keys.every(key=>byKey.has(key)))continue;
    keys.forEach(key=>vectored.add(key));
    const entries=keys.map(key=>{
      const field=byKey.get(key);
      return {label:key.slice(-1),control:controlFor(row,field),title:field.label};
    });
    const group=groupFor(byKey.get(keys[0]),row.table);
    if(!groups.has(group))groups.set(group,[]);
    const vectorHelp=(byKey.get(keys[0]).description||"").trim();
    groups.get(group).push(detailField({label,control:LexeditorUI.multiNumberRow(entries,{columns:3,nowrap:true}),
      help:vectorHelp?infoHelp(vectorHelp):null}));
  }
  for(const field of row.fields){
    if(vectored.has(field.key))continue;
    if(pairedCounts.has(field.key))continue;
    const pairCount=pairFor(field);
    if(pairCount){
      pairedCounts.add(pairCount.key);
      const pairGroup=groupFor(field,row.table);if(!groups.has(pairGroup))groups.set(pairGroup,[]);
      let pairHelp=field.description.trim();
      if(!field.editable)pairHelp=field.protectedReason||"This property is preserved. Its choices or behavior are not sufficiently documented for editing.";
      if(pairHelp.replace(/[.\s]/g,"").toLowerCase()===field.label.replace(/[.\s]/g,"").toLowerCase())pairHelp="";
      // The count's own description says how many, which the pairing shows;
      // only a sentence saying more (materials' "-1 leaves the slot empty")
      // joins the row's bubble.
      const extra=pairCount.description.trim().split(/(?<=[.!?])\s+/).filter(sentence=>sentence&&!/how many|the amount|how much/i.test(sentence)).join(" ");
      if(extra)pairHelp=pairHelp?`${pairHelp} ${extra}`:extra;
      let pairControl=controlFor(row,field);
      const pairLink=field.editable&&links.get(field.key);
      if(pairLink){
        const face=pairControl.matches?.(".ds1-reference-face")?pairControl
          :pairControl.querySelector?.(".ds1-reference-face")??pairControl;
        pairControl=el("span",{class:"ds1-reference-field"},pairControl,referencePicker(row,field,face));
      }
      // A pair item is a record link by construction, never a label link,
      // so the label keeps the item's own name with no hoverable.
      groups.get(pairGroup).push(detailField({label:shownLabel(field),property:field.key,
        control:LexeditorUI.controlGroup([pairControl,controlFor(row,pairCount)],{className:"ds1-item-count-pair"}),
        icon:field.icon||null,help:pairHelp?infoHelp(pairHelp):null}));
      continue;
    }
    const group=groupFor(field,row.table);if(!groups.has(group))groups.set(group,[]);
    let help=field.description.trim();
    if(!field.editable)help=field.protectedReason||"This property is preserved. Its choices or behavior are not sufficiently documented for editing.";
    if(help.replace(/[.\s]/g,"").toLowerCase()===field.label.replace(/[.\s]/g,"").toLowerCase())help="";
    const link=field.editable&&links.get(field.key);
    const fieldAssetLink=(row.recordLinks||[]).find(entry=>entry.kind==="asset"&&entry.field===field.key)||null;
    let control=controlFor(row,field);
    // A Play-sound event's Sound keeps its number input and gains the
    // derived stream's face beside it, the way a message ID keeps its
    // number beside its dialog face.
    if(link&&link.kind==="sound")control=el("span",{class:"ds1-sound-row"},control,soundFace(row,field,link));
    if(link){
      const face=control.matches?.(".ds1-reference-face")?control
        :control.querySelector?.(".ds1-reference-face")??control;
      const picker=link.kind==="sound"?soundPicker(row,field,face,link):referencePicker(row,field,face);
      control=el("span",{class:"ds1-reference-field"},control,picker);
    }
    const dialog=dialogs.get(field.key);
    if(dialog){
      const input=control.querySelector?.("input")??control;
      control=el("span",{class:"ds1-dialog-row"},control,dialogFace(row,field,dialog));
      control=el("span",{class:"ds1-reference-field"},control,dialogPicker(row,field,dialog,input));
    }
    if(fieldAssetLink&&field.editable){
      const face=control.matches?.(".ds1-asset-face")?control
        :control.querySelector?.(".ds1-asset-face")??control;
      const assetChoice=assetChoiceButton(row,field,face,fieldAssetLink);
      if(assetChoice)control=el("span",{class:"ds1-reference-field"},control,assetChoice);
    }
    const shown=shownLabel(field);
    const textLink=row.table==="EquipParamProtector"?TEXT_LABEL_LINKS[field.key]:null;
    const npcLink=!textLink?(row.recordLinks||[]).find(entry=>entry.kind==="npc"&&entry.field===field.key&&entry.resolved):null;
    const label=textLink?hoverable({content:shown,targetType:"ds1-text",targetId:textLink,
      targetLabel:`${shown} in Text`,preview:()=>textLabelPreview(textLink),activate:()=>openTextLabel(textLink)})
      :npcLink?hoverable({content:shown,targetType:"ds1-npc",targetId:npcLink.id,
      targetLabel:`${npcLink.name} in ${NPC_TAB_LABELS[npcLink.tab]||"Enemies"}`,
      preview:()=>recordPreview(npcLink),activate:()=>openRecord(npcLink)}):shown;
    groups.get(group).push(detailField({label,property:field.key,control,icon:field.icon||null,
      // A face carries no input to sniff, so linked rows name their lock
      // state outright; inputs keep the sniffed state they already have.
      ...((link||fieldAssetLink)?{readOnly:state.readOnly||!field.editable}:{}),
      // A flag is stored as a u8 bit but edited as a boolean; naming the
      // storage type here kept the checkbox out of the boolean field layout.
      help:help?infoHelp(help,field.editable&&field.helpKey?{helpKey:field.helpKey}:{}):null,dataType:field.type==="bool"?"BOOL":field.dtype.toUpperCase(),...(fieldAssetLink?{}:{min:field.minimum,max:field.maximum})}));
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
async function attackPreview(id,table="AtkParam_Npc"){
  const cacheKey=`${table}:${id}`;
  if(!attackPreviews.has(cacheKey))attackPreviews.set(cacheKey,api(`/api/row?table=${table}&id=${id}`).then(result=>result.row,
    error=>{attackPreviews.delete(cacheKey);throw error;}));
  const row=await attackPreviews.get(cacheKey);
  const users=row.impact?row.impact.variants.length:0;
  // The shared label-and-value rows, read-only: a preview is a small panel.
  return LexeditorUI.stack({fill:false,compact:true},el("strong",{},row.name),
    ...row.fields.map(field=>detailField({label:field.label,control:readonlyField(
      field.type==="enum"?(field.enum[String(field.value)]||`Unknown (${field.value})`):LexeditorUI.formatNumber(field.value))})),
    ...(row.impact?[LexeditorUI.detailText(users===1?"Used by 1 NPC variant.":`Shared by ${users} NPC variants.`)]
      :[LexeditorUI.detailText("A player attack: its damage is a motion value, a percentage of the weapon's attack rating.")]));
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
  if(!row)return "";
  if(row.table==="NpcParam"){
    const chr=row.values?.chr;
    if(!chr)return "";
    return window.Ds1Preview.thumbnail({url:`/api/chr/geometry?chr=${encodeURIComponent(chr)}`,label:`${row.name} model`});
  }
  if(row.table==="NativeRules"&&ds1LabelKinds.has(row.labelKind)){
    const art=el("img",{class:"lex-ds1-shop-icon",loading:"lazy",
      src:`/api/label?name=${encodeURIComponent(row.labelKind)}`,
      alt:"",draggable:"false","data-lex-no-image":"off"});
    art.addEventListener("error",()=>{if(art.isConnected)art.remove();},{once:true});
    return art;
  }
  if(!ds1IconTables.has(row.table))return "";
  const id=Number(row.id);
  if(!Number.isInteger(id))return "";
  const picture=el("img",{class:"lex-ds1-shop-icon",loading:"lazy",
    src:`/api/icon?table=${encodeURIComponent(row.table)}&id=${id}`,
    alt:"",draggable:"false","data-lex-no-image":"off"});
  picture.addEventListener("error",()=>{if(picture.isConnected)picture.remove();},{once:true});
  return picture;
}
function textureIconCell(row){
  if(!row||(row.table!=="Asset"&&row.table!=="AssetTexture"))return "";
  if(row.values&&row.values.kind==="archive")return "";
  const picture=el("img",{class:"lex-ds1-shop-icon",loading:"lazy",
    src:`/api/assets/preview?file=${encodeURIComponent(row.file||row.id)}&member=${encodeURIComponent(row.member||"")}&index=${row.index||0}`,
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
  // The tab is the header: the bare table owns the tab, and the opened
  // line docks under it, with no repeated section title.
  return [columnList({rows,key:row=>row.key,
    columns:[{key:"icon",label:"",width:"36px"},{key:"name",label:"Item",grow:1,align:"start"},
      {key:"price",label:"Price",numeric:true},{key:"stock",label:"Stock",numeric:true}]}),full];
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
  if(!data.rows.length)return [head,
    LexeditorUI.detailNote(`Behavior set ${data.variation} holds no behaviors. This enemy cannot act.`)];
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
      preview:()=>move.target.kind==="attack"?attackPreview(move.target.id,move.target.table):recordPreview({kind:move.target.kind,table:move.target.table,id:move.target.id}),
      activate:()=>move.target.kind==="attack"?openAttack(move.target.id,move.target.table):openEffect({id:move.target.id})})
      :move.target.detail}));
  // The tab is the header: the bare controls own the tab, the table
  // takes the middle and the pager pins at its foot, with no repeated
  // section title.
  return [head,
    LexeditorUI.bottomSearch({key:"monster-behaviors",value:state.behaviorQuery,label:"Search behaviors",
      change:value=>{state.behaviorQuery=value;state.behaviorPage=0;render();}}),
    columnList({rows,key:row=>row.key,
      columns:[{key:"behavior",label:"Behavior",grow:1},{key:"calls",label:"Calls",grow:1}]}),
    LexeditorUI.pager({inline:true,stacked:true,pages,page:state.behaviorPage,total:here.length,pageSize:size,
      change:value=>{state.behaviorPage=value;render();}})]
}
function monsterAttacksSection(){
  const links=state.monsterAttacks;
  if(!links)return LexeditorUI.loadingPanel({label:"Loading attacks"});
  if(!links.rows.length)return LexeditorUI.detailNote("No attack link was resolved for this monster. The Attacks tab lists every attack record.");
  const rows=links.rows.map(attack=>({key:`${attack.table}:${attack.id}`,
    name:hoverable({content:attack.name,targetType:"ds1-attack",targetId:attack.id,
      targetLabel:`${attack.name} in Attacks`,preview:()=>attackPreview(attack.id,attack.table),activate:()=>openAttack(attack.id,attack.table)}),
    route:attack.route}));
  // The tab is the header, so the bare table owns the tab below it with
  // no repeated section title (framework.css fills a bare table tab).
  return columnList({rows,key:row=>row.key,
    columns:[{key:"name",label:"Attack",grow:1},{key:"route",label:"Route"}]});
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
    help:title==="Blocking"?"How much damage and buildup this monster blocks while it guards.":null}));
  const accept=tabs.map(tab=>tab.id);
  const shape=applyFieldTabOverrides(groups,tabs,{accept,callerShape:`${state.row.table}:${state.sub}`});
  tabs.push({id:"attacks",label:"Attacks",bespoke:true,help:attackHelp});
  if(effects)tabs.push({id:"effects",label:"Effects",empty:!effects.length,help:"Effects this monster carries. Changing a shared effect changes every use of it."});
  if(state.row.table==="NpcParam"&&state.npcShop&&state.npcShop.rows.length)tabs.push({id:"shop",label:"Shop",bespoke:true,help:"Everything this merchant sells, in shop order. Price and stock edit here; the item name opens the rest of the line below it. -1 stock means unlimited."});
  tabs.push({id:"ai",label:"AI",bespoke:true,help:"The think record driving this enemy: senses, distances and goals. Swap it with the finder; think records are edited in the AI tab."});
  tabs.push({id:"behaviors",label:"Behaviors",bespoke:true,help:"The behavior set this enemy uses. Every behavior in the set is one move it can choose; each move calls one attack, projectile or effect."});
  // Model viewing lives in the header magnifier's drawer, for every NPC
  // with a model or attacks; there is no Model tab.
  const active=tabs.some(tab=>tab.id===state.monsterTab)?state.monsterTab:tabs[0].id;
  // Content builds for the tab the panel resolves, not the remembered one:
  // overrides may have drained the remembered tab (or the record under it
  // changed), and the panel falls back to the first live tab.
  const content=resolved=>resolved==="attacks"?monsterAttacksSection()
    :resolved==="effects"?effects
    :resolved==="shop"?npcShopSection()
    :resolved==="ai"?monsterThinkSection()
    :resolved==="behaviors"?monsterBehaviorsSection()
    :groups.get(tabs.find(tab=>tab.id===resolved)?.label);
  return tabbedPanel({label:"Monster details",active,tabs,paginate:{unpaged:true},fieldTabs:{shape,accept,members:Object.fromEntries([...groups].map(([title,fields])=>[tabId(title),(Array.isArray(fields)?fields:[]).map(field=>field?.dataset?.lexLayoutField).filter(Boolean)]))},
    change:id=>{state.monsterTab=id;render();},content});
}
// Guard items read their Defense tab's guard block under three headers:
// the guard's own settings, the damage it absorbs, the statuses it
// resists. Ammo and shields share the weapon table; other weapons keep
// the one flat list. A field the table gains later lands in Properties
// with the other settings.
const GUARD_DEFENSE_HEADERS=[
  ["Properties",["guardAngle","staminaGuardDef","guardmotionCategory","defenseBaseParry","guardBaseRepel","guardCutCancelRate","guardLevel","enableGuard"]],
  ["Defenses",["physGuardCutRate","magGuardCutRate","fireGuardCutRate","thunGuardCutRate","slashGuardCutRate","blowGuardCutRate","thrustGuardCutRate"]],
  ["Resistances",["poisonGuardResist","diseaseGuardResist","bloodGuardResist","curseGuardResist"]]];
function guardDefenseSections(fields){
  const buckets=GUARD_DEFENSE_HEADERS.map(([title])=>[title,[]]);
  for(const field of fields){
    const at=GUARD_DEFENSE_HEADERS.findIndex(([,keys])=>keys.includes(field.dataset?.lexLayoutField));
    buckets[at<0?0:at][1].push(field);
  }
  return buckets.filter(([,body])=>body.length).map(([title,body])=>detailSection({title,body}));
}
function itemDetail(groups){
  // Basics folds into Properties: one tab, the Basics fields first.
  // Enemies keep their own Basics tab (monsterDetail never merges).
  if(groups.has("Basics")){
    const basics=groups.get("Basics");groups.delete("Basics");
    groups.set("Properties",[...basics,...(groups.get("Properties")||[])]);
  }
  // Every section is a tab; the tab is the header, so a section tab
  // shows its fields with no repeated section title.
  const tabId=title=>title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"");
  const tabs=[...groups].map(([title])=>({id:tabId(title),label:title}));
  const active=tabs.some(tab=>tab.id===state.itemTab)?state.itemTab:tabs[0].id;
  const accept=tabs.map(tab=>tab.id);
  const shape=applyFieldTabOverrides(groups,tabs,{accept,callerShape:`${state.row.table}:${state.sub}`});
  // Content builds for the tab the panel resolves, not the remembered one:
  // overrides may have drained the remembered tab (or the record under it
  // changed), and the panel falls back to the first live tab.
  const content=(resolved,selected)=>{const body=groups.get(selected?.label);
    return selected?.label==="Defense"&&state.row&&["ammo","shields"].includes(catalogSub(state.row.table,state.row))
      ?guardDefenseSections(body):body;};
  return tabbedPanel({label:"Item details",active,tabs,paginate:{unpaged:true},fieldTabs:{shape,accept,members:Object.fromEntries([...groups].map(([title,fields])=>[tabId(title),(Array.isArray(fields)?fields:[]).map(field=>field?.dataset?.lexLayoutField).filter(Boolean)]))},
    change:id=>{state.itemTab=id;render();},content});
}
function effectDetail(groups){
  // Every section is a tab; the tab is the header, so a section tab
  // shows its fields with no repeated section title.
  const tabId=title=>title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"");
  const tabs=[...groups].map(([title])=>({id:tabId(title),label:title}));
  const active=tabs.some(tab=>tab.id===state.effectTab)?state.effectTab:tabs[0].id;
  const accept=tabs.map(tab=>tab.id);
  const shape=applyFieldTabOverrides(groups,tabs,{accept,callerShape:`${state.row.table}:${state.sub}`});
  // Content builds for the tab the panel resolves, not the remembered one:
  // overrides may have drained the remembered tab (or the record under it
  // changed), and the panel falls back to the first live tab.
  return tabbedPanel({label:"Effect details",active,tabs,paginate:{unpaged:true},fieldTabs:{shape,accept,members:Object.fromEntries([...groups].map(([title,fields])=>[tabId(title),(Array.isArray(fields)?fields:[]).map(field=>field?.dataset?.lexLayoutField).filter(Boolean)]))},
    change:id=>{state.effectTab=id;render();},content:(resolved,selected)=>groups.get(selected?.label)});
}
function attackDetail(groups,impact){
  // The parameter sections share one Properties tab; Usages lists every
  // owner, behavior and projectile that reaches the attack. Groups are
  // sections, never tabs, so section dragging keeps working inside.
  const tabs=[{id:"properties",label:"Properties"},{id:"usages",label:"Usages",bespoke:true,
    help:`${impact.variants.length} owners across ${impact.behaviors.length} behaviors`+
      (impact.bulletReferences.length?` and ${impact.bulletReferences.length} projectiles`:"")+
      `. Parameter links do not prove an animation invokes the attack.`}];
  const active=tabs.some(tab=>tab.id===state.attackTab)?state.attackTab:tabs[0].id;
  const accept=["properties"];
  const shape=applyFieldTabOverrides(groups,tabs,{accept,callerShape:`${state.row.table}:${state.sub}`});
  const content=resolved=>resolved==="usages"?attackUsagesSection(impact)
    :[...groups].map(([title,body])=>detailSection({title,body}));
  return tabbedPanel({label:"Attack details",active,tabs,paginate:{unpaged:true},fieldTabs:{shape,accept,members:{properties:[...groups].flatMap(([,fields])=>(Array.isArray(fields)?fields:[]).map(field=>field?.dataset?.lexLayoutField).filter(Boolean))}},
    change:id=>{state.attackTab=id;render();},content});
}
function attackUsagesSection(impact){
  const sections=[];
  const owners=impact.variants||[];
  if(owners.length){
    const rows=owners.map(entry=>{
      const admitted=entry.tab&&entry.sub;
      const name=admitted?hoverable({content:entry.name,targetType:"ds1-npc",targetId:entry.id,
        targetLabel:`${entry.name} in ${NPC_TAB_LABELS[entry.tab]||"Enemies"}`,
        preview:()=>recordPreview({kind:"npc",table:"NpcParam",id:entry.id}),
        activate:()=>openRecord({kind:"npc",tab:entry.tab,sub:entry.sub,table:"NpcParam",id:entry.id})}):entry.name;
      return {key:`NpcParam:${entry.id}`,
        owner:admitted?el("span",{style:"display:flex;gap:8px;align-items:center;justify-content:space-between;"},name,
          el("button",{type:"button",onclick:()=>openAttackViewer(entry,state.row.id).catch(notify)},"Open viewer")):name};
    });
    sections.push(detailSection({title:"Enemies & NPCs",body:[columnList({rows,key:row=>row.key,
      columns:[{key:"owner",label:"Owner",grow:1}]})]}));
  }
  const behaviors=impact.behaviors||[];
  if(behaviors.length){
    const rows=behaviors.map(move=>({key:`BehaviorParam:${move.id}`,
      behavior:hoverable({content:move.name,targetType:"ds1-behavior",targetId:move.id,
        targetLabel:`${move.name} in AI`,preview:()=>recordPreview({kind:"behavior",table:"BehaviorParam",id:move.id}),
        activate:()=>openRecord({kind:"behavior",table:"BehaviorParam",id:move.id})})}));
    sections.push(detailSection({title:"Behaviors",body:[columnList({rows,key:row=>row.key,
      columns:[{key:"behavior",label:"Behavior",grow:1}]})]}));
  }
  const bullets=impact.bulletReferences||[];
  if(bullets.length){
    const rows=bullets.map(proj=>({key:`Bullet:${proj.id}`,
      projectile:hoverable({content:proj.name,targetType:"ds1-bullet",targetId:proj.id,
        targetLabel:`${proj.name} in Attacks`,preview:()=>recordPreview({kind:"bullet",table:"Bullet",id:proj.id}),
        activate:()=>openRecord({kind:"bullet",table:"Bullet",id:proj.id})})}));
    sections.push(detailSection({title:"Projectiles",body:[columnList({rows,key:row=>row.key,
      columns:[{key:"projectile",label:"Projectile",grow:1}]})]}));
  }
  if((impact.paths||[]).length)
    sections.push(detailSection({title:"Reference paths",body:[logView(impact.paths.join("\n"))]}));
  if(!sections.length)return LexeditorUI.detailNote("No enemy, NPC, behavior or projectile links reach this attack.");
  return sections;
}
function lightDetail(row,groups){
  // Coordinates first like placements; the Light section below names
  // what shines there, then the look it wears.
  const vectors=groups.get("Position")||[];
  const identity=[
    detailField({label:"Kind",control:readonlyField(row.kind,{format:false})}),
    detailField({label:"Point",control:readonlyField(row.point,{format:false}),
      help:infoHelp("The shared spot this light shines from. Effects standing on it move along.")}),
    detailField({label:"Part",control:readonlyField(row.part,{format:false}),
      help:infoHelp("The object this light hangs from, usually its torch.")}),
    detailField({label:"Area part",control:readonlyField(row.areaPart,{format:false}),
      help:infoHelp("The map piece this light belongs to.")})];
  return [...vectors,detailSection({title:"Light",body:[...identity,...(groups.get("Light")||[])]})];
}
function msbDetail(row,groups){
  if(row.kind==="Light")return lightDetail(row,groups);
  if(row.kind==="Message")return messageDetail(row,groups);
  // Coordinates first, with no header above them: the placement's own
  // position, rotation and scale are the instance, and the Placement
  // group below names what stands there.
  const vectors=["Position","Rotation","Scale"].flatMap(title=>groups.get(title)||[]);
  const identity=[
    // (no Name row: the heading owns the name, like every other record)
    detailField({label:"Kind",control:readonlyField(row.kind,{format:false})}),
    detailField({label:"Part",control:readonlyField(row.id,{format:false})}),
    ...(row.model&&row.kind!=="Region"?[detailField({label:"Model",control:readonlyField(row.model,{format:false})})]:[])];
  if(row.think!==null&&row.think!==undefined)identity.push(
    detailField({label:"AI table",control:readonlyField(row.think,{format:false}),
      help:infoHelp("Which AI table drives this enemy.")}));
  const ordered=new Map([["Placement",[...identity,...(groups.get("Placement")||[])]]]);
  for(const [title,body] of groups)if(title!=="Placement"&&title!=="Position"&&title!=="Rotation"&&title!=="Scale")ordered.set(title,body);
  return [...vectors,...[...ordered].map(([title,body])=>detailSection({title,body}))];
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
const formatSoundLength=seconds=>`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,"0")}`;
// One stream's bytes, fetched once: the heading player rebuilds on
// every render, and the stream route serves no-store bytes, so a
// server URL re-downloaded and server-side re-extracted the whole
// stream on every render (open, every search keystroke, every
// selection), serializing the app behind extracts. The first render
// keeps the eager server URL for its play button; the landed bytes
// swap it for a blob URL all later renders reuse. Single entry:
// streams run to tens of megabytes, so only the current one is kept.
const soundAudioCache={id:null,url:null,loading:null,failed:null};
const soundStreamUrl=row=>`/api/sound/stream?file=${encodeURIComponent(row.bank||"")}&stream=${encodeURIComponent(row.name||"")}`;
function soundAudioSrc(row){
  const id=key(row);
  if(soundAudioCache.id!==id){
    if(soundAudioCache.url)URL.revokeObjectURL(soundAudioCache.url);
    soundAudioCache.id=id;soundAudioCache.url=null;soundAudioCache.loading=null;soundAudioCache.failed=null;
  }
  if(!soundAudioCache.url&&!soundAudioCache.loading&&!soundAudioCache.failed&&row.bank&&row.name){
    const wanted=id,url=soundStreamUrl(row);
    soundAudioCache.loading=fetch(url).then(response=>{
      if(!response.ok)throw new Error(`Could not load ${row.name}.`);
      return response.blob();
    }).then(blob=>{
      if(soundAudioCache.id!==wanted)return;
      soundAudioCache.url=URL.createObjectURL(blob);
      soundAudioCache.loading=null;render();
    }).catch(()=>{if(soundAudioCache.id===wanted){soundAudioCache.loading=null;soundAudioCache.failed=wanted;}});
  }
  return soundAudioCache.url||soundStreamUrl(row);
}
function renderSoundDetail(row){
  const bank=row.bank||"",stream=row.name||"";
  const body=[
    detailSection({title:"SOUND",body:[
      detailField({label:"BANK",property:"bank",control:readonlyField(bank)}),
      detailField({label:"LENGTH",property:"length",control:readonlyField(formatSoundLength(row.duration||0))}),
      detailField({label:"SIZE",property:"size",control:readonlyField(formatAssetSize(row.size||0))})]}),
    detailSection({title:"ACTIONS",body:[detailField({label:"",control:actionRow(...soundBankActions(row))})]})];
  return detailPanel({title:row.name,meta:formatSoundLength(row.duration||0),
    help:"The bank file holds this stream. Replacing the bank replaces every stream inside it.",
    audio:{src:soundAudioSrc(row),label:stream},
    paginate:{unpaged:true},body});
}
function soundBankActions(row){
  const bank=row.bank||"";
  const locked=state.readOnly||state.assetBusy;
  const replace=el("button",{type:"button",disabled:locked,
    title:state.readOnly?"This is the game's own data, shown read-only. Create a mod to replace sounds.":state.assetBusy?"An upload is already running.":"Replace this stream's bank file",
    onclick:()=>replaceSoundBank(bank)},"Replace bank\u2026");
  if(!row.overridden)return[replace];
  const remove=el("button",{type:"button",disabled:locked,
    title:state.readOnly?"This is the game's own data, shown read-only.":state.assetBusy?"An upload is already running.":"Drop the mod's copy of this bank",
    onclick:()=>removeSoundBankOverride(bank)},"Remove override");
  return[replace,remove];
}
let soundBankTarget=null;
function replaceSoundBank(bank){
  if(state.assetBusy||state.readOnly||!bank)return;
  soundBankTarget=bank;assetFilePicker().click();
}
async function removeSoundBankOverride(bank){
  if(state.assetBusy||!bank)return;
  if(!await confirmAction({title:"Remove this override?",message:"The mod stops carrying this bank, and the installed game bank plays again.",confirmLabel:"Remove",cancelLabel:"Cancel"}))return;
  state.assetBusy=true;render();
  try{await api("/api/assets/remove",{relative:bank});await loadItems();}
  catch(error){notify(error);}
  finally{state.assetBusy=false;render();}
}
function renderAssetDetail(){
  const row=state.rows.find(row=>key(row)===state.selected);
  if(!row)return detailPanel({title:"File",actions:[assetUploadButton()],body:[LexeditorUI.detailNote("Select a file.")]});
  if(!state.row||key(state.row)!==state.selected||!state.assetDetail)
    return detailPanel({title:row.name,actions:[assetUploadButton()],body:[LexeditorUI.loadingPanel({label:"Loading file"})]});
  const info=state.assetDetail;
  const fromMod=info.source==="mod";
  const busy=state.assetBusy;
  const locked=state.readOnly||busy;
  const progress=state.assetUpload?`Uploading ${formatAssetSize(state.assetUpload.received)} of ${formatAssetSize(state.assetUpload.total)}`:"";
  const previewUrl=texture=>`/api/assets/preview?side=${info.source}&file=${encodeURIComponent(row.file||row.id)}&member=${encodeURIComponent(texture.member||"")}&index=${texture.index}`;
  const textureHelp=texture=>infoHelp(`${texture.width} by ${texture.height}, ${texture.format}. Preview of the ${fromMod?"mod":"installed game"} file, shrunk to fit.`);
  // Vanilla-vs-mod already shows in the list (tinted names, pen nibs), so
  // the panel carries no SOURCE row; files join the mod through + in the
  // detail header, never a Replace action.
  const body=[];
  let icon=null,preview=null,help="",audio=null;
  if(state.tab==="models")({icon,preview,help}=assetModelPanel(row,info,body,previewUrl,textureHelp));
  else if(state.tab==="textures")({icon,preview,help}=assetTexturePanel(row,row.table==="AssetTexture"?{...info,textures:singleTexture(info,row)}:info,body,previewUrl,textureHelp));
  else{
    help="Add this file to the mod with + in the header. The game loads the mod's copy once applied. Remove drops the mod's copy.";
    body.push(detailSection({title:"PREVIEW",body:[soundPreview({note:"No preview",
      help:infoHelp("Files play in the game. They have no picture to show.")})]}));
  }
  const actions=[
    fromMod?el("button",{type:"button","data-asset-action":"remove",disabled:locked,onclick:()=>removeAssetOverride(row.file||row.id)},"Remove override"):null,
    progress?el("span",{role:"status"},progress):null].filter(Boolean);
  if(actions.length)body.push(detailSection({title:"ACTIONS",body:[detailField({label:"",control:actionRow(...actions)})]}));
  return detailPanel({title:row.name,actions:[assetUploadButton()],meta:formatAssetSize(info.size),icon,help,modelPreview:preview,paginate:{unpaged:true},audio,body,
    ...(state.tab==="textures"?{previewPin:{key:"icon",label:"Icon"}}:{})});
}
async function uploadAsset(target,file,refresh){
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
    if(refresh){await refresh();return;}
    if(files){state.assetFiles=files;state.rows=assetRows(files);if(state.tab==="textures")state.rows=await expandTextureRows(state.rows);}
    state.selected=`Asset:${target}`;remapTextureSelection();
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
    state.assetFiles=result.files;state.rows=assetRows(result.files);if(state.tab==="textures")state.rows=await expandTextureRows(state.rows);
    state.selected=`Asset:${target}`;remapTextureSelection();state.row=null;state.assetDetail=null;
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
  collision:["Collision data","Collision surfaces control where characters can walk and where death zones apply. Show their high and low meshes in Maps."],
  "no-mesh":["No model mesh","This file holds no model mesh to preview. It still replaces as a whole file."],
  unreadable:["Unreadable model","This file does not open as a model. It still replaces as a whole file."]};
// One shared thumbnail strip for the Models and Textures tabs: the
// file's textures as squares in a wrapping row, each named under its
// picture, instead of a vertical stack of label-plus-image rows.
function assetPreviewStrip(textures,previewUrl,textureHelp){
  // Tiles below 64 pixels upscale crisp, and a texture painted one
  // flat color carries no picture at all: c0000's only texture is
  // blank white, and a bare white tile reads as broken, so the tile
  // keeps its name with a blank note and no image. Pictures stay
  // hidden until the verdict; anything odd reveals its plain tile.
  const markTiny=image=>{if(image.naturalWidth<64||image.naturalHeight<64)image.classList.add("ds1-texture-tiny");};
  const markBlank=(image,tile,name)=>{
    const reveal=()=>{image.style.visibility="visible";};
    if(!image.naturalWidth){image.remove();return;}
    try{
      const sample=document.createElement("canvas");
      sample.width=image.naturalWidth;sample.height=image.naturalHeight;
      const ctx=sample.getContext("2d",{willReadFrequently:true});
      if(!ctx){reveal();return;}
      ctx.drawImage(image,0,0);
      const pixels=ctx.getImageData(0,0,sample.width,sample.height).data;
      // Every pixel votes, alpha included: sampling one pixel in
      // sixteen called a white texture with one red pixel blank.
      const red=pixels[0],green=pixels[1],blue=pixels[2],alpha=pixels[3];

      for(let at=4;at<pixels.length;at+=4){
        if(pixels[at]!==red||pixels[at+1]!==green||pixels[at+2]!==blue||pixels[at+3]!==alpha){reveal();return;}
      }
      tile.classList.add("ds1-texture-blank");
      name.textContent=`${name.textContent} \u00b7 blank`;
      image.remove();
    }catch(_error){reveal();}
  };
  return el("div",{class:"ds1-texture-strip",role:"list"},
    ...textures.map(texture=>{
      const name=el("span",{class:"ds1-texture-name",title:texture.name},texture.name);
      const tile=el("figure",{class:"ds1-texture-tile",role:"listitem"},
        el("img",{src:texture.png||previewUrl(texture),alt:texture.name,class:"lex-asset-thumbnail",loading:"lazy",
          style:"visibility:hidden;",onload:event=>{markTiny(event.target);markBlank(event.target,tile,name);}}),
        el("div",{class:"ds1-texture-caption"},name,
          el("span",{class:"ds1-texture-help"},textureHelp(texture))));
      return tile;
    }));
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
    help:"Add this file to the mod with + in the header. The game loads the mod's copy once applied. The magnifier opens the 3D model. Remove drops the mod's copy."};
}
// One texture row previews its own texture only; a stale index (the
// container changed under it) falls back to the whole file.
function singleTexture(info,row){
  const match=(info.textures||[]).filter(entry=>entry.index===row.index&&(entry.member||"")===(row.member||""));
  return match.length?match:info.textures||[];
}
function assetTexturePanel(row,info,body,previewUrl,textureHelp){
  const textures=info.textures||[];
  if(textures.length){
    body.push(detailSection({title:"PREVIEW",body:[assetPreviewStrip(textures,previewUrl,textureHelp)]}));
    const first=textures[0];
    if(row.table==="AssetTexture")body.push(
      detailField({label:"FILE",control:readonlyField(row.file,{format:false}),
        help:infoHelp("The container this texture ships in. Add and Remove replace the whole file.")}));
    return {icon:LexeditorUI.iconSlot({content:el("img",{src:previewUrl(first),alt:row.name,loading:"lazy"})}),
      preview:{label:`${row.name} textures`,
        openLabel:`View ${row.name} textures`,closeLabel:`Close ${row.name} textures`,
        content:()=>el("div",{class:"ds1-texture-drawer"},LexeditorUI.stack(...textures.map(texture=>detailField({label:texture.name,
          control:el("img",{src:previewUrl(texture),alt:texture.name,style:"max-width:100%;height:auto"}),
          help:textureHelp(texture)})))),
        onClose:drawer=>drawer.replaceChildren()},
      help:"Add this file to the mod with + in the header. The game loads the mod's copy once applied. The magnifier shows every texture full-size. Remove drops the mod's copy."};
  }
  // The archive kind is file metadata, not a preview: it sits loose in
  // the panel instead of under PREVIEW, pinnable through the row's kind.
  if(info.reason==="split-archive"){
    const file=String(row.file||row.id||"");
    const header=file.replace(/\.tpfbdt(\.dcx)?$/i,".tpfbhd$1");
    const splitHelp=header!==file
      ?`The data half of ${header}. Its textures list under that header file; this half replaces as a whole file.`
      :"Many textures packed into one whole-file archive. It replaces as a whole file and has no per-texture preview; single .tpf and .dds files do.";
    body.push(detailField({label:"ARCHIVE",property:"kind",control:readonlyField("Split archive"),
      help:infoHelp(splitHelp)}));
  }
  else if(info.reason==="unreadable")body.push(detailSection({title:"PREVIEW",body:[
    detailField({label:"TEXTURES",control:readonlyField("No preview"),
      help:infoHelp("This file does not open as textures. It still replaces as a whole file.")})]}));
  else body.push(detailSection({title:"PREVIEW",body:[
    detailField({label:"TEXTURES",control:readonlyField("No preview"),
      help:infoHelp("Only TPF containers and DDS files preview.")})]}));
  return {icon:LexeditorUI.iconSlot({content:LexeditorUI.noThumbnail("ds1")}),preview:null,
    help:"Add this file to the mod with + in the header. The game loads the mod's copy once applied. Remove drops the mod's copy."};
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
      if(!file){soundBankTarget=null;return;}
      if(soundBankTarget){const bank=soundBankTarget;soundBankTarget=null;void uploadAsset(bank,file,async()=>{await loadItems();render();});return;}
      const target=state.rows.find(row=>key(row)===state.selected);
      if(target)void uploadAsset(target.file||target.id,file);};
    document.body.append(assetPicker);
  }
  return assetPicker;
}
function assetAddUpload(){
  if(state.assetBusy||state.readOnly)return;
  soundBankTarget=null;
  const target=state.rows.find(row=>key(row)===state.selected);
  if(!target){LexeditorUI.showToast("Select a file in the list to add it to the mod.");return;}
  assetFilePicker().click();
}
function assetUploadButton(){
  const locked=state.readOnly||state.assetBusy;
  const title=state.readOnly?"This is the game's own data, shown read-only. Create a mod to add files to it.":state.assetBusy?"An upload is already running.":"Add file to mod";
  return el("button",{type:"button",class:"lex-header-icon","data-asset-action":"add",title,"aria-label":title,disabled:locked,
    onclick:()=>assetAddUpload()},LexeditorUI.addIcon());
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
  const here=state.mapId?`&map=${encodeURIComponent(state.mapId)}`:"";
  const found=await api(`/api/world/locate?table=ItemLotParam&id=${lotId}${here}`).catch(notify);
  if(!found)return;
  // A lot no placed enemy drops has nowhere to fly to: a short toast,
  // not a modal, since there is nothing for the reader to act on.
  if(!found.map){LexeditorUI.showToast("No placed enemy drops this lot.");return;}
  await goToPlacement(found.map,`${found.map}:${found.key}`);
}
function mapsNoun(){
  const table=state.row?.table||"";
  if(table==="ItemLotParam")return "Drop";
  if(table.endsWith(".msb")&&String(state.row?.id||"").startsWith("light:"))return "Light";
  if(table.endsWith(".msb")&&String(state.row?.id||"").startsWith("message:"))return "Message";
  if(table==="ShopLineupParam")return "Shop entry";
  if(table==="ObjActParam")return "Treasure";
  return "Placement";
}
function addSkillButton(){
  return el("button",{type:"button",class:"lex-header-icon","aria-label":"Add Ash of War",title:"Add Ash of War",disabled:state.rowBusy,onclick:()=>addSkill()},LexeditorUI.addIcon());
}
function emptySkillDetail(){
  return detailPanel({title:"Ashes of War",actions:[addSkillButton()],body:[LexeditorUI.detailNote(
    state.rows.length?"No matching Ashes of War. Change the search, or add a skill.":"No Ashes of War yet. Add a skill, then assign it from a weapon’s details.")]});
}
async function addSkill(){
  if(state.readOnly){await viewportRequestMod();return;}
  if(state.rowBusy)return;
  state.rowBusy=true;render();
  try{const result=await api("/api/rows/add",{table:"WeaponSkill",id:null});state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.query="";await loadItems();state.selected=key(result.row);const index=sortedRows().findIndex(row=>key(row)===state.selected);if(index>=0)state.page=Math.floor(index/state.pageSize);await loadDetail();}
  catch(error){notify(error);}
  finally{state.rowBusy=false;render();}
}
function rowActionButtons(kind){
  const locked=state.readOnly||state.rowBusy;
  const playerStart=kind==="placement"&&state.row.kind==="Player";
  const nouns=kind==="message"?["message","map"]:kind==="placement"?["placement","map"]:kind==="light"?["light","map"]:["record","table"];
  const light=kind==="light";
  const goTo=(kind==="placement"||kind==="message"||light)
    ?[el("button",{type:"button",class:"lex-header-icon","data-row-action":"goto","data-row-kind":kind,
      title:`Show this ${kind} in the map viewport`,"aria-label":`Show this ${kind} in the map viewport`,
      onclick:()=>light?goToLight(key(state.row)):kind==="message"?goToMessage(key(state.row)):goToPlacement(state.row.table,key(state.row))},targetIcon())]
    :kind==="record"&&state.tab==="maps"&&state.row.table==="ItemLotParam"
    ?[el("button",{type:"button",class:"lex-header-icon","data-row-action":"goto","data-row-kind":kind,
      title:"Show where this drops in the map viewport","aria-label":"Show where this drops in the map viewport",
      onclick:()=>goToDrop(state.row.id)},targetIcon())]
    :[];
  const duplicateTitle=state.readOnly?`Open a mod project to add ${nouns[0]}s`:`Copy this ${nouns[0]} under the next free ID`;
  const removeTitle=playerStart?"The player start cannot be removed":state.readOnly?`Open a mod project to remove ${nouns[0]}s`:`Remove this ${nouns[0]} from its ${nouns[1]}`;
  return [...(state.row?.table==="WeaponSkill"?[addSkillButton()]:[]),...goTo,el("button",{type:"button",class:"lex-header-icon","data-row-action":"duplicate","data-row-kind":kind,disabled:locked,
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
// Messages duplicate through the placements route like placements,
// but the fresh view must land before the detail reads it: message
// rows ride the view, not the record lists.
async function duplicateMessage(){
  if(state.rowBusy||!state.row)return;
  state.rowBusy=true;render();
  try{
    const result=await api("/api/placements/add",{map:state.row.table,id:state.row.id});
    state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
    await loadItems();
    state.selected=key(result.row);
    if(state.tab==="maps")await refreshMapsAfterStructure();
    await loadDetail();
  }
  catch(error){notify(error);}
  finally{state.rowBusy=false;render();}
}
async function removeMessage(){
  if(state.rowBusy||!state.row)return;
  if(!await confirmAction({title:"Remove this message?",
    message:"The message leaves the map. Its marker stays for anything else standing on it.",
    confirmLabel:"Remove",cancelLabel:"Cancel"}))return;
  state.rowBusy=true;render();
  try{
    const result=await api("/api/placements/remove",{map:state.row.table,id:state.row.id});
    state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
    await loadItems();
    if(state.tab==="maps")await refreshMapsAfterStructure();
    const next=(state.mapView?.messages||[])[0];
    state.selected=next?`${state.mapView.map}:${next.key}`:state.rows[0]?key(state.rows[0]):null;state.row=null;
    await loadDetail();
  }
  catch(error){notify(error);}
  finally{state.rowBusy=false;render();}
}
async function duplicateRow(kind){
  if(kind==="message")return duplicateMessage();
  if(state.rowBusy||!state.row)return;
  const placement=kind==="placement"||kind==="light";
  state.rowBusy=true;
  if(state.tab==="maps")refreshMapsDetail();else render();
  try{
    const result=placement?await api("/api/placements/add",{map:state.row.table,id:state.row.id})
      :await api("/api/rows/add",{table:state.row.table,id:state.row.id});
    state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
    await loadItems();
    state.selected=key(result.row);
    const index=sortedRows().findIndex(row=>key(row)===state.selected);
    if(index>=0)state.page=Math.floor(index/state.pageSize);
    if(placement&&state.tab==="maps")await refreshMapsAfterStructure();
    await loadDetail();
  }
  catch(error){notify(error);}
  finally{state.rowBusy=false;render();}
}
async function removeRow(kind){
  if(kind==="message")return removeMessage();
  if(state.rowBusy||!state.row)return;
  const placement=kind==="placement"||kind==="light";
  const impact=!placement&&state.tab==="attacks"&&state.row.impact
    ?` It is reached by ${state.row.impact.variants.length} NPC variants and ${state.row.impact.behaviors.length} behaviors.`:"";
  if(!await confirmAction({title:placement?"Remove this placement?":"Remove this record?",
    message:(placement?"The placement leaves the map. Its bytes stay in the file, unused."
      :"The record leaves its table. Anything that points at it will point at nothing.")+impact,
    confirmLabel:"Remove",cancelLabel:"Cancel"}))return;
  state.rowBusy=true;
  if(state.tab==="maps")refreshMapsDetail();else render();
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
// The graph's own axes, in player terms: what the horizontal value is (the
// stat or level the curve reads) and what the line measures. Anything not
// listed is a weapon or spell-tool curve: stat points in, scaling share out.
function curveAxes(row){
  const id=Number(row.id);
  if(id===100)return {x:"Vitality",y:"HP"};
  if(id===101)return {x:"Attunement",y:"MP"};
  if(id===102)return {x:"Soul level",y:"Defense"};
  if(id===110||id===111||id===112)return {x:"Soul level",y:"Resistance"};
  if(id===113)return {x:"Humanity",y:"Resistance"};
  if(id===150)return {x:"Kindling",y:"Estus"};
  return {x:"Stat",y:"Scaling",yUnit:"%"};
}
function curveDetail(actions,groups){
  const row=state.row;
  const at=key=>Number(row.fields.find(item=>item.key===key)?.value??0);
  const stages=[0,1,2,3,4].map(i=>at(`stageMaxVal${i}`));
  if(stages.every(value=>value===0))return costDetail(actions,row,groups);
  let graph=null;
  const live=key=>{
    const input=graph?.querySelector(`input[data-field-key="${key}"]`);
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
    return {label:short,key:short.toLowerCase(),control,help:field.description||""};
  });
  // Each span names its own variables, never lo/hi abstractions: T3 and
  // T4 are its threshold levels, V3 and V4 their values, S3 its shape
  // (the left stage's, like the game). The left side names the Y axis.
  const axes=curveAxes(row);
  const segments=[0,1,2,3].map(i=>({from:stages[i],to:stages[i+1],
    formula:LexeditorUI.mathFormula(
      `${axes.y}(x) = V${i+1} + (V${i+2} - V${i+1}) * ((x - T${i+1})/(T${i+2} - T${i+1}))^S${i+1}`,{variables})}));
  const ends=[0,1,2,3,4].map(i=>at(`stageMaxGrowVal${i}`));
  const floor=Math.min(0,...ends),ceil=Math.max(...ends);
  graph=curveEditor({title:row.name,overlayExtrema:true,variables,
    domain:{min:stages[0],max:stages[4]>stages[0]?stages[4]:stages[0]+1},
    range:{min:floor,max:ceil>floor?ceil:floor+1},
    xLabel:axes.x,yLabel:axes.y,yUnit:axes.yUnit,
    graphLabel:`${row.name} from ${stages[0]} to ${stages[4]}`,evaluate,segments});
  graph.dataset.curveRow=String(row.id);
  graph.curveEvaluate=evaluate;
  // A lone graph fills its tab: no wrapper and no section header around
  // the only content. Its guidance joins the panel help bubble instead.
  const graphHelp="The line passes through every stage point and bends between them with the left stage's shape. A shape of 1 draws straight, a higher shape starts slow, and a negative shape starts fast. Each span names its own variables, each in its variable's color. Hovering a variable in the drawer or the equation lights it in both. Edit every value from the variables drawer over the graph.";
  const panelHelp=typeof row.help==="string"&&row.help?`${row.help}\n\n${graphHelp}`:(row.help||graphHelp);
  return detailPanel({title:row.name,help:panelHelp,actions,paginate:{unpaged:true},body:[graph]});
}
function costDetail(actions,row,groups){
  void groups;
  const at=key=>Number(row.fields.find(item=>item.key===key)?.value??0);
  let graph=null;
  const live=key=>{
    const input=graph?.querySelector(`input[data-field-key="${key}"]`);
    const value=input?Number(input.value):NaN;
    return Number.isFinite(value)?value:at(key);
  };
  // The community cubic, accurate level 12 and up. Only its cubic
  // term is wired to the record: boundry_inclination_soul is 0.02 on
  // the vanilla row, exactly the published cubic coefficient, while
  // the other coefficients' sources are undocumented.
  const price=level=>Math.round(live("boundry_inclination_soul")*Math.pow(level,3)+3.06*Math.pow(level,2)+105.6*level-895);
  const names={init_inclination_soul:"C1",adjustment_value:"C2",boundry_inclination_soul:"C3",boundry_value:"C4"};
  const variables=row.fields.filter(field=>names[field.key]).map(field=>{
    const control=plainControlFor(row,field);
    if(control instanceof Element&&field.label)control.title=field.label;
    control.addEventListener?.("change",()=>{edits.then(()=>{graph?.refreshCurve?.();});});
    return {label:names[field.key],key:names[field.key].toLowerCase(),control,help:field.description||""};
  });
  const floor=Math.floor(price(12)),ceil=Math.ceil(price(99));
  graph=curveEditor({title:row.name,overlayExtrema:true,variables,
    domain:{min:12,max:99},range:{min:floor,max:ceil>floor?ceil:floor+1},
    xLabel:"Level",yLabel:"Souls",
    graphLabel:`${row.name} from level 12 to 99`,evaluate:price,
    formula:LexeditorUI.mathFormula("Souls(L) = C3*L^3 + 3.06*L^2 + 105.6*L - 895",{variables})});
  graph.dataset.curveRow=String(row.id);
  graph.curveEvaluate=price;
  const graphHelp="Souls per level from the community cubic, accurate level 12 and up. Only the cubic term (C3) reads the record. The other coefficients are fitted because their sources are undocumented. Edit every value from the variables drawer over the graph.";
  const panelHelp=typeof row.help==="string"&&row.help?`${row.help}\n\n${graphHelp}`:(row.help||graphHelp);
  return detailPanel({title:row.name,help:panelHelp,actions,paginate:{unpaged:true},body:[graph]});
}
function renderScriptDetail(){
  const info=state.scriptDetail;
  if(!info)return detailPanel({title:state.row?.name||"State",body:[LexeditorUI.detailNote("Select a state.")]});
  const commandLine=command=>`${command.bank}:${command.id}`+(command.args.length?`  ${command.args.join(", ")}`:"");
  const showList=list=>list.length?list.map(command=>`  ${commandLine(command)}`).join("\n"):"  (none)";
  const showCondition=(condition,depth)=>{
    const pad="  ".repeat(depth);
    const head=`${pad}if ${condition.evaluator}`+(condition.target===null||condition.target===undefined?"":` -> state ${condition.target}`);
    return [head,...condition.pass.map(command=>`${pad}  ${commandLine(command)}`),
      ...condition.sub.flatMap(entry=>showCondition(entry,depth+1))];
  };
  const commands=`entry:\n${showList(info.entry)}\nexit:\n${showList(info.exit)}\nwhile:\n${showList(info.while)}`;
  const conditions=info.conditions.length?info.conditions.flatMap(condition=>showCondition(condition,0)).join("\n"):"(no conditions)";
  return detailPanel({title:state.row.name,
    body:[detailSection({title:"COMMANDS",body:[logView(commands)]}),
      detailSection({title:"CONDITIONS",body:[logView(conditions)]})]});
}
function detail(){
  if(state.mapTab==='collision'&&state.tab==='maps')return collisionDetail();
  const impact=state.row?.impact;
  // A record's heading is its name, on every tab. An attack's sharing
  // lives in its help bubble, never under it.
  const noun=state.tab==="npcs"?(state.sub==="unowned-shops"?"Shop entry":"NPC"):state.tab==="drops"?"Drop":state.tab==="attacks"?(state.sub==="projectiles"?"Projectile":"Attack"):state.tab==="enemies"?(state.sub==="behaviors"?"Behavior":state.sub==="ai"?"AI record":"Monster"):state.tab==="maps"?mapsNoun():state.tab==="animations"?"Event":state.tab==="effects"?"Effect":state.tab==="misc"?(state.sub==="encumbrance"?"Load band":state.sub==="encumbrance-overrides"?"Override":"Stamina"):state.tab==="text"?"Label":state.tab==="scripts"?"State":state.tab==="stats"?(state.sub==="levelup"?"Defense":state.sub==="curves"?"Curve":state.sub==="upgrade-materials"?"Material set":state.sub==="starting-classes"?"Class":state.sub==="starting-gifts"?"Gift":"Upgrade"):state.tab==="sound"?"Sound":"Item";
  if(state.tab==="sound"&&state.row?.table==="SoundStream"){
    const soundRow=state.rows.find(row=>key(row)===state.selected);
    if(soundRow)return renderSoundDetail(soundRow);
  }
  if(ASSET_TABS.has(state.tab))return renderAssetDetail();
  if(state.tab==="scripts"&&state.row?.table==="ScriptState")return renderScriptDetail();
  if(!state.row){
    if(state.tab==="items"&&state.sub==="ashes-of-war")return emptySkillDetail();
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
  const meta=state.tab==="maps"&&state.row&&msbRowEarly?(state.row.kind==="Light"?`look ${state.row.preset}`:state.row.kind==="Message"?`message ${state.row.textId}`:`model ${state.row.model}`):state.tab==="animations"&&state.row?`${state.row.binder} · ${state.row.tae} · ${state.row.animName}`:"";
  // The enemy's AI table lives on the AI tab's Think record panel; the
  // field still rides row.fields for that panel, but the tab groups
  // below must not repeat it as a row of their own.
  const groups=fieldSections(state.row.table==="NpcParam"
    ?{...state.row,fields:(state.row.fields||[]).filter(field=>field.key!=="aiThinkId")}:state.row);
  // Hit fields read slot by slot with a status line each, like the
  // viewer, instead of the stored field-by-field order.
  if((state.row.table==="AtkParam_Npc"||state.row.table==="AtkParam_Pc")&&groups.has("Hitbox"))
    groups.set("Hitbox",hitboxGroupWithStatus(state.row,groups.get("Hitbox"),null));
  const eventRowEarly=state.tab==="animations"&&state.animScope.level==="events"&&String(state.row.id||"").startsWith("ev:");
  const paramRowEarly=!msbRowEarly&&!tableEarly.endsWith(".anibnd.dcx")&&state.row.table!=="NativeRules"&&state.row.table!=="Asset"&&state.row.table!=="MenuText";
  const rowActionsEarly=state.row.band?bandActions():eventRowEarly?taeActions():msbRowEarly?rowActionButtons(state.row.kind==="Light"?"light":state.row.kind==="Message"?"message":"placement"):paramRowEarly?rowActionButtons("record"):[];
  if(state.row.table==="NpcParam")return armDs1Preview(detailPanel({title:state.row.name,actions:rowActionsEarly,body:[monsterDetail(groups)]}),state.row.table,state.row.id);
  if(state.tab==="stats"&&state.sub==="curves"&&paramRowEarly)return curveDetail(rowActionsEarly,groups);
  let help=state.row.help;
  if(impact){
    const examples=impact.variants.slice(0,3).map(n=>n.name).join(", ");
    help=`Editing this record changes every use of it. Known parameter links reach ${impact.variants.length} NPC variants and ${impact.behaviors.length} behaviors.`+
      (examples?` Examples: ${examples}.`:" Ownership is unresolved.")+
      ` ${impact.bulletReferences.length} projectile records reference this attack ID; player and enemy contexts may differ.`+
      " Animation, script and effect calls are not fully traced, so this is a minimum impact estimate.";
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
    return armDs1Preview(detailPanel({title,meta,help,actions:rowActionsEarly,body:[effectDetail(groups)]}),state.row.table,state.row.id);  // Attacks with traced usages split into Properties and Usages;
  // player attacks and projectiles have no traced owners, so they
  // keep the flat sections.
  if(state.row.table==="AtkParam_Npc"&&impact)
    return armDs1Preview(detailPanel({title,meta,help,actions:rowActionsEarly,body:[attackDetail(groups,impact)]}),state.row.table,state.row.id);
  return armDs1Preview(detailPanel({title,meta,help,actions:rowActionsEarly,paginate:{unpaged:true},
    body:[...groups].map(([title,body])=>detailSection({title,body}))}),state.row.table,state.row.id);
}
const ds1PreviewAvailability=new Map();
// The open enemy viewer's refresh, when one is open: undo and redo
// repaint it instead of re-rendering the page out from under it.
let chrDrawerRefresh=null,chrFieldsSeq=0;
// An attack tab's viewer link: the enemy to open and the attack to
// show once its detail lands. Consumed by the preview settle below.
let pendingViewer=null,keepViewerPending=false;
// Label kinds with equipment-screen art (icons.py); anything else keeps the
// shared fallback glyph.
const ds1LabelKinds=new Set(["physical","magic","fire","lightning","critical",
  "physicalDef","magicDef","fireDef","lightningDef",
  "str","dex","int","faith","weight","durability",
  "poison","toxic","bleed","curse","poise",
  "vit","att","end","res","soulLv","souls","slot","humanity","humanityStat","hp","stamina","mp",
  "divine","occult","stability"]);const ds1IconTables=new Set(["EquipParamWeapon","EquipParamProtector","EquipParamAccessory",
  "EquipParamGoods","Magic","SpEffectParam","WeaponSkill"]);
function ds1LabelArt(panel){
  if(!(panel instanceof Element))return;
  for(const field of panel.querySelectorAll("[data-lex-icon]")){
    const kind=field.getAttribute("data-lex-icon");
    if(!ds1LabelKinds.has(kind))continue;
    // A pinned table header carries its kind on the label itself; a
    // detail field carries it on the field around its label.
    const label=field.matches(".lex-pinned-header-label")?field:field.querySelector(":scope > .lex-detail-field-label");
    if(!label||label.querySelector(":scope > img.lex-ds1-label-art"))continue;
    const art=el("img",{class:"lex-ds1-label-art",src:`/api/label?name=${encodeURIComponent(kind)}`,
      alt:"",draggable:"false","aria-hidden":"true","data-lex-no-image":"off"});
    const glyph=label.querySelector(":scope > .lex-type-glyph");
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
    // Humans walk on the shared player rig, which carries bones but
    // no meshes: their bodies are armor sets the game assembles, not
    // one model file. Previewing the bare rig shows a glitched empty
    // stage, so mesh-less links take the honest empty state instead:
    // the placeholder, no magnifier, and the reason on the icon.
    const chr=(view.chrs||[]).find(entry=>entry.available&&(entry.meshes||0)>0);
    if(chr)return {kind:"chr",name:`${view.name} model`,npc:id,
      url:`/api/chr/geometry?chr=${encodeURIComponent(chr.id)}`};
    // Attacks without a model still open the viewer: the drawer lists
    // them with their hitboxes while the stage hides, having nothing
    // to stand on. Only an NPC with neither a model nor attacks keeps
    // the honest empty header with no magnifier.
    if((view.attackCount||0)>0||(view.attacks||[]).length)return {kind:"chr",name:`${view.name} attacks`,npc:id};
    if((view.chrs||[]).some(entry=>entry.available))
      return {reason:`${view.name} is assembled from armor, so there is no one model to preview.`};
    return {reason:`${view.name} has no character model.`};
  }
  if(table==="Magic")return {reason:"Spells have no model to preview."};
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
  if(state.pagedView?.pinOwner){
    const previewBox=heading.querySelector('.lex-detail-panel-icon');
    if(previewBox)LexeditorUI.attachPreviewPin(previewBox,state.pagedView.pinOwner,"icon","Icon");
  }
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
  if(target.kind==="chr"){
    // A viewer link preselects its attack; the request is one-shot.
    const attack=target.attackId;
    delete target.attackId;
    return chrDrawerContent(target,attack);
  }
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
  stage.lexViewModes?.bar?.append(picker);
  show(`/api/parts/geometry?table=${encodeURIComponent(target.table)}&id=${target.id}&variant=${encodeURIComponent(picked.variant)}`);
  return stage;
}
// The enemy viewer: the Model tab's contents merged into the magnifier
// drawer - an attack list on the left, the animated stage with its motion
// picker and playback timeline in the middle, and the viewed attack's
// hitbox fields in a panel on the right. One viewer, not two: enemies
// with a preview open it here, and the Model tab stays only where no
// preview opens. Hitbox timing is not shown: parameter links do not prove
// an animation uses the attack, so no timeline can say when a slot strikes.
// The enemy viewer's picked motion per enemy, kept while the page
// lives: reopening the drawer replays the last motion, not the first.
const chrAnimPick=new Map();
// The enemy viewer shares three.js with the animation mount: one
// import for every drawer, so overlay math never reloads the module.
let chrThree=null;
const chrThreeLib=async()=>chrThree||(chrThree=await import("three"));
// The viewed body: the first working model, like the anchor chips.
function chrViewed(view){
  return (view?.chrs||[]).find(entry=>entry.available)||(view?.chrs||[])[0]||null;
}
function dist3(a,b){
  return Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
}
// Dropping the overlay group: a remount drops it first, and the
// animation mount drops it on dispose, so no GL buffers strand.
function chrDropOverlays(stageHost){
  const overlay=stageHost._chrOverlay;
  stageHost._chrOverlay=null;
  if(!overlay)return;
  if(overlay.group.parent)overlay.group.parent.remove(overlay.group);
  for(const item of overlay.trash)item.dispose?.();
}
// Re-seating the overlays on the live bones after every pose: anchored
// points follow their bone, unattached ones sit at rest, and the body
// capsule follows the root sideways while staying vertical.
function chrPositionOverlays(stageHost,bones){
  const overlay=stageHost._chrOverlay;
  if(!overlay)return;
  if(bones&&bones.length&&overlay.bonesRef!==bones){
    overlay.bonesRef=bones;
    overlay.byName=new Map(bones.map(bone=>[bone.name,bone]));
  }
  const place=(mesh,dummy)=>{
    const bone=dummy.bone_name?overlay.byName.get(dummy.bone_name):null;
    if(bone)bone.getWorldPosition(mesh.position);
    else mesh.position.set(dummy.pos[0],dummy.pos[1],dummy.pos[2]);
  };
  for(const item of overlay.items){
    if(!item.capsule){place(item.mesh,item.dummy);continue;}
    const boneA=item.a.bone_name?overlay.byName.get(item.a.bone_name):null;
    const boneB=item.b.bone_name?overlay.byName.get(item.b.bone_name):null;
    if(boneA)boneA.getWorldPosition(item.tmpA);else item.tmpA.set(item.a.pos[0],item.a.pos[1],item.a.pos[2]);
    if(boneB)boneB.getWorldPosition(item.tmpB);else item.tmpB.set(item.b.pos[0],item.b.pos[1],item.b.pos[2]);
    item.mesh.position.set((item.tmpA.x+item.tmpB.x)/2,(item.tmpA.y+item.tmpB.y)/2,(item.tmpA.z+item.tmpB.z)/2);
    item.tmpD.copy(item.tmpB).sub(item.tmpA);
    if(item.tmpD.lengthSq()>1e-12)item.mesh.quaternion.setFromUnitVectors(overlay.up,item.tmpD.normalize());
  }
  if(overlay.bodyMesh){
    const root=overlay.bonesRef?overlay.bonesRef[0]:null;
    if(root){
      root.getWorldPosition(overlay.scratch);
      overlay.bodyMesh.position.set(overlay.scratch.x,
        overlay.scratch.y+(overlay.body.offset||0)+overlay.body.height/2,overlay.scratch.z);
    }else overlay.bodyMesh.position.set(0,(overlay.body.offset||0)+overlay.body.height/2,0);
  }
}
// Hitbox overlays on the animated stage: green dots on the viewed
// attack's anchors, red spheres and capsules on its live slots, and
// the body's blue capsule. Only the dummies the viewed attack's slots
// name light up; a slot that names a point the model lacks is
// reported, not drawn. Rest seating is static; the first pose re-seats
// everything live.
async function chrBuildOverlays(stageHost,view,attackId){
  const scene=stageHost._animScene?stageHost._animScene():null;
  if(!scene)return null;
  const THREE=await chrThreeLib();
  chrDropOverlays(stageHost);
  const chr=chrViewed(view);
  const byId=new Map((chr?.dummies||[]).map(dummy=>[dummy.id,dummy]));
  const attack=(view.attacks||[]).find(entry=>entry.id===attackId);
  const wanted=new Set();
  for(const slot of attack?.slots||[]){
    if(typeof slot.first==="number")wanted.add(slot.first);
    if(slot.shape==="capsule"&&typeof slot.second==="number")wanted.add(slot.second);
  }
  const shown=[...byId].filter(([id])=>wanted.has(id));
  const body=view.body||{};
  const group=new THREE.Group();
  const items=[];
  const trash=[];
  const dotGeo=new THREE.SphereGeometry(body.height>0?Math.max(body.height*0.004,0.005):0.01,8,8);
  const dotMat=new THREE.MeshBasicMaterial({color:0x44dd66});
  const hitMat=new THREE.MeshBasicMaterial({color:0xff5533,transparent:true,opacity:0.4,depthWrite:false});
  trash.push(dotGeo,dotMat,hitMat);
  for(const [,dummy] of shown){
    const dot=new THREE.Mesh(dotGeo,dotMat);
    group.add(dot);
    items.push({mesh:dot,dummy});
  }
  let live=0,missing=0;
  for(const slot of attack?.slots||[]){
    if(!slot.active)continue;
    const a=byId.get(slot.first);
    if(!a){missing++;continue;}
    const b=slot.shape==="capsule"?byId.get(slot.second):null;
    if(slot.shape==="capsule"&&b&&dist3(a.pos,b.pos)>1e-6){
      const geo=new THREE.CapsuleGeometry(slot.radius,dist3(a.pos,b.pos),8,16);
      trash.push(geo);
      const mesh=new THREE.Mesh(geo,hitMat);
      group.add(mesh);
      items.push({mesh,capsule:true,a,b,tmpA:new THREE.Vector3(),tmpB:new THREE.Vector3(),tmpD:new THREE.Vector3()});
    }else{
      if(slot.shape==="capsule")missing++;
      const geo=new THREE.SphereGeometry(slot.radius,16,12);
      trash.push(geo);
      const mesh=new THREE.Mesh(geo,hitMat);
      group.add(mesh);
      items.push({mesh,dummy:a});
    }
    live++;
  }
  let bodyMesh=null;
  if(body.radius>0&&body.height>0){
    const geo=new THREE.CapsuleGeometry(body.radius,Math.max(body.height-body.radius*2,0),8,16);
    const mat=new THREE.MeshBasicMaterial({color:0x3388ff,transparent:true,opacity:0.3,depthWrite:false});
    trash.push(geo,mat);
    bodyMesh=new THREE.Mesh(geo,mat);
    group.add(bodyMesh);
  }
  scene.add(group);
  const liveNames=new Set(stageHost._animBones?stageHost._animBones().map(bone=>bone.name):[]);
  const used=new Set();
  for(const slot of attack?.slots||[]){
    if(!slot.active)continue;
    if(typeof slot.first==="number")used.add(slot.first);
    if(slot.shape==="capsule"&&typeof slot.second==="number")used.add(slot.second);
  }
  let staticCount=0;
  for(const id of used){
    const dummy=byId.get(id);
    if(dummy&&!(dummy.bone_name&&liveNames.has(dummy.bone_name)))staticCount++;
  }
  stageHost._chrOverlay={group,items,bodyMesh,body,trash,
    bonesRef:null,byName:new Map(),scratch:new THREE.Vector3(),up:new THREE.Vector3(0,1,0)};
  stageHost.dataset.dots=String(shown.length);
  chrPositionOverlays(stageHost,null);
  return {live,missing,static:staticCount};
}
// The stage's status line: what model shows, what the viewed attack
// strikes with, and the body's size. The mount's own problem rides
// along, so an unreadable motion still explains itself.
function chrWriteSummary(status,view,attackId,counts,mountProblem){
  const chr=chrViewed(view);
  if(!chr)return;
  const plural=(n,one,many)=>`${n} ${n===1?one:many}`;
  const short=n=>+Number(n).toFixed(3);
  const attack=(view.attacks||[]).find(entry=>entry.id===attackId);
  const body=view.body||{};
  let text=`${chr.id}: ${plural(chr.meshes??0,"mesh","meshes")}, ${plural(chr.dummies?.length??0,"model point","model points")}. `;
  text+=attack?`Attack "${attack.name}": ${plural(counts.live,"live hitbox","live hitboxes")}`:"No linked attack";
  if(counts.missing)text+=`, ${plural(counts.missing,"slot points","slots point")} at a missing model point`;
  if(counts.static)text+=`, ${plural(counts.static,"anchor sits","anchors sit")} at rest`;
  text+=body.radius>0&&body.height>0?` Body R ${short(body.radius)} x H ${short(body.height)}.`:".";
  if((view.chrs||[]).length>1)text+=` Also wears ${(view.chrs||[]).filter(entry=>entry.id!==chr.id).map(entry=>entry.id).join(", ")}.`;
  status.textContent=text+(mountProblem?` ${mountProblem}`:"");
}
async function chrDrawerContent(target,initialAttack=null){
  const view=await api(`/api/chr/view?npc=${target.npc}`);
  const listHost=el("div",{class:"lex-chr-viewer-list"});
  const pickerRow=el("div",{class:"lex-chr-viewer-picker"});
  const stageHost=el("div",{class:"lex-chr-viewer-stage"});
  const timelineHost=el("div",{class:"lex-chr-viewer-timeline"});
  const status=el("div",{class:"lex-viewport-status"});
  const fieldsHost=el("div",{class:"lex-chr-viewer-fields"});
  const wrap=el("div",{class:"lex-chr-viewer"},listHost,
    el("div",{class:"lex-chr-viewer-main"},pickerRow,stageHost,timelineHost,status),fieldsHost);
  let attackId=(view.attacks||[]).some(entry=>entry.id===initialAttack)?initialAttack:(view.attacks||[])[0]?.id??null;
  const renderList=()=>{listHost.replaceChildren(chrAttackList(view.attacks||[],attackId,pick));};
  // The drawer appends this content after the factory resolves, and the
  // stage refuses a detached host, so the first mount waits a frame.
  // Nothing mounted means nothing to stand on: the stage hides instead
  // of leaving a black hole, and the attack list and hitbox panel stay.
  // The generation pins every decision to the latest mount, so a slow
  // mount cannot hide its replacement's canvas or seat stale overlays.
  let stageGen=0;
  let anims=null,animsFor=null,animsError="";
  let mountProblem="";
  let mountedFile=null;
  const motionOf=()=>{
    const select=pickerRow.querySelector("select");
    const file=select?select.value:chrAnimPick.get(target.npc);
    const entries=anims||[];
    return entries.find(entry=>entry.file&&entry.file===file)
      ||entries.find(entry=>entry.file&&entry.available!==false)
      ||entries.find(entry=>entry.file)||null;
  };
  const renderPicker=()=>{
    const chr=chrViewed(view);
    if(!chr||!chr.available){pickerRow.replaceChildren();return;}
    if(anims===null){pickerRow.replaceChildren(LexeditorUI.loadingStatus("Reading animations"));return;}
    if(!anims.length){pickerRow.replaceChildren(LexeditorUI.detailNote(
      animsError?`No animations: ${animsError}.`:"No animations are installed for this model."));return;}
    const select=el("select",{class:"lex-chr-viewer-motion","aria-label":"Animation"},
      ...anims.map(entry=>el("option",{value:entry.file||""},
        `${entry.file||"(no file)"}${entry.frames?` — ${entry.frames} frames`:""}${entry.available===false?" (unavailable)":""}`)));
    const current=motionOf()?.file;
    if(current)select.value=current;
    // A picked motion remounts once: input and change both fire for one
    // pick where both arrive, and input alone arrives in vanilla, where
    // change events on selects never reach their listeners. A value the
    // stage already plays is a no-op, so the second event lands silent.
    const repick=()=>{
      if(select.value===(mountedFile??false)&&stageHost.querySelector("canvas"))return;
      chrAnimPick.set(target.npc,select.value);
      renderStage();
    };
    select.addEventListener("input",repick);
    select.addEventListener("change",repick);
    pickerRow.replaceChildren(el("span",{class:"lex-chr-viewer-motion-label"},"Animation"),
      infoHelp("Motions from this model's animation binder. Pick one to pose the model; hitbox timing is not shown, because parameters do not prove an animation uses the attack."),
      select);
  };
  const renderOverlays=async ()=>{
    try{
      const counts=await chrBuildOverlays(stageHost,view,attackId);
      if(!wrap.isConnected)return;
      if(counts)chrWriteSummary(status,view,attackId,counts,mountProblem);
    }catch(error){if(wrap.isConnected)notify(error);}
  };
  const renderStage=async ()=>{
    const gen=++stageGen;
    stageHost.hidden=false;
    timelineHost.replaceChildren();
    const chr=chrViewed(view);
    if(!chr||!chr.available){
      pickerRow.replaceChildren();
      mountProblem="";
      status.textContent=!chr?`${view.name}: no placed character model.`
        :`${view.name}: ${chr.id} — ${chr.reason||"model unavailable"}.`;
      stageHost.hidden=true;
      return;
    }
    if(animsFor!==chr.id){
      anims=null;animsFor=chr.id;animsError="";
      renderPicker();
      try{anims=(await api(`/api/anim/list?chr=${encodeURIComponent(chr.id)}`)).anims||[];}
      catch(error){anims=[];animsError=error.message||String(error);}
      if(gen!==stageGen||!wrap.isConnected)return;
      renderPicker();
    }
    await new Promise(request=>requestAnimationFrame(request));
    if(gen!==stageGen||!stageHost.isConnected)return;
    chrDropOverlays(stageHost);
    mountedFile=null;
    const motion=motionOf();
    await Ds1Anim.mount(stageHost,chr.id,motion,timelineHost,status,null,
        {afterPose:posed=>chrPositionOverlays(stageHost,posed),onDispose:()=>chrDropOverlays(stageHost)})
      .catch(error=>{if(gen===stageGen)status.textContent=error.message||String(error);});
    if(gen!==stageGen||!stageHost.isConnected)return;
    if(!stageHost.querySelector("canvas")){stageHost.hidden=true;return;}
    mountedFile=motion?.file??null;
    mountProblem=status.textContent.trim();
    await renderOverlays();
  };
  const renderFields=async ()=>{
    if(attackId==null){fieldsHost.replaceChildren();return;}
    fieldsHost.replaceChildren(LexeditorUI.loadingStatus("Reading hitboxes"));
    try{
      const result=await api(`/api/row?table=AtkParam_Npc&id=${attackId}&sub=attacks`);
      if(!wrap.isConnected)return;
      const attackRow={table:"AtkParam_Npc",id:attackId,name:result.row.name,fields:result.row.fields};
      // The body's own fields ride along: the hurtbox edits beside its hitboxes.
      const npcResult=await api(`/api/row?table=NpcParam&id=${target.npc}`).catch(()=>null);
      if(!wrap.isConnected)return;
      const npcRow=npcResult?.row?{table:"NpcParam",id:target.npc,name:npcResult.row.name,fields:npcResult.row.fields}:null;
      fieldsHost.replaceChildren(chrHitboxFields(attackRow,chrDummies(view),refreshSoon),...(npcRow?[chrBodyFields(npcRow,refreshSoon)]:[]));
      // Test seam: each completed fields paint bumps the generation.
      fieldsHost.dataset.fieldsSeq=String(++chrFieldsSeq);
    }catch(error){
      if(wrap.isConnected)fieldsHost.replaceChildren(LexeditorUI.detailNote("Could not read the attack."));
      notify(error);
    }
  };
  const refresh=async ()=>{
    if(!wrap.isConnected){chrDrawerRefresh=null;return false;}
    const before=chrViewed(view)?.id;
    const fresh=await api(`/api/chr/view?npc=${target.npc}`);
    Object.assign(view,fresh);
    if(!(view.attacks||[]).some(entry=>entry.id===attackId))attackId=(view.attacks||[])[0]?.id??null;
    renderList();
    if(chrViewed(view)?.id!==before){animsFor=null;await renderStage();}
    else await renderOverlays();
    await renderFields();
    return true;
  };
  const refreshSoon=()=>{edits.then(refresh).catch(()=>{});};
  const pick=id=>{if(id===attackId)return;attackId=id;renderList();renderOverlays();renderFields();};
  chrDrawerRefresh=refresh;
  renderList();renderStage();renderFields();
  return wrap;
}
async function refreshChrDrawer(){
  if(typeof chrDrawerRefresh!=="function")return false;
  try{return await chrDrawerRefresh();}
  catch(error){notify(error);return true;}
}
function chrAttackList(attacks,selectedId,onPick){
  return columnList({rows:attacks.map(entry=>({id:entry.id,name:entry.name,values:{route:entry.route}})),
    key:row=>row.id,selected:selectedId,select:row=>{if(row.id!==selectedId)onPick(row.id);},
    columns:[{key:"name",label:"Attack",grow:1},
      {key:"route",label:"Route",render:row=>String(row.values.route||"")}]});
}
// The viewed model's anchor points: hitbox drop targets read them.
function chrDummies(view){
  return chrViewed(view)?.dummies||[];
}
// A slot's point field doubles as a drop target: a dropped model
// point re-anchors the hitbox, and the viewer repaints on landing.
// One hit slot's status line, shared by the Attacks tab and the enemy
// viewer: live or idle, sphere or capsule, and which anchors it hangs
// from. dummyIds names the viewed model's anchors when one is in view;
// without it a slot can only say live or idle, never where it sits.
function hitSlotText(slot,values,dummyIds){
  const radius=Number(values.get(`hit${slot}_Radius`)??0);
  const first=Number(values.get(`hit${slot}_DmyPoly1`)??-1);
  const second=Number(values.get(`hit${slot}_DmyPoly2`)??-1);
  const size=+Number(radius).toFixed(3);
  if(!(radius>0))return `Idle: radius 0 strikes nothing.`;
  if(!(first>=0))return `Idle: no anchor set.`;
  const missing=anchor=>dummyIds&&!dummyIds.has(anchor);
  if(missing(first))return `Live: sphere, radius ${size} m on anchor ${first}. That anchor is not on this body model.`;
  if(second>=0&&second!==first){
    if(missing(second))return `Live: sphere, radius ${size} m on anchor ${first}. Anchor ${second} is not on this body model.`;
    return `Live: capsule, radius ${size} m from anchor ${first} to anchor ${second}.`;
  }
  return `Live: sphere, radius ${size} m on anchor ${first}.`;
}
function hitSlotOf(key){
  const hit=/^hit(\d)_(Radius|DmyPoly1|DmyPoly2)$/.exec(key||"");
  if(hit)return Number(hit[1]);
  const priority=/^hti(\d)_Priority$/.exec(key||"");
  return priority?Number(priority[1]):null;
}
// One slot's status row: the text plus the hooks an edit uses to
// refresh it in place.
function hitSlotStatusRow(slot,values,dummyIds){
  const control=readonlyField(hitSlotText(slot,values,dummyIds),{format:false});
  control.dataset.hitSlotStatus=String(slot);
  if(dummyIds&&dummyIds.size)control.dataset.hitSlotDummies=[...dummyIds].join(",");
  return detailField({label:`Hit ${slot}`,control});
}
// The Attacks tab stores hit fields field by field (every Size, then
// every First point), while the viewer lays them slot by slot. One
// ordering wins: each slot's status line, then that slot's own fields,
// with the shared source select last.
function hitboxGroupWithStatus(row,kids,dummyIds){
  const values=new Map((row.fields||[]).map(field=>[field.key,field.value]));
  const keyOf=kid=>kid.querySelector?.("[data-field-key]")?.dataset.fieldKey;
  const buckets=[[],[],[],[]],rest=[];
  for(const kid of kids){
    const slot=hitSlotOf(keyOf(kid));
    if(slot===null||slot<0||slot>3)rest.push(kid);
    else buckets[slot].push(kid);
  }
  const out=[];
  for(let slot=0;slot<4;slot++){
    out.push(hitSlotStatusRow(slot,values,dummyIds));
    out.push(...buckets[slot]);
  }
  out.push(...rest);
  return out;
}
// A hit-slot edit moves that slot's status line in place, on the tab
// and in the viewer, without rebuilding the panel out from under it.
function syncHitSlotStatus(row){
  const values=new Map((row.fields||[]).map(field=>[field.key,field.value]));
  for(const node of document.querySelectorAll("[data-hit-slot-status]")){
    const ids=node.dataset.hitSlotDummies;
    node.value=hitSlotText(Number(node.dataset.hitSlotStatus),values,
      ids?new Set(ids.split(",").map(Number)):null);
  }
}
// An attack row's owners open in the enemy viewer with that attack
// showing, instead of landing on the enemy and leaving the reader to
// find the magnifier and then the attack in its list.
async function openAttackViewer(variant,attackId){
  pendingViewer={npc:variant.id,attack:attackId};
  keepViewerPending=true;
  await navigate(variant.tab,variant.sub,`NpcParam:${variant.id}`);
}
function hitboxPointDrop(shared,def){
  return el("span",{class:"ds1-hitbox-drop","data-point-field":def.key},shared);
}
// A chip drags by pointer, like a panel label: past a few pixels the
// point field under the pointer lights up, and releasing over one
// re-anchors the hitbox there.
function dummyChipDrag(chip,attackRow,defs,afterEdit,dummyId){
  let down=null;
  const clear=()=>document.querySelectorAll(".ds1-hitbox-over")
    .forEach(node=>node.classList.remove("ds1-hitbox-over"));
  const under=event=>event.clientX===undefined?null
    :document.elementFromPoint(event.clientX,event.clientY)?.closest("[data-point-field]");
  chip.addEventListener("pointerdown",event=>{
    if(state.readOnly||event.button!==0)return;
    down={x:event.clientX,y:event.clientY};
    try{chip.setPointerCapture(event.pointerId);}catch(_ignored){}
  });
  chip.addEventListener("pointermove",event=>{
    if(!down)return;
    if(Math.hypot(event.clientX-down.x,event.clientY-down.y)<4)return;
    if(event.cancelable)event.preventDefault();
    clear();
    under(event)?.classList.add("ds1-hitbox-over");
  });
  const drop=event=>{
    if(!down)return;
    down=null;
    const target=under(event);
    clear();
    if(!target)return;
    const def=defs.get(target.dataset.pointField);
    if(!def)return;
    commit(attackRow,def,dummyId,target.querySelector("input,select")||target);
    afterEdit();
  };
  chip.addEventListener("pointerup",drop);
  chip.addEventListener("pointercancel",()=>{down=null;clear();});
}
function chrHitboxFields(attackRow,dummies,afterEdit){
  const defs=new Map((attackRow.fields||[]).map(field=>[field.key,field]));
  const values=new Map((attackRow.fields||[]).map(field=>[field.key,field.value]));
  const dummyIds=(dummies||[]).length?new Set(dummies.map(dummy=>dummy.id)):null;
  const body=[];
  for(let slot=0;slot<4;slot++){
    body.push(hitSlotStatusRow(slot,values,dummyIds));
    for(const key of [`hit${slot}_Radius`,`hit${slot}_DmyPoly1`,`hit${slot}_DmyPoly2`]){
      const def=defs.get(key);
      if(!def)continue;
      // The Attacks tab's own controls: units, bounds and the vanilla
      // reference ride along, and the viewer repaints after each edit.
      const shared=controlFor(attackRow,def);
      shared.addEventListener("change",()=>afterEdit());
      const point=/^hit\d_DmyPoly[12]$/.test(def.key);
      const input=point?hitboxPointDrop(shared,def):shared;






      body.push(detailField({label:def.label,control:input,
        ...(def.description?{help:infoHelp(def.description)}:{})}));
    }
  }
  if(dummies.length){
    const strip=el("div",{class:"ds1-dummy-strip",role:"list"});
    for(const dummy of dummies){
      // The chip names where its anchor sits: bone and bind-pose
      // position join the number, so a bare ID becomes a place.
      const spot=(dummy.pos||[]).map(axis=>+Number(axis).toFixed(2)).join(", ");
      const where=dummy.bone_name?` on ${dummy.bone_name}`:"";
      const at=spot?` at (${spot})`:"";
      const chip=el("button",{type:"button",class:"ds1-dummy-chip",disabled:state.readOnly,
        "data-dummy":String(dummy.id),"aria-label":`Model point ${dummy.id}${where}${at}`,
        title:`Anchor ${dummy.id}${where}${at}. Drag onto a slot's point field to move the hitbox there`},`#${dummy.id}`);
      dummyChipDrag(chip,attackRow,defs,afterEdit,dummy.id);
      strip.append(chip);
    }
    body.push(detailField({label:"Model points",control:strip,
      help:infoHelp("The viewed model's anchor points. Drag one onto a slot's First or Second point to move that hitbox there.")}));
  }
  body.push(actionRow(el("button",{type:"button",onclick:()=>openAttack(attackRow.id,attackRow.table)},
    `Edit ${attackRow.name||"attack"} in Attacks`)));
  return detailSection({title:"Hitboxes",body});
}
// The body's own hurtbox beside its hitboxes: radius, height and
// vertical shift, through the same shared controls as every tab.
function chrBodyFields(npcRow,afterEdit){
  const defs=new Map((npcRow.fields||[]).map(field=>[field.key,field]));
  const body=[];
  for(const name of ["hitRadius","hitHeight","hitYOffset"]){
    const def=defs.get(name);
    if(!def)continue;
    const shared=controlFor(npcRow,def);
    shared.addEventListener("change",()=>afterEdit());
    body.push(detailField({label:def.label,control:shared,
      ...(def.description?{help:infoHelp(def.description)}:{})}));
  }
  if(!body.length)return LexeditorUI.detailNote("This enemy's body has no editable hurtbox.");
  return detailSection({title:"Body",body});
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
    // An attack's viewer link asked for this enemy: its drawer opens
    // with that attack showing. Anything else drops the request.
    const want=pendingViewer&&table==="NpcParam"&&Number(id)===pendingViewer.npc?pendingViewer:null;
    if(want)pendingViewer=null;
    if(target.reason){if(want)notify(target.reason);ds1PreviewReason(panel,table,id,target.reason);return;}
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
      onClose:drawer=>{chrDrawerRefresh=null;window.Ds1Preview.stop(drawer);drawer.replaceChildren();delete window.__lexPreview;}});
    if(want){target.attackId=want.attack;panel.lexModelPreview?.open();}
    const previewBox=heading&&heading.querySelector('.lex-detail-panel-icon');
    if(previewBox&&state.pagedView?.pinOwner)
      LexeditorUI.attachPreviewPin(previewBox,state.pagedView.pinOwner,"icon","Icon");
  };
  // Detail panels mount after detail() returns, so a cached answer settles
  // on a microtask: settling synchronously would find a detached panel.
  if("settled" in entry)queueMicrotask(()=>settle(entry.settled));else entry.promise.then(()=>settle(entry.settled));
  ds1LabelArt(panel);
  return panel;
}
function taeActions(){
  const disabled=state.readOnly||state.taeBusy||state.pending>0;
  // The shared header-button style: boxed icon buttons with hover
  // titles, like the bands header below. The accessible names stay
  // put, so the add form and remove confirm open as before.
  const addTitle=state.readOnly?"Open a mod project to add events":"Add an event to this motion";
  const removeTitle=state.readOnly?"Open a mod project to remove events":"Remove the selected event";
  return [
    el("button",{type:"button",class:"lex-header-icon","data-tae-action":"add",disabled,title:addTitle,"aria-label":"Add event",onclick:()=>beginTaeForm().catch(notify)},LexeditorUI.copyIcon()),
    el("button",{type:"button",class:"lex-header-icon","data-tae-action":"remove",disabled,title:removeTitle,"aria-label":"Remove event",onclick:()=>removeTaeEvent().catch(notify)},LexeditorUI.removeIcon())
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
  refreshAnimList();refreshAnimDetail();
}
function renderTaeForm(){
  const form=state.taeForm;
  const type=el("select",{"aria-label":"Event type","data-tae-input":"type",disabled:state.taeBusy,
    onchange:event=>{form.type=event.target.value;refreshAnimDetail();}},
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
      el("button",{type:"button",disabled:state.taeBusy,onclick:()=>{state.taeForm=null;refreshAnimDetail();}},"Cancel")],
    body:[detailSection({title:"Event",body:[
      detailField({label:"Event type",control:type,
        help:infoHelp("Which documented event to add. Its values start at 0, so set them after. Only documented types can be added.")}),
      detailField({label:"Start (s)",control:start}),
      detailField({label:"End (s)",control:end})]})]});
}
function submitTaeForm(form){
  if(state.taeBusy||state.readOnly||state.taeForm!==form)return;
  state.taeBusy=true;state.pending++;refreshAnimList();refreshAnimDetail();
  edits=edits.then(async()=>{
    try{
      const result=await api("/api/tae/add",{table:form.binder,tae:form.tae,anim:form.anim,
        type:Number(form.type),start:Number(form.start),end:Number(form.end)});
      state.rows=result.events;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
      state.taeForm=null;state.selected=key(result.row);state.animQuery="";
      await loadItems();
      const index=animListMatches().findIndex(row=>key(row)===state.selected);
      state.animPage=Math.max(0,Math.floor(index/paneSize("events")));
    }catch(error){
      state.taeForm=null;await refreshState();await loadItems();notify(error);
    }finally{
      state.pending--;state.taeBusy=false;refreshAnimList();refreshAnimDetail();revealSelection();shell.refresh();
    }
  }).catch(notify);
}
async function removeTaeEvent(){
  if(state.readOnly||state.taeBusy||state.pending||!state.row)return;
  const ok=await confirmAction({title:`Remove ${state.row.name}?`,
    message:"The event leaves the animation at once. Save keeps the removal in the mod project.",
    confirmLabel:"Remove event",cancelLabel:"Cancel"});
  if(!ok)return;
  state.taeBusy=true;state.pending++;refreshAnimList();refreshAnimDetail();
  try{
    const [table,id]=[state.row.table,state.row.id];
    const result=await api("/api/tae/remove",{table,id});
    state.rows=result.events;state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
    state.selected=null;state.row=null;state.animQuery="";
    await loadItems();
  }catch(error){await refreshState();await loadItems();notify(error);}
  finally{state.taeBusy=false;state.pending--;refreshAnimList();refreshAnimDetail();revealSelection();shell.refresh();}
}
function bandActions(){
  const disabled=state.readOnly||state.bandBusy||state.pending>0;
  // The shared header-button style: boxed icon buttons with hover
  // titles, like every other detail header. The accessible names
  // stay put, so the split and merge forms open as before.
  const addTitle=state.readOnly?"Open a mod project to add load bands":"Split this band in two";
  const deleteTitle=state.readOnly?"Open a mod project to delete load bands":"Merge this band into a neighbour";
  return [
    el("button",{type:"button",class:"lex-header-icon","data-band-action":"add",disabled:disabled||!state.row.band.canAdd,
      title:addTitle,"aria-label":"Add band",onclick:()=>beginBandForm("add")},LexeditorUI.copyIcon()),
    el("button",{type:"button",class:"lex-header-icon","data-band-action":"delete",disabled:disabled||!state.row.band.canDelete,
      title:deleteTitle,"aria-label":"Delete band",onclick:()=>beginBandForm("delete")},LexeditorUI.removeIcon())
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
  const noun=misc?(state.sub==="encumbrance"?"bands":state.sub==="encumbrance-overrides"?"overrides":"stamina"):state.tab==="effects"?"effects":state.tab==="attacks"?(state.sub==="projectiles"?"projectiles":"attacks"):state.tab==="npcs"?(state.sub==="unowned-shops"?"shop lines":"NPCs"):state.tab==="drops"?"drops":state.tab==="ai"?(state.sub==="behaviors"?"behaviors":state.sub==="player-behaviors"?"player behaviors":"AI records"):state.tab==="enemies"?(state.sub==="bosses"?"bosses":"monsters"):state.tab==="text"?"labels":state.tab==="scripts"?"states":state.tab==="stats"?(state.sub==="levelup"?"gains":state.sub==="curves"?"curves":state.sub==="upgrade-materials"?"material sets":state.sub==="starting-classes"?"classes":state.sub==="starting-gifts"?"gifts":"upgrades"):state.tab==="sound"?"sounds":ASSET_TABS.has(state.tab)?"files":"items";
  const label=misc?"Misc.":state.tab==="effects"?"Effects":state.tab==="attacks"?"Attacks":state.tab==="animations"?"Animations":state.tab==="npcs"?"NPCs":state.tab==="drops"?"Drops":state.tab==="ai"?"AI":state.tab==="enemies"?"Enemies":state.tab==="text"?"Text":state.tab==="scripts"?"Scripts":state.tab==="stats"?"Stats":ASSET_TABS.has(state.tab)?ASSET_LABELS[state.tab]:"Items";
  // sortedRows owns this list's order (filter, name sort, meaningful-order tabs); the framework yields.
  const view=pagedListDetail({className:"ds1-records",rows:sortedRows(),key,selected:state.selected,slots:false,order:"given",noun,modOnly:modOnlySpec(),
    page:state.page,pageSize:state.pageSize,defaultSplit:32,minLeft:230,minRight:380,splitKey:"ds1-"+state.tab+"-"+state.sub,rowsKey:"ds1-"+state.tab+"-"+state.sub,barrelKey:"ds1-"+state.tab+"-"+state.sub,legacyColumnsKey:"ds1-"+state.tab,
    search:{key:"ds1-records-search",value:state.query,label:"Search "+noun,change:value=>{state.query=value;state.page=0;render();}},
    // Creation lives in the detail header: records duplicate there, and
    // asset files join the mod through + in the file header - adding at
    // a path the game has replaces it through the loader, so asset tabs
    // need no Replace action of their own. The list keeps no add button.
    tableAdd:false,
    sync:next=>{
      state.page=next.page;state.pageSize=next.pageSize;state.selection=next.selection||[];
      if(state.selected!==next.selected){state.selected=next.selected;void loadDetail().then(render).catch(notify);}
    },
    change:next=>{state.page=next.page;state.pageSize=next.pageSize;if(next.reason==="pins"&&state.pagedView?.refreshMaster){state.pagedView.refreshMaster();ds1LabelArt(state.pagedView);}else render();},
    master:({rows:listed,selected,select})=>{
      selectVisibleRecord=select;
      return columnList({rows:listed,key,selected,
      decorateRow:(node,row)=>{if(row.table!=="SoundStream"||soundStreamNumber(row.name)!==null)LexeditorUI.decorateSearchCandidate(node,{type:`ds1-${row.table}`,value:row.id,label:row.name});
        if(row.modelPick)LexeditorUI.decorateSearchCandidate(node,{type:row.modelPick.type,value:row.modelPick.value,label:row.name});
        return node;},
      sortState:tabSort(),
      sort:column=>{if(misc||(state.tab==="stats"&&state.sub==="levelup"))return;const before=tabSort();state.sorts[sortScope()]={key:column,dir:before.key===column?-before.dir:1};render();},
      // The record is fetched first, then the shared list swaps in its detail
      // pane once. It used to draw the pane with the old record, then render
      // the whole page twice more as two loads of the same row came back.
      select:async(row,event)=>{
        await edits;
        if(!event?.shiftKey&&!event?.ctrlKey&&!event?.metaKey){state.selected=key(row);await loadDetail();}
        select(row,event);shell.refresh();},
      columns:(misc&&state.sub==="encumbrance")?[{key:"range",label:"Load",grow:1},{key:"name",label:"Name",grow:1}]:
        state.tab==="items"?[{key:"name",label:"Name",sortable:true,grow:1}]:
        state.tab==="textures"?[{key:"name",label:"Name",sortable:true,grow:1},
          {key:"file",label:"File",sortable:true,render:row=>row.file||""},
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
    // names: script states have no stored names; the list names them by archive, script, group and state.
    // names: a menu label keeps its slot name, so an edited label keeps its record.
    renamable:row=>state.tab==="text"?false:state.tab==="stats"?!["CalcCorrectGraph","EquipMtrlSetParam","CharaInitParam","NativeRules"].includes(row.table):state.tab==="items"&&!(state.sub==="spells"&&row.table!=="Magic"),
    describePinnedCell,commitPinnedCell,
    detail,emptyDetail:()=>state.tab==="items"&&state.sub==="ashes-of-war"?emptySkillDetail():detailPanel({title:"No matching "+noun,...(ASSET_TABS.has(state.tab)?{actions:[assetUploadButton()]}:{}),body:[LexeditorUI.detailNote("Change the search to find a record.")]})});
  state.pagedView=view;
  // Pinned headers take the same game art as their fields; the master
  // list renders here, outside any detail panel.
  ds1LabelArt(view);
  const subtabs=subtabsFor(state.tab);
  // Enemies names its one list (Monsters) so the category reads; Attacks
  // under Attacks would only repeat the tab.
  const strip=subtabBar({tabs:subtabs,showSingle:state.tab==="enemies",active:state.sub,label,order:(state.tab==="sound"||state.tab==="scripts")?"given":undefined,change:id=>navigate(state.tab,id)});
  return LexeditorUI.stack(strip,view);
}
function viewportHooks(){
  return {readOnly:state.readOnly||state.mapTab==='collision',transforms:state.mapTab!=='collision',collision:{high:state.mapCollisionHigh===true,low:state.mapCollisionLow===true},navigation:state.mapNavigation,regions:state.mapRegions,
    onSelect:(key,info)=>{state.mapSelected=key;state.mapInfo=info||null;refreshViewportBar();
    if(state.mapTab==='collision'){
      if(info?.kind==='Collision'&&info.model!==state.collision?.model)void chooseCollision({model:info.model,mesh:0});
      return;
    }
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
  const light=state.mapInfo?.kind==="Light";
  for(const button of buttons){
    const action=button.dataset.viewportAction;
    if(action==="duplicate"){
      button.disabled=state.readOnly||state.mapBusy||!movable;
      button.title=state.readOnly?"Open a mod project to add placements"
        :!state.mapSelected?"Select a placement in the viewport first"
        :!movable?"This placement cannot be duplicated here"
        :"Copy this placement under the next free ID";
    }else if(action==="remove"){
      button.disabled=state.readOnly||state.mapBusy||!movable||playerStart;
      button.title=playerStart?"The player start cannot be removed"
        :state.readOnly?"Open a mod project to remove placements"
        :!state.mapSelected?"Select a placement in the viewport first"
        :!movable?"This placement cannot be removed here"
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
  if(state.tab!=="maps")return;
  for(let i=0;i<3;i++){
    const input=document.querySelector(`[data-maps-detail] [data-field-key="${names[i]}"]`);
    if(input&&input.isConnected)input.value=String(afters[i]);
  }
}
async function refreshMapsAfterUndo(entry){
  if((entry.edits||[entry]).some(edit=>String(edit.table).startsWith('CollisionMesh|'))){
    await refreshCollision();return;
  }
  const edits=entry.edits||[entry];
  const moved=new Map();
  let namesChanged=false;
  for(const edit of edits){
    if(!String(edit.table).endsWith(".msb"))continue;
    const row=state.rows.find(row=>row.table===edit.table&&row.id===edit.id);
    if(row&&state.mapView?.map===edit.table){
      const part=state.mapView.parts.find(part=>part.key===edit.id);
      if(part&&String(edit.id).startsWith("region:")&&["shapeType","width","height","depth","radius"].includes(edit.field)){
        part.shape=row.values.shapeType;
        part.dimensions=Object.fromEntries(["width","height","depth","radius"].filter(name=>row.values[name]!==undefined).map(name=>[name,row.values[name]]));
        viewportCtl?.updateRegion?.(edit.id,part.shape,part.dimensions);
      }
      if(part&&edit.field==="hitFilter"){
        part.hitFilter=row.values.hitFilter;
        viewportCtl?.updateCollision?.(edit.id,part.hitFilter);
      }
      if(part&&edit.field.startsWith("scale")){
        part.scale=[row.values.scaleX,row.values.scaleY,row.values.scaleZ];
        viewportCtl?.scaleTo?.(edit.id,part.scale);
      }
    }
    if(edit.field==="npcId")namesChanged=true;
    else if(["posX","posY","posZ","rotX","rotY","rotZ"].includes(edit.field))
      moved.set(edit.table+":"+edit.id,{map:edit.table,id:edit.id});
  }
  for(const {map,id} of moved.values()){
    const lightRow=String(id).startsWith("light:");
    const messageRow=String(id).startsWith("message:");
    const row=state.rows.find(entry=>entry.table===map&&entry.id===id);
    let pos=null,rot=null;
    if(row){pos=[row.values.posX,row.values.posY,row.values.posZ];rot=[row.values.rotX,row.values.rotY,row.values.rotZ];}
    else if((lightRow||messageRow)&&state.row&&state.row.table===map&&state.row.id===id){
      // Lights and messages ride no record list; the freshly
      // undone detail row carries the position back instead.
      const val=lookup=>state.row.fields.find(item=>item.key===lookup)?.value;
      pos=[val("posX"),val("posY"),val("posZ")];
    }
    if(!pos)continue;
    if(state.mapView&&map===state.mapView.map){
      const part=state.mapView.parts.find(entry=>entry.key===id)||(lightRow?(state.mapView.lights||[]).find(entry=>entry.key===id):messageRow?(state.mapView.messages||[]).find(entry=>entry.key===id):null);
      if(part){part.pos=pos;if(!lightRow&&!messageRow)part.rot=rot;}
      if(!messageRow)viewportCtl?.moveTo?.(id,pos);
      if(!lightRow&&!messageRow)viewportCtl?.turnTo?.(id,rot);
    }
    syncPlacementRow(map,id,["posX","posY","posZ"],pos);
    if(!lightRow&&!messageRow)syncPlacementRow(map,id,["rotX","rotY","rotZ"],rot);
  }
  if(namesChanged){
    // An enemy swap can move a placement between the NPC and enemy
    // directory and change the map\u2019s own counts.
    state.mapList=(await api("/api/table?tab=viewport")).rows;
    await loadDirectory().catch(notify);
  }
  refreshMapSide();refreshDirectory();refreshMapsDetail();
}
function viewportMove(map,key,pos){
  if(state.readOnly||state.mapBusy||!state.mapView)return Promise.resolve(false);
  const names=["posX","posY","posZ"];
  const before=(state.mapView.parts.find(part=>part.key===key)||(state.mapView.lights||[]).find(part=>part.key===key))?.pos||[0,0,0];
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
      const part=state.mapView.parts.find(entry=>entry.key===key)||(state.mapView.lights||[]).find(entry=>entry.key===key);
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
  if(String(key).startsWith("light:"))return Promise.resolve(false);
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
  refreshMapSide();refreshDirectory();refreshMapsDetail();
  const host=document.querySelector("[data-viewport-host]");
  if(host&&state.tab==="maps"){
    viewportCtl=null;
    const token=++viewportMount;
    const ctl=await Ds1Viewport.mount(host,map,state.mapView,viewportHooks()).catch(failMount(host,"Could not load the map."));
    if(token!==viewportMount){ctl?.dispose?.();return;}
    viewportCtl=ctl;
    viewportCtl?.setGizmoMode?.(state.mapGizmo);
    viewportCtl?.setCollisionLayers?.(state.mapCollisionHigh===true,state.mapCollisionLow===true);
    viewportCtl?.setMapOverlays?.(state.mapNavigation,state.mapRegions);
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
    await reloadViewport(map,result.row.id);
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
    if(part.kind==="Player")continue;
    if(!part.model)continue;
    const type=Number(part.key.split(":")[0]);
    const identity=`${type}:${part.model}`;
    const entry=counts.get(identity)||{model:part.model,type,kind:part.kind,count:0};
    entry.count++;counts.set(identity,entry);
  }
  const models=[...counts.values()].sort((a,b)=>a.kind.localeCompare(b.kind)||a.model.localeCompare(b.model));
  LexeditorUI.choicePopover({label:"Model",
    choices:[...models.map(entry=>({label:`${entry.kind}: ${entry.model} (${entry.count})`,value:{model:entry.model,type:entry.type}})),
      ...(state.mapView.createKinds||[]).map(kind=>({label:kind.label,value:kind.id}))],
    select:async choice=>{
      state.mapBusy=true;refreshViewportBar();
      try{
        const at=viewportCtl?.aim?.()||[0,0,0];
        const result=await api("/api/placements/create",{map,
          ...(typeof choice==="string"?{model:choice}:choice),pos:at,rot:[0,0,0]});
        state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;state.nativeRules=result.nativeRules||state.nativeRules;
        await reloadViewport(map,result.row.id);
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
  if(state.mapTab==='collision'){await loadCollision();return;}
  clampMapSelection();
  await loadDetail();
}
// The selected placement always belongs to the open map: switching maps,
// adding or removing placements re-points it instead of stranding it.
function clampMapSelection(){
  const here=state.rows.filter(row=>row.table===state.mapId);
  // Messages ride the view, not the record lists: a selection on
  // one survives the clamp like a placement's does.
  const viewKeys=state.mapView?[...(state.mapView.messages||[]),...(state.mapView.lights||[])].map(entry=>`${state.mapView.map}:${entry.key}`):[];
  if(!here.some(row=>key(row)===state.selected)&&!viewKeys.includes(state.selected))state.selected=here[0]?key(here[0]):null;
  const row=state.rows.find(row=>key(row)===state.selected);
  state.mapSelected=row?row.id:viewKeys.includes(state.selected)?state.selected.slice(state.mapId.length+1):null;
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
  if(!row){
    if(state.tab==="maps"&&/\.msb:light:/.test(placementKey))return selectLight(placementKey,fromCanvas);
    if(state.tab==="maps"&&/\.msb:message:/.test(placementKey))return selectMessage(placementKey,fromCanvas);
    return;
  }
  if(placementKey===state.selected&&state.row&&key(state.row)===placementKey)return;
  state.selected=placementKey;state.mapSelected=row.id;
  if(!fromCanvas&&viewportCtl)viewportCtl.select(state.mapSelected);
  await loadDetail().catch(notify);
  refreshMapSide();refreshDirectory();refreshMapsDetail();
}
// Lights ride the open map view, not the record lists: the key after
// the first colon is the viewport id (light:N).
async function selectLight(lightKey,fromCanvas){
  if(lightKey===state.selected&&state.row&&key(state.row)===lightKey)return;
  state.selected=lightKey;state.mapSelected=lightKey.slice(lightKey.indexOf(":")+1);
  if(!fromCanvas&&viewportCtl)viewportCtl.select(state.mapSelected);
  await loadDetail().catch(notify);
  refreshMapSide();refreshDirectory();refreshMapsDetail();
}
function refreshMapSide(){
  if(state.tab!=="maps")return;
  const side=document.querySelector("[data-maps-side]");
  if(!side){render();return;}
  stopPaneFit(side);
  side.replaceChildren(mapsStrip(),mapsPane());
}
const DIRECTORY_PARAM_TABS=new Set(["drops","treasure"]);
const DIRECTORY_TABS=["all","drops","treasure","npcs","enemies"];
const isDirectoryFoe=row=>(row.values.kind==="Enemy"||row.values.kind==="Dummy enemy")&&!row.values.isNpc;
const isDirectoryFriend=row=>(row.values.kind==="Enemy"||row.values.kind==="Dummy enemy")&&row.values.isNpc;
let dirTabRestored=false;
async function loadDirectory(){
  if(!dirTabRestored){dirTabRestored=true;try{const saved=localStorage.getItem("lex-ds1-directory-tab");if(saved)state.dirTab=saved;}catch(_error){}}
  if(!DIRECTORY_TABS.includes(state.dirTab))state.dirTab="all";
  if(state.dirTab==="all"){state.dirRows=[];return;}
  if(state.dirTab==="npcs")state.dirRows=state.rows.filter(isDirectoryFriend);
  else if(state.dirTab==="enemies")state.dirRows=state.rows.filter(isDirectoryFoe);
  else state.dirRows=(await api("/api/table?tab="+encodeURIComponent(state.dirTab))).rows;
  const pages=Math.max(1,Math.ceil(directoryMatches().length/state.pageSize));
  if(state.dirPage>pages-1)state.dirPage=pages-1;
}
function directoryTabs(){
  return [{id:"all",label:"All",help:"Every placement on the open map: enemies, objects and player starts. Pick one to edit it."},
    ...state.worldTabs.filter(entry=>DIRECTORY_PARAM_TABS.has(entry.id)),
    {id:"npcs",label:"NPCs",help:"Named characters who do not fight you: merchants, blacksmiths and quest givers. Pick one to see it in the map."},
    {id:"enemies",label:"Enemies",help:"Everything placed that fights you, bosses included. Pick one to see it in the map."}];
}
// The directory shows a reference name split across columns: the item (or
// the enemy standing there) under Name, its owner under Owner, and the map
// list's own name under Map. The row's full name stays untouched for
// sorting and the detail pane.
function dirRowName(row){
  if(DIRECTORY_PARAM_TABS.has(state.dirTab))return row.values.item||row.name;
  return row.values.who||row.display?.npcId||row.values.part||row.name;
}
function dirRowMap(row){
  return (row.values.mapNames||[]).join(", ");
}
function directoryMatches(){
  const query=state.dirQuery.toLowerCase();
  let filtered=state.dirRows.filter(row=>(row.id+" "+row.name+" "+(row.range||"")+" "+dirRowMap(row)).toLowerCase().includes(query));
  // Local keeps only rows from the open map. Placements name their map;
  // lots resolve through their dropping NPCs, and interaction rows through
  // object activations, including the object's inherited model parameter.
  if(state.dirLocal){
    if(state.dirTab==="npcs"||state.dirTab==="enemies")filtered=filtered.filter(row=>row.table===state.mapId);
    else if(DIRECTORY_PARAM_TABS.has(state.dirTab))filtered=filtered.filter(row=>(row.values.maps||[]).includes(state.mapId));
  }
  return filtered.sort((a,b)=>LexeditorUI.compareRecords(a,b,tabSort())||(a.id>b.id?1:a.id<b.id?-1:0));
}
function directoryPane(){
  return el("div",{"data-maps-dir":"",style:"display:flex;flex-direction:column;min-height:0;flex:1 1 auto;min-width:0;"},directoryStrip(),...directoryList());
}
function refreshDirectory(){
  if(state.tab!=="maps")return;
  const pane=document.querySelector("[data-maps-dir]");
  if(!pane)return;
  stopPaneFit(pane);
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
  const supported=state.dirTab==="npcs"||state.dirTab==="enemies"||DIRECTORY_PARAM_TABS.has(state.dirTab);
  const node=LexeditorUI.pagerToggle({label:"Local?",
    title:supported?"Show only rows from the open map":"All placements already belong to the open map",
    checked:state.dirLocal,disabled:!supported,
    change:value=>{state.dirLocal=value;state.dirPage=0;refreshDirectory();}});
  node.setAttribute("data-dir-local","");
  node.querySelector("input").setAttribute("data-lex-view-filter","");
  return node;
}
function directoryList(){
  if(state.dirTab==="all")return [placementsPane()];
  const matches=directoryMatches();
  const size=paneSize("dir");
  const pages=Math.max(1,Math.ceil(matches.length/size));
  if(state.dirPage>pages-1)state.dirPage=pages-1;
  const shown=matches.slice(state.dirPage*size,(state.dirPage+1)*size);
  const param=DIRECTORY_PARAM_TABS.has(state.dirTab);
  const select=(row,event)=>{
    if(event&&(event.shiftKey||event.ctrlKey||event.metaKey))return;
    if(param)void selectDirectoryParam(row);
    else void selectPlacement(key(row),false);
  };
  const columns=[{key:"name",label:"Name",grow:1,render:row=>dirRowName(row)}];
  if(state.dirTab==="drops")columns.push({key:"owner",label:"Owner",grow:1,
    sortValue:row=>row.values.owner||"",render:row=>row.values.owner||""});
  // Local shows only the open map's rows, so the Map column would repeat
  // the same map on every row; it returns when unticked.
  if(!state.dirLocal)columns.push({key:"map",label:"Map",grow:1,
    sortValue:row=>dirRowMap(row),render:row=>dirRowMap(row)});
  if(!param)columns.push(goToCell(row=>`Show ${dirRowName(row)} in the map viewport`,row=>goToPlacement(row.table,key(row))));
  else if(state.dirTab==="drops")columns.push(goToCell(row=>`Show where ${dirRowName(row)} drops`,row=>goToDrop(row.id)));
  // Search on its own row up top, like the animations panes; the pager
  // below the list only pages and filters.
  const list=columnList({rows:shown,key,selected:state.selected,select,columns,class:"lex-list-fill"});
  const pager=LexeditorUI.compactPager({pages,page:state.dirPage,total:matches.length,pageSize:size,
    filters:[directoryLocalRow()],
    change:value=>{state.dirPage=value;refreshDirectory();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizePaneRows(list,size,false);
  fitPaneList(list,"dir",size,both);
  return [LexeditorUI.bottomSearch({key:"maps-directory",value:state.dirQuery,label:"Search the world",
      change:value=>{state.dirQuery=value;state.dirPage=0;refreshDirectory();}}),
    both];
}
async function selectDirectoryParam(row){
  if(key(row)===state.selected&&state.row&&key(state.row)===key(row))return;
  state.selected=key(row);
  await loadDetail().catch(notify);
  refreshMapSide();refreshDirectory();refreshMapsDetail();
}
function mapsStrip(){
  return LexeditorUI.tabStrip({tabs:[{id:"maps",label:"Maps"},{id:"placements",label:"Placements"},{id:"lights",label:"Lights"},{id:"messages",label:"Messages"},{id:"collision",label:"Collision"}],
    active:state.mapTab,label:"Map views",change:async id=>{
      await edits;const wasCollision=state.mapTab==='collision';state.mapTab=id;
      if(id==='collision'){await chooseCollision({});return;}
      if(wasCollision){state.collision=null;clampMapSelection();await loadDetail();render();}
      else refreshMapSide();
    }});
}
async function loadCollision(options={}){
  const previous=state.collision;
  const token=navigation,map=state.mapId;
  const models=Object.entries(state.mapView?.models||{}).filter(([,value])=>value.type===5).map(([name])=>name);
  const selectedModel=state.mapView?.parts.find(part=>part.key===state.mapSelected&&part.kind==='Collision')?.model;
  const next={model:previous?.model||selectedModel||models[0],layer:'high',mesh:0,kind:'vertices',
    query:'',page:0,pageSize:20,...previous,...options};
  if(!models.includes(next.model))next.model=models[0];
  state.collision=next;state.selection=[];
  state.mapCollisionHigh=next.layer==='high';state.mapCollisionLow=next.layer==='low';
  next.rows=[];next.error='';next.loading=true;state.row=null;
  const current=()=>state.collision===next&&state.tab==='maps'&&state.mapTab==='collision'&&state.mapId===map&&navigation===token;
  if(!next.model){next.error='This map has no collision models.';next.loading=false;return true;}
  try{
    const result=await api(`/api/map/collision?map=${encodeURIComponent(map)}&model=${encodeURIComponent(next.model)}&layer=${next.layer}&mesh=${next.mesh}&kind=${next.kind}`);
    if(!current())return false;
    Object.assign(next,result);
    state.selected=next.rows.some(row=>key(row)===(options.selected||state.selected))?(options.selected||state.selected):next.rows[0]?key(next.rows[0]):null;
    await loadDetail();
    return current();
  }catch(error){if(current()){next.error=error.message;state.row=null;return true;}return false;}
  finally{next.loading=false;}
}
async function chooseCollision(options){
  await edits;
  if(state.tab!=='maps'||state.mapTab!=='collision')return;
  const loaded=loadCollision(options);render();
  if(!await loaded)return;
  state.mapCollisionHigh=state.collision.layer==='high';state.mapCollisionLow=state.collision.layer==='low';
  viewportCtl?.setCollisionLayers?.(state.mapCollisionHigh,state.mapCollisionLow);
  render();markCollisionPoint(true);
}
function markCollisionPoint(focus=false){
  const collision=state.collision;
  const part=state.mapView?.parts.find(part=>part.model===collision?.model&&part.key===state.mapSelected)
    ||state.mapView?.parts.find(part=>part.model===collision?.model);
  viewportCtl?.point?.(part?.key,state.row?.previewPosition,focus);
}
async function refreshCollision(){
  if(state.tab!=='maps'||state.mapTab!=='collision')return;
  const table=state.collision?.table;
  for(const cached of recordRows.keys())if(cached.startsWith(`${table}:`))recordRows.delete(cached);
  if(!await loadCollision())return;
  render();
  if(state.collision?.model)await viewportCtl?.reloadCollision?.(state.collision.model);
  markCollisionPoint();
}
function collisionDetail(){
  const collision=state.collision;
  const row=state.row;
  const noun=collision?.kind==='faces'?'face':'vertex';
  if(collision?.loading)return detailPanel({title:`Collision ${noun}`,body:[LexeditorUI.loadingPanel({label:'Loading collision records'})]});
  const derived=collision?.kind==='faces'&&collision.derivedFaces;
  const actions=['add','duplicate','remove'].map(action=>el('button',{type:'button',class:'lex-header-icon',
    'aria-label':`${action[0].toUpperCase()+action.slice(1)} collision ${noun}`,
    title:derived?collision.faceEditReason:`${action[0].toUpperCase()+action.slice(1)} collision ${noun}`,
    disabled:state.readOnly||state.rowBusy||derived||!!collision?.error||(!row&&action!=='add'),
    onclick:()=>changeCollisionStructure(action)},
    action==='add'?LexeditorUI.addIcon():action==='duplicate'?LexeditorUI.copyIcon():LexeditorUI.removeIcon()));
  if(!row||!String(row.table).startsWith('CollisionMesh|'))return detailPanel({title:`Collision ${noun}`,actions,
    body:[LexeditorUI.detailNote(collision?.error||`Select a ${noun}.`)]});
  return detailPanel({title:row.name,actions,body:[...fieldSections(row)].map(([title,body])=>detailSection({title,body}))});
}
function changeCollisionStructure(action){
  if(state.readOnly||state.rowBusy)return;
  const collision=state.collision,table=collision.table,kind=collision.kind;
  if(kind==='faces'&&collision.derivedFaces)return;
  const index=Number(state.row?.id.split(':')[1]||0);
  const token=navigation;
  const current=()=>navigation===token&&state.tab==='maps'&&state.mapTab==='collision'&&state.collision===collision;
  state.rowBusy=true;state.pending++;shell.refresh();
  edits=edits.then(async()=>{
  try{
    const before=(await api(`/api/map/collision/state?table=${encodeURIComponent(table)}`)).mesh;
    const after=structuredClone(before);
    const faceArrays=['faces','materialIndices','materialIndices16'].filter(name=>Array.isArray(after[name]));
    let selected=index;
    if(action==='remove'){
      if(after[kind].length===1)throw new Error(`Keep at least one ${kind==='vertices'?'vertex':'face'} in a collision mesh. Remove the collision placement to remove it from the map.`);
      if(kind==='vertices'){
        const connected=collision.derivedFaces?0:after.faces.filter(face=>face.slice(0,3).includes(index)).length;
        if(collision.derivedFaces&&after.vertices.length<=3)throw new Error('Keep at least three distinct vertices in a convex collision.');
        if(!collision.derivedFaces&&connected===after.faces.length)throw new Error('Removing this vertex would leave no faces. Remove the collision placement instead.');
        if(connected&&!await confirmAction({title:'Remove connected faces?',message:`Removing Vertex ${index} also removes ${connected} connected faces.`,confirmLabel:'Remove',cancelLabel:'Cancel'}))return;
        after.vertices.splice(index,1);after.flags.splice(index,1);
        if(!collision.derivedFaces){
          const keep=after.faces.map(face=>!face.slice(0,3).includes(index));
          for(const name of faceArrays)after[name]=after[name].filter((row,i)=>keep[i]);
          after.faces=after.faces.map(face=>face.map((value,i)=>i<3&&value>index?value-1:value));
        }
      }else for(const name of faceArrays)after[name].splice(index,1);
      selected=Math.min(index,after[kind].length-1);
    }else{
      selected=after[kind].length;
      if(kind==='vertices'){
        const center=[0,1,2].map(axis=>after.vertices.reduce((sum,v)=>sum+v[axis],0)/after.vertices.length);
        after.vertices.push(action==='duplicate'?[...after.vertices[index]]:[...center,after.vertices[0][3]]);
        after.flags.push([...after.flags[action==='duplicate'?index:0]]);
      }else{
        if(action==='add'&&after.vertices.length<3)throw new Error('Add at least three vertices before adding a face.');
        after.faces.push(action==='duplicate'?[...after.faces[index]]:[0,1,2,after.faces[0][3]]);
        for(const name of faceArrays)if(name!=='faces')after[name].push([...after[name][action==='duplicate'?index:0]]);
      }
    }
    const snapshotBytes=JSON.stringify(before).length+JSON.stringify(after).length;
    if(snapshotBytes>16*1024*1024)throw new Error('This structural edit exceeds the 16 MiB undo limit.');
    const result=await api('/api/map/collision/state',{table,mesh:after});
    state.dirty=result.dirtyCount;state.changes=result.changes||state.changes;
    fieldHistory.record({collision:true,table,before,after,snapshotBytes});
    if(current()){
      state.selected=`${table}:${kind==='vertices'?'v':'f'}:${selected}`;
      await refreshCollision();
    }
  }catch(error){notify(error);}
  finally{state.rowBusy=false;state.pending--;render();}
  });
  return edits;
}
function renderCollision(current){
  const collision=state.collision||{rows:[],error:'Choose Collision again to load this map.',kind:'vertices'};
  const selector=(label,value,choices,change)=>detailField({label,control:el('select',{'aria-label':label,value,
    onchange:event=>change(event.target.value)},...choices.map(([id,name])=>el('option',{value:id,selected:String(id)===String(value)},name)))});
  const header=LexeditorUI.stack({fill:false,compact:true},mapsStrip(),
    selector('Collision model',collision.model,Object.entries(state.mapView?.models||{}).filter(([,item])=>item.type===5).map(([name])=>[name,name]),model=>chooseCollision({model,mesh:0,page:0})),
    selector('Layer',collision.layer,[['high','High collision'],['low','Low collision']],layer=>chooseCollision({layer,mesh:0,page:0})),
    selector('Mesh',collision.mesh,(collision.meshes||[]).map(mesh=>[mesh.id,mesh.name]),mesh=>chooseCollision({mesh:Number(mesh),page:0})),
    LexeditorUI.tabStrip({tabs:[{id:'vertices',label:'Vertices'},{id:'faces',label:'Faces'}],active:collision.kind,label:'Collision records',
      change:kind=>chooseCollision({kind,page:0})}));
  const preview=collision.preview?.isConnected?collision.preview:mapsViewportPane(current);
  collision.preview=preview;
  const rows=collision.rows.filter(row=>row.name.toLowerCase().includes((collision.query||'').toLowerCase()));
  // names: collision vertices and faces have array indices, not stored names.
  const view=pagedListDetail({className:'ds1-collision',rows,key,selected:state.selected,slots:false,noun:collision.kind,
    tableAdd:false,page:collision.page,pageSize:collision.pageSize,rowsKey:'ds1-collision-'+collision.kind,
    splitKey:'ds1-collision',minLeft:240,minMiddle:280,minRight:360,masterHeader:header,middlePanel:()=>preview,
    search:{key:'ds1-collision-search',value:collision.query||'',label:'Search '+collision.kind,change:value=>{collision.query=value;collision.page=0;render();}},
    sync:next=>{collision.page=next.page;collision.pageSize=next.pageSize;state.selection=next.selection||[];},
    change:next=>{collision.page=next.page;collision.pageSize=next.pageSize;if(next.reason==='pins')view.refreshMaster();else render();},
    master:({rows,selected,select})=>collision.loading?LexeditorUI.loadingPanel({label:'Loading collision records'}):columnList({rows,key,selected,
      columns:[{key:'name',label:'Name',grow:1}],
      decorateRow:(node,row)=>{LexeditorUI.decorateSearchCandidate(node,{type:`ds1-${row.table}`,value:row.id,label:row.name});return node;},
      select:async(row,event)=>{await edits;state.selected=key(row);await loadDetail();select(row,event);markCollisionPoint(true);shell.refresh();}}),
    describePinnedCell,commitPinnedCell,detail:()=>collisionDetail(),emptyDetail:()=>collisionDetail()});
  state.pagedView=view;return view;
}
function mapsPane(){
  if(state.mapTab==="placements")return directoryPane();
  if(state.mapTab==="lights")return lightsPane();
  if(state.mapTab==="messages")return messagesPane();
  return mapsListPane();
}
// The right panel always shows the current selection's details, like
// the animations tab: no Selection tab needed.
function mapsDetailBox(){
  const panel=detail();
  panel.style.flex="1 1 auto";panel.style.minHeight="0";
  return el("div",{"data-maps-detail":"",style:"display:flex;flex-direction:column;flex:1 1 auto;min-height:0;overflow:auto;"},panel);
}
function refreshMapsDetail(){
  if(state.tab!=="maps")return;
  const pane=document.querySelector("[data-maps-detail]");
  if(!pane){render();return;}
  pane.replaceWith(mapsDetailBox());
}
function mapsListPane(){
  selectVisibleRecord=null;
  const columns=[
    {key:"name",label:"Name",sortable:true,grow:1},
    {key:"npcs",label:"NPCs",sortable:true,numeric:true,sortValue:row=>row.values.npcs,render:row=>String(row.values.npcs)},
    {key:"drops",label:"Drops",sortable:true,numeric:true,sortValue:row=>row.values.drops,render:row=>String(row.values.drops)},
    {key:"enemies",label:"Enemies",sortable:true,numeric:true,sortValue:row=>row.values.enemies,render:row=>String(row.values.enemies)}];
  // The order belongs to the whole list, not to the page: sort before slicing.
  const sort=state.mapListSort;
  const here=sort?[...state.mapList].sort((left,right)=>{
    const column=columns.find(entry=>entry.key===sort.key)||columns[0];
    const value=row=>typeof column.sortValue==="function"?column.sortValue(row):row[column.key];
    const first=value(left),second=value(right);
    const result=typeof first==="number"&&typeof second==="number"?first-second
      :String(first).localeCompare(String(second),undefined,{numeric:true,sensitivity:"base"});
    return result*sort.dir;
  }):state.mapList;
  const size=paneSize("maps");
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.mapListPage>pages-1)state.mapListPage=pages-1;
  const shown=here.slice(state.mapListPage*size,(state.mapListPage+1)*size);
  const list=columnList({rows:shown,key:row=>row.id,selected:state.mapId,select:row=>chooseMap(row.id),
    class:"lex-list-fill",sortState:sort||undefined,
    sort:columnKey=>{state.mapListSort={key:columnKey,
      dir:state.mapListSort?.key===columnKey?-state.mapListSort.dir:1};state.mapListPage=0;refreshMapSide();},
    columns});
  const pager=LexeditorUI.compactPager({pages,page:state.mapListPage,total:here.length,pageSize:size,
    change:value=>{state.mapListPage=value;refreshMapSide();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizePaneRows(list,size,false);
  fitPaneList(list,"maps",size,both);
  return both;
}
function placementFilterMatches(row){
  const filter=state.mapPlacementFilter||"all";
  if(filter==="all")return true;
  const viewPart=state.mapView?.parts.find(entry=>entry.key===row.id);
  const kind=row.values?.kind||viewPart?.kind||"";
  const hit=row.values?.hitFilter??viewPart?.hitFilter;
  if(filter==="collisions")return kind==="Collision"||kind==="Connect collision";
  if(filter==="death")return hit===13||hit===14||hit===15;
  if(filter==="pieces")return kind==="Map piece";
  if(filter==="navigation")return kind==="Navigation";
  if(filter==="regions")return kind==="Region";
  if(filter==="events")return String(row.id).startsWith("event");
  return true;
}
function placementsPane(){
  const here=sortedRows().filter(row=>row.table===state.mapId&&placementFilterMatches(row));
  const size=paneSize("placements");
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.page>pages-1)state.page=pages-1;
  const shown=here.slice(state.page*size,(state.page+1)*size);
  const select=(row,event)=>{
    if(event&&(event.shiftKey||event.ctrlKey||event.metaKey))return;
    selectPlacement(key(row),false);
  };
  selectVisibleRecord=select;
  const columns=[{key:"name",label:"Name",grow:1}];
  // Names never carry the map: it gets its own column, shared with the
  // directory, but only when the rows span more than one map. This list
  // is scoped to the open map, so the column stays hidden here.
  if(new Set(here.map(row=>row.table)).size>1)columns.push({key:"map",label:"Map",grow:1,
    sortValue:row=>dirRowMap(row),render:row=>dirRowMap(row)});
  columns.push(goToCell(row=>`Show ${row.name} in the map viewport`,row=>goToPlacement(row.table,key(row))));
  const list=columnList({rows:shown,key,selected:state.selected,select,class:"lex-list-fill",columns});
  const kindFilter=LexeditorUI.pagerSelect({label:"Show",value:state.mapPlacementFilter||"all",
    options:[{id:"all",label:"All placements"},{id:"collisions",label:"Collisions"},{id:"death",label:"Death zones"},{id:"pieces",label:"Map pieces"},{id:"navigation",label:"Navigation"},{id:"regions",label:"Regions"},{id:"events",label:"Events"}],
    change:value=>{state.mapPlacementFilter=value;state.page=0;refreshMapSide();}});
  const pager=LexeditorUI.compactPager({pages,page:state.page,total:here.length,pageSize:size,
    filters:[kindFilter],change:value=>{state.page=value;refreshMapSide();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizePaneRows(list,size,false);
  fitPaneList(list,"placements",size,both);
  return LexeditorUI.stack(
    LexeditorUI.bottomSearch({key:"maps-placements",value:state.query,label:"Search placements",
      change:value=>{state.query=value;state.page=0;
        // Filtering picks its first match, as the old list did, but
        // stays on this tab: the reader asked to search, not to leave.
        // The pick routes through selection so the details follow it.
        const matches=sortedRows().filter(row=>row.table===state.mapId&&placementFilterMatches(row));
        if(matches.length&&!matches.some(row=>key(row)===state.selected)){
          void selectPlacement(key(matches[0]),false);
        }else refreshMapSide();}}),
    both);
}
// The open map's lights, straight from its view: no fetch, and the
// list dies with the map, so a map switch cannot strand it.
function lightsPane(){
  const map=state.mapView&&state.mapView.map===state.mapId?state.mapView.map:null;
  const pool=map?(state.mapView.lights||[]).map(entry=>({id:entry.key,table:map,name:entry.name,
    values:{preset:entry.preset}})):[];
  const needle=(state.lightQuery||"").trim().toLocaleLowerCase();
  const here=pool.filter(row=>!needle||String(row.name||"").toLocaleLowerCase().includes(needle))
    .sort((a,b)=>String(a.name||"").localeCompare(String(b.name||""),undefined,{numeric:true,sensitivity:"base"}));
  const size=paneSize("lights");
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.lightPage==null)state.lightPage=0;
  if(state.lightPage>pages-1)state.lightPage=pages-1;
  const shown=here.slice(state.lightPage*size,(state.lightPage+1)*size);
  const select=(row,event)=>{
    if(event&&(event.shiftKey||event.ctrlKey||event.metaKey))return;
    selectLight(key(row),false);
  };
  const columns=[{key:"name",label:"Name",grow:1},
    {key:"preset",label:"Look",numeric:true,sortValue:row=>row.values.preset,render:row=>String(row.values.preset)}];
  columns.push(goToCell(row=>`Show ${row.name} in the map viewport`,row=>goToLight(key(row))));
  const list=columnList({rows:shown,key,selected:state.selected,select,class:"lex-list-fill",columns});
  const pager=LexeditorUI.compactPager({pages,page:state.lightPage||0,total:here.length,pageSize:size,
    change:value=>{state.lightPage=value;refreshMapSide();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizePaneRows(list,size,false);
  fitPaneList(list,"lights",size,both);
  return LexeditorUI.stack(
    LexeditorUI.bottomSearch({key:"maps-lights",value:state.lightQuery||"",label:"Search lights",
      change:value=>{state.lightQuery=value;state.lightPage=0;refreshMapSide();}}),
    both);
}
async function goToLight(lightKey){
  await selectLight(lightKey,false);
  const id=lightKey.slice(lightKey.indexOf(":")+1);
  if(viewportCtl)viewportCtl.focus(id);
  else state.mapFocus=id;
}
// The open map's developer soapstone messages, straight from its
// view like lights: no fetch, and the list dies with the map, so a
// map switch cannot strand it. Text previews resolve through the
// Text tab's Blood writing entries; the view carries no words itself.
const messageTextCache=new Map();
async function messageTextPreview(textId){
  if(messageTextCache.has(textId))return messageTextCache.get(textId);
  try{
    const row=(await api(`/api/row?table=Blood_writing_.fmg&id=${textId}`)).row;
    const text=row.fields.find(field=>field.key==="text")?.value||"";
    const first=String(text).split("\n",1)[0].slice(0,120);
    messageTextCache.set(textId,first||`(no message text ${textId})`);
  }catch(_error){messageTextCache.set(textId,`(no message text ${textId})`);}
  return messageTextCache.get(textId);
}
function messagePreviewCell(row){
  const textId=row.values?.text;
  const cell=el("span",{class:"ds1-message-preview","data-message-text":String(textId??"")},"…");
  if(textId===null||textId===undefined){cell.textContent="—";return cell;}
  messageTextPreview(textId).then(preview=>{if(cell.isConnected)cell.textContent=preview;});
  return cell;
}
function messagesPane(){
  const map=state.mapView&&state.mapView.map===state.mapId?state.mapView.map:null;
  if(state.mapView&&state.mapView.map===state.mapId&&state.mapView.messages===undefined)
    return LexeditorUI.detailNote("Messages are not available in this build yet.");
  const pool=map?(state.mapView.messages||[]).map(entry=>({id:entry.key,table:map,name:entry.name,
    values:{text:entry.textId},message:entry})):[];
  const needle=(state.messageQuery||"").trim().toLocaleLowerCase();
  const here=pool.filter(row=>!needle||String(row.name||"").toLocaleLowerCase().includes(needle)
    ||String(messageTextCache.get(row.values.text)??"").toLocaleLowerCase().includes(needle))
    .sort((a,b)=>String(a.name||"").localeCompare(String(b.name||""),undefined,{numeric:true,sensitivity:"base"}));
  const size=paneSize("messages");
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.messagePage==null)state.messagePage=0;
  if(state.messagePage>pages-1)state.messagePage=pages-1;
  const shown=here.slice(state.messagePage*size,(state.messagePage+1)*size);
  const select=(row,event)=>{
    if(event&&(event.shiftKey||event.ctrlKey||event.metaKey))return;
    selectMessage(key(row),false);
  };
  const columns=[{key:"name",label:"Name",grow:1},
    {key:"text",label:"Message",grow:2,sortValue:row=>row.values.text,render:row=>messagePreviewCell(row)}];
  columns.push(goToCell(row=>`Show ${row.name} in the map viewport`,row=>goToMessage(key(row))));
  const list=columnList({rows:shown,key,selected:state.selected,select,class:"lex-list-fill",columns});
  const pager=LexeditorUI.compactPager({pages,page:state.messagePage||0,total:here.length,pageSize:size,
    change:value=>{state.messagePage=value;refreshMapSide();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizePaneRows(list,size,false);
  fitPaneList(list,"messages",size,both);
  return LexeditorUI.stack(
    LexeditorUI.bottomSearch({key:"maps-messages",value:state.messageQuery||"",label:"Search messages",
      change:value=>{state.messageQuery=value;state.messagePage=0;refreshMapSide();}}),
    both);
}
// Messages ride the open map view like lights: the key after the
// first colon is the viewport id (message:N).
async function selectMessage(messageKey,fromCanvas){
  if(messageKey===state.selected&&state.row&&key(state.row)===messageKey)return;
  state.selected=messageKey;state.mapSelected=messageKey.slice(messageKey.indexOf(":")+1);
  if(!fromCanvas&&viewportCtl)viewportCtl.select(state.mapSelected);
  await loadDetail().catch(notify);
  refreshMapSide();refreshDirectory();refreshMapsDetail();
}
async function goToMessage(messageKey){
  await selectMessage(messageKey,false);
  const id=messageKey.slice(messageKey.indexOf(":")+1);
  if(viewportCtl)viewportCtl.focus(id);
  else state.mapFocus=id;
}
function messagePreviewFace(row){
  const textId=row.textId;
  if(textId===null||textId===undefined)return readonlyField("—",{format:false});
  return hoverable({content:`Message ${textId}`,targetType:"ds1-text",
    targetId:`Blood_writing_.fmg:${textId}`,targetLabel:`Message ${textId} in Text`,
    "aria-label":`Message text ${textId}`,
    preview:()=>messageTextPreview(textId).then(text=>el("div",{class:"ds1-dialog-preview"},text)),
    activate:()=>navigate("text","fmg-blood-writing",`Blood_writing_.fmg:${textId}`)});
}
function messageDetail(row,groups){
  // Coordinates first like lights; the Message section below names
  // the text it shows, then the marker it stands on.
  const vectors=groups.get("Position")||[];
  const identity=[
    detailField({label:"Kind",control:readonlyField(row.kind,{format:false})}),
    detailField({label:"Message",control:messagePreviewFace(row),
      help:infoHelp("The words the sign shows, from the Text tab's Blood writing entries. Open it there to change the wording.")}),
    detailField({label:"Marker",control:readonlyField(row.point??"None (hidden)",{format:false}),
      help:infoHelp("The invisible marker this message sits on. None hides the message.")}),
    detailField({label:"Part",control:readonlyField(row.part??"—",{format:false}),
      help:infoHelp("The map piece or object this message anchors to.")})];
  return [...vectors,detailSection({title:"Message",body:[...identity,...(groups.get("Message")||[])]})];
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
  // The characters pane keeps its own page: resetting it here pushed the
  // reader back to page one on every pick. Only the animations pane
  // (a new character's list) starts over.
  state.animCharId=key(row);state.animQuery="";state.animPage=0;
  state.animScope={level:"anims"};state.taeForm=null;
  const request=++recordsRequest;
  await loadAnimView(request);
  if(state.animLeftTab!=="events"&&state.animView&&animMotionRows(state.animView).length===0)
    state.animLeftTab="chars";
  if(state.animLeftTab==="events"){
    const motion=(state.rows||[]).find(entry=>key(entry)===state.selected);
    if(motion&&motion.motion&&motion.motion.tae){
      animScopeFor(motion);
      state.selected=null;state.row=null;
      await loadAnimEvents(request);
    }else state.animLeftTab="anims";
  }
  refreshAnimLeft();refreshAnimDetail();remountAnim();
}
async function pickAnimMotion(row){
  if(!row||key(row)===state.selected)return;
  state.selected=key(row);
  // The whole left pane refreshes, not just the list: the Events tab's
  // gate follows the newly selected motion.
  refreshAnimLeft();refreshAnimDetail();remountAnim();
}
async function pickAnimEvent(row){
  if(!row||key(row)===state.selected)return;
  state.selected=key(row);
  await loadDetail().catch(notify);
  seekAnimEvent(row);
  refreshAnimList();refreshAnimDetail();
}
let pendingAnimSeek=null;
// Selecting an event moves the playhead to it, the way clicking its
// timeline marker does. A viewer still mounting an older motion keeps
// the seek pending until the motion it plays matches the events scope.
function seekAnimEvent(row){
  if(!row)return;
  pendingAnimSeek=row.id;
  flushAnimSeek();
}
function flushAnimSeek(){
  if(pendingAnimSeek==null||state.tab!=="animations")return;
  const host=document.querySelector("[data-anim-host]");
  const viewer=host?._animViewer;
  const scope=state.animScope;
  // The mount plays the drilled motion from its own binder, which may be
  // a sibling bank while the events scope names the main binder.
  const motion=scope.level==="events"?currentAnimMotion():null;
  const wanted=motion?`${currentAnimCharId()}|${motion.binder||""}|${motion.file||""}`:null;
  if(!viewer||!wanted||host._animMotion!==wanted)return;
  viewer.toEvent?.(pendingAnimSeek);
  pendingAnimSeek=null;
}
function animScopeFor(row){
  const motion=row.motion;
  // The scope's binder is the file holding the events, which is the main
  // binder by construction: links only resolve against its TAE files, so
  // a drill implies the event file is there. The motion itself may live
  // in a sibling motion bank, whose binder would find no event file.
  state.animScope={level:"events",binder:`${currentAnimCharId()}.anibnd.dcx`,tae:motion.tae,anim:motion.taeIndex,
    charName:state.animScope.charName,animName:row.name,motionFile:motion.file||null};
}
async function animDrillEvents(row){
  const motion=row.motion;
  if(!motion||!motion.tae)return;
  animScopeFor(row);
  state.animQuery="";state.animPage=0;state.selected=null;state.row=null;state.taeForm=null;
  const request=++recordsRequest;
  await loadAnimEvents(request);
  refreshAnimList();
}
// The motion the viewer plays: the drilled one on the Events pane,
// else the selected animations row.
function currentAnimMotionRef(){
  const scope=state.animScope;
  if(scope.level==="events")return {file:scope.motionFile||null,tae:scope.tae||null,taeIndex:scope.anim??null};
  const row=(state.rows||[]).find(entry=>key(entry)===state.selected);
  return row&&row.table==="AnimMotion"?row.motion:null;
}
async function switchAnimLeft(id){
  if(id===state.animLeftTab)return;
  if(id==="events"){
    if(state.animScope.level!=="events"){
      const row=(state.rows||[]).find(entry=>key(entry)===state.selected);
      if(!row||!row.motion||!row.motion.tae){refreshAnimLeft();return;}
      await animDrillEvents(row);
    }
    state.animLeftTab="events";
  }else if(id==="anims"){
    if(state.animScope.level==="events")await animBackToAnims();
    state.animLeftTab="anims";
  }else state.animLeftTab="chars";
  refreshAnimLeft();refreshAnimDetail();
}
// A timeline event marker seeks (the viewer does that) and selects
// the event: the left panel shows its Events pane, the right panel
// its details.
async function animTimelineEvent(cue){
  if(state.tab!=="animations"||!cue||!cue.id)return;
  if(state.animScope.level!=="events"){
    const row=(state.rows||[]).find(entry=>key(entry)===state.selected);
    if(!row||!row.motion||!row.motion.tae)return;
    await animDrillEvents(row);
    state.animLeftTab="events";
  }
  const found=(state.rows||[]).find(entry=>entry.id===cue.id);
  if(found&&key(found)!==state.selected){
    state.selected=key(found);
    await loadDetail().catch(notify);
  }
  if(found){
    seekAnimEvent(found);
    const size=paneSize("events");
    const index=animListMatches().findIndex(entry=>key(entry)===state.selected);
    if(index>=0)state.animPage=Math.floor(index/size);
  }
  // A cue only moves the events list: while the reader browses characters
  // or animations the panes show nothing the cue touches, and rebuilding
  // them on every cue flickered the detail labels.
  if(state.animLeftTab==="events"){refreshAnimLeft();refreshAnimDetail();}
}
async function animBackToAnims(){
  const scope=state.animScope;
  state.animScope={level:"anims",binder:scope.binder,charName:scope.charName};
  state.animQuery="";state.animPage=0;state.taeForm=null;
  state.rows=state.animView?animMotionRows(state.animView):[];
  const same=state.rows.find(row=>row.motion&&(row.motion.file||null)===(scope.motionFile||null)&&
    (row.motion.tae||null)===(scope.tae||null)&&String(row.motion.taeIndex??"")===String(scope.anim??""));
  const playable=same||state.rows.find(row=>row.motion.file)||state.rows[0];
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
// A missing skeleton or an unreadable motion is routine browsing, not an
// action failure: the reason stays in the viewport, centered the way the
// loading throbber centers while it works, no alert. A top strip over a
// black void read as a stuck load (c9999's pure-black viewport).
function failAnimMount(host,status,error){
  host.querySelector(":scope > .lex-panel-loading")?.remove();
  status.textContent="Could not load the animation.";
  const reason=LexeditorUI.notice({tone:"warning",message:error.message||String(error)});
  reason.style.maxWidth="440px";
  host.append(el("div",{"data-anim-failed":"",
    style:"position:absolute;inset:0;display:grid;place-items:center;padding:24px;"},reason));
  console.error(error);
}
function remountAnim(){
  if(state.tab!=="animations")return;
  const host=document.querySelector("[data-anim-host]");
  const timeline=document.querySelector("[data-anim-timeline]");
  const status=document.querySelector("[data-anim-status]");
  if(!host||!timeline||!status||!host.isConnected){render();return;}
  const token=++animMount;
  Ds1Anim.mount(host,currentAnimCharId(),currentAnimMotion(),timeline,status,animTimelineEvent).then(()=>flushAnimSeek()).catch(error=>{
    if(token!==animMount)return;
    failAnimMount(host,status,error);
  });
}
// A panel pages only what fits it: the fitted size caps the global
// row count, so a paginated list never grows its own scrollbar. One set
// of sizing rules for every side panel: animations and maps alike.
const PANE_FITS={char:"animCharFit",anims:"animFit",events:"animEventFit",
  dir:"dirFit",maps:"mapListFit",placements:"mapFit",lights:"mapLightFit",messages:"mapMessageFit"};
function paneSize(which){
  return Math.max(1,Math.min(state.pageSize,state[PANE_FITS[which]]||Infinity));
}
// The fit measures the paged pane (list plus pager), and the wheel turns
// pages through that same pane: fitted lists never scroll.
function fitPaneList(list,which,size,available){
  LexeditorUI.fitListPage({list,available:available||list,pageSize:size,fixedRowHeight:32,
    resize:(fittedHeight,geometry)=>{list.style.setProperty("--lex-fitted-row-height",`${geometry.rowHeight}px`);},
    change:value=>{
      if(state[PANE_FITS[which]]===value)return;
      state[PANE_FITS[which]]=value;
      if(which==="dir"||which==="maps"||which==="placements"||which==="lights"||which==="messages"){
        if(state.tab!=="maps")return;
        if(which==="dir")refreshDirectory();else refreshMapSide();
        return;
      }
      if(state.tab!=="animations")return;
      if(which==="char")refreshAnimChars();else refreshAnimList();
    }});
}
function stopPaneFit(pane){
  pane.querySelector(".lex-column-list")?.__lexFitListObserver?.disconnect?.();
}
// Fitted rows fill to the pager like paged tables: capacity tracks
// stretch the leftover and filler rows square off a short page. Maps
// side panels skip the filler rows, so a short or empty panel shows
// only its records.
function sizePaneRows(list,size,pad=true){
  if(pad)LexeditorUI.padBarrelTable(list,size);
  list.classList.add("lex-page-sized-table");
  list.style.setProperty("--lex-page-row-count",String(Math.max(size,
    list.querySelectorAll(":scope > .lex-column-list-row").length)));
  list.style.setProperty("--lex-page-font-row-count",String(size));
}
function animCharsPane(){
  const here=animCharMatches();
  const size=paneSize("char");
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
  sizePaneRows(list,size);
  fitPaneList(list,"char",size,both);
  return el("div",{"data-anim-chars":"",style:"display:flex;flex-direction:column;flex:1 1 auto;min-height:0;"},
    LexeditorUI.bottomSearch({key:"anims-characters",value:state.animCharQuery,label:"Search characters",
      change:value=>{state.animCharQuery=value;state.animCharPage=0;refreshAnimChars();}}),
    both);
}
// The animations list shows what each motion is, not a button to its
// events: the event count and the playing length, both sortable. The
// Events tab (or its timeline markers) still drills into the cues.
function animEventsCountCell(){
  return {key:"events",label:"Events",numeric:true,
    sortValue:row=>row.motion?.eventCount??null,
    render:row=>{
      const count=row.motion?.eventCount;
      return count===undefined||count===null?"—":String(count);}};
}
function animLengthCell(){
  return {key:"length",label:"Length",numeric:true,
    sortValue:row=>row.motion?.duration??null,
    render:row=>{
      const motion=row.motion;
      if(!motion||typeof motion.duration!=="number")return "—";
      return `${motion.duration.toFixed(2)}s`;}};
}
function animAnimsPane(){
  if(state.animListError)return [LexeditorUI.notice({tone:"warning",message:state.animListError})];
  const here=animListMatches();
  const size=paneSize("anims");
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.animPage>pages-1)state.animPage=pages-1;
  const shown=here.slice(state.animPage*size,(state.animPage+1)*size);
  const select=row=>{if(key(row)!==state.selected)void pickAnimMotion(row);};
  const list=columnList({rows:shown,key,selected:state.selected,select,class:"lex-list-fill",
    columns:[{key:"name",label:"Name",grow:1},animEventsCountCell(),animLengthCell()]});
  const pager=LexeditorUI.compactPager({pages,page:state.animPage,total:here.length,pageSize:size,
    change:value=>{state.animPage=value;refreshAnimList();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizePaneRows(list,size);
  fitPaneList(list,"anims",size,both);
  return [
    LexeditorUI.bottomSearch({key:"anims-list",value:state.animQuery,label:"Search animations",
      change:value=>{state.animQuery=value;state.animPage=0;refreshAnimList();}}),
    both];
}
function animEventsPane(){
  if(state.animEventError)return [LexeditorUI.notice({tone:"warning",message:state.animEventError})];
  const here=animListMatches();
  const size=paneSize("events");
  const pages=Math.max(1,Math.ceil(here.length/size));
  if(state.animPage>pages-1)state.animPage=pages-1;
  const shown=here.slice(state.animPage*size,(state.animPage+1)*size);
  const select=row=>{if(key(row)!==state.selected)void pickAnimEvent(row);};
  selectVisibleRecord=select;
  const list=columnList({rows:shown,key,selected:state.selected,select,class:"lex-list-fill",
    columns:[{key:"name",label:"Name",grow:1}]});
  const pager=LexeditorUI.compactPager({pages,page:state.animPage,total:here.length,pageSize:size,
    change:value=>{state.animPage=value;refreshAnimList();}});
  const both=LexeditorUI.pagedPane(list,pager);
  both.style.flex="1 1 auto";both.style.minHeight="0";
  sizePaneRows(list,size);
  fitPaneList(list,"events",size,both);
  return [
    LexeditorUI.bottomSearch({key:"anims-events",value:state.animQuery,label:"Search events",
      change:value=>{state.animQuery=value;state.animPage=0;refreshAnimList();}}),
    both];
}
function animListPane(){
  const level=state.animScope.level;
  return el("div",{"data-anim-list":"",style:"display:flex;flex-direction:column;flex:1 1 auto;min-height:0;"},...(level==="events"?animEventsPane():animAnimsPane()));
}
// The left panel's three lists: characters, the current character's
// animations, and the current animation's events. Animations needs a
// character, events needs a motion with an event file; a tab with
// nothing to show is disabled with its reason on the tooltip.
function animLeftTabs(){
  const charActive=!!state.animCharId;
  const motion=currentAnimMotionRef();
  const eventsActive=state.animScope.level==="events"||!!(motion&&motion.tae);
  // A character whose list loaded with no motions shows a disabled
  // Animations tab (the viewport holds its bind pose instead); while
  // the list is still loading, or after it failed, the tab stays
  // enabled so the reader sees the list or its error.
  const emptyAnims=state.animScope.level!=="events"&&state.animView&&animMotionRows(state.animView).length===0;
  const tabs=[
    {id:"chars",label:"Characters"},
    {id:"anims",label:"Animations",...(charActive&&!emptyAnims?{}:{disabled:true,
      disabledReason:emptyAnims?"This character has no animations.":"Select a character first."})},
    {id:"events",label:"Events",...(eventsActive?{}:{disabled:true,
      disabledReason:charActive?"The current animation has no event file.":"Select a character first."})}];
  return LexeditorUI.tabStrip({label:"Animation lists",tabs,active:state.animLeftTab,
    change:id=>{switchAnimLeft(id).catch(notify);}});
}
function animLeftPane(){
  const tab=state.animLeftTab;
  return el("div",{"data-anim-left":"",style:"display:flex;flex-direction:column;flex:1 1 auto;min-height:0;gap:8px;"},
    animLeftTabs(),
    tab==="anims"||tab==="events"?animListPane():animCharsPane());
}
function refreshAnimLeft(){
  if(state.tab!=="animations")return;
  const pane=document.querySelector("[data-anim-left]");
  if(!pane){render();return;}
  stopPaneFit(pane);
  pane.replaceWith(animLeftPane());
}
function refreshAnimChars(){
  if(state.tab!=="animations")return;
  const pane=document.querySelector("[data-anim-chars]");
  if(!pane){refreshAnimLeft();return;}
  stopPaneFit(pane);
  pane.replaceWith(animCharsPane());
}
function refreshAnimList(){
  if(state.tab!=="animations")return;
  const pane=document.querySelector("[data-anim-list]");
  if(!pane){refreshAnimLeft();return;}
  stopPaneFit(pane);
  pane.replaceWith(animListPane());
}
// The right panel shows the current selection: a character's file
// and animation count, a motion's file and event link, or the
// selected event's editable fields.
function animCharDetail(){
  const row=(state.animChars||[]).find(entry=>key(entry)===state.animCharId);
  if(!row)return detailPanel({title:"Character",body:[LexeditorUI.detailNote("Select a character.")]});
  const count=state.animView?animMotionRows(state.animView).length:null;
  return detailPanel({title:row.name,body:[detailSection({title:"Character",body:[
    detailField({label:"Character ID",control:readonlyField(row.id,{format:false})}),
    detailField({label:"Binder",control:readonlyField(row.values?.binder||"",{format:false})}),
    detailField({label:"Animations",control:readonlyField(count===null?"Loading…":count)})]})]});
}
function animMotionDetail(){
  const row=(state.rows||[]).find(entry=>key(entry)===state.selected);
  const motion=row&&row.table==="AnimMotion"?row.motion:null;
  if(!motion)return detailPanel({title:"Animation",body:[LexeditorUI.detailNote("Select an animation.")]});
  const fields=[
    detailField({label:"File",control:readonlyField(motion.file||"(no playable motion)",{format:false})}),
    detailField({label:"Binder",control:readonlyField(motion.binder||"",{format:false})})];
  if(typeof motion.duration==="number"&&typeof motion.frames==="number")
    fields.push(detailField({label:"Length",
      control:readonlyField(`${motion.duration.toFixed(2)}s, ${motion.frames} frames`,{format:false})}));
  if(motion.eventCount!==undefined&&motion.eventCount!==null)
    fields.push(detailField({label:"Events",control:readonlyField(motion.eventCount)}));
  if(motion.tae)fields.push(detailField({label:"Event file",
    control:readonlyField(`${motion.tae} · animation ${motion.taeIndex}`,{format:false})}));
  if(motion.available===false&&motion.reason)fields.push(
    detailField({label:"Status",control:readonlyField(motion.reason,{format:false})}));
  return detailPanel({title:row.name,body:[detailSection({title:"Animation",body:fields})]});
}
function animDetailPane(){
  const tab=state.animLeftTab;
  if(tab==="events")return detail();
  if(tab==="anims")return animMotionDetail();
  return animCharDetail();
}
function animDetailBox(){
  // Like the maps Selection pane: the panel flexes to fill the lane,
  // giving its paged body a definite height to fit against.
  const panel=animDetailPane();
  panel.style.flex="1 1 auto";panel.style.minHeight="0";
  return el("div",{"data-anim-detail":"",style:"display:flex;flex-direction:column;flex:1 1 auto;min-height:0;overflow:auto;"},panel);
}
function refreshAnimDetail(){
  if(state.tab!=="animations")return;
  const pane=document.querySelector("[data-anim-detail]");
  if(!pane){render();return;}
  pane.replaceWith(animDetailBox());
}
function mapsViewportPane(current){
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
  const highToggle=LexeditorUI.pagerToggle({label:"High collision",checked:state.mapCollisionHigh===true,
    change:value=>{state.mapCollisionHigh=value;viewportCtl?.setCollisionLayers?.(state.mapCollisionHigh===true,state.mapCollisionLow===true);}});
  const lowToggle=LexeditorUI.pagerToggle({label:"Low collision",checked:state.mapCollisionLow===true,
    change:value=>{state.mapCollisionLow=value;viewportCtl?.setCollisionLayers?.(state.mapCollisionHigh===true,state.mapCollisionLow===true);}});
  const navigationToggle=LexeditorUI.pagerToggle({label:"Navigation",checked:state.mapNavigation,
    change:value=>{state.mapNavigation=value;viewportCtl?.setMapOverlays?.(state.mapNavigation,state.mapRegions);}});
  const regionsToggle=LexeditorUI.pagerToggle({label:"Regions",checked:state.mapRegions,
    change:value=>{state.mapRegions=value;viewportCtl?.setMapOverlays?.(state.mapNavigation,state.mapRegions);}});
  const host=el("div",{class:"lex-viewport-host","data-viewport-host":"",style:VIEWPORT_STYLE+"height:100%;flex:1 1 auto;"},LexeditorUI.loadingPanel({label:"Loading map"}));
  requestAnimationFrame(()=>{
    viewportCtl=null;refreshViewportBar();
    const token=++viewportMount;
    Ds1Viewport.mount(host,current.id,state.mapView,viewportHooks()).then(ctl=>{
      if(token!==viewportMount)return;
      viewportCtl=ctl;
      viewportCtl?.setGizmoMode?.(state.mapGizmo);
      viewportCtl?.setCollisionLayers?.(state.mapCollisionHigh===true,state.mapCollisionLow===true);
      viewportCtl?.setMapOverlays?.(state.mapNavigation,state.mapRegions);
      if(state.mapSelected&&viewportCtl)viewportCtl.select(state.mapSelected);
      if(state.mapFocus&&viewportCtl){viewportCtl.focus(state.mapFocus);state.mapFocus=null;}
      if(state.mapTab==='collision')markCollisionPoint(true);
      refreshViewportBar();
    }).catch(error=>{if(token===viewportMount)failMount(host,"Could not load the map.")(error);});
  });
  // The buttons hover over the picture, not in a bar above it. They hang
  // on a wrapper: mounting clears the host itself for its canvas.
  const wrap=el("div",{style:"position:relative;min-width:0;flex:1 1 auto;display:flex;flex-direction:column;min-height:520px;"},host);
  LexeditorUI.hoverActions(wrap,{label:"Map actions",
    actions:[...(state.mapTab==='collision'?[]:[{node:duplicate},{node:remove},{node:add},{node:rotate}]),{node:highToggle},{node:lowToggle},{node:navigationToggle},{node:regionsToggle}]});
  const viewPane=el("div",{style:"min-width:0;display:flex;flex-direction:column;"},wrap);
  return viewPane;
}
function renderMaps(){
  if(!state.mapList.length)return LexeditorUI.notice({tone:"warning",message:"No map files found."});
  const current=state.mapList.find(row=>row.id===state.mapId)||state.mapList[0];
  if(state.mapTab==='collision')return renderCollision(current);
  const viewPane=mapsViewportPane(current);
  const lists=el("div",{"data-maps-side":"",class:"ds1-maps-left","aria-label":"Map lists",
    style:"min-width:0;min-height:0;display:flex;flex-direction:column;overflow:auto;"},mapsStrip(),mapsPane());
  const selection=el("div",{"data-maps-detail-panel":"",class:"ds1-maps-detail","aria-label":"Selection details",
    style:"min-width:0;min-height:0;display:flex;flex-direction:column;overflow:auto;"},mapsDetailBox());
  // The lists, the viewport and the Selection details share one panel
  // layout, like every list-and-detail page: a strip between each pair,
  // automatic shares clamped to measured minimums, refit as room
  // changes. Floors that fit an 1100px window: the lists keep room for
  // their tabs and table, and the view and detail floors plus two strips
  // stay under what is left. The detail vectors never stack (one row,
  // always), so the detail floor keeps the boxes wide enough that values
  // fit at full size.
  return LexeditorUI.panelLayout([lists,viewPane,selection],"ds1-maps-view",
    {defaultSizes:[24,46,30],minSizes:[300,280,360]});
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
    Ds1Anim.mount(host,currentAnimCharId(),currentAnimMotion(),timeline,status,animTimelineEvent).then(()=>flushAnimSeek()).catch(error=>{
      if(token!==animMount)return;
      failAnimMount(host,status,error);
    });
  });
  // Plain panels, not collapsible ones: the lists are the page, and
  // collapsing them away only stranded readers. The collapsible
  // component stays global for callers that still want it.
  const lists=el("div",{"data-anim-left-panel":"",class:"ds1-anim-left","aria-label":"Animation lists",
    style:"flex:0 0 360px;min-width:0;min-height:0;display:flex;flex-direction:column;overflow:auto;"},animLeftPane());
  const selection=el("div",{"data-anim-detail-panel":"",class:"ds1-anim-detail","aria-label":"Selection details",
    style:"flex:0 0 360px;min-width:0;min-height:0;display:flex;flex-direction:column;overflow:auto;"},
    animDetailBox());
  return el("div",{class:"ds1-anim"},lists,viewPane,selection);
}
function appliedLabel(deploy){
  if(!deploy.enabled&&deploy.nativeProjectActive)return "Yes, this mod's native rules";
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
  const selectedActive=deploy.enabled&&deploy.thisProjectActive||deploy.nativeProjectActive;
  const upToDate=selectedActive?(deploy.stale?"No, rebuild after the latest save":"Yes"):"-";
  return detailPanel({className:"lex-information-panel",title:"Information",body:[
    detailSection({title:"ITEMS",body:[detailField({label:"EDITION",control:readonlyField("Dark Souls Remastered / Steam")}),
      detailField({label:"SUPPORT",control:readonlyField("Items, effects, native rules, monster stats, enemy attacks, placements, animation events and assets"),help:infoHelp("Edit documented item properties, reviewed monster stats, enemy attack damage, map placements and animation event timing, or replace whole asset files. Names are reference labels. Unknown fields and padding stay unchanged. Saves go to the selected mod project.")})]}),
    detailSection({title:"INSTALLED GAME",body:[
      detailField({label:"APPLIED",control:readonlyField(appliedLabel(deploy))}),
      detailField({label:"ORIGINAL PRESERVED",control:readonlyField(deploy.everApplied?(deploy.backupOk?"Yes":"No, needs attention"):(deploy.nativeProjectActive?"Not needed for native rules":"Not yet applied")),
        help:infoHelp("The first Apply keeps one copy of the installed file exactly as it was. Disable always restores that copy.")}),
      detailField({label:"UP TO DATE",control:readonlyField(upToDate),
        help:infoHelp("Save builds changes for enabled library mods. Apply installs saved changes from this project.")}),
      needsAttentionNote(deploy),
      actionRow(
        el("button",{type:"button",disabled:state.deployBusy||!deploy.isProject||!deploy.sourceReady||deploy.changedExternally,onclick:()=>deploymentAction("apply")},deploy.everApplied?"Reapply":"Apply"),
        el("button",{type:"button",disabled:state.deployBusy||(!deploy.everApplied&&!deploy.native?.canRestore)||deploy.changedExternally,onclick:()=>deploymentAction("disable")},"Restore original")
      )].filter(Boolean)}),
    detailSection({title:"NATIVE RULES",body:[
      detailField({label:"APPLIED PROJECT",control:readonlyField(deploy.native?.project?.path||(deploy.nativeProjectActive?"Selected library mod":"None")),
        help:infoHelp("Library native rules follow each mod's switch. Projects outside the library keep their last applied rules until reapplied or restored.")}),
      deploy.native?.problem?LexeditorUI.detailNote(deploy.native.problem):null,
      deploy.native?.pendingRecovery?LexeditorUI.detailNote("An interrupted native operation is recoverable. Retry Apply or Restore original."):null,
      state.nativeRules?.migration?LexeditorUI.detailNote(state.nativeRules.migration):null
    ].filter(Boolean)}),
    modLoaderSection({loader:deploy.note||"Enabled mods combine over the game's files. Native mods use Lexeditor Loader.",
      output:"Apply combines saved changes from enabled mods with the game's preserved originals.",
      order:"The Mods tab lists overlaps and changes that cannot combine.",
      safety:"Apply prepares enabled mods before it writes installed files. The loader applies native changes in memory.",
      removal:"Restore original restores all owned files. The project and library tweak settings stay unchanged."})]});
}
// Tweaks are library mods: a switch saves at once, and changed tweaks
// rebuild when the mod project saves.
async function tweakRequest(path,body,failure){
  if(state.tweakBusy)return;
  state.tweakBusy=true;render();
  try{state.tweaks=await api(path,body);state.tweaksNeedRebuild=!!state.tweaks.needsRebuild;reportTweakRebuild(state.tweaks);}
  catch(error){LexeditorUI.showAlert({title:failure,message:error.message||String(error)});await loadTweaks().catch(()=>{});}
  finally{state.tweakBusy=false;render();}
}
async function restoreTweaks(){
  const ok=await confirmAction({title:"Remove the installed tweaks?",message:"Restores owned menu files and removes Lexeditor's loader. Close the game first. Saved mod settings stay unchanged.",confirmLabel:"Restore original",cancelLabel:"Cancel"});
  if(!ok)return;
  await tweakRequest("/api/tweaks/restore",{},"Could not restore the game files");
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
    help:"Play installs your enabled tweaks and applies their changes when the game starts. The loader adds multiplayer protection, but cannot guarantee against account restrictions. Modded play uses separate characters that Steam Cloud can sync. Removing the loader returns to your vanilla characters and keeps your modded progress for reinstalling. One original and one recent backup help recover damaged modded saves. Restore original removes the loader and restores changed game files.",
    body:[detailField({label:"APPLIED",control:readonlyField(applied)}),
      (status.staleMods||[]).length?LexeditorUI.detailNote(state.readOnly
        ?"The enabled tweaks changed since the last build. Close the game, then press Play to rebuild them."
        :"The enabled tweaks changed since the last build. Save to rebuild them."):null,
      status.state==="vanilla"&&!status.problem&&!status.needsRebuild&&(status.tweaks||[]).some(row=>row.enabled)?LexeditorUI.detailNote("These tweaks are on but not installed yet. Press Play to install them."):null,
      status.loaderMessage?detailField({label:"LAST GAME START",control:readonlyField(status.loaderMessage),
        help:infoHelp("What the loader reported the last time the game started. If the game was updated or another tool changed it, the loader changes nothing and says so here.")}):null,
      empty?missingMods:null,
      status.problem?LexeditorUI.detailNote(status.problem):null,
      actionRow(el("button",{type:"button",disabled:busy||!status.windows||!status.canRestore,onclick:restoreTweaks},"Restore original"))].filter(Boolean)});
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
// Directory notifications do the detection; this request reads a revision.
// Clean project data follows external edits. Unsaved edits and focused inputs
// defer replacement; history only resets when a new disk baseline was loaded.
let modRevision=0, modProjectRevision=0, ignoredModRevision=null, modRefreshPending=false, modProjectRefreshPending=false, modPollTimer=null, modPollBusy=false, modPollStopped=false;
let modProjectFiles=[];
async function refreshProjectData(){
  let locked=false;
  try{
    const probe=await api('/api/project-refresh',{files:modProjectFiles,checkOnly:true});
    if(probe.deferred)return;
    if(!probe.changed){modProjectRefreshPending=false;modProjectFiles=[];return;}
    if(document.body.inert||state.pending||state.dirty||state.rowBusy||state.bandForm||state.taeForm||state.assetUpload
       ||document.querySelector('input:focus,select:focus,textarea:focus'))return;
    locked=true;state.pending++;LexeditorUI.setEditorBusy('project-refresh','Refreshing mod files');
    const result=await api('/api/project-refresh',{files:modProjectFiles});
    modProjectRefreshPending=!!result.deferred;
    if(!result.deferred)modProjectFiles=[];
    if(!result.refreshed)return;
    attackPreviews.clear();recordRows.clear();textLabelPreviews.clear();fieldHistory.clear();
    await refreshState();
    if(!shell.isModsOpen())await navigate(state.tab,state.sub);
  }catch(error){
    modProjectRefreshPending=false;
    modProjectFiles=[];
    LexeditorUI.showToast(`Could not refresh the view after mod files changed: ${error.message}`,{tone:'warning'});
  }finally{
    if(locked){state.pending--;LexeditorUI.setEditorBusy('project-refresh',null);shell.refresh();}
  }
}
async function pollModChanges(){
  if(modPollBusy||modPollStopped)return;
  modPollBusy=true;
  try{
    const response=await fetch(`/api/mod-changes?since=${modRevision}&projectSince=${modProjectRevision}`);
    if(!response.ok)return;
    const result=await response.json();
    const changed=result.revision!==modRevision;
    modRevision=result.revision;
    modProjectRevision=result.projectRevision||0;
    modRefreshPending ||= changed;
    if(result.projectChanged){
      modProjectRefreshPending=true;
      modProjectFiles=modProjectFiles===null||!Array.isArray(result.projectFiles)?null:[...new Set([...modProjectFiles,...result.projectFiles])];
      if(modProjectFiles&&(modProjectFiles.length>128||new TextEncoder().encode(JSON.stringify(modProjectFiles)).length>48000))modProjectFiles=null;
    }
    if(!document.body.inert&&!state.pending&&!document.querySelector('[aria-modal="true"]')){
      state.tweaksNeedRebuild=!!result.tweaksNeedRebuild&&ignoredModRevision!==modRevision;
      shell.refresh();
      if(modProjectRefreshPending&&!state.dirty&&!state.bandForm&&!state.taeForm&&!state.assetUpload
         &&!fieldHistory.applying&&!document.querySelector('input:focus,select:focus,textarea:focus')){
        await refreshProjectData();
      }
    if(modRefreshPending){
      modRefreshPending=false;
      await shell.refreshMods();
      if(state.tab==="tweaks"&&!shell.isModsOpen()&&!document.querySelector('#main input:focus,#main select:focus,#main textarea:focus')){
        await loadTweaks();render();
      }
    }
    }
  }catch(_error){/* A session changing projects can briefly be unavailable. */}
  finally{
    modPollBusy=false;
    if(!modPollStopped)modPollTimer=setTimeout(pollModChanges,document.hidden?3000:1000);
  }
}
window.addEventListener('pagehide',()=>{modPollStopped=true;clearTimeout(modPollTimer);},{once:true});
window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&(state.dirty||state.pending||state.tweaksNeedRebuild))event.preventDefault();});
boot().then(pollModChanges);
