"use strict";
state.moduleDataValidation=null;
state.moduleDataValidating=false;

async function validateAllModuleData(){
  if(state.moduleDataValidating)return;
  if(moduleDataDirty()){
    showAlert?.("Save or discard the current ModuleData edits before validating the project so the report reflects files on disk.","Unsaved ModuleData edits");
    return;
  }
  state.moduleDataValidating=true;
  state.moduleDataValidation={rows:[],scanned:0,total:0,issues:0,errors:0,schemas:0};
  render();
  try{
    const files=await ensureModuleDataFiles();
    state.moduleDataValidation.total=files.length;
    for(const path of files){
      let row;
      try{
        const value=await api(`/api/module-data?path=${encodeURIComponent(path)}`);
        const records=(value.records||[]).filter(record=>record.schemaIssueCount);
        row={
          path,
          ok:true,
          rootTag:value.rootTag||"",
          records:value.recordCount||0,
          schema:value.schema?.id||"",
          schemaPath:value.schema?.path||"",
          issues:value.schemaIssueCount||0,
          issueRecords:records.map(record=>({path:record.path,id:record.id||"",name:record.name||"",issues:record.schemaIssueCount||0})),
          error:""
        };
        if(row.schema)state.moduleDataValidation.schemas++;
        state.moduleDataValidation.issues+=row.issues;
      }catch(error){
        row={path,ok:false,rootTag:"",records:0,schema:"",schemaPath:"",issues:0,issueRecords:[],error:String(error.message||error)};
        state.moduleDataValidation.errors++;
      }
      state.moduleDataValidation.rows.push(row);
      state.moduleDataValidation.scanned++;
      render();
    }
  }finally{
    state.moduleDataValidating=false;
    render();
  }
}

function moduleDataValidationBlock(){
  const report=state.moduleDataValidation;
  if(!report)return null;
  const clean=report.rows.filter(row=>row.ok&&!row.issues).length;
  const schemaMisses=report.rows.filter(row=>row.ok&&!row.schema).length;
  const heading=state.moduleDataValidating?
    `Validating ModuleData… ${report.scanned}/${report.total||"?"}`:
    `ModuleData validation · ${report.scanned} file(s)`;
  return el("div",{class:"bl-list-block"},
    el("h3",{},heading),
    el("div",{},`${report.issues} schema issue(s) · ${report.errors} parse/read error(s) · ${clean} clean · ${report.schemas} XSD match(es) · ${schemaMisses} without XSD`),
    report.rows.length?el("div",{class:"bl-list"},...report.rows.map(row=>el("button",{
      type:"button",class:"bl-item",onclick:()=>loadModuleData(row.path)
    },
      `${row.ok?(row.issues?"⚠":"✓"):"✗"} ${row.path}`,
      el("small",{},row.ok?
        `${row.records} record(s) · ${row.schema?`XSD ${row.schema}`:"no XSD"}${row.issues?` · ${row.issues} issue(s)`:""}`:
        row.error)
    ))):el("div",{class:"bl-note"},"No ModuleData files scanned yet."));
}

const renderModuleDataBeforeValidation=renderModuleData;
renderModuleData=function(){
  renderModuleDataBeforeValidation();
  const head=main.querySelector(".bl-master-head");
  const master=main.querySelector(".bl-master");
  if(!head||!master)return;
  head.append(el("button",{
    type:"button",
    disabled:state.moduleDataValidating,
    onclick:validateAllModuleData,
    title:"Parse every project ModuleData XML file and apply any uniquely matched installed Bannerlord XSD"
  },state.moduleDataValidating?"Validating…":"Validate all"));
  const block=moduleDataValidationBlock();
  if(block)head.insertAdjacentElement("afterend",block);
};
