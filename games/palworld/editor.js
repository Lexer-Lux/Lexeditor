"use strict";

const {el,detailPanel,detailSection,detailField,panelLayout,readonlyField,infoHelp}=LexeditorUI;
const TYPES=["Paks","Lua","LogicMods","UE4SS","PalSchema"];
const OFFICIAL_TAGS=["PalSchema","UE4SS","Model Replacement","Utilities","Gameplay","User Interface"];
let tab="package",info=null,model=null,savedModel=null,mapRows=[],shell=null;
let palCatalog=[],palPath="",palPatch=null,palSaved=null,palSelected="";
const clone=value=>JSON.parse(JSON.stringify(value));
const packageDirty=()=>model&&savedModel&&JSON.stringify(model)!==JSON.stringify(savedModel);
const patchDirty=()=>palPatch&&palSaved&&JSON.stringify(palPatch.records)!==JSON.stringify(palSaved.records);
const dirtyCount=()=>Number(packageDirty())+Number(patchDirty());
const refreshShell=()=>shell?.refresh?.();

async function api(path,options={}){
  const response=await fetch(path,{cache:"no-store",...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});
  let payload={};
  try{payload=await response.json()}catch(_error){payload={error:`HTTP ${response.status}`}}
  if(!response.ok)throw new Error(payload.error||`HTTP ${response.status}`);
  return payload;
}

function textControl(key,{placeholder=""}={}){
  return el("input",{type:"text",value:model[key]??"",placeholder,oninput:event=>{model[key]=event.target.value;refreshShell()}});
}
function numberControl(key){
  return el("input",{type:"number",min:0,step:1,value:model[key]??"",oninput:event=>{model[key]=event.target.value===""?null:Number(event.target.value);refreshShell()}});
}
function boolControl(key){
  return el("input",{type:"checkbox",checked:!!model[key],onchange:event=>{model[key]=event.target.checked;refreshShell()}});
}
function listControl(key){
  return el("textarea",{rows:3,value:Array.isArray(model[key])?model[key].join("\n"):"",oninput:event=>{model[key]=event.target.value.split(/[\n,]+/).map(value=>value.trim()).filter(Boolean);refreshShell()}});
}
function tagControl(){
  const known=new Set(Array.isArray(model.Tags)?model.Tags.filter(tag=>OFFICIAL_TAGS.includes(tag)):[]);
  const unknown=Array.isArray(model.Tags)?model.Tags.filter(tag=>!OFFICIAL_TAGS.includes(tag)):[];
  return el("div",{},...OFFICIAL_TAGS.map(tag=>{
    const input=el("input",{type:"checkbox",checked:known.has(tag),onchange:event=>{
      if(event.target.checked)known.add(tag);else known.delete(tag);
      model.Tags=[...OFFICIAL_TAGS.filter(value=>known.has(value)),...unknown];refreshShell();
    }});
    return el("label",{class:"lex-check-row"},input,el("span",{},tag));
  }),unknown.length?el("div",{class:"lex-muted"},`Preserved unknown tags: ${unknown.join(", ")}`):null);
}
function selectType(rule){
  return el("select",{onchange:event=>{rule.Type=event.target.value;refreshShell()}},...TYPES.map(value=>{
    const option=el("option",{value},value);option.selected=value===rule.Type;return option;
  }));
}
function ruleCard(rule,index){
  const server=el("input",{type:"checkbox",checked:!!rule.IsServer,onchange:event=>{if(event.target.checked)rule.IsServer=true;else delete rule.IsServer;refreshShell()}});
  const targets=el("textarea",{rows:2,value:Array.isArray(rule.Targets)?rule.Targets.join("\n"):"",oninput:event=>{rule.Targets=event.target.value.split(/\n+/).map(value=>value.trim()).filter(Boolean);refreshShell()}});
  return el("div",{class:"pal-rule"},
    el("div",{class:"pal-rule-head"},el("span",{},`INSTALL RULE ${index+1}`),el("button",{type:"button",onclick:()=>{model.InstallRule.splice(index,1);render();refreshShell()}},"Remove")),
    el("div",{class:"pal-rule-fields"},
      detailField({label:"TYPE",control:selectType(rule),dataType:"ENUM"}),
      detailField({label:"SERVER",control:server,dataType:"BOOL",help:infoHelp("Dedicated-server rule. Omitted means the normal client rule.")}),
      detailField({label:"TARGETS",control:targets,help:infoHelp("Paths are relative to the package root. Lexeditor rejects absolute paths and parent traversal.")})
    )
  );
}
function issueSection(){
  const issues=Array.isArray(info?.issues)?info.issues:[];
  if(!issues.length)return null;
  return detailSection({title:"VALIDATION",body:issues.map(issue=>el("div",{class:`pal-issue ${issue.severity||""}`},`${String(issue.severity||"").toUpperCase()}: ${issue.path} — ${issue.message}`))});
}
function packagePanel(){
  const sections=[detailSection({title:"PACKAGE",body:[
    detailField({label:"MOD NAME",control:textControl("ModName")}),
    detailField({label:"PACKAGE NAME",control:textControl("PackageName"),help:infoHelp("Pocketpair's uploader accepts ASCII letters and digits only. PackageName is the loader identity, so collisions are unsafe.")}),
    detailField({label:"VERSION",control:textControl("Version"),help:infoHelp("The official loader compares this as a plain string to decide whether to reinstall the package.")}),
    detailField({label:"AUTHOR",control:textControl("Author")}),
    detailField({label:"THUMBNAIL",control:textControl("Thumbnail")}),
    detailField({label:"MIN REVISION",control:numberControl("MinRevision"),dataType:"INT",min:0}),
    detailField({label:"DEBUG MODE",control:boolControl("DebugMode"),dataType:"BOOL",help:infoHelp("Official loader debug mode forces package reinstall on each launch.")}),
  ]}),detailSection({title:"DEPENDENCIES & TAGS",body:[
    detailField({label:"DEPENDENCIES",control:listControl("Dependencies"),help:infoHelp("One official package name per line.")}),
    detailField({label:"WORKSHOP TAGS",control:tagControl()}),
  ]}),detailSection({title:"INSTALL RULES",body:[
    el("div",{class:"pal-rules"},...(Array.isArray(model.InstallRule)?model.InstallRule:[]).map(ruleCard)),
    el("div",{class:"pal-actions"},el("button",{type:"button",onclick:()=>{(model.InstallRule??=[]).push({Type:"Paks",Targets:["./Paks/"]});render();refreshShell()}},"Add install rule")),
  ]})];
  const issues=issueSection();if(issues)sections.push(issues);
  return detailPanel({className:"pal-detail",title:model.ModName||model.PackageName||"Palworld Package",identity:model.PackageName||"PACKAGE",meta:"Official v0.7+ mod package",body:sections});
}

function recordKey(row){return `${row.table}\0${row.row}\0${row.field}`}
function selectedPatchRecord(){
  if(!palPatch?.records?.length)return null;
  return palPatch.records.find(row=>recordKey(row)===palSelected)||palPatch.records[0];
}
function setPatchValue(record,value){record.value=value;refreshShell()}
function scalarControl(record){
  if(!record.writable)return readonlyField(typeof record.value==="object"?JSON.stringify(record.value):String(record.value??"null"));
  if(record.kind==="bool")return el("input",{type:"checkbox",checked:!!record.value,onchange:event=>setPatchValue(record,event.target.checked)});
  if(record.kind==="int"||record.kind==="float")return el("input",{type:"number",step:record.kind==="int"?1:"any",value:record.value,oninput:event=>{if(event.target.value==="")return;setPatchValue(record,record.kind==="int"?Number.parseInt(event.target.value,10):Number(event.target.value))}});
  return el("input",{type:"text",value:record.value??"",oninput:event=>setPatchValue(record,event.target.value)});
}
function patchList(){
  const rows=palPatch?.records||[];
  if(!rows.length)return el("div",{class:"pal-empty"},"No raw-table properties found in this patch.");
  return el("div",{class:"pal-patch-list"},...rows.map(row=>{
    const key=recordKey(row);
    return el("button",{type:"button",class:`pal-patch-row${key===palSelected?" selected":""}`,onclick:()=>{palSelected=key;render()}},
      el("span",{class:"pal-patch-table-name"},row.table),
      el("span",{class:"pal-patch-row-name"},row.row),
      el("span",{class:"pal-patch-field-name"},row.field),
      el("span",{class:"pal-patch-value"},row.kind==="complex"||row.kind==="filters"?JSON.stringify(row.value):String(row.value??"null"))
    );
  }));
}
function patchDetail(){
  const record=selectedPatchRecord();
  if(!record)return detailPanel({className:"pal-detail",title:"PalSchema",identity:"RAW",meta:"No selected property",body:[detailSection({title:"PATCH",body:[detailField({label:"STATUS",control:readonlyField("No patch property selected")})]})]});
  const reason=record.writable?"Existing scalar property; Lexeditor preserves its JSON type.":(record.reason||"Read-only.");
  return detailPanel({className:"pal-detail",title:record.field,identity:record.row,meta:record.table,body:[
    detailSection({title:"TARGET",body:[
      detailField({label:"DATA TABLE",control:readonlyField(record.table)}),
      detailField({label:"ROW",control:readonlyField(record.row)}),
      detailField({label:"PROPERTY",control:readonlyField(record.field)}),
      detailField({label:"PATCH VALUE",control:scalarControl(record),dataType:(record.kind||"JSON").toUpperCase(),help:infoHelp(reason)}),
    ]}),
    detailSection({title:"WRITE BOUNDARY",body:[
      detailField({label:"FILE",control:readonlyField(palPath||"None")}),
      detailField({label:"FORMAT",control:readonlyField(palPatch?.writable?".json — structured scalar writes enabled":".jsonc — read-only changed writes")}),
      detailField({label:"SEMANTICS",control:readonlyField("PalSchema applies only the named DataTable / row / property at runtime")}),
    ]}),
  ]});
}
function patchSelector(){
  const select=el("select",{disabled:patchDirty(),onchange:async event=>{await selectPatch(event.target.value)}},...palCatalog.map(row=>{const option=el("option",{value:row.path},`${row.mod} / ${row.name}${row.writable?"":" (read only)"}`);option.selected=row.path===palPath;return option}));
  return el("div",{class:"pal-patch-toolbar"},el("span",{class:"pal-patch-label"},"RAW PATCH"),select,patchDirty()?el("span",{class:"pal-issue"},"Save or discard current patch edits before switching files."):null);
}
function palschemaPanel(){
  if(!palCatalog.length)return detailPanel({className:"pal-detail",title:"PalSchema",identity:"RAW",meta:"No raw patches discovered",body:[detailSection({title:"DISCOVERY",body:[detailField({label:"STATUS",control:readonlyField("No direct <PalSchema target>/<mod>/raw/*.json[c] files found")}),detailField({label:"BOUNDARY",control:readonlyField("Only official Type=PalSchema InstallRule Targets are scanned")})]})]});
  return el("div",{class:"pal-schema-root"},patchSelector(),el("div",{class:"pal-schema-columns"},patchList(),patchDetail()));
}

function infoPanel(){
  return detailPanel({className:"pal-detail",title:"Information",identity:"PALWORLD",meta:"Current plugin boundary",body:[
    detailSection({title:"PROJECT",body:[detailField({label:"ROOT",control:readonlyField(info?.project||"Unavailable")}),detailField({label:"SOURCE HASH",control:readonlyField(info?.sourceSha256||"Unavailable")})]}),
    detailSection({title:"SCOPE",body:[detailField({label:"LOADER",control:readonlyField("Pocketpair official v0.7+ loader + PalSchema raw patches")}),detailField({label:"EDITABLE",control:readonlyField("Info.json; existing scalar fields in PalSchema raw .json patches")}),detailField({label:"READ ONLY",control:readonlyField("JSONC changed writes, nested PalSchema data, filters/deletions, raw Unreal assets")})]}),
  ]});
}
const mapState={page:0,query:"",status:"",sort:["filename",1]};
function dataMapPanel(){return LexeditorUI.dataMap({rows:mapRows,page:mapState.page,query:mapState.query,status:mapState.status,sort:mapState.sort,changePage:value=>{mapState.page=value;render()},changeQuery:value=>{mapState.query=value;mapState.page=0;render()},changeStatus:value=>{mapState.status=value;mapState.page=0;render()},changeSort:key=>{mapState.sort=[key,-mapState.sort[1]];render()}}).content}
function render(){
  if(!model)return;
  let content;if(tab==="datamap")content=dataMapPanel();else if(tab==="info")content=infoPanel();else if(tab==="palschema")content=palschemaPanel();else content=packagePanel();
  document.querySelector("#main").replaceChildren(panelLayout([content],"pal-layout",{layoutKey:`palworld-${tab}`,defaultSizes:[100]}));refreshShell();
}
async function selectPatch(path){
  if(patchDirty())return;
  palPath=path;palPatch=path?await api(`/api/palschema/patch?path=${encodeURIComponent(path)}`):null;palSaved=palPatch?clone(palPatch):null;palSelected=palPatch?.records?.length?recordKey(palPatch.records[0]):"";render();
}
function patchEdits(){
  if(!palPatch||!palSaved)return[];const before=new Map(palSaved.records.map(row=>[recordKey(row),row]));
  return palPatch.records.filter(row=>row.writable&&before.has(recordKey(row))&&JSON.stringify(row.value)!==JSON.stringify(before.get(recordKey(row)).value)).map(row=>({table:row.table,row:row.row,field:row.field,value:row.value}));
}
async function save(){
  if(patchDirty()){palPatch=await api("/api/palschema/patch/save",{method:"POST",body:JSON.stringify({path:palPath,sourceSha256:palPatch.sourceSha256,edits:patchEdits()})});palSaved=clone(palPatch);palSelected=palPatch.records.length?recordKey(palPatch.records[0]):""}
  if(packageDirty()){
    const editable=["ModName","PackageName","Thumbnail","Version","DebugMode","MinRevision","Author","Dependencies","Tags","InstallRule"];const changes={};for(const key of editable)changes[key]=model[key]??null;
    info=await api("/api/info/save",{method:"POST",body:JSON.stringify({sourceSha256:info.sourceSha256,changes})});model=clone(info.data);savedModel=clone(model);const catalog=await api("/api/palschema/catalog");palCatalog=catalog.patches||[];
  }
  render();
}
async function discard(){model=clone(savedModel);if(palSaved){palPatch=clone(palSaved);palSelected=palPatch.records.length?recordKey(palPatch.records[0]):""}render()}
function navigate(value){tab=value;render()}
async function init(){
  try{
    const results=await Promise.all([api("/api/info"),api("/api/data-map"),api("/api/palschema/catalog")]);info=results[0];mapRows=results[1].rows||[];palCatalog=results[2].patches||[];model=clone(info.data);savedModel=clone(model);
    if(palCatalog.length){palPath=palCatalog[0].path;palPatch=await api(`/api/palschema/patch?path=${encodeURIComponent(palPath)}`);palSaved=clone(palPatch);palSelected=palPatch.records.length?recordKey(palPatch.records[0]):""}
    shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"palworld",name:"Palworld",themeName:"palworld",theme:{accent:"#55c7d9","accent-text":"#08262c"}},tabs:[{id:"package",label:"Package"},{id:"palschema",label:"PalSchema"}],activeTab:()=>tab,navigate,help:()=>navigate("datamap"),helpActive:()=>tab==="datamap",helpTitle:"Open Palworld Data Map",dirtyCount,save,discard,projectSnapshot:()=>({canCreate:true,projects:[{name:model?.ModName||model?.PackageName||"Palworld package",path:info?.project||"",valid:true,current:true}]}),info:()=>navigate("info"),infoActive:()=>tab==="info",infoTitle:"Open Palworld setup and runtime information"});
    render();LexeditorUI.finishPluginLoading();
  }catch(error){document.querySelector("#main").replaceChildren(el("div",{class:"pal-issue error"},`Palworld project could not open: ${error.message}`));LexeditorUI.finishPluginLoading()}
}
init();
