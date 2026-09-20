
  "use strict";
  const {el,clone,showAlert,confirmAction}=LexeditorUI;
  const main=document.querySelector("#main");
  const state={
    tab:"module",module:null,savedModule:null,project:null,savedProject:null,
    datamap:{rows:[]},query:"",mapStatus:"",page:0,sort:["filename",1],
    dependencySelection:{kind:"dependency",index:0},submoduleIndex:0,xmlIndex:0,
    buildConfiguration:"Debug",building:false,buildResult:null,deployment:null,
    skills:null,savedSkills:null,skillSelection:{kind:"attribute",index:0},
    effects:null,savedEffects:null,effectIndex:0,
    perks:null,savedPerks:null,perkIndex:0,
    xpSources:null,savedXpSources:null,xpSourceIndex:0,
    source:null,savedSourceText:null
  };

  async function api(path,options){
    const response=await fetch(path,options);
    const value=await response.json();
    if(!response.ok||value.error)throw new Error(value.error||`${response.status} ${response.statusText}`);
    return value;
  }
  const post=(path,payload)=>api(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  const refresh=()=>shell?.refresh?.();
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const metadata=m=>({name:m.name,id:m.id,version:m.version,moduleCategory:m.moduleCategory||"",moduleType:m.moduleType||"",url:m.url||"",updateInfo:m.updateInfo||"",defaultModule:!!m.defaultModule,singleplayer:!!m.singleplayer,multiplayer:!!m.multiplayer});
  const moduleEditable=m=>m?{metadata:metadata(m),dependencies:m.dependencies||[],communityDependencies:m.communityDependencies||[],legacyDependencies:m.legacyDependencies||[],modulesToLoadAfterThis:m.modulesToLoadAfterThis||[],incompatibleModules:m.incompatibleModules||[],submodules:m.submodules||[],xmls:m.xmls||[]}:null;
  const moduleSavePayload=(m,baseline)=>({...moduleEditable(m),legacyDependenciesBaseline:clone(baseline?.legacyDependencies||[]),sourceHash:baseline?.sourceHash||""});
  const moduleDirty=()=>state.module&&state.savedModule&&!same(moduleEditable(state.module),moduleEditable(state.savedModule));
  const projectDirty=()=>state.project?.projectFile&&state.savedProject?.projectFile&&!same(state.project.projectFile.properties,state.savedProject.projectFile.properties);
  const skillsEditable=value=>value?{attributes:value.attributes||[],skills:value.skills||[]}:null;
  const effectsEditable=value=>value?value.effects||[]:null;
  const perksEditable=value=>value?value.perks||[]:null;
  const xpSourcesEditable=value=>value?value.sources||[]:null;
  const skillsDirty=()=>state.skills?.available&&state.savedSkills?.available&&!same(skillsEditable(state.skills),skillsEditable(state.savedSkills));
  const effectsDirty=()=>state.effects?.available&&state.savedEffects?.available&&!same(effectsEditable(state.effects),effectsEditable(state.savedEffects));
  const perksDirty=()=>state.perks?.available&&state.savedPerks?.available&&!same(perksEditable(state.perks),perksEditable(state.savedPerks));
  const xpSourcesDirty=()=>state.xpSources?.available&&state.savedXpSources?.available&&!same(xpSourcesEditable(state.xpSources),xpSourcesEditable(state.savedXpSources));
  const sourceDirty=()=>state.source&&state.savedSourceText!==null&&state.source.text!==state.savedSourceText;
  const normalizedFilePath=value=>String(value||"").replace(/\\/g,"/").replace(/\/{2,}/g,"/").toLocaleLowerCase();
  const sameFilePath=(left,right)=>{const a=normalizedFilePath(left),b=normalizedFilePath(right);return !!a&&!!b&&a===b};
  function structuredSourceConflict(){
    if(!sourceDirty())return "";
    const sourcePath=state.source?.absolutePath||state.source?.path||"";
    const candidates=[
      ["SubModule.xml",moduleDirty(),state.module?.path],
      ["project file",projectDirty(),state.project?.projectFile?.path],
      ["custom skill definitions",skillsDirty(),state.skills?.path],
      ["effect definitions",effectsDirty(),state.effects?.path],
      ["perk definitions",perksDirty(),state.perks?.path],
      ["XP source definitions",xpSourcesDirty(),state.xpSources?.path],
      ["MCM defaults",mcmDirty(),state.mcmDefaults?.path],
      ["Gauntlet prefab",gauntletDirty(),state.gauntlet?.path],
      ["ModuleData XML",moduleDataDirty(),state.moduleData?.path],
    ];
    return candidates.find(([_label,dirty,path])=>dirty&&sameFilePath(sourcePath,path))?.[0]||"";
  }
  function dirtyCount(){return Number(moduleDirty())+Number(projectDirty())+Number(skillsDirty())+Number(effectsDirty())+Number(perksDirty())+Number(xpSourcesDirty())+Number(sourceDirty())}

  function fieldRow(label,control){return [el("div",{class:"bl-label"},label),el("div",{class:"bl-control"},control)]}
  function textInput(value,change,attrs={}){
    return el("input",{type:"text",value:value??"",...attrs,oninput:event=>{change(event.target.value);refresh()}});
  }
  function checkbox(value,change){
    return el("input",{type:"checkbox",checked:!!value,onchange:event=>{change(event.target.checked);refresh()}});
  }
  function textareaInput(value,change,attrs={}){
    return el("textarea",{...attrs,oninput:event=>{change(event.target.value);refresh()}},value??"");
  }
  function numberInput(value,change,attrs={}){
    return el("input",{type:"number",step:"any",value:Number(value),...attrs,oninput:event=>{if(event.target.value!=="")change(Number(event.target.value));refresh()}});
  }
  function select(value,choices,change){
    const node=el("select",{onchange:event=>{change(event.target.value);refresh()}},
      ...choices.map(([key,label])=>{const option=el("option",{value:key},label);option.selected=key===value;return option}));
    return node;
  }
  function setModuleField(key,value){state.module[key]=value}

  function renderModule(){
    const m=state.module;
    if(!m){main.replaceChildren(uiEmpty("Module","No SubModule.xml is loaded."));return}
    const categories=[["","Legacy / not set"],["Singleplayer","Singleplayer"],["SingleplayerOptional","Singleplayer optional"],["Multiplayer","Multiplayer"],["MultiplayerOptional","Multiplayer optional"],["Server","Server"],["ServerOptional","Server optional"]];
    const types=[["","Default / not set"],["Community","Community"],["Official","Official"],["OfficialOptional","Official optional"]];
    main.replaceChildren(BLUI.detailPanel({
      title:m.name||m.id||"Bannerlord Module",
      renameRecord:value=>setModuleField("name",value),
      renameLabel:"Module display name",
      identity:m.id||null,
      meta:m.version||"",
      body:[
        BLUI.detailSection({title:"IDENTITY",body:[
          textField("Module ID",m.id,value=>setModuleField("id",value),"The stable Bannerlord module identifier used by dependencies, deployment folder naming and the launch module list."),
          textField("Version",m.version,value=>setModuleField("version",value),"Bannerlord and dependency metadata use this version for compatibility checks."),
          selectField("Category",m.moduleCategory||"",categories,value=>setModuleField("moduleCategory",value),"Bannerlord's current module category controls which launcher or game contexts consider this module."),
          selectField("Module type",m.moduleType||"",types,value=>setModuleField("moduleType",value),"Community versus official classification stored in SubModule.xml.")
        ]}),
        BLUI.detailSection({title:"DISCOVERY & COMPATIBILITY",body:[
          textField("Project URL",m.url||"",value=>setModuleField("url",value),"Optional community metadata link shown to mod tooling.",{placeholder:"https://…"}),
          textField("Update info",m.updateInfo||"",value=>setModuleField("updateInfo",value),"Supported community update grammar is NexusMods:<id>, GitHub:<user>/<repo>, or both separated by a semicolon.",{placeholder:"NexusMods:1234;GitHub:user/repo"}),
          boolField("Default module",m.defaultModule,value=>setModuleField("defaultModule",value),"Legacy Bannerlord flag retained for compatibility with older module descriptors."),
          boolField("Single-player",m.singleplayer,value=>setModuleField("singleplayer",value),"Legacy flag declaring that this module participates in single-player."),
          boolField("Multi-player",m.multiplayer,value=>setModuleField("multiplayer",value),"Legacy flag declaring that this module participates in multiplayer.")
        ]}),
        BLUI.detailSection({title:"STRUCTURE",body:[
          readField("Descriptor",m.path),
          readField("Native dependencies",(m.dependencies||[]).length),
          readField("BLSE metadata",(m.communityDependencies||[]).length),
          readField("Legacy relations",(m.legacyDependencies||[]).length),
          readField("Forced-after relations",(m.modulesToLoadAfterThis||[]).length),
          readField("Incompatibilities",(m.incompatibleModules||[]).length),
          readField("Submodules",(m.submodules||[]).length),
          readField("XML registrations",(m.xmls||[]).length)
        ]})
      ]
    }));
  }

  function relationList(kind){
    if(kind==="community")return state.module.communityDependencies||[];
    if(kind==="legacy")return state.module.legacyDependencies||[];
    if(kind==="incompatible")return state.module.incompatibleModules||[];
    if(kind==="loadAfter")return state.module.modulesToLoadAfterThis||[];
    return state.module.dependencies||[];
  }
  function dependencyRows(){
    return [
      ...(state.module.dependencies||[]).map((row,index)=>({kind:"dependency",index,row})),
      ...(state.module.communityDependencies||[]).map((row,index)=>({kind:"community",index,row})),
      ...(state.module.legacyDependencies||[]).map((row,index)=>({kind:"legacy",index,row})),
      ...(state.module.modulesToLoadAfterThis||[]).map((row,index)=>({kind:"loadAfter",index,row})),
      ...(state.module.incompatibleModules||[]).map((row,index)=>({kind:"incompatible",index,row}))
    ];
  }
  function legacyRelationLabel(row){
    if(row.origin==="LoadAfterModules")return "Legacy load-after";
    if(row.origin==="DependedModules/OptionalDependModule")return "Legacy nested optional";
    return "Legacy optional dependency";
  }
  function addDependency(kind){
    if(kind==="dependency"){
      state.module.dependencies.push({index:null,id:"",dependentVersion:"",optional:false,attributes:{}});
    }else if(kind==="community"){
      state.module.communityDependencies=state.module.communityDependencies||[];
      state.module.communityDependencies.push({index:null,id:"",order:"LoadBeforeThis",optional:false,incompatible:false,version:"",attributes:{}});
    }else if(kind==="loadAfter"){
      state.module.modulesToLoadAfterThis=state.module.modulesToLoadAfterThis||[];
      state.module.modulesToLoadAfterThis.push({index:null,id:"",attributes:{}});
    }else{
      state.module.incompatibleModules.push({index:null,id:"",elementTag:"Module",attributes:{}});
    }
    const list=relationList(kind);
    state.dependencySelection={kind,index:list.length-1};
    render();refresh();
  }
  function removeDependency(){
    const selection=state.dependencySelection;
    const list=relationList(selection.kind);
    if(!list.length)return;
    list.splice(selection.index,1);
    state.dependencySelection={kind:selection.kind,index:Math.max(0,Math.min(selection.index,list.length-1))};
    render();refresh();
  }
  function renderDependencies(){
    const items=dependencyRows().map(item=>{
      const row=item.row;
      const kindLabel=item.kind==="dependency"?"Native":item.kind==="community"?"BLSE":item.kind==="legacy"?"Legacy":item.kind==="loadAfter"?"Load after this":"Incompatible";
      return {kind:item.kind,index:item.index,row,id:row.id||"",kindLabel,version:row.dependentVersion||row.version||"",optional:!!row.optional,
        searchText:`${row.id||""} ${kindLabel} ${row.dependentVersion||row.version||""} ${row.origin||""}`};
    });
    const selected=`${state.dependencySelection.kind}:${state.dependencySelection.index}`;
    const columns=[
      {key:"kindLabel",label:"Relation",sortable:true,help:"Native, BLSE/BUTR, preserved legacy, inverse load-after, or incompatibility relation."},
      {key:"id",label:"Module ID",sortable:true,edit:(item,value)=>{item.row.id=String(value);refresh()},editValue:item=>item.row.id,
        help:"Stable target module identifier used by Bannerlord dependency resolution."},
      {key:"version",label:"Version",sortable:true,help:"Native dependent version or BLSE community version/range when that relation supports one."},
      {key:"optional",label:"Optional",sortable:true,render:item=>item.optional?"Yes":"No"}
    ];
    const filters=[
      uiButton("+ Native",()=>addDependency("dependency"),{title:"Add a native dependency"}),
      uiButton("+ BLSE",()=>addDependency("community"),{title:"Add BLSE/BUTR dependency metadata"}),
      uiButton("+ After",()=>addDependency("loadAfter"),{title:"Force a module to load after this module"}),
      uiButton("+ Incompatible",()=>addDependency("incompatible"),{title:"Add an incompatible module"})
    ];
    const detail=item=>{
      const row=item.row,fields=[
        textField("Module ID",row.id||"",value=>row.id=value,"The target module's stable Bannerlord ID. Duplicate relation precedence is resolved by this ID.")
      ];
      if(item.kind==="dependency"){
        fields.push(
          textField("Dependent version",row.dependentVersion||"",value=>row.dependentVersion=value,"Native launcher-style dependent version. Lexeditor reports mismatches as launcher-style warnings."),
          boolField("Optional",row.optional,value=>row.optional=value,"Optional dependencies affect order only when the target is already enabled; Lexeditor Play does not auto-enable them.")
        );
      }else if(item.kind==="community"){
        fields.push(
          selectField("Order",row.order||"",[["","No ordering edge"],["LoadBeforeThis","Dependency loads before this module"],["LoadAfterThis","Dependency loads after this module"]],value=>row.order=value,"BLSE/BUTR ordering edge relative to the current module."),
          textField("Version / range",row.version||"",value=>row.version=value,"BLSE community versions support minimums, wildcards and inclusive ranges.",{placeholder:"v2.0.* or v2.0.0-v2.3.*"}),
          boolField("Optional",row.optional,value=>row.optional=value,"An optional BLSE relation constrains ordering only when the target is otherwise enabled."),
          boolField("Incompatible",row.incompatible,value=>row.incompatible=value,"An incompatible BLSE relation cannot also carry an ordering edge.")
        );
      }else if(item.kind==="legacy"){
        fields.push(
          readField("Legacy shape",row.origin||"legacy dependency","Lexeditor preserves the historical XML element shape and unknown attributes; it only edits or removes rows that already exist."),
          readField("Meaning",row.order==="LoadAfterThis"?"Required legacy load-after relation":"Optional legacy compatibility relation")
        );
      }else if(item.kind==="loadAfter"){
        fields.push(readField("Meaning","Target loads after this module","This orders modules but does not enable the target module."));
      }else{
        fields.push(readField("Meaning","Incompatible module","Bannerlord should not run both modules together."));
      }
      return BLUI.detailPanel({title:item.kindLabel,identity:row.id||null,meta:item.version||"",
        actions:[uiButton("Remove",()=>{state.dependencySelection={kind:item.kind,index:item.index};removeDependency()},{danger:true})],
        body:[BLUI.detailSection({title:"RELATION",body:fields})]});
    };
    main.replaceChildren(tableView({
      key:"dependencies",rows:items,keyOf:item=>`${item.kind}:${item.index}`,columns,detail,noun:"module relations",
      placeholder:"Search module relations…",selected,
      setSelected:value=>{const [kind,index]=String(value).split(":");state.dependencySelection={kind,index:Number(index)}},
      filters
    }));
  }

  function addTag(submodule){
    submodule.tags=submodule.tags||[];
    submodule.tags.push({index:null,key:"",value:"",attributes:{}});
    render();refresh();
  }
  function renderTags(submodule){
    const rows=(submodule.tags||[]).map((tag,index)=>el("div",{class:"bl-tag-row"},
      textInput(tag.key,value=>tag.key=value,{placeholder:"key"}),
      textInput(tag.value,value=>tag.value=value,{placeholder:"value"}),
      el("button",{type:"button",onclick:()=>{submodule.tags.splice(index,1);render();refresh()},title:"Remove tag"},"×")
    ));
    return el("div",{class:"bl-tags"},
      ...rows,
      el("div",{class:"bl-actions"},el("button",{type:"button",onclick:()=>addTag(submodule)},"+ Add tag"))
    );
  }
  function addAssembly(submodule){
    submodule.assemblies=submodule.assemblies||[];
    submodule.assemblies.push({index:null,value:"",attributes:{}});
    render();refresh();
  }
  function renderAssemblies(submodule){
    return el("div",{class:"bl-tags"},
      ...(submodule.assemblies||[]).map((assembly,index)=>el("div",{class:"bl-tag-row",style:"grid-template-columns:minmax(180px,1fr) auto"},
        textInput(assembly.value,value=>assembly.value=value,{placeholder:"Additional assembly DLL"}),
        el("button",{type:"button",onclick:()=>{submodule.assemblies.splice(index,1);render();refresh()},title:"Remove assembly"},"×")
      )),
      el("div",{class:"bl-actions"},el("button",{type:"button",onclick:()=>addAssembly(submodule)},"+ Add assembly"))
    );
  }
  function addSubmodule(){
    state.module.submodules.push({index:null,name:"",dllName:"",classType:"",assemblies:[],tags:[]});
    state.submoduleIndex=state.module.submodules.length-1;render();refresh();
  }
  function removeSubmodule(){
    state.module.submodules.splice(state.submoduleIndex,1);
    state.submoduleIndex=Math.max(0,Math.min(state.submoduleIndex,state.module.submodules.length-1));render();refresh();
  }
  function renderSubmodules(){
    const rows=state.module.submodules||[];
    const record=rows[state.submoduleIndex];
    const master=el("div",{class:"bl-master"},
      el("div",{class:"bl-master-head"},el("strong",{},"Submodules"),el("button",{type:"button",onclick:addSubmodule},"+ Add")),
      el("div",{class:"bl-list"},...rows.map((row,index)=>el("button",{type:"button",class:`bl-item${index===state.submoduleIndex?" active":""}`,onclick:()=>{state.submoduleIndex=index;render()}},
        row.name||"(new submodule)",el("small",{},row.dllName||row.classType||"No DLL/class yet"))))
    );
    const detail=!record?el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"Select or add a submodule.")):el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.name||"New submodule"),
        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeSubmodule},"Remove")),
        el("div",{class:"bl-grid"},
          ...fieldRow("Name",textInput(record.name,value=>record.name=value)),
          ...fieldRow("DLL name",textInput(record.dllName,value=>record.dllName=value)),
          ...fieldRow("Class type",textInput(record.classType,value=>record.classType=value))
        ),
        el("h2",{},"Assemblies"),renderAssemblies(record),
        el("div",{class:"bl-note"},"Additional assemblies declared under this SubModule are preserved and edited as explicit DLL names."),
        el("h2",{},"Tags"),renderTags(record)
      ));
    main.replaceChildren(el("div",{class:"bl-split"},master,detail));
  }

  function addGameType(xml){
    xml.includedGameTypes=xml.includedGameTypes||[];
    xml.includedGameTypes.push({index:null,value:"",attributes:{}});
    render();refresh();
  }
  function renderGameTypes(xml){
    return el("div",{class:"bl-tags"},
      ...(xml.includedGameTypes||[]).map((row,index)=>el("div",{class:"bl-tag-row",style:"grid-template-columns:minmax(180px,1fr) auto"},
        textInput(row.value,value=>row.value=value,{placeholder:"GameType value"}),
        el("button",{type:"button",onclick:()=>{xml.includedGameTypes.splice(index,1);render();refresh()}},"×")
      )),
      el("div",{class:"bl-actions"},el("button",{type:"button",onclick:()=>addGameType(xml)},"+ Add game type"))
    );
  }
  function addXml(){
    state.module.xmls.push({index:null,id:"",path:"",includedGameTypes:[]});
    state.xmlIndex=state.module.xmls.length-1;render();refresh();
  }
  function removeXml(){
    state.module.xmls.splice(state.xmlIndex,1);
    state.xmlIndex=Math.max(0,Math.min(state.xmlIndex,state.module.xmls.length-1));render();refresh();
  }
  function renderXmls(){
    const rows=state.module.xmls||[];
    const record=rows[state.xmlIndex];
    const master=el("div",{class:"bl-master"},
      el("div",{class:"bl-master-head"},el("strong",{},"XML registrations"),el("button",{type:"button",onclick:addXml},"+ Add")),
      el("div",{class:"bl-list"},...rows.map((row,index)=>el("button",{type:"button",class:`bl-item${index===state.xmlIndex?" active":""}`,onclick:()=>{state.xmlIndex=index;render()}},
        row.id||"(new XML)",el("small",{},row.path||"No path yet"))))
    );
    const detail=!record?el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"No Xmls/XmlNode registrations in this project.")):el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.id||"New XML registration"),
        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeXml},"Remove")),
        el("div",{class:"bl-grid"},
          ...fieldRow("ID",textInput(record.id,value=>record.id=value)),
          ...fieldRow("Path",textInput(record.path,value=>record.path=value))
        ),
        el("h2",{},"Included game types"),renderGameTypes(record),
        el("div",{class:"bl-note"},"New XML registrations require at least one IncludedGameTypes/GameType entry; Lexeditor will not guess Campaign or another game type for you.")
      ));
    main.replaceChildren(el("div",{class:"bl-split"},master,detail));
  }
