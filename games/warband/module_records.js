(() => {
  "use strict";
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const copy=value=>JSON.parse(JSON.stringify(value));
  function create(options){
    const {state,api,main,toolbar,refreshShell,renderApp,setStatus,dataMapRows,sourceDraft}=options;
    const cache=new Map(),edits={},view={};let active="";
    const availableRows=()=> (dataMapRows()||[]).filter(row=>row.dataset);
    const rowFor=dataset=>availableRows().find(row=>row.dataset===dataset);
    const labelFor=dataset=>rowFor(dataset)?.recordLabel||dataset;
    const viewState=dataset=>view[dataset]||(view[dataset]={query:"",page:0,pageSize:20,selected:""});
    const editBucket=dataset=>edits[dataset]||(edits[dataset]={});
    const editKey=row=>String(row.recordIndex);
    const effective=(dataset,row,key)=>{
      const changed=editBucket(dataset)[editKey(row)]?.fields;
      return Object.prototype.hasOwnProperty.call(changed||{},key)?changed[key]:row.fields?.[key];
    };
    function setField(dataset,row,key,value){
      const bucket=editBucket(dataset),recordKey=editKey(row),base=row.fields?.[key];
      if(same(value,base)){
        if(bucket[recordKey]?.fields)delete bucket[recordKey].fields[key];
        if(bucket[recordKey]&&!Object.keys(bucket[recordKey].fields).length)delete bucket[recordKey];
      }else{
        const record=bucket[recordKey]||(bucket[recordKey]={recordIndex:row.recordIndex,originalId:row.id,fields:{}});
        record.fields[key]=copy(value);
      }
      refreshDirtyChrome();
    }
    const datasetDirtyCount=dataset=>Object.values(editBucket(dataset)).reduce((n,row)=>n+Object.keys(row.fields||{}).length,0);
    function refreshDirtyChrome(){
      const dirty=active?datasetDirtyCount(active):0;
      const discard=toolbar().querySelector("[data-warband-module-discard]");
      if(discard)discard.disabled=!dirty;
      const count=toolbar().querySelector("[data-warband-module-dirty]");
      if(count)count.textContent=dirty+" unsaved field"+(dirty===1?"":"s");
      refreshShell();
    }
    const dirtyCount=()=>Object.keys(edits).reduce((n,dataset)=>n+datasetDirtyCount(dataset),0);
    const snapshot=()=>({edits:copy(edits),active,view:copy(view)});
    function restore(value){
      for(const key of Object.keys(edits))delete edits[key];
      Object.assign(edits,copy(value?.edits||{}));active=value?.active||active;
      for(const key of Object.keys(view))delete view[key];
      Object.assign(view,copy(value?.view||{}));
    }
    async function load(dataset,force=false){
      const current=cache.get(dataset);
      if(!force&&(current?.loading||current?.data))return current?.data;
      cache.set(dataset,{loading:true,data:current?.data||null,error:""});renderApp();
      try{
        const data=await api("/api/module-records?dataset="+encodeURIComponent(dataset));
        cache.set(dataset,{loading:false,data,error:""});
        const local=viewState(dataset);
        if(!local.selected&&data.rows?.length)local.selected=String(data.rows[0].recordIndex);
        return data;
      }catch(error){
        cache.set(dataset,{loading:false,data:null,error:error.message||String(error)});return null;
      }finally{renderApp();}
    }
    function activate(dataset){
      active=dataset||active||availableRows().find(row=>row.coverage==="structured"&&row.openable)?.dataset||availableRows()[0]?.dataset||"";
      viewState(active);
    }
    function open(dataset){activate(dataset);state.tab="misc";renderApp();}
    function fieldControl(dataset,row,spec,readOnly){
      const value=effective(dataset,row,spec.key),problem=row.fieldProblems?.[spec.key];
      const disabled=readOnly||spec.kind==="identity"||!!problem;
      if(/^vec[234]$/.test(spec.kind)){
        const count=Number(spec.kind.slice(3));
        if(!Array.isArray(value)||value.length!==count)return LexeditorUI.readonlyField(String(value??""),{format:false});
        return LexeditorUI.multiNumberRow(value.map((component,index)=>({
          label:spec.components?.[index]||String(index+1),
          control:LexeditorUI.el("input",{type:"number",step:"any",value:component,disabled,
            oninput:event=>{if(event.target.value==="")return;const next=[...effective(dataset,row,spec.key)];next[index]=Number(event.target.value);setField(dataset,row,spec.key,next);}})
        })),{columns:Math.min(count,3)});
      }
      const attrs={value:value??"",disabled};
      if(spec.kind==="integer"||spec.kind==="number"){
        if(typeof value!=="number")return LexeditorUI.el("input",{value:String(value??""),disabled:true,title:problem||"This source value is not a numeric literal; edit it in source."});
        Object.assign(attrs,{type:"number",step:spec.kind==="integer"?1:"any"});
        if(spec.min!==undefined)attrs.min=spec.min;if(spec.max!==undefined)attrs.max=spec.max;
        attrs.oninput=event=>{if(event.target.value==="")return;setField(dataset,row,spec.key,spec.kind==="integer"?Number.parseInt(event.target.value,10):Number(event.target.value));};
        return LexeditorUI.el("input",attrs);
      }
      if(spec.kind==="expr"){
        const control=LexeditorUI.codeField({value:value??"",disabled,oninput:event=>setField(dataset,row,spec.key,event.target.value)});return control;
      }
      if(spec.kind==="text"){
        return LexeditorUI.textArea({value:value??"",rows:4,disabled,oninput:event=>setField(dataset,row,spec.key,event.target.value)});
      }
      attrs.oninput=event=>setField(dataset,row,spec.key,event.target.value);return LexeditorUI.el("input",attrs);
    }
    function detail(dataset,data,row){
      if(!row)return LexeditorUI.detailPanel({className:"warband-module-detail",title:"Select a "+data.schema.label.toLowerCase()+" record"});
      if(row.problem)return LexeditorUI.detailPanel({className:"warband-module-detail",title:row.name||row.id,identity:row.id,body:[LexeditorUI.el("section",{class:"card error"},row.problem)]});
      const readOnly=state.activeSource!=="mine";
      const fields=data.schema.fields.filter(spec=>row.presentFields?.includes(spec.key)).map(spec=>{
        const description=row.fieldProblems?.[spec.key]?(spec.help||"")+" This field is not a supported literal in this record: "+row.fieldProblems[spec.key]+". Use source editing for this field.":spec.help||"";
        return LexeditorUI.detailField({label:spec.label,property:spec.key,
          dataType:({identity:"ID",string:"STRING",text:"STRING",expr:"EXPR",integer:"INT",number:"FLOAT",vec2:"VECTOR2",vec3:"VECTOR3",vec4:"VECTOR4"})[spec.kind]||"VALUE",
          description,control:fieldControl(dataset,row,spec,readOnly)});
      });
      return LexeditorUI.detailPanel({className:"warband-module-detail",title:row.name||row.id,identity:row.id,
        meta:data.schema.status==="integrated"?"Structured":"Structured partial",
        body:[LexeditorUI.detailGroup({title:data.schema.label,body:fields}),LexeditorUI.detailNote(data.schema.notes)]});
    }
    function render(){
      const rows=availableRows();if(!active||!rows.some(row=>row.dataset===active))activate();
      const selector=LexeditorUI.el("select",{"aria-label":"Warband Module System dataset",onchange:event=>{active=event.target.value;viewState(active);renderApp();}},
        ...rows.map(row=>LexeditorUI.el("option",{value:row.dataset,selected:row.dataset===active},row.recordLabel||row.dataset)));
      const dirty=datasetDirtyCount(active);
      const discard=LexeditorUI.el("button",{type:"button",disabled:!dirty,"data-warband-module-discard":"1",onclick:()=>{edits[active]={};setStatus("Discarded unsaved "+labelFor(active)+" changes");refreshShell();renderApp();}},"Discard changes");
      toolbar().replaceChildren(selector,discard,LexeditorUI.el("span",{class:"count","data-warband-module-dirty":"1"},dirty+" unsaved field"+(dirty===1?"":"s")));
      const entry=cache.get(active);
      if(!entry){main().replaceChildren(LexeditorUI.notice({className:"warband-module-state",message:"Loading structured Module System records…"}));load(active);return;}
      if(entry.loading&&!entry.data){main().replaceChildren(LexeditorUI.notice({className:"warband-module-state",message:"Loading structured Module System records…"}));return;}
      if(entry.error){main().replaceChildren(LexeditorUI.notice({className:"warband-module-state",title:labelFor(active)+" could not be loaded",message:entry.error,action:LexeditorUI.el("button",{type:"button",onclick:()=>load(active,true)},"Retry")}));return;}
      const data=entry.data;
      if(!data?.available){main().replaceChildren(LexeditorUI.notice({className:"warband-module-state",title:labelFor(active)+" source is unavailable",message:"The selected project does not contain this Module System source file."}));return;}
      const local=viewState(active),query=local.query.trim().toLocaleLowerCase();
      const filtered=(data.rows||[]).filter(row=>!query||[row.id,row.name,...Object.values(row.fields||{}).map(value=>Array.isArray(value)?value.join(" "):value)].some(value=>String(value??"").toLocaleLowerCase().includes(query)));
      if(!filtered.length&&!query){main().replaceChildren(LexeditorUI.notice({className:"warband-module-state",title:"No "+data.schema.label.toLowerCase()+" records",message:data.filename+" contains an empty "+data.schema.label.toLowerCase()+" list."}));return;}
      const columns=data.schema.columns.map(key=>{
        const spec=data.schema.fields.find(field=>field.key===key)||{label:key};
        const column={key,label:spec.label,sortable:false,
          render:row=>{const value=effective(active,row,key),text=Array.isArray(value)?value.join(", "):String(value??"");return LexeditorUI.el("span",{class:"warband-cell-text",title:text},text);}};
        if(["string","text","integer","number"].includes(spec.kind)){
          column.editValue=row=>effective(active,row,key);
          column.edit=(row,value)=>{
            const parsed=spec.kind==="integer"?Number.parseInt(value,10):spec.kind==="number"?Number(value):value;
            if((spec.kind==="integer"||spec.kind==="number")&&!Number.isFinite(parsed))return;
            setField(active,row,key,parsed);renderApp();
          };
          if(spec.kind==="integer"||spec.kind==="number"){column.numeric=true;column.step=spec.kind==="integer"?1:"any";if(spec.min!==undefined)column.min=spec.min;if(spec.max!==undefined)column.max=spec.max;}
        }
        return column;
      });
      const selectedRow=filtered.find(row=>String(row.recordIndex)===local.selected)||filtered[0];if(selectedRow)local.selected=String(selectedRow.recordIndex);
      main().replaceChildren(LexeditorUI.pagedListDetail({rows:filtered,key:row=>String(row.recordIndex),selected:local.selected,
        noun:data.schema.label.toLowerCase(),splitKey:"warband-module-"+active,className:"warband-paged-table warband-module-data",slots:false,
        fit:{minRowHeight:36},page:local.page,pageSize:local.pageSize,defaultSplit:45,
        search:{key:"warband-module-"+active,value:local.query,placeholder:"Search "+data.schema.label.toLowerCase()+"…",change:value=>{local.query=value;local.page=0;renderApp();}},
        master:({rows:pageRows,selected,select})=>LexeditorUI.columnList({rows:pageRows,key:row=>String(row.recordIndex),columns,selected,selectedClass:"selected",select,class:"warband-record-list","aria-label":data.schema.label+" records"}),
        detail:row=>detail(active,data,row),
        sync:next=>{local.page=next.page;local.pageSize=next.pageSize;local.selected=next.selected||"";},
        change:next=>{local.page=next.page;local.pageSize=next.pageSize;local.selected=next.selected||"";renderApp();}}));
    }
    async function saveAll(){
      let saved=0;const savedFiles=[];
      for(const dataset of Object.keys(edits)){
        const datasetEdits=Object.values(editBucket(dataset)).filter(record=>Object.keys(record.fields||{}).length);
        if(!datasetEdits.length)continue;
        const data=cache.get(dataset)?.data;if(!data?.available)throw new Error(labelFor(dataset)+" source is not loaded");
        if(sourceDraft(data.filename))throw new Error(labelFor(dataset)+" has structured edits while "+data.filename+" also has an unsaved source edit. Save or discard one editing path before using the other.");
        const result=await api("/api/module-records/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({dataset,sha256:data.sha256,edits:datasetEdits})});
        saved+=Number(result.saved||0);savedFiles.push(data.filename);edits[dataset]={};await load(dataset,true);
      }
      return {saved,files:savedFiles};
    }
    function fileHasEdits(filename){const row=availableRows().find(value=>value.filename===filename&&value.dataset);return row?datasetDirtyCount(row.dataset)>0:false;}
    return {render,open,activate,dirtyCount,snapshot,restore,saveAll,fileHasEdits,load,active:()=>active,datasetDirtyCount};
  }
  window.WarbandModuleRecords={create};
})();
