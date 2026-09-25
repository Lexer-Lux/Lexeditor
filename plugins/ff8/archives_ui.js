// What is inside the game's archives: the entry names, their stored sizes and
// whether they are compressed. Read-only by design - the plugin extracts what
// it edits into the project copy, and browsing must never write to the game.
function FF8ArchivesUI({el,columnList,pagedPane,pager,detailPanel,detailSection,detailField,
                        readonlyField,infoHelp,notice,panelLayout,shell,formatNumber}){
  const local={archives:[],archive:"main",query:"",page:0,pageSize:60,data:null,
    selected:null,error:"",busy:false,loaded:false,source:""};
  async function api(path,options){
    const response=await fetch(path,options||{}),value=await response.json();
    if(!response.ok)throw new Error(value.error||response.statusText);
    return value;
  }
  async function loadArchives(){
    try{const payload=await api("/api/archives");local.archives=payload.rows||[];local.source=payload.source||"";
      if(!local.archives.some(row=>row.name===local.archive&&row.available))
        local.archive=(local.archives.find(row=>row.available)||{name:"main"}).name;
      local.error="";}
    catch(error){local.error=String(error.message||error)}
  }
  async function loadEntries(){
    if(!local.archive)return;
    local.busy=true;
    try{const query=new URLSearchParams({name:local.archive,query:local.query,
        page:String(local.page),pageSize:String(local.pageSize)});
      local.data=await api(`/api/archive?${query}`);local.selected=null;local.error="";}
    catch(error){local.error=String(error.message||error);local.data=null}
    finally{local.busy=false}
  }
  function readable(bytes){
    const value=Number(bytes)||0;
    if(value>=1024*1024)return `${formatNumber(Math.round(value/1024/1024*10)/10)} MB`;
    if(value>=1024)return `${formatNumber(Math.round(value/1024))} KB`;
    return `${formatNumber(value)} B`;
  }
  function entryDetail(row){
    if(!row)return notice({message:"Choose an entry to see where it is stored."});
    const extract=el("button",{type:"button",class:"lex-dialog-action primary",
      onclick:async event=>{event.preventDefault();
        extract.textContent="Extracting…";
        try{const result=await api("/api/archive/extract",{method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({name:local.archive,index:row.index})});
          local.extracted=`${result.bytes} bytes written to ${result.path}`;}
        catch(error){local.extracted=`Could not extract: ${error.message}`}
        extract.textContent="Extract copy";render()}},"Extract copy");
    return detailPanel({title:row.basename,meta:row.name,body:[
      detailSection({title:"STORED",body:[
        detailField({label:"ARCHIVE",control:readonlyField(local.archive)}),
        detailField({label:"ENTRY NAME",help:infoHelp("The name the archive stores, with its original folder path. FFNx matches a replacement by this name under its direct folder."),control:readonlyField(row.name)}),
        detailField({label:"INDEX",help:infoHelp("Position of this entry in the archive's own list."),control:readonlyField(row.index)}),
        detailField({label:"UNPACKED SIZE",help:infoHelp("How large the file is once its compression is undone."),control:readonlyField(readable(row.bytes))}),
        detailField({label:"COMPRESSED",help:infoHelp("Whether the archive stores this entry compressed. Lexeditor writes replacements uncompressed."),control:readonlyField(row.compressed?"Yes":"No")}),
        detailField({label:"OFFSET",help:infoHelp("Where the stored bytes begin inside the .fs file."),control:readonlyField(`0x${Number(row.offset).toString(16).toUpperCase()}`)})]}),
      detailSection({title:"EXTRACT",help:infoHelp("Browsing reads the archive's own list. This copies one entry into the project so it can be looked at or edited, and it keeps one previous copy of what it overwrites. The installed game is never changed, and repacking a whole archive is still not built."),body:[
        detailField({label:"ACTION",control:extract}),
        local.extracted?detailField({label:"LAST EXTRACT",control:readonlyField(local.extracted)}):null]})]});
  }
  function view(){
    const rows=(local.data?.rows||[]).map(row=>({...row,id:row.index}));
    const list=columnList({rows,key:row=>row.id,columns:[
      {key:"index",label:"#",number:true,sortable:false,render:row=>row.index},
      {key:"basename",label:"FILE",grow:1,render:row=>row.basename},
      {key:"name",label:"STORED NAME",grow:2,render:row=>row.name},
      {key:"bytes",label:"SIZE",numeric:true,render:row=>readable(row.bytes)},
      {key:"compressed",label:"ZIP",render:row=>row.compressed?"●":"·"}],
      selected:local.selected,select:id=>{local.selected=id;render()},
      class:"ff8-record-list ff8-archive-list","aria-label":`${local.archive} entries`});
    const picker=el("select",{onchange:event=>{local.archive=event.target.value;local.page=0;
      local.selected=null;void loadEntries().then(render)}},
      ...local.archives.map(row=>{const option=el("option",{value:row.name},
        row.available?`${row.name} · ${row.entries} entries`:`${row.name} · not installed`);
        option.disabled=!row.available;option.selected=row.name===local.archive;return option}));
    // An archive holds thousands of entries, so the server sends one page and
    // the pager asks for the next. The whole paged list-detail is built for a
    // page, not for a pane: nested in one it kept its own page-sized height and
    // clipped every row past the first screen. A table and its pager are two
    // rows of one pane instead, which is how the starting inventory is built.
    const total=Math.max(0,Number(local.data?.matched ?? local.data?.total ?? rows.length)||0);
    const pages=Math.max(1,Math.ceil(total/Math.max(1,local.pageSize)));
    local.page=Math.max(0,Math.min(local.page,pages-1));
    const pageBar=pager({inline:true,page:local.page,pages,pageSize:local.pageSize,total,
      noun:"entries",
      search:{key:"ff8-archive-search",value:local.query,delay:120,label:"Search entries",
        placeholder:"Search stored names…",change:value=>{local.query=value;local.page=0;
          void loadEntries().then(render)}},
      rowControl:{value:local.pageSize,change:value=>{const size=Number(value);
        if(Number.isFinite(size)&&size>0){local.pageSize=size;local.page=0;
          void loadEntries().then(render)}}},
      change:value=>{local.page=value;void loadEntries().then(render)}});
    const entries=detailPanel({heading:false,className:"ff8-archive-entries",body:[
      pagedPane(list,pageBar)]});
    const status=[
      detailField({label:"ARCHIVE",help:infoHelp("The game's own FS/FI/FL triplet. Main holds kernel, init, namedic and wm2field; field holds every field map."),control:picker}),
      detailField({label:"ENTRIES",control:readonlyField(local.data?`${formatNumber(local.data.matched)} shown of ${formatNumber(local.data.total)}`:"—")}),
      detailField({label:"SOURCE",help:infoHelp("The installed game. Browsing never changes it."),control:readonlyField(local.source||"—")})];
    const repack=el("button",{type:"button",class:"lex-dialog-action",
      onclick:async event=>{event.preventDefault();
        repack.textContent="Repacking…";
        try{const result=await api("/api/archive/repack",{method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({name:local.archive})});
          local.repacked=`${result.replaced} replaced entries written to ${result.folder}`;}
        catch(error){local.repacked=`Could not repack: ${error.message}`}
        repack.textContent="Repack to project";render()}},"Repack to project");
    const right=detailPanel({heading:false,className:"ff8-archive-panel",body:[
      detailSection({title:"ARCHIVE",body:status}),
      detailSection({title:"REPACK",help:infoHelp("Builds this archive in the project's own repacked folder from the files the project replaces. Entries are written uncompressed, the way Deling rebuilds an archive. The installed game is never changed, and the archive is read back before it is reported."),body:[
        detailField({label:"ACTION",control:repack}),
        local.repacked?detailField({label:"LAST REPACK",control:readonlyField(local.repacked)}):null]}),
      local.error?notice({message:local.error,tone:"warning"}):null,
      local.busy?notice({message:"Reading the archive list…"}):null]});
    const chosen=rows.find(entry=>entry.id===local.selected)||null;
    const entry=chosen?entryDetail(chosen)
      :detailPanel({heading:false,className:"ff8-archive-panel",
        body:[notice({message:"Choose an entry to see where it is stored."})]});
    return panelLayout([entries,entry,right],"ff8-archives",
      {layoutKey:"ff8-archives",defaultSizes:[1,1,1]});
  }
  function render(){
    if(!local.loaded&&!local.busy){local.loaded=true;void loadArchives().then(()=>loadEntries()).then(render)}
    // FF8's shell calls a view for its side effect, so this one mounts itself
    // the way showPaged does for the record pages.
    const node=view(),host=document.querySelector("#main");
    if(host)host.replaceChildren(node);
    return node;
  }
  return {render};
}
