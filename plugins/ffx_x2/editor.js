"use strict";

const {
  el, clone, mountShell, finishPluginLoading, showAlert, showToast, confirmAction,
  pagedListDetail, columnList, columnPreferences, detailPanel, detailSection,
  detailField, detailNote, multiNumberRow, toggleRow, subtabBar, readonlyField,
  recordId, infoHelp, integrationStatus, dataMap, modLoaderSection, formatNumber,
  stack, actionRow, badge, panelLayout
}=LexeditorUI;

const $=selector=>document.querySelector(selector);
const post=body=>({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
async function api(path,options){
  const response=await fetch(path,options);
  let value={};
  try{value=await response.json()}catch(_error){}
  if(!response.ok)throw new Error(value.error||("Request failed: "+response.status));
  return value;
}

const GROUPS={
  "ffx-battle":{
    label:"FFX Battle",
    help:"Character bases, auto-ability elements, CTB timing, Mix results and ability animation IDs.",
    datasets:["ffx-player-stats","ffx-auto-abilities","ctb-base","mix-table","ffx-command","ffx-item","ffx-monmagic1","ffx-monmagic2"]
  },
  "ffx-economy":{
    label:"FFX Economy",
    help:"Treasure rewards and the proved gil-price tables.",
    datasets:["treasures","item-prices","auto-ability-prices"]
  },
  "ffx-shops":{
    label:"FFX Shops",
    help:"The sixteen proved inventory slots for item and gear shops.",
    datasets:["item-shops","gear-shops"]
  },
  "ffx2":{
    label:"FFX-2",
    help:"Proved ability animation IDs, accessory base abilities/prices and dressphere ability trees.",
    datasets:["ffx2-abilities","ffx2-accessories","ffx2-jobs"]
  },
  "archives":{
    label:"Archives",
    help:"Read-only browsing and byte-exact extraction from both installed VBF archives.",
    datasets:["archive-x","archive-x2"]
  }
};

const field=(key,label,options)=>Object.assign({key:key,label:label,type:"number",min:0,max:65535,step:1,column:true,pinned:true},options||{});
const simple=(options)=>Object.assign({kind:"simple",fields:[]},options);
const SPECS={
  "treasures":simple({
    label:"Treasure Rewards",endpoint:"/api/treasures",save:"/api/treasures/save",
    fields:[
      field("kind","Reward kind",{type:"select",choices:[[0,"Gil"],[2,"Item / command"],[5,"Gear"],[10,"Key item"]],help:"Chooses the reward family this treasure entry gives. Unknown existing values are preserved until you deliberately choose a known family."}),
      field("quantity","Quantity",{max:255,help:"Number of reward units. For gil rewards the game uses this value in hundreds of gil."}),
      field("typeId","Type ID",{max:65535,help:"Identifies the item, gear or key item inside the selected reward family. Gil rewards do not use this identifier."})
    ]
  }),
  "item-prices":simple({
    label:"Item / Command Prices",endpoint:"/api/item-prices",save:"/api/item-prices/save",
    context:[{key:"commandId",label:"Command / item ID",format:hex16}],
    fields:[field("gilPrice","Gil price",{max:4294967295,help:"Base gil price associated with this command or item identifier."})]
  }),
  "auto-ability-prices":simple({
    label:"Auto-Ability Prices",endpoint:"/api/auto-ability-prices",save:"/api/auto-ability-prices/save",
    context:[{key:"abilityId",label:"Auto-ability ID",format:hex16}],
    fields:[field("gilPrice","Gil price",{max:4294967295,help:"Base gil price associated with this auto-ability identifier."})]
  }),
  "ctb-base":simple({
    label:"CTB Timing",endpoint:"/api/ctb-base",save:"/api/ctb-base/save",
    context:[
      {key:"agility",label:"Agility",format:String},
      {key:"minIcv",label:"Derived minimum ICV",format:String},
      {key:"maxIcv",label:"Derived maximum ICV",format:String}
    ],
    fields:[
      field("tickSpeed","Tick speed",{max:255,help:"Timing value selected by this Agility row in the game's CTB lookup."}),
      field("icvBonus","ICV bonus",{max:255,help:"Initial-CTB bonus value selected by this Agility row."})
    ]
  }),
  "ffx-player-stats":simple({
    label:"Player Base Stats",endpoint:"/api/ffx-player-stats",save:"/api/ffx-player-stats/save",
    fields:[
      field("baseHp","Base HP",{max:4294967295,help:"Starting base HP used by this player-stat record."}),
      field("baseMp","Base MP",{max:4294967295,help:"Starting base MP used by this player-stat record."}),
      field("strength","Strength",{max:255,help:"Base Strength before progression and equipment modifiers."}),
      field("defense","Defense",{max:255,pinned:false,help:"Base physical Defense before progression and equipment modifiers."}),
      field("magic","Magic",{max:255,pinned:false,help:"Base Magic before progression and equipment modifiers."}),
      field("magicDefense","Magic Defense",{max:255,pinned:false,help:"Base magical Defense before progression and equipment modifiers."}),
      field("agility","Agility",{max:255,pinned:false,help:"Base Agility used by this character record."}),
      field("luck","Luck",{max:255,pinned:false,help:"Base Luck used by this character record."}),
      field("evasion","Evasion",{max:255,pinned:false,help:"Base Evasion used by this character record."}),
      field("accuracy","Accuracy",{max:255,pinned:false,help:"Base Accuracy used by this character record."})
    ]
  }),
  "ffx-command":animationSpec("Commands","command"),
  "ffx-item":animationSpec("Items","item"),
  "ffx-monmagic1":animationSpec("Monster Magic 1","monmagic1"),
  "ffx-monmagic2":animationSpec("Monster Magic 2","monmagic2"),
  "ffx2-abilities":simple({
    label:"FFX-2 Abilities",endpoint:"/api/ffx2-abilities",save:"/api/ffx2-abilities/save",
    context:[
      {key:"nameKey",label:"Name text key",format:hex16,help:"Localized name reference carried by this ability record."},
      {key:"descriptionKey",label:"Description text key",format:hex16,help:"Localized description reference carried by this ability record."}
    ],
    fields:[
      field("animation1","Animation 1",{max:65535,help:"First animation resource identifier used by this ability record."}),
      field("animation2","Animation 2",{max:65535,help:"Second animation resource identifier used by this ability record."})
    ]
  }),
  "ffx-auto-abilities":{
    kind:"elements",label:"Auto-Ability Elements",endpoint:"/api/ffx-auto-abilities",save:"/api/ffx-auto-abilities/save"
  },
  "mix-table":{
    kind:"mix",label:"Rikku Mix Results",endpoint:"/api/mix-table",save:"/api/mix-table/save"
  },
  "item-shops":{
    kind:"slots",slotKey:"itemIds",editKey:"itemId",label:"Item Shops",endpoint:"/api/item-shops",save:"/api/item-shops/save",
    slotHelp:"Item or command ID stocked in this shop slot."
  },
  "gear-shops":{
    kind:"slots",slotKey:"gearIds",editKey:"gearId",label:"Gear Shops",endpoint:"/api/gear-shops",save:"/api/gear-shops/save",
    slotHelp:"Gear record index stocked in this shop slot."
  },
  "ffx2-accessories":{
    kind:"accessories",label:"FFX-2 Accessories",endpoint:"/api/ffx2-accessories",save:"/api/ffx2-accessories/save"
  },
  "ffx2-jobs":{
    kind:"jobs",label:"FFX-2 Dresspheres",endpoint:"/api/ffx2-jobs",save:"/api/ffx2-jobs/save"
  },
  "archive-x":{kind:"archive",game:"x",label:"FFX Archive"},
  "archive-x2":{kind:"archive",game:"x2",label:"FFX-2 Archive"}
};

function animationSpec(label,table){
  return simple({
    label:label+" Animations",
    endpoint:"/api/ffx-commands?table="+encodeURIComponent(table),
    save:"/api/ffx-commands/save",
    table:table,
    fields:[
      field("animation1","Animation 1",{max:65535,help:"First animation resource identifier used by this entry."}),
      field("animation2","Animation 2",{max:65535,help:"Second animation resource identifier used by this entry."})
    ]
  });
}
function hex16(value){return "0x"+Number(value||0).toString(16).toUpperCase().padStart(4,"0")}
function numberText(value){return Number.isFinite(Number(value))?formatNumber(Number(value)):String(value==null?"":value)}
function choiceLabel(field,value){
  return field.choices?.find(pair=>Number(pair[0])===Number(value))?.[1] || ("Unknown "+value);
}
function elementMaskLabel(value){
  const bits=[[1,"Fire"],[2,"Ice"],[4,"Thunder"],[8,"Water"],[16,"Holy"]];
  const labels=bits.filter(([bit])=>(Number(value)&bit)!==0).map(([_bit,label])=>label);
  return labels.length?labels.join(" · "):"None";
}
function equal(a,b){return JSON.stringify(a)===JSON.stringify(b)}
function rowKey(row){return Number(row.id)}
function labelForRow(spec,row){return spec.label.replace(/s$/,"")+" record "+row.id}

const state={
  tab:"ffx-battle",subtabs:{},datasets:{},dashboard:null,dataMap:null,
  mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1],
  busy:false,booting:true,error:"",archiveQueries:{x:"",x2:""}
};
for(const [groupKey,group] of Object.entries(GROUPS))state.subtabs[groupKey]=group.datasets[0];

function datasetState(key){
  if(!state.datasets[key])state.datasets[key]={
    loaded:false,loading:false,error:"",data:null,baseline:null,query:"",page:0,pageSize:15,
    selected:null,sort:{key:"id",dir:1},prefs:null
  };
  return state.datasets[key];
}

function currentDatasetKey(){return state.subtabs[state.tab]||GROUPS[state.tab]?.datasets[0]||""}
function dirtyRows(ds){
  if(!ds.loaded||!ds.data||!ds.baseline)return[];
  const before=new Map(ds.baseline.rows.map(row=>[rowKey(row),row]));
  return ds.data.rows.filter(row=>!equal(row,before.get(rowKey(row))));
}
function dirtyCount(){return Object.values(state.datasets).reduce((sum,ds)=>sum+dirtyRows(ds).length,0)}
function pendingChanges(){
  const changes=[];
  for(const [key,ds] of Object.entries(state.datasets)){
    const spec=SPECS[key]; if(!spec||spec.kind==="archive")continue;
    for(const row of dirtyRows(ds))changes.push({label:spec.label+" / record "+row.id,before:"saved",after:"modified"});
  }
  return changes;
}
function refreshShell(){shell?.refresh?.()}
function markChanged(){refreshShell()}
function setLoading(message){
  $("#main").replaceChildren(el("div",{class:"lex-notice",role:"status"},message||"Loading FFX/X-2 data…"));
}
function setError(message){
  $("#main").replaceChildren(el("div",{class:"lex-notice lex-tone-warning",role:"alert"},message));
}

async function ensureDataset(key,force){
  const spec=SPECS[key],ds=datasetState(key);
  if(spec.kind==="archive")return ensureArchive(key,force);
  if(ds.loaded&&!force)return ds;
  // Join an in-flight load instead of rendering an empty dataset: fast tab
    // switches otherwise race and the later render wins with no data.
  if(ds.loading&&ds.promise)return ds.promise;
  ds.loading=true;ds.error="";
  ds.promise=(async()=>{
    try{
      const data=await api(spec.endpoint);
      ds.data=clone(data);ds.baseline=clone(data);ds.loaded=true;
      if(ds.selected==null||!data.rows.some(row=>rowKey(row)===ds.selected))ds.selected=data.rows[0]?rowKey(data.rows[0]):null;
      if(!ds.prefs)ds.prefs=columnPreferences("ffxx2-"+key,columnsFor(key),()=>render());
    }catch(error){ds.error=error.message;ds.loaded=false;throw error}
    finally{ds.loading=false}
    return ds;
  })();
  return ds.promise;
}

async function ensureArchive(key,force){
  const spec=SPECS[key],ds=datasetState(key),query=state.archiveQueries[spec.game]||"";
  if(ds.loaded&&!force&&ds.loadedQuery===query)return ds;
  if(ds.loading&&ds.promise)return ds.promise;
  ds.loading=true;ds.error="";
  ds.promise=(async()=>{
  try{
    let entries=[],offset=0,total=0,headerMd5="";
    do{
      const page=await api("/api/archive?game="+encodeURIComponent(spec.game)+"&q="+encodeURIComponent(query)+"&offset="+offset+"&limit=250");
      total=page.total;headerMd5=page.headerMd5;entries.push(...page.entries);offset=entries.length;
      if(!page.entries.length)break;
    }while(entries.length<total);
    const rows=entries.map((entry,index)=>Object.assign({id:index},entry));
    ds.data={game:spec.game,headerMd5:headerMd5,total:total,rows:rows};
    ds.baseline=clone(ds.data);ds.loaded=true;ds.loadedQuery=query;
    if(ds.selected==null||!rows.some(row=>row.path===ds.selected))ds.selected=rows[0]?.path||null;
  }catch(error){ds.error=error.message;ds.loaded=false;throw error}
  finally{ds.loading=false}
  return ds;
  })();
  return ds.promise;
}

function updateValue(key,row,fieldKey,value){
  const spec=SPECS[key];
  if(spec.kind==="simple"){
    const f=spec.fields.find(item=>item.key===fieldKey);
    row[fieldKey]=f?.type==="select"?Number(value):Number(value);
  }else row[fieldKey]=value;
  markChanged();
}

function choiceEditor(field,row,commit){
  const select=el("select",{"aria-label":field.label});
  const known=new Map(field.choices.map(pair=>[String(pair[0]),pair[1]]));
  if(!known.has(String(row[field.key])))select.append(el("option",{value:String(row[field.key])},"Unknown "+row[field.key]));
  for(const pair of field.choices)select.append(el("option",{value:String(pair[0])},pair[1]));
  select.value=String(row[field.key]);
  select.addEventListener("change",()=>commit(Number(select.value)));
  select.addEventListener("keydown",event=>{
    if(event.key==="Escape"){event.preventDefault();commit(undefined)}
    if(event.key==="Enter"){event.preventDefault();commit(Number(select.value))}
  });
  select.addEventListener("blur",()=>commit(Number(select.value)));
  return select;
}

function columnsFor(key){
  const spec=SPECS[key];
  if(spec.kind==="archive")return[
    {key:"path",label:"Archive path",sortable:true,pointerColumn:true},
    {key:"bytes",label:"Bytes",numeric:true,sortable:true},
    {key:"blocks",label:"Blocks",numeric:true,sortable:true},
    {key:"staged",label:"Project copy",sortable:true,render:row=>row.staged?"Staged":"Archive only"}
  ];
  const base=[{key:"id",label:"Record",numeric:true,sortable:true,pinned:true}];
  if(spec.kind==="simple"){
    for(const context of spec.context||[])base.push({key:context.key,label:context.label,sortable:true,pinned:false,render:row=>context.format?context.format(row[context.key]):row[context.key]});
    for(const f of spec.fields){
      base.push({
        key:f.key,label:f.label,sortable:true,numeric:f.type!=="select",min:f.min,max:f.max,step:f.step,
        choices:f.type==="select"?undefined:null,pinned:f.pinned!==false,help:f.help,
        render:f.type==="select"?(row=>choiceLabel(f,row[f.key])):undefined,
        sortValue:f.type==="select"?(row=>choiceLabel(f,row[f.key])):undefined,
        edit:(row,value)=>{row[f.key]=Number(value);markChanged()},
        editor:f.type==="select"?(row,commit)=>choiceEditor(f,row,commit):undefined
      });
    }
  }else if(spec.kind==="elements"){
    base.push({key:"abilityId",label:"Ability ID",sortable:true,render:row=>hex16(row.abilityId)});
    for(const name of ["strike","absorb","immune","resist","weak"])base.push({
      key:name,label:name[0].toUpperCase()+name.slice(1),sortable:true,pinned:name==="strike",
      render:row=>elementMaskLabel(row[name]),sortValue:row=>row[name]
    });
  }else if(spec.kind==="mix"){
    base.push({key:"originCommandId",label:"First ingredient",sortable:true,render:row=>hex16(row.originCommandId)});
    base.push({key:"definedResults",label:"Defined results",numeric:true,sortable:true});
  }else if(spec.kind==="slots"){
    base.push({key:"occupiedSlots",label:"Occupied",numeric:true,sortable:true});
    base.push({key:"legacyRate",label:"Legacy rate",numeric:true,sortable:true,pinned:false});
  }else if(spec.kind==="accessories"){
    base.push({key:"nameKey",label:"Name key",sortable:true,render:row=>hex16(row.nameKey)});
    base.push({key:"price",label:"Price",numeric:true,sortable:true,edit:(row,value)=>{row.price=Number(value);markChanged()},min:0,max:4294967295});
    base.push({key:"icon",label:"Icon",numeric:true,sortable:true,pinned:false});
  }else if(spec.kind==="jobs"){
    base.push({key:"nameKey",label:"Name key",sortable:true,render:row=>hex16(row.nameKey)});
    base.push({key:"berserkAction",label:"Berserk action",sortable:true,pinned:false,render:row=>hex16(row.berserkAction)});
  }
  return base;
}

function filteredRows(key,ds){
  const q=String(ds.query||"").trim().toLocaleLowerCase();
  let rows=[...(ds.data?.rows||[])];
  if(q)rows=rows.filter(row=>JSON.stringify(row).toLocaleLowerCase().includes(q));
  const column=columnsFor(key).find(item=>item.key===ds.sort.key)||{key:"id"};
  const value=row=>column.sortValue?column.sortValue(row):row[column.key];
  rows.sort((a,b)=>{
    const left=value(a),right=value(b);
    const result=typeof left==="number"&&typeof right==="number"?left-right:String(left??"").localeCompare(String(right??""),undefined,{numeric:true,sensitivity:"base"});
    return result*ds.sort.dir;
  });
  return rows;
}
function changeSort(ds,key){
  ds.sort=ds.sort.key===key?{key:key,dir:-ds.sort.dir}:{key:key,dir:1};
  ds.page=0;render();
}

function numberInput(key,row,f){
  const input=el("input",{type:"number",min:f.min,max:f.max,step:f.step||1,value:row[f.key],"aria-label":f.label,
    oninput:event=>{if(event.target.value!==""){row[f.key]=Number(event.target.value);markChanged()}},
    onchange:()=>render()});
  return input;
}
function selectInput(key,row,f){
  const select=el("select",{"aria-label":f.label,onchange:event=>{row[f.key]=Number(event.target.value);markChanged();render()}});
  const known=new Map(f.choices.map(pair=>[String(pair[0]),pair[1]]));
  if(!known.has(String(row[f.key])))select.append(el("option",{value:String(row[f.key])},"Unknown "+row[f.key]));
  for(const pair of f.choices)select.append(el("option",{value:String(pair[0])},pair[1]));
  select.value=String(row[f.key]);return select;
}
function pinFor(ds,key,label){return ds.prefs?.pinButton?.(key,label)||null}
function contextFields(spec,row){
  return (spec.context||[]).map(c=>detailField({
    label:c.label.toUpperCase(),control:readonlyField(c.format?c.format(row[c.key]):String(row[c.key])),
    help:c.help?infoHelp(c.help):null
  }));
}

function simpleDetail(key,ds,row){
  const spec=SPECS[key],fields=[];
  fields.push(...contextFields(spec,row));
  for(const f of spec.fields){
    const control=f.type==="select"?selectInput(key,row,f):numberInput(key,row,f);
    fields.push(detailField({
      label:f.label.toUpperCase(),control:control,min:f.min,max:f.max,dataType:f.type==="select"?"ENUM":"INT",
      help:f.help?infoHelp(f.help):null,pin:pinFor(ds,f.key,f.label),attrs:{"data-lex-property":f.key}
    }));
  }
  return detailPanel({
    title:spec.label.replace(/s$/,""),identity:recordId(row.id),
    meta:ds.data.source==="project"?"Project overlay":"Installed archive baseline",
    body:[detailSection({title:"EDITABLE DATA",body:fields})]
  });
}

const ELEMENT_FIELDS={
  strike:"Adds the selected elemental Strike properties to attacks using this auto-ability.",
  absorb:"Selected elements are absorbed rather than damaging the target.",
  immune:"Selected elements are ignored by the target.",
  resist:"Selected elements are resisted by the target.",
  weak:"Selected elements are treated as weaknesses by the target."
};
function elementDetail(key,ds,row){
  const spec=SPECS[key],sections=[];
  for(const fieldKey of ["strike","absorb","immune","resist","weak"]){
    const toggles=(ds.data.elements||[]).map(element=>{
      const bit=Number(element.bit);
      return{
        key:element.key,label:element.label,bit:Math.log2(bit),
        checked:(row[fieldKey]&bit)!==0,
        help:element.label+" is included in the "+fieldKey+" mask.",
        change:on=>{row[fieldKey]=on?(row[fieldKey]|bit):(row[fieldKey]&~bit);markChanged()}
      };
    });
    sections.push(detailField({
      label:fieldKey.toUpperCase(),dataType:"FLAGS",min:0,max:31,
      help:infoHelp(ELEMENT_FIELDS[fieldKey]),control:toggleRow({label:fieldKey+" elements",value:()=>row[fieldKey],toggles:toggles}),
      pin:pinFor(ds,fieldKey,fieldKey),attrs:{"data-lex-property":fieldKey}
    }));
  }
  return detailPanel({
    title:"Auto-ability elements",identity:recordId(row.id),meta:"Ability "+hex16(row.abilityId),
    body:[detailSection({title:"ELEMENT BEHAVIOUR",body:sections}),
      detailSection({title:"PRESERVED DATA",body:[detailNote("Unknown upper element bits and every non-element field remain untouched by this editor.")]})]
  });
}
function groupedNumbers(entries,columns){
  return multiNumberRow(entries,{columns:columns||2});
}
function mixDetail(key,ds,row){
  const groups=[];
  for(let start=0;start<row.resultCommandIds.length;start+=16){
    const entries=[];
    for(let index=start;index<Math.min(start+16,row.resultCommandIds.length);index++){
      const input=el("input",{type:"number",min:0,max:65535,step:1,value:row.resultCommandIds[index],
        "aria-label":"Partner "+index+" result command ID",
        oninput:event=>{if(event.target.value!==""){row.resultCommandIds[index]=Number(event.target.value);markChanged()}},
        onchange:()=>render()});
      entries.push({label:String(index),title:"Partner slot "+index,control:input});
    }
    groups.push(detailSection({title:"PARTNER SLOTS "+start+"–"+(Math.min(start+15,row.resultCommandIds.length-1)),body:[
      detailNote("Each value is the command produced when this first ingredient is mixed with the numbered partner slot."),
      groupedNumbers(entries,4)
    ]}));
  }
  return detailPanel({
    title:"Mix first ingredient",identity:recordId(row.id),meta:"Command "+hex16(row.originCommandId),
    body:groups
  });
}
function slotsDetail(key,ds,row){
  const spec=SPECS[key],values=row[spec.slotKey],groups=[];
  for(let start=0;start<values.length;start+=8){
    const entries=[];
    for(let index=start;index<Math.min(start+8,values.length);index++){
      const input=el("input",{type:"number",min:0,max:65535,step:1,value:values[index],
        "aria-label":"Slot "+(index+1)+" ID",
        oninput:event=>{if(event.target.value!==""){values[index]=Number(event.target.value);markChanged()}},
        onchange:()=>render()});
      entries.push({label:"Slot "+(index+1),title:spec.slotHelp,control:input});
    }
    groups.push(detailSection({title:"INVENTORY "+(start+1)+"–"+Math.min(start+8,values.length),body:[groupedNumbers(entries,2)]}));
  }
  groups.unshift(detailSection({title:"CONTEXT",body:[
    detailField({label:"OCCUPIED",control:readonlyField(String(row.occupiedSlots)),help:infoHelp("Number of nonzero inventory slots in this shop record.")}),
    detailField({label:"LEGACY RATE",control:readonlyField(String(row.legacyRate)),help:infoHelp("Existing leading shop rate is shown for context and is not part of the proved writable inventory surface.")})
  ]}));
  return detailPanel({
    title:spec.label.replace(/s$/,""),identity:recordId(row.id),meta:"16 proved inventory slots",body:groups
  });
}
function accessoryDetail(key,ds,row){
  const entries=row.abilityIds.map((value,index)=>{
    const input=el("input",{type:"number",min:0,max:65535,step:1,value:value,"aria-label":"Base ability "+(index+1),
      oninput:event=>{if(event.target.value!==""){row.abilityIds[index]=Number(event.target.value);markChanged()}},
      onchange:()=>render()});
    return{label:"Ability "+(index+1),control:input,title:"Base ability ID granted by this accessory."};
  });
  const price=el("input",{type:"number",min:0,max:4294967295,step:1,value:row.price,"aria-label":"Accessory price",
    oninput:event=>{if(event.target.value!==""){row.price=Number(event.target.value);markChanged()}},onchange:()=>render()});
  return detailPanel({
    title:"Accessory",identity:recordId(row.id),meta:"Name key "+hex16(row.nameKey),
    body:[
      detailSection({title:"CONTEXT",body:[
        detailField({label:"NAME KEY",control:readonlyField(hex16(row.nameKey)),help:infoHelp("Localized name reference associated with this accessory.")}),
        detailField({label:"HELP KEY",control:readonlyField(hex16(row.helpKey)),help:infoHelp("Localized help-text reference associated with this accessory.")}),
        detailField({label:"ICON",control:readonlyField(String(row.icon)),help:infoHelp("Existing icon identifier; the proved writable accessory surface does not include it.")})
      ]}),
      detailSection({title:"PRICE",body:[detailField({label:"GIL PRICE",control:price,min:0,max:4294967295,dataType:"INT",pin:pinFor(ds,"price","Price"),attrs:{"data-lex-property":"price"},help:infoHelp("Base gil price stored by this accessory record.")})]}),
      detailSection({title:"BASE ABILITIES",body:[groupedNumbers(entries,2)]})
    ]
  });
}
function jobDetail(key,ds,row){
  const groups=[];
  for(let start=0;start<row.abilities.length;start+=4){
    const entries=[];
    for(let index=start;index<Math.min(start+4,row.abilities.length);index++){
      const pair=row.abilities[index];
      const req=el("input",{type:"number",min:0,max:65535,step:1,value:pair.requirementId,"aria-label":"Dressphere "+row.id+" ability "+(index+1)+" requirement",
        oninput:event=>{if(event.target.value!==""){pair.requirementId=Number(event.target.value);markChanged()}},onchange:()=>render()});
      const ability=el("input",{type:"number",min:0,max:65535,step:1,value:pair.abilityId,"aria-label":"Dressphere "+row.id+" ability "+(index+1),
        oninput:event=>{if(event.target.value!==""){pair.abilityId=Number(event.target.value);markChanged()}},onchange:()=>render()});
      entries.push({label:"Req "+(index+1),control:req,title:"Ability ID that must be learned before this slot is available."});
      entries.push({label:"Ability "+(index+1),control:ability,title:"Ability learned in this dressphere slot."});
    }
    groups.push(detailSection({title:"ABILITY PAIRS "+(start+1)+"–"+Math.min(start+4,row.abilities.length),body:[groupedNumbers(entries,2)]}));
  }
  groups.unshift(detailSection({title:"CONTEXT",body:[
    detailField({label:"NAME KEY",control:readonlyField(hex16(row.nameKey)),help:infoHelp("Localized dressphere-name reference associated with this record.")}),
    detailField({label:"HELP KEY",control:readonlyField(hex16(row.helpKey)),help:infoHelp("Localized help-text reference associated with this dressphere.")}),
    detailField({label:"ICON",control:readonlyField(String(row.icon)),help:infoHelp("Existing dressphere icon identifier; it is not part of the proved writable surface.")}),
    detailField({label:"BERSERK ACTION",control:readonlyField(hex16(row.berserkAction)),help:infoHelp("Existing automatic action identifier; it is shown for context and not edited here.")})
  ]}));
  return detailPanel({
    title:"Dressphere",identity:recordId(row.id),meta:"16 requirement / learned-ability pairs",body:groups
  });
}

function detailFor(key,ds,row){
  const kind=SPECS[key].kind;
  if(kind==="simple")return simpleDetail(key,ds,row);
  if(kind==="elements")return elementDetail(key,ds,row);
  if(kind==="mix")return mixDetail(key,ds,row);
  if(kind==="slots")return slotsDetail(key,ds,row);
  if(kind==="accessories")return accessoryDetail(key,ds,row);
  if(kind==="jobs")return jobDetail(key,ds,row);
  return detailPanel({title:SPECS[key].label,body:[detailNote("No detail renderer is available.")]});
}

function renderRecordDataset(key,host){
  const spec=SPECS[key],ds=datasetState(key),rows=filteredRows(key,ds),columns=columnsFor(key);
  if(!rows.length){
    host.replaceChildren(el("div",{class:"lex-notice"},"No records match this search."));
    return;
  }
  if(ds.selected==null||!ds.data.rows.some(row=>rowKey(row)===ds.selected))ds.selected=rowKey(rows[0]);
  const view=pagedListDetail({
    rows:rows,key:row=>rowKey(row),slots:false,page:ds.page,pageSize:ds.pageSize,selected:ds.selected,noun:"records",
    splitKey:"ffxx2-"+key,defaultSplit:46,minLeft:300,minRight:330,
    search:{key:"ffxx2-"+key,value:ds.query,label:"Search "+spec.label,placeholder:"Search "+spec.label.toLocaleLowerCase()+"…",
      change:value=>{ds.query=value;ds.page=0;render()}},
    fit:{minRowHeight:38},
    master:({rows:shown,selected,select})=>columnList({
      rows:shown,key:row=>rowKey(row),selected:selected,select:row=>select(row),sortState:ds.sort,
      sort:column=>changeSort(ds,column),columnPreferences:ds.prefs,columns:columns,
      refresh:()=>render(),"aria-label":spec.label+" Table"
    }),
    detail:row=>detailFor(key,ds,row),
    emptyDetail:()=>detailPanel({title:spec.label,body:[detailNote("Select a record to edit it.")]}),
    sync:next=>{ds.page=next.page;ds.pageSize=next.pageSize;ds.selected=next.selected},
    change:next=>{ds.page=next.page;ds.pageSize=next.pageSize;ds.selected=next.selected;render()}
  });
  ds.page=view.page;
  host.replaceChildren(view);
}

function archiveColumns(){
  return[
    {key:"path",label:"Archive path",sortable:true},
    {key:"bytes",label:"Bytes",numeric:true,sortable:true},
    {key:"blocks",label:"Blocks",numeric:true,sortable:true},
    {key:"staged",label:"Project copy",sortable:true,render:row=>row.staged?"Staged":"Archive only"}
  ];
}
async function extractArchiveRow(spec,ds,row){
  try{
    await api("/api/project/extract",post({game:spec.game,path:row.path,headerMd5:ds.data.headerMd5}));
    await ensureArchive(spec.game==="x"?"archive-x":"archive-x2",true);
    state.dashboard=await api("/api/dashboard");state.dataMap=await api("/api/datamap");
    showToast("Extracted byte-identical project copy.");render();
  }catch(error){showAlert({title:"Could not extract file",message:error.message})}
}
function archiveDetail(key,ds,row){
  const spec=SPECS[key];
  const extract=el("button",{type:"button",disabled:row.staged,onclick:()=>extractArchiveRow(spec,ds,row)},row.staged?"Already staged":"Extract to project");
  return detailPanel({
    title:"Archive entry",meta:spec.label,body:[
      detailSection({title:"SOURCE",body:[
        detailField({label:"ARCHIVE PATH",control:readonlyField(row.path),help:infoHelp("Path stored in the installed VBF archive.")}),
        detailField({label:"EFL PATH",control:readonlyField(row.eflPath),help:infoHelp("Canonical path Fahrenheit uses for a project replacement.")}),
        detailField({label:"BYTES",control:readonlyField(numberText(row.bytes))}),
        detailField({label:"BLOCKS",control:readonlyField(String(row.blocks))}),
        detailField({label:"PROJECT COPY",control:readonlyField(row.staged?"Present":"Not extracted")})
      ]}),
      detailSection({title:"ACTION",body:[actionRow(extract)]})
    ]
  });
}
function renderArchive(key,host){
  const spec=SPECS[key],ds=datasetState(key);
  const rows=[...(ds.data?.rows||[])];
  const sort=ds.sort||{key:"path",dir:1};
  rows.sort((a,b)=>{
    const left=a[sort.key],right=b[sort.key];
    const result=typeof left==="number"&&typeof right==="number"?left-right:String(left??"").localeCompare(String(right??""),undefined,{numeric:true});
    return result*sort.dir;
  });
  if(ds.selected==null||!rows.some(row=>row.path===ds.selected))ds.selected=rows[0]?.path||null;
  const view=pagedListDetail({
    rows:rows,key:row=>row.path,slots:false,page:ds.page,pageSize:ds.pageSize,selected:ds.selected,noun:"files",
    splitKey:"ffxx2-"+key,defaultSplit:56,minLeft:360,minRight:300,fit:{minRowHeight:38},
    search:{key:"ffxx2-"+key,value:state.archiveQueries[spec.game]||"",label:"Search "+spec.label,
      placeholder:"Search the complete "+spec.label.toLocaleLowerCase()+"…",change:value=>{state.archiveQueries[spec.game]=value;ds.page=0;ds.loaded=false;render()}},
    master:({rows:shown,selected,select})=>columnList({
      rows:shown,key:row=>row.path,selected:selected,select:row=>select(row),sortState:sort,
      sort:column=>{ds.sort=sort.key===column?{key:column,dir:-sort.dir}:{key:column,dir:1};ds.page=0;render()},
      columns:archiveColumns(),"aria-label":spec.label+" Table"
    }),
    detail:row=>archiveDetail(key,ds,row),
    emptyDetail:()=>detailPanel({title:spec.label,body:[detailNote("No archive files match this search.")]}),
    sync:next=>{ds.page=next.page;ds.pageSize=next.pageSize;ds.selected=next.selected},
    change:next=>{ds.page=next.page;ds.pageSize=next.pageSize;ds.selected=next.selected;render()}
  });
  ds.page=view.page;host.replaceChildren(view);
}

async function renderGroup(){
  const group=GROUPS[state.tab],key=currentDatasetKey(),spec=SPECS[key];
  const tabs=group.datasets.map(dataset=>({id:dataset,label:SPECS[dataset].label,help:SPECS[dataset].kind==="archive"?"Browse and extract the installed archive without rewriting it.":"Open the proved structured editor for this table."}));
  const content=el("div",{});
  const page=stack(subtabBar({tabs:tabs,active:key,label:group.label+" datasets",change:value=>{state.subtabs[state.tab]=value;render()}}),content);
  $("#main").replaceChildren(page);
  content.replaceChildren(el("div",{class:"lex-notice",role:"status"},"Loading "+spec.label+"…"));
  try{
    const ds=await ensureDataset(key,false);
    if(state.tab!==Object.keys(GROUPS).find(groupKey=>GROUPS[groupKey].datasets.includes(key))&&currentDatasetKey()!==key)return;
    if(spec.kind==="archive")renderArchive(key,content);else renderRecordDataset(key,content);
  }catch(error){content.replaceChildren(el("div",{class:"lex-notice lex-tone-warning",role:"alert"},"Could not load "+spec.label+": "+error.message))}
  refreshShell();
}

function mapView(){
  const view=dataMap({
    rows:state.dataMap?.rows||[],query:state.mapQuery,status:state.mapStatus,page:state.mapPage,sort:state.mapSort,pageSize:50,
    open:row=>{
      if(!row.target)return;
      if(row.target==="info"){state.tab="info";render();return}
      const match=Object.entries(GROUPS).find(([_groupKey,group])=>group.datasets.includes(row.target));
      if(row.target==="ffx-commands"){
        state.tab="ffx-battle";state.subtabs["ffx-battle"]="ffx-command";
      }else if(match){state.tab=match[0];state.subtabs[state.tab]=row.target}
      if(row.datasetKey&&["command","item","monmagic1","monmagic2"].includes(row.datasetKey)){
        state.tab="ffx-battle";state.subtabs["ffx-battle"]="ffx-"+row.datasetKey;
      }
      render();
    },
    changeQuery:value=>{state.mapQuery=value;state.mapPage=0;render()},
    changeStatus:value=>{state.mapStatus=value;state.mapPage=0;render()},
    changePage:page=>{state.mapPage=page;render()},
    changeSort:key=>{const active=state.mapSort[0],dir=state.mapSort[1];state.mapSort=[key,active===key?-dir:1];render()}
  });
  state.mapPage=view.page;$("#main").replaceChildren(view.content);
}

function statusText(ready,readyText,missingText){
  return badge(ready?readyText:missingText,ready?{tone:"success"}:{});
}
async function deploymentAction(action){
  if(state.busy)return;
  if(dirtyCount()){showAlert({title:"Save project changes first",message:"Deployment uses files already saved in the project overlay."});return}
  if(action==="revert"){
    const ok=await confirmAction({title:"Revert Lexeditor Fahrenheit deployment?",message:"Only the Lexeditor-owned file-only mod is removed. Unrelated Fahrenheit loadorder entries are preserved.",confirmLabel:"Revert",cancelLabel:"Cancel"});
    if(!ok)return;
  }
  state.busy=true;refreshShell();
  try{
    await api("/api/deployment/"+action,post({}));
    state.dashboard=await api("/api/dashboard");state.dataMap=await api("/api/datamap");render();
  }catch(error){showAlert({title:"Deployment failed",message:error.message})}
  finally{state.busy=false;refreshShell()}
}
async function play(game){
  if(state.busy)return;
  try{await api("/api/play",post({game:game}));showToast(game==="x"?"FFX launch requested through Fahrenheit Stage 0.":"FFX-2 launch requested through Fahrenheit Stage 0.")}
  catch(error){showAlert({title:"Could not start game",message:error.message})}
}
function infoView(){
  const dash=state.dashboard||{},launch=dash.launch||{},deploy=dash.deployment||{},game=dash.game||{};
  const games=launch.games||{};
  const gamePanel=detailPanel({title:"Collection",meta:"Steam app 359870",body:[
    detailSection({title:"GAME",body:[
      detailField({label:"ROOT",control:readonlyField(game.root||"Unavailable")}),
      detailField({label:"FFX",control:statusText(!!games.x?.ready,"Executable ready","Executable missing"),help:infoHelp("Lexeditor starts FFX through Fahrenheit Stage 0, not through the Square Enix collection launcher.")}),
      detailField({label:"FFX-2",control:statusText(!!games.x2?.ready,"Executable ready","Executable missing"),help:infoHelp("Lexeditor starts FFX-2 through Fahrenheit Stage 0, not through the collection launcher.")})
    ]}),
    detailSection({title:"PLAY",body:[actionRow(
      el("button",{type:"button",disabled:!games.x?.ready||!launch.ready,onclick:()=>play("x")},"Play FFX"),
      el("button",{type:"button",disabled:!games.x2?.ready||!launch.ready,onclick:()=>play("x2")},"Play FFX-2")
    )]})
  ]});
  const helperPanel=detailPanel({title:"Fahrenheit",meta:"External File Loader runtime",body:[
    detailSection({title:"RUNTIME",body:[
      detailField({label:"STAGE 0",control:statusText(!!launch.stage0Ready,"Ready","Missing")}),
      detailField({label:"STAGE 1",control:statusText(!!launch.stage1Ready,"Ready","Missing")}),
      detailNote("This branch currently interoperates with an installed Fahrenheit runtime. The helper packaging/update audit remains active until a pinned, license-safe distribution path is proved.")
    ]})
  ]});
  const deploymentPanel=detailPanel({title:"Project & Deployment",meta:dash.project?.root||"",body:[
    detailSection({title:"PROJECT",body:[
      detailField({label:"FILES",control:readonlyField(String(dash.project?.fileCount||0))}),
      detailField({label:"DEPLOYED",control:readonlyField(deploy.deployed?"Yes":"No")})
    ]}),
    detailSection({title:"ACTIONS",body:[actionRow(
      el("button",{type:"button",disabled:state.busy||!deploy.fahrenheitReady,onclick:()=>deploymentAction("deploy")},"Deploy Project"),
      el("button",{type:"button",disabled:state.busy||!deploy.deployed,onclick:()=>deploymentAction("revert")},"Revert")
    )]}),
    modLoaderSection({
      loader:"Fahrenheit External File Loader. Lexeditor owns one file-only mod and does not rebuild either installed VBF.",
      output:"Project replacements live under efl/x for FFX and efl/x2 for FFX-2, then deploy into the Lexeditor-owned Fahrenheit mod.",
      order:"Lexeditor adds exactly one lexeditor-ffx-x2 loadorder entry and preserves unrelated entries.",
      safety:"Installed FFX_Data.vbf and FFX2_Data.vbf stay read-only; stale source hashes fail closed before structured saves.",
      removal:"Revert removes only the unchanged Lexeditor-owned deployment and its exact loadorder entry."
    })
  ]});
  $("#main").replaceChildren(panelLayout([gamePanel,helperPanel,deploymentPanel],{layoutKey:"ffx-x2-info"}));
}

async function buildEdits(key,ds){
  const spec=SPECS[key],before=new Map(ds.baseline.rows.map(row=>[rowKey(row),row])),edits=[];
  for(const row of dirtyRows(ds)){
    const old=before.get(rowKey(row));
    if(spec.kind==="simple"){
      const edit={id:row.id};
      for(const f of spec.fields)edit[f.key]=row[f.key];
      edits.push(edit);
    }else if(spec.kind==="elements"){
      edits.push({id:row.id,strike:row.strike,absorb:row.absorb,immune:row.immune,resist:row.resist,weak:row.weak});
    }else if(spec.kind==="mix"){
      const results=[];
      row.resultCommandIds.forEach((value,index)=>{if(value!==old.resultCommandIds[index])results.push({partner:index,resultCommandId:value})});
      if(results.length)edits.push({id:row.id,results:results});
    }else if(spec.kind==="slots"){
      const slots=[];
      row[spec.slotKey].forEach((value,index)=>{if(value!==old[spec.slotKey][index])slots.push({slot:index,[spec.editKey]:value})});
      if(slots.length)edits.push({id:row.id,slots:slots});
    }else if(spec.kind==="accessories"){
      const edit={id:row.id},abilities=[];
      if(row.price!==old.price)edit.price=row.price;
      row.abilityIds.forEach((value,index)=>{if(value!==old.abilityIds[index])abilities.push({slot:index,abilityId:value})});
      if(abilities.length)edit.abilities=abilities;
      edits.push(edit);
    }else if(spec.kind==="jobs"){
      const abilities=[];
      row.abilities.forEach((pair,index)=>{
        const prior=old.abilities[index];
        if(pair.requirementId!==prior.requirementId||pair.abilityId!==prior.abilityId)abilities.push({slot:index,requirementId:pair.requirementId,abilityId:pair.abilityId});
      });
      if(abilities.length)edits.push({id:row.id,abilities:abilities});
    }
  }
  return edits;
}
async function saveAll(){
  if(state.busy)return;
  state.busy=true;refreshShell();
  try{
    for(const [key,ds] of Object.entries(state.datasets)){
      const spec=SPECS[key];if(!spec||spec.kind==="archive"||!dirtyRows(ds).length)continue;
      const edits=await buildEdits(key,ds);if(!edits.length)continue;
      const request={headerMd5:ds.baseline.headerMd5,baselineSha256:ds.baseline.baselineSha256,edits:edits};
      if(spec.table)request.table=spec.table;
      const saved=await api(spec.save,post(request));
      ds.data=clone(saved);ds.baseline=clone(saved);ds.loaded=true;
    }
    state.dashboard=await api("/api/dashboard");state.dataMap=await api("/api/datamap");
    showToast("Saved FFX/X-2 project changes.");
  }catch(error){showAlert({title:"Save failed",message:error.message});throw error}
  finally{state.busy=false;render();refreshShell()}
}
async function discardAll(){
  for(const ds of Object.values(state.datasets)){
    if(ds.loaded&&ds.baseline&&ds.data)ds.data=clone(ds.baseline);
  }
  render();refreshShell();
}
function projectSources(){
  return[{key:"mine",label:"My Mod",path:state.dashboard?.project?.root||"Project overlay"},{key:"vanilla",label:"Vanilla",path:state.dashboard?.game?.root||"Installed VBF archives"}];
}

async function render(){
  if(state.booting)return;
  if(state.tab==="info")infoView();
  else if(state.tab==="datamap")mapView();
  else await renderGroup();
  refreshShell();
}
function navigate(tab){
  state.tab=tab;
  setLoading(tab==="info"?"Loading plugin information…":tab==="datamap"?"Loading Data Map…":"Loading "+(GROUPS[tab]?.label||"FFX/X-2")+"…");
  return render();
}

const shell=mountShell({
  host:"#lexeditor-shell",brand:"LEXEDITOR",
  plugin:{id:"ffx-x2",name:"Final Fantasy X/X-2 HD Remaster",themeName:"ffx-x2",theme:{accent:"#5f8fd3","accent-text":"#ffffff"}},
  tabs:Object.entries(GROUPS).map(([id,group])=>({id:id,label:group.label})),
  activeTab:()=>state.tab,navigate:navigate,
  help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the FFX/X-2 Data Map",
  info:()=>navigate("info"),infoActive:()=>state.tab==="info",infoTitle:"Open FFX/X-2 setup and runtime information",
  pendingChanges:pendingChanges,dirtyCount:dirtyCount,readonly:()=>state.busy,save:saveAll,discard:discardAll
});

async function boot(){
  setLoading("Loading FFX/X-2 collection…");
  try{
    const values=await Promise.all([api("/api/dashboard"),api("/api/datamap")]);
    state.dashboard=values[0];state.dataMap=values[1];state.booting=false;
    await render();finishPluginLoading();
  }catch(error){
    state.booting=false;finishPluginLoading();setError("Failed to load FFX/X-2 plugin: "+error.message);
  }
}
window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&dirtyCount())event.preventDefault()});
boot();
