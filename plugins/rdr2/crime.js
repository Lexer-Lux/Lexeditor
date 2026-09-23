// ----- Crime & Law (crimeinformation.meta, SP variation) -----
const CRIME_COLS = [
  ["CrimeValue", "Bounty $", "money", "Base monetary crime value, stored in cents; normally becomes bounty when the crime is reported."],
  ["PunishingCrimeValue", "Punish $", "money", "Secondary monetary value used by punishment/escalation logic. Its exact call sites are not documented; treat this interpretation as inferred."],
  ["ImmediateDetectionRange", "Detect rng", "num", "Range within which the crime can be detected immediately instead of relying only on normal witness reporting."],
  ["Timeout", "Timeout", "num", "Inferred: lifetime/cooldown window for this crime-information event. Exact units and call sites are not documented."],
  ["MinTimeBeforeNotifyLawEnforcement", "Notify delay", "num", "Minimum delay before a witness may notify law enforcement: the player's intervention window."],
  ["MinWantedLevelSP", "Min wanted", "num", "Minimum single-player wanted level this crime may establish."],
  ["ForcedWantedLevelIncreaseSP", "Forced wanted+", "num", "Number of wanted levels forcibly added in single player."],
  ["NumWitnesses", "Witnesses", "num", "Inferred: witness-count requirement/limit used by the witness-information rule. This is not a world NPC spawn count."],
  ["ConfrontChance", "Confront %", "num", "Inferred: chance that the configured confrontation behavior runs before or during reporting."],
  ["Disabled", "Off", "bool", "Disables this crime's SP rule when checked."],
];

async function ensureCrime(ds) {
  const st = refStore(ds);
  if (!st.crime && state.config.datasets[ds].crime) {
    try { st.crime = await api("/api/crime", undefined, ds); } catch (e) { st.crime = { crimes: [] }; }
  }
  if (!st.dispatch && state.config.datasets[ds].dispatch) {
    try { st.dispatch = await api("/api/dispatch", undefined, ds); } catch (e) { st.dispatch = { rows: [] }; }
  }
  return st.crime;
}

async function ensureBountyHunters(ds=state.ds){
  if(!state.bountyHunters[ds])state.bountyHunters[ds]=normalizeBountyHunters(await api("/api/bounty-hunters",undefined,ds));
  return state.bountyHunters[ds];
}

const BOUNTY_PRESENTATION={
  settings:{
    RandomWeight:["Response weight","Relative selection weight against other eligible bounty responses. It is not a percentage or a time interval; larger values make this response more likely when the engine chooses among candidates."],
    MinBounty:["Minimum bounty (cents)","Minimum total bounty required before this wilderness bounty-hunter response is eligible. The stored unit is cents, so 1200 means $12.00."],
    MaxLocationOverrideRadius:["Location override radius","Maximum radius used by the response's location-override field. The data names the unit as a world-space distance, but the exact relocation formula has not been resolved; tune this cautiously in game."],
    MinDistanceToTown:["Minimum town distance","Minimum world-space distance from a town before this wilderness response is eligible."],
    IdealSpawnDistanceToTown:["Ideal town distance","Preferred world-space distance from a town used when the response chooses a spawn location. This is a target, not a guaranteed exact distance."]},
  cooldowns:{
    DelayInGameHoursAfterBountyAcquired:["After bounty acquired","Random in-game-hour delay after the player acquires a bounty before another bounty-hunter response may be eligible."],
    DelayInGameHoursAfterMyIncident:["After hunter encounter","Random in-game-hour delay after this bounty-hunter response owns an incident before it may run again."],
    DelayInGameHoursAfterMyIncidentTargetKilled:["After incident target killed","Random in-game-hour delay used when this response's incident target was killed. The data does not expose a more specific player-facing condition."],
    DelayInGameHoursAfterMyIncidentTargetUndetected:["After target escaped detection","In-game-hour delay after the incident target becomes undetected. Rockstar gates this row at WANTED_LEVEL3 and above."]},
  levels:{
    "Clean":"No active wanted/search level (internal wanted score 0). Arthur can still owe a regional bounty while this row applies.",
    "Wanted 1":"Rockstar wanted level 1: internal wanted score 1 through 4,999. This is pursuit severity, not bounty dollars.",
    "Wanted 2":"Rockstar wanted level 2: internal wanted score 5,000 through 14,999. This is pursuit severity, not bounty dollars.",
    "Wanted 3":"Rockstar wanted level 3: internal wanted score 15,000 through 24,999. This is pursuit severity, not bounty dollars.",
    "Wanted 3+":"Rockstar wanted level 3 or higher: internal wanted score 15,000 or more. This special row is used only for the target-undetected delay.",
    "Wanted 4+":"Rockstar wanted level 4 or higher: internal wanted score 25,000 or more. It also includes level 5, which starts at 100,000."},
  phases:{InitialRiders:"Initial riders",OneStarBountyHunters:"Bounty tier 1",TwoStarBountyHunters:"Bounty tier 2",ThreeStarBountyHunters:"Bounty tier 3",FourStarBountyHunters:"Bounty tier 4",FiveStarBountyHunters:"Bounty tier 5"},
  presets:{BountyHunter:"Regular hunter",BountyHunterShotgun:"Shotgun hunter",BountyHunterSniper:"Sniper",PoliceDog:"Police dog"},
  multiplierHelp:"Engine GroupMultiplier for this phase. Rockstar's data does not document the exact group-size formula, so this remains a raw multiplier and should be tuned in game.",
  scopeNote:"Combat specs and loadouts are shared by ordinary law dispatch; they are shown read-only here so bounty-only edits do not silently retune every lawman."
};
function safeDisplay(value,fallback="—"){return value===null||value===undefined||String(value).trim()===""?fallback:String(value);}
function humanizeId(value,fallback="Setting"){
  const raw=safeDisplay(value,fallback).replace(/^.*\//,"").replace(/([a-z0-9])([A-Z])/g,"$1 $2").replace(/_/g," ");
  return raw==="—"?fallback:raw;
}
function normalizeBountyHunters(data){
  const d=data&&typeof data==="object"?data:{};
  d.settings=Array.isArray(d.settings)?d.settings:[];d.cooldowns=Array.isArray(d.cooldowns)?d.cooldowns:[];
  d.phases=Array.isArray(d.phases)?d.phases:[];d.presets=Array.isArray(d.presets)?d.presets:[];
  d.scopeNote=safeDisplay(d.scopeNote,BOUNTY_PRESENTATION.scopeNote);
  d.settings.forEach(s=>{s.id=safeDisplay(s.id,`response/${safeDisplay(s.field,"Unknown")}`);s.field=safeDisplay(s.field,s.id.split("/").pop());const p=BOUNTY_PRESENTATION.settings[s.field]||[humanizeId(s.field),""];s.label=safeDisplay(s.label,p[0]);s.help=safeDisplay(s.help,p[1]);});
  d.cooldowns.forEach(r=>{r.section=safeDisplay(r.section,"Cooldown");r.ids=r.ids&&typeof r.ids==="object"?r.ids:{};r.vanilla=r.vanilla&&typeof r.vanilla==="object"?r.vanilla:{};const p=BOUNTY_PRESENTATION.cooldowns[r.section]||[humanizeId(r.section,"Cooldown"),""];r.eventLabel=safeDisplay(r.eventLabel,p[0]);r.help=safeDisplay(r.help,p[1]);r.level=safeDisplay(r.level,"Tier");r.levelHelp=safeDisplay(r.levelHelp,BOUNTY_PRESENTATION.levels[r.level]||"Rockstar wanted/search state; not bounty dollars.");});
  d.phases.forEach(p=>{p.name=safeDisplay(p.name,"Phase");p.label=safeDisplay(p.label,BOUNTY_PRESENTATION.phases[p.name]||humanizeId(p.name,"Phase"));p.multiplierHelp=safeDisplay(p.multiplierHelp,BOUNTY_PRESENTATION.multiplierHelp);p.groups=Array.isArray(p.groups)?p.groups:[];p.groups.forEach(g=>{g.ids=g.ids&&typeof g.ids==="object"?g.ids:{};g.vanilla=g.vanilla&&typeof g.vanilla==="object"?g.vanilla:{};g.preset=safeDisplay(g.preset,"Responder");g.presetLabel=safeDisplay(g.presetLabel,BOUNTY_PRESENTATION.presets[g.preset]||humanizeId(g.preset,"Responder"));});});
  d.presets.forEach(p=>{p.preset=safeDisplay(p.preset,"Responder");p.label=safeDisplay(p.label,BOUNTY_PRESENTATION.presets[p.preset]||humanizeId(p.preset,"Responder"));p.loadouts=Array.isArray(p.loadouts)?p.loadouts:[];});
  return d;
}
function scrollableCrimeTable(table){return table;}

function bountyNumber(setting,label,help,reference=null){
  if(!setting)return el("span",{},"—");
  const cur=state.bountyHunterEdits[setting.id]??setting.value;
  const input=el("input",{type:"number",min:"0",step:"any",value:cur,disabled:isRO(),class:setting.id in state.bountyHunterEdits?"edited":"",
    onchange:ev=>{const v=ev.target.value;if(v===setting.value)delete state.bountyHunterEdits[setting.id];else state.bountyHunterEdits[setting.id]=v;renderToolbarOnly();refreshGlobalSave();}});
  const refs=state.ds==="mine"&&reference?[["V","vtag",String(reference.value).replace(/f$/i,"")]]:null;
  const control=refField(input,refs,undefined,v=>applyToControl(input,v),String);
  return label===""?control:LexeditorUI.detailField({label:safeDisplay(label,"Setting"),control,help:help?fieldHelp(help):null});
}

async function renderBountyHunters(){
  const current=renderScope("renderBountyHunters");
  const d=await ensureBountyHunters();if(!current())return;const m=$("#main");m.innerHTML="";
  if(!d.available)return noData("The dedicated bountyhunters.meta has not been staged in this dataset.");
  const vsetting=id=>{const s=d.settings.find(x=>x.id===id);return s?.vanilla==null?null:{id,value:s.vanilla};};
  const vcool=id=>{for(const r of d.cooldowns)for(const [bound,settingId] of Object.entries(r.ids))if(settingId===id&&r.vanilla?.[bound]!=null)return {id,value:r.vanilla[bound]};return null;};
  const vphase=id=>{for(const p of d.phases){if(p.multiplierId===id&&p.multiplierVanilla!=null)return {id,value:p.multiplierVanilla};for(const g of p.groups)for(const [key,settingId] of Object.entries(g.ids))if(settingId===id&&g.vanilla?.[key]!=null)return {id,value:g.vanilla[key]};}return null;};
  m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},el("b",{},"Bounty-hunter-only response: "),"threshold, encounter spacing, five escalation phases, hunter composition and dog support. Shared law combat/loadout specs are deliberately read-only below; changing them here would also retune ordinary lawmen."));
  const setting=id=>{const x=d.settings.find(s=>s.id===id);return x&&{...x,value:String(x.value).replace(/f$/i,"")};};
  const top=LexeditorUI.stack({fill:false});
  for(const s of d.settings)top.append(bountyNumber(setting(s.id),s.label,s.help,vsetting(s.id)));m.append(LexeditorUI.detailSection({title:"Encounter trigger",body:top}));
  const tierHelp="Rockstar stores five rows labelled WANTED_CLEAN, WANTED_LEVEL1, WANTED_LEVEL2, WANTED_LEVEL3 and WANTED_LEVEL4+. These are the player's current wanted/search state, not bounty-dollar ranges. Clean means no active wanted level; it does not mean the regional bounty balance is zero. ‘Wanted 4+’ means level 4 and any higher engine tier.";
  const bound=(r,k)=>r.ids[k]?bountyNumber({id:r.ids[k],value:safeDisplay(r[k],"")},"","",vcool(r.ids[k])):el("span",{},"—");
  const cool=columnList({class:"cooldown-table",align:"start",headerAlign:"start","aria-label":"Encounter spacing",
    rows:d.cooldowns,key:(r,index)=>`${r.eventLabel}:${r.level}:${index}`,editable:true,localSort:false,
    template:"minmax(220px,1.4fr) minmax(160px,1fr) 120px 120px",
    columns:[{key:"event",label:"Cooldown event",cellClass:"key",
        render:r=>el("span",{},r.eventLabel,fieldHelp(r.help))},
      {key:"level",label:()=>el("span",{},"Wanted tier ",fieldHelp(tierHelp)),cellClass:"key wanted-tier-cell",
        render:r=>el("span",{},r.level,fieldHelp(r.levelHelp))},
      {key:"min",label:"Min hours",render:r=>bound(r,"min")},
      {key:"max",label:"Max hours",render:r=>bound(r,"max")}]});
  m.append(el("section",{},el("h2",{},"Encounter spacing"),
    LexeditorUI.stack({fill:false,className:"lex-notice"},el("b",{},"Wanted tier is current pursuit state, not bounty value. "),
      "Clean means no active wanted/search level; Arthur can still owe a regional bounty, so the bounty-acquired and hunter-encounter cooldown tables legitimately contain Clean rows. Min and Max are the stored randomized delay range in in-game hours."),
    scrollableCrimeTable(cool)));
  const poolHelp="Fixed responders are always requested by that phase. Random responders are alternatives selected by their relative Weight. Chance is a separate 0–1 gate, used here for police dogs.";
  // One row per group, and the phase's own label and scale ride on the first
  // of its rows, as they did in the table this replaced.
  const phaseRows=d.phases.flatMap(p=>(p.groups.length?p.groups:[null]).map((g,index)=>({p,g,first:index===0})));
  const groupCell=(g,k)=>g?.ids[k]?bountyNumber({id:g.ids[k],value:safeDisplay(g[k],"").replace(/f$/i,"")},"","",vphase(g.ids[k])):el("span",{},"—");
  const pt=columnList({class:"phase-table",align:"start",headerAlign:"start","aria-label":"Escalation composition",
    rows:phaseRows,key:(row,index)=>`${row.p.label}:${index}`,editable:true,localSort:false,
    template:"minmax(140px,1fr) 120px 110px minmax(160px,1fr) 90px 90px 100px 100px",
    columns:[{key:"phase",label:"Phase",cellClass:"key",render:row=>row.first?row.p.label:""},
      {key:"scale",label:"Group scale",render:row=>row.first&&row.p.multiplierId
        ?bountyNumber({id:row.p.multiplierId,value:safeDisplay(row.p.multiplier,"").replace(/f$/i,"")},"",row.p.multiplierHelp,vphase(row.p.multiplierId))
        :el("span",{},row.first?"—":"")},
      {key:"pool",label:()=>el("span",{},"Pool ",fieldHelp(poolHelp)),
        render:row=>row.g?(row.g.bucket==="fixed"?"Fixed":"Random"):"No new group"},
      {key:"responder",label:"Responder",render:row=>row.g?row.g.presetLabel:"Reuses available hunters"},
      {key:"min",label:"Min",render:row=>groupCell(row.g,"min")},
      {key:"max",label:"Max",render:row=>groupCell(row.g,"max")},
      {key:"chance",label:()=>el("span",{},"Chance ",fieldHelp("A normalized probability used when this group is evaluated; for example, 0.2 means a 20% chance.")),
        render:row=>groupCell(row.g,"chance")},
      {key:"weight",label:()=>el("span",{},"Weight ",fieldHelp("Relative selection weight inside the random pool. It is compared with the other weights in the same phase; it is not an independent percentage.")),
        render:row=>groupCell(row.g,"weight")}]});
  m.append(el("section",{},el("h2",{},"Escalation composition"),scrollableCrimeTable(pt)));
  const deps=columnList({class:"responder-table",align:"start",headerAlign:"start","aria-label":"Responder equipment and tactics",
    rows:d.presets,key:p=>p.preset,localSort:false,
    template:"minmax(180px,1fr) minmax(0,1.6fr) minmax(160px,1fr) minmax(140px,1fr)",
    columns:[{key:"label",label:"Responder",cellClass:"key",
        render:p=>el("span",{},p.label,LexeditorUI.detailNote(p.preset))},
      {key:"loadouts",label:"Weapons / weights",
        render:p=>p.loadouts.map(x=>safeDisplay(x.name,"Loadout")+(x.weight?` (${x.weight})`:"")).join(", ")},
      {key:"combat",label:"Combat profile",render:p=>mobArchetypeLink("combat",safeDisplay(p.combatInfo))},
      {key:"chase",label:"Mounted tactics",render:p=>safeDisplay(p.chaseProfile)}]});
  m.append(el("section",{},el("h2",{},"Equipment and tactics (shared law dependencies)"),
    el("div",{class:"subtle"},d.scopeNote),scrollableCrimeTable(deps)));
}

async function saveBountyHunters(){
  const edits=Object.entries(state.bountyHunterEdits).map(([id,value])=>({id,value}));if(!edits.length)return 0;
  const r=await api("/api/bounty-hunters/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});
  state.bountyHunterEdits={};state.bountyHunters.mine=null;toast(`Saved ${r.saved} bounty-hunter setting(s)`);renderCrime();return r.saved;
}

function normalizeHonorActions(data){
  const d=data&&typeof data==="object"?data:{};d.events=Array.isArray(d.events)?d.events:[];d.tiers=Array.isArray(d.tiers)?d.tiers:[];
  d.events.forEach((r,i)=>{r.id=safeDisplay(r.id,`honor_event_${i+1}`);r.label=safeDisplay(r.label,humanizeId(r.id,"Honor event"));r.enabled=Boolean(r.enabled);});
  d.tiers.forEach((r,i)=>{r.id=safeDisplay(r.id,`honor_tier_${i+1}`);r.vanilla=safeDisplay(r.vanilla,"—");r.amount=r.amount??(r.vanilla==="—"?0:Number(r.vanilla));r.enabled=Boolean(r.enabled);});
  return d;
}
async function ensureHonorActions(){if(!state.honorActions)state.honorActions=normalizeHonorActions(await api("/api/honor-actions"));return state.honorActions;}
async function renderHonorActions(){
  const current=renderScope("renderHonorActions");
  const d=await ensureHonorActions();if(!current())return;const m=$("#main");m.innerHTML="";
  if(!d.available)return noData("Honor runtime controls are unavailable for this profile.");
  const table=(title,rows,tier)=>{
    const enabledBox=r=>{
      const edit=state.honorActionEdits[r.id]||{};
      const box=el("input",{type:"checkbox","aria-label":`${safeDisplay(r.label,r.id)} enabled`,
        onchange:e=>{state.honorActionEdits[r.id]={...(state.honorActionEdits[r.id]||{}),enabled:e.target.checked};refreshGlobalSave();}});
      box.checked=edit.enabled??r.enabled;
      return box;
    };
    const amountBox=r=>{
      const edit=state.honorActionEdits[r.id]||{};
      return el("input",{type:"number",step:"1",value:edit.amount??r.amount,
        "aria-label":`Replacement for vanilla honor amount ${safeDisplay(r.vanilla)}`,
        title:"Editable replacement applied to every honor action that uses this vanilla amount.",
        class:("amount" in edit)?"edited":"",
        onchange:e=>{state.honorActionEdits[r.id]={...(state.honorActionEdits[r.id]||{}),amount:Number(e.target.value)};refreshGlobalSave();}});
    };
    const list=columnList({class:"honor-table",align:"start",headerAlign:"start","aria-label":title,
      rows,key:r=>r.id,editable:true,localSort:false,
      template:tier?"minmax(160px,1fr) 110px minmax(160px,1fr)":"minmax(220px,1fr) 110px",
      columns:[{key:"name",label:tier?"Vanilla amount":"Honor event",cellClass:"key",
          render:r=>el("span",{},tier?safeDisplay(r.vanilla):safeDisplay(r.label,humanizeId(r.id,"Honor event")),
            LexeditorUI.detailNote(safeDisplay(r.id,"honor_control")))},
        {key:"enabled",label:"Enabled",cellClass:"bool-cell",render:enabledBox},
        ...(tier?[{key:"amount",label:"Replacement amount",render:amountBox}]:[])]});
    return LexeditorUI.detailSection({title,body:list});};
  // Amounts used to be buried below all 21 event toggles, which made the page
  // look toggle-only. Put the editable table first and state its proven shared
  // scope instead of inventing independent per-event values the game lacks.
  m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},el("b",{},"Honor amounts are editable in the first table. "),
    "Each replacement changes every action that uses that vanilla amount; event toggles remain independent."),
    LexeditorUI.stack({fill:false},
      table("Editable honor amounts",d.tiers,true),table("Independent event toggles",d.events,false)));
}
async function saveHonorActions(){const edits=Object.entries(state.honorActionEdits).map(([id,v])=>({id,...v}));if(!edits.length)return 0;const r=await api("/api/honor-actions/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.honorActionEdits={};state.honorActions=null;toast(`Saved ${r.saved} honor control(s)`);renderCrime();return r.saved;}

const DISPATCH_LABELS = {
  "SinglePlayerWantedLevelThresholds": "Wanted level thresholds (crime score to reach level)",
  "SingleplayerWantedLevelRadius": "WANTED CIRCLE radius per wanted level (m)",
  "HiddenEvasionTimes": "Hidden-evasion table (ALL ZERO — unused in SP; the real escape timer is TimeEvadingForEscape in incidentstuning.meta)",
  "WantedIncidentEvasion": "Active pursuit / search (incidentstuning.meta)",
  "CopsToPreserveAroundPlayer": "Lawmen kept around you (per wanted level)",
  "LawSpawnDelayMin": "Law spawn delay MIN (s)",
  "LawSpawnDelayMax": "Law spawn delay MAX (s)",
  "DispatchOrderDistances": "Pursuit order distances / culling",
  "": "Global",
};
const DISPATCH_FIELD_LABELS = {
  ParoleDuration: "Post-search parole / reacquisition duration",
  TimeEvadingForEscape: "Time hidden before escaping (seconds)",
};
const DISPATCH_FIELD_HELP = {
  ParoleDuration: "Rockstar's dispatch field for the short parole phase after the active incident ends. This is the candidate for the dark-red-lawman reacquisition window. The shipped value is 9000 raw engine units; the schema does not declare the unit, so calibrate it in game before making a very large change.",
  TimeEvadingForEscape: "CBountyIncident.Evasion.TimeEvadingForEscape in tune/incidentstuning.meta. This is the real Story Mode pursuit/search escape timer; Rockstar ships 75 seconds. dispatch.meta's HiddenEvasionTimes rows are all zero and are not substituted for this control.",
};

function dispatchLabel(g) {
  if (DISPATCH_LABELS[g] !== undefined) return DISPATCH_LABELS[g];
  const m = /^(\w+)\/\w+\[([^\]]+)\]$/.exec(g);
  if (m) return (m[1] === "RegionInfo" ? "Region: " : "Mayhem cooldown: ")
              + m[2].replace(/^LAW_REGION_|^MAYHEM_MODIFIER_/, "").replace(/_/g, " ");
  return g;
}

function dispatchSection() {
  const st = refStore(state.ds);
  if (!st.dispatch || !st.dispatch.rows.length) return el("div");
  const vd = state.store.vanilla?.dispatch;
  const wrap = el("div");
  if(state.helpOpen.crime)wrap.append(el("div", { class: "hint", style: "margin-top:18px" },
    el("b", {}, "Dispatch / wanted response (dispatch.meta): "),
    "thresholds are the bounty $ that trigger each wanted level; radius/evasion/lawmen ",
    "are per level. CAUTION: the Crime Tweaks author deliberately shipped vanilla ",
    "dispatch.meta citing a camp-respawn-after-escape bug with modified ones — ours is ",
    "vanilla-identical until you edit, and we should test carefully after changes."));
  const dispatchRows=sortedRows("dispatch",st.dispatch.rows,{setting:r=>dispatchLabel(r.group),field:r=>r.field,value:r=>+r.value});
  const dispatchValue=r=>{
    const ek=r.group+"|"+r.field;
    const cur=isRO()?r.value:(state.dispatchEdits[ek]??r.value);
    const vRow=vd&&vd.rows.find(x=>x.group===r.group&&x.field===r.field);
    const inp=el("input",{type:"number",step:"any",value:cur,
      "aria-label":`${dispatchLabel(r.group)} ${r.field}`,
      class:ek in state.dispatchEdits?"edited":"",
      onchange:ev=>{
        const v=ev.target.value;
        if(v===r.value)delete state.dispatchEdits[ek];
        else state.dispatchEdits[ek]=v;
        ev.target.classList.toggle("edited",ek in state.dispatchEdits);
        renderToolbarOnly();
      }});
    return refField(inp, vRow?[["V","vtag",vRow.value]]:null, cur, (v,ev)=>applyToInput(ev,v), String);
  };
  wrap.append(columnList({class:"dispatch-table",align:"start",headerAlign:"start","aria-label":"Dispatch settings",
    rows:dispatchRows,key:r=>r.group+"|"+r.field,editable:true,localSort:false,
    template:"minmax(180px,1fr) minmax(200px,1.2fr) minmax(160px,1fr)",
    columns:[{key:"setting",label:"Setting",cellClass:"cat",render:r=>dispatchLabel(r.group)},
      {key:"field",label:"Field",cellClass:"key",
        render:r=>el("span",{},DISPATCH_FIELD_LABELS[r.field]||r.field.replace("WantedLevel","WL "),
          DISPATCH_FIELD_HELP[r.field]?fieldHelp(DISPATCH_FIELD_HELP[r.field]):"")},
      {key:"value",label:"Value",render:dispatchValue}]}));
  return wrap;
}

async function switchCrimeSection(value) {
  state.filters.crimeSection=value;
  await renderCrime();
  await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
  if(document.scrollingElement)document.scrollingElement.scrollTop=0;
  window.scrollTo(0,0);
}

async function renderCrime() {
  const current=renderScope("renderCrime");
  const f = state.filters;
  if(!f.crimeSection)f.crimeSection="crimes";
  if (!state.config.datasets[state.ds].crime)
    return noData(`This dataset has no crimeinformation.meta (${dsInfo().dir}).`);
  const data = await ensureCrime(state.ds);
  if (state.ds === "mine") { await ensureCrime("vanilla"); await ensureCrime("crimeTweaks"); }
  if(!current())return;
  const tb = $("#toolbar"); tb.innerHTML = "";
  const sectionTabs=LexeditorUI.subtabBar({active:f.crimeSection,label:"Crime view",tabs:[["bounty","Bounty hunters"],["crimes","Crime rules"],["dispatch","Dispatch & wanted"],["honor","Honor actions"]].map(([id,label])=>({id,label})),change:switchCrimeSection});
  tb.append(sectionTabs);
  if(f.crimeSection==="dispatch"){
    tb.append(el("span",{class:"count"},`${refStore(state.ds).dispatch?.rows.length||0} settings`),savebar(saveCrime));
    const m=$("#main");m.innerHTML="";m.append(dispatchSection());refreshGlobalSave();installTabContext();return;
  }
  if(f.crimeSection==="bounty"){
    tb.append(el("span",{class:"count"},"5 escalation phases"),savebar(saveBountyHunters));
    await renderBountyHunters();refreshGlobalSave();installTabContext();return;
  }
  if(f.crimeSection==="honor"){
    const d=await ensureHonorActions();if(!current())return;tb.append(el("span",{class:"count"},`${d.events?.length||0} events · ${d.tiers?.length||0} shared tiers`),savebar(saveHonorActions));
    await renderHonorActions();refreshGlobalSave();installTabContext();return;
  }
  tb.append(el("input", { type: "text", placeholder: "Search crimes… (e.g. MURDER, ROBBERY)", value: f.crimeQ || "",
      oninput: ev => { f.crimeQ = ev.target.value; filterRerender(ev,renderCrime); } }),
    el("span", { class: "count", id: "crimecount" }),savebar(saveCrime));
  const q = (f.crimeQ || "").trim().toUpperCase();
  let rows = data.crimes.filter(c => !q || c.key.toUpperCase().includes(q)||humanName("crimes",c.key).toUpperCase().includes(q));
  const crimeGetters={name:c=>humanName("crimes",c.key)||c.key,severity:c=>c.severity};CRIME_COLS.forEach(([field])=>crimeGetters[field]=c=>field==="Disabled"?String(c[field]):+c[field]);
  rows=sortedRows("crime",rows,crimeGetters);
  $("#crimecount").textContent = `${rows.length} crimes (SP variation)`;
  const m = $("#main"); m.innerHTML = "";
  if(state.helpOpen.crime)m.append(el("div", { class: "hint" },
    el("b", {}, "Law's reaction rulebook: "), "per crime — ", el("b", {}, "Bounty $"),
    " added when reported, detection range, how long a witness takes to notify the law ",
    "(your window to stop them), witnesses spawned, minimum/forced wanted level, and ",
    el("b", {}, "Off"), " to disable the crime entirely. NOTE: your Crime Tweaks mod ",
    "replaces this same file — when MyOverhaul is installed, load order decides."));
  const vc = state.store.vanilla?.crime;
  const cc = state.store.crimeTweaks?.crime;
  const vanillaRow = c => vc && vc.crimes.find(x => x.key === c.key);
  const tweakRow = c => cc && cc.crimes.find(x => x.key === c.key);
  const fieldControl = (c, [field, label, kind]) => {
    const ek = c.key + "|" + field;
    const raw = isRO() ? c[field] : (state.crimeEdits[ek] ?? c[field]);
    const vRow = vanillaRow(c), ctRow = tweakRow(c);
    if (raw === null || raw === undefined) return "—";
    if (kind === "bool") {
      const cb = el("input", { type: "checkbox", "aria-label": `${c.key} ${label}`,
        onchange: ev => {
          const v = ev.target.checked ? "true" : "false";
          if (v === c[field]) delete state.crimeEdits[ek]; else state.crimeEdits[ek] = v;
          renderToolbarOnly();
        } });
      cb.checked = String(raw) === "true";
      return refField(cb, [["V","vtag",vRow?.[field]],["CT","cttag",ctRow?.[field]]], raw,
        (v)=>{cb.checked=String(v)==="true";cb.dispatchEvent(new Event("change"));}, v=>String(v),
        { bool: true });
    }
    const isMoney = kind === "money";
    const inp = el("input", { type: "number", step: isMoney ? "0.01" : "any",
      value: isMoney ? fmtMoney(+raw) : (+raw % 1 ? (+raw).toFixed(2) : String(+raw)),
      class: ek in state.crimeEdits ? "edited" : "",
      "aria-label": `${c.key} ${label}`,
      onchange: ev => {
        const v = isMoney ? String(Math.round(parseFloat(ev.target.value || "0") * 100))
                          : String(+ev.target.value || 0);
        if (v === String(+c[field])) delete state.crimeEdits[ek];
        else state.crimeEdits[ek] = v;
        ev.target.classList.toggle("edited", ek in state.crimeEdits);
        renderToolbarOnly();
      } });
    return refField(inp, [["V","vtag",vRow?.[field]],["CT","cttag",ctRow?.[field]]], raw,
      (v,ev)=>applyToInput(ev,isMoney?fmtMoney(+v):String(+v)), v=>isMoney?"$"+fmtMoney(+v):String(+v));
  };
  const severityControl = c => {
    const sevEk = c.key + "|severity";
    const severityValue = isRO() ? c.severity : (state.crimeEdits[sevEk] ?? c.severity);
    const vRow = vanillaRow(c), ctRow = tweakRow(c);
    const sev = el("select", { class: "key", disabled: isRO(),
      "aria-label": `${c.key} severity`,
      onchange: ev => {
        if (ev.target.value === c.severity) delete state.crimeEdits[sevEk];
        else state.crimeEdits[sevEk] = ev.target.value;
        ev.target.classList.toggle("edited", sevEk in state.crimeEdits);
        renderToolbarOnly();
      } },...["None","Low","Medium","High"].map(value=>{const option=el("option",{value},value);if(value===severityValue)option.selected=true;return option;}));
    return refField(sev, [["V","vtag",vRow?.severity],["CT","cttag",ctRow?.severity]], severityValue,
      (v,ev)=>applyToInput(ev,v), v=>String(v));
  };
  m.append(columnList({class:"crime-table",align:"start",headerAlign:"start","aria-label":"Crimes",
    rows,key:c=>c.key,editable:true,localSort:false,
    template:`minmax(220px,1.4fr) repeat(${CRIME_COLS.length},minmax(0,.9fr)) 120px`,
    columns:[{key:"name",label:()=>el("span",{},"Name / crime",fieldHelp("The editable name is an editor-only identification label, stored in this RDR2 plugin's labels.json; it does not rename game UI text.")),
        cellClass:"key",
        render:c=>el("span",{class:"crime-name"},humanNameInput("crimes",c.key),el("span",{class:"crime-key"},c.key.replace("CRIME_","")))},
      ...CRIME_COLS.map(col=>({key:col[0],
        label:col[3]?()=>el("span",{},col[1],fieldHelp(col[3])):col[1],
        cellClass:col[2]==="bool"?"bool-cell":"",
        render:c=>fieldControl(c,col)})),
      {key:"severity",label:()=>el("span",{},"Severity",fieldHelp("Qualitative severity class used by crime escalation and law-response rules.")),
        render:severityControl}]}));
  installTabContext();
}

async function saveCrime() {
  if (isRO()) return;
  const edits = Object.entries(state.crimeEdits).map(([k, value]) => {
    const [key, field] = k.split("|");
    return { key, field, value };
  });
  const dEdits = Object.entries(state.dispatchEdits).map(([k, value]) => {
    const [group, field] = k.split("|");
    return { group, field, value };
  });
  if (!edits.length && !dEdits.length) return;
  try {
    let saved = 0;
    if (edits.length) {
      const r = await api("/api/crime/save", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ edits }) });
      saved += r.saved;
      const st = refStore("mine");
      for (const e of edits) {
        const c = st.crime && st.crime.crimes.find(x => x.key === e.key);
        if (c) c[e.field] = e.value;
      }
      state.crimeEdits = {};
    }
    if (dEdits.length) {
      const r2 = await api("/api/dispatch/save", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ edits: dEdits }) });
      saved += r2.saved;
      const st = refStore("mine");
      for (const e of dEdits) {
        const row = st.dispatch && st.dispatch.rows.find(x => x.group === e.group && x.field === e.field);
        if (row) row.value = e.value;
      }
      state.dispatchEdits = {};
    }
    toast(`Saved ${saved} change(s) to crime/dispatch`);
    renderCrime();
  } catch (ex) { throw showSaveFailure(ex); }
}
