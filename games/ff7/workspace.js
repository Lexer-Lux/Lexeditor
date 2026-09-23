"use strict";
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
  function derivedListValue(row,key){
    if(key==="derived:aiScripts")return aiUsedCount(row);
    if(key==="derived:growthKind")return {primary:0,hp:1,mp:2,exp:3}[growthCurveKind(row)]??9;
    if(key==="derived:encounterEnemies")return Array.from({length:6},(_,i)=>Number(row.values[`slot${i}_enemy`])!==0xFFFF).filter(Boolean).length;
    if(key==="derived:textLength")return String(row.values?.text||"").length;
    return undefined;
  }
  function derivedSummaryColumns(){
    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return[{key:"derived:aiScripts",label:"AI",help:"Battle-AI event scripts used out of the sixteen available hooks.",sortable:true,grow:.42,render:row=>`${aiUsedCount(row)}/16`}];
    if(state.tab==="growthCurves")return[{key:"derived:growthKind",label:"TYPE",help:"What this growth curve controls.",sortable:true,grow:.48,render:row=>({primary:"Primary",hp:"HP",mp:"MP",exp:"EXP"}[growthCurveKind(row)])}];
    if(state.tab==="encounters")return[{key:"derived:encounterEnemies",label:"FOES",help:"Number of non-empty enemy slots in this formation.",sortable:true,grow:.42,render:row=>derivedListValue(row,"derived:encounterEnemies")}];
    if(["texts","exeText"].includes(state.tab))return[{key:"derived:textLength",label:"CHARS",help:"Decoded character count for this text record.",sortable:true,grow:.42,render:row=>derivedListValue(row,"derived:textLength")}];
    return[];
  }
  function summaryColumns(){
    const explained=new Set(["CALC","FX","M.AP","TYPE","MENU","ORDER","RATE"]);
    const fields=(MASTER_SUMMARY_FIELDS[state.tab]||[]).flatMap(([fieldKey,label],index)=>{
      const field=fieldByKey(fieldKey);if(!field)return[];
      return[{key:`value:${fieldKey}`,label,help:explained.has(label)?field.label:null,sortable:true,grow:.48,pinned:index>=2?false:true,render:row=>{const full=semanticListValue(row,field);return el("span",{title:full},compactListValue(full))}}];
    });
    return[...fields,...derivedSummaryColumns()];
  }
  function listSortValue(row,key){
    if(key==="name")return displayRowName(row);
    if(key==="description")return row.description||"";
    if(String(key).startsWith("value:"))return row.values?.[String(key).slice(6)];
    if(String(key).startsWith("derived:"))return derivedListValue(row,key);
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
      ...(category()?.descriptionEditable&&!summaries.length?[{key:"description",label:"DESC",help:"In-game description text",sortable:true,grow:3,pinned:false,render:row=>el("span",{title:row.description},row.description)}]:[]),
    ];
    const prefs=columnPreferences(`ff7-v2-${state.tab}`,columns,()=>render());
    const sort=state.sort[state.tab]||{key:"id",dir:1};
    return columnList({rows,key:row=>row.id,selected,select:row=>{const id=typeof row==="object"?row.id:row;if(id!==state.selected[state.tab])LexeditorUI.playThemeSound?.("move");select(row)},sortState:sort,sort:key=>{state.sort[state.tab]=sort.key===key?{key,dir:-sort.dir}:{key,dir:1};render()},columnPreferences:prefs,columns,class:"ff7-table","aria-label":`${labels[state.tab]} records`});
  }
  function unavailableView(){
    // state.data is null until the first successful load. Reading through it
    // threw here, the render aborted, and the tab was left completely blank
    // with no message at all.
    const data=state.data||{};
    const error=data.errors?.[state.tab];
    const source=data.families?.[category()?.family]?.sourceRelativePath||category()?.family||data.sourceRelativePath||"English KERNEL.BIN in the selected installation";
    return detailPanel({className:"ff7-detail",title:labels[state.tab],identity:null,meta:"Data unavailable",body:[
      detailSection({title:"STATUS",body:[
        detailField({label:"STATE",control:integrationStatus("not-integrated")}),
        detailField({label:"SOURCE",control:readonlyField(source)}),
        detailField({label:"PROBLEM",control:readonlyField(error||"No readable records are available for this dataset.")}),
        detailField({label:"NEXT",control:el("button",{type:"button",onclick:()=>navigate("datamap")},"Open Data Map")}),
      ]}),
    ]});
  }
  function integratedView(){
    const group=state.tab,sourceRows=state.records[group]||[],query=state.query[group]||"",sort=state.sort[group]||{key:"id",dir:1};
    if(!sourceRows.length)return unavailableView();
    const needle=query.trim().toLocaleLowerCase();
    const rows=[...sourceRows].filter(row=>!needle||recordSearchText(row).includes(needle)).sort((a,b)=>compareListValues(listSortValue(a,sort.key),listSortValue(b,sort.key))*sort.dir);
    if(!rows.some(row=>row.id===state.selected[group]))state.selected[group]=rows[0]?.id??null;
    // A one-record dataset has no selection problem to solve. Giving half the
    // workspace to a one-row master is pure chrome, so show its editor directly.
    if(sourceRows.length===1&&rows.length===1)return recordDetail(rows[0]);
    // The shared paged table is optimized for pages of records and deliberately
    // fills its master pane. For genuinely tiny fixed FF7 tables (recruits and
    // growth-bonus families), use an ordinary master/detail instead so 2–4 rows
    // retain normal row height rather than being expanded across a full page.
    if(sourceRows.length<=4){
      const selected=rows.find(row=>row.id===state.selected[group])||rows[0];
      if(!selected)return unavailableView();
      const master=listTable(rows,selected.id,row=>{state.selected[group]=typeof row==="object"?row.id:row;render()});
      master.classList.add("ff7-compact-master");
      return LexeditorUI.listDetail(master,recordDetail(selected),"ff7-layout ff7-compact-layout",{splitKey:`ff7-${group}`,defaultSplit:42,minLeft:260,minRight:360});
    }
    return pagedListDetail({rows,key:row=>row.id,slots:false,selected:state.selected[group],page:state.page[group]||0,pageSize:state.pageSize[group]||12,noun:labels[group],className:"ff7-layout",splitKey:`ff7-${group}`,rowsKey:`ff7-${group}`,defaultSplit:50,minLeft:320,minRight:360,search:{key:`ff7-${group}`,value:query,label:`Search ${labels[group]}`,change:value=>{state.query[group]=value;state.page[group]=0;render()}},filters:[datasetStatus()],modOnly:modOnlySpec(group),sync:next=>{state.page[group]=next.page;state.pageSize[group]=next.pageSize;if(next.selected!==null)state.selected[group]=next.selected},change:next=>{state.page[group]=next.page;state.pageSize[group]=next.pageSize;if(next.selected!==null)state.selected[group]=next.selected;render()},master:view=>listTable(view.rows,view.selected,view.select),detail:row=>recordDetail(row)});
  }
  function unresolvedView(){
    const area=state.data.unresolved?.[state.tab];
    return detailPanel({className:"ff7-detail",title:labels[state.tab],identity:null,meta:"Not integrated",body:[
      detailSection({title:"STATUS",body:[
        detailField({label:"STATE",control:integrationStatus("not-integrated")}),
        detailField({label:"SOURCE",control:readonlyField(area?.source||"Dataset source information could not be loaded.")}),
        detailField({label:"REASON",control:readonlyField(area?.reason||"This tab has no connected editor. See Info for loading errors.")}),
        detailField({label:"NEXT",control:readonlyField(area?.unlock||"Reload the dataset availability report.")}),
      ]}),
    ]});
  }
  function syncConfigMap(config){
    const row=state.dataMap?.rows.find(item=>item.category==="tweaks");
    if(row)Object.assign(row,{status:config.available?"integrated":"partial",coverage:config.available?"structured":"unavailable",openable:config.available,sourcePath:config.path,notes:config.message});
  }
  async function refreshPlatformConfig(force=false){
    if(state.platformLoading||state.saving||state.activeSource!=="mine")return;
    if(Object.keys(platformChanges()).length){
      if(!force||!await LexeditorUI.confirmAction({title:"Discard unsaved FFNx settings?",message:"Reloading reads the installed file again. Your unsaved FFNx settings would be lost.",confirmLabel:"Discard and reload",cancelLabel:"Keep editing"}))return;
    }
    const revision=state.platformRevision;
    state.platformLoading=true;
    try{
      const config=await api("/api/platform-config");
      if(revision!==state.platformRevision||state.saving)return;
      state.platformConfig=config;state.savedPlatformConfig=clone(config);state.platformError="";syncConfigMap(config);
      if(state.tab==="tweaks")render();
    }catch(error){state.platformError=error.message;if(state.tab==="tweaks")render()}
    finally{state.platformLoading=false;shellRefresh()}
  }
  function tweakView(){
    const reload=el("button",{type:"button",disabled:readonly(),onclick:()=>refreshPlatformConfig(true)},"Reload settings");
    const view=platformConfigView({config:state.platformConfig,query:state.platformQuery,disabled:readonly(),search:value=>{state.platformQuery=value},change:(id,value)=>{
      if(readonly())return;
      const field=(state.platformConfig?.sections||[]).flatMap(section=>section.fields).find(candidate=>candidate.id===id);
      if(field){field.value=value;state.platformRevision++;shellRefresh()}
    }});
    const panel=detailPanel({className:"ff7-detail",title:"FFNx",identity:null,meta:"Runtime settings",body:[
      detailSection({title:"ACTIONS",body:[detailField({label:"CONFIGURATION",control:reload})]}),
      ...(state.platformError?[detailSection({title:"ERROR",body:[detailField({label:"MESSAGE",control:readonlyField(state.platformError)})]})]:[]),
      detailSection({title:"SETTINGS",body:[view]}),
    ]});
    return tabbedPanel({tabs:[{id:"ffnx",label:"FFNx"}],active:"ffnx",label:"Tweaks sections",change:()=>{},content:panel});
  }
  function infoView(){
    const baseline=state.dashboard.baseline,sounds=LexeditorUI.sharedSettings()?.developerMode?LexeditorUI.soundCoverageTable(state.dashboard.themeSounds?.rows||[]):null;
    return detailPanel({className:"lex-information-panel ff7-detail",icon:infoIcon(),title:identity.name,identity:null,meta:identity.edition,body:[
      detailSection({title:"GAME",body:[
        detailField({label:"Game root",control:readonlyField(state.dashboard.game.root||"Unavailable")}),
        detailField({label:"Source",control:readonlyField(baseline.source||"Unavailable")}),
      ]}),
      detailSection({title:"PROJECT",body:[
        detailField({label:"Project output",control:readonlyField(baseline.projectPath||"Unavailable")}),
        detailField({label:"Vanilla SHA-256",control:readonlyField(baseline.sha256||"Unavailable")}),
        detailField({label:"Status",control:readonlyField(baseline.message||"Unavailable")}),
      ]}),
      ...((state.dashboard.problems||[]).length?[detailSection({title:"PROBLEMS",body:(state.dashboard.problems||[]).map((problem,index)=>detailField({label:`Problem ${index+1}`,control:readonlyField(problem)}))})]:[]),
      ...(sounds?[detailSection({title:"THEME SOUNDS",body:[sounds]})]:[]),
      LexeditorUI.modLoaderSection({
        loader:"FFNx, the community runtime for the PC releases. It loads from the game folder and applies Lexeditor's data alongside its own patches.",
        output:"Edited kernel, scene, text and executable data are written into the selected project folder, not over the installed files.",
        order:"FFNx applies its own configuration first, then mod data. Two mods editing the same kernel section conflict; the later one wins.",
        safety:"Installed kernel, scene and executable files are read only. Every write goes to the project copy.",
        removal:"Point FFNx away from the project folder, or delete it. The install is already untouched.",
      }),
    ]});
  }
  function mapView(){const view=LexeditorUI.dataMap({rows:state.dataMap.rows,open:row=>{const target=row.target||row.category;if(target)navigate(target)},query:state.mapQuery,status:state.mapStatus,page:state.mapPage,sort:state.mapSort,pageSize:100,changeQuery:value=>{state.mapQuery=value;state.mapPage=0;render()},changeStatus:value=>{state.mapStatus=value;state.mapPage=0;render()},changePage:value=>{state.mapPage=value;render()},changeSort:key=>{const[active,direction]=state.mapSort;state.mapSort=[key,active===key?-direction:1];render()}});state.mapPage=view.page;return view.content}
  // The strip above the table repeated the record count the pager already
  // shows and pushed the table down a line on every dataset. What it alone
  // carried - whether this view is vanilla or a project copy, and which file
  // it came from - now rides on the pagination bar with the other status.
  function datasetStatus(){
    const metadata=category(),family=state.data.families?.[metadata?.family];
    const rows=state.records[state.tab]||[],saved=state.saved[state.tab]||[];
    const source=family?.sourceRelativePath||state.data.sourceRelativePath||metadata?.family||"";
    const usingProject=family?!!family.usingProject:!!state.data.usingProject;
    const dirty=JSON.stringify(rows)!==JSON.stringify(saved);
    const status=dirty?"Unsaved changes":usingProject?"Mod data":"Vanilla data";
    return el("span",{class:"ff7-dataset-status",style:"font-size:.75em;white-space:nowrap",
      title:String(source||"Loaded game data")},el("span",{},status));
  }
  // FF7 can tell what the mod changes by comparing each record with the saved
  // baseline for the same dataset, which is exactly what a save would write.
  function modOnlySpec(group){
    const saved=state.saved[group]||[];
    const byId=new Map(saved.map(row=>[row.id,row]));
    return {available:state.activeSource==="mine"&&saved.length>0,
      value:state.modOnly===true,
      changed:row=>{const base=byId.get(row.id);
        return !base||JSON.stringify(row)!==JSON.stringify(base);},
      change:value=>{state.modOnly=value;state.page[group]=0;render()}};
  }
  function dataWorkspace(){
    const sub=groups[parentTab(state.tab)];
    if(!sub)return el("section",{class:"ff7-workspace"},integratedView());
    const nav=subtabBar({tabs:sub.map(id=>({id,label:subtabLabels[id]||labels[id]})),active:state.tab,label:labels[parentTab(state.tab)]+" datasets",change:id=>{if(id!==state.tab)LexeditorUI.playThemeSound?.("confirm");navigate(id)}});
    return el("section",{class:"ff7-workspace lex-tabbed-panel"},nav,el("div",{class:"lex-tabbed-panel-content"},integratedView()));
  }
