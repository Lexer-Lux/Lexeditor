  "use strict";
  const {el,columnList,columnPreferences,detailPanel,detailField,readonlyField,infoHelp,detailSection,clone,recordId,pagedListDetail,panelLayout,infoIcon}=LexeditorUI;
  const PLUGIN="ff7r2";
  let tab="characters";
  // Which presentation tool the Tweaks page shows. One level of subtabs only.
  let tweakTab="reshade";
  let game={found:false,root:"",renderer:"dxgi",binaries:""};
  let reshade={available:false,effects:[]};
  let injector=null, injectorDraft=null, injectorBusy=false;
  let packageBusy=false;
  // What the Data Map shows and where the reader has got to in it.
  const state={dataMap:{rows:[]},mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1]};

  async function loadGame(){
    try{const response=await fetch("/api/game");if(response.ok)game=await response.json()}
    catch(_error){/* the browser preview has no service; the page still renders */}
  }
  async function loadReshade(){
    try{reshade=await LexeditorUI.callWindow?.("mod_reshade",PLUGIN)||reshade}
    catch(_error){/* the browser preview has no desktop host */}
  }
  // Every ReShade change answers with the game's fresh ReShade state.
  async function actReshade(method,...args){
    try{
      const value=await LexeditorUI.callWindow?.(method,PLUGIN,...args);
      if(value&&value.effects)reshade=value;else await loadReshade();
    }catch(error){LexeditorUI.showToast?.(error.message||String(error),true);}
    render();
  }

  // ---- Shader Injector ------------------------------------------------------
  function acceptInjector(state){
    injector=state;
    injectorDraft=state?.settings?clone(state.settings.values):null;
  }
  async function loadInjector(){
    try{
      const response=await fetch("/api/shader-injector");
      const value=await response.json();
      if(!response.ok)throw new Error(value.error||"Could not read Shader Injector");
      acceptInjector(value);
    }catch(error){injector={available:false,reason:error.message||String(error)};injectorDraft=null}
  }
  async function injectorAction(route,body,done){
    if(injectorBusy)return;
    injectorBusy=true;render();
    try{
      const response=await fetch(`/api/shader-injector/${route}`,{method:"POST",
        headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});
      const value=await response.json();
      if(!response.ok)throw new Error(value.error||"Shader Injector refused that");
      acceptInjector(value.status);
      if(done)LexeditorUI.showToast?.(typeof done==="function"?done(value.result):done);
    }catch(error){LexeditorUI.showToast?.(error.message||String(error),true)}
    finally{injectorBusy=false;render()}
  }

  function megabytes(bytes){return `${(Number(bytes||0)/1048576).toLocaleString(undefined,{maximumFractionDigits:0})} MB`}

  async function clearShaderCache(){
    const cache=injector?.shaderCache||{files:[],bytes:0,folder:""};
    if(!cache.files.length)return;
    const ok=await LexeditorUI.confirmAction({title:"Clear the shader cache?",
      message:`Deletes ${cache.files.length} cache file${cache.files.length===1?"":"s"} (${megabytes(cache.bytes)}) from\n${cache.folder}\n\nThe game rebuilds it on the next start. Close the game first.`,
      confirmLabel:"Clear cache"});
    if(ok)injectorAction("clear-cache",{},result=>result.failed.length
      ?`Could not delete ${result.failed.length}: ${result.failed[0].error}`
      :`Cleared ${result.removed.length} cache file${result.removed.length===1?"":"s"}.`);
  }

  function injectorStatusCard(){
    const state=injector||{available:false,reason:"Reading Shader Injector…"};
    if(!state.available){
      return LexeditorUI.detailPanel({title:"SHADER INJECTOR",body:[
        detailSection({title:"INSTALLATION",body:[
          detailField({label:"STATUS",control:readonlyField(state.reason||"Unavailable.")}),
        ]}),
      ]});
    }
    const status=state.foreignDll
      ? "Not installed. dsound.dll here belongs to something else, and Lexeditor will not replace it."
      : state.installed
        ? (state.enabled?"Installed and loading with the game.":"Installed, switched off. The game will not load it.")
        : "Not installed.";
    const actions=el("div",{class:"lex-reshade-actions"});
    if(!state.installed&&!state.foreignDll){
      actions.append(el("button",{type:"button",class:"lex-dialog-action primary",disabled:injectorBusy,
        onclick:()=>injectorAction("install",{},`Shader Injector ${state.version} installed.`)},
        `Install Shader Injector ${state.version}`));
    }
    if(state.installed&&state.missingFiles.length){
      actions.append(el("button",{type:"button",class:"lex-dialog-action primary",disabled:injectorBusy,
        onclick:()=>injectorAction("install",{},"Missing files restored.")},"Restore missing files"));
    }
    if(state.installed){
      actions.append(el("button",{type:"button",class:"lex-dialog-action",disabled:injectorBusy,
        onclick:async()=>{
          const edited=state.modifiedFiles.length;
          const ok=await LexeditorUI.confirmAction({title:"Remove Shader Injector?",
            message:`This removes dsound.dll and the files the ${state.version} release put in ShaderInjector.`+
              (edited?`\n\n${edited} file${edited===1?"":"s"} you edited will be kept.`:""),
            confirmLabel:"Remove"});
          if(ok)injectorAction("uninstall",{},result=>`Removed ${result.removed.length} files.`+
            (result.kept.length?` Kept ${result.kept.length} you edited.`:""));
        }},"Remove from this game"));
    }
    const load=el("input",{type:"checkbox",checked:state.enabled,disabled:!state.installed||injectorBusy,
      "aria-label":"Load Shader Injector with the game",
      onchange:event=>injectorAction("enabled",{enabled:event.target.checked},
        event.target.checked?"Shader Injector will load with the game.":"Shader Injector switched off.")});
    const rows=[
      detailField({label:"RELEASE",control:readonlyField(`${state.version}, ${state.variant} preset, by ${state.author} (MIT)`),
        help:infoHelp(`Upstream's release archive ships inside Lexeditor and is only installed if it hashes to the published asset. Source: ${state.source}`)}),
      detailField({label:"STATUS",control:readonlyField(status)}),
      detailField({label:"LOAD IN GAME",dataType:"BOOL",control:load,
        help:infoHelp("Off renames dsound.dll so Windows never loads it. The ShaderInjector folder and anything you edited in it stay put, so switching back on is instant.")}),
      detailField({label:"INSTALL",control:actions}),
      detailField({label:"FOLDER",control:readonlyField(state.folder)}),
    ];
    if(state.modifiedFiles.length){
      rows.push(detailField({label:"EDITED FILES",control:readonlyField(
        `${state.modifiedFiles.length} file${state.modifiedFiles.length===1?"":"s"} in ShaderInjector differ from the release. They are kept on reinstall and removal.`),
        help:infoHelp(state.modifiedFiles.slice(0,12).join("\n"))}));
    }
    if(state.missingFiles.length){
      rows.push(detailField({label:"MISSING FILES",control:readonlyField(
        `${state.missingFiles.length} file${state.missingFiles.length===1?"":"s"} from the release are gone. Restore puts them back.`)}));
    }
    for(const clash of state.conflicts||[]){
      rows.push(detailField({label:"KEY CLASH",control:readonlyField(clash.message),tone:"warning",
        help:infoHelp("ReShade is installed in the same folder and answers the same key, so one press does both. Change the key below, or in ReShade's own settings.")}));
    }
    const cache=state.shaderCache||{files:[],bytes:0,folder:""};
    const clear=el("button",{type:"button",class:"lex-dialog-action",disabled:injectorBusy||!cache.files.length,
      onclick:clearShaderCache},"Clear shader cache");
    return LexeditorUI.detailPanel({title:"SHADER INJECTOR",body:[
      detailSection({title:"INSTALLATION",body:rows}),
      detailSection({title:"GAME SHADER CACHE",body:[
        detailField({label:"CACHE",control:readonlyField(cache.files.length
          ?`${megabytes(cache.bytes)} in ${cache.folder}`:`No cache in ${cache.folder}`),
          help:infoHelp("The injector can only replace shaders it watches the game create, and a game with a warm cache creates almost none. Upstream's install guide makes clearing it the first step, and it is worth doing again after a game update.")}),
        detailField({label:"CLEAR",control:el("div",{class:"lex-reshade-actions"},clear)}),
      ]}),
    ]});
  }

  function settingControl(setting){
    const section=injectorDraft[setting.section], value=section[setting.key];
    const label=`${setting.label}`;
    const set=next=>{section[setting.key]=next;render()};
    const disabled=injectorBusy;
    if(setting.kind==="bool"){
      return el("input",{type:"checkbox",checked:value===true,disabled,"aria-label":label,
        onchange:event=>set(event.target.checked)});
    }
    if(setting.kind==="key"||setting.kind==="choice"){
      const options=setting.kind==="key"
        ? Object.entries(injector.keyNames).map(([code,name])=>[Number(code),name])
        : setting.choices.map(choice=>[choice.value,choice.label]);
      if(!options.some(([code])=>code===Number(value)))options.push([Number(value),`Key code ${value}`]);
      const select=el("select",{disabled,"aria-label":label,onchange:event=>set(Number(event.target.value))},
        ...options.map(([code,name])=>{const option=el("option",{value:String(code)},name);option.selected=code===Number(value);return option}));
      return select;
    }
    const step=setting.kind==="float"?(setting.key==="MenuScale"?0.05:0.01):1;
    return el("input",{type:"number",value:String(value),step,disabled,"aria-label":label,
      ...(setting.minimum!==null?{min:setting.minimum}:{}),...(setting.maximum!==null?{max:setting.maximum}:{}),
      onchange:event=>{const next=Number(event.target.value);if(Number.isFinite(next))set(setting.kind==="float"?next:Math.round(next))}});
  }

  function injectorSettingsCard(){
    if(!injector?.available||!injectorDraft)return null;
    const titles={InjectorSettings:"INJECTOR",RenderDoc:"RENDERDOC",ShaderDiscovery:"SHADER DISCOVERY"};
    const sections=[];
    for(const name of Object.keys(titles)){
      const fields=injector.schema.filter(setting=>setting.section===name).map(setting=>detailField({
        label:setting.label,dataType:setting.kind==="bool"?"BOOL":setting.kind==="float"?"FLOAT":setting.kind==="int"?"INT":"ENUM",
        control:settingControl(setting),help:infoHelp(setting.help)}));
      sections.push(detailSection({title:titles[name],body:fields}));
    }
    const saved=injector.settings.values;
    const dirty=JSON.stringify(saved)!==JSON.stringify(injectorDraft);
    const file=injector.settings;
    const fileRows=[
      detailField({label:"FILE",control:readonlyField(file.exists
        ?file.path:`${file.path} — not created yet. The injector writes it on first start; saving here creates it now.`)}),
      detailField({label:"SAVE",control:el("div",{class:"lex-reshade-actions"},
        el("button",{type:"button",class:"lex-dialog-action primary",disabled:!dirty||injectorBusy,
          onclick:()=>injectorAction("settings",{changes:injectorDraft},"Saved ShaderInjector.ini. Restart the game to apply.")},"Save settings"),
        el("button",{type:"button",class:"lex-dialog-action",disabled:!dirty||injectorBusy,
          onclick:()=>{injectorDraft=clone(saved);render()}},"Revert"))}),
    ];
    for(const problem of file.problems||[]){
      fileRows.push(detailField({label:"FILE PROBLEM",control:readonlyField(problem),tone:"warning"}));
    }
    return LexeditorUI.detailPanel({title:"SHADERINJECTOR.INI",body:[
      detailSection({title:"SETTINGS FILE",body:fileRows}), ...sections]});
  }

  // ---- Engine Config (shared Unreal editor, issue 478) ------------------------
  let engineConfig=null, engineDraft=null, engineConfigBusy=false;
  async function loadEngineConfig(){
    try{
      const response=await fetch("/api/unreal-config");
      const value=await response.json();
      if(!response.ok)throw new Error(value.error||"Could not read Engine Config");
      engineConfig=value;
      engineDraft=clone(value.overrides||{});
    }catch(error){engineConfig={error:error.message||String(error)};engineDraft=null}
  }
  async function engineConfigAction(route,body,done){
    if(engineConfigBusy)return;
    engineConfigBusy=true;render();
    try{
      const response=await fetch(`/api/unreal-config/${route}`,{method:"POST",
        headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});
      const value=await response.json();
      if(!response.ok)throw new Error(value.error||"Engine Config refused that");
      engineConfig=value.result;
      engineDraft=clone(value.result.overrides||{});
      if(done)LexeditorUI.showToast?.(typeof done==="function"?done(value.result):done);
    }catch(error){LexeditorUI.showToast?.(error.message||String(error),true)}
    finally{engineConfigBusy=false;render()}
  }
  function engineSettingControl(item){
    const key=item.key, disabled=engineConfigBusy;
    const shown=engineDraft[key]!==undefined?engineDraft[key]
      :engineConfig.observed&&engineConfig.observed[key]!==undefined?engineConfig.observed[key]:"";
    const set=next=>{engineDraft[key]=next;render()};
    if(item.type==="choice"){
      const options=(item.choices||[]).map(choice=>[choice,String(choice)]);
      if(shown!==""&&!options.some(([code])=>code===Number(shown)))options.push([Number(shown),`Current ${shown}`]);
      return el("select",{disabled,"aria-label":item.name,onchange:event=>set(Number(event.target.value))},
        ...options.map(([code,name])=>{const option=el("option",{value:String(code)},name);option.selected=code===Number(shown);return option}));
    }
    const step=item.type==="float"?0.01:1;
    return el("input",{type:"number",value:String(shown),step,disabled,"aria-label":item.name,
      ...(item.minimum!==null&&item.minimum!==undefined?{min:item.minimum}:{}),
      ...(item.maximum!==null&&item.maximum!==undefined?{max:item.maximum}:{}),
      onchange:event=>{const next=Number(event.target.value);if(Number.isFinite(next))set(item.type==="float"?next:Math.round(next))}});
  }
  function engineConfigCard(){
    const config=engineConfig;
    if(!config||config.error){
      return LexeditorUI.detailPanel({title:"ENGINE CONFIG",body:[
        detailSection({title:"STATUS",body:[
          detailField({label:"STATUS",control:readonlyField(config?.error||"Reading Engine Config…")}),
        ]}),
      ]});
    }
    const fileRows=[
      detailField({label:"FILE",control:readonlyField(config.configExists?config.configPath
        :`${config.configPath} — not created yet. Saving here creates it with a Lexeditor block.`)}),
      detailField({label:"ENGINE",control:readonlyField(config.engine||"")}),
    ];
    if(config.notes)fileRows.push(detailField({label:"NOTES",control:readonlyField(config.notes)}));
    if(config.externalChange)fileRows.push(detailField({label:"EXTERNAL CHANGE",tone:"warning",
      control:el("div",{class:"lex-reshade-actions"},
        el("button",{type:"button",class:"lex-dialog-action",disabled:engineConfigBusy,
          onclick:()=>engineConfigAction("refresh",{},"Rebased on the current file.")},"Reload status"))}));
    const fields=(config.advanced||[]).map(item=>{
      const managed=config.overrides&&Object.prototype.hasOwnProperty.call(config.overrides,item.key);
      const help=[item.unverified_note||"",item.description,
        item.restart_required?"Restart the game after changing it.":"Takes effect without a restart on most builds.",
        item.dependencies&&item.dependencies.length?`Related: ${item.dependencies.join(", ")}.`:""
      ].filter(Boolean).join(" ");
      const controls=[engineSettingControl(item)];
      if(managed)controls.push(el("button",{type:"button",class:"lex-dialog-action",disabled:engineConfigBusy,
        onclick:()=>engineConfigAction("default",{key:item.key},"Back to the game default.")},"Use game default"));
      return detailField({label:(managed?"* ":"")+item.name.toUpperCase()+(item.unverified_note?" (UNVERIFIED)":""),
        dataType:item.type==="float"?"FLOAT":item.type==="choice"?"ENUM":"INT",
        control:el("div",{class:"lex-reshade-actions"},...controls),
        help:infoHelp((managed?"Managed by Lexeditor. ":"")+help)});
    });
    const saved=config.overrides||{};
    const dirty=JSON.stringify(saved)!==JSON.stringify(engineDraft||{});
    const saveRows=[detailField({label:"SAVE",control:el("div",{class:"lex-reshade-actions"},
      el("button",{type:"button",class:"lex-dialog-action primary",disabled:!dirty||engineConfigBusy,
        onclick:()=>engineConfigAction("apply",{values:engineDraft||{}},"Saved Engine.ini. Restart the game where noted.")},"Save settings"),
      el("button",{type:"button",class:"lex-dialog-action",disabled:!dirty||engineConfigBusy,
        onclick:()=>{engineDraft=clone(saved);render()}},"Revert"),
      el("button",{type:"button",class:"lex-dialog-action",disabled:engineConfigBusy||!Object.keys(saved).length,
        onclick:async()=>{const ok=await LexeditorUI.confirmAction({title:"Remove all Engine Config overrides?",
          message:"Removes the Lexeditor block and restores values you had before, where recorded.",confirmLabel:"Remove all"});
          if(ok)engineConfigAction("reset",{},"All overrides removed.")}},"Reset all"))})];
    if(config.backup)saveRows.push(detailField({label:"BACKUP",control:readonlyField(config.backup)}));
    return LexeditorUI.detailPanel({title:"ENGINE CONFIG",body:[
      detailSection({title:"CONFIG FILE",body:fileRows}),
      detailSection({title:"SETTINGS",body:fields}),
      detailSection({title:"SAVE",body:saveRows}),
    ]});
  }
  // Every plugin names its loaders in the same five fields.
  function loaderCard(){
    return LexeditorUI.modLoaderSection({
      loader:"ReShade as dxgi.dll; Shader Injector as dsound.dll.",
      output:"ReShadePreset.ini and ShaderInjector.ini beside the game.",
      order:"Shader Injector first, then ReShade.",
      safety:"Never overwrites a DLL Lexeditor did not put there.",
      removal:"Switch each off on its own tab.",
    });
  }

  function tweaks(){
    const section=LexeditorUI.reshadeSection({snapshot:reshade,act:actReshade});
    const cards=tweakTab==="injector"
      ? [injectorStatusCard(),injectorSettingsCard(),loaderCard()].filter(Boolean)
      : tweakTab==="engine"
      ? [engineConfigCard()]
      : [section||LexeditorUI.detailNote("ReShade is not set up for this game yet.")];
    // Setup is not finished while the shader cache predates the injector, so
    // the step and its button sit above both subtabs until it is done.
    const notice=injector?.setupNotice;
    const banner=notice?LexeditorUI.notice({title:notice.title,message:notice.message,
      action:el("button",{type:"button",class:"lex-dialog-action primary",disabled:injectorBusy,
        onclick:clearShaderCache},notice.actionLabel)}):null;
    return LexeditorUI.settingsColumns(cards,{columnWidth:"520px",notice:banner,
      tabs:[
        {id:"reshade",label:"ReShade",help:"Effects over the finished frame."},
        {id:"injector",label:"Shader Injector",help:"Replaces Rebirth's own shaders."},
        {id:"engine",label:"Engine Config",help:"Unreal Engine.ini settings from the shared catalogue."},
      ],activeTab:tweakTab,tabsLabel:"Presentation tools",changeTab:id=>{tweakTab=id;render()}});
  }

  async function loadDataMap(){
    try{const response=await fetch("/api/datamap");if(response.ok)state.dataMap=await response.json()}
    catch(_error){state.dataMap={rows:[]}}
  }

  // ---- PlayerParameter project data ----------------------------------------
  let workspace=null, player=null, savedPlayer=null;
  let playerError="", playerBusy=false, activeSource="mine";
  let selectedRecord=null, recordPage=0, recordPageSize=12, recordQuery="";
  let recordSort={key:"key",dir:1};

  // BattlePlayerParameter has a public storage schema, but the gameplay meaning
  // and safe ranges of its fields remain unproved. Keep it source-only.
  let battlePlayer=null, battlePlayerError="", battlePlayerBusy=false;
  let selectedBattlePlayerRecord=null, battlePlayerPage=0, battlePlayerPageSize=12, battlePlayerQuery="";
  let battlePlayerSort={key:"key",dir:1};

  // #471 is deliberately source-only until array writes and the actual Steal
  // formula have native acceptance. The view exposes proved serialized data.
  let battleItem=null, battleItemError="", battleItemBusy=false;
  let selectedBattleRecord=null, battlePage=0, battlePageSize=12, battleQuery="";
  let battleSort={key:"key",dir:1};

  const playerValueColumn=(key,label,pinned=true)=>({
    key,label,numeric:true,sortable:true,pinned,
    editValue:row=>row[key],
    editor:(row,commit)=>playerCellEditor(row,key,commit),
    edit:(row,value)=>editPlayerTableValue(row,key,value),
  });
  const PLAYER_COLUMNS=[
    {key:"key",label:"Record",sortable:true,width:"minmax(160px,2fr)"},
    playerValueColumn("HPMax","HP Max"),
    playerValueColumn("MPMax","MP Max"),
    playerValueColumn("Strength","Strength"),
    playerValueColumn("Vitality","Vitality",false),
    playerValueColumn("Magic","Magic",false),
    playerValueColumn("Spilit","Spilit",false),
    playerValueColumn("Dexterity","Dexterity",false),
    playerValueColumn("Luck","Luck",false),
  ];
  const playerPrefs=columnPreferences("ff7r2-player-parameter",PLAYER_COLUMNS,()=>render());
  const BATTLE_COLUMNS=[
    {key:"key",label:"Record",sortable:true,width:"minmax(160px,2fr)"},
    {key:"StealItemName_Array",label:"Steal items",numeric:true,sortable:true},
    {key:"StealItemQuantity_Array",label:"Quantities",numeric:true,sortable:true},
    {key:"NormalItemPercent_Array",label:"Normal rates",numeric:true,sortable:true},
    {key:"RareItemPercent_Array",label:"Rare rates",numeric:true,sortable:true},
    {key:"StealFaildCountArrayIndex",label:"Fail index",numeric:true,sortable:true},
  ];
  const battlePrefs=columnPreferences("ff7r2-battle-item-possession",BATTLE_COLUMNS,()=>render());
  const BATTLE_PLAYER_COLUMNS=[
    {key:"key",label:"Record",sortable:true,width:"minmax(160px,2fr)"},
    {key:"CommandAbilityID_Array",label:"Commands",numeric:true,sortable:true},
    {key:"EnableAerialShortCut",label:"Aerial flag (raw)",numeric:true,sortable:true},
    {key:"UniqueAbilityType0",label:"Unique type (raw)",numeric:true,sortable:true},
    {key:"KeyDownTime",label:"Key-down time (raw)",numeric:true,sortable:true},
    {key:"GuardParameterValue_Array",label:"Guard params",numeric:true,sortable:true},
    {key:"DodgeType_Array",label:"Dodge types",numeric:true,sortable:true},
    {key:"LimitAbilityID_Array",label:"Limits",numeric:true,sortable:true},
  ];
  const battlePlayerPrefs=columnPreferences("ff7r2-battle-player-parameter",BATTLE_PLAYER_COLUMNS,()=>render());

  const FIELD_HELP={
    HPMax:"Base maximum HP stored by this PlayerParameter record.",
    MPMax:"Base maximum MP stored by this PlayerParameter record.",
    Strength:"Serialized Strength stat. Lexeditor does not assume an undocumented damage formula.",
    Vitality:"Serialized Vitality stat. Lexeditor does not assume an undocumented defense formula.",
    Magic:"Serialized Magic stat. Lexeditor does not assume an undocumented magic formula.",
    Spilit:"The asset property is spelled Spilit. Lexeditor preserves that exact Rebirth field name instead of silently renaming it.",
    Dexterity:"Serialized Dexterity stat. Its downstream formulas are not inferred here.",
    Luck:"Serialized Luck stat. Its downstream formulas are not inferred here.",
    Experience:"Serialized Experience value for this PlayerParameter record.",
    SPMax:"Serialized maximum SP value for this PlayerParameter record.",
    TreeLevel:"Serialized TreeLevel value for this PlayerParameter record."
  };

  async function api(path,body){
    const options=body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)};
    const response=await fetch(path,options);
    let value={};
    try{value=await response.json()}catch(_error){}
    if(!response.ok){const error=new Error(value.error||("Request failed: "+response.status));error.payload=value;throw error}
    return value;
  }

  function enrichPlayer(value){
    if(!value||!Array.isArray(value.records))return value;
    for(const row of value.records){
      row.id=String(row.nameIndex)+":"+String(row.nameNumber);
      for(const field of row.fields||[])row[field.name]=field.value;
    }
    return value;
  }

  function installPlayer(value){
    player=enrichPlayer(value);
    savedPlayer=clone(player);
    playerError="";
    if(player?.records?.length&&!player.records.some(row=>row.id===selectedRecord)){
      selectedRecord=player.records[0].id;
    }
  }

  async function loadWorkspace(){
    try{workspace=await api("/api/workspace")}
    catch(error){workspace=null;playerError=error.message}
  }

  async function loadPlayer(){
    playerBusy=true;
    try{
      const value=await api("/api/player-parameter?source="+encodeURIComponent(activeSource));
      installPlayer(value);
    }catch(error){
      player=null;savedPlayer=null;playerError=error.message;
      if(error.payload?.workspace)workspace=error.payload.workspace;
    }finally{playerBusy=false}
  }

  function installBattleItem(value){
    battleItem=value;
    battleItemError="";
    if(battleItem?.records){
      for(const row of battleItem.records){
        row.id=String(row.nameIndex)+":"+String(row.nameNumber);
        for(const field of row.fields||[]){
          row[field.name]=field.kind==="array"?Number(field.arrayCount||0):field.value;
        }
      }
      if(battleItem.records.length&&!battleItem.records.some(row=>row.id===selectedBattleRecord)){
        selectedBattleRecord=battleItem.records[0].id;
      }
    }
  }

  async function loadBattleItem(){
    battleItemBusy=true;
    try{installBattleItem(await api("/api/battle-item-possession"))}
    catch(error){
      battleItem=null;battleItemError=error.message;
      if(error.payload?.workspace)workspace=error.payload.workspace;
    }finally{battleItemBusy=false}
  }

  function installBattlePlayer(value){
    battlePlayer=value;
    battlePlayerError="";
    if(battlePlayer?.records){
      for(const row of battlePlayer.records){
        row.id=String(row.nameIndex)+":"+String(row.nameNumber);
        for(const field of row.fields||[]){
          row[field.name]=field.kind==="array"?Number(field.arrayCount||0):field.value;
        }
      }
      if(battlePlayer.records.length&&!battlePlayer.records.some(row=>row.id===selectedBattlePlayerRecord)){
        selectedBattlePlayerRecord=battlePlayer.records[0].id;
      }
    }
  }

  async function loadBattlePlayer(){
    battlePlayerBusy=true;
    try{installBattlePlayer(await api("/api/battle-player-parameter"))}
    catch(error){
      battlePlayer=null;battlePlayerError=error.message;
      if(error.payload?.workspace)workspace=error.payload.workspace;
    }finally{battlePlayerBusy=false}
  }

  function fieldOf(row,name){return (row?.fields||[]).find(field=>field.name===name)}
  function playerFieldNumber(field,value){
    if(!field?.editable||field.kind==="bool"||field.kind==="array"||field.kind==="name"||field.kind==="string")return null;
    const raw=String(value??"").replaceAll(",","").replace(/\s/g,"");
    if(raw==="")return null;
    let next=Number(raw);
    if(!Number.isFinite(next))return null;
    if(field.kind!=="float"&&!Number.isInteger(next))return null;
    if(Number.isSafeInteger(field.minimum)&&next<field.minimum)return null;
    if(Number.isSafeInteger(field.maximum)&&next>field.maximum)return null;
    return next;
  }
  function editPlayerTableValue(row,key,value){
    const field=fieldOf(row,key),next=playerFieldNumber(field,value);
    if(next===null)return;
    field.value=next;row[key]=next;shell.refresh?.();
  }
  function playerCellEditor(row,key,commit){
    const field=fieldOf(row,key);
    const attrs={type:"number",value:String(field?.value??""),"aria-label":key+" table value",
      step:field?.kind==="float"?"any":"1"};
    if(Number.isSafeInteger(field?.minimum))attrs.min=field.minimum;
    if(Number.isSafeInteger(field?.maximum))attrs.max=field.maximum;
    const input=el("input",attrs);
    input.addEventListener("keydown",event=>{
      if(event.key==="Enter"){event.preventDefault();const next=playerFieldNumber(field,input.value);if(next!==null)commit(next)}
      if(event.key==="Escape"){event.preventDefault();commit(undefined)}
    });
    input.addEventListener("blur",()=>{const next=playerFieldNumber(field,input.value);commit(next===null?undefined:next)});
    return input;
  }
  function savedRow(row){return (savedPlayer?.records||[]).find(item=>item.id===row.id)}
  function savedField(row,field){return fieldOf(savedRow(row),field.name)}

  function changedFields(){
    if(!player||!savedPlayer||activeSource!=="mine")return [];
    const result=[];
    for(const row of player.records){
      for(const field of row.fields||[]){
        const before=savedField(row,field);
        if(before&&JSON.stringify(before.value)!==JSON.stringify(field.value)){
          result.push({row,field,before:before.value,after:field.value});
        }
      }
    }
    return result;
  }

  function dirtyCount(){return changedFields().length}
  function readonlyPlayer(){return playerBusy||activeSource!=="mine"||workspace?.readOnly===true}

  function pendingChanges(){
    return changedFields().map(change=>({
      label:change.row.key+" / "+change.field.name,
      before:change.before,
      after:change.after
    }));
  }

  async function savePlayer(){
    if(readonlyPlayer()||!player)return;
    const changes=changedFields().map(change=>({
      nameIndex:change.row.nameIndex,
      nameNumber:change.row.nameNumber,
      property:change.field.name,
      value:change.after
    }));
    if(!changes.length)return;
    playerBusy=true;shell.refresh?.();
    try{
      installPlayer(await api("/api/player-parameter/save",{
        sha256:player.activeSha256,
        changes
      }));
      workspace=await api("/api/workspace");
      LexeditorUI.showToast?.("Saved "+changes.length+" PlayerParameter field"+(changes.length===1?"":"s")+" to the project staging path.");
    }catch(error){
      LexeditorUI.showToast?.(error.message||String(error),true);
      throw error;
    }finally{playerBusy=false;render()}
  }

  async function discardPlayer(){
    if(!player)return;
    await loadPlayer();
    render();
  }

  async function reopenPlayer(){
    await Promise.all([loadWorkspace(),loadPlayer()]);
    render();
  }

  async function resetPlayer(){
    if(activeSource!=="mine"||workspace?.readOnly)return;
    const ok=await LexeditorUI.confirmAction({
      title:"Revert staged PlayerParameter?",
      message:"Deletes only this project's staged PlayerParameter.uasset. The extracted source and installed game are not changed.",
      confirmLabel:"Revert staged file"
    });
    if(!ok)return;
    playerBusy=true;
    try{
      installPlayer(await api("/api/player-parameter/reset",{}));
      workspace=await api("/api/workspace");
    }catch(error){LexeditorUI.showToast?.(error.message||String(error),true)}
    finally{playerBusy=false;render()}
  }

  async function buildPackageCandidate(){
    if(packageBusy)return;
    packageBusy=true;render();
    try{
      const value=await api("/api/package/build",{});
      workspace=value.workspace||workspace;
      const path=value.result?.candidateDirectory||"the project build folder";
      LexeditorUI.showToast?.("Built an isolated FF7R2 package candidate in "+path+". It is not installed or game-accepted.");
    }catch(error){
      LexeditorUI.showToast?.(error.message||String(error),true);
    }finally{packageBusy=false;render()}
  }

  async function switchProjectSource(value){
    activeSource=String(value||"mine")==="vanilla"?"vanilla":"mine";
    selectedRecord=null;recordPage=0;
    await loadPlayer();
    render();
  }

  function playerRows(){
    const rows=[...(player?.records||[])];
    const needle=recordQuery.trim().toLocaleLowerCase();
    const filtered=needle?rows.filter(row=>{
      const values=[row.key,row.name,...(row.fields||[]).map(field=>field.value)];
      return values.join(" ").toLocaleLowerCase().includes(needle);
    }):rows;
    const key=recordSort.key,dir=recordSort.dir;
    return filtered.sort((left,right)=>{
      const a=left[key],b=right[key];
      if(typeof a==="number"||typeof b==="number")return (Number(a||0)-Number(b||0))*dir;
      return String(a??"").localeCompare(String(b??""))*dir;
    });
  }

  function playerTable(rows,picked,select){
    return columnList({
      rows,key:row=>row.id,selected:picked,select,
      sortState:recordSort,
      sort:key=>{recordSort=recordSort.key===key?{key,dir:-recordSort.dir}:{key,dir:1};render()},
      columnPreferences:playerPrefs,columns:PLAYER_COLUMNS,
      refresh:()=>{render();shell.refresh?.()},
      class:"ff7r2-table","aria-label":"Final Fantasy VII Rebirth PlayerParameter records"
    });
  }

  function fieldControl(row,field){
    const disabled=readonlyPlayer()||!field.editable;
    if(!field.editable){
      const suffix=field.kind==="array"?" element(s)":"";
      const value=field.kind==="array"?String(field.value)+suffix:String(field.value??"");
      return {control:readonlyField(value),dataType:field.kind==="array"?"ARRAY":String(field.kind||field.type).toUpperCase(),
        help:infoHelp([FIELD_HELP[field.name],field.note].filter(Boolean).join("\n"))};
    }
    if(field.kind==="bool"){
      return {dataType:"BOOL",help:infoHelp([FIELD_HELP[field.name],field.note].filter(Boolean).join("\n")),
        control:el("input",{type:"checkbox",checked:field.value===true,disabled,"aria-label":field.name,
          onchange:event=>{field.value=event.target.checked;row[field.name]=field.value;render();shell.refresh?.()}})};
    }
    const attrs={type:"number",value:String(field.value),disabled,"aria-label":field.name,
      step:field.kind==="float"?"any":"1"};
    if(Number.isSafeInteger(field.minimum))attrs.min=field.minimum;
    if(Number.isSafeInteger(field.maximum))attrs.max=field.maximum;
    const captureNumeric=event=>{
      const raw=String(event.target.value??"").replaceAll(",","").replace(/\s/g,"");
      if(raw==="")return false;
      let next=Number(raw);
      if(!Number.isFinite(next))return false;
      if(field.kind!=="float"&&!Number.isInteger(next))return false;
      if(Number.isSafeInteger(field.minimum)&&next<field.minimum)return false;
      if(Number.isSafeInteger(field.maximum)&&next>field.maximum)return false;
      field.value=next;row[field.name]=next;shell.refresh?.();return true;
    };
    return {dataType:field.kind==="float"?"FLOAT":"INT",min:attrs.min,max:attrs.max,
      help:infoHelp([FIELD_HELP[field.name],field.note].filter(Boolean).join("\n")),
      control:el("input",{...attrs,
        oninput:event=>captureNumeric(event),
        onchange:event=>{if(captureNumeric(event))render();}
      })};
  }

  function playerRecordPanel(row){
    if(!row)return statusPanel("NO RECORD","No PlayerParameter record is selected.");
    const scalar=[],readonly=[];
    for(const field of row.fields||[]){
      const column=PLAYER_COLUMNS.find(item=>item.key===field.name);
      const item=detailField({
        label:field.name.toUpperCase(),...fieldControl(row,field),
        pin:column?playerPrefs.pinButton(field.name,column.label):null
      });
      (field.editable?scalar:readonly).push(item);
    }
    const projectActions=el("div",{class:"lex-reshade-actions"},
      el("button",{type:"button",class:"lex-dialog-action",disabled:playerBusy,onclick:reopenPlayer},"Reopen from disk"),
      ...(workspace?.playerParameter?.outputPresent&&activeSource==="mine"
        ?[el("button",{type:"button",class:"lex-dialog-action",disabled:playerBusy||workspace?.readOnly,onclick:resetPlayer},"Revert staged file")]
        :[])
    );
    const sections=[
      detailSection({title:"IDENTITY",body:[
        detailField({label:"ROW FNAME",control:readonlyField(row.key),
          help:infoHelp("This is the DataObject row FName read from Rebirth's minimal-name map, not a generated display ID.")}),
        detailField({label:"NAME INDEX",control:readonlyField(String(row.nameIndex))}),
        detailField({label:"NAME NUMBER",control:readonlyField(String(row.nameNumber))}),
      ]}),
      detailSection({title:"FIXED-WIDTH VALUES",body:scalar.length?scalar:[
        detailField({label:"STATUS",control:readonlyField("No safely editable scalar fields in this record.")})
      ]}),
    ];
    if(readonly.length)sections.push(detailSection({title:"READ-ONLY VALUES",body:readonly}));
    sections.push(detailSection({title:"PROJECT FILE",body:[
      detailField({label:"ACTIVE",control:readonlyField(player?.projectRelativePath||"")}),
      detailField({label:"ACTIONS",control:projectActions}),
    ]}));
    return detailPanel({className:"ff7r2-detail",title:row.key,icon:el("span",{class:"ff7r2-record-icon"},"VII"),
      identity:recordId(row.key),meta:"PlayerParameter",body:sections});
  }

  function statusPanel(title,message){
    return detailPanel({className:"ff7r2-detail",title,icon:infoIcon(),identity:null,meta:"Rebirth project data",body:[
      detailSection({title:"STATUS",body:[
        detailField({label:"DETAIL",control:readonlyField(message)}),
        detailField({label:"SOURCE PATH",control:readonlyField(workspace?.playerParameter?.sourceRelative||"source/End/Content/DataObject/Resident/PlayerParameter.uasset")}),
        detailField({label:"ACTION",control:el("div",{class:"lex-reshade-actions"},
          el("button",{type:"button",class:"lex-dialog-action",disabled:playerBusy,onclick:reopenPlayer},"Reopen from disk"))}),
      ]})
    ]});
  }

  function charactersPanel(){
    if(playerBusy&&!player)return statusPanel("LOADING","Reading the staged or extracted PlayerParameter DataObject.");
    if(!player)return statusPanel("PLAYERPARAMETER NOT LOADED",playerError||"The project has no extracted source asset yet.");
    if(!player.records.length)return statusPanel("EMPTY PLAYERPARAMETER","The DataObject parsed successfully but contains no rows.");
    const rows=playerRows();
    return pagedListDetail({
      rows,key:row=>row.id,slots:false,selected:selectedRecord,page:recordPage,pageSize:recordPageSize,noun:"records",
      className:"ff7r2-layout",splitKey:"ff7r2-player",rowsKey:"ff7r2-player",defaultSplit:48,minLeft:330,minRight:390,
      search:{key:"ff7r2-player-search",value:recordQuery,label:"Search PlayerParameter records",
        change:value=>{recordQuery=value;recordPage=0;render()}},
      sync:next=>{recordPage=next.page;recordPageSize=next.pageSize;if(next.selected!==null)selectedRecord=next.selected},
      change:next=>{recordPage=next.page;recordPageSize=next.pageSize;if(next.selected!==null)selectedRecord=next.selected;render()},
      master:state=>playerTable(state.rows,state.selected,state.select),
      detail:row=>playerRecordPanel(row)
    });
  }

  function battlePlayerRows(){
    const rows=[...(battlePlayer?.records||[])];
    const needle=battlePlayerQuery.trim().toLocaleLowerCase();
    const filtered=needle?rows.filter(row=>{
      const values=[row.key,row.name,...(row.fields||[]).flatMap(field=>
        Array.isArray(field.value)?field.value:[field.value])];
      return values.join(" ").toLocaleLowerCase().includes(needle);
    }):rows;
    const key=battlePlayerSort.key,dir=battlePlayerSort.dir;
    return filtered.sort((left,right)=>{
      const a=left[key],b=right[key];
      if(typeof a==="number"||typeof b==="number")return (Number(a||0)-Number(b||0))*dir;
      return String(a??"").localeCompare(String(b??""))*dir;
    });
  }

  function battlePlayerTable(rows,picked,select){
    return columnList({
      rows,key:row=>row.id,selected:picked,select,
      sortState:battlePlayerSort,
      sort:key=>{battlePlayerSort=battlePlayerSort.key===key?{key,dir:-battlePlayerSort.dir}:{key,dir:1};render()},
      columnPreferences:battlePlayerPrefs,columns:BATTLE_PLAYER_COLUMNS,
      refresh:()=>{render();shell.refresh?.()},
      class:"ff7r2-table ff7r2-battle-player-table",
      "aria-label":"Final Fantasy VII Rebirth BattlePlayerParameter records"
    });
  }

  function sourceFieldLabel(name){
    const overrides={
      NormalItemName_Array:"Normal item names",
      NormalItemPercent_Array:"Normal item rates",
      RareItemName_Array:"Rare item names",
      RareItemPercent_Array:"Rare item rates",
      StealItemName_Array:"Steal item names",
      StealItemQuantity_Array:"Steal item quantities",
      StealFaildCountArrayIndex:"Steal failure count array index",
    };
    if(overrides[name])return overrides[name];
    return String(name||"")
      .replace(/_Array$/," array")
      .replaceAll("_"," ")
      .replace(/([a-z0-9])([A-Z])/g,"$1 $2")
      .replace(/\bId\b/gi,"ID")
      .replace(/\bFname\b/gi,"FName");
  }

  function battlePlayerRecordPanel(row){
    if(!row)return detailPanel({className:"ff7r2-detail",title:"NO RECORD",icon:infoIcon(),identity:null,
      meta:"BattlePlayerParameter",body:[detailSection({title:"STATUS",body:[
        detailField({label:"DETAIL",control:readonlyField("No BattlePlayerParameter record is selected.")})
      ]})]});
    const fields=(row.fields||[]).map(field=>detailField({
      label:sourceFieldLabel(field.name).toUpperCase(),
      dataType:field.kind==="array"?("ARRAY<"+String(field.type||"VALUE").toUpperCase()+">"):String(field.kind||field.type).toUpperCase(),
      control:readonlyField(field.kind==="array"?arrayDisplay(field):String(field.value??""))
    }));
    return detailPanel({className:"ff7r2-detail ff7r2-battle-player-detail",title:row.key,
      icon:el("span",{class:"ff7r2-record-icon"},"VII"),identity:recordId(row.key),
      meta:"BattlePlayerParameter — read-only source data",body:[
        detailSection({title:"INTEGRATION STATUS",body:[
          LexeditorUI.detailNote("Public declarations prove the storage schema, but not the gameplay behavior, enum domains or safe edit ranges. This page therefore stops at structured source inspection."),
        ]}),
        detailSection({title:"IDENTITY",body:[
          detailField({label:"ROW FNAME",control:readonlyField(row.key)}),
          detailField({label:"NAME INDEX",control:readonlyField(String(row.nameIndex))}),
          detailField({label:"NAME NUMBER",control:readonlyField(String(row.nameNumber))}),
        ]}),
        detailSection({title:"SERIALIZED FIELDS",body:fields.length?fields:[
          detailField({label:"STATUS",control:readonlyField("This row has no decoded fields.")})
        ]}),
        detailSection({title:"SOURCE FILE",body:[
          detailField({label:"PATH",control:readonlyField(battlePlayer?.projectRelativePath||workspace?.battlePlayerParameter?.sourceRelative||"")}),
          detailField({label:"MODE",control:readonlyField("Read-only; no BattlePlayerParameter staging or save route.")}),
        ]}),
      ]});
  }

  function battleParamsPanel(){
    if(battlePlayerBusy&&!battlePlayer)return detailPanel({className:"ff7r2-detail",title:"LOADING",icon:infoIcon(),identity:null,
      meta:"Battle Params",body:[detailSection({title:"STATUS",body:[
        detailField({label:"DETAIL",control:readonlyField("Reading the extracted BattlePlayerParameter DataObject.")})
      ]})]});
    if(!battlePlayer)return detailPanel({className:"ff7r2-detail",title:"BATTLEPLAYERPARAMETER NOT LOADED",icon:infoIcon(),identity:null,
      meta:"Battle Params",body:[detailSection({title:"STATUS",body:[
        detailField({label:"DETAIL",control:readonlyField(battlePlayerError||"The project has no extracted BattlePlayerParameter source asset yet.")}),
        detailField({label:"SOURCE PATH",control:readonlyField(workspace?.battlePlayerParameter?.sourceRelative||"source/End/Content/DataObject/Resident/BattlePlayerParameter.uasset")}),
        detailField({label:"ACTION",control:el("div",{class:"lex-reshade-actions"},
          el("button",{type:"button",class:"lex-dialog-action",disabled:battlePlayerBusy,onclick:async()=>{await loadBattlePlayer();render()}}, "Reopen from disk"))}),
      ]})]});
    if(!battlePlayer.records?.length)return detailPanel({className:"ff7r2-detail",title:"EMPTY BATTLEPLAYERPARAMETER",icon:infoIcon(),identity:null,
      meta:"Battle Params",body:[detailSection({title:"STATUS",body:[
        detailField({label:"DETAIL",control:readonlyField("The DataObject parsed successfully but contains no rows.")})
      ]})]});
    const rows=battlePlayerRows();
    return pagedListDetail({
      rows,key:row=>row.id,slots:false,selected:selectedBattlePlayerRecord,page:battlePlayerPage,pageSize:battlePlayerPageSize,noun:"records",
      className:"ff7r2-layout",splitKey:"ff7r2-battle-player",rowsKey:"ff7r2-battle-player",defaultSplit:48,minLeft:330,minRight:390,
      search:{key:"ff7r2-battle-player-search",value:battlePlayerQuery,label:"Search BattlePlayerParameter records",
        change:value=>{battlePlayerQuery=value;battlePlayerPage=0;render()}},
      sync:next=>{battlePlayerPage=next.page;battlePlayerPageSize=next.pageSize;if(next.selected!==null)selectedBattlePlayerRecord=next.selected},
      change:next=>{battlePlayerPage=next.page;battlePlayerPageSize=next.pageSize;if(next.selected!==null)selectedBattlePlayerRecord=next.selected;render()},
      master:state=>battlePlayerTable(state.rows,state.selected,state.select),
      detail:row=>battlePlayerRecordPanel(row)
    });
  }

  function battleRows(){
    const rows=[...(battleItem?.records||[])];
    const needle=battleQuery.trim().toLocaleLowerCase();
    const filtered=needle?rows.filter(row=>{
      const values=[row.key,row.name,...(row.fields||[]).flatMap(field=>
        Array.isArray(field.value)?field.value:[field.value])];
      return values.join(" ").toLocaleLowerCase().includes(needle);
    }):rows;
    const key=battleSort.key,dir=battleSort.dir;
    return filtered.sort((left,right)=>{
      const a=left[key],b=right[key];
      if(typeof a==="number"||typeof b==="number")return (Number(a||0)-Number(b||0))*dir;
      return String(a??"").localeCompare(String(b??""))*dir;
    });
  }

  function battleTable(rows,picked,select){
    return columnList({
      rows,key:row=>row.id,selected:picked,select,
      sortState:battleSort,
      sort:key=>{battleSort=battleSort.key===key?{key,dir:-battleSort.dir}:{key,dir:1};render()},
      columnPreferences:battlePrefs,columns:BATTLE_COLUMNS,
      refresh:()=>{render();shell.refresh?.()},
      class:"ff7r2-table ff7r2-formulae-table",
      "aria-label":"Final Fantasy VII Rebirth BattleItemPossession records"
    });
  }

  function arrayDisplay(field){
    const values=Array.isArray(field?.value)?field.value:[];
    return values.length?values.map((value,index)=>index+": "+String(value)).join("  ·  "):"(empty)";
  }

  function battleRecordPanel(row){
    if(!row)return detailPanel({className:"ff7r2-detail",title:"NO RECORD",icon:infoIcon(),identity:null,
      meta:"BattleItemPossession",body:[detailSection({title:"STATUS",body:[
        detailField({label:"DETAIL",control:readonlyField("No BattleItemPossession record is selected.")})
      ]})]});
    const fields=(row.fields||[]).map(field=>detailField({
      label:sourceFieldLabel(field.name).toUpperCase(),
      dataType:field.kind==="array"?("ARRAY<"+String(field.type||"VALUE").toUpperCase()+">"):String(field.kind||field.type).toUpperCase(),
      control:readonlyField(field.kind==="array"?arrayDisplay(field):String(field.value??""))
    }));
    return detailPanel({className:"ff7r2-detail ff7r2-formulae-detail",title:row.key,
      icon:el("span",{class:"ff7r2-record-icon"},"VII"),identity:recordId(row.key),
      meta:"BattleItemPossession — read-only source data",body:[
        detailSection({title:"FORMULA STATUS",body:[
          LexeditorUI.detailNote("The complete Steal formula has not been reconstructed; this view exposes only proved serialized source data."),
          LexeditorUI.detailNote("Public mod evidence reports the 25% rate data is shared between steals and drops."),
          LexeditorUI.detailNote("Generated runtime types include StealSuccessRateAdd, but its arithmetic/order is not exposed."),
          LexeditorUI.detailNote("Generated runtime types distinguish StealFailed, AlreadyStolen and NothingToSteal; their branch conditions are not exposed."),
        ]}),
        detailSection({title:"IDENTITY",body:[
          detailField({label:"ROW FNAME",control:readonlyField(row.key)}),
          detailField({label:"NAME INDEX",control:readonlyField(String(row.nameIndex))}),
          detailField({label:"NAME NUMBER",control:readonlyField(String(row.nameNumber))}),
        ]}),
        detailSection({title:"SERIALIZED FIELDS",body:fields.length?fields:[
          detailField({label:"STATUS",control:readonlyField("This row has no decoded fields.")})
        ]}),
        detailSection({title:"SOURCE FILE",body:[
          detailField({label:"PATH",control:readonlyField(battleItem?.projectRelativePath||workspace?.battleItemPossession?.sourceRelative||"")}),
          detailField({label:"MODE",control:readonlyField("Read-only; no BattleItemPossession staging or array writes.")}),
        ]}),
      ]});
  }

  function formulaePanel(){
    if(battleItemBusy&&!battleItem)return detailPanel({className:"ff7r2-detail",title:"LOADING",icon:infoIcon(),identity:null,
      meta:"Formulae",body:[detailSection({title:"STATUS",body:[
        detailField({label:"DETAIL",control:readonlyField("Reading the extracted BattleItemPossession DataObject.")})
      ]})]});
    if(!battleItem)return detailPanel({className:"ff7r2-detail",title:"BATTLEITEMPOSSESSION NOT LOADED",icon:infoIcon(),identity:null,
      meta:"Formulae",body:[detailSection({title:"STATUS",body:[
        detailField({label:"DETAIL",control:readonlyField(battleItemError||"The project has no extracted BattleItemPossession source asset yet.")}),
        detailField({label:"SOURCE PATH",control:readonlyField(workspace?.battleItemPossession?.sourceRelative||"source/End/Content/DataObject/Resident/BattleItemPossession.uasset")}),
        detailField({label:"ACTION",control:el("div",{class:"lex-reshade-actions"},
          el("button",{type:"button",class:"lex-dialog-action",disabled:battleItemBusy,onclick:async()=>{await loadBattleItem();render()}}, "Reopen from disk"))}),
      ]})]});
    if(!battleItem.records?.length)return detailPanel({className:"ff7r2-detail",title:"EMPTY BATTLEITEMPOSSESSION",icon:infoIcon(),identity:null,
      meta:"Formulae",body:[detailSection({title:"STATUS",body:[
        detailField({label:"DETAIL",control:readonlyField("The DataObject parsed successfully but contains no rows.")})
      ]})]});
    const rows=battleRows();
    return pagedListDetail({
      rows,key:row=>row.id,slots:false,selected:selectedBattleRecord,page:battlePage,pageSize:battlePageSize,noun:"records",
      className:"ff7r2-layout",splitKey:"ff7r2-battle-items",rowsKey:"ff7r2-battle-items",defaultSplit:48,minLeft:330,minRight:390,
      search:{key:"ff7r2-battle-search",value:battleQuery,label:"Search BattleItemPossession records",
        change:value=>{battleQuery=value;battlePage=0;render()}},
      sync:next=>{battlePage=next.page;battlePageSize=next.pageSize;if(next.selected!==null)selectedBattleRecord=next.selected},
      change:next=>{battlePage=next.page;battlePageSize=next.pageSize;if(next.selected!==null)selectedBattleRecord=next.selected;render()},
      master:state=>battleTable(state.rows,state.selected,state.select),
      detail:row=>battleRecordPanel(row)
    });
  }

  function informationPanel(){
    const ws=workspace||{};
    const pp=ws.playerParameter||{};
    const delivery=ws.delivery||{};
    const packaging=delivery.packaging||{};
    const retoc=ws.tooling?.retoc||{};
    const rezen=ws.tooling?.unrealReZen||{};
    const loadOrder=packaging.loadOrder||{};
    const rankedMods=Array.isArray(loadOrder.ranked)?loadOrder.ranked:[];
    const unrankedMods=Array.isArray(loadOrder.unranked)?loadOrder.unranked:[];
    const incompleteMods=Array.isArray(loadOrder.incomplete)?loadOrder.incomplete:[];
    const precedenceSummary=rankedMods.length
      ?rankedMods.slice(0,6).map(item=>item.winnerRank+". "+item.package+" (patch "+item.patchLevel+")").join("  ·  ")
      :(loadOrder.present?"No complete ASCII *_P triples found.":"~mods is not available in the located game.");
    const stagedCount=Number(packaging.stagedFileCount||0);
    const packageState=packaging.ready
      ?(stagedCount+" audited staged file"+(stagedCount===1?"":"s")+"; explicit dependencies and game archives are ready.")
      :("Not ready: "+((packaging.missing||["explicit dependencies"]).join("; ")));
    const packageActions=el("div",{class:"lex-reshade-actions"},
      el("button",{type:"button",class:"lex-dialog-action primary",
        disabled:packageBusy||ws.readOnly===true||packaging.ready!==true,
        onclick:buildPackageCandidate},"Build isolated candidate"));
    return detailPanel({className:"ff7r2-detail lex-information-panel",icon:infoIcon(),title:"Information",
      identity:null,meta:"Rebirth source, project and delivery state",body:[
      detailSection({title:"GAME",body:[
        detailField({label:"ROOT",control:readonlyField(ws.game?.root||"Not located")}),
        detailField({label:"RENDERER",control:readonlyField(ws.game?.renderer||"dxgi")}),
      ]}),
      detailSection({title:"PROJECT",body:[
        detailField({label:"ROOT",control:readonlyField(ws.projectRoot||"No project selected")}),
        detailField({label:"SOURCE",control:readonlyField(pp.sourcePresent?(pp.sourceRelative+" — ready"):(pp.sourceRelative||"Missing"))}),
        detailField({label:"PLAYERPARAMETER OUTPUT",control:readonlyField(pp.outputPresent?(pp.outputRelative+" — present"):(pp.outputRelative||"Not written"))}),
        detailField({label:"PACKAGE INPUTS",control:readonlyField(
          delivery.staged
            ?((delivery.stagedFileCount||0)+" audited staged file"+((delivery.stagedFileCount||0)===1?"":"s")+" under content/End/Content")
            :"No staged gameplay output.")}),
        detailField({label:"DELIVERY",control:readonlyField(
          delivery.packaged
            ?"Isolated package candidate exists; it is not installed or accepted in-game."
            :delivery.staged?"Staged project output only; not packaged or installed.":"No staged gameplay output.")}),
        detailField({label:"SAFETY",control:readonlyField(delivery.reason||"The installed game is never overwritten by the DataObject editor.")}),
      ]}),
      detailSection({title:"IOSTORE TOOLING",body:[
        detailField({label:"RETOC",control:readonlyField((retoc.pinned||"v0.1.5")+" — not automatically integrated"),
          help:infoHelp(retoc.reason||"Requires explicit dependency setup.")}),
        detailField({label:"UNREALREZEN",control:readonlyField((rezen.reference||"FF7R2 fork")+" — dependency-explicit candidate route"),
          help:infoHelp(rezen.reason||"Real-game package acceptance is pending.")}),
        detailField({label:"PACKAGING PREFLIGHT",control:readonlyField(packageState),
          help:infoHelp("Lexeditor does not download, copy or relocate UnrealReZen or Oodle here. LEXEDITOR_FF7R2_OODLE must point to oo2core_9_win64.dll already beside the explicit LEXEDITOR_FF7R2_UNREALREZEN executable; the FF7R2 release's CUE4Parse/1.1.1 dependency manifest and installed game's local IoStore archives are also required.")}),
        detailField({label:"BUILD CANDIDATE",control:packageActions,
          help:infoHelp("Builds .pak/.utoc/.ucas only under this project's build folder. Nothing is copied to End/Content/Paks/~mods.")}),
      ]}),
      detailSection({title:"NATIVE MOD LOAD ORDER",body:[
        detailField({label:"ROOT",control:readonlyField(loadOrder.root||"End/Content/Paks/~mods")}),
        detailField({label:"PRECEDENCE",control:readonlyField(precedenceSummary),
          help:infoHelp(loadOrder.rule||"Higher numeric patch level wins; otherwise the case-insensitively smaller complete path wins.")}),
        detailField({label:"UNCLASSIFIED",control:readonlyField(
          unrankedMods.length+" unranked complete package"+(unrankedMods.length===1?"":"s")+"; "+
          incompleteMods.length+" incomplete triple"+(incompleteMods.length===1?"":"s"))}),
        detailField({label:"SCOPE",control:readonlyField(loadOrder.scope||"Filename/path precedence only; package contents are not inspected."),
          help:infoHelp("This is a read-only audit of native package names and paths. It does not unpack mods, detect which assets overlap, change priority, or activate Lexeditor's unaccepted candidate.")}),
      ]}),
      LexeditorUI.modLoaderSection({
        loader:"Rebirth gameplay assets are loaded from IoStore. A candidate can be packed with explicitly supplied UnrealReZen + Oodle; ReShade uses dxgi.dll and Shader Injector uses dsound.dll.",
        output:"Gameplay Save currently stages PlayerParameter under content/End/Content. Build Candidate audits every staged regular file under that content root and writes a three-file IoStore package only under <project>/build/.",
        order:"For complete native *_P triples, higher numeric _<n>_P patch level wins; at the same level the case-insensitively smaller complete path wins. Lexeditor reports that filename/path precedence read-only, but does not inspect asset overlap or install its unaccepted candidate.",
        safety:"The candidate process rejects staged symlinks, hashes every staged input before packing, rechecks the complete file set and hashes after packing, and requires explicit local dependencies plus CUE4Parse/1.1.1 metadata. The user-supplied oo2core_9_win64.dll must already sit beside UnrealReZen; Lexeditor does not download, copy or relocate it and never writes the installed game. Presentation helpers retain their DLL ownership checks.",
        removal:"Revert/delete the staged project file or delete an isolated project build candidate. No gameplay package is installed by this integration yet."
      }),
    ]});
  }


  function dataMapView(){
    const view=LexeditorUI.dataMap({rows:state.dataMap?.rows||[],query:state.mapQuery,status:state.mapStatus,
      page:state.mapPage,sort:state.mapSort,pageSize:100,
      open:row=>{if(row.target)navigate(row.target)},
      changeQuery:value=>{state.mapQuery=value;state.mapPage=0;render()},
      changeStatus:value=>{state.mapStatus=value;state.mapPage=0;render()},
      changePage:page=>{state.mapPage=page;render()},
      changeSort:key=>{const [active,direction]=state.mapSort;state.mapSort=[key,active===key?-direction:1];render()}});
    state.mapPage=view.page;
    // The map fills the page itself; its filters live in its own pager.
    return view.content;
  }

  function render(){
    const main=document.querySelector("#main");
    let content;
    if(tab==="datamap")content=dataMapView();
    else if(tab==="info")content=panelLayout([informationPanel()],"ff7r2-layout",{layoutKey:"ff7r2-info",defaultSizes:[100]});
    else if(tab==="tweaks")content=tweaks();
    else if(tab==="battleparams")content=battleParamsPanel();
    else if(tab==="formulae")content=formulaePanel();
    else content=charactersPanel();
    main.replaceChildren(content);
    shell.refresh?.();
  }
  function navigate(value){tab=String(value||"characters");render()}

  const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",
    plugin:{id:PLUGIN,name:"Final Fantasy VII Rebirth",themeName:"ff7r2",
      theme:{accent:"#3f7fd0","accent-text":"#f2f7ff"}},
    tabs:[{id:"characters",label:"Characters"},{id:"battleparams",label:"Battle Params"},{id:"formulae",label:"Formulae"},{id:"tweaks",label:"Tweaks"}],
    activeTab:()=>tab,navigate,
    help:()=>navigate("datamap"),helpActive:()=>tab==="datamap",helpTitle:"Open the FF7 Rebirth Data Map",
    info:()=>navigate("info"),infoActive:()=>tab==="info",infoTitle:"Open Rebirth plugin information",
    projectSources:()=>[{key:"vanilla",label:"Extracted source",path:workspace?.playerParameter?.sourceRelative||"Project source PlayerParameter"}],
    projectActiveSource:()=>activeSource,selectProjectSource:switchProjectSource,
    pendingChanges,dirtyCount,readonly:readonlyPlayer,save:savePlayer,discard:discardPlayer
  });

  (async()=>{
    await Promise.all([loadGame(),loadReshade(),loadInjector(),loadEngineConfig(),loadDataMap(),loadWorkspace(),loadPlayer(),loadBattlePlayer(),loadBattleItem()]);
    render();
    LexeditorUI.finishPluginLoading();
  })();
  
