  "use strict";
  const {el,columnList,list,masterDetail,pagedListDetail,pager,clone,showAlert,hoverable,detailPanel,detailField,detailGroup}=LexeditorUI;
  const $=selector=>document.querySelector(selector);
  const state={
    booting:true,modOnly:false,tab:"items",dashboard:null,settings:null,troops:null,items:null,upgrades:null,modules:null,datamap:null,activeSource:"mine",
    manual:null,font:null,selectedModule:"",selectedSetting:"",selectedItem:"",selectedTroop:"",selectedUpgrade:"",selectedFile:"",catalogFile:null,catalogDraft:"",
    settingEdits:{},itemEdits:{},troopEdits:{},filters:{items:"",troops:"",cut:false,upgrades:"",settings:"",datamap:"",mapStatus:""},
    pages:{items:0,troops:0,upgrades:0,datamap:0,settings:0},pageSizes:{items:20,troops:20,upgrades:20,settings:20},sorts:{items:["name",1],troops:["name",1],upgrades:["from",1],datamap:["filename",1],settings:["section",1]},
    build:{cursor:0,lines:[],running:false,returnCode:null},status:"Ready"
  };

  async function api(path,options){const response=await fetch(path,options);const value=await response.json();if(value.error)throw new Error(value.error);return value;}
  // "Mod contents only" keeps the records this project has actually changed.
  // Warband records edits against the record itself, so the filter is the set
  // of records that carry one. A view whose records this editor cannot change
  // says so rather than offering a switch that would hide everything.
  function modOnlySpec(view,changed){
    return {available:state.activeSource==="mine"&&typeof changed==="function",
      value:state.modOnly===true,changed:changed||(()=>true),
      unavailableTitle:"This view has no editable records to filter by.",
      change:value=>{state.modOnly=value;state.pages[view]=0;render()}};
  }
  function itemDirtyCount(){return Object.values(state.itemEdits).reduce((total,row)=>total+Object.keys(row.fields||{}).length,0);}
  function dirtyCount(){return state.activeSource==="mine"?Object.keys(state.settingEdits).length+itemDirtyCount()+Object.values(state.troopEdits).reduce((n,r)=>n+Object.keys(r.fields).length,0)+(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text?1:0):0;}
  function historyCapture(){return {troopEdits:clone(state.troopEdits),settingEdits:clone(state.settingEdits),itemEdits:clone(state.itemEdits),catalogDraft:state.catalogDraft,selectedFile:state.selectedFile,catalogFile:clone(state.catalogFile)};}
  async function historyRestore(snapshot){state.troopEdits=clone(snapshot.troopEdits||{});state.settingEdits=clone(snapshot.settingEdits);state.itemEdits=clone(snapshot.itemEdits||{});state.catalogDraft=snapshot.catalogDraft;state.selectedFile=snapshot.selectedFile;state.catalogFile=clone(snapshot.catalogFile);}
  function effectiveSetting(row){return state.settingEdits[row.line]??row.value;}
  function setStatus(text){state.status=text;const target=$("#plugin-status");if(target)target.textContent=text;}
  function bitmapText(text,pixels){
    const font=state.font;if(!font?.available)return document.createTextNode(text);
    const scale=pixels/font.fontSize;
    return LexeditorUI.bitmapText({label:text,lineHeight:font.lineSpacing*scale,glyphs:[...text].map(character=>{
      const metrics=font.characters[String(character.codePointAt(0))];
      if(!metrics)return {width:pixels*.52,text:character};
      return {width:Math.max(1,metrics.postshift*scale),quad:metrics.w>metrics.u&&metrics.h>metrics.v?{
        left:metrics.preshift*scale,top:(font.fontSize-metrics.yadjust)*scale,width:(metrics.w-metrics.u)*scale,height:(metrics.h-metrics.v)*scale,
        atlasWidth:font.width*scale,atlasHeight:font.height*scale,u:metrics.u*scale,v:metrics.v*scale}:null};
    })});
  }
  function applyInstalledWarbandFont(){
    const brand=(window.LexeditorUI?.shellTextNodes?.()||[])[0]?.closest("button");if(brand&&!brand.dataset.bitmapFont){brand.dataset.bitmapFont="1";brand.replaceChildren(bitmapText("LEXEDITOR",24));}
    document.querySelectorAll("nav button").forEach(button=>{if(button.dataset.bitmapFont)return;const target=(window.LexeditorUI?.shellTextNodes?.(button)||[])[0]||button;if(!target)return;const label=target.textContent;button.dataset.bitmapFont="1";button.setAttribute("aria-label",label);target.replaceChildren(bitmapText(label,26));});
  }
  function search(rows,query,fields){const needle=query.trim().toLowerCase();return needle?rows.filter(row=>fields.some(field=>String(row[field]??"").toLowerCase().includes(needle))):rows;}
  function sorted(rows,view){const [key,direction]=state.sorts[view];return [...rows].sort((a,b)=>direction*String(a[key]??"").localeCompare(String(b[key]??""),undefined,{numeric:true}));}
  function sort(view,key){const [active,direction]=state.sorts[view];state.sorts[view]=[key,active===key?-direction:1];render();}
  function renderTableView(view,rows,columns,options={}){
    const query=state.filters[view]||"",filtered=sorted(search(rows,query,options.searchFields||columns.map(column=>column.key)),view);
    const keyOf=options.key||((row)=>columns.map(column=>String(row[column.key]??"")).join("|"));
    const selected=options.selected?.()||"",setSelected=options.setSelected||(()=>{});
    const detail=row=>row?detailPanel({title:row.name||String(keyOf(row)),body:[LexeditorUI.detailSection({body:columns.map(column=>
      detailField({label:typeof column.label==="string"?column.label:column.key,control:LexeditorUI.readonlyField(row[column.key]??"—",{format:false})}))})]})
      :detailPanel({title:"No matching records"});
    $("#toolbar").replaceChildren();
    $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec(view,options.changed),rows:filtered,key:keyOf,slots:false,fit:{minRowHeight:36},page:state.pages[view],pageSize:state.pageSizes[view],selected,noun:view,splitKey:`warband-${view}`,className:"warband-paged-table",defaultSplit:58,
      search:{key:`warband-${view}`,value:query,placeholder:`Search ${view}…`,change:value=>{state.filters[view]=value;state.pages[view]=0;render();}},filters:options.filters||[],
      master:({rows,selected,select})=>columnList({rows,key:keyOf,columns:columns.map(column=>({...column,sortable:true})),sortState:{key:state.sorts[view][0],dir:state.sorts[view][1]},sort:key=>sort(view,key),selected,selectedClass:"selected",select,class:"warband-record-list", "aria-label":`${view} records`}),
      detail:options.detail||detail,sync:next=>{state.pages[view]=next.page;state.pageSizes[view]=next.pageSize;setSelected(next.selected||"");},change:next=>{state.pages[view]=next.page;state.pageSizes[view]=next.pageSize;setSelected(next.selected||"");render();}}));
  }

  async function buildSavedModule(){
    const started=await api("/api/build/start",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    if(!started.started)throw new Error(started.reason||"The Warband build could not start.");
    state.build={cursor:0,lines:[],running:true,returnCode:null};setStatus("Saving and building…");
    while(state.build.running){
      await new Promise(resolve=>setTimeout(resolve,200));
      const result=await api(`/api/build/status?cursor=${state.build.cursor}`);
      state.build.cursor=result.cursor;state.build.lines.push(...result.lines);state.build.running=result.running;state.build.returnCode=result.returnCode;
    }
    if(state.build.returnCode!==0||!state.build.lines.join("").includes("Build verified:")){
      throw new Error("The source was saved, but the module build failed. Open Info to read the log.");
    }
    setStatus("Saved and build verified");
  }

  async function saveAll(){
    try{
      const itemSourceDirty=state.catalogFile?.filename==="module_items.py"&&state.catalogFile.editable&&state.catalogDraft!==state.catalogFile.text;
      if(itemDirtyCount()&&itemSourceDirty)throw new Error("Items has structured edits while module_items.py also has unsaved source edits. Save or discard one editing path before using the other.");
      if(Object.keys(state.settingEdits).length){const edits=Object.entries(state.settingEdits).map(([line,value])=>({line:+line,value}));const result=await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.settings=await api("/api/settings");state.settingEdits={};setStatus(`Saved ${result.saved} settings`);}
      const troopEdits=Object.values(state.troopEdits).filter(row=>Object.keys(row.fields).length);
      if(troopEdits.length){
        if(state.catalogFile?.filename==="module_troops.py"&&state.catalogDraft!==state.catalogFile.text)throw new Error("Save or discard the troop source draft first.");
        await api("/api/troops/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sha256:state.troops.sha256,edits:troopEdits})});
        state.troops=await api("/api/troops");state.troopEdits={};
        if(state.catalogFile?.filename==="module_troops.py"){state.catalogFile=await api("/api/catalog/file?name=module_troops.py");state.catalogDraft=state.catalogFile.text;}
      }
      if(itemDirtyCount()){
        const selectedRecord=state.items.rows.find(row=>row.id===state.selectedItem)?.recordIndex,edits=Object.values(state.itemEdits);
        const result=await api("/api/items/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.items=await api("/api/items");state.itemEdits={};
        if(selectedRecord!==undefined)state.selectedItem=state.items.rows.find(row=>row.recordIndex===selectedRecord)?.id||"";
        if(state.catalogFile?.filename==="module_items.py"){state.catalogFile=await api("/api/catalog/file?name=module_items.py");state.catalogDraft=state.catalogFile.text;}
        setStatus(`Saved ${result.saved} item records`);
      }
      if(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text){const result=await api("/api/catalog/file/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({filename:state.catalogFile.filename,text:state.catalogDraft,encoding:state.catalogFile.encoding})});state.catalogFile.text=state.catalogDraft;setStatus(`Saved ${state.catalogFile.filename}; backup created`);}
      await buildSavedModule();
      shell.history.clear();shell.refresh();render();
    }catch(error){setStatus("Save failed");showAlert({title:"Save failed",items:[{item:"Save",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }

  function viewFor(tab){return {items:renderItems,manuals:renderManuals,upgrades:renderUpgrades,troops:renderTroops,tweaks:renderSettings,datamap:renderDataMap,dashboard:renderDashboard}[tab];}
  function navigate(tab){disposeWarbandPreview();state.tab=tab;render();}
  function renderVanilla(){$("#toolbar").replaceChildren();$("#main").replaceChildren(detailPanel({className:"lex-information-panel",title:"Vanilla",body:[LexeditorUI.detailSection({body:[
    LexeditorUI.detailText("The installed Native module is read-only. Its generated text files do not contain the Module System source used by this editor."),
    LexeditorUI.detailText("Select a mod to edit Items, Troops, Troop Trees, or Tweaks.")]})]}))}
  function render(){document.querySelectorAll("nav button").forEach(button=>button.classList.toggle("active",button.dataset.tab===state.tab));if(state.booting)return;if(state.activeSource!=="mine"&&!['manuals','datamap','dashboard'].includes(state.tab))renderVanilla();else viewFor(state.tab)();shell.refresh();}
  async function switchProjectSource(value){state.activeSource=String(value||"mine")==="vanilla"?"vanilla":"mine";shell.history?.clear();render()}
  
