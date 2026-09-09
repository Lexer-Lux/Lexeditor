"use strict";
  async function save(){
    try{
      if(moduleDirty()){
        const result=await post("/api/module/save",moduleEditable(state.module));
        state.module=result.module;state.savedModule=clone(result.module);
      }
      if(projectDirty()){
        const current=state.project.projectFile.properties;
        const before=state.savedProject.projectFile.properties;
        const edits=Object.fromEntries((state.project.projectFile.editableProperties||[])
          .filter(name=>current[name]!==before[name]).map(name=>[name,current[name]]));
        if(Object.keys(edits).length){
          const result=await post("/api/project/save",{edits});
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
          skills:makeEdits(state.skills.skills,state.savedSkills.skills,skillFields)
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
        const result=await post("/api/effects/save",{edits});
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
        const result=await post("/api/perks/save",{edits});
        state.perks=result;state.savedPerks=clone(result);
      }
      if(xpSourcesDirty()){
        const edits=(state.xpSources.sources||[]).flatMap((row,index)=>{
          const old=state.savedXpSources.sources[index];if(!old)return [];
          return row.defaultAmount!==old.defaultAmount?[{index:row.index,originalId:old.id,fields:{defaultAmount:row.defaultAmount}}]:[];
        });
        const result=await post("/api/xp-sources/save",{edits});
        state.xpSources=result;state.savedXpSources=clone(result);
      }
      if(mcmDirty()){
        const edits=(state.mcmDefaults.settings||[]).flatMap((row,index)=>{
          const old=state.savedMcmDefaults.settings[index];if(!old)return [];
          return row.default!==old.default?[{property:row.property,value:row.default}]:[];
        });
        const result=await post("/api/settings-defaults/save",{edits});
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
        const result=await post("/api/runtime-overrides/save",{effects:effectEdits,xpSources:xpEdits});
        state.runtimeOverrides=result;state.savedRuntimeOverrides=clone(result);
      }
      if(sourceDirty()){
        const result=await post("/api/source/save",{path:state.source.path,text:state.source.text});
        state.source=result;state.savedSourceText=result.text;
        if(state.source.path.toLowerCase().endsWith(".csproj")){
          state.project=await api("/api/project");state.savedProject=clone(state.project);
        }
      }
      state.datamap=await api("/api/datamap");
      state.deployment=await api("/api/deployment").catch(()=>state.deployment);
      render();
    }catch(error){showAlert?.(String(error.message||error),"Bannerlord save failed")}
  }

  const shell=LexeditorUI.mountShell({
    host:"#lexeditor-shell",brand:"LEXEDITOR",
    plugin:{id:"bannerlord",themeName:"bannerlord",theme:{accent:"#8d2f25",highlight:"#a56b34"}},
    tabs:[
      {id:"module",label:"Module"},{id:"dependencies",label:"Dependencies"},
      {id:"submodules",label:"Submodules"},{id:"xmls",label:"XML"},
      {id:"skills",label:"Skills"},{id:"effects",label:"Effects"},
      {id:"perks",label:"Perks"},{id:"xp",label:"XP"},{id:"settings",label:"Settings"},
      {id:"runtime",label:"Runtime"},{id:"build",label:"Build"},{id:"deployment",label:"Deployment"}
    ],
    activeTab:()=>state.tab,navigate,
    help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the Bannerlord Data Map",
    dirtyCount,readonly:()=>false,save
  });

  Promise.all([api("/api/module"),api("/api/project"),api("/api/skills"),api("/api/effects"),api("/api/perks"),api("/api/xp-sources"),api("/api/settings-defaults"),api("/api/runtime-overrides"),api("/api/deployment"),api("/api/datamap")]).then(([module,project,skills,effects,perks,xpSources,mcmDefaults,runtimeOverrides,deployment,datamap])=>{
    state.module=module;state.savedModule=clone(module);
    state.project=project;state.savedProject=clone(project);
    state.skills=skills;state.savedSkills=clone(skills);
    state.effects=effects;state.savedEffects=clone(effects);
    state.perks=perks;state.savedPerks=clone(perks);
    state.xpSources=xpSources;state.savedXpSources=clone(xpSources);
    state.mcmDefaults=mcmDefaults;state.savedMcmDefaults=clone(mcmDefaults);
    state.runtimeOverrides=runtimeOverrides;state.savedRuntimeOverrides=clone(runtimeOverrides);
    state.deployment=deployment;
    state.datamap=datamap;render();
  }).catch(error=>{
    main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Bannerlord plugin error"),el("div",{class:"bl-note"},String(error.message||error))));
    refresh();
  });
