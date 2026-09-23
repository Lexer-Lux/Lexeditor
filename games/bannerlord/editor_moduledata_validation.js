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

function moduleDataValidationSection(){
  const report=state.moduleDataValidation;
  if(!report)return null;
  const clean=report.rows.filter(row=>row.ok&&!row.issues).length;
  const schemaMisses=report.rows.filter(row=>row.ok&&!row.schema).length;
  const rows=report.rows.map((row,index)=>({
    index,row,path:row.path,status:row.ok?(row.issues?"Issues":"Clean"):"Error",
    records:Number(row.records||0),schema:row.schema||"none",issues:Number(row.issues||0),
    searchText:`${row.path} ${row.schema||""} ${row.error||""}`
  }));
  return BLUI.detailSection({
    title:state.moduleDataValidating?`PROJECT VALIDATION · ${report.scanned}/${report.total||"?"}`:`PROJECT VALIDATION · ${report.scanned} FILE(S)`,
    help:BLUI.infoHelp("Validate all reparses every project ModuleData XML file and applies a Bannerlord XSD only when the installed schema match is unique. It does not rewrite files."),
    body:[
      readField("Summary",`${report.issues} schema issue(s) · ${report.errors} parse/read error(s) · ${clean} clean · ${report.schemas} XSD match(es) · ${schemaMisses} without XSD`),
      rows.length?BLUI.columnList({
        rows,key:item=>item.index,selected:null,columns:[
          {key:"path",label:"File"},
          {key:"status",label:"Status"},
          {key:"records",label:"Records",numeric:true},
          {key:"schema",label:"XSD"},
          {key:"issues",label:"Issues",numeric:true},
          {key:"open",label:"",sortable:false,render:item=>uiButton("Open",()=>{state.moduleDataView="records";loadModuleData(item.row.path)})}
        ],
        "aria-label":"ModuleData validation results"
      }):readField("Files","No ModuleData files scanned yet")
    ]
  });
}
