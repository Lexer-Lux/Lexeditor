"use strict";
state.moduleDataFiles=null;
state.moduleData=null;
state.savedModuleData=null;
state.moduleDataRecordPath="";
state.moduleDataElementPath="";
state.moduleDataFilter="";
state.moduleDataNewId="";

function prepareModuleData(value){
  for(const element of value?.elements||[]){
    for(const missing of element.missingRequired||[]){
      if(missing.add===undefined)missing.add=false;
      if(missing.value===undefined){
        if(missing.fixed!==undefined)missing.value=String(missing.fixed);
        else if(missing.default!==undefined)missing.value=String(missing.default);
        else if(missing.choices?.length)missing.value=String(missing.choices[0]);
        else if(missing.kind==="bool")missing.value="false";
        else if(missing.kind==="number")missing.value=String(missing.min!==undefined?missing.min:0);
        else missing.value="";
      }
    }
  }
  return value;
}

const moduleDataEditable=value=>value?{
  relativePath:value.relativePath,
  elements:(value.elements||[]).map(element=>({
    path:element.path,tag:element.tag,
    attributes:(element.attributes||[]).map(attribute=>({name:attribute.name,value:String(attribute.value)})),
    missingRequired:(element.missingRequired||[]).map(attribute=>({
      name:attribute.name,add:!!attribute.add,value:attribute.add?String(attribute.value??""):""
    }))
  }))
}:null;
const moduleDataDirty=()=>state.moduleData&&state.savedModuleData&&!same(moduleDataEditable(state.moduleData),moduleDataEditable(state.savedModuleData));
const dirtyCountWithoutModuleData=dirtyCount;
dirtyCount=function(){return dirtyCountWithoutModuleData()+Number(moduleDataDirty())};

function defaultDuplicateId(record){return record?.id?`${record.id}_copy`:""}
function applyModuleDataRecordSelection(record){
  state.moduleDataRecordPath=record?.path||"";
  state.moduleDataElementPath=record?.path||"";
  state.moduleDataNewId=defaultDuplicateId(record);
}
const xmlBooleanChecked=value=>["true","1"].includes(String(value).trim().toLowerCase());

async function ensureModuleDataFiles(){
  if(state.moduleDataFiles!==null)return state.moduleDataFiles;
  try{
    const result=await api("/api/module-data-files");
    state.moduleDataFiles=result.files||[];
    if(!state.moduleData&&state.moduleDataFiles.length)await loadModuleData(state.moduleDataFiles[0],false);
  }catch(error){
    state.moduleDataFiles=[];
    showAlert?.(String(error.message||error),"ModuleData scan failed");
  }
  return state.moduleDataFiles;
}

async function reloadModuleData(){
  if(!state.moduleData)return;
  await loadModuleData(state.moduleData.relativePath,true);
}

async function loadModuleData(path,ask=true){
  if(!path)return;
  if(ask&&moduleDataDirty()){
    const confirmed=await confirmAction({
      title:"Discard unsaved ModuleData changes?",
      message:"Discard unsaved ModuleData changes?",confirmLabel:"Discard"
    });
    if(!confirmed)return;
  }
  try{
    const value=prepareModuleData(await api(`/api/module-data?path=${encodeURIComponent(path)}`));
    state.moduleData=value;state.savedModuleData=clone(value);
    applyModuleDataRecordSelection(value.records?.[0]);
    state.moduleDataFilter="";
    state.tab="moduledata";render();
  }catch(error){showAlert?.(String(error.message||error),"Could not open ModuleData XML")}
}

function moduleDataControl(attribute){
  if(attribute.fixed!==undefined)return el("code",{title:"Fixed by Bannerlord XSD"},String(attribute.value));
  const assign=value=>{attribute.value=String(value);refresh()};
  if(attribute.kind==="bool")return checkbox(xmlBooleanChecked(attribute.value),value=>assign(value?"true":"false"));
  if(attribute.kind==="enum")return select(attribute.value,(attribute.choices||[]).map(value=>[value,value]),assign);
  if(attribute.kind==="number"){
    const attrs={step:attribute.integer?1:"any"};
    if(attribute.min!==undefined)attrs.min=attribute.min;
    if(attribute.max!==undefined)attrs.max=attribute.max;
    return numberInput(Number(attribute.value),assign,attrs);
  }
  return textInput(attribute.value,assign,{spellcheck:"false"});
}

function missingRequiredValueControl(attribute){
  const disabled=!attribute.add;
  const assign=value=>{attribute.value=String(value);refresh()};
  if(attribute.fixed!==undefined)return el("code",{},String(attribute.fixed));
  if(attribute.kind==="bool")return el("input",{
    type:"checkbox",checked:xmlBooleanChecked(attribute.value),disabled,
    onchange:event=>assign(event.target.checked?"true":"false")
  });
  if(attribute.kind==="enum"){
    const node=el("select",{disabled,onchange:event=>assign(event.target.value)},
      ...(attribute.choices||[]).map(value=>el("option",{value},value)));
    node.value=String(attribute.value);return node;
  }
  if(attribute.kind==="number"){
    const attrs={disabled,step:attribute.integer?1:"any"};
    if(attribute.min!==undefined)attrs.min=attribute.min;
    if(attribute.max!==undefined)attrs.max=attribute.max;
    return numberInput(Number(attribute.value),assign,attrs);
  }
  return textInput(attribute.value,assign,{disabled,spellcheck:"false"});
}

function missingRequiredControl(attribute){
  const toggle=el("input",{
    type:"checkbox",checked:!!attribute.add,title:"Add this XSD-required attribute on Save",
    onchange:event=>{attribute.add=event.target.checked;render();refresh()}
  });
  return el("div",{class:"bl-control"},toggle,missingRequiredValueControl(attribute));
}

function moduleDataAttributeLabel(attribute){
  const suffix=[];
  if(attribute.required)suffix.push("required");
  if(attribute.schemaType)suffix.push(attribute.schemaType);
  if(attribute.schemaIssue)suffix.push("⚠ invalid");
  return suffix.length?`${attribute.name} · ${suffix.join(" · ")}`:attribute.name;
}
function moduleDataRecordLabel(record){const identity=record.name||record.id||"";return identity?`${record.tag} · ${identity}`:record.tag}

function selectModuleDataRecord(path){
  const record=(state.moduleData?.records||[]).find(row=>row.path===path);
  applyModuleDataRecordSelection(record);render();
}

async function runModuleDataRecordAction(action,record){
  if(!record)return;
  if(moduleDataDirty()){
    showAlert?.("Save or discard this ModuleData file's pending attribute edits before duplicating or deleting a record.","Unsaved ModuleData edits");
    return;
  }
  if(action==="delete"){
    const confirmed=await confirmAction({
      title:"Delete ModuleData record?",
      message:`Delete ${moduleDataRecordLabel(record)} from ${state.moduleData.relativePath}? A .lexeditor.bak backup will be created.`,
      confirmLabel:"Delete"
    });
    if(!confirmed)return;
  }
  const newId=state.moduleDataNewId.trim();
  if(action==="duplicate"&&record.id&&!newId){showAlert?.("Enter a new record ID before duplicating this record.","New ID required");return}
  try{
    const payload={recordAction:action,elementPath:record.path,tag:record.tag,originalId:record.id||""};
    if(action==="duplicate")payload.newId=newId;
    const result=prepareModuleData(await post("/api/module-data/save",{
      path:state.moduleData.relativePath,edits:[payload],sourceHash:state.savedModuleData.sourceHash||""
    }));
    state.moduleData=result;state.savedModuleData=clone(result);
    let selected=null;
    if(action==="duplicate"&&newId)selected=(result.records||[]).find(row=>row.id===newId);
    if(!selected)selected=(result.records||[]).find(row=>row.path===record.path)||(result.records||[])[0];
    applyModuleDataRecordSelection(selected);render();refresh();
  }catch(error){showAlert?.(String(error.message||error),`ModuleData ${action} failed`)}
}

function renderModuleData(){
  if(state.moduleDataFiles===null){main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"ModuleData XML"),el("div",{class:"bl-empty"},"Scanning ModuleData…")));ensureModuleDataFiles().then(()=>render());return}
  if(!state.moduleDataFiles.length){main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"ModuleData XML"),el("div",{class:"bl-empty"},"No XML files found under ModuleData.")));return}
  if(!state.moduleData){loadModuleData(state.moduleDataFiles[0],false);return}

  const filter=state.moduleDataFilter.trim().toLowerCase();
  const records=(state.moduleData.records||[]).filter(record=>!filter||`${record.tag} ${record.id||""} ${record.name||""} ${record.path}`.toLowerCase().includes(filter));
  let record=(state.moduleData.records||[]).find(row=>row.path===state.moduleDataRecordPath);
  if(!record&&records.length){record=records[0];applyModuleDataRecordSelection(record)}
  const nodes=record?(state.moduleData.elements||[]).filter(element=>element.path===record.path||element.path.startsWith(record.path+"/")):[];
  let node=nodes.find(element=>element.path===state.moduleDataElementPath);
  if(!node&&nodes.length){node=nodes[0];state.moduleDataElementPath=node.path}

  const fileSelect=select(state.moduleData.relativePath,state.moduleDataFiles.map(path=>[path,path]),value=>loadModuleData(value));
  const schema=state.moduleData.schema,issueCount=state.moduleData.schemaIssueCount||0;
  const master=el("div",{class:"bl-master"},
    el("div",{class:"bl-master-head"},el("strong",{},`${state.moduleData.rootTag} (${state.moduleData.recordCount||0})`),
      el("button",{type:"button",onclick:()=>reloadModuleData()},"Reload")),
    el("div",{class:"bl-list-block"},fileSelect),
    el("div",{class:"bl-list-block"},schema?el("div",{},el("strong",{},`XSD: ${schema.id||"matched schema"}`),el("small",{},` · ${schema.path||""}`),el("div",{class:"bl-note"},issueCount?`⚠ ${issueCount} schema issue(s) detected in this document.`:"No XSD attribute issues detected.")):el("div",{class:"bl-note"},"No unique installed Bannerlord XSD matched; using conservative literal typing.")),
    el("div",{class:"bl-list-block"},textInput(state.moduleDataFilter,value=>{state.moduleDataFilter=value;render()},{placeholder:"Filter records"})),
    el("div",{class:"bl-list"},...records.map(row=>el("button",{type:"button",class:`bl-item${row.path===state.moduleDataRecordPath?" active":""}`,onclick:()=>selectModuleDataRecord(row.path)},moduleDataRecordLabel(row),el("small",{},`${row.schemaIssueCount?`⚠ ${row.schemaIssueCount} issue(s) · `:""}${row.id||"no id"} · line ${row.line}`))))
  );

  let detail;
  if(!record)detail=el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"This XML has no top-level object records."));
  else{
    const nodeChoices=nodes.map(element=>[element.path,`${element.schemaIssues?.length?"⚠ ":""}${"· ".repeat(Math.max(0,element.depth-1))}${element.tag}${element.hint?` · ${element.hint}`:""}`]);
    const attributeRows=node?(node.attributes||[]).flatMap(attribute=>fieldRow(moduleDataAttributeLabel(attribute),moduleDataControl(attribute))):[];
    const boundNotes=node?(node.attributes||[]).flatMap(attribute=>{const constraints=[];if(attribute.min!==undefined)constraints.push(`min ${attribute.min}`);if(attribute.max!==undefined)constraints.push(`max ${attribute.max}`);if(attribute.fixed!==undefined)constraints.push(`fixed ${attribute.fixed}`);if(attribute.default!==undefined)constraints.push(`default ${attribute.default}`);if(attribute.schemaIssue)constraints.push(`⚠ ${attribute.schemaIssue}`);return constraints.length?[el("div",{class:"bl-note"},`${attribute.name}: ${constraints.join(" · ")}`)]:[]}):[];
    const missing=node?.missingRequired||[];
    const issuePanel=node?.schemaIssues?.length?el("div",{class:"bl-list-block"},el("h3",{},"XSD issues"),el("ul",{},...node.schemaIssues.map(value=>el("li",{},value)))):null;
    const missingPanel=missing.length?el("div",{class:"bl-list-block"},el("h3",{},"Missing required attributes"),el("div",{class:"bl-grid"},...missing.flatMap(value=>fieldRow(`${value.name}${value.schemaType?` · ${value.schemaType}`:""}`,missingRequiredControl(value)))),el("div",{class:"bl-note"},"Check an attribute to repair it on Save. Lexeditor only inserts attributes the active XSD marks as required; all other structural XML changes remain source-only.")):null;
    const lifecycle=el("div",{class:"bl-actions"},
      record.id?textInput(state.moduleDataNewId,value=>{state.moduleDataNewId=value},{placeholder:"New duplicate ID",spellcheck:"false"}):null,
      el("button",{type:"button",onclick:()=>runModuleDataRecordAction("duplicate",record)},"Duplicate record"),
      el("button",{type:"button",class:"danger",onclick:()=>runModuleDataRecordAction("delete",record)},"Delete record"));
    detail=el("div",{class:"bl-detail"},el("section",{class:"bl-panel"},
      el("h2",{},moduleDataRecordLabel(record)),lifecycle,
      el("div",{class:"bl-grid"},...fieldRow("Record path",el("code",{},record.path)),...fieldRow("Record ID",record.id||"—"),...fieldRow("Record name",record.name||"—"),...fieldRow("Record XSD issues",String(record.schemaIssueCount||0)),...fieldRow("Nested node",select(state.moduleDataElementPath,nodeChoices,value=>{state.moduleDataElementPath=value;render()})),...(node?[...fieldRow("XML tag",node.tag),...fieldRow("Source line",String(node.line)),...attributeRows]:[])),
      issuePanel,missingPanel,...boundNotes,
      el("div",{class:"bl-note"},schema?"Bannerlord XSD metadata is active: enums become selects, booleans checkboxes, numeric bounds are enforced, integer types reject fractions, fixed values are read-only, malformed existing values are flagged, and missing required attributes can be repaired surgically.":"Without a unique installed XSD match, Lexeditor only infers literal booleans and numbers; references, localization strings, IDs, enums, and other values remain text."),
      el("div",{class:"bl-note"},"Duplicate/Delete are explicit immediate operations with backups and are disabled logically while this document has unsaved attribute edits. Duplicating preserves the complete nested record body and changes only its top-level id when one exists."),
      el("div",{class:"bl-note"},"Unknown child elements and attributes are deliberately preserved, and attribute saves patch only changed/added spans instead of reserializing the document.")));
  }
  main.replaceChildren(el("div",{class:"bl-split"},master,detail));
}

function moduleDataEdits(){
  if(!moduleDataDirty())return [];
  const beforeElements=Object.fromEntries((state.savedModuleData.elements||[]).map(element=>[element.path,element]));const edits=[];
  for(const element of state.moduleData.elements||[]){const old=beforeElements[element.path];if(!old)continue;const oldAttributes=Object.fromEntries((old.attributes||[]).map(attribute=>[attribute.name,attribute]));for(const attribute of element.attributes||[]){const previous=oldAttributes[attribute.name];if(previous&&String(previous.value)!==String(attribute.value))edits.push({elementPath:element.path,tag:element.tag,attribute:attribute.name,originalValue:String(previous.value),value:attribute.value})}for(const missing of element.missingRequired||[])if(missing.add)edits.push({addRequired:true,elementPath:element.path,tag:element.tag,attribute:missing.name,value:missing.value})}
  return edits;
}
async function saveModuleData(){const edits=moduleDataEdits();if(!edits.length)return;const result=prepareModuleData(await post("/api/module-data/save",{path:state.moduleData.relativePath,edits,sourceHash:state.savedModuleData.sourceHash||""}));state.moduleData=result;state.savedModuleData=clone(result);if(!(result.records||[]).some(record=>record.path===state.moduleDataRecordPath))applyModuleDataRecordSelection(result.records?.[0])}

renderDataMap=function(){const view=LexeditorUI.dataMap({rows:state.datamap.rows,query:state.query,status:state.mapStatus,page:state.page,sort:state.sort,tableClass:"bannerlord-data-map",open:row=>{if(row.target==="moduledata")loadModuleData(row.editorPath||row.filename);else if(row.target==="gauntlet")loadGauntlet(row.editorPath||row.filename);else if(row.target==="runtime")navigate("runtime");else if(row.target==="module")navigate("module");else if(row.target==="build")navigate("build");else if(row.target==="skills")navigate("skills");else if(row.target==="effects")navigate("effects");else if(row.target==="perks")navigate("perks");else if(row.target==="xp")navigate("xp");else if(row.target==="settings")navigate("settings")},openSource,changeQuery:value=>{state.query=value;state.page=0;renderDataMap()},changeStatus:value=>{state.mapStatus=value;state.page=0;renderDataMap()},changePage:value=>{state.page=value;renderDataMap()},changeSort:key=>{const [active,direction]=state.sort;state.sort=[key,active===key?-direction:1];renderDataMap()}});main.replaceChildren(view.content)};
render=function(){const views={module:renderModule,dependencies:renderDependencies,submodules:renderSubmodules,xmls:renderXmls,skills:renderSkills,effects:renderEffects,perks:renderPerks,xp:renderXpSources,settings:renderMcmDefaults,runtime:renderRuntimeOverrides,gauntlet:renderGauntlet,moduledata:renderModuleData,build:renderBuild,deployment:renderDeployment,datamap:renderDataMap,source:renderSource};(views[state.tab]||renderModule)();refresh()};