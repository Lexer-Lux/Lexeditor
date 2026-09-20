// ----- Mobs: enemy stats (#190, first slice of #171) -----
// Two source files, shown side by side but never joined: combatbehaviour.meta
// owns how well a faction shoots, pedhealth.meta owns how much it takes to kill.
// The ped-model -> profile/archetype binding is not in either file.
const MOB_LAYERS={
  combat:{label:"Combat profiles",file:"combat",
    hint:"One record per faction. WeaponAccuracy is the base hit chance before any situational modifier — PLAYER is 0.1, GANG_ODRISCOLLS is 0.6. Changing a row changes every ped bound to that profile."},
  health:{label:"Health archetypes",file:"health",
    hint:"One record per health archetype. DefaultEnergy is the HP pool; the ENEMY_EASIEST→HARDEST and LAW_* ladders are the difficulty tiers."},
};
const MOB_COMBAT_COLUMNS=[
  ["WeaponAccuracy","Accuracy","Base hit chance for this faction, before pedaccuracy.meta's situational modifiers. This is the value behind an enemy who cannot hit you."],
  ["AccuracyOffsetModifier","Acc offset","Scales the aim offset applied to shots that are meant to miss."],
  ["CombatAbility","Ability","CA_Poor / CA_Average / CA_Professional. A named tier the combat code reads, not a number."],
  ["WeaponShootRateModifier","Shoot rate",""],
  ["BlindFireChance","Blind fire",""],
  ["FiringPatternHash","Firing pattern",""],
  ["TimeBetweenPeeks","Peek gap","Seconds in cover before this faction pops out again."],
  ["MaxShootingDistance","Max range","-1 means no explicit cap."],
  ["CrouchChance","Crouch",""],
  ["AttackRanges","Attack range",""],
  ["CombatMovement","Movement",""],
];
const MOB_HEALTH_COLUMNS=[
  ["DefaultEnergy","HP","Health pool for this archetype."],
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
  m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},el("b",{},layer.label+": "),layer.hint,
    el("div",{class:"subtle"},`Source: ${data.source}. Accuracy is finished off by pedaccuracy.meta on the AI tab, which ships only companion and Default — that global stack is what halves incoming accuracy against a moving target.`)));
  const columns=layerKey==="health"?MOB_HEALTH_COLUMNS:MOB_COMBAT_COLUMNS;
  const q=(f.mobQ||"").toUpperCase();
  let rows=data.records.filter(r=>r.group===f.mobGroup&&(!q||r.name.toUpperCase().includes(q)));
  if(layerKey==="health")rows=rows.filter(r=>r.section==="HealthConfig");
  tb.insertBefore(el("span",{class:"count"},`${rows.length} record${rows.length===1?"":"s"}`),tb.querySelector(".savebar"));
  if(!rows.length)return m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},"Nothing in this group matches the filter."));
  const fieldOf=(record,name)=>record.fields.find(x=>x.field===name);
  const getters={name:r=>r.name};
  columns.forEach(col=>{getters[col[0]]=r=>{const hit=fieldOf(r,col[0]);if(!hit)return "";const n=parseFloat(hit.value);return Number.isFinite(n)&&String(n)!==""?n:hit.value;};});
  const statControl=(record,col)=>{
    const field=fieldOf(record,col[0]);
    if(!field)return "—";
    const editKey=`${layer.file}|${field.path.join(".")}`;
    const cur=(editKey in state.mobEdits)?state.mobEdits[editKey].value:field.value;
    const numeric=/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(String(field.value)),boolean=/^(true|false)$/i.test(String(field.value));
    const choices=[...new Set([...data.records.flatMap(r=>r.fields.filter(x=>x.field===field.field).map(x=>String(x.value))),String(cur)])].sort();
    const input=el(!numeric&&!boolean?"select":"input",{type:boolean?"checkbox":numeric?"number":"text",...(boolean?{checked:String(cur).toLowerCase()==="true"}:{value:cur}),
      class:editKey in state.mobEdits?"edited":"",
      "aria-label":`${record.name} ${field.field}`,
      title:`${field.field} (${field.kind})`,
      onchange:ev=>{
        const value=boolean?String(ev.target.checked):ev.target.value;
        if(numeric&&(!value.trim()||!Number.isFinite(Number(value)))){ev.target.setCustomValidity("Enter a finite number");ev.target.reportValidity();return;}
        ev.target.setCustomValidity("");
        if(value===field.value)delete state.mobEdits[editKey];
        else state.mobEdits[editKey]={file:layer.file,path:field.path,kind:field.kind,value};
        ev.target.classList.toggle("edited",editKey in state.mobEdits);
        renderToolbarOnly();
      }});
    if(!numeric&&!boolean)input.replaceChildren(...choices.map(value=>el("option",{value,selected:value===String(cur)},value)));
    if(isRO())input.disabled=true;
    return input;
  };
  m.append(columnList({class:"mob-table",align:"start",headerAlign:"start","aria-label":"Mob archetypes",
    rows:sortedRows("mobs",rows,getters),key:record=>record.name,editable:true,localSort:false,
    template:`minmax(180px,1fr) repeat(${columns.length},minmax(0,.8fr))`,
    columns:[{key:"name",label:"Record",cellClass:"key"},
      ...columns.map(col=>({key:col[0],
        label:col[2]?()=>el("span",{},col[1],fieldHelp(col[2])):col[1],
        render:record=>statControl(record,col)}))]}));
}

async function saveMobs(){
  const edits=Object.values(state.mobEdits);if(!edits.length)return 0;
  const r=await api("/api/mobs/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});
  state.mobEdits={};state.mobs=null;toast(`Saved ${r.saved} mob stat field(s)`);renderMobs();return r.saved;
}
