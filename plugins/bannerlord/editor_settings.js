"use strict";
state.mcmDefaults=null;
state.savedMcmDefaults=null;
state.mcmIndex=0;
const mcmEditable=value=>value?value.settings||[]:null;
const mcmDirty=()=>state.mcmDefaults?.available&&state.savedMcmDefaults?.available&&!same(mcmEditable(state.mcmDefaults),mcmEditable(state.savedMcmDefaults));
const dirtyCountWithoutMcm=dirtyCount;
dirtyCount=function(){return dirtyCountWithoutMcm()+Number(mcmDirty())};

// The shared Tweaks page: the mod's MCM defaults, and ReShade on a subtab of
// its own, which the page loads and drives.
function renderMcmDefaults(){
  const page=cards=>main.replaceChildren(LexeditorUI.tweaksPage({plugin:"bannerlord",render,
    pages:[{id:"mcm",label:"MCM Defaults",body:()=>cards}]}));
  if(!state.mcmDefaults?.available){page([uiEmpty("Tweaks","This project does not contain typed MCM defaults in src/LexerSkillTweaksSettings.cs.")]);return}
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
  page(cards);
}
