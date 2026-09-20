// ----- AI architecture -----
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
  m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},el("b",{},"AI is layered, not one value set per enemy model. "),
    "Perception profiles own sight, hearing, smell, fields of view, movement thresholds, and time/weather modifiers; combat profiles define gangs/law/animals/companions; global files modify aim distraction, contextual accuracy, damage and noise. Programs/styles are decision graphs. See docs/STEALTH_SYSTEM_AUDIT.md before changing crouch/prone perception."));
  if(layer.files){
    if(!state.aiData)state.aiData={};
    if(!state.aiData[f.aiFile])state.aiData[f.aiFile]=await api("/api/ai/"+f.aiFile);
    if(!current())return;
    if(!state.aiRefs)state.aiRefs={};
    if(!state.aiRefs[f.aiFile])state.aiRefs[f.aiFile]=await api("/api/ai-reference/"+f.aiFile);
    if(!current())return;
    const data=state.aiData[f.aiFile],refData=state.aiRefs[f.aiFile],edits=state.aiEdits[f.aiFile]||(state.aiEdits[f.aiFile]={}),q=(f.aiQ||"").toUpperCase();
    const refByPath={};refData.fields.forEach(x=>refByPath[x.path.join(".")]=x.value);
    const rows=sortedRows("ai",data.fields.filter(x=>!q||x.context.toUpperCase().includes(q)||x.field.toUpperCase().includes(q)),{context:x=>x.context,field:x=>x.field,value:x=>x.value}).slice(0,1000);
    tb.insertBefore(el("span",{class:"count"},`${rows.length}${data.fields.length>1000?` shown of ${data.fields.length}`:" fields"}`),tb.querySelector(".savebar"));
    m.append(columnList({class:"ai-field-table",align:"start",headerAlign:"start","aria-label":"AI fields",
      rows,key:row=>row.path.join("."),editable:true,localSort:false,
      template:"minmax(180px,1fr) minmax(180px,1fr) minmax(0,1.4fr)",
      columns:[{key:"context",label:"Profile / context",cellClass:"key"},
        {key:"field",label:"Field",cellClass:"key"},
        {key:"value",label:"Value",render:row=>{
          const key=row.path.join("."),cur=edits[key]?.value??row.value,rv=refByPath[key];
          const inp=el("input",{value:cur,class:key in edits?"edited":"",
            "aria-label":`${row.context} ${row.field}`,
            onchange:ev=>{edits[key]={path:row.path,kind:row.kind,value:ev.target.value};renderToolbarOnly();}});
          return refField(inp, rv===undefined?null:[["UCO","ucotag",rv]], cur, (v,ev)=>applyToInput(ev,v), String);}}]}));
    return;
  }
  const text=state.datamap.sections.map(s=>s.lines.join("\n")).join("\n");
  layer.terms.forEach(term=>{
    const lines=text.split("\n").filter(line=>line.toLowerCase().includes(term.toLowerCase())).slice(0,20);
    m.append(LexeditorUI.detailSection({title:term,body:LexeditorUI.stack({fill:false},...lines.map(line=>LexeditorUI.detailNote(line)))}));
  });
  m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},el("b",{},"Programs & Styles are read-only here: "),
    "combat-director and melee-reasoner files are decision graphs. Flattening their transitions, conditions and tasks into generic value rows would make destructive edits too easy; they need a graph-aware editor."));
}

async function saveAI(){
  const file=state.filters.aiFile,map=state.aiEdits[file]||{},edits=Object.values(map);if(!edits.length)return;
  const r=await api("/api/ai/"+file+"/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});
  state.aiEdits[file]={};delete state.aiData[file];toast(`Saved ${r.saved} AI field(s) to ${file}`);renderAI();
}
