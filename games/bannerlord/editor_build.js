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

  async function selectBuildProject(name){
    if(!name)return;
    try{
      const project=await api(`/api/project?project=${encodeURIComponent(name)}`);
      state.project=project;state.savedProject=clone(project);renderBuild();refresh();
    }catch(error){showAlert?.(String(error.message||error),"Bannerlord project selection failed")}
  }

  function renderBuild(){
    const project=state.project?.projectFile;
    if(!project){
      const files=state.project?.projectFiles||[];
      if(files.length>1){
        main.replaceChildren(BLUI.detailPanel({
          title:"Build",meta:"Choose project",
          body:[BLUI.detailSection({title:"PROJECT",body:[
            selectField("Project file","",[["","Choose .csproj"],...files.map(name=>[name,name])],value=>selectBuildProject(value),"Lexeditor will not guess which top-level project to build when several exist.")
          ]})]
        }));return;
      }
      main.replaceChildren(uiEmpty("Build","No .csproj exists in this project."));return;
    }
    const editable=project.editableProperties||[],props=project.properties||{};
    const blocked=state.building||dirtyCount()>0;
    const properties=BLUI.detailPanel({
      title:project.name,meta:`${project.sdk||"classic MSBuild"} · ${project.references.length} references · ${project.packages.length} packages`,
      body:[
        BLUI.detailSection({title:"EDITABLE PROJECT PROPERTIES",body:editable.map(name=>BLUI.detailField({
          label:name,control:projectControl(name,props[name]??""),
          help:BLUI.infoHelp(["BannerlordDir","GameBin","ModuleDir","OutputPath"].includes(name)?
            "Lexeditor-hosted builds pin this path to the selected Bannerlord installation or module even if the project file contains another value.":
            "Lexeditor edits only a unique unconditional MSBuild property. Conditional or duplicate definitions stay read-only.")
        }))}),
        Object.keys(project.ambiguousProperties||{}).length?BLUI.detailSection({
          title:"READ-ONLY AMBIGUOUS PROPERTIES",
          body:Object.entries(project.ambiguousProperties).map(([name,reason])=>readField(name,reason))
        }):null
      ].filter(Boolean)
    });
    const refs=project.references.map(row=>`${row.include}${row.metadata?.HintPath?` — ${row.metadata.HintPath}`:""}`);
    const packages=project.packages.map(row=>`${row.include}${row.metadata?.Version?` ${row.metadata.Version}`:""}`);
    const targets=project.targets.map(row=>`${row.name||"(unnamed target)"}${row.afterTargets?` after ${row.afterTargets}`:""}${row.beforeTargets?` before ${row.beforeTargets}`:""}`);
    const inventory=BLUI.detailPanel({
      title:"Build & Deploy",meta:state.buildResult?(state.buildResult.succeeded?"Last build passed":"Last build failed"):"No build run yet",
      actions:[
        select(state.buildConfiguration,[["Debug","Debug"],["Release","Release"]],value=>state.buildConfiguration=value),
        uiButton(state.building?"Working…":"Build",()=>runBuild(false),{disabled:blocked}),
        uiButton("Build + Deploy",()=>runBuild(true),{disabled:blocked}),
        uiButton("Sync assets",syncAssets,{disabled:blocked})
      ],
      body:[
        dirtyCount()>0?BLUI.detailSection({title:"SAVE REQUIRED",body:[
          readField("Pending changes",dirtyCount(),"Build and deployment operate on files on disk. Save Lexeditor edits first so the game receives the values currently shown.")
        ]}):null,
        BLUI.detailSection({title:"TOOLCHAIN",body:[
          readField("Compiler","dotnet build","Build requires a system .NET SDK available on PATH. Bannerlord uses its native module loader; dotnet is a development toolchain prerequisite, not a runtime loader or self-updating helper managed by Lexeditor."),
          readField("Trust boundary","Project-defined MSBuild targets run with your user permissions","Hosted path pinning protects Lexeditor's standard outputs but is not a sandbox. Build only projects you trust.")
        ]}),
        BLUI.detailSection({title:"REFERENCES",body:refs.length?refs.map((value,index)=>readField(`Reference ${index+1}`,value)):[readField("References","None")]}),
        BLUI.detailSection({title:"PACKAGES",body:packages.length?packages.map((value,index)=>readField(`Package ${index+1}`,value)):[readField("Packages","None")]}),
        BLUI.detailSection({title:"TARGETS",body:targets.length?targets.map((value,index)=>readField(`Target ${index+1}`,value)):[readField("Targets","None")]}),
        state.deployResult?BLUI.detailSection({title:"LAST ASSET SYNC",body:[
          readField("Target",state.deployResult.target||"—"),
          readField("Copied",(state.deployResult.copied||[]).length),
          readField("Unchanged",(state.deployResult.unchanged||[]).length),
          readField("Backups",(state.deployResult.backups||[]).length)
        ]}):null,
        BLUI.detailSection({title:"OUTPUT",body:[
          BLUI.detailField({label:"Build log",control:el("pre",{class:"bannerlord-build-log"},state.buildResult?.output||"Build output appears here.")})
        ]})
      ].filter(Boolean)
    });
    main.replaceChildren(BLUI.panelLayout([properties,inventory],"bannerlord-build-layout",{
      layoutKey:"bannerlord-build",stackAt:1000,defaultSizes:[44,56]
    }));
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
