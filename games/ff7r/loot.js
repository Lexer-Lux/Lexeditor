"use strict";
  function lootChoiceName(id){return state.loot?.itemChoices?.find(choice=>choice.id===id)?.name||id}
  function lootSpec(kind){return state.loot?.groups?.find(group=>group.kind===kind)||null}
  function lootSummary(record,spec){if(!spec)return"—";const items=record.values[spec.itemProperty]||[],chances=spec.percentProperty?(record.values[spec.percentProperty]||[]):[],quantities=spec.quantityProperty?(record.values[spec.quantityProperty]||[]):[];if(!items.length)return"—";return items.map((item,index)=>{let suffix="";if(index<chances.length)suffix=` ${chances[index]}%`;else if(index<quantities.length)suffix=` [${quantities[index]}]`;return`${lootChoiceName(item)}${suffix}`}).join(", ")}
  function lootViewRows(){const q=state.lootQuery.toLocaleLowerCase();return records().map(record=>({record,tag:record.tag,normal:lootSummary(record,lootSpec("normal")),rare:lootSummary(record,lootSpec("rare")),steal:lootSummary(record,lootSpec("steal"))})).filter(row=>!q||`${row.tag} ${row.normal} ${row.rare} ${row.steal}`.toLocaleLowerCase().includes(q)).sort((a,b)=>compareValues(a[state.lootSort.key],b[state.lootSort.key])*state.lootSort.dir)}
  function lootTablePanel(){const rows=lootViewRows();return columnList({rows,key:row=>row.record.id,selected:state.selected,select:row=>{state.selected=row.record.id;render()},sortState:state.lootSort,sort:key=>{state.lootSort=state.lootSort.key===key?{key,dir:-state.lootSort.dir}:{key,dir:1};render()},columnPreferences:lootPrefs,columns:lootColumns,class:"ff7r-table","aria-label":"FF7 Remake enemy drops and steals"})}
  function lootSlotControl(row,spec,index){
    const itemProp=property(spec.itemProperty);
    if(!itemProp)return readonlyField("Installed schema no longer matches this semantic slot.");
    const parts=[{label:"ITEM",control:semanticItemInput(row,itemProp,index)}];
    if(spec.percentProperty){const prop=property(spec.percentProperty);if(prop)parts.push({label:"CHANCE %",control:percentInput(row,prop,index)})}
    if(spec.quantityProperty){const prop=property(spec.quantityProperty);if(prop)parts.push({label:stealFieldLabel(spec),title:stealFieldHelp(spec),control:numericInput(row,prop,index)})}
    return LexeditorUI.controlGroup(parts,{columns:parts.length});
  }
  // BattleItemPossession gives steal a single numeric array and no percent
  // array. Calling it QUANTITY produced readings like "25 bladed staffs" for a
  // unique weapon, which no steal table can mean. Until the field's meaning is
  // confirmed against the running game, the control is named after the raw
  // property and says plainly that the unit is unverified.
  function stealFieldLabel(spec){
    return spec.percentProperty?"QUANTITY":String(spec.quantityProperty||"VALUE").replace(/_Array$/,"");
  }
  function stealFieldHelp(spec){
    if(spec.percentProperty)return null;
    return infoHelp("The installed table exposes this array without a matching percent array, so Lexeditor cannot tell whether the number is a count or a steal rate. It is shown and written as the raw "+spec.quantityProperty+" value.");
  }
  function lootRecordPanel(row=selectedRecord()){
    if(!row)return loadingPanel("Enemy loot","No BattleItemPossession rows were found.");const sections=[detailSection({title:"BATTLE",help:infoHelp("These drops live in the game's BattleItemPossession table, one row per battle. The Data ID is that row's key."),body:[detailField({label:"DATA ID",control:readonlyField(row.tag),pin:lootPrefs.pinButton("tag","Enemy / Battle ID")})]})];
    const labels={normal:"NORMAL DROPS",rare:"RARE DROPS",steal:"STEAL"};for(const spec of state.loot?.groups||[]){const itemProp=property(spec.itemProperty),items=itemProp?(row.values[itemProp.name]||[]):[];const body=items.length?items.map((_item,index)=>detailField({label:`SLOT ${index+1}`,control:lootSlotControl(row,spec,index),help:spec.percentProperty?infoHelp("Chance is the installed raw percent field, constrained by this semantic editor to 0–100."):null})): [detailNote("This drop array is empty on this record, so there are no slots to edit.")];sections.push(detailSection({title:labels[spec.kind]||spec.kind.toUpperCase(),body}))}
    return detailPanel({className:"ff7r-detail",title:row.tag||"Battle",body:sections});
  }
  function lootPanel(){if(state.busy&&state.tab==="loot")return loadingPanel("Loading enemy loot","Discovering BattleItemPossession and validated drop arrays…");if(state.lootError)return errorPanel(state.lootError);if(state.loot&&!state.loot.available)return loadingPanel("Enemy loot unavailable",state.loot.reason||"BattleItemPossession was not found or did not contain recognized drop/steal arrays.");if(!state.loot)return loadingPanel("Enemy loot","Open this tab to discover the installed FF7R loot table.");if(state.data?.asset!==state.loot.asset)return loadingPanel("Loading enemy loot","Reading BattleItemPossession…");return LexeditorUI.stack(pagedTable({id:"loot",noun:"enemies",
      modOnly:modOnlySpec(row=>row.record),
      rows:lootViewRows(),key:row=>row.record.id,selected:state.selected,
      setSelected:row=>{state.selected=row.record.id},
      query:state.lootQuery,setQuery:value=>{state.lootQuery=value},
      searchLabel:"Search FF7 Remake enemy loot",searchPlaceholder:"Search enemies, battle IDs, items, and chances",
      sortState:state.lootSort,sort:key=>{state.lootSort=state.lootSort.key===key?{key,dir:-state.lootSort.dir}:{key,dir:1};render()},
      prefs:lootPrefs,columns:lootColumns,ariaLabel:"FF7 Remake enemy drops and steals",
      split:56,minLeft:420,minRight:400,detail:()=>lootRecordPanel()}))}
