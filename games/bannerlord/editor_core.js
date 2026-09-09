
  "use strict";
  const {el,clone,showAlert}=LexeditorUI;
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
  const metadata=m=>({name:m.name,id:m.id,version:m.version,moduleCategory:m.moduleCategory||"",moduleType:m.moduleType||"",defaultModule:!!m.defaultModule,singleplayer:!!m.singleplayer,multiplayer:!!m.multiplayer});
  const moduleEditable=m=>m?{metadata:metadata(m),dependencies:m.dependencies||[],communityDependencies:m.communityDependencies||[],modulesToLoadAfterThis:m.modulesToLoadAfterThis||[],incompatibleModules:m.incompatibleModules||[],submodules:m.submodules||[],xmls:m.xmls||[]}:null;
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
    if(!m){main.replaceChildren(el("div",{class:"bl-empty"},"No SubModule.xml loaded."));return}
    main.replaceChildren(el("section",{class:"bl-card"},
      el("h2",{},m.name||m.id||"Bannerlord Module"),
      el("div",{class:"bl-grid"},
        ...fieldRow("Name",textInput(m.name,value=>setModuleField("name",value))),
        ...fieldRow("ID",textInput(m.id,value=>setModuleField("id",value))),
        ...fieldRow("Version",textInput(m.version,value=>setModuleField("version",value))),
        ...fieldRow("Module category",select(m.moduleCategory||"",[["","Legacy / not set"],["Singleplayer","Singleplayer"],["SingleplayerOptional","Singleplayer optional"],["Multiplayer","Multiplayer"],["MultiplayerOptional","Multiplayer optional"],["Server","Server"],["ServerOptional","Server optional"]],value=>setModuleField("moduleCategory",value))),
        ...fieldRow("Module type",select(m.moduleType||"",[["","Default / not set"],["Community","Community"],["Official","Official"],["OfficialOptional","Official optional"]],value=>setModuleField("moduleType",value))),
        ...fieldRow("Default module",checkbox(m.defaultModule,value=>setModuleField("defaultModule",value))),
        ...fieldRow("Single-player",checkbox(m.singleplayer,value=>setModuleField("singleplayer",value))),
        ...fieldRow("Multi-player",checkbox(m.multiplayer,value=>setModuleField("multiplayer",value))),
        ...fieldRow("SubModule.xml",el("code",{},m.path)),
        ...fieldRow("Native dependencies",String((m.dependencies||[]).length)),
        ...fieldRow("BLSE dependency metadata",String((m.communityDependencies||[]).length)),
        ...fieldRow("Modules forced after this",String((m.modulesToLoadAfterThis||[]).length)),
        ...fieldRow("Incompatible modules",String((m.incompatibleModules||[]).length)),
        ...fieldRow("Submodules",String((m.submodules||[]).length)),
        ...fieldRow("XML registrations",String((m.xmls||[]).length))
      ),
      el("div",{class:"bl-note"},"The remaining SubModule.xml records have dedicated list/detail tabs so record identity stays in the master list and editable fields stay in the detail pane.")
    ));
  }

  function relationList(kind){
    if(kind==="community")return state.module.communityDependencies||[];
    if(kind==="incompatible")return state.module.incompatibleModules||[];
    if(kind==="loadAfter")return state.module.modulesToLoadAfterThis||[];
    return state.module.dependencies||[];
  }
  function dependencyRows(){
    return [
      ...(state.module.dependencies||[]).map((row,index)=>({kind:"dependency",index,row})),
      ...(state.module.communityDependencies||[]).map((row,index)=>({kind:"community",index,row})),
      ...(state.module.modulesToLoadAfterThis||[]).map((row,index)=>({kind:"loadAfter",index,row})),
      ...(state.module.incompatibleModules||[]).map((row,index)=>({kind:"incompatible",index,row}))
    ];
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
    const rows=dependencyRows();
    const selection=state.dependencySelection;
    const list=relationList(selection.kind);
    const record=list[selection.index];
    const master=el("div",{class:"bl-master"},
      el("div",{class:"bl-master-head"},el("strong",{},"Module relations"),
        el("button",{type:"button",onclick:()=>addDependency("dependency"),title:"Add native dependency"},"+ Dep"),
        el("button",{type:"button",onclick:()=>addDependency("community"),title:"Add BLSE/BUTR dependency metadata"},"+ BLSE"),
        el("button",{type:"button",onclick:()=>addDependency("loadAfter"),title:"Force another module to load after this module"},"+ After"),
        el("button",{type:"button",onclick:()=>addDependency("incompatible"),title:"Add incompatible module"},"+ Inc")),
      el("div",{class:"bl-list"},...rows.map(item=>{
        const active=item.kind===selection.kind&&item.index===selection.index;
        const label=item.kind==="dependency"?"Native dependency":item.kind==="community"?`BLSE ${item.row.order||"metadata"}`:item.kind==="loadAfter"?"Loads after this":"Incompatible";
        const version=item.row.dependentVersion||item.row.version||"";
        const flags=item.kind==="community"?[item.row.optional?"optional":"",item.row.incompatible?"incompatible":""].filter(Boolean).join(" · "):"";
        return el("button",{type:"button",class:`bl-item${active?" active":""}`,onclick:()=>{state.dependencySelection={kind:item.kind,index:item.index};render()}},
          item.row.id||"(new module)",el("small",{},label+(version?` · ${version}`:"")+(flags?` · ${flags}`:"")));
      }))
    );
    let detail;
    if(!record)detail=el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"Select or add a module relation."));
    else if(selection.kind==="community")detail=el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.id||"New BLSE dependency metadata"),
        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeDependency},"Remove")),
        el("div",{class:"bl-grid"},
          ...fieldRow("Module ID",textInput(record.id,value=>record.id=value)),
          ...fieldRow("Order",select(record.order||"",[["","No ordering edge"],["LoadBeforeThis","Dependency loads before this module"],["LoadAfterThis","Dependency loads after this module"]],value=>record.order=value)),
          ...fieldRow("Version / range",textInput(record.version,value=>record.version=value,{placeholder:"v2.0.* or v2.0.0-v2.3.*"})),
          ...fieldRow("Optional",checkbox(record.optional,value=>record.optional=value)),
          ...fieldRow("Incompatible",checkbox(record.incompatible,value=>record.incompatible=value))
        ),
        el("div",{class:"bl-note"},"BLSE/BUTR community metadata is evaluated before duplicate native dependency rows. Required rows can load either before or after this module; optional rows constrain order only when otherwise enabled. Unknown attributes on existing rows are preserved.")));
    else if(selection.kind==="incompatible")detail=el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.id||"New incompatible module"),
        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeDependency},"Remove")),
        el("div",{class:"bl-grid"},...fieldRow("Module ID",textInput(record.id,value=>record.id=value))),
        el("div",{class:"bl-note"},"If this module is enabled too, Bannerlord treats the relation as incompatible. New rows use the current <Module Id=…> shape; older existing rows keep their original element shape.")));
    else if(selection.kind==="loadAfter")detail=el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.id||"New inverse dependency"),
        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeDependency},"Remove")),
        el("div",{class:"bl-grid"},...fieldRow("Module ID",textInput(record.id,value=>record.id=value))),
        el("div",{class:"bl-note"},"Bannerlord will force this module to load after the current module. This is an ordering constraint, not a request to enable the target module.")));
    else detail=el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.id||"New dependency"),
        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeDependency},"Remove")),
        el("div",{class:"bl-grid"},
          ...fieldRow("Module ID",textInput(record.id,value=>record.id=value)),
          ...fieldRow("Dependent version",textInput(record.dependentVersion,value=>record.dependentVersion=value,{placeholder:"Optional"})),
          ...fieldRow("Optional",checkbox(record.optional,value=>record.optional=value))
        ),
        el("div",{class:"bl-note"},"Optional dependencies constrain order only when already enabled; Lexeditor Play does not auto-enable an optional module merely because it is installed. Unknown dependency attributes are preserved when an existing row is edited.")
      ));
    main.replaceChildren(el("div",{class:"bl-split"},master,detail));
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
        el("h2",{},"Included game types"),renderGameTypes(record)
      ));
    main.replaceChildren(el("div",{class:"bl-split"},master,detail));
  }
