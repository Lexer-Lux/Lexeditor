"use strict";
  function skillRows(){
    if(!state.skills?.available)return [];
    return [
      ...(state.skills.attributes||[]).map((row,index)=>({kind:"attribute",index,row})),
      ...(state.skills.skills||[]).map((row,index)=>({kind:"skill",index,row}))
    ];
  }
  function renderSkills(){
    if(!state.skills?.available){main.replaceChildren(uiEmpty("Skills","This project does not contain src/CustomSkillDefinitions.cs in the supported LexerSkillTweaks shape."));return}
    const items=skillRows().map(item=>({
      kind:item.kind,index:item.index,row:item.row,name:item.row.name||item.row.stringId,internal:item.row.stringId,
      attribute:item.kind==="attribute"?"Attribute":item.row.attributeId,
      searchText:`${item.kind} ${item.row.name||""} ${item.row.stringId||""} ${item.row.attributeId||""}`
    }));
    const columns=[
      {key:"name",label:"Name",edit:(item,value)=>{item.row.name=String(value);refresh()},editValue:item=>item.row.name},
      {key:"internal",label:"Internal name"},
      {key:"attribute",label:"Attribute"}
    ];
    const selected=`${state.skillSelection.kind}:${state.skillSelection.index}`;
    const detail=item=>{
      const row=item.row;
      if(item.kind==="attribute")return BLUI.detailPanel({
        title:row.name||row.stringId,renameRecord:value=>{row.name=value;refresh()},meta:row.stringId,
        body:[BLUI.detailSection({title:"ATTRIBUTE",body:[
          readField("Internal name",row.stringId,"Stable string ID referenced by other C# code; Lexeditor deliberately does not rename it."),
          textField("Abbreviation",row.abbreviation||"",value=>row.abbreviation=value,"Short label displayed where the mod uses this custom attribute."),
          BLUI.detailField({label:"Description",control:textareaInput(row.description||"",value=>row.description=value),help:BLUI.infoHelp("Player-facing explanation of this custom attribute.")})
        ]})]});
      const attributes=(state.skills.attributes||[]).map(attribute=>[attribute.stringId,attribute.name||attribute.stringId]);
      return BLUI.detailPanel({
        title:row.name||row.stringId,renameRecord:value=>{row.name=value;refresh()},meta:row.stringId,
        body:[BLUI.detailSection({title:"SKILL",body:[
          readField("Internal name",row.stringId,"Stable skill string ID used by gameplay code."),
          selectField("Attribute",row.attributeId,attributes,value=>row.attributeId=value,"Custom attribute this skill is grouped under on the character screen."),
          BLUI.detailField({label:"Description",control:textareaInput(row.description||"",value=>row.description=value),help:BLUI.infoHelp("Player-facing explanation of what this skill changes or represents.")}),
          BLUI.detailField({label:"How to learn",control:textareaInput(row.howToLearn||"",value=>row.howToLearn=value),help:BLUI.infoHelp("Player-facing guidance describing the actions that award this custom skill XP.")})
        ]})]});
    };
    main.replaceChildren(tableView({
      key:"skills",rows:items,keyOf:item=>`${item.kind}:${item.index}`,columns,detail,noun:"attributes and skills",placeholder:"Search skills…",
      selected,setSelected:value=>{const [kind,index]=String(value).split(":");state.skillSelection={kind,index:Number(index)}}
    }));
  }

  function renderEffects(){
    if(!state.effects?.available){main.replaceChildren(uiEmpty("Effects","This project does not contain src/CustomSkillEffectRanges.cs in the supported Effect(...) shape."));return}
    const items=(state.effects.effects||[]).map((row,index)=>({
      index,row,label:row.label,skill:row.skillId,low:Number(row.defaultLow),high:Number(row.defaultHigh),suffix:row.suffix||"",
      searchText:`${row.label} ${row.id} ${row.skillId}`
    }));
    const columns=[
      {key:"label",label:"Effect"},{key:"skill",label:"Skill"},
      {key:"low",label:"Level 0",numeric:true,edit:(item,value)=>{item.row.defaultLow=Number(value);refresh()},editValue:item=>item.row.defaultLow,
        editor:(item,commit)=>cellNumber(item.row.defaultLow,commit,{step:"any"})},
      {key:"high",label:"Level 100",numeric:true,edit:(item,value)=>{item.row.defaultHigh=Number(value);refresh()},editValue:item=>item.row.defaultHigh,
        editor:(item,commit)=>cellNumber(item.row.defaultHigh,commit,{step:"any"})}
    ];
    const detail=item=>BLUI.detailPanel({
      title:item.row.label,meta:item.row.id,
      body:[BLUI.detailSection({title:"SCALING",body:[
        readField("Internal name",item.row.id,"Stable effect ID used by runtime override JSON."),
        readField("Skill",item.row.skillId),
        numberField("Level 0",item.row.defaultLow,value=>item.row.defaultLow=value,{help:"Default gameplay magnitude at custom skill level 0 when no deployed runtime override exists."}),
        numberField("Level 100",item.row.defaultHigh,value=>item.row.defaultHigh=value,{help:"Default gameplay magnitude at custom skill level 100. Intermediate levels interpolate linearly."}),
        readField("Unit suffix",item.row.suffix||"none"),
        readField("Per-level slope",(Number(item.row.defaultHigh)-Number(item.row.defaultLow))/100)
      ]})]
    });
    main.replaceChildren(tableView({
      key:"effects",rows:items,keyOf:item=>item.index,columns,detail,noun:"quantitative effects",placeholder:"Search effects…",
      selected:state.effectIndex,setSelected:value=>state.effectIndex=Number(value)
    }));
  }

  function renderPerks(){
    if(!state.perks?.available){main.replaceChildren(uiEmpty("Perks","This project does not contain src/CustomSkillPerks.cs in the supported Perk(...) shape."));return}
    const items=(state.perks.perks||[]).map((row,index)=>({
      index,row,name:row.name,skill:row.skillId,level:Number(row.level),implemented:!!row.implemented,
      searchText:`${row.name} ${row.id} ${row.skillId} ${row.implemented?"implemented":"not implemented"}`
    }));
    const columns=[
      {key:"name",label:"Name"},{key:"skill",label:"Skill"},
      {key:"level",label:"Level",numeric:true,edit:(item,value)=>{item.row.level=Math.round(Number(value));refresh()},editValue:item=>item.row.level,
        editor:(item,commit)=>cellNumber(item.row.level,commit,{min:0,max:100,step:1,integer:true})},
      {key:"implemented",label:"Implemented",render:item=>item.implemented?"Yes":"No"}
    ];
    const detail=item=>BLUI.detailPanel({
      title:item.row.name,meta:item.row.id,
      body:[BLUI.detailSection({title:"PERK",body:[
        readField("Internal name",item.row.id,"Stable perk identity used by the mod's gameplay code."),
        readField("Skill",item.row.skillId),
        numberField("Level",item.row.level,value=>item.row.level=Math.round(value),{min:0,max:100,step:1,help:"Custom skill level required for this perk."}),
        readField("Implemented",item.row.implemented?"Yes":"No","Unimplemented entries are design placeholders; Lexeditor does not invent gameplay mechanics for them."),
        BLUI.detailField({label:"Description",control:textareaInput(item.row.description||"",value=>item.row.description=value),help:BLUI.infoHelp("Player-facing perk description. Editing text does not create mechanics for an unimplemented perk.")})
      ]})]
    });
    main.replaceChildren(tableView({
      key:"perks",rows:items,keyOf:item=>item.index,columns,detail,noun:"perks",placeholder:"Search perks…",
      selected:state.perkIndex,setSelected:value=>state.perkIndex=Number(value)
    }));
  }

  function renderXpSources(){
    if(!state.xpSources?.available){main.replaceChildren(uiEmpty("XP Sources","This project does not contain src/CustomSkillXpSourcesConfig.cs in the supported Source(...) shape."));return}
    const items=(state.xpSources.sources||[]).map((row,index)=>({
      index,row,label:row.label,skill:row.skillId,amount:Number(row.defaultAmount),
      searchText:`${row.label} ${row.id} ${row.skillId}`
    }));
    const columns=[
      {key:"label",label:"Source"},{key:"skill",label:"Skill"},
      {key:"amount",label:"Default XP",numeric:true,edit:(item,value)=>{item.row.defaultAmount=Math.max(0,Number(value));refresh()},editValue:item=>item.row.defaultAmount,
        editor:(item,commit)=>cellNumber(item.row.defaultAmount,commit,{min:0,step:"any"})}
    ];
    const detail=item=>BLUI.detailPanel({
      title:item.row.label,meta:item.row.id,
      body:[BLUI.detailSection({title:"XP AWARD",body:[
        readField("Internal name",item.row.id,"Runtime source identity used by XP award calls and deployed override JSON."),
        readField("Skill",item.row.skillId),
        numberField("Default XP",item.row.defaultAmount,value=>item.row.defaultAmount=Math.max(0,value),{min:0,help:"Fallback XP awarded by this source when no deployed runtime override replaces it."})
      ]})]
    });
    main.replaceChildren(tableView({
      key:"xp",rows:items,keyOf:item=>item.index,columns,detail,noun:"XP sources",placeholder:"Search XP sources…",
      selected:state.xpSourceIndex,setSelected:value=>state.xpSourceIndex=Number(value)
    }));
  }

  function deploymentAssetBlock(title,status){
    const row=status||{source:0,deployed:0,missing:[],different:[],inSync:true};
    const missing=row.missing||[],different=row.different||[];
    return el("div",{class:"bl-list-block"},el("h3",{},title),
      el("div",{},`${row.source||0} project file(s) · ${row.deployed||0} deployed · ${missing.length} missing · ${different.length} different`),
      missing.length?el("ul",{},...missing.map(value=>el("li",{},`Missing: ${value}`))):null,
      different.length?el("ul",{},...different.map(value=>el("li",{},`Different: ${value}`))):null,
      row.inSync?el("div",{class:"bl-note"},"Project-owned files match the deployed copies."):null);
  }

  function dependencyDiagnosticLine(row){
    let source="Native dependency";
    if(row.origin==="DependedModuleMetadatas")source="BLSE metadata";
    else if(row.origin==="LoadAfterModules")source="Legacy LoadAfterModules";
    else if(String(row.origin||"").startsWith("OptionalDependModules/")||row.origin==="DependedModules/OptionalDependModule")source="Launcher optional dependency";
    const details=[source];
    if(row.order==="LoadBeforeThis")details.push("loads before this");
    else if(row.order==="LoadAfterThis")details.push("loads after this");
    if(row.optional)details.push("optional");
    if(row.incompatible)details.push("incompatible");
    if(row.effective===false)details.push(`SHADOWED by ${row.shadowedByOrigin||"earlier relation"}`);
    if(row.overriddenByCommunityMetadata)details.push("native row overridden by extended metadata");
    if(row.requiredVersion)details.push(`requires ${row.requiredVersion}`);
    if(row.installedVersion)details.push(`installed ${row.installedVersion}`);
    if(row.versionMatch===true)details.push("version OK");
    else if(row.versionMatch===false)details.push("VERSION MISMATCH");
    const marker=row.effective===false?"↳":(row.installed?"✓":"✗");
    return `${marker} ${row.id} — ${details.join(" · ")}`;
  }

  function renderDeployment(){
    const d=state.deployment;
    if(!d){main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Deployment"),el("div",{class:"bl-empty"},"Deployment status is unavailable.")));return}
    const yesNo=value=>value?"Yes":"No";
    const summary=el("section",{class:"bl-card"},
      el("h2",{},d.projectName||d.moduleId||"Deployment"),
      el("div",{class:"bl-grid"},
        ...fieldRow("Module ID",d.moduleId||"—"),
        ...fieldRow("Runnable",yesNo(d.runnable)),
        ...fieldRow("Project deployed",yesNo(d.deployed)),
        ...fieldRow("Project/deployed sync",yesNo(d.inSync)),
        ...fieldRow("Descriptor sync",yesNo(d.descriptorInSync)),
        ...fieldRow("Project version",d.projectVersion||"—"),
        ...fieldRow("Deployed version",d.deployedVersion||"—"),
        ...fieldRow("Game root",el("code",{},d.gameRoot||"")),
        ...fieldRow("Module root",el("code",{},d.deployedRoot||""))
      ),
      el("div",{class:"bl-list-block"},el("h3",{},"Issues"),
        d.issues?.length?el("ul",{},...d.issues.map(value=>el("li",{},value))):el("div",{class:"bl-note"},"No deployment problems detected by the static checks.")),
      bannerlordModLoaderSection()
    );
    const deps=d.dependencies||[],bins=d.binaries||[],assets=d.assets||{},overrides=d.runtimeOverrides||{};
    const legacyGui={source:assets.sourceGuiXml||0,deployed:assets.deployedGuiXml||0,missing:assets.missingGuiXml||[],different:assets.differentGuiXml||[],inSync:!(assets.missingGuiXml||[]).length&&!(assets.differentGuiXml||[]).length};
    const detail=el("section",{class:"bl-card"},
      el("h2",{},"Installed module diagnostics"),
      el("div",{class:"bl-list-block"},el("h3",{},"Dependencies"),
        deps.length?el("ul",{},...deps.map(row=>el("li",{},dependencyDiagnosticLine(row)))):el("div",{class:"bl-note"},"No declared dependency relations.")),
      el("div",{class:"bl-list-block"},el("h3",{},"Module binaries"),
        bins.length?el("ul",{},...bins.map(row=>el("li",{},`${row.exists?"✓":"✗"} ${row.name}${row.exists?` · ${row.size} bytes`:" · missing"}${row.classType?` · ${row.classType}`:""}`))):el("div",{class:"bl-note"},"No SubModule DLL entries.")),
      deploymentAssetBlock("GUI assets",assets.gui||legacyGui),
      deploymentAssetBlock("ModuleData assets",assets.moduleData),
      el("div",{class:"bl-list-block"},el("h3",{},"Runtime balancing overrides"),
        ...Object.entries(overrides).map(([key,row])=>el("div",{},`${key}: ${row.exists?(row.valid?`${row.keys} override key(s)`:"INVALID JSON"):"not present"}`,row.error?el("small",{},` · ${row.error}`):null))),
      el("div",{class:"bl-note"},"Runtime balance JSON is intentionally excluded from project/deployed asset sync because it is managed as deployed runtime state by the Runtime tab.")
    );
    main.replaceChildren(el("div",{class:"bl-build-layout"},summary,detail));
  }
