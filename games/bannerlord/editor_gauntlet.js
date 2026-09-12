"use strict";
state.gauntletFiles=null;
state.gauntlet=null;
state.savedGauntlet=null;
state.gauntletElementPath="";
state.gauntletFilter="";

const gauntletEditable=value=>value?{
  relativePath:value.relativePath,
  elements:(value.elements||[]).map(element=>({
    path:element.path,tag:element.tag,
    attributes:(element.attributes||[]).map(attribute=>({name:attribute.name,value:String(attribute.value)}))
  }))
}:null;
const gauntletDirty=()=>state.gauntlet&&state.savedGauntlet&&!same(gauntletEditable(state.gauntlet),gauntletEditable(state.savedGauntlet));
const dirtyCountWithoutGauntlet=dirtyCount;
dirtyCount=function(){return dirtyCountWithoutGauntlet()+Number(gauntletDirty())};

async function ensureGauntletFiles(){
  if(state.gauntletFiles!==null)return state.gauntletFiles;
  try{
    const result=await api("/api/gauntlet-files");
    state.gauntletFiles=result.files||[];
    if(!state.gauntlet&&state.gauntletFiles.length)await loadGauntlet(state.gauntletFiles[0],false);
  }catch(error){
    state.gauntletFiles=[];
    showAlert?.(String(error.message||error),"Gauntlet prefab scan failed");
  }
  return state.gauntletFiles;
}

async function reloadGauntlet(){
  if(!state.gauntlet)return;
  await loadGauntlet(state.gauntlet.relativePath,true);
}

async function loadGauntlet(path,ask=true){
  if(!path)return;
  if(ask&&gauntletDirty()){
    const confirmed=await confirmAction({
      title:"Discard unsaved Gauntlet changes?",
      message:"Discard unsaved Gauntlet prefab changes?",confirmLabel:"Discard"
    });
    if(!confirmed)return;
  }
  try{
    const value=await api(`/api/gauntlet?path=${encodeURIComponent(path)}`);
    state.gauntlet=value;state.savedGauntlet=clone(value);
    state.gauntletElementPath=value.elements?.[0]?.path||"";
    state.gauntletFilter="";
    state.tab="gauntlet";render();
  }catch(error){showAlert?.(String(error.message||error),"Could not open Gauntlet prefab")}
}

function gauntletControl(attribute){
  const assign=value=>{attribute.value=String(value);refresh()};
  if(attribute.kind==="bool")return checkbox(String(attribute.value).toLowerCase()==="true",value=>assign(value?"true":"false"));
  if(attribute.kind==="number")return numberInput(Number(attribute.value),value=>assign(value),{step:"any"});
  if(attribute.kind==="enum")return select(attribute.value,(attribute.choices||[]).map(value=>[value,value]),assign);
  return textInput(attribute.value,assign,{spellcheck:"false"});
}

function gauntletElementLabel(element){
  const hint=String(element.hint||"");
  return hint?`${element.tag} · ${hint}`:element.tag;
}

function renderGauntlet(){
  if(state.gauntletFiles===null){
    main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Gauntlet Prefabs"),el("div",{class:"bl-empty"},"Scanning GUI/Prefabs…")));
    ensureGauntletFiles().then(()=>render());return;
  }
  if(!state.gauntletFiles.length){
    main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Gauntlet Prefabs"),el("div",{class:"bl-empty"},"No XML prefabs found under GUI/Prefabs.")));return;
  }
  if(!state.gauntlet){
    loadGauntlet(state.gauntletFiles[0],false);return;
  }

  const filter=state.gauntletFilter.trim().toLowerCase();
  const rows=(state.gauntlet.elements||[]).filter(element=>{
    if(!filter)return true;
    const attributes=(element.attributes||[]).map(row=>`${row.name} ${row.value}`).join(" ");
    return `${element.tag} ${element.path} ${element.hint||""} ${attributes}`.toLowerCase().includes(filter);
  });
  let record=(state.gauntlet.elements||[]).find(element=>element.path===state.gauntletElementPath);
  if(!record&&rows.length){record=rows[0];state.gauntletElementPath=record.path}

  const fileSelect=select(state.gauntlet.relativePath,state.gauntletFiles.map(path=>[path,path]),value=>loadGauntlet(value));
  const master=el("div",{class:"bl-master"},
    el("div",{class:"bl-master-head"},el("strong",{},`Widgets (${state.gauntlet.elementCount||0})`),
      el("button",{type:"button",onclick:()=>reloadGauntlet()},"Reload")),
    el("div",{class:"bl-list-block"},fileSelect),
    el("div",{class:"bl-list-block"},textInput(state.gauntletFilter,value=>{state.gauntletFilter=value;render()},{placeholder:"Filter widgets / attributes"})),
    el("div",{class:"bl-list"},...rows.map(element=>el("button",{
      type:"button",class:`bl-item${element.path===state.gauntletElementPath?" active":""}`,
      style:`padding-left:${11+Math.min(element.depth,12)*14}px`,
      onclick:()=>{state.gauntletElementPath=element.path;render()}
    },gauntletElementLabel(element),el("small",{},`line ${element.line} · ${element.attributes?.length||0} attribute(s)`))))
  );

  let detail;
  if(!record)detail=el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"No matching widget."));
  else{
    const attributeRows=(record.attributes||[]).flatMap(attribute=>fieldRow(attribute.name,gauntletControl(attribute)));
    detail=el("div",{class:"bl-detail"},el("section",{class:"bl-panel"},
      el("h2",{},gauntletElementLabel(record)),
      el("div",{class:"bl-grid"},
        ...fieldRow("Element path",el("code",{},record.path)),
        ...fieldRow("XML tag",record.tag),
        ...fieldRow("Source line",String(record.line)),
        ...attributeRows
      ),
      el("div",{class:"bl-note"},"Bindings such as @IsEnabled remain text values; literal booleans, numeric values, and known Gauntlet enums get typed controls. Lexeditor edits existing attributes only in this slice."),
      el("div",{class:"bl-note"},"Writes are surgical: the backend patches only changed attribute-value spans, validates the resulting XML, creates a .lexeditor.bak backup, and preserves surrounding comments/formatting.")
    ));
  }
  main.replaceChildren(el("div",{class:"bl-split"},master,detail));
}

function gauntletEdits(){
  if(!gauntletDirty())return [];
  const beforeElements=Object.fromEntries((state.savedGauntlet.elements||[]).map(element=>[element.path,element]));
  const edits=[];
  for(const element of state.gauntlet.elements||[]){
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

async function saveGauntlet(){
  const edits=gauntletEdits();
  if(!edits.length)return;
  const result=await post("/api/gauntlet/save",{
    path:state.gauntlet.relativePath,edits,sourceHash:state.savedGauntlet.sourceHash||""
  });
  state.gauntlet=result;state.savedGauntlet=clone(result);
  if(!(result.elements||[]).some(element=>element.path===state.gauntletElementPath))
    state.gauntletElementPath=result.elements?.[0]?.path||"";
}

renderDataMap=function(){
  const view=LexeditorUI.dataMap({
    rows:state.datamap.rows,query:state.query,status:state.mapStatus,page:state.page,sort:state.sort,
    tableClass:"bannerlord-data-map",
    open:row=>{
      if(row.target==="gauntlet")loadGauntlet(row.editorPath||row.filename);
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
  main.replaceChildren(view.content);
};

render=function(){
  const views={module:renderModule,dependencies:renderDependencies,submodules:renderSubmodules,xmls:renderXmls,
    skills:renderSkills,effects:renderEffects,perks:renderPerks,xp:renderXpSources,settings:renderMcmDefaults,
    runtime:renderRuntimeOverrides,gauntlet:renderGauntlet,build:renderBuild,deployment:renderDeployment,
    datamap:renderDataMap,source:renderSource};
  (views[state.tab]||renderModule)();refresh();
};
