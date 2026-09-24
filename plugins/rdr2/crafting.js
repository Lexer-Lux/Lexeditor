// ----- Crafting recipe graph -----
function customCraftingTouch(){state.customCraftingDirty=true;refreshGlobalSave();renderToolbarOnly();}
const CUSTOM_CRAFT_STATIONS={CUSTOM_ANY:"Anywhere in the custom menu",...CRAFT_COST_KEYS};
function customCraftingStationValues(){
  return [...new Set([
    ...Object.keys(CUSTOM_CRAFT_STATIONS),
    ...(state.customCrafting?.vanilla||[]).map(recipe=>recipe.station).filter(Boolean),
    ...(state.customCraftingDraft||[]).map(recipe=>recipe.station).filter(Boolean)
  ])].sort((a,b)=>(CUSTOM_CRAFT_STATIONS[a]||a).localeCompare(CUSTOM_CRAFT_STATIONS[b]||b));
}
function customCraftingStationSelect(recipe,onSet,readonly=false){
  const select=el("select",{class:"key",title:"Choose an existing crafting context. Free-entry context IDs are not allowed.",disabled:readonly,onchange:ev=>onSet(ev.target.value)});
  for(const value of customCraftingStationValues()){
    const option=el("option",{value},`${CUSTOM_CRAFT_STATIONS[value]||value} — ${value}`);
    if(value===recipe.station)option.selected=true;
    select.append(option);
  }
  return select;
}
function customCraftingCategory(recipe){return catalogItem(recipe.output_item)?.category||recipe.category||"";}
function customCraftingValidation(){
  const errors=[],byRow={},seen=new Map(),keys=new Set((refStore("mine").catalog?.items||[]).map(item=>item.key));
  const stations=new Set(customCraftingStationValues()),unlocks=new Set(recipeUnlockKeys());
  const add=(index,message)=>{errors.push(message);(byRow[index]??=[]).push(message);};
  state.customCraftingDraft.forEach((recipe,index)=>{
    const id=String(recipe.recipe_id||"").trim(),prefix=id||`Recipe ${index+1}`;
    if(!id)add(index,`${prefix}: Recipe ID is required`);else if(seen.has(id)){add(index,`${prefix}: Recipe ID must be unique`);add(seen.get(id),`${prefix}: Recipe ID must be unique`);}else seen.set(id,index);
    if(!String(recipe.title||"").trim())add(index,`${prefix}: Name is required`);
    if(!String(recipe.output_item||"").trim())add(index,`${prefix}: Output item is required`);
    else if(keys.size&&!keys.has(recipe.output_item))add(index,`${prefix}: Unknown output ${recipe.output_item}`);
    else if(recipe.category!==customCraftingCategory(recipe))add(index,`${prefix}: Category must follow the output item`);
    if(!recipe.station||!stations.has(recipe.station))add(index,`${prefix}: Context must be selected from the controlled list`);
    if(recipe.unlock&&!unlocks.has(recipe.unlock))add(index,`${prefix}: Unlock must be selected from an existing recipe unlock`);
    if(!Number.isInteger(+recipe.output_quantity)||+recipe.output_quantity<1)add(index,`${prefix}: Output quantity must be a positive whole number`);
    if(!recipe.ingredients?.length)add(index,`${prefix}: Add at least one ingredient`);
    (recipe.ingredients||[]).forEach((part,partIndex)=>{
      if(!String(part.item||"").trim())add(index,`${prefix}: Ingredient ${partIndex+1} needs an item`);
      else if(keys.size&&!keys.has(part.item))add(index,`${prefix}: Unknown ingredient ${part.item}`);
      if(!Number.isInteger(+part.quantity)||+part.quantity<1)add(index,`${prefix}: Ingredient ${partIndex+1} quantity must be a positive whole number`);
    });
  });
  return {errors,byRow};
}
function moveCustomCraftingRow(list,index,direction){const target=index+direction;if(target<0||target>=list.length)return;[list[index],list[target]]=[list[target],list[index]];customCraftingTouch();renderCrafting();}
function nextCustomCraftingId(output){
  const stem=String(output||"recipe").toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"");
  const used=new Set(state.customCraftingDraft.map(recipe=>recipe.recipe_id));let id=`lex_${stem}`,ordinal=2;
  while(used.has(id))id=`lex_${stem}_${ordinal++}`;
  return id;
}
function addCustomCraftingRecipe(){
  pickIdentifier("Recipe output",catalogItemOptions(),state.filters.craftSelCustom||"",output=>{
    const item=catalogItem(output),name=localizedValue(item?.nameKey)||output;
    state.customCraftingDraft.push({recipe_id:nextCustomCraftingId(output),category:item?.category||"",title:name,
      description:"",station:"CUSTOM_ANY",output_item:output,output_quantity:1,ingredients:[],unlock:""});
    state.filters.craftSelCustom=output;customCraftingTouch();renderCrafting();
  });
}
function moveCustomCraftingRecipe(output,sourceIndex,direction){
  const indexes=state.customCraftingDraft.map((recipe,index)=>recipe.output_item===output?index:-1).filter(index=>index>=0);
  const position=indexes.indexOf(sourceIndex),target=position+direction;if(position<0||target<0||target>=indexes.length)return;
  [state.customCraftingDraft[sourceIndex],state.customCraftingDraft[indexes[target]]]=[state.customCraftingDraft[indexes[target]],state.customCraftingDraft[sourceIndex]];
  customCraftingTouch();renderCrafting();
}
async function saveCustomCrafting(){
  if(!state.customCraftingDirty)return 0;
  for(const recipe of state.customCraftingDraft){const item=catalogItem(recipe.output_item);if(item)recipe.category=item.category;}
  const validation=customCraftingValidation();
  if(validation.errors.length){toast(`Fix ${validation.errors.length} custom recipe error(s)`,true);renderCrafting();throw new Error(validation.errors.join("\n"));}
  const result=await api("/api/custom-crafting",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({recipes:state.customCraftingDraft})},"mine");
  state.customCrafting.custom=JSON.parse(JSON.stringify(state.customCraftingDraft));state.customCrafting.errors=[];state.customCraftingDirty=false;refreshGlobalSave();toast(`Saved ${result.saved} custom recipe(s)`);renderCrafting();return result.saved;
}
function craftingCategoryLabel(value){return String(value||"—").replace("CI_CATEGORY_","").replaceAll("_"," ");}
function craftingOutputGroups(source){
  const groups=new Map();
  source.forEach((recipe,index)=>{
    const key=recipe.output_item||`__missing_${index}`;
    if(!groups.has(key)){
      const item=catalogItem(recipe.output_item),name=localizedValue(item?.nameKey)||recipe.title||recipe.output_item||"Missing output";
      groups.set(key,{key,item,name,category:item?.category||recipe.category||"",recipes:[]});
    }
    groups.get(key).recipes.push({recipe,index});
  });
  return [...groups.values()];
}
function craftingGroupMatches(group,query,ingredient){
  if(ingredient&&!group.recipes.some(({recipe})=>(recipe.ingredients||[]).some(part=>part.item===ingredient)))return false;
  if(!query)return true;
  const values=[group.key,group.name,group.category];
  for(const {recipe} of group.recipes)values.push(recipe.recipe_id,recipe.title,recipe.description,recipe.station,recipe.unlock,
    ...(recipe.ingredients||[]).map(part=>part.item));
  return values.some(value=>String(value||"").toUpperCase().includes(query));
}
function sharedTableSort(tab,key,rerender){
  const active=state.sorts[tab]?.key===key,current=state.sorts[tab];state.sorts[tab]={key,dir:active?-current.dir:1};rerender();
}
function craftingOutputList(groups,mode,selected,select,rerender){
  const tab=`crafting-${mode}`;
  return columnList({rows:groups,key:group=>group.key,selected,select,
    sortState:state.sorts[tab],
    sort:key=>sharedTableSort(tab,key,rerender),columns:[
      {key:"name",label:"Item",grow:2,render:group=>itemLink(group.key,true,originDisplayName(group.name,group.item))},
      {key:"key",label:"ID",grow:1},
      {key:"category",label:"Category",grow:1,render:group=>craftingCategoryLabel(group.category)},
      {key:"recipes",label:"Recipes",numeric:true,render:group=>group.recipes.length}]});
}
function readonlyCraftingField(label,content){
  return LexeditorUI.detailField({label,control:LexeditorUI.readonlyField(content||"—",{format:false})});
}
function readonlyCraftingRecipe({recipe},position){
  const ingredients=columnList({rows:(recipe.ingredients||[]).map((part,index)=>({...part,index})),key:part=>part.index,
    columns:[{key:"item",label:"Ingredient",grow:1,render:part=>itemLink(part.item)},
      {key:"quantity",label:"Quantity",numeric:true}]});
  return LexeditorUI.detailSection({title:`Recipe ${position+1}`,body:[
    readonlyCraftingField("ID",recipe.recipe_id),
    readonlyCraftingField("Context",CUSTOM_CRAFT_STATIONS[recipe.station]||recipe.station),
    readonlyCraftingField("Makes",String(recipe.output_quantity)),
    readonlyCraftingField("Learned",recipe.unlock||"Always known"),
    readonlyCraftingField("Description",recipe.description||"No description"),ingredients]});
}
function customCraftingRecipe(entry,group,position,validation){
  const {recipe,index}=entry,update=(field,value)=>{recipe[field]=value;customCraftingTouch();};
  const ingredients=columnList({rows:(recipe.ingredients||[]).map((part,partIndex)=>({part,partIndex})),key:row=>row.partIndex,editable:true,
    columns:[{key:"item",label:"Ingredient",grow:1,render:({part})=>linkedCatalogKeyEditor(part.item,value=>{part.item=value;customCraftingTouch();renderCrafting()})},
      {key:"quantity",label:"Quantity",width:"100px",render:({part})=>el("input",{type:"number",min:1,step:1,value:part.quantity??1,onchange:ev=>{part.quantity=Math.max(1,Math.round(+ev.target.value||1));customCraftingTouch()}})},
      {key:"remove",label:"",width:"45px",render:({partIndex})=>closeButton({title:"Remove ingredient",onclick:()=>{recipe.ingredients.splice(partIndex,1);customCraftingTouch();renderCrafting()}})}]});
  const name=el("input",{value:recipe.title||"",onchange:ev=>{update("title",ev.target.value.trim());renderCrafting()}});
  const quantity=el("input",{type:"number",min:1,step:1,value:recipe.output_quantity??1,onchange:ev=>update("output_quantity",Math.max(1,Math.round(+ev.target.value||1)))});
  const unlock=validatedKeyEditor("Recipe unlock",recipe.unlock||"ALWAYS KNOWN",recipeUnlockKeys(),value=>{update("unlock",value==="ALWAYS KNOWN"?"":value);renderCrafting()});
  const description=LexeditorUI.textArea({onchange:ev=>update("description",ev.target.value)});description.value=recipe.description||"";
  return LexeditorUI.detailSection({title:`Recipe ${position+1}`,body:[LexeditorUI.actionRow(LexeditorUI.recordId(recipe.recipe_id),
    el("button",{title:"Move recipe up",disabled:position===0,onclick:()=>moveCustomCraftingRecipe(group.key,index,-1)},"↑"),
    el("button",{title:"Move recipe down",disabled:position===group.recipes.length-1,onclick:()=>moveCustomCraftingRecipe(group.key,index,1)},"↓")),
    LexeditorUI.tileGrid([{label:"Name",control:name},{label:"Makes",control:quantity},{label:"Context",control:customCraftingStationSelect(recipe,value=>{update("station",value);renderCrafting()})},{label:"Learned",control:unlock},{label:"Description",control:description}].map(LexeditorUI.detailField)),
    ingredients,LexeditorUI.actionRow(newButton({title:"Add ingredient",onclick:()=>pickIdentifier("Ingredient",catalogItemOptions(),"",value=>{recipe.ingredients.push({item:value,quantity:1});customCraftingTouch();renderCrafting()})}),
      el("button",{onclick:()=>pickIdentifier("Recipe output",catalogItemOptions(),recipe.output_item,value=>{const item=catalogItem(value);recipe.output_item=value;recipe.category=item?.category||"";state.filters.craftSelCustom=value;customCraftingTouch();renderCrafting()})},"Move to another item"),
      el("button",{onclick:()=>{state.customCraftingDraft.splice(index,1);customCraftingTouch();renderCrafting()}},"Remove recipe")),
    ...(validation.byRow[index]||[]).map(message=>LexeditorUI.notice({message,tone:"danger"}))]});
}

function craftingDetail(group,mode){
  if(!group)return LexeditorUI.detailPanel({title:"Crafting",body:LexeditorUI.detailNote("No recipe output is selected.")});
  const validation=mode==="custom"?customCraftingValidation():null;
  const recipes=group.recipes.map((entry,position)=>mode==="custom"
    ?customCraftingRecipe(entry,group,position,validation):readonlyCraftingRecipe(entry,position));
  return LexeditorUI.detailPanel({title:itemLink(group.key,true,originDisplayName(group.name,group.item)),
    identity:group.key,meta:craftingCategoryLabel(group.category),body:recipes});
}
function renderCrafting() {
  const f=state.filters;if(!f.craftMode||(f.craftMode==="custom"&&state.ds!=="mine"))f.craftMode="vanilla";
  const requestedOutput=f.craftOutput;
  if(f.craftOutput){
    const inVanilla=(state.customCrafting.vanilla||[]).some(recipe=>recipe.output_item===f.craftOutput);
    const inCustom=(state.customCraftingDraft||[]).some(recipe=>recipe.output_item===f.craftOutput);
    if(!inVanilla&&inCustom&&state.ds==="mine")f.craftMode="custom";else if(inVanilla)f.craftMode="vanilla";
    f[f.craftMode==="custom"?"craftSelCustom":"craftSelVanilla"]=f.craftOutput;f.craftOutput="";
  }
  const mode=f.craftMode,tb=$("#toolbar");tb.innerHTML="";
  const tabs=LexeditorUI.subtabBar({active:mode,label:"Recipe source",tabs:[{id:"vanilla",label:"Vanilla"},{id:"custom",label:"Custom",disabled:state.ds!=="mine",help:"Custom recipes belong to My Mod."}],change:value=>{f.craftMode=value;f.craftQ="";f.craftIngredient="";f.craftPage=0;renderCrafting()}});
  const source=mode==="custom"?state.customCraftingDraft:state.customCrafting.vanilla||[];
  const q=(f.craftQ||"").trim().toUpperCase();
  let groups=craftingOutputGroups(source).filter(group=>craftingGroupMatches(group,q,f.craftIngredient));
  const sortTab=`crafting-${mode}`;
  groups=sortedRows(sortTab,groups,{name:group=>group.name||group.key,category:group=>group.category,recipes:group=>group.recipes.length});
  const selectedField=mode==="custom"?"craftSelCustom":"craftSelVanilla";
  if(!groups.some(group=>group.key===f[selectedField]))f[selectedField]=groups[0]?.key||"";
  if(requestedOutput){
    const requestedIndex=groups.findIndex(group=>group.key===requestedOutput);
    if(requestedIndex>=0)f.craftPage=Math.floor(requestedIndex/Math.max(1,Number(f.craftPageSize)||20));
  }
  tb.append(tabs);
  const bottomFilters=[];
  if(f.craftIngredient)bottomFilters.push(el("button",{title:`Showing recipes that use ${f.craftIngredient}`,onclick:()=>{f.craftIngredient="";f.craftPage=0;renderCrafting();}},`Ingredient: ${f.craftIngredient} ×`));
  if(mode==="custom")bottomFilters.push(newButton({title:"Create recipe",onclick:addCustomCraftingRecipe,disabled:!state.customCrafting.available}),savebar(saveCustomCrafting));
  const m=$("#main");m.innerHTML="";
  if(mode==="custom"&&!state.customCrafting.available){m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},`Custom crafting runtime files are unavailable for this profile. Expected ${state.customCrafting.customFile||"custom_crafting_recipes.tsv"}.`));return;}
  m.append(LexeditorUI.pagedListDetail({
    modOnly:modOnlySpec(touchedRecords([state.craftEdits]),()=>{f.craftPage=0;},renderCrafting),
    rows:groups,key:group=>group.key,slots:false,page:f.craftPage,pageSize:f.craftPageSize,selected:f[selectedField],noun:"items",
    splitKey:`rdr2-crafting-${mode}`,defaultSplit:44,
    search:{key:`rdr2-crafting-${mode}`,value:f.craftQ||"",placeholder:"Search recipe outputs…",change:value=>{f.craftQ=value;f.craftIngredient="";f.craftPage=0;renderCrafting();}},filters:bottomFilters,
    className:"lootsplit",
    master:({rows,selected,select})=>craftingOutputList(rows,mode,selected,select,renderCrafting),
    detail:group=>craftingDetail(group,mode),
    sync:next=>{f.craftPage=next.page;f.craftPageSize=next.pageSize;f[selectedField]=next.selected||"";},
    change:next=>{f.craftPage=next.page;f.craftPageSize=next.pageSize;f[selectedField]=next.selected||"";renderCrafting();}
  }));
}

function priceQtyInput(it, section, cost, part) {
  const editKey = [it.key, section, cost.key, part.item].join("|");
  const cur = isRO() ? part.qty : (state.priceEdits[editKey] ?? part.qty);
  return el("input", { type: "number", min: "0", step: "1", value: cur,
    class: editKey in state.priceEdits ? "edited" : "",
    onchange: ev => {
      const v = Math.round(parseFloat(ev.target.value || "0"));
      if (v === part.qty) delete state.priceEdits[editKey];
      else state.priceEdits[editKey] = v;
      ev.target.classList.toggle("edited", editKey in state.priceEdits);
      renderToolbarOnly();
    } });
}

function setItemEffects(it, list) {
  if (JSON.stringify(list) === JSON.stringify(it.effects)) delete state.itemEffectEdits[it.key];
  else state.itemEffectEdits[it.key] = list;
}

const FALLBACK_ALCOHOL_STRENGTH=[
  {key:"CI_TAG_DRINKING_BEER",type:"0xC76BC07D",label:"Beer (light)",rank:1},
  {key:"0x435E057A",type:"0xC76BC07D",label:"Whiskey",rank:2},
  {key:"0x3B952FEE",type:"0xC76BC07D",label:"Rum",rank:2},
  {key:"0xEFAD85F3",type:"0xC76BC07D",label:"Spirits (gin / brandy / moonshine)",rank:3},
  {key:"0x88B79CD0",type:"0xC76BC07D",label:"Saloon whiskey",rank:2},
];
const TAG_TYPE_LABELS_UI={
  "0x42D03BDE":"Item flag","0x48FA3731":"Satchel folder","0xC76BC07D":"Document / inspect / drink",
  "0xE599E90D":"Clothing component","0x33634061":"Clothing meta","0xE4521CDF":"Clothing style",
  "0x30ECAC7E":"Weapon engraving design","0x6534EAA0":"Clothing material","0x7E334732":"Clothing palette",
  "0x9E74B133":"Clothing tint","0x912DE0BA":"Clothing decal","0x83752C8C":"Clothing asset","0x7EE8BE10":"Clothing layer",
};
function normalizeTagToken(value){
  const text=String(value||"").trim();
  if(!text)return "";
  if(/^0x[0-9a-fA-F]{1,8}$/.test(text))return "0x"+text.slice(2).toUpperCase().padStart(8,"0");
  return text;
}
function normalizeTag(tag){
  if(!tag)return null;
  if(typeof tag==="string")return {key:normalizeTagToken(tag),type:""};
  const key=normalizeTagToken(tag.key),type=normalizeTagToken(tag.type);
  return key?{key,type}:null;
}
function tagId(tag){const t=normalizeTag(tag);return t?`${t.key}|${t.type}`:"";}
function tagsEqual(a,b){
  const aa=(a||[]).map(normalizeTag).filter(Boolean).map(tagId).sort();
  const bb=(b||[]).map(normalizeTag).filter(Boolean).map(tagId).sort();
  return JSON.stringify(aa)===JSON.stringify(bb);
}
function itemTagsOf(it){
  if(!it)return [];
  const raw=isRO()?it.tags:(state.itemTagEdits[it.key]??it.tags??[]);
  return (raw||[]).map(normalizeTag).filter(Boolean);
}
function setItemTags(it,list){
  const clean=(list||[]).map(normalizeTag).filter(Boolean);
  if(tagsEqual(clean,it.tags||[]))delete state.itemTagEdits[it.key];
  else state.itemTagEdits[it.key]=clean;
}
function itemHasTag(it,key){
  const want=normalizeTagToken(key);
  return itemTagsOf(it).some(t=>t.key===want);
}
function prettyTagKey(key){
  key=normalizeTagToken(key);
  if(key.startsWith("CI_TAG_"))return key.replace(/^CI_TAG_/,"").replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase());
  return key;
}
function tagPurposeGroup(key){
  key=normalizeTagToken(key);
  if(FALLBACK_ALCOHOL_STRENGTH.some(r=>r.key===key)||key==="CI_TAG_ITEM_ALCOHOL")return "Alcohol";
  if(key.startsWith("CI_TAG_ITEM_"))return "Item class";
  if(key.startsWith("CI_TAG_CATEGORY_"))return "Category";
  if(key.startsWith("CI_TAG_SHOP_"))return "Shop";
  if(key.startsWith("CI_TAG_FOLDER_"))return "Satchel folder";
  if(key.startsWith("CI_TAG_PAPER_")||key.startsWith("CI_TAG_INSPECT_")||key.startsWith("CI_TAG_POCKET_"))return "Document & inspect";
  if(key.startsWith("CI_TAG_WEAPON_")||key.startsWith("CI_TAG_LONG_"))return "Weapon";
  if(key.startsWith("CI_TAG_DRINKING_")||key.startsWith("CI_TAG_APPLY_")||key.startsWith("CI_TAG_REMOVE_"))return "Interaction";
  if(key.startsWith("CI_TAG_"))return "Other named";
  return "Unresolved";
}
function tagTypeLabel(typ){
  // Must not call tagCatalog() — rebuildTagMaps uses this while building maps.
  typ=normalizeTagToken(typ);
  return TAG_TYPE_LABELS_UI[typ]||typ||"(no type)";
}
/** Build/refresh tag catalog from server payload + every loaded item (mine + refs). */
function rebuildTagMaps(catalog){
  if(!catalog)return {tags:[],types:[],alcoholStrength:FALLBACK_ALCOHOL_STRENGTH};
  // Re-entrancy guard: tagTypeLabel/tagCatalog must never re-enter rebuild.
  if(catalog._tagMapsBuilding)return catalog.tagCatalog||{tags:[],types:[],alcoholStrength:FALLBACK_ALCOHOL_STRENGTH};
  catalog._tagMapsBuilding=true;
  try{
    const prevCatalog=catalog.tagCatalog;
    const alcohol=prevCatalog?.alcoholStrength?.length?prevCatalog.alcoholStrength:FALLBACK_ALCOHOL_STRENGTH;
    const seen=new Map();
    const ingest=(tag,count=1)=>{
      const t=normalizeTag(tag);if(!t)return;
      const id=t.key;
      const prev=seen.get(id);
      const resolved=!/^0x/i.test(t.key)||alcohol.some(a=>normalizeTagToken(a.key)===t.key);
      const typ=t.type||prev?.type||"";
      const row={
        key:t.key,type:typ,
        label:alcohol.find(a=>normalizeTagToken(a.key)===t.key)?.label||prettyTagKey(t.key),
        typeLabel:tagTypeLabel(typ),
        group:tagPurposeGroup(t.key),
        resolved,
        pickable:resolved||t.key.startsWith("CI_TAG_"),
        count:(prev?.count||0)+count,
      };
      if(prev&&prev.type&&!t.type)row.type=prev.type;
      if(prev&&t.type&&!prev.type)row.type=t.type;
      seen.set(id,row);
    };
    // Seed from prior server/client catalog without re-walking if already dense.
    for(const row of prevCatalog?.tags||[])ingest(row,row.count||1);
    for(const it of catalog.items||[])for(const tag of it.tags||[])ingest(tag,1);
    for(const ds of ["vanilla","kiddos"]){
      const items=refStore(ds).catalog?.items||[];
      for(const it of items)for(const tag of it.tags||[])ingest(tag,1);
    }
    for(const a of alcohol)ingest(a,0);
    const tags=[...seen.values()].sort((a,b)=>(a.group||"").localeCompare(b.group||"")||(a.label||"").localeCompare(b.label||"")||a.key.localeCompare(b.key));
    catalog.tagCatalog={
      tags,
      types:Object.entries(TAG_TYPE_LABELS_UI).map(([type,label])=>({type,label})),
      alcoholStrength:alcohol,
    };
    return catalog.tagCatalog;
  }finally{
    delete catalog._tagMapsBuilding;
  }
}
function tagCatalog(){
  const cat=state.catalog;
  if(!cat)return {tags:[],types:[],alcoholStrength:FALLBACK_ALCOHOL_STRENGTH};
  if(cat._tagMapsBuilding)return cat.tagCatalog||{tags:[],types:[],alcoholStrength:FALLBACK_ALCOHOL_STRENGTH};
  if(!cat.tagCatalog?.tags?.length)rebuildTagMaps(cat);
  return cat.tagCatalog||{tags:[],types:[],alcoholStrength:FALLBACK_ALCOHOL_STRENGTH};
}
function tagMeta(tag){
  const t=normalizeTag(tag);
  if(!t)return null;
  const rows=tagCatalog().tags||[];
  return rows.find(r=>r.key===t.key&&(!t.type||!r.type||r.type===t.type))
    || rows.find(r=>r.key===t.key)
    || {key:t.key,type:t.type,label:prettyTagKey(t.key),typeLabel:tagTypeLabel(t.type),
        group:tagPurposeGroup(t.key),resolved:!/^0x/i.test(t.key),pickable:t.key.startsWith("CI_TAG_")};
}
function tagDisplayLabel(tag){
  const meta=tagMeta(tag);
  return meta?.label||prettyTagKey(tag?.key||tag);
}
function tagDisplayTitle(tag){
  const t=normalizeTag(tag),meta=tagMeta(t);
  if(!t)return "";
  return `${meta?.label||t.key}\nkey: ${t.key}\ntype: ${t.type||meta?.type||"(none)"} (${tagTypeLabel(t.type||meta?.type)})\ngroup: ${meta?.group||tagPurposeGroup(t.key)}`;
}
function isResolvedTag(tag){
  const t=normalizeTag(tag);
  if(!t)return false;
  if(alcoholStrengthOptions().some(r=>normalizeTagToken(r.key)===t.key))return true;
  return !/^0x/i.test(t.key);
}
function alcoholStrengthOptions(){return tagCatalog().alcoholStrength?.length?tagCatalog().alcoholStrength:FALLBACK_ALCOHOL_STRENGTH;}
function alcoholStrengthOf(tags){
  const keys=new Set((tags||[]).map(t=>normalizeTag(t)?.key).filter(Boolean));
  return alcoholStrengthOptions().find(opt=>keys.has(normalizeTagToken(opt.key)))||null;
}
function applyAlcoholDrinkClass(it,optionKey){
  const strengthKeys=new Set(alcoholStrengthOptions().map(o=>normalizeTagToken(o.key)));
  let next=itemTagsOf(it).filter(t=>!strengthKeys.has(t.key));
  if(optionKey){
    const opt=alcoholStrengthOptions().find(o=>normalizeTagToken(o.key)===normalizeTagToken(optionKey));
    if(opt)next=[...next,normalizeTag(opt)];
  }
  setItemTags(it,next);
}
function addTagToItem(it,tag){
  const t=normalizeTag(tag);if(!t)return false;
  const next=itemTagsOf(it);
  if(next.some(x=>x.key===t.key))return false; // one entry per key
  // Fill type from catalog when missing
  if(!t.type){
    const meta=tagMeta(t);
    if(meta?.type)t.type=meta.type;
  }
  next.push(t);setItemTags(it,next);return true;
}
function pickCatalogTag(it,onPick){
  rebuildTagMaps(state.catalog);
  const present=new Set(itemTagsOf(it).map(t=>t.key));
  const options=(tagCatalog().tags||[]).filter(t=>t.pickable&&!present.has(t.key));
  const backdrop=pickerHost();backdrop.innerHTML="";backdrop.hidden=false;
  const panel=LexeditorUI.stack({fill:false,className:"lex-dialog",attrs:{role:"dialog","aria-modal":"true"}});
  const search=el("input",{type:"text",placeholder:"Search tags (e.g. CONSUMABLE, HORSE, FOLDER)…",value:""});
  const list=LexeditorUI.stack({fill:false});
  const draw=()=>{
    const q=search.value.trim().toUpperCase();
    list.innerHTML="";
    const groups=new Map();
    options.filter(t=>!q||`${t.label} ${t.key} ${t.group} ${t.typeLabel||""}`.toUpperCase().includes(q))
      .forEach(t=>{if(!groups.has(t.group))groups.set(t.group,[]);groups.get(t.group).push(t);});
    let shown=0;
    for(const [group,rows] of groups){
      if(shown>=500)break;
      list.append(el("div",{class:"picker-group"},group));
      for(const t of rows){
        if(shown>=500)break;
        list.append(el("button",{class:"lex-dialog-action",title:tagDisplayTitle(t),onclick:()=>{
          onPick({key:t.key,type:t.type});backdrop.hidden=true;
        }},el("span",{class:"lex-inline-label"},t.label),el("span",{class:"key"},t.key)));
        shown++;
      }
    }
    if(!shown)list.append(el("div",{class:"cat"},options.length?"No tags match that search.":"No named tags available — reload the editor so catalog tag data loads."));
  };
  search.addEventListener("input",draw);
  panel.append(
    el("div",{class:"head"},el("b",{},"Add catalog tag"),
      el("span",{class:"cat",style:"margin-left:auto"},`${options.length} named options · no free-entry hashes`)),
    search,list,el("button",{onclick:()=>backdrop.hidden=true},"Cancel"));
  backdrop.append(panel);draw();search.focus();
}
function itemTagsCell(it){
  const wrap=LexeditorUI.stack({fill:false});
  const draw=()=>{
    tagCatalog();
    const current=itemTagsOf(it),dirty=it.key in state.itemTagEdits;
    const alcoholKeys=new Set(alcoholStrengthOptions().map(option=>normalizeTagToken(option.key)));
    const showAlcohol=itemHasTag(it,"CI_TAG_ITEM_ALCOHOL")||current.some(tag=>alcoholKeys.has(tag.key));
    const visible=current.filter(tag=>!alcoholKeys.has(tag.key));
    const sources=[["V","vtag",refItem("vanilla",it.key)],["K","ktag",refItem("kiddos",it.key)]].filter(([, ,source])=>source);
    const references=sources.map(([tag,cls,source])=>[tag,cls,(source.tags||[]).map(normalizeTag).filter(entry=>entry&&!alcoholKeys.has(entry.key))]);
    const tagChip=(tag,removable)=>{
      const unresolved=!isResolvedTag(tag);
      const chip=LexeditorUI.inlineLabel(
        el("span",{class:"tag-label"},tagDisplayLabel(tag)),unresolved?LexeditorUI.badge("Unresolved",{tone:"warning"}):null);chip.title=tagDisplayTitle(tag);
      if(!isRO()&&removable){
        const remove=closeButton({title:"Remove tag"});
        remove.addEventListener("click",event=>{
          event.stopPropagation();event.preventDefault();
          setItemTags(it,itemTagsOf(it).filter(entry=>entry.key!==normalizeTag(tag).key));draw();renderToolbarOnly();
        });
        remove.addEventListener("click",event=>event.stopPropagation());chip.append(remove);
      }
      return chip;
    };
    const add=isRO()?"":newButton({title:"Add catalog tag",
      onclick:()=>pickCatalogTag(it,tag=>{if(addTagToItem(it,tag)){draw();renderToolbarOnly();}})});
    const field=multiValueReferences({
      kind:"item-tags",current:visible,references,keyOf:tag=>normalizeTag(tag).key,entryValue:tag=>normalizeTag(tag).type,
      formatValue:value=>value?`${tagTypeLabel(value)} (${value})`:"(no type)",sortKey:tag=>tagDisplayLabel(tag),
      renderCurrent:tag=>tagChip(tag,true),renderGhost:tag=>tagChip(tag,false),addControl:add,
      emptyText:showAlcohol?"":"no tags",
    });
    const unresolved=visible.filter(tag=>!isResolvedTag(tag));
    if(unresolved.length)field.querySelector(".multi-ref-current")?.append(el("span",{class:"tag-advanced",
      title:"Unresolved tag keys appear as hashes. They can be removed but not free-typed."},`${unresolved.length} unresolved`));
    wrap.replaceChildren(field);
    if(showAlcohol){
      const currentStrength=alcoholStrengthOf(current);
      const select=el("select",{
        title:"Drink class (exclusive). This is a coarse animation and brand tag, not the numerical intoxication amount. Set the actual drunkenness added per use in the Drunkenness field beside it.",
        class:dirty?"edited":"",onchange:event=>{applyAlcoholDrinkClass(it,event.target.value);draw();renderToolbarOnly();}
      },el("option",{value:""},isRO()&&!currentStrength?"—":"Drink class: none"));
      for(const option of alcoholStrengthOptions()){
        const row=el("option",{value:option.key},option.label);
        if(currentStrength&&normalizeTagToken(currentStrength.key)===normalizeTagToken(option.key))row.selected=true;
        select.append(row);
      }
      if(isRO())select.disabled=true;
      const drinkEntry={key:"drink-class",value:currentStrength?.key||""};
      const drinkReferences=sources.map(([tag,cls,source])=>{
        const tags=(source.tags||[]).map(normalizeTag).filter(Boolean),strength=alcoholStrengthOf(tags);
        const applies=tags.some(entry=>entry.key==="CI_TAG_ITEM_ALCOHOL")||!!strength;
        return [tag,cls,applies?[{key:"drink-class",value:strength?.key||""}]:[]];
      });
      const drinkRow=LexeditorUI.stack({fill:false},LexeditorUI.detailField({label:"Drink class",control:select}));
      const drinkStack=multiValueReferenceStack(drinkReferences,"drink-class",drinkEntry,{keyOf:entry=>entry.key,entryValue:entry=>entry.value,
        formatValue:value=>alcoholStrengthOptions().find(option=>normalizeTagToken(option.key)===normalizeTagToken(value))?.label||"none"},false);
      if(drinkStack)drinkRow.append(drinkStack);wrap.append(drinkRow);
      if(state.ds==="mine"){
        // Build the displayed value from the immutable imported baseline plus the
        // sparse override map. Do not trust a flattened `entries` response here.
        const vanilla=state.alcohol.vanilla?.[it.key],savedOverride=state.alcohol.overrides?.[it.key];
        const runtime=state.alcoholEdits[it.key]??savedOverride??vanilla;
        const available=state.alcohol.available&&vanilla!==undefined;
        const input=el("input",{type:"number",min:"0",max:"1",step:"any",value:runtime===undefined?"":fmtCompactNumber(runtime),placeholder:"Unavailable",
          class:it.key in state.alcoholEdits?"edited":"",disabled:!available,
          title:available?"Actual drunkenness added when consumed. 1.0 causes immediate blackout. This runtime value is separate from Rockstar's coarse drink-class tag.":(state.alcohol.reason||"No verified per-drink strength is available for this item."),
          // Recorded as it is typed, not only on blur. Chromium withholds the
          // change event here - the number box is rebuilt around the reader
          // between keystrokes - so an edit made by typing was silently lost
          // and Save stayed grey. Blur still does the correcting.
          oninput:event=>{
            const value=event.target.valueAsNumber;
            if(!Number.isFinite(value)||value<0||value>1)return;
            state.alcoholEdits[it.key]=value;renderToolbarOnly();},
          onchange:event=>{
            const value=event.target.valueAsNumber;
            if(!Number.isFinite(value)||value<0||value>1){
              delete state.alcoholEdits[it.key];
              event.target.value=runtime===undefined?"":fmtCompactNumber(runtime);
              toast("Drunkenness must be a number from 0 to 1.",true);
              renderToolbarOnly();return;
            }
            state.alcoholEdits[it.key]=value;renderToolbarOnly();}});
        wrap.append(LexeditorUI.inlineLabel("Drunkenness",input,
          ...(vanilla===undefined?[]:[el("span",{class:"ref"},`V ${fmtCompactNumber(vanilla)}`)]),
          fieldHelp("Actual per-drink drunkenness: 0 adds no drunkenness; 1.0 triggers the game's normal blackout path. Enter the displayed vanilla value to remove an override. Drink class remains a separate coarse tag.")));
      }
    }
  };
  draw();return wrap;
}

function showEffectUsage(effect,keys){
  const backdrop=pickerHost();backdrop.innerHTML="";backdrop.hidden=false;
  const panel=LexeditorUI.stack({fill:false,className:"lex-dialog",attrs:{role:"dialog","aria-modal":"true"}});
  panel.append(el("div",{class:"head"},el("b",{},`Items using ${humanName("effects",effect.key)||effect.label||effect.key}`),el("span",{class:"cat",style:"margin-left:auto"},`${keys.length} item${keys.length===1?"":"s"}`)));
  const list=LexeditorUI.stack({fill:false});
  keys.map(key=>state.catalog.items.find(it=>it.key===key)).filter(Boolean)
    .sort((a,b)=>(localizedValue(a.nameKey)||a.key).localeCompare(localizedValue(b.nameKey)||b.key))
    .forEach(it=>list.append(rdrHoverable({content:el("span",{class:"lex-dialog-action"},
      el("span",{class:"lex-inline-label"},localizedValue(it.nameKey)||"No localized name"),el("span",{class:"key"},it.key)),
      targetType:"rdr2-item",targetId:it.key,targetLabel:`${localizedValue(it.nameKey)||it.key} in Items`,
      activate:()=>{backdrop.hidden=true;goToItem(it.key);}})));
  panel.append(list,el("button",{onclick:()=>backdrop.hidden=true},"Close"));backdrop.append(panel);
}

function effectSummary(e) {
  let s = e.id;
  if (+e.percent) s += ` ${e.percent}%`;
  if (+e.time) s += ` for ${formatEffectDuration(e.time, e.timeunits)}`;
  return s;
}

function formatEffectDuration(time, units) {
  const n = Number(time);
  const u = String(units);
  const labels = {
    "0": ["second", "seconds"],
    "1": ["minute", "minutes"],
    "2": ["in-game hour", "in-game hours"],
    "3": ["in-game day", "in-game days"],
  };
  const pair = labels[u];
  if (!pair) return `${time} (units ${units})`;
  return `${time} ${Math.abs(n) === 1 ? pair[0] : pair[1]}`;
}

function effectBehaviorHelp(e){
  const id=(e.id||"").toUpperCase();
  return ({
    "0X45EA9E3E":"Weapon Accuracy Diff for shop/radial comparison. Improved sights change this advertised bar; real spread/FOV also live in weaponcomponents.meta.",
    "0X77323E93":"Weapon Power Diff for shop/radial comparison (ammo/components). Actual damage also lives in weapons.ymt DamageInfos.",
    "0X9D36F302":"Weapon Range Diff for shop/radial comparison (scopes, HV ammo). Falloff curves live in DamageFallOffInfo.",
    "0XF01DB3AC":"Base weapon Damage bar. Present on guns, bow, lasso, and melee; value tracks the radial Damage stat.",
    "0X624213C0":"Base weapon Range bar. Snipers high, sawed-off/melee low; family-tier values shared across related weapons.",
    "0X660FC4D3":"Range family tier. Matches 0x624213C0 on firearms that have both; absent on bow/melee.",
    "0X3AA14E2E":"Base weapon Accuracy bar (inferred). Always equals 0x51364153 on vanilla weapons that carry both.",
    "0X51364153":"Paired accuracy channel — vanilla values always match 0x3AA14E2E when both exist. Possibly hip-fire vs ADS or a second consumer of the same base.",
    "0X91548886":"Base weapon Fire Rate bar (inferred). Low on bolt/sniper, high on M1899/Cattleman.",
    "0X3BC9A031":"Base weapon Reload bar (inferred). Low on snipers, higher on pistols.",
    "0X7988865E":"Secondary weapon bar A. Not damage/range; mid-high on most firearms. Candidate: handling, sway, or stability.",
    "0X7E3305FD":"Secondary weapon bar B. Mid values on firearms. Candidate: condition capacity or degradation resistance.",
    "0X5754B3EE":"Flat constant 5 on nearly every firearm. Unknown unit — not a radial bar.",
    "0XBE3AC851":"Flat constant 10 on nearly every firearm. Unknown unit.",
    "0XD04A6763":"Flat constant 10 on firearms + bow. Unknown unit.",
    "CS_ARCHIEDOWNTWEEN_MS1_BOOT_000_C0_000_NM":"Still a real behavior ID used as a weapon bar, but the symbol is a bad OpenIV/CodeX resolution (cutscene NM name). Treat the string as an opaque id, not a boot animation.",
    "0X014BBDD2":"Horse breed attribute A. High on Arabians, low on draft breeds — mobility cluster (speed-like).",
    "0XEC3968A2":"Horse breed attribute B. Mobility cluster (acceleration-like).",
    "0X09F9A8CD":"Horse breed attribute C. Mobility cluster (handling-like).",
    "0X38AC6CAF":"Horse breed attribute D. Body cluster. Health-like but does not perfectly match every wiki health ranking.",
    "0X00783EF8":"Horse breed attribute E. Body cluster (stamina-like).",
    "0X73269FE7":"Horse breed attribute F. Temperament/bonding-like; not a mobility bar.",
    "0X45900CD7":"Saddle equipment stat A. Scales stock < improved < special. One of speed/accel/stamina saddle bonuses.",
    "0XF2935D5F":"Saddle equipment stat B. Parallel to A/C on the same saddles.",
    "0X5FB62877":"Saddle equipment stat C. Parallel to A/B on the same saddles.",
    "0X7C5A4804":"Stirrup equipment bonus A. Paired with B/C on stirrup items.",
    "0X9F69F9E3":"Stirrup equipment bonus B.",
    "0XCD995CA6":"Stirrup equipment bonus C (often the largest of the three).",
  })[id]||"";
}
function effectBehaviorName(e){
  // Prefer labels.json; keep a tiny built-in fallback for the three long-documented weapon diffs.
  return humanName("behaviors",e.id)||({
    "0X45EA9E3E":"Weapon accuracy display modifier",
    "0X77323E93":"Weapon power display modifier",
    "0X9D36F302":"Weapon range display modifier",
  })[(e.id||"").toUpperCase()]||"";
}

function showCreateEffect(){
  if(isRO())return;
  const backdrop=pickerHost();backdrop.innerHTML="";backdrop.hidden=false;
  const behaviors=[...new Set(state.catalog.effects.map(e=>e.id))].sort((a,b)=>(humanName("behaviors",a)||a).localeCompare(humanName("behaviors",b)||b));
  const durations=[...new Set(state.catalog.effects.map(e=>e.durationcategory))].sort();
  const key=el("input",{placeholder:"LEX_EFFECT_SALTED_BEEF"}),label=el("input",{placeholder:"Salty snack"});
  const behavior=el("select",{},...behaviors.map(id=>el("option",{value:id},`${humanName("behaviors",id)||effectBehaviorName({id})||id}${humanName("behaviors",id)||effectBehaviorName({id})?` — ${id}`:""}`)));
  const value=el("input",{type:"number",value:"0"}),percent=el("input",{type:"number",step:"any",value:"0"});
  const time=el("input",{type:"number",value:"0"}),units=el("select",{},el("option",{value:"0"},"0 — seconds"),el("option",{value:"1"},"1 — minutes"),el("option",{value:"2"},"2 — in-game hours"),el("option",{value:"3"},"3 — in-game days"));
  const duration=el("select",{},...durations.map(id=>el("option",{value:id},id.replace("EFFECT_DURATION_CATEGORY_",""))));
  const close=()=>{backdrop.hidden=true;backdrop.innerHTML="";};
  const create=async()=>{try{
    const result=await api("/api/catalog/effects/create",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({key:key.value,label:label.value,behavior:behavior.value,value:value.value,percent:percent.value,time:time.value,timeunits:units.value,durationcategory:duration.value})});
    if(result.label){state.labels.effects=state.labels.effects||{};state.labels.effects[result.key]=result.label;}
    if(result.symbol){state.labels.effectSymbols=state.labels.effectSymbols||{};state.labels.effectSymbols[result.key]=result.symbol;}
    const store=refStore("mine");store.catalog=await api("/api/catalog",undefined,"mine");store.effectByKey={};for(const effect of store.catalog.effects)store.effectByKey[effect.key]=effect;
    state.catalog=store.catalog;state.effectByKey=store.effectByKey;state.filters.effQ=result.key;close();await switchDataset("mine");toast(`Created ${result.label||result.key}`);
  }catch(ex){toast("Create effect failed: "+ex.message,true);}};
  const panel=LexeditorUI.stack({fill:false,className:"lex-dialog",attrs:{role:"dialog","aria-modal":"true"}},el("div",{class:"head"},el("b",{},"Create effect record"),el("span",{class:"cat",style:"margin-left:auto"},"catalog_sp.ymt")),
    LexeditorUI.stack({fill:false,className:"lex-notice"},"Creates a new data record using an existing engine behavior. It does not create a new engine behavior."),
    LexeditorUI.tileGrid([{label:"Symbolic effect ID",control:key},{label:"Editor label",control:label},{label:"Engine behavior",control:behavior},{label:"Value",control:value},{label:"Percent override",control:percent},{label:"Time",control:time},{label:"Time units",control:units},{label:"Duration category",control:duration}].map(LexeditorUI.detailField)),
    LexeditorUI.actionRow(el("button",{onclick:close},"Cancel"),el("button",{class:"save",onclick:create},"Create effect")));
  backdrop.append(panel);key.focus();
}

async function saveCatalog() {
  if (isRO()) return;
  const prices = Object.entries(state.priceEdits).map(([k, qty]) => {
    const [item, section, costKey, partItem] = k.split("|");
    return { item, section, costKey, partItem, qty };
  });
  const buyability=Object.entries(state.buyabilityEdits).map(([item,value])=>({item,...value}));
  const sellability=Object.entries(state.sellabilityEdits).map(([item,value])=>({item,...value}));
  const yields = Object.entries(state.yieldEdits).map(([k, qty]) => {
    const [item, section, costKey] = k.split("|"); return {item,section,costKey,qty};
  });
  const carry = Object.entries(state.carryEdits).map(([k, qty]) => {
    const [item, slot] = k.split("|");
    return { item, slot, qty };
  });
  const craft = Object.entries(state.craftEdits).map(([item, entries]) => ({
    item, entries: portableCraftEntries(entries).map(e => ({ ...e, parts: e.parts.filter(p => p.item) })) }));
  const effects = Object.entries(state.effectEdits).map(([k, value]) => {
    const [key, field] = k.split("|");
    return { key, field, value };
  });
  const itemEffects = Object.entries(state.itemEffectEdits).map(([item, effs]) => ({ item, effects: effs }));
  const itemTags = Object.entries(state.itemTagEdits).map(([item, tags]) => ({ item, tags }));
  const quickSelect=Object.entries(state.quickSelectEdits).map(([item,value])=>({item,slots:value.slots}));
  const descriptions=Object.entries(state.descriptionKeyEdits).map(([item,key])=>({item,key}));
  try {
    if(Object.keys(state.alcoholEdits).length){
      // Save only explicit edits. The backend merges them into the latest file;
      // a stale browser must not reset an unrelated drink (including Moonshine).
      const entries={...state.alcoholEdits};
      await api("/api/alcohol-strengths/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({entries})});
      state.alcohol=await api("/api/alcohol-strengths",undefined,"mine");
      state.alcoholEdits={};
    }
    const localizedSaved=await saveLocalization();
    const r = await api("/api/catalog/save", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prices, buyability, sellability, yields, bundles:Object.entries(state.bundleEdits).map(([key,qty])=>({key,qty})), effects, itemEffects, itemTags, quickSelect: quickSelect, descriptions, carry, craft }) });
    // fold edits into local model so UI stays consistent
    for (const e of prices) {
      const it = state.catalog.items.find(i => i.key === e.item);
      const list = e.section === "buy" ? it.buy : it.sell;
      for (const c of list) if (c.key === e.costKey)
        for (const p of c.parts) if (p.item === e.partItem) p.qty = e.qty;
    }
    for(const e of yields){const it=state.catalog.items.find(i=>i.key===e.item);const cost=it&&it[e.section].find(c=>c.key===e.costKey);if(cost)cost.yield=e.qty;}
    for(const e of buyability){const it=state.catalog.items.find(i=>i.key===e.item);if(it){const other=it.buy.filter(c=>c.costtype!=="COST_TYPE_PRICE"||!c.parts.some(p=>p.item==="CURRENCY_CASH"));it.buy=e.buyable?other.concat([{key:"COST_SHOP_DEFAULT",costtype:"COST_TYPE_PRICE",yield:1,parts:[{item:"CURRENCY_CASH",qty:e.cents??100}],unlocks:[]}]):other;}}
    for(const e of sellability){const it=state.catalog.items.find(i=>i.key===e.item);if(it)it.sell=e.sellable?[{key:"SELL_SHOP_DEFAULT",costtype:"COST_TYPE_PRICE",yield:1,parts:[{item:"CURRENCY_CASH",qty:e.cents??100}],unlocks:[]}]:[];}
    for (const e of effects) {
      const eff = state.effectByKey[e.key];
      if (eff) eff[e.field] = String(e.value);
    }
    for (const e of itemEffects) {
      const it = state.catalog.items.find(i => i.key === e.item);
      if (it) it.effects = e.effects;
    }
    for (const e of itemTags) {
      const it = state.catalog.items.find(i => i.key === e.item);
      if (it) it.tags = e.tags;
    }
    if(quickSelect.length){
      state.quickSelect=await api("/api/quick-select");
      refStore("mine").quickSelect=state.quickSelect;
    }
    for(const e of descriptions){const it=state.catalog.items.find(i=>i.key===e.item);if(it)it.descriptionKey=e.key;}
    for (const e of carry) {
      const it = state.catalog.items.find(i => i.key === e.item);
      const s = it && (it.carry || []).find(x => x.slot === e.slot);
      if (s) s.qty = e.qty;
    }
    for (const e of craft) {
      const it = state.catalog.items.find(i => i.key === e.item);
      if (it) it.buy = it.buy.filter(c => !isCraftCost(c)).concat(
        e.entries.map(en => ({ key: en.key, costtype: "COST_TYPE_CRAFT", yield: en.yield,
          parts: en.parts, unlocks: en.unlocks || [] })));
    }
    state.priceEdits = {}; state.buyabilityEdits={}; state.sellabilityEdits={}; state.yieldEdits = {}; state.bundleEdits={}; state.effectEdits = {}; state.itemEffectEdits = {}; state.itemTagEdits = {}; state.quickSelectEdits={}; state.descriptionKeyEdits={}; state.carryEdits = {}; state.craftEdits = {}; state.shopAcceptance=null;
    toast(`Saved ${r.saved} catalog + ${localizedSaved} in-game text change(s)`);
    render();
  } catch (ex) { throw showSaveFailure(ex); }
}
