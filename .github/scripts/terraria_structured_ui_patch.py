from pathlib import Path

path=Path('games/terraria/editor.html')
text=path.read_text(encoding='utf-8')

def one(old,new):
    global text
    count=text.count(old)
    if count!=1: raise SystemExit(f'expected one editor anchor, found {count}: {old[:120]!r}')
    text=text.replace(old,new,1)

one(
    '.terraria-asset-preview audio{width:min(720px,100%)}\n',
    '.terraria-asset-preview audio{width:min(720px,100%)}\n'
    '    .terraria-content-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px}\n'
    '    .terraria-content-group{display:grid;gap:8px;padding:10px;border:1px solid var(--lex-border);background:var(--lex-panel)}\n'
    '    .terraria-content-field{display:grid;grid-template-columns:minmax(120px,1fr) minmax(120px,1.4fr);gap:8px;align-items:center}\n'
    '    .terraria-content-field textarea{min-height:90px;resize:vertical}\n'
    '    .terraria-content-field input,.terraria-content-field select,.terraria-content-field textarea{width:100%}\n'
)
one(
    '  let contentCreating=false,contentKind="item",contentName="",contentDisplay="",contentTooltip="",contentResult=null,error="";\n',
    '  let contentCreating=false,contentKind="item",contentName="",contentDisplay="",contentDescription="",contentResult=null;\n'
    '  let contentSchemas=[],contentFiles=[],contentCreateValues={},structuredSaved=null,structuredCurrent=null,structuredLoading=false;\n'
    '  let logicKind="system",logicName="",logicCreating=false,error="";\n',
)
one(
    '  function sourceDirty(){return !!(sourceSaved&&sourceCurrent&&sourceCurrent.text!==sourceSaved.text)}\n'
    '  const dirtyCount=()=>dirtyKeys().length+localizationDirtyEntries().length+(sourceDirty()?1:0);\n',
    '  function sourceDirty(){return !!(sourceSaved&&sourceCurrent&&sourceCurrent.text!==sourceSaved.text)}\n'
    '  function structuredDirty(){return !!(structuredSaved&&structuredCurrent&&JSON.stringify(structuredSaved.values)!==JSON.stringify(structuredCurrent.values))}\n'
    '  const dirtyCount=()=>dirtyKeys().length+localizationDirtyEntries().length+(sourceDirty()?1:0)+(structuredDirty()?1:0);\n',
)

start=text.find('  async function createContentScaffold(){\n')
end=text.find('  function projectName(){',start)
if start<0 or end<0: raise SystemExit('content function block anchors missing')
new_block=r'''  function contentSchema(kind=contentKind){return contentSchemas.find(schema=>schema.kind===kind)||null}
  function schemaDefaults(kind){const schema=contentSchema(kind);return Object.fromEntries((schema?.fields||[]).map(field=>[field.name,clone(field.default)]))}
  function resetContentCreateValues(){contentCreateValues=schemaDefaults(contentKind)}
  function localizedContentKind(kind){return ["item","npc","projectile","buff","tile"].includes(kind)}
  function describedContentKind(kind){return kind==="item"||kind==="buff"}
  function schemaFieldControl(field,values,onchange,disabled=false){
    const value=values[field.name]??field.default;
    if(field.type==="bool")return el("input",{type:"checkbox",checked:!!value,disabled,onchange:event=>onchange(event.target.checked)});
    if(field.type==="enum"){
      const select=el("select",{disabled,onchange:event=>onchange(event.target.value)});
      for(const optionValue of field.options||[]){const option=el("option",{value:optionValue},optionValue);option.selected=String(value)===String(optionValue);select.append(option)}
      return select;
    }
    if(field.type==="lines")return el("textarea",{value:String(value??""),disabled,placeholder:field.help||"One entry per line",oninput:event=>onchange(event.target.value)});
    const numeric=field.type==="int"||field.type==="float";
    return el("input",{type:numeric?"number":"text",value:String(value??""),step:field.type==="float"?"any":"1",min:numeric&&field.min!==undefined?field.min:null,max:numeric&&field.max!==undefined?field.max:null,disabled,oninput:event=>onchange(numeric?event.target.value:event.target.value)});
  }
  function schemaEditor(schema,values,onchange,{disabled=false}={}){
    if(!schema)return el("div",{class:"terraria-note"},"No schema available.");
    const groups=[];for(const field of schema.fields){let group=groups.find(row=>row.name===field.group);if(!group){group={name:field.group,fields:[]};groups.push(group)}group.fields.push(field)}
    return el("div",{class:"terraria-content-grid"},...groups.map(group=>el("div",{class:"terraria-content-group"},el("strong",{},group.name),...group.fields.map(field=>el("label",{class:"terraria-content-field",title:field.help||""},el("span",{},field.label),schemaFieldControl(field,values,value=>{values[field.name]=value;onchange();},disabled)))));
  }
  async function refreshStructuredContent(preferredPath=""){
    const catalog=await request("/api/content");contentSchemas=catalog.schemas||[];contentFiles=catalog.files||[];
    if(!contentSchema(contentKind)&&contentSchemas.length)contentKind=contentSchemas[0].kind;
    if(!Object.keys(contentCreateValues).length)resetContentCreateValues();
    const path=preferredPath||structuredCurrent?.path||contentFiles[0]?.path||"";
    if(path&&contentFiles.some(file=>file.path===path)){const state=await request(`/api/content/file?path=${encodeURIComponent(path)}`);structuredSaved=clone(state);structuredCurrent=clone(state)}
    else{structuredSaved=null;structuredCurrent=null}
  }
  async function loadStructuredContent(path){
    if(!path||structuredDirty())return;structuredLoading=true;error="";render();
    try{const state=await request(`/api/content/file?path=${encodeURIComponent(path)}`);structuredSaved=clone(state);structuredCurrent=clone(state)}catch(exc){structuredSaved=null;structuredCurrent=null;error=String(exc.message||exc)}
    structuredLoading=false;render();
  }
  async function createStructuredContent(){
    if(contentCreating||dirtyCount())return;const name=contentName.trim();if(!name){error="Enter an internal content/class name.";render();return}
    contentCreating=true;contentResult=null;error="";render();
    try{
      const result=await request("/api/content/create",{method:"POST",body:JSON.stringify({kind:contentKind,name,values:contentCreateValues,displayName:contentDisplay,description:contentDescription})});
      const [source,localization,assets,map,catalog]=await Promise.all([request("/api/source"),request("/api/localization"),request("/api/assets"),request("/api/data-map"),request("/api/content")]);
      sourceFiles=source.files;localizationFiles=localization.files;assetFiles=assets.files;mapRows=map.rows;contentSchemas=catalog.schemas||[];contentFiles=catalog.files||[];
      structuredSaved=clone(result);structuredCurrent=clone(result);contentResult=result;contentName="";contentDisplay="";contentDescription="";resetContentCreateValues();
    }catch(exc){error=String(exc.message||exc)}
    contentCreating=false;render();shell?.refresh?.();
  }
  async function createLogicScaffold(){
    if(logicCreating||dirtyCount())return;const name=logicName.trim();if(!name){error="Enter a logic class name.";render();return}
    logicCreating=true;error="";render();
    try{const result=await request(logicKind==="player"?"/api/content/player":"/api/content/system",{method:"POST",body:JSON.stringify({name})});logicName="";contentResult=result;const [source,map]=await Promise.all([request("/api/source"),request("/api/data-map")]);sourceFiles=source.files;mapRows=map.rows}catch(exc){error=String(exc.message||exc)}
    logicCreating=false;render();
  }
  function contentPanel(){
    const locked=contentCreating||logicCreating||structuredLoading||dirtyCount()>0;const createSchema=contentSchema(contentKind);
    const kindSelect=el("select",{disabled:locked,onchange:event=>{contentKind=event.target.value;contentResult=null;resetContentCreateValues();render()}},...contentSchemas.map(schema=>{const option=el("option",{value:schema.kind},schema.label);option.selected=schema.kind===contentKind;return option}));
    const createHeader=el("div",{class:"terraria-note terraria-content-form"},el("strong",{},"New structured content"),kindSelect,el("input",{type:"text",value:contentName,placeholder:"Internal class name",disabled:locked,oninput:event=>{contentName=event.target.value}}),localizedContentKind(contentKind)?el("input",{type:"text",value:contentDisplay,placeholder:"Display / map name (optional)",disabled:locked,oninput:event=>{contentDisplay=event.target.value}}):null,describedContentKind(contentKind)?el("input",{type:"text",value:contentDescription,placeholder:contentKind==="item"?"Tooltip (optional)":"Description (optional)",disabled:locked,oninput:event=>{contentDescription=event.target.value}}):null,el("button",{class:"terraria-build-button",type:"button",disabled:locked||!createSchema,onclick:createStructuredContent},contentCreating?"CREATING…":"CREATE"));
    const createEditor=schemaEditor(createSchema,contentCreateValues,()=>{shell?.refresh?.()},{disabled:locked});
    const selector=el("select",{disabled:structuredLoading||structuredDirty(),onchange:event=>loadStructuredContent(event.target.value)},el("option",{value:""},"Select managed content…"),...contentFiles.map(file=>{const option=el("option",{value:file.path},`${file.name} · ${file.kind}`);option.selected=file.path===structuredCurrent?.path;return option}));
    const managedToolbar=el("div",{class:"terraria-note terraria-content-form"},el("strong",{},"Managed content"),selector,structuredLoading?el("span",{},"Loading…"):structuredCurrent?el("span",{class:"terraria-status"},structuredCurrent.kind):el("span",{class:"terraria-status"},`${contentFiles.length} FILES`));
    const managedEditor=structuredCurrent?schemaEditor({fields:structuredCurrent.schema},structuredCurrent.values,()=>{render();shell?.refresh?.()}):el("div",{class:"terraria-note"},contentFiles.length?"Select managed content above.":"No marker-managed content exists yet. Create one above; legacy/raw C# files remain editable in Source.");
    const logicSelect=el("select",{disabled:locked,onchange:event=>{logicKind=event.target.value}},...[["system","ModSystem"],["player","ModPlayer"]].map(([value,label])=>{const option=el("option",{value},label);option.selected=value===logicKind;return option}));
    const logicForm=el("div",{class:"terraria-note terraria-content-form"},el("strong",{},"Logic scaffold"),logicSelect,el("input",{type:"text",value:logicName,placeholder:"Class name",disabled:locked,oninput:event=>{logicName=event.target.value}}),el("button",{class:"terraria-build-button",type:"button",disabled:locked,onclick:createLogicScaffold},logicCreating?"CREATING…":"CREATE"));
    const notes=[];if(contentResult)notes.push(el("div",{class:"terraria-note terraria-success"},el("strong",{},`${contentResult.name} created.`),el("div",{class:"terraria-build-path"},`Source: ${contentResult.path||contentResult.source?.path||"created"}`)));
    notes.push(el("div",{class:"terraria-note"},"Structured saves replace only the LEXEDITOR-BEGIN/END managed region and its metadata header. Add custom AI, draw hooks, networking, advanced loot/spawn logic, etc. outside that region in Source; Lexeditor preserves it. Manual edits inside the managed region are intentionally replaced by the next property save."));
    return el("div",{class:"terraria-page"},...warnings(),createHeader,createEditor,...notes,managedToolbar,managedEditor,logicForm);
  }
'''
text=text[:start]+new_block+text[end:]

one(
    '      const [metadata,map,build,localization,source,assets]=await Promise.all([request("/api/build-metadata"),request("/api/data-map"),request("/api/build"),request("/api/localization"),request("/api/source"),request("/api/assets")]);\n'
    '      saved=clone(metadata);current=clone(metadata);mapRows=map.rows;buildInfo=build;localizationFiles=localization.files;sourceFiles=source.files;assetFiles=assets.files;error="";\n',
    '      const [metadata,map,build,localization,source,assets,structured]=await Promise.all([request("/api/build-metadata"),request("/api/data-map"),request("/api/build"),request("/api/localization"),request("/api/source"),request("/api/assets"),request("/api/content")]);\n'
    '      saved=clone(metadata);current=clone(metadata);mapRows=map.rows;buildInfo=build;localizationFiles=localization.files;sourceFiles=source.files;assetFiles=assets.files;contentSchemas=structured.schemas||[];contentFiles=structured.files||[];if(!contentSchema(contentKind)&&contentSchemas.length)contentKind=contentSchemas[0].kind;resetContentCreateValues();error="";\n',
)
one(
    '      const firstAsset=assetFiles.find(file=>!file.error&&file.editable)?.path;\n'
    '      const loads=[];\n',
    '      const firstAsset=assetFiles.find(file=>!file.error&&file.editable)?.path;\n'
    '      const firstStructured=contentFiles[0]?.path;\n'
    '      const loads=[];\n',
)
one(
    '      if(firstAsset)loads.push(request(`/api/assets/file?path=${encodeURIComponent(firstAsset)}`).then(state=>{assetCurrent=state}));\n'
    '      await Promise.all(loads);\n',
    '      if(firstAsset)loads.push(request(`/api/assets/file?path=${encodeURIComponent(firstAsset)}`).then(state=>{assetCurrent=state}));\n'
    '      if(firstStructured)loads.push(request(`/api/content/file?path=${encodeURIComponent(firstStructured)}`).then(state=>{structuredSaved=clone(state);structuredCurrent=clone(state)}));\n'
    '      await Promise.all(loads);\n',
)

save_anchor='  async function save(){\n    if(!dirtyCount())return;error="";\n    try{\n'
replacement='  async function save(){\n    if(!dirtyCount())return;error="";\n    try{\n      if(structuredDirty()&&sourceDirty()&&structuredCurrent?.path===sourceCurrent?.path)throw new Error("This managed C# file has unsaved edits in both Content and Source. Discard one editing mode before saving.");\n'
one(save_anchor,replacement)
one(
    '      if(sourceSaved&&sourceCurrent&&sourceDirty()){\n',
    '      if(structuredSaved&&structuredCurrent&&structuredDirty()){\n'
    '        const result=await request("/api/content/file",{method:"POST",body:JSON.stringify({path:structuredCurrent.path,values:structuredCurrent.values,expectedSha256:structuredSaved.sha256})});structuredSaved=clone(result);structuredCurrent=clone(result);contentFiles=(await request("/api/content")).files;sourceFiles=(await request("/api/source")).files;if(sourceCurrent?.path===result.path&&!sourceDirty()){const state=await request(`/api/source/file?path=${encodeURIComponent(result.path)}`);sourceSaved=clone(state);sourceCurrent=clone(state)}\n'
    '      }\n'
    '      if(sourceSaved&&sourceCurrent&&sourceDirty()){\n',
)
one(
    '        const result=await request("/api/source/file",{method:"POST",body:JSON.stringify({path:sourceCurrent.path,text:sourceCurrent.text,expectedSha256:sourceSaved.sha256})});sourceSaved=clone(result);sourceCurrent=clone(result);sourceFiles=(await request("/api/source")).files;\n'
    '      }\n',
    '        const result=await request("/api/source/file",{method:"POST",body:JSON.stringify({path:sourceCurrent.path,text:sourceCurrent.text,expectedSha256:sourceSaved.sha256})});sourceSaved=clone(result);sourceCurrent=clone(result);sourceFiles=(await request("/api/source")).files;if(structuredCurrent?.path===result.path){try{const state=await request(`/api/content/file?path=${encodeURIComponent(result.path)}`);structuredSaved=clone(state);structuredCurrent=clone(state)}catch(_ignored){structuredSaved=null;structuredCurrent=null;contentFiles=(await request("/api/content")).files}}\n'
    '      }\n',
)
one(
    '  async function discard(){current=clone(saved);locCurrent=clone(locSaved);sourceCurrent=clone(sourceSaved);locDeletedKeys.clear();locNewKey="";locNewValue="";sourceNewPath="";sourceRenamePath="";assetRenamePath="";error="";render()}\n',
    '  async function discard(){current=clone(saved);locCurrent=clone(locSaved);sourceCurrent=clone(sourceSaved);structuredCurrent=clone(structuredSaved);locDeletedKeys.clear();locNewKey="";locNewValue="";sourceNewPath="";sourceRenamePath="";assetRenamePath="";error="";render()}\n',
)
one(
    '    dirtyCount,readonly:()=>!current?.editable&&!locCurrent?.editable&&!sourceCurrent?.editable,save,discard,\n',
    '    dirtyCount,readonly:()=>!current?.editable&&!locCurrent?.editable&&!sourceCurrent?.editable&&!structuredCurrent?.editable,save,discard,\n',
)
path.write_text(text,encoding='utf-8')
