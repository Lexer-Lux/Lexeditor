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
          BLUI.detailField({label:"Build log",control:BLUI.logView(state.buildResult?.output||"Build output appears here.")})
        ]})
      ].filter(Boolean)
    });
    main.replaceChildren(BLUI.panelLayout([properties,inventory],{
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
    if(!state.source){main.replaceChildren(uiEmpty("Source","No source file selected."));return}
    const textarea=el("textarea",{value:state.source.text,spellcheck:"false","aria-label":`Source ${state.source.path}`,oninput:event=>{state.source.text=event.target.value;refresh()}});
    main.replaceChildren(BLUI.detailPanel({title:"Source only",identity:state.source.path,meta:`${state.source.encoding} · ${state.source.size} bytes`,body:[BLUI.detailSection({title:"SOURCE",body:[BLUI.detailField({label:"TEXT",className:"lex-text-editor lex-detail-field-stacked",control:textarea,help:BLUI.infoHelp("Raw file text. Structured edits to the same file must be saved or discarded first.")})]})]}));
  }

  function renderDataMap(){}
  function navigate(tab){state.tab=tab}
  function render(){}

