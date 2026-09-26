// ----- GameplayTweaks settings -----
// The presentation schema lives in this plugin's settings_schema.json and arrives on
// /api/settings. GameplayTweaks.ini remains the source of truth for which
// settings exist; the schema only says how they are arranged and described.
// Anything the schema does not mention still renders as its own category, so a
// newly added INI section can never be lost.
function settingsSchema(){return (state.settings&&state.settings.schema)||{};}
function schemaMap(name){const value=settingsSchema()[name];return value&&typeof value==="object"?value:{};}
function schemaSet(name){const value=settingsSchema()[name];return new Set(Array.isArray(value)?value:[]);}

function humanSettingName(name){
  return String(name).replace(/[_-]/g," ").replace(/([a-z0-9])([A-Z])/g,"$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g,"$1 $2")
    .replace(/([A-Za-z])(\d)/g,"$1 $2").replace(/(\d)([A-Za-z])/g,"$1 $2").replace(/([A-Za-z])([+-]\d)/g,"$1 $2")
    .replace(/\bMs\b/g,"MS").replace(/\bXp\b/g,"XP").replace(/\bIni\b/g,"INI").replace(/\bAi\b/g,"AI");
}
function settingLabel(section,key){
  const authored=schemaMap("labels")[`${section}|${key}`];
  if(authored)return authored;
  return key==="Enabled"?humanSettingName(section):humanSettingName(key);
}
function settingIsDeveloper(section,key){return schemaSet("dev").has(`${section}|${key}`);}
function settingConstBoundary(section,key){
  const value=schemaMap("const")[`${section}|${key}`];
  return typeof value==="string"?value:"";
}
function settingChoices(section,key){
  const entry=schemaMap("choices")[`${section}|${key}`];
  return entry&&Array.isArray(entry.options)?entry.options:null;
}
function settingRange(section,key){
  const entry=schemaMap("ranges")[`${section}|${key}`];
  return entry&&typeof entry==="object"?entry:null;
}
function settingIsBoolean(section,key){
  // The boolean list is extracted from the reading code (readB / GetPrivateProfileIntA
  // ... != 0). Fall back to the old name heuristics only for keys the runtime does
  // not read yet, so a new INI key still gets a sensible control.
  if(schemaSet("booleans").has(`${section}|${key}`))return true;
  return key==="Enabled"; // every [Section] Enabled the runtime reads goes through readB().
}

// Help resolution order: the INI's own comment for that key, then the schema's
// supplemental text, then a pattern for the repeated numeric families. Section
// introductions belong on category headings; reusing one for a field can put a
// large, unrelated block behind that field's "?".
function settingPatternHelp(section,key){
  let m;
  if(key==="Enabled")return `Master switch for ${humanSettingName(section)}. Turning it off leaves the rest of this section saved so the same configuration returns when it is re-enabled.`;
  if(section==="WalletCap"&&(m=/^Rank(\d+)Dollars$/.exec(key)))
    return `Wallet capacity in dollars at Gambler challenge rank ${m[1]}.`;
  if(section==="HonorPrices"&&(m=/^Rank([+-]\d+)Multiplier$/.exec(key)))
    return `Shop purchase-price multiplier at honor rank ${m[1]}. 1.00 is the undiscounted catalog price; above 1 is a surcharge, below 1 a discount.`;
  if(section==="Camera"&&(m=/^(.*)ShoulderOffset$/.exec(key)))
    return `Horizontal offset for the ${humanSettingName(m[1]).toLowerCase()} camera. The engine can limit visible movement even when the stored value changes.`;
  if(section==="Camera"&&(m=/^(.*)Distance$/.exec(key)))
    return `Orbit distance for the ${humanSettingName(m[1]).toLowerCase()} camera. The engine can limit the visible distance in some camera states.`;
  if(section==="Camera"&&(m=/^(.*)LowCamera$/.exec(key)))
    return `Choose LOW instead of NORMAL framing for the ${humanSettingName(m[1]).toLowerCase()} camera. This is a two-state setting, not continuous height; some camera states ignore it.`;
  if((m=/^(SpentBar|SpentCore|Live|Zero)([RGBA])$/.exec(key))){
    const channel={R:"Red",G:"Green",B:"Blue",A:"Alpha"}[m[2]];
    return `${channel} component of the ${humanSettingName(m[1]).toLowerCase()} colour. RGB components control hue/brightness while Alpha controls opacity.`;
  }
  return "";
}
function settingHelp(section,setting){
  const compound=`${section.name}|${setting.key}`;
  const ordinary=(setting.help||"").trim()||schemaMap("help")[compound]||settingPatternHelp(section.name,setting.key)||"";
  const boundary=settingConstBoundary(section.name,setting.key);
  if(!ordinary&&!boundary)return "";
  // Bounds and units are already printed by the property control/metadata. Only
  // lifecycle consequences belong here in addition to authored behavior help.
  return [ordinary,boundary?`Changing this setting requires: ${boundary}`:""].filter(Boolean).join(" ");
}

function settingUnit(section,key){
  const compound=`${section}|${key}`;
  const authored=schemaMap("units")[compound];
  if(typeof authored==="string")return authored;
  if(compound==="Campsites|Key")return "VK code";
  if(/Ms$/.test(key))return "ms";
  if(/Hours$/.test(key))return "hours";
  if(/Seconds$/.test(key))return "seconds";
  if(/MetersPerSecond$/.test(key))return "m/s";
  if(/PerSecond$/.test(key)||/Rate$/.test(key))return "points/s";
  if(/Meters$/.test(key)||/Range$/.test(key)||key==="ClearRadius")return "m";
  if(/Degrees/.test(key)||/AngleDeg$/.test(key))return "degrees";
  if(/Percent$/.test(key))return "%";
  if(/Dollars$/.test(key))return "dollars";
  if(/Cents$/.test(key))return "cents";
  if(/Multiplier$/.test(key)||/Scale$/.test(key))return "x";
  if(/Chance$/.test(key)||/(Alpha|Deadzone|Extent|ScreenRadius|Yellowness)$/.test(key))return "fraction";
  if(/Hour$/.test(key))return "clock hour";
  if(key==="MinimumSpeed")return "m/s";
  if(/Speed$/.test(key))return "/s";
  if(/(MaximumWorldCasings|MaxTags)$/.test(key))return "items";
  if(/HealthPerLayer$/.test(key))return "HP";
  if(/(Cap|Pistol|Revolver|Repeater|Rifle|Shotgun|Arrow|Varmint|Herbs|Food)$/.test(key))return "items";
  if(/(Mode|Style)$/.test(key))return "mode";
  if(/Sign$/.test(key))return "sign";
  if(/^(EquipP3|EquipP4|EquipP5)$/.test(key))return "flag";
  if(key==="ZoomLevel")return "zoom units";
  if(key==="GlobalFirearmSpeed")return "game speed";
  return "game units";
}
function decimalSettingValue(value){
  return String(value).trim()!==""&&/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/i.test(String(value).trim());
}

function renderSettingField(section,setting){
  const compound=`${section.name}|${setting.key}`,current=state.settingEdits[compound]??setting.value;
  const label=settingLabel(section.name,setting.key),dev=settingIsDeveloper(section.name,setting.key);
  const constBoundary=settingConstBoundary(section.name,setting.key);
  const changeValue=value=>{if(value===setting.value)delete state.settingEdits[compound];else state.settingEdits[compound]=value;refreshGlobalSave();};
  const choices=settingChoices(section.name,setting.key);
  let control;
  if(settingIsBoolean(section.name,setting.key)){
    // Matches the runtime's own test: GetPrivateProfileIntA(...) != 0.
    const on=Number.parseInt(String(current).trim(),10)!==0&&String(current).trim()!=="";
    control=el("input",{type:"checkbox","aria-label":label,...(on?{checked:true}:{}),
      onchange:ev=>changeValue(ev.target.checked?"1":"0")});
  }else if(choices){
    // Never silently rewrite a value the schema does not list: an unrecognised
    // current value is offered back as its own option.
    const options=choices.some(([value])=>value===String(current))?choices:[[String(current),`${current} (current value)`],...choices];
    const select=el("select",{"aria-label":label,onchange:ev=>{changeValue(ev.target.value);ev.target.classList.toggle("edited",compound in state.settingEdits);}},
      ...options.map(([value,text])=>el("option",{value,...(value===String(current)?{selected:true}:{})},text)));
    control=el("span",{class:"setting-value"},select);
  }else{
    const numeric=decimalSettingValue(current);
    const range=settingRange(section.name,setting.key);
    const commit=ev=>{
      let value=ev.target.value;
      if(range&&decimalSettingValue(value)){
        let number=Number(value);
        if(Number.isFinite(Number(range.min)))number=Math.max(Number(range.min),number);
        if(Number.isFinite(Number(range.max)))number=Math.min(Number(range.max),number);
        value=String(number);ev.target.value=value;
      }
      changeValue(value);ev.target.classList.toggle("edited",compound in state.settingEdits);
    };
    const input=el("input",{type:numeric?"number":"text",...(numeric?{step:range?.step??"any"}:{}),
      ...(range&&range.min!==undefined?{min:range.min}:{}),...(range&&range.max!==undefined?{max:range.max}:{}),
      value:current,"aria-label":label,
      ...(compound==="Campsites|Key"?{inputmode:"text"}:{}),
      onchange:commit});
    const unit=numeric||compound==="Campsites|Key"?settingUnit(section.name,setting.key):"";
    control=el("span",{class:"setting-value"},input,...(unit?[el("span",{class:"setting-unit"},unit)]:[]));
  }
  const help=settingHelp(section,setting);
  return el("div",{"data-setting-section":section.name,class:["settings-field",dev?"dev":"",constBoundary?"const":""].filter(Boolean).join(" ")},
    el("div",{class:"settings-field-label"},
      el("span",{class:"settings-field-name"},label,
        dev?el("span",{class:"setting-dev-chip",title:"Developer setting: the runtime gates it behind developer mode, or the INI documents it as a probe/trace."},"DEV"):"",
        constBoundary?el("span",{class:"setting-const-chip",title:`Constant setting. ${constBoundary}`},"CONST"):"",
        help?fieldHelp(help):""),
      el("span",{class:"setting-source"},`${section.name} / ${setting.key}`)),
    el("div",{class:"settings-field-control"},control));
}

function refreshSettingAvailability(){
  const switches=new Map((state.settings?.sections||[]).map(section=>{
    const enabled=section.settings.find(setting=>setting.key==="Enabled");
    return [section.name,!enabled||Number.parseInt(state.settingEdits[`${section.name}|Enabled`]??enabled.value,10)!==0];
  }));
  document.querySelectorAll("[data-setting-section]").forEach(row=>{
    const disabled=isRO()||switches.get(row.dataset.settingSection)===false;
    row.setAttribute("aria-disabled",String(disabled));
    row.style.opacity=disabled?".45":"";
    row.querySelectorAll("input,select,textarea,button").forEach(control=>control.disabled=disabled);
  });
}

function settingEnableControl({section,setting}){
  const compound=`${section.name}|${setting.key}`;
  const control=el("input",{type:"checkbox","aria-label":`Enable ${humanSettingName(section.name)}`,
    title:settingHelp(section,setting),style:"width:24px;height:24px;margin-left:auto;flex:none",
    checked:Number.parseInt(state.settingEdits[compound]??setting.value,10)!==0,disabled:isRO(),
    onchange:event=>{
      const value=event.target.checked?"1":"0";
      if(value===setting.value)delete state.settingEdits[compound];else state.settingEdits[compound]=value;
      refreshSettingAvailability();refreshGlobalSave();
    }});
  return control;
}

function renderSettingCategory(category){
  const masters=category.subs.flatMap(sub=>sub.entries).filter(({setting})=>setting.key==="Enabled");
  const heading=(tag,title,help,entries=[])=>el(tag,{},LexeditorUI.actionRow(
    el("span",{style:"flex:1"},title),help?fieldHelp(help):"",...entries.map(settingEnableControl)));
  const subs=el("div",{class:"settings-subs"});
  for(const sub of category.subs){
    const fields=el("div",{class:"settings-fields"});
    for(const {section,setting} of sub.entries){
      if(setting.key!=="Enabled")fields.append(renderSettingField(section,setting));
    }
    const switches=masters.length===1?[]:sub.entries.filter(({setting})=>setting.key==="Enabled");
    subs.append(el("div",{class:"settings-sub"},
      sub.title||switches.length?heading("h3",sub.title||humanSettingName(switches[0].section.name),sub.help,switches):"",fields));
  }
  return el("section",{class:"settings-section"},
    heading("h2",category.title,category.help,masters.length===1?masters:[]),subs);
}

// Resolve the schema against the INI that actually loaded. Sections and keys the
// schema names but the INI does not have are skipped silently; keys the INI has
// but the schema does not name fall through to their own category.
function buildSettingsCategories(){
  const schema=settingsSchema(),hidden=schemaMap("hidden"),used=new Set(Object.keys(hidden));
  const byName=new Map(state.settings.sections.map(section=>[section.name.toLowerCase(),section]));
  const take=(sectionName,key)=>{
    const section=byName.get(String(sectionName).toLowerCase());
    if(!section)return [];
    const wanted=key==="*"
      ?section.settings.filter(setting=>!used.has(`${section.name}|${setting.key}`))
      :section.settings.filter(setting=>setting.key.toLowerCase()===String(key).toLowerCase()&&!used.has(`${section.name}|${setting.key}`));
    for(const setting of wanted)used.add(`${section.name}|${setting.key}`);
    return wanted.map(setting=>({section,setting}));
  };
  const categories=[];
  for(const category of (Array.isArray(schema.categories)?schema.categories:[])){
    const subs=[];
    for(const sub of (category.subs||[])){
      const entries=[];
      for(const [sectionName,key] of (sub.entries||[]))entries.push(...take(sectionName,key));
      if(entries.length)subs.push({title:sub.title||"",help:sub.help||"",entries});
    }
    if(subs.length)categories.push({title:category.title,help:category.help||"",subs});
  }
  // Everything the schema did not claim keeps its own INI section, in INI order.
  for(const section of state.settings.sections){
    const entries=section.settings.filter(setting=>!used.has(`${section.name}|${setting.key}`))
      .map(setting=>({section,setting}));
    if(!entries.length)continue;
    for(const setting of entries)used.add(`${section.name}|${setting.key}`);
    categories.push({title:humanSettingName(section.name),help:section.help||"",
      subs:[{title:"",help:"",entries}]});
  }
  return categories.sort((a,b)=>a.title.localeCompare(b.title,undefined,{sensitivity:"base"}));
}

async function saveSettings(){
  const edits=Object.entries(state.settingEdits).map(([compound,value])=>{const cut=compound.indexOf("|");return {section:compound.slice(0,cut),key:compound.slice(cut+1),value};});
  if(!edits.length)return;
  const result=await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});
  for(const edit of edits){const section=state.settings.sections.find(s=>s.name===edit.section),setting=section?.settings.find(s=>s.key===edit.key);if(setting)setting.value=edit.value;}
  state.settingEdits={};toast(`Saved ${result.saved} GameplayTweaks setting${result.saved===1?"":"s"}`);renderSettings();
}

function discardSettings(){
  state.settingEdits={};toast("Restored the last saved GameplayTweaks settings");renderSettings();refreshGlobalSave();
}

async function renderSettings(){
  const current=renderScope("renderSettings");
  const tb=$("#toolbar");tb.innerHTML="";
  if(!state.settings)state.settings=await api("/api/settings");
  if(!current())return;
  // No per-tab save control here, deliberately: RDR2's settings are saved by
  // the one global save button along with everything else, so the editor has a
  // single place to press. A second save on this tab is what
  // verify_rdr2_tweaks_shared_save exists to prevent.
  const m=$("#main");m.querySelector(".settings-layout")?.__settingsColumnsObserver?.disconnect();m.innerHTML="";
  if(!state.settings.available){m.append(LexeditorUI.stack({fill:false,className:"lex-notice"},"GameplayTweaks.ini is not installed for this editor profile. Catalog, loot, crafting, and other data editing remain available."));installTabContext();return;}
  m.append(LexeditorUI.settingsColumns(buildSettingsCategories().filter(category=>category.subs.length).map(renderSettingCategory),{columnMajor:true,strictColumns:true}));
  refreshSettingAvailability();
  installTabContext();
}
