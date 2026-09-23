"use strict";
  function pagedTable(spec){
    return LexeditorUI.pagedListDetail({
      rows:spec.rows,key:spec.key,slots:false,noun:spec.noun||"records",
      page:state.pages[spec.id]||0,selected:spec.selected,
      className:"ff7r-layout",paneClass:"ff7r-pane",splitKey:`ff7r-${spec.id}`,rowsKey:`ff7r-${spec.id}-rows`,
      defaultSplit:spec.split||40,minLeft:spec.minLeft||340,minRight:spec.minRight||420,
      search:{key:`ff7r-${spec.id}`,value:spec.query,label:spec.searchLabel,
        placeholder:spec.searchPlaceholder,
        change:value=>{spec.setQuery(value);state.pages[spec.id]=0;render()}},
      filters:spec.filters||[],
      modOnly:spec.modOnly||null,
      change:next=>{state.pages[spec.id]=next.page;render()},
      sync:next=>{state.pages[spec.id]=next.page},
      master:({rows,selected,select})=>columnList({rows,key:spec.key,selected,
        select:row=>{spec.setSelected(row);select(row);},
        sortState:spec.sortState,sort:spec.sort,
        columnPreferences:spec.prefs,columns:spec.columns,class:"ff7r-table",
        "aria-label":spec.ariaLabel}),
      detail:spec.detail,
    });
  }
  function curatedColumns(spec){
    const properties=state.data?.properties||[];
    return [{key:"id",label:"ID",numeric:true,numberedId:true,sortable:true,width:"74px"},
      {key:"tag",label:"Record",sortable:true,width:"minmax(12em,1fr)"},
      ...properties.map(prop=>({key:propertyColumnKey(prop),label:prop.label||prop.name,
        numeric:!prop.array&&["INT","FLOAT"].includes(semanticType(prop)),
        sortable:true,
        // The curated set is what the tab opens with. Every other property is
        // declared but unpinned, so its pin in the detail panel has a column
        // to bring in rather than nothing to toggle.
        pinned:spec.columns.includes(prop.name)?undefined:false}))];
  }
  function curatedRows(spec){
    const q=String(state.curatedQuery||"").toLocaleLowerCase();
    const properties=state.data?.properties||[];
    const rows=records().map(record=>{
      const row={record,id:record.id,tag:record.tag};
      for(const prop of properties){
        row[propertyColumnKey(prop)]=propertyCellValue(record,prop);
      }
      return row;
    });
    const filtered=q?rows.filter(row=>`${Object.values(row).filter(value=>typeof value!=="object").join(" ")} ${flattenStrings(row.record.values).join(" ")}`.toLocaleLowerCase().includes(q)):rows;
    const key=state.curatedSort.key,dir=state.curatedSort.dir;
    return filtered.sort((a,b)=>compareValues(a[key],b[key])*dir);
  }
  function curatedPanel(spec){
    if(state.busy)return loadingPanel(spec.label,`Reading ${spec.basename}…`);
    if(state.error&&!state.data)return errorPanel(state.error);
    if(!curatedAsset(spec))return loadingPanel(spec.label,
      `The installed FF7R archives do not contain a ${spec.basename} table.`);
    if(!state.data)return loadingPanel(spec.label,"Open this tab to read the table.");
    // Say which of the game's tables this is when there is more than one. The
    // reader was seeing one field map's enemies with nothing on screen to say
    // that seven more tables of the same name exist.
    const siblings=curatedAssets(spec);
    const picker=siblings.length>1?LexeditorUI.subtabBar({
      label:`${spec.label} tables`,
      active:state.data?.asset||siblings[0].asset,
      tabs:siblings.map(item=>({id:item.asset,
        label:/\/Resident\//i.test(item.asset)?"General":String(item.asset).split("/").slice(-2,-1)[0]||String(item.asset).split("/").pop()})),
      change:value=>{state.curatedAsset=value;state.selected=null;state.pages[spec.id]=0;
        state.asset=value;loadAsset(value).then(()=>render());},
    }):null;
    return LexeditorUI.stack(picker,pagedTable({id:spec.id,noun:spec.noun,
      modOnly:modOnlySpec(row=>row.record),
      rows:curatedRows(spec),key:row=>row.record.id,
      selected:state.selected,setSelected:row=>{state.selected=row.record.id},
      query:state.curatedQuery,setQuery:value=>{state.curatedQuery=value},
      searchLabel:`Search ${spec.label}`,searchPlaceholder:"Search record names and IDs",
      sortState:state.curatedSort,
      sort:key=>{state.curatedSort=state.curatedSort.key===key
        ?{key,dir:-state.curatedSort.dir}:{key,dir:1};render()},
      prefs:curatedPrefs(spec),columns:curatedColumns(spec),
      ariaLabel:`FF7 Remake ${spec.label}`,
      split:52,minLeft:380,minRight:400,detail:()=>recordPanel()}));
  }
  const curatedPrefsCache={};
  function curatedPrefs(spec){
    const columns=curatedColumns(spec);
    const signature=columns.map(column=>column.key).join("|");
    const cached=curatedPrefsCache[spec.id];
    if(!cached||cached.signature!==signature){
      curatedPrefsCache[spec.id]={signature,
        prefs:columnPreferences(`ff7r-${spec.id}`,columns,()=>render())};
    }
    return curatedPrefsCache[spec.id].prefs;
  }
  function pagedDataPanel(){
    const rows=sortedRows();
    return LexeditorUI.pagedListDetail({
      rows,key:row=>row.id,slots:false,noun:"records",
      page:state.dataPage||0,selected:state.selected,
      className:"ff7r-layout",paneClass:"ff7r-pane",splitKey:"ff7r-data",rowsKey:"ff7r-data-rows",
      defaultSplit:36,minLeft:320,minRight:420,
      search:{key:"ff7r-data",value:state.query,label:"Search FF7 Remake records",
        placeholder:"Search IDs, values, and resolved names",
        change:value=>{state.query=value;state.dataPage=0;render()}},
      modOnly:modOnlySpec(),change:next=>{state.dataPage=next.page;render()},
      sync:next=>{state.dataPage=next.page},
      master:({rows:page,selected,select})=>columnList({rows:page,key:row=>row.id,selected,
        select:row=>{state.selected=row.id;select(row);},
        sortState:state.sort,sort:key=>{state.sort=state.sort.key===key?{key,dir:-state.sort.dir}:{key,dir:1};render()},
        columnPreferences:dataPreferences(),columns:dataTableColumns(),class:"ff7r-table",
        "aria-label":"FF7 Remake DataObject records"}),
      detail:()=>recordPanel(),
    });
  }
