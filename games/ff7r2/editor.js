  "use strict";
  const {el,detailField,readonlyField,infoHelp,detailSection,clone}=LexeditorUI;
  const PLUGIN="ff7r2";
  let tab="tweaks";
  // Which presentation tool the Tweaks page shows. One level of subtabs only.
  let tweakTab="reshade";
  let game={found:false,root:"",renderer:"dxgi",binaries:""};
  let reshade={available:false,effects:[]};
  let injector=null, injectorDraft=null, injectorBusy=false;
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
      ],activeTab:tweakTab,tabsLabel:"Presentation tools",changeTab:id=>{tweakTab=id;render()}});
  }

  async function loadDataMap(){
    try{const response=await fetch("/api/datamap");if(response.ok)state.dataMap=await response.json()}
    catch(_error){state.dataMap={rows:[]}}
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
    if(tab==="datamap"){main.replaceChildren(dataMapView());shell.refresh?.();return}
    main.replaceChildren(tweaks());
    shell.refresh?.();
  }
  function navigate(value){tab=String(value||"tweaks");render()}

  const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",
    plugin:{id:PLUGIN,name:"Final Fantasy VII Rebirth",themeName:"ff7r2",
      theme:{accent:"#3f7fd0","accent-text":"#f2f7ff"}},
    tabs:[{id:"tweaks",label:"Tweaks"}],
    activeTab:()=>tab,navigate,dirtyCount:()=>0,
    help:()=>navigate("datamap"),helpActive:()=>tab==="datamap",helpTitle:"Open the FF7 Rebirth Data Map"});

  (async()=>{
    await Promise.all([loadGame(),loadReshade(),loadInjector(),loadDataMap()]);
    render();
    LexeditorUI.finishPluginLoading();
  })();
  
