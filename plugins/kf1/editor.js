"use strict";
const {el,detailPanel,actionRow,stack,notice}=LexeditorUI;
let tab="settings",config=null,saved=null,error="",mapRows=[],query="",setup=false,profile="keep";
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
    let replaceCustom=false;
    if(profile!=="keep"&&config.controls.selected==="custom"){
      replaceCustom=await LexeditorUI.confirmAction({title:"Replace custom bindings?",message:"This replaces your keyboard and controller bindings with the selected preset.",confirmLabel:"Replace bindings",cancelLabel:"Keep my bindings"});
      if(!replaceCustom)return;
    }
    config=await request("/api/settings/controls",{sha256:config.sha256,controlsSha256:config.controls.sha256,profile,replaceCustom});saved=structuredClone(values());setup=false;error="";render();
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
      LexeditorUI.creditsPanel("kf1")
    ]));
  }else if(!config){
    main.replaceChildren(detailPanel({title:"Port settings",body:[notice(error||"Loading settings…"),actionRow(el("button",{type:"button",onclick:()=>reload().catch(problem=>{error=problem.message;render();})},"Reload"))]}));
  }else{
    const view=LexeditorUI.platformConfigView({config,query,showHeader:false,search:value=>{query=value;},change:(id,value)=>{fields().find(field=>field.id===id).value=value;shell.refresh();}});
    main.replaceChildren(stack(error?notice(error):null,
      detailPanel({title:"Controls",help:"Classic Controls restores the baseline upstream port bindings. Modern Controls adds RT/RB attack, LT/LB cast, Cross/E interact and Circle/Left Shift held run. Original Select/Tab menu and Triangle/Q item or spell bindings stay available; equipped maps use the same item action. Cross confirms and Circle backs out in menus. F2 remains optional Debug Tools; this port has no Remaster Editor.",body:[
        setup?stack(el("label",{},"Control preset",el("select",{"aria-label":"Control preset",onchange:event=>{profile=event.target.value;}},
          ...[["keep","Keep current bindings"],["classic","Classic Controls"],["modern","Modern Controls"]].map(([value,label])=>el("option",{value,selected:profile===value},label)))),
          actionRow(el("button",{type:"button",onclick:controls},"Finish control setup"),el("button",{type:"button",onclick:()=>{setup=false;render();}},"Cancel")))
        :actionRow(el("button",{type:"button",onclick:()=>{setup=true;profile="keep";render();}},"Run control setup again")),
      ]}),actionRow(el("button",{type:"button",onclick:()=>reload().catch(problem=>{error=problem.message;render();})},"Reload")),view));
  }
  shell.refresh();
}
function navigate(next){if(next==="mods"){shell.header.querySelector('[data-tab="mods"]').click();return;}tab=next;render();}
const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"kf1",name:"King's Field I"},
  tabs:[{id:"settings",label:"Settings"}],activeTab:()=>tab,navigate,
  help:()=>navigate("datamap"),helpActive:()=>tab==="datamap",info:()=>navigate("info"),infoActive:()=>tab==="info",
  dirtyCount:dirty,save,discard:reload,readonly:()=>false,
  projectSnapshot:async()=>({canCreate:false,projects:[]})});
Promise.all([reload(),request("/api/data-map").then(value=>{mapRows=value.rows;})])
  .catch(problem=>{error=problem.message;render();}).finally(()=>LexeditorUI.finishPluginLoading());
