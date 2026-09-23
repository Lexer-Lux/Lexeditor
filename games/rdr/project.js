"use strict";
  function renderProject(){
    // No "read only" banner. Every read-only value already carries the shared
    // lock mark, so the banner restated in words what the controls show.
    $("#toolbar").replaceChildren();
    const {detailSection,detailText,notice,actionRow}=LexeditorUI;
    const status=(tone,message)=>notice({tone,message});
    const button=(label,onclick,disabled,primary)=>el("button",{type:"button",class:primary?"primary":null,onclick,disabled},label);
    const sources=state.dashboard.manifest?.sources||{};
    const preparation=detailSection({title:"PREPARATION",body:[
      ...(state.dashboard.problems.length?state.dashboard.problems.map(problem=>status("warning",problem))
        :[status("success",`${state.files.counts.all||0} tuning files, ${state.items?.counts?.all||0} items, and ${state.shops?.counts?.items||0} shop entries prepared. Installed archives are read-only.`)]),
      LexeditorUI.logView(Object.keys(sources).length?`${Object.entries(sources).map(([label,source])=>`${label}: ${source.path}\nSHA-256: ${source.sha256}`).join("\n\n")}\n\nPrepared: ${state.dashboard.manifest.preparedAt}\nInventory files: ${state.dashboard.manifest.fileCounts?.inventory||0}\nShop dictionaries: ${state.dashboard.manifest.fileCounts?.gringoUnpacked||0}`:"Preparation manifest is not available.")]});
    const redHook=state.dashboard.redHook;
    const intro=redHook.skipIntroLogos;
    const redHookSection=detailSection({title:"REDHOOK",body:[
      redHook.installed?status("success","RedHook is installed."):status("warning",`RedHook is required. Missing: ${redHook.missing.join(", ")}.`),
      redHook.installed?(intro.enabled?status("success","Startup logo movies are disabled."):status("warning",intro.problem||"Startup logo skipping is not enabled.")):null,
      fact("Game root",redHook.gameRoot),
      !redHook.installed?actionRow(button("Open official RedHook page",()=>openRedHook(),false,true)):null]});
    const deployment=state.dashboard.deployment||{rows:[],pending:false,active:false};
    const deploymentRows=(deployment.rows||[]).filter(row=>row.overrideCount||row.targetExists).map(row=>
      fact(`${row.name}: ${row.overrideCount} override${row.overrideCount===1?"":"s"}`,
        row.changedSinceDeploy?"changed outside Lexeditor — deployment locked":row.deployed?"deployed and current":row.overrideCount?"saved; deployment needed":"not deployed"));
    const shopTest=state.dashboard.shopTest||{available:false,reason:"No shop test candidate is available."};
    const shopTestSection=detailSection({title:"SHOP EDIT TEST",body:!shopTest.available?[status("warning",shopTest.reason)]:[
      detailText("Lexeditor selected one stable prepared record so the in-game check does not require you to invent a shop, item, or value."),
      fact("Shop",shopTest.shop),
      fact("Item",shopTest.item),
      fact("Price multiplier",`vanilla ${shopTest.baselinePriceModifier} · current ${shopTest.currentPriceModifier} · test ${shopTest.testPriceModifier}`),
      shopTest.status==="staged"?status("success","Test value is staged. Deploy Project before launching RDR1.")
        :shopTest.status==="custom"?status("warning","This candidate already has a different custom price; the test helper will not overwrite it.")
        :status(null,"Candidate is at its vanilla price and ready to stage."),
      detailText(shopTest.instruction),
      actionRow(
        button("Stage Shop Test",()=>stageShopTest(),!shopTest.stageAllowed||shopTest.status==="staged",true),
        button("Restore Shop Test",()=>restoreShopTest(),!shopTest.restoreAllowed||shopTest.status!=="staged"),
        button("Open in Shops",()=>openShopTest(),!shopTest.available))]});
    const missionTest=state.dashboard.missionTest||{available:false,problem:"Mission reward test is unavailable."};
    const missionTestSection=detailSection({title:"MISSION REWARD TEST",body:!missionTest.available?[status("warning",missionTest.problem)]:[
      detailText("Lexeditor uses a fixed early Story mission and preserves the exact mission-2 override that existed before staging."),
      fact("Mission",`${missionTest.storyTitle} · ${missionTest.mission} · ID ${missionTest.missionId}`),
      fact("Vanilla rewards",`cash ${missionTest.vanillaRewards.cash} · fame ${missionTest.vanillaRewards.fame} · honor ${missionTest.vanillaRewards.honor}`),
      fact("Test rewards",`cash ${missionTest.testRewards.cash} · fame ${missionTest.testRewards.fame} · honor ${missionTest.testRewards.honor}`),
      missionTest.status==="staged"?status("success","Mission test is staged in LexerRDR.missions.json.")
        :status(null,missionTest.status==="custom"?"A pre-existing mission-2 override exists; Stage will snapshot it and Restore will put it back exactly.":"Mission 2 is at vanilla override state and ready to stage."),
      detailText(missionTest.route),detailText(missionTest.expected),detailText(missionTest.instruction),
      actionRow(
        button("Stage Mission Test",()=>stageMissionTest(),!missionTest.stageAllowed,true),
        button("Restore Mission Test",()=>restoreMissionTest(),!missionTest.restoreAllowed),
        button("Open in Missions",()=>openMissionTest(),false))]});
    const deliverySection=detailSection({title:"SAVED FILES AND GAME DELIVERY",body:[
      detailText("Save writes the project workspace. Deploy Project rebuilds verified copies of only the affected RPF archives and installs those copies under the loader's update\\game folder. The original game\\*.rpf archives are never overwritten."),
      detailText("LexerRDR.ini, loot JSON and mission JSON are consumed by the native runtime from this workspace; archive-backed XML/WGD edits use the update-folder copies below."),
      deployment.pending?status("warning","Saved archive edits are newer than the current deployment.")
        :deployment.active?status("success","Archive deployment matches the saved project.")
        :status(null,"No Lexeditor archive-copy deployment is active."),
      actionRow(
        button(deployment.active?"Redeploy Project":"Deploy Project",()=>deployProject(),!deployment.pending,true),
        button("Revert Deployment",()=>revertProject(),!deployment.active)),
      fact("Update-folder target",deployment.updateRoot||"Unavailable"),
      ...deploymentRows,
      ...Object.entries(state.dashboard.paths).filter(([name])=>["Editable overrides","Inventory overrides","Shop overrides","Settings","Loot ASI override","Mission ASI override"].includes(name)).map(([name,path])=>fact(name,path))]});
    $("#main").replaceChildren(LexeditorUI.detailPanel({className:"lex-information-panel",icon:LexeditorUI.infoIcon(),title:"Information",meta:"Preparation, RedHook, in-game tests and deployment",body:[
      preparation,redHookSection,shopTestSection,missionTestSection,deliverySection,
      LexeditorUI.modLoaderSection({
        loader:"RedHook, the community runtime for the PC release. It loads the plugin's overrides when the game starts.",
        output:"Edits are written as Git-backed override files in the project folder, which RedHook reads over the stock data.",
        order:"RedHook applies overrides after the base data. Two mods overriding the same file conflict; the later one wins.",
        safety:"Installed game source data is read only. Every edit is stored as a separate override rather than a rewrite.",
        removal:"Remove the override files, or uninstall RedHook to return the game to stock.",
      })]}));shell.refresh();
  }
  async function openRedHook(){try{await api("/api/redhook/open",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});setStatus("Opened the official RedHook page");}catch(error){setStatus(`Could not open RedHook: ${error.message}`);showAlert({title:"Could not open RedHook",message:String(error.message||error)});}}
  async function configureRedHook(){await api("/api/redhook/configure",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");}
  async function stageShopTest(){
    try{setStatus("Staging deterministic shop price test…");const result=await api("/api/shop-test/stage",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.shops=await api("/api/shops");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Shop test staged");renderProject();}
    catch(error){setStatus("Shop test staging failed");showAlert({title:"Shop test staging failed",items:[{item:"Price test",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  async function restoreShopTest(){
    try{setStatus("Restoring deterministic shop test price…");const result=await api("/api/shop-test/restore",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.shops=await api("/api/shops");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Shop test restored");renderProject();}
    catch(error){setStatus("Shop test restore failed");showAlert({title:"Shop test restore failed",items:[{item:"Price test",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  function openShopTest(){const test=state.dashboard.shopTest;if(!test?.available)return;state.shopQuery=test.item;state.shopName=test.shop;state.shopCategory="";state.shopSelected=test.id;navigate("shops");}
  async function stageMissionTest(){
    try{setStatus("Staging deterministic mission reward test…");const result=await api("/api/mission-test/stage",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.missions=await api("/api/missions");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Mission test staged");renderProject();}
    catch(error){setStatus("Mission test staging failed");showAlert({title:"Mission test staging failed",items:[{item:"Mission 2",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  async function restoreMissionTest(){
    try{setStatus("Restoring pre-test mission reward state…");const result=await api("/api/mission-test/restore",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.missions=await api("/api/missions");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Mission test restored");renderProject();}
    catch(error){setStatus("Mission test restore failed");showAlert({title:"Mission test restore failed",items:[{item:"Mission 2",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  function openMissionTest(){const test=state.dashboard.missionTest;if(!test?.missionId)return;state.missionQuery=test.mission;state.missionRegion="";state.missionSelected=test.missionId;navigate("missions");}
  async function deployProject(){
    try{setStatus("Building verified RPF copies…");const result=await api("/api/deployment/deploy",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");setStatus(result.message||"Project archive copies deployed");renderProject();}
    catch(error){setStatus("Deployment failed");showAlert({title:"Deployment failed",items:[{item:"Archive copies",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  async function revertProject(){
    try{setStatus("Reverting Lexeditor archive copies…");const result=await api("/api/deployment/revert",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");setStatus(result.message||"Archive deployment reverted");renderProject();}
    catch(error){setStatus("Revert failed");showAlert({title:"Revert failed",items:[{item:"Archive copies",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  function renderRedHookNotice(){
    const redHook=state.dashboard?.redHook;
    if(!redHook||redHook.installed||state.redHookNoticeShown)return;
    state.redHookNoticeShown=true;
    LexeditorUI.confirmAction({title:"RedHook is required",
      message:`Install the official RedHook files before you use LexerRDR in the game.\n\nMissing: ${redHook.missing.join(", ")}`,
      cancelLabel:"Keep editing",confirmLabel:"Open official download"}).then(open=>{if(open)openRedHook();});
  }

  function numberEdit(raw,label,{minimum,maximum,step}={}){
    if(raw===null||typeof raw==="boolean"||String(raw).trim()==="")throw new Error(`${label} needs a number`);
    const value=Number(raw);
    if(!Number.isFinite(value)||(Number(step)===1&&!Number.isInteger(value)))throw new Error(`${label} needs a finite ${Number(step)===1?"integer":"number"}`);
    if(minimum!==undefined&&value<Number(minimum)||maximum!==undefined&&value>Number(maximum))throw new Error(`${label} is outside its allowed range`);
    return value;
  }
  function validateSettings(){
    for(const [identity,value] of Object.entries(state.settingEdits)){
      const [section,key]=identity.split("\u0000"),setting=state.settings?.sections?.find(row=>row.name===section)?.settings.find(row=>row.key===key);
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
