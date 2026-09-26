  "use strict";
  const {el,columnList,detailPanel,detailSection,detailField,infoHelp,pagedListDetail,readonlyField}=LexeditorUI;
  const $=selector=>document.querySelector(selector);
  const TABLES=[
    {id:"EquipParamWeapon",label:"Weapons"},
    {id:"EquipParamProtector",label:"Armor"},
    {id:"EquipParamAccessory",label:"Rings"},
    {id:"Magic",label:"Spells"},
    {id:"SpEffectParam",label:"Effects"},
    {id:"NpcParam",label:"Enemies"},
  ];
  const state={booting:true,tab:"EquipParamWeapon",dirty:0,source:"",project:"",output:"",info:null,datamap:null,
    tables:{},details:{},map:{page:0,query:"",status:"",sort:["filename",1]},error:""};
  for(const table of TABLES)state.tables[table.id]={rows:[],loaded:false,selected:null,page:0,pageSize:20,query:"",sort:["id",1]};

  async function api(path,options){
    const response=await fetch(path,options);let value={};
    try{value=await response.json()}catch(_error){}
    if(!response.ok||value.error)throw new Error(value.error||(response.status+" "+response.statusText));
    return value;
  }
  const dirtyCount=()=>Number(state.dirty)||0;
  const tableState=id=>state.tables[id];

  function sortedRows(id){
    const table=tableState(id),query=table.query.trim().toLocaleLowerCase();
    const [key,dir]=table.sort;
    return table.rows.filter(row=>!query||(String(row.id)+" "+row.name).toLocaleLowerCase().includes(query))
      .sort((left,right)=>{
        const a=left[key],b=right[key];
        const result=typeof a==="number"&&typeof b==="number"?a-b:String(a).localeCompare(String(b),undefined,{numeric:true,sensitivity:"base"});
        return result*dir;
      });
  }

  async function loadTable(id,force=false){
    const table=tableState(id);
    if(!table.loaded||force){
      const result=await api("/api/table?name="+encodeURIComponent(id));
      table.rows=result.rows||[];table.loaded=true;state.dirty=result.dirtyCount??state.dirty;
      if(!table.rows.some(row=>row.id===table.selected))table.selected=table.rows[0]?.id??null;
    }
    if(table.selected!==null)await loadDetail(id,table.selected,force);
  }
  async function loadDetail(id,rowId,force=false){
    const current=state.details[id];
    if(!force&&current&&current.id===rowId)return current;
    const result=await api("/api/row?table="+encodeURIComponent(id)+"&id="+encodeURIComponent(rowId));
    state.details[id]=result.row;state.dirty=result.dirtyCount??state.dirty;return result.row;
  }

  function fieldHelp(field){
    const parts=[];if(field.description)parts.push(field.description);
    if(field.reference)parts.push("This stores a row ID referencing "+field.reference+".");
    if(field.enumName)parts.push("Choices come from the pinned "+field.enumName+" metadata.");
    return parts.join(" ");
  }
  async function editField(table,row,field,value){
    try{
      const result=await api("/api/edit",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({table,id:row.id,field:field.key,value})});
      state.details[table]=result.row;state.dirty=result.dirtyCount||0;shell.refresh();render();
    }catch(error){
      LexeditorUI.showAlert({title:"Edit rejected",message:error.message||String(error)});
      await loadDetail(table,row.id,true);render();
    }
  }
  function fieldControl(table,row,field){
    if(field.type==="bool")return el("input",{type:"checkbox",checked:!!field.value,"aria-label":field.label,
      "data-ds3-field":field.key,onchange:event=>editField(table,row,field,event.target.checked?1:0)});
    if(field.type==="enum"){
      const entries=Object.entries(field.enum||{}).sort((a,b)=>Number(a[0])-Number(b[0]));
      const select=el("select",{"aria-label":field.label,"data-ds3-field":field.key,
        onchange:event=>editField(table,row,field,event.target.value)},
        ...entries.map(([value,label])=>el("option",{value},value+" — "+label)));
      select.value=String(field.value);return select;
    }
    let submitted=String(field.value),commitTimer=0;
    const submit=control=>{
      const value=String(control?.value??"").replace(/,/g,"").trim();
      if(!value||value===submitted)return;
      submitted=value;
      void editField(table,row,field,value);
    };
    const schedule=event=>{
      clearTimeout(commitTimer);
      const control=event.currentTarget;
      commitTimer=setTimeout(()=>submit(control),120);
    };
    const commit=event=>{clearTimeout(commitTimer);submit(event.currentTarget)};
    const attrs={type:"number",value:field.value,step:/^f/.test(field.dtype)?"any":1,
      "aria-label":field.label,"data-ds3-field":field.key,
      oninput:schedule,onchange:commit,onblur:commit};
    if(field.minimum!==null&&field.minimum!==undefined)attrs.min=field.minimum;
    if(field.maximum!==null&&field.maximum!==undefined)attrs.max=field.maximum;
    return el("input",attrs);
  }
  function rowDetail(table,rowIdentity){
    const row=state.details[table];
    if(!row||row.id!==rowIdentity.id)return detailPanel({title:rowIdentity.name,identity:String(rowIdentity.id),
      body:[LexeditorUI.loadingPanel({label:"Loading this record"})]});
    const groups=new Map();
    for(const field of row.fields||[]){
      if(!groups.has(field.group))groups.set(field.group,[]);
      const help=fieldHelp(field);
      groups.get(field.group).push(detailField({label:field.label,property:field.key,control:fieldControl(table,row,field),
        dataType:String(field.dtype||"").toUpperCase(),min:field.minimum,max:field.maximum,
        help:help?infoHelp(help):null,attrs:{"data-field":field.key}}));
    }
    return detailPanel({title:row.name,identity:String(row.id),meta:row.description,
      body:[...groups].map(([title,fields])=>detailSection({title,body:fields}))});
  }

  function renderTable(id){
    const table=tableState(id),label=TABLES.find(value=>value.id===id)?.label||id;
    if(!table.loaded){$("#main").replaceChildren(detailPanel({title:label,body:[LexeditorUI.loadingPanel({label:"Loading records"})]}));return}
    if(!table.rows.length){$("#main").replaceChildren(detailPanel({title:label,body:[LexeditorUI.detailNote("No records were found in this parameter table.")]}));return}
    const view=pagedListDetail({addDisabledReason:"Dark Souls III params can take new row IDs, but Lexeditor only edits existing rows. Adding a row is not supported yet.",
      rows:sortedRows(id),key:row=>row.id,slots:false,noun:"records",page:table.page,pageSize:table.pageSize,
      selected:table.selected,className:"ds3-layout",splitKey:"ds3-"+id,rowsKey:"ds3-"+id,
      defaultSplit:42,minLeft:280,minRight:360,fit:{minRowHeight:34},
      search:{key:"ds3-"+id+"-search",value:table.query,label:"Search "+label,
        change:value=>{table.query=value;table.page=0;render()}},
      sync:next=>{table.page=next.page;table.pageSize=next.pageSize;if(next.selected!==null)table.selected=next.selected},
      change:next=>{table.page=next.page;table.pageSize=next.pageSize;if(next.selected!==null)table.selected=next.selected;render()},
      master:({rows:listed,selected,select})=>columnList({
        rows:listed,key:row=>row.id,selected,
        select:row=>{select(row);table.selected=row.id;void loadDetail(id,row.id,true).then(()=>render())},
        sortState:{key:table.sort[0],dir:table.sort[1]},
        sort:key=>{table.sort=[key,table.sort[0]===key?-table.sort[1]:1];table.page=0;render()},
        columns:[
          {key:"id",label:"ID",numberedId:true,numeric:true,sortable:true,align:"start"},
          {key:"name",label:"Name",sortable:true,align:"start"},
        ]}),
      detail:row=>rowDetail(id,row),
      emptyDetail:()=>detailPanel({title:"No matching records",body:[LexeditorUI.detailNote("Change the search to show a record.")]}),
    });
    $("#main").replaceChildren(view);
  }

  function renderDataMap(){
    const map=state.map;
    const view=LexeditorUI.dataMap({plugin:"ds3",rows:state.datamap?.rows||[],page:map.page,query:map.query,status:map.status,sort:map.sort,
      open:row=>{if(row.target)navigate(row.target)},
      changePage:value=>{map.page=value;render()},changeQuery:value=>{map.query=value;map.page=0;render()},
      changeStatus:value=>{map.status=value;map.page=0;render()},
      changeSort:key=>{map.sort=[key,map.sort[0]===key?-map.sort[1]:1];render()}});
    $("#main").replaceChildren(view.content);
  }

  function renderInfo(){
    const info=state.info||{},target=info.target||{};
    $("#main").replaceChildren(detailPanel({className:"lex-information-panel",icon:LexeditorUI.infoIcon(),title:"Information",
      meta:"Dark Souls III parameter integration and safe export state",body:[
        detailSection({title:"TARGET",body:[
          detailField({label:"PLATFORM",control:readonlyField(target.platform||"PC / Steam")}),
          detailField({label:"APP VERSION",control:readonlyField(target.appVersion||"1.15.2"),
            help:infoHelp("This is the supported PC target version. Real-game acceptance of this candidate is still pending.")}),
          detailField({label:"REGULATION",control:readonlyField(target.regulationVersion||"1.35")}),
          detailField({label:"ARCHIVE BUILD",control:readonlyField(target.archiveBuild||"—"),
            help:infoHelp("The build string the loaded regulation archive stores in its own header, for example 01350000 for Regulation 1.35. The editor patches only the build it has audited, and it refuses another one instead of guessing at changed row layouts.")}),
          detailField({label:"PARAMDEF DATA",control:readonlyField(String(target.paramdefDataVersion||201))})]}),
        detailSection({title:"FILES",body:[
          detailField({label:"SOURCE",control:readonlyField(info.source||"Unavailable")}),
          detailField({label:"PROJECT",control:readonlyField(info.project||"Unavailable")}),
          detailField({label:"OUTPUT",control:readonlyField(info.output||"Unavailable")}),
          LexeditorUI.detailNote(info.safety||"Installed game files are read-only.")]}),
        detailSection({title:"ACCEPTANCE",body:[
          LexeditorUI.notice({tone:"warning",message:info.realGameVerified
            ?"This candidate has recorded real-game verification."
            :"No real-game verification has been recorded. Parser, roundtrip, browser, and packaged-candidate evidence are separate from in-game acceptance."})]}),
        LexeditorUI.modLoaderSection({
          loader:"Lexeditor does not install or activate a DS3 mod loader. For offline acceptance, configure a compatible external loader separately.",
          output:"Save writes one encrypted Data0.bdt into the selected Lexeditor project and never writes the installed Game/Data0.bdt.",
          order:"Lexeditor authors one regulation archive. It does not define a priority stack or semantically merge separate external Data0.bdt replacements.",
          safety:"No game executable, online setting, anti-cheat setting, save, or installed archive is changed.",
          removal:"Stop loading the project Data0.bdt in the external loader, or delete the project folder. The installed game remains unchanged."})]}));
  }

  function renderError(){
    $("#main").replaceChildren(detailPanel({title:"Dark Souls III could not load",body:[
      LexeditorUI.notice({tone:"warning",message:state.error||"Unknown loading error."}),
      LexeditorUI.detailNote("The editor has not written any game or project file.")]}));
  }
  function render(){
    if(state.error){renderError();shell?.refresh?.();return}
    if(state.booting)return;
    if(state.tab==="datamap")renderDataMap();else if(state.tab==="info")renderInfo();else renderTable(state.tab);
    shell?.refresh?.();
  }
  async function navigate(value){
    state.tab=value;
    if(TABLES.some(table=>table.id===value)){
      try{await loadTable(value)}catch(error){state.error=error.message||String(error)}
    }
    render();
  }

  async function saveProject(){
    const result=await api("/api/save",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    state.dirty=result.dirtyCount||0;state.source=result.source||state.source;state.info=await api("/api/info");
    if(TABLES.some(table=>table.id===state.tab))await loadDetail(state.tab,tableState(state.tab).selected,true);
    LexeditorUI.showToast("Exported "+result.path);shell.refresh();render();
  }
  async function discardChanges(){
    const result=await api("/api/discard",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    state.dirty=result.dirtyCount||0;state.source=result.source||state.source;state.details={};
    for(const table of Object.values(state.tables))table.loaded=false;
    if(TABLES.some(table=>table.id===state.tab))await loadTable(state.tab,true);
    state.info=await api("/api/info");shell.refresh();render();
  }
