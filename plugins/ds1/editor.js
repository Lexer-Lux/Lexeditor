"use strict";
const {el,detailPanel,detailSection,detailField,readonlyField,infoHelp,pagedListDetail,columnList,subtabBar}=LexeditorUI;
const state={tab:"items",sub:"consumables",tabs:[],rows:[],selected:null,row:null,dirty:0,pending:0,
  readOnly:true,query:"",page:0,pageSize:20,sort:{key:"id",dir:1},error:""};
let edits=Promise.resolve(),navigation=0;
const key=row=>`${row.table}:${row.id}`;
async function api(path,body){
  const response=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const result=await response.json();
  if(!response.ok||result.error)throw new Error(result.error||response.statusText);
  return result;
}
const notify=error=>LexeditorUI.showAlert({title:"Dark Souls",message:error.message||String(error)});
const shell=LexeditorUI.mountShell({
  host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ds1",name:"Dark Souls Remastered"},
  tabs:[{id:"items",label:"Items",help:"Edit item properties in the selected mod. Vanilla is read-only. Unknown fields stay protected. Saves do not install a mod."}],
  activeTab:()=>state.tab,navigate:()=>navigate("items"),
  info:()=>navigate("info"),infoActive:()=>state.tab==="info",
  readonly:()=>state.readOnly,dirtyCount:()=>state.dirty+state.pending,save,discard
});
async function refreshState(){
  const result=await api("/api/state");
  state.tabs=result.tabs;state.readOnly=result.readOnly;state.dirty=result.dirtyCount;
}
async function loadItems(){
  const sub=state.sub;
  const result=await api("/api/table?tab="+encodeURIComponent(sub));
  if(state.sub!==sub)return;
  state.rows=result.rows;state.dirty=result.dirtyCount;
  if(!state.rows.some(row=>key(row)===state.selected))state.selected=state.rows[0]?key(state.rows[0]):null;
  await loadDetail();
}
async function loadDetail(){
  const row=state.rows.find(row=>key(row)===state.selected);
  if(!row){state.row=null;return;}
  const result=await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}`);
  if(state.selected===key(row))state.row=result.row;
}
async function navigate(tab,sub=state.sub){
  const token=++navigation;await edits;state.tab=tab;
  if(sub!==state.sub){state.sub=sub;state.selected=null;state.query="";state.page=0;}
  try{if(tab==="items")await loadItems();if(token!==navigation)return;state.error="";render();}
  catch(error){if(token===navigation){state.error=error.message;render();}}
}
async function save(){
  await edits;
  try{await api("/api/save",{});await refreshState();shell.refresh();LexeditorUI.showToast("Items saved to the mod project.");}
  catch(error){notify(error);throw error;}
}
async function discard(){
  await edits;
  try{await api("/api/discard",{});await refreshState();await loadItems();render();}catch(error){notify(error);}
}
function commit(row,field,value,control){
  if(state.readOnly||!field.editable)return;
  state.pending++;shell.refresh();
  edits=edits.then(async()=>{
    try{
      const result=await api("/api/edit",{table:row.table,id:row.id,field:field.key,value});
      state.dirty=result.dirtyCount;
      if(state.row&&key(state.row)===key(row))state.row=result.row;
      const changed=result.row.fields.find(item=>item.key===field.key);
      if(control.isConnected){if(field.type==="bool")control.checked=!!changed.value;else control.value=String(changed.value);}
      if(["goodsType","weaponCategory"].includes(field.key)){await loadItems();render();}
    }catch(error){
      notify(error);
      const result=await api(`/api/row?table=${encodeURIComponent(row.table)}&id=${row.id}`);
      const original=result.row.fields.find(item=>item.key===field.key);
      if(control.isConnected){if(field.type==="bool")control.checked=!!original.value;else control.value=String(original.value);}
    }finally{state.pending--;shell.refresh();}
  }).catch(notify);
}
function controlFor(row,field){
  if(!field.editable)return readonlyField(field.value,{"aria-label":field.label});
  const attrs={"aria-label":field.label,"data-field-key":field.key};
  // The shared shell catches edit attempts in Vanilla and offers Create a mod.
  if(field.type==="bool")return el("input",{...attrs,type:"checkbox",checked:!!field.value,
    onchange:event=>commit(row,field,event.target.checked?1:0,event.target)});
  if(field.type==="enum"){
    const choices=Object.entries(field.enum);
    if(!choices.some(([value])=>value===String(field.value)))choices.unshift([String(field.value),`Unknown (${field.value})`]);
    const control=el("select",{...attrs,onchange:event=>commit(row,field,Number(event.target.value),event.target)},
      ...choices.map(([value,label])=>el("option",{value,disabled:!(value in field.enum)},label)));
    control.value=String(field.value);return control;
  }
  return el("input",{...attrs,type:"number",value:field.value,min:field.minimum,max:field.maximum,
    step:/^(f|angle)/.test(field.dtype)?"any":1,onchange:event=>{
      const input=event.target;if(!input.value.trim()||!input.checkValidity()){input.reportValidity();return;}
      commit(row,field,Number(input.value),input);
    }});
}
function groupFor(field){
  const name=field.key.toLowerCase();
  if(/icon|model|sort|menu|visual|sfx|material/.test(name))return "Appearance";
  if(/price|value|trophy|shop|qwc/.test(name))return "Value & rewards";
  if(/guard|defen|resist|damagecut/.test(name))return "Defense";
  if(/attack|damage|correct|reinforce|repa|durability/.test(name))return "Combat";
  if(/ref|speffect|behavior|bullet|replace|magicid/.test(name))return "Effects & references";
  if(/require|proper|slot|consume|stamina|dexterity|humanity|hero/.test(name))return "Requirements & costs";
  if(/motion|anim|spatk|hold/.test(name))return "Use behavior";
  return "Properties";
}
function detail(){
  if(!state.row)return detailPanel({title:"Properties",body:[LexeditorUI.detailNote("Select an item.")]});
  if(key(state.row)!==state.selected)return detailPanel({title:"Properties",body:[LexeditorUI.loadingPanel({label:"Loading item"})]});
  const groups=new Map();
  for(const field of state.row.fields){
    const group=groupFor(field);if(!groups.has(group))groups.set(group,[]);
    let help=field.description.trim();
    if(!field.editable)help="This property is preserved. Its choices or behavior are not sufficiently documented for editing.";
    if(help.replace(/[.\s]/g,"").toLowerCase()===field.label.replace(/[.\s]/g,"").toLowerCase())help="";
    groups.get(group).push(detailField({label:field.label,property:field.key,control:controlFor(state.row,field),
      help:help?infoHelp(help):null,dataType:field.dtype.toUpperCase(),min:field.minimum,max:field.maximum}));
  }
  return detailPanel({title:"Properties",paginate:{inline:true},
    body:[...groups].map(([title,body])=>detailSection({title,body}))});
}
function renderItems(){
  const query=state.query.toLowerCase();
  const rows=state.rows.filter(row=>(row.id+" "+row.name).toLowerCase().includes(query)).sort((a,b)=>{
    const left=a[state.sort.key],right=b[state.sort.key];
    return state.sort.dir*(typeof left==="number"?left-right:String(left).localeCompare(String(right),undefined,{numeric:true}));
  });
  const view=pagedListDetail({className:"ds1-records",rows,key,selected:state.selected,slots:false,noun:"items",
    page:state.page,pageSize:state.pageSize,defaultSplit:32,minLeft:230,minRight:380,splitKey:"ds1-items",rowsKey:"ds1-items-"+state.sub,
    search:{key:"ds1-items-search",value:state.query,label:"Search items",change:value=>{state.query=value;state.page=0;render();}},
    sync:next=>{
      state.page=next.page;state.pageSize=next.pageSize;
      if(state.selected!==next.selected){state.selected=next.selected;void loadDetail().then(render).catch(notify);}
    },
    change:next=>{state.page=next.page;state.pageSize=next.pageSize;render();},
    master:({rows:listed,selected,select})=>columnList({rows:listed,key,selected,sortState:state.sort,
      sort:column=>{state.sort={key:column,dir:state.sort.key===column?-state.sort.dir:1};render();},
      select:async row=>{await edits;select(row);state.selected=key(row);await loadDetail();render();},
      columns:[{key:"id",label:"ID",numberedId:true,numeric:true,sortable:true,align:"start"},{key:"name",label:"Name",sortable:true,grow:1}]}),
    detail,emptyDetail:()=>detailPanel({title:"No matching items",body:[LexeditorUI.detailNote("Change the search to find an item.")]})});
  return el("div",{class:"ds1-items"},subtabBar({tabs:state.tabs,order:"given",active:state.sub,label:"Items",change:id=>navigate("items",id)}),view);
}
function renderInfo(){
  return detailPanel({className:"lex-information-panel",title:"Information",body:[
    detailSection({title:"ITEMS",body:[detailField({label:"EDITION",control:readonlyField("Dark Souls Remastered / Steam")}),
      detailField({label:"SUPPORT",control:readonlyField("Item properties"),help:infoHelp("Edit documented item properties. Names are reference labels. Unknown fields and padding stay unchanged. Saves go to the selected mod project.")})]}),
    LexeditorUI.modLoaderSection({loader:"External loading is not configured by this editor.",
      output:"The selected mod contains param/GameParam/GameParam.parambnd.dcx.",
      order:"One complete parameter archive. Separate archives are not merged.",
      safety:"Saves replace only the mod copy. Installed files and saves are not modified.",
      removal:"Remove the mod copy. Nothing is installed into the game."})]});
}
function render(){
  document.querySelector("#main").replaceChildren(state.error?LexeditorUI.notice({tone:"warning",message:state.error}):state.tab==="items"?renderItems():renderInfo());
  shell.refresh();
}
async function boot(){
  try{await refreshState();await loadItems();render();}catch(error){state.error=error.message;render();}
  finally{document.body.dataset.ds1Ready=state.error?"error":"true";await LexeditorUI.finishPluginLoading();}
}
window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&(state.dirty||state.pending))event.preventDefault();});
boot();
