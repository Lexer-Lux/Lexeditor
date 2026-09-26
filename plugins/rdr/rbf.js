/* Protected RDR1 RBF0 scalar editor. Only fixed-width bool/uint32/float
   leaves returned by rbf.py are writable; every other RBF byte remains opaque. */
(function (global) {
  "use strict";
  global.RDRRbfUI = function RDRRbfUI(deps) {
    const {state,api,el,columnList,pagedListDetail,cell,shown,detailField,
      sourceControl,modOnlySpec,setStatus,shell} = deps;
    const UI=global.LexeditorUI;
    let discardButton=null;
    const value=row=>Object.prototype.hasOwnProperty.call(state.rbfEdits,row.id)
      ? state.rbfEdits[row.id].value : row.value;
    const equal=(row,next)=>row.kind==="bool" ? Boolean(next)===Boolean(row.value)
      : Number(next)===Number(row.value);
    const refreshDiscard=()=>{if(discardButton?.isConnected)discardButton.disabled=!Object.keys(state.rbfEdits).length;};
    function edit(row,next){
      if(equal(row,next))delete state.rbfEdits[row.id];
      else state.rbfEdits[row.id]={
        value:next,path:row.resourcePath,recordOffset:row.recordOffset,
        fieldPath:row.path,kind:row.kind,rawHex:row.rawHex,
      };
      refreshDiscard();shell().refresh();
    }
    function matchingRows(){
      const needle=state.rbfQuery.trim().toLowerCase();
      return (state.rbf?.rows||[]).filter(row=>!needle||[
        row.path,row.name,row.kind,row.resourcePath,String(value(row)),row.role,
      ].some(candidate=>String(candidate||"").toLowerCase().includes(needle)));
    }
    const COLUMNS=[
      {key:"field",label:"Field",width:"minmax(0,1.35fr)",render:row=>cell(row.path)},
      {key:"type",label:"Type",width:"minmax(0,.55fr)",render:row=>cell(row.kind)},
      {key:"value",label:"Value",width:"minmax(0,.65fr)",render:row=>cell(String(value(row)))},
      {key:"resource",label:"File",width:"minmax(0,1.1fr)",render:row=>cell(row.resourcePath)},
    ];
    function control(row){
      const vanilla=state.vanilla.rbf?.rows?.find(item=>item.id===row.id)?.value;
      let input;
      if(row.kind==="bool")input=el("input",{type:"checkbox",checked:Boolean(value(row)),disabled:state.activeSource!=="mine",
        onchange:event=>edit(row,event.target.checked),"aria-label":row.path});
      else input=el("input",{type:"number",value:String(value(row)),step:row.kind==="uint32"?"1":"any",
        min:row.kind==="uint32"?"0":undefined,max:row.kind==="uint32"?"4294967295":undefined,
        disabled:state.activeSource!=="mine",oninput:event=>edit(row,event.target.value),"aria-label":row.path});
      return sourceControl(input,()=>value(row),vanilla,next=>edit(row,next));
    }
    function detail(){
      const row=(state.rbf?.rows||[]).find(item=>item.id===state.rbfSelected);
      if(!row)return UI.detailPanel({className:"record-detail rbf-detail",title:"Select an RBF0 scalar",
        body:[UI.detailNote("Only fixed-width boolean, uint32 and float leaves are exposed. Strings, vectors, byte blocks and unknown records stay byte-for-byte opaque.")]});
      return UI.detailPanel({className:"record-detail rbf-detail",title:row.name,meta:row.path,body:[
        detailField("File",shown(row.resourcePath),"","The prepared RBF0 tuning resource which owns this scalar."),
        detailField("Field",shown(row.path),"","Descriptor path reconstructed from the RBF0 structure and attribute count."),
        detailField("Role",shown(row.role)),
        detailField("Type",shown(row.kind),"","Lexeditor exposes only fixed-width RBF0 primitives whose byte span is public and bounded."),
        detailField("Source",shown(row.sourcePath),"","Read-only prepared bytes from the installed tuning archive."),
        detailField("Override",shown(row.projectPath),"","Save writes a separate archive-relative project override; the prepared source stays unchanged."),
        detailField("Value",control(row),
          "Format-level scalar only; no gameplay range or semantic meaning is inferred from the field name.",
          "The write is in-place and width-preserving. Stale offsets/raw bytes are rejected and every byte outside the selected scalar span must remain identical."),
      ]});
    }
    function discard(){state.rbfEdits={};shell().history.clear();setStatus("Discarded unsaved RBF0 scalar edits");render();shell().refresh();}
    function render(){
      discardButton=el("button",{type:"button",disabled:!Object.keys(state.rbfEdits).length,onclick:discard},"Discard RBF edits");
      const scalarCount=state.rbf?.counts?.scalars||0,resourceCount=state.rbf?.counts?.resources||0;
      const count=`${scalarCount} safe scalar${scalarCount===1?"":"s"} · ${resourceCount} RBF0 resource${resourceCount===1?"":"s"}`;
      document.querySelector("#toolbar").replaceChildren(discardButton,el("span",{class:"count"},count));
      const rows=matchingRows();
      document.querySelector("#main").replaceChildren(pagedListDetail({addDisabledReason:"These are the values this file already holds; the game reads them by name, so a new one would be ignored.",
        modOnly:modOnlySpec(state.rbfEdits,()=>{state.rbfPage=0;}),rows,key:row=>row.id,slots:false,
        page:state.rbfPage,pageSize:state.rbfPageSize,selected:state.rbfSelected,noun:"scalars",
        splitKey:"rdr-rbf",className:"rdr-split",defaultSplit:50,fit:{minRowHeight:32},
        search:{key:"rdr-rbf",value:state.rbfQuery,placeholder:"Search RBF0 fields or resources…",
          change:next=>{state.rbfQuery=next;state.rbfPage=0;render();}},filters:[],
        master:({rows,selected,select})=>columnList({rows,key:row=>row.id,columns:COLUMNS,selected,
          selectedClass:"sel",select,class:"rdr-record-list","aria-label":"RDR RBF0 safe scalars"}),
        detail,
        sync:next=>{state.rbfPage=next.page;state.rbfPageSize=next.pageSize;state.rbfSelected=next.selected||"";},
        change:next=>{state.rbfPage=next.page;state.rbfPageSize=next.pageSize;state.rbfSelected=next.selected||"";render();},
      }));
      shell().refresh();
    }
    function validate(){
      for(const edit of Object.values(state.rbfEdits)){
        if(edit.kind==="bool"&&typeof edit.value!=="boolean")throw new Error(`${edit.fieldPath} needs true or false`);
        if(edit.kind==="uint32"){
          const number=Number(edit.value);
          if(!Number.isInteger(number)||number<0||number>4294967295)throw new Error(`${edit.fieldPath} needs an integer from 0 to 4294967295`);
        }
        if(edit.kind==="float"&&!Number.isFinite(Number(edit.value)))throw new Error(`${edit.fieldPath} needs a finite number`);
      }
    }
    async function savePending(saved){
      const groups={};
      for(const [id,edit] of Object.entries(state.rbfEdits)){
        const group=groups[edit.path]||=( {path:edit.path,ids:[],edits:[]} );
        group.ids.push(id);group.edits.push({recordOffset:edit.recordOffset,path:edit.fieldPath,kind:edit.kind,rawHex:edit.rawHex,value:edit.value});
      }
      for(const group of Object.values(groups)){
        const result=await api("/api/rbf/save",{method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({path:group.path,edits:group.edits})});
        for(const id of group.ids)delete state.rbfEdits[id];
        saved.push(`${result.saved} RBF0 scalar${result.saved===1?"":"s"} in ${group.path}`);
      }
      refreshDiscard();
    }
    const clearEdits=()=>{state.rbfEdits={};refreshDiscard();};
    return {render,validate,savePending,clearEdits,dirtyCount:()=>Object.keys(state.rbfEdits).length};
  };
})(window);
