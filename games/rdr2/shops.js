// ----- Shop inventories -----
async function renderShops(){
  if(!dsInfo().catalog)return noData(`This dataset has no catalog_sp.ymt (${dsInfo().dir}).`);
  const st=refStore(state.ds);if(!st.shops)st.shops=await api("/api/shops");state.shops=st.shops;
  if(state.ds==="mine"&&(!state.shopBuyers||!state.shopBuyers.available))state.shopBuyers=await api("/api/shop-buyers");
  if(state.ds==="mine")for(const ds of ["vanilla","kiddos"]){const rs=refStore(ds);if(state.config.datasets[ds].catalog&&!rs.shops)rs.shops=await api("/api/shops",undefined,ds);}
  const f=state.filters,tb=$("#toolbar"),m=$("#main");tb.innerHTML="";
  const shops=[...st.shops.shops].sort((a,b)=>shopLabel(a.type).localeCompare(shopLabel(b.type)));
  const shopTypes=[...new Set([...shops.map(shop=>shop.type),...(state.shopBuyers?.shops||[])])]
    .sort((a,b)=>shopLabel(a).localeCompare(shopLabel(b)));
  if(!shopTypes.includes(f.shopType))f.shopType=shopTypes.includes("ST_GENERAL")?"ST_GENERAL":shopTypes[0]||"";
  if(f.shopMode==="report"){
    if(!state.shopAcceptance)state.shopAcceptance=await api("/api/shops/acceptance");
    tb.append(el("button",{onclick:()=>{f.shopMode="workspace";render();}},el("span",{class:"lex-ui-symbol"},"‹")," BACK TO SHOPS"),
      el("button",{class:"active",disabled:true},"ACCEPTANCE REPORT"));
    m.innerHTML="";
    renderShopAcceptanceReport(m);
    refreshGlobalSave();return;
  }
  const previous={buys:document.querySelector(".shop-panel-buys .shop-ledger-list")?.scrollTop||0,
    shops:document.querySelector(".shop-picker-list")?.scrollTop||0,
    sells:document.querySelector(".shop-panel-sells .shop-ledger-list")?.scrollTop||0};
  const buyQ=(f.shopBuyQ||"").trim().toUpperCase(),sellQ=(f.shopSellQ||"").trim().toUpperCase();
  const selected=shops.find(shop=>shop.type===f.shopType)||null;
  tb.append(el("button",{class:"acceptance-report",title:"Shows the saved effective acceptance report. Save pending shop changes first.",onclick:()=>{f.shopMode="report";render();}},"ACCEPTANCE REPORT"),
    savebar(saveShopTab));
  m.innerHTML="";
  const buys=renderShopLedger("buys",f.shopType,selected,buyQ);
  const picker=renderShopPicker(shopTypes,shops,f.shopType);
  const sells=renderShopLedger("sells",f.shopType,selected,sellQ);
  m.append(LexeditorUI.panelLayout([buys,picker,sells],"shop-workspace",{
    layoutKey:"rdr2-shops",defaultSizes:[1,.5,1],minSizes:[330,190,330]}));
  buys.querySelector(".shop-ledger-list").scrollTop=previous.buys;
  picker.querySelector(".shop-picker-list").scrollTop=previous.shops;
  sells.querySelector(".shop-ledger-list").scrollTop=previous.sells;
  refreshGlobalSave();
}

function shopBuyState(shopType,it){
  if(!state.shopBuyers?.available||!state.shopBuyers.shops?.includes(shopType))
    return {active:false,kind:"unavailable",mode:"default",title:"No captured buyer data exists for this shop type."};
  const mode=merchantOverride(shopType,it.key);
  if(mode==="accept")return {active:true,kind:"accept",mode,title:"Explicit Accept override. Click to Reject; right-click to return to Vanilla."};
  if(mode==="reject")return {active:false,kind:"reject",mode,title:"Explicit Reject override. Click to Accept; right-click to return to Vanilla."};
  const listed=!!state.shopBuyers.vanillaBuyers?.[shopType]?.includes(it.key);
  return listed
    ?{active:true,kind:"listed",mode,title:"Rockstar's sparse buyer PDATA explicitly lists this item. Click to Reject; right-click to restore Vanilla."}
    :{active:false,kind:"unknown",mode,title:"Not explicitly listed. Rockstar's compiled category rule remains unknown. Click to force Accept; right-click keeps Vanilla."};
}

function stageMerchantOverride(shop,item,mode){
  const base=state.shopBuyers?.overrides?.[shop]?.[item]??"default",key=`${shop}|${item}`;
  if(mode===base)delete state.shopBuyerDirty[key];else state.shopBuyerDirty[key]=mode;
  state.shopAcceptance=null;
}

function ensureShopPanelPrice(it,section){
  if(cashOf(it,section)!==null)return;
  if(section==="buy")state.buyabilityEdits[it.key]={buyable:true,cents:100};
  else {state.sellabilityEdits[it.key]={sellable:true,cents:100};state.shopAcceptance=null;}
}

function toggleShopBuy(shopType,it,status){
  if(status.kind==="unavailable"||isRO())return;
  const mode=status.active?"reject":"accept";
  stageMerchantOverride(shopType,it.key,mode);
  if(mode==="accept")ensureShopPanelPrice(it,"sell");
  refreshGlobalSave();renderShops();
}

function resetShopBuy(shopType,it){
  if(isRO())return;
  stageMerchantOverride(shopType,it.key,"default");
  refreshGlobalSave();renderShops();
}

function stageShopSellAddition(shop,it,plan){
  ensureShopPanelPrice(it,"buy");
  const row=newShopListing(it.key,plan);
  shop.items.push(row);state.shopDirty.add(shop.type);
  $("#picker").classList.add("hidden");refreshGlobalSave();renderShops();
}

function showShopCatalogueDestination(shop,it,plan){
  const backdrop=$("#picker");backdrop.innerHTML="";backdrop.classList.remove("hidden");
  const options=el("div",{class:"shop-category-options"});
  for(const category of plan.categories||[]){
    const layouts=[...new Set((category.pages||[]).map(page=>page.layout))];
    const occupancy=(category.pages||[]).map(page=>`${page.occupancy}/${page.capacity??"?"}`).join(" · ")||"no pages yet";
    options.append(el("button",{class:"shop-category-option",onclick:async()=>{
      try{
        const selected=await api(`/api/shops/catalogue-placement?item=${encodeURIComponent(it.key)}&shop=${encodeURIComponent(shop.type)}&category=${encodeURIComponent(category.key)}`);
        stageShopSellAddition(shop,it,selected);
      }catch(error){toast(error.message,true);}
    }},el("b",{},category.path.join(" › ")),el("span",{},`PAGE LAYOUT ${layouts.join(", ")||"from proved item page"}`),
      el("span",{},`PAGE OCCUPANCY ${occupancy}`)));
  }
  const panel=el("div",{class:"picker-panel shop-catalogue-destination"},
    el("div",{class:"head"},el("b",{},"CATALOGUE DESTINATION"),el("span",{class:"cat",style:"margin-left:auto"},shopLabel(shop.type))),
    el("div",{class:"hint"},plan.reason),options,
    ...(options.children.length?[]:[el("div",{class:"hint"},"This shop has no printed catalogue category, so Lexeditor cannot stage the listing.")]),
    el("div",{class:"dialog-actions"},el("button",{onclick:()=>backdrop.classList.add("hidden")},"CANCEL")));
  backdrop.append(panel);
}

async function toggleShopSell(shop,it,enabled){
  if(!shop||isRO())return;
  if(enabled){setShopListing(shop,it.key,false);return;}
  try{
    const plan=await api(`/api/shops/catalogue-placement?item=${encodeURIComponent(it.key)}&shop=${encodeURIComponent(shop.type)}`);
    if(plan.requiresDestination)showShopCatalogueDestination(shop,it,plan);
    else stageShopSellAddition(shop,it,plan);
  }catch(error){toast(error.message,true);}
}

function shopPanelPrice(it,section,active){
  const value=cashOf(it,section),parts=cashParts(it[section],section),attrs={type:"number",step:"0.01",min:"0",
    value:value===null?"":fmtMoney(value),placeholder:"N/A",title:`Global ${section==="sell"?"sell":"buy"} price for ${it.key}`};
  if(isRO())attrs.readonly="readonly";
  if(!active)attrs.disabled=true;
  if(active&&!isRO())attrs.onchange=ev=>{
    const cents=Math.max(0,Math.round((parseFloat(ev.target.value)||0)*100));
    let edited=true;
    if(parts.length){
      const [cost,part]=parts[0],editKey=`${it.key}|${section}|${cost.key}|${part.item}`;
      if(cents===part.qty)delete state.priceEdits[editKey];else state.priceEdits[editKey]=cents;
      edited=editKey in state.priceEdits;
    }else if(section==="buy")state.buyabilityEdits[it.key]={buyable:true,cents};
    else {state.sellabilityEdits[it.key]={sellable:true,cents};state.shopAcceptance=null;}
    if(section==="sell")state.shopAcceptance=null;
    ev.target.classList.toggle("edited",edited);refreshGlobalSave();
  };
  return el("span",{class:"money"},el("input",attrs));
}

function shopRequirementText(requirement){
  return `${requirement.type||"Unresolved type"}: ${requirement.key||"Unresolved key"}${requirement.state?` = ${requirement.state}`:""}${requirement.lock?` · lock ${requirement.lock}`:""}`;
}

function shopRequirementGroups(row){
  if(Array.isArray(row?.requirementGroups))return row.requirementGroups;
  return row?.requirements?.length?[{count:"1",requirements:row.requirements}]:[];
}

function shopRequirementCount(row){
  return shopRequirementGroups(row).reduce((total,group)=>total+(group.requirements||[]).length,0);
}

function shopRequirementOptions(){
  const types=new Set(),keys=new Set();
  for(const shop of state.shops?.shops||[])for(const row of shop.items||[])for(const group of shopRequirementGroups(row))
    for(const requirement of group.requirements||[]){if(requirement.type)types.add(requirement.type);if(requirement.key)keys.add(requirement.key);}
  return {types:[...types].sort(),keys:[...keys].sort()};
}

function normalizeShopRequirementDraft(groups){
  return groups.map(group=>({count:String(group.count??"1").trim(),requirements:(group.requirements||[]).map(requirement=>({
    type:String(requirement.type||"").trim(),key:String(requirement.key||"").trim(),state:String(requirement.state??"1").trim(),
    lock:String(requirement.lock??"false").trim().toLowerCase()}))}));
}

function validateShopRequirementDraft(groups){
  for(let groupIndex=0;groupIndex<groups.length;groupIndex++){
    const group=groups[groupIndex];
    if(!/^-?\d+$/.test(String(group.count??"")))return `Group ${groupIndex+1}: count must be a whole number.`;
    for(let requirementIndex=0;requirementIndex<(group.requirements||[]).length;requirementIndex++){
      const requirement=group.requirements[requirementIndex],prefix=`Group ${groupIndex+1}, condition ${requirementIndex+1}`;
      if(!requirement.type||!requirement.key)return `${prefix}: type and key are required.`;
      if(!/^-?\d+$/.test(String(requirement.state??"")))return `${prefix}: state must be a whole number.`;
      if(!["true","false"].includes(String(requirement.lock)))return `${prefix}: lock must be true or false.`;
    }
  }
  return "";
}

function showShopRequirements(shop,row,it){
  const backdrop=$("#picker"),readonly=isRO(),draft=JSON.parse(JSON.stringify(shopRequirementGroups(row))),options=shopRequirementOptions();
  const renderEditor=()=>{
    backdrop.innerHTML="";backdrop.classList.remove("hidden");
    const typeList=`shop-condition-types-${Date.now()}`,keyList=`shop-condition-keys-${Date.now()}`;
    const panel=el("div",{class:"picker-panel shop-requirement-editor"},el("div",{class:"head"},
      el("b",{},localizedValue(it.nameKey)||it.key),el("span",{class:"cat",style:"margin-left:auto"},`${shopLabel(shop.type)} · AVAILABILITY`)),
      el("div",{class:"hint"},"Each card is one real requirement group. Count is the group's stored threshold. Conditions inside a group keep their exact type, key, state, and lock fields; Lexeditor does not invent AND/OR meaning."),
      el("datalist",{id:typeList},...options.types.map(value=>el("option",{value}))),
      el("datalist",{id:keyList},...options.keys.map(value=>el("option",{value}))));
    const grid=el("div",{class:"shop-requirement-grid"});
    draft.forEach((group,groupIndex)=>{
      const card=el("section",{class:"shop-requirement-card"},el("div",{class:"shop-requirement-group-head"},
        el("b",{},`GROUP ${groupIndex+1}`),el("label",{},"COUNT",el("input",{type:"number",step:"1",value:group.count??"1",disabled:readonly,
          oninput:ev=>group.count=ev.target.value})),el("span"),
        el("button",{class:"del",disabled:readonly,title:"Remove this requirement group",onclick:()=>{draft.splice(groupIndex,1);renderEditor();}},"×")));
      (group.requirements||[]).forEach((requirement,requirementIndex)=>card.append(el("div",{class:"shop-requirement-row"},
        el("label",{},"TYPE",el("input",{list:typeList,value:requirement.type||"",disabled:readonly,oninput:ev=>requirement.type=ev.target.value})),
        el("label",{},"KEY",el("input",{list:keyList,value:requirement.key||"",disabled:readonly,oninput:ev=>requirement.key=ev.target.value})),
        el("label",{},"STATE",el("input",{type:"number",step:"1",value:requirement.state??"1",disabled:readonly,oninput:ev=>requirement.state=ev.target.value})),
        el("label",{},"LOCK",el("select",{disabled:readonly,onchange:ev=>requirement.lock=ev.target.value},
          ...["false","true"].map(value=>el("option",{value,selected:String(requirement.lock)===value},value.toUpperCase())))),
        el("button",{class:"del",disabled:readonly,title:"Remove this condition",onclick:()=>{group.requirements.splice(requirementIndex,1);renderEditor();}},"×"))));
      card.append(newButton({disabled:readonly,title:"Add condition",onclick:()=>{group.requirements.push({type:"",key:"",state:"1",lock:"false"});renderEditor();}}));
      grid.append(card);
    });
    if(!draft.length)grid.append(el("div",{class:"hint"},"No requirement groups. This listing is always available in this shop."));
    panel.append(grid,el("div",{class:"shop-requirement-actions"},
      newButton({disabled:readonly,title:"Add condition group",onclick:()=>{draft.push({count:"1",requirements:[]});renderEditor();}}),
      el("span"),el("button",{onclick:()=>backdrop.classList.add("hidden")},readonly?"CLOSE":"CANCEL"),
      readonly?null:el("button",{class:"active",onclick:()=>{
        const cleaned=normalizeShopRequirementDraft(draft),error=validateShopRequirementDraft(cleaned);
        if(error){toast(error,true);return;}
        row.requirementGroups=cleaned;row.requirements=cleaned.flatMap(group=>group.requirements);
        state.shopDirty.add(shop.type);backdrop.classList.add("hidden");refreshGlobalSave();renderShops();
      }},"APPLY")));
    backdrop.append(panel);
  };
  renderEditor();
}

function shopRowIdentity(it){
  const name=localizedValue(it.nameKey);return itemLink(it.key,true,el("div",{class:"shop-item-name",title:`${it.key}${name?" — "+name:""}`},
    el("span",{class:"k"},originDisplayName(name||it.key,it)),name?el("span",{class:"li-name"},it.key):""));
}

function shopConditionCell(shop,listing,it){
  if(!shop||!listing)return el("div",{class:"shop-item-conditions"},el("span",{class:"muted"},"—"));
  const groups=shopRequirementGroups(listing),conditions=shopRequirementCount(listing);
  const title=conditions?groups.map((group,index)=>`Group ${index+1} · count ${group.count}:\n${(group.requirements||[]).map(shopRequirementText).join("\n")||"No conditions"}`).join("\n\n"):
    "No conditions; always available in this inventory.";
  const label=conditions?`${conditions} CONDITION${conditions===1?"":"S"}`:"ALWAYS";
  return el("div",{class:"shop-item-conditions"},el("button",{class:`shop-condition-link${conditions?"":" always"}`,title,
    onclick:ev=>{ev.stopPropagation();showShopRequirements(shop,listing,it);}},label));
}

function shopCatalogueMenuLabel(key){
  const resolved=humanName("catalogueMenus",key)||key||"Unresolved";
  if(/^0x[0-9a-f]{8}$/i.test(resolved))return resolved.toUpperCase();
  const cleaned=resolved.replace(/^(?:GENERAL_MENU_|TAILOR_MENU_|MENU_)/i,"")
    .replace(/_(?:STYLE_SELECTOR|SELECTOR|MENU)$/i,"").replaceAll("_"," ").trim();
  return (cleaned||resolved).toLowerCase().replace(/\b\w/g,letter=>letter.toUpperCase());
}

function shopCatalogueMenuId(key){return shopCatalogueMenuLabel(key).toUpperCase();}

function shopCatalogueFilterModel(shop){
  const rawPaths=(shop?.catalogueCategories||[]).map(category=>category.path||[]).filter(path=>path.length);
  if(!rawPaths.length)return {prefix:0,top:[],second:[],topSelected:"",secondSelected:""};
  const minDepth=Math.min(...rawPaths.map(path=>path.length));
  let prefix=0;
  while(prefix<minDepth-1&&rawPaths.every(path=>String(path[prefix]).toUpperCase()===String(rawPaths[0][prefix]).toUpperCase()))prefix++;
  const paths=rawPaths.map(path=>path.slice(prefix)),topById=new Map();
  paths.forEach(path=>{const id=shopCatalogueMenuId(path[0]);if(!topById.has(id))topById.set(id,{id,label:shopCatalogueMenuLabel(path[0])});});
  const top=[...topById.values()].sort((a,b)=>a.label.localeCompare(b.label));
  if(!topById.has(state.filters.shopSellCategory))state.filters.shopSellCategory="";
  const topSelected=state.filters.shopSellCategory,secondById=new Map();
  if(topSelected)paths.filter(path=>shopCatalogueMenuId(path[0])===topSelected&&path.length>1).forEach(path=>{
    const id=shopCatalogueMenuId(path[1]);if(!secondById.has(id))secondById.set(id,{id,label:shopCatalogueMenuLabel(path[1])});
  });
  const second=[...secondById.values()].sort((a,b)=>a.label.localeCompare(b.label));
  if(!secondById.has(state.filters.shopSellSubcategory))state.filters.shopSellSubcategory="";
  return {prefix,top,second,topSelected,secondSelected:state.filters.shopSellSubcategory};
}

function shopCatalogueFilterTabs(model){
  if(!model.top.length)return [];
  const topCount=model.top.length+1;
  const top=el("div",{class:"shop-catalogue-tabs",style:`--shop-tab-count:${topCount}`,
    "aria-label":"Catalogue categories"},
    el("button",{class:model.topSelected?"":"active","data-catalogue-category":"all",onclick:()=>{
      state.filters.shopSellCategory="";state.filters.shopSellSubcategory="";renderShops();
    }},"All"),...model.top.map(category=>el("button",{class:model.topSelected===category.id?"active":"",
      "data-catalogue-category":category.id,onclick:()=>{state.filters.shopSellCategory=category.id;
        state.filters.shopSellSubcategory="";renderShops();}},category.label)));
  if(!model.topSelected||!model.second.length)return [top];
  const secondCount=model.second.length+1;
  const second=el("div",{class:"shop-catalogue-tabs secondary",style:`--shop-tab-count:${secondCount}`,
    "aria-label":"Catalogue subcategories"},
    el("button",{class:model.secondSelected?"":"active","data-catalogue-subcategory":"all",onclick:()=>{
      state.filters.shopSellSubcategory="";renderShops();
    }},"All"),...model.second.map(category=>el("button",{class:model.secondSelected===category.id?"active":"",
      "data-catalogue-subcategory":category.id,onclick:()=>{state.filters.shopSellSubcategory=category.id;renderShops();}},category.label)));
  return [top,second];
}

function shopListingMatchesCatalogueFilter(listing,model){
  if(!model.topSelected)return true;
  return (listing?.cataloguePages||[]).some(page=>{
    const path=(page.categoryPath||[]).slice(model.prefix);
    return shopCatalogueMenuId(path[0])===model.topSelected&&
      (!model.secondSelected||shopCatalogueMenuId(path[1])===model.secondSelected);
  });
}

function shopAvailabilityButton(side,shopType,shop,it,status){
  const available=status.active,disabled=isRO()||(side==="buys"?status.kind==="unavailable":!shop);
  const title=side==="buys"?status.title:(shop
    ?available?`Listed in ${shopLabel(shopType)}. Click to remove it from this shop.`:`Not listed in ${shopLabel(shopType)}. Click to add it to this shop.`
    :"This shop type has no catalog inventory container.");
  const attrs={class:`shop-availability ${available?"on":status.kind==="unknown"?"unknown":"off"}`,title,
    "aria-label":title,disabled,onclick:ev=>{ev.stopPropagation();if(side==="buys")toggleShopBuy(shopType,it,status);else toggleShopSell(shop,it,available);}};
  if(side==="buys")attrs.oncontextmenu=ev=>{ev.preventDefault();ev.stopPropagation();resetShopBuy(shopType,it);};
  return el("button",attrs,available?"✓":"×");
}

function renderShopLedger(side,shopType,shop,q){
  const buying=side==="buys",catalogueFilter=buying?null:shopCatalogueFilterModel(shop);
  let rows=state.catalog.items.map(it=>{
    const listing=shop&&shopListing(shop,it.key),status=buying?shopBuyState(shopType,it):{active:!!listing,kind:listing?"listed":"absent"};
    return {it,listing,status};
  }).filter(row=>(!q||itemSearchText(row.it).includes(q))&&
    (buying||shopListingMatchesCatalogueFilter(row.listing,catalogueFilter)))
    .filter(row=>q||row.status.active||(buying&&row.status.kind==="reject"));
  rows.sort((a,b)=>(localizedValue(a.it.nameKey)||a.it.key).localeCompare(localizedValue(b.it.nameKey)||b.it.key));
  const total=rows.length,shown=rows.slice(0,600),title=buying?"BUYS":"SELLS";
  const header=buying
    ?el("div",{class:"shop-ledger-head"},el("span"),el("span",{},"Item"),el("span",{},"Price"),el("span"))
    :el("div",{class:"shop-ledger-head"},el("span"),el("span",{},"Item"),el("span",{},"Availability"),el("span",{},"Price"),el("span"));
  const list=LexeditorUI.list({rows:shown,key:row=>row.it.key,selected:null,class:"shop-ledger-list",
    header,rowClass:row=>`shop-ledger-row${row.status.active?"":" inactive"}`,select:()=>{},render:row=>[
      el("button",{class:"shop-item-jump",title:`Open ${localizedValue(row.it.nameKey)||row.it.key} in Items`,
        onclick:ev=>{ev.stopPropagation();goToItem(row.it.key);}},"🔍"),
      shopRowIdentity(row.it),
      buying?null:shopConditionCell(shop,row.listing,row.it),
      el("div",{class:"shop-item-price"},shopPanelPrice(row.it,buying?"sell":"buy",row.status.active)),
      shopAvailabilityButton(side,shopType,shop,row.it,row.status)]});
  const subtitle=buying
    ?"We can't see the actual state of each item's sellability but we can change it, so what you see here are custom overrides. Left-click to toggle, right-click to clear."
    :shop?`${total}${total>600?"+":""} matching stock listings · catalogue tabs filter the printed categories; availability remains editable per listing.`:"No catalog inventory exists for this shop type.";
  const filterKey=buying?"shopBuyQ":"shopSellQ",searchLabel=buying?"BUYS":"SELLS";
  const search=rdrSearchField({id:`shop-${side}-search`,className:"shop-panel-search",
    placeholder:`Search ${searchLabel}…`,label:`Search ${searchLabel}`,value:state.filters[filterKey]||"",
    oninput:ev=>{state.filters[filterKey]=ev.target.value;state.filters.shopExact="";filterRerender(ev,renderShops);}});
  return el("section",{class:`shop-panel shop-panel-${side}`},el("div",{class:"shop-panel-head"},
    el("h2",{class:"shop-panel-title"},title),search,el("div",{class:"shop-panel-subtitle"},subtitle)),
    ...(buying?[]:shopCatalogueFilterTabs(catalogueFilter)),list);
}

function renderShopPicker(shopTypes,shops,selected){
  const rows=shopTypes.map(type=>({type,shop:shops.find(shop=>shop.type===type)||null}));
  const list=LexeditorUI.list({rows,key:row=>row.type,selected,selectedClass:"sel",class:"shop-picker-list",
    header:el("div",{class:"shop-picker-head"},el("div",{class:"shop-picker-title"},
      el("span",{class:"shop-picker-total"},String(shopTypes.length))," SHOPS")),
    rowClass:"shop-picker-row",select:row=>{state.filters.shopType=row.type;state.filters.shopSellCategory="";
      state.filters.shopSellSubcategory="";renderShops();},render:row=>{
      const explicit=state.catalog.items.reduce((count,it)=>count+(shopBuyState(row.type,it).active?1:0),0);
      return el("div",{},el("span",{class:"shop-name"},shopLabel(row.type)),
        el("span",{class:"shop-counts"},`${explicit}+ buys · ${row.shop?.items.length||0} sells`));
    }});
  return el("section",{class:"shop-panel shop-panel-picker"},list);
}

const ACCEPTANCE_COLS=[
  ["EXPLICIT_ACCEPT","Explicitly listed","This shop's exception list names the item and the catalog prices it."],
  ["LISTED_NO_PRICE","Listed, but no price","CONFLICT: the shop list names it, the catalog gives it no sell price. Unresolved — do not assume either side wins."],
  ["BLOCKED","Blocked by us","Our reject override greys the Sell action for this merchant."],
  ["UNSELLABLE","No sell price anywhere","No SELL_SHOP_DEFAULT on the catalog item."],
  ["ENGINE_DEFAULT_UNKNOWN","Unknown","Decided by Rockstar's compiled shop category rules. Not readable from any file or script. This is NOT a refusal."],
];

function renderShopAcceptanceReport(m){
  const a=state.shopAcceptance;
  if(!a||!a.available)return m.append(el("div",{class:"hint"},a?.reason||"No merchant baseline captured yet."));
  if(dirtyCount())m.append(el("div",{class:"hint"},el("b",{},"Unsaved shop changes are not in this report. "),"Return to Shops, save them, and reopen the report."));
  m.append(el("div",{class:"hint"},el("b",{},"What this is: "),
    "each shop's real, effective acceptance rules — the four things we can actually prove, and one honest unknown. ",
    el("b",{},"The unknown column is the normal case and does not mean “no”. "),
    "Rockstar decides ordinary acceptance in compiled shop category rules that appear in no data file and in no script. ",
    "The exception list is a sparse permit list, not a whitelist: only 5 of 20 shops carry any entries at all, and the ",
    "trapper's list holds no pelts and no carcasses even though he plainly buys both."));
  const table=columnList({class:"shop-table shop-acceptance-table","aria-label":"Shop acceptance",
    rows:a.shops.map(shop=>({shop,counts:a.summary[shop]||{}})),key:row=>row.shop,
    template:`31% repeat(${ACCEPTANCE_COLS.length},minmax(0,1fr))`,
    columns:[{key:"shop",label:"Shop",render:row=>shopLabel(row.shop)},
      ...ACCEPTANCE_COLS.map(([key,label,tip])=>({key,label:()=>el("span",{title:tip},label),
        sortValue:row=>Number(row.counts[key]||0),
        cellClass:row=>row.counts[key]?"":"muted",
        render:row=>String(row.counts[key]||0)}))]});
  m.append(table);
  const conflicts=a.rows.filter(r=>r.verdict==="LISTED_NO_PRICE");
  if(conflicts.length){
    m.append(el("div",{class:"hint",style:"margin-top:18px"},el("b",{},`${conflicts.length} conflicts: `),
      "listed by the shop, but the catalog gives no sell price. These do change hands in game, so “no price” cannot be assumed to win."));
    m.append(columnList({class:"shop-table","aria-label":"Listed with no catalog price",
      rows:conflicts.slice(0,300),key:(r,index)=>`${r.shop}:${r.item}:${index}`,
      template:"31% minmax(0,1fr) minmax(0,1fr)",
      columns:[{key:"shop",label:"Shop",render:r=>shopLink(r.shop)},
        {key:"item",label:"Item",render:r=>itemLink(r.item)},
        {key:"source",label:"Source"}]}));
    if(conflicts.length>300)m.append(el("div",{class:"hint"},`Showing 300 of ${conflicts.length}.`));
  }
  const stray=Object.entries(a.unresolvedListed||{}).filter(([,v])=>v.length);
  if(stray.length){
    m.append(el("div",{class:"hint",style:"margin-top:18px"},el("b",{},"Listed but not in the catalog at all: "),
      "these tokens sit in a shop's buyer list with no catalog record behind them. Either dead references or items created elsewhere."));
    m.append(columnList({class:"shop-table","aria-label":"Listed but not in the catalog",
      rows:stray.map(([shop,list])=>({shop,tokens:list.join(", ")})),key:row=>row.shop,
      template:"31% minmax(0,1fr)",
      columns:[{key:"shop",label:"Shop",render:row=>shopLabel(row.shop)},
        {key:"tokens",label:"Tokens"}]}));
  }
}

function renderShopItemPicker(items,m){
  const rows=sortedRows("shops-picker",items,{name:it=>localizedValue(it.nameKey)||it.key});
  $("#toolbar").insertBefore(el("span",{class:"count"},`${rows.length} matching items${rows.length>200?" (showing 200)":""}`),$("#toolbar").lastChild);
  m.append(columnList({class:"shop-table","aria-label":"Matching items",
    rows:rows.slice(0,200),key:it=>it.key,template:"minmax(0,1fr)",
    columns:[{key:"name",label:"Item",sortValue:it=>localizedValue(it.nameKey)||it.key,
      render:it=>el("span",{},el("button",{class:"table-link",onclick:()=>{state.filters.shopExact=it.key;state.filters.shopBuyQ=it.key;state.filters.shopSellQ=it.key;renderShops();}},
        localizedValue(it.nameKey)||"No localized name"),itemLink(it.key))}]}));
}

const NAME_CELL_FOR=it=>el("span",{},el("span",{class:"record-name"},originDisplayName(localizedValue(it.nameKey)||"No localized name",it)),itemLink(it.key,false));
function shopListing(shop,item){return shop.items.find(row=>row.item===item);}
function newShopListing(item,placement=null){
  const destination=placement?.destination;
  const cataloguePages=destination?[{...destination,page:destination.page||"NEW PAGE",
    occupancy:destination.occupancy+(placement.source?1:0)}]:[];
  return {item,requirementGroups:[],requirements:[],cataloguePages,
    catalogueCategory:destination?.category||null};
}
function shopSaveEdit(type){
  const shop=state.shops.shops.find(candidate=>candidate.type===type);
  return {type,items:shop.items.map(row=>({item:row.item,requirementGroups:shopRequirementGroups(row),
    ...(row.catalogueCategory?{catalogueCategory:row.catalogueCategory}:{})}))};
}
function setShopListing(shop,item,enabled){
  const row=shopListing(shop,item);
  if(enabled&&!row)shop.items.push(newShopListing(item));
  if(!enabled&&row)shop.items.splice(shop.items.indexOf(row),1);
  state.shopDirty.add(shop.type);refreshGlobalSave();renderShops();
}
function renderShopMatrix(it,shops,m,mode){
  const selling=mode==="buy";
  m.append(columnList({class:"shop-table shop-item-summary","aria-label":"Item prices",
    rows:[it],key:row=>row.key,localSort:false,
    template:`31% minmax(0,1fr)${selling?" minmax(0,1fr)":""}`,
    columns:[{key:"item",label:"Item",render:row=>el("span",{},
        el("span",{class:"record-name"},originDisplayName(localizedValue(row.nameKey)||"No localized name",row)),
        itemLink(row.key,false))},
      {key:"price",label:selling?"Global buy price":"Global sell price",
        render:row=>selling?buyPriceCell(row,cashParts(row.buy,"buy"),shopPriceRef(row,"buy"))
          :sellPriceCell(row,cashParts(row.sell,"sell"),shopPriceRef(row,"sell"))},
      ...(selling?[{key:"yield",label:"Purchase output",render:row=>purchaseQuantityCell(row)}]:[])]}));
  const allTypes=[...new Set([...(selling?shops.map(s=>s.type):[]),...(state.shopBuyers?.shops||[])])].sort((a,b)=>shopLabel(a).localeCompare(shopLabel(b)));
  const shopFor=type=>shops.find(s=>s.type===type);
  const listingFor=type=>{const shop=shopFor(type);return shop&&shopListing(shop,it.key);};
  const buyerRule=cashOf(it,"sell")===null
    ? "No — no SELL_SHOP_DEFAULT payout"
    : "Unknown — Rockstar keeps this shop's category filter in compiled script";
  m.append(columnList({class:"shop-table shop-matrix","aria-label":"Shops",
    rows:allTypes.map(type=>({type})),key:row=>row.type,editable:true,localSort:false,
    template:"31% minmax(0,1fr) minmax(0,1fr)",
    columns:[{key:"shop",label:"Shop",render:row=>shopLabel(row.type)},
      {key:"rule",label:selling?"Requirements":"Vanilla behavior",cellClass:"requirements",
        render:row=>{const listing=listingFor(row.type);
          if(!selling)return buyerRule+(merchantAccepted(row.type,it.key)?"; explicit PDATA row present":"");
          if(listing?.requirements?.length)return listing.requirements.map(r=>`${r.type}: ${r.key}${r.state?` = ${r.state}`:""}`).join(" · ");
          return listing?"Always available":"—";}},
      {key:"state",label:selling?"Sells":"Buy override",
        render:row=>{
          if(selling)return el("input",{type:"checkbox",checked:!!listingFor(row.type),
            title:"Include this item in this shop's stock",
            onchange:ev=>setShopListing(shopFor(row.type),it.key,ev.target.checked)});
          const override=merchantOverride(row.type,it.key);
          return el("select",{title:"Vanilla keeps Rockstar's compiled category decision; Accept and Reject explicitly override it.",
            onchange:ev=>setMerchantOverride(row.type,it.key,ev.target.value)},
            ...[["default","Vanilla"],["accept","Accept"],["reject","Reject"]].map(([value,label])=>
              el("option",{value,...(override===value?{selected:true}:{})},label)));}}]}));
  if(!selling)m.append(el("div",{class:"hint"},el("b",{},"Merchant overrides: "),"Vanilla preserves Rockstar's category decision. Accept adds a PDATA exception; Reject greys the Sell action when that item is selected in this merchant's satchel."));
}

const SHOP_LABELS={ST_TAILOR:"Tailor",ST_NEWSPAPER_BOY:"Newspaper seller",ST_CLOTHING:"Clothing catalog",ST_BUTCHER:"Butcher",ST_HANDHELD:"Handheld catalog",ST_TRAPPER:"Trapper",ST_TRAIN_STATION:"Train station",ST_CAMP_SHAVING:"Camp shaving",ST_GENERAL:"General store",ST_BARBER:"Barber",ST_MARKET:"Market",ST_FENCE:"Fence",ST_FRENCH_MARKET:"French Market",ST_HORSE_SHOP:"Stable / horse shop",ST_HORSE_TRAINER:"Horse trainer",ST_HAIR:"Hair services",ST_EXOTIC:"Exotics",ST_QUARTERMASTER:"Quartermaster",ST_DOCTOR:"Doctor",ST_PEARSON:"Pearson",ST_WEAPON_MOD_STORE:"Weapon customization",ST_BAIT:"Bait shop",ST_GUNSMITH:"Gunsmith","0xC314BB67":"Unresolved catalog shop 0xC314BB67"};
const shopLabel=type=>SHOP_LABELS[type]||`Unresolved shop type ${type}`;
const itemSearchText=it=>`${localizedValue(it?.nameKey)} ${it?.key||""}`.toUpperCase();
function addItemToShop(shop,itemKey){
  if(!shop||shop.items.some(row=>row.item===itemKey))return;
  shop.items.push(newShopListing(itemKey));
  state.shopDirty.add(shop.type);
  renderShops();
}
function pickShopForItem(it,shops){
  const available=shops.filter(shop=>!shop.items.some(row=>row.item===it.key));
  if(!available.length){toast("This item is already listed in every shop type");return;}
  const labels=available.map(shop=>`${shopLabel(shop.type)} - ${shop.type}`);
  pickIdentifier(`Shop for ${localizedValue(it.nameKey)||it.key}`,labels,"",picked=>{
    const index=labels.indexOf(picked);
    if(index>=0)addItemToShop(available[index],it.key);
  });
}
function shopPriceRef(it,section){const v=refItem("vanilla",it.key),k=refItem("kiddos",it.key),p=refItem("prices1899",it.key);return refStack([["V","vtag",cashOf(v,section)],["K","ktag",cashOf(k,section)],["1899","p1899tag",cashOf(p,section)]],section==="buy"?it.buy:it.sell,(x,e)=>applyToInput(e,fmtMoney(x)),x=>"$"+fmtMoney(x));}
function shopItemMatches(it,q){return state.filters.shopExact?it?.key===state.filters.shopExact:(!q||itemSearchText(it).includes(q));}
function renderShopInventory(shop,q,m){
  if(!shop)return;
  let rows=shop.items.map(row=>({row,it:state.catalog.items.find(i=>i.key===row.item)})).filter(x=>shopItemMatches(x.it,q));
  rows=sortedRows("shops-buy",rows,{name:x=>localizedValue(x.it?.nameKey)||x.row.item,price:x=>cashOf(x.it,"buy")??Infinity,qty:x=>effectivePurchaseYieldOf(x.it),requirements:x=>x.row.requirements.map(r=>`${r.type}:${r.key}:${r.state}`).join("|")});
  $("#toolbar").insertBefore(el("span",{class:"count"},`${rows.length} of ${shop.items.length} listings`),$("#toolbar").lastChild);
  const exact=state.catalog.items.find(it=>it.key.toUpperCase()===q);
  const soldBy=exact?state.shops.shops.filter(candidate=>candidate.items.some(row=>row.item===exact.key)):[];
  if(exact)m.append(el("div",{class:"hint"},el("b",{},"Sold by: "),...soldBy.length?soldBy.map((candidate,index)=>shopLink(candidate.type,`${index?" · ":""}${shopLabel(candidate.type)}`)):["no standard shop inventory"]));
  m.append(el("div",{class:"hint"},el("b",{},`${shopLabel(shop.type)}: `),"each row is something this shop can sell to the player. Price and purchase output are global catalog values shared by every shop; requirements belong to this listing only."));
  const table=columnList({class:"shop-table","aria-label":"Shop inventory",
    rows:rows.slice(0,600).filter(entry=>entry.it),key:({row})=>row.item,editable:true,
    template:"31% 165px 155px minmax(0,1fr) 40px",
    columns:[{key:"name",label:"Item",sortValue:({it})=>localizedValue(it.nameKey)||it.key,
        render:({it})=>NAME_CELL_FOR(it)},
      {key:"price",label:"Global buy price",sortValue:({it})=>cashOf(it,"buy")??Infinity,
        render:({it})=>buyPriceCell(it,cashParts(it.buy,"buy"),shopPriceRef(it,"buy"))},
      {key:"qty",sortValue:({it})=>effectivePurchaseYieldOf(it),
        label:()=>el("span",{},"Purchase output",fieldHelp("What one purchase ultimately provides. Bundle containers show both the raw purchased container and the usable items produced when it opens.")),
        render:({it})=>purchaseQuantityCell(it)},
      {key:"requirements",label:"Availability requirements",cellClass:"requirements",
        sortValue:({row})=>row.requirements.map(r=>`${r.type}:${r.key}:${r.state}`).join("|"),
        render:({row})=>row.requirements.length?row.requirements.map(r=>`${r.type}: ${r.key}${r.state?` = ${r.state}`:""}`).join(" · "):"Always available in this inventory"},
      {key:"remove",label:"",sortable:false,render:({row})=>el("span",{class:"del",title:"Remove from this shop inventory",
        onclick:()=>{shop.items.splice(shop.items.indexOf(row),1);state.shopDirty.add(shop.type);renderShops();}},"×")}]});
  m.append(table,el("div",{class:"addrow"},newButton({title:"Add item to this shop",onclick:()=>pickIdentifier("Catalog item",state.catalog.items.map(x=>x.key).sort(),"",v=>{if(!shop.items.some(x=>x.item===v)){shop.items.push(newShopListing(v));state.shopDirty.add(shop.type);}renderShops();})})));
}
function renderAllShopInventories(shops,q,m){
  const grouped=new Map();
  shops.forEach(shop=>shop.items.forEach(row=>{const it=state.catalog.items.find(i=>i.key===row.item);if(!it||!shopItemMatches(it,q))return;const group=grouped.get(it.key)||{it,listings:[]};group.listings.push({shop,row});grouped.set(it.key,group);}));
  let rows=sortedRows("shops-buy-all",[...grouped.values()],{name:x=>localizedValue(x.it.nameKey)||x.it.key,price:x=>cashOf(x.it,"buy")??Infinity,qty:x=>effectivePurchaseYieldOf(x.it),shops:x=>x.listings.map(v=>shopLabel(v.shop.type)).sort().join("|")});
  $("#toolbar").insertBefore(el("span",{class:"count"},`${rows.length} matching items`),$("#toolbar").lastChild);
  m.append(el("div",{class:"hint"},el("b",{},"Global catalog prices: "),"an item's buy price and purchase output are shared by every shop. Shop membership and availability requirements are edited separately below."));
  m.append(columnList({class:"shop-table","aria-label":"Items sold by shop",
    rows:rows.slice(0,1000),key:({it})=>it.key,editable:true,
    template:"31% 165px 155px minmax(0,1fr)",
    columns:[{key:"name",label:"Item",sortValue:({it})=>localizedValue(it.nameKey)||it.key,
        render:({it})=>NAME_CELL_FOR(it)},
      {key:"price",label:"Global buy price",sortValue:({it})=>cashOf(it,"buy")??Infinity,
        render:({it})=>buyPriceCell(it,cashParts(it.buy,"buy"),shopPriceRef(it,"buy"))},
      {key:"qty",label:"Purchase output",sortValue:({it})=>effectivePurchaseYieldOf(it),
        render:({it})=>purchaseQuantityCell(it)},
      {key:"shops",label:"Sold by / availability",cellClass:"requirements",
        sortValue:({listings})=>listings.map(v=>shopLabel(v.shop.type)).sort().join("|"),
        render:({listings})=>el("span",{},...listings.sort((a,b)=>shopLabel(a.shop.type).localeCompare(shopLabel(b.shop.type))).map(({shop,row})=>
          el("div",{},el("button",{class:"table-link",onclick:()=>{state.filters.shopType=shop.type;renderShops();}},shopLabel(shop.type))," — ",
            row.requirements.length?row.requirements.map(r=>`${r.type}: ${r.key}${r.state?` = ${r.state}`:""}`).join(" · "):"always available",
            el("span",{class:"del",title:`Remove from ${shopLabel(shop.type)}`,
              onclick:()=>{shop.items.splice(shop.items.indexOf(row),1);state.shopDirty.add(shop.type);renderShops();}}," ×"))))}]}));
}
function renderShopSellPrices(q,m){
  let rows=state.catalog.items.filter(it=>(cashOf(it,"sell")!==null||q)&&shopItemMatches(it,q));
  rows=sortedRows("shops-sell",rows,{name:it=>localizedValue(it.nameKey)||it.key,price:it=>cashOf(it,"sell")??Infinity});
  $("#toolbar").insertBefore(el("span",{class:"count"},`${rows.length} matching items${rows.length>600?" (showing 600)":""}`),$("#toolbar").lastChild);
  m.append(el("div",{class:"hint"},el("b",{},"BUYS: "),"The price field is the only proven global sellability control. It is editable. Merchant-specific acceptance cannot be derived from PDATA; its exceptions are displayed read-only and never mean that a blank merchant rejects an item."));
  m.append(columnList({class:"shop-table","aria-label":"Sell prices",
    rows:rows.slice(0,600),key:it=>it.key,editable:true,
    template:"31% 165px minmax(0,1fr)",
    columns:[{key:"name",label:"Item",sortValue:it=>localizedValue(it.nameKey)||it.key,
        render:it=>NAME_CELL_FOR(it)},
      {key:"price",label:"Sell price",sortValue:it=>cashOf(it,"sell")??Infinity,
        render:it=>sellPriceCell(it,cashParts(it.sell,"sell"),shopPriceRef(it,"sell"))},
      {key:"known",label:"What is known",sortable:false,render:it=>globalSaleStatusCell(it)}]}));
}

function merchantAccepted(shop,item){
  return !!state.shopBuyers?.buyers?.[shop]?.includes(item);
}
function merchantOverride(shop,item){
  return state.shopBuyerDirty[`${shop}|${item}`] ?? state.shopBuyers?.overrides?.[shop]?.[item] ?? "default";
}
function setMerchantOverride(shop,item,mode){
  const base=state.shopBuyers?.overrides?.[shop]?.[item]??"default",key=`${shop}|${item}`;
  if(mode===base)delete state.shopBuyerDirty[key];else state.shopBuyerDirty[key]=mode;
  refreshGlobalSave();renderShops();
}
async function saveShopBuyerOverrides(){
  const edits=Object.entries(state.shopBuyerDirty).map(([key,mode])=>{const cut=key.indexOf("|");return{shop:key.slice(0,cut),item:key.slice(cut+1),mode};});
  if(!edits.length)return 0;
  const r=await api("/api/shop-buyers/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});
  state.shopBuyerDirty={};state.shopBuyers=await api("/api/shop-buyers");state.shopAcceptance=null;return r.saved;
}
function globalSaleStatusCell(it){
  const payout=cashOf(it,"sell");
  if(payout===null)return el("div",{class:"requirements"},"Not normally sellable — no SELL_SHOP_DEFAULT record");
  const explicit=state.shopBuyers?.shops?.filter(shop=>merchantAccepted(shop,it.key)).map(shopLabel)||[];
  const text=`Globally sellable for $${fmtMoney(payout)}. Merchant category coverage is not yet recovered from compiled scripts.`;
  return el("div",{class:"requirements",title:"The editor knows the global catalog sale switch and payout. It does not pretend the sparse PDATA list tells us who normally accepts the item."},text,explicit.length?el("div",{class:"subtle"},"Explicit PDATA: "+explicit.join(", ")):null);
}

async function saveShops(){if(isRO()||!state.shopDirty.size)return;const edits=[...state.shopDirty].map(shopSaveEdit);
  try{const r=await api("/api/shops/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.shopDirty.clear();toast(`Saved ${r.saved} shop membership change(s)`);renderShops();}catch(ex){throw showSaveFailure(ex);}}

async function saveShopTab(){
  if(isRO())return;
  if(state.shopDirty.size){
    const edits=[...state.shopDirty].map(shopSaveEdit);
    try{await api("/api/shops/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.shopDirty.clear();refStore("mine").shops=null;}
    catch(ex){throw showSaveFailure(ex);}
  }
  if(Object.keys(state.shopBuyerDirty).length)await saveShopBuyerOverrides();
  await saveCatalog();
}
