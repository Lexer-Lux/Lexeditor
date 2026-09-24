/* Shared Unreal Engine Config panel (issue 478).
 *
 * One Engine Config editor for every Unreal game. Each game's Tweaks page
 * mounts one panel; the game supplies status data through /api/unreal-config
 * and this module owns every control, draft, save and reset flow. Game pages
 * use only LexeditorUI primitives here and never copy this file.
 */
(function(){
  "use strict";
  // Per-game loader evidence arrives as config.iniUnlocker ({verified,
  // candidatePresent). Games without an unlocker concept omit the field and
  // get no row; the panel never assumes one universal loading story.
  function unlockerText(unlocker){
    if(unlocker.verified)return "Verified — the game loads Engine.ini, so saved overrides apply after a restart where noted.";
    if(unlocker.candidatePresent)return "A proxy DLL is present, but Lexeditor could not verify Engine.ini loading. Saved overrides may not apply.";
    return "No INI unlocker found next to the game executable. The game may ignore saved overrides.";
  }
  // Tweaks pages page cards into fixed-height columns and refuse a section
  // taller than one page, so settings render in small groups of at most four
  // fields. Keys missing here fall into OTHER SETTINGS rather than vanishing
  // when the catalogue grows.
  const SETTING_GROUPS=[
    {title:"DISPLAY",keys:["t.MaxFPS","r.VSync"]},
    {title:"POST-PROCESSING",keys:["r.EyeAdaptationQuality","r.MotionBlurQuality","r.DepthOfFieldQuality","r.BloomQuality"]},
    {title:"IMAGE QUALITY",keys:["r.SceneColorFringeQuality","r.Tonemapper.Sharpen","r.PostProcessAAQuality","r.MaxAnisotropy"]},
    {title:"LIGHTING AND SHADOWS",keys:["r.Shadow.MaxResolution","r.SSR.Quality","r.VolumetricFog"]},
    {title:"DISTANCE AND STREAMING",keys:["r.ViewDistanceScale","r.Foliage.DensityScale","r.Streaming.PoolSize"]},
  ];
  function groupTitle(key){
    const found=SETTING_GROUPS.find(group=>group.keys.includes(key));
    return found?found.title:"OTHER SETTINGS";
  }
  function groupOrder(title){
    const index=SETTING_GROUPS.findIndex(group=>group.title===title);
    return index<0?SETTING_GROUPS.length:index;
  }
  function createPanel(options){
    const route=(options&&options.route)||"/api/unreal-config";
    const rerender=(options&&options.rerender)||function(){};
    const {el,detailPanel,detailSection,detailField,readonlyField,infoHelp,clone}=LexeditorUI;
    let config=null,draft=null,busy=false,loaded=false;
    async function load(){
      try{
        const response=await fetch(route);
        const value=await response.json();
        if(!response.ok)throw new Error(value.error||"Could not read Engine Config");
        config=value;
        draft=clone(value.overrides||{});
        loaded=true;
      }catch(error){config={error:error.message||String(error)};draft=null}
      rerender();
    }
    async function ensure(){
      if(loaded)return;
      await load();
    }
    async function action(name,body,done){
      if(busy)return;
      busy=true;rerender();
      try{
        const response=await fetch(`${route}/${name}`,{method:"POST",
          headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});
        const value=await response.json();
        if(!response.ok)throw new Error(value.error||"Engine Config refused that");
        config=value.result;
        draft=clone(value.result.overrides||{});
        if(done)LexeditorUI.showToast?.(typeof done==="function"?done(value.result):done);
      }catch(error){LexeditorUI.showToast?.(error.message||String(error),true)}
      finally{busy=false;rerender()}
    }
    function shownValue(item){
      return draft[item.key]!==undefined?draft[item.key]
        :config.observed&&config.observed[item.key]!==undefined?config.observed[item.key]:"";
    }
    function settingControl(item){
      const disabled=busy;
      const shown=shownValue(item);
      const set=next=>{draft[item.key]=next;rerender()};
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
    function element(){
      if(!config||config.error){
        return detailPanel({title:"ENGINE CONFIG",body:[
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
      if(config.iniUnlocker)fileRows.push(detailField({label:"INI UNLOCKER",
        ...(config.iniUnlocker.verified?{}:{tone:"warning"}),
        control:readonlyField(unlockerText(config.iniUnlocker))}));
      if(config.notes)fileRows.push(detailField({label:"NOTES",control:readonlyField(config.notes)}));
      if(config.externalChange)fileRows.push(detailField({label:"EXTERNAL CHANGE",tone:"warning",
        control:el("div",{class:"lex-reshade-actions"},
          el("button",{type:"button",class:"lex-dialog-action",disabled:busy,
            onclick:()=>action("refresh",{},"Rebased on the current file.")},"Reload status"))}));
      const settingField=item=>{
        const managed=config.overrides&&Object.prototype.hasOwnProperty.call(config.overrides,item.key);
        const legacy=item.managed_by&&item.managed_by!=="unreal-config";
        const help=[item.unverified_note||"",item.description,
          item.restart_required?"Restart the game after changing it.":"Takes effect without a restart on most builds.",
          item.dependencies&&item.dependencies.length?`Related: ${item.dependencies.join(", ")}.`:""
        ].filter(Boolean).join(" ");
        const shown=shownValue(item);
        const controls=legacy
          ?[readonlyField(shown===""?"Game default":String(shown))]
          :[settingControl(item)];
        if(managed&&!legacy)controls.push(el("button",{type:"button",class:"lex-dialog-action",disabled:busy,
          onclick:()=>action("default",{key:item.key},"Back to the game default.")},"Use game default"));
        return detailField({label:(managed?"* ":"")+item.name.toUpperCase()+(item.unverified_note?" (UNVERIFIED)":""),
          dataType:item.type==="float"?"FLOAT":item.type==="choice"?"ENUM":"INT",
          control:el("div",{class:"lex-reshade-actions"},...controls),
          help:infoHelp((legacy?"Managed by another Lexeditor group; change it there. ":managed?"Managed by Lexeditor. ":"")+help)});
      };
      const byGroup=new Map();
      for(const item of config.advanced||[]){
        const title=groupTitle(item.key);
        if(!byGroup.has(title))byGroup.set(title,[]);
        byGroup.get(title).push(settingField(item));
      }
      const settingSections=[...byGroup.entries()]
        .sort(([a],[b])=>groupOrder(a)-groupOrder(b))
        .map(([title,body])=>detailSection({title,body}));
      const saved=config.overrides||{};
      const dirty=JSON.stringify(saved)!==JSON.stringify(draft||{});
      const saveRows=[detailField({label:"SAVE",control:el("div",{class:"lex-reshade-actions"},
        el("button",{type:"button",class:"lex-dialog-action primary",disabled:!dirty||busy,
          onclick:()=>action("apply",{values:draft||{}},"Saved Engine.ini. Restart the game where noted.")},"Save settings"),
        el("button",{type:"button",class:"lex-dialog-action",disabled:!dirty||busy,
          onclick:()=>{draft=clone(saved);rerender()}},"Revert"),
        el("button",{type:"button",class:"lex-dialog-action",disabled:busy||!Object.keys(saved).length,
          onclick:async()=>{const ok=await LexeditorUI.confirmAction({title:"Remove all Engine Config overrides?",
            message:"Removes the Lexeditor block and restores values you had before, where recorded.",confirmLabel:"Remove all"});
            if(ok)action("reset",{},"All overrides removed.")}},"Reset all"))})];
      if(config.backup)saveRows.push(detailField({label:"BACKUP",control:readonlyField(config.backup)}));
      return detailPanel({title:"ENGINE CONFIG",body:[
        detailSection({title:"CONFIG FILE",body:fileRows}),
        ...settingSections,
        detailSection({title:"SAVE",body:saveRows}),
      ]});
    }
    return {element,load,ensure};
  }
  window.LexeditorUnrealConfig={createPanel};
})();
