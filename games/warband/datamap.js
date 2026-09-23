"use strict";
  async function selectCatalog(row){
    if(moduleRecords?.fileHasEdits(row.filename)){showAlert({title:"Structured edits are open",items:[{item:row.filename,issue:"Discard or save the Misc. changes before opening this file as raw source."}],closeLabel:"Close"});return;}
    if(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text&&!confirm("Discard the unsaved source-file edit?"))return;
    state.selectedFile=row.filename;state.catalogFile=await api(`/api/catalog/file?name=${encodeURIComponent(row.filename)}`);state.catalogDraft=state.catalogFile.text||"";shell.history.clear();renderDataMap();
  }
  function closeCatalog(){
    if(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text&&!confirm("Discard the unsaved source-file edit?"))return;
    state.selectedFile="";state.catalogFile=null;state.catalogDraft="";shell.history.clear();renderDataMap();
  }
  function sourceDialog(){
    if(!state.catalogFile)return null;
    const backdrop=el("div",{class:"lex-dialog-backdrop"});
    const panel=el("div",{class:"lex-dialog lex-source-dialog"},
      el("div",{class:"lex-source-dialog-head"},el("h2",{},state.catalogFile.filename),el("button",{onclick:closeCatalog,"aria-label":"Close source editor"},"×")),
      el("p",{},state.catalogFile.editable?`${state.catalogFile.path} [${state.catalogFile.encoding}]`:state.catalogFile.reason),
      state.catalogFile.editable?el("textarea",{value:state.catalogDraft,oninput:event=>{state.catalogDraft=event.target.value;shell.refresh();}},state.catalogDraft):"");
    backdrop.append(panel);backdrop.addEventListener("click",event=>{if(event.target===backdrop)closeCatalog();});return backdrop;
  }
  const coverageNames={structured:"Structured editable",view:"Read-only view",source:"Source only",unavailable:"Unavailable"};
  function renderDataMap(){
    window.LexeditorUI?.dismissDialogs?.();
    const view=LexeditorUI.dataMap({rows:state.datamap.rows,query:state.filters.datamap,
      status:state.filters.mapStatus,page:state.pages.datamap,sort:state.sorts.datamap,
      tableClass:"warband-record-list",open:row=>row.dataset?moduleRecords.open(row.dataset):navigate(row.view),openSource:selectCatalog,
      changeQuery:value=>{state.filters.datamap=value;state.pages.datamap=0;renderDataMap()},
      changeStatus:value=>{state.filters.mapStatus=value;state.pages.datamap=0;renderDataMap()},
      changePage:value=>{state.pages.datamap=value;renderDataMap()},
      changeSort:key=>sort("datamap",key)});
    state.pages.datamap=view.page;$("#toolbar").replaceChildren(...view.controls);
    $("#main").replaceChildren(view.content);
    const dialog=sourceDialog();if(dialog)document.body.append(dialog);
  }
