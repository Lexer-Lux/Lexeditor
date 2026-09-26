"use strict";

const BLUI={
  pagedListDetail:LexeditorUI.pagedListDetail,
  columnList:LexeditorUI.columnList,
  detailPanel:LexeditorUI.detailPanel,
  detailSection:LexeditorUI.detailSection,
  detailField:LexeditorUI.detailField,
  readonlyField:LexeditorUI.readonlyField,
  infoHelp:LexeditorUI.infoHelp,
  settingsColumns:LexeditorUI.settingsColumns,
  pager:LexeditorUI.pager,
  panelLayout:LexeditorUI.panelLayout,
  tabbedPanel:LexeditorUI.tabbedPanel,
  infoIcon:LexeditorUI.infoIcon,
  logView:LexeditorUI.logView
};
state.uiTables=state.uiTables||{};
state.tweakPage=state.tweakPage||0;
state.gauntletView=state.gauntletView||"files";
state.moduleDataView=state.moduleDataView||"files";

function uiState(key){
  return state.uiTables[key]||(state.uiTables[key]={page:0,pageSize:12,selected:null,query:"",sort:{key:"",dir:1}});
}
function uiText(value){
  return BLUI.readonlyField(value===undefined||value===null||value===""?"—":String(value));
}
function uiButton(label,onclick,{danger=false,disabled=false,title=""}={}){
  return el("button",{type:"button",class:danger?"bannerlord-danger":"",disabled,title,onclick},label);
}
function uiLoading(title,message){
  return BLUI.loadingPanel({label:`${title}: ${message}`});
}
function uiEmpty(title,message,actions=[]){
  return BLUI.detailPanel({icon:BLUI.infoIcon(),title,meta:"Nothing to edit",actions,
    body:[BLUI.detailSection({title:"STATUS",body:[BLUI.detailField({label:"State",control:uiText(message)})]})]});
}
function uiError(title,message){
  return BLUI.detailPanel({icon:BLUI.infoIcon(),title,meta:"Problem",
    body:[BLUI.detailSection({title:"ERROR",body:[BLUI.detailField({label:"What happened",control:uiText(message),
      help:BLUI.infoHelp("This is the specific failure returned by the Bannerlord editor. Correct the project or installation problem, then reopen the page.")})]})]});
}
function textField(label,value,change,help,attrs={}){
  return BLUI.detailField({label,control:textInput(value,change,attrs),help:help?BLUI.infoHelp(help):null});
}
function boolField(label,value,change,help){
  return BLUI.detailField({label,control:checkbox(value,change),dataType:"BOOL",help:help?BLUI.infoHelp(help):null});
}
function numberField(label,value,change,{min,max,step="any",help}={}){
  const attrs={step};if(min!==undefined)attrs.min=min;if(max!==undefined)attrs.max=max;
  return BLUI.detailField({label,control:numberInput(value,change,attrs),min,max,help:help?BLUI.infoHelp(help):null});
}
function selectField(label,value,choices,change,help){
  return BLUI.detailField({label,control:select(value,choices,change),dataType:"ENUM",help:help?BLUI.infoHelp(help):null});
}
function readField(label,value,help){
  return BLUI.detailField({label,control:uiText(value),help:help?BLUI.infoHelp(help):null});
}
function cellSelect(value,choices,commit){
  const node=el("select",{"aria-label":"Edit table value"});
  for(const [key,label] of choices){const option=el("option",{value:key},label);option.selected=String(key)===String(value);node.append(option)}
  node.onchange=()=>commit(node.value);
  node.onkeydown=event=>{if(event.key==="Escape"){event.preventDefault();commit(undefined)}};
  return node;
}
function cellNumber(value,commit,{min,max,step="any",integer=false}={}){
  const attrs={type:"number",value:Number(value),step,"aria-label":"Edit numeric table value"};
  if(min!==undefined)attrs.min=min;if(max!==undefined)attrs.max=max;
  const node=el("input",attrs);
  const done=()=>{if(node.value===""){commit(undefined);return}let next=Number(node.value);if(!Number.isFinite(next)){commit(undefined);return}
    if(integer)next=Math.round(next);if(min!==undefined)next=Math.max(Number(min),next);if(max!==undefined)next=Math.min(Number(max),next);commit(next)};
  node.onchange=done;
  node.onkeydown=event=>{if(event.key==="Enter"){event.preventDefault();done()}else if(event.key==="Escape"){event.preventDefault();commit(undefined)}};
  return node;
}
function cellBool(value,commit){
  const node=el("input",{type:"checkbox",checked:!!value,"aria-label":"Edit boolean table value"});
  node.onchange=()=>commit(node.checked);
  node.onkeydown=event=>{if(event.key==="Escape"){event.preventDefault();commit(undefined)}};
  return node;
}
function filterSortRows(rows,key){
  const ui=uiState(key),needle=String(ui.query||"").trim().toLocaleLowerCase();
  let out=needle?rows.filter(row=>String(row.searchText||Object.values(row).filter(value=>typeof value!=="object").join(" ")).toLocaleLowerCase().includes(needle)):rows.slice();
  const sortKey=ui.sort?.key,dir=ui.sort?.dir||1;
  if(sortKey)out=out.map((row,index)=>({row,index})).sort((a,b)=>{
    const left=a.row[sortKey],right=b.row[sortKey];
    const result=typeof left==="number"&&typeof right==="number"?left-right:String(left??"").localeCompare(String(right??""),undefined,{numeric:true,sensitivity:"base"});
    return result?result*dir:a.index-b.index;
  }).map(item=>item.row);
  return out;
}
function tableView({key,rows,keyOf,columns,detail,noun="records",placeholder="Search…",selected,setSelected,filters=[],emptyDetail}){
  const ui=uiState(key),prepared=filterSortRows(rows,key);
  if(selected===undefined||selected===null)selected=ui.selected;
  const available=new Set(prepared.map(keyOf));
  if(selected!==null&&!available.has(selected))selected=prepared.length?keyOf(prepared[0]):null;
  ui.selected=selected;
  return BLUI.pagedListDetail({addDisabledReason:"Bannerlord mods can add new XML objects, but Lexeditor only edits the ones the game and your mods already define. Adding a record is not supported yet.",
    rows:prepared,key:keyOf,slots:false,page:ui.page,pageSize:ui.pageSize,selected,noun,
    splitKey:`bannerlord-${key}`,
    search:{key:`bannerlord-${key}`,value:ui.query,placeholder,label:`Search ${noun}`,change:value=>{ui.query=value;ui.page=0;render()}},
    filters,
    master:({rows:shown,selected:picked,select})=>BLUI.columnList({
      rows:shown,key:keyOf,selected:picked,select,sortState:ui.sort,
      sort:columnKey=>{ui.sort=ui.sort.key===columnKey?{key:columnKey,dir:-ui.sort.dir}:{key:columnKey,dir:1};ui.page=0;render()},
      columns,refresh:()=>{render();refresh()},"aria-label":`Bannerlord ${noun}`
    }),
    detail,
    emptyDetail:emptyDetail||(()=>uiEmpty(`No ${noun}`,`No ${noun} match the current search.`)),
    sync:next=>{ui.page=next.page;ui.pageSize=next.pageSize;ui.selected=next.selected;if(next.selected!==null)setSelected?.(next.selected)},
    change:next=>{ui.page=next.page;ui.pageSize=next.pageSize;ui.selected=next.selected;if(next.selected!==null)setSelected?.(next.selected);render()}
  });
}
function bannerlordModLoaderSection(){
  return LexeditorUI.modLoaderSection({
    loader:"Bannerlord's native module loader. Lexeditor deploys one native module and launches Bannerlord with an explicit /singleplayer _MODULES_*...*_MODULES_ loadout.",
    output:"Build + Deploy writes the project's module-owned output under Bannerlord/Modules/<SubModule ID>. Binaries come from MSBuild; XML, GUI and ModuleData assets are synchronized transactionally by Lexeditor.",
    order:"Lexeditor resolves required dependency closure and declared native, BLSE and legacy ordering. Optional dependencies are not enabled merely because they are installed.",
    safety:"Deployment is additive, backs up overwritten module-owned assets, excludes runtime-override JSON and never edits Bannerlord base-game files. Custom MSBuild targets still run with your user permissions.",
    removal:"Stop launching the module and remove its deployed Modules/<SubModule ID> folder to uninstall it. The separate source project is left untouched."
  });
}


function deploymentDependencyText(row){
  let source="Native dependency";
  if(row.origin==="DependedModuleMetadatas")source="BLSE metadata";
  else if(row.origin==="LoadAfterModules")source="Legacy LoadAfterModules";
  else if(String(row.origin||"").startsWith("OptionalDependModules/")||row.origin==="DependedModules/OptionalDependModule")source="Launcher optional dependency";
  const details=[source];
  if(row.order==="LoadBeforeThis")details.push("loads before this");
  else if(row.order==="LoadAfterThis")details.push("loads after this");
  if(row.optional)details.push("optional");
  if(row.incompatible)details.push("incompatible");
  if(row.effective===false)details.push(`shadowed by ${row.shadowedByOrigin||"earlier relation"}`);
  if(row.requiredVersion)details.push(`requires ${row.requiredVersion}`);
  if(row.installedVersion)details.push(`installed ${row.installedVersion}`);
  if(row.versionMatch===true)details.push("version OK");
  else if(row.versionMatch===false)details.push("VERSION MISMATCH");
  return details.join(" · ");
}

function renderInfo(){
  const deployment=state.deployment||{};
  const issues=deployment.issues||[],assets=deployment.assets||{},overrides=deployment.runtimeOverrides||{};
  main.replaceChildren(BLUI.detailPanel({
    className:"lex-information-panel",
    title:deployment.projectName||deployment.moduleId||state.module?.name||"Bannerlord",
    icon:BLUI.infoIcon(),meta:"Setup, deployment & runtime",
    body:[
      BLUI.detailSection({title:"PROJECT & INSTALLATION",body:[
        readField("Project",state.project?.root||"—"),
        readField("Game root",deployment.gameRoot||"Selected Bannerlord installation"),
        readField("Module ID",deployment.moduleId||state.module?.id||"—"),
        readField("Deployed module",deployment.deployedRoot||"Not deployed")
      ]}),
      BLUI.detailSection({title:"SETUP & UPDATE BOUNDARIES",body:[
        readField("Runtime loader","Bannerlord native module system","No third-party loader or runtime helper is installed by this plugin. Bannerlord itself owns the module loader, so there is no Bannerlord helper entry to pin or place in Lexeditor's Updates drawer."),
        readField("Build toolchain","System dotnet SDK","Only the Build page invokes dotnet. Lexeditor does not install or auto-update the machine's .NET SDK. The current shared helper contract is for mandatory runtime helpers and would incorrectly block the editor when an optional build-only SDK is absent; a managed/pinned dotnet toolchain therefore needs shared optional-helper support before Bannerlord can expose it through Updates."),
        readField("Modding Kit schemas","Optional local XmlSchemas","XSD enrichment reads schemas from a locally installed Bannerlord Modding Kit or game toolchain when present. These game/toolkit-owned schemas are not bundled or redistributed; absent or ambiguous schemas fall back to conservative literal editing.")
      ]}),
      bannerlordModLoaderSection(),
      BLUI.detailSection({title:"DEPLOYMENT STATUS",body:[
        readField("Runnable",deployment.runnable?"Yes":"No"),
        readField("Project deployed",deployment.deployed?"Yes":"No"),
        readField("Project/deployed sync",deployment.inSync?"Yes":"No"),
        readField("Descriptor sync",deployment.descriptorInSync?"Yes":"No")
      ]}),
      issues.length?BLUI.detailSection({title:"CURRENT ISSUES",body:issues.map((issue,index)=>readField(`Issue ${index+1}`,issue))}):
        BLUI.detailSection({title:"CURRENT ISSUES",body:[readField("Static checks","No deployment problem detected")]}),
      BLUI.detailSection({title:"VERSIONS",body:[
        readField("Project version",deployment.projectVersion||"—"),
        readField("Deployed version",deployment.deployedVersion||"—")
      ]}),
      BLUI.detailSection({title:"DEPENDENCIES",body:(deployment.dependencies||[]).length?
        deployment.dependencies.map((row,index)=>readField(row.id||`Relation ${index+1}`,deploymentDependencyText(row))):
        [readField("Dependencies","No declared dependency relations")]}),
      BLUI.detailSection({title:"BINARIES",body:(deployment.binaries||[]).length?
        deployment.binaries.map((row,index)=>readField(row.name||`Binary ${index+1}`,row.exists?`${row.size} bytes · ${row.classType||"module assembly"}`:"Missing")):
        [readField("Binaries","No SubModule DLL entries")]}),
      BLUI.detailSection({title:"ASSETS",body:[
        readField("GUI",assets.gui?`${assets.gui.source||0} source · ${assets.gui.deployed||0} deployed · ${assets.gui.inSync?"in sync":"different"}`:"None"),
        readField("ModuleData",assets.moduleData?`${assets.moduleData.source||0} source · ${assets.moduleData.deployed||0} deployed · ${assets.moduleData.inSync?"in sync":"different"}`:"None")
      ]}),
      BLUI.detailSection({title:"RUNTIME OVERRIDES",body:Object.keys(overrides).length?
        Object.entries(overrides).map(([key,row])=>readField(key,row.exists?(row.valid?`${row.keys} keys`:`Invalid JSON: ${row.error||"parse error"}`):"Not present")):
        [readField("Overrides","None deployed")]})
    ]
  }));
}

state.moduleView=state.moduleView||"metadata";
state.skillView=state.skillView||"definitions";

function wrapCurrentViewInTabs({tabs,active,label,change}){
  const content=[...main.childNodes];
  main.replaceChildren(BLUI.tabbedPanel({tabs,active,label,change,content}));
}
function renderModuleArea(){
  const renderers={metadata:renderModule,dependencies:renderDependencies,submodules:renderSubmodules,xmls:renderXmls};
  (renderers[state.moduleView]||renderModule)();
  wrapCurrentViewInTabs({
    tabs:[{id:"metadata",label:"Metadata"},{id:"dependencies",label:"Dependencies"},{id:"submodules",label:"Submodules"},{id:"xmls",label:"XML"}],
    active:state.moduleView,label:"Module structure",
    change:value=>{state.moduleView=value;render()}
  });
}
function renderSkillsArea(){
  const renderers={definitions:renderSkills,effects:renderEffects,perks:renderPerks,xp:renderXpSources};
  (renderers[state.skillView]||renderSkills)();
  wrapCurrentViewInTabs({
    tabs:[{id:"definitions",label:"Skills"},{id:"effects",label:"Effects"},{id:"perks",label:"Perks"},{id:"xp",label:"XP Sources"}],
    active:state.skillView,label:"Skill overhaul data",
    change:value=>{state.skillView=value;render()}
  });
}
