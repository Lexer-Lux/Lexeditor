  "use strict";
  const {el,list,columnList,pagedListDetail,pager,provenanceControl,clone,showAlert,infoHelp}=LexeditorUI;
  const $=selector=>document.querySelector(selector);
  const state={booting:true,modOnly:false,tab:"items",activeSource:"mine",files:{rows:[],counts:{}},dashboard:null,status:"Ready",items:null,itemSelected:"",itemQuery:"",itemSource:"",itemPage:0,itemPageSize:20,itemEdits:{},shops:null,shopSelected:"",shopQuery:"",shopName:"",shopCategory:"",shopPage:0,shopPageSize:20,shopEdits:{},missions:null,missionSelected:"",missionQuery:"",missionArea:"",missionPage:0,missionPageSize:20,missionEdits:{},vanilla:{items:null,shops:null,missions:null},settings:null,settingEdits:{},loot:null,lootDocument:null,lootDirty:false,lootScript:null,lootScriptEdits:{},dataMap:null,mapQuery:"",mapStatus:"",mapPage:0,dataMapSort:["filename",1]};
  const PAGE_SIZE=250;

  async function api(path,options){const response=await fetch(path,options);const value=await response.json();if(value.error)throw new Error(value.error);return value;}
  // "Mod contents only" keeps the rows this project has actually changed. RDR
  // already records every edit against the record's id, so the filter is that
  // record set and nothing else.
  function modOnlySpec(edits,resetPage){
    return {available:state.activeSource==="mine",value:state.modOnly===true,
      changed:row=>Object.prototype.hasOwnProperty.call(edits,String(row.id)),
      change:value=>{state.modOnly=value;resetPage();render()}};
  }
  function dirtyCount(){return state.activeSource==="mine"?Object.keys(state.itemEdits).length+Object.keys(state.shopEdits).length+Object.keys(state.missionEdits).length+Object.keys(state.settingEdits).length+(state.lootDirty?1:0):0;}
  function setStatus(text){state.status=text;}
  function historyCapture(){return {itemEdits:clone(state.itemEdits),shopEdits:clone(state.shopEdits),missionEdits:clone(state.missionEdits),settingEdits:clone(state.settingEdits),lootDocument:clone(state.lootDocument),lootDirty:state.lootDirty};}
  function historyRestore(snapshot){state.itemEdits=clone(snapshot.itemEdits||{});state.shopEdits=clone(snapshot.shopEdits||{});state.missionEdits=clone(snapshot.missionEdits||{});state.settingEdits=clone(snapshot.settingEdits||{});state.lootDocument=clone(snapshot.lootDocument);state.lootDirty=!!snapshot.lootDirty;}
  function cell(text){return el("span",{title:String(text??"")},String(text||"—"));}
  function shown(text){return LexeditorUI.readonlyField(text??"—",{format:false,title:String(text??"")});}
  function fact(label,text){return LexeditorUI.detailField({label,control:shown(text)});}
  function projectBadge(record){return LexeditorUI.badge(record.project?"Project":"Vanilla",{tone:record.project?"success":null});}
  function unavailable(title,message){return LexeditorUI.detailPanel({className:"lex-information-panel",title,body:[LexeditorUI.detailNote(message)]});}
  // `description` is prose under the row; `help` is the shared info bubble that
  // every other plugin's fields carry. RDR's rows had neither, so nothing on
  // the page explained what any of it edits.
  function detailField(label,value,help="",bubble=""){const control=value instanceof Node?value:el("span",{},String(value??"—"));return LexeditorUI.detailField({label,control,description:help||"",help:bubble?LexeditorUI.infoHelp(bubble):null});}
  function applyControlValue(control,value){if(control.type==="checkbox")control.checked=String(value).toLowerCase()==="true";else control.value=String(value);control.dispatchEvent(new Event(control.type==="checkbox"||control.tagName==="SELECT"?"change":"input",{bubbles:true}));}
  function sourceControl(control,current,vanilla,apply,format){if(state.activeSource!=="mine"||vanilla===undefined)return control;return provenanceControl({control,current,vanilla,internal:true,format,apply:value=>{apply(value);applyControlValue(control,value);shell.refresh()}})}

  async function saveAll(){
    if(!dirtyCount()||state.activeSource!=="mine")return;
    try{
      validatePendingEdits();
      const saved=[];
      const itemGroups={};
      for(const [key,value] of Object.entries(state.itemEdits)){const split=key.lastIndexOf("|");const id=key.slice(0,split),field=key.slice(split+1);(itemGroups[id]||(itemGroups[id]=[])).push({field,value});}
      for(const [id,edits] of Object.entries(itemGroups)){
        const item=state.items.rows.find(row=>row.id===id);if(!item)throw new Error(`Item ${id} is no longer loaded`);
        await api("/api/item/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:item.source,index:item.index,expectedName:item.name,edits})});saved.push(item.name);
      }
      const shopGroups={};
      for(const [key,value] of Object.entries(state.shopEdits)){const split=key.lastIndexOf("|");const id=key.slice(0,split),field=key.slice(split+1);(shopGroups[id]||(shopGroups[id]=[])).push({field,value});}
      for(const [id,edits] of Object.entries(shopGroups)){
        const item=state.shops.rows.find(row=>row.id===id);if(!item)throw new Error(`Shop item ${id} is no longer loaded`);
        await api("/api/shop/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:item.source,rootHash:item.rootHash,itemIndex:item.itemIndex,expectedName:item.name,edits})});saved.push(`${item.shop}: ${item.name}`);
      }
      if(Object.keys(state.missionEdits).length){
        const overrides=[];
        for(const mission of state.missions.missions){
          const rewards={};
          for(const reward of MISSION_REWARDS){
            const raw=missionValue(mission,reward.key),value=numberEdit(raw,`${mission.name} ${reward.label}`,{...state.missions.limits.rewards[reward.key],step:1});
            if(!Number.isInteger(value))throw new Error(`${mission.name} ${reward.label.toLowerCase()} must be an integer`);
            if(value!==mission.baseRewards[reward.key])rewards[reward.key]=value;
          }
          if(Object.keys(rewards).length)overrides.push({id:mission.id,rewards});
        }
        const result=await api("/api/missions/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({schemaVersion:1,contract:"LexerRDR.mission-rewards",overrides})});saved.push(`${result.saved} mission reward field(s)`);
      }
      if(Object.keys(state.settingEdits).length){
        const edits=Object.entries(state.settingEdits).map(([identity,value])=>{const [section,key]=identity.split("\u0000");return {section,key,value};});
        await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});saved.push("LexerRDR.ini");
      }
      if(state.lootDirty){await api("/api/loot/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({document:state.lootDocument})});saved.push("LexerRDR.loot.json");}
      [state.files,state.items,state.shops,state.missions,state.settings,state.loot,state.dashboard]=await Promise.all([api("/api/files"),api("/api/items"),api("/api/shops"),api("/api/missions"),optionalRuntime("/api/settings"),optionalRuntime("/api/loot"),api("/api/dashboard")]);
      state.itemEdits={};state.shopEdits={};state.missionEdits={};state.settingEdits={};state.lootDocument=clone(state.loot.document);state.lootDirty=false;shell.history.clear();setStatus(`Saved to workspace: ${saved.join(", ")}. ${state.dashboard.deployment?.pending?"Deploy Project to rebuild the archive copies.":"Runtime-backed files are ready from the workspace."}`);render();
    }catch(error){setStatus("Save failed");showAlert({title:"Save failed",items:[{item:"Save",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }

  function navigate(tab){state.tab=tab;render();}
  function renderVanillaOnly(){$("#toolbar").replaceChildren();$("#main").replaceChildren(LexeditorUI.detailPanel({className:"lex-information-panel",title:"Vanilla",body:[LexeditorUI.detailSection({body:[
    LexeditorUI.detailText("This page contains LexerRDR mod data and has no Vanilla game-file equivalent."),LexeditorUI.detailText("Select a mod to edit this page.")]})]}));shell.refresh()}
  function render(){document.querySelectorAll("nav button").forEach(button=>button.classList.toggle("active",button.dataset.tab===state.tab));if(state.booting)return;if(state.activeSource!=="mine"&&["loot","settings"].includes(state.tab))renderVanillaOnly();else if(state.tab==="items")renderItems();else if(state.tab==="shops")renderShops();else if(state.tab==="loot")renderLoot();else if(state.tab==="missions")renderMissions();else if(state.tab==="settings")renderSettings();else if(state.tab==="datamap")renderDataMap();else renderProject();}
  async function switchProjectSource(value){const next=String(value||"mine")==="vanilla"?"vanilla":"mine";if(next===state.activeSource)return;state.activeSource=next;state.itemEdits={};state.shopEdits={};state.missionEdits={};state.settingEdits={};state.lootDocument=clone(state.loot?.document);state.lootDirty=false;if(next==="vanilla"){state.items=clone(state.vanilla.items);state.shops=clone(state.vanilla.shops);state.missions=clone(state.vanilla.missions)}else[state.items,state.shops,state.missions]=await Promise.all([api("/api/items"),api("/api/shops"),api("/api/missions")]);shell.history?.clear();render()}
  const shell=LexeditorUI.mountShell({
    host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"rdr",themeName:"rdr",theme:{bg:"#11100f",panel:"#1a1816","panel-2":"#211e1a",border:"#4e4237",text:"#e8ded0",muted:"#aa9b89",accent:"#a92b20","accent-text":"#fff5e8",highlight:"#c99a50",success:"#69955d",font:'RDRLino,"Segoe UI",sans-serif',"heading-font":"Redemption,Georgia,serif"}},
    tabs:[{id:"items",label:"Items"},{id:"shops",label:"Shops"},{id:"loot",label:"Loot Tables"},{id:"missions",label:"Missions"},{id:"settings",label:"Tweaks"}],activeTab:()=>state.tab,navigate,help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the RDR Data Map",info:()=>navigate("project"),infoActive:()=>state.tab==="project",infoTitle:"Open RDR setup information",projectSources:()=>[{key:"vanilla",label:"Vanilla",path:"Prepared unchanged RDR game data"}],projectActiveSource:()=>state.activeSource,selectProjectSource:switchProjectSource,dirtyCount,readonly:()=>state.activeSource!=="mine",save:saveAll,
    history:{capture:historyCapture,restore:historyRestore,render,enabled:()=>!state.booting&&state.activeSource==="mine",limit:50}
  });

  async function optionalRuntime(path){
    try{return await api(path);}catch(error){return {available:false,file:path,sections:[],reason:error.message};}
  }
  async function boot(){
    try{[state.files,state.dashboard,state.items,state.shops,state.missions,state.settings,state.loot,state.vanilla.items,state.vanilla.shops,state.vanilla.missions]=await Promise.all([api("/api/files"),api("/api/dashboard"),api("/api/items"),api("/api/shops"),api("/api/missions"),optionalRuntime("/api/settings"),optionalRuntime("/api/loot"),api("/api/items?dataset=vanilla"),api("/api/shops?dataset=vanilla"),api("/api/missions?dataset=vanilla")]);if(state.dashboard.redHook.installed)await configureRedHook();state.lootDocument=state.loot.available?clone(state.loot.document):null;state.booting=false;render();if(!state.dashboard.redHook.installed){await openRedHook();renderRedHookNotice();}LexeditorUI.finishPluginLoading();}
    catch(error){state.booting=false;LexeditorUI.finishPluginLoading();$("#main").textContent=`Failed to load RDR plugin: ${error.message}`;setStatus("Load failed");}
  }
  window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&dirtyCount())event.preventDefault();});
  boot();
  
