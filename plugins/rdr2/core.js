"use strict";
const $ = s => document.querySelector(s);
const el = window.LexeditorUI.el;
const newButton=window.LexeditorUI.newButton;
const closeButton=window.LexeditorUI.closeButton;
const columnList=window.LexeditorUI.columnList;
function showSaveFailure(error){const message=error?.message||String(error);toast("Save failed",true);LexeditorUI.showAlert({title:"Save failed",items:[{item:"Save",issue:message}],closeLabel:"Confirm and Close"});return error instanceof Error?error:new Error(message)}

const state = {
  booting: true,
  loadError: null,
  tab: "items",
  ds: "mine",           // current dataset (mine | kiddos | vanilla)
  store: {},            // ds -> {catalog, quickSelect, effectByKey, loot, matrix}
  catalog: null,        // {items, effects} — pointer into store[ds]
  quickSelect: null,    // active quickselectitems.ymt item-to-slot mappings
  effectByKey: {},
  loot: {},             // file -> {tables} — pointer into store[ds]
  lootFile: null,
  matrix: null,
  shops: null,
  config: null,
  // dirty edit stores
  priceEdits: {},       // "itemKey|section|costKey|partItem" -> qty(cents)
  buyabilityEdits: {},  // itemKey -> {buyable, cents}
  sellabilityEdits: {}, // itemKey -> {sellable, cents}
  yieldEdits: {},       // "itemKey|section|costKey" -> quantity received
  carryEdits: {},       // "itemKey|slot" -> qty
  bundleEdits: {},      // "loot file|table|item" -> opened-item quantity
  craftEdits: {},       // itemKey -> [{key, yield, parts:[{item,qty}]}] (full craft replace)
  customCrafting: {available:false,customFile:null,vanillaFile:null,vanilla:[],custom:[],errors:[]},
  customCraftingDraft: [],
  customCraftingDirty: false,
  crimeEdits: {},       // "crimeKey|field" -> value
  dispatchEdits: {},    // "group|field" -> value
  bountyHunters: {},
  bountyHunterEdits: {}, // concrete bountyhunters.meta / cooldown field id -> value
  honorActions: null,
  honorActionEdits: {},
  lootSoundEdits: {},
  lootSoundSelected: null,
  effectEdits: {},      // "effKey|field" -> value
  itemEffectEdits: {},  // itemKey -> [effect keys]
  itemTagEdits: {},     // itemKey -> [{key, type}]
  quickSelectEdits: {}, // itemKey -> {group, slots:[{id, sortOrder}]}
  alcohol: {available:false,file:null,entries:{}},
  alcoholEdits: {},     // itemKey -> numeric drunkenness added per use
  descriptionKeyEdits: {}, // itemKey -> newly-created localization key
  settings: null,
  settingEdits: {},       // "section|key" -> value
  lootDirty: {},        // file -> Set(tableKey)
  lootCollapsed: new Set(), // "tableKey|entryIndex" of nested tables collapsed by hand
  matrixDirty: new Set(),
  shopDirty: new Set(),
  shopBuyers: null,
  shopBuyerDirty: {}, // "shop|item" -> default/accept/reject
  challengeEdits: {},
  challengeSourceEdits: {},
  challengeConditionEdits: {},
  challengeRewardEdits: {},
  challengeUiEdits: {},
  challengeModeEdits: {},
  aiEdits: {},
  mobs: null,
  mobEdits: {},          // "file|indexPath" -> {file, path, kind, value}
  mobModels: null,
  modOnly: false,
  localization: null,
  localizationEdits: {},
  weaponData: {},
  weaponReference: null,
  weaponEdits: {},
  projectileSpeeds: {},
  projectileSpeedEdits: {},
  weaponShellVfxEdit: null,
  labels: {},
  modelPreviewAvailability: {},
  modelPreviewLoads: {},
  helpOpen: {},
  dataMapSort: ["filename",1],
  expandedRecipes: new Set(),
  sorts: {
    items:{key:"name",dir:1}, "crafting-vanilla":{key:"name",dir:1}, "crafting-custom":{key:"name",dir:1}, effects:{key:"name",dir:1}, behaviors:{key:"name",dir:1},
    loot:{key:"table",dir:1},
    "shops-buy":{key:"name",dir:1}, "shops-sell":{key:"name",dir:1},
    crime:{key:"name",dir:1}, ai:{key:"context",dir:1}, weapons:{key:"field",dir:1},
    dispatch:{key:"setting",dir:1}, mobs:{key:"name",dir:1}, "mob-models":{key:"model",dir:1}
  },
  filters: { q: "", category: "", group: "", itemSection: "all", itemSource: "all", itemPage: 0, itemPageSize: 20, onlyEffects: false, onlyNamed: true, effectSection:"effects", behaviorQ:"", behaviorPage:0, behaviorPageSize:20, behaviorSel:"", effectPage:0, effectPageSize:20, effectSel:"",
             craftMode:"vanilla", craftQ:"", craftSelVanilla:"", craftSelCustom:"", craftOutput:"", craftIngredient:"", craftPage:0, craftPageSize:20,
              lootQ: "", lootPage:0, lootPageSize:20, animal: "", shopBuyQ: "", shopSellQ: "", shopSellCategory: "", shopSellSubcategory: "", shopExact: "", shopType: "ST_GENERAL", shopMode: "workspace",
             mobView: "archetypes", mobGroup: "humans", mobLayer: "combat", mobQ: "",
             mobModelGroup: "gang", mobModelQ: "", mapQ:"", mapStatus:"", mapPage:0 },
};

function toast(msg,err){LexeditorUI.showToast(msg,{tone:err?"danger":""});
}

const TAB_CONTEXT = {
  items:{files:()=>`${state.catalog?.activeFile||"catalog_sp.ymt"} + ${state.quickSelect?.activeFile||"quickselectitems.ymt"} + strings.gxt2`,help:"Items are catalog records. The first field is the actual in-game English name from Rockstar's localization key; editing it writes a strings.gxt2 override loaded by LML. Category is the precise inventory/catalog classification; group is the broader gameplay family. Quick-select slots are the actual radial assignments from quickselectitems.ymt; each item can have zero, one, or several, and every slot uses a controlled selector. Effects and Tags use + buttons that open full in-editor selectors; there are no free-entry effect or tag fields. Unresolved hashes already on an item are removable-only. Drink class is an exclusive tag that categorizes a drink (it is NOT the numeric alcohol/inebriation value, which lives outside this catalog). A steel-blue globe marks content imported from Red Dead Online. A brass pen nib marks content created locally in LEXEDITOR. Both icons are display-only and are never saved into a record."},
  crafting:{files:()=>state.filters.craftMode==="custom"?(state.customCrafting.customFile||"custom_crafting_recipes.tsv"):(state.customCrafting.vanillaFile||"vanilla_crafting_recipes.tsv"),help:"Vanilla recipes are a read-only snapshot of Rockstar's shipped COST_TYPE_CRAFT records. Custom recipes live in a separate runtime file and never rewrite catalog_sp.ymt. The custom schema permits unlimited recipe rows and unlimited ingredient rows. Recipe IDs must be unique; outputs and ingredients must be real catalog item IDs; all quantities are positive whole numbers. Linked outputs use a steel-blue globe for Red Dead Online content and a brass pen nib for locally created content."},
  effects:{files:()=>`${state.catalog?.activeFile||"catalog_sp.ymt"} + plugin labels.json`,help:"An effect record combines an item-facing catalog key with an engine Behavior ID. You may create new effect records with different magnitudes, durations, and labels, but they must reuse a Behavior ID the engine already implements; inventing a new Behavior ID does not create new game code. Catalog-reference and Behavior labels are editor-only organization stored in this plugin's labels.json. Changing a shared effect changes every item that references it. Timed effects use Time + Time Units: 0 seconds, 1 minutes, 2 in-game hours, 3 in-game days. A steel-blue globe marks a Red Dead Online effect. A brass pen nib marks an effect created locally in LEXEDITOR."},
  loot:{files:()=>state.lootFile==="__matrix"?"loot_items_matrix.meta":state.lootFile,help:"Loot table files define probabilistic drops and references to other pools. On Item Groups (and other loot files) you can create empty tables and delete unreferenced ones; point other tables at a new group with entry type Table. Skinning is a deterministic quality matrix in loot_items_matrix.meta."},
  shops:{files:()=>`${state.catalog?.activeFile||"catalog_sp.ymt"} + parseddata/0x0BA63B3D.ymt + merchant_buy_overrides.csv`,help:"The selected shop is in the middle. BUYS controls the global SELL_SHOP_DEFAULT payout plus explicit per-merchant Accept or Reject overrides. An item absent from sparse buyer PDATA remains engine-default unknown, not proven rejected. SELLS controls this shop's stock membership, listing-specific availability groups, and global COST_SHOP_DEFAULT price. A steel-blue globe marks Red Dead Online content. A brass pen nib marks locally created content."},
  settings:{files:()=>state.settings?.file||"GameplayTweaks.ini",help:"GameplayTweaks.asi re-reads this INI approximately every two seconds, so most settings can be tuned while Story Mode is running. This optional tab is unavailable when LEXEDITOR is used without GameplayTweaks; the rest of the editor remains fully functional."},
  challenges:{files:"goals_sp.meta + challenges_sp.meta + strings.gxt2",help:"goals_sp.meta defines nested requirements and target values; rows are labeled as goal counters, exclusion guards, or required conditions/triggers. challenges_sp.meta defines strand order and rewards. Visible names and descriptions are actual in-game English localization and save through strings.gxt2. Vanilla XP rewards are fixed bundles: First 25, Second 50, Third 100, Fourth 150 XP. Attribute levels 1–8 unlock at cumulative 0 / 50 / 100 / 200 / 350 / 550 / 800 / 1100 XP; levels 9–10 use bonus-rank progression."},
  weapons:{files:"active install.xml weapon layers + strings.gxt2",help:"Ammo Types combines shared CAmmoInfo behavior with every weapon-specific DamageInfos variant keyed to that ammo. Damage and penetration vary by weapon; High Velocity range comes from the linked DamageFallOffInfo curve. The radial stat bars summarize these underlying values rather than storing a separate authoritative set of stats. LEXEDITOR resolves four OpenIV-exported record-type hashes to Rockstar's named weapon schema before saving; this preserves rumble, degradation, falloff, and vehicle-weapon records. A steel-blue globe marks a weapon or ammunition record from an RDO-only weapon layer; edits save back to that record's exact active layer."},
  ai:{files:()=>state.filters.aiFile||"combat styles/programs (Data Map)",help:"AI is layered across profile, global tuning, and decision-graph files. UCO values are reference-only."},
  mobs:{files:()=>state.filters.mobView==="models"?"MobProbe/mob_stats.csv":(state.filters.mobLayer==="health"?"pedhealth.meta":"ai/combatbehaviour.meta"),help:"Archetypes edits the real combatbehaviour.meta and pedhealth.meta records. Combat profiles own fields such as WeaponAccuracy. Health archetypes own HP, armour, and injury or knockout thresholds. Observed Models is read-only MobProbe evidence. No shipped data file directly binds every ped model to one archetype, so LEXEDITOR does not invent or save that relationship."},
  crime:{files:()=>state.filters.crimeSection==="honor"?(state.honorActions?.file||"honor_actions.csv"):state.filters.crimeSection==="bounty"?"dispatchresponses/wilderness/bountyhunters.meta + dispatch.meta":state.filters.crimeSection==="dispatch"?"dispatch.meta":"crimeinformation.meta",help:"Crime Rules controls reporting and response. Honor Actions exposes 21 exact independent event toggles and 19 shared magnitude tiers; amounts are tiers reused by many actions, never invented per-action values."},
  datamap:{files:"DATA_MAP.md",help:"The Data Map documents the effective extracted game-data set; it does not edit game files."}
};

function fieldHelp(text){return LexeditorUI.infoHelp(text,{class:"field-help"});}
function rdrSearchField({id,placeholder,label=placeholder,value="",oninput}){
  return LexeditorUI.inlineLabel(LexeditorUI.searchIcon(),el("input",{id,type:"search",placeholder,"aria-label":label,value,oninput}));
}

function tabContext(){const c=TAB_CONTEXT[state.tab]||{};return typeof c.files==="function"?c.files():c.files||"";}
function installTabContext(){
  // Tab help belongs to the shell tab. Keep a page's own status messages visible.
  $("#toolbar")?.querySelectorAll(".help-toggle").forEach(node=>node.remove());
}

function filterRerender(ev,rerender){
  const source=ev.currentTarget||ev.target,placeholder=source.placeholder,type=source.type;
  const id=source.id,scope=source.closest("#toolbar")?"#toolbar":source.closest("#main")?"#main":"body";
  const start=source.selectionStart,end=source.selectionEnd,direction=source.selectionDirection;
  const restore=()=>{
    const next=(id&&document.getElementById(id))||[...document.querySelectorAll(`${scope} input`)]
      .find(input=>input.placeholder===placeholder&&input.type===type);
    if(!next)return;
    next.focus({preventScroll:true});
    if(start!==null)next.setSelectionRange(start,end,direction||"none");
  };
  const pending=rerender();
  if(pending&&typeof pending.then==="function")pending.then(restore);
  else restore();
}

function sortedRows(tab,rows,getters){const s=state.sorts[tab];if(!s||!getters[s.key])return rows;return [...rows].sort((a,b)=>{const av=getters[s.key](a),bv=getters[s.key](b);return s.dir*(typeof av==="number"&&typeof bv==="number"?av-bv:String(av??"").localeCompare(String(bv??"")));});}
function purchaseYieldValue(it){
  const cost=it?.buy?.find(c=>c.costtype==="COST_TYPE_PRICE"&&c.parts.some(p=>p.item==="CURRENCY_CASH"));
  if(!cost)return null;
  return +(state.yieldEdits[`${it.key}|buy|${cost.key}`]??cost.yield??1);
}
function purchaseYieldOf(it){return purchaseYieldValue(it)??Infinity;}
const PURCHASE_CONTAINERS={
  UPGRADE_FSH_BAIT_WORM_CAN:{table:"BAIT_WORMS",target:"UPGRADE_FSH_BAIT_WORM",container:"can"},
  UPGRADE_FSH_BAIT_CRICKET_TIN:{table:"BAIT_CRICKETS",target:"UPGRADE_FSH_BAIT_CRICKET",container:"tin"}
};
function purchaseBundleOf(it){
  const spec=PURCHASE_CONTAINERS[it?.key];if(!spec)return null;
  const target=state.catalog?.items.find(candidate=>candidate.key===spec.target);
  const source=target?.lootSources?.find(row=>row.file==="loot_table_itemgroups.meta"&&row.table===spec.table);
  if(!source)return null;
  const editKey=`${source.file}|${spec.table}|${spec.target}`;
  const edited=state.bundleEdits[editKey];
  return {...spec,targetItem:target,min:edited??(source.min||source.max||"1"),max:edited??(source.max||source.min||"1"),file:source.file,editKey,source};
}
function purchaseContainersFor(it){
  return Object.keys(PURCHASE_CONTAINERS).map(key=>state.catalog?.items.find(candidate=>candidate.key===key))
    .filter(Boolean).map(purchaseBundleOf).filter(bundle=>bundle?.target===it?.key);
}
function effectivePurchaseYieldOf(it){const bundle=purchaseBundleOf(it);return bundle?+(bundle.min||1):purchaseYieldOf(it);}
function defaultCarryCap(it){const row=(it?.carry||[]).find(x=>x.slot==="SLOTID_ANY")||(it?.carry||[])[0];return row?+(state.carryEdits[`${it.key}|${row.slot}`]??row.qty):-Infinity;}
function humanName(scope,key){return state.labels?.[scope]?.[key]||"";}
// display name for an effect: user/editor label > recovered hash name > raw key
function effectDisplayName(key){
  return humanName("effects",key) || (state.effectByKey[key]?.label ? state.effectByKey[key].label + "*" : key);
}
function humanNameInput(scope,key,placeholder="Add display name…"){return el("input",{class:"human-name",type:"text",value:humanName(scope,key),placeholder,title:"Editor-only human-readable label; stored in this RDR2 plugin's labels.json and never written to the mod.",onchange:async ev=>{const value=ev.target.value;state.labels[scope]=state.labels[scope]||{};if(value.trim())state.labels[scope][key]=value.trim();else delete state.labels[scope][key];await api("/api/labels/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scope,key,value})});}});}
function localizedValue(key){return state.localizationEdits[key]??state.localization?.values?.[key]??"";}
// A localisation entry that holds only whitespace is not a name. Several
// catalogue headings and their base-game rows both resolve to a non-breaking
// space, and offering that blank as a reference would let a click record a
// change that writes the same blank back. Blank means no reference to apply.
function localizedReference(key){const value=state.localization?.vanilla?.[key];return String(value??"").trim()?value:undefined;}
function originMarker(record){
  if(record?.rdoAdded){
    const ns="http://www.w3.org/2000/svg",icon=document.createElementNS(ns,"svg");
    for(const [key,value] of Object.entries({viewBox:"0 0 24 24",width:"14",height:"14",fill:"none",stroke:"#8da9ba","stroke-width":"2",role:"img","aria-label":"Imported from Red Dead Online"}))icon.setAttribute(key,value);
    const title=document.createElementNS(ns,"title");title.textContent="Imported from Red Dead Online";
    const circle=document.createElementNS(ns,"circle");circle.setAttribute("cx","12");circle.setAttribute("cy","12");circle.setAttribute("r","9");
    const path=document.createElementNS(ns,"path");path.setAttribute("d","M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18");
    icon.append(title,circle,path);return icon;
  }
  if(record?.customAdded)return el("span",{class:"lex-ui-symbol",title:"Created locally in LEXEDITOR","aria-label":"Created locally in LEXEDITOR"},"✒️");
  return "";
}

function originDisplayName(value,record){return LexeditorUI.inlineLabel(
  originMarker(record),el("span",{},value));}
function catalogItem(key){return state.catalog?.items.find(item=>item.key===key)||null;}
function sanitizeItemDescription(value){
  return value
    .replace(/~(?:COLOR_[A-Z0-9_]+|[bgrs])~/gi, "")
    .replace(/(~n~)[bgr]~/gi, "$1");
}
function localizationInput(key,placeholder="No localized name"){
  if(!key)return el("input",{class:"human-name",value:"N/A",readonly:"readonly",title:"This record has no localization key."});
  // Some catalogue headings resolve to a non-breaking space. Treat blank
  // names as empty on screen so the placeholder remains visible. Keep the
  // source untouched unless the user supplies a name.
  const visible=value=>String(value??"").trim()?String(value):"";
  const attrs={class:"human-name localized-name",type:"text",value:visible(localizedValue(key)),placeholder,title:`In-game localization: ${key}`,onchange:ev=>{const value=ev.target.value,base=visible(state.localization?.values?.[key]);if(value===base)delete state.localizationEdits[key];else state.localizationEdits[key]=value;renderToolbarOnly();}};
  if(isRO())attrs.readonly="readonly";return el("input",attrs);
}
function localizationTextarea(key,placeholder="No localized description",onEdit){
  if(!key){const area=LexeditorUI.textArea({readonly:"readonly",title:"This record has no localization key."});area.value="N/A";return area;}
  const attrs={class:"localized-description",placeholder,title:`In-game localization: ${key}`,onchange:ev=>{const value=ev.target.value,base=state.localization?.values?.[key]??"";if(value===base)delete state.localizationEdits[key];else state.localizationEdits[key]=value;ev.target.classList.toggle("edited",key in state.localizationEdits);if(onEdit)onEdit(value);renderToolbarOnly();}};
  if(isRO())attrs.readonly="readonly";const area=LexeditorUI.textArea(attrs);area.value=localizedValue(key);return area;
}
async function saveLocalization(){const edits=Object.entries(state.localizationEdits).map(([key,value])=>({key,value}));if(!edits.length)return 0;const r=await api("/api/localization/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});for(const e of edits)state.localization.values[e.key]=e.value;state.localizationEdits={};return r.saved;}

// "Mod contents only" keeps the records this project has actually changed.
// RDR2 files every edit under a composite key whose first segment names the
// record it belongs to, so the filter for a view is the set of first segments
// across the maps that view writes to, plus any dirty sets kept beside them.
function touchedRecords(maps = [], sets = [], segment = 0) {
  const out = new Set();
  for (const map of maps)
    for (const key of Object.keys(map || {})) out.add(String(key).split("|")[segment]);
  for (const set of sets) for (const key of (set || [])) out.add(String(key));
  return out;
}
function modOnlySpec(touched, resetPage, redraw) {
  return {
    available: !isRO(),
    value: state.modOnly === true,
    changed: key => touched.has(String(key)),
    change: value => { state.modOnly = value; resetPage(); redraw(); },
  };
}
const ITEM_EDIT_MAPS = () => [state.priceEdits, state.buyabilityEdits, state.sellabilityEdits,
  state.yieldEdits, state.bundleEdits, state.itemEffectEdits, state.itemTagEdits,
  state.quickSelectEdits, state.descriptionKeyEdits, state.carryEdits, state.craftEdits,
  state.localizationEdits];
function dirtyCount() {
  const catalog = ["priceEdits","buyabilityEdits","sellabilityEdits","yieldEdits","bundleEdits",
    "itemEffectEdits","itemTagEdits","quickSelectEdits","descriptionKeyEdits","carryEdits","craftEdits","effectEdits","localizationEdits"]
    .reduce((n,key)=>n+Object.keys(state[key]).length,0);
  return catalog + (state.customCraftingDirty?1:0) + Object.keys(state.alcoholEdits).length + Object.keys(state.settingEdits).length + state.shopDirty.size + Object.keys(state.shopBuyerDirty).length + state.matrixDirty.size +
    Object.values(state.lootDirty).reduce((n,s)=>n+s.size,0) +
    Object.keys(state.crimeEdits).length + Object.keys(state.dispatchEdits).length + Object.keys(state.bountyHunterEdits).length + Object.keys(state.honorActionEdits).length + Object.keys(state.lootSoundEdits).length +
    Object.keys(state.challengeEdits).length + Object.keys(state.challengeSourceEdits).length + Object.keys(state.challengeConditionEdits).length +
    Object.keys(state.challengeRewardEdits).length + Object.keys(state.challengeUiEdits).length + Object.keys(state.challengeModeEdits).length +
    Object.values(state.aiEdits).reduce((n,edits)=>n+Object.keys(edits).length,0) +
    Object.keys(state.mobEdits).length +
    Object.values(state.weaponEdits).reduce((n,edits)=>n+Object.keys(edits).length,0) +
    (state.weaponShellVfxEdit===null?0:1);
}

// The shared history engine owns command ordering and keyboard shortcuts. The
// RDR2 plugin supplies only its editable state. Large read-only catalog and
// reference datasets stay outside each snapshot; the three views that edit
// loaded rows in place supply their small mutable working sets explicitly.
const RDR2_HISTORY_KEYS = [
  "priceEdits", "buyabilityEdits", "sellabilityEdits", "yieldEdits", "bundleEdits",
  "craftEdits", "customCraftingDraft", "customCraftingDirty", "crimeEdits",
  "dispatchEdits", "bountyHunterEdits", "honorActionEdits", "lootSoundEdits", "effectEdits",
  "itemEffectEdits", "itemTagEdits", "quickSelectEdits", "alcoholEdits", "descriptionKeyEdits",
  "settingEdits", "lootDirty", "matrixDirty", "shopDirty", "shopBuyerDirty",
  "challengeEdits", "challengeSourceEdits", "challengeConditionEdits",
  "challengeRewardEdits", "challengeUiEdits", "challengeModeEdits", "aiEdits",
  "mobEdits", "localizationEdits", "weaponEdits",
  "weaponShellVfxEdit", "projectileSpeedEdits"
];
function rdr2HistoryCapture(){
  const values={};
  for(const key of RDR2_HISTORY_KEYS)values[key]=LexeditorUI.clone(state[key]);
  const mine=state.store.mine||{};
  return {values,mutable:{shops:LexeditorUI.clone(mine.shops??null),loot:LexeditorUI.clone(mine.loot??{}),matrix:LexeditorUI.clone(mine.matrix??null)}};
}
async function rdr2HistoryRestore(snapshot){
  for(const [key,value] of Object.entries(snapshot.values))state[key]=LexeditorUI.clone(value);
  const mine=refStore("mine");
  mine.shops=LexeditorUI.clone(snapshot.mutable.shops);
  mine.loot=LexeditorUI.clone(snapshot.mutable.loot);
  mine.matrix=LexeditorUI.clone(snapshot.mutable.matrix);
  if(state.ds==="mine"){
    state.shops=mine.shops;
    state.loot=mine.loot;
    state.matrix=mine.matrix;
  }
}

function fmtMoney(cents) { return (cents / 100).toFixed(2); }
function fmtCompactNumber(value){const n=Number(value);return Number.isFinite(n)?String(n):String(value??"");}

// ---------- data loading ----------
function dsInfo() { return state.config.datasets[state.ds]; }
function isRO() { return dsInfo().readonly; }

async function api(path, opts, dsOverride) {
  const sep = path.includes("?") ? "&" : "?";
  const r = await fetch(path + sep + "ds=" + (dsOverride || state.ds), opts);
  const j = await r.json();
  if (j.error) throw new Error(j.error);
  return j;
}

// ---------- reference datasets (vanilla / kiddos shown beside "mine") ----------
const REF_DS = ["vanilla", "kiddos", "prices1899"];
let refsLoading = false;

function refStore(ds) {
  if (!state.store[ds]) state.store[ds] = { catalog: null, quickSelect:null, effectByKey: {}, loot: {}, matrix: null, shops:null };
  return state.store[ds];
}

function hasScope(ds, scope, file) {
  const info = state.config.datasets[ds];
  return info && (info.scopes.includes("all") || info.scopes.includes(scope) || (file && info.scopes.includes(file)));
}

async function ensureRefCatalogs(rerender) {
  if (state.ds !== "mine" || refsLoading) return;
  const missing = REF_DS.filter(ds => state.config.datasets[ds].catalog && !refStore(ds).catalog);
  if (!missing.length) return;
  refsLoading = true;
  try {
    for (const ds of missing) {
      const st = refStore(ds);
      st.catalog = await api("/api/catalog", undefined, ds);
      for (const e of st.catalog.effects) st.effectByKey[e.key] = e;
    }
  } catch (e) { /* refs are best-effort */ }
  refsLoading = false;
  if(state.catalog)rebuildTagMaps(state.catalog);
  if (rerender) rerender();
}

async function ensureRefLoot(file, rerender) {
  if (state.ds !== "mine") return;
  const missing = REF_DS.filter(ds => hasScope(ds, "loot", file) &&
    state.config.datasets[ds].lootFiles.includes(file) && !refStore(ds).loot[file]);
  if (!missing.length) return;
  for (const ds of missing) {
    try { refStore(ds).loot[file] = await api("/api/loot/" + file, undefined, ds); }
    catch (e) { refStore(ds).loot[file] = { tables: [] }; }
  }
  if (rerender) rerender();
}

async function ensureRefMatrix() {
  if (state.ds !== "mine") return;
  for (const ds of ["vanilla", "kiddos"]) {
    if (hasScope(ds, "matrix") && state.config.datasets[ds].matrix && !refStore(ds).matrix)
      try { refStore(ds).matrix = await api("/api/matrix", undefined, ds); } catch (e) { /* best effort */ }
  }
}

function cashOf(it, section) {
  if (!it) return null;
  const availability=(section==="buy"?state.buyabilityEdits:state.sellabilityEdits)[it.key];
  if(availability&&!availability[section+"able"])return null;
  for (const c of it[section])
    for (const p of c.parts)
      if (p.item === "CURRENCY_CASH" && (section === "sell" || c.costtype === "COST_TYPE_PRICE")){
        const editKey=`${it.key}|${section}|${c.key}|${p.item}`;
        return state.priceEdits[editKey]??p.qty;
      }
  if(availability?.[section+"able"])return availability.cents??100;
  return null;
}

function cashCost(it,section) {
  if(!it)return null;
  return it[section].find(c=>c.parts.some(p=>p.item==="CURRENCY_CASH")&&(section==="sell"||c.costtype==="COST_TYPE_PRICE"))||null;
}

function cashParts(costs,section){
  const found=[];
  for(const cost of costs||[]){
    if(section!=="sell"&&cost.costtype!=="COST_TYPE_PRICE")continue;
    for(const part of cost.parts||[])if(part.item==="CURRENCY_CASH")found.push([cost,part]);
  }
  return found;
}

function currentShopTypesForItem(itemKey){
  const loaded=refStore(state.ds).shops?.shops;
  if(loaded)return loaded.filter(shop=>shop.items.some(row=>row.item===itemKey)).map(shop=>shop.type);
  const it=state.catalog?.items.find(candidate=>candidate.key===itemKey);
  return (it?.shopListings||[]).map(listing=>listing.shop);
}

function refItem(ds, key) {
  const st = state.store[ds];
  if (!st || !st.catalog) return null;
  if (!st._byKey) {
    st._byKey = {};
    for (const it of st.catalog.items) st._byKey[it.key] = it;
  }
  return st._byKey[key] || null;
}

const SLOT_LABELS = {
  "SLOTID_ANY":"default / any", "SLOTID_SATCHEL":"satchel",
  "0x04718245":"LotE satchel", "0xBE85CADE":"consumables satchel upgrade",
  "0x0D7CB5AE":"provisions satchel upgrade", "0xE655E53D":"ammo upgrade A",
  "0xD4774180":"ammo upgrade B", "0x550898DE":"unresolved engine slot A",
  "0xAEEE1782":"unresolved engine slot B"
};
const slotLabel = slot => SLOT_LABELS[slot] || (slot.startsWith("0x") ? `unresolved slot ${slot}` : slot.replace("SLOTID_","").toLowerCase());
function carrySlotOptions(it) {
  const slots = new Set(Object.keys(SLOT_LABELS));
  const collect = candidate => {
    if (!candidate) return;
    for (const rule of candidate.carry || []) slots.add(rule.slot);
  };
  collect(it);
  collect(refItem("vanilla", it.key));
  collect(refItem("kiddos", it.key));
  // Ammo upgrades apply across several ammo categories, so use the whole AMMO
  // group. Other items stay category-scoped to avoid irrelevant component slots.
  for (const candidate of state.catalog.items)
    if (candidate.category === it.category || (it.group === "AMMO" && candidate.group === "AMMO")) collect(candidate);
  return [...slots].filter(slot => !(it.carry || []).some(rule => rule.slot === slot))
    .sort((a,b)=>slotLabel(a).localeCompare(slotLabel(b))).map(value=>({value,label:`${slotLabel(value)} — ${value}`}));
}

// small "V … · K …" line; clicking a value applies it to the input in the same cell
function refLine(pairs, fmt, apply) {
  if (state.ds !== "mine") return "";
  const div = el("div", { class: "ref" });
  let any = false;
  for (const [tag, cls, val] of pairs) {
    const s = el("span", { title: "click to apply" }, ...(any ? ["· "] : []), el("b", { class: cls }, tag + " "),
      val === null || val === undefined ? "—" : fmt(val));
    if (val !== null && val !== undefined && apply)
      s.addEventListener("click", ev => apply(val, ev));
    div.append(s);
    any = true;
  }
  return any ? div : "";
}

// Compact reference values sit beside the input. Matching values carry no
// information and are omitted. If every available reference matches, the
// shared component returns nothing.
function refStack(pairs, current, apply, fmt) {
  fmt = fmt || String;
  if (state.ds !== "mine") return "";
  const norm = v => {
    if (v === null || v === undefined || v === "") return null;
    const s = String(v).trim();
    if (/^-?(?:\d+(?:\.\d*)?|\.\d+)$/.test(s)) return String(Number(s));
    return s.replace(/^0+(?=\d)/,"");
  };
  return LexeditorUI.referenceDisplay({
    className:"ref refstack",
    current:current===undefined?undefined:norm(current),
    sources:pairs.filter(([, , value])=>norm(value)!==null).map(([tag,cls,value])=>({
      name:tag==="V"?"Vanilla":tag,
      shortName:tag,
      className:cls,
      value,
    })),
    same:(left,right)=>norm(left)===norm(right),
    format:fmt,
    apply:(value,event)=>apply?.(value,event),
  })||"";
}

// refLine is now an alias: any caller that has not yet been given a `current`
// value still gets the unified compact display (it simply will not grey, since
// without current there is nothing to compare against). Signature preserved:
// refLine(pairs, fmt, apply) -> refStack(pairs, undefined, apply, fmt).
function refLine(pairs, fmt, apply) { return refStack(pairs, undefined, apply, fmt); }

/** Control + refStack on one row. The only supported way to attach V/K/etc.
 *  references to an editable field. Pass the control node and the same pairs
 *  you would give refStack; empty/no-ref collapses to just the control.
 *  opts.bool: compact centered checkbox layout (crime Off column). */
function refField(control, pairs, current, apply, fmt, opts={}) {
  const sources=state.ds==="mine"?(pairs||[]).filter(([, , value])=>value!==null&&value!==undefined&&value!==""):[];
  const vanilla=sources.find(([tag])=>tag==="V");
  return LexeditorUI.provenanceControl({control,current:()=>current,vanilla:vanilla?.[2],
    references:sources.filter(([tag])=>tag!=="V").map(([tag,,value])=>({name:tag,shortName:tag,value})),
    format:fmt||String,apply:(value,event)=>{current=value;if(event)event.lexReferenceControl=control;apply?.(value,event);}});
}

function multiValueReferenceStack(references,key,currentEntry,{keyOf,entryValue,formatValue=String},ghost=false){
  if(state.ds!=="mine"||!references.length)return "";
  const stack=LexeditorUI.stack({fill:false});
  const comparable=value=>value===undefined||value===null?null:String(value);
  const currentValue=entryValue&&currentEntry?comparable(entryValue(currentEntry)):null;
  for(const [tag,cls,entries] of references){
    const referenceEntry=(entries||[]).find(entry=>keyOf(entry)===key);
    if(!referenceEntry){
      stack.append(LexeditorUI.badge(`${tag} ×`,{tone:"muted",title:`${tag}: this entry is not present`}));
      continue;
    }
    const referenceValue=entryValue?comparable(entryValue(referenceEntry)):null;
    const matches=!ghost&&(!entryValue||referenceValue===currentValue);
    if(matches||!entryValue||referenceValue===null){
      stack.append(LexeditorUI.badge(`${tag} ✓`,{tone:"success",title:`${tag}: this entry is present${ghost?"":" and matches"}`}));
      continue;
    }
    const shown=formatValue(referenceValue,referenceEntry);
    stack.append(LexeditorUI.badge(`${tag}: ${shown}`,{title:`${tag}: ${shown}`}));
  }
  return stack;
}

function multiValueReferences({kind,current,references,keyOf,entryValue,formatValue,sortKey,renderCurrent,renderGhost,addControl,emptyText="none"}){
  const wrap=LexeditorUI.stack({fill:false,attrs:{"data-multi-ref-kind":kind}});
  const live=LexeditorUI.actionRow();
  const currentKeys=new Set();
  for(const entry of current){
    const key=keyOf(entry);currentKeys.add(key);
    const row=LexeditorUI.stack({fill:false,attrs:{"data-multi-ref-key":key}},renderCurrent(entry));
    const stack=multiValueReferenceStack(references,key,entry,{keyOf,entryValue,formatValue},false);
    if(stack)row.append(stack);
    live.append(row);
  }
  if(addControl)live.append(addControl);
  if(!current.length&&!addControl&&emptyText)live.append(el("span",{class:"cat"},emptyText));
  wrap.append(live);
  if(state.ds==="mine"){
    const ghosts=new Map();
    for(const [, ,entries] of references)for(const entry of entries||[]){
      const key=keyOf(entry);if(!currentKeys.has(key)&&!ghosts.has(key))ghosts.set(key,entry);
    }
    const rows=[...ghosts.entries()].sort((a,b)=>String(sortKey?sortKey(a[1]):a[0]).localeCompare(String(sortKey?sortKey(b[1]):b[0]),undefined,{sensitivity:"base"}));
    if(rows.length){
      const ghostList=LexeditorUI.actionRow();
      for(const [key,entry] of rows){
        const row=LexeditorUI.stack({fill:false,attrs:{"data-multi-ref-key":key}},(renderGhost||renderCurrent)(entry));
        const stack=multiValueReferenceStack(references,key,entry,{keyOf,entryValue,formatValue},true);
        if(stack)row.append(stack);ghostList.append(row);
      }
      wrap.append(ghostList);
    }
  }
  return wrap;
}

// Carry rules are already one row per context. Keep each reference on its own
// compact line beside the value rather than adding another row below it.
function carryRefLine(pairs, fmt) {
  if (state.ds !== "mine") return "";
  const div=LexeditorUI.actionRow();
  for(const [tag,cls,val] of pairs)
    div.append(el("span",{},el("b",{class:cls},tag+" "),val===null||val===undefined?"—":fmt(val)));
  return div;
}

function applyToInput(ev, newVal) {
  const control=ev.lexReferenceControl;
  const inp = control?.matches("input,textarea,select")?control:
    control?.querySelector("input,textarea,select")||ev.target.closest("td, .cellwrap, .price-cell")?.querySelector("input,textarea,select");
  if (!inp) return;
  inp.value = newVal;
  inp.dispatchEvent(new Event("change", {bubbles:true}));
}

function applyToControl(control, newVal) {
  control.value = newVal;
  control.dispatchEvent(new Event("change", {bubbles:true}));
}

let datasetLoadVersion = 0;
async function switchDataset(ds) {
  const loadVersion = ++datasetLoadVersion;
  state.ds = ds;
  if($("#datasetname")) $("#datasetname").textContent = (dsInfo().readonly ? "🔒 " : "✏️ ") + dsInfo().label;
  if($("#modpath")) $("#modpath").textContent = dsInfo().dir;
  document.body.classList.toggle("readonly", isRO());
  if (!state.store[ds]) state.store[ds] = { catalog: null, quickSelect:null, effectByKey: {}, loot: {}, matrix: null, shops:null };
  const st = state.store[ds];
  if (!st.catalog && dsInfo().catalog) {
    $("#main").replaceChildren(LexeditorUI.loadingPanel({label:"Loading dataset"}));
  }
  // Request independent data together, but publish it only after both complete.
  // Explicit dataset ids prevent a later UI selection from redirecting a request.
  const [catalog, quickSelect] = await Promise.all([
    st.catalog || (dsInfo().catalog ? api("/api/catalog", undefined, ds) : null),
    st.quickSelect || api("/api/quick-select", undefined, ds).catch(error=>({available:false,items:{},slotsByGroup:{},reason:error.message,activeFile:"quickselectitems.ymt"})),
  ]);
  st.catalog = catalog;
  st.quickSelect = quickSelect;
  if(catalog)for(const effect of catalog.effects)st.effectByKey[effect.key]=effect;
  if(loadVersion!==datasetLoadVersion)return;
  state.catalog = st.catalog;
  state.quickSelect = st.quickSelect;
  state.effectByKey = st.effectByKey;
  state.loot = st.loot;
  state.matrix = st.matrix;
  state.lootFile = [...dsInfo().lootFiles].sort((a,b)=>(LOOT_TAB_LABELS[a]||a).localeCompare(LOOT_TAB_LABELS[b]||b))[0] || null;
  const dlI = $("#dl-items"); dlI.innerHTML = "";
  if (st.catalog) {
    rebuildTagMaps(st.catalog);
    for (const it of [...st.catalog.items].sort((a, b) => a.key.localeCompare(b.key)))
      dlI.append(el("option", { value: it.key }));
  }
  if(!state.booting){
    await render();
    LexeditorUI.finishPluginLoading();
  }
}

async function boot() {
  try {
    const [config, labels, localization, alcohol, customCrafting] = await Promise.all([
      api("/api/config", undefined, "mine"),
      api("/api/labels", undefined, "mine"),
      api("/api/localization", undefined, "mine"),
      api("/api/alcohol-strengths", undefined, "mine").catch(error=>({available:false,file:null,entries:{},vanilla:{},overrides:{},reason:error.message})),
      api("/api/custom-crafting", undefined, "mine").catch(()=>({available:false,customFile:null,vanillaFile:null,vanilla:[],custom:[],errors:["Custom crafting API unavailable"]})),
    ]);
    Object.assign(state, {config, labels, localization, alcohol, customCrafting});
    state.customCraftingDraft = JSON.parse(JSON.stringify(state.customCrafting.custom||[]));
    const sel = $("#dsselect");
    if(sel) for (const [key, info] of Object.entries(state.config.datasets)) {
      const o = el("option", { value: key }, (info.readonly ? "🔒 " : "✏️ ") + info.label);
      if (key === state.ds) o.selected = true;
      sel.append(o);
    }
    if(sel) sel.addEventListener("change", () => switchDataset(sel.value));
    await switchDataset("mine");
  } catch (ex) {
    state.loadError = ex;
    throw ex;
  } finally {
    state.booting = false;
  }
  await render();
  LexeditorUI.finishPluginLoading();
}

function noData(msg) {
  const m = $("#main"); m.innerHTML = "";
  m.append(LexeditorUI.stack({fill:false,className:"lex-notice"}, msg));
}

async function loadLoot(file) {
  if (!state.loot[file]) {
    state.loot[file] = await api("/api/loot/" + file);
    state.loot[file].tables.forEach(t => { t.open = false; });
  }
  const dl = $("#dl-tables"); dl.innerHTML = "";
  for (const t of state.loot[file].tables) dl.append(el("option", { value: t.key }));
}

async function ensureAllLoot() {
  for (const file of dsInfo().lootFiles) await loadLoot(file);
  const dl = $("#dl-tables"); dl.innerHTML = "";
  for (const file of dsInfo().lootFiles)
    for (const t of state.loot[file].tables) dl.append(el("option", { value: t.key, label: file }));
}

function findLootTable(key) {
  for (const file of dsInfo().lootFiles) {
    const table = state.loot[file]?.tables.find(t => t.key === key);
    if (table) return { file, table };
  }
  return null;
}

// ---------- rendering ----------

function renderInfo(){
  $("#toolbar").replaceChildren(el("span",{},"RDR2 plugin information"));
  $("#main").replaceChildren(LexeditorUI.stack({fill:false,className:"lex-notice"},
    el("h2",{},"Ready"),
    el("p",{},"Installed game files and extracted reference data stay read-only. The mod selector in the top bar controls the editable mod."),
    el("p",{},`${Object.keys(state.config?.datasets||{}).length} source datasets are available to comparison controls.`)),
    LexeditorUI.modLoaderSection({
      loader:"Lenny's Mod Loader (LML) for data and assets, plus ScriptHookRDR2 for the ASI runtime.",
      output:"Edits are written into the mod folder LML loads. Generated ASI builds are installed beside the game executable only when you deploy them.",
      order:"LML applies mods in the order listed in its own configuration; a later mod editing the same file wins. ASI plugins load independently of that order.",
      safety:"Installed game archives and extracted reference data are read only. Nothing is written into the base RPF files.",
      removal:"Remove the mod folder from LML, and delete the ASI from the game folder if one was installed.",
    }));
}

function navigationState() {
  return {lexeditor:true,tab:state.tab,filters:JSON.parse(JSON.stringify(state.filters)),lootFile:state.lootFile,
    scrollX:window.scrollX,scrollY:window.scrollY};
}

function navigate(tab, filterChanges={}) {
  if (state.booting) return;
  history.replaceState(navigationState(),"",location.href);
  state.tab=tab;Object.assign(state.filters,filterChanges);
  history.pushState({...navigationState(),scrollX:0,scrollY:0},"",`#${tab}`);
  render().finally(()=>window.scrollTo(0,0));
}

function rdrHoverable({content,targetType,targetId,targetLabel,activate,className=""}) {
  return LexeditorUI.hoverable({content,targetType,targetId,targetLabel,activate,class:className});
}

function goToItem(key) {
  navigate("items",{q:key,category:"",group:"",itemSection:"all",itemSource:"all",itemSel:key,itemPage:0});
}

function goToRecipesUsing(key) {
  navigate("crafting",{craftIngredient:key,craftQ:""});
}

function goToRecipeOutput(key) {
  navigate("crafting",{craftOutput:key,craftIngredient:"",craftQ:""});
}

function goToItemShops(it,mode){
  navigate("shops",{shopMode:"workspace",shopBuyQ:it.key,shopSellQ:it.key,shopExact:""});
}

function goToEffect(key){
  navigate("effects",{effectSection:"effects",effQ:key,effectSel:key,effectPage:0});
}

function goToBehavior(id){
  navigate("effects",{effectSection:"behaviors",behaviorQ:id,behaviorSel:id,behaviorPage:0});
}

function goToLootTable(file,key){
  state.lootFile=file;navigate("loot",{lootQ:key,lootSel:key,lootPage:0});
}

function goToShop(type){
  navigate("shops",{shopMode:"workspace",shopType:type,shopSellCategory:"",shopSellSubcategory:""});
}

function itemLink(key,markOrigin=true,content=null) {
  const item=catalogItem(key);
  if(!item)return content??originDisplayName(key,null);
  const label=localizedValue(item.nameKey)||key;
  return rdrHoverable({content:content??originDisplayName(key,markOrigin?item:null),targetType:"rdr2-item",targetId:key,
    targetLabel:`${label} in Items`,activate:()=>goToItem(key),className:"item-link key"});
}

function effectLink(key,content=null){
  const effect=state.effectByKey[key];if(!effect)return content??effectDisplayName(key);
  const label=effectDisplayName(key);
  return rdrHoverable({content:content??label,targetType:"rdr2-effect",targetId:key,targetLabel:`${label} in Effects`,activate:()=>goToEffect(key)});
}

function behaviorLink(id,content=null){
  if(!behaviorChoices().includes(id))return content??id;
  const label=humanName("behaviors",id)||effectBehaviorName({id})||id;
  return rdrHoverable({content:content??label,targetType:"rdr2-behavior",targetId:id,targetLabel:`${label} in Behavior IDs`,activate:()=>goToBehavior(id)});
}

function lootTableLink(file,key,content=null){
  const found=findLootTable(key);if(!found||found.file!==file)return content??key;
  return rdrHoverable({content:content??key,targetType:"rdr2-loot-table",targetId:`${file}|${key}`,
    targetLabel:`${key} in Loot Tables`,activate:()=>goToLootTable(file,key)});
}

function shopLink(type,content=null){
  const exists=(state.shops?.shops||[]).some(shop=>shop.type===type)||(state.shopBuyers?.shops||[]).includes(type);
  if(!exists)return content??shopLabel(type);
  return rdrHoverable({content:content??shopLabel(type),targetType:"rdr2-shop",targetId:type,
    targetLabel:`${shopLabel(type)} in Shops`,activate:()=>goToShop(type)});
}

function weaponRecordLink(section,name,content=null){
  const record=state.weaponData[state.ds]?.[section]?.find(row=>row.name===name);
  if(!record)return content??name;
  const label=localizedValue(name)||name;
  return rdrHoverable({content:content??label,targetType:"rdr2-weapon-record",targetId:`${section}|${name}`,
    targetLabel:`${label} in ${section==="ammo"?"Ammo types":"Weapons"}`,activate:()=>navigate("weapons",{weaponSection:section,weapon:name,weaponQ:"",weaponFieldQ:""})});
}

function mobArchetypeLink(layer,name,content=null){
  const record=state.mobs?.[layer]?.records?.find(row=>row.name===name);
  if(!record)return content??name;
  return rdrHoverable({content:content??name,targetType:"rdr2-mob-archetype",targetId:`${layer}|${record.group}|${name}`,
    targetLabel:`${name} in Mobs`,activate:()=>navigate("mobs",{mobView:"archetypes",mobLayer:layer,mobGroup:record.group,mobQ:name})});
}

async function fillItemSources(it,list){
  let scriptRows=[];
  if(it.scriptReferenceCount){
    try{scriptRows=(await api(`/api/item-script-provenance?item=${encodeURIComponent(it.key)}`)).rows||[];}
    catch(error){scriptRows=[{type:"Script index unavailable",confidence:"error",detail:error.message,acquisition:false}];}
  }
  list.replaceChildren();
  const section=(title,rows)=>list.append(LexeditorUI.detailSection({title,body:LexeditorUI.stack({fill:false},...(rows.length?rows:["None indexed"]).map(row=>typeof row==="string"?LexeditorUI.detailNote(row):row))}));
  const provenanceRow=x=>el("div",{},
    el("b",{},x.type||"Reference"),
    x.confidence?el("span",{class:"cat"},` · ${x.confidence}`):"",
    x.file?el("div",{class:"cat"},`${x.file}${x.record?` · ${x.record}`:""}`):"",
    x.detail?el("div",{},x.detail):"",
    x.quantity?el("div",{class:"cat"},`quantity ${x.quantity}`):"",
    x.repeatable!==null&&x.repeatable!==undefined?el("div",{class:"cat"},x.repeatable?"repeatable":"one-time/limited"):"");
  section("Identity",[
    `Internal key: ${it.key}`,
    it.model?`Model: ${it.model}`:"Model: none declared",
    (it.textures||[]).length?`Icon: ${(it.textures||[]).map(t=>`${t.dict||"?"}/${t.id||"?"}`).join(", ")}`:"Icon: none declared",
    `Category/group: ${it.category||"?"} / ${it.group||"?"}`,
    (itemTagsOf(it)||[]).length?`Tags: ${itemTagsOf(it).map(tagDisplayLabel).join(", ")}`:"Tags: none"
  ]);
  section("Shops selling this item to you",(it.shopListings||[]).map(x=>rdrHoverable({
    content:el("span",{},`${shopLabel(x.shop)} · listing count ${x.quantities.join("/")}`),targetType:"rdr2-shop",targetId:x.shop,
    targetLabel:`${shopLabel(x.shop)} in Shops`,activate:()=>goToShop(x.shop)})));
  section("Crafting",craftView(it).map(x=>rdrHoverable({content:el("span",{},`${x.key} · yields ${x.yield}`),
    targetType:"rdr2-crafting-output",targetId:it.key,targetLabel:`${localizedValue(it.nameKey)||it.key} in Crafting`,
    activate:()=>goToRecipeOutput(it.key)})));
  section("Direct loot-table membership (reachability resolved below)",(it.lootSources||[]).map(x=>rdrHoverable({
    content:el("span",{},`${x.table} · rate ${x.rate??"default"}${x.min||x.max?` · qty ${x.min||"default"}–${x.max||x.min||"default"}`:""}${x.condition?` · ${x.condition}`:""}`),
    targetType:"rdr2-loot-table",targetId:`${x.file}|${x.table}`,targetLabel:`${x.table} in Loot Tables`,
    activate:()=>goToLootTable(x.file,x.table)})));
  section("Skinning yields",(it.skinningSources||[]).map(x=>`${x.animal} · ${x.skin}/${x.damage} · ×${x.qty}`));
  const provenance=it.provenanceSources||[];
  section("Confirmed acquisition paths",provenance.filter(x=>x.acquisition&&x.confidence==="confirmed").map(provenanceRow));
  section("Acquisition candidates",provenance.filter(x=>x.acquisition&&x.confidence!=="confirmed").map(provenanceRow));
  section("References only",[...provenance.filter(x=>!x.acquisition),...scriptRows.filter(x=>!x.acquisition)].map(provenanceRow));
  const summary=it.sourceSummary||{};
  section("Assessment",[
    summary.status==="confirmed"?`${summary.confirmed} confirmed source record(s)`:
      summary.status==="candidate"?`No confirmed source; ${summary.candidates} candidate record(s)`:
      "No source found in the currently indexed evidence",
    summary.possibleCutContent?"Possible cut content after exhaustive indexed coverage":"Not labelled cut content; at least one acquisition layer is incomplete or evidence exists"
  ]);
  section("Coverage",(state.catalog.provenanceCoverage||[]).map(x=>provenanceRow({type:x.layer,confidence:x.status,detail:x.detail,acquisition:false})));
  return list;
}

function pickerHost(){
  let root=document.getElementById("picker");
  if(!root){
    root=el("div",{id:"picker",class:"lex-dialog-backdrop",hidden:true});
    root.addEventListener("click",event=>{if(event.target===root)root.hidden=true});
    root.addEventListener("keydown",event=>{if(event.key==="Escape"){event.stopPropagation();root.hidden=true}});
    document.body.append(root);
  }
  return root;
}
function pickIdentifier(title, values, current, onPick) {
  const backdrop=pickerHost(); backdrop.innerHTML=""; backdrop.hidden=false;
  const panel=LexeditorUI.stack({fill:false,className:"lex-dialog",attrs:{role:"dialog","aria-modal":"true"}});
  const search=el("input",{type:"text",placeholder:`Search ${title.toLowerCase()}…`,value:""});
  const list=LexeditorUI.stack({fill:false});
  const normalize=v=>typeof v==="string"?{value:v,label:v}:v;
  const options=values.map(normalize);
  const draw=()=>{const q=search.value.trim().toUpperCase();list.innerHTML="";
    options.filter(v=>!q||`${v.label} ${v.value}`.toUpperCase().includes(q)).slice(0,400).forEach(v=>list.append(el("button",{class:"lex-dialog-action",onclick:()=>{onPick(v.value);backdrop.hidden=true;}},v.label)));
  };
  search.addEventListener("input",draw);
  panel.append(el("div",{class:"head"},el("b",{},title),el("span",{class:"cat",style:"margin-left:auto"},`${options.length} valid identifiers`)),search,list,
    el("button",{onclick:()=>backdrop.hidden=true},"Cancel"));backdrop.append(panel);draw();search.focus();
}

function recipesUsing(itemKey) {
  const found = [];
  for (const output of state.catalog.items)
    craftView(output).forEach((recipe, index) => {
      if (recipe.parts.some(p => p.item === itemKey)) found.push({ output, recipe, index });
    });
  return found;
}

// A page load may finish after the user selects another page or dataset.
// Call the returned check after each asynchronous read, before using the result.
let renderRevision=0;
const pageRevisions=new Map();
function renderScope(page){
  const revision=(pageRevisions.get(page)||0)+1;
  pageRevisions.set(page,revision);
  const navigation=renderRevision,tab=state.tab,dataset=state.ds;
  return ()=>navigation===renderRevision&&tab===state.tab&&dataset===state.ds&&revision===pageRevisions.get(page);
}

function render() {
  renderRevision++;
  document.querySelectorAll("nav button").forEach(b =>
    b.classList.toggle("active", b.dataset.tab === state.tab));
  if (state.booting) {
    document.body.classList.remove("loot-split-view");
    document.body.classList.remove("weapon-detail-view");
    document.body.classList.remove("shop-workspace-view");
    $("#main").replaceChildren(LexeditorUI.loadingPanel({label:"Loading editor data"}));
    refreshGlobalSave();
    return Promise.resolve();
  }
  // Record list-detail tabs keep fixed-height split panes. Weapons grows with its open
  // categories and uses the document scrollbar instead of a nested detail one.
  document.body.classList.toggle("loot-split-view",
    (state.tab==="loot" && state.lootFile!=="__matrix") || state.tab==="items" || state.tab==="crafting" || state.tab==="effects");
  document.body.classList.toggle("weapon-detail-view",state.tab==="weapons");
  document.body.classList.toggle("shop-workspace-view",
    state.tab==="shops" && state.filters.shopMode!=="report");
  if(state.renderedTab!==state.tab){
    const main=$("#main");
    if(main){main.scrollLeft=0;main.replaceChildren(LexeditorUI.loadingPanel());}
    state.renderedTab=state.tab;
  }
  const rendered=Promise.resolve(TABS[state.tab]()).finally(()=>installTabContext());
  refreshGlobalSave();
  return rendered;
}

function refreshGlobalSave() {
  const b=$("#global-save"), n=dirtyCount();
  b.disabled=isRO() || !n;
  b.title=n?`Save all ${n} unsaved change${n===1?"":"s"} to mod files`:"No unsaved mod-file changes";
  b.onclick=n?saveAllChanges:null;
  rdr2Shell?.refresh();
}

async function saveAllChanges() {
  if(isRO()||!dirtyCount())return;
  const originalLootFile=state.lootFile;
  try {
    if(Object.keys(state.settingEdits).length)await saveSettings();
    if(state.customCraftingDirty)await saveCustomCrafting();
    if(state.shopDirty.size)await saveShops();
    if(Object.keys(state.shopBuyerDirty).length)await saveShopBuyerOverrides();
    const catalogStores=["priceEdits","buyabilityEdits","sellabilityEdits","yieldEdits","bundleEdits",
      "itemEffectEdits","itemTagEdits","quickSelectEdits","descriptionKeyEdits","carryEdits","craftEdits","effectEdits","localizationEdits","alcoholEdits"];
    if(catalogStores.some(key=>Object.keys(state[key]).length))await saveCatalog();
    await saveLootSounds();
    await saveLoot();   // saves every dirty loot file itself
    state.lootFile=originalLootFile;
    if(state.matrixDirty.size)await saveMatrix();
    if(Object.keys(state.challengeEdits).length||Object.keys(state.challengeSourceEdits).length||Object.keys(state.challengeConditionEdits).length||
       Object.keys(state.challengeRewardEdits).length||Object.keys(state.challengeUiEdits).length||Object.keys(state.challengeModeEdits).length)await saveChallenges();
    for(const [key,map] of Object.entries(state.weaponEdits))if(Object.keys(map).length){
      const cut=key.indexOf("|"),section=key.slice(0,cut),name=key.slice(cut+1);
      const record=state.weaponData.mine?.[section]?.find(row=>row.name===name);
      await api("/api/weapons/save",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({section,name,sourceFile:record?.sourceFile,edits:Object.values(map)})});
      delete state.weaponEdits[key];
    }
    if(state.weaponShellVfxEdit!==null)await saveWeaponShellVfx();
    if(!Object.keys(state.weaponEdits).length)delete state.weaponData.mine;
    for(const [file,map] of Object.entries(state.aiEdits))if(Object.keys(map).length){
      await api("/api/ai/"+file+"/save",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({edits:Object.values(map)})});
      state.aiEdits[file]={};delete state.aiData[file];
    }
    if(Object.keys(state.mobEdits).length){
      await api("/api/mobs/save",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({edits:Object.values(state.mobEdits)})});
      state.mobEdits={};state.mobs=null;
    }
    if(Object.keys(state.crimeEdits).length||Object.keys(state.dispatchEdits).length)await saveCrime();
    if(Object.keys(state.bountyHunterEdits).length)await saveBountyHunters();
    if(Object.keys(state.honorActionEdits).length)await saveHonorActions();
    rdr2Shell.history?.clear();render();toast("All changes saved to mod files");
  } catch(ex) {
    state.lootFile=originalLootFile;refreshGlobalSave();showSaveFailure(ex);
  }
}

function savebar(onSave) {
  if (isRO()) {
    return LexeditorUI.stack({fill:false,className:"savebar"}, LexeditorUI.badge("Read-only reference"));
  }
  const n = dirtyCount();
  queueMicrotask(refreshGlobalSave);
  return LexeditorUI.stack({fill:false,className:"savebar"},
    el("span", { class: "dirty" }, n ? `${n} unsaved change${n > 1 ? "s" : ""} · use header SAVE` : ""));
}
