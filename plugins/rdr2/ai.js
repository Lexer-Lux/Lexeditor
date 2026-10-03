// ----- AI architecture -----
const AI_PANEL_HELP="Perception profiles control sight, hearing, smell and movement thresholds. Combat profiles group gangs, law, animals and companions. Global settings affect accuracy, damage, distraction and noise. Numeric limits are not yet established. Unsupported values are read-only.";
const AI_PROGRAM_HELP="Programs and styles control combat decisions. These graphs are read-only here.";
function aiFieldType(row){
  if(row.readonly||typeof row.value!=="string")return "readonly";
  if(/^(true|false)$/i.test(row.value))return "boolean";
  if(/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(row.value))return Number.isFinite(Number(row.value))?"number":"readonly";
  if(/^[+-]?(?:nan|inf|infinity)$/i.test(row.value))return "readonly";
  return "choice";
}
function aiChoices(rows,row){return [...new Set(rows.filter(r=>r.field===row.field&&!r.readonly&&typeof r.value==="string").map(r=>r.value))];}
function aiDraftError(row,value,rows){
  const type=aiFieldType(row);
  if(type==="readonly")return "This AI field is read-only.";
  if(typeof value!=="string")return "AI values must be text.";
  if(type==="number")return /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value)&&Number.isFinite(Number(value))?"":"Enter a finite number.";
  if(type==="boolean")return /^(true|false)$/i.test(value)?"":"Choose true or false.";
  return aiChoices(rows,row).includes(value)?"":"Choose a value present in the source data.";
}
function aiSaveBody(file){
  const rows=state.aiData?.[file]?.fields||[],edits=Object.values(state.aiEdits[file]||{}),seen=new Set();
  for(const edit of edits){
    if(!edit||Object.keys(edit).sort().join(",")!=="kind,path,value"||!Array.isArray(edit.path)||!edit.path.length||edit.path.some(i=>!Number.isSafeInteger(i)||i<0))throw new Error("Invalid AI target.");
    const key=edit.path.join("."),matches=rows.filter(r=>r.path.join(".")===key),row=matches[0];
    if(matches.length!==1||seen.has(key)||row.kind!==edit.kind)throw new Error("Unknown or duplicate AI target.");
    seen.add(key);const error=aiDraftError(row,edit.value,rows);if(error)throw new Error(error);
  }
  return {edits};
}
async function preflightAISave(){
  const bodies=Object.entries(state.aiEdits).filter(([,map])=>Object.keys(map).length).map(([file])=>[file,aiSaveBody(file)]);
  for(const [file,body] of bodies)await api("/api/ai/"+file+"/validate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
}
function aiValueControl(file,row,rows,reference){
  const key=row.path.join("."),edits=state.aiEdits[file],cur=edits[key]?.value??row.value,type=aiFieldType(row),editable=!isRO()&&type!=="readonly";
  const changed=value=>{if(!editable)return;if(value===row.value||(type==="boolean"&&value.toLowerCase()===row.value.toLowerCase()))delete edits[key];else edits[key]={path:row.path,kind:row.kind,value};refreshGlobalSave();};
  let control;
  if(type==="readonly")return LexeditorUI.readonlyField(String(cur));
  if(type==="boolean")control=el("input",{type:"checkbox",checked:cur.toLowerCase()==="true",disabled:!editable,"aria-label":row.field,onchange:e=>changed(e.target.checked?"true":"false")});
  else if(type==="number"){
    control=el("input",{type:"number",step:"any",required:true,disabled:!editable,value:cur,"aria-label":row.field,"data-lex-validate-number":"true",oninput:e=>{changed(e.target.value);e.target.setCustomValidity(aiDraftError(row,e.target.value,rows));e.target.classList.toggle("edited",key in edits);}});
    control.setCustomValidity(aiDraftError(row,cur,rows));
  }else control=el("select",{disabled:!editable,"aria-label":row.field,onchange:e=>changed(e.target.value)},...aiChoices(rows,row).map(value=>el("option",{value,selected:value===cur},value)));
  control.classList.toggle("edited",key in edits);
  const validReference=reference!==undefined&&!aiDraftError(row,reference,rows);
  return refField(control,validReference?[["UCO","ucotag",reference]]:null,cur,(value)=>{if(!editable)return;if(type==="boolean"){control.checked=value.toLowerCase()==="true";control.dispatchEvent(new Event("change",{bubbles:true}));}else{control.value=value;control.dispatchEvent(new Event(type==="number"?"input":"change",{bubbles:true}));}},String);
}
async function renderAI() {
  const current=renderScope("renderAI");
  if (!state.datamap) state.datamap=await api("/api/datamap");
  if(!current())return;
  const f=state.filters; if(!f.aiLayer)f.aiLayer="profiles";
  const layers={
    global:{label:"Global",files:["ai/noisetuning.meta","ai/pedaccuracy.meta","ai/peddamage.meta","ai/peddistraction.meta"]},
    profiles:{label:"Peds / profiles",files:["ai/combatbehaviour.meta","ai/pedperception.meta"]},
    programs:{label:"Programs & styles",terms:["combatstyles.meta","combatdirector.meta","melee_reasoner.meta"]},
  };
  const tb=$("#toolbar");tb.innerHTML="";
  tb.append(LexeditorUI.subtabBar({active:f.aiLayer,label:"AI layer",tabs:Object.entries(layers).map(([id,info])=>({id,label:info.label})),change:key=>{f.aiLayer=key;f.aiFile="";renderAI()}}));
  const layer=layers[f.aiLayer];
  if(layer.files){
    if(!f.aiFile||!layer.files.includes(f.aiFile))f.aiFile=layer.files[0];
    tb.append(el("select",{onchange:ev=>{f.aiFile=ev.target.value;renderAI();}},...layer.files.map(file=>{const o=el("option",{value:file},file);if(file===f.aiFile)o.selected=true;return o;})),
      el("input",{type:"text",placeholder:"Filter context or field…",value:f.aiQ||"",oninput:ev=>{f.aiQ=ev.target.value;filterRerender(ev,renderAI);}}),savebar(saveAI));
  }
  const m=$("#main");m.innerHTML="";
  if(layer.files){
    if(!state.aiData)state.aiData={};
    if(!state.aiData[f.aiFile])state.aiData[f.aiFile]=await api("/api/ai/"+f.aiFile);
    if(!current())return;
    if(!state.aiRefs)state.aiRefs={};
    if(!state.aiRefs[f.aiFile])state.aiRefs[f.aiFile]=await api("/api/ai-reference/"+f.aiFile);
    if(!current())return;
    const data=state.aiData[f.aiFile],refData=state.aiRefs[f.aiFile],q=(f.aiQ||"").toUpperCase();
    state.aiEdits[f.aiFile] ||= {};
    if(data.available===false){m.append(LexeditorUI.detailNote("AI source file is missing."));return;}
    const refByPath={};refData.fields.forEach(x=>refByPath[x.path.join(".")]=x.value);
    const rows=sortedRows("ai",data.fields.filter(x=>!q||x.context.toUpperCase().includes(q)||x.field.toUpperCase().includes(q)),{context:x=>x.context,field:x=>x.field,value:x=>x.value});
    // names: These scalar identities belong to fixed game profiles and cannot be renamed.
    m.append(LexeditorUI.pagedListDetail({rows,key:r=>r.path.join("."),selected:f.aiSelected?.[f.aiFile]||rows[0]?.path.join("."),renamable:false,pageSize:15,noun:"AI fields",slots:false,splitKey:"rdr2-ai",
      sync:view=>{f.aiSelected ||= {};f.aiSelected[f.aiFile]=view.selected},
      master:view=>columnList({class:"ai-field-table",rows:view.rows,key:r=>r.path.join("."),selected:view.selected,select:view.select,"aria-label":"AI fields",columns:[{key:"context",label:"Profile / context"},{key:"field",label:"Field"}]}),
      detail:row=>LexeditorUI.detailPanel({title:row.field,help:fieldHelp(AI_PANEL_HELP),body:[LexeditorUI.detailField({label:"Value",control:aiValueControl(f.aiFile,row,data.fields,refByPath[row.path.join(".")])})]})}));
    return;
  }
  const text=state.datamap.sections.map(s=>s.lines.join("\n")).join("\n");
  layer.terms.forEach(term=>{
    const lines=text.split("\n").filter(line=>line.toLowerCase().includes(term.toLowerCase())).slice(0,20);
    m.append(LexeditorUI.detailSection({title:term,body:LexeditorUI.stack({fill:false},...lines.map(line=>LexeditorUI.detailNote(line)))}));
  });
  m.append(LexeditorUI.detailPanel({title:"Programs & styles",help:fieldHelp(AI_PROGRAM_HELP),body:[]}));
}

async function saveAI(){
  if(isRO())return 0;
  const file=state.filters.aiFile,body=aiSaveBody(file);if(!body.edits.length)return 0;
  await api("/api/ai/"+file+"/validate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const r=await api("/api/ai/"+file+"/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  state.aiEdits[file]={};delete state.aiData[file];toast(`Saved ${r.saved} AI field(s) to ${file}`);renderAI();
}
