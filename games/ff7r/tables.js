"use strict";
  // Records are identified by their game key, not the parser row index, so
  // the tag column leads the table.
  // Text entries likewise lead with their resource and text ID.
  const dataColumns=[{key:"tag",label:"Record",sortable:true,width:"minmax(12em,1fr)"}];
  const economyColumns=[{key:"tag",label:"ID",sortable:true,width:"minmax(10em,.8fr)"},{key:"name",label:"Item",sortable:true,width:"minmax(14em,1.2fr)"},{key:"buy",label:"Buy",numeric:true,sortable:true},{key:"sale",label:"Sell",numeric:true,sortable:true},{key:"maxCount",label:"Carry Cap",numeric:true,sortable:true}];
  // Four columns at fourteen ems each did not fit the list panel, so the Steal
  // column was cut in half by the panel edge. The minimums are sized so all
  // four fit the default split; the cells ellipsise if a value is longer.
  const lootColumns=[{key:"tag",label:"Enemy / Battle ID",sortable:true,width:"minmax(9em,.9fr)"},{key:"normal",label:"Normal",sortable:true,width:"minmax(8em,1fr)"},{key:"rare",label:"Rare",sortable:true,width:"minmax(8em,1fr)"},{key:"steal",label:"Steal",sortable:true,width:"minmax(8em,1fr)"}];
  const textColumns=[{key:"resource",label:"Resource",sortable:true,width:"minmax(10em,.7fr)"},{key:"key",label:"Text ID",sortable:true,width:"minmax(12em,.8fr)"},{key:"text",label:"Text",sortable:true,width:"minmax(16em,1.2fr)"}];
  function propertyCellValue(row,prop){
    const value=row.values?.[prop.name];
    if(Array.isArray(value))return value.length?value.map(item=>resolvedText(item)||item).join(", "):"—";
    return value===undefined||value===null||value===""?"—":resolvedText(value)||value;
  }
  function dataTableColumns(){
    return [...dataColumns,...(state.data?.properties||[]).map(prop=>({
      key:propertyColumnKey(prop),label:prop.label,sortable:true,pinned:false,
      width:"minmax(7em,1fr)",
      numeric:!prop.array&&["INT","FLOAT"].includes(semanticType(prop)),
      render:row=>propertyCellValue(row,prop),
      sortValue:row=>propertyCellValue(row,prop)}))];
  }
  function dataPreferences(){
    const asset=state.data?.asset||state.asset||"none";
    const signature=(state.data?.properties||[]).map(prop=>prop.name).join(",");
    const entry=dataPrefsCache.get(asset);
    if(entry&&entry.signature===signature)return entry.prefs;
    const prefs=LexeditorUI.columnPreferences(`ff7r-records:${asset}`,dataTableColumns(),()=>render());
    dataPrefsCache.set(asset,{signature,prefs});
    return prefs;
  }
  const economyPrefs=LexeditorUI.columnPreferences("ff7r-economy",economyColumns,()=>render());
  const lootPrefs=LexeditorUI.columnPreferences("ff7r-loot",lootColumns,()=>render());
  const textPrefs=LexeditorUI.columnPreferences("ff7r-text-records",textColumns,()=>render());
  const assets=()=>state.catalog?.assets||[];
  const isTweak=item=>String(item.group||"").startsWith("Lexeditor ");
  const tweakAssets=()=>assets().filter(isTweak);
  const gameAssets=()=>assets().filter(item=>!isTweak(item));
  const textAssets=()=>state.catalog?.textAssets||[];
  const currentAsset=()=>assets().find(row=>row.asset===state.asset)||assets()[0]||null;
  const currentTextAsset=()=>textAssets().find(row=>row.asset===state.textAsset)||null;
  const records=()=>state.data?.records||[];
  // Every resource for the chosen language is loaded together, so the Text tab
  // is one list of all the game's text with the resource as an ordinary column.
  // Picking a resource before being allowed to look at anything was the old
  // shape, and it meant a search could only ever find what was already open.
  const textPacks=()=>Object.values(state.textPacks||{});
  const textRecords=()=>textPacks().flatMap(pack=>pack.data.records.map(row=>({
    row, asset:pack.item.asset, resource:pack.item.name,
    id:`${pack.item.asset}#${row.id}`,
    number:row.id, key:row.key, text:row.text, subentries:row.subentries})));
  const selectedRecord=()=>records().find(row=>row.id===state.selected)||records()[0]||null;
  const selectedTextRecord=()=>textRecords().find(row=>row.id===state.textSelected)||textRecords()[0]||null;
  const textPackOf=view=>state.textPacks?.[view?.asset]||null;
  const comparable=value=>JSON.stringify(value);
  const refreshShell=()=>shell?.refresh?.();
  const sourceSuffix=()=>state.activeSource==="vanilla"?"&source=vanilla":"";
  const semanticKey=()=>`${state.activeSource}:${state.textLanguage||"US"}`;
  const property=name=>state.data?.properties?.find(prop=>prop.name===name)||null;

  function dataEdits(){return diffRecords(state.data,state.dataBaseline)}
  // Both the Misc tab and every tweak group on the Tweaks page compare a loaded
  // DataObject against the copy it was loaded as. One routine, so a tweak edit
  // is written back exactly the way a Misc edit is.
  function diffRecords(current,baseline){
    if(state.activeSource!=="mine"||!current||!baseline)return[];
    const out=[];
    for(let i=0;i<current.records.length;i++){
      const row=current.records[i],base=baseline.records[i];if(!base)continue;
      for(const prop of current.properties){
        if(!prop.editable)continue;
        const value=row.values[prop.name],old=base.values[prop.name];
        if(prop.array){const count=Math.min(value.length,old.length);for(let j=0;j<count;j++)if(comparable(value[j])!==comparable(old[j]))out.push({entry:i,property:prop.name,index:j,value:value[j]})}
        else if(comparable(value)!==comparable(old))out.push({entry:i,property:prop.name,value});
      }
    }
    return out;
  }
  function textEdits(){return textEditGroups().flatMap(group=>group.edits)}
  // Every resource is loaded, so a save writes each one that changed rather
  // than the single resource that happened to be open.
  function textEditGroups(){
    if(state.activeSource!=="mine")return[];
    return textPacks()
      .map(pack=>({pack,edits:textDiff(pack.data,pack.baseline)}))
      .filter(group=>group.edits.length);
  }
  function textDiff(data,baseline){
    if(!data||!baseline)return[];
    const out=[];
    for(let i=0;i<data.records.length;i++){
      const row=data.records[i],base=baseline.records[i];if(!base)continue;
      if(row.text!==base.text)out.push({entry:i,text:row.text});
      const baseSubs=new Map((base.subentries||[]).map(sub=>[sub.id,sub.text]));
      for(const sub of row.subentries||[])if(baseSubs.has(sub.id)&&sub.text!==baseSubs.get(sub.id))out.push({entry:i,subId:sub.id,text:sub.text});
    }
    return out;
  }

  function flattenStrings(value,out=[]){if(typeof value==="string")out.push(value);else if(Array.isArray(value))for(const child of value)flattenStrings(child,out);else if(value&&typeof value==="object")for(const child of Object.values(value))flattenStrings(child,out);return out}
  function resolvedText(value){return typeof value==="string"?state.data?.textLookup?.[value]||"":""}
  function compareValues(a,b){if(a===b)return 0;if(a===undefined||a===null||a==="—")return 1;if(b===undefined||b===null||b==="—")return-1;if(typeof a==="number"&&typeof b==="number")return a-b;return String(a).localeCompare(String(b),undefined,{numeric:true,sensitivity:"base"})}
  function sortedRows(){
    const q=state.query.toLocaleLowerCase();
    return [...records()].filter(row=>{
      if(!q)return true;
      const values=flattenStrings(row.values);
      const resolved=values.map(value=>state.data?.textLookup?.[value]||"");
      return `${row.id} ${row.tag} ${values.join(" ")} ${resolved.join(" ")}`.toLocaleLowerCase().includes(q);
    }).sort((a,b)=>compareValues(a[state.sort.key],b[state.sort.key])*state.sort.dir);
  }
  function sortedTextRows(){
    const q=state.textQuery.toLocaleLowerCase();
    return textRecords()
      .filter(row=>!state.textResource||row.asset===state.textResource)
      .filter(row=>!q||`${row.number} ${row.resource} ${row.key} ${row.text} ${(row.subentries||[]).map(sub=>`${sub.id} ${sub.text}`).join(" ")}`.toLocaleLowerCase().includes(q))
      .sort((a,b)=>compareValues(a[state.textSort.key],b[state.textSort.key])*state.textSort.dir);
  }
