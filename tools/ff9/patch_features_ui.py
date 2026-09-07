from pathlib import Path

p = Path('games/ff9/editor.html')
s = p.read_text(encoding='utf-8')

s = s.replace(
'''const state={tab:"items",dashboard:null,dataMap:null,catalog:[],datasets:{},datasetChoice:{},activeSource:"mine",selected:{},query:{},page:{},pageSize:{},sort:{},mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1],busy:false,error:"",runtimeError:""};''',
'''const state={tab:"items",dashboard:null,dataMap:null,catalog:[],datasets:{},datasetChoice:{},activeSource:"mine",selected:{},query:{},page:{},pageSize:{},sort:{},mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1],busy:false,error:"",runtimeError:"",tweak:"memoria",features:null,savedFeatures:null,deployment:null};''')

s = s.replace(
'''function dirtyCount(){if(state.activeSource!=="mine")return 0;let count=0;for(const data of Object.values(state.datasets))if(data?.rows)for(const row of data.rows)count+=Object.keys(changedFields(data,row)).length;return count}''',
'''function featureChanges(){const current=state.features?.features||{},saved=state.savedFeatures?.features||{};return Object.fromEntries(Object.keys(current).filter(key=>current[key]!==saved[key]).map(key=>[key,current[key]]))}
  function dirtyCount(){if(state.activeSource!=="mine")return 0;let count=Object.keys(featureChanges()).length;for(const data of Object.values(state.datasets))if(data?.rows)for(const row of data.rows)count+=Object.keys(changedFields(data,row)).length;return count}''')

s = s.replace(
'''state.dashboard.runtime=await api("/api/runtime");
      state.dataMap=await api("/api/datamap");''',
'''state.dashboard.runtime=await api("/api/runtime");
      state.dataMap=await api("/api/datamap");
      state.deployment=await api("/api/deployment");''')
# The replacement above deliberately matches both legacy and integrated files.
# Collapse any repeated insertion so running this patcher twice is a no-op.
duplicate_deployment = '''state.dataMap=await api("/api/datamap");
      state.deployment=await api("/api/deployment");
      state.deployment=await api("/api/deployment");'''
single_deployment = '''state.dataMap=await api("/api/datamap");
      state.deployment=await api("/api/deployment");'''
while duplicate_deployment in s:
    s = s.replace(duplicate_deployment, single_deployment)

legacy = '''function tweaks(){
    setToolbar([subtabBar({tabs:[{id:"memoria",label:"Memoria"}],active:"memoria",label:"Tweaks",change:()=>{}})]);
    $("#main").replaceChildren(el("section",{class:"ff9-card"},el("h2",{},"Memoria"),el("p",{},"can't be bothered to make this when the memoria guys already did this themselves. just hit play and you can edit the settings in the launcher that comes up")));
  }'''
previous = '''function tweaks(){
    const tabs=[{id:"memoria",label:"Memoria"},{id:"improved",label:"Improved Interface"},{id:"eat",label:"Better Eat"}];
    setToolbar([subtabBar({tabs,active:state.tweak,label:"Tweaks",change:id=>{state.tweak=id;tweaks()}})]);
    if(state.tweak==="memoria"){
      $("#main").replaceChildren(el("section",{class:"ff9-card"},el("h2",{},"Memoria"),el("p",{},"can't be bothered to make this when the memoria guys already did this themselves. just hit play and you can edit the settings in the launcher that comes up")));
      return;
    }
    const key=state.tweak==="improved"?"ImprovedInterface":"BetterEat";
    const title=state.tweak==="improved"?"Improved Interface":"Better Eat";
    const description=state.tweak==="improved"?
      "Adds Circle reveal-only dialogue, Square fast-forward, snapshot-only dialogue history, full-width battle ATB/Trance with HP/MP bars, queued action drain, and an unbeaten Tetra Master opponent prompt. Keyboard equivalents follow your normal Memoria bindings.":
      "Disables useless Eat/Cook targets, refuses to consume enemies that cannot teach Quina anything, and gives enemies carrying an unlearned Blue Magic ability a blue glow.";
    const enabled=!!state.features?.features?.[key],deployed=state.deployment?.deployed;
    const toggle=el("label",{},el("input",{type:"checkbox",checked:enabled,disabled:state.busy||state.activeSource!=="mine",onchange:event=>{state.features.features[key]=event.target.checked;shell.refresh()}})," Enabled");
    const actions=el("div",{class:"ff9-runtime-actions"},
      el("button",{type:"button",disabled:state.busy||dirtyCount()>0||state.activeSource!=="mine",onclick:()=>deploymentAction("deploy")},deployed?"Redeploy Project":"Deploy Project"),
      el("button",{type:"button",disabled:state.busy||!deployed||state.activeSource!=="mine",onclick:()=>deploymentAction("revert")},"Revert Lexeditor Mod"));
    $("#main").replaceChildren(el("section",{class:"ff9-card"},el("h2",{},title),el("p",{},description),toggle,
      el("p",{class:"ff9-source"},deployed?(state.deployment.runtimeCurrent?"Deployed runtime is current.":"Deployed runtime needs redeployment."):"Save changes, then Deploy Project to activate them in Memoria."),actions));
  }
  async function deploymentAction(action){
    if(state.busy||state.activeSource!=="mine")return;
    if(dirtyCount()){state.runtimeError="Save your project changes before deployment.";await render();return}
    if(action==="revert"&&!window.confirm("Remove only the Lexeditor-owned FF9 Memoria mod folder and its FolderNames entry?"))return;
    state.busy=true;shell.refresh();
    try{state.deployment=await api(`/api/deployment/${action}`,{});state.dataMap=await api("/api/datamap");state.runtimeError=""}
    catch(error){state.runtimeError=error.message;throw error}
    finally{state.busy=false;await render()}
  }'''
updated = '''function tweaks(){
    const tabs=[{id:"memoria",label:"Memoria"},{id:"improved",label:"Improved Interface"},{id:"eat",label:"Better Eat"},{id:"xp",label:"XP Bars"},{id:"hpmp",label:"HP/MP Bars"}];
    setToolbar([subtabBar({tabs,active:state.tweak,label:"Tweaks",change:id=>{state.tweak=id;tweaks()}})]);
    if(state.tweak==="memoria"){
      $("#main").replaceChildren(el("section",{class:"ff9-card"},el("h2",{},"Memoria"),el("p",{},"can't be bothered to make this when the memoria guys already did this themselves. just hit play and you can edit the settings in the launcher that comes up")));
      return;
    }
    const defs={
      improved:{key:"ImprovedInterface",title:"Improved Interface",description:"Adds Circle reveal-only dialogue, Square fast-forward, snapshot-only dialogue history, full-width battle ATB/Trance with HP/MP bars, queued action drain, an unbeaten Tetra Master opponent prompt, and highlights Mognet when the current Moogle can receive one of your carried letters. Keyboard equivalents follow your normal Memoria bindings."},
      eat:{key:"BetterEat",title:"Better Eat",description:"Disables useless Eat/Cook targets, refuses to consume enemies that cannot teach Quina anything, and gives enemies carrying an unlearned Blue Magic ability a blue glow."},
      xp:{key:"XPBars",title:"XP Bars",description:"Adds an experience-progress bar under each party member's block on the post-battle EXP screen."},
      hpmp:{key:"HPMPBars",title:"HP/MP Bars",description:"Adds a red HP bar and blue MP bar directly below each party member's HP and MP text in battle."}
    };
    const def=defs[state.tweak]||defs.improved,key=def.key,title=def.title,description=def.description;
    const enabled=!!state.features?.features?.[key],deployed=state.deployment?.deployed;
    const toggle=el("label",{},el("input",{type:"checkbox",checked:enabled,disabled:state.busy||state.activeSource!=="mine",onchange:event=>{state.features.features[key]=event.target.checked;shell.refresh()}})," Enabled");
    const actions=el("div",{class:"ff9-runtime-actions"},
      el("button",{type:"button",disabled:state.busy||dirtyCount()>0||state.activeSource!=="mine",onclick:()=>deploymentAction("deploy")},deployed?"Redeploy Project":"Deploy Project"),
      el("button",{type:"button",disabled:state.busy||!deployed||state.activeSource!=="mine",onclick:()=>deploymentAction("revert")},"Revert Lexeditor Mod"));
    $("#main").replaceChildren(el("section",{class:"ff9-card"},el("h2",{},title),el("p",{},description),toggle,
      el("p",{class:"ff9-source"},deployed?(state.deployment.runtimeCurrent?"Deployed runtime is current.":"Deployed runtime needs redeployment."):"Save changes, then Deploy Project to activate them in Memoria."),actions));
  }
  async function deploymentAction(action){
    if(state.busy||state.activeSource!=="mine")return;
    if(dirtyCount()){state.runtimeError="Save your project changes before deployment.";await render();return}
    if(action==="revert"&&!window.confirm("Remove only the Lexeditor-owned FF9 Memoria mod folder and its FolderNames entry?"))return;
    state.busy=true;shell.refresh();
    try{state.deployment=await api(`/api/deployment/${action}`,{});state.dataMap=await api("/api/datamap");state.runtimeError=""}
    catch(error){state.runtimeError=error.message;throw error}
    finally{state.busy=false;await render()}
  }'''
if previous in s:
    s = s.replace(previous, updated)
elif legacy in s:
    s = s.replace(legacy, updated)
elif updated not in s:
    raise SystemExit('tweaks block not found and integrated block not present')

s = s.replace(
'''async function save(){if(state.busy)return;state.busy=true;shell.refresh();try{for(const [key,data] of Object.entries(state.datasets)){if(!data?.rows)continue;const changes=data.rows.map(row=>({line:row.line,scene:row.scene,record:row.record,values:changedFields(data,row)})).filter(change=>Object.keys(change.values).length);if(changes.length)installData(await api("/api/save",{key,sha256:data.sha256,sceneHashes:data.sceneHashes||{},changes}))}state.error=""}catch(error){state.error=error.message;throw error}finally{state.busy=false;render()}}''',
'''async function save(){if(state.busy)return;state.busy=true;shell.refresh();try{for(const [key,data] of Object.entries(state.datasets)){if(!data?.rows)continue;const changes=data.rows.map(row=>({line:row.line,scene:row.scene,record:row.record,values:changedFields(data,row)})).filter(change=>Object.keys(change.values).length);if(changes.length)installData(await api("/api/save",{key,sha256:data.sha256,sceneHashes:data.sceneHashes||{},changes}))}if(Object.keys(featureChanges()).length){state.features=await api("/api/features/save",{sha256:state.savedFeatures.sha256,features:state.features.features});state.savedFeatures=clone(state.features)}state.error=""}catch(error){state.error=error.message;throw error}finally{state.busy=false;render()}}''')

s = s.replace(
'''async function discard(){for(const key of Object.keys(state.datasets))await loadDataset(key,true);render()}''',
'''async function discard(){for(const key of Object.keys(state.datasets))await loadDataset(key,true);state.features=await api("/api/features");state.savedFeatures=clone(state.features);state.deployment=await api("/api/deployment");render()}''')

s = s.replace(
'''Promise.all([api("/api/dashboard"),api("/api/datamap"),api("/api/catalog")]).then(([dashboard,map,catalog])=>{state.dashboard=dashboard;state.dataMap=map;state.catalog=catalog.datasets;render().then(()=>LexeditorUI.finishPluginLoading())})''',
'''Promise.all([api("/api/dashboard"),api("/api/datamap"),api("/api/catalog"),api("/api/features"),api("/api/deployment")]).then(([dashboard,map,catalog,features,deployment])=>{state.dashboard=dashboard;state.dataMap=map;state.catalog=catalog.datasets;state.features=features;state.savedFeatures=clone(features);state.deployment=deployment;render().then(()=>LexeditorUI.finishPluginLoading())})''')

p.write_text(s, encoding='utf-8')
