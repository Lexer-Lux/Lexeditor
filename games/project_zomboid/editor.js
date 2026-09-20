"use strict";
const main=document.getElementById("main");
let tab="metadata",metadata=null,animationMeshes={rows:[],errors:[]},items={rows:[],errors:[]},evolved={rows:[],errors:[]},crafts={rows:[],errors:[]},fixings={rows:[],errors:[]},fluids={rows:[],errors:[]},vehicles={rows:[],errors:[]},sounds={rows:[],errors:[]},models={rows:[],errors:[]},mannequins={rows:[],errors:[]},timedActions={rows:[],errors:[]},scripts={rows:[],counts:{},errors:[]},datamap={rows:[]},deployment=null,shell=null;
const shellTabs=[
  {id:"metadata",label:"Mod Metadata"},
  {id:"animationmeshes",label:"Animation Meshes"},
  {id:"items",label:"Items"},
  {id:"evolved",label:"Evolved Recipes"},
  {id:"crafts",label:"Craft Recipes"},
  {id:"fixing",label:"Fixing"},
  {id:"fluids",label:"Fluids"},
  {id:"vehicles",label:"Vehicles"},
  {id:"sounds",label:"Sounds"},
  {id:"models",label:"Models"},
  {id:"mannequins",label:"Mannequins"},
  {id:"timedactions",label:"Timed Actions"},
  {id:"scripts",label:"Scripts"},
];
const editorTabs=new Map(shellTabs.map(row=>[row.label,row.id]));
const mapState={page:0,query:"",status:"",sort:["filename",1]};
const scriptState={selected:null,page:0,pageSize:15,query:"",sort:{key:"name",dir:1}};
async function api(path,options={}){const response=await fetch(path,{...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});let payload={};try{payload=await response.json()}catch{}if(!response.ok)throw new Error(payload.error||`Request failed (${response.status})`);return payload}
function setStatus(message,error=false){LexeditorUI.showToast?.(message,error)}
async function reload(){try{[metadata,animationMeshes,items,evolved,crafts,fixings,fluids,vehicles,sounds,models,mannequins,timedActions,scripts,datamap,deployment]=await Promise.all([api("/api/mod-info"),api("/api/animationmeshes"),api("/api/items"),api("/api/evolvedrecipes"),api("/api/craftrecipes"),api("/api/fixings"),api("/api/fluids"),api("/api/vehicles"),api("/api/sounds"),api("/api/models"),api("/api/mannequins"),api("/api/timedactions"),api("/api/zedscript"),api("/api/datamap"),api("/api/deployment")]);render()}catch(error){setStatus(error.message,true);renderLoadError(error)}}
function renderLoadError(error){main.replaceChildren(LexeditorUI.detailPanel({className:"lex-information-panel",title:"Project Zomboid could not load",identity:null,meta:"Plugin load error",body:[LexeditorUI.detailSection({title:"ERROR",body:[sharedReadonly("Message",error.message||String(error),"Resolve this project/install problem, then reload the plugin.")]} )]}))}
function renderMetadata(){
  const row={fields:metadata.fields,duplicateKeys:metadata.duplicateKeys},readers={};
  const build=spec=>{const value=sharedControl(row,spec);if(value.read)readers[spec.key]=value.read;return value.field};
  const sections=metadataSpecs.map(group=>LexeditorUI.detailSection({title:group.title,body:group.fields.map(build)}));
  const save=LexeditorUI.el("button",{type:"button",class:"lex-command-primary",onclick:()=>saveMetadata(readers)},"Save Metadata");
  main.replaceChildren(LexeditorUI.detailPanel({className:"pz-metadata",title:metadata.fields.name||"Mod Metadata",identity:null,meta:metadata.path,body:[
    LexeditorUI.detailSection({title:"SOURCE",body:[sharedReadonly("File",metadata.path,"Build 42 mod.info source. Lexeditor patches modeled keys and preserves unrelated lines.")]}),
    ...sections,
    LexeditorUI.detailSection({title:"PRESERVATION",body:[
      sharedReadonly("Unmodeled Lines",String(metadata.unmodeledLines),"Non-empty lines outside the modeled scalar keys are preserved unless the file itself is externally changed."),
      sharedReadonly("Duplicate Keys",metadata.duplicateKeys.length?metadata.duplicateKeys.join(", "):"None","Duplicated keys are shown but their controls are disabled so Lexeditor cannot make an ambiguous write."),
    ]}),
    LexeditorUI.detailSection({title:"ACTIONS",body:[LexeditorUI.el("div",{class:"pz-shared-actions"},save)]}),
  ]}));
}
async function saveMetadata(readers){const edits={};for(const [key,read] of Object.entries(readers)){const value=read();if(String(value)!==String(metadata.fields?.[key]??""))edits[key]=value}if(!Object.keys(edits).length){setStatus("No metadata changes to save");return}try{metadata=await api("/api/mod-info/save",{method:"POST",body:JSON.stringify({sha256:metadata.sha256,edits})});setStatus("Metadata saved");await reload()}catch(error){setStatus(error.message,true)}}
const structuredState=Object.fromEntries(["animationmeshes","items","evolved","crafts","fixing","fluids","vehicles","sounds","models","mannequins","timedactions"].map(id=>[id,{selected:null,page:0,pageSize:15,query:"",sort:{key:"id",dir:1}}]));
const boolField=(key,label,help,extra={})=>({key,label,type:"bool",help,...extra});
const textField=(key,label,help,extra={})=>({key,label,type:"text",help,...extra});
const numberField=(key,label,help,extra={})=>({key,label,type:"number",help,...extra});
const selectSpec=(key,label,help,choices,extra={})=>({key,label,type:"select",help,choices,...extra});
const metadataSpecs=[
  {title:"IDENTITY",fields:[
    textField("name","Name","Display name shown for the mod in Project Zomboid's mod UI.",{addable:true}),
    textField("id","ID","Stable mod identifier used by dependency and load-order metadata. Build 42 rejects commas, semicolons and equals signs here.",{addable:true}),
    textField("author","Author","Author credit stored in mod.info.",{addable:true}),
    textField("modversion","Mod Version","Version label for this mod. This is author metadata, not the Project Zomboid build requirement.",{addable:true}),
    textField("description","Description","Description shown with the mod's metadata.",{addable:true,type:"textarea"}),
  ]},
  {title:"PRESENTATION",fields:[
    textField("icon","Icon","Icon resource/path declared by mod.info for the mod listing.",{addable:true}),
    textField("url","URL","Project/homepage URL declared by the mod.",{addable:true}),
    textField("category","Category","Native Project Zomboid mod category metadata.",{addable:true}),
  ]},
  {title:"COMPATIBILITY",fields:[
    textField("versionMin","Minimum Game Version","Minimum supported Project Zomboid version. Lexeditor validates dotted versions such as 42.20 or 42.20.4.",{addable:true}),
    textField("versionMax","Maximum Game Version","Maximum supported Project Zomboid version. Leave empty when the mod does not declare an upper bound.",{addable:true}),
    textField("require","Required Mods","Dependency mod IDs passed through to Project Zomboid's native mod loader.",{addable:true}),
    textField("incompatible","Incompatible Mods","Mod IDs declared incompatible with this mod.",{addable:true}),
  ]},
  {title:"LOAD ORDER",fields:[
    textField("loadModAfter","Load After","Mod IDs this mod asks Project Zomboid to load before it.",{addable:true}),
    textField("loadModBefore","Load Before","Mod IDs this mod asks Project Zomboid to load after it.",{addable:true}),
  ]},
];
const structuredConfigs={
  animationmeshes:{title:"Animation Meshes",noun:"animation meshes",save:"/api/animationmeshes/save",saved:"Animation mesh",rows:()=>animationMeshes.rows,limits:"Repeated animation source lists are preserved exactly: animationDirectory and animationPrefix entries stay read-only.",fields:[
    boolField("keepMeshAnimations","Keep Mesh Animations","Controls whether animations already attached to the source mesh are retained when Project Zomboid loads this animation mesh."),
    textField("meshFile","Mesh File","Names the skinned mesh resource used by this animation mesh. Change it only to another valid Project Zomboid mesh resource."),
    textField("postProcess","Post Process","Passes the Build 42 mesh post-processing directive through to the loader. Unknown directives are not invented or normalized."),
  ],summary:row=>[
    sharedReadonly("Animation Directories",String(row.animationDirectoryCount??0),"Repeated animationDirectory entries are deliberately read-only."),
    sharedReadonly("Animation Prefixes",String(row.animationPrefixCount??0),"Repeated animationPrefix entries are deliberately read-only."),
  ]},
  items:{title:"Items",noun:"items",save:"/api/items/save",saved:"Item",rows:()=>items.rows,limits:"Only existing ItemType, Weight, Icon and DisplayCategory scalars are editable; nested, missing and unknown item data is preserved.",fields:[
    selectSpec("ItemType","Item Type","Selects the Build 42 item-type enum used by the engine.",row=>row.itemTypeOptions||[]),
    numberField("Weight","Weight","Item weight used by inventory and encumbrance calculations. The source property must already exist.",{min:0,step:"any"}),
    textField("Icon","Icon","Names the item icon resource shown in inventory UI."),
    textField("DisplayCategory","Display Category","Controls the inventory category label/group used for this item."),
  ]},
  evolved:{title:"Evolved Recipes",noun:"evolved recipes",save:"/api/evolvedrecipes/save",saved:"Evolved recipe",rows:()=>evolved.rows,limits:"Only current top-level scalar properties are patched; unknown and nested evolved-recipe data is preserved.",fields:[
    boolField("AddIngredientIfCooked","Add Ingredient If Cooked","Allows this recipe's ingredient handling when the ingredient is already cooked."),
    textField("AddIngredientSound","Add Ingredient Sound","Names the sound event played when an ingredient is added."),
    textField("BaseItem","Base Item","Names the item used as the recipe's base container or starting item."),
    boolField("CanAddSpicesEmpty","Can Add Spices Empty","Allows spices to be added while the evolved recipe has no regular ingredients."),
    boolField("Cookable","Cookable","Build 42 treats Cookable as a presence-only flag. Lexeditor shows it but does not synthesize or remove it.",{locked:true}),
    numberField("MaxItems","Max Items","Maximum number of ingredients the evolved recipe accepts.",{min:1,step:1,integer:true}),
    numberField("MinimumWater","Minimum Water","Minimum water amount required by the evolved recipe.",{step:"any"}),
    textField("Name","Name Key","Localization/name key used for this evolved recipe."),
    textField("ResultItem","Result Item","Item type produced by the evolved recipe."),
    textField("Template","Template","Template recipe identifier inherited by this record."),
  ]},
  crafts:{title:"Craft Recipes",noun:"craft recipes",save:"/api/craftrecipes/save",saved:"Craft recipe",rows:()=>crafts.rows,limits:"Inputs, outputs, callbacks, mappers and under-typed craftRecipe grammar remain read-only and are preserved exactly. Skill maps use Skill:level;Skill:level.",fields:[
    boolField("AllowBatchCraft","Allow Batch Craft","Allows the recipe to be crafted repeatedly as a batch when the game permits it."),
    textField("AutoLearnAll","Auto Learn All","Semicolon-separated Skill:level requirements; every listed threshold must be satisfied for automatic learning."),
    textField("AutoLearnAny","Auto Learn Any","Semicolon-separated Skill:level requirements; any listed threshold may unlock automatic learning."),
    boolField("CanWalk","Can Walk","Allows the character to keep walking while this recipe's timed action runs."),
    textField("category","Category","Crafting-menu category used to group the recipe."),
    textField("Icon","Icon","Names the icon resource shown for the recipe."),
    numberField("ResearchSkillLevel","Research Skill Level","Skill level gate used by the recipe's research/learning behavior. Negative sentinel values are preserved.",{step:1,integer:true}),
    textField("SkillRequired","Skill Required","Semicolon-separated Skill:level requirements required to craft the recipe."),
    textField("tags","Tags","Semicolon/comma data used by Build 42 to classify this recipe. Lexeditor does not invent tags."),
    numberField("time","Time","Base timed-action duration declared by the recipe.",{step:1,integer:true}),
    textField("timedAction","Timed Action","Names the timed-action behavior used while the recipe is performed."),
    textField("Tooltip","Tooltip Key","Localization key for the crafting tooltip."),
  ],summary:row=>[
    sharedReadonly("Inputs",row.hasInputs?"Present":"Not detected","Input blocks remain read-only and are preserved."),
    sharedReadonly("Outputs",row.hasOutputs?"Present":"Not detected","Output blocks remain read-only and are preserved."),
  ]},
  fixing:{title:"Fixing",noun:"fixing records",save:"/api/fixings/save",saved:"Fixing record",rows:()=>fixings.rows,limits:"Require, Fixer, GlobalItem and other repair grammar remain read-only and are preserved exactly.",fields:[
    numberField("ConditionModifier","Condition Modifier","Multiplier applied by this fixing definition when restoring condition.",{step:"any"}),
  ]},
  fluids:{title:"Fluids",noun:"fluids",save:"/api/fluids/save",saved:"Fluid",rows:()=>fluids.rows,limits:"Properties, Categories, blend lists, Poison blocks and unknown fluid data remain read-only and are preserved.",fields:[
    textField("ColorReference","Color Reference","Names the Build 42 color reference used to render the fluid."),
    textField("DisplayName","Display Name Key","Localization key used for the fluid's display name."),
  ]},
  vehicles:{title:"Vehicles",noun:"vehicles",save:"/api/vehicles/save",saved:"Vehicle",rows:()=>vehicles.rows,limits:"Parts, areas, passengers, wheels, models, physics geometry, arrays and unknown vehicle data remain read-only and are preserved.",fields:[
    numberField("animalTrailerSize","Animal Trailer Size","Capacity/size scalar used by animal-trailer behavior.",{min:0,step:"any"}),
    textField("carMechanicsOverlay","Car Mechanics Overlay","Names the mechanics-overlay resource shown for this vehicle."),
    textField("carModelName","Car Model Name","Names the vehicle model identifier used by the car definition."),
    numberField("engineForce","Engine Force","Drive-force scalar; higher values generally increase acceleration, with final behavior also depending on mass and gearing.",{min:0,step:"any"}),
    numberField("engineIdleSpeed","Engine Idle Speed","Engine idle-speed scalar used by the vehicle simulation.",{min:0,step:"any"}),
    numberField("engineLoudness","Engine Loudness","Relative engine noise scalar used by vehicle sound/noise behavior.",{min:0,step:1,integer:true}),
    numberField("engineQuality","Engine Quality","Engine-quality scalar used by vehicle mechanics and condition behavior.",{min:0,step:1,integer:true}),
    numberField("engineRepairLevel","Engine Repair Level","Mechanics/repair-level scalar associated with engine repair.",{min:0,step:1,integer:true}),
    textField("engineRPMType","Engine RPM Type","Names the RPM behavior/profile used by the vehicle engine."),
    numberField("gearRatioCount","Gear Ratio Count","Number of gear ratios declared by the vehicle. Build 42 currently accepts this editor range of 1–9.",{min:1,max:9,step:1,integer:true}),
    boolField("hasLighter","Has Lighter","Controls whether the vehicle exposes the built-in lighter feature."),
    boolField("isSmallVehicle","Small Vehicle","Marks the definition as a small vehicle for Build 42 vehicle behavior."),
  ]},
  sounds:{title:"Sounds",noun:"sounds",save:"/api/sounds/save",saved:"Sound",rows:()=>sounds.rows,limits:"Audio clip child blocks, file paths, distance, reverb, volume and unknown sound data remain read-only and are preserved.",fields:[
    textField("category","Category","Sound category used by Project Zomboid's audio system."),
    boolField("is3D","3D Sound","Enables spatial/3D positioning for this sound definition."),
    boolField("loop","Loop","Repeats the sound while its emitter remains active."),
    selectSpec("master","Master","Selects the master audio bus/category for this sound.",row=>row.masterOptions||["Primary","Ambient","Music","VehicleEngine"]),
    numberField("maxInstancesPerEmitter","Max Instances Per Emitter","Maximum concurrent copies this sound may play from one emitter.",{step:1,integer:true}),
  ],summary:row=>[
    sharedReadonly("Clips",row.hasClips?"Present":"Not detected","Clip child blocks remain read-only and are preserved."),
  ]},
  models:{title:"Models",noun:"models",save:"/api/models/save",saved:"Model",rows:()=>models.rows,limits:"Mesh/texture paths, references, color/transform data, bone weights, attachments and unknown model data remain read-only and are preserved.",fields:[
    selectSpec("cullFace","Cull Face","Selects which polygon faces the model renderer culls.",row=>row.cullFaceOptions||["Back","Front","None"]),
    boolField("invertX","Invert X","Mirrors the model along the X axis when Build 42 loads it."),
    textField("postProcess","Post Process","Passes the model post-processing directive through to the loader."),
    numberField("scale","Scale","Scale multiplier applied to the model.",{step:"any"}),
    textField("shader","Shader","Names the shader used to render this model."),
    boolField("static","Static","Marks the model as static rather than dynamically skinned/animated."),
    boolField("undoCoreScale","Undo Core Scale","Controls Build 42's core-scale compensation for the model."),
  ],summary:row=>[
    sharedReadonly("Attachments",row.hasAttachments?"Present":"Not detected","Attachment child blocks remain read-only and are preserved."),
  ]},
  mannequins:{title:"Mannequins",noun:"mannequins",save:"/api/mannequins/save",saved:"Mannequin",rows:()=>mannequins.rows,limits:"The referenced model block and unknown mannequin data remain read-only and are preserved.",fields:[
    textField("animSet","Animation Set","Animation set assigned to the mannequin."),
    textField("animState","Animation State","Animation state the mannequin uses within its animation set."),
    boolField("female","Female","Selects the mannequin's female body/animation branch."),
    textField("outfit","Outfit","Outfit identifier applied to the mannequin."),
    textField("pose","Pose","Pose identifier used when displaying the mannequin."),
    textField("texture","Texture","Body/skin texture identifier used by the mannequin."),
  ],summary:row=>[
    sharedReadonly("Model Reference",row.modelReference||"Not present","The referenced model block is read-only in this editor."),
  ]},
  timedactions:{title:"Timed Actions",noun:"timed actions",save:"/api/timedactions/save",saved:"Timed action",rows:()=>timedActions.rows,limits:"Sound/model references, animation variables, muscle-strain data and other timed-action grammar remain read-only and are preserved.",fields:[
    textField("actionAnim","Action Animation","Animation state/action name used while this timed action runs."),
  ]},
};
function sharedReadonly(label,value,help){return LexeditorUI.detailField({label:label.toUpperCase(),control:LexeditorUI.readonlyField(value),help:LexeditorUI.infoHelp(help)})}
function sharedControl(row,spec){
  const raw=row.fields?.[spec.key]??"",present=raw!=="",ambiguous=(row.duplicateKeys||[]).includes(spec.key);
  const disabled=(!present&&spec.addable!==true)||ambiguous||spec.locked===true;
  let control,read=null,dataType="STRING";
  if(spec.type==="bool"){
    control=LexeditorUI.el("input",{type:"checkbox",checked:String(raw).toLowerCase()==="true",disabled,"aria-label":spec.label});
    dataType="BOOL";if(!disabled)read=()=>control.checked?"true":"false";
  }else if(spec.type==="select"){
    const values=[...(typeof spec.choices==="function"?spec.choices(row):spec.choices||[])];
    if(raw&&!values.includes(raw))values.unshift(raw);
    control=LexeditorUI.el("select",{disabled,"aria-label":spec.label},...values.map(value=>{const option=LexeditorUI.el("option",{value},value);option.selected=value===raw;return option}));
    dataType="ENUM";if(!disabled)read=()=>control.value;
  }else if(spec.type==="textarea"){
    control=LexeditorUI.el("textarea",{disabled,"aria-label":spec.label});control.value=raw;
    if(!disabled)read=()=>control.value;
  }else{
    const attrs={type:spec.type==="number"?"number":"text",value:raw,disabled,"aria-label":spec.label};
    if(spec.min!==undefined)attrs.min=spec.min;if(spec.max!==undefined)attrs.max=spec.max;if(spec.step!==undefined)attrs.step=spec.step;
    control=LexeditorUI.el("input",attrs);
    dataType=spec.type==="number"?(spec.integer?"INT":"FLOAT"):"STRING";
    if(!disabled)read=()=>control.value;
  }
  let help=spec.help;
  if(!present)help+=spec.addable===true?" Saving a non-empty value adds this key to mod.info.":" This property is absent in this record, so Lexeditor leaves it absent.";
  else if(ambiguous)help+=" This property appears more than once, so editing is disabled to avoid an ambiguous write.";
  return{field:LexeditorUI.detailField({label:spec.label.toUpperCase(),control,dataType,min:spec.min,max:spec.max,help:LexeditorUI.infoHelp(help)}),read};
}
async function saveStructured(kind,row,readers){
  const config=structuredConfigs[kind],edits={};
  for(const [key,read] of Object.entries(readers)){const value=read();if(String(value)!==String(row.fields?.[key]??""))edits[key]=value}
  if(!Object.keys(edits).length){setStatus("No changes to save");return}
  try{
    await api(config.save,{method:"POST",body:JSON.stringify({path:row.path,module:row.module,id:row.id,sha256:row.sha256,edits})});
    setStatus(config.saved+" saved");await reload();
  }catch(error){setStatus(error.message,true)}
}
function structuredDetail(kind,row){
  const config=structuredConfigs[kind],readers={},fields=config.fields.map(spec=>{const built=sharedControl(row,spec);if(built.read)readers[spec.key]=built.read;return built.field});
  const limits=sharedReadonly("Unmodeled Data","Preserved",config.limits);
  const extras=config.summary?config.summary(row):[];
  const save=LexeditorUI.el("button",{type:"button",class:"lex-command-primary",disabled:Object.keys(readers).length===0,onclick:()=>saveStructured(kind,row,readers)},"Save "+config.saved);
  return LexeditorUI.detailPanel({className:"pz-record-detail",title:row.fullType||row.id,identity:null,meta:row.path,body:[
    LexeditorUI.detailSection({title:"SOURCE",body:[sharedReadonly("Module",row.module||"—","The ZedScript module containing this record."),sharedReadonly("File",row.path,"Project-relative source file. Saves patch this file atomically.")]}),
    LexeditorUI.detailSection({title:"PROPERTIES",body:fields}),
    LexeditorUI.detailSection({title:"PRESERVATION",body:[limits,...extras]}),
    LexeditorUI.detailSection({title:"ACTIONS",body:[LexeditorUI.el("div",{class:"pz-shared-actions"},save)]}),
  ]});
}
function structuredRows(kind){
  const config=structuredConfigs[kind],state=structuredState[kind],query=state.query.trim().toLocaleLowerCase(),rows=[...(config.rows()||[])];
  const filtered=rows.filter(row=>!query||[row.id,row.fullType,row.module,row.path].some(value=>String(value||"").toLocaleLowerCase().includes(query)));
  const {key,dir}=state.sort;
  return filtered.sort((a,b)=>dir*String(a[key]??"").localeCompare(String(b[key]??""),undefined,{numeric:true}));
}
function renderStructured(kind){
  const config=structuredConfigs[kind],state=structuredState[kind],rows=structuredRows(kind);
  if(state.selected&&!rows.some(row=>row.key===state.selected))state.selected=null;
  if(!state.selected&&rows.length)state.selected=rows[0].key;
  const view=LexeditorUI.pagedListDetail({rows,key:row=>row.key,selected:state.selected,page:state.page,pageSize:state.pageSize,noun:config.noun,className:"pz-record-layout",splitKey:"project-zomboid-"+kind,rowsKey:"project-zomboid-"+kind,
    search:{key:"project-zomboid-"+kind,value:state.query,label:"Search "+config.title,change:value=>{state.query=value;state.page=0;renderStructured(kind)}},
    sync:next=>{state.page=next.page;state.pageSize=next.pageSize;if(next.selected!==null)state.selected=next.selected},
    change:next=>{state.page=next.page;state.pageSize=next.pageSize;if(next.selected!==null)state.selected=next.selected;renderStructured(kind)},
    master:({rows:shown,selected,select})=>LexeditorUI.columnList({rows:shown,key:row=>row.key,selected,select,sortState:state.sort,
      sort:key=>{state.sort=state.sort.key===key?{key,dir:-state.sort.dir}:{key,dir:1};state.page=0;renderStructured(kind)},
      class:"pz-record-table","aria-label":config.title,
      columns:[{key:"id",label:"Record",sortable:true},{key:"module",label:"Module",sortable:true},{key:"path",label:"File",sortable:true}]}),
    detail:row=>structuredDetail(kind,row)});
  main.replaceChildren(view);shell?.refresh?.();
}
function renderAnimationMeshes(){renderStructured("animationmeshes")}
function renderItems(){renderStructured("items")}
function renderEvolved(){renderStructured("evolved")}
function renderCrafts(){renderStructured("crafts")}
function renderFixings(){renderStructured("fixing")}
function renderFluids(){renderStructured("fluids")}
function renderVehicles(){renderStructured("vehicles")}
function renderSounds(){renderStructured("sounds")}
function renderModels(){renderStructured("models")}
function renderMannequins(){renderStructured("mannequins")}
function renderTimedActions(){renderStructured("timedactions")}
const scriptEditorTabs={animationsMesh:"animationmeshes",item:"items",evolvedrecipe:"evolved",craftRecipe:"crafts",fixing:"fixing",fluid:"fluids",vehicle:"vehicles",sound:"sounds",model:"models",mannequin:"mannequins",timedAction:"timedactions"};
function scriptKey(row){return [row.path,row.module,row.kind,row.name].join("\u001f")}
function scriptRows(){
  const query=scriptState.query.trim().toLocaleLowerCase(),rows=(scripts.rows||[]).map(row=>({...row,key:scriptKey(row),editor:row.editable?"Structured editor":"Read-only viewer"}));
  const filtered=rows.filter(row=>!query||[row.kind,row.name,row.module,row.path,row.editor].some(value=>String(value||"").toLocaleLowerCase().includes(query)));
  const {key,dir}=scriptState.sort;return filtered.sort((a,b)=>dir*String(a[key]??"").localeCompare(String(b[key]??""),undefined,{numeric:true}));
}
function openScriptRecord(row){
  const target=scriptEditorTabs[row.kind];if(!target)return;
  const source=structuredConfigs[target]?.rows?.()||[];
  const match=source.find(candidate=>candidate.path===row.path&&candidate.module===row.module&&candidate.id===row.name);
  if(match)structuredState[target].selected=match.key;
  navigate(target);
}
function scriptDetail(row){
  const target=scriptEditorTabs[row.kind],body=[LexeditorUI.detailSection({title:"RECORD",body:[
    sharedReadonly("Kind",row.kind,"Top-level Build 42 ZedScript family detected by the structural inventory."),
    sharedReadonly("Name",row.name,"Record name as declared in the script."),
    sharedReadonly("Module",row.module,"ZedScript module containing the record."),
    sharedReadonly("File",row.path,"Project-relative script file containing the record."),
    sharedReadonly("Integration",row.editable?"Partial · structured editor":"Partial · read-only viewer",row.editable?"A structured editor exists, but unsupported fields remain preserved rather than exposed.":"Lexeditor can identify this record but has no structured editor for its fields yet."),
  ]})];
  if(target)body.push(LexeditorUI.detailSection({title:"ACTIONS",body:[LexeditorUI.el("div",{class:"pz-shared-actions"},LexeditorUI.el("button",{type:"button",class:"lex-command-primary",onclick:()=>openScriptRecord(row)},"Open Structured Editor"))]}));
  if((scripts.errors||[]).length)body.push(LexeditorUI.detailSection({title:"CURRENT PROBLEMS",body:[sharedReadonly("Parser Errors",String(scripts.errors.length),"At least one script file failed closed. The affected file is left untouched and is also reported in Data Map.")]}));
  return LexeditorUI.detailPanel({title:row.name,identity:null,meta:row.kind,body});
}
function renderScripts(){
  const rows=scriptRows();if(scriptState.selected&&!rows.some(row=>row.key===scriptState.selected))scriptState.selected=null;if(!scriptState.selected&&rows.length)scriptState.selected=rows[0].key;
  const view=LexeditorUI.pagedListDetail({rows,key:row=>row.key,selected:scriptState.selected,page:scriptState.page,pageSize:scriptState.pageSize,noun:"script records",className:"pz-script-layout",splitKey:"project-zomboid-scripts",rowsKey:"project-zomboid-scripts",
    search:{key:"project-zomboid-scripts",value:scriptState.query,label:"Search Build 42 script records",change:value=>{scriptState.query=value;scriptState.page=0;renderScripts()}},
    sync:next=>{scriptState.page=next.page;scriptState.pageSize=next.pageSize;if(next.selected!==null)scriptState.selected=next.selected},
    change:next=>{scriptState.page=next.page;scriptState.pageSize=next.pageSize;if(next.selected!==null)scriptState.selected=next.selected;renderScripts()},
    master:({rows:shown,selected,select})=>LexeditorUI.columnList({rows:shown,key:row=>row.key,selected,select,sortState:scriptState.sort,
      sort:key=>{scriptState.sort=scriptState.sort.key===key?{key,dir:-scriptState.sort.dir}:{key,dir:1};scriptState.page=0;renderScripts()},
      class:"pz-script-table","aria-label":"Build 42 Script Inventory",columns:[{key:"kind",label:"Kind",sortable:true},{key:"name",label:"Record",sortable:true},{key:"module",label:"Module",sortable:true},{key:"path",label:"File",sortable:true}]}),
    detail:scriptDetail});
  main.replaceChildren(view);shell?.refresh?.();
}
function renderDatamap(){const rows=datamap.rows.map(row=>{const editorTargets=String(row.editor||"").split(",").map(value=>value.trim()).filter(value=>editorTabs.has(value)).map(label=>({id:editorTabs.get(label),label})),scriptView=String(row.filename||"").endsWith(".txt"),targets=[...editorTargets,...(scriptView?[{id:"scripts",label:"Script Inventory"}]:[])];const editable=editorTargets.length>0;return{filename:row.filename,controls:row.editor||(scriptView?"Script Inventory":"Recognized Build 42 data"),notes:row.notes,status:(editable||scriptView)?"partial":"not-integrated",coverage:editable?"structured":scriptView?"view":"unavailable",targets}});const view=LexeditorUI.dataMap({rows,page:mapState.page,query:mapState.query,status:mapState.status,sort:mapState.sort,open:row=>navigate(row.target),changePage:value=>{mapState.page=value;renderDatamap()},changeQuery:value=>{mapState.query=value;mapState.page=0;renderDatamap()},changeStatus:value=>{mapState.status=value;mapState.page=0;renderDatamap()},changeSort:key=>{mapState.sort=mapState.sort[0]===key?[key,-mapState.sort[1]]:[key,1];renderDatamap()}});mapState.page=view.page;main.replaceChildren(view.content)}
function renderInfo(){
  const target=deployment.target||"<Zomboid user folder>/mods/<project>",state=deployment.deployed?(deployment.owned?"Deployed · owned":"Deployed · external change detected"):"Not deployed";
  const deploy=LexeditorUI.el("button",{type:"button",class:"lex-command-primary",onclick:()=>changeDeployment("/api/deploy")},deployment.deployed?"Redeploy":"Deploy Local Mod");
  const remove=LexeditorUI.el("button",{type:"button",disabled:!deployment.owned,onclick:()=>changeDeployment("/api/undeploy")},"Remove Owned Deployment");
  main.replaceChildren(LexeditorUI.detailPanel({className:"lex-information-panel",title:"Project Zomboid Information",identity:null,meta:"Build 42 setup and local deployment",body:[
    LexeditorUI.detailSection({title:"DEPLOYMENT",body:[
      sharedReadonly("Target",target,"Native local-mod destination under the selected user's Zomboid/mods folder. The installed Steam game tree is never the deployment target."),
      sharedReadonly("Files",String(deployment.fileCount??0),"Number of files currently present in the resolved deployment."),
      sharedReadonly("State",state,"Owned means the deployed file hashes still match Lexeditor's recorded deployment. External changes disable removal/replacement until ownership is safe again."),
      sharedReadonly("Game Source","Read only","The installed Build 42 Steam tree is source material only; Lexeditor does not modify it."),
    ]}),
    LexeditorUI.modLoaderSection({loader:"Project Zomboid native Build 42 mod system.",output:"A full local development mod copy under <user>/Zomboid/mods/<project>.",order:"Project Zomboid owns activation and ordering; mod.info can declare require/incompatible/loadModBefore/loadModAfter relationships.",safety:"The installed Steam game tree is never modified; only the owned local deployment is replaced or removed.",removal:"Remove the owned local deployment; the authoring project is preserved."}),
    LexeditorUI.detailSection({title:"ACTIONS",body:[LexeditorUI.el("div",{class:"pz-shared-actions"},deploy,remove)]}),
  ]}));
}
async function changeDeployment(path){try{deployment=await api(path,{method:"POST",body:"{}"});setStatus(path.endsWith("undeploy")?"Owned deployment removed":"Local mod deployed");await reload()}catch(error){setStatus(error.message,true)}}
function render(){if(tab==="metadata")renderMetadata();else if(tab==="animationmeshes")renderAnimationMeshes();else if(tab==="items")renderItems();else if(tab==="evolved")renderEvolved();else if(tab==="crafts")renderCrafts();else if(tab==="fixing")renderFixings();else if(tab==="fluids")renderFluids();else if(tab==="vehicles")renderVehicles();else if(tab==="sounds")renderSounds();else if(tab==="models")renderModels();else if(tab==="mannequins")renderMannequins();else if(tab==="timedactions")renderTimedActions();else if(tab==="scripts")renderScripts();else if(tab==="datamap")renderDatamap();else if(tab==="info")renderInfo();else renderMetadata();shell?.refresh?.()}
function navigate(value){tab=value;render()}
shell=LexeditorUI.mountShell({
  host:"#lexeditor-shell",
  brand:"LEXEDITOR",
  plugin:{id:"project-zomboid",name:"Project Zomboid",themeName:"project-zomboid",theme:{accent:"#708057"}},
  tabs:shellTabs,
  activeTab:()=>tab,
  navigate,
  help:()=>navigate("datamap"),
  helpActive:()=>tab==="datamap",
  helpTitle:"Open Project Zomboid Data Map",
  info:()=>navigate("info"),
  infoActive:()=>tab==="info",
  infoTitle:"Open Project Zomboid setup and deployment information",
});
void reload().finally(()=>LexeditorUI.finishPluginLoading?.());
