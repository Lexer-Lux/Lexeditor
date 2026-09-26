"use strict";
  async function selectModule(name){state.selectedModule=name;state.manual=await api(`/api/manual?module=${encodeURIComponent(name)}`);renderManuals();}
  function renderManuals(){
    $("#toolbar").replaceChildren(el("span",{},`${state.modules.modules.length} installed modules`));
    const master=list({rows:state.modules.modules,key:name=>name,selected:state.selectedModule,select:selectModule,render:name=>el("div",{},el("b",{},name))});
    const detail=state.manual
      ?detailPanel({title:state.manual.module,meta:`${state.manual.pages.length} pages`,body:state.manual.pages.map(page=>
        LexeditorUI.detailSection({title:page.title,body:[LexeditorUI.detailText(page.body.trim())]}))})
      :detailPanel({title:"Mod manuals",body:[LexeditorUI.detailNote("Select an installed mod to read its manual.")]});
    $("#main").replaceChildren(masterDetail(master,detail,"",{splitKey:"warband-manuals",defaultSplit:38}));
  }

  function settingDetail(row){
    return detailPanel({title:el("h2",{class:"lex-detail-panel-title"},bitmapText(row.key,24)),meta:row.section,body:[LexeditorUI.detailSection({body:[
      detailField({label:"Value",property:"value",control:el("input",{value:effectiveSetting(row),oninput:event=>{if(event.target.value===row.value)delete state.settingEdits[row.line];else state.settingEdits[row.line]=event.target.value;shell.refresh();}})}),
      LexeditorUI.detailNote(row.description||"No description.")]})]});
  }
  async function saveSettings(){
    const edits=Object.entries(state.settingEdits).map(([line,value])=>({line:+line,value}));if(!edits.length)return;
    const result=await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.settings=await api("/api/settings");state.settingEdits={};await buildSavedModule();shell.history.clear();setStatus(`Saved ${result.saved} settings and build verified`);renderSettings();shell.refresh();
  }
  function discardSettings(){state.settingEdits={};setStatus("Restored the last saved settings");renderSettings();shell.refresh()}
  function renderSettings(){
    // No plugin Save button in the bar: the shell's own Save owns every
    // unsaved change in the editor, and a second one beside it asks the reader
    // which of the two they meant.
    renderTableView("settings",state.settings.rows,[{key:"key",label:"Key"},{key:"section",label:"Section"},{key:"value",label:"Value",render:row=>el("span",{title:effectiveSetting(row)},effectiveSetting(row))}],
      {key:row=>String(row.line),selected:()=>state.selectedSetting,setSelected:value=>{state.selectedSetting=value;},
       searchFields:["section","key","value","description"],changed:row=>state.settingEdits[row.line]!==undefined,detail:settingDetail});
  }
