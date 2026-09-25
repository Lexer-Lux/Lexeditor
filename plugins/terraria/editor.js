  "use strict";
  const {el,actionRow,badge,codeField,detailNote,detailPanel,detailSection,detailField,logView,notice,readonlyField,infoHelp,panelLayout,pagedListDetail,columnList,stack,textArea,tabbedPanel,confirmAction}=LexeditorUI;
  let tab="metadata",saved=null,current=null,mapRows=[],buildInfo=null,buildResult=null,building=false;
  let localizationFiles=[],locSaved=null,locCurrent=null,locLoading=false,locFilter="",locNewKey="",locNewValue="",locDeletedKeys=new Set();
  let sourceFiles=[],sourceSaved=null,sourceCurrent=null,sourceLoading=false,sourceNewPath="",sourceRenamePath="",sourceGotoLine=0;
  let assetFiles=[],assetCurrent=null,assetLoading=false,assetNewPath="",assetRenamePath="",assetImportFile=null,assetReplaceFile=null;
  let contentCreating=false,contentKind="item",contentName="",contentDisplay="",contentDescription="",contentResult=null;
  let contentSchemas=[],contentFiles=[],contentCreateValues={},structuredSaved=null,structuredCurrent=null,structuredLoading=false;
  let logicKind="system",logicName="",logicCreating=false,error="";
  let contentView="managed",contentQuery="",contentPage=0,contentPageSize=15,contentSort={key:"name",dir:1};
  let localizationCatalog=[],locCulture="",locQuery="",locPage=0,locPageSize=15,locSort={key:"key",dir:1};
  let sourceQuery="",sourcePage=0,sourcePageSize=15,sourceSort={key:"path",dir:1},sourceCreateMode=false;
  let assetQuery="",assetPage=0,assetPageSize=15,assetSort={key:"path",dir:1},assetImportMode=false;
  let mapPage=0,mapQuery="",mapStatus="",mapSort=["filename",1];

  const clone=value=>JSON.parse(JSON.stringify(value));
  async function request(path,options={}){
    const response=await fetch(path,{headers:{"Content-Type":"application/json"},...options});
    const payload=await response.json();
    if(!response.ok)throw new Error(payload.error||`Request failed (${response.status})`);
    return payload;
  }
  const basename=value=>String(value||"").split(/[\\/]/).filter(Boolean).at(-1)||"";
  const foldername=value=>{const parts=String(value||"").split(/[\\/]/).filter(Boolean);parts.pop();return parts.join("/")||"Project root"};
  function sortedRows(rows,state,getters={}){
    const key=state?.key||Object.keys(getters)[0]||"path",dir=Number(state?.dir)||1,get=getters[key]||((row)=>row?.[key]);
    return [...rows].sort((left,right)=>{const a=get(left),b=get(right);const result=typeof a==="number"&&typeof b==="number"?a-b:String(a??"").localeCompare(String(b??""),undefined,{numeric:true,sensitivity:"base"});return result*dir});
  }
  function nextSort(state,key){return state.key===key?{key,dir:-state.dir}:{key,dir:1}}
  function loadingPanel(message="Loading…"){return el("p",{class:"lex-notice",role:"status"},message)}

  function emptyPanel(title,message){return detailPanel({title,body:[el("p",{class:"lex-notice"},message)]})}
  // A game with no mod yet is not a stuck editor. The service says what is
  // missing (usually the mod source folder), and this shows that instead of a
  // spinner that waits for a file nobody is going to create on its own.
  function missingModPanel(title="No mod yet"){
    return detailPanel({title,body:[
      el("p",{class:"lex-notice lex-tone-warning",role:"alert"},error||"This game has no mod source yet."),
      el("p",{class:"lex-notice"},"Lexeditor edits tModLoader source projects - a folder that holds build.txt. Choose Create Mod in the Mod menu, or select the folder that holds your build.txt.")]})}
  // Every tab describes a mod source, so a game with no mod has nothing to
  // list on any of them. They must say that instead of showing an empty table
  // that reads as a broken page.
  function noModSource(){return !current&&!!error}
  function cultureFlag(culture){const code=String(culture||"").toLowerCase();if(code==="en-us")return "🇺🇸";if(code==="en-gb")return "🇬🇧";if(code==="fr-fr")return "🇫🇷";if(code==="de-de")return "🇩🇪";if(code==="es-es")return "🇪🇸";if(code==="it-it")return "🇮🇹";if(code==="pt-br")return "🇧🇷";if(code==="ru-ru")return "🇷🇺";if(code==="pl-pl")return "🇵🇱";if(code==="zh-hans")return "🇨🇳";if(code==="ja-jp")return "🇯🇵";if(code==="ko-kr")return "🇰🇷";return "🌐"}
  function showNavigationLoading(label){document.querySelector("#main").replaceChildren(loadingPanel(`Loading ${label}…`))}

  function dirtyKeys(){
    if(!saved||!current)return [];
    return Object.keys(current.values).filter(key=>JSON.stringify(current.values[key])!==JSON.stringify(saved.values[key]));
  }
  function localizationCreatedEntries(){return locCurrent?.entries?.filter(entry=>entry.isNew)??[]}
  function localizationUpdatedEntries(){
    if(!locSaved||!locCurrent)return [];
    const original=new Map(locSaved.entries.map(entry=>[entry.key,entry.value]));
    return locCurrent.entries.filter(entry=>entry.editable&&!entry.isNew&&entry.value!==original.get(entry.key));
  }
  function localizationDeletedEntries(){return [...locDeletedKeys]}
  function localizationDirtyEntries(){return [...localizationUpdatedEntries(),...localizationCreatedEntries(),...localizationDeletedEntries().map(key=>({key,isDeleted:true}))]}
  function sourceDirty(){return !!(sourceSaved&&sourceCurrent&&sourceCurrent.text!==sourceSaved.text)}
  function structuredDirty(){return !!(structuredSaved&&structuredCurrent&&JSON.stringify(structuredSaved.values)!==JSON.stringify(structuredCurrent.values))}
  const dirtyCount=()=>dirtyKeys().length+localizationDirtyEntries().length+(sourceDirty()?1:0)+(structuredDirty()?1:0);
  function setValue(key,value){current.values[key]=value;render();shell?.refresh?.()}
  function controlLabel(key){
    const words=String(key).replace(/([a-z0-9])([A-Z])/g,"$1 $2").replace(/[_-]+/g," ").trim().toLowerCase();
    return words ? words[0].toUpperCase()+words.slice(1) : "Value";
  }
  function textControl(key,{placeholder="",label=controlLabel(key)}={}){
    return el("input",{type:"text",value:current.values[key]??"",placeholder,"aria-label":label,disabled:!current.editable,oninput:event=>{current.values[key]=event.target.value;shell?.refresh?.()}});
  }
  function listControl(key,{placeholder="",label=controlLabel(key)}={}){
    const values=Array.isArray(current.values[key])?current.values[key]:[];
    return textArea({value:values.join("\n"),placeholder,"aria-label":label,disabled:!current.editable,oninput:event=>{current.values[key]=event.target.value.split(/\r?\n/).map(value=>value.trim()).filter(Boolean);shell?.refresh?.()}});
  }
  function boolControl(key){
    const declared=key in current.values;
    return el("input",{
      type:"checkbox","aria-label":controlLabel(key),
      "aria-description":declared?"":"Not declared in build.txt. Check to add this property.",
      title:declared?"":"Not declared — check to add",
      checked:declared?!!current.values[key]:false,
      disabled:!current.editable,
      onchange:event=>setValue(key,event.target.checked),
    });
  }
  function sideControl(){
    const select=el("select",{"aria-label":"Side",disabled:!current.editable,onchange:event=>setValue("side",event.target.value)});
    for(const value of ["Both","Client","Server","NoSync"]){const option=el("option",{value},value);option.selected=current.values.side===value;select.append(option)}
    return select;
  }
  function warnings(){
    if(!current)return [];
    const items=[];
    if(current.duplicates.length)items.push(el("p",{class:"lex-notice lex-tone-warning",role:"alert"},`Structured saving is disabled because build.txt repeats: ${current.duplicates.join(", ")}. Remove the ambiguity in source first.`));
    if(error)items.push(el("p",{class:"lex-notice lex-tone-warning",role:"alert"},error));
    return items;
  }
  function metadataPanel(){
    if(!current)return error?missingModPanel():loadingPanel("Loading build.txt…");
    const panel=detailPanel({title:"build.txt",identity:"TMOD",meta:"tModLoader package metadata",body:[
      ...warnings(),
      detailSection({title:"IDENTITY",body:[
        detailField({label:"DISPLAY NAME",control:textControl("displayName"),dataType:"STRING",help:infoHelp("The player-facing mod name shown by tModLoader.")}),
        detailField({label:"AUTHOR",control:textControl("author"),dataType:"STRING",help:infoHelp("The author text tModLoader shows with the mod.")}),
        detailField({label:"VERSION",control:textControl("version",{placeholder:"1.0"}),dataType:"VERSION",help:infoHelp("The package version tModLoader records for dependency and update comparisons.")}),
        detailField({label:"HOMEPAGE",control:textControl("homepage",{placeholder:"Not declared"}),dataType:"STRING",help:infoHelp("Optional project or support page shown with the mod metadata.")}),
      ]}),
      detailSection({title:"RUNTIME",body:[detailField({label:"SIDE",control:sideControl(),dataType:"ENUM",help:infoHelp("Controls whether tModLoader expects this mod on clients, servers, both sides, or without network synchronization.")})]}),
      detailSection({title:"PACKAGE",body:[
        detailField({label:"HIDE CODE",control:boolControl("hideCode"),dataType:"BOOL",help:infoHelp("When enabled, tModLoader omits source visibility from the packaged mod according to its build rules.")}),
        detailField({label:"HIDE RESOURCES",control:boolControl("hideResources"),dataType:"BOOL",help:infoHelp("When enabled, tModLoader hides packaged resources according to its build rules.")}),
        detailField({label:"INCLUDE SOURCE",control:boolControl("includeSource"),dataType:"BOOL",help:infoHelp("Includes source in the built package when tModLoader supports it.")}),
        detailField({label:"NO COMPILE",control:boolControl("noCompile"),dataType:"BOOL",help:infoHelp("Tells tModLoader not to compile C# for this project; use only for projects designed for that native build mode.")}),
        detailField({label:"PLAYABLE ON PREVIEW",control:boolControl("playableOnPreview"),dataType:"BOOL",help:infoHelp("Marks whether tModLoader Preview may load the mod. This does not make 1.4.5-only APIs compatible with this 1.4.4-targeted editor.")}),
        detailField({label:"TRANSLATION MOD",control:boolControl("translationMod"),dataType:"BOOL",help:infoHelp("Marks the project as a translation mod for tModLoader packaging and loading.")}),
      ]}),
    ]});
    return panelLayout([panel],{layoutKey:"terraria-metadata",defaultSizes:[100]});
  }
  function informationPanel(){
    const runtimeState=buildInfo?.available?"Ready":buildInfo?.reason||"Not detected";
    const enabledState=!buildInfo?.enabledStateValid?"Unknown":buildInfo?.enabled?"Enabled":"Disabled";
    return detailPanel({className:"lex-information-panel",title:"Information",meta:"Terraria / tModLoader setup and deployment",body:[
      detailSection({title:"SUPPORTED RUNTIME",body:[
        detailField({label:"TARGET",control:readonlyField("tModLoader 1.4.4 stable v2026.07.3.0"),help:infoHelp("This plugin is authored and regression-tested against tModLoader 1.4.4 stable v2026.07.3.0. Preview/1.4.5 APIs are outside this PR compatibility boundary.")}),
        detailField({label:"INSTALLED VERSION",control:readonlyField(buildInfo?.runtimeVersion||"Not detected")}),
        detailField({label:"INSTALL",control:readonlyField(buildInfo?.installRoot||"Not detected")}),
        detailField({label:"BUILD HANDOFF",control:readonlyField(runtimeState),help:infoHelp("Build Mod invokes the installed tModLoader native build pipeline; Lexeditor does not reproduce its compiler or .tmod packager.")}),
      ]}),
      detailSection({title:"PROJECT",body:[
        detailField({label:"SOURCE",control:readonlyField(buildInfo?.project||"Not selected"),help:infoHelp("Editable files stay in the selected tModLoader ModSources project rather than the vanilla Terraria installation.")}),
        detailField({label:"PACKAGE",control:readonlyField(buildInfo?.expectedArtifact||"Not available")}),
        detailField({label:"ENABLED",control:readonlyField(enabledState),help:infoHelp("Lexeditor reads tModLoader enabled-mod state but does not rewrite enabled.json behind the running loader.")}),
      ]}),
      detailSection({title:"RUNTIME OWNERSHIP",body:[
        detailField({label:"TML INSTALL",control:readonlyField("External Steam runtime (app 1281930)"),help:infoHelp("tModLoader is the game runtime this plugin targets, not a Lexeditor helper executable. Steam/Terraria ownership and tModLoader installation remain outside Lexeditor; no automatic helper updater is installed or enabled by this plugin.")}),
        detailField({label:"AUTO UPDATES",control:readonlyField("None managed by Lexeditor"),help:infoHelp("Lexeditor does not silently update tModLoader. Steam owns that runtime installation; this plugin must fail closed when the detected runtime is outside its supported target.")}),
      ]}),
      LexeditorUI.modLoaderSection({
        loader:"tModLoader 1.4.4 stable. Lexeditor authors native tModLoader source mods; it does not patch vanilla Terraria or install a second loader.",
        output:"Source stays under ModSources/<ModName>/. Build Mod invokes tModLoader native build and expects the package under the save root at Mods/<ModName>.tmod.",
        order:"tModLoader resolves dependencies and runtime load order. build.txt sortAfter/sortBefore express ordering requests; Lexeditor does not invent a separate file-priority system.",
        safety:"Lexeditor edits only the selected ModSources project. Vanilla Terraria files and tModLoader enabled.json remain read only.",
        removal:"Disable or remove the mod through tModLoader, then delete its local .tmod and source project if desired. No vanilla Terraria data needs restoring.",
      }),
    ]});
  }

  async function openBuildDiagnostic(diagnostic){
    if(!diagnostic?.projectFile)return;
    try{const state=await request(`/api/source/file?path=${encodeURIComponent(diagnostic.path)}`);sourceSaved=clone(state);sourceCurrent=clone(state);sourceGotoLine=Math.max(1,Number(diagnostic.line)||1);tab="source";error="";render()}catch(exc){error=String(exc.message||exc);render()}
  }
  function buildCard(){
    if(!buildInfo)return loadingPanel("Checking native tModLoader build handoff…");
    const blockedByDirty=dirtyCount()>0;
    const reason=blockedByDirty?"Save or discard edits before building.":(buildInfo.reason||"Ready to invoke tModLoader native -build path.");
    const body=[detailField({label:"ACTION",control:actionRow(
      el("button",{class:"lex-dialog-action primary",disabled:building||blockedByDirty||!buildInfo.available,onclick:buildMod},building?"BUILDING…":"BUILD MOD"),el("strong",{},buildInfo.available&&!blockedByDirty?"Native build ready":"Native build unavailable"))}),
      detailNote(reason),
      detailField({label:"PACKAGE",control:badge(buildInfo.artifactExists?"Package built":"Package missing")}),
      detailField({label:"ENABLED",control:badge(!buildInfo.enabledStateValid?"Enabled state unknown":(buildInfo.enabled?"Enabled":"Disabled"))}),
      detailNote(`Expected package: ${buildInfo.expectedArtifact}`),
      detailNote(`tModLoader state: ${buildInfo.enabledStatePath}`)];
    if(!buildInfo.enabledStateValid&&buildInfo.enabledStateError)body.push(el("p",{class:"lex-notice lex-tone-warning",role:"alert"},buildInfo.enabledStateError));
    if(buildResult){
      const success=buildResult.ok;
      const summary=success?`Build succeeded${buildResult.artifactExists?" and produced the expected .tmod":""}${buildResult.enabled?"; tModLoader reports it enabled.":"."}`:(buildResult.error||`Build failed with exit code ${buildResult.exitCode??"unknown"}.`);
      body.push(notice({message:summary,tone:success?"success":"warning"}));
      if(success&&buildResult.enabledStateValid&&!buildResult.enabled)body.push(detailNote("The package was built, but enabled.json does not currently list this mod as enabled."));
      const diagnostics=Array.isArray(buildResult.diagnostics)?buildResult.diagnostics:[];
      if(diagnostics.length){
        const rows=diagnostics.map((row,index)=>({...row,id:index+1,location:`${row.path}:${row.line}:${row.column}`}));
        body.push(columnList({rows,key:row=>row.id,selected:null,select:row=>openBuildDiagnostic(row),columns:[
          {key:"severity",label:"Severity",sortable:true},
          {key:"location",label:"Location",sortable:true,align:"start"},
          {key:"code",label:"Code",sortable:true},
          {key:"message",label:"Message",sortable:true,align:"start"},
        ],"aria-label":"tModLoader build diagnostics"}));
      }
      const log=[buildResult.stdout&&`STDOUT\n${buildResult.stdout}`,buildResult.stderr&&`STDERR\n${buildResult.stderr}`,buildResult.nativeLog&&`TMODLOADER NATIVES LOG\n${buildResult.nativeLog}`].filter(Boolean).join("\n\n");
      if(log)body.push(logView(log));
    }
    return detailSection({title:"BUILD",body});
  }

  function dependenciesPanel(){
    if(!current)return error?missingModPanel():loadingPanel("Loading build.txt…");
    const panel=detailPanel({title:"References & Build",identity:"TMOD",meta:"tModLoader dependency and package rules",body:[
      ...warnings(),
      detailSection({title:"DEPENDENCIES",body:[
        detailField({label:"MOD REFERENCES",control:listControl("modReferences",{placeholder:"ExampleMod\nExampleLibrary@1.2"}),dataType:"LIST",help:infoHelp("Required tModLoader mods. Version-qualified dependencies use ModName@1.2. A mod cannot also appear as a weak reference or DLL reference.")}),
        detailField({label:"WEAK REFERENCES",control:listControl("weakReferences",{placeholder:"OptionalMod"}),dataType:"LIST",help:infoHelp("Optional tModLoader mods that may be absent. Do not repeat a required mod here.")}),
        detailField({label:"DLL REFERENCES",control:listControl("dllReferences",{placeholder:"LibraryName"}),dataType:"LIST",help:infoHelp("Managed libraries the project compiles against. A required mod reference cannot also be listed as a DLL reference.")}),
      ]}),
      detailSection({title:"LOAD ORDER",body:[
        detailField({label:"SORT AFTER",control:listControl("sortAfter",{placeholder:"ModName"}),dataType:"LIST",help:infoHelp("Requests that tModLoader load this mod after the named mods when both are present.")}),
        detailField({label:"SORT BEFORE",control:listControl("sortBefore",{placeholder:"ModName"}),dataType:"LIST",help:infoHelp("Requests that tModLoader load this mod before the named mods when both are present.")}),
      ]}),
      detailSection({title:"BUILD FILTER",body:[detailField({label:"BUILD IGNORE",control:listControl("buildIgnore",{placeholder:"Folder/*\nFile.ext"}),dataType:"LIST",help:infoHelp("Project-relative patterns tModLoader should exclude from the built .tmod package.")})]}),
      buildCard(),
    ]});
    return panelLayout([panel],{layoutKey:"terraria-dependencies",defaultSizes:[100]});
  }

  function contentSchema(kind=contentKind){return contentSchemas.find(schema=>schema.kind===kind)||null}
  function schemaDefaults(kind){const schema=contentSchema(kind);return Object.fromEntries((schema?.fields||[]).map(field=>[field.name,clone(field.default)]))}
  function resetContentCreateValues(){contentCreateValues=schemaDefaults(contentKind)}
  function localizedContentKind(kind){return ["item","npc","projectile","buff","tile","wall","prefix","biome"].includes(kind)}
  function describedContentKind(kind){return kind==="item"||kind==="buff"}
  function schemaFieldControl(field,values,onchange,disabled=false){
    const value=values[field.name]??field.default,common={disabled,"aria-label":field.label};
    if(field.type==="bool")return el("input",{...common,type:"checkbox",checked:!!value,onchange:event=>onchange(event.target.checked)});
    if(field.type==="enum"){
      const select=el("select",{...common,onchange:event=>onchange(event.target.value)});
      for(const optionValue of field.options||[]){const option=el("option",{value:optionValue},optionValue);option.selected=String(value)===String(optionValue);select.append(option)}
      return select;
    }
    if(field.type==="lines")return textArea({...common,value:String(value??""),placeholder:"One entry per line",oninput:event=>onchange(event.target.value)});
    const numeric=field.type==="int"||field.type==="float";
    return el("input",{...common,type:numeric?"number":"text",value:String(value??""),step:field.type==="float"?"any":"1",min:numeric&&field.min!==undefined?field.min:null,max:numeric&&field.max!==undefined?field.max:null,oninput:event=>{if(!numeric||event.target.value!=="")onchange(numeric?Number(event.target.value):event.target.value)}});
  }
  function schemaSections(schema,values,onchange,{disabled=false}={}){
    const fields=schema?.fields||[],groups=[];
    for(const field of fields){let group=groups.find(row=>row.name===field.group);if(!group){group={name:field.group||"GENERAL",fields:[]};groups.push(group)}group.fields.push(field)}
    return groups.map(group=>detailSection({title:String(group.name||"GENERAL").toUpperCase(),body:group.fields.map(field=>detailField({
      label:String(field.label||field.name).toUpperCase(),
      dataType:field.type==="bool"?"BOOL":field.type==="enum"?"ENUM":field.type==="int"?"INT":field.type==="float"?"FLOAT":field.type==="lines"?"LIST":"STRING",
      min:field.min,max:field.max,help:field.help?infoHelp(field.help):null,
      control:schemaFieldControl(field,values,value=>{values[field.name]=value;onchange(field,value)},disabled),
    }))}));
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
  function structuredDetail(row){
    if(!row)return emptyPanel("Managed Content","No managed content is selected.");
    if(structuredLoading||structuredCurrent?.path!==row.path)return loadingPanel(`Loading ${row.name}…`);
    const schema={fields:structuredCurrent.schema||[]};
    return detailPanel({title:row.name,meta:`${row.kind} · ${row.path}`,body:[
      ...schemaSections(schema,structuredCurrent.values,()=>{render();shell?.refresh?.()},{disabled:!structuredCurrent.editable}),
      detailSection({title:"SOURCE BOUNDARY",body:[
        detailField({label:"FILE",control:readonlyField(row.path)}),
        detailField({label:"MANAGED REGION",control:readonlyField("LEXEDITOR-BEGIN / LEXEDITOR-END"),help:infoHelp("Content edits regenerate only the marked Lexeditor region. Author-written C# outside that region is preserved and remains editable on Source.")}),
      ]}),
    ]});
  }
  function contentManagedPanel(){
    const query=contentQuery.trim().toLocaleLowerCase();
    let rows=contentFiles.filter(row=>!query||`${row.name} ${row.kind} ${row.path}`.toLocaleLowerCase().includes(query));
    rows=sortedRows(rows,contentSort,{name:row=>row.name,kind:row=>row.kind,path:row=>row.path});
    return pagedListDetail({rows,key:row=>row.path,slots:false,noun:"managed content",page:contentPage,pageSize:contentPageSize,selected:structuredCurrent?.path||rows[0]?.path||null,
      splitKey:"terraria-content",rowsKey:"terraria-content",defaultSplit:43,minLeft:300,minRight:360,
      search:{key:"terraria-content",value:contentQuery,label:"Search managed Terraria content",placeholder:"Search names, families, or source paths…",change:value=>{contentQuery=value;contentPage=0;render()}},
      sync:next=>{contentPage=next.page;contentPageSize=next.pageSize;if(next.selected&&next.selected!==structuredCurrent?.path&&!structuredLoading)void loadStructuredContent(next.selected)},
      change:next=>{contentPage=next.page;contentPageSize=next.pageSize;if(next.selected&&next.selected!==structuredCurrent?.path)void loadStructuredContent(next.selected);else render()},
      master:({rows,selected,select})=>columnList({rows,key:row=>row.path,selected,select,sortState:contentSort,sort:key=>{contentSort=nextSort(contentSort,key);render()},
        template:"minmax(130px,1fr) minmax(105px,.72fr) minmax(170px,1.35fr)",
        columns:[{key:"name",label:"Name",sortable:true,align:"start"},{key:"kind",label:"Family",sortable:true,align:"start"},{key:"path",label:"Source",sortable:true,align:"start"}],"aria-label":"Terraria managed content"}),
      detail:structuredDetail,emptyDetail:()=>emptyPanel("Managed Content","No managed content matches the current search."),
    });
  }
  function contentCreatePanel(){
    const locked=contentCreating||logicCreating||structuredLoading||dirtyCount()>0,schema=contentSchema(contentKind);
    const kindSelect=el("select",{disabled:locked,"aria-label":"Content family",onchange:event=>{contentKind=event.target.value;contentResult=null;resetContentCreateValues();render()}},...contentSchemas.map(row=>{const option=el("option",{value:row.kind},row.label);option.selected=row.kind===contentKind;return option}));
    const identity=detailSection({title:"NEW CONTENT",body:[
      detailField({label:"FAMILY",dataType:"ENUM",control:kindSelect,help:infoHelp("Choose the tModLoader content base class Lexeditor will generate and manage.")}),
      detailField({label:"CLASS NAME",dataType:"STRING",control:el("input",{type:"text",value:contentName,disabled:locked,"aria-label":"Internal class name",placeholder:"MyItem",oninput:event=>{contentName=event.target.value}}),help:infoHelp("A C# identifier used for the generated class and native content path.")}),
      localizedContentKind(contentKind)?detailField({label:"DISPLAY NAME",dataType:"STRING",control:el("input",{type:"text",value:contentDisplay,disabled:locked,"aria-label":"Display name",placeholder:"Optional player-facing name",oninput:event=>{contentDisplay=event.target.value}})}):null,
      describedContentKind(contentKind)?detailField({label:"DESCRIPTION",dataType:"STRING",control:el("input",{type:"text",value:contentDescription,disabled:locked,"aria-label":"Description",placeholder:"Optional player-facing text",oninput:event=>{contentDescription=event.target.value}})}):null,
    ].filter(Boolean)});
    const actions=detailSection({title:"CREATE",body:[detailField({label:"ACTION",control:el("button",{class:"lex-dialog-action primary",type:"button",disabled:locked||!schema,onclick:createStructuredContent},contentCreating?"CREATING…":"Create content"),help:infoHelp("Creation never overwrites an existing C# or asset path. Lexeditor also creates the localization and placeholder assets required by the selected family.")})]});
    const result=contentResult?detailSection({title:"LAST CREATED",body:[detailField({label:"SOURCE",control:readonlyField(contentResult.path||contentResult.source?.path||"Created")})]}):null;
    const panel=detailPanel({title:"Create Content",meta:"Native tModLoader structured scaffold",body:[identity,...schemaSections(schema,contentCreateValues,()=>shell?.refresh?.(),{disabled:locked}),actions,result].filter(Boolean)});
    return panelLayout([panel],{layoutKey:"terraria-content-create",defaultSizes:[100]});
  }
  function logicScaffoldPanel(){
    const locked=contentCreating||logicCreating||structuredLoading||dirtyCount()>0;
    const select=el("select",{disabled:locked,"aria-label":"Logic scaffold type",onchange:event=>{logicKind=event.target.value}},...([["system","ModSystem"],["player","ModPlayer"]].map(([value,label])=>{const option=el("option",{value},label);option.selected=value===logicKind;return option})));
    return detailPanel({title:"Logic Scaffold",meta:"Empty author-controlled C# class",body:[detailSection({title:"SCAFFOLD",body:[
      detailField({label:"TYPE",dataType:"ENUM",control:select,help:infoHelp("Creates an empty ModSystem or ModPlayer class for behavior that remains author-controlled C# rather than a structured property form.")}),
      detailField({label:"CLASS NAME",dataType:"STRING",control:el("input",{type:"text",value:logicName,disabled:locked,"aria-label":"Logic class name",placeholder:"GameplaySystem",oninput:event=>{logicName=event.target.value}})}),
      detailField({label:"ACTION",control:el("button",{class:"lex-dialog-action primary",type:"button",disabled:locked,onclick:createLogicScaffold},logicCreating?"CREATING…":"Create scaffold")}),
    ]})]});
  }
  function contentPanel(){
    if(noModSource())return missingModPanel();
    const tabs=[{id:"managed",label:"Managed"},{id:"create",label:"Create"},{id:"scaffolds",label:"Scaffolds"}];
    const content=contentView==="create"?contentCreatePanel():contentView==="scaffolds"?logicScaffoldPanel():contentManagedPanel();
    return stack({},...warnings(),tabbedPanel({tabs,active:contentView,label:"Terraria content views",change:value=>{contentView=value;render()},content}));
  }

  function projectName(){const parts=String(buildInfo?.project||"").split(/[\\/]/).filter(Boolean);return parts.at(-1)||"ExampleMod"}
  async function refreshLocalizationCatalog(){
    const usable=localizationFiles.filter(file=>!file.error&&file.loadable);
    const states=await Promise.all(usable.map(file=>request(`/api/localization/file?path=${encodeURIComponent(file.path)}`).catch(()=>null)));
    localizationCatalog=states.filter(Boolean).flatMap(state=>(state.entries||[]).map((entry,index)=>({...entry,path:state.path,culture:state.culture,prefix:state.prefix,index})));
    const cultures=[...new Set(localizationCatalog.map(row=>row.culture).filter(Boolean))].sort();
    if(!cultures.includes(locCulture))locCulture=locCurrent?.culture&&cultures.includes(locCurrent.culture)?locCurrent.culture:(cultures[0]||"");
  }
  function localizationRows(){
    const base=localizationCatalog.filter(row=>row.path!==locCurrent?.path);
    const live=locCurrent?(locCurrent.entries||[]).map((entry,index)=>({...entry,path:locCurrent.path,culture:locCurrent.culture,prefix:locCurrent.prefix,index})):[];
    return [...base,...live];
  }
  async function editLocalizationCell(row,value){
    if(locCurrent?.path!==row.path)await loadLocalizationFile(row.path,row.key);
    const entry=locCurrent?.entries?.find(item=>item.key===row.key);
    if(!entry?.editable)return;
    entry.value=String(value);locSelectedKey=row.key;render();shell?.refresh?.();
  }
  let locSelectedKey="";
  function addLocalizationEntry(){
    if(!locCurrent?.editable)return;
    const suffix=locNewKey.trim();if(!suffix){error="Enter a localization key.";render();return}
    const key=locCurrent.prefix?`${locCurrent.prefix}.${suffix}`:suffix;
    if(locDeletedKeys.has(key)){error="Save or discard the staged deletion before recreating that key.";render();return}
    if(locCurrent.entries.some(entry=>entry.key===key)){error=`Localization key already exists: ${key}`;render();return}
    locCurrent.entries.push({key,sourceKey:suffix,value:locNewValue,line:null,editable:true,kind:"new",isNew:true});locSelectedKey=key;locNewKey="";locNewValue="";error="";render();shell?.refresh?.();
  }
  async function deleteLocalizationRow(row){
    if(locCurrent?.path!==row.path)await loadLocalizationFile(row.path,row.key);
    const index=locCurrent?.entries?.findIndex(entry=>entry.key===row.key)??-1;if(index<0)return;
    const entry=locCurrent.entries[index];
    if(entry.isNew){locCurrent.entries.splice(index,1);render();shell?.refresh?.();return}
    if(!entry.editable)return;
    const approved=await confirmAction({title:"Delete localization key?",message:`Delete ${entry.key} from ${locCurrent.path}?`,confirmLabel:"Delete"});
    if(!approved)return;locDeletedKeys.add(entry.key);locCurrent.entries.splice(index,1);render();shell?.refresh?.();
  }
  function localizationDetail(row){
    if(!row)return emptyPanel("Localization","No localization entry is selected.");
    if(locLoading||locCurrent?.path!==row.path)return loadingPanel(`Loading ${row.key}…`);
    const entry=locCurrent.entries.find(item=>item.key===row.key);if(!entry)return emptyPanel("Localization","The selected entry is no longer present.");
    const control=entry.editable?el("input",{type:"text",value:entry.value,"aria-label":"Localization value",oninput:event=>{entry.value=event.target.value;shell?.refresh?.()}}):readonlyField(entry.value||`[${entry.kind}]`);
    const addKey=locCurrent.editable?detailSection({title:"ADD KEY",body:[
      detailField({label:"KEY",dataType:"STRING",control:el("input",{type:"text",value:locNewKey,"aria-label":"New localization key",placeholder:locCurrent.prefix?"Custom.Greeting":`Mods.${projectName()}.Custom.Greeting`,oninput:event=>{locNewKey=event.target.value}})}),
      detailField({label:"VALUE",dataType:"STRING",control:el("input",{type:"text",value:locNewValue,"aria-label":"New localization value",oninput:event=>{locNewValue=event.target.value}})}),
      detailField({label:"ACTION",control:el("button",{class:"lex-dialog-action primary",type:"button",onclick:addLocalizationEntry},"Add key")}),
    ]}):null;
    return detailPanel({title:entry.key,meta:`${locCurrent.culture||"Unknown culture"} · ${locCurrent.path}`,body:[
      detailSection({title:"TEXT",body:[detailField({label:"VALUE",dataType:"STRING",control,help:infoHelp("The player-facing localized string used by tModLoader for this effective key.")})]}),
      detailSection({title:"SOURCE",body:[
        detailField({label:"RESOURCE",control:readonlyField(locCurrent.path)}),
        detailField({label:"LINE",control:readonlyField(entry.isNew?"New key":String(entry.line??"Preserved"))}),
        detailField({label:"PREFIX",control:readonlyField(locCurrent.prefix||"None"),help:infoHelp("A prefix encoded in the localization filename is applied to effective tModLoader keys without changing unrelated HJSON structure.")}),
      ]}),
      entry.editable?detailSection({title:"ACTIONS",body:[detailField({label:"DELETE",control:el("button",{class:"lex-dialog-action",type:"button",onclick:()=>deleteLocalizationRow(row)},entry.isNew?"Remove new key":"Delete key")})]}):null,
      addKey,
    ].filter(Boolean)});
  }
  function localizationCulturePanel(){
    const query=locQuery.trim().toLocaleLowerCase();
    let rows=localizationRows().filter(row=>row.culture===locCulture&&(!query||`${row.key} ${row.value} ${row.path}`.toLocaleLowerCase().includes(query)));
    rows=sortedRows(rows,locSort,{key:row=>row.key,value:row=>row.value,path:row=>row.path});
    const selected=rows.some(row=>row.key===locSelectedKey&&row.path===locCurrent?.path)?locSelectedKey:(rows[0]?.key||"");
    return pagedListDetail({rows,key:row=>`${row.path}\u001f${row.key}`,slots:false,noun:"localization entries",page:locPage,pageSize:locPageSize,selected:rows.find(row=>row.key===selected&&row.path===locCurrent?.path)?`${locCurrent.path}\u001f${selected}`:(rows[0]?`${rows[0].path}\u001f${rows[0].key}`:null),
      splitKey:`terraria-localization-${locCulture}`,rowsKey:`terraria-localization-${locCulture}`,defaultSplit:48,minLeft:320,minRight:360,
      search:{key:`terraria-localization-${locCulture}`,value:locQuery,label:`Search ${locCulture} localization`,placeholder:"Search keys, values, or resource paths…",change:value=>{locQuery=value;locPage=0;render()}},
      sync:next=>{locPage=next.page;locPageSize=next.pageSize;if(next.selected){const [path,key]=String(next.selected).split("\u001f");locSelectedKey=key;if(path!==locCurrent?.path&&!locLoading)void loadLocalizationFile(path,key)}},
      change:next=>{locPage=next.page;locPageSize=next.pageSize;if(next.selected){const [path,key]=String(next.selected).split("\u001f");locSelectedKey=key;if(path!==locCurrent?.path)void loadLocalizationFile(path,key);else render()}else render()},
      master:({rows,selected,select})=>columnList({rows,key:row=>`${row.path}\u001f${row.key}`,selected,select,sortState:locSort,sort:key=>{locSort=nextSort(locSort,key);render()},refresh:()=>{render();shell?.refresh?.()},
        template:"minmax(180px,1.25fr) minmax(170px,1.1fr) minmax(160px,1fr)",
        columns:[{key:"key",label:"Key",sortable:true,align:"start"},{key:"value",label:"Value",sortable:true,align:"start",edit:(row,value)=>void editLocalizationCell(row,value),editValue:row=>row.value},{key:"path",label:"Resource",sortable:true,align:"start"}],"aria-label":`${locCulture} localization entries`}),
      detail:localizationDetail,emptyDetail:()=>emptyPanel("Localization","No localization entries match this language/search."),
    });
  }
  function localizationPanel(){
    if(noModSource())return missingModPanel();
    const cultures=[...new Set(localizationRows().map(row=>row.culture).filter(Boolean))].sort();
    if(!cultures.length)return stack({fill:false},...warnings(),emptyPanel("Localization","No loadable .hjson localization files are present in this source project yet."));
    if(!cultures.includes(locCulture))locCulture=cultures[0];
    const tabs=cultures.map(culture=>({id:culture,label:`${cultureFlag(culture)} ${culture}`}));
    return stack({},...warnings(),tabbedPanel({tabs,active:locCulture,label:"Localization languages",change:value=>{locCulture=value;locQuery="";locPage=0;const row=localizationRows().find(item=>item.culture===value);if(row&&row.path!==locCurrent?.path)void loadLocalizationFile(row.path,row.key);else render()},content:localizationCulturePanel()}));
  }

  async function renameSourceFileAction(){
    if(sourceLoading||dirtyCount()||!sourceCurrent)return;const newPath=sourceRenamePath.trim();if(!newPath){error="Enter the new project-relative .cs path.";render();return}
    sourceLoading=true;error="";render();try{const renamed=await request("/api/source/rename",{method:"POST",body:JSON.stringify({path:sourceCurrent.path,newPath,expectedSha256:sourceCurrent.sha256})});sourceSaved=clone(renamed);sourceCurrent=clone(renamed);sourceRenamePath="";const [source,map]=await Promise.all([request("/api/source"),request("/api/data-map")]);sourceFiles=source.files;mapRows=map.rows;sourceQuery=""}catch(exc){error=String(exc.message||exc)}sourceLoading=false;render();
  }
  async function renameSourceRow(row,newPath){if(row.path===newPath)return;if(sourceCurrent?.path!==row.path)await loadSourceFile(row.path);sourceRenamePath=String(newPath);await renameSourceFileAction()}
  async function deleteSourceFileAction(){
    if(sourceLoading||dirtyCount()||!sourceCurrent)return;const approved=await confirmAction({title:"Delete C# source?",message:`Delete ${sourceCurrent.path}? This removes only the selected mod source file.`,confirmLabel:"Delete"});if(!approved)return;
    sourceLoading=true;error="";render();try{await request("/api/source/delete",{method:"POST",body:JSON.stringify({path:sourceCurrent.path,expectedSha256:sourceCurrent.sha256})});const [source,map]=await Promise.all([request("/api/source"),request("/api/data-map")]);sourceFiles=source.files;mapRows=map.rows;sourceSaved=null;sourceCurrent=null;if(sourceFiles.length){const state=await request(`/api/source/file?path=${encodeURIComponent(sourceFiles[0].path)}`);sourceSaved=clone(state);sourceCurrent=clone(state)}}catch(exc){error=String(exc.message||exc)}sourceLoading=false;render();
  }
  async function createSourceFile(){
    if(sourceLoading||dirtyCount())return;const path=sourceNewPath.trim();if(!path){error="Enter a project-relative .cs path.";render();return}
    sourceLoading=true;error="";render();try{const created=await request("/api/source/create",{method:"POST",body:JSON.stringify({path,text:""})});sourceSaved=clone(created);sourceCurrent=clone(created);sourceNewPath="";sourceCreateMode=false;const [source,map]=await Promise.all([request("/api/source"),request("/api/data-map")]);sourceFiles=source.files;mapRows=map.rows}catch(exc){error=String(exc.message||exc)}sourceLoading=false;render();
  }
  function sourceCreateDetail(){return detailPanel({title:"New C# Source",meta:"Project-relative file",body:[detailSection({title:"CREATE",body:[
    detailField({label:"PATH",dataType:"STRING",control:el("input",{type:"text",value:sourceNewPath,"aria-label":"New C# path",placeholder:"Content/Items/MyItem.cs",disabled:sourceLoading||dirtyCount()>0,oninput:event=>{sourceNewPath=event.target.value}}),help:infoHelp("Creates a new UTF-8 C# file inside the selected mod source project. Existing paths are never overwritten.")}),
    detailField({label:"ACTION",control:el("button",{class:"lex-dialog-action primary",type:"button",disabled:sourceLoading||dirtyCount()>0,onclick:createSourceFile},"Create source")}),
  ]})]})}
  function sourceDetail(row){
    if(sourceCreateMode)return sourceCreateDetail();if(!row)return emptyPanel("Source","No C# source file is selected.");
    if(sourceLoading||sourceCurrent?.path!==row.path)return loadingPanel(`Loading ${row.path}…`);
    const editor=codeField({value:sourceCurrent.text,"aria-label":`C# source ${sourceCurrent.path}`,oninput:event=>{sourceCurrent.text=event.target.value;shell?.refresh?.()},onkeydown:event=>{if(event.key!=="Tab")return;event.preventDefault();const target=event.target,start=target.selectionStart,end=target.selectionEnd;target.setRangeText("\t",start,end,"end");sourceCurrent.text=target.value;shell?.refresh?.()}});
    if(sourceGotoLine){const line=sourceGotoLine;sourceGotoLine=0;setTimeout(()=>{const rows=editor.value.split("\n");let start=0;for(let i=1;i<line&&i<=rows.length;i++)start+=rows[i-1].length+1;const end=start+(rows[Math.min(line-1,rows.length-1)]||"").length;editor.focus();editor.setSelectionRange(start,end);editor.scrollTop=Math.max(0,(line-5)*20)},0)}
    const rename=el("input",{type:"text",value:sourceRenamePath||sourceCurrent.path,"aria-label":"Rename C# source path",disabled:sourceLoading||dirtyCount()>0,oninput:event=>{sourceRenamePath=event.target.value}});
    return detailPanel({title:basename(row.path),meta:row.path,body:[
      detailSection({title:"FILE",body:[
        detailField({label:"PATH",control:rename,dataType:"STRING"}),
        detailField({label:"LINES",control:readonlyField(String(sourceCurrent.lines))}),
        detailField({label:"SIZE",control:readonlyField(`${sourceCurrent.bytes} bytes`)}),
      ]}),
      detailField({label:"C# SOURCE",className:"lex-text-editor lex-detail-field-stacked",control:editor,help:infoHelp("Raw author-controlled C#. tModLoader compiler diagnostics remain authoritative; Lexeditor preserves BOM/newline style and refuses stale writes.")}),
      detailSection({title:"ACTIONS",body:[
        detailField({label:"RENAME / MOVE",control:el("button",{class:"lex-dialog-action",type:"button",disabled:sourceLoading||dirtyCount()>0,onclick:renameSourceFileAction},"Rename / move")}),
        detailField({label:"DELETE SOURCE",control:el("button",{class:"lex-dialog-action",type:"button",disabled:sourceLoading||dirtyCount()>0,onclick:deleteSourceFileAction},"Delete source")}),
      ]}),
    ]});
  }
  function sourcePanel(){
    if(noModSource())return missingModPanel();
    const query=sourceQuery.trim().toLocaleLowerCase();let rows=sourceFiles.filter(row=>!row.error&&(!query||row.path.toLocaleLowerCase().includes(query)));rows=sortedRows(rows,sourceSort,{path:row=>row.path,lines:row=>row.lines,bytes:row=>row.bytes});
    return stack({},...warnings(),pagedListDetail({rows,key:row=>row.path,slots:false,noun:"source files",page:sourcePage,pageSize:sourcePageSize,selected:sourceCreateMode?"__new__":sourceCurrent?.path||rows[0]?.path||null,
      splitKey:"terraria-source",rowsKey:"terraria-source",defaultSplit:44,minLeft:300,minRight:380,add:()=>{sourceCreateMode=true;render()},addTitle:"Add C# source file",addDisabled:sourceLoading||dirtyCount()>0,
      search:{key:"terraria-source",value:sourceQuery,label:"Search Terraria source files",placeholder:"Search project-relative C# paths…",change:value=>{sourceQuery=value;sourcePage=0;sourceCreateMode=false;render()}},
      sync:next=>{sourcePage=next.page;sourcePageSize=next.pageSize;if(next.selected&&next.selected!=="__new__"&&next.selected!==sourceCurrent?.path&&!sourceLoading){sourceCreateMode=false;void loadSourceFile(next.selected)}},
      change:next=>{sourcePage=next.page;sourcePageSize=next.pageSize;if(next.selected&&next.selected!=="__new__"&&next.selected!==sourceCurrent?.path){sourceCreateMode=false;void loadSourceFile(next.selected)}else render()},
      master:({rows,selected,select})=>columnList({rows,key:row=>row.path,selected,select,sortState:sourceSort,sort:key=>{sourceSort=nextSort(sourceSort,key);render()},refresh:()=>render(),
        template:"minmax(230px,1fr) 72px 84px",columns:[
        {key:"path",label:"Path",sortable:true,align:"start",edit:(row,value)=>void renameSourceRow(row,String(value)),editValue:row=>row.path},
        {key:"lines",label:"Lines",sortable:true,numeric:true},{key:"bytes",label:"Bytes",sortable:true,numeric:true},
      ],"aria-label":"Terraria C# source files"}),
      detail:sourceDetail,emptyDetail:()=>sourceCreateMode?sourceCreateDetail():emptyPanel("Source","No C# source files match the current search."),
    }));
  }

  function fileBase64(file){
    return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error("Could not read selected asset."));reader.onload=()=>{const value=String(reader.result||"");const comma=value.indexOf(",");if(comma<0)reject(new Error("Could not encode selected asset."));else resolve(value.slice(comma+1))};reader.readAsDataURL(file)});
  }
  async function refreshAssets(path=""){
    const [assets,map]=await Promise.all([request("/api/assets"),request("/api/data-map")]);assetFiles=assets.files;mapRows=map.rows;
    const selected=path||assetCurrent?.path||assetFiles.find(file=>!file.error&&file.editable)?.path;
    if(selected&&assetFiles.some(row=>row.path===selected)){assetCurrent=await request(`/api/assets/file?path=${encodeURIComponent(selected)}`)}else assetCurrent=null;
  }
  async function loadAsset(path){if(!path)return;assetLoading=true;error="";render();try{assetCurrent=await request(`/api/assets/file?path=${encodeURIComponent(path)}`);assetReplaceFile=null;assetRenamePath=""}catch(exc){assetCurrent=null;error=String(exc.message||exc)}assetLoading=false;render()}
  async function importAsset(){
    if(assetLoading||dirtyCount())return;const path=assetNewPath.trim(),file=assetImportFile;if(!path||!file){error="Choose an asset file and enter its project-relative destination path.";render();return}if(file.size>16*1024*1024){error="Asset exceeds Lexeditor 16 MiB asset limit.";render();return}
    assetLoading=true;error="";render();try{const dataBase64=await fileBase64(file);const created=await request("/api/assets/create",{method:"POST",body:JSON.stringify({path,dataBase64})});assetNewPath="";assetImportFile=null;assetImportMode=false;await refreshAssets(created.path)}catch(exc){error=String(exc.message||exc)}assetLoading=false;render();
  }
  async function replaceAsset(){if(assetLoading||dirtyCount()||!assetCurrent||!assetReplaceFile)return;const file=assetReplaceFile;if(file.size>16*1024*1024){error="Asset exceeds Lexeditor 16 MiB asset limit.";render();return}assetLoading=true;error="";render();try{const dataBase64=await fileBase64(file);const replaced=await request("/api/assets/file",{method:"POST",body:JSON.stringify({path:assetCurrent.path,dataBase64,expectedSha256:assetCurrent.sha256})});assetReplaceFile=null;await refreshAssets(replaced.path)}catch(exc){error=String(exc.message||exc)}assetLoading=false;render()}
  async function renameAssetAction(){if(assetLoading||dirtyCount()||!assetCurrent)return;const newPath=assetRenamePath.trim();if(!newPath){error="Enter the new project-relative asset path.";render();return}assetLoading=true;error="";render();try{const renamed=await request("/api/assets/rename",{method:"POST",body:JSON.stringify({path:assetCurrent.path,newPath,expectedSha256:assetCurrent.sha256})});assetRenamePath="";await refreshAssets(renamed.path)}catch(exc){error=String(exc.message||exc)}assetLoading=false;render()}
  async function renameAssetRow(row,newPath){if(row.path===newPath)return;if(assetCurrent?.path!==row.path)await loadAsset(row.path);assetRenamePath=String(newPath);await renameAssetAction()}
  async function deleteAssetAction(){if(assetLoading||dirtyCount()||!assetCurrent)return;const approved=await confirmAction({title:"Delete asset?",message:`Delete ${assetCurrent.path} from this mod source project?`,confirmLabel:"Delete"});if(!approved)return;assetLoading=true;error="";render();try{await request("/api/assets/delete",{method:"POST",body:JSON.stringify({path:assetCurrent.path,expectedSha256:assetCurrent.sha256})});await refreshAssets()}catch(exc){error=String(exc.message||exc)}assetLoading=false;render()}
  function assetPreview(){if(!assetCurrent)return null;const src=`/api/assets/raw?path=${encodeURIComponent(assetCurrent.path)}&sha=${encodeURIComponent(assetCurrent.sha256)}`;if(assetCurrent.preview==="image")return el("img",{src,alt:assetCurrent.path});if(assetCurrent.preview==="audio")return el("audio",{src,controls:true});return detailNote("No browser preview is available for this asset format.")}
  function assetImportDetail(){const locked=assetLoading||dirtyCount()>0;return detailPanel({title:"Import Asset",meta:"Known tModLoader package resource",body:[detailSection({title:"IMPORT",body:[
    detailField({label:"PATH",dataType:"STRING",control:el("input",{type:"text",value:assetNewPath,"aria-label":"Asset destination path",placeholder:"Content/Items/Sword.png",disabled:locked,oninput:event=>{assetNewPath=event.target.value}})}),
    detailField({label:"FILE",control:el("input",{type:"file",accept:".png,.xnb,.rawimg,.fxc,.wav,.mp3,.ogg",disabled:locked,"aria-label":"Asset file",onchange:event=>{assetImportFile=event.target.files?.[0]||null}})}),
    detailField({label:"ACTION",control:el("button",{class:"lex-dialog-action primary",type:"button",disabled:locked,onclick:importAsset},"Import asset"),help:infoHelp("Import is exclusive-create, limited to 16 MiB, and never overwrites an existing project resource.")}),
  ]})]})}
  function assetDetail(row){
    if(assetImportMode)return assetImportDetail();if(!row)return emptyPanel("Assets","No asset is selected.");if(assetLoading||assetCurrent?.path!==row.path)return loadingPanel(`Loading ${row.path}…`);
    const locked=assetLoading||dirtyCount()>0,dimensions=assetCurrent.width&&assetCurrent.height?`${assetCurrent.width} × ${assetCurrent.height}`:"Not decoded";
    const rename=el("input",{type:"text",value:assetRenamePath||assetCurrent.path,"aria-label":"Rename asset path",disabled:locked,oninput:event=>{assetRenamePath=event.target.value}});
    return detailPanel({title:basename(row.path),meta:row.path,body:[
      detailSection({title:"PREVIEW",body:[detailField({label:"PREVIEW",control:assetPreview()})]}),
      detailSection({title:"FILE",body:[
        detailField({label:"PATH",dataType:"STRING",control:rename}),detailField({label:"FORMAT",control:readonlyField(assetCurrent.kind||assetCurrent.extension)}),detailField({label:"SIZE",control:readonlyField(`${assetCurrent.bytes} bytes`)}),detailField({label:"DIMENSIONS",control:readonlyField(dimensions)}),
      ]}),
      detailSection({title:"REPLACE",body:[
        detailField({label:"FILE",control:el("input",{type:"file",accept:assetCurrent.extension,disabled:locked,"aria-label":"Replacement asset",onchange:event=>{assetReplaceFile=event.target.files?.[0]||null}})}),
        detailField({label:"ACTION",control:el("button",{class:"lex-dialog-action",type:"button",disabled:locked||!assetReplaceFile,onclick:replaceAsset},"Replace asset"),help:infoHelp("Replacement is SHA-guarded and preserves the selected path; tModLoader remains authoritative for runtime validity.")}),
      ]}),
      detailSection({title:"ACTIONS",body:[
        detailField({label:"RENAME / MOVE",control:el("button",{class:"lex-dialog-action",type:"button",disabled:locked,onclick:renameAssetAction},"Rename / move")}),
        detailField({label:"DELETE ASSET",control:el("button",{class:"lex-dialog-action",type:"button",disabled:locked,onclick:deleteAssetAction},"Delete asset")}),
      ]}),
    ]});
  }
  function assetsPanel(){
    if(noModSource())return missingModPanel();
    const query=assetQuery.trim().toLocaleLowerCase();let rows=assetFiles.filter(row=>!row.error&&(!query||`${row.path} ${row.kind}`.toLocaleLowerCase().includes(query)));rows=sortedRows(rows,assetSort,{path:row=>row.path,kind:row=>row.kind,bytes:row=>row.bytes});
    return stack({},...warnings(),pagedListDetail({rows,key:row=>row.path,slots:false,noun:"assets",page:assetPage,pageSize:assetPageSize,selected:assetImportMode?"__new__":assetCurrent?.path||rows[0]?.path||null,
      splitKey:"terraria-assets",rowsKey:"terraria-assets",defaultSplit:46,minLeft:300,minRight:360,add:()=>{assetImportMode=true;render()},addTitle:"Import Terraria asset",addDisabled:assetLoading||dirtyCount()>0,
      search:{key:"terraria-assets",value:assetQuery,label:"Search Terraria assets",placeholder:"Search asset paths or formats…",change:value=>{assetQuery=value;assetPage=0;assetImportMode=false;render()}},
      sync:next=>{assetPage=next.page;assetPageSize=next.pageSize;if(next.selected&&next.selected!=="__new__"&&next.selected!==assetCurrent?.path&&!assetLoading){assetImportMode=false;void loadAsset(next.selected)}},
      change:next=>{assetPage=next.page;assetPageSize=next.pageSize;if(next.selected&&next.selected!=="__new__"&&next.selected!==assetCurrent?.path){assetImportMode=false;void loadAsset(next.selected)}else render()},
      master:({rows,selected,select})=>columnList({rows,key:row=>row.path,selected,select,sortState:assetSort,sort:key=>{assetSort=nextSort(assetSort,key);render()},refresh:()=>render(),
        template:"minmax(220px,1fr) 100px 84px",columns:[
        {key:"path",label:"Path",sortable:true,align:"start",edit:(row,value)=>void renameAssetRow(row,String(value)),editValue:row=>row.path},
        {key:"kind",label:"Format",sortable:true,align:"start"},{key:"bytes",label:"Bytes",sortable:true,numeric:true},
      ],"aria-label":"Terraria assets"}),
      detail:assetDetail,emptyDetail:()=>assetImportMode?assetImportDetail():emptyPanel("Assets","No assets match the current search."),
    }));
  }

  function mappedDataRows(){
    // The Data Map answers "what data can I edit". With no mod source the
    // honest answer is the reason, not an empty table.
    if(!mapRows.length&&error)return [{filename:"No mod source yet",controls:"Nothing to map",notes:error,coverage:"unavailable",status:"not-integrated"}];
    const managed=new Set(contentFiles.map(row=>row.path));
    return mapRows.map(row=>{
      const filename=row.path,lower=filename.toLocaleLowerCase();
      if(filename==="build.txt")return {filename,controls:"Mod Metadata and Dependencies & Build",notes:"Common build.txt fields are structured; unknown/future properties and localized display-name variants are preserved but not modeled.",coverage:"structured",status:"partial",targets:[{id:"metadata",label:"Mod Metadata"},{id:"dependencies",label:"Dependencies & Build"}]};
      if(lower.endsWith(".cs"))return {filename,controls:managed.has(filename)?"Managed Content plus raw Source":"Raw C# Source",notes:managed.has(filename)?"The Lexeditor-managed region is structured; author C# outside it remains raw Source.":"Lexeditor can safely edit the UTF-8 C# file but does not infer arbitrary C# semantics.",coverage:managed.has(filename)?"structured":"source",status:"partial",targets:managed.has(filename)?[{id:"content",label:"Content"}]:[],sourceOpenable:true,openable:true};
      if(lower.endsWith(".hjson"))return {filename,controls:"Localization",notes:"Single-line string leaves are editable across the language table; complex HJSON values are preservation-only.",coverage:"structured",status:"partial",target:"localization"};
      if([".png",".xnb",".rawimg",".fxc",".wav",".mp3",".ogg"].some(ext=>lower.endsWith(ext)))return {filename,controls:"Assets",notes:"Known assets can be previewed where supported and replaced/renamed safely; Lexeditor does not semantically edit image/audio/compiled asset payloads.",coverage:"view",status:"partial",target:"assets"};
      if(lower.endsWith(".csproj"))return {filename,controls:"tModLoader project file",notes:"Required by the native project but not edited by a dedicated Lexeditor view.",coverage:"unavailable",status:"not-integrated"};
      return {filename,controls:row.family||"Project resource",notes:"Lexeditor preserves this project resource but has no dedicated viewer/editor for it.",coverage:"unavailable",status:"not-integrated"};
    });
  }
  function openDataMapRow(row){const target=row.target||row.view;if(target)navigate(target)}
  function openDataMapSource(row){sourceQuery=basename(row.filename);sourcePage=0;sourceCreateMode=false;navigate("source");const match=sourceFiles.find(item=>item.path===row.filename);if(match)void loadSourceFile(match.path)}
  function dataMapPanel(){
    const view=LexeditorUI.dataMap({rows:mappedDataRows(),page:mapPage,query:mapQuery,status:mapStatus,sort:mapSort,
      changePage:value=>{mapPage=value;render()},changeQuery:value=>{mapQuery=value;mapPage=0;render()},changeStatus:value=>{mapStatus=value;mapPage=0;render()},changeSort:key=>{mapSort=[key,mapSort[0]===key?-mapSort[1]:1];render()},
      open:openDataMapRow,openSource:openDataMapSource});
    return view.content;
  }
  function render(){
    let content;
    if(tab==="datamap")content=dataMapPanel();else if(tab==="info")content=panelLayout([informationPanel()],{layoutKey:"terraria-info",defaultSizes:[100]});else if(tab==="assets")content=assetsPanel();else if(tab==="source")content=sourcePanel();else if(tab==="localization")content=localizationPanel();else if(tab==="content")content=contentPanel();else if(tab==="dependencies")content=dependenciesPanel();else content=metadataPanel();
    document.querySelector("#main").replaceChildren(content);shell?.refresh?.();
  }

  async function loadLocalizationFile(path,key=""){
    if(!path||localizationDirtyEntries().length)return;locLoading=true;error="";render();
    try{const state=await request(`/api/localization/file?path=${encodeURIComponent(path)}`);locSaved=clone(state);locCurrent=clone(state);locCulture=state.culture||locCulture;locSelectedKey=key||state.entries?.[0]?.key||"";locNewKey="";locNewValue="";locDeletedKeys.clear()}catch(exc){locSaved=null;locCurrent=null;error=String(exc.message||exc)}
    locLoading=false;render();
  }

  async function loadSourceFile(path){
    if(!path||sourceDirty())return;sourceLoading=true;error="";render();
    try{const state=await request(`/api/source/file?path=${encodeURIComponent(path)}`);sourceSaved=clone(state);sourceCurrent=clone(state);sourceRenamePath=""}catch(exc){sourceSaved=null;sourceCurrent=null;error=String(exc.message||exc)}
    sourceLoading=false;render();
  }

  async function load(){
    try{
      const [metadata,map,build,localization,source,assets,structured]=await Promise.all([request("/api/build-metadata"),request("/api/data-map"),request("/api/build"),request("/api/localization"),request("/api/source"),request("/api/assets"),request("/api/content")]);
      saved=clone(metadata);current=clone(metadata);mapRows=map.rows;buildInfo=build;localizationFiles=localization.files;sourceFiles=source.files;assetFiles=assets.files;contentSchemas=structured.schemas||[];contentFiles=structured.files||[];if(!contentSchema(contentKind)&&contentSchemas.length)contentKind=contentSchemas[0].kind;resetContentCreateValues();error="";
      const firstLoc=localizationFiles.find(file=>!file.error&&file.loadable)?.path||localizationFiles.find(file=>!file.error)?.path;
      const firstSource=sourceFiles.find(file=>!file.error&&file.editable)?.path;
      const firstAsset=assetFiles.find(file=>!file.error&&file.editable)?.path;
      const firstStructured=contentFiles[0]?.path;
      const loads=[];
      if(firstLoc)loads.push(request(`/api/localization/file?path=${encodeURIComponent(firstLoc)}`).then(state=>{locSaved=clone(state);locCurrent=clone(state);locCulture=state.culture||"";locSelectedKey=state.entries?.[0]?.key||""}));
      if(firstSource)loads.push(request(`/api/source/file?path=${encodeURIComponent(firstSource)}`).then(state=>{sourceSaved=clone(state);sourceCurrent=clone(state)}));
      if(firstAsset)loads.push(request(`/api/assets/file?path=${encodeURIComponent(firstAsset)}`).then(state=>{assetCurrent=state}));
      if(firstStructured)loads.push(request(`/api/content/file?path=${encodeURIComponent(firstStructured)}`).then(state=>{structuredSaved=clone(state);structuredCurrent=clone(state)}));
      await Promise.all(loads);await refreshLocalizationCatalog();
    }catch(exc){error=String(exc.message||exc)}
    render();
  }

  async function save(){
    if(!dirtyCount())return;error="";
    try{
      if(structuredDirty()&&sourceDirty()&&structuredCurrent?.path===sourceCurrent?.path)throw new Error("This managed C# file has unsaved edits in both Content and Source. Discard one editing mode before saving.");
      if(saved&&current&&dirtyKeys().length){
        const updates={};for(const key of dirtyKeys()){const value=current.values[key];if(value===""&&!(key in saved.values))continue;if(Array.isArray(value)&&!value.length&&!(key in saved.values))continue;updates[key]=value}
        if(Object.keys(updates).length){const result=await request("/api/build-metadata",{method:"POST",body:JSON.stringify({updates,expectedSha256:saved.sha256})});saved=clone(result);current=clone(result)}else saved=clone(current);
      }
      const changedLocalization=localizationUpdatedEntries(),createdLocalization=localizationCreatedEntries(),deletedLocalization=localizationDeletedEntries();
      if(locSaved&&locCurrent&&(changedLocalization.length||createdLocalization.length||deletedLocalization.length)){
        const updates={},creates={};for(const entry of changedLocalization)updates[entry.key]=entry.value;for(const entry of createdLocalization)creates[entry.key]=entry.value;
        const result=await request("/api/localization/file",{method:"POST",body:JSON.stringify({path:locCurrent.path,updates,creates,deletes:deletedLocalization,expectedSha256:locSaved.sha256})});locSaved=clone(result);locCurrent=clone(result);locDeletedKeys.clear();locNewKey="";locNewValue="";localizationFiles=(await request("/api/localization")).files;await refreshLocalizationCatalog();
      }
      if(structuredSaved&&structuredCurrent&&structuredDirty()){
        const result=await request("/api/content/file",{method:"POST",body:JSON.stringify({path:structuredCurrent.path,values:structuredCurrent.values,expectedSha256:structuredSaved.sha256})});structuredSaved=clone(result);structuredCurrent=clone(result);contentFiles=(await request("/api/content")).files;sourceFiles=(await request("/api/source")).files;if(sourceCurrent?.path===result.path&&!sourceDirty()){const state=await request(`/api/source/file?path=${encodeURIComponent(result.path)}`);sourceSaved=clone(state);sourceCurrent=clone(state)}
      }
      if(sourceSaved&&sourceCurrent&&sourceDirty()){
        const result=await request("/api/source/file",{method:"POST",body:JSON.stringify({path:sourceCurrent.path,text:sourceCurrent.text,expectedSha256:sourceSaved.sha256})});sourceSaved=clone(result);sourceCurrent=clone(result);sourceFiles=(await request("/api/source")).files;if(structuredCurrent?.path===result.path){try{const state=await request(`/api/content/file?path=${encodeURIComponent(result.path)}`);structuredSaved=clone(state);structuredCurrent=clone(state)}catch(_ignored){structuredSaved=null;structuredCurrent=null;contentFiles=(await request("/api/content")).files}}
      }
    }catch(exc){error=String(exc.message||exc)}
    render();
  }

  async function buildMod(){
    if(building||dirtyCount()||!buildInfo?.available)return;building=true;buildResult=null;error="";render();
    try{buildResult=await request("/api/build",{method:"POST",body:"{}"});buildInfo=await request("/api/build")}catch(exc){error=String(exc.message||exc);try{buildInfo=await request("/api/build")}catch(_ignored){}}finally{building=false;render()}
  }
  async function discard(){current=clone(saved);locCurrent=clone(locSaved);sourceCurrent=clone(sourceSaved);structuredCurrent=clone(structuredSaved);locDeletedKeys.clear();locNewKey="";locNewValue="";sourceNewPath="";sourceRenamePath="";assetRenamePath="";sourceCreateMode=false;assetImportMode=false;error="";await refreshLocalizationCatalog();render()}
  function navigate(value){if(value===tab)return;tab=value;showNavigationLoading(value==="datamap"?"Data Map":value==="info"?"Info":value);requestAnimationFrame(render)}
  const shell=LexeditorUI.mountShell({
    host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"terraria",name:"Terraria",themeName:"terraria",theme:{accent:"#77b255"}},
    tabs:[{id:"metadata",label:"Mod Metadata"},{id:"dependencies",label:"Dependencies & Build"},{id:"content",label:"Content"},{id:"localization",label:"Localization"},{id:"source",label:"Source"},{id:"assets",label:"Assets"}],activeTab:()=>tab,navigate,
    help:()=>navigate("datamap"),helpActive:()=>tab==="datamap",helpTitle:"Open Terraria Data Map",
    info:()=>navigate("info"),infoActive:()=>tab==="info",infoTitle:"Open Terraria setup and runtime information",
    dirtyCount,readonly:()=>!current?.editable&&!locCurrent?.editable&&!sourceCurrent?.editable&&!structuredCurrent?.editable,save,discard,
  });
  load().finally(()=>LexeditorUI.finishPluginLoading());
