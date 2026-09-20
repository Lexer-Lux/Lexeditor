"use strict";
state.mcmDefaults=null;
state.savedMcmDefaults=null;
state.mcmIndex=0;
const mcmEditable=value=>value?value.settings||[]:null;
const mcmDirty=()=>state.mcmDefaults?.available&&state.savedMcmDefaults?.available&&!same(mcmEditable(state.mcmDefaults),mcmEditable(state.savedMcmDefaults));
const dirtyCountWithoutMcm=dirtyCount;
dirtyCount=function(){return dirtyCountWithoutMcm()+Number(mcmDirty())};

function renderMcmDefaults(){
  if(!state.mcmDefaults?.available){main.replaceChildren(uiEmpty("Tweaks","This project does not contain typed MCM defaults in src/LexerSkillTweaksSettings.cs."));return}
  const grouped=new Map();
  for(const row of state.mcmDefaults.settings||[]){const group=row.group||"Other";if(!grouped.has(group))grouped.set(group,[]);grouped.get(group).push(row)}
  const cards=[...grouped].map(([group,rows])=>BLUI.detailSection({title:group,body:rows.map(row=>{
    let control;
    if(row.kind==="bool")control=checkbox(row.default,value=>row.default=value);
    else control=numberInput(row.default,value=>row.default=row.kind==="int"?Math.round(value):value,{min:row.min,max:row.max,step:row.kind==="int"?1:"any"});
    const explanation=[row.hint||"",row.requireRestart?"Requires a restart before Bannerlord uses the new default.":"Changes the C# default for new or unspecified MCM profile values; it does not overwrite an existing player's saved MCM profile."].filter(Boolean).join(" ");
    return BLUI.detailField({
      label:row.label,control,
      min:row.kind==="bool"?undefined:row.min,max:row.kind==="bool"?undefined:row.max,
      dataType:row.kind==="bool"?"BOOL":row.kind==="int"?"INT":"FLOAT",
      help:BLUI.infoHelp(explanation)
    });
  })}));
  const pageSize=6,pages=Math.max(1,Math.ceil(cards.length/pageSize));
  state.tweakPage=Math.max(0,Math.min(state.tweakPage,pages-1));
  const shown=cards.slice(state.tweakPage*pageSize,(state.tweakPage+1)*pageSize);
  main.replaceChildren(el("div",{class:"bannerlord-tweaks-page"},
    BLUI.settingsColumns(shown,{className:"bannerlord-tweaks"}),
    BLUI.pager({page:state.tweakPage,pages,total:cards.length,pageSize,change:value=>{state.tweakPage=value;render()}})
  ));
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
