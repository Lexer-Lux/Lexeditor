"use strict";

// Shared navigation and record pages. Format-specific command and map controls
// remain in their existing modules.
const ctPages = {};
const ctMap = {page:0,query:"",status:"",sort:["filename",1]};
const ctLanguages = {
  de:["🇩🇪","Deutsch"],en:["🇬🇧","English"],es:["🇪🇸","Español"],fr:["🇫🇷","Français"],
  it:["🇮🇹","Italiano"],ja:["🇯🇵","日本語"],jp:["🇯🇵","日本語"],ko:["🇰🇷","한국어"],
  kr:["🇰🇷","한국어"],zh:["🇨🇳","中文"],cn:["🇨🇳","简体中文"],tw:["🇹🇼","繁體中文"],"zh-Hans":["🇨🇳","简体中文"],"zh-Hant":["🇹🇼","繁體中文"],
  ru:["🇷🇺","Русский"],pt:["🇵🇹","Português"],br:["🇧🇷","Português do Brasil"]
};

function ctLanguageLabel(id){
  const rect=(x,y,w,h,c)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${c}"/>`;
  const horizontal=colors=>colors.map((c,i)=>rect(0,i*20/colors.length,30,20/colors.length,c)).join("");
  const vertical=colors=>colors.map((c,i)=>rect(i*30/colors.length,0,30/colors.length,20,c)).join("");
  const star=(x,y,r,c,points=5)=>{const p=[];for(let i=0;i<points*2;i++){const a=-Math.PI/2+i*Math.PI/points,rr=i%2?r*.4:r;p.push(`${x+Math.cos(a)*rr},${y+Math.sin(a)*rr}`);}return `<polygon points="${p.join(" ")}" fill="${c}"/>`;};
  const flags={
    de:horizontal(["#111","#d00","#ffce00"]),
    fr:vertical(["#002395","white","#ed2939"]),it:vertical(["#009246","white","#ce2b37"]),
    es:horizontal(["#aa151b","#f1bf00","#f1bf00","#aa151b"])+rect(8,8,3,4,"#aa151b"),
    en:rect(0,0,30,20,"#012169")+'<path d="M0 0L30 20M30 0L0 20" stroke="white" stroke-width="5"/><path d="M0 0L30 20M30 0L0 20" stroke="#c8102e" stroke-width="2"/>'+rect(12,0,6,20,"white")+rect(0,7,30,6,"white")+rect(13,0,4,20,"#c8102e")+rect(0,8,30,4,"#c8102e"),
    ja:rect(0,0,30,20,"white")+'<circle cx="15" cy="10" r="6" fill="#bc002d"/>',
    ko:rect(0,0,30,20,"white")+'<circle cx="15" cy="10" r="5" fill="#cd2e3a"/><path d="M10 10a5 5 0 0 0 10 0a2.5 2.5 0 0 0-5 0a2.5 2.5 0 0 1-5 0" fill="#0047a0"/><g stroke="#111" stroke-width=".8"><path d="M4 5l3-3m-2 4l3-3m-2 4l3-3M21 16l3-3m-2 4l3-3m-2 4l3-3M22 2l3 3m-4-2l3 3m-4-2l3 3M4 13l3 3m-4-2l3 3m-4-2l3 3"/></g>',
    "zh-Hans":rect(0,0,30,20,"#de2910")+star(5,5,3,"#ffde00")+[[10,2],[12,5],[12,8],[10,10]].map(([x,y])=>star(x,y,1,"#ffde00")).join(""),
    "zh-Hant":rect(0,0,30,20,"#fe0000")+rect(0,0,15,10,"#000095")+star(7.5,5,4,"white",12)+'<circle cx="7.5" cy="5" r="2.2" fill="white"/>'
  };
  const name=ctLanguages[id]?.[1]||id;
  const body=flags[id];
  return el("span",{class:"ct-language-label"},body?el("img",{alt:"",width:24,height:16,src:"data:image/svg+xml,"+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 20">${body}</svg>`)}):null,name);
}

state.messages.language = "";
state.infoSection = "setup";
loadDeployment = async function(){state.deployment=await api("/api/deployment?quick=1");};

function ctRecordPage(key, rows, columns, detail, options={}) {
  const page = ctPages[key] ||= {page:0,selected:null,query:""};
  const filtered = rows.filter(row=>!page.query || Object.values(row).some(value=>
    typeof value!=="object" && String(value??"").toLocaleLowerCase().includes(page.query.toLocaleLowerCase())));
  return LexeditorUI.pagedListDetail({
    rows:filtered,key:row=>row.id,slots:true,noun:options.noun||"records",
    page:page.page,selected:page.selected,revealSelected:false,maxBarrels:1,
    splitKey:`chrono-${key}`,rowsKey:`chrono-${key}-rows`,className:`ct-${key}-page`,
    defaultSplit:55,minLeft:260,minRight:260,
    search:{key:`chrono-${key}-search`,value:page.query,label:`Search ${options.noun||key}`,
      change:value=>{page.query=value;page.page=0;render();}},
    sync:next=>{
      const changed=next.selected!==page.selected;
      Object.assign(page,next);
      if(changed&&options.select){const row=rows.find(row=>row.id===next.selected);if(row)queueMicrotask(()=>options.select(row));}
    },
    change:next=>{
      const changed=next.selected!==page.selected;Object.assign(page,next);render();
      if(changed&&options.select){const row=rows.find(row=>row.id===next.selected);if(row)options.select(row);}
    },
    master:({rows,selected,select})=>LexeditorUI.columnList({rows,key:row=>row.id,selected,
      select:row=>{select(row);options.select?.(row);},columns,
      template:columns.map((column,index)=>index===0?(key==="events"?"76px":"60px"):"minmax(100px,1fr)").join(" ")}),
    detail,
    emptyDetail:()=>LexeditorUI.detailPanel({title:"No matching records"})
  });
}

loadMessage = async function() {
  if (!state.messages.catalog.length) await loadMessageCatalog();
  const languages=[...new Set(state.messages.catalog.map(row=>row.language))];
  if(!languages.includes(state.messages.language))state.messages.language=languages.includes("en")?"en":languages[0]||"";
  if(!state.messages.language){state.messages.data=state.messages.original=null;return;}
  const source=state.source,language=state.messages.language;
  const data=await api(`/api/messages/language?${new URLSearchParams({language,source})}`);
  if(source!==state.source||language!==state.messages.language)return;
  state.messages.data=data;state.messages.original=clone(data);
};

messageChanges = function() {
  const original=new Map((state.messages.original?.rows||[]).map(row=>[row.id,row.text]));
  return (state.messages.data?.rows||[]).filter(row=>original.get(row.id)!==row.text);
};

const ctOriginalSave=save,ctOriginalDiscard=discard;
save = async function() {
  if(state.tab!=="text")return ctOriginalSave();
  if(state.source!=="mine"||state.busy)return;
  state.busy=true;state.error="";refreshShell();
  try {
    const files=new Map();
    for(const row of messageChanges()){
      if(!files.has(row.path))files.set(row.path,[]);
      files.get(row.path).push({id:row.line,text:row.text});
    }
    for(const [path,changes] of files){
      const saved=await api("/api/save/message",{path,changes,sha256:state.messages.original.tables[path].sha256});
      state.messages.original.tables[path].sha256=saved.sha256;
      const savedRows=new Map(saved.rows.map(row=>[row.id,row.text]));
      for(const row of state.messages.original.rows)if(row.path===path)row.text=savedRows.get(row.line);
    }
    await loadDashboard();
  }catch(error){state.error=String(error.message||error);}
  finally{state.busy=false;render();refreshShell();}
};
discard = async function(){if(state.tab!=="text")return ctOriginalDiscard();await loadMessage();render();refreshShell();};

textView = function() {
  const languages=[...new Set(state.messages.catalog.map(row=>row.language))].sort();
  const bar=LexeditorUI.subtabBar({label:"Text languages",active:state.messages.language,
    tabs:languages.map(id=>({id,label:ctLanguageLabel(id)})),
    change:async language=>{
      if(language===state.messages.language||!await abandonAllowed())return;
      state.messages.language=language;state.messages.data=null;await loadActive();
    }});
  const data=state.messages.data;
  const content=ctRecordPage(`text-${state.messages.language}`,data?.rows||[],[
    {key:"line",label:"ID"},{key:"key",label:"Key"},{key:"text",label:"Text"},{key:"file",label:"Resource"}
  ],row=>LexeditorUI.detailPanel({title:row.key||`Line ${row.line}`,identity:row.line,body:[
    LexeditorUI.detailField({label:"Resource",control:LexeditorUI.readonlyField(row.path)}),
    LexeditorUI.detailField({label:"Text",dataType:"STRING",control:el("textarea",{
      class:"ct-text-editor",disabled:state.source!=="mine",rows:5,
      oninput:event=>{row.text=event.target.value;refreshShell();}
    },row.text)})
  ]}),{noun:"text entries"});
  return el("div",{class:"ct-shared-page"},bar,errorNode(),content);
};

loadEvents = async function(){
  const source=state.source,first=await api(`/api/events?${new URLSearchParams({source,limit:"250"})}`);
  const rows=[...first.rows];
  for(let offset=rows.length;offset<first.matchCount;offset+=250){
    const next=await api(`/api/events?${new URLSearchParams({source,limit:"250",offset:String(offset)})}`);
    rows.push(...next.rows);
  }
  if(source!==state.source)return;
  state.events.data={...first,rows};
  const page=ctPages.events ||= {page:0,selected:null,query:""};
  if(!rows.some(row=>row.id===page.selected))page.selected=rows.find(row=>!row.problem)?.id??rows[0]?.id??null;
  state.events.selected=page.selected;
  await loadEventDetail(page.selected);
};
loadEventDetail = async function(id){
  state.events.detail=null;
  const source=state.source;
  const row=state.events.data?.rows.find(row=>row.id===id);
  if(row?.problem){state.events.detail={...row,objects:[]};return;}
  if(id===null||id===undefined)return;
  try{const detail=await api(`/api/events?${new URLSearchParams({id:String(id),source})}`);
    if(state.events.selected===id&&source===state.source)state.events.detail=detail;
  }catch(error){if(state.events.selected===id&&source===state.source)state.events.detail={...row,problem:String(error.message||error),objects:[]};}
};
eventsView = function(){
  return el("div",{class:"ct-shared-page"},errorNode(),ctRecordPage("events",state.events.data?.rows||[],[
    {key:"id",label:"ID"},{key:"name",label:"Event"},{key:"objectCount",label:"Objects"},
    {key:"decodedCommandCount",label:"Commands"},{key:"problem",label:"Status",render:row=>row.problem?"Unavailable":"Ready"}
  ],row=>{
    const event=state.events.detail?.id===row.id?state.events.detail:null;
    const body=[];
    if(!event)body.push(el("p",{},"Loading event…"));
    else if(event.problem)body.push(el("p",{role:"alert"},event.problem));
    else for(const object of event.objects||[]){
      body.push(el("details",{class:"ct-object",open:object.id===0},
        el("summary",{},`Object ${object.id}`),
        ...object.functions.map(fn=>el("details",{class:"ct-object",open:object.id===0&&fn.id===0},
          el("summary",{},fn.name),functionCommandView(fn,object.id)))));
    }
    return LexeditorUI.detailPanel({title:row.name,identity:row.id,body});
  },{noun:"events",select:async row=>{state.events.selected=row.id;await loadEventDetail(row.id);render();}}));
};

dataMapView = function(){
  const rows=(state.dataMap?.rows||[]).map(row=>({...row,
    coverage:["structured","view","source","unavailable"].includes(row.coverage)?row.coverage:/structured|fixed-write/.test(String(row.coverage))?"structured":row.openable?"view":"unavailable",
    target:row.target==="deployment"?"info":row.target}));
  return LexeditorUI.dataMap({rows,...ctMap,open:row=>navigate(row.target),
    changePage:value=>{ctMap.page=value;render();},changeQuery:value=>{ctMap.query=value;ctMap.page=0;render();},
    changeStatus:value=>{ctMap.status=value;ctMap.page=0;render();},
    changeSort:key=>{ctMap.sort=[key,ctMap.sort[0]===key?-ctMap.sort[1]:1];render();}}).content;
};

function ctInfoView(){
  const bar=LexeditorUI.subtabBar({label:"Plugin information",active:state.infoSection,
    tabs:[{id:"setup",label:"Setup"},{id:"files",label:"Project files"}],
    change:value=>{state.infoSection=value;render();}});
  let content;
  if(state.infoSection==="files")content=ctRecordPage("project-files",(state.changes?.rows||[]).map(row=>({...row,id:row.path})),[
    {key:"path",label:"Resource"},{key:"status",label:"Status"},{key:"size",label:"Size"}
  ],row=>LexeditorUI.detailPanel({title:row.path,body:[
    LexeditorUI.detailField({label:"Status",control:LexeditorUI.readonlyField(row.status)}),
    el("button",{type:"button",onclick:()=>revertOverride(row)},"Revert to Vanilla")
  ]}),{noun:"project files"});
  else {
    const data=state.deployment,c=data?.ctext;
    content=LexeditorUI.detailPanel({className:"lex-information-panel",title:"Chrono Trigger",body:[chronoModLoaderSection(),
      LexeditorUI.detailField({label:"Runtime",control:LexeditorUI.readonlyField(c?.installed?"CTExt installed":"CTExt not installed")}),
      LexeditorUI.detailField({label:"Project",control:LexeditorUI.readonlyField(c?.projectName||"No project selected")}),
      el("div",{class:"ct-deploy-actions"},
        el("button",{type:"button",disabled:!data?.canDeploy||state.busy||state.source!=="mine",onclick:deployProject},"Deploy and activate"),
        el("button",{type:"button",disabled:state.busy||state.source!=="mine",onclick:exportCtp},"Export CTP"),
        el("button",{type:"button",disabled:state.busy,onclick:async()=>{
          state.busy=true;state.error="";render();refreshShell();
          try{state.deployment=await api("/api/deployment");}catch(error){state.error=String(error.message||error);}
          finally{state.busy=false;render();refreshShell();}
        }},"Check project")) ,
      ...(data?.audit?.issues||[]).filter(row=>row.level!=="info").map(row=>el("p",{role:"alert"},row.message)),
      state.exportResult?el("p",{role:"status"},`Exported: ${state.exportResult.path}`):null,
      window.ChronoTriggerEventAudit(),
      LexeditorUI.creditsPanel("chrono-trigger")
    ]});
  }
  return el("div",{class:"ct-shared-page"},bar,errorNode(),content);
}

abandonAllowed = async function(){
  if(!dirtyCount())return true;
  if(!await LexeditorUI.confirmAction({title:"Unsaved changes",message:"Discard unsaved Chrono Trigger edits?",confirmLabel:"Discard"}))return false;
  await discard();return true;
};

let ctLoadGeneration=0;
loadActive = async function(){
  const generation=++ctLoadGeneration,tab=state.tab;
  state.busy=true;state.error="";render();refreshShell();
  try{
    if(!state.dashboard)await loadDashboard();
    if(tab==="text")await loadMessage();
    else if(tab==="events")await loadEvents();
    else if(tab==="info")await Promise.all([loadDeployment(),loadChanges()]);
    else if(tab==="datamap")await loadDataMap();
    else if(tab==="resources")await loadArchive();
    else if(tab==="worlds")await loadWorlds();
    else await loadScenes();
  }catch(error){if(generation===ctLoadGeneration)state.error=String(error.message||error);}
  finally{if(generation===ctLoadGeneration){state.busy=false;render();refreshShell();}}
};
navigate = async function(value){
  if(value==="deployment"||value==="changes"){state.infoSection=value==="changes"?"files":"setup";value="info";}
  if(value===state.tab)return;
  if(!await abandonAllowed())return;
  state.tab=value;await loadActive();
};
const ctLegacyRender=render;
render=function(){
  const main=document.querySelector("#main");
  if(state.busy){main.replaceChildren(el("div",{class:"ct-empty",role:"status"},"Loading…"));return;}
  if(state.tab==="info")main.replaceChildren(ctInfoView());
  else ctLegacyRender();
  main.querySelectorAll(".ct-summary").forEach(node=>node.remove());
};
