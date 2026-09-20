// ----- Effects -----
function effectSectionTabs(){
  const section=state.filters.effectSection||"effects";
  return LexeditorUI.subtabBar({active:section,label:"Effects view",tabs:[{id:"effects",label:"Effects"},{id:"behaviors",label:"Behavior IDs"}],change:key=>{state.filters.effectSection=key;renderEffects()}});
}

function behaviorChoices(){
  return [...new Set(state.catalog.effects.map(e=>e.id).filter(Boolean))]
    .sort((a,b)=>(humanName("behaviors",a)||effectBehaviorName({id:a})||a).localeCompare(humanName("behaviors",b)||effectBehaviorName({id:b})||b));
}

function behaviorDetail(row){
  const effects=state.catalog.effects.filter(effect=>effect.id===row.id);
  return LexeditorUI.detailPanel({title:LexeditorUI.detailField({label:"Name",control:humanNameInput("behaviors",row.id,effectBehaviorName({id:row.id})||"Name this behavior…")}),meta:row.id,help:effectBehaviorHelp({id:row.id}),body:LexeditorUI.detailSection({title:"Used by",body:effects.length?LexeditorUI.stack({fill:false},...effects.map(effect=>effectLink(effect.key,`${humanName("effects",effect.key)||effect.symbol||effect.label||effect.key} · ${effect.key}`))):LexeditorUI.detailNote("No effects")})});
}

function renderBehaviors(){
  const f=state.filters,tb=$("#toolbar");tb.innerHTML="";
  tb.append(effectSectionTabs());
  const usage={};for(const e of state.catalog.effects)usage[e.id]=(usage[e.id]||0)+1;
  const q=(f.behaviorQ||"").trim().toUpperCase();
  let rows=behaviorChoices().map(id=>({id,name:humanName("behaviors",id)||effectBehaviorName({id})||"",used:usage[id]||0}))
    .filter(row=>!q||`${row.name} ${row.id}`.toUpperCase().includes(q));
  rows=sortedRows("behaviors",rows,{name:r=>r.name||r.id,id:r=>r.id,used:r=>r.used});
  const m=$("#main");m.innerHTML="";
  m.append(LexeditorUI.pagedListDetail({
    modOnly:(()=>{const edited=touchedRecords([state.effectEdits]);
      const ids=new Set(state.catalog.effects.filter(effect=>edited.has(effect.key)).map(effect=>effect.id));
      return {available:!isRO(),value:state.modOnly===true,changed:row=>ids.has(row.id),
        change:value=>{state.modOnly=value;f.behaviorPage=0;renderBehaviors();}};})(),
    rows,key:row=>row.id,slots:false,page:f.behaviorPage,pageSize:f.behaviorPageSize,selected:f.behaviorSel,noun:"behavior IDs",
    splitKey:"rdr2-effect-behaviors",defaultSplit:55,minLeft:480,
    search:{key:"rdr2-effect-behaviors",value:f.behaviorQ||"",placeholder:"Search behavior IDs…",change:value=>{f.behaviorQ=value;f.behaviorPage=0;renderBehaviors();}},
    className:"lootsplit",fit:{rowSelector:".behavior-column-row",minRowHeight:64},
    master:({rows,selected,select})=>LexeditorUI.columnList({rows,key:row=>row.id,selected,selectedClass:"sel",select,
      class:"loot-list behavior-column-list",headerClass:"loot-listhead",
      template:"minmax(180px,1.5fr) minmax(130px,1fr) 72px",sortState:state.sorts.behaviors,sort:key=>sharedTableSort("behaviors",key,renderBehaviors),
      columns:[
        {key:"name",label:"Behavior name",sortable:true,render:row=>LexeditorUI.stack({fill:false},el("span",{class:"lex-inline-label"},row.name||"Unlabeled"))},
        {key:"id",label:"Behavior ID",sortable:true,cellClass:"technical-id"},
        {key:"used",label:"Used by",sortable:true,render:row=>String(row.used)}],rowClass:"loot-item behavior-column-row"}),
    detail:behaviorDetail,
    sync:next=>{f.behaviorPage=next.page;f.behaviorPageSize=next.pageSize;f.behaviorSel=next.selected||"";},
    change:next=>{f.behaviorPage=next.page;f.behaviorPageSize=next.pageSize;f.behaviorSel=next.selected||"";renderBehaviors();}
  }));installTabContext();
}

function effectNumberEditor(e,field,currentBehavior){
  const ek=e.key+"|"+field,cur=isRO()?e[field]:(state.effectEdits[ek]??e[field]);
  const percentNow=+(state.effectEdits[e.key+"|percent"]??e.percent);
  const isOuterBar=["EFFECT_HEALTH","EFFECT_STAMINA","EFFECT_DEADEYE"].includes(currentBehavior);
  const isPercentResource=/^EFFECT_(HORSE_)?(HEALTH|STAMINA|DEADEYE)_CORE$/.test(currentBehavior)||/^EFFECT_HORSE_(HEALTH|STAMINA)$/.test(currentBehavior);
  const valueDriven=isOuterBar||["0x77323E93","0x45EA9E3E","0x9D36F302"].includes(currentBehavior.toUpperCase());
  const inactive=field==="percent"&&valueDriven;
  const role=field==="value"&&isOuterBar?"Actual outer-bar point change":field==="value"&&isPercentResource?"Inventory/wheel display tier; Percent Override controls the real change":inactive?"Not consumed by this known Value-driven behavior":field==="percent"&&isPercentResource?"Actual refill/loss percentage":field==="value"&&valueDriven?"Active engine magnitude":"Behavior-specific field";
  const expectedTier=isPercentResource&&percentNow!==0?Math.sign(percentNow)*Math.max(1,Math.min(10,Math.round(Math.abs(percentNow)/10))):null;
  const tierMismatch=field==="value"&&expectedTier!==null&&Number(cur)!==expectedTier;
  const input=el("input",{type:"number",step:field==="percent"?"any":"1",value:field==="percent"?fmtCompactNumber(cur):cur,...(inactive?{readonly:"readonly"}:{}),title:tierMismatch?`${role}. Warning: ${fmtCompactNumber(percentNow)}% normally maps to display tier ${expectedTier}.`:role,
    class:ek in state.effectEdits?"edited":"",onchange:ev=>{const value=ev.target.value;
      if(Number(value)===Number(e[field]))delete state.effectEdits[ek];else state.effectEdits[ek]=value;renderEffects();renderToolbarOnly();}});
  const control=field==="percent"?LexeditorUI.unitField(input,"%")
    :tierMismatch?LexeditorUI.inlineLabel(input,fieldHelp(`Display tier ${cur} contradicts ${fmtCompactNumber(percentNow)}%; expected tier ${expectedTier}.`)):input;
  const vEff=state.store.vanilla?.effectByKey?.[e.key],kEff=state.store.kiddos?.effectByKey?.[e.key];
  return refField(control,[["V","vtag",vEff?vEff[field]:null],["K","ktag",kEff?kEff[field]:null]],cur,
    inactive?null:(value,event)=>applyToInput(event,value),value=>(+value%1?(+value).toFixed(2):String(+value)));
}

function effectDetail(e,behaviors,used){
  const body=[];
  const behaviorKey=e.key+"|id",currentBehavior=state.effectEdits[behaviorKey]??e.id;
  const field=(label,control,help="")=>LexeditorUI.detailField({label,control,help:help?fieldHelp(help):null});
  const behavior=el("select",{value:currentBehavior,class:behaviorKey in state.effectEdits?"edited":"",...(isRO()?{disabled:true}:{}),onchange:event=>{
    const value=event.target.value;if(value===e.id)delete state.effectEdits[behaviorKey];else state.effectEdits[behaviorKey]=value;renderEffects();renderToolbarOnly();
  }},...behaviors.map(id=>el("option",{value:id,selected:id===currentBehavior},`${humanName("behaviors",id)||effectBehaviorName({id})||id}${humanName("behaviors",id)||effectBehaviorName({id})?` — ${id}`:""}`)));
  body.push(field("Behavior ID",LexeditorUI.controlGroup([behavior,behaviorLink(currentBehavior)]),effectBehaviorHelp({id:currentBehavior})),
    field("Engine value / display tier",effectNumberEditor(e,"value",currentBehavior)),
    field("Percent override",effectNumberEditor(e,"percent",currentBehavior)),
    field("Time",effectNumberEditor(e,"time",currentBehavior)),
    field("Time units",effectNumberEditor(e,"timeunits",currentBehavior)),
    field("Duration category",el("span",{class:"cat"},e.durationcategory.replace("EFFECT_DURATION_CATEGORY_",""))));
  body.push(field("Used by",used.length?el("button",{class:"table-link",title:"Show every item using this effect",onclick:()=>showEffectUsage(e,used)},`${used.length} item${used.length===1?"":"s"}`):el("span",{class:"cat"},"No items")));
  return LexeditorUI.detailPanel({title:field("Name",humanNameInput("effects",e.key)),meta:`${e.symbol||e.label?`${e.symbol||e.label} · `:""}${e.key}`,actions:originMarker(e),body});
}

function effectColumnList(rows,selected,select,usage){
  const current=(e,field)=>state.effectEdits[e.key+"|"+field]??e[field];
  const column=(key,label,help="")=>({key,label:el("span",{},label,help?fieldHelp(help):""),sortable:true});
  return LexeditorUI.columnList({rows,key:e=>e.key,selected,selectedClass:"sel",select,
    class:"loot-list effect-column-list",headerClass:"loot-listhead",
    template:"minmax(170px,2fr) minmax(130px,1.5fr) 58px 64px 48px 52px minmax(82px,1fr) 58px",
    sortState:state.sorts.effects,sort:key=>sharedTableSort("effects",key,renderEffects),rowClass:"loot-item effect-column-row",
    columns:[
      {...column("name","Effect","Editor label and catalog reference."),render:e=>LexeditorUI.stack({fill:false},
        el("span",{class:"lex-inline-label"},originDisplayName(humanName("effects",e.key)||e.symbol||e.label||e.key,e)),el("span",{class:"key"},e.key))},
      {...column("id","Behavior ID","Engine operation selected by this effect."),render:e=>LexeditorUI.stack({fill:false},
        behaviorLink(current(e,"id"),humanName("behaviors",current(e,"id"))||effectBehaviorName({id:current(e,"id")})||current(e,"id")),el("span",{class:"technical-id"},current(e,"id")))},
      {...column("value","Value"),render:e=>String(current(e,"value"))},
      {...column("percent","Percent","Gameplay magnitude. Engine Value is the wheel preview tier: 1≈12.5%, 3=25%, 5=50%, 8=75%, 10=100%."),render:e=>`${fmtCompactNumber(current(e,"percent"))}%`},
      {...column("time","Time"),render:e=>String(current(e,"time"))},
      {...column("units","Units"),render:e=>String(current(e,"timeunits"))},
      {...column("duration","Duration"),render:e=>e.durationcategory.replace("EFFECT_DURATION_CATEGORY_","")},
      {...column("used","Used by"),render:e=>String((usage[e.key]||[]).length)}]});
}

function renderEffects(){
  if(!state.catalog)return noData(`This dataset has no catalog_sp.ymt yet (${dsInfo().dir}).`);
  ensureRefCatalogs(()=>{if(state.tab==="effects")renderEffects();});
  const f=state.filters;if((f.effectSection||"effects")==="behaviors")return renderBehaviors();
  const tb=$("#toolbar");tb.innerHTML="";
  tb.append(effectSectionTabs());
  const effectFilters=[el("label",{class:"lex-bottom-filter"},el("input",{type:"checkbox",...(f.onlyNamed?{checked:""}:{}),onchange:event=>{f.onlyNamed=event.target.checked;f.effectPage=0;renderEffects();}})," labeled only"),
    isRO()?el("span"):newButton({title:"Create new effect",onclick:showCreateEffect}),
    savebar(saveCatalog)];
  const q=(f.effQ||"").trim().toUpperCase(),behaviors=behaviorChoices(),usage={};
  for(const item of state.catalog.items)for(const key of item.effects)(usage[key]=usage[key]||[]).push(item.key);
  const effectHasLabel=e=>Boolean(humanName("effects",e.key)||e.symbol||humanName("behaviors",e.id)||e.label||!e.key.startsWith("0x"));
  let rows=state.catalog.effects.filter(e=>{const searchable=`${humanName("effects",e.key)} ${e.symbol||""} ${humanName("behaviors",e.id)} ${e.label||""} ${e.key} ${e.id}`.toUpperCase();
    return(!q||searchable.includes(q))&&(!f.onlyNamed||effectHasLabel(e));});
  rows=sortedRows("effects",rows,{name:e=>humanName("effects",e.key)||e.label||e.key,id:e=>state.effectEdits[e.key+"|id"]??e.id,
    value:e=>+(state.effectEdits[e.key+"|value"]??e.value),percent:e=>+(state.effectEdits[e.key+"|percent"]??e.percent),
    time:e=>+(state.effectEdits[e.key+"|time"]??e.time),units:e=>+(state.effectEdits[e.key+"|timeunits"]??e.timeunits),
    duration:e=>e.durationcategory,used:e=>(usage[e.key]||[]).length});
  const m=$("#main");m.innerHTML="";
  m.append(LexeditorUI.pagedListDetail({modOnly:(()=>{const touched=touchedRecords([state.effectEdits]);
      return {available:!isRO(),value:state.modOnly===true,changed:e=>touched.has(e.key),
        change:value=>{state.modOnly=value;f.effectPage=0;renderEffects();}};})(),
    rows,key:e=>e.key,slots:false,page:f.effectPage,pageSize:f.effectPageSize,selected:f.effectSel,noun:"effects",
    splitKey:"rdr2-effects",defaultSplit:64,minLeft:790,minRight:420,className:"lootsplit",
    search:{key:"rdr2-effects",value:f.effQ||"",placeholder:"Search effects… (e.g. HEALTH_CORE)",change:value=>{f.effQ=value;f.effectPage=0;renderEffects();}},filters:effectFilters,
    fit:{rowSelector:".effect-column-row",minRowHeight:64},
    master:({rows,selected,select})=>effectColumnList(rows,selected,select,usage),detail:e=>effectDetail(e,behaviors,usage[e.key]||[]),
    sync:next=>{f.effectPage=next.page;f.effectPageSize=next.pageSize;f.effectSel=next.selected||"";},
    change:next=>{f.effectPage=next.page;f.effectPageSize=next.pageSize;f.effectSel=next.selected||"";renderEffects();}}));installTabContext();
}
