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
  return el("div",{class:"lex-action-row"},toggle,missingRequiredValueControl(attribute));
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
  if(state.moduleDataFiles===null){
    main.replaceChildren(uiLoading("ModuleData","Scanning ModuleData…"));
    ensureModuleDataFiles().then(()=>render());return;
  }
  if(!state.moduleDataFiles.length){
    main.replaceChildren(uiEmpty("ModuleData","No XML files were found under ModuleData."));return;
  }
  if(state.moduleDataView==="files"||!state.moduleData){
    const files=state.moduleDataFiles.map((path,index)=>({index,path,name:path.split(/[\\/]/).pop(),searchText:path}));
    const columns=[{key:"name",label:"XML file"},{key:"path",label:"Resource path"}];
    const detail=item=>BLUI.detailPanel({
      title:item.name,meta:item.path,
      actions:[uiButton("Open records",()=>{state.moduleDataView="records";loadModuleData(item.path,false)})],
      body:[BLUI.detailSection({title:"MODULE DATA",body:[
        readField("Resource path",item.path),
        readField("Editor","Top-level records and nested attributes","Opening the XML shows top-level object records in the shared Table + Detail editor. Installed Modding Kit XSDs enrich controls only when a unique schema matches.")
      ]})]
    });
    main.replaceChildren(tableView({
      key:"moduledata-files",rows:files,keyOf:item=>item.path,columns,detail,noun:"ModuleData XML files",
      placeholder:"Search ModuleData files…",selected:uiState("moduledata-files").selected,setSelected:()=>{},
      filters:[uiButton("Validate all",()=>validateAllModuleData(),{disabled:!!state.moduleDataValidating})]
    }));return;
  }

  const records=(state.moduleData.records||[]).map(record=>({
    record,key:record.path,tag:record.tag,id:record.id||"",name:record.name||"",
    issues:Number(record.schemaIssueCount||0),line:Number(record.line),
    searchText:`${record.tag} ${record.id||""} ${record.name||""} ${record.path}`
  }));
  const columns=[
    {key:"name",label:"Name"},{key:"id",label:"Internal name"},
    {key:"tag",label:"XML tag"},{key:"issues",label:"XSD issues",numeric:true}
  ];
  const detail=item=>{
    const record=item.record;
    const nodes=(state.moduleData.elements||[]).filter(element=>element.path===record.path||element.path.startsWith(record.path+"/"));
    let node=nodes.find(element=>element.path===state.moduleDataElementPath);
    if(!node&&nodes.length){node=nodes[0];state.moduleDataElementPath=node.path}
    const nodeChoices=nodes.map(element=>[element.path,`${element.schemaIssues?.length?"⚠ ":""}${"· ".repeat(Math.max(0,element.depth-1))}${element.tag}${element.hint?` · ${element.hint}`:""}`]);
    const actions=[
      record.id?textInput(state.moduleDataNewId,value=>{state.moduleDataNewId=value},{placeholder:"New duplicate ID",spellcheck:"false","aria-label":"New duplicate record ID"}):null,
      uiButton("Duplicate",()=>runModuleDataRecordAction("duplicate",record)),
      uiButton("Delete",()=>runModuleDataRecordAction("delete",record),{danger:true})
    ].filter(Boolean);
    const attributeFields=node?(node.attributes||[]).map(attribute=>BLUI.detailField({
      label:moduleDataAttributeLabel(attribute),control:moduleDataControl(attribute),
      min:attribute.min,max:attribute.max,
      dataType:attribute.kind==="bool"?"BOOL":attribute.kind==="enum"?"ENUM":attribute.integer?"INT":attribute.kind==="number"?"FLOAT":undefined,
      help:BLUI.infoHelp(attribute.schemaIssue?attribute.schemaIssue:
        attribute.fixed!==undefined?"The matched Bannerlord XSD fixes this value, so Lexeditor leaves it read-only.":
        attribute.kind==="enum"?"The matched Bannerlord XSD supplies this finite choice list.":
        attribute.kind==="number"?"Numeric type and any shown bounds come from the matched Bannerlord XSD.":
        "Existing XML attribute. Without an unambiguous schema Lexeditor does not invent reference, enum, or range semantics.")
    })):[];
    const missing=node?.missingRequired||[];
    const validation=typeof moduleDataValidationSection==="function"?moduleDataValidationSection():null;
    return BLUI.detailPanel({
      title:record.name||record.id||record.tag,meta:state.moduleData.relativePath,actions,
      body:[
        BLUI.detailSection({title:"RECORD",body:[
          readField("Resource path",state.moduleData.relativePath),
          readField("Record path",record.path),
          readField("Internal name",record.id||"none"),
          readField("Name",record.name||"none"),
          readField("XSD issues",record.schemaIssueCount||0),
          nodes.length?selectField("Nested node",state.moduleDataElementPath,nodeChoices,value=>{state.moduleDataElementPath=value;render()},"Choose which nested XML element's attributes are shown."):readField("Nested node","none")
        ]}),
        node?BLUI.detailSection({title:"ATTRIBUTES",body:[
          readField("XML tag",node.tag),readField("Source line",node.line),...attributeFields
        ]}):null,
        missing.length?BLUI.detailSection({
          title:"MISSING REQUIRED ATTRIBUTES",
          help:BLUI.infoHelp("These fields are offered only because the matched Bannerlord XSD marks them required. Check one to add it on Save."),
          body:missing.map(attribute=>BLUI.detailField({
            label:attribute.name,control:missingRequiredControl(attribute),
            help:attribute.schemaType?BLUI.infoHelp(`Required ${attribute.schemaType} attribute from the matched XSD.`):null
          }))
        }):null,
        node?.schemaIssues?.length?BLUI.detailSection({title:"XSD ISSUES",body:node.schemaIssues.map((issue,index)=>readField(`Issue ${index+1}`,issue))}):null,
        validation
      ].filter(Boolean)
    });
  };
  const filters=[
    uiButton("XML files",()=>{
      if(moduleDataDirty())showAlert?.("Save or reload the current ModuleData changes before switching files.","Unsaved ModuleData changes");
      else{state.moduleDataView="files";render()}
    }),
    uiButton("Reload",()=>reloadModuleData()),
    uiButton(state.moduleDataValidating?"Validating…":"Validate all",()=>validateAllModuleData(),{disabled:!!state.moduleDataValidating})
  ];
  main.replaceChildren(tableView({
    key:`moduledata-${state.moduleData.relativePath}`,rows:records,keyOf:item=>item.key,columns,detail,noun:"ModuleData records",
    placeholder:"Search ModuleData records…",selected:state.moduleDataRecordPath,
    setSelected:value=>{const record=(state.moduleData.records||[]).find(row=>row.path===String(value));applyModuleDataRecordSelection(record)},
    filters
  }));
}

function moduleDataEdits(){
  if(!moduleDataDirty())return [];
  const beforeElements=Object.fromEntries((state.savedModuleData.elements||[]).map(element=>[element.path,element]));const edits=[];
  for(const element of state.moduleData.elements||[]){const old=beforeElements[element.path];if(!old)continue;const oldAttributes=Object.fromEntries((old.attributes||[]).map(attribute=>[attribute.name,attribute]));for(const attribute of element.attributes||[]){const previous=oldAttributes[attribute.name];if(previous&&String(previous.value)!==String(attribute.value))edits.push({elementPath:element.path,tag:element.tag,attribute:attribute.name,originalValue:String(previous.value),value:attribute.value})}for(const missing of element.missingRequired||[])if(missing.add)edits.push({addRequired:true,elementPath:element.path,tag:element.tag,attribute:missing.name,value:missing.value})}
  return edits;
}
async function saveModuleData(){const edits=moduleDataEdits();if(!edits.length)return;const result=prepareModuleData(await post("/api/module-data/save",{path:state.moduleData.relativePath,edits,sourceHash:state.savedModuleData.sourceHash||""}));state.moduleData=result;state.savedModuleData=clone(result);if(!(result.records||[]).some(record=>record.path===state.moduleDataRecordPath))applyModuleDataRecordSelection(result.records?.[0])}
