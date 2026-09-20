"use strict";
const {el,list,pagedListDetail,pager,provenanceControl,clone,showAlert,infoHelp}=LexeditorUI;
const $=selector=>document.querySelector(selector);
const state={booting:true,modOnly:false,tab:"items",activeSource:"mine",files:{rows:[],counts:{}},dashboard:null,status:"Ready",items:null,itemSelected:"",itemQuery:"",itemSource:"",itemPage:0,itemPageSize:20,itemEdits:{},shops:null,shopSelected:"",shopQuery:"",shopName:"",shopCategory:"",shopPage:0,shopPageSize:20,shopEdits:{},strings:null,stringTable:null,stringTableId:"",stringSelected:"",stringQuery:"",stringLanguage:"",stringPage:0,stringPageSize:20,stringEdits:{},stringLoadError:"",missions:null,missionSelected:"",missionQuery:"",missionArea:"",missionPage:0,missionPageSize:20,missionEdits:{},vanilla:{items:null,shops:null,strings:null,stringTable:null,missions:null},settings:null,settingEdits:{},loot:null,lootDocument:null,lootDirty:false,lootScript:null,lootScriptEdits:{},dataMap:null,mapQuery:"",mapStatus:"",mapPage:0,dataMapSort:["filename",1]};
const PAGE_SIZE=250;

async function api(path,options){const response=await fetch(path,options);const value=await response.json();if(value.error)throw new Error(value.error);return value;}
// "Mod contents only" keeps the rows this project has actually changed. RDR
// already records every edit against the record's id, so the filter is that
// record set and nothing else.
function modOnlySpec(edits,resetPage){
  return {available:state.activeSource==="mine",value:state.modOnly===true,
    changed:row=>Object.prototype.hasOwnProperty.call(edits,String(row.id)),
    change:value=>{state.modOnly=value;resetPage();render()}};
}
function dirtyCount(){return state.activeSource==="mine"?Object.keys(state.itemEdits).length+Object.keys(state.shopEdits).length+Object.keys(state.stringEdits).length+Object.keys(state.missionEdits).length+Object.keys(state.settingEdits).length+(state.lootDirty?1:0):0;}
function setStatus(text){state.status=text;}
function historyCapture(){return {itemEdits:clone(state.itemEdits),shopEdits:clone(state.shopEdits),stringEdits:clone(state.stringEdits),missionEdits:clone(state.missionEdits),settingEdits:clone(state.settingEdits),lootDocument:clone(state.lootDocument),lootDirty:state.lootDirty};}
function historyRestore(snapshot){state.itemEdits=clone(snapshot.itemEdits||{});state.shopEdits=clone(snapshot.shopEdits||{});state.stringEdits=clone(snapshot.stringEdits||{});state.missionEdits=clone(snapshot.missionEdits||{});state.settingEdits=clone(snapshot.settingEdits||{});state.lootDocument=clone(snapshot.lootDocument);state.lootDirty=!!snapshot.lootDirty;}
function matchingItems(){
  const needle=state.itemQuery.trim().toLowerCase();
  return (state.items?.rows||[]).filter(item=>(!needle||[item.name,item.friendlyName,item.type,item.icon].some(value=>String(value||"").toLowerCase().includes(needle)))&&(!state.itemSource||item.source===state.itemSource));
}
function itemValue(item,field){const key=`${item.id}|${field.field}`;return Object.prototype.hasOwnProperty.call(state.itemEdits,key)?state.itemEdits[key]:field.value;}
function editItem(item,field,value){const key=`${item.id}|${field.field}`;if(value===field.value)delete state.itemEdits[key];else state.itemEdits[key]=value;shell.refresh();}
function selectItem(item){state.itemSelected=item.id;renderItems();}
function recordCell(className,value,title=value){return el("span",{class:`rdr-record-cell ${className}`,title:String(title||"")},String(value||"—"));}
// `description` is prose under the row; `help` is the shared info bubble that
// every other plugin's fields carry. RDR's rows had neither, so nothing on
// the page explained what any of it edits.
function detailField(label,value,help="",bubble=""){const control=value instanceof Node?value:el("span",{},String(value??"—"));return LexeditorUI.detailField({label,control,description:help||"",help:bubble?LexeditorUI.infoHelp(bubble):null});}
function applyControlValue(control,value){if(control.type==="checkbox")control.checked=String(value).toLowerCase()==="true";else control.value=String(value);control.dispatchEvent(new Event(control.type==="checkbox"||control.tagName==="SELECT"?"change":"input",{bubbles:true}));}
function sourceControl(control,current,vanilla,apply,format){if(state.activeSource!=="mine"||vanilla===undefined)return control;return provenanceControl({control,current,vanilla,internal:true,format,apply:value=>{apply(value);applyControlValue(control,value);shell.refresh()}})}
const stringsUI=RDRStringTablesUI({state,api,el,list,pagedListDetail,recordCell,detailField,sourceControl,modOnlySpec,setStatus,shell:()=>shell});
function itemRow(item){return el("div",{class:"rdr-record-row"},recordCell("rdr-record-name",item.friendlyName||item.name||`Item ${item.index}`),recordCell("rdr-record-id",item.name||`#${item.index}`),recordCell("rdr-record-type",item.type),recordCell("rdr-record-source",item.sourceLabel));}
function scalarControl(item,field){
  const value=itemValue(item,field);
  const vanillaItem=state.vanilla.items?.rows?.find(row=>row.id===item.id),vanilla=vanillaItem?.fields?.find(value=>value.field===field.field)?.value;
  let control;if(field.control==="checkbox")control=el("input",{type:"checkbox",checked:String(value).toLowerCase()==="true",disabled:state.activeSource!=="mine",onchange:event=>editItem(item,field,event.target.checked?"true":"false"),"aria-label":field.field});
  else if(field.control==="select")control=el("select",{disabled:state.activeSource!=="mine",onchange:event=>editItem(item,field,event.target.value)},...(field.options||[]).map(option=>el("option",{value:option,selected:String(option)===String(value)},option||"(none)")));
  else if(field.control==="number")control=el("input",{type:"number",value,step:String(field.step??"any"),min:field.minimum,max:field.maximum,disabled:state.activeSource!=="mine",oninput:event=>editItem(item,field,event.target.value)});
  else control=el("input",{type:"text",value,spellcheck:false,disabled:state.activeSource!=="mine",oninput:event=>editItem(item,field,event.target.value)});
  return sourceControl(control,()=>itemValue(item,field),vanilla,next=>editItem(item,field,String(next)));
}
function itemDetail(){
  const item=(state.items?.rows||[]).find(row=>row.id===state.itemSelected);
  if(!item)return el("div",{class:"lex-detail empty"},el("div",{},el("h2",{},"Select an inventory item"),el("p",{},"Edits become full XML overrides in C:\\RDRMod. The installed content.rpf stays unchanged.")));
  // An item's name is the heading, so the heading is where it is typed. It
  // used to be two ordinary rows further down - NAME and FRIENDLYNAME - so
  // the name a reader sees at the top was the one copy they could not
  // change. NAME is the record's key and the override's filename, so it
  // stays read-only, under the heading where the other identities go.
  const fieldNamed=wanted=>item.fields.find(field=>String(field.field).toLowerCase()===wanted);
  const friendly=fieldNamed("friendlyname");
  const rest=item.fields.filter(field=>!["name","friendlyname"].includes(String(field.field).toLowerCase()));
  return LexeditorUI.detailPanel({className:"record-detail item-detail",
    title:(friendly?itemValue(item,friendly):"")||item.friendlyName||item.name||`Item ${item.index}`,
    renameLabel:"Item name",
    renameRecord:state.activeSource==="mine"&&friendly?value=>editItem(item,friendly,value):undefined,
    identity:LexeditorUI.recordId(item.index),
    meta:item.name||"",
    actions:el("span",{class:`badge${item.project?" project":""}`},item.project?"Project":"Vanilla"),
    body:[
      detailField("Record type",item.type,"","The XML element this record comes from. It decides which fields the game reads."),
      detailField("Dataset",item.sourceLabel,"","Which shipped data file this item was defined in: the base game or one of its DLC."),
      detailField("Vanilla source",el("code",{title:item.sourcePath},item.sourcePath),"","The untouched file inside the installed content.rpf. Lexeditor never writes here."),
      detailField("Project override",el("code",{title:item.projectPath},item.projectPath),"","Where your edit is written, as a full XML override. The game loads this instead of the vanilla file."),
      // No bubble on the data fields themselves. A generic note repeated on
      // every scalar is noise, and the four rows above already say where the
      // value comes from and where an edit is written.
      ...rest.map(field=>detailField(field.field,scalarControl(item,field)))]});
}
function renderItems(){
  const rows=matchingItems();
  $("#toolbar").replaceChildren();
  const sourceFilter=el("select",{"aria-label":"Filter items by source",onchange:event=>{state.itemSource=event.target.value;state.itemPage=0;renderItems();}},el("option",{value:"",selected:!state.itemSource},"Base game and DLC"),...(state.items?.sources||[]).map(source=>el("option",{value:source.id,selected:source.id===state.itemSource},source.label)));
  $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec(state.itemEdits,()=>{state.itemPage=0}),rows,key:item=>item.id,slots:false,page:state.itemPage,pageSize:state.itemPageSize,selected:state.itemSelected,noun:"items",splitKey:"rdr-items",className:"rdr-split",defaultSplit:44,fit:{rowSelector:".rdr-record-entry",headerSelector:".rdr-listhead",minRowHeight:32},
    search:{key:"rdr-items",value:state.itemQuery,placeholder:"Search RDR inventory items…",change:value=>{state.itemQuery=value;state.itemPage=0;renderItems();}},filters:[sourceFilter],
    master:({rows,selected,select})=>list({rows,key:item=>item.id,selected,selectedClass:"sel",select,class:"rdr-record-list",header:el("div",{class:"rdr-listhead"},el("span",{},"Name"),el("span",{},"ID"),el("span",{},"Type"),el("span",{},"Source")),rowClass:"rdr-record-entry",render:itemRow,"aria-label":"RDR inventory items"}),
    detail:()=>itemDetail(),sync:next=>{state.itemPage=next.page;state.itemPageSize=next.pageSize;state.itemSelected=next.selected||"";},change:next=>{state.itemPage=next.page;state.itemPageSize=next.pageSize;state.itemSelected=next.selected||"";renderItems();}}));shell.refresh();
}

const SHOP_FIELDS=[
  {field:"PriceModifier",key:"priceModifier",label:"Price modifier",step:"0.01",min:"0",max:"1000",help:"Multiplier applied to the base item price"},
  {field:"QuantityPerPurchase",key:"quantityPerPurchase",label:"Quantity per purchase",step:"1",min:"0",max:"2147483647",help:"Units received for one purchase"},
  {field:"TotalAvailableQuantity",key:"totalAvailableQuantity",label:"Available stock",step:"1",min:"-1",max:"2147483647",help:"-1 is reserved for records that use unlimited stock"}
];
function matchingShops(){const needle=state.shopQuery.trim().toLowerCase();return (state.shops?.rows||[]).filter(item=>(!needle||[item.name,item.shop,item.category].some(value=>String(value||"").toLowerCase().includes(needle)))&&(!state.shopName||item.shop===state.shopName)&&(!state.shopCategory||item.category===state.shopCategory));}
function shopBaseline(item,field){
  const value=item[field.key];
  if(field.key!=="priceModifier"||!Number.isFinite(value))return String(value);
  // Show the shortest decimal which represents the stored float32 value.
  for(let digits=1;digits<=9;digits++){const text=String(Number(value.toPrecision(digits)));if(Math.fround(Number(text))===value)return text;}
  return String(value);
}
function shopValue(item,field){const key=`${item.id}|${field.field}`;return Object.prototype.hasOwnProperty.call(state.shopEdits,key)?state.shopEdits[key]:shopBaseline(item,field);}
function editShop(item,field,value){const key=`${item.id}|${field.field}`;if(value===shopBaseline(item,field))delete state.shopEdits[key];else state.shopEdits[key]=value;shell.refresh();}
function selectShopItem(item){state.shopSelected=item.id;renderShops();}
function shopRow(item){return el("div",{class:"rdr-record-row"},recordCell("rdr-record-name",item.name),recordCell("rdr-record-id",item.shop),recordCell("rdr-record-type",item.category),recordCell("rdr-record-source",`x${item.quantityPerPurchase} / ${item.totalAvailableQuantity}`));}
function shopDetail(){
  const item=(state.shops?.rows||[]).find(row=>row.id===state.shopSelected);
  if(!item)return el("div",{class:"lex-detail empty"},el("div",{},el("h2",{},"Select a shop item"),el("p",{},"Edits create a packed WGD override. The installed gringores.rpf stays unchanged.")));
  return el("div",{class:"lex-detail record-detail shop-detail"},
    el("div",{class:"detail-head"},el("h2",{},item.name),el("span",{class:`badge${item.project?" project":""}`},item.project?"Project":"Vanilla")),
    detailField("Shop",item.shop),detailField("Stock type",item.category),
    detailField("Root hash",el("code",{},item.rootHash)),
    detailField("Vanilla resource",el("code",{title:item.sourcePath},item.sourcePath)),
    detailField("Project override",el("code",{title:item.projectPath},item.projectPath)),
    el("div",{class:"source-note"},el("strong",{},"Live ShopInventory fields. "),"The save preserves the other Gringo components and packs a verified resource override."),
    ...SHOP_FIELDS.map(field=>{const control=el("input",{type:"number",step:field.step,min:field.min,max:field.max,value:shopValue(item,field),disabled:state.activeSource!=="mine",oninput:event=>editShop(item,field,event.target.value)}),vanilla=state.vanilla.shops?.rows?.find(row=>row.id===item.id)?.[field.key];return detailField(field.label,sourceControl(control,()=>shopValue(item,field),vanilla===undefined?undefined:String(vanilla),value=>editShop(item,field,String(value))),field.help)})
  );
}
function renderShops(){
  const rows=matchingShops();
  const shopNames=[...new Set((state.shops?.rows||[]).map(item=>item.shop))].sort((a,b)=>a.localeCompare(b));
  const categories=[...new Set((state.shops?.rows||[]).map(item=>item.category))].sort((a,b)=>a.localeCompare(b));
  $("#toolbar").replaceChildren();
  const shopFilter=el("select",{"aria-label":"Filter shop stock by shop",onchange:event=>{state.shopName=event.target.value;state.shopPage=0;renderShops();}},el("option",{value:"",selected:!state.shopName},"All shops"),...shopNames.map(name=>el("option",{value:name,selected:name===state.shopName},name)));
  const categoryFilter=el("select",{"aria-label":"Filter shop stock by type",onchange:event=>{state.shopCategory=event.target.value;state.shopPage=0;renderShops();}},el("option",{value:"",selected:!state.shopCategory},"All stock types"),...categories.map(category=>el("option",{value:category,selected:category===state.shopCategory},category)));
  $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec(state.shopEdits,()=>{state.shopPage=0}),rows,key:item=>item.id,slots:false,page:state.shopPage,pageSize:state.shopPageSize,selected:state.shopSelected,noun:"items",splitKey:"rdr-shops",className:"rdr-split",defaultSplit:44,fit:{rowSelector:".rdr-record-entry",headerSelector:".rdr-listhead",minRowHeight:32},
    search:{key:"rdr-shops",value:state.shopQuery,placeholder:"Search RDR shop stock…",change:value=>{state.shopQuery=value;state.shopPage=0;renderShops();}},filters:[shopFilter,categoryFilter],
    master:({rows,selected,select})=>list({rows,key:item=>item.id,selected,selectedClass:"sel",select,class:"rdr-record-list",header:el("div",{class:"rdr-listhead"},el("span",{},"Item"),el("span",{},"Shop"),el("span",{},"Type"),el("span",{},"Qty / Stock")),rowClass:"rdr-record-entry",render:shopRow,"aria-label":"RDR shop inventory"}),
    detail:()=>shopDetail(),sync:next=>{state.shopPage=next.page;state.shopPageSize=next.pageSize;state.shopSelected=next.selected||"";},change:next=>{state.shopPage=next.page;state.shopPageSize=next.pageSize;state.shopSelected=next.selected||"";renderShops();}}));shell.refresh();
}

const MISSION_REWARDS=[
  {key:"cash",label:"Cash reward",help:"Changes the cash awarded when this mission completes; it does not alter prices, pickups, or other missions."},
  {key:"fame",label:"Fame reward",help:"Changes this mission's completion Fame award independently of its cash and Honor rewards."},
  {key:"honor",label:"Honor reward",help:"Changes this mission's completion Honor adjustment independently of its cash and Fame rewards."}
];
function missionArea(mission){return String(mission.assetPath||"").split("/")[2]||"Unknown";}
function matchingMissions(){const needle=state.missionQuery.trim().toLowerCase();return (state.missions?.missions||[]).filter(mission=>(!needle||[mission.id,mission.name,mission.scriptName,mission.localizationKey,mission.assetPath].some(value=>String(value||"").toLowerCase().includes(needle)))&&(!state.missionArea||missionArea(mission)===state.missionArea));}
function missionValue(mission,reward){const key=`${mission.id}|${reward}`;return Object.prototype.hasOwnProperty.call(state.missionEdits,key)?state.missionEdits[key]:String(mission.rewards[reward]);}
function editMission(mission,reward,value){const key=`${mission.id}|${reward}`;if(value===String(mission.rewards[reward]))delete state.missionEdits[key];else state.missionEdits[key]=value;shell.refresh();}
function selectMission(mission){state.missionSelected=mission.id;renderMissions();}
function missionRow(mission){return el("div",{class:"rdr-record-row rdr-mission-row"},recordCell("rdr-record-id",`#${mission.id} · ${mission.scriptName}`),recordCell("rdr-record-name",mission.name),recordCell("rdr-record-type",missionArea(mission)),recordCell("rdr-record-source",`$${mission.rewards.cash} / F${mission.rewards.fame} / H${mission.rewards.honor}`));}
function missionDetail(){
  const mission=(state.missions?.missions||[]).find(row=>row.id===state.missionSelected);
  if(!mission)return el("div",{class:"lex-detail empty"},el("div",{},el("h2",{},"No mission selected")));
  const limits=state.missions.limits;
  return el("div",{class:"lex-detail record-detail mission-detail"},
    el("div",{class:"detail-head"},el("h2",{},mission.name),el("span",{class:`badge${mission.project?" project":""}`},mission.project?"Project":"Vanilla")),
    detailField("Mission ID",String(mission.id)),detailField("Script",mission.scriptName),detailField("Area",missionArea(mission)),
    detailField("Localization key",el("code",{},mission.localizationKey)),detailField("Archive path",el("code",{title:mission.archivePath},mission.archivePath)),
    detailField("Reward evidence",el("code",{title:mission.rewardSource.file},`${mission.rewardSource.function} / ${mission.rewardSource.case}`)),
    el("div",{class:"source-note"},el("strong",{},"The extracted mission table stays read-only. "),"Save writes only cash, fame, or honor values that differ from the base into LexerRDR.missions.json."),
    ...MISSION_REWARDS.map(reward=>{const rewardLimits=limits.rewards[reward.key],control=el("input",{type:"number",inputmode:"numeric",min:String(rewardLimits.minimum),max:String(rewardLimits.maximum),step:String(limits.step),value:missionValue(mission,reward.key),disabled:state.activeSource!=="mine",oninput:event=>editMission(mission,reward.key,event.target.value)});return detailField(reward.label,
      sourceControl(control,()=>missionValue(mission,reward.key),String(mission.baseRewards[reward.key]),value=>editMission(mission,reward.key,String(value))),
      reward.help);})
  );
}
function renderMissions(){
  const rows=matchingMissions();
  const areas=[...new Set((state.missions?.missions||[]).map(missionArea))].sort((a,b)=>a.localeCompare(b));
  $("#toolbar").replaceChildren();
  const areaFilter=el("select",{"aria-label":"Filter missions by area",onchange:event=>{state.missionArea=event.target.value;state.missionPage=0;renderMissions();}},el("option",{value:"",selected:!state.missionArea},"All areas"),...areas.map(area=>el("option",{value:area,selected:area===state.missionArea},area)));
  $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec(state.missionEdits,()=>{state.missionPage=0}),rows,key:mission=>mission.id,slots:false,page:state.missionPage,pageSize:state.missionPageSize,selected:state.missionSelected,noun:"missions",splitKey:"rdr-missions",className:"rdr-split",defaultSplit:44,fit:{rowSelector:".rdr-record-entry",headerSelector:".rdr-listhead",minRowHeight:32},
    search:{key:"rdr-missions",value:state.missionQuery,placeholder:"Search Story missions…",change:value=>{state.missionQuery=value;state.missionPage=0;renderMissions();}},filters:[areaFilter],
    master:({rows,selected,select})=>list({rows,key:mission=>mission.id,selected,selectedClass:"sel",select,class:"rdr-record-list",header:el("div",{class:"rdr-listhead rdr-mission-row"},el("span",{},"ID / Script"),el("span",{},"Mission"),el("span",{},"Area"),el("span",{},"Cash / Fame / Honor")),rowClass:"rdr-record-entry",render:missionRow,"aria-label":"RDR Story mission rewards"}),
    detail:()=>missionDetail(),sync:next=>{state.missionPage=next.page;state.missionPageSize=next.pageSize;state.missionSelected=next.selected||"";},change:next=>{state.missionPage=next.page;state.missionPageSize=next.pageSize;state.missionSelected=next.selected||"";renderMissions();}}));shell.refresh();
}

function settingKey(section,setting){return `${section.name}\u0000${setting.key}`;}
function settingValue(section,setting){const key=settingKey(section,setting);return Object.prototype.hasOwnProperty.call(state.settingEdits,key)?state.settingEdits[key]:setting.value;}
function editSetting(section,setting,value){const key=settingKey(section,setting);if(value===setting.value)delete state.settingEdits[key];else state.settingEdits[key]=value;shell.refresh();}
function settingControl(section,setting){
  const value=settingValue(section,setting);
  if(setting.control==="checkbox")return el("input",{type:"checkbox",checked:value.toLowerCase()==="true",onchange:event=>editSetting(section,setting,event.target.checked?"true":"false"),"aria-label":setting.key});
  if(setting.control==="number")return el("input",{type:"number",min:setting.minimum,max:setting.maximum,step:setting.step,value,oninput:event=>editSetting(section,setting,event.target.value)});
  if(setting.control==="select")return el("select",{onchange:event=>editSetting(section,setting,event.target.value)},...(setting.options||[]).map(option=>el("option",{value:option,selected:String(option)===String(value)},option)));
  return el("input",{type:"text",value,oninput:event=>editSetting(section,setting,event.target.value),spellcheck:false});
}
async function saveSettings(){
  validateSettings();
  const edits=Object.entries(state.settingEdits).map(([identity,value])=>{const [section,key]=identity.split("\u0000");return {section,key,value};});if(!edits.length)return;
  await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.settings=await api("/api/settings");state.settingEdits={};shell.history.clear();setStatus("Saved LexerRDR.ini in the workspace; runtime loading is not verified");renderSettings();shell.refresh();
}
function discardSettings(){state.settingEdits={};setStatus("Restored the last saved settings");renderSettings();shell.refresh()}
function renderSettings(){
  $("#toolbar").replaceChildren(el("span",{},state.settings?.available?"LexerRDR.ini — project settings for LexerRDR.asi":"LexerRDR.ini is not available"),el("span",{class:"count"},state.settings?.file||""),LexeditorUI.settingsSaveControl({pendingChanges:()=>(state.settings?.sections||[]).flatMap(section=>section.settings.filter(setting=>Object.prototype.hasOwnProperty.call(state.settingEdits,settingKey(section,setting))).map(setting=>({label:`${section.name} / ${setting.key}`,before:setting.value,after:settingValue(section,setting)}))),dirtyCount:()=>Object.keys(state.settingEdits).length,save:saveSettings,discard:discardSettings,readonly:()=>!state.settings?.available}));
  if(!state.settings?.available){$("#main").replaceChildren(el("div",{class:"empty"},el("div",{},el("h2",{},"LexerRDR.ini is missing"),el("p",{},state.settings?.reason||"The runtime settings file must be present before its values can be edited."))));shell.refresh();return;}
  const sections=state.settings.sections.map(section=>el("section",{class:"settings-section"},el("h2",{},section.name),section.help?el("div",{class:"source-note"},section.help):null,...section.settings.map(setting=>el("div",{class:"field"},el("label",{},setting.key,setting.help?el("small",{},setting.help):null),settingControl(section,setting)))));
  $("#main").replaceChildren(LexeditorUI.settingsColumns(sections));shell.refresh();
}

function lootNumber(parent,key,label,step="1",minimum="0",maximum="100000",note=""){
  return el("div",{class:"field"},el("label",{},label,note?infoHelp(note):null),el("input",{type:"number",step,min:minimum,max:maximum,value:String(parent[key]),oninput:event=>{parent[key]=event.target.value.trim()===""?"":Number(event.target.value);state.lootDirty=true;shell.refresh();}}));
}
function lootFlag(parent,key,label,note=""){return el("div",{class:"field"},el("label",{},label,note?infoHelp(note):null),el("input",{type:"checkbox",checked:!!parent[key],onchange:event=>{parent[key]=event.target.checked;state.lootDirty=true;shell.refresh();},"aria-label":label}));}
// The corpse loot table itself, read out of the script that holds it. There
// is no drops XML in this game: the items are constants compiled into
// lootcorpsegenericnoanim.wsc, and a patched copy of that script is written
// into the mod folder, where the game already picks up loose overrides by
// archive path.
function lootScriptItem(slot){
  const edited=state.lootScriptEdits[slot.index];
  return edited===undefined?slot.item:edited;
}
function lootScriptDirty(){return Object.keys(state.lootScriptEdits).length}
function lootScriptCard(){
  const script=state.lootScript;
  // The save button is held here rather than re-rendering the card on every
  // keystroke: a full render would rebuild the box being typed into.
  let saveButton=null;
  if(!script)return el("section",{class:"card"},el("h2",{},"Corpse loot table"),
    el("div",{class:"loading"},"Reading the script that holds it…"));
  if(!script.available)return el("section",{class:"card"},
    el("h2",{},"Corpse loot table",
      infoHelp("The table lives in a compiled script inside content.rpf. Lexeditor reads it through the same RPF6 bridge it uses everywhere else; this is what stopped it.")),
    el("p",{class:"error"},script.reason||"The loot script could not be read."));
  const fields=script.slots.map(slot=>{
    const input=el("input",{type:"number",min:0,max:slot.maximum,step:1,
      value:String(lootScriptItem(slot)),"aria-label":`Loot branch ${slot.index+1} item`,
      oninput:event=>{
        const value=Number(event.target.value);
        if(value===slot.vanilla)delete state.lootScriptEdits[slot.index];
        else state.lootScriptEdits[slot.index]=value;
        if(saveButton)saveButton.disabled=!lootScriptDirty();
        shell.refresh();
      }});
    return el("div",{class:"field"},
      el("label",{},`Branch ${slot.index+1}`,
        slot.maximum<script.maximum
          ? infoHelp(`This branch is encoded as a short push and can only hold 0 to ${slot.maximum}. A larger item would move every address after it in the script.`)
          : null,
        el("small",{},`vanilla ${slot.vanilla}`)),
      input);
  });
  const save=el("button",{class:"save",disabled:!lootScriptDirty(),
    onclick:()=>saveLootScript()},"Write the loot override");
  saveButton=save;
  return el("section",{class:"card"},
    el("h2",{},"Corpse loot table",
      infoHelp("Each branch of the game's LootType switch and the item enum it hands over, read straight out of the script's bytecode. Saving writes a patched copy of the script into the mod folder; the game loads that instead of the archived one, and the original archive is never touched.")),
    el("div",{class:"source-note"},
      el("div",{},script.path),
      el("div",{},script.overrideExists?`Override in place: ${script.override}`
                                        :"No override written yet.")),
    el("div",{class:"field-grid"},...fields),
    el("div",{class:"loot-script-actions"},save));
}
async function loadLootScript(){
  try{state.lootScript=await api("/api/loot/script")}
  catch(error){state.lootScript={available:false,reason:error.message}}
}
async function saveLootScript(){
  const slots=Object.entries(state.lootScriptEdits)
    .map(([index,item])=>({index:Number(index),item:Number(item)}));
  if(!slots.length)return;
  try{
    await api("/api/loot/script/save",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify({slots})});
    state.lootScriptEdits={};
    await loadLootScript();
    LexeditorUI.showToast?.("The loot override was written into the mod folder.");
  }catch(error){LexeditorUI.showToast?.(error.message||String(error),true)}
  renderLoot();
}

function renderLoot(){
  $("#toolbar").replaceChildren(el("span",{},"Corpse loot from the installed WSC context"),el("span",{class:"count"},state.loot?.file||""));
  if(!state.loot?.available||!state.lootDocument){$("#main").replaceChildren(el("div",{class:"empty"},el("div",{},el("h2",{},"Loot ASI override is unavailable"),el("p",{},state.loot?.reason||"The project file could not be loaded."))));shell.refresh();return;}
  const doc=state.lootDocument,bonus=doc.corpseBonusItem,money=doc.money,base=money.baseRoll;
  const bonusRows=bonus.entries.map(entry=>el("tr",{},
    el("td",{class:"mono"},String(entry.itemEnum)),
    el("td",{},el("input",{type:"number",min:"0",max:"100000",step:"1",value:String(entry.quantity),oninput:event=>{entry.quantity=event.target.value.trim()===""?"":Number(event.target.value);state.lootDirty=true;shell.refresh();}})),
    el("td",{},el("input",{type:"number",min:"0",max:"100000",step:"1",value:String(entry.weight),oninput:event=>{entry.weight=event.target.value.trim()===""?"":Number(event.target.value);state.lootDirty=true;shell.refresh();}}))));
  const bonusTable=el("table",{class:"loot-table"},
    el("thead",{},el("tr",{},el("th",{},"Item enum"),el("th",{},"Quantity"),el("th",{},"Weight"))),
    el("tbody",{},...bonusRows));
  const source=el("section",{class:"card"},
    el("h2",{},"Corpse bonus item",el("span",{class:"asi-badge"},"ASI override"),
      infoHelp("Not an RPF replacement: LexerRDR.asi owns this schema-versioned project file, and it accepts only the five item IDs proven in Function_117.")),
    lootNumber(bonus,"chancePercent","Bonus roll chance (%)","1","0","100","How often looting a body rolls for a bonus item at all. At 0 no body ever yields one; at 100 every body rolls, and the table below then decides which item comes up."),bonusTable);
  const moneyCard=el("section",{class:"card"},el("h2",{},"Money paths",el("span",{class:"asi-badge"},"ASI override")),el("div",{class:"source-note"},`Function_123: ${money.decoratorPaths.map(path=>`${path.decorator} = ${path.operation}`).join(" · ")}`),el("div",{class:"field-grid"},lootNumber(base.range,"minimum","Base minimum","0.01",undefined,undefined,"The low end of the money a body carries before any multiplier below is applied. The game picks a value between this and the maximum."),lootNumber(base.range,"maximum","Base maximum","0.01",undefined,undefined,"The high end of that same range. Set it equal to the minimum to give every body the same amount."),lootFlag(base,"applyStatScale","Apply stat scale","Multiply the rolled amount by the game's own difficulty and progression scale, so late-game bodies carry more. Off pays the raw roll everywhere."),lootFlag(base,"applyItem17Multiplier","Apply item 17 multiplier","Honour the multiplier the game attaches to item slot 17, which is how it grants a player bonus to money found. Off ignores that bonus."),lootFlag(base,"applyFinalMultiplier","Apply final multiplier","Apply the last multiplier in the chain, after the other two. This is the one to turn off to see the raw roll.")));
  const evidence=el("details",{class:"card loot-evidence"},el("summary",{},"Which script this is reading"),el("div",{class:"path-row"},el("b",{},"Archive"),el("code",{},doc.source?.archive||"Not supplied")),el("div",{class:"path-row"},el("b",{},"Script"),el("code",{},doc.source?.script||"Not supplied")),el("pre",{class:"manifest"},(doc.source?.functions||[]).map(fn=>`${fn.name} @ ${fn.positionHex} / ${fn.positionDecimal}\n${fn.role}`).join("\n\n")));
  // Two questions come up on this page every time: where the ordinary
  // per-enemy drop list is edited, and whether enemies carry drop tables of
  // their own somewhere else. Both are answered here rather than left for
  // the reader to conclude from the absence of a table.
  const scope=el("section",{class:"card"},
    el("h2",{},"What this tab covers",
      infoHelp("Searched, not assumed. content.rpf holds the corpse loot logic at content/release64/scripting/gringo/commonscripts/lootcorpsegenericnoanim.wsc, and Lexeditor's RPF6 bridge decompiles it. What a body yields is a switch on a LootType decorator carried by the ped: each branch adds a fixed item enum, written into the script rather than looked up from a table, in Function_90 at bytecode offset 0x36F4. None of the 183 XML files in the archive is a drops table. Editing the script itself is possible and not yet built: the game already loads loose overrides by archive path for non-XML files, so a modified copy of that script would be picked up, and what is missing is writing the item enums back into its bytecode. Until then the two cards below patch the running functions, which is the seam that exists today.")),
    el("p",{},"Loot here is compiled script, not a data table. A body's items come from a switch on its LootType inside lootcorpsegenericnoanim.wsc in content.rpf, and no XML in the archive holds a drops table. The table below is that switch, read out of the script's bytecode and written back as a loose override; the two cards under it patch the running functions instead, which is how the bonus roll and the money are reached."));
  $("#main").replaceChildren(el("div",{class:"stack"},scope,lootScriptCard(),
    el("div",{class:"loot-layout"},source,moneyCard),evidence));shell.refresh();
  if(!state.lootScript)loadLootScript().then(()=>renderLoot());
}

async function renderDataMap(){
  if(!state.dataMap)state.dataMap=await api("/api/datamap");
  const view=LexeditorUI.dataMap({
    rows:state.dataMap.rows||[],query:state.mapQuery,status:state.mapStatus,page:state.mapPage,
    sort:state.dataMapSort,pageSize:100,
    changeQuery:value=>{state.mapQuery=value;state.mapPage=0;renderDataMap();},
    changeStatus:value=>{state.mapStatus=value;state.mapPage=0;renderDataMap();},
    changePage:page=>{state.mapPage=page;renderDataMap();},
    changeSort:key=>{const [active,direction]=state.dataMapSort;state.dataMapSort=[key,active===key?-direction:1];renderDataMap();},
    open:row=>{if(row.target)navigate(row.target);}
  });
  state.mapPage=view.page;
  $("#toolbar").replaceChildren(...view.controls);
  $("#main").replaceChildren(view.content);
  shell.refresh();
}

function renderProject(){
  // No "read only" banner. Every read-only value already carries the shared
  // lock mark, so the banner restated in words what the controls show.
  $("#toolbar").replaceChildren();
  const sources=state.dashboard.manifest?.sources||{};
  const statusCard=el("section",{class:"card"},el("h2",{},"Preparation"),state.dashboard.problems.length?el("div",{class:"error"},...state.dashboard.problems.map(problem=>el("div",{},problem))):el("div",{class:"ok"},`${state.files.counts.all||0} tuning files, ${state.items?.counts?.all||0} items, and ${state.shops?.counts?.items||0} shop entries prepared. Installed archives are read-only.`),el("pre",{class:"manifest"},Object.keys(sources).length?`${Object.entries(sources).map(([label,source])=>`${label}: ${source.path}\nSHA-256: ${source.sha256}`).join("\n\n")}\n\nPrepared: ${state.dashboard.manifest.preparedAt}\nInventory files: ${state.dashboard.manifest.fileCounts?.inventory||0}\nShop dictionaries: ${state.dashboard.manifest.fileCounts?.gringoUnpacked||0}`:"Preparation manifest is not available."));
  const redHook=state.dashboard.redHook;
  const intro=redHook.skipIntroLogos;
  const redHookCard=el("section",{class:"card"},el("h2",{},"RedHook"),redHook.installed?el("div",{class:"ok"},"RedHook is installed."):el("div",{class:"error"},`RedHook is required. Missing: ${redHook.missing.join(", ")}.`),redHook.installed?(intro.enabled?el("div",{class:"ok"},"Startup logo movies are disabled."):el("div",{class:"error"},intro.problem||"Startup logo skipping is not enabled.")):null,el("div",{class:"path-row"},el("b",{},"Game root"),el("code",{title:redHook.gameRoot},redHook.gameRoot)),!redHook.installed?el("button",{type:"button",onclick:()=>openRedHook()},"Open official RedHook page"):null);
  const deployment=state.dashboard.deployment||{rows:[],pending:false,active:false};
  const deploymentRows=(deployment.rows||[]).filter(row=>row.overrideCount||row.targetExists).map(row=>
    el("div",{class:"path-row"},el("b",{},`${row.name}: ${row.overrideCount} override${row.overrideCount===1?"":"s"}`),
      el("code",{title:row.target},row.changedSinceDeploy?"changed outside Lexeditor — deployment locked":row.deployed?"deployed and current":row.overrideCount?"saved; deployment needed":"not deployed")));
  const shopTest=state.dashboard.shopTest||{available:false,reason:"No shop test candidate is available."};
  const shopTestCard=el("section",{class:"card"},el("h2",{},"Shop edit test"),
    !shopTest.available?el("div",{class:"error"},shopTest.reason):[
      el("p",{},"Lexeditor selected one stable prepared record so the in-game check does not require you to invent a shop, item, or value."),
      el("div",{class:"path-row"},el("b",{},"Shop"),el("code",{},shopTest.shop)),
      el("div",{class:"path-row"},el("b",{},"Item"),el("code",{},shopTest.item)),
      el("div",{class:"path-row"},el("b",{},"Price multiplier"),el("code",{},`vanilla ${shopTest.baselinePriceModifier} · current ${shopTest.currentPriceModifier} · test ${shopTest.testPriceModifier}`)),
      el("div",{class:shopTest.status==="staged"?"ok":shopTest.status==="custom"?"error":"source-note"},shopTest.status==="staged"?"Test value is staged. Deploy Project before launching RDR1.":shopTest.status==="custom"?"This candidate already has a different custom price; the test helper will not overwrite it.":"Candidate is at its vanilla price and ready to stage."),
      el("p",{},shopTest.instruction),
      el("div",{class:"redhook-actions"},
        el("button",{type:"button",onclick:()=>stageShopTest(),disabled:!shopTest.stageAllowed||shopTest.status==="staged"},"Stage Shop Test"),
        el("button",{type:"button",class:"secondary",onclick:()=>restoreShopTest(),disabled:!shopTest.restoreAllowed||shopTest.status!=="staged"},"Restore Shop Test"),
        el("button",{type:"button",class:"secondary",onclick:()=>openShopTest(),disabled:!shopTest.available},"Open in Shops"))
    ]);
  const missionTest=state.dashboard.missionTest||{available:false,problem:"Mission reward test is unavailable."};
  const missionTestCard=el("section",{class:"card"},el("h2",{},"Mission reward test"),
    !missionTest.available?el("div",{class:"error"},missionTest.problem):[
      el("p",{},"Lexeditor uses a fixed early Story mission and preserves the exact mission-2 override that existed before staging."),
      el("div",{class:"path-row"},el("b",{},"Mission"),el("code",{},`${missionTest.storyTitle} · ${missionTest.mission} · ID ${missionTest.missionId}`)),
      el("div",{class:"path-row"},el("b",{},"Vanilla rewards"),el("code",{},`cash ${missionTest.vanillaRewards.cash} · fame ${missionTest.vanillaRewards.fame} · honor ${missionTest.vanillaRewards.honor}`)),
      el("div",{class:"path-row"},el("b",{},"Test rewards"),el("code",{},`cash ${missionTest.testRewards.cash} · fame ${missionTest.testRewards.fame} · honor ${missionTest.testRewards.honor}`)),
      el("div",{class:missionTest.status==="staged"?"ok":"source-note"},missionTest.status==="staged"?"Mission test is staged in LexerRDR.missions.json.":missionTest.status==="custom"?"A pre-existing mission-2 override exists; Stage will snapshot it and Restore will put it back exactly.":"Mission 2 is at vanilla override state and ready to stage."),
      el("p",{},missionTest.route),el("p",{},missionTest.expected),el("p",{},missionTest.instruction),
      el("div",{class:"redhook-actions"},
        el("button",{type:"button",onclick:()=>stageMissionTest(),disabled:!missionTest.stageAllowed},"Stage Mission Test"),
        el("button",{type:"button",class:"secondary",onclick:()=>restoreMissionTest(),disabled:!missionTest.restoreAllowed},"Restore Mission Test"),
        el("button",{type:"button",class:"secondary",onclick:()=>openMissionTest()},"Open in Missions"))
    ]);
  const deliveryCard=el("section",{class:"card"},el("h2",{},"Saved files and game delivery"),
    el("p",{},"Save writes the project workspace. Deploy Project rebuilds verified copies of only the affected RPF archives and installs those copies under the loader's update\game folder. The original game\*.rpf archives are never overwritten."),
    el("p",{},"LexerRDR.ini, loot JSON and mission JSON are consumed by the native runtime from this workspace; archive-backed XML/WGD edits use the update-folder copies below."),
    el("div",{class:deployment.pending?"error":deployment.active?"ok":"source-note"},deployment.pending?"Saved archive edits are newer than the current deployment.":deployment.active?"Archive deployment matches the saved project.":"No Lexeditor archive-copy deployment is active."),
    el("div",{class:"redhook-actions"},
      el("button",{type:"button",onclick:()=>deployProject(),disabled:!deployment.pending},deployment.active?"Redeploy Project":"Deploy Project"),
      el("button",{type:"button",class:"secondary",onclick:()=>revertProject(),disabled:!deployment.active},"Revert Deployment")),
    el("div",{class:"path-row"},el("b",{},"Update-folder target"),el("code",{title:deployment.updateRoot||""},deployment.updateRoot||"Unavailable")),
    ...deploymentRows,
    ...Object.entries(state.dashboard.paths).filter(([name])=>["Editable overrides","Inventory overrides","Shop overrides","Settings","Loot ASI override","Mission ASI override"].includes(name)).map(([name,path])=>el("div",{class:"path-row"},el("b",{},name),el("code",{title:path},path))));
  $("#main").replaceChildren(el("div",{class:"cards"},statusCard,redHookCard,shopTestCard,missionTestCard,deliveryCard),
    LexeditorUI.modLoaderSection({
      loader:"RedHook, the community runtime for the PC release. It loads the plugin's overrides when the game starts.",
      output:"Edits are written as Git-backed override files in the project folder, which RedHook reads over the stock data.",
      order:"RedHook applies overrides after the base data. Two mods overriding the same file conflict; the later one wins.",
      safety:"Installed game source data is read only. Every edit is stored as a separate override rather than a rewrite.",
      removal:"Remove the override files, or uninstall RedHook to return the game to stock.",
    }));shell.refresh();
}

async function openRedHook(){try{await api("/api/redhook/open",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});setStatus("Opened the official RedHook page");}catch(error){setStatus(`Could not open RedHook: ${error.message}`);showAlert({title:"Could not open RedHook",message:String(error.message||error)});}}
async function configureRedHook(){await api("/api/redhook/configure",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");}
async function stageShopTest(){
  try{setStatus("Staging deterministic shop price test…");const result=await api("/api/shop-test/stage",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.shops=await api("/api/shops");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Shop test staged");renderProject();}
  catch(error){setStatus("Shop test staging failed");showAlert({title:"Shop test staging failed",items:[{item:"Price test",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
}
async function restoreShopTest(){
  try{setStatus("Restoring deterministic shop test price…");const result=await api("/api/shop-test/restore",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.shops=await api("/api/shops");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Shop test restored");renderProject();}
  catch(error){setStatus("Shop test restore failed");showAlert({title:"Shop test restore failed",items:[{item:"Price test",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
}
function openShopTest(){const test=state.dashboard.shopTest;if(!test?.available)return;state.shopQuery=test.item;state.shopName=test.shop;state.shopCategory="";state.shopSelected=test.id;navigate("shops");}
async function stageMissionTest(){
  try{setStatus("Staging deterministic mission reward test…");const result=await api("/api/mission-test/stage",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.missions=await api("/api/missions");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Mission test staged");renderProject();}
  catch(error){setStatus("Mission test staging failed");showAlert({title:"Mission test staging failed",items:[{item:"Mission 2",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
}
async function restoreMissionTest(){
  try{setStatus("Restoring pre-test mission reward state…");const result=await api("/api/mission-test/restore",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.missions=await api("/api/missions");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Mission test restored");renderProject();}
  catch(error){setStatus("Mission test restore failed");showAlert({title:"Mission test restore failed",items:[{item:"Mission 2",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
}
function openMissionTest(){const test=state.dashboard.missionTest;if(!test?.missionId)return;state.missionQuery=test.mission;state.missionRegion="";state.missionSelected=test.missionId;navigate("missions");}
async function deployProject(){
  try{setStatus("Building verified RPF copies…");const result=await api("/api/deployment/deploy",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");setStatus(result.message||"Project archive copies deployed");renderProject();}
  catch(error){setStatus("Deployment failed");showAlert({title:"Deployment failed",items:[{item:"Archive copies",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
}
async function revertProject(){
  try{setStatus("Reverting Lexeditor archive copies…");const result=await api("/api/deployment/revert",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");setStatus(result.message||"Archive deployment reverted");renderProject();}
  catch(error){setStatus("Revert failed");showAlert({title:"Revert failed",items:[{item:"Archive copies",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
}
function renderRedHookNotice(){
  document.querySelector(".redhook-modal")?.remove();
  const redHook=state.dashboard?.redHook;
  if(!redHook||redHook.installed)return;
  const modal=el("div",{class:"redhook-modal"},el("section",{class:"redhook-panel"},el("h2",{},"RedHook is required"),el("p",{},"Install the official RedHook files before you use LexerRDR in the game."),el("code",{},`Missing: ${redHook.missing.join(", ")}`),el("div",{class:"redhook-actions"},el("button",{type:"button",class:"secondary",onclick:()=>modal.remove()},"Keep editing"),el("button",{type:"button",onclick:()=>openRedHook()},"Open official download"))));
  document.body.append(modal);
}

function numberEdit(raw,label,{minimum,maximum,step}={}){
  if(raw===null||typeof raw==="boolean"||String(raw).trim()==="")throw new Error(`${label} needs a number`);
  const value=Number(raw);
  if(!Number.isFinite(value)||(Number(step)===1&&!Number.isInteger(value)))throw new Error(`${label} needs a finite ${Number(step)===1?"integer":"number"}`);
  if(minimum!==undefined&&value<Number(minimum)||maximum!==undefined&&value>Number(maximum))throw new Error(`${label} is outside its allowed range`);
  return value;
}
function validateSettings(){
  for(const [identity,value] of Object.entries(state.settingEdits)){
    const [section,key]=identity.split("\u0000"),setting=state.settings?.sections?.find(row=>row.name===section)?.settings.find(row=>row.key===key);
    if(!setting)throw new Error(`Setting ${section}/${key} is no longer loaded`);
    if(setting.control==="number")numberEdit(value,`${section}/${key}`,setting);
    if(setting.control==="checkbox"&&!["true","false"].includes(String(value).toLowerCase()))throw new Error(`${key} must be true or false`);
  }
}
function validatePendingEdits(){
  stringsUI.validate();
  for(const [identity,value] of Object.entries(state.itemEdits)){
    const split=identity.lastIndexOf("|"),item=state.items?.rows.find(row=>row.id===identity.slice(0,split)),field=item?.fields.find(row=>row.field===identity.slice(split+1));
    if(!field)throw new Error(`Item field ${identity} is no longer loaded`);
    if(field.control==="number")numberEdit(value,`${item.name} ${field.field}`,field);
    if(field.control==="select"&&!field.options.includes(value))throw new Error(`${field.field} needs a known choice`);
  }
  for(const [identity,value] of Object.entries(state.shopEdits)){
    const split=identity.lastIndexOf("|"),field=SHOP_FIELDS.find(row=>row.field===identity.slice(split+1));
    if(!field)throw new Error(`Shop field ${identity} is no longer loaded`);
    numberEdit(value,field.label,{minimum:field.min,maximum:field.max,step:field.step});
  }
  for(const [identity,value] of Object.entries(state.missionEdits)){
    const kind=identity.slice(identity.lastIndexOf("|")+1);
    numberEdit(value,`Mission ${identity}`,{...state.missions.limits.rewards[kind],step:1});
  }
  validateSettings();
  if(state.lootDirty){
    const bonus=state.lootDocument.corpseBonusItem,range=state.lootDocument.money.baseRoll.range;
    numberEdit(bonus.chancePercent,"Bonus chance",{minimum:0,maximum:100,step:1});
    for(const entry of bonus.entries)for(const key of ["quantity","weight"])numberEdit(entry[key],`Item ${entry.itemEnum} ${key}`,{minimum:0,maximum:100000,step:1});
    const minimum=numberEdit(range.minimum,"Money minimum",{minimum:0,maximum:100000}),maximum=numberEdit(range.maximum,"Money maximum",{minimum:0,maximum:100000});
    if(minimum>maximum)throw new Error("Money minimum must not exceed maximum");
  }
}

async function saveAll(){
  if(!dirtyCount()||state.activeSource!=="mine")return;
  try{
    validatePendingEdits();
    const saved=[];
    const itemGroups={};
    for(const [key,value] of Object.entries(state.itemEdits)){const split=key.lastIndexOf("|");const id=key.slice(0,split),field=key.slice(split+1);(itemGroups[id]||(itemGroups[id]=[])).push({field,value});}
    for(const [id,edits] of Object.entries(itemGroups)){
      const item=state.items.rows.find(row=>row.id===id);if(!item)throw new Error(`Item ${id} is no longer loaded`);
      await api("/api/item/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:item.source,index:item.index,expectedName:item.name,edits})});saved.push(item.name);
    }
    const shopGroups={};
    for(const [key,value] of Object.entries(state.shopEdits)){const split=key.lastIndexOf("|");const id=key.slice(0,split),field=key.slice(split+1);(shopGroups[id]||(shopGroups[id]=[])).push({field,value});}
    for(const [id,edits] of Object.entries(shopGroups)){
      const item=state.shops.rows.find(row=>row.id===id);if(!item)throw new Error(`Shop item ${id} is no longer loaded`);
      await api("/api/shop/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:item.source,rootHash:item.rootHash,itemIndex:item.itemIndex,expectedName:item.name,edits})});saved.push(`${item.shop}: ${item.name}`);
    }
    if(Object.keys(state.stringEdits).length)await stringsUI.savePending(saved);
    if(Object.keys(state.missionEdits).length){
      const overrides=[];
      for(const mission of state.missions.missions){
        const rewards={};
        for(const reward of MISSION_REWARDS){
          const raw=missionValue(mission,reward.key),value=numberEdit(raw,`${mission.name} ${reward.label}`,{...state.missions.limits.rewards[reward.key],step:1});
          if(!Number.isInteger(value))throw new Error(`${mission.name} ${reward.label.toLowerCase()} must be an integer`);
          if(value!==mission.baseRewards[reward.key])rewards[reward.key]=value;
        }
        if(Object.keys(rewards).length)overrides.push({id:mission.id,rewards});
      }
      const result=await api("/api/missions/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({schemaVersion:1,contract:"LexerRDR.mission-rewards",overrides})});saved.push(`${result.saved} mission reward field(s)`);
    }
    if(Object.keys(state.settingEdits).length){
      const edits=Object.entries(state.settingEdits).map(([identity,value])=>{const [section,key]=identity.split("\u0000");return {section,key,value};});
      await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});saved.push("LexerRDR.ini");
    }
    if(state.lootDirty){await api("/api/loot/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({document:state.lootDocument})});saved.push("LexerRDR.loot.json");}
    [state.files,state.items,state.shops,state.strings,state.missions,state.settings,state.loot,state.dashboard,state.vanilla.strings]=await Promise.all([api("/api/files"),api("/api/items"),api("/api/shops"),api("/api/string-tables"),api("/api/missions"),optionalRuntime("/api/settings"),optionalRuntime("/api/loot"),api("/api/dashboard"),api("/api/string-tables?dataset=vanilla")]);
    if(state.stringTableId)await stringsUI.load(state.stringTableId,false);
    state.itemEdits={};state.shopEdits={};stringsUI.clearEdits();state.missionEdits={};state.settingEdits={};state.lootDocument=clone(state.loot.document);state.lootDirty=false;shell.history.clear();setStatus(`Saved to workspace: ${saved.join(", ")}. ${state.dashboard.deployment?.pending?"Deploy Project to rebuild the archive copies.":"Runtime-backed files are ready from the workspace."}`);render();
  }catch(error){setStatus("Save failed");showAlert({title:"Save failed",items:[{item:"Save",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
}

function navigate(tab){state.tab=tab;render();}
function renderVanillaOnly(){$("#toolbar").replaceChildren();$("#main").replaceChildren(el("section",{class:"card"},el("h2",{},"Vanilla"),el("p",{},"This page contains LexerRDR mod data and has no Vanilla game-file equivalent."),el("p",{},"Select a mod to edit this page.")));shell.refresh()}
function render(){document.querySelectorAll("nav button").forEach(button=>button.classList.toggle("active",button.dataset.tab===state.tab));if(state.booting)return;if(state.activeSource!=="mine"&&["loot","settings"].includes(state.tab))renderVanillaOnly();else if(state.tab==="items")renderItems();else if(state.tab==="shops")renderShops();else if(state.tab==="strings")stringsUI.render();else if(state.tab==="loot")renderLoot();else if(state.tab==="missions")renderMissions();else if(state.tab==="settings")renderSettings();else if(state.tab==="datamap")renderDataMap();else renderProject();}
async function switchProjectSource(value){const next=String(value||"mine")==="vanilla"?"vanilla":"mine";if(next===state.activeSource)return;state.activeSource=next;state.itemEdits={};state.shopEdits={};stringsUI.clearEdits();state.missionEdits={};state.settingEdits={};state.lootDocument=clone(state.loot?.document);state.lootDirty=false;if(next==="vanilla"){state.items=clone(state.vanilla.items);state.shops=clone(state.vanilla.shops);state.strings=clone(state.vanilla.strings);state.missions=clone(state.vanilla.missions)}else[state.items,state.shops,state.strings,state.missions]=await Promise.all([api("/api/items"),api("/api/shops"),api("/api/string-tables"),api("/api/missions")]);if(state.stringTableId)await stringsUI.load(state.stringTableId,false);shell.history?.clear();render()}
const shell=LexeditorUI.mountShell({
  host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"rdr",themeName:"rdr",theme:{bg:"#11100f",panel:"#1a1816","panel-2":"#211e1a",border:"#4e4237",text:"#e8ded0",muted:"#aa9b89",accent:"#a92b20","accent-text":"#fff5e8",highlight:"#c99a50",success:"#69955d",font:'RDRLino,"Segoe UI",sans-serif',"heading-font":"Redemption,Georgia,serif"}},
  tabs:[{id:"items",label:"Items"},{id:"shops",label:"Shops"},{id:"strings",label:"Strings"},{id:"loot",label:"Loot Tables"},{id:"missions",label:"Missions"},{id:"settings",label:"Tweaks"}],activeTab:()=>state.tab,navigate,help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the RDR Data Map",info:()=>navigate("project"),infoActive:()=>state.tab==="project",infoTitle:"Open RDR setup information",projectSources:()=>[{key:"vanilla",label:"Vanilla",path:"Prepared unchanged RDR game data"}],projectActiveSource:()=>state.activeSource,selectProjectSource:switchProjectSource,dirtyCount,readonly:()=>state.activeSource!=="mine",save:saveAll,
  history:{capture:historyCapture,restore:historyRestore,render,enabled:()=>!state.booting&&state.activeSource==="mine",limit:50}
});

async function optionalRuntime(path){
  try{return await api(path);}catch(error){return {available:false,file:path,sections:[],reason:error.message};}
}
async function boot(){
  try{[state.files,state.dashboard,state.items,state.shops,state.strings,state.missions,state.settings,state.loot,state.vanilla.items,state.vanilla.shops,state.vanilla.strings,state.vanilla.missions]=await Promise.all([api("/api/files"),api("/api/dashboard"),api("/api/items"),api("/api/shops"),api("/api/string-tables"),api("/api/missions"),optionalRuntime("/api/settings"),optionalRuntime("/api/loot"),api("/api/items?dataset=vanilla"),api("/api/shops?dataset=vanilla"),api("/api/string-tables?dataset=vanilla"),api("/api/missions?dataset=vanilla")]);if(state.dashboard.redHook.installed)await configureRedHook();state.lootDocument=state.loot.available?clone(state.loot.document):null;const firstTable=stringsUI.firstAvailableId();if(firstTable)await stringsUI.load(firstTable,false);state.booting=false;render();if(!state.dashboard.redHook.installed)renderRedHookNotice();LexeditorUI.finishPluginLoading();}
  catch(error){state.booting=false;LexeditorUI.finishPluginLoading();$("#main").textContent=`Failed to load RDR plugin: ${error.message}`;setStatus("Load failed");}
}
window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&dirtyCount())event.preventDefault();});
boot();

