from pathlib import Path
root=Path.cwd()
p=root/'games/rdr/editor.html'
s=p.read_text()
start=s.index('  function shopValue(')
end=s.index('  function selectShopItem',start)
s=s[:start]+'''  function shopBaseline(item,field){
    const value=item[field.key];
    if(field.key!=="priceModifier"||!Number.isFinite(value))return String(value);
    // Show the shortest decimal which represents the stored float32 value.
    for(let digits=1;digits<=9;digits++){const text=String(Number(value.toPrecision(digits)));if(Math.fround(Number(text))===value)return text;}
    return String(value);
  }
  function shopValue(item,field){const key=`${item.id}|${field.field}`;return Object.prototype.hasOwnProperty.call(state.shopEdits,key)?state.shopEdits[key]:shopBaseline(item,field);}
  function editShop(item,field,value){const key=`${item.id}|${field.field}`;if(value===shopBaseline(item,field))delete state.shopEdits[key];else state.shopEdits[key]=value;shell.refresh();}
''' + s[end:]
s=s.replace('''    const edits=Object.entries(state.settingEdits).map(([identity,value])=>''','''    validateSettings();
    const edits=Object.entries(state.settingEdits).map(([identity,value])=>''',1)
s=s.replace('setStatus("Saved LexerRDR.ini settings")','setStatus("Saved LexerRDR.ini in the workspace; runtime loading is not verified")')
s=s.replace('parent[key]=step==="1"?Number.parseInt(event.target.value,10):Number(event.target.value);','parent[key]=event.target.value.trim()===""?"":Number(event.target.value);')
s=s.replace('entry.quantity=Number.parseInt(event.target.value,10);','entry.quantity=event.target.value.trim()===""?"":Number(event.target.value);')
s=s.replace('entry.weight=Number.parseInt(event.target.value,10);','entry.weight=event.target.value.trim()===""?"":Number(event.target.value);')
s=s.replace('doc.source.archive','doc.source?.archive||"Not supplied"').replace('doc.source.script','doc.source?.script||"Not supplied"').replace('doc.source.functions.map','(doc.source?.functions||[]).map')
needle='  async function saveAll(){'
validation='''  function numberEdit(raw,label,{minimum,maximum,step}={}){
    if(raw===null||typeof raw==="boolean"||String(raw).trim()==="")throw new Error(`${label} needs a number`);
    const value=Number(raw);
    if(!Number.isFinite(value)||(Number(step)===1&&!Number.isInteger(value)))throw new Error(`${label} needs a finite ${Number(step)===1?"integer":"number"}`);
    if(minimum!==undefined&&value<Number(minimum)||maximum!==undefined&&value>Number(maximum))throw new Error(`${label} is outside its allowed range`);
    return value;
  }
  function validateSettings(){
    for(const [identity,value] of Object.entries(state.settingEdits)){
      const [section,key]=identity.split("\\u0000"),setting=state.settings?.sections?.find(row=>row.name===section)?.settings.find(row=>row.key===key);
      if(!setting)throw new Error(`Setting ${section}/${key} is no longer loaded`);
      if(setting.control==="number")numberEdit(value,`${section}/${key}`,setting);
      if(setting.control==="checkbox"&&!["true","false"].includes(String(value).toLowerCase()))throw new Error(`${key} must be true or false`);
    }
  }
  function validatePendingEdits(){
    for(const [identity,value] of Object.entries(state.itemEdits)){
      const split=identity.lastIndexOf("|"),item=state.items?.rows.find(row=>row.id===identity.slice(0,split)),field=item?.fields.find(row=>row.field===identity.slice(split+1));
      if(!field)throw new Error(`Item field ${identity} is no longer loaded`);
      if(field.control==="number")numberEdit(value,`${item.name} ${field.field}`,field);
      if(field.control==="select"&&!field.options.includes(value))throw new Error(`${field.field} needs a known choice`);
    }
    for(const [identity,value] of Object.entries(state.shopEdits)){
      const split=identity.lastIndexOf("|"),field=SHOP_FIELDS.find(row=>row.field===identity.slice(split+1));
      if(!field)throw new Error(`Shop field ${identity} is no longer loaded`);
      numberEdit(value,field.label,{minimum:field.min,maximum:field.max,step:field.step});
    }
    for(const [identity,value] of Object.entries(state.missionEdits)){
      const kind=identity.slice(identity.lastIndexOf("|")+1);
      numberEdit(value,`Mission ${identity}`,{...state.missions.limits.rewards[kind],step:1});
    }
    validateSettings();
    if(state.lootDirty){
      const bonus=state.lootDocument.corpseBonusItem,range=state.lootDocument.money.baseRoll.range;
      numberEdit(bonus.chancePercent,"Bonus chance",{minimum:0,maximum:100,step:1});
      for(const entry of bonus.entries)for(const key of ["quantity","weight"])numberEdit(entry[key],`Item ${entry.itemEnum} ${key}`,{minimum:0,maximum:100000,step:1});
      const minimum=numberEdit(range.minimum,"Money minimum",{minimum:0,maximum:100000}),maximum=numberEdit(range.maximum,"Money maximum",{minimum:0,maximum:100000});
      if(minimum>maximum)throw new Error("Money minimum must not exceed maximum");
    }
  }

'''
assert needle in s
s=s.replace(needle,validation+needle,1)
s=s.replace('''    if(!dirtyCount())return;
    try{
      const saved=[];''','''    if(!dirtyCount()||state.activeSource!=="mine")return;
    try{
      validatePendingEdits();
      const saved=[];''',1)
s=s.replace('''const raw=missionValue(mission,reward.key),value=Number(raw);''','''const raw=missionValue(mission,reward.key),value=numberEdit(raw,`${mission.name} ${reward.label}`,{...state.missions.limits.rewards[reward.key],step:1});''')
s=s.replace('''setStatus(`Saved ${saved.join(", ")}`)''','''setStatus(`Saved to workspace: ${saved.join(", ")}. In-game deployment is not verified.`)''')
s=s.replace('''state.settingEdits={};state.lootDirty=false;if(next==="vanilla")''','''state.settingEdits={};state.lootDocument=clone(state.loot?.document);state.lootDirty=false;if(next==="vanilla")''',1)
s=s.replace('''  async function boot(){''','''  async function optionalRuntime(path){
    try{return await api(path);}catch(error){return {available:false,file:path,sections:[],reason:error.message};}
  }
  async function boot(){''',1)
s=s.replace('''api("/api/settings"),api("/api/loot")''','''optionalRuntime("/api/settings"),optionalRuntime("/api/loot")''')
s=s.replace('''el("p",{},"Create the project settings file before editing runtime values.")''','''el("p",{},state.settings?.reason||"The runtime settings file must be present before its values can be edited.")''')
s=s.replace('''    $("#main").replaceChildren(el("div",{class:"cards"},statusCard,redHookCard));shell.refresh();''','''    const deliveryCard=el("section",{class:"card"},el("h2",{},"Saved files and game delivery"),
      el("p",{},"Save updates the workspace only. It does not install XML/WGD overrides or prove that LexerRDR.asi loaded a changed INI/JSON file."),
      el("p",{},"Game deployment is not verified. Do not overwrite installed archives. The native runtime and its loader must be checked before an in-game test."),
      ...Object.entries(state.dashboard.paths).filter(([name])=>["Editable overrides","Inventory overrides","Shop overrides","Settings","Loot ASI override","Mission ASI override"].includes(name)).map(([name,path])=>el("div",{class:"path-row"},el("b",{},name),el("code",{title:path},path))));
    $("#main").replaceChildren(el("div",{class:"cards"},statusCard,redHookCard,deliveryCard));shell.refresh();''',1)
p.write_text(s)
p=root/'games/rdr/server.py'
s=p.read_text().replace('''            "Inventory overrides": str(CONTENT_OVERRIDE_ROOT),''','''            "Inventory overrides": str(CONTENT_OVERRIDE_ROOT),
            "Shop overrides": str(GRINGO_OVERRIDE_ROOT),
            "Mission ASI override": str(mission_rewards.OVERRIDE_FILE),''',1)
p.write_text(s)
p=root/'games/rdr/plugin.py'
s=p.read_text()
s=s.replace('''        loot_document = json.loads((PROJECT_ROOT / "LexerRDR.loot.json").read_text(encoding="utf-8"))''','''        # Synthetic contract values, never the user's private runtime configuration.
        from tools.rdr_test_support import loot_document as synthetic_loot_document
        loot_document = synthetic_loot_document()''')
s=s.replace('''                source["file"]: hashlib.sha256(Path(source["file"]).read_bytes()).hexdigest()
                for source in missions.get("sources", [])''','''                str(PLUGIN_ROOT / "missions.generated.json"):
                hashlib.sha256((PLUGIN_ROOT / "missions.generated.json").read_bytes()).hexdigest()''')
s=s.replace('RDR Missions save changed a read-only decompiled source','RDR Missions save changed the read-only generated reward table')
p.write_text(s)
