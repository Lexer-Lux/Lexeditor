  "use strict";
  const {el,columnList,columnPreferences,detailPanel,detailSection,detailNote,detailField,readonlyField,recordId,infoHelp,infoIcon,panelLayout,clone,EditHistory}=LexeditorUI;
  const $=selector=>document.querySelector(selector);
  async function api(path,body){const response=await fetch(path,body===undefined?undefined:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});let payload={};try{payload=await response.json()}catch(_error){}if(!response.ok)throw new Error(payload.error||response.statusText);return payload}

  const state={modOnly:false,textPacks:null,textResource:"",textBusy:false,reshade:null,curatedQuery:"",curatedSort:{key:"id",dir:1},
    tab:"data",catalog:null,info:null,dataMap:null,activeSource:"mine",busy:false,error:"",projectMessage:"",
    asset:"",data:null,dataBaseline:null,selected:0,query:"",sort:{key:"tag",dir:1},
    economy:null,economyKey:"",economyError:"",economyTable:"",economyQuery:"",economySort:{key:"name",dir:1},
    loot:null,lootKey:"",lootError:"",lootQuery:"",lootSort:{key:"tag",dir:1},
    textLanguage:"US",textAsset:"",textData:null,textBaseline:null,textSelected:0,textQuery:"",textSort:{key:"key",dir:1},
    mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1]
  };
  if(!state.pages)state.pages={};
  // Any property of the loaded DataObject can be pinned into the table. The pin
  // is the same control every other table uses; what differs here is that the
  // column set is the record's own schema rather than a fixed list, so the
  // preferences are keyed per asset and a property column starts unpinned.
  const dataPrefsCache=new Map();
  const propertyColumnKey=prop=>`p:${prop.name}`;
  const dirtyCount=()=>dataEdits().length+textEdits().length+tweakEditGroups().reduce((total,group)=>total+group.edits.length,0);

  async function confirmReplace(kind){
    const count=kind==="text"?textEdits().length:dataEdits().length;
    if(!count)return true;
    return LexeditorUI.confirmAction({
      title:"Discard unsaved changes?",
      message:`${count} unsaved ${kind==="text"?"text":"game-data"} change${count===1?"":"s"} would be lost by opening another resource.`,
      confirmLabel:"Discard and open",cancelLabel:"Keep editing"});
  }
  async function loadAsset(asset=state.asset){
    if(!asset)return;
    state.busy=true;state.error="";render();
    try{state.data=await api(`/api/data?asset=${encodeURIComponent(asset)}${sourceSuffix()}&language=${encodeURIComponent(state.textLanguage||"US")}`);state.dataBaseline=clone(state.data);state.selected=state.data.records[0]?.id??0;state.asset=asset;state.query=""}
    catch(error){state.data=null;state.dataBaseline=null;state.error=error.message}
    finally{state.busy=false;render();refreshShell()}
  }
  async function selectAsset(asset){if(asset===state.asset)return true;if(!await confirmReplace("data"))return false;state.asset=asset;await loadAsset(asset);return !!state.data}

  async function loadEconomy(){
    const key=semanticKey();
    if(state.economyKey!==key){
      state.busy=true;state.economyError="";render();
      try{state.economy=await api(`/api/economy?language=${encodeURIComponent(state.textLanguage||"US")}${sourceSuffix()}`);state.economyKey=key}
      catch(error){state.economy=null;state.economyError=error.message}
      finally{state.busy=false;render()}
    }
    const tables=(state.economy?.tables||[]).filter(table=>table.available);
    if(!tables.length)return true;
    const wanted=economyTableFor(state.tab);
    if(wanted)state.economyTable=wanted.asset;
    else if(!tables.some(table=>table.asset===state.economyTable))state.economyTable=tables[0].asset;
    if(state.data?.asset!==state.economyTable){if(!await selectAsset(state.economyTable))return false}
    return true;
  }
  const ECONOMY_TABS=[{id:"equipment",label:"Equipment"},{id:"item",label:"Items"},{id:"materia",label:"Materia"}];
  const isEconomyTab=tab=>ECONOMY_TABS.some(entry=>entry.id===tab);
  const economyKind=table=>String(table?.asset||"").split("/").pop().split(".")[0].toLocaleLowerCase();
  function economyTableFor(tab){return economyTables().find(table=>economyKind(table)===tab)||null}
  async function selectEconomyTable(asset){if(asset===state.economyTable)return;const previous=state.economyTable;state.economyTable=asset;if(!await selectAsset(asset))state.economyTable=previous;render()}
  async function loadLoot(){
    const key=semanticKey();
    if(state.lootKey!==key){
      state.busy=true;state.lootError="";render();
      try{state.loot=await api(`/api/loot?language=${encodeURIComponent(state.textLanguage||"US")}${sourceSuffix()}`);state.lootKey=key}
      catch(error){state.loot=null;state.lootError=error.message}
      finally{state.busy=false;render()}
    }
    if(!state.loot?.available||!state.loot.asset)return true;
    if(state.data?.asset!==state.loot.asset){if(!await selectAsset(state.loot.asset))return false}
    return true;
  }

  // Thirty-seven resources per language, read together. Requesting them in
  // parallel is what makes one list of all the game's text practical; asking
  // for them one after another took long enough that the tab had to make you
  // choose first, which is the shape this replaces.
  async function loadAllText(language=state.textLanguage){
    const list=textAssets().filter(row=>row.language===language);
    if(!list.length){state.textPacks={};return}
    state.textBusy=true;state.error="";render();
    try{
      const packs={};
      await Promise.all(list.map(async item=>{
        try{
          const data=await api(`/api/text?asset=${encodeURIComponent(item.asset)}${sourceSuffix()}`);
          packs[item.asset]={item,data,baseline:clone(data)};
        }catch(error){state.error=error.message}
      }));
      state.textPacks=packs;
      const resident=residentTextAsset();
      if(resident&&packs[resident.asset]){
        state.textAsset=resident.asset;
        state.textData=packs[resident.asset].data;
        state.textBaseline=packs[resident.asset].baseline;
      }
      const first=textRecords()[0];
      if(!textRecords().some(row=>row.id===state.textSelected))state.textSelected=first?.id??null;
    }catch(error){state.error=error.message}
    finally{state.textBusy=false;render();refreshShell()}
  }
  // One resource at a time, kept only for the callers that still name one.
  async function loadTextAsset(asset=state.textAsset){
    if(!asset)return;
    state.busy=true;state.error="";render();
    try{const data=await api(`/api/text?asset=${encodeURIComponent(asset)}${sourceSuffix()}`);
      const item=textAssets().find(row=>row.asset===asset)||{asset,name:asset};
      state.textPacks={...(state.textPacks||{}),[asset]:{item,data,baseline:clone(data)}};
      state.textData=data;state.textBaseline=clone(data);
      state.textSelected=`${asset}#${data.records[0]?.id??0}`;state.textAsset=asset;state.textQuery="";
      if(data.language)state.textLanguage=data.language}
    catch(error){state.textData=null;state.textBaseline=null;state.error=error.message}
    finally{state.busy=false;render();refreshShell()}
  }
  async function selectTextAsset(asset){if(asset===state.textAsset)return;if(!await confirmReplace("text"))return;state.textAsset=asset;await loadTextAsset(asset)}
  async function selectTextLanguage(language){
    if(language===state.textLanguage)return;
    if(!await confirmReplace("text"))return;
    state.textLanguage=language;state.economyKey="";state.lootKey="";
    state.textAsset="";state.textData=null;state.textBaseline=null;state.textPacks=null;
    if(state.data)await loadAsset(state.asset);
    if(state.tab==="text")await loadAllText(language);else render();
    if(isEconomyTab(state.tab))await loadEconomy();if(state.tab==="loot")await loadLoot();
  }

  function render(){let content;const curated=curatedSpec(state.tab);if(curated)content=curatedPanel(curated);else if(state.tab==="datamap")content=dataMapPanel();else if(state.tab==="tweaks")content=tweaksPanel();else if(state.tab==="info")content=infoPanel();else if(state.tab==="text")content=textPanel();else if(isEconomyTab(state.tab))content=economyPanel();else if(state.tab==="loot")content=lootPanel();else content=dataPanel();$("#main").replaceChildren(content);refreshShell()}
  async function navigate(tab){const previous=state.tab;state.tab=tab;render();if(tab==="text"){if(!state.textPacks)await loadAllText();else render()}else if(isEconomyTab(tab)){if(!await loadEconomy()){state.tab=previous;render()}else{await ensureResidentText();render()}}else if(tab==="loot"){if(!await loadLoot()){state.tab=previous;render()}}
    else if(curatedSpec(tab)){
      const spec=curatedSpec(tab);
      // Keep whichever of this table's archives the reader last chose.
      const siblings=curatedAssets(spec);
      const item=siblings.find(entry=>entry.asset===state.curatedAsset)||siblings[0]||null;
      if(item&&(state.asset!==item.asset||!state.data)){
        state.asset=item.asset;await loadAsset(item.asset);
      }
      state.pages[tab]=0;render();
    }
    else if(tab==="tweaks"){
      if(!state.reshade)await loadReshade();
      if(!state.tweaks)await loadAllTweaks();else render();
    }
    else if(tab==="data"){
      // Opening this tab loaded nothing, so the table sat empty behind the
      // picker until the user changed the dropdown by hand.
      const list=gameAssets();
      const wanted=list.some(item=>item.asset===state.asset)?state.asset:(list[0]?.asset||"");
      if(wanted&&(state.asset!==wanted||!state.data)){state.asset=wanted;await loadAsset(wanted);render()}
    }}

  async function save(){
    if(state.activeSource!=="mine")return;
    const gameplay=dataEdits(),text=textEdits(),tweaks=tweakEditGroups();
    if(!gameplay.length&&!text.length&&!tweaks.length)return;
    state.busy=true;state.error="";render();
    try{
      if(gameplay.length){const result=await api("/api/save",{asset:state.data.asset,sourceSha256:state.data.sourceSha256,activeSha256:state.data.activeSha256,edits:gameplay});state.data.activeSha256=result.activeSha256;state.data.usingProject=true;state.dataBaseline=clone(state.data);state.projectMessage=`Saved ${result.saved} gameplay value${result.saved===1?"":"s"}.`}
      for(const group of tweakEditGroups()){
        const data=group.entry.data;
        const result=await api("/api/save",{asset:data.asset,sourceSha256:data.sourceSha256,activeSha256:data.activeSha256,edits:group.edits});
        data.activeSha256=result.activeSha256;data.usingProject=true;group.entry.baseline=clone(data);
        state.projectMessage=`${state.projectMessage?state.projectMessage+" ":""}Saved ${result.saved} value${result.saved===1?"":"s"} in ${group.entry.item.name||data.asset}.`;
      }
      for(const group of textEditGroups()){
        const data=group.pack.data;
        const result=await api("/api/text/save",{asset:data.asset,sourceUassetSha256:data.sourceUassetSha256,sourceUexpSha256:data.sourceUexpSha256,activeUassetSha256:data.activeUassetSha256,activeUexpSha256:data.activeUexpSha256,edits:group.edits});
        data.activeUassetSha256=result.activeUassetSha256;data.activeUexpSha256=result.activeUexpSha256;data.usingProject=true;
        group.pack.baseline=clone(data);
        if(state.textData===data)state.textBaseline=clone(data);
        state.projectMessage=`${state.projectMessage?state.projectMessage+" ":""}Saved ${result.saved} text value${result.saved===1?"":"s"} in ${group.pack.item.name||data.asset}.`;
      }
      editHistory.clear();
    }catch(error){state.error=error.message;throw error}
    finally{state.busy=false;render();refreshShell()}
  }
  async function discard(){if(state.data&&state.dataBaseline)state.data=clone(state.dataBaseline);for(const pack of textPacks())pack.data.records=clone(pack.baseline.records);for(const entry of Object.values(state.tweaks||{}))entry.data=clone(entry.baseline);if(state.textData&&state.textBaseline)state.textData=clone(state.textBaseline);editHistory.clear();render();refreshShell()}
  const editHistory=new EditHistory({capture:()=>({data:state.data?clone(state.data.records):null,text:Object.fromEntries(textPacks().map(pack=>[pack.item.asset,clone(pack.data.records)]))}),restore:snapshot=>{if(state.data&&snapshot?.data)state.data.records=clone(snapshot.data);for(const [asset,records] of Object.entries(snapshot?.text||{})){const pack=state.textPacks?.[asset];if(pack)pack.data.records=clone(records)}},render:async()=>render(),enabled:()=>state.activeSource==="mine"&&["data","loot","text"].includes(state.tab)||isEconomyTab(state.tab),changed:()=>refreshShell()});

  async function selectProjectSource(value){if(dirtyCount()&&!await LexeditorUI.confirmAction({title:"Discard unsaved changes?",message:"Switching source reloads everything from the other source. All unsaved FF7R changes would be lost.",confirmLabel:"Discard and switch",cancelLabel:"Keep editing"}))return;state.activeSource=String(value||"mine");state.economyKey="";state.lootKey="";if(state.data)await loadAsset(state.asset);if(state.tweaks){state.tweaks=null;if(state.tab==="tweaks")await loadAllTweaks()}if(state.textPacks){state.textPacks=null;state.textData=null;state.textBaseline=null;if(state.tab==="text")await loadAllText();else await ensureResidentText()}if(isEconomyTab(state.tab))await loadEconomy();if(state.tab==="loot")await loadLoot()}
  const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ff7r",name:"FINAL FANTASY VII REMAKE INTERGRADE",themeName:"ff7r",theme:{accent:"#1d6fb8"}},tabs:[{id:"equipment",label:"Equipment"},{id:"item",label:"Items"},{id:"materia",label:"Materia"},{id:"characters",label:"Characters"},{id:"abilities",label:"Abilities"},{id:"enemies",label:"Enemies"},{id:"loot",label:"Enemy Loot"},{id:"data",label:"Misc"},{id:"tweaks",label:"Tweaks"},{id:"text",label:"Text"}],activeTab:()=>state.tab,navigate,help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open FF7 Remake Data Map",dirtyCount,readonly:()=>state.activeSource!=="mine",history:editHistory,save,discard,projectSnapshot:()=>({canCreate:false,projects:[{name:"FF7R Mod",path:state.info?.projectRoot||"Project",valid:true,current:true}]}),projectSources:()=>[{key:"vanilla",label:"Vanilla",path:"Installed FF7R PAK resources"}],projectActiveSource:()=>state.activeSource,selectProjectSource,info:()=>navigate("info"),infoActive:()=>state.tab==="info",infoTitle:"Open FF7 Remake setup and runtime information"});
  editHistory.observe(document);

  (async()=>{try{
    [state.catalog,state.dataMap,state.info]=await Promise.all([api("/api/catalog"),api("/api/datamap"),api("/api/info")]);
    state.asset=assets()[0]?.asset||"";
    const availableLanguages=languages();state.textLanguage=availableLanguages.includes("US")?"US":availableLanguages[0]||"US";
    state.textAsset=textAssets().find(row=>row.language===state.textLanguage)?.asset||"";
    if(state.asset)await loadAsset(state.asset);else state.error="No FF7 Remake DataObject pairs were found in the installed PAKs.";
  }catch(error){state.error=error.message;render()}finally{LexeditorUI.finishPluginLoading();render()}})();
  
