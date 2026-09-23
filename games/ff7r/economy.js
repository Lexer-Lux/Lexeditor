"use strict";
  function economyTables(){return(state.economy?.tables||[]).filter(table=>table.available)}
  function currentEconomyTable(){return economyTableFor(state.tab)||economyTables().find(table=>table.asset===state.economyTable)||economyTables()[0]||null}
  function economySemanticRow(tag){return currentEconomyTable()?.rows?.find(row=>row.id===tag)||null}
  function economyViewRows(){const q=state.economyQuery.toLocaleLowerCase(),buy=property("BuyValue"),sale=property("SaleValue"),maxCount=property("MaxCount");return records().map(record=>{const semantic=economySemanticRow(record.tag);return{record,tag:record.tag,name:semantic?.name||record.tag,buy:buy?record.values[buy.name]:"—",sale:sale?record.values[sale.name]:"—",maxCount:maxCount?record.values[maxCount.name]:"—"}}).filter(row=>!q||`${row.tag} ${row.name} ${row.buy} ${row.sale} ${row.maxCount}`.toLocaleLowerCase().includes(q)).sort((a,b)=>compareValues(a[state.economySort.key],b[state.economySort.key])*state.economySort.dir)}
  function economyTablePanel(){const rows=economyViewRows();return columnList({rows,key:row=>row.record.id,selected:state.selected,select:row=>{state.selected=row.record.id;render()},sortState:state.economySort,sort:key=>{state.economySort=state.economySort.key===key?{key,dir:-state.economySort.dir}:{key,dir:1};render()},columnPreferences:economyPrefs,columns:economyColumns,class:"ff7r-table","aria-label":"FF7 Remake item prices and carry capacity"})}
  function economyRecordPanel(row=selectedRecord()){
    const table=currentEconomyTable();if(!row||!table)return loadingPanel("Item settings","No editable item-setting rows were found.");const semantic=economySemanticRow(row.tag);const fields=[detailField({label:"DATA ID",control:readonlyField(row.tag),pin:economyPrefs.pinButton("tag","ID")})];
    const specs=[["BuyValue","BUY PRICE"],["SaleValue","SELL PRICE"],["CanSale","CAN SELL"],["MaxCount","MAX CARRY"]];for(const[name,label]of specs){const prop=property(name);if(prop){let help=null;if(name==="BuyValue")help=infoHelp("The installed FF7R table exposes BuyValue directly; this control writes that same DataObject field.");else if(name==="MaxCount")help=infoHelp("FF7R's Item/Equipment schema exposes MaxCount as the inventory carry/stack cap; this control writes that authoritative DataObject field.");fields.push(detailField({label,control:propertyControl(row,prop),dataType:semanticType(prop),min:name==="CanSale"?undefined:semanticMin(prop),max:name==="CanSale"?undefined:semanticMax(prop),help}))}}
    if(semantic?.textId)fields.splice(1,0,detailField({label:"TEXT ID",control:readonlyField(semantic.textId)}));
    // The description is the same text resource the name comes from, so it is
    // shown here and edited on the Text tab rather than duplicated as a second
    // editable copy that could disagree with the resource.
    if(semantic?.descriptionId)fields.push(detailField({label:"DESCRIPTION",
      control:descriptionControl(semantic),
      help:infoHelp("An item's description is one entry in the FF7R text resource that its name also comes from. Editing it here edits that entry: the Text tab shows the same record with the same pending change, and saving writes it into the resource. When another resource is loaded with unsaved changes this stays read-only rather than replacing it, and the button opens the entry on the Text tab.")}));
    return detailPanel({className:"ff7r-detail",title:semantic?.name||row.tag,identity:recordId(row.id),meta:table.name||"Item settings",body:[detailSection({title:"ITEM SETTINGS",body:fields})]});
  }
  // Descriptions live in resident_txtres for the current language, the same
  // resource an item's name comes from. There is exactly one of those per
  // language, so the Items tab loads it as the tab's text resource and the
  // description is edited here, in the item, against that one loaded copy.
  // Nothing is duplicated: the Text tab shows the same record with the same
  // pending edit, and the existing text save writes it.
  const residentTextAsset=()=>textAssets().find(row=>
    row.language===state.textLanguage
    && String(row.name||"").toLocaleLowerCase()==="resident_txtres");
  function descriptionRecord(descriptionId){
    if(!descriptionId)return null;
    const resident=residentTextAsset();
    const pack=resident?state.textPacks?.[resident.asset]:null;
    if(!pack)return null;
    return pack.data.records.find(row=>row.key===descriptionId)||null;
  }
  // Opening an item view brings that language's resident text with it. That is
  // the one resource an item's name and description live in, and having it
  // loaded is what lets the description be edited in the item rather than on
  // another tab.
  async function ensureResidentText(){
    const resident=residentTextAsset();
    if(!resident||state.textPacks?.[resident.asset])return;
    await loadTextAsset(resident.asset);
  }
  function descriptionControl(semantic){
    const record=descriptionRecord(semantic.descriptionId);
    if(record&&state.activeSource==="mine"){
      const box=LexeditorUI.textArea({rows:2,
        "aria-label":`Description for ${semantic.name||semantic.textId||"this item"}`,
        oninput:event=>{record.text=event.target.value;refreshShell()}});
      box.value=record.text??"";
      return box;
    }
    const shown=(record?record.text:semantic.description)
      || `(${state.textLanguage||"US"} has no text for ${semantic.descriptionId})`;
    return LexeditorUI.actionRow(detailNote(shown),
      el("button",{type:"button",
        title:`Open ${semantic.descriptionId} on the Text tab`,
        onclick:()=>editDescription(semantic.descriptionId)},"Edit text…"));
  }
  async function editDescription(textId){
    state.textQuery=String(textId||"");
    state.pages.text=0;
    await navigate("text");
    // The entry is in whichever resource holds this language's item text. If
    // the loaded one does not have it, the search box still says what to look
    // for rather than leaving the player guessing.
    const match=textRecords().find(row=>row.key===textId);
    if(match)state.textSelected=match.id;
    render();
  }
  function economyPanel(){if(state.busy&&isEconomyTab(state.tab))return loadingPanel("Loading item settings","Discovering installed FF7R Item/Equipment/Materia tables…");if(state.economyError)return errorPanel(state.economyError);if(state.economy&&!state.economy.available)return loadingPanel("Item settings unavailable","The installed FF7R archives did not expose a validated Item/Equipment/Materia table containing BuyValue, SaleValue, CanSale, or MaxCount.");const table=currentEconomyTable();if(!table)return loadingPanel("Item settings","Open this tab to discover installed FF7R item tables.");if(state.data?.asset!==table.asset)return loadingPanel("Loading item table","Reading the selected item DataObject…");return LexeditorUI.stack(pagedTable({id:`economy-${state.tab}`,noun:"items",
      modOnly:modOnlySpec(row=>row.record),
      rows:economyViewRows(),key:row=>row.record.id,selected:state.selected,
      setSelected:row=>{state.selected=row.record.id},
      query:state.economyQuery,setQuery:value=>{state.economyQuery=value},
      searchLabel:"Search FF7 Remake items",searchPlaceholder:"Search items and IDs",
      sortState:state.economySort,sort:key=>{state.economySort=state.economySort.key===key?{key,dir:-state.economySort.dir}:{key,dir:1};render()},
      prefs:economyPrefs,columns:economyColumns,ariaLabel:"FF7 Remake item prices and carry capacity",
      split:45,minLeft:380,minRight:420,detail:()=>economyRecordPanel()}))}
