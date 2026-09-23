  "use strict";
  const {el,columnList,columnPreferences,detailPanel,detailSection,detailField,recordId,infoHelp,pagedListDetail,provenanceControl,platformConfigView,clone,EditHistory,subtabBar,tabbedPanel,readonlyField,infoIcon,integrationStatus,toggleRow}=LexeditorUI;
  const identity=window.__lexeditorPlugin||{id:"ff7",name:"Final Fantasy 7 (Original)",edition:"Steam"};
  const integrated=["accessories","armor","characters","initialState","initialInventory","initialMateria","stolenMateria","commands","playerAttacks","limitBreaks","magicOrder","items","itemSortOrder","keyItems","materia","materiaEquipEffects","materiaPriority","apMultiplier","weapons","enemies","encounters","enemyAttacks","shops","prices","texts","exeText","audioMixing","characterNames","growthCurves","growthBonuses","characterAI","enemyAI","formationAI","recruits","defaultNames","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings","worldMovement"];
  const unresolved=["tweaks","deployment"];
  const labels={accessories:"Accessories",armor:"Armor",characters:"Characters",initialState:"New game",initialInventory:"Starting inventory",initialMateria:"Starting Materia",stolenMateria:"Yuffie stolen Materia",commands:"Commands",playerAttacks:"Player attacks",limitBreaks:"Limit breaks",magicOrder:"Magic menu",items:"Items",itemSortOrder:"Name sort",keyItems:"Key items",materia:"Materia",materiaEquipEffects:"Equip effects",materiaPriority:"Menu priority",apMultiplier:"Master sale price",weapons:"Weapons",enemies:"Enemies",encounters:"Encounters",shops:"Shops",prices:"Prices",texts:"Text",exeText:"Executable text",audioMixing:"Audio mixing",enemyAttacks:"Enemy attacks",tweaks:"Tweaks",deployment:"Deployment",characterNames:"Initial names",growthCurves:"Growth curves",growthBonuses:"Growth bonuses",characterAI:"Character AI",enemyAI:"Enemy AI",formationAI:"Formation AI",recruits:"Recruits",defaultNames:"Default names",fieldEncounters:"Field encounters",worldEncounters:"World encounters",yuffieEncounters:"Yuffie encounters",chocoboRatings:"Chocobo ratings",worldMovement:"World movement"};
  const subtabLabels={characters:"Stats",characterNames:"Names",growthCurves:"Curves",growthBonuses:"Bonuses",characterAI:"AI",recruits:"Recruits",defaultNames:"Defaults",initialState:"Setup",initialInventory:"Inventory",initialMateria:"Materia",stolenMateria:"Stolen",itemSortOrder:"Name sort",keyItems:"Key items",encounters:"Battles",formationAI:"AI",fieldEncounters:"Field",worldEncounters:"World",yuffieEncounters:"Yuffie",chocoboRatings:"Chocobo",worldMovement:"Movement"};
  const groups={characters:["characters","characterNames","growthCurves","growthBonuses","characterAI","recruits","defaultNames"],initialState:["initialState","initialInventory","initialMateria","stolenMateria"],commands:["commands","playerAttacks","limitBreaks","magicOrder"],items:["items","itemSortOrder","keyItems"],materia:["materia","materiaEquipEffects","materiaPriority","apMultiplier"],enemies:["enemies","enemyAttacks","enemyAI"],encounters:["encounters","formationAI","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings","worldMovement"],shops:["shops","prices"],texts:["texts","exeText"]};
  const parentTab=id=>Object.keys(groups).find(key=>groups[key].includes(id))||id;
  const tabs=[...new Set([...integrated,...unresolved].map(parentTab))].map(id=>({id,label:labels[id]}));
  const api=async(path,options={})=>{const response=await fetch(path,options),body=await response.json();if(!response.ok)throw new Error(body.error||response.statusText);return body};
  const state={loaded:false,modOnly:false,tab:"items",dashboard:null,dataMap:null,data:null,records:{},saved:{},invalid:{},platformConfig:null,savedPlatformConfig:null,platformQuery:"",platformError:"",platformRevision:0,platformLoading:false,deployment:null,deploymentError:"",deploymentLoading:false,activeSource:"mine",selected:{},page:{},pageSize:{},query:{},sort:{},aiEvent:{},mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1],saving:false};
  const main=document.querySelector("#main");
  const category=()=>state.data.categories.find(value=>value.id===state.tab);
  const rowById=(group,id,source=state.records)=>(source?.[group]||[]).find(row=>row.id===id);
  const platformFields=config=>Object.fromEntries((config?.sections||[]).flatMap(section=>section.fields).map(field=>[field.id,field.value]));
  const platformChanges=()=>{const current=platformFields(state.platformConfig),saved=platformFields(state.savedPlatformConfig),changes={};for(const [id,value] of Object.entries(current))if(JSON.stringify(value)!==JSON.stringify(saved[id]))changes[id]=value;return changes};
  const kernelDirty=()=>JSON.stringify(state.records)!==JSON.stringify(state.saved);
  const dirtyCount=()=>state.activeSource!=="mine"?0:Number(kernelDirty()||Object.keys(state.invalid).length>0)+Object.keys(platformChanges()).length;
  const readonly=()=>state.saving||state.activeSource!=="mine";
  const shellRefresh=()=>shell?.refresh?.();

  // Returning early left #main completely empty until the kernel finished
  // reading, so whichever tab the user opened first was a blank page rather
  // than a page that was loading. A tab must always render something.
  function render(){if(!state.loaded){main.replaceChildren(detailPanel({className:"ff7-detail",title:"Loading FF7 data",identity:null,meta:"Reading kernel.bin",body:[detailSection({title:"STATUS",body:[detailField({label:"STATE",control:readonlyField("Reading the installed FF7 data files…")})]})]}));return}let content;if(state.tab==="info")content=infoView();else if(state.tab==="datamap")content=mapView();else if(state.tab==="tweaks")content=tweakView();else if(state.tab==="deployment")content=deploymentView();else if(integrated.includes(state.tab))content=dataWorkspace();else content=unresolvedView();main.replaceChildren(content);shellRefresh()}
  function navigate(tab){state.tab=tab;render();if(tab==="tweaks")void refreshPlatformConfig();if(tab==="deployment")void refreshDeployment()}
  async function save(){
    if(readonly())return;
    if(Object.keys(state.invalid).length)throw new Error("Correct the empty or out-of-range numeric fields before saving.");
    state.saving=true;state.platformRevision++;render();
    try{
      const kernelKeys=state.data.kernelCategories||["items","weapons","armor","accessories","materia","characters"];
      const subset=(keys,source)=>Object.fromEntries(keys.filter(key=>Object.hasOwn(source,key)).map(key=>[key,source[key]]));
      const kernelRecords=subset(kernelKeys,state.records);
      if(JSON.stringify(kernelRecords)!==JSON.stringify(subset(kernelKeys,state.saved))){
        const result=await api("/api/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({records:kernelRecords,sourceSha256:state.data.sourceSha256,activeSha256:state.data.activeSha256,usingProject:state.data.usingProject})});
        Object.assign(state.records,result.records||kernelRecords);Object.assign(state.saved,clone(result.records||kernelRecords));state.data.activeSha256=result.sha256;state.data.usingProject=true;state.dashboard.baseline.projectPath=result.path;
        editHistory.clear();
      }
      // Each source has its own verified atomic replacement and saved snapshot.
      // A later failure must not pretend an earlier file was rolled back.
      for(const [family,report] of Object.entries(state.data.families||{})){
        const records=subset(report.categories,state.records);
        if(JSON.stringify(records)===JSON.stringify(subset(report.categories,state.saved)))continue;
        const result=await api("/api/extended/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({family,records,sourceSha256:report.sourceSha256,activeSha256:report.activeSha256,usingProject:report.usingProject})});
        Object.assign(state.records,result.records||records);Object.assign(state.saved,clone(result.records||records));const {records:canonical,...snapshot}=result;Object.assign(report,snapshot);editHistory.clear();
      }
      const changes=platformChanges();
      if(Object.keys(changes).length){state.platformConfig=await api("/api/platform-config/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sha256:state.savedPlatformConfig.sha256,changes})});state.savedPlatformConfig=clone(state.platformConfig);state.platformError="";syncConfigMap(state.platformConfig)}
      editHistory.clear();
    }finally{state.saving=false;render()}
  }
  async function discard(){state.records=clone(state.saved);state.invalid={};state.platformConfig=clone(state.savedPlatformConfig);state.platformRevision++;editHistory.clear();render()}
  async function switchProjectSource(value){state.activeSource=String(value||"mine")==="vanilla"?"vanilla":"mine";state.records=clone(state.activeSource==="vanilla"?state.data.vanilla:state.saved);state.invalid={};state.platformRevision++;editHistory.clear();render()}
  const editHistory=new EditHistory({capture:()=>state.records,restore:snapshot=>{state.records=clone(snapshot);state.invalid={}},render:async()=>render(),enabled:()=>state.loaded&&!readonly(),changed:shellRefresh});
  const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:identity.id,name:identity.name,themeName:identity.id,theme:{}},tabs,activeTab:()=>parentTab(state.tab),navigate,help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the FF7 Data Map",info:()=>navigate("info"),infoActive:()=>state.tab==="info",infoTitle:"Open FF7 plugin information",projectSources:()=>[{key:"vanilla",label:"Vanilla",path:state.dashboard?.baseline?.source||"Installed unchanged KERNEL.BIN"}],projectActiveSource:()=>state.activeSource,selectProjectSource:switchProjectSource,dirtyCount,readonly,save,discard,history:editHistory});
  editHistory.observe(document);
  Promise.allSettled([api("/api/dashboard"),api("/api/datamap"),api("/api/data"),api("/api/platform-config"),api("/api/deployment")]).then(results=>{
    const [dashboard,map,data,config,deployment]=results;
    state.dashboard=dashboard.status==="fulfilled"?dashboard.value:{baseline:{message:dashboard.reason.message},game:{},problems:[]};
    state.dataMap=map.status==="fulfilled"?map.value:{rows:[{filename:"Data Map",controls:"Availability report",notes:map.reason.message,status:"blocked",openable:false}]};
    state.data=data.status==="fulfilled"?data.value:{categories:[],records:{},vanilla:{},errors:Object.fromEntries(integrated.map(key=>[key,data.reason.message]))};
    state.platformConfig=config.status==="fulfilled"?config.value:{available:false,runtime:"FFNx",format:"toml",path:"FFNx.toml in the selected game directory",sections:[],message:config.reason.message};
    state.platformError=config.status==="rejected"?config.reason.message:"";
    state.deployment=deployment.status==="fulfilled"?deployment.value:{ready:false,blocked:[deployment.reason.message],files:[],ffnx:{available:false,message:deployment.reason.message}};state.deploymentError=deployment.status==="rejected"?deployment.reason.message:"";syncDeploymentMap(state.deployment);
    for(const result of [map,data,config,deployment])if(result.status==="rejected")state.dashboard.problems.push(result.reason.message);
    state.records=clone(state.data.records);state.saved=clone(state.records);state.savedPlatformConfig=clone(state.platformConfig);
    for(const group of integrated)state.selected[group]=state.records[group]?.[0]?.id??null;
    state.loaded=true;
    if(state.dashboard.themeSounds)LexeditorUI.configureThemeSounds(state.dashboard.themeSounds);
    render();LexeditorUI.finishPluginLoading();
  }).catch(error=>{main.replaceChildren(detailPanel({className:"ff7-detail",title:"FF7 interface error",identity:null,meta:"Load failed",body:[detailSection({title:"ERROR",body:[detailField({label:"MESSAGE",control:readonlyField(error.message)})]})]}));LexeditorUI.finishPluginLoading()});
  window.addEventListener("focus",()=>{if(state.loaded&&state.tab==="tweaks")void refreshPlatformConfig()});
  setInterval(()=>{if(state.loaded&&state.tab==="tweaks"&&!state.platformConfig?.available&&document.visibilityState==="visible")void refreshPlatformConfig()},3000);
  window.addEventListener("lexeditor-settings-ready",()=>{if(state.loaded&&state.tab==="info")render()});
  
