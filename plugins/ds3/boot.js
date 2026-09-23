  const shell=LexeditorUI.mountShell({
    host:"#lexeditor-shell",brand:"LEXEDITOR",
    plugin:{id:"ds3",name:"Dark Souls III",themeName:"ds3",theme:{
      bg:"#11110f",panel:"#191915","panel-2":"#22211c",border:"#514a3c",text:"#e8e1d4",
      muted:"#aaa08e",accent:"#a4824c","accent-text":"#17130d",highlight:"#c2a66f",success:"#779363"
    }},
    tabs:TABLES.map(table=>({id:table.id,label:table.label})),activeTab:()=>state.tab,navigate,
    help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the Dark Souls III Data Map",
    info:()=>navigate("info"),infoActive:()=>state.tab==="info",infoTitle:"Open Dark Souls III information",
    dirtyCount,readonly:()=>false,save:saveProject,discard:discardChanges
  });

  async function boot(){
    try{
      const [snapshot,dataMap,info]=await Promise.all([api("/api/state"),api("/api/datamap"),api("/api/info")]);
      state.dirty=snapshot.dirtyCount||0;state.source=snapshot.source||"";state.project=snapshot.project||"";
      state.output=snapshot.output||"";state.datamap=dataMap;state.info=info;
      await loadTable(state.tab);state.booting=false;render();document.body.dataset.ds3Ready="true";LexeditorUI.finishPluginLoading();
    }catch(error){
      state.error=error.message||String(error);state.booting=false;render();
      document.body.dataset.ds3Ready="error";LexeditorUI.finishPluginLoading();
    }
  }
  window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&dirtyCount())event.preventDefault()});
  boot();
