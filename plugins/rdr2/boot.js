// ---------- tabs & boot ----------
// Every page is loaded by now, so this is where the tabs are named.
const TABS = { items: renderItems, crafting: renderCrafting, effects: renderEffects, loot: renderLoot, shops:renderShops, settings:renderSettings,
  challenges: renderChallenges, weapons: renderWeapons, ai: renderAI, mobs: renderMobs,
  crime: renderCrime, datamap: renderDataMap, info: renderInfo };

const rdr2Shell=LexeditorUI.mountShell({
  host:"#lexeditor-shell",
  plugin:{
    id:"rdr2",themeName:"rdr2",
    theme:{bg:"#100f0d",panel:"#191714","panel-2":"#24211c",border:"#4a4439",text:"#e8e1d4",muted:"#918a7e",accent:"#a92b20","accent-text":"#ffffff",highlight:"#d7b65d",success:"#667b50",font:'"Lex RDR Lino", "Arial Narrow", "Segoe UI", sans-serif',"heading-font":'"Lex Redemption", Georgia, serif'}
  },
  tabs:[
    ["ai","AI"],["challenges","Challenges"],["crime","Crime & Law"],["crafting","Crafting"],
    ["effects","Effects"],["items","Items"],["loot","Loot Tables"],
    ["mobs","Mobs"],["shops","Shops"],["settings","Tweaks"],["weapons","Weapons"]
  ].map(([id,label])=>({id,label,help:TAB_CONTEXT[id]?.help})),
  activeTab:()=>state.tab,
  navigate,
  help:()=>navigate("datamap"),
  helpActive:()=>state.tab==="datamap",
  helpTitle:"Open the RDR2 Data Map",
  info:()=>navigate("info"),
  infoActive:()=>state.tab==="info",
  infoTitle:"Open RDR2 setup information",
  projectSources:()=>Object.entries(state.config?.datasets||{}).filter(([key])=>key!=="mine").map(([key,info])=>({key,label:info.label,path:info.dir||"Read-only reference"})),
  projectActiveSource:()=>state.ds,
  selectProjectSource:key=>switchDataset(key),
  dirtyCount,
  readonly:()=>!!state.config&&isRO(),
  save:saveAllChanges,
  history:{
    capture:rdr2HistoryCapture,
    restore:rdr2HistoryRestore,
    render,
    enabled:()=>!state.booting&&!!state.config&&!isRO(),
    limit:50
  }
});
const initialTab=location.hash.replace(/^#/,"");
if(TABS[initialTab])state.tab=initialTab;
history.replaceState(navigationState(),"",location.hash||"#items");
window.addEventListener("popstate",ev=>{if(!ev.state?.lexeditor)return;state.tab=ev.state.tab;state.filters=ev.state.filters;state.lootFile=ev.state.lootFile;
  render().finally(()=>requestAnimationFrame(()=>window.scrollTo(ev.state.scrollX||0,ev.state.scrollY||0)));});
window.addEventListener("beforeunload", ev => { if (!window.__lexeditorNavigating && dirtyCount()) ev.preventDefault(); });
boot().catch(ex => { LexeditorUI.finishPluginLoading(); $("#main").innerHTML = ""; $("#main").append(LexeditorUI.stack({fill:false,className:"lex-notice"}, "Failed to load: " + ex.message)); });
