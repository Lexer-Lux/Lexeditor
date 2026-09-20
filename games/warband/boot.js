  const shell=LexeditorUI.mountShell({
    host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"warband",themeName:"warband",theme:{bg:"#e8d9b4",panel:"#f4e7c5","panel-2":"#dcc99a",border:"#8b6b39",text:"#2b2114",muted:"#6e5b3d",accent:"#7a2020","accent-text":"#fff5d8",highlight:"#a8661c",success:"#556b2f",font:'"Segoe UI",system-ui,sans-serif',"heading-font":"Georgia,serif"}},
    tabs:[["items","Items"],["misc","Misc."],["upgrades","Troop Trees"],["troops","Troops"],["tweaks","Tweaks"]].map(([id,label])=>({id,label})),
    activeTab:()=>state.tab,navigate,help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the Warband Data Map",info:()=>navigate("dashboard"),infoActive:()=>state.tab==="dashboard",infoTitle:"Open Warband information and log",projectSources:()=>[{key:"vanilla",label:"Vanilla",path:`${state.dashboard?.paths?.Game||"Installed Warband"}/Modules/Native`}],projectActiveSource:()=>state.activeSource,selectProjectSource:switchProjectSource,dirtyCount,readonly:()=>state.activeSource!=="mine",save:saveAll,
    history:{capture:historyCapture,restore:historyRestore,render,enabled:()=>!state.booting&&state.activeSource==="mine",limit:50}
  });
  moduleRecords=WarbandModuleRecords.create({state,api,main:()=>$("#main"),toolbar:()=>$("#toolbar"),refreshShell:()=>shell.refresh(),renderApp:render,setStatus,dataMapRows:()=>state.datamap?.rows||[],sourceDraft:filename=>state.catalogFile?.filename===filename&&state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text});

  async function boot(){
    try{
      [state.dashboard,state.settings,state.troops,state.items,state.upgrades,state.modules,state.datamap,state.font]=await Promise.all([api("/api/dashboard"),api("/api/settings"),api("/api/troops"),api("/api/items"),api("/api/upgrades"),api("/api/modules"),api("/api/datamap"),api("/api/warband-font")]);
      state.booting=false;applyInstalledWarbandFont();render();LexeditorUI.finishPluginLoading();
    }catch(error){state.booting=false;LexeditorUI.finishPluginLoading();$("#main").textContent=`Failed to load Warband plugin: ${error.message}`;setStatus("Load failed");}
  }
  window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&dirtyCount())event.preventDefault();});
  boot();
  
