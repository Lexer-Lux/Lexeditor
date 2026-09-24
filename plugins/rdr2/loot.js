// ----- Loot tables -----
const LOOT_FILE_HELP = {
  "loot_table_ped.meta": "NPC archetypes, gangs, lawmen, and honor/event/gender conditions; usually points into item groups or rewards.",
  "loot_table_itemgroups.meta": "Reusable bundles that resolve table names into concrete inventory items.",
  "loot_table_reward.meta": "Money and other reusable reward bundles, including amount ranges.",
  "loot_table_container.meta": "World containers, wagons, saddlebags, and similar loot sources.",
  "loot_table_herb.meta": "Plant and herb harvesting drops.",
};
const LOOT_TAB_LABELS = {
  "loot_table_ped.meta":"Peds", "loot_table_itemgroups.meta":"Item Groups",
  "loot_table_reward.meta":"Rewards & Money", "loot_table_container.meta":"Containers",
  "loot_table_herb.meta":"Herbs",
};
const HERB_TABLE_NAMES={
  HERB_LOOT_ORCHID_ACUNA_STAR:"Acuna's Star Orchid",HERB_LOOT_ORCHID_CIGAR:"Cigar Orchid",
  HERB_LOOT_ORCHID_CLAMSHELL:"Clamshell Orchid",HERB_LOOT_ORCHID_GHOST:"Ghost Orchid",
  HERB_LOOT_ORCHID_LADY_OF_NIGHT:"Lady of the Night Orchid",HERB_LOOT_ORCHID_NIGHT_SCENTED:"Night Scented Orchid",
  HERB_LOOT_ORCHID_RAT_TAIL:"Rat Tail Orchid",HERB_LOOT_ORCHID_SPIDER:"Spider Orchid"
};
function lootTableName(t){return t.name||HERB_TABLE_NAMES[t.key]||"";}
// Entry types observed across vanilla loot tables. Only Table and Item resolve to a
// pickable name list; the rest are engine-interpreted and edited as free values.
const LOOT_ENTRY_TYPES=["Item","Table","Collectible","Money","Ammo","Horse","Weapon"];
function lootConditions(){const values=new Set();for(const file of Object.values(state.loot))for(const t of file.tables)for(const e of t.entries)if(e.rewardcondition)values.add(e.rewardcondition);return [...values].sort();}
// Only "Table" entries name another loot table; every other type names a catalog item.
// Treating Collectible/Money/Ammo as table references made save validation reject them.
function validLootNames(type){if(type!=="Table")return state.catalog.items.map(x=>x.key).sort();const out=[];for(const file of Object.values(state.loot))for(const t of file.tables)out.push(t.key);return [...new Set(out)].sort();}
// ----- Loot table usage ("where is this actually used?") -----
// Two independent answers, because loot tables are reached two different ways:
//   * data  - another loot table names this one; resolved live from the loaded files.
//   * script- the engine/script invokes it by name; baked by tools/build_loot_usage.py
//             because it requires scanning ~2,200 decompiled scripts.
function lootUsageOf(key){return state.lootUsage?.tables?.[key]||null;}

function lootDataRefs(key){
  const out=[];
  for(const [file,data] of Object.entries(state.loot||{})){
    if(!data?.tables)continue;
    for(const t of data.tables)
      if(t.entries.some(e=>e.type==="Table"&&e.name===key))out.push({file,key:t.key});
  }
  return out;
}

// Ordered most-specific first: a concrete world pickup beats a script name beats a guess.
function lootSourceCell(t){
  const cell=LexeditorUI.actionRow();
  const u=lootUsageOf(t.key), refs=lootDataRefs(t.key);
  const chip=(cls,text,title)=>LexeditorUI.badge(text,{title:title||"",tone:cls==="src-pickup"?"success":""});
  if(u?.pickups?.length)
    cell.append(chip("src-pickup","looted from "+u.pickups.join(", "),
      "The world prop you interact with. Script maps this model straight to this table."));
  if(u?.scripts?.length){
    const list=u.scripts;
    cell.append(chip("src-script",list.slice(0,3).join(", ")+(list.length>3?` +${list.length-3} more`:""),
      "Story-mode scripts that invoke this table by name:\n"+list.join("\n")));
  }
  if(u?.mpScripts?.length&&!u?.scripts?.length&&!u?.pickups?.length)
    cell.append(chip("src-mp","multiplayer only","Only referenced by online scripts; inert in story mode."));
  for(const r of refs.slice(0,4))
    cell.append(el("button",{type:"button",title:`Entry in ${r.file}`,
      onclick:ev=>{ev.stopPropagation();state.lootFile=r.file;state.filters.lootQ=r.key;renderLoot();}},"◂ "+r.key));
  if(refs.length>4)cell.append(chip("src-data",`+${refs.length-4} more tables`));
  if(!cell.childNodes.length)
    cell.append(chip("src-engine","engine-bound",
      "No loot table names it and no script invokes it by name. The engine selects it from the ped model, container archetype or plant it is attached to."));
  return cell;
}

function lootTabButtons(){
  const files=[...dsInfo().lootFiles].sort((a,b)=>(LOOT_TAB_LABELS[a]||a).localeCompare(LOOT_TAB_LABELS[b]||b));
  return LexeditorUI.subtabBar({active:state.lootFile,label:"Loot view",tabs:[{id:"__all",label:"All tables"},{id:"__sounds",label:"Pickup sounds"},...files.map(id=>({id,label:LOOT_TAB_LABELS[id]||id})),...(dsInfo().matrix?[{id:"__matrix",label:"Skinning"}]:[])],change:value=>{
    state.lootFile=value;state.filters.lootQ="";state.filters.lootPage=0;renderLoot();
  }});
}
async function renderLootSounds(){
  const current=renderScope("renderLootSounds");
  document.body.classList.remove("loot-split-view");
  $("#toolbar").replaceChildren(lootTabButtons(),savebar(saveLootSounds));
  const main=$("#main");main.replaceChildren(LexeditorUI.stack({fill:false,className:"lex-notice"},"Loading sound mappings…"));
  const data=await api("/api/loot-sounds");
  if(!current())return;
  if(state.tab!=="loot"||state.lootFile!=="__sounds")return;
  main.replaceChildren();
  if(!data.available){main.append(el("p",{},"Pickup sound data is missing. Prepare this game's reference files to edit it."));return;}
  const query=(state.lootSoundQuery||" ").trim().toLowerCase();
  const rows=data.rows.filter(row=>`${row.key} ${row.section} ${row.value}`.toLowerCase().includes(query));
  const selected=rows.find(row=>row.id===state.lootSoundSelected)||rows[0];
  state.lootSoundSelected=selected?.id;
  main.append(LexeditorUI.pagedListDetail({
    rows,key:row=>row.id,selected:selected?.id,noun:"mappings",pageSize:15,slots:true,
    page:state.lootSoundPage||0,change:view=>{
      state.lootSoundPage=view.page;state.lootSoundSelected=view.selected;
      if(view.reason!=="select"&&view.reason!=="sync")renderLootSounds();
    },
    splitKey:"rdr2-loot-sounds",defaultSplit:45,
    select:id=>{state.lootSoundSelected=id;},
    search:{value:state.lootSoundQuery||"",label:"Find pickup sound",change:value=>{
      state.lootSoundQuery=value;state.lootSoundPage=0;renderLootSounds();}},
    master:view=>LexeditorUI.columnList({rows:view.rows,key:row=>row.id,
      selected:view.selected,select:view.select,columns:[
        {key:"key",label:"Item"},{key:"section",label:"Section"},
        {key:"map",label:"Map",render:row=>String(row.map+1)}]}),
    detail:row=>{
      const label=row.section==="Sounds"?"Sound category":"Sound set";
      const choices=row.section==="Sounds"?data.categories:data.soundSets;
      const control=el("select",{"aria-label":label,disabled:isRO()?"":null,onchange:event=>{
        if(event.target.value===row.value)delete state.lootSoundEdits[row.id];
        else state.lootSoundEdits[row.id]=event.target.value;
        refreshGlobalSave();
      }},...choices.map(value=>el("option",{value,
        selected:value===((isRO()?undefined:state.lootSoundEdits[row.id])??row.value)},value)));
      return LexeditorUI.detailPanel({title:row.key,meta:row.section,body:[
        LexeditorUI.detailField({label,control,help:LexeditorUI.infoHelp("Choose the sound used when this item is picked up.")}),
        LexeditorUI.detailNote("Casing sounds: Tweaks → Spent Casings → Pickup Sound Name and Pickup Sound Set.")
      ]});
    }
  }));
}
async function saveLootSounds(){
  if(isRO())return 0;
  const edits=Object.entries(state.lootSoundEdits).map(([id,value])=>({id,value}));
  if(!edits.length)return 0;
  const result=await api("/api/loot-sounds/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});
  state.lootSoundEdits={};refreshGlobalSave();if(state.tab==="loot"&&state.lootFile==="__sounds")await renderLootSounds();return result.saved;
}
async function renderLoot() {
  const current=renderScope("renderLoot");
  if(state.lootFile==="__sounds")return renderLootSounds();
  if(state.lootFile==="__matrix"){
    document.body.classList.remove("loot-split-view");
    return renderMatrix();
  }
  document.body.classList.add("loot-split-view");
  const f = state.filters;
  const allView = state.lootFile === "__all";
  const tb = $("#toolbar"); tb.innerHTML = "";
  const canCreateGroup=!isRO()&&!allView&&state.lootFile&&state.lootFile!=="__matrix";
  tb.append(lootTabButtons());
  const lootFilters=[canCreateGroup?newButton({title:state.lootFile==="loot_table_itemgroups.meta"
      ?"Create a new reusable item group table in loot_table_itemgroups.meta"
      :"Create a new empty loot table in this file",
      onclick:()=>createLootTableDialog()}):el("span"),
    el("span",{class:"cat",title:allView?"every loot file":state.lootFile},allView?"all loot files":state.lootFile),
    savebar(saveLoot)];
  const m = $("#main"); m.innerHTML = "";
  if (!state.lootFile) { m.append(LexeditorUI.stack({fill:false,className:"lex-notice"}, `This dataset has no loot files yet (${dsInfo().dir}).`)); return; }
  if (!allView && !state.loot[state.lootFile]) {
    m.append(LexeditorUI.stack({fill:false,className:"lex-notice"}, "Loading…"));
    await loadLoot(state.lootFile);
  }
  if(!current())return;
  await ensureAllLoot();
  if(!current())return;
  if (!state.lootUsage) state.lootUsage = await api("/api/loot-usage").catch(() => ({ tables: {}, missing: true }));
  if(!current())return;
  m.innerHTML = "";
  for (const file of allView ? Object.keys(state.loot) : [state.lootFile])
    ensureRefLoot(file, () => { if (state.tab === "loot") renderLoot(); });

  if (state.lootUsage?.missing) m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},
    el("b",{},"Sources unavailable: "),"the RDR2 plugin service predates /api/loot-usage. Return to the Lexeditor main menu and reopen RDR2 to refresh it; table→table references below still work."));

  if(state.helpOpen.loot)m.append(el("div", { class: "hint" },
    el("b", {}, "How loot works: "),
    el("b", {}, "AggregateDrop"), " rolls every entry independently — Rate is that entry's own chance, and you can get several items at once. ",
    el("b", {}, "ContinuousLinearDrop"), " lays the rates end to end on a number line and rolls once, so the entries are mutually exclusive: rates summing to 1.0 always yield exactly one entry, and summing to less leaves the remainder as \"nothing\". ",
    "Entry type ", el("b", {}, "Table"), " rolls another table (expand it inline to edit); ", el("b", {}, "Item"), " drops that item directly. ",
    "Blank Min/Max means this entry does not override quantity.",
    el("div", { style: "margin-top:6px" }, allView
      ? el("span",{},el("b",{},"All tables: "),"every loot file at once. The Sources column says where each table is triggered from.")
      : el("span",{},el("b",{},state.lootFile + ": "), LOOT_FILE_HELP[state.lootFile] || "Loot table data.")),
    el("div", { style: "margin-top:6px" }, el("b", {}, "Not this tab: "),
      "lootconfigdata.meta controls looting interactions and QuickBehavior auto-pickups. damagecleanlinessdata.meta controls which weapon/damage combinations preserve animal quality.")));

  const q = f.lootQ.trim().toUpperCase();
  const files = allView ? Object.keys(state.loot) : [state.lootFile];
  let rows = [];
  for (const file of files)
    for (const t of (state.loot[file]?.tables||[])) rows.push({t, file});
  rows = rows.filter(({t}) =>
    !q || t.key.toUpperCase().includes(q) || lootTableName(t).toUpperCase().includes(q) ||
    t.entries.some(e => (e.name || "").toUpperCase().includes(q)));
  rows.sort((a,b)=>a.t.key.localeCompare(b.t.key));
  rows = sortedRows("loot",rows,{
    table:x=>x.t.key, name:x=>lootTableName(x.t), file:x=>x.file,
    type:x=>x.t.type||"", entries:x=>x.t.entries.length,
    sources:x=>lootUsageOf(x.t.key)?.kind||"engine"});

  // The shared paged list-detail preset keeps Loot Tables in the same fitted,
  // no-scroll master and fixed-pager contract as Items and Crafting.
  const view=LexeditorUI.pagedListDetail({
    modOnly:(()=>{const dirty=state.lootDirty[state.lootFile];
      return {available:!isRO(),value:state.modOnly===true,
        changed:row=>!!dirty&&dirty.has(row.t.key),
        change:value=>{state.modOnly=value;f.lootPage=0;renderLoot();}};})(),
    rows,key:row=>row.t.key,slots:false,page:f.lootPage,pageSize:f.lootPageSize,selected:f.lootSel,noun:state.lootFile==="loot_table_herb.meta"?"plant loot tables":"tables",
    splitKey:"rdr2-loot-tables",defaultSplit:44,
    search:{key:"rdr2-loot-tables",value:f.lootQ,placeholder:"Search tables… (e.g. VALENTINE, GANG)",change:value=>{f.lootQ=value;f.lootPage=0;renderLoot();}},filters:lootFilters,
    className:"lootsplit",fit:{rowSelector:".loot-item",headerSelector:".loot-listhead"},
    master:({rows,selected,select})=>LexeditorUI.columnList({
      rows,key:row=>row.t.key,selected,selectedClass:"sel",select,
      class:"loot-list loot-table-column-list",headerClass:"loot-listhead",
      sortState:state.sorts.loot,sort:key=>sharedTableSort("loot",key,renderLoot),rowClass:"loot-item",
      columns:[
        {key:"table",label:"Table",sortable:true,grow:1,render:({t,file})=>
          // One line, ellipsized. The file lives in the detail pane, not here.
          el("div",{class:"lex-inline-label",title:`${t.key}${lootTableName(t)?" — "+lootTableName(t):""}\n${LOOT_TAB_LABELS[file]||file}`},
            el("span",{class:"k"},t.key),
            lootTableName(t)&&lootTableName(t)!==t.key?el("span",{class:"li-name"},lootTableName(t)):"")},
        {key:"entries",label:"Entries",sortable:true,render:({t})=>String(t.entries.length)},
        {key:"type",label:"Drop type",sortable:true,render:({t})=>(t.type||"").replace("Drop","")}]
    }),
    detail:row=>lootDetail(row.t,row.file),
    emptyDetail:()=>LexeditorUI.stack({fill:false},LexeditorUI.stack({fill:false,className:"lex-notice"},"No tables match that search.")),
    sync:next=>{f.lootPage=next.page;f.lootPageSize=next.pageSize;f.lootSel=next.selected||"";},
    change:next=>{f.lootPage=next.page;f.lootPageSize=next.pageSize;f.lootSel=next.selected||"";renderLoot();}
  });
  m.append(view);
}

function markLootDirty(tableKey, file = state.lootFile) {
  (state.lootDirty[file] = state.lootDirty[file] || new Set()).add(tableKey);
  renderToolbarOnly();
}

// Which .meta a table key lives in, so nested edits mark the right file dirty.
function lootFileOf(key){
  for (const [file,data] of Object.entries(state.loot||{}))
    if (data?.tables?.some(t=>t.key===key)) return file;
  return state.lootFile;
}

function lootDetail(t, file) {
  const body=LexeditorUI.stack({fill:false});
  const u = lootUsageOf(t.key);
  const typeSel = el("select",{class:"droptype",title:
      "AggregateDrop: every entry rolled independently, several can hit at once.\n"+
      "ContinuousLinearDrop: one roll across the combined rates, entries are mutually exclusive.",
    onchange:ev=>{t.type=ev.target.value;markLootDirty(t.key,file);renderLoot();}},
    ...["AggregateDrop","ContinuousLinearDrop"].map(v=>{const o=el("option",{value:v},v);if(t.type===v)o.selected=true;return o;}));
  const deleteBtn=!isRO()?el("button",{class:"lex-ui-symbol icon-link",style:"color:#d77b70;width:auto;padding:0 8px",
    title:"Delete this table from the loot file. Refused if any other table still references it as a Table entry.",
    onclick:()=>deleteLootTableDialog(t,file)},"Delete"):el("span");
  body.append(LexeditorUI.detailField({label:"Drop type",control:refField(typeSel,[["V","vtag",state.store.vanilla?.loot?.[file]?.tables.find(x=>x.key===t.key)?.type??null],["K","ktag",state.store.kiddos?.loot?.[file]?.tables.find(x=>x.key===t.key)?.type??null]],t.type,v=>{t.type=v;markLootDirty(t.key,file);renderLoot()})}),
    lootRollSummary(t),LexeditorUI.detailSection({title:"Sources",body:lootSourceCell(t)}),lootEntryGrid(t,file,0,new Set([t.key])));
  return LexeditorUI.detailPanel({title:lootTableName(t)||t.key,meta:t.key,actions:deleteBtn,body});
}

async function createLootTableDialog(){
  if(isRO()||!state.lootFile||state.lootFile==="__all"||state.lootFile==="__matrix")return;
  const file=state.lootFile;
  const isGroups=file==="loot_table_itemgroups.meta";
  const raw=prompt(isGroups
    ?"New item-group key (e.g. LEX_MY_TONICS). Letters, numbers, underscores."
    :"New loot table key (e.g. LEX_CUSTOM_DROP). Letters, numbers, underscores.",
    isGroups?"LEX_":"LEX_");
  if(raw===null)return;
  const key=raw.trim().toUpperCase().replace(/[^A-Z0-9_]+/g,"_").replace(/_+/g,"_").replace(/^_|_$/g,"");
  if(!key){toast("Key is empty",true);return;}
  const dropType=confirm("OK = AggregateDrop (each entry rolls independently).\nCancel = ContinuousLinearDrop (mutually exclusive rates).")
    ?"AggregateDrop":"ContinuousLinearDrop";
  try{
    const r=await api(`/api/loot/${file}/create`,{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({key,type:dropType,name:key.replace(/_/g," ")})});
    if(!state.loot[file])state.loot[file]={tables:[]};
    state.loot[file].tables.push({...r.table,open:false});
    // Bust server cache is automatic on mtime; refresh local list order
    state.loot[file].tables.sort((a,b)=>a.key.localeCompare(b.key));
    state.filters.lootSel=r.table.key;
    state.filters.lootQ="";
    toast(`Created ${r.table.key}`);
    renderLoot();
  }catch(ex){toast("Create failed: "+ex.message,true);}
}

async function deleteLootTableDialog(t,file){
  if(isRO()||!t||!file)return;
  if(!confirm(`Delete loot table ${t.key} from ${file}?\n\nThis is permanent on Save... actually it writes immediately. Refused if other tables still reference it.`))
    return;
  try{
    // Flush pending entry edits for this table first so we don't re-save a deleted key.
    if(state.lootDirty[file])state.lootDirty[file].delete(t.key);
    await api(`/api/loot/${file}/delete`,{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({key:t.key})});
    state.loot[file].tables=state.loot[file].tables.filter(x=>x.key!==t.key);
    if(state.filters.lootSel===t.key)state.filters.lootSel="";
    toast(`Deleted ${t.key}`);
    renderLoot();
  }catch(ex){toast("Delete failed: "+ex.message,true);}
}

// Plain-language read of what one roll of this table yields, derived from the
// drop type and the rate total. Cheap to compute and it is the number that
// actually matters when you retune rates.
function lootRollSummary(t){
  const rates=t.entries.map(e=>parseFloat(e.rate)).filter(n=>!isNaN(n));
  if(!rates.length) return el("span",{class:"rollsum"},"");
  const sum=+rates.reduce((a,b)=>a+b,0).toFixed(3);
  if(t.type==="ContinuousLinearDrop"){
    if(sum<=1.001) return el("span",{class:"rollsum ok"},
      `one entry at most · ${Math.round(sum*100)}% something, ${Math.round((1-sum)*100)}% nothing`);
    return el("span",{class:"rollsum warn"},`rates total ${sum} — beyond 1.0 this yields multiple picks`);
  }
  const n=t.entries.length;
  return el("span",{class:"rollsum"},
    `${n} independent roll${n===1?"":"s"} · ${sum} item${sum===1?"":"s"} expected per open`);
}

// One editable grid of entries. Nested Table entries expand in place at depth+1 and
// edit the real child table, marking that child's own file dirty.
function lootEntryGrid(t, file, depth, seen) {
  const grid=LexeditorUI.stack({fill:false});
  // Match the reference entry by name, falling back to position. The fallback is what
  // makes a reference on the NAME field possible at all: when the name is the thing that
  // changed, a name-keyed lookup can never find its own counterpart.
  const refEntry=(entryName,i,ds)=>{
    const rt=state.store[ds]?.loot?.[file]?.tables.find(x=>x.key===t.key);
    if(!rt)return null;
    return rt.entries.find(x=>x.name===entryName) || rt.entries[i] || null;
  };
  const lootRefValue=(field,entryName,i,ds)=>{
    const en=refEntry(entryName,i,ds);
    return en?(en[field]??null):null;
  };
  const refPairs=(field,entryName,i)=>[["V","vtag",lootRefValue(field,entryName,i,"vanilla")],
    ["K","ktag",lootRefValue(field,entryName,i,"kiddos")],
    ...(hasScope("prices1899","loot",file)?[["1899","p1899tag",lootRefValue(field,entryName,i,"prices1899")]]:[])];
  t.entries.forEach((e,i)=>{
    const inp=(field,attrs={})=>el("input",{value:e[field]??"",...attrs,
      onchange:ev=>{e[field]=ev.target.value;ev.target.classList.add("edited");markLootDirty(t.key,file);
        if(field==="rate")renderLoot();}});
    const target=e.type==="Table"?findLootTable(e.name):null;
    const cyclic=target&&seen.has(target.table.key);
    // Nested tables are open by default; the toggle collapses them. Depth is capped so a
    // deep chain cannot render the whole file at once.
    const openKey=`${t.key}|${i}`;
    const isOpen=!state.lootCollapsed.has(openKey)&&depth<3;
    const expander=target&&!cyclic
      ? el("button",{type:"button",title:isOpen?"Collapse this table":"Expand this table",
          onclick:()=>{isOpen?state.lootCollapsed.add(openKey):state.lootCollapsed.delete(openKey);renderLoot();}},isOpen?"▾":"▸")
      : el("span",{});
    // Name and type are one decision, not two: picking a loot table makes the entry a
    // Table, picking a catalog item makes it an item kind. The type rides inside the name
    // control as a label so it cannot be set to something the name contradicts. The label
    // is still clickable, because Item/Collectible/Money/Ammo all name catalog items and
    // nothing in the name distinguishes them.
    const isTable=e.type==="Table";
    const setKind=kind=>{
      pickIdentifier(kind==="Table"?"Loot table":"Catalog item",validLootNames(kind),e.name,v=>{
        e.name=v;
        if(kind==="Table")e.type="Table";
        else if(e.type==="Table")e.type="Item";   // leaving Table: default to plain Item
        markLootDirty(t.key,file);renderLoot();});
    };
    const typeTag=el("button",{type:"button",title:isTable
        ? "This entry rolls another loot table. Click the name to point it somewhere else."
        : `Item kind: ${e.type}. Click to change between Item / Collectible / Money / Ammo / Weapon / Horse — these all name a catalog item, so the name alone cannot tell them apart.`,
      onclick:ev=>{ev.stopPropagation();
        if(isTable)return;
        pickIdentifier("Entry type",LOOT_ENTRY_TYPES.filter(x=>x!=="Table"),e.type,
          v=>{e.type=v;markLootDirty(t.key,file);renderLoot();});}},e.type||"?");
    const nameBtn=el("button",{class:"lex-ui-symbol icon-link",title:isTable?"Choose a different loot table":"Choose a different catalog item",
      onclick:()=>setKind(isTable?"Table":"Item")},"✎");
    const mention=isTable
      ? target?lootTableLink(target.file,target.table.key,el("span",{class:"nametext"},e.name)):el("span",{class:"badref",title:"No loot table with this name"},e.name||"!")
      : catalogItem(e.name)?itemLink(e.name,true,el("span",{class:"nametext"},e.name)):
        el("span",{class:"badref",title:"No catalog item with this name"},e.name||"(choose…)");
    const conditions=lootConditions();
    const conditionSel=el("select",{title:"Optional engine-defined reward condition",
      onchange:ev=>{e.rewardcondition=ev.target.value;markLootDirty(t.key,file);}},
      el("option",{value:""},"Always / no condition"),
      ...conditions.map(v=>{const o=el("option",{value:v},v);if(e.rewardcondition===v)o.selected=true;return o;}));
    const numeric=(field,attrs)=>{const control=inp(field,attrs);return refField(control,refPairs(field,e.name,i),e[field],value=>applyToControl(control,value))};
    grid.append(LexeditorUI.detailSection({title:`Entry ${i+1}`,body:[
      LexeditorUI.actionRow(expander,mention,typeTag,nameBtn,refStack(refPairs("name",e.name,i),e.name,v=>{e.name=v;markLootDirty(t.key,file);renderLoot()}),
        closeButton({title:"Remove entry",onclick:()=>{t.entries.splice(i,1);markLootDirty(t.key,file);renderLoot()}})),
      LexeditorUI.tileGrid([
        {label:"Rate",control:numeric("rate",{type:"number",step:"0.05",min:0})},
        {label:"Min",control:numeric("min",{type:"number",step:1,placeholder:"default",title:"Blank = do not override quantity."})},
        {label:"Max",control:numeric("max",{type:"number",step:1,placeholder:"default",title:"Blank = do not override quantity."})},
        {label:"Condition",control:refField(conditionSel,refPairs("rewardcondition",e.name,i),e.rewardcondition,v=>{e.rewardcondition=v;markLootDirty(t.key,file);renderLoot()})}].map(LexeditorUI.detailField),{minWidth:150})]}));
    if(cyclic) grid.append(LexeditorUI.detailNote(`↻ ${e.name} already appears higher in this chain`));
    if(target&&isOpen){
      const childFile=lootFileOf(target.table.key);
      grid.append(LexeditorUI.detailSection({title:target.table.key,body:[LexeditorUI.detailNote(`${target.table.type} · ${LOOT_TAB_LABELS[childFile]||childFile}`),lootEntryGrid(target.table,childFile,depth+1,new Set([...seen,target.table.key]))]}));
    }
  });
  // ContinuousLinearDrop is one roll across the combined rates, so whatever the rates do
  // not cover is a real outcome: nothing. Show it as a row rather than hiding the number
  // in a corner readout.
  if(t.type==="ContinuousLinearDrop"){
    const sum=+t.entries.map(e=>parseFloat(e.rate)||0).reduce((a,b)=>a+b,0).toFixed(3);
    const left=+(1-sum).toFixed(3);
    grid.append(LexeditorUI.detailField({label:"Nothing",control:LexeditorUI.readonlyField(left>=0?left.toFixed(2):"0.00"),help:fieldHelp("Automatic: 1.0 minus the rates above. This is the chance that no entry is selected. Rates above 1.0 can yield more than one entry.")}));
  }
  grid.append(LexeditorUI.actionRow(
    newButton({title:"Add a catalog item directly to this table",
      onclick:()=>pickIdentifier("Catalog item",validLootNames("Item"),"",name=>{t.entries.push({name,rate:"1.0",type:"Item"});markLootDirty(t.key,file);renderLoot();})}),
    newButton({title:"Add a reference that rolls another loot table or reusable Item Group",
      onclick:()=>pickIdentifier("Loot table",validLootNames("Table").filter(name=>name!==t.key),"",name=>{t.entries.push({name,rate:"1.0",type:"Table"});markLootDirty(t.key,file);renderLoot();})})));
  return grid;
}

// Saves every dirty loot file. Expanding a nested table edits whatever file that child
// lives in, so one session can dirty several files at once and state.lootFile is now a
// view selector ("__all") rather than the edit target.
async function saveLoot() {
  if (isRO()) return;
  const conditions = new Set(lootConditions());
  const pending = Object.entries(state.lootDirty).filter(([, d]) => d && d.size);
  if (!pending.length) return;
  const batches = [];
  for (const [file, dirty] of pending) {
    const edits = [...dirty].map(key => {
      const t = state.loot[file].tables.find(x => x.key === key);
      return { tableKey: key, entries: t.entries.filter(e => e.name) };
    });
    for (const edit of edits) for (const e of edit.entries) {
      if (!validLootNames(e.type).includes(e.name)) {
        throw showSaveFailure(new Error(`${e.name || "Blank name"} is not an existing ${e.type}.`)); }
      if (e.rewardcondition && !conditions.has(e.rewardcondition)) {
        throw showSaveFailure(new Error(`Unknown condition ${e.rewardcondition}.`)); }
    }
    batches.push({ file, edits });
  }
  try {
    let saved = 0;
    for (const { file, edits } of batches) {
      const r = await api(`/api/loot/${file}/save`, { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ edits }) });
      state.lootDirty[file] = new Set();
      saved += r.saved;
    }
    toast(`Saved ${saved} table(s) across ${batches.length} file(s)`);
    renderLoot();
  } catch (ex) { throw showSaveFailure(ex); }
}

// ----- Skinning matrix -----
async function renderMatrix() {
  const current=renderScope("renderMatrix");
  const f = state.filters;
  if (!dsInfo().matrix) return noData(`This dataset has no loot_items_matrix.meta yet (${dsInfo().dir}).`);
  const st = state.store[state.ds];
  if (!st.matrix) st.matrix = await api("/api/matrix");
  if(!current())return;
  state.matrix = st.matrix;
  await ensureRefMatrix();
  if(!current())return;
  const tb = $("#toolbar"); tb.innerHTML = "";
  const animals = [...state.matrix.animals].sort((a, b) => a.key.localeCompare(b.key));
  const animalQuery = (f.animalQ || "").trim().toUpperCase();
  const filteredAnimals = animals.filter(a => !animalQuery || a.key.toUpperCase().includes(animalQuery));
  if ((!f.animal || !animals.some(a => a.key === f.animal)) && animals.length) f.animal = animals[0].key;
  if (animalQuery && filteredAnimals.length && !filteredAnimals.some(a => a.key === f.animal))
    f.animal = filteredAnimals[0].key;
  tb.append(
    lootTabButtons(),
    el("input", { type: "text", placeholder: "Filter animals…", value: f.animalQ || "", style: "width:180px",
      oninput: ev => { f.animalQ = ev.target.value; filterRerender(ev,renderMatrix); } }),
    el("select", { onchange: ev => { f.animal = ev.target.value; renderMatrix(); } },
      ...filteredAnimals.slice(0, 600)
        .map(a => { const o = el("option", { value: a.key }, a.key); if (a.key === f.animal) o.selected = true; return o; })),
    el("span", { class: "count" }, animalQuery ? `${filteredAnimals.length} of ${animals.length} animals` : `${animals.length} animals`),
    savebar(saveMatrix));
  const m = $("#main"); m.innerHTML = "";
  if (state.helpOpen.loot) m.append(el("div", { class: "hint" },
    el("b", {}, "Skinning yields: "), "what an animal gives when skinned, based on ",
    el("b", {}, "DamageQuality"), " (the kill-quality result from weapon/damage cleanliness rules) × ", el("b", {}, "SkinQuality"),
    " (the animal's inherent Poor/Good/Perfect quality, plus special Rare/Legendary variants). Change the yielded item or quantity to change results."));
  if (animalQuery && !filteredAnimals.length) {
    m.append(LexeditorUI.stack({fill:false,className:"lex-notice"}, `No animals match “${f.animalQ}”.`));
    return;
  }
  const a = animals.find(x => x.key === f.animal);
  if (!a) return;
  const yieldSortLabel = (key,label) => { const cur=state.sorts.matrix, active=cur?.key===key;
    return el("span",{class:`header-label yield-sort${active?" sorted":""}`,
      onclick:()=>{state.sorts.matrix={key,dir:active?-cur.dir:1};renderMatrix();}},
      label, active?el("span",{class:"lex-ui-symbol"},cur.dir>0?" ▼":" ▲"):""); };
  // The yields render as a nested grid inside one cell, so that column's own
  // heading uses the same grid or "Item given"/"Qty" float free of the controls
  // they label.
  const yieldHead=()=>LexeditorUI.actionRow(yieldSortLabel("item","Item given"),yieldSortLabel("qty","Quantity"));
  const matrixRows=[];
  const stars=q=>{const n={Poor:1,Good:2,Perfect:3}[q];return LexeditorUI.badge(n===undefined?q.toUpperCase():"★".repeat(n)+"☆".repeat(3-n),{title:q})};
  const qualSel = (row, field) => el("span", {}, el("select", { onchange: ev => { row[field] = ev.target.value; state.matrixDirty.add(a.key); renderMatrix(); } },
    ...["Poor", "Good", "Perfect",...(field==="skin"?["Rare","Legendary"]:[])].map(v => { const o = el("option", { value: v }, v); if (row[field] === v) o.selected = true; return o; })), stars(row[field]));
  const rank = {Poor:1, Good:2, Perfect:3, Rare:4, Legendary:5};
  // Preserve each loaded row's identity across item edits so its V/K reset
  // remains available after the current item key no longer matches either
  // reference dataset. Non-enumerable metadata never enters the save payload.
  for (const row of a.rows) if (!Object.hasOwn(row, "_referenceItem"))
    Object.defineProperty(row, "_referenceItem", { value: row.item, enumerable: false });
  let groups = [...a.rows.reduce((map,row)=>{const key=`${row.damage}|${row.skin}`;if(!map.has(key))map.set(key,{damage:row.damage,skin:row.skin,rows:[]});map.get(key).rows.push(row);return map;},new Map()).values()];
  if(!state.sorts.matrix)groups.sort((x,y)=>rank[x.skin]-rank[y.skin]||rank[x.damage]-rank[y.damage]);
  groups=sortedRows("matrix",groups,{damage:x=>rank[x.damage]??0,skin:x=>rank[x.skin]??0,item:x=>x.rows.map(r=>localizedValue(state.catalog.items.find(i=>i.key===r.item)?.nameKey)||r.item).sort()[0]||"",qty:x=>x.rows.reduce((n,r)=>n+(+r.qty||0),0)});
  groups.forEach(group => {
    const row=group.rows[0];
    const groupQualSel=field=>el("span",{},el("select",{onchange:ev=>{group.rows.forEach(r=>r[field]=ev.target.value);state.matrixDirty.add(a.key);renderMatrix();}},
      ...["Poor","Good","Perfect",...(field==="skin"?["Rare","Legendary"]:[])].map(v=>{const o=el("option",{value:v},v);if(group[field]===v)o.selected=true;return o;})),stars(group[field]));
    const matrixRef = ds => {
      const animal = state.store[ds]?.matrix?.animals.find(x => x.key === a.key);
      return animal?.rows.find(x => x.damage === row.damage && x.skin === row.skin && x.item === row.item) ||
        animal?.rows.find(x => x.damage === row.damage && x.skin === row.skin) || null;
    };
    const yields=LexeditorUI.stack({fill:false});
    group.rows.sort((x,y)=>x.item.localeCompare(y.item)).forEach(yieldRow=>{
      const referenceItem=yieldRow._referenceItem;
      const vr=state.store.vanilla?.matrix?.animals.find(x=>x.key===a.key)?.rows.find(x=>x.damage===yieldRow.damage&&x.skin===yieldRow.skin&&x.item===referenceItem);
      const kr=state.store.kiddos?.matrix?.animals.find(x=>x.key===a.key)?.rows.find(x=>x.damage===yieldRow.damage&&x.skin===yieldRow.skin&&x.item===referenceItem);
      const applyYieldReference = ref => {
        if (!ref) return;
        yieldRow.item = ref.item;
        yieldRow.qty = ref.qty ?? 1;
        state.matrixDirty.add(a.key);
        renderMatrix();
      };
      const quantity=el("input",{type:"number",step:1,min:1,value:yieldRow.qty??1,placeholder:"1",onchange:ev=>{yieldRow.qty=Math.max(1,Math.round(+ev.target.value||1));state.matrixDirty.add(a.key);renderToolbarOnly()}});
      yields.append(LexeditorUI.stack({fill:false},LexeditorUI.controlGroup([
        {label:"Item",control:linkedCatalogKeyEditor(yieldRow.item,value=>{yieldRow.item=value;state.matrixDirty.add(a.key);renderMatrix()})},
        {label:"Quantity",control:quantity},
        closeButton({title:"Remove yield",onclick:()=>{a.rows.splice(a.rows.indexOf(yieldRow),1);state.matrixDirty.add(a.key);renderMatrix()}})]),
        refLine([["V","vtag",vr?`${vr.item} ×${vr.qty??1}`:null],["K","ktag",kr?`${kr.item} ×${kr.qty??1}`:null]],v=>v,
          value=>applyYieldReference(vr&&value===`${vr.item} ×${vr.qty??1}`?vr:kr))));
    });
    yields.append(LexeditorUI.actionRow(newButton({title:"Add yield",onclick:()=>{a.rows.push({damage:group.damage,skin:group.skin,item:"",qty:1});state.matrixDirty.add(a.key);renderMatrix();}})));
    matrixRows.push({group,yields,qual:groupQualSel});
  });
  m.append(columnList({class:"matrix-table",align:"start",headerAlign:"start","aria-label":"Yields by quality",
    rows:matrixRows,key:({group})=>`${group.damage}|${group.skin}`,editable:true,localSort:false,
    template:"minmax(140px,1fr) minmax(140px,1fr) minmax(0,3fr)",
    columns:[{key:"damage",label:()=>el("span",{},"Damage quality",fieldHelp("Kill cleanliness/appropriateness resolved using damagecleanlinessdata.meta; independent of the animal's starting star quality.")),
        render:row=>row.qual("damage")},
      {key:"skin",label:()=>el("span",{},"Skin quality",fieldHelp("The animal's inherent quality: Poor=1 star, Good=2, Perfect=3. Rare and Legendary are separate special values, not zero-star Poor.")),
        render:row=>row.qual("skin")},
      {key:"yields",label:yieldHead,sortable:false,render:row=>row.yields}]}));
  m.append(el("div", { class: "addrow", style: "margin-top:10px" },
    newButton({title:"Add matrix row",onclick: () => {
      a.rows.push({ damage: "Poor", skin: "Poor", item: "", qty: 1 });
      state.matrixDirty.add(a.key); renderMatrix();
    }})));
}
