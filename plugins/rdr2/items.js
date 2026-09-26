// ----- Items & Prices -----
function isPlantItem(it){
  return it.key.startsWith("CONSUMABLE_HERB_") ||
    (it.lootSources||[]).some(s=>s.file==="loot_table_herb.meta");
}

// A "unique" is a one-of-a-kind item: trinkets, talismans, legendary animal parts,
// gang keepsakes, discovery collectibles and quest valuables. The catalog has no single
// flag for this, so it is derived from three signals. Carry caps are read from VANILLA so
// the tab stays stable while the user retunes caps in this dataset.
function vanillaCarry(it, slot){
  const src = refItem("vanilla", it.key) || it;
  const rule = (src.carry || []).find(c => c.slot === slot);
  return rule ? Number(rule.qty) : null;
}

function isUniqueItem(it){
  if (itemHasTag(it, "CI_TAG_ITEM_TRINKET")) return true;   // 20 crafted trinkets
  if (it.key.startsWith("PROVISION_TALISMAN_")) return true;          // talismans sit in CLOTHING with cap on SLOTID_ANY
  // Consumables and upgrades reach cap 1 for balance reasons, not because they are unique.
  if (it.group === "CONSUMABLE" || it.group === "UPGRADE") return false;
  return vanillaCarry(it, "SLOTID_SATCHEL") === 1;
}

const INGREDIENT_ITEM_KEYS = new Set(["LEX_BRASS","LEX_GUNPOWDER","LEX_LEAD","LEX_STEEL"]);
function isIngredientItem(it){return INGREDIENT_ITEM_KEYS.has(it.key)||it.key.startsWith("LEX_CASING_");}

const ITEM_SECTIONS = [
  {id:"all", label:"All"},
  {id:"advert", label:"Advert", match:it=>it.group==="ADVERT"},
  {id:"ammo", label:"Ammo", match:it=>it.group==="AMMO"},
  {id:"clothing", label:"Clothing", match:it=>it.group==="CLOTHING"},
  {id:"consumables", label:"Consumables", match:it=>it.group==="CONSUMABLE"},
  {id:"documents", label:"Document", match:it=>it.group==="DOCUMENT"},
  {id:"herbs", label:"Herbs", match:isPlantItem},
  {id:"horses", label:"Horses", match:it=>it.group==="HORSE"||it.group==="HORSE_EQUIPMENT"},
  {id:"ingredients", label:"Ingredients", match:isIngredientItem},
  {id:"provisions", label:"Provisions", match:it=>it.group==="PROVISION"},
  {id:"uniques", label:"Uniques", match:isUniqueItem},
  {id:"upgrades", label:"Upgrades", match:it=>it.group==="UPGRADE"},
  {id:"valuables", label:"Valuables", match:it=>it.group==="MONEY"||it.group==="CURRENCY"||it.category==="CI_CATEGORY_VALUABLE"},
  {id:"weapons", label:"Weapons", match:it=>it.group==="WEAPON"||it.group==="WEAPON_MOD"||it.group==="WEAPON_DECORATION"||it.group==="COMPONENT"},
  {id:"misc", label:"Misc"}
];

function itemSectionOf(it){
  // Precedence keeps broad catalog groups from swallowing more useful views.
  if(isPlantItem(it))return "herbs";
  if(isIngredientItem(it))return "ingredients";
  // Uniques outrank valuables/provisions/clothing, which would otherwise swallow
  // the skull statue, the trinkets and the talismans respectively.
  if(isUniqueItem(it))return "uniques";
  if(it.group==="MONEY"||it.group==="CURRENCY"||it.category==="CI_CATEGORY_VALUABLE")return "valuables";
  const section=ITEM_SECTIONS.find(s=>s.id!=="all"&&s.id!=="herbs"&&s.id!=="misc"&&s.match?.(it));
  return section?.id||"misc";
}

function itemSectionMatches(it,section){
  return !section||section==="all"||itemSectionOf(it)===section;
}


function renderItems() {
  if (!state.catalog) return noData(`This dataset has no catalog_sp.ymt yet (${dsInfo().dir}).`);
  ensureRefCatalogs(()=>{if(state.tab==="items")renderItems();});
  const f = state.filters;
  const cats = [...new Set(state.catalog.items.map(i => i.category))].sort();
  const groups = [...new Set(state.catalog.items.map(i => i.group))].sort();
  if(!ITEM_SECTIONS.some(s=>s.id===f.itemSection))f.itemSection="all";
  const tb = $("#toolbar"); tb.innerHTML = "";
  const filters=LexeditorUI.actionRow(
    el("select", { "aria-label":"Filter items by category", onchange: ev => {
      f.category = ev.target.value;
      f.itemPage=0;
      renderItems();
    } },
      el("option", { value: "" }, "All categories"),
      ...cats.map(c => { const o = el("option", { value: c }, c.replace("CI_CATEGORY_", "")); if (c === f.category) o.selected = true; return o; })),
    el("select", { "aria-label":"Filter items by group", onchange: ev => { f.group = ev.target.value; f.itemPage=0; renderItems(); } },
      el("option", { value: "" }, "All groups"),
      ...groups.map(g => { const o = el("option", { value: g }, g || "(none)"); if (g === f.group) o.selected = true; return o; })),
    el("select", { "aria-label":"Filter items by source state", title:"Filter by acquisition evidence", onchange: ev => { f.itemSource=ev.target.value;f.itemPage=0;renderItems(); } },
      ...[["all","All source states"],["confirmed","Confirmed acquisition"],["candidate","Candidate only"],["unknown","No known source"],["model","Has model"],["no-name","No localization"]].map(([value,label])=>{const o=el("option",{value},label);if(value===f.itemSource)o.selected=true;return o;})));
  const metadata=LexeditorUI.actionRow(savebar(saveCatalog));
  const addItem=isRO()?el("span"):newButton({title:"Create new item",onclick:createNewItem});
  tb.append(LexeditorUI.subtabBar({tabs:ITEM_SECTIONS,active:f.itemSection,
    change:id=>{f.itemSection=id;f.itemPage=0;renderItems();}}));

  const q = f.q.trim().toUpperCase();
  let rows = state.catalog.items.filter(it =>
    itemSectionMatches(it,f.itemSection) &&
    (!q || it.key.toUpperCase().includes(q) || localizedValue(it.nameKey).toUpperCase().includes(q) || localizedValue(it.descriptionKey||state.descriptionKeyEdits[it.key]||"").toUpperCase().includes(q)) &&
    (!f.category || it.category === f.category) &&
    (!f.group || it.group === f.group) &&
    (f.itemSource==="all" || f.itemSource==="model"&&!!it.model || f.itemSource==="no-name"&&!localizedValue(it.nameKey).trim() || it.sourceSummary?.status===f.itemSource));
  rows=sortedRows("items",rows,{name:it=>localizedValue(it.nameKey)||it.key,description:it=>localizedValue(it.descriptionKey||state.descriptionKeyEdits[it.key]||""),buy:it=>cashOf(it,"buy")??Infinity,buyqty:effectivePurchaseYieldOf,sell:it=>cashOf(it,"sell")??Infinity,carry:defaultCarryCap,recipe:it=>craftView(it).length,recipes:it=>recipesUsing(it.key).length,effects:it=>(state.itemEffectEdits[it.key]??it.effects).length,tags:it=>itemTagsOf(it).length});
  // The shared preset owns the page slice, selected-row fallback, master,
  // detail, fitted capacity, and fixed bottom pager.
  const view=LexeditorUI.pagedListDetail({
    modOnly:(()=>{const touched=touchedRecords(ITEM_EDIT_MAPS());
      return modOnlySpec(touched,()=>{f.itemPage=0;},renderItems);})(),
    rows,key:it=>it.key,slots:false,page:f.itemPage,pageSize:f.itemPageSize,selected:f.itemSel,noun:"items",
    splitKey:"rdr2-items",defaultSplit:44,
    search:{key:"rdr2-items",value:f.q,placeholder:"Search items… (e.g. TONIC, PROVISION_)",label:"Search items",change:value=>{f.q=value;f.itemPage=0;renderItems();}},
    filters:[addItem,metadata,filters],
    className:"lootsplit",
    master:({rows,selected,select})=>columnList({rows,key:it=>it.key,selected,select,
      columns:[
        {key:"name",label:"Name / Item",grow:2,render:it=>originDisplayName(localizedValue(it.nameKey).trim()||it.key,it)},
        {key:"key",label:"ID",grow:2},
        {key:"group",label:"Group",grow:1},
        {key:"category",label:"Category",grow:1,render:it=>it.category.replace("CI_CATEGORY_","")}]}),
    detail:it=>itemRow(it),
    emptyDetail:()=>LexeditorUI.stack({fill:false},LexeditorUI.stack({fill:false,className:"lex-notice"},"No items match.")),
    sync:next=>{f.itemPage=next.page;f.itemPageSize=next.pageSize;f.itemSel=next.selected||"";},
    change:next=>{f.itemPage=next.page;f.itemPageSize=next.pageSize;f.itemSel=next.selected||"";renderItems();}
  });
  const m = $("#main"); m.innerHTML = "";
  m.append(view);
}

async function createNewItem(){
  const key=(prompt("New internal item ID (for example LEX_SULFUR):","")||"").trim().toUpperCase();
  if(!key)return;
  const name=(prompt("In-game name:",key.replace(/^LEX_/,"").replaceAll("_"," "))||"").trim();
  if(!name)return;
  const description=prompt("In-game description:","")??"";
  const category=(prompt("Catalog category:","CI_CATEGORY_MATERIALS")||"CI_CATEGORY_MATERIALS").trim().toUpperCase();
  const group=(prompt("Catalog group:","PROVISION")||"PROVISION").trim().toUpperCase();
  try{
    await api("/api/catalog/create",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({key,name,description,category,group,capacity:20})});
    const store=refStore("mine"); store.catalog=await api("/api/catalog",undefined,"mine"); store.effectByKey={};
    for(const effect of store.catalog.effects)store.effectByKey[effect.key]=effect;
    state.localization=await api("/api/localization",undefined,"mine");
    state.catalog=store.catalog; state.effectByKey=store.effectByKey;
    state.filters.q=key; state.filters.category=""; state.filters.group=""; renderItems();
    toast(`Created ${key}`);
  }catch(ex){toast("Create item failed: "+ex.message,true);}
}

// "!" badge inside the first price input of a cell (right-aligned, hover text)
function addInputWarn(container,text){container.append(fieldHelp(text));}

function priceInput(it, section, cost, part) {
  const editKey = [it.key, section, cost.key, part.item].join("|");
  const cur = isRO() ? part.qty : (state.priceEdits[editKey] ?? part.qty);
  const inp = el("input", { type: "number", step: "0.01", min: "0", value: fmtMoney(cur),
    class: editKey in state.priceEdits ? "edited" : "",
    onchange: ev => {
      const cents = Math.round(parseFloat(ev.target.value || "0") * 100);
      if (cents === part.qty) delete state.priceEdits[editKey];
      else state.priceEdits[editKey] = cents;
      ev.target.classList.toggle("edited", editKey in state.priceEdits);
      renderToolbarOnly();
    } });
  return LexeditorUI.unitField(inp,"$");
}

function sellPriceCell(it,sellCash,sellRef){
  const edited=state.sellabilityEdits[it.key],sellable=edited?edited.sellable:sellCash.length>0;
  const cell=LexeditorUI.stack({fill:false,className:"price-cell"}),controls=LexeditorUI.actionRow();
  if(sellable){
    const rows=sellCash.length?sellCash:[[null,{qty:edited?.cents??100,item:"CURRENCY_CASH"}]];
    for(const [c,p] of rows) controls.append(c?priceInput(it,"sell",c,p):LexeditorUI.inlineLabel("$",el("input",{type:"number",step:"0.01",min:"0",value:fmtMoney(p.qty),onchange:e=>{state.sellabilityEdits[it.key]={sellable:true,cents:Math.round((+e.target.value||0)*100)};renderToolbarOnly();}})));
    controls.append(el("button",{class:"lex-ui-symbol icon-link",title:"Open Shops filtered to this item's resale information",onclick:()=>goToItemShops(it,"sell")},"⌕"));
    controls.append(!isRO()?closeButton({title:"Make unsellable",onclick:()=>{state.sellabilityEdits[it.key]={sellable:false};render();}}):el("span"));
  }else{
    controls.append(el("input",{class:"na-price",value:"N/A",readonly:"",title:"No cash sell price is defined."}),!isRO()?newButton({title:"Add a generic SELL_SHOP_DEFAULT payout. This does not choose which merchants accept the item.",onclick:()=>{state.sellabilityEdits[it.key]={sellable:true,cents:100};render();}}):el("span"),el("span"));
  }
  cell.append(controls);
  if(sellable)addInputWarn(controls,"Globally sellable: vanilla shop scripts use this SELL_SHOP_DEFAULT payout. PDATA contains sparse special-case entries, not the normal merchant whitelist.");
  cell.append(sellRef);return cell;
}

function buyPriceCell(it,buyCash,buyRef){
  const edited=state.buyabilityEdits[it.key],buyable=edited?edited.buyable:buyCash.length>0,cell=LexeditorUI.stack({fill:false,className:"price-cell"}),controls=LexeditorUI.actionRow();
  if(buyable){
    const rows=buyCash.length?buyCash:[[null,{qty:edited?.cents??100,item:"CURRENCY_CASH"}]];
    for(const [cost,part] of rows)controls.append(cost?priceInput(it,"buy",cost,part):LexeditorUI.inlineLabel("$",el("input",{type:"number",step:"0.01",min:"0",value:fmtMoney(part.qty),onchange:e=>{state.buyabilityEdits[it.key]={buyable:true,cents:Math.round((+e.target.value||0)*100)};renderToolbarOnly();}})));
    controls.append(el("button",{class:"lex-ui-symbol icon-link",title:"Open Shops and show which inventories sell this item",onclick:()=>goToItemShops(it,"buy")},"⌕"));
    controls.append(!isRO()?closeButton({title:"Remove cash purchase price; shop membership is unchanged",onclick:()=>{state.buyabilityEdits[it.key]={buyable:false};renderItems();}}):el("span"));
  }else{
    controls.append(el("input",{class:"na-price",value:"N/A",readonly:"",title:(it.shopListings||[]).length?"No cash cost; commonly a free/default option already present in a shop inventory":"No generic cash purchase cost is defined"}),!isRO()?newButton({title:"Add COST_SHOP_DEFAULT cash price; also list it in Shops if it is not already present",onclick:()=>{state.buyabilityEdits[it.key]={buyable:true,cents:100};renderItems();}}):el("span"),el("span"));
  }
  cell.append(controls);
  if(buyable&&!currentShopTypesForItem(it.key).length)addInputWarn(controls,"Priced, but not listed in any standard shop inventory — the price exists in the catalog, but no merchant currently stocks it.");
  cell.append(buyRef);return cell;
}

function purchaseQuantityCell(it) {
  const pending=state.buyabilityEdits[it.key];
  const cost=it.buy.find(c=>c.costtype==="COST_TYPE_PRICE"&&c.parts.some(p=>p.item==="CURRENCY_CASH"))||
    (pending?.buyable?{key:"COST_SHOP_DEFAULT",costtype:"COST_TYPE_PRICE",yield:1,parts:[{item:"CURRENCY_CASH",qty:pending.cents??100}],unlocks:[]}:null);
  if(!cost)return el("div",{},el("input",{class:"na-price",value:"N/A",readonly:"",title:"No cash purchase record defines a purchase quantity."}));
  const editKey=`${it.key}|buy|${cost.key}`,base=cost.yield||1,cur=isRO()?base:(state.yieldEdits[editKey]??base);
  const bundle=purchaseBundleOf(it);
  const attrs={type:"number",min:"1",step:"1",value:cur,class:editKey in state.yieldEdits?"edited":"",title:bundle?`Raw ${bundle.container} record quantity before the game unpacks its contents`:"Units received for this catalog purchase"};
  if(isRO())attrs.readonly="";else attrs.oninput=ev=>{const value=Math.max(1,Math.round(+ev.target.value||1));if(value===base)delete state.yieldEdits[editKey];else state.yieldEdits[editKey]=value;ev.target.classList.toggle("edited",editKey in state.yieldEdits);renderToolbarOnly();};
  const fields=LexeditorUI.stack({fill:false},el("input",attrs));
  if(bundle){
    const outAttrs={type:"number",min:"1",step:"1",value:bundle.min,class:bundle.editKey in state.bundleEdits?"edited":"",title:`Usable ${localizedValue(bundle.targetItem?.nameKey)||bundle.target} produced when this ${bundle.container} opens`};
    if(isRO())outAttrs.readonly="";else outAttrs.onchange=ev=>{const value=String(Math.max(1,Math.round(+ev.target.value||1)));const base=String(bundle.source.min||bundle.source.max||"1");if(value===base)delete state.bundleEdits[bundle.editKey];else state.bundleEdits[bundle.editKey]=value;renderToolbarOnly();};
    fields.append(LexeditorUI.actionRow(el("input",outAttrs),
      itemLink(bundle.target,true,localizedValue(bundle.targetItem?.nameKey)||bundle.target)));
  }
  return LexeditorUI.stack({fill:false},refField(fields, [
    ["V","vtag",purchaseYieldValue(refItem("vanilla",it.key))],
    ["K","ktag",purchaseYieldValue(refItem("kiddos",it.key))],
    ["1899","p1899tag",purchaseYieldValue(refItem("prices1899",it.key))]
  ], purchaseYieldValue(it), (v,ev)=>applyToInput(ev,v), String));
}

function renderToolbarOnly() {
  const sb = document.querySelector(".savebar");
  if (sb) sb.replaceWith(savebar(state.tab === "items" ? saveCatalog :
    state.tab === "crafting" ? saveCustomCrafting :
    state.tab === "effects" ? saveCatalog :
    state.tab === "loot" ? (state.lootFile === "__matrix" ? saveMatrix : state.lootFile === "__sounds" ? saveLootSounds : saveLoot) :
    state.tab === "shops" ? saveShopTab :
    state.tab === "challenges" ? saveChallenges :
    state.tab === "weapons" ? saveWeapons :
    state.tab === "ai" ? saveAI :
    state.tab === "crime" ? saveCrime : saveMatrix));
  refreshGlobalSave();
}

const isCraftCost = c => c.costtype === "COST_TYPE_CRAFT" || (c.key || "").includes("CRAFT");
const CRAFT_COST_KEYS = {
  COST_CRAFTING:"General / portable recipe",
  COST_CRAFTING_2:"Alternate ingredients #2",
  COST_CRAFTING_3:"Alternate ingredients #3",
  COST_CRAFTING_4:"Alternate ingredients #4",
  COST_CRAFTING_FIRE:"Campfire: tonics, remedies & coffee",
  COST_CRAFTING_GRILL:"Campfire grill: seasoned meat",
  COST_CRAFTING_KNIFE:"Plain-meat cooking recipe",
  COST_CRAFTING_TRAPPER:"Trapper crafting",
  COST_CRAFTING_FENCE:"Fence crafting",
  COST_CRAFTING_PEARSON:"Pearson camp crafting"
};

function craftKeySelect(entry,onchange,usedKeys=[]) {
  return el("select", {class:"key",title:"Recipe context or alternate-recipe slot. The COST_CRAFTING_2–4 keys are alternate ingredient formulas for the same output, not different crafting stations.",onchange},
    ...Object.entries(CRAFT_COST_KEYS).map(([value,label])=>{const attrs={value,title:value};if(usedKeys.includes(value)&&entry.key!==value)attrs.disabled="disabled";const option=el("option",attrs,`${label} — ${value}`);if(entry.key===value)option.selected=true;return option;}));
}
function nextCraftKey(entries){return Object.keys(CRAFT_COST_KEYS).find(key=>!entries.some(e=>e.key===key))||"";}

function recipeUnlockKeys(){
  if(!state.catalog._recipeUnlockKeys){const base=new Set(["ALWAYS KNOWN"]);for(const it of state.catalog.items)for(const cost of it.buy.filter(isCraftCost))for(const key of cost.unlocks||[])if(key)base.add(key);state.catalog._recipeUnlockKeys=[...base].sort();}
  const keys=new Set(state.catalog._recipeUnlockKeys);
  for(const entries of Object.values(state.craftEdits))for(const recipe of entries)for(const key of recipe.unlocks||[])if(key)keys.add(key);
  return [...keys].sort();
}

function catalogItemKeys(){return state.catalog._itemKeys||(state.catalog._itemKeys=state.catalog.items.map(x=>x.key).sort());}

function catalogItemOptions(){
  return state.catalog._itemOptions||(state.catalog._itemOptions=state.catalog.items
    .map(it=>({value:it.key,label:`${localizedValue(it.nameKey)||"No localized name"} - ${it.key}`}))
    .sort((a,b)=>a.label.localeCompare(b.label)));
}

function pickNewIngredient(output,recipeIndex,rerender){
  pickIdentifier("Ingredient",catalogItemOptions(),"",item=>{
    ensureCraft(output)[recipeIndex].parts.push({item,qty:1});
    rerender();
  });
}

function validatedKeyEditor(kind,value,values,onSet){
  const input=el("input",{value,readonly:true,title:`Selected existing ${kind.toLowerCase()} identifier. Use the search button to change it.`});
  return LexeditorUI.choiceField(input,el("button",{title:`Choose an existing ${kind.toLowerCase()}`,onclick:()=>pickIdentifier(kind,values,input.value,v=>{input.value=v;onSet(v)})},LexeditorUI.selectionIcon()));
}

function linkedCatalogKeyEditor(value,onSet){
  const wrap=el("div",{class:"linked-catalog-key-editor"},validatedKeyEditor("Catalog item",value,catalogItemOptions(),onSet));
  const item=catalogItem(value);if(item)wrap.append(itemLink(value,true,localizedValue(item.nameKey)||value));
  return wrap;
}

function craftView(it) {
  // edited copy if present, else the underlying data (not yet dirty)
  return state.craftEdits[it.key] ??
    it.buy.filter(isCraftCost).map(c => ({ key: c.key, yield: c.yield || 1,
      parts: c.parts.map(p => ({ item: p.item, qty: p.qty })), unlocks: [...(c.unlocks || [])] }));
}

function costToRecipe(cost){
  return { key: cost.key, yield: cost.yield || 1,
    parts: cost.parts.map(p => ({ item: p.item, qty: p.qty })),
    unlocks: [...(cost.unlocks || [])] };
}

function refRecipes(it, ds){
  const ref=refItem(ds,it.key);
  return ref?ref.buy.filter(isCraftCost).map(costToRecipe):[];
}

function recipeSummary(recipe){
  if(!recipe)return "not present";
  const station=CRAFT_COST_KEYS[recipe.key]||recipe.key;
  const unlock=(recipe.unlocks||[])[0]||"ALWAYS KNOWN";
  const parts=(recipe.parts||[]).map(p=>`${p.item} ×${p.qty}`).join(", ")||"no ingredients";
  return `${station}; makes ${recipe.yield||1}; ${unlock}; ${parts}`;
}

function applyRecipeReference(it,index,recipe){
  const recipes=ensureCraft(it);
  recipes[index]=JSON.parse(JSON.stringify(recipe));
  renderItems();
}

function recipeReferenceControls(it,index){
  if(isRO())return "";
  const refs=[["V","vtag",refRecipes(it,"vanilla")[index]],["K","ktag",refRecipes(it,"kiddos")[index]]]
    .filter(([, , recipe])=>recipe);
  if(!refs.length)return "";
  return LexeditorUI.stack({fill:false},
    el("span",{class:"cat"},"Reference recipe"),
    ...refs.map(([tag,cls,recipe])=>el("button",{class:"table-link",title:recipeSummary(recipe),
      onclick:()=>applyRecipeReference(it,index,recipe)},el("b",{class:cls},tag+" "),recipeSummary(recipe))));
}

function ensureCraft(it) {
  if (!state.craftEdits[it.key])
    state.craftEdits[it.key] = JSON.parse(JSON.stringify(craftView(it)));
  return state.craftEdits[it.key];
}

function portableCraftEntries(entries){
  return entries.map(entry=>{
    if(!["COST_CRAFTING_TRAPPER","COST_CRAFTING_FENCE"].includes(entry.key))return entry;
    return {...entry,key:"COST_CRAFTING",parts:entry.parts.filter(part=>part.item!=="CURRENCY_CASH")};
  });
}

function craftCell(it) {
  const cell=LexeditorUI.stack({fill:false}),entries=craftView(it),controls=LexeditorUI.actionRow();
  const displayName=localizedValue(it.nameKey);
  const recipeVariant=!entries.length&&displayName?state.catalog.items.find(other=>other!==it&&localizedValue(other.nameKey)===displayName&&craftView(other).length):null;
  if(recipeVariant)controls.append(el("button",{class:"lex-ui-symbol icon-link",title:`Recipe is stored on ${recipeVariant.key}`,onclick:()=>goToRecipeOutput(recipeVariant.key)},"⌕"));
  if(entries.length)controls.append(el("button",{class:"lex-ui-symbol icon-link",title:"Open this item's recipes in Crafting",onclick:()=>goToRecipeOutput(it.key)},"⌕"));
  if(!entries.length&&isRO())controls.append(el("span",{class:"cat"},"none"));
  else if(recipeVariant)controls.append(el("button",{class:"table-link",title:`The game stores this formula on the separate ${recipeVariant.key} record.`,onclick:()=>goToRecipeOutput(recipeVariant.key)},"Recipe on crafted variant"));
  else {
    const toggleRecipe=()=>{
      if(!entries.length){const list=ensureCraft(it),key=nextCraftKey(list);if(key)list.push({key,yield:1,parts:[{item:"",qty:1}],unlocks:[]});}
      if(state.expandedRecipes.has(it.key))state.expandedRecipes.delete(it.key);else state.expandedRecipes.add(it.key);
      renderItems();
    };
    controls.append(entries.length
      ?el("button",{class:"table-link",onclick:toggleRecipe},`${entries.length} recipe${entries.length===1?"":"s"}`)
      :newButton({title:"Add recipe",onclick:toggleRecipe}));
  }
  cell.append(controls);
  if (!isRO()) {
    const vit = refItem("vanilla", it.key);
    const kit = refItem("kiddos", it.key);
    const vrecipes = vit ? vit.buy.filter(isCraftCost) : [];
    const krecipes = kit ? kit.buy.filter(isCraftCost) : [];
    if (vrecipes.length||krecipes.length) cell.append(refLine([
      ["V","vtag",vrecipes.length?vrecipes.length:null],["K","ktag",krecipes.length?krecipes.length:null]],v=>`${v} recipe${v===1?"":"s"}`));
  }
  return cell;
}


function itemEffectsCell(it){
  const cell=el("div");
  const draw=()=>{
    const current=isRO()?it.effects:[...(state.itemEffectEdits[it.key]??it.effects)];
    const vanilla=refItem("vanilla",it.key),kiddos=refItem("kiddos",it.key);
    const references=[["V","vtag",vanilla?.effects||[]],["K","ktag",kiddos?.effects||[]]]
      .filter(([, ,entries],index)=>index===0?!!vanilla:!!kiddos);
    const effectChip=(key,removable)=>{
      const known=state.effectByKey[key];
      const chip=LexeditorUI.inlineLabel(effectLink(key));chip.title=(known?effectSummary(known):"Unknown effect")+"\nkey: "+key;
      if(!isRO()&&removable){
        const remove=closeButton({title:"Remove effect"});
        remove.addEventListener("click",event=>{
          event.stopPropagation();event.preventDefault();
          const next=[...(state.itemEffectEdits[it.key]??it.effects)];
          next.splice(next.indexOf(key),1);setItemEffects(it,next);draw();renderToolbarOnly();
        });
        remove.addEventListener("click",event=>event.stopPropagation());chip.append(remove);
      }
      return chip;
    };
    let controls="";
    if(!isRO()){
      const add=newButton({title:"Add effect",onclick:()=>{
        const present=new Set(state.itemEffectEdits[it.key]??it.effects);
        const options=state.catalog.effects.filter(effect=>!present.has(effect.key)).map(effect=>{
          const name=effectDisplayName(effect.key);return {value:effect.key,label:name===effect.key?effect.key:`${name} (${effect.key})`};
        }).sort((a,b)=>a.label.localeCompare(b.label,undefined,{sensitivity:"base"}));
        pickIdentifier("Add effect",options,"",key=>{
          const next=[...(state.itemEffectEdits[it.key]??it.effects)];
          if(!next.includes(key)){next.push(key);setItemEffects(it,next);draw();renderToolbarOnly();}
        });
      }});
      const buttons=[add];
      const changed=vanilla&&JSON.stringify([...current].sort())!==JSON.stringify([...(vanilla.effects||[])].sort());
      if(changed)buttons.push(el("button",{class:"lex-ui-symbol icon-link",title:"Restore the complete Vanilla effect set",onclick:()=>{
        setItemEffects(it,[...(vanilla.effects||[])]);draw();renderToolbarOnly();
      }},"↺"));
      controls=el("span",{},...buttons);
    }
    cell.replaceChildren(multiValueReferences({
      kind:"item-effects",current,references,keyOf:key=>key,
      sortKey:key=>effectDisplayName(key),renderCurrent:key=>effectChip(key,true),renderGhost:key=>effectChip(key,false),
      addControl:controls,emptyText:"no effects",
    }));
  };
  draw();return cell;
}

const QUICK_SELECT_WEAPON_GROUP="QUICK_SELECT_ITEM_TYPE_WEAPON";
const QUICK_SELECT_SATCHEL_GROUP="QUICK_SELECT_ITEM_TYPE_SATCHEL_ITEM";
function quickSelectGroupForItem(it){
  return state.quickSelect?.items?.[it.key]?.group||
    (it.key.startsWith("WEAPON_")?QUICK_SELECT_WEAPON_GROUP:QUICK_SELECT_SATCHEL_GROUP);
}
function quickSelectBaseForItem(it){
  return state.quickSelect?.items?.[it.key]||{group:quickSelectGroupForItem(it),slots:[]};
}
function quickSelectSlotLabel(slot){
  return slot.toLowerCase().replace(/^sub_group_/,"").replace(/^weapons_/,"").replace(/^player_/,"player ")
    .replace(/^horse_/,"horse ").replaceAll("_"," ").replace(/\b\w/g,letter=>letter.toUpperCase());
}
function setQuickSelectSlots(it,slots){
  const base=quickSelectBaseForItem(it),next={group:base.group,slots:slots.map(row=>({id:row.id,sortOrder:row.sortOrder??null}))};
  if(JSON.stringify(next)===JSON.stringify(base))delete state.quickSelectEdits[it.key];
  else state.quickSelectEdits[it.key]=next;
  renderToolbarOnly();
}
function quickSelectSlotsCell(it){
  const wrap=LexeditorUI.stack({fill:false});
  if(!state.quickSelect?.available){
    wrap.append(el("span",{class:"cat",title:state.quickSelect?.reason||"quickselectitems.ymt is unavailable"},"Unavailable"));
    return wrap;
  }
  const draw=()=>{
    wrap.innerHTML="";
    const base=quickSelectBaseForItem(it),current=state.quickSelectEdits[it.key]||base;
    const known=state.quickSelect.slotsByGroup?.[current.group]||[];
    const used=new Set(current.slots.map(row=>row.id));
    if(!current.slots.length)wrap.append(el("span",{class:"cat"},"Not assigned to the quick-select radial"));
    current.slots.forEach((row,index)=>{
      const select=el("select",{class:it.key in state.quickSelectEdits?"edited":"",disabled:isRO(),title:`Quick-select slot ID: ${row.id}`,
        onchange:event=>{const next=current.slots.map(entry=>({...entry}));next[index].id=event.target.value;setQuickSelectSlots(it,next);draw();}});
      for(const slot of known){
        if(used.has(slot)&&slot!==row.id)continue;
        const option=el("option",{value:slot},quickSelectSlotLabel(slot));
        if(slot===row.id)option.selected=true;
        select.append(option);
      }
      if(!known.includes(row.id))select.prepend(el("option",{value:row.id,selected:""},row.id));
      wrap.append(LexeditorUI.actionRow(select,
        el("span",{class:"cat quick-select-order",title:"The file stores this sort order. Lexeditor preserves it when the slot changes."},
          row.sortOrder===null?"order: automatic":`order ${row.sortOrder}`),
        isRO()?"":closeButton({title:"Remove this quick-select assignment",onclick:()=>{
          const next=current.slots.filter((_,slotIndex)=>slotIndex!==index).map(entry=>({...entry}));setQuickSelectSlots(it,next);draw();
        }})));
    });
    if(!isRO()){
      const available=known.filter(slot=>!used.has(slot)).map(slot=>({value:slot,label:quickSelectSlotLabel(slot)}));
      wrap.append(newButton({class:"quick-select-add",disabled:!available.length,title:available.length?"Add another valid quick-select slot":"Every valid slot is already assigned",onclick:()=>{
        pickIdentifier("Add quick-select slot",available,"",slot=>{
          const now=state.quickSelectEdits[it.key]||quickSelectBaseForItem(it);
          setQuickSelectSlots(it,[...now.slots.map(entry=>({...entry})),{id:slot,sortOrder:null}]);draw();
        });
      }}));
    }
  };
  draw();return wrap;
}

function itemRow(it) {
  const buyCash = [], sellCash = [], other = [];
  for (const c of it.buy) {
    if (isCraftCost(c)) continue; // crafting handled by craftCell
    for (const p of c.parts) {
      if (p.item === "CURRENCY_CASH" && c.costtype === "COST_TYPE_PRICE") buyCash.push([c, p]);
      else other.push(["buy", c, p]);
    }
  }
  for (const c of it.sell) {
    for (const p of c.parts) {
      if (p.item === "CURRENCY_CASH") sellCash.push([c, p]);
      else other.push(["sell", c, p]);
    }
  }
  const effCell=itemEffectsCell(it);

  const vanIt = refItem("vanilla", it.key), kidIt = refItem("kiddos", it.key), p1899It = refItem("prices1899", it.key);
  const buyRef = refStack([["V", "vtag", cashOf(vanIt, "buy")], ["K", "ktag", cashOf(kidIt, "buy")], ["1899", "p1899tag", cashOf(p1899It, "buy")]],
    it.buy, (v, ev) => applyToInput(ev, fmtMoney(v)), v => "$" + fmtMoney(v));
  const sellRef = refStack([["V", "vtag", cashOf(vanIt, "sell")], ["K", "ktag", cashOf(kidIt, "sell")], ["1899", "p1899tag", cashOf(p1899It, "sell")]],
    it.sell, (v, ev) => applyToInput(ev, fmtMoney(v)), v => "$" + fmtMoney(v));
  const slotInfo=(slot,qty)=>{
    if(slot==="SLOTID_ANY"&&qty==="-1"&&/^UPGRADE_FSH_BAIT_(BREAD|CHEESE|CORN)$/.test(it.key))
      return "Permanent food-bait entitlement. Rockstar uses this -1 record plus a bait-specific tag to make Bread, Cheese, and Corn Bait available without maintaining or consuming a stack.";
    if(slot==="SLOTID_ANY")return qty==="0"?
      "Fallback/default inventory context. Zero means this fallback contributes no capacity; a specific Satchel or upgrade slot supplies the real limit." : qty==="-1"?
      "Fallback/default inventory context. -1 means no numeric catalog cap in this context; physical carrying rules or another inventory system may still restrict it." :
      "Fallback/default capacity used when no more-specific inventory slot applies.";
    if(slot==="SLOTID_SATCHEL")return "Base player-satchel capacity.";
    if(slot==="0x04718245")return "Legend of the East satchel capacity contribution; together with the base and category upgrade values it commonly raises the total to 99.";
    if(slot==="0xBE85CADE")return "Category-specific consumables satchel upgrade contribution.";
    if(slot==="0x0D7CB5AE")return "Category-specific provisions/materials satchel upgrade contribution.";
    if(slot==="0xE655E53D"||slot==="0xD4774180")return "One of the two cumulative ammunition-capacity upgrade contributions used by Rockstar across ammo categories. Add both rules when an ammo type should benefit from both vanilla ammo upgrades; the final capacity is the sum of its applicable rules.";
    if(slot==="0x550898DE"||slot==="0xAEEE1782")return "Unresolved engine inventory slot. Rockstar stored only this hash; no name was recovered from community string corpora. It is almost always -1 and is not proven to be a player-facing unlimited carry cap or a specific camp/horse context.";
    return `Hashed inventory/upgrade slot ${slot}. Its exact Rockstar name is unresolved; infer its contribution from which item categories use it and the vanilla reference value.`;
  };
  const carryCell = LexeditorUI.stack({fill:false});
  const permanentFoodBait=/^UPGRADE_FSH_BAIT_(BREAD|CHEESE|CORN)$/.test(it.key);
  const loteRule=(it.carry||[]).find(c=>c.slot==="0x04718245");
  for (const c of (it.carry || []).filter(c=>c.slot!=="0x04718245")) {
    const ek = it.key + "|" + c.slot;
    const cur = isRO() ? c.qty : (state.carryEdits[ek] ?? c.qty);
    const vIt = refItem("vanilla", it.key), kIt = refItem("kiddos", it.key);
    const vSlot = vIt && (vIt.carry || []).find(x => x.slot === c.slot);
    const kSlot = kIt && (kIt.carry || []).find(x => x.slot === c.slot);
    const displaySlot=permanentFoodBait&&c.slot==="SLOTID_ANY"&&String(cur)==="-1"?"permanent / unlimited":slotLabel(c.slot);
    const row = LexeditorUI.actionRow(
      el("span", { class: "cat slot-label", title: `${c.slot}\n${slotInfo(c.slot,String(cur))}` }, displaySlot),
      el("input", { type: "number", step: "1", value: cur,
        class: ek in state.carryEdits ? "edited" : "", title:`Capacity contribution from ${slotLabel(c.slot)} (${c.slot})`,
        onchange: ev => {
          const v = String(Math.round(parseFloat(ev.target.value || "0")));
          if (v === c.qty) delete state.carryEdits[ek];
          else state.carryEdits[ek] = v;
          ev.target.classList.toggle("edited", ek in state.carryEdits);
          renderToolbarOnly();
        } }));
    if (!isRO() && (vSlot || kSlot)) {
      const ref = carryRefLine([["V","vtag",vSlot?.qty],["K","ktag",kSlot?.qty]],value=>permanentFoodBait&&String(value)==="-1"?"unlimited":String(value));
      row.append(ref);
    }
    carryCell.append(row);
  }
  if(!isRO()){
    const otherTotal=(it.carry||[]).filter(c=>c.slot!=="0x04718245"&&!['0xE655E53D','0xD4774180'].includes(c.slot)).reduce((sum,c)=>{
      const value=+(state.carryEdits[`${it.key}|${c.slot}`]??c.qty);return sum+(value>0?value:0);
    },0);
    const loteValue=loteRule?+(state.carryEdits[`${it.key}|0x04718245`]??loteRule.qty):0;
    carryCell.append(LexeditorUI.actionRow(
      el("span",{class:"cat slot-label"},"LotE 999?"),
      fieldHelp("Sets the Legend of the East satchel contribution so this item's combined applicable capacity is exactly 999."),
      el("input",{type:"checkbox",title:"Set this item's total capacity to 999 with the Legend of the East satchel",...((loteValue+otherTotal===999)?{checked:""}:{}),onchange:ev=>{
      it.carry=it.carry||[];let rule=it.carry.find(c=>c.slot==="0x04718245");
      if(!rule){rule={slot:"0x04718245",qty:"0"};it.carry.push(rule);}
      const key=`${it.key}|0x04718245`;
      if(ev.target.checked){const other=it.carry.filter(c=>c!==rule&&!["0xE655E53D","0xD4774180"].includes(c.slot)).reduce((sum,c)=>{const v=+(state.carryEdits[`${it.key}|${c.slot}`]??c.qty);return sum+(v>0?v:0);},0);state.carryEdits[key]=String(Math.max(0,999-other));}
      else if(rule.qty==="0")delete state.carryEdits[key];else state.carryEdits[key]=rule.qty;
      renderItems();
    }})));
    carryCell.append(LexeditorUI.actionRow(newButton({title:"Add another context-specific capacity rule",onclick:()=>{
      const slots=carrySlotOptions(it);
      pickIdentifier("Carry-cap slot",slots,"",slot=>{it.carry=it.carry||[];it.carry.push({slot,qty:"1"});state.carryEdits[`${it.key}|${slot}`]="1";renderItems();});
    }})));
  }
  const thrownAmmo = it.key.startsWith("WEAPON_THROWN_") ?
    (it.key.includes("THROWING_KNIVES") ? "AMMO_THROWING_KNIVES" :
     it.key.includes("TOMAHAWK") ? "AMMO_TOMAHAWK" :
     it.key.includes("DYNAMITE") ? "AMMO_DYNAMITE" :
     it.key.includes("MOLOTOV") ? "AMMO_MOLOTOV" : "") : "";
  if (thrownAmmo) {
    carryCell.innerHTML="";
    carryCell.append(el("div",{class:"cat"},"Weapon instance (not usable quantity)"),
      itemLink(thrownAmmo,true,`Capacity → ${thrownAmmo}`));
  }
  const bundleInfo=purchaseBundleOf(it),containerInfo=purchaseContainersFor(it);
  const relationshipTitle=bundleInfo?
    `Container item. One purchase opens into ${bundleInfo.min} × ${localizedValue(bundleInfo.targetItem?.nameKey)||bundleInfo.target}. The container's price controls the shop purchase; the contained item's carry cap controls usable bait capacity.`:
    containerInfo.length?`Contained item produced by ${containerInfo.map(bundle=>localizedValue(state.catalog.items.find(x=>x.key===Object.keys(PURCHASE_CONTAINERS).find(key=>PURCHASE_CONTAINERS[key].target===it.key))?.nameKey)||bundle.container).join(", ")}. Its own price does not control that container purchase; its carry cap controls the usable bait stack.`:"";
  const texture=(it.textures||[]).find(t=>t.dict==="INVENTORY_ITEMS"&&t.type==="INVENTORY")||(it.textures||[])[0];
  const referenceName=it.nameKey?localizedReference(it.nameKey):undefined;
  const nameReference=referenceName!==undefined&&referenceName!==localizedValue(it.nameKey)
    ?el("div",{class:"name-ref"},refStack([["V","vtag",referenceName]],localizedValue(it.nameKey),(value,ev)=>{const inp=ev.currentTarget.closest(".item-identity")?.querySelector("input.localized-name");if(inp){inp.value=value;inp.dispatchEvent(new Event("change"));}},String)):"";
  const identityMain=el("div",{class:"item-identity-main"},
      el("div",{class:"name-line"},
        relationshipTitle?el("span",{class:"special-info",title:relationshipTitle},"⚠"):"",
        localizationInput(it.nameKey),
        null,
        el("div",{class: "item-meta-line"},
          el("span",{class:"key item-meta-id"},it.key),
          el("span",{class: "item-meta-taxonomy"},
            el("span",{class:"item-meta-group"},it.group||"NO GROUP"),
            el("span",{class:"item-meta-separator","aria-hidden":"true"}),
            el("span",{class:"item-meta-category"},it.category.replace("CI_CATEGORY_","")))),
        nameReference));
  // Shown, not clicked: the heading icon's click belongs to the shared model
  // preview, and there is no separate full-size dialog.
  const identity=el("div",{class:"item-identity"},itemIcon(texture,it),identityMain);

  const identityCell = el("div", {},identity);
  const usedInCell = (() => { const uses = recipesUsing(it.key); return el("div", {}, uses.length ?
      el("button", { class:"save", style:"padding:4px 10px", onclick:()=>goToRecipesUsing(it.key) }, `${uses.length} recipe${uses.length===1?"":"s"}`) :
      el("span", {class:"cat"}, "none")); })();
  const cells = {
    identity: identityCell, description: itemDescriptionCell(it),
    buy: buyPriceCell(it,buyCash,buyRef), purchase: purchaseQuantityCell(it),
    sell: sellPriceCell(it,sellCash,sellRef), carry: carryCell,
    quickSelect: el("div",{},quickSelectSlotsCell(it)),
    recipe: craftCell(it), usedIn: usedInCell, effects: effCell,
    tags: el("div", {}, itemTagsCell(it)),
  };
  return itemDetailPane(it, cells);
}

// Split-view detail: the same cells itemRow builds, laid out vertically as
// full-width labelled rows so each field has room for its input + beside refs
// (reuses every cell builder; the <td> children are just moved into a div).
function itemDetailPane(it, cells){
  // The identity is the panel's HEADING, in the shared shape every other
  // plugin uses: an icon slot on the left and the record's names beside it.
  // It used to be the first ordinary field in the scrolling body, which is
  // why this plugin also had to grow its own preview button - there was no
  // heading icon for the shared control to take over.
  const controlFor=cell=>cell;
  const field=(label,cell,help)=>LexeditorUI.detailField({label,control:controlFor(cell),help:help?fieldHelp(help):null});
  const identity=cells.identity.querySelector(".item-identity");
  const identityIcon=identity?.querySelector("[data-inventory-icon]");
  const identityMain=identity?.querySelector(".item-identity-main");
  const input=identityMain?.querySelector("input.localized-name")||localizationInput(it.nameKey);
  const vanilla=localizedReference(it.nameKey);
  const name=refField(input,vanilla===undefined?[]:[["V","vtag",vanilla]],input.value,
    value=>{input.value=value;input.dispatchEvent(new Event("change"));},String);
  const body=LexeditorUI.stack({fill:false});
  input.setAttribute("aria-label","Item name");
  input.placeholder="No localized name";
  const pane=LexeditorUI.detailPanel({titleControl:name,
    meta:it.key,icon:identityIcon||null,body});
  body.append(LexeditorUI.controlGroup([
    {label:"Group",control:LexeditorUI.readonlyField(it.group||"No group")},
    {label:"Category",control:LexeditorUI.readonlyField(it.category.replace("CI_CATEGORY_",""))}]));
  const relationship=identityMain?.querySelector(".special-info");
  if(relationship)body.append(relationship);
  body.append(
    field("Description",cells.description),
    field("Buy price",cells.buy),
    field("Purchase output",cells.purchase,"What one purchase ultimately provides."),
    field("Sell price",cells.sell),
    field("Carry cap rules",cells.carry,"Each number is that inventory context's capacity contribution; applicable rules combine."),
    field("Quick-select slots",cells.quickSelect,"Actual radial assignments from quickselectitems.ymt. An item can have zero, one, or several slots. New assignments use the next sort order automatically."),
    field("Recipe",cells.recipe),
    field("Used in recipes",cells.usedIn),
    field("Effects",cells.effects),
    field("Tags",cells.tags,"Catalog tags. Use + to select a named tag from the full grouped list. Free-entry hashes are not supported."));
  const sources=LexeditorUI.stack({fill:false},LexeditorUI.detailNote("Loading acquisition sources…"));
  body.append(LexeditorUI.detailSection({title:"Acquisition sources",body:sources}));
  fillItemSources(it,sources).catch(error=>sources.replaceChildren(LexeditorUI.detailNote(error.message)));
  return attachItemModelPreview(pane,it);
}

const inventoryIconLoads=new Map();

function inventoryIconCandidates(texture){
  if(!texture?.id)return [];
  const dict=(texture.dict||"").toUpperCase();
  // Some catalog viewer references contain multiple texture names (for
  // example a two-page book) separated by whitespace. Treat those as
  // ordered fallbacks instead of URL-encoding the whole string into one
  // impossible filename.
  const ids=String(texture.id).trim().split(/\s+/).filter(Boolean)
    .map(value=>encodeURIComponent(value.toLowerCase()));
  if(!ids.length)return [];
  if(dict==="INVENTORY_ITEMS")return ids.flatMap(id=>[
    `/assets/inventory_icons/inventory_items/${id}.png`,
    `https://femga.com:8080/images/samples/ui_textures_no_bg/inventory_items/${id}.png`,
  ]);
  // Femga stores the RDO dictionary below its ui_textures_mp family. The old
  // generic dictionary path omitted that family and returned an HTML 404.
  if(dict==="INVENTORY_ITEMS_MP")return ids.map(id=>
    `https://femga.com:8080/images/samples/ui_textures_no_bg/ui_textures_mp/inventory_items_mp/${id}.png`);
  if(dict==="LEX_INVENTORY_ITEMS")return ids.map(id=>`/assets/item-icons/${id}.png`);
  if(dict==="ITEM_TEXTURES"||dict==="UI_ITEMVIEWER")return ids.map(id=>
    `/assets/dictionary_icons/${dict.toLowerCase()}/${id}.png`);
  if(dict)return ids.map(id=>
    `https://femga.com:8080/images/samples/ui_textures_no_bg/${dict.toLowerCase()}/${id}.png`);
  return [];
}

function inventoryIconKey(texture){return `${(texture?.dict||"").toUpperCase()}|${(texture?.id||"").toUpperCase()}`;}

function loadInventoryIcon(texture){
  const key=inventoryIconKey(texture),known=inventoryIconLoads.get(key);
  if(known)return known;
  const candidates=inventoryIconCandidates(texture);
  const load=new Promise(resolve=>{
    const tryAt=index=>{
      if(index>=candidates.length){resolve("");return;}
      const image=new Image();
      image.onload=()=>resolve(image.naturalWidth&&image.naturalHeight?candidates[index]:"");
      image.onerror=()=>tryAt(index+1);
      image.src=candidates[index];
    };
    tryAt(0);
  });
  inventoryIconLoads.set(key,load);return load;
}

function brokenImageIcon(){
  const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");
  svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("aria-hidden","true");
  const path=document.createElementNS(ns,"path");path.setAttribute("fill","none");path.setAttribute("stroke","currentColor");
  path.setAttribute("stroke-width","1.7");path.setAttribute("stroke-linecap","round");path.setAttribute("stroke-linejoin","round");
  path.setAttribute("d","M4 4h16v16H4z M7 16l3-3 2 2 2-2 3 3 M8 8h.01 M5 19 19 5");svg.append(path);return svg;
}

function itemIcon(texture,it){
  const slot=LexeditorUI.iconSlot({message:"Loading icon…"});
  slot.dataset.inventoryIcon="";
  slot.title=texture?`${texture.dict} / ${texture.id}`:"No inventory icon";
  slot.lexLoaded=loadInventoryIcon(texture).then(src=>{
    if(src)slot.replaceChildren(el("img",{src,alt:`${localizedValue(it.nameKey)?.trim()||it.key} icon`}));
    else{slot.dataset.missing="true";slot.replaceChildren(brokenImageIcon());}
  });
  return slot;
}

function modelPreviewKey(it){return `${state.ds}|${it.key}|${it.model||""}`;}

function modelEyeThrobber(){return LexeditorUI.badge("…",{title:"Loading model preview"});}

// The shared model-preview control: the panel's heading icon is the trigger,
// its magnifier stays visible while open, and the model appears in the drawer
// that slides over the editing surface. Every plugin gets that same control
// from the framework. What stays private here is the part that has to be:
// which archive holds the mesh, whether this machine can read it, and how the
// geometry is fetched and drawn. This plugin used to own the whole thing - a
// separate eye button in the name line opening a page-wide modal - so a reader
// moving between games met a different control in the same situation.
function attachItemModelPreview(pane,it){
  const icon=window.LexeditorUI?.panelIcon?.(pane);
  if(!icon)return pane;
  const describe=text=>{icon.title=text;icon.setAttribute("aria-label",text);};
  const hideEmptyIcon=()=>{
    const slot=icon.querySelector("[data-inventory-icon]");
    slot?.lexLoaded?.then(()=>{if(slot.dataset.missing==="true"){
      icon.parentElement?.classList.add("no-icon");icon.remove();
    }});
  };
  if(!it.model){describe("This catalog item does not name a model asset");hideEmptyIcon();return pane;}
  const key=modelPreviewKey(it);
  let status=state.modelPreviewAvailability[key];
  if(!status){
    const promise=api(`/api/model-preview/availability?item=${encodeURIComponent(it.key)}`)
      .then(result=>{state.modelPreviewAvailability[key]=result;return result;})
      .catch(error=>{const result={available:false,reason:`Model check failed: ${error.message}`};state.modelPreviewAvailability[key]=result;return result;});
    status={checking:true,promise};state.modelPreviewAvailability[key]=status;
  }
  const settle=result=>{
    if(!pane.contains(icon))return;
    if(result?.available!==true){
      describe(result?.reason||"This installed model is not previewable");
      hideEmptyIcon();
      return;
    }
    armItemModelPreview(pane,it);
  };
  if(status.checking&&status.promise){
    describe(`Checking the installed ${it.model} asset\u2026`);
    status.promise.then(settle,()=>settle(null));
  }else settle(status);
  return pane;
}

// The drawer's contents. It opens immediately saying what it is doing, because
// reading a mesh out of the installed archives is not instant and a control
// that does nothing for four seconds reads as broken.
function armItemModelPreview(pane,it){
  const name=localizedValue(it.nameKey)||it.key;
  let controller=null;
  const facts=LexeditorUI.stack({fill:false,compact:true});
  const modelDetails=LexeditorUI.detailSection({title:"Model geometry",body:facts});
  LexeditorUI.attachModelPreview(pane,{
    label:`${name} model`,
    openLabel:`View the real ${it.model} model`,
    closeLabel:`Close the ${it.model} model`,
    content:()=>{
      const canvas=el("canvas",{"aria-label":`Interactive 3D preview of ${it.model}`});
      const stage=LexeditorUI.modelStage({message:`Preparing the real ${it.model} model…`}),message=stage.lexMessage;
      stage.prepend(canvas);
      const drawer=stage;
      canvas.hidden=true;
      prepareModelPreview(it).promise.then(async task=>{
        if(!drawer.isConnected)return;
        const preview=task.preview,geometry=task.geometry;
        controller=await createModelRenderer(canvas,geometry);
        if(!drawer.isConnected){controller.dispose();controller=null;return;}
        canvas.hidden=false;
        message.replaceChildren(el("span",{},"Drag to rotate \u00b7 Wheel to zoom \u00b7 Double-click to reset"));
        message.className="lex-model-stage-hint";
        facts.replaceChildren(
          el("span",{},`${preview.format} \u00b7 LOD ${geometry.lod}`),
          el("span",{},`${preview.summary.vertices.toLocaleString()} vertices`),
          el("span",{},`${preview.summary.triangles.toLocaleString()} triangles`),
          el("span",{title:`${preview.source.outerArchive} \u2192 ${preview.source.archiveChain.join(" \u2192 ")} \u2192 ${preview.source.entry}`},
            `${preview.source.outerArchive} \u2192 ${preview.source.entry}`),
          el("span",{},preview.limitations.join(" ")));
        if(!modelDetails.isConnected)LexeditorUI.sectionParts(pane).content.append(modelDetails);
        window.__lexModelPreview={item:it.key,model:it.model,preview,geometry,canvas,controller};
        requestAnimationFrame(controller.draw);
      }).catch(error=>{
        delete state.modelPreviewLoads[modelPreviewKey(it)];
        if(drawer.isConnected)message.replaceChildren(el("span",{},error.message));
      });
      return drawer;
    },
    onClose:drawer=>{
      controller?.dispose();controller=null;
      drawer.replaceChildren();
      delete window.__lexModelPreview;
    },
  });
}

function prepareModelPreview(it){
  const key=modelPreviewKey(it),existing=state.modelPreviewLoads[key];
  if(existing)return existing;
  const task={key,status:"loading",preview:null,geometry:null,error:null,promise:null};
  task.promise=(async()=>{
    const preview=await api("/api/model-preview",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({item:it.key,model:it.model})});
    const response=await fetch(preview.geometryUrl);if(!response.ok)throw new Error("The cached model geometry could not be read.");
    task.preview=preview;task.geometry=await response.json();task.status="ready";return task;
  })().catch(error=>{task.status="error";task.error=error;throw error;});
  state.modelPreviewLoads[key]=task;return task;
}

function formatFileSize(value){
  const bytes=Math.max(0,Number(value)||0);if(bytes<1024)return `${bytes} B`;
  const units=["KB","MB","GB"],power=Math.min(units.length,Math.floor(Math.log(bytes)/Math.log(1024)));
  return `${(bytes/1024**power).toFixed(power>1?2:1)} ${units[power-1]}`;
}

async function showLexeditorSettings(){
  document.querySelector(".model-settings-backdrop")?.remove();
  const backdrop=el("div",{class:"lex-dialog-backdrop model-settings-backdrop","data-lex-history-control":"true"});
  const dialog=el("section",{class:"lex-dialog lex-settings-dialog",role:"dialog","aria-modal":"true","aria-label":"Lexeditor settings"});
  const status=el("div",{class:"lex-dialog-status","aria-live":"polite"},"Loading settings…");
  let onKey=null;
  const close=()=>{if(onKey)document.removeEventListener("keydown",onKey);backdrop.remove();};
  const closeButton=el("button",{class:"lex-dialog-action",onclick:close},"Close");
  dialog.append(el("h2",{},"Lexeditor Settings"),el("p",{},"Storage used by editor-only files."),status);
  backdrop.append(dialog);document.body.append(backdrop);
  backdrop.addEventListener("click",event=>{if(event.target===backdrop)close();});
  onKey=event=>{if(event.key==="Escape")close();};
  document.addEventListener("keydown",onKey);
  try{
    let settings=await api("/api/model-preview/settings");
    let savedCacheSize=Number(settings.cacheSizeMb);
    const size=el("input",{type:"number",min:String(settings.minCacheSizeMb),max:String(settings.maxCacheSizeMb),step:"1",value:String(settings.cacheSizeMb),"aria-label":"Model preview cache size in MB"});
    const usage=el("div");
    const path=LexeditorUI.detailNote("");
    const update=next=>{
      settings=next;size.value=String(next.cacheSizeMb);
      usage.textContent=`${formatFileSize(next.cacheBytes)} used by ${next.cacheEntries} cached preview${next.cacheEntries===1?"":"s"}.`;
      path.textContent=next.cacheRoot;
    };
    const save=LexeditorUI.settingsSaveControl({
      dirtyCount:()=>Number(size.value)!==savedCacheSize?1:0,
      pendingChanges:()=>Number(size.value)===savedCacheSize?[]:[{label:"Model preview cache size (MB)",before:savedCacheSize,after:Number(size.value)}],
      save:async()=>{status.textContent="Saving settings…";const next=await api("/api/model-preview/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({cacheSizeMb:Number(size.value)})});update(next);savedCacheSize=Number(next.cacheSizeMb);status.textContent="Cache settings saved.";},
      discard:()=>{size.value=String(savedCacheSize);status.textContent="Restored the last saved cache setting.";}
    });
    const clear=el("button",{class:"lex-dialog-action danger-action",onclick:async()=>{
      if(clear.dataset.armed!=="true"){
        clear.dataset.armed="true";clear.textContent="Click again to clear";
        status.textContent="Only generated model previews will be removed. They can be created again.";
        setTimeout(()=>{if(clear.isConnected){clear.dataset.armed="false";clear.textContent="Clear cache";}},5000);return;
      }
      clear.disabled=true;status.textContent="Clearing model previews…";
      try{const next=await api("/api/model-preview/cache/clear",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.modelPreviewLoads={};update(next);status.textContent=`Cleared ${formatFileSize(next.removedBytes)} from the model-preview cache.`;}
      catch(error){status.textContent=error.message;}finally{clear.disabled=false;clear.dataset.armed="false";clear.textContent="Clear cache";}
    }},"Clear cache");
    const card=LexeditorUI.detailSection({title:"Item model previews",body:[
      LexeditorUI.detailField({label:"Maximum cache size",control:LexeditorUI.unitField(size,"MB"),help:fieldHelp(`Between ${settings.minCacheSizeMb} MB and ${settings.maxCacheSizeMb} MB. Old previews leave the cache first.`)}),
      LexeditorUI.stack({fill:false},usage,path,LexeditorUI.detailNote(`Supported now: ${settings.supportedFormats.join(", ")}.`),LexeditorUI.detailNote(`Not yet: ${settings.notYetSupported.join(", ")}.`))]});
    dialog.replaceChildren(el("h2",{},"Lexeditor Settings"),el("p",{},"Storage used by editor-only files."),card,status,
      el("div",{class:"lex-dialog-actions"},clear,closeButton,save));
    update(settings);status.textContent="";size.focus();
  }catch(error){
    status.textContent=error.message;dialog.append(el("div",{class:"lex-dialog-actions"},closeButton));
  }
}

async function createModelRenderer(canvas,geometry){
  const gl=canvas.getContext("webgl2",{antialias:true,alpha:false});
  if(!gl)throw new Error("This window cannot start the WebGL 2 model renderer.");
  if(!geometry.materials?.length)throw new Error("The model has no decoded game material.");
  const compile=(type,source)=>{
    const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);
    if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){const message=gl.getShaderInfoLog(shader);gl.deleteShader(shader);throw new Error("Model renderer shader failed: "+message);}
    return shader;
  };
  const vertex=compile(gl.VERTEX_SHADER,`#version 300 es
    in vec3 aPosition;in vec3 aNormal;in vec2 aTexCoord0;in vec2 aTexCoord1;in vec4 aColor;
    uniform float uYaw;uniform float uPitch;uniform float uZoom;uniform float uAspect;
    out vec3 vNormal;out vec3 vPosition;out vec2 vTexCoord0;out vec2 vTexCoord1;out vec4 vColor;
    vec3 rotateY(vec3 v,float a){float c=cos(a),s=sin(a);return vec3(c*v.x+s*v.z,v.y,-s*v.x+c*v.z);}
    vec3 rotateX(vec3 v,float a){float c=cos(a),s=sin(a);return vec3(v.x,c*v.y-s*v.z,s*v.y+c*v.z);}
    void main(){vec3 p=vec3(aPosition.x,aPosition.z,-aPosition.y);vec3 n=vec3(aNormal.x,aNormal.z,-aNormal.y);
      p=rotateX(rotateY(p,uYaw),uPitch);n=rotateX(rotateY(n,uYaw),uPitch);
      vNormal=n;vPosition=p;vTexCoord0=vec2(1.0-aTexCoord0.x,aTexCoord0.y);vTexCoord1=vec2(1.0-aTexCoord1.x,aTexCoord1.y);vColor=aColor;
      gl_Position=vec4(p.x*uZoom/uAspect,p.y*uZoom,p.z*.28,1.0);}`);
  const fragment=compile(gl.FRAGMENT_SHADER,`#version 300 es
    precision highp float;in vec3 vNormal;in vec3 vPosition;in vec2 vTexCoord0;in vec2 vTexCoord1;in vec4 vColor;
    uniform sampler2D uLayer0Diffuse;uniform sampler2D uLayer0Normal;uniform sampler2D uLayer0Material;
    uniform sampler2D uLayer1Diffuse;uniform sampler2D uLayer1Material;uniform sampler2D uControl;uniform sampler2D uEngraving;uniform sampler2D uAlbedoPalette;
    uniform float uUseAlbedoPalette;uniform float uMaterialKind;
    out vec4 outColor;
    mat3 cotangentFrame(vec3 n,vec3 p,vec2 uv){vec3 dp1=dFdx(p),dp2=dFdy(p);vec2 duv1=dFdx(uv),duv2=dFdy(uv);
      vec3 dp2perp=cross(dp2,n),dp1perp=cross(n,dp1);vec3 t=dp2perp*duv1.x+dp1perp*duv2.x;vec3 b=dp2perp*duv1.y+dp1perp*duv2.y;
      float invmax=inversesqrt(max(dot(t,t),dot(b,b)));return mat3(t*invmax,b*invmax,n);}
    vec3 srgbToLinear(vec3 color){return pow(max(color,vec3(0.0)),vec3(2.2));}
    void main(){vec3 surfaceNormal=normalize(vNormal);if(!gl_FrontFacing)surfaceNormal=-surfaceNormal;
      vec3 mapNormal=texture(uLayer0Normal,vTexCoord0).xyz*2.0-1.0;mapNormal.xy*=1.65;mapNormal.z=sqrt(max(1.0-dot(mapNormal.xy,mapNormal.xy),.001));mapNormal.y=-mapNormal.y;
      vec3 n=normalize(cotangentFrame(surfaceNormal,vPosition,vTexCoord0)*mapNormal);
      if(uMaterialKind>.5){vec3 base=srgbToLinear(texture(uLayer0Diffuse,vTexCoord0).rgb);vec3 packed=texture(uLayer0Material,vTexCoord0).rgb;
        float roughness=clamp(packed.g,.12,.95);vec3 lightDir=normalize(vec3(-.28,.68,.68)),fillDir=normalize(vec3(.72,.18,.55)),viewDir=vec3(0.0,0.0,1.0),halfDir=normalize(lightDir+viewDir);
        float ndl=max(dot(n,lightDir),0.0),fill=max(dot(n,fillDir),0.0),ndh=max(dot(n,halfDir),0.0),fresnel=pow(1.0-max(dot(n,viewDir),0.0),5.0);float specular=pow(ndh,mix(18.0,150.0,1.0-roughness));
        vec3 color=base*(.20+.70*ndl+.10*fill)+vec3(.035)*(specular*(.22+.62*(1.0-roughness))+fresnel*.08);outColor=vec4(pow(clamp(color,vec3(0.0),vec3(1.0)),vec3(1.0/2.2)),1.0);return;}
      vec3 control=texture(uControl,vTexCoord0).rgb;float rustSignal=max(control.r,control.g*.7);
      float rustMask=smoothstep(.18,.78,rustSignal)*mix(.46,.18,step(.5,uUseAlbedoPalette));
      vec4 layer0=texture(uLayer0Diffuse,vTexCoord0);float paletteRow=(floor(vColor.g*255.0+.5)+.5)/128.0;
      vec3 paletteColor=srgbToLinear(texture(uAlbedoPalette,vec2(layer0.g,paletteRow)).rgb);
      vec3 clean=mix(srgbToLinear(layer0.rgb),paletteColor*1.28,step(.5,uUseAlbedoPalette));vec3 rust=srgbToLinear(texture(uLayer1Diffuse,vTexCoord1*32.0).rgb);
      vec3 material=mix(texture(uLayer0Material,vTexCoord0).rgb,texture(uLayer1Material,vTexCoord1*32.0).rgb,rustMask);
      vec4 engraving=texture(uEngraving,vTexCoord0);float wear=engraving.b;float groove=smoothstep(.05,.55,engraving.r);
      float surfaceVariation=mix(.68,1.32,dot(control,vec3(.34,.46,.20)));
      vec3 base=mix(clean,rust,rustMask)*mix(.74,1.18,wear)*surfaceVariation;base=mix(base,base*.16,groove*.72);
      float metallic=clamp(material.r,0.0,1.0);float roughness=clamp(material.g-.14*(1.0-rustMask),.07,.9);
      vec3 lightDir=normalize(vec3(-.28,.68,.68)),fillDir=normalize(vec3(.72,.18,.55)),viewDir=normalize(vec3(0.0,0.0,1.0)),halfDir=normalize(lightDir+viewDir);
      float ndl=max(dot(n,lightDir),0.0),fill=max(dot(n,fillDir),0.0),ndh=max(dot(n,halfDir),0.0),fresnel=pow(1.0-max(dot(n,viewDir),0.0),5.0);
      float specular=pow(ndh,mix(18.0,190.0,1.0-roughness));vec3 specColor=mix(vec3(.04),base,metallic);
      float rim=pow(1.0-max(dot(n,viewDir),0.0),2.2);float sheen=pow(max(dot(n,normalize(vec3(-.72,.30,.62))),0.0),5.0);
      vec3 environment=mix(vec3(.045,.055,.075),vec3(.36,.40,.47),clamp(n.y*.5+.5,0.0,1.0));
      vec3 color=base*(.38+.76*ndl+.24*fill)*(1.0-metallic*.28)+specColor*(specular*3.2+fresnel*.42+sheen*.34)+environment*(.13+.22*metallic);
      color+=vec3(.18,.23,.34)*rim*(.05+.10*metallic)+vec3(.32,.12,.04)*rustMask*.24;color*=.86;color=pow(clamp(color,vec3(0.0),vec3(1.0)),vec3(1.0/2.2));outColor=vec4(color,1.0);}`);
  const program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);
  gl.deleteShader(vertex);gl.deleteShader(fragment);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error("Model renderer link failed: "+gl.getProgramInfoLog(program));
  const locations={position:gl.getAttribLocation(program,"aPosition"),normal:gl.getAttribLocation(program,"aNormal"),texCoord0:gl.getAttribLocation(program,"aTexCoord0"),texCoord1:gl.getAttribLocation(program,"aTexCoord1"),color:gl.getAttribLocation(program,"aColor"),
    yaw:gl.getUniformLocation(program,"uYaw"),pitch:gl.getUniformLocation(program,"uPitch"),zoom:gl.getUniformLocation(program,"uZoom"),aspect:gl.getUniformLocation(program,"uAspect"),useAlbedoPalette:gl.getUniformLocation(program,"uUseAlbedoPalette"),materialKind:gl.getUniformLocation(program,"uMaterialKind")};
  const textureUniforms=["uLayer0Diffuse","uLayer0Normal","uLayer0Material","uLayer1Diffuse","uLayer1Material","uControl","uEngraving","uAlbedoPalette"].map(name=>gl.getUniformLocation(program,name));
  const imageOf=url=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error("A decoded game texture could not be loaded."));image.src=url;});
  const resources=[];
  const textureOf=async(meta,fallback,repeat=true)=>{const texture=gl.createTexture(),image=meta?await imageOf(meta.url):null;gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
    if(image){gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);}
    else{gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array(fallback));}
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,repeat?gl.REPEAT:gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,repeat?gl.REPEAT:gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.generateMipmap(gl.TEXTURE_2D);resources.push({kind:"texture",value:texture});return texture;};
  const materialSets=await Promise.all(geometry.materials.map(async material=>{const shader=material.shader.toLowerCase(),t=material.textures||{};
    if(shader==="standard_weapon_2lyr")return{kind:0,hasPalette:!!t.albedopalettetex,textures:await Promise.all([
      textureOf(t.lyr0diffusetex,[211,203,189,255]),textureOf(t.lyr0normaltex,[128,128,255,255]),textureOf(t.lyr0materialatex,[255,58,255,255]),
      textureOf(t.lyr1diffusetex,[74,42,30,255]),textureOf(t.lyr1materialatex,[0,140,255,255]),textureOf(t.controltexturetex,[0,0,0,255]),textureOf(t.engravingtexturetex,[0,0,180,255]),textureOf(t.albedopalettetex,[128,92,56,255],false)])};
    if(shader==="standard"||shader==="standard_dirt"||shader==="standard_glass")return{kind:1,glass:shader==="standard_glass",hasPalette:false,textures:await Promise.all([
      textureOf(t.diffusetex,[148,142,132,255]),textureOf(t.bumptex,[128,128,255,255]),textureOf(t.speculartex,[22,150,255,255]),
      textureOf(t.diffusetex2,[0,0,0,255]),textureOf(t.speculartex2,[0,128,255,255]),textureOf(null,[0,0,0,255]),textureOf(null,[0,0,0,255]),textureOf(t.tintpalettetex,[128,128,128,255],false)])};
    throw new Error(`The ${material.shader} game material is not rendered yet.`);}));
  const bounds=geometry.bounds,center=bounds.min.map((value,index)=>(value+bounds.max[index])/2);
  const largest=Math.max(...bounds.max.map((value,index)=>value-bounds.min[index]),.000001),scale=1.90/largest;
  const meshes=geometry.meshes.map(mesh=>{const positions=new Float32Array(mesh.positions.length*3),normals=new Float32Array(mesh.normals.length*3),texCoord0=new Float32Array(mesh.texCoords0.length*2),texCoord1=new Float32Array(mesh.texCoords1.length*2),colors=new Float32Array(mesh.colors.length*4);
    mesh.positions.forEach((row,i)=>{positions[i*3]=(row[0]-center[0])*scale;positions[i*3+1]=(row[1]-center[1])*scale;positions[i*3+2]=(row[2]-center[2])*scale;});
    mesh.normals.forEach((row,i)=>{normals[i*3]=row[0];normals[i*3+1]=row[1];normals[i*3+2]=row[2];});mesh.texCoords0.forEach((row,i)=>{texCoord0[i*2]=row[0];texCoord0[i*2+1]=row[1];});mesh.texCoords1.forEach((row,i)=>{texCoord1[i*2]=row[0];texCoord1[i*2+1]=row[1];});mesh.colors.forEach((row,i)=>colors.set(row,i*4));
    const indices=new Uint32Array(mesh.triangles.flat()),vao=gl.createVertexArray();gl.bindVertexArray(vao);
    const attribute=(location,size,data)=>{const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,size,gl.FLOAT,false,0,0);resources.push({kind:"buffer",value:buffer});};
    attribute(locations.position,3,positions);attribute(locations.normal,3,normals);attribute(locations.texCoord0,2,texCoord0);attribute(locations.texCoord1,2,texCoord1);attribute(locations.color,4,colors);
    const indexBuffer=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,indexBuffer);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,indices,gl.STATIC_DRAW);resources.push({kind:"vao",value:vao},{kind:"buffer",value:indexBuffer});return{vao,count:indices.length,material:mesh.material};});
  meshes.sort((left,right)=>Number(materialSets[left.material].glass)-Number(materialSets[right.material].glass));
  gl.bindVertexArray(null);gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.useProgram(program);textureUniforms.forEach((location,index)=>gl.uniform1i(location,index));
  let yaw=0,pitch=-.16,zoom=1,dragging=false,lastX=0,lastY=0,disposed=false;
  const draw=()=>{if(disposed)return;const rect=canvas.getBoundingClientRect(),ratio=Math.min(devicePixelRatio||1,2),width=Math.max(1,Math.floor(rect.width*ratio)),height=Math.max(1,Math.floor(rect.height*ratio));if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
    gl.viewport(0,0,width,height);gl.clearColor(.035,.032,.027,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(program);gl.uniform1f(locations.yaw,yaw);gl.uniform1f(locations.pitch,pitch);gl.uniform1f(locations.zoom,zoom);gl.uniform1f(locations.aspect,width/height);
    for(const mesh of meshes){const materialSet=materialSets[mesh.material];materialSet.textures.forEach((texture,index)=>{gl.activeTexture(gl.TEXTURE0+index);gl.bindTexture(gl.TEXTURE_2D,texture);});gl.uniform1f(locations.useAlbedoPalette,materialSet.hasPalette?1:0);gl.uniform1f(locations.materialKind,materialSet.kind);gl.bindVertexArray(mesh.vao);gl.drawElements(gl.TRIANGLES,mesh.count,gl.UNSIGNED_INT,0);}gl.bindVertexArray(null);};
  const reset=()=>{yaw=0;pitch=-.16;zoom=1;draw();},down=event=>{dragging=true;lastX=event.clientX;lastY=event.clientY;canvas.classList.add("dragging");canvas.setPointerCapture(event.pointerId);},move=event=>{if(!dragging)return;yaw+=(event.clientX-lastX)*.012;pitch=Math.max(-1.45,Math.min(1.45,pitch+(event.clientY-lastY)*.012));lastX=event.clientX;lastY=event.clientY;draw();},up=event=>{dragging=false;canvas.classList.remove("dragging");if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);},wheel=event=>{event.preventDefault();zoom=Math.max(.35,Math.min(2.8,zoom*Math.exp(-event.deltaY*.001)));draw();};
  canvas.addEventListener("pointerdown",down);canvas.addEventListener("pointermove",move);canvas.addEventListener("pointerup",up);canvas.addEventListener("pointercancel",up);canvas.addEventListener("wheel",wheel,{passive:false});canvas.addEventListener("dblclick",reset);const observer=new ResizeObserver(draw);observer.observe(canvas);requestAnimationFrame(draw);
  canvas.dataset.meshes=String(geometry.summary.meshes);canvas.dataset.vertices=String(geometry.summary.vertices);canvas.dataset.triangles=String(geometry.summary.triangles);canvas.dataset.material=geometry.materials[0].shader;
  return{reset,draw,state:()=>({yaw,pitch,zoom}),dispose:()=>{disposed=true;observer.disconnect();canvas.removeEventListener("pointerdown",down);canvas.removeEventListener("pointermove",move);canvas.removeEventListener("pointerup",up);canvas.removeEventListener("pointercancel",up);canvas.removeEventListener("wheel",wheel);canvas.removeEventListener("dblclick",reset);for(const resource of resources){if(resource.kind==="vao")gl.deleteVertexArray(resource.value);else if(resource.kind==="texture")gl.deleteTexture(resource.value);else gl.deleteBuffer(resource.value);}gl.deleteProgram(program);}};
}

function itemDescriptionCell(it){
  if(isRO()&&!it.descriptionKey){const area=LexeditorUI.textArea({readonly:"readonly",title:"This catalog record has no description field."});area.value="N/A";return el("div",{},area);}
  const shared=it.descriptionKey&&state.catalog.items.filter(x=>x.descriptionKey===it.descriptionKey).length>1;
  const generatedDescriptionKey=/^0x[0-9a-f]{8}$/i.test(it.key)
    ? `LEX_DESC_${it.key.slice(2).toUpperCase()}`
    : `${it.key}_DESC`;
  const key=state.descriptionKeyEdits[it.key]||(shared?generatedDescriptionKey:it.descriptionKey)||generatedDescriptionKey;
  let editor;
  if(shared&&!state.descriptionKeyEdits[it.key]){
    const attrs={class:"localized-description",placeholder:"No localized description",title:`This text currently shares ${it.descriptionKey}; editing creates the independent key ${key}.`,onchange:ev=>{const value=sanitizeItemDescription(ev.target.value);ev.target.value=value;state.descriptionKeyEdits[it.key]=key;state.localizationEdits[key]=value;ev.target.classList.add("edited");renderToolbarOnly();}};
    if(isRO())attrs.readonly="readonly";editor=LexeditorUI.textArea(attrs);editor.value=localizedValue(it.descriptionKey);
  }else {
    editor=localizationTextarea(key,it.descriptionKey?"No localized description":"Add an in-game description…",value=>{if(!it.descriptionKey||shared){if(value.trim())state.descriptionKeyEdits[it.key]=key;else delete state.descriptionKeyEdits[it.key];}});
    const originalChange=editor.onchange;
    editor.onchange=ev=>{ev.target.value=sanitizeItemDescription(ev.target.value);originalChange(ev);};
  }
  const vanilla=localizedReference(it.descriptionKey||key);
  return el("div", {class:"desc-cell"}, refField(editor, vanilla===undefined?[]:[["V","vtag",vanilla]], localizedValue(key), v=>applyToControl(editor,v), String));
}
