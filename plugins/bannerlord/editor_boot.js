"use strict";
  async function reloadStructuredSource(absolutePath){
    if(sameFilePath(absolutePath,state.module?.path)){
      const value=await api("/api/module");state.module=value;state.savedModule=clone(value);return;
    }
    if(sameFilePath(absolutePath,state.project?.projectFile?.path)){
      const selected=state.project?.projectFile?.name||"";
      const value=await api(`/api/project${selected?`?project=${encodeURIComponent(selected)}`:""}`);
      state.project=value;state.savedProject=clone(value);return;
    }
    if(sameFilePath(absolutePath,state.skills?.path)){const value=await api("/api/skills");state.skills=value;state.savedSkills=clone(value);return}
    if(sameFilePath(absolutePath,state.effects?.path)){const value=await api("/api/effects");state.effects=value;state.savedEffects=clone(value);return}
    if(sameFilePath(absolutePath,state.perks?.path)){const value=await api("/api/perks");state.perks=value;state.savedPerks=clone(value);return}
    if(sameFilePath(absolutePath,state.xpSources?.path)){const value=await api("/api/xp-sources");state.xpSources=value;state.savedXpSources=clone(value);return}
    if(sameFilePath(absolutePath,state.mcmDefaults?.path)){const value=await api("/api/settings-defaults");state.mcmDefaults=value;state.savedMcmDefaults=clone(value);return}
    if(sameFilePath(absolutePath,state.gauntlet?.path)){
      const value=await api(`/api/gauntlet?path=${encodeURIComponent(state.gauntlet.relativePath)}`);
      state.gauntlet=value;state.savedGauntlet=clone(value);return;
    }
    if(sameFilePath(absolutePath,state.moduleData?.path)){
      const value=prepareModuleData(await api(`/api/module-data?path=${encodeURIComponent(state.moduleData.relativePath)}`));
      state.moduleData=value;state.savedModuleData=clone(value);return;
    }
  }

  async function save(){
    try{
      const sourceConflict=structuredSourceConflict();
      if(sourceConflict){
        throw new Error(`The same ${sourceConflict} file has unsaved structured and raw-source edits. Save or discard one editing surface before saving the other.`);
      }
      if(moduleDirty()){
        const result=await post("/api/module/save",moduleSavePayload(state.module,state.savedModule));
        state.module=result.module;state.savedModule=clone(result.module);
      }
      if(projectDirty()){
        const current=state.project.projectFile.properties;
        const before=state.savedProject.projectFile.properties;
        const edits=Object.fromEntries((state.project.projectFile.editableProperties||[])
          .filter(name=>current[name]!==before[name]).map(name=>[name,current[name]]));
        if(Object.keys(edits).length){
          const result=await post("/api/project/save",{project:state.project.projectFile?.name||null,edits,sourceHash:state.savedProject.projectFile?.sourceHash||""});
          state.project.projectFile=result.project;
          state.savedProject=clone(state.project);
        }
      }
      if(skillsDirty()){
        const attributeFields=["name","abbreviation","description"];
        const skillFields=["name","description","howToLearn","attributeId"];
        const makeEdits=(current,before,fields)=>current.flatMap((row,index)=>{
          const old=before[index];if(!old)return[];
          const changed=Object.fromEntries(fields.filter(field=>row[field]!==old[field]).map(field=>[field,row[field]]));
          return Object.keys(changed).length?[{index:row.index,originalId:old.stringId,fields:changed}]:[];
        });
        const result=await post("/api/skills/save",{
          attributes:makeEdits(state.skills.attributes,state.savedSkills.attributes,attributeFields),
          skills:makeEdits(state.skills.skills,state.savedSkills.skills,skillFields),
          sourceHash:state.savedSkills.sourceHash||""
        });
        state.skills=result;state.savedSkills=clone(result);
      }
      if(effectsDirty()){
        const edits=(state.effects.effects||[]).flatMap((row,index)=>{
          const old=state.savedEffects.effects[index];if(!old)return[];
          const fields={};
          if(row.defaultLow!==old.defaultLow)fields.defaultLow=row.defaultLow;
          if(row.defaultHigh!==old.defaultHigh)fields.defaultHigh=row.defaultHigh;
          return Object.keys(fields).length?[{index:row.index,originalId:old.id,fields}]:[];
        });
        const result=await post("/api/effects/save",{edits,sourceHash:state.savedEffects.sourceHash||""});
        state.effects=result;state.savedEffects=clone(result);
      }
      if(perksDirty()){
        const edits=(state.perks.perks||[]).flatMap((row,index)=>{
          const old=state.savedPerks.perks[index];if(!old)return [];
          const fields={};
          if(row.level!==old.level)fields.level=row.level;
          if(row.description!==old.description)fields.description=row.description;
          return Object.keys(fields).length?[{index:row.index,originalId:old.id,fields}]:[];
        });
        const result=await post("/api/perks/save",{edits,sourceHash:state.savedPerks.sourceHash||""});
        state.perks=result;state.savedPerks=clone(result);
      }
      if(xpSourcesDirty()){
        const edits=(state.xpSources.sources||[]).flatMap((row,index)=>{
          const old=state.savedXpSources.sources[index];if(!old)return [];
          return row.defaultAmount!==old.defaultAmount?[{index:row.index,originalId:old.id,fields:{defaultAmount:row.defaultAmount}}]:[];
        });
        const result=await post("/api/xp-sources/save",{edits,sourceHash:state.savedXpSources.sourceHash||""});
        state.xpSources=result;state.savedXpSources=clone(result);
      }
      if(mcmDirty()){
        const edits=(state.mcmDefaults.settings||[]).flatMap((row,index)=>{
          const old=state.savedMcmDefaults.settings[index];if(!old)return [];
          return row.default!==old.default?[{property:row.property,value:row.default}]:[];
        });
        const result=await post("/api/settings-defaults/save",{edits,sourceHash:state.savedMcmDefaults.sourceHash||""});
        state.mcmDefaults=result;state.savedMcmDefaults=clone(result);
      }
      if(runtimeDirty()){
        const beforeEffects=Object.fromEntries((state.savedRuntimeOverrides.effects||[]).map(row=>[row.id,row]));
        const beforeXp=Object.fromEntries((state.savedRuntimeOverrides.xpSources||[]).map(row=>[row.id,row]));
        const effectEdits=(state.runtimeOverrides.effects||[]).filter(row=>{
          const old=beforeEffects[row.id];return !old||row.overridden!==old.overridden||Number(row.low)!==Number(old.low)||Number(row.high)!==Number(old.high);
        }).map(row=>({id:row.id,overridden:!!row.overridden,low:Number(row.low),high:Number(row.high)}));
        const xpEdits=(state.runtimeOverrides.xpSources||[]).filter(row=>{
          const old=beforeXp[row.id];return !old||row.overridden!==old.overridden||Number(row.amount)!==Number(old.amount);
        }).map(row=>({id:row.id,overridden:!!row.overridden,amount:Number(row.amount)}));
        const result=await post("/api/runtime-overrides/save",{
          effects:effectEdits,xpSources:xpEdits,
          effectsHash:state.savedRuntimeOverrides.effectsHash||"",
          xpSourcesHash:state.savedRuntimeOverrides.xpSourcesHash||""
        });
        state.runtimeOverrides=result;state.savedRuntimeOverrides=clone(result);
      }
      if(gauntletDirty())await saveGauntlet();
      if(moduleDataDirty())await saveModuleData();
      if(sourceDirty()){
        const result=await post("/api/source/save",{
          path:state.source.path,text:state.source.text,originalText:state.savedSourceText,
          sourceHash:state.source.sourceHash||""
        });
        state.source=result;state.savedSourceText=result.text;
        await reloadStructuredSource(result.absolutePath||result.path);
      }
      state.datamap=await api("/api/datamap");
      state.deployment=await api("/api/deployment").catch(()=>state.deployment);
      const runtime=await api("/api/runtime-overrides").catch(()=>null);
      if(runtime){state.runtimeOverrides=runtime;state.savedRuntimeOverrides=clone(runtime)}
      render();
    }catch(error){showAlert?.(String(error.message||error),"Bannerlord save failed")}
  }

  async function discardAllChanges(){
    const runtimeRequest=api("/api/runtime-overrides").catch(error=>({available:false,error:String(error.message||error),effects:[],xpSources:[]}));
    const selectedProject=state.project?.projectFile?.name||"";
    const projectRequest=api(`/api/project${selectedProject?`?project=${encodeURIComponent(selectedProject)}`:""}`);
    const requests=[
      api("/api/module"),projectRequest,api("/api/skills"),api("/api/effects"),api("/api/perks"),
      api("/api/xp-sources"),api("/api/settings-defaults"),runtimeRequest,api("/api/deployment"),api("/api/datamap")
    ];
    const gauntletPath=state.gauntlet?.relativePath||"";
    const moduleDataPath=state.moduleData?.relativePath||"";
    const sourcePath=state.source?.path||"";
    if(gauntletPath)requests.push(api(`/api/gauntlet?path=${encodeURIComponent(gauntletPath)}`));
    if(moduleDataPath)requests.push(api(`/api/module-data?path=${encodeURIComponent(moduleDataPath)}`));
    if(sourcePath)requests.push(api(`/api/source?path=${encodeURIComponent(sourcePath)}`));
    const values=await Promise.all(requests);
    const [module,project,skills,effects,perks,xpSources,mcmDefaults,runtimeOverrides,deployment,datamap]=values;
    state.module=module;state.savedModule=clone(module);
    state.project=project;state.savedProject=clone(project);
    state.skills=skills;state.savedSkills=clone(skills);
    state.effects=effects;state.savedEffects=clone(effects);
    state.perks=perks;state.savedPerks=clone(perks);
    state.xpSources=xpSources;state.savedXpSources=clone(xpSources);
    state.mcmDefaults=mcmDefaults;state.savedMcmDefaults=clone(mcmDefaults);
    state.runtimeOverrides=runtimeOverrides;state.savedRuntimeOverrides=clone(runtimeOverrides);
    state.deployment=deployment;state.datamap=datamap;
    let offset=10;
    if(gauntletPath){state.gauntlet=values[offset++];state.savedGauntlet=clone(state.gauntlet)}
    if(moduleDataPath){state.moduleData=prepareModuleData(values[offset++]);state.savedModuleData=clone(state.moduleData)}
    if(sourcePath){state.source=values[offset++];state.savedSourceText=state.source.text}
    render();refresh();
  }

  renderDataMap=function(){
    const open=row=>{
      if(row.target==="module"){state.moduleView="metadata";navigate("module")}
      else if(row.target==="dependencies"){state.moduleView="dependencies";navigate("module")}
      else if(row.target==="submodules"){state.moduleView="submodules";navigate("module")}
      else if(row.target==="xmls"){state.moduleView="xmls";navigate("module")}
      else if(row.target==="skills"){state.skillView="definitions";navigate("skills")}
      else if(row.target==="effects"){state.skillView="effects";navigate("skills")}
      else if(row.target==="perks"){state.skillView="perks";navigate("skills")}
      else if(row.target==="xp"){state.skillView="xp";navigate("skills")}
      else if(row.target==="settings")navigate("tweaks")
      else if(row.target==="runtime")navigate("runtime")
      else if(row.target==="gauntlet"){state.gauntletView="widgets";loadGauntlet(row.editorPath||row.filename)}
      else if(row.target==="moduledata"){state.moduleDataView="records";loadModuleData(row.editorPath||row.filename)}
      else if(row.target==="build")navigate("build")
    };
    const view=LexeditorUI.dataMap({
      rows:state.datamap.rows,query:state.query,status:state.mapStatus,page:state.page,sort:state.sort,
      open,openSource,
      changeQuery:value=>{state.query=value;state.page=0;renderDataMap()},
      changeStatus:value=>{state.mapStatus=value;state.page=0;renderDataMap()},
      changePage:value=>{state.page=value;renderDataMap()},
      changeSort:key=>{const [active,direction]=state.sort;state.sort=[key,active===key?-direction:1];renderDataMap()}
    });
    main.replaceChildren(view.content);
  };

  navigate=function(tab){
    state.tab=tab;
    const title=tab==="datamap"?"Data Map":tab==="info"?"Information":tab==="tweaks"?"Tweaks":String(tab).replace(/^\w/,value=>value.toUpperCase());
    main.replaceChildren(uiLoading(title,"Loading page…"));
    requestAnimationFrame(()=>render());
  };

  render=function(){
    const views={
      module:renderModuleArea,skills:renderSkillsArea,tweaks:renderMcmDefaults,runtime:renderRuntimeOverrides,
      gauntlet:renderGauntlet,moduledata:renderModuleData,build:renderBuild,info:renderInfo,
      datamap:renderDataMap,source:renderSource
    };
    try{(views[state.tab]||renderModuleArea)()}
    catch(error){main.replaceChildren(uiError("Bannerlord UI error",String(error.message||error)))}
    refresh();
  };

  const shell=LexeditorUI.mountShell({
    host:"#lexeditor-shell",brand:"LEXEDITOR",
    plugin:{id:"bannerlord",themeName:"bannerlord",theme:{accent:"#8d2f25",highlight:"#a56b34"}},
    tabs:[
      {id:"module",label:"Module"},{id:"skills",label:"Skills"},{id:"tweaks",label:"Tweaks"},
      {id:"runtime",label:"Runtime"},{id:"gauntlet",label:"Gauntlet"},
      {id:"moduledata",label:"ModuleData"},{id:"build",label:"Build"}
    ],
    activeTab:()=>state.tab,navigate,
    help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the Bannerlord Data Map",
    info:()=>navigate("info"),infoActive:()=>state.tab==="info",infoTitle:"Open Bannerlord setup, deployment, and runtime information",
    dirtyCount,readonly:()=>false,save,discard:discardAllChanges
  });

  const runtimeRequest=api("/api/runtime-overrides").catch(error=>({available:false,error:String(error.message||error),effects:[],xpSources:[]}));
  Promise.all([api("/api/module"),api("/api/project"),api("/api/skills"),api("/api/effects"),api("/api/perks"),api("/api/xp-sources"),api("/api/settings-defaults"),runtimeRequest,api("/api/deployment"),api("/api/datamap")]).then(([module,project,skills,effects,perks,xpSources,mcmDefaults,runtimeOverrides,deployment,datamap])=>{
    state.module=module;state.savedModule=clone(module);
    state.project=project;state.savedProject=clone(project);
    state.skills=skills;state.savedSkills=clone(skills);
    state.effects=effects;state.savedEffects=clone(effects);
    state.perks=perks;state.savedPerks=clone(perks);
    state.xpSources=xpSources;state.savedXpSources=clone(xpSources);
    state.mcmDefaults=mcmDefaults;state.savedMcmDefaults=clone(mcmDefaults);
    state.runtimeOverrides=runtimeOverrides;state.savedRuntimeOverrides=clone(runtimeOverrides);
    state.deployment=deployment;
    state.datamap=datamap;render();LexeditorUI.finishPluginLoading();
  }).catch(error=>{
    main.replaceChildren(uiError("Bannerlord plugin error",String(error.message||error)));
    LexeditorUI.finishPluginLoading();
    refresh();
  });
