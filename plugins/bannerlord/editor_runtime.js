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
    main.replaceChildren(uiEmpty("Runtime Overrides","Deploy the selected module with supported custom effect and XP definitions before editing runtime overrides.",[
      uiButton("Reload",()=>reloadRuntimeOverrides(false))
    ]));return
  }
  const effectMode=state.runtimeKind==="effects";
  const items=(effectMode?(value.effects||[]):(value.xpSources||[])).map((row,index)=>({
    index,row,label:row.label,skill:row.skillId,overridden:!!row.overridden,
    low:effectMode?Number(row.low):undefined,high:effectMode?Number(row.high):undefined,amount:effectMode?undefined:Number(row.amount),
    searchText:`${row.label} ${row.id} ${row.skillId} ${row.overridden?"override":"source default"}`
  }));
  const columns=effectMode?[
    {key:"label",label:"Effect"},{key:"skill",label:"Skill"},
    {key:"overridden",label:"Override",render:item=>item.row.overridden?"On":"Off",
      edit:(item,value)=>enableRuntimeOverride(item.row,!!value),editor:(item,commit)=>cellBool(item.row.overridden,commit)},
    {key:"low",label:"Level 0",numeric:true,edit:(item,value)=>{if(item.row.overridden){item.row.low=Number(value);refresh()}},editValue:item=>item.row.low,
      editor:(item,commit)=>item.row.overridden?cellNumber(item.row.low,commit,{step:"any"}):uiText(item.row.low)},
    {key:"high",label:"Level 100",numeric:true,edit:(item,value)=>{if(item.row.overridden){item.row.high=Number(value);refresh()}},editValue:item=>item.row.high,
      editor:(item,commit)=>item.row.overridden?cellNumber(item.row.high,commit,{step:"any"}):uiText(item.row.high)}
  ]:[
    {key:"label",label:"XP source"},{key:"skill",label:"Skill"},
    {key:"overridden",label:"Override",render:item=>item.row.overridden?"On":"Off",
      edit:(item,value)=>enableRuntimeOverride(item.row,!!value),editor:(item,commit)=>cellBool(item.row.overridden,commit)},
    {key:"amount",label:"XP",numeric:true,edit:(item,value)=>{if(item.row.overridden){item.row.amount=Math.max(0,Number(value));refresh()}},editValue:item=>item.row.amount,
      editor:(item,commit)=>item.row.overridden?cellNumber(item.row.amount,commit,{min:0,step:"any"}):uiText(item.row.amount)}
  ];
  const detail=item=>{
    const row=item.row;
    const fields=[
      readField("Internal name",row.id,"Stable deployed JSON key."),
      readField("Skill",row.skillId),
      boolField("Override deployed value",row.overridden,value=>enableRuntimeOverride(row,value),"When enabled, deployed ModuleData JSON takes precedence over the C# source default without rebuilding.")
    ];
    if(effectMode){
      fields.push(
        readField("Source default @0",`${row.defaultLow}${row.suffix||""}`),
        readField("Source default @100",`${row.defaultHigh}${row.suffix||""}`),
        BLUI.detailField({label:"Runtime @0",control:numberInput(row.low,value=>row.low=value,{disabled:!row.overridden,step:"any"}),help:BLUI.infoHelp("Deployed gameplay magnitude at custom skill level 0.")}),
        BLUI.detailField({label:"Runtime @100",control:numberInput(row.high,value=>row.high=value,{disabled:!row.overridden,step:"any"}),help:BLUI.infoHelp("Deployed gameplay magnitude at custom skill level 100.")}),
        readField("Runtime slope",(Number(row.high)-Number(row.low))/100)
      );
    }else{
      fields.push(
        readField("Source default",`${row.defaultAmount} XP`),
        BLUI.detailField({label:"Runtime amount",control:numberInput(row.amount,value=>row.amount=Math.max(0,value),{disabled:!row.overridden,min:0,step:"any"}),min:0,help:BLUI.infoHelp("Deployed XP amount used instead of the C# fallback while this override is enabled.")})
      );
    }
    return BLUI.detailPanel({title:row.label,meta:row.id,body:[
      BLUI.detailSection({title:"DEPLOYED VALUE",body:fields}),
      BLUI.detailSection({title:"LOCATION",body:[readField("Deployed module",value.deployedRoot)]})
    ]});
  };
  const table=tableView({
    key:`runtime-${state.runtimeKind}`,rows:items,keyOf:item=>item.index,columns,detail,
    noun:effectMode?"runtime effects":"runtime XP sources",
    placeholder:effectMode?"Search runtime effects…":"Search runtime XP…",
    selected:state.runtimeIndex,setSelected:value=>state.runtimeIndex=Number(value),
    filters:[uiButton("Reload",()=>reloadRuntimeOverrides())]
  });
  main.replaceChildren(BLUI.tabbedPanel({
    tabs:[{id:"effects",label:"Effects"},{id:"xp",label:"XP"}],active:state.runtimeKind,label:"Runtime override type",
    change:kind=>{state.runtimeKind=kind;state.runtimeIndex=0;render()},content:table
  }));
}
