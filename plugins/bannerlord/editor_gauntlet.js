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

// New prefabs and elements are copies of existing ones, like every other
// record Bannerlord creates: pick what to copy, then name the new prefab.
function beginGauntletPrefabCreation(){
  const files=state.gauntletFiles||[];
  if(!files.length||gauntletDirty())return;
  let template=state.gauntlet?.relativePath&&files.includes(state.gauntlet.relativePath)?state.gauntlet.relativePath:files[0];
  const name=textInput(template.split(/[\\/]/).pop().replace(/\.xml$/i,"")+"Copy",()=>{},
    {required:true,"aria-label":"New prefab name",spellcheck:"false",pattern:"[A-Za-z0-9_][A-Za-z0-9_. \\-]{0,78}"});
  const source=select(template,files.map(path=>[path,path]),value=>{template=value});
  source.setAttribute("aria-label","Copy from prefab");
  main.replaceChildren(BLUI.detailPanel({title:"Add Gauntlet prefab",body:[
    BLUI.detailField({label:"Copy from",control:source,help:BLUI.infoHelp("The new prefab starts as an exact copy of this one, in the same folder.")}),
    BLUI.detailField({label:"Name",control:name}),
    LexeditorUI.actionRow(uiButton("Cancel",()=>{state.gauntletView="files";render()}),uiButton("Create prefab",async()=>{
      if(!name.reportValidity())return;
      try{
        const created=await post("/api/gauntlet/create",{source:template,name:name.value});
        state.gauntletFiles=null;await ensureGauntletFiles();
        state.gauntletView="widgets";await loadGauntlet(created.relativePath,false);
      }catch(error){showAlert?.(String(error.message||error),"Could not create the prefab")}
    })),
  ]}));
}

function beginGauntletElementCreation(){
  const elements=(state.gauntlet?.elements||[]).filter(element=>element.depth>0);
  if(!elements.length||gauntletDirty())return;
  let template=elements.find(element=>element.path===state.gauntletElementPath)?.path||elements[0].path;
  const source=select(template,elements.map(element=>[element.path,`${gauntletElementLabel(element)} (${element.path})`]),value=>{template=value});
  source.setAttribute("aria-label","Copy from element");
  main.replaceChildren(BLUI.detailPanel({title:"Add Gauntlet element",body:[
    BLUI.detailField({label:"Copy from",control:source,help:BLUI.infoHelp("Copies this element and everything inside it to just after it. The rest of the prefab keeps its exact formatting.")}),
    LexeditorUI.actionRow(uiButton("Cancel",()=>render()),uiButton("Create element",async()=>{
      try{
        const result=await post("/api/gauntlet/duplicate",{path:state.gauntlet.relativePath,elementPath:template,sourceHash:state.savedGauntlet?.sourceHash||""});
        state.gauntlet=result;state.savedGauntlet=clone(result);
        state.gauntletElementPath=result.created||template;render();
      }catch(error){showAlert?.(String(error.message||error),"Could not add the element")}
    })),
  ]}));
}

function renderGauntlet(){
  if(state.gauntletFiles===null){
    main.replaceChildren(uiLoading("Gauntlet","Scanning GUI/Prefabs…"));
    ensureGauntletFiles().then(()=>render());return;
  }
  if(!state.gauntletFiles.length){
    main.replaceChildren(uiEmpty("Gauntlet","No XML prefabs were found under GUI/Prefabs."));return;
  }
  if(state.gauntletView==="files"||!state.gauntlet){
    const files=state.gauntletFiles.map((path,index)=>({index,path,name:path.split(/[\\/]/).pop(),searchText:path}));
    const columns=[{key:"name",label:"Prefab"},{key:"path",label:"Resource path"}];
    const detail=item=>BLUI.detailPanel({
      title:item.name,meta:item.path,
      actions:[uiButton("Open widgets",()=>{state.gauntletView="widgets";loadGauntlet(item.path,false)})],
      body:[BLUI.detailSection({title:"PREFAB",body:[
        readField("Resource path",item.path,"Module-relative Gauntlet prefab path."),
        readField("Editor","Existing widget attributes","Opening the prefab shows its XML elements as a searchable, paginated Table + Detail editor.")
      ]})]
    });
    main.replaceChildren(tableView({
      key:"gauntlet-files",rows:files,keyOf:item=>item.path,columns,detail,noun:"Gauntlet prefab files",
      add:beginGauntletPrefabCreation,
      placeholder:"Search prefab files…",selected:uiState("gauntlet-files").selected,setSelected:()=>{}
    }));return;
  }

  const items=(state.gauntlet.elements||[]).map(element=>({
    element,key:element.path,tag:element.tag,hint:element.hint||"",line:Number(element.line),attributes:(element.attributes||[]).length,
    searchText:`${element.tag} ${element.path} ${element.hint||""} ${(element.attributes||[]).map(attribute=>`${attribute.name} ${attribute.value}`).join(" ")}`
  }));
  const columns=[
    {key:"tag",label:"XML tag"},{key:"hint",label:"Binding / hint"},
    {key:"line",label:"Line",numeric:true},{key:"attributes",label:"Attributes",numeric:true}
  ];
  const detail=item=>BLUI.detailPanel({
    title:gauntletElementLabel(item.element),meta:state.gauntlet.relativePath,
    body:[
      BLUI.detailSection({title:"ELEMENT",body:[
        readField("Resource path",state.gauntlet.relativePath),
        readField("Element path",item.element.path),
        readField("XML tag",item.element.tag),
        readField("Source line",item.element.line)
      ]}),
      BLUI.detailSection({title:"ATTRIBUTES",body:(item.element.attributes||[]).map(attribute=>
        BLUI.detailField({
          label:attribute.name,control:gauntletControl(attribute),
          help:BLUI.infoHelp(attribute.kind==="enum"?
            "Known Gauntlet enum. Lexeditor edits the existing literal and preserves the surrounding prefab XML.":
            attribute.kind==="bool"?
              "Literal Bannerlord UI boolean. Bindings such as @IsEnabled remain text and are not coerced.":
              attribute.kind==="number"?
                "Literal numeric Gauntlet attribute. Lexeditor does not invent bounds that the prefab does not provide.":
                "Existing Gauntlet attribute. Lexeditor patches only this value span and preserves comments and formatting.")
        })
      )})
    ]
  });
  const filters=[
    uiButton("Prefab files",()=>{
      if(gauntletDirty())showAlert?.("Save or reload the current prefab before switching files.","Unsaved Gauntlet changes");
      else{state.gauntletView="files";render()}
    }),
    uiButton("Reload",()=>reloadGauntlet())
  ];
  main.replaceChildren(tableView({
    key:`gauntlet-${state.gauntlet.relativePath}`,rows:items,keyOf:item=>item.key,columns,detail,noun:"Gauntlet elements",
    add:beginGauntletElementCreation,addDisabled:gauntletDirty(),
    addDisabledReason:"Save or reload this prefab's pending edits before adding an element.",
    placeholder:"Search widgets and attributes…",selected:state.gauntletElementPath,
    setSelected:value=>state.gauntletElementPath=String(value),filters
  }));
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
