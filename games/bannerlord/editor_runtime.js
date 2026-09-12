"use strict";
state.runtimeOverrides=null;
state.savedRuntimeOverrides=null;
state.runtimeKind="effects";
state.runtimeIndex=0;

const runtimeEditable=value=>value?{
  effects:(value.effects||[]).map(row=>({id:row.id,overridden:!!row.overridden,low:Number(row.low),high:Number(row.high)})),
  xpSources:(value.xpSources||[]).map(row=>({id:row.id,overridden:!!row.overridden,amount:Number(row.amount)}))
}:null;
const runtimeDirty=()=>state.runtimeOverrides&&state.savedRuntimeOverrides&&!same(runtimeEditable(state.runtimeOverrides),runtimeEditable(state.savedRuntimeOverrides));
const dirtyCountWithoutRuntime=dirtyCount;
dirtyCount=function(){return dirtyCountWithoutRuntime()+Number(runtimeDirty())};

async function reloadRuntimeOverrides(ask=true){
  if(ask&&runtimeDirty()){
    const confirmed=await confirmAction({
      title:"Reload runtime overrides?",
      message:"Discard unsaved Runtime Override changes and reload the deployed JSON from disk?",
      confirmLabel:"Reload"
    });
    if(!confirmed)return;
  }
  try{
    const value=await api("/api/runtime-overrides");
    state.runtimeOverrides=value;state.savedRuntimeOverrides=clone(value);
    render();refresh();
  }catch(error){showAlert?.(String(error.message||error),"Could not reload runtime overrides")}
}

function enableRuntimeOverride(row,enabled){
  row.overridden=enabled;
  if(!enabled){
    if(state.runtimeKind==="effects"){
      row.low=Number(row.defaultLow);row.high=Number(row.defaultHigh);
    }else row.amount=Number(row.defaultAmount);
  }
  render();refresh();
}

function renderRuntimeOverrides(){
  const value=state.runtimeOverrides;
  if(!value?.available){
    main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Runtime Overrides"),
      el("div",{class:"bl-empty"},"The selected Bannerlord module must be deployed and contain supported custom effect/XP definitions before runtime overrides can be edited."),
      el("button",{type:"button",onclick:()=>reloadRuntimeOverrides(false)},"Reload")));return
  }
  const effectMode=state.runtimeKind==="effects";
  const rows=effectMode?(value.effects||[]):(value.xpSources||[]);
  state.runtimeIndex=Math.max(0,Math.min(state.runtimeIndex,Math.max(0,rows.length-1)));
  const record=rows[state.runtimeIndex];
  const master=el("div",{class:"bl-master"},
    el("div",{class:"bl-master-head"},
      el("strong",{},effectMode?`Runtime Effects (${rows.length})`:`Runtime XP (${rows.length})`),
      el("button",{type:"button",class:effectMode?"active":"",onclick:()=>{state.runtimeKind="effects";state.runtimeIndex=0;render()}},"Effects"),
      el("button",{type:"button",class:!effectMode?"active":"",onclick:()=>{state.runtimeKind="xp";state.runtimeIndex=0;render()}},"XP"),
      el("button",{type:"button",onclick:()=>reloadRuntimeOverrides()},"Reload")),
    el("div",{class:"bl-list"},...rows.map((row,index)=>el("button",{
      type:"button",class:`bl-item${index===state.runtimeIndex?" active":""}`,onclick:()=>{state.runtimeIndex=index;render()}
    },row.label,el("small",{},`${row.skillId} · ${row.overridden?"override":"source default"}`))))
  );
  let detail;
  if(!record)detail=el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"No supported runtime values."));
  else{
    const controls=[
      ...fieldRow(effectMode?"Effect ID":"Source ID",el("code",{},record.id)),
      ...fieldRow("Skill",record.skillId),
      ...fieldRow("Override deployed value",checkbox(record.overridden,value=>enableRuntimeOverride(record,value)))
    ];
    if(effectMode){
      controls.push(
        ...fieldRow("Source default @0",`${record.defaultLow}${record.suffix||""}`),
        ...fieldRow("Source default @100",`${record.defaultHigh}${record.suffix||""}`),
        ...fieldRow("Runtime @0",numberInput(record.low,value=>record.low=value,{disabled:!record.overridden,step:"any"})),
        ...fieldRow("Runtime @100",numberInput(record.high,value=>record.high=value,{disabled:!record.overridden,step:"any"})),
        ...fieldRow("Runtime slope",String((Number(record.high)-Number(record.low))/100))
      );
    }else{
      controls.push(
        ...fieldRow("Source default",`${record.defaultAmount} XP`),
        ...fieldRow("Runtime amount",numberInput(record.amount,value=>record.amount=value,{disabled:!record.overridden,min:0,step:"any"}))
      );
    }
    detail=el("div",{class:"bl-detail"},el("section",{class:"bl-panel"},
      el("h2",{},record.label),el("div",{class:"bl-grid"},...controls),
      el("div",{class:"bl-note"},record.overridden?
        "This value is written to the deployed module's ModuleData JSON and takes precedence over the C# default at runtime.":
        "No deployed override is active. Bannerlord will use the C# source default. Enable the override to tune runtime behavior without rebuilding."),
      el("div",{class:"bl-note"},`Deployed module: ${value.deployedRoot}`)
    ));
  }
  main.replaceChildren(el("div",{class:"bl-split"},master,detail));
}

const renderDataMapBeforeRuntime=renderDataMap;
renderDataMap=function(){
  const view=LexeditorUI.dataMap({
    rows:state.datamap.rows,query:state.query,status:state.mapStatus,page:state.page,sort:state.sort,
    tableClass:"bannerlord-data-map",
    open:row=>{
      if(row.target==="runtime")navigate("runtime");
      else if(row.target==="module")navigate("module");
      else if(row.target==="build")navigate("build");
      else if(row.target==="skills")navigate("skills");
      else if(row.target==="effects")navigate("effects");
      else if(row.target==="perks")navigate("perks");
      else if(row.target==="xp")navigate("xp");
      else if(row.target==="settings")navigate("settings");
    },
    openSource,
    changeQuery:value=>{state.query=value;state.page=0;renderDataMap()},
    changeStatus:value=>{state.mapStatus=value;state.page=0;renderDataMap()},
    changePage:value=>{state.page=value;renderDataMap()},
    changeSort:key=>{const [active,direction]=state.sort;state.sort=[key,active===key?-direction:1];renderDataMap()}
  });
  main.replaceChildren(view.content);
};

render=function(){
  const views={module:renderModule,dependencies:renderDependencies,submodules:renderSubmodules,xmls:renderXmls,
    skills:renderSkills,effects:renderEffects,perks:renderPerks,xp:renderXpSources,settings:renderMcmDefaults,
    runtime:renderRuntimeOverrides,build:renderBuild,deployment:renderDeployment,datamap:renderDataMap,source:renderSource};
  (views[state.tab]||renderModule)();refresh();
};
