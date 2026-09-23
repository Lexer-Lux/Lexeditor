"use strict";
  function recordPanel(row=selectedRecord()){
    if(!row)return detailPanel({className:"ff7r-detail",title:"No record",body:[detailSection({title:"DATA",body:[detailNote("This DataObject has no rows.")]})]});
    const spec=curatedSpec(state.tab);
    const prefs=spec?curatedPrefs(spec):dataPreferences();
    const fields=state.data.properties.map(prop=>detailField({label:prop.label,control:propertyControl(row,prop),dataType:prop.array?`${semanticType(prop)}[]`:semanticType(prop),min:semanticMin(prop),max:semanticMax(prop),help:propertyHelp(prop),pin:prefs.pinButton(propertyColumnKey(prop),prop.label)}));
    return detailPanel({className:"ff7r-detail",title:row.tag||"Unnamed record",meta:currentAsset()?.name||state.asset,body:[detailSection({title:"PROPERTIES",body:fields})]});
  }
  function tablePanel(){const rows=sortedRows();return columnList({rows,key:row=>row.id,selected:state.selected,select:row=>{state.selected=row.id;render()},sortState:state.sort,sort:key=>{state.sort=state.sort.key===key?{key,dir:-state.sort.dir}:{key,dir:1};render()},columnPreferences:dataPreferences(),columns:dataTableColumns(),class:"ff7r-table","aria-label":"FF7 Remake DataObject records"})}
  function assetToolbar(){const select=el("select",{"aria-label":"FF7 Remake misc data table",onchange:event=>selectAsset(event.target.value),disabled:state.busy});for(const item of (state.tab==="tweaks"?tweakAssets():gameAssets())){const label=item.group?`${item.group} / ${item.name}`:item.name;const option=el("option",{value:item.asset},label);option.selected=item.asset===state.asset;select.append(option)}return LexeditorUI.toolbar(el("label",{},"Table"),select)}
  function dataPanel(){if(state.busy&&state.tab==="data")return loadingPanel("Loading DataObject","Reading the selected gameplay .uasset/.uexp pair…");if(state.error&&!state.data)return errorPanel(state.error);return LexeditorUI.stack(assetToolbar(),pagedDataPanel())}
  // The DataObject list uses the shared paged Table + Detail, so its search and
  // paging live in the standard bottom bar instead of a private top strip.
  // Tweaks are settings, not records, and they are not seventeen destinations
  // either. Every group is loaded up front and laid out on one scrolling page
  // in as many columns as the window allows, which is the shape RDR2 uses. No
  // subtab bar to walk, no dropdown to pick a group from, and no load between
  // reading one switch and the next.
  function tweaksPanel(){
    const list=tweakAssets();
    if(!list.length)return loadingPanel("Tweaks","No Lexeditor tweak groups were found in the catalog.");
    if(!state.tweaks||(!Object.keys(state.tweaks).length&&state.tweaksPending))
      return loadingPanel("Loading tweaks",`Reading ${state.tweaksPending} tweak group${state.tweaksPending===1?"":"s"}…`);
    if(state.tweaksError&&!Object.keys(state.tweaks).length)return errorPanel(state.tweaksError);
    const cards=list.map(item=>tweakCard(state.tweaks[item.asset])).filter(Boolean);
    if(state.tweaksPending)cards.push(el("section",{class:"ff7r-card ff7r-tweaks-pending"},
      el("h3",{},`${state.tweaksPending} more group${state.tweaksPending===1?"":"s"} still reading`),
      el("p",{},"These take longer to read than the rest and will appear here when they arrive.")));
    cards.push(LexeditorUI.reshadeSection({snapshot:state.reshade,save:saveReshade,act:actReshade}));
    return LexeditorUI.stack(
      LexeditorUI.settingsColumns(cards,{className:"ff7r-tweaks"}));
  }
  // A group with one record shows its properties by name. A group with several
  // names each row, because the row is the thing being configured.
  function tweakCard(entry){
    if(!entry)return null;
    const {item,data}=entry;
    const title=String(item.name||item.asset.split("/").pop()).toLocaleUpperCase();
    if(!data?.records?.length)return detailSection({title,body:[detailField({
      label:"STATE",control:readonlyField("This tweak group exposes no settings.")})]});
    const fieldsOf=row=>data.properties.map(prop=>detailField({
      label:prop.label,
      control:propertyControl(row,prop,data),
      dataType:prop.array?`${semanticType(prop)}[]`:semanticType(prop),
      min:prop.min,max:prop.max,help:propertyHelp(prop)}));
    // A group with several records nests one titled block per record. Naming
    // the record inside each property label instead produced a compound name
    // no property lane could hold, and the label fitter shrank it to a smudge.
    const body=data.records.length>1
      ? data.records.map(row=>detailSection({
          title:String(row.tag||`#${row.id}`),body:fieldsOf(row)}))
      : fieldsOf(data.records[0]);
    return detailSection({title,body});
  }
  // Seventeen small DataObjects, read together. They are requested in parallel
  // because the page cannot show anything until the last of them arrives.
  async function loadAllTweaks(){
    const list=tweakAssets();
    if(!list.length){state.tweaks={};return}
    // Each group appears as it arrives. Waiting for the last of them meant one
    // slow asset held the whole page: NoMoreCheats takes the better part of a
    // minute to read while the other five are back inside a second, so the tab
    // sat on "Reading every Lexeditor tweak group" long enough to look hung.
    state.tweaksError="";
    state.tweaks=state.tweaks||{};
    state.tweaksBusy=false;
    state.tweaksPending=list.length;
    render();
    await Promise.all(list.map(async item=>{
      try{
        const data=await api(`/api/data?asset=${encodeURIComponent(item.asset)}${sourceSuffix()}&language=${encodeURIComponent(state.textLanguage||"US")}`);
        state.tweaks[item.asset]={item,data,baseline:clone(data)};
      }catch(error){state.tweaksError=error.message}
      finally{
        state.tweaksPending=Math.max(0,(state.tweaksPending||1)-1);
        if(state.tab==="tweaks")render();
      }
    }));
    state.tweaksPending=0;render();refreshShell()
  }
  function tweakEditGroups(){
    if(state.activeSource!=="mine"||!state.tweaks)return[];
    return Object.values(state.tweaks)
      .map(entry=>({entry,edits:diffRecords(entry.data,entry.baseline)}))
      .filter(group=>group.edits.length);
  }
  async function loadReshade(){
    try{const value=await LexeditorUI.callWindow?.("mod_reshade","ff7r");if(value)state.reshade=value}
    catch(_error){/* browser preview has no desktop host; the section still renders */}
  }
  // Install, remove and "choose the DLL" each answer with a fresh snapshot.
  async function actReshade(method,...args){
    try{
      const value=method==="adopt_reshade"
        ? await LexeditorUI.callWindow?.(method)
        : await LexeditorUI.callWindow?.(method,"ff7r",...args);
      if(value&&value.manifest)state.reshade=value;else await loadReshade();
    }catch(error){LexeditorUI.showToast?.(error.message||String(error),true);}
    render();
  }
  async function saveReshade(manifest){
    try{const value=await LexeditorUI.callWindow?.("save_mod_reshade","ff7r",manifest);if(value)state.reshade=value}
    catch(error){LexeditorUI.showToast?.(error.message||String(error),true)}
    render();
  }
  // "Mod contents only" hides everything this mod does not touch. For a data
  // table that means the rows whose values differ from the vanilla baseline the
  // editor loaded, which is exactly what a save would write.
  function modOnlyAvailable(){return state.activeSource==="mine"&&!!state.dataBaseline}
  function recordChangedFromVanilla(record){
    const baseline=state.dataBaseline?.records?.[record.entry??record.index];
    const base=baseline||state.dataBaseline?.records?.find(row=>row.id===record.id);
    if(!base)return true;
    for(const prop of state.data?.properties||[]){
      if(JSON.stringify(record.values[prop.name])!==JSON.stringify(base.values[prop.name]))return true;
    }
    return false;
  }
  // The toggle itself, its place on the pagination bar and the page reset are
  // the shared table's job now. FF7R only says whether it can tell and how.
  function modOnlySpec(recordOf){
    return {available:modOnlyAvailable(),value:state.modOnly===true,
      changed:row=>recordChangedFromVanilla(recordOf?recordOf(row):row),
      change:value=>{state.modOnly=value;
        for(const key of Object.keys(state.pages))state.pages[key]=0;render()}};
  }
