from pathlib import Path

PATH = Path("games/ff7/editor.html")
text = PATH.read_text(encoding="utf-8")


def replace_between(source, start_marker, end_marker, replacement):
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[:start] + replacement + source[end:]


master_block = r'''  const MASTER_SUMMARY_FIELDS={
    characters:[["level","Lv"],["maxHp","HP"],["maxMp","MP"]],
    recruits:[["level","Lv"],["maxHp","HP"],["maxMp","MP"]],
    commands:[["initialCursorAction","Action"]],
    playerAttacks:[["mpCost","MP"],["attackPower","Power"],["damageCalculationId","Formula"]],
    limitBreaks:[["mpCost","MP"],["attackPower","Power"],["damageCalculationId","Formula"]],
    items:[["attackPower","Power"],["damageCalculationId","Formula"]],
    weapons:[["attackStrength","Attack"],["accuracyRate","Hit"],["growthRate","AP growth"]],
    armor:[["defense","Defense"],["magicDefense","M.Def"],["growthRate","AP growth"]],
    accessories:[["specialEffect","Effect"]],
    materia:[["level5Ap","Master AP"],["materiaType","Behavior"]],
    materiaEquipEffects:[["hpPercent","HP %"],["mpPercent","MP %"]],
    enemies:[["level","Lv"],["hp","HP"],["experience","EXP"]],
    enemyAttacks:[["cost","MP"],["power","Power"],["formula","Formula"]],
    shops:[["type","Type"],["count","Slots"]],
    prices:[["price","Price"]],
    initialState:[["gil","Gil"]],
    initialInventory:[["amount","Qty"]],
    initialMateria:[["ap","AP"]],
    stolenMateria:[["ap","AP"]],
    magicOrder:[["menuGroup","Section"],["position","Pos"]],
    itemSortOrder:[["position","Sort"]],
    materiaPriority:[["priority","Priority"]],
    audioMixing:[["volume","Volume"],["pan","Pan"]],
    apMultiplier:[["multiplier","Multiplier"]],
  };
  function globalInventoryRecord(value,priceTable=false){
    const id=Number(value),specs=priceTable?[["items",0,128],["weapons",128,128],["armor",256,32],["accessories",288,32],["materia",384,96]]:[["items",0,128],["weapons",128,128],["armor",256,32],["accessories",288,32]];
    for(const [group,start,count] of specs)if(id>=start&&id<start+count){const record=rowById(group,id-start);if(record)return{group,record}}
    return null;
  }
  function displayRowName(row){
    if(state.tab==="prices"){
      const hit=globalInventoryRecord(row.id,true);if(hit)return`${candidateLabel(hit.record)} — ${labels[hit.group]||hit.group}`;
    }
    if(state.tab==="itemSortOrder"){
      const hit=globalInventoryRecord(row.id,false);if(hit)return`${candidateLabel(hit.record)} — ${labels[hit.group]||hit.group}`;
    }
    if(state.tab==="materiaPriority"){
      const record=rowById("materia",row.id);if(record)return candidateLabel(record);
    }
    if(state.tab==="initialInventory"){
      const value=Number(row.values.item);if(value===0x1FF)return`Slot ${row.id+1} — Empty`;
      const hit=globalInventoryRecord(value,false);return`Slot ${row.id+1} — ${hit?candidateLabel(hit.record):`Unknown item ${value}`}`;
    }
    if(state.tab==="initialMateria"||state.tab==="stolenMateria"){
      const value=Number(row.values.materia),record=value===0xFF?null:rowById("materia",value);
      return`Slot ${row.id+1} — ${value===0xFF?"Empty":record?candidateLabel(record):`Unknown Materia ${value}`}`;
    }
    if(state.tab==="magicOrder"){
      const record=rowById("playerAttacks",row.id);if(record)return candidateLabel(record);
    }
    return String(row.values?.name||row.name||`Record ${row.id}`);
  }
  function semanticListValue(row,field){
    const value=row.values?.[field.key];if(value===undefined||value===null)return"—";
    if(field.dataType==="enum")return enumSummary(field,value);
    if(field.dataType==="flags")return flagsSummary(field,value);
    if(field.dataType==="boolean")return Number(value)?"Enabled":"Disabled";
    if(field.dataType==="scaled")return String(Number(value)*(Number(field.displayScale)||1));
    if(field.dataType==="statusChange")return statusChangeSummary(value);
    if(field.dataType==="lootRate")return lootRateSummary(value);
    return String(value);
  }
  function compactListValue(value){
    const full=String(value),head=full.includes(" — ")?full.split(" — ")[0]:full;
    return head.length>26?head.slice(0,25)+"…":head;
  }
  function summaryColumns(){
    return (MASTER_SUMMARY_FIELDS[state.tab]||[]).flatMap(([fieldKey,label])=>{
      const field=fieldByKey(fieldKey);if(!field)return[];
      return[{key:`value:${fieldKey}`,label,sortable:true,grow:.65,pinned:false,render:row=>{const full=semanticListValue(row,field);return el("span",{title:full},compactListValue(full))}}];
    });
  }
  function listSortValue(row,key){
    if(key==="name")return displayRowName(row);
    if(key==="description")return row.description||"";
    if(String(key).startsWith("value:"))return row.values?.[String(key).slice(6)];
    return row[key];
  }
  function compareListValues(left,right){
    if(left===undefined||left===null)return right===undefined||right===null?0:1;
    if(right===undefined||right===null)return-1;
    if(typeof left==="number"&&typeof right==="number")return left-right;
    return String(left).localeCompare(String(right),undefined,{numeric:true,sensitivity:"base"});
  }
  function recordSearchText(row){
    const semantic=(category()?.fields||[]).map(field=>semanticListValue(row,field)).join(" ");
    return`${row.id} ${displayRowName(row)} ${row.name||""} ${row.description||""} ${row.values?.text||""} ${semantic}`.toLocaleLowerCase();
  }
  function listTable(rows,selected,select){
    const summaries=summaryColumns(),columns=[
      {key:"id",label:"ID",numberedId:true,sortable:true},
      {key:"name",label:"Name",sortable:true,grow:2,render:row=>{const name=displayRowName(row);return el("span",{title:name},name)}},
      ...summaries,
      ...(category()?.descriptionEditable&&!summaries.length?[{key:"description",label:"Description",sortable:true,grow:3,pinned:false,render:row=>el("span",{title:row.description},row.description)}]:[]),
    ];
    const prefs=columnPreferences(`ff7-${state.tab}`,columns,()=>render());
    const sort=state.sort[state.tab]||{key:"name",dir:1};
    return columnList({rows,key:row=>row.id,selected,select:row=>{const id=typeof row==="object"?row.id:row;if(id!==state.selected[state.tab])LexeditorUI.playThemeSound?.("move");select(row)},sortState:sort,sort:key=>{state.sort[state.tab]=sort.key===key?{key,dir:-sort.dir}:{key,dir:1};render()},columnPreferences:prefs,columns,class:"ff7-table","aria-label":`${labels[state.tab]} records`});
  }
'''

integrated_block = r'''  function integratedView(){
    const group=state.tab,query=state.query[group]||"",sort=state.sort[group]||{key:"name",dir:1};
    if(!state.records[group]?.length)return unavailableView();
    const needle=query.trim().toLocaleLowerCase();
    const rows=[...state.records[group]].filter(row=>!needle||recordSearchText(row).includes(needle)).sort((a,b)=>compareListValues(listSortValue(a,sort.key),listSortValue(b,sort.key))*sort.dir);
    if(!rows.some(row=>row.id===state.selected[group]))state.selected[group]=rows[0]?.id??null;
    return pagedListDetail({rows,key:row=>row.id,slots:false,selected:state.selected[group],page:state.page[group]||0,pageSize:state.pageSize[group]||12,noun:labels[group],className:"ff7-layout",splitKey:`ff7-${group}`,rowsKey:`ff7-${group}`,defaultSplit:50,minLeft:320,minRight:360,search:{key:`ff7-${group}`,value:query,label:`Search ${labels[group]}`,change:value=>{state.query[group]=value;state.page[group]=0;render()}},sync:next=>{state.page[group]=next.page;state.pageSize[group]=next.pageSize;if(next.selected!==null)state.selected[group]=next.selected},change:next=>{state.page[group]=next.page;state.pageSize[group]=next.pageSize;if(next.selected!==null)state.selected[group]=next.selected;render()},master:view=>listTable(view.rows,view.selected,view.select),detail:row=>recordDetail(row)});
  }
'''

workspace_block = r'''  function datasetSummary(){
    const metadata=category(),family=state.data.families?.[metadata?.family],rows=state.records[state.tab]||[],saved=state.saved[state.tab]||[];
    const source=family?.sourceRelativePath||state.data.sourceRelativePath||metadata?.family||"Loaded game data";
    const usingProject=family?!!family.usingProject:!!state.data.usingProject,dirty=JSON.stringify(rows)!==JSON.stringify(saved);
    const status=dirty?"Unsaved changes":usingProject?"Project copy":"Vanilla source";
    const parts=[el("strong",{},labels[state.tab]),el("span",{style:"opacity:.72"},`${rows.length.toLocaleString()} records`),el("span",{style:"font-weight:600"},status)];
    if(source)parts.push(el("span",{title:String(source),style:"margin-left:auto;max-width:42ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;opacity:.62"},String(source)));
    return el("div",{class:"ff7-dataset-summary",style:"display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;padding:.55rem .75rem;min-width:0"},...parts);
  }
  function dataWorkspace(){
    const sub=groups[parentTab(state.tab)],summary=datasetSummary();
    if(!sub)return el("section",{class:"ff7-workspace"},summary,integratedView());
    const nav=subtabBar({tabs:sub.map(id=>({id,label:labels[id]})),active:state.tab,label:labels[parentTab(state.tab)]+" datasets",change:id=>{if(id!==state.tab)LexeditorUI.playThemeSound?.("confirm");navigate(id)}});
    return el("section",{class:"ff7-workspace lex-tabbed-panel"},nav,summary,el("div",{class:"lex-tabbed-panel-content"},integratedView()));
  }
'''

if "MASTER_SUMMARY_FIELDS" in text:
    raise SystemExit("FF7 UI refinement already present; refusing to apply twice")

text = replace_between(text, "  function listTable(rows,selected,select){", "  function unavailableView(){", master_block)
text = replace_between(text, "  function integratedView(){", "  function unresolvedView(){", integrated_block)
text = replace_between(text, "  function dataWorkspace(){", "  function render(){", workspace_block)
PATH.write_text(text, encoding="utf-8")
print("Applied FF7 semantic browsing refinement")
