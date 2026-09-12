"use strict";
  function skillRows(){
    if(!state.skills?.available)return [];
    return [
      ...(state.skills.attributes||[]).map((row,index)=>({kind:"attribute",index,row})),
      ...(state.skills.skills||[]).map((row,index)=>({kind:"skill",index,row}))
    ];
  }
  function renderSkills(){
    if(!state.skills?.available){
      main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Custom skills"),el("div",{class:"bl-empty"},"This project does not contain src/CustomSkillDefinitions.cs in the supported LexerSkillTweaks shape.")));return
    }
    const selection=state.skillSelection;
    const list=selection.kind==="attribute"?state.skills.attributes:state.skills.skills;
    const record=list[selection.index];
    const rows=skillRows();
    const master=el("div",{class:"bl-master"},
      el("div",{class:"bl-master-head"},el("strong",{},"Attributes & skills")),
      el("div",{class:"bl-list"},...rows.map(item=>{
        const active=item.kind===selection.kind&&item.index===selection.index;
        return el("button",{type:"button",class:`bl-item${active?" active":""}`,onclick:()=>{state.skillSelection={kind:item.kind,index:item.index};render()}},
          item.row.name||item.row.stringId,
          el("small",{},item.kind==="attribute"?`Attribute · ${item.row.stringId}`:`Skill · ${item.row.attributeId}`));
      }))
    );
    let detail;
    if(!record)detail=el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"Select a custom definition."));
    else if(selection.kind==="attribute")detail=el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.name||record.stringId),
        el("div",{class:"bl-grid"},
          ...fieldRow("String ID",el("code",{},record.stringId)),
          ...fieldRow("Name",textInput(record.name,value=>record.name=value)),
          ...fieldRow("Abbreviation",textInput(record.abbreviation,value=>record.abbreviation=value)),
          ...fieldRow("Description",textareaInput(record.description,value=>record.description=value))
        ),
        el("div",{class:"bl-note"},"String IDs remain read-only because other C# code may reference them.")
      ));
    else{
      const attributes=(state.skills.attributes||[]).map(row=>[row.stringId,row.name||row.stringId]);
      detail=el("div",{class:"bl-detail"},
        el("section",{class:"bl-panel"},el("h2",{},record.name||record.stringId),
          el("div",{class:"bl-grid"},
            ...fieldRow("String ID",el("code",{},record.stringId)),
            ...fieldRow("Name",textInput(record.name,value=>record.name=value)),
            ...fieldRow("Attribute",select(record.attributeId,attributes,value=>record.attributeId=value)),
            ...fieldRow("Description",textareaInput(record.description,value=>record.description=value)),
            ...fieldRow("How to learn",textareaInput(record.howToLearn,value=>record.howToLearn=value))
          ),
          el("div",{class:"bl-note"},"Lexeditor patches only the string arguments inside the existing SkillDefinition call and refuses a save if record identities/counts change.")
        ));
    }
    main.replaceChildren(el("div",{class:"bl-split"},master,detail));
  }

  function renderEffects(){
    if(!state.effects?.available){
      main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Quantitative effects"),el("div",{class:"bl-empty"},"This project does not contain src/CustomSkillEffectRanges.cs in the supported Effect(...) shape.")));return
    }
    const rows=state.effects.effects||[];
    const record=rows[state.effectIndex];
    const master=el("div",{class:"bl-master"},
      el("div",{class:"bl-master-head"},el("strong",{},"Quantitative effects")),
      el("div",{class:"bl-list"},...rows.map((row,index)=>el("button",{type:"button",class:`bl-item${index===state.effectIndex?" active":""}`,onclick:()=>{state.effectIndex=index;render()}},
        row.label,el("small",{},`${row.skillId} · ${row.defaultLow}${row.suffix} → ${row.defaultHigh}${row.suffix}`))))
    );
    const detail=!record?el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"No quantitative effects parsed.")):el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.label),
        el("div",{class:"bl-grid"},
          ...fieldRow("Effect ID",el("code",{},record.id)),
          ...fieldRow("Skill",record.skillId),
          ...fieldRow("Level 0",numberInput(record.defaultLow,value=>record.defaultLow=value)),
          ...fieldRow("Level 100",numberInput(record.defaultHigh,value=>record.defaultHigh=value)),
          ...fieldRow("Suffix",record.suffix||"—"),
          ...fieldRow("Per-level slope",String((record.defaultHigh-record.defaultLow)/100))
        ),
        el("div",{class:"bl-note"},"These are the C# default ranges used when no runtime custom_skill_effects.json override exists. Labels and IDs remain stable so existing runtime override keys do not silently break.")
      ));
    main.replaceChildren(el("div",{class:"bl-split"},master,detail));
  }

  function renderPerks(){
    if(!state.perks?.available){
      main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"Perks"),el("div",{class:"bl-empty"},"This project does not contain src/CustomSkillPerks.cs in the supported Perk(...) shape.")));return
    }
    const rows=state.perks.perks||[];
    const record=rows[state.perkIndex];
    const master=el("div",{class:"bl-master"},
      el("div",{class:"bl-master-head"},el("strong",{},`Perks (${rows.length})`)),
      el("div",{class:"bl-list"},...rows.map((row,index)=>el("button",{type:"button",class:`bl-item${index===state.perkIndex?" active":""}`,onclick:()=>{state.perkIndex=index;render()}},
        `${row.implemented?"":"*"}${row.name}`,
        el("small",{},`${row.skillId} · level ${row.level}${row.implemented?" · implemented":" · not implemented"}`))))
    );
    const detail=!record?el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"No perks parsed.")):el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.name),
        el("div",{class:"bl-grid"},
          ...fieldRow("Perk ID",el("code",{},record.id)),
          ...fieldRow("Skill",record.skillId),
          ...fieldRow("Name",record.name),
          ...fieldRow("Level",numberInput(record.level,value=>record.level=Math.round(value),{min:0,max:100,step:1})),
          ...fieldRow("Implemented",record.implemented?"Yes":"No"),
          ...fieldRow("Description",textareaInput(record.description,value=>record.description=value))
        ),
        el("div",{class:"bl-note"},"Skill, name, and implementation status stay read-only because gameplay code looks perks up by skill/name and unimplemented entries do not necessarily have mechanics behind them.")
      ));
    main.replaceChildren(el("div",{class:"bl-split"},master,detail));
  }

  function renderXpSources(){
    if(!state.xpSources?.available){
      main.replaceChildren(el("section",{class:"bl-card"},el("h2",{},"XP Sources"),el("div",{class:"bl-empty"},"This project does not contain src/CustomSkillXpSourcesConfig.cs in the supported Source(...) shape.")));return
    }
    const rows=state.xpSources.sources||[];
    const record=rows[state.xpSourceIndex];
    const master=el("div",{class:"bl-master"},
      el("div",{class:"bl-master-head"},el("strong",{},`XP Sources (${rows.length})`)),
      el("div",{class:"bl-list"},...rows.map((row,index)=>el("button",{type:"button",class:`bl-item${index===state.xpSourceIndex?" active":""}`,onclick:()=>{state.xpSourceIndex=index;render()}},
        row.label,el("small",{},`${row.skillId} · ${row.defaultAmount} XP`))))
    );
    const detail=!record?el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"No XP sources parsed.")):el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.label),
        el("div",{class:"bl-grid"},
          ...fieldRow("Source ID",el("code",{},record.id)),
          ...fieldRow("Skill",record.skillId),
          ...fieldRow("Label",record.label),
          ...fieldRow("Default XP",numberInput(record.defaultAmount,value=>record.defaultAmount=value,{min:0,step:"any"}))
        ),
        el("div",{class:"bl-note"},"This edits the C# fallback award. Skill and source label stay fixed because runtime award calls use them as the source identity; deployed JSON overrides may still replace the fallback value at runtime.")
      ));
    main.replaceChildren(el("div",{class:"bl-split"},master,detail));
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
