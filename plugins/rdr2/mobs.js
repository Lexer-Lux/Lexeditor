// ----- Mobs: enemy stats (#190, first slice of #171) -----
// Two source files, shown side by side but never joined: combatbehaviour.meta
// owns how well a faction shoots, pedhealth.meta owns how much it takes to kill.
// The ped-model -> profile/archetype binding is not in either file.
const MOB_LAYERS={
  combat:{label:"Combat profiles",file:"combat",
    hint:"Combat profiles control faction accuracy and combat behavior. A profile change affects every character assigned to it. Situational accuracy settings are on the AI tab."},
  health:{label:"Health archetypes",file:"health",
    hint:"These profiles control health and related character resources. Choose a section to see its profiles. A change affects every character assigned to that profile."},
};
const MOB_COMBAT_COLUMNS=[
  ["WeaponAccuracy","Accuracy","Base hit chance for this faction before situational accuracy modifiers."],
  ["AccuracyOffsetModifier","Acc offset","Scales the aim offset applied to shots that are meant to miss."],
  ["CombatAbility","Ability",""],
  ["WeaponShootRateModifier","Shoot rate",""],
  ["BlindFireChance","Blind fire",""],
  ["FiringPatternHash","Firing pattern",""],
  ["TimeBetweenPeeks","Peek gap","Seconds in cover before this faction pops out again."],
  ["MaxShootingDistance","Max range","-1 means no explicit cap."],
  ["CrouchChance","Crouch",""],
  ["AttackRanges","Attack range",""],
  ["CombatMovement","Movement",""],
];

function mobRecordKey(record){return record.fields[0]?.path.slice(0,-1).join(".")||`${record.section||""}/${record.name}`;}
function mobsSaveBody(){
  const edits=Object.values(state.mobEdits),seen=new Set();
  for(const edit of edits){
    if(!edit||Object.keys(edit).sort().join(",")!=="file,kind,path,value"||!Object.hasOwn(MOB_LAYERS,edit.file)||!Array.isArray(edit.path)||!edit.path.length||edit.path.some(i=>!Number.isSafeInteger(i)||i<0))throw new Error("Invalid Mobs target.");
    const rows=state.mobs?.[edit.file]?.records?.flatMap(record=>record.fields)||[],key=edit.path.join("."),identity=edit.file+"|"+key,matches=rows.filter(row=>row.path.join(".")===key),row=matches[0];
    if(matches.length!==1||seen.has(identity)||row.kind!==edit.kind)throw new Error("Unknown or duplicate Mobs target.");
    seen.add(identity);const error=aiDraftError(row,edit.value,rows);if(error)throw new Error(error);
  }
  return {edits};
}
async function preflightMobsSave(){
  const body=mobsSaveBody();if(!body.edits.length)return;
  await api("/api/mobs/validate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
}
const MOB_HEALTH_COLUMNS=[
  ["DefaultEnergy","HP",""],
  ["DefaultArmour","Armour",""],
  ["InjuredHealthThreshold","Injured at",""],
  ["CriticallyInjuredHealthThreshold","Critical at",""],
  ["FireVulnerability","Fire vuln","1.0 is a normal human; most animals sit well below."],
  ["MeleeProperties/FatiguedHealthThreshold","Fatigued at",""],
  ["MeleeProperties/KnockedOutHealthThreshold","KO at",""],
  ["Invincible","Invincible",""],
];

async function renderMobs(){
  const current=renderScope("renderMobs");
  const f=state.filters;
  if(!state.mobs)state.mobs=await api("/api/mobs");
  if(!current())return;
  if(f.mobView==="models")return renderMobModels();
  return renderMobArchetypes();
}

function mobViewTabs(active){
  const f=state.filters;
  return LexeditorUI.subtabBar({tabs:[{id:"combat",label:"Combat profiles",help:MOB_LAYERS.combat.hint},
    {id:"health",label:"Health archetypes",help:MOB_LAYERS.health.hint},{id:"models",label:"Observed Models"}],
    active:active==="models"?"models":f.mobLayer||"combat",
    change:key=>{f.mobView=key==="models"?"models":"archetypes";if(key!=="models")f.mobLayer=key;renderMobs()}});
}
function mobGroupFilter(groups,key,rerender){
  const select=el("select",{"aria-label":"Group",onchange:event=>{state.filters[key]=event.target.value;rerender()}},
    ...groups.map(([value,label])=>el("option",{value,selected:value===state.filters[key]},label)));
  return LexeditorUI.detailField({label:"Group",control:select});
}

// Per-model evidence is read-only. The model -> archetype binding is in no data
// file we ship, so LEXEDITOR never presents an HP-based guess as a saved fact.
const MOB_MODEL_STATS=[
  ["DefaultEnergy","HP"],["DefaultArmour","Armour"],
  ["InjuredHealthThreshold","Injured at"],["CriticallyInjuredHealthThreshold","Critical at"],
  ["FireVulnerability","Fire vuln"],["MeleeProperties/KnockedOutHealthThreshold","KO at"],
];
async function renderMobModels(){
  const current=renderScope("renderMobModels");
  const f=state.filters;
  if(!state.mobModels)state.mobModels=await api("/api/mob-models");
  if(!current())return;
  const data=state.mobModels,tb=$("#toolbar");tb.innerHTML="";
  if(!f.mobModelGroup)f.mobModelGroup="gang";
  const groups=[["gang","Gangs"],["ambient","Ambient"],["unique","Unique"],["scenario","Scenario"]];
  tb.append(mobViewTabs("models"),
    mobGroupFilter(groups,"mobModelGroup",renderMobModels),
    el("input",{type:"text",placeholder:"Filter observed model…",value:f.mobModelQ||"",oninput:ev=>{f.mobModelQ=ev.target.value;filterRerender(ev,renderMobModels);}}));
  const m=$("#main");m.innerHTML="";
  if(!data.probeAvailable){m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},el("b",{},"No model observations are available. "),
    "MobProbe writes this read-only evidence after it sees models in the running game. Use Archetypes to edit the real combat and health data."));return;}
  m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},el("b",{},`MobProbe observed ${data.probedCount} models. `),
    "Possible health profiles are shown only as candidates. Equal HP does not prove a model-to-profile binding."));
  const archetypes=state.mobs?.health?.records?.filter(r=>r.section==="HealthConfig")||[];
  const statOf=(name,field)=>{const rec=archetypes.find(r=>r.name===name);if(!rec)return "";
    const hit=rec.fields.find(x=>x.field===field);return hit?hit.value:"";};
  const q=(f.mobModelQ||"").toUpperCase();
  const rows=data.models.filter(r=>r.observedHealth!==null&&r.group===f.mobModelGroup&&(!q||r.model.includes(q)));
  tb.append(el("span",{class:"count"},`${rows.length} observed`));
  if(!rows.length){m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},"No observed models match this group and filter."));return;}
  const getters={model:r=>r.model,hp:r=>r.observedHealth??Infinity,archetype:r=>r.candidates.length===1?r.candidates[0]:""};
  m.append(columnList({class:"mob-model-table",align:"start",headerAlign:"start","aria-label":"Mob models",
    rows:sortedRows("mob-models",rows,getters),key:r=>r.model,localSort:false,
    template:`minmax(180px,1fr) 130px minmax(0,1.4fr) repeat(${MOB_MODEL_STATS.length},minmax(0,.7fr))`,
    columns:[{key:"model",label:"Model",cellClass:"key"},
      {key:"hp",label:()=>el("span",{},"Observed HP",fieldHelp("What the running game actually gave this model. Blank means MobProbe has not seen it.")),
        render:r=>r.observedHealth??el("span",{class:"subtle"},r.probeStatus||"not probed")},
      {key:"candidates",label:"Possible health profiles",cellClass:"requirements",
        render:r=>r.candidates.length
          ?el("span",{},...r.candidates.flatMap((name,index)=>[index?", ":"",mobArchetypeLink("health",name)]))
          :"No exact HP match"},
      ...MOB_MODEL_STATS.map(c=>({key:c[0],label:c[1],
        render:r=>{const chosen=r.candidates.length===1?r.candidates[0]:"";return chosen?statOf(chosen,c[0]):"—";}}))]}));
}

async function renderMobArchetypes(){
  const f=state.filters;
  const layerKey=MOB_LAYERS[f.mobLayer]?f.mobLayer:"combat";
  const layer=MOB_LAYERS[layerKey],data=state.mobs[layer.file];
  const tb=$("#toolbar");tb.innerHTML="";
  tb.append(mobViewTabs("archetypes"),
    mobGroupFilter([["humans","Humans"],["animals","Animals"],["other","Other"]],"mobGroup",renderMobs),
    el("input",{type:"text",placeholder:"Filter record…",value:f.mobQ||"",oninput:ev=>{f.mobQ=ev.target.value;filterRerender(ev,renderMobs);}}),
    savebar(saveMobs));
  const m=$("#main");m.innerHTML="";
  if(!data||!data.available)return noData(`No ${layerKey==="health"?"pedhealth.meta":"combatbehaviour.meta"} in this dataset and no vanilla extract to fall back on.`);
  if(layerKey==="health"){
    const sections=[...new Set(data.records.map(record=>record.section))];
    if(!sections.includes(f.mobHealthSection))f.mobHealthSection=sections.includes("HealthConfig")?"HealthConfig":sections[0];
    const labels={HealthConfig:"Health",StaminaConfig:"Stamina",SpecialAbilityConfig:"Special ability",HealthRechargeConfig:"Health recharge",EnergyConfig:"Energy"};
    tb.append(LexeditorUI.detailField({label:"Section",control:el("select",{"aria-label":"Section",onchange:event=>{f.mobHealthSection=event.target.value;renderMobs();}},
      ...sections.map(section=>el("option",{value:section,selected:section===f.mobHealthSection},labels[section]||section)))}));
  }
  const columns=layerKey==="health"?MOB_HEALTH_COLUMNS:MOB_COMBAT_COLUMNS;
  const q=(f.mobQ||"").toUpperCase();
  let rows=data.records.filter(r=>r.group===f.mobGroup&&(!q||r.name.toUpperCase().includes(q)));
  if(layerKey==="health")rows=rows.filter(r=>r.section===f.mobHealthSection);
  if(!rows.length)return m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},"Nothing in this group matches the filter."));
  const fieldOf=(record,name)=>record.fields.find(x=>x.field===name);
  const getters={name:r=>r.name};
  columns.forEach(col=>{getters[col[0]]=r=>{const hit=fieldOf(r,col[0]);if(!hit)return "";const n=parseFloat(hit.value);return Number.isFinite(n)&&String(n)!==""?n:hit.value;};});
  const allFields=data.records.flatMap(record=>record.fields);
  const statControl=(record,field)=>{
    const editKey=`${layer.file}|${field.path.join(".")}`;
    const cur=(editKey in state.mobEdits)?state.mobEdits[editKey].value:field.value;
    return xmlScalarControl(field,allFields,{value:cur,edited:()=>editKey in state.mobEdits,label:`${record.name} ${field.field}`,change:value=>{
        if(value===field.value||(aiFieldType(field)==="boolean"&&value.toLowerCase()===field.value.toLowerCase()))delete state.mobEdits[editKey];
        else state.mobEdits[editKey]={file:layer.file,path:field.path,kind:field.kind,value};
        refreshGlobalSave();
      }});
  };
  const ordered=sortedRows("mobs",rows,getters);
  // names: Game profile identities stay fixed; changing their names would change runtime bindings.
  m.append(LexeditorUI.pagedListDetail({rows:ordered,key:mobRecordKey,selected:f.mobSelected?.[layer.file]||mobRecordKey(ordered[0]),renamable:false,pageSize:15,noun:"archetypes",slots:false,splitKey:"rdr2-mobs",
    sync:view=>{f.mobSelected ||= {};f.mobSelected[layer.file]=view.selected},
    master:view=>columnList({class:"mob-table",rows:view.rows,key:mobRecordKey,selected:view.selected,select:view.select,"aria-label":"Mob archetypes",columns:[{key:"name",label:"Record"},{key:"group",label:"Group"}]}),
    detail:record=>LexeditorUI.detailPanel({title:record.name,help:fieldHelp(layer.hint+" Numeric limits are not yet established. Unsupported values are read-only."),body:record.fields.filter(field=>field.field!=="Name").map(field=>{
      const definition=columns.find(col=>col[0]===field.field);
      return LexeditorUI.detailField({label:definition?.[1]||field.field,help:definition?.[2]?fieldHelp(definition[2]):null,control:statControl(record,field)});
    })})}));
}

async function saveMobs(){
  if(isRO())return 0;
  const body=mobsSaveBody();if(!body.edits.length)return 0;
  await api("/api/mobs/validate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const r=await api("/api/mobs/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  state.mobEdits={};state.mobs=null;toast(`Saved ${r.saved} mob stat field(s)`);renderMobs();return r.saved;
}
