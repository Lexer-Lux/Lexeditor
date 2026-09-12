"use strict";
state.mcmDefaults=null;
state.savedMcmDefaults=null;
state.mcmIndex=0;
const mcmEditable=value=>value?value.settings||[]:null;
const mcmDirty=()=>state.mcmDefaults?.available&&state.savedMcmDefaults?.available&&!same(mcmEditable(state.mcmDefaults),mcmEditable(state.savedMcmDefaults));
const dirtyCountWithoutMcm=dirtyCount;
dirtyCount=function(){return dirtyCountWithoutMcm()+Number(mcmDirty())};

function renderMcmDefaults(){
  if(!state.mcmDefaults?.available){
    main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"MCM Defaults"),el("div",{class:"bl-empty"},"This project does not contain typed MCM defaults in src/LexerSkillTweaksSettings.cs.")));return
  }
  const rows=state.mcmDefaults.settings||[];
  const record=rows[state.mcmIndex];
  const master=el("div",{class:"bl-master"},
    el("div",{class:"bl-master-head"},el("strong",{},`MCM Defaults (${rows.length})`)),
    el("div",{class:"bl-list"},...rows.map((row,index)=>el("button",{type:"button",class:`bl-item${index===state.mcmIndex?" active":""}`,onclick:()=>{state.mcmIndex=index;render()}},
      row.label,el("small",{},`${row.group} · ${row.kind}${row.requireRestart?" · restart":""}`))))
  );
  let control=null;
  if(record){
    if(record.kind==="bool")control=checkbox(record.default,value=>record.default=value);
    else control=numberInput(record.default,value=>record.default=record.kind==="int"?Math.round(value):value,{
      min:record.min,max:record.max,step:record.kind==="int"?1:"any"
    });
  }
  const detail=!record?el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"No supported MCM defaults parsed.")):el("div",{class:"bl-detail"},
    el("section",{class:"bl-panel"},el("h2",{},record.label),
      el("div",{class:"bl-grid"},
        ...fieldRow("Property",el("code",{},record.property)),
        ...fieldRow("Group",record.group),
        ...fieldRow("Default",control),
        ...(record.kind==="bool"?[]:fieldRow("Range",`${record.min} to ${record.max}`)),
        ...fieldRow("Restart required",record.requireRestart?"Yes":"No"),
        ...fieldRow("Source expression",el("code",{},record.defaultExpression||"implicit language default"))
      ),
      el("div",{class:"bl-note"},record.hint||"No MCM hint text."),
      el("div",{class:"bl-note"},"This edits the C# default backing field, not your currently saved MCM user profile. Lexeditor derives the control type and bounds from the SettingProperty attribute and refuses out-of-range writes.")
    ));
  main.replaceChildren(el("div",{class:"bl-split"},master,detail));
}

renderDataMap=function(){
  const view=LexeditorUI.dataMap({
    rows:state.datamap.rows,query:state.query,status:state.mapStatus,page:state.page,sort:state.sort,
    tableClass:"bannerlord-data-map",
    open:row=>{if(row.target==="module")navigate("module");else if(row.target==="build")navigate("build");else if(row.target==="skills")navigate("skills");else if(row.target==="effects")navigate("effects");else if(row.target==="perks")navigate("perks");else if(row.target==="xp")navigate("xp");else if(row.target==="settings")navigate("settings")},
    openSource,
    changeQuery:value=>{state.query=value;state.page=0;renderDataMap()},
    changeStatus:value=>{state.mapStatus=value;state.page=0;renderDataMap()},
    changePage:value=>{state.page=value;renderDataMap()},
    changeSort:key=>{const [active,direction]=state.sort;state.sort=[key,active===key?-direction:1];renderDataMap()}
  });
  main.replaceChildren(view.content);
};

render=function(){
  const views={module:renderModule,dependencies:renderDependencies,submodules:renderSubmodules,xmls:renderXmls,skills:renderSkills,effects:renderEffects,perks:renderPerks,xp:renderXpSources,settings:renderMcmDefaults,build:renderBuild,deployment:renderDeployment,datamap:renderDataMap,source:renderSource};
  (views[state.tab]||renderModule)();
  refresh();
};
