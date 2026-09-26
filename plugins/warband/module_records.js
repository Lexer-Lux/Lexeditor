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
      // The shell's own Save carries the unsaved count and the History pair
      // undoes an edit, so this view keeps no second Save or Discard of its
      // own. A panel-local Discard beside the real Save asked the reader
      // which of the two they meant.
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
    // Music, factions, skills and sounds are page tabs of their own, so the
    // remaining Module System areas share the Misc. page behind a subtab bar.
    // A dropdown hid how many areas exist and made every switch two gestures.
    const PROMOTED={music:"music",factions:"factions",skills:"skills",sounds:"sounds"};
    const tabFor=dataset=>PROMOTED[dataset]||"misc";
    const promotedDataset=tab=>Object.keys(PROMOTED).find(dataset=>PROMOTED[dataset]===tab)||"";
    const miscRows=()=>availableRows().filter(row=>!PROMOTED[row.dataset]);
    // One set of column preferences per area, so a pin the reader adds is still
    // there after moving between records, pages and areas.
    const preferences=new Map();
    function preferencesFor(dataset,definitions){
      let prefs=preferences.get(dataset);
      if(!prefs){prefs=LexeditorUI.columnPreferences("warband-module-"+dataset,definitions,()=>renderApp());preferences.set(dataset,prefs);}
      return prefs;
    }
    function activate(dataset){
      active=dataset||active||availableRows().find(row=>row.coverage==="structured"&&row.openable)?.dataset||availableRows()[0]?.dataset||"";
      viewState(active);
    }
    function open(dataset){activate(dataset);state.tab=tabFor(dataset);renderApp();}
    // A finder elsewhere in the plugin opens the record it names, so a mesh
    // property can show the mesh's own row instead of only its name.
    function openRecord(dataset,recordIndex){
      if(!availableRows().some(row=>row.dataset===dataset))return false;
      open(dataset);
      viewState(dataset).selected=String(recordIndex);
      renderApp();
      return true;
    }
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
    function detail(dataset,data,row,prefs){
      if(!row)return LexeditorUI.detailPanel({className:"warband-module-detail",title:"Select a "+data.schema.label.toLowerCase()+" record"});
      if(row.problem)return LexeditorUI.detailPanel({className:"warband-module-detail",title:row.name||row.id,identity:row.id,body:[LexeditorUI.el("section",{class:"card error"},row.problem)]});
      const readOnly=state.activeSource!=="mine";
      const choices=data.choices||{};
      const fields=data.schema.fields.filter(spec=>row.presentFields?.includes(spec.key)).map(spec=>{
        const description=row.fieldProblems?.[spec.key]?(spec.help||"")+" This field is not a supported literal in this record: "+row.fieldProblems[spec.key]+". Use source editing for this field.":spec.help||"";
        const choice=row.fieldProblems?.[spec.key]?null:choices[spec.key];
        if(choice?.kind==="bits"){
          // A flag field lists the names the project's own header defines, so
          // the reader picks the flags instead of typing an expression.
          return WarbandFieldControls.bitFields({label:spec.label,help:description,flags:choice.flags,pin:prefs?.pinButton(spec.key,spec.label),
            expression:effective(dataset,row,spec.key),readOnly,
            apply:value=>{setField(dataset,row,spec.key,value);renderApp();}});
        }
        if(choice?.kind==="mesh"){
          // A mesh property names a mesh this project declares, so it is chosen
          // from those names and can open the mesh's own record.
          return WarbandFieldControls.meshRows({label:spec.label,property:spec.key,add:false,pin:prefs?.pinButton(spec.key,spec.label),
            entries:[{name:String(effective(dataset,row,spec.key)??""),flag:"0"}],choices:choice.meshes,readOnly,
            apply:next=>{setField(dataset,row,spec.key,next.length?next[0].name:"none");renderApp();},
            open:entry=>{const match=choice.meshes.find(value=>value.name===entry.name);
              if(match&&match.recordIndex!==undefined&&match.recordIndex!==null)openRecord("meshes",match.recordIndex);}})[0];
        }
        return LexeditorUI.detailField({label:spec.label,property:spec.key,
          pin:prefs?.pinButton(spec.key,spec.label),
          dataType:({identity:"ID",string:"STRING",text:"STRING",expr:"EXPR",integer:"INT",number:"FLOAT",vec2:"VECTOR2",vec3:"VECTOR3",vec4:"VECTOR4"})[spec.kind]||"VALUE",
          description,control:fieldControl(dataset,row,spec,readOnly)});
      });
      // The heading is drawn in the installed game's own font, the same face
      // the shell and the shell's tabs use.
      return LexeditorUI.detailPanel({className:"warband-module-detail",title:bitmapText(row.name||row.id,24),
        // The heading shows the record's name; the ID repeats beside it only
        // when it is a different string. Coverage and the source caveat are
        // panel help, not a second subtitle and a paragraph on the page.
        identity:row.id===row.name?"":row.id,
        help:data.schema.notes+" "+(data.schema.status==="integrated"
          ?"Every documented field is editable here."
          :"Fields this editor does not interpret stay in the source; open the Data Map row's source editor for those."),
        body:[LexeditorUI.detailGroup({title:data.schema.label,body:fields})]});
    }
    function render(tab){
      const rows=availableRows();
      const promoted=promotedDataset(tab);
      if(promoted)active=promoted;
      else if(!active||!rows.some(row=>row.dataset===active)||PROMOTED[active])active=miscRows()[0]?.dataset||"";
      viewState(active);
      toolbar().replaceChildren();
      // The bar belongs to the page, above the panel it switches, and a page
      // that shows one area has no bar at all; the shared control handles that.
      const bar=promoted?null:LexeditorUI.subtabBar({label:"Module System area",
        tabs:miscRows().map(row=>({id:row.dataset,label:row.recordLabel||row.dataset})),active,
        change:value=>{active=value;viewState(active);renderApp();}});
      const host=node=>promoted||!bar?node:LexeditorUI.stack(bar,node);
      const entry=cache.get(active);
      if(!entry){main().replaceChildren(host(LexeditorUI.notice({className:"warband-module-state",message:"Loading structured Module System records…"})));load(active);return;}
      if(entry.loading&&!entry.data){main().replaceChildren(host(LexeditorUI.notice({className:"warband-module-state",message:"Loading structured Module System records…"})));return;}
      if(entry.error){main().replaceChildren(host(LexeditorUI.notice({className:"warband-module-state",title:labelFor(active)+" could not be loaded",message:entry.error,action:LexeditorUI.el("button",{type:"button",onclick:()=>load(active,true)},"Retry")})));return;}
      const data=entry.data;
      if(!data?.available){main().replaceChildren(host(LexeditorUI.notice({className:"warband-module-state",title:labelFor(active)+" source is unavailable",message:"The selected project does not contain this Module System source file."})));return;}
      const local=viewState(active),query=local.query.trim().toLocaleLowerCase();
      const filtered=(data.rows||[]).filter(row=>!query||[row.id,row.name,...Object.values(row.fields||{}).map(value=>Array.isArray(value)?value.join(" "):value)].some(value=>String(value??"").toLocaleLowerCase().includes(query)));
      if(!filtered.length&&!query){main().replaceChildren(host(LexeditorUI.notice({className:"warband-module-state",title:"No "+data.schema.label.toLowerCase()+" records",message:data.filename+" contains an empty "+data.schema.label.toLowerCase()+" list."})));return;}
      // Every field is a column definition, so the pin beside a property in the
      // detail pane can add that property to the table. The fields the area
      // already shows start pinned; the rest wait in the panel.
      const definitions=data.schema.fields.map(spec=>{
        const key=spec.key,column={key,label:spec.label,sortable:false,pinned:data.schema.columns.includes(key)?true:false,
          render:row=>{const value=effective(active,row,key),text=Array.isArray(value)?value.join(", "):String(value??"");return LexeditorUI.el("span",{class:"warband-cell-text",title:text},text);},
          sortValue:row=>effective(active,row,key)};
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
      const prefs=preferencesFor(active,definitions);
      const selectedRow=filtered.find(row=>String(row.recordIndex)===local.selected)||filtered[0];if(selectedRow)local.selected=String(selectedRow.recordIndex);
      main().replaceChildren(host(LexeditorUI.pagedListDetail({rows:filtered,key:row=>String(row.recordIndex),selected:local.selected,
        noun:data.schema.label.toLowerCase(),splitKey:"warband-module-"+active,className:"warband-paged-table warband-module-data",slots:false,
        fit:{minRowHeight:36},page:local.page,pageSize:local.pageSize,defaultSplit:45,
        search:{key:"warband-module-"+active,value:local.query,placeholder:"Search "+data.schema.label.toLowerCase()+"…",change:value=>{local.query=value;local.page=0;renderApp();}},
        master:({rows:pageRows,selected,select})=>LexeditorUI.columnList({rows:pageRows,key:row=>String(row.recordIndex),columns:definitions,columnPreferences:prefs,selected,selectedClass:"selected",select,class:"warband-record-list","aria-label":data.schema.label+" records"}),
        detail:row=>detail(active,data,row,prefs),
        sync:next=>{local.page=next.page;local.pageSize=next.pageSize;local.selected=next.selected||"";},
        change:next=>{local.page=next.page;local.pageSize=next.pageSize;local.selected=next.selected||"";renderApp();}})));
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
    return {render,open,openRecord,activate,dirtyCount,snapshot,restore,saveAll,fileHasEdits,load,active:()=>active,datasetDirtyCount,tabFor};
  }
  window.WarbandModuleRecords={create};
})();
