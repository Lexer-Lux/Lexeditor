"use strict";
const {el,detailPanel,actionRow,stack,notice}=LexeditorUI;
let tab="settings",config=null,saved=null,error="",mapRows=[],query="",loading={};
const mapState={page:0,query:"",status:"",sort:["filename",1]};
async function request(path,body){
  const response=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const value=await response.json();if(!response.ok)throw new Error(value.error||"Request failed");return value;
}
const fields=()=>config?.sections.flatMap(section=>section.fields)||[];
const values=()=>Object.fromEntries(fields().map(field=>[field.id,field.value]));
const dirty=()=>saved&&JSON.stringify(values())!==JSON.stringify(saved)?1:0;
async function reload(){config=await request("/api/settings");saved=structuredClone(values());error="";render();}
async function save(){try{config=await request("/api/settings",{sha256:config.sha256,values:values()});saved=structuredClone(values());error="";render();}catch(problem){error=problem.message;render();}}
async function controls(){
  try{if(dirty())throw new Error("Save or discard your display changes before applying the controls.");
    config=await request("/api/settings/controls",{sha256:config.sha256});saved=structuredClone(values());error="";render();
  }catch(problem){error=problem.message;render();}
}
function render(){
  const main=document.querySelector("#main");
  if(tab==="datamap"){
    const map=LexeditorUI.dataMap({rows:mapRows,...mapState,open:row=>{if(row.target)navigate(row.target)},
      changePage:value=>{mapState.page=value;render();},changeQuery:value=>{mapState.query=value;mapState.page=0;render();},
      changeStatus:value=>{mapState.status=value;mapState.page=0;render();},changeSort:key=>{mapState.sort=[key,mapState.sort[0]===key?-mapState.sort[1]:1];render();}});main.replaceChildren(map.content);
  }else if(tab==="info"){
    main.replaceChildren(LexeditorUI.settingsColumns([
      detailPanel({title:"King's Field I",body:["Japanese 1994 release, SLPS-00017. English fan translation."]}),
      detailPanel({title:"Verdite1",help:"This setup uses the existing archive/recomp port. F1 opens its native settings. F2 opens Debug Tools only when that optional mod is enabled; this build has no Remaster Editor.",body:[el("a",{href:"https://github.com/Lexer-Lux/verdite1/tree/codex/kf1-settings",target:"_blank",rel:"noreferrer"},"Port source")]}),
      LexeditorUI.modLoaderSection({loader:loading.loader,output:loading.structure,order:loading.overriding,
        safety:"Mod setup leaves disc data, game binaries and memory cards unchanged.",
        removal:"Disable it in Mods with the game closed. The native loader leaves disabled library folders unloaded."}),
      LexeditorUI.creditsPanel("kf1")
    ]));
  }else if(!config){
    main.replaceChildren(detailPanel({title:"Port settings",body:[notice(error||"Loading settings…"),actionRow(el("button",{type:"button",onclick:()=>reload().catch(problem=>{error=problem.message;render();})},"Reload"))]}));
  }else{
    const view=LexeditorUI.platformConfigView({config,query,showHeader:false,search:value=>{query=value;},change:(id,value)=>{fields().find(field=>field.id===id).value=value;shell.refresh();}});
    main.replaceChildren(stack(error?notice(error):null,
      actionRow(el("button",{type:"button",onclick:controls},"Apply Lexer's controls"),
        LexeditorUI.infoHelp("RT and RB attack. LT, LB, Square and Q use the equipped spell or item, including the map. Cross and E interact. Hold Circle or Left Shift to run. Triangle or Tab opens the menu. Cross confirms and Circle backs out in menus."),
        el("button",{type:"button",onclick:()=>reload().catch(problem=>{error=problem.message;render();})},"Reload")),view));
  }
  shell.refresh();
}
function navigate(next){if(next==="mods"){shell.header.querySelector('[data-tab="mods"]').click();return;}tab=next;render();}
const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"kf1",name:"King's Field I"},
  tabs:[{id:"settings",label:"Settings"}],activeTab:()=>tab,navigate,
  help:()=>navigate("datamap"),helpActive:()=>tab==="datamap",info:()=>navigate("info"),infoActive:()=>tab==="info",
  dirtyCount:dirty,save,discard:reload,readonly:()=>false,
  projectSnapshot:async()=>({canCreate:false,projects:[]})});
Promise.all([reload(),request("/api/data-map").then(value=>{mapRows=value.rows;}),
  request("/shared/mod-loading.json").then(value=>{loading=value.plugins.kf1;})])
  .catch(problem=>{error=problem.message;render();}).finally(()=>LexeditorUI.finishPluginLoading());
