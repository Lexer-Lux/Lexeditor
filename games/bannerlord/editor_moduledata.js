"use strict";
state.moduleDataFiles=null;
state.moduleData=null;
state.savedModuleData=null;
state.moduleDataRecordPath="";
state.moduleDataElementPath="";
state.moduleDataFilter="";

const moduleDataEditable=value=>value?{
  relativePath:value.relativePath,
  elements:(value.elements||[]).map(element=>({
    path:element.path,tag:element.tag,
    attributes:(element.attributes||[]).map(attribute=>({name:attribute.name,value:String(attribute.value)}))
  }))
}:null;
const moduleDataDirty=()=>state.moduleData&&state.savedModuleData&&!same(moduleDataEditable(state.moduleData),moduleDataEditable(state.savedModuleData));
const dirtyCountWithoutModuleData=dirtyCount;
dirtyCount=function(){return dirtyCountWithoutModuleData()+Number(moduleDataDirty())};

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

async function loadModuleData(path,ask=true){
  if(!path)return;
  if(ask&&moduleDataDirty()&&!window.confirm("Discard unsaved ModuleData changes?"))return;
  try{
    const value=await api(`/api/module-data?path=${encodeURIComponent(path)}`);
    state.moduleData=value;state.savedModuleData=clone(value);
    const first=value.records?.[0];
    state.moduleDataRecordPath=first?.path||"";
    state.moduleDataElementPath=first?.path||"";
    state.moduleDataFilter="";
    state.tab="moduledata";render();
  }catch(error){showAlert?.(String(error.message||error),"Could not open ModuleData XML")}
}

function moduleDataControl(attribute){
  if(attribute.fixed!==undefined)return el("code",{title:"Fixed by Bannerlord XSD"},String(attribute.value));
  const assign=value=>{attribute.value=String(value);refresh()};
  if(attribute.kind==="bool")return checkbox(String(attribute.value).toLowerCase()==="true",value=>assign(value?"true":"false"));
  if(attribute.kind==="enum")return select(attribute.value,(attribute.choices||[]).map(value=>[value,value]),assign);
  if(attribute.kind==="number"){
    const attrs={step:attribute.integer?1:"any"};
    if(attribute.min!==undefined)attrs.min=attribute.min;
    if(attribute.max!==undefined)attrs.max=attribute.max;
    return numberInput(Number(attribute.value),assign,attrs);
  }
  return textInput(attribute.value,assign,{spellcheck:"false"});
}

function moduleDataAttributeLabel(attribute){
  const suffix=[];
  if(attribute.required)suffix.push("required");
  if(attribute.schemaType)suffix.push(attribute.schemaType);
  if(attribute.schemaIssue)suffix.push("⚠ invalid");
  return suffix.length?`${attribute.name} · ${suffix.join(" · ")}`:attribute.name;
}

function moduleDataRecordLabel(record){
  const identity=record.name||record.id||"";
  return identity?`${record.tag} · ${identity}`:record.tag;
}

function selectModuleDataRecord(path){
  state.moduleDataRecordPath=path;
  state.moduleDataElementPath=path;
  render();
}

function renderModuleData(){
  if(state.moduleDataFiles===null){
    main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"ModuleData XML"),el("div",{class:"bl-empty"},"Scanning ModuleData…")));
    ensureModuleDataFiles().then(()=>render());return;
  }
  if(!state.moduleDataFiles.length){
    main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"ModuleData XML"),el("div",{class:"bl-empty"},"No XML files found under ModuleData.")));return;
  }
  if(!state.moduleData){loadModuleData(state.moduleDataFiles[0],false);return}

  const filter=state.moduleDataFilter.trim().toLowerCase();
  const records=(state.moduleData.records||[]).filter(record=>{
    if(!filter)return true;
    return `${record.tag} ${record.id||""} ${record.name||""} ${record.path}`.toLowerCase().includes(filter);
  });
  let record=(state.moduleData.records||[]).find(row=>row.path===state.moduleDataRecordPath);
  if(!record&&records.length){record=records[0];state.moduleDataRecordPath=record.path}
  const nodes=record?(state.moduleData.elements||[]).filter(element=>element.path===record.path||element.path.startsWith(record.path+"/")):[];
  let node=nodes.find(element=>element.path===state.moduleDataElementPath);
  if(!node&&nodes.length){node=nodes[0];state.moduleDataElementPath=node.path}

  const fileSelect=select(state.moduleData.relativePath,state.moduleDataFiles.map(path=>[path,path]),value=>loadModuleData(value));
  const schema=state.moduleData.schema;
  const issueCount=state.moduleData.schemaIssueCount||0;
  const master=el("div",{class:"bl-master"},
    el("div",{class:"bl-master-head"},el("strong",{},`${state.moduleData.rootTag} (${state.moduleData.recordCount||0})`)),
    el("div",{class:"bl-list-block"},fileSelect),
    el("div",{class:"bl-list-block"},
      schema?el("div",{},
        el("strong",{},`XSD: ${schema.id||"matched schema"}`),
        el("small",{},` · ${schema.path||""}`),
        el("div",{class:"bl-note"},issueCount?`⚠ ${issueCount} schema issue(s) detected in this document.`:"No XSD attribute issues detected.")):
        el("div",{class:"bl-note"},"No unique installed Bannerlord XSD matched; using conservative literal typing.")),
    el("div",{class:"bl-list-block"},textInput(state.moduleDataFilter,value=>{state.moduleDataFilter=value;render()},{placeholder:"Filter records"})),
    el("div",{class:"bl-list"},...records.map(row=>el("button",{
      type:"button",class:`bl-item${row.path===state.moduleDataRecordPath?" active":""}`,
      onclick:()=>selectModuleDataRecord(row.path)
    },moduleDataRecordLabel(row),el("small",{},`${row.schemaIssueCount?`⚠ ${row.schemaIssueCount} issue(s) · `:""}${row.id||"no id"} · line ${row.line}`))))
  );

  let detail;
  if(!record)detail=el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"This XML has no top-level object records."));
  else{
    const nodeChoices=nodes.map(element=>[
      element.path,
      `${element.schemaIssues?.length?"⚠ ":""}${"· ".repeat(Math.max(0,element.depth-1))}${element.tag}${element.hint?` · ${element.hint}`:""}`
    ]);
    const attributeRows=node?(node.attributes||[]).flatMap(attribute=>fieldRow(moduleDataAttributeLabel(attribute),moduleDataControl(attribute))):[];
    const boundNotes=node?(node.attributes||[]).flatMap(attribute=>{
      const constraints=[];
      if(attribute.min!==undefined)constraints.push(`min ${attribute.min}`);
      if(attribute.max!==undefined)constraints.push(`max ${attribute.max}`);
      if(attribute.fixed!==undefined)constraints.push(`fixed ${attribute.fixed}`);
      if(attribute.default!==undefined)constraints.push(`default ${attribute.default}`);
      if(attribute.schemaIssue)constraints.push(`⚠ ${attribute.schemaIssue}`);
      return constraints.length?[el("div",{class:"bl-note"},`${attribute.name}: ${constraints.join(" · ")}`)]:[];
    }):[];
    const missing=node?.missingRequired||[];
    const issuePanel=node?.schemaIssues?.length?el("div",{class:"bl-list-block"},
      el("h3",{},"XSD issues"),el("ul",{},...node.schemaIssues.map(value=>el("li",{},value)))):null;
    const missingPanel=missing.length?el("div",{class:"bl-list-block"},
      el("h3",{},"Missing required attributes"),
      el("ul",{},...missing.map(value=>el("li",{},`${value.name}${value.schemaType?` (${value.schemaType})`:""}`))),
      el("div",{class:"bl-note"},"Missing required attributes are diagnosed but not auto-created in this slice; use Source for structural XML changes.")):null;
    detail=el("div",{class:"bl-detail"},el("section",{class:"bl-panel"},
      el("h2",{},moduleDataRecordLabel(record)),
      el("div",{class:"bl-grid"},
        ...fieldRow("Record path",el("code",{},record.path)),
        ...fieldRow("Record ID",record.id||"—"),
        ...fieldRow("Record name",record.name||"—"),
        ...fieldRow("Record XSD issues",String(record.schemaIssueCount||0)),
        ...fieldRow("Nested node",select(state.moduleDataElementPath,nodeChoices,value=>{state.moduleDataElementPath=value;render()})),
        ...(node?[
          ...fieldRow("XML tag",node.tag),
          ...fieldRow("Source line",String(node.line)),
          ...attributeRows
        ]:[])
      ),
      issuePanel,missingPanel,...boundNotes,
      el("div",{class:"bl-note"},schema?
        "Bannerlord XSD metadata is active: enums become selects, booleans checkboxes, numeric bounds are enforced, integer types reject fractions, fixed values are read-only, and malformed existing values/missing required attributes are flagged.":
        "Without a unique installed XSD match, Lexeditor only infers literal booleans and numbers; references, localization strings, IDs, enums, and other values remain text."),
      el("div",{class:"bl-note"},"This slice edits existing attributes only. Unknown child elements and attributes are deliberately preserved, and saves patch only changed value spans instead of reserializing the document.")
    ));
  }
  main.replaceChildren(el("div",{class:"bl-split"},master,detail));
}

function moduleDataEdits(){
  if(!moduleDataDirty())return [];
  const beforeElements=Object.fromEntries((state.savedModuleData.elements||[]).map(element=>[element.path,element]));
  const edits=[];
  for(const element of state.moduleData.elements||[]){
    const old=beforeElements[element.path];if(!old)continue;
    const oldAttributes=Object.fromEntries((old.attributes||[]).map(attribute=>[attribute.name,attribute]));
    for(const attribute of element.attributes||[]){
      const previous=oldAttributes[attribute.name];
      if(previous&&String(previous.value)!==String(attribute.value)){
        edits.push({
          elementPath:element.path,tag:element.tag,attribute:attribute.name,
          originalValue:String(previous.value),value:attribute.value
        });
      }
    }
  }
  return edits;
}

async function saveModuleData(){
  const edits=moduleDataEdits();
  if(!edits.length)return;
  const result=await post("/api/module-data/save",{path:state.moduleData.relativePath,edits});
  state.moduleData=result;state.savedModuleData=clone(result);
  if(!(result.records||[]).some(record=>record.path===state.moduleDataRecordPath)){
    state.moduleDataRecordPath=result.records?.[0]?.path||"";
    state.moduleDataElementPath=state.moduleDataRecordPath;
  }
}

renderDataMap=function(){
  const view=LexeditorUI.dataMap({
    rows:state.datamap.rows,query:state.query,status:state.mapStatus,page:state.page,sort:state.sort,
    tableClass:"bannerlord-data-map",
    open:row=>{
      if(row.target==="moduledata")loadModuleData(row.editorPath||row.filename);
      else if(row.target==="gauntlet")loadGauntlet(row.editorPath||row.filename);
      else if(row.target==="runtime")navigate("runtime");
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
  main.replaceChildren(view);
};

render=function(){
  const views={module:renderModule,dependencies:renderDependencies,submodules:renderSubmodules,xmls:renderXmls,
    skills:renderSkills,effects:renderEffects,perks:renderPerks,xp:renderXpSources,settings:renderMcmDefaults,
    runtime:renderRuntimeOverrides,gauntlet:renderGauntlet,moduledata:renderModuleData,
    build:renderBuild,deployment:renderDeployment,datamap:renderDataMap,source:renderSource};
  (views[state.tab]||renderModule)();refresh();
};
