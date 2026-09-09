"use strict";
  state.deployResult=null;
  const booleanProjectProperties=new Set(["AppendTargetFrameworkToOutputPath","CopyLocalLockFileAssemblies"]);
  function projectControl(name,value){
    if(booleanProjectProperties.has(name))return checkbox(String(value).toLowerCase()==="true",checked=>state.project.projectFile.properties[name]=checked?"true":"false");
    if(name==="Nullable")return select(value||"disable",[["disable","disable"],["enable","enable"],["warnings","warnings"],["annotations","annotations"]],next=>state.project.projectFile.properties[name]=next);
    return textInput(value,next=>state.project.projectFile.properties[name]=next);
  }

  function requireSavedForBuild(){
    if(dirtyCount()===0)return true;
    showAlert?.("Save all Lexeditor changes before building or deploying so the game receives the same data currently shown in the editor.","Unsaved changes");
    return false;
  }

  function runBuild(deploy=false){
    if(state.building||!requireSavedForBuild())return;
    state.building=true;state.deployResult=null;
    state.buildResult={output:deploy?"Building, then synchronizing module assets…":"Building…",succeeded:false};renderBuild();
    const endpoint=deploy?"/api/build-deploy":"/api/build";
    post(endpoint,{project:state.project.projectFile?.name||null,configuration:state.buildConfiguration}).then(result=>{
      if(deploy){
        state.buildResult=result.build||{output:"Build result unavailable.",succeeded:false};
        state.deployResult=result.assets||null;
        if(result.deployment)state.deployment=result.deployment;
      }else{
        state.buildResult=result;
        return api("/api/deployment").then(value=>{state.deployment=value}).catch(()=>{});
      }
    }).catch(error=>{
      state.buildResult={output:String(error.message||error),succeeded:false};state.deployResult=null;
    }).finally(()=>{state.building=false;renderBuild();refresh()});
  }

  function syncAssets(){
    if(state.building||!requireSavedForBuild())return;
    state.building=true;state.deployResult=null;
    post("/api/deploy-assets",{}).then(result=>{
      state.deployResult=result.assets||null;
      if(result.deployment)state.deployment=result.deployment;
    }).catch(error=>{
      state.deployResult={error:String(error.message||error),copied:[],unchanged:[],backups:[]};
    }).finally(()=>{state.building=false;renderBuild();refresh()});
  }

  function deploySummary(){
    const d=state.deployResult;
    if(!d)return null;
    if(d.error)return el("div",{class:"bl-list-block"},el("h3",{},"Asset deployment"),el("div",{},d.error));
    const copied=d.copied||[],unchanged=d.unchanged||[],backups=d.backups||[];
    return el("div",{class:"bl-list-block"},
      el("h3",{},"Asset deployment"),
      el("div",{},`${copied.length} copied · ${unchanged.length} unchanged · ${backups.length} backup(s) · 0 deleted`),
      el("div",{class:"bl-note"},`Target: ${d.target||"—"}`),
      copied.length?el("ul",{},...copied.map(value=>el("li",{},value))):null,
      el("div",{class:"bl-note"},"Runtime balance JSON is intentionally excluded so build/deploy cannot overwrite values managed by the Runtime tab."));
  }

  function renderBuild(){
    const project=state.project?.projectFile;
    if(!project){main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Build"),el("div",{class:"bl-empty"},"No .csproj exists in this project.")));return}
    const editable=project.editableProperties||[];
    const props=project.properties||{};
    const left=el("section",{class:"bl-card"},el("h2",{},project.name),
      el("div",{class:"bl-grid"},...editable.flatMap(name=>fieldRow(name,projectControl(name,props[name]??"")))),
      el("div",{class:"bl-note"},`SDK: ${project.sdk||"(classic MSBuild)"} · ${project.references.length} assembly references · ${project.packages.length} packages`),
      Object.keys(project.ambiguousProperties||{}).length?el("div",{class:"bl-note"},`Read-only ambiguous MSBuild properties: ${Object.entries(project.ambiguousProperties).map(([name,reason])=>`${name} (${reason})`).join("; ")}. Lexeditor does not evaluate MSBuild conditions.`):null,
      el("div",{class:"bl-note"},"Lexeditor-hosted builds pin BannerlordDir, GameBin, ModuleDir, and OutputPath to the selected Bannerlord installation. Project-local values remain editable for external builds but cannot redirect Lexeditor Build / Build + deploy.")
    );
    const referenceLines=project.references.map(row=>`${row.include}${row.metadata?.HintPath?` — ${row.metadata.HintPath}`:""}`);
    const packageLines=project.packages.map(row=>`${row.include}${row.metadata?.Version?` ${row.metadata.Version}`:""}`);
    const targetLines=project.targets.map(row=>`${row.name||"(unnamed target)"}${row.afterTargets?` after ${row.afterTargets}`:""}${row.beforeTargets?` before ${row.beforeTargets}`:""}`);
    const blocked=state.building||dirtyCount()>0;
    const right=el("section",{class:"bl-card"},
      el("h2",{},"Build & project inventory"),
      el("div",{class:"bl-build-toolbar"},
        select(state.buildConfiguration,[["Debug","Debug"],["Release","Release"]],value=>state.buildConfiguration=value),
        el("button",{type:"button",class:"bl-build-button",disabled:blocked,onclick:()=>runBuild(false)},state.building?"Working…":"dotnet build"),
        el("button",{type:"button",class:"bl-build-button",disabled:blocked,onclick:()=>runBuild(true)},"Build + deploy"),
        el("button",{type:"button",class:"bl-build-button",disabled:blocked,onclick:syncAssets},"Sync assets"),
        state.buildResult?el("strong",{},state.buildResult.succeeded?"PASS":""):null
      ),
      dirtyCount()>0?el("div",{class:"bl-note"},"Save pending Lexeditor edits before build/deploy. These actions operate on files on disk, not unsaved controls."):null,
      el("div",{class:"bl-list-block"},el("h3",{},"References"),referenceLines.length?el("ul",{},...referenceLines.map(v=>el("li",{},v))):el("div",{class:"bl-note"},"No assembly references.")),
      el("div",{class:"bl-list-block"},el("h3",{},"Packages"),packageLines.length?el("ul",{},...packageLines.map(v=>el("li",{},v))):el("div",{class:"bl-note"},"No package references.")),
      el("div",{class:"bl-list-block"},el("h3",{},"Targets"),targetLines.length?el("ul",{},...targetLines.map(v=>el("li",{},v))):el("div",{class:"bl-note"},"No explicit MSBuild targets.")),
      deploySummary(),
      el("pre",{class:"bl-build-log"},state.buildResult?.output||"Build output will appear here. Lexeditor invokes dotnet directly without a shell. Asset deployment is additive and never deletes deployed files.")
    );
    main.replaceChildren(el("div",{class:"bl-build-layout"},left,right));
  }

  async function openSource(row){
    try{
      const source=await api(`/api/source?path=${encodeURIComponent(row.filename)}`);
      state.source=source;state.savedSourceText=source.text;state.tab="source";render();
    }catch(error){showAlert?.(String(error.message||error),"Bannerlord source error")}
  }
  function renderSource(){
    if(!state.source){main.replaceChildren(el("div",{class:"bl-empty"},"No source file selected."));return}
    const textarea=el("textarea",{value:state.source.text,spellcheck:"false",oninput:event=>{state.source.text=event.target.value;refresh()}});
    main.replaceChildren(el("section",{class:"bl-source"},
      el("div",{class:"bl-source-head"},el("strong",{},"Source only"),el("code",{},state.source.path),el("span",{},`${state.source.encoding} · ${state.source.size} bytes`)),
      textarea
    ));
  }

  function renderDataMap(){
    const view=LexeditorUI.dataMap({
      rows:state.datamap.rows,query:state.query,status:state.mapStatus,page:state.page,sort:state.sort,
      tableClass:"bannerlord-data-map",
      open:row=>{if(row.target==="module")navigate("module");else if(row.target==="build")navigate("build");else if(row.target==="skills")navigate("skills");else if(row.target==="effects")navigate("effects");else if(row.target==="perks")navigate("perks");else if(row.target==="xp")navigate("xp")},
      openSource,
      changeQuery:value=>{state.query=value;state.page=0;renderDataMap()},
      changeStatus:value=>{state.mapStatus=value;state.page=0;renderDataMap()},
      changePage:value=>{state.page=value;renderDataMap()},
      changeSort:key=>{const [active,direction]=state.sort;state.sort=[key,active===key?-direction:1];renderDataMap()}
    });
    main.replaceChildren(view.content);
  }

  function navigate(tab){state.tab=tab;render()}
  function render(){
    const views={module:renderModule,dependencies:renderDependencies,submodules:renderSubmodules,xmls:renderXmls,skills:renderSkills,effects:renderEffects,perks:renderPerks,xp:renderXpSources,build:renderBuild,deployment:renderDeployment,datamap:renderDataMap,source:renderSource};
    (views[state.tab]||renderModule)();refresh();
  }
