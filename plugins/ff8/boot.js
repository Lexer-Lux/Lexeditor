  function renderDataMap(){const view=LexeditorUI.dataMap({rows:state.datamap.rows,open:row=>{if(row.filename==="FFNx.toml")state.settingsTab="platform";else if(row.filename.includes("FLYING_EVA"))state.settingsTab="gameplay";if(row.target)navigate(row.target)},query:state.filters.datamap,status:state.filters.mapStatus,page:state.pages.datamap,sort:state.sorts.datamap,pageSize:100,changeQuery:value=>{state.filters.datamap=value;state.pages.datamap=0;renderDataMap()},changeStatus:value=>{state.filters.mapStatus=value;state.pages.datamap=0;renderDataMap()},changePage:page=>{state.pages.datamap=page;renderDataMap()},changeSort:key=>{const [active,direction]=state.sorts.datamap;state.sorts.datamap=[key,active===key?-direction:1];renderDataMap()}});state.pages.datamap=view.page;$("#toolbar").replaceChildren(...view.controls);$("#main").replaceChildren(view.content)}
  function renderDashboard(){
    const toolbar=$("#toolbar");toolbar.replaceChildren();toolbar.hidden=true;
    const dashboard=state.dashboard,runtime=dashboard.runtime,baseline=dashboard.baseline,game=dashboard.game;
    const openFolder=async()=>{try{if(!await openGameFolder("ff8"))throw new Error("Open this page in the Lexeditor desktop app to use Windows Explorer.")}catch(error){showAlert({title:"Could not open game folder",message:error.message||String(error)})}};
    const value=text=>readonlyField(String(text??""),{format:false});
    const body=[
      detailSection({title:"GAME",body:[
        detailField({label:"STATE",control:value(game.ready?"Ready":"Needs attention"),
          help:infoHelp(game.ready?"Ready means Lexeditor found the configured FF8 installation and can read the game files this editor depends on.":"Not ready means one or more required FF8 paths or files are missing or unreadable; the reported installation problems identify the concrete cause.")}),
        detailField({label:"FOLDER",control:LexeditorUI.choiceField(value(game.root),el("button",{type:"button",title:"Open the game folder","aria-label":"Open the game folder",onclick:openFolder},"Open"))}),
        detailField({label:"EXECUTABLE",control:value(game.executable)}),
      ]}),
      detailSection({title:"GAME DATA",body:[
        detailField({label:"STATE",control:value(baseline.ready?"Ready":"Not ready"),help:infoHelp(baseline.message)}),
        detailField({label:"FILES",control:value(baseline.fileCount?formatNumber(baseline.fileCount):"0")}),
      ]}),
      detailSection({title:"FFNX",body:[
        detailField({label:"STATE",control:value(runtime.installed?"Installed":"Not installed"),help:infoHelp(runtime.message||"")}),
        detailField({label:"VERSION",control:value(runtime.version||"—")}),
      ]}),
      detailSection({title:"EDITOR",body:[
        detailField({label:"SHOW NEW GAME TAB",control:newGameToggle(),help:infoHelp("Show the New Game tab, which edits starting gil, GFs, characters, Magic and items. It stays hidden unless this is on, because most editing never touches starting data. Changing this reloads the editor.")}),
      ]}),
    ];
    body.push(LexeditorUI.modLoaderSection({
      loader:"FFNx, the community runtime for the PC release. It loads from the game folder and applies Lexeditor's data with its own patches.",
      output:"Edited kernel, field, battle and executable data is written into the selected project folder, which FFNx reads.",
      order:"FFNx applies its configuration first, then mod data. Two mods editing the same kernel section conflict; the later one wins.",
      safety:"Installed game archives are read only. Every write goes to the project copy, and extracted source data is kept separately.",
      removal:"Point FFNx away from the project folder, or delete it. The install is already untouched.",
    }));
    body.push(LexeditorUI.creditsPanel("ff8"));
    if(LexeditorUI.sharedSettings()?.developerMode){
      body.push(detailSection({title:"PLUGIN SFX",body:[LexeditorUI.soundCoverageTable(dashboard.themeSounds?.rows||[])]}));
    }
    $("#main").replaceChildren(detailPanel({className:"lex-information-panel ff8-information",
      icon:infoIcon(),title:"Information",meta:"Installation, extracted game data, and the FFNx helper",body}));
  }
  function newGameToggle(){
    const input=el("input",{type:"checkbox",checked:state.editorSettings?.showNewGame===true,"aria-label":"Show New Game tab",onchange:async event=>{
      if(dirtyCount()){event.target.checked=!event.target.checked;showAlert({title:"Save or discard first",message:"The editor reloads to show or hide the New Game tab. Save or discard the pending changes, then flip this again."});return}
      try{state.editorSettings=await api("/api/editor-settings/save",post({showNewGame:event.target.checked}));location.reload()}
      catch(error){event.target.checked=!event.target.checked;showAlert({title:"Could not save the editor setting",message:error.message||String(error)})}
    }});
    return input;
  }
  const settingsPayload=()=>({flyingEvaBonus:state.data.settings.flyingEvaBonus,flyingEvaEnabled:state.data.settings.flyingEvaEnabled,autoSortInventory:state.data.settings.autoSortInventory,autoSortMagic:state.data.settings.autoSortMagic,enhancedAbilityMenu:state.data.settings.enhancedAbilityMenu,singleGf:state.data.settings.singleGf,gfSpellbooksEnabled:state.data.settings.gfSpellbooksEnabled,fixedCommandMenu:state.data.settings.fixedCommandMenu,universalItem:state.data.settings.universalItem,scannedTargetScan:state.data.settings.scannedTargetScan,partySwitch:state.data.settings.partySwitch,drawOncePerEnemy:state.data.settings.drawOncePerEnemy,streamlinedDraw:state.data.settings.streamlinedDraw,formulaeRework:state.data.settings.formulaeRework,trueAtbWait:state.data.settings.trueAtbWait,betterTargeting:state.data.settings.betterTargeting,modernControls:state.data.settings.modernControls,worldMapFullscreen:state.data.settings.worldMapFullscreen,battleResultsHelp:state.data.settings.battleResultsHelp,gfAcquisitionRework:state.data.settings.gfAcquisitionRework,vibrationConsolidation:state.data.settings.vibrationConsolidation,sharedMagicInventory:state.data.settings.sharedMagicInventory,damageLimitRemoval:state.data.settings.damageLimitRemoval,betterCard:state.data.settings.betterCard,fastStart:state.data.settings.fastStart,xpBars:state.data.settings.xpBars,hpBars:state.data.settings.hpBars,betterHpColors:state.data.settings.betterHpColors,gfHpBars:state.data.settings.gfHpBars,inGameTime:state.data.settings.inGameTime,interactionIndicators:state.data.settings.interactionIndicators,noMagicConsumption:state.data.settings.noMagicConsumption,gfHpCasting:state.data.settings.gfHpCasting,gfHpCastingCosts:state.data.settings.gfHpCastingCosts,dropsAfterMug:state.data.settings.dropsAfterMug,dropChance:state.data.settings.dropChance,flatStatAbilities:state.data.settings.flatStatAbilities,maxSpellEnabled:state.data.settings.maxSpellEnabled,maxSpell:state.data.settings.maxSpell,sfxVolume:state.data.settings.sfxVolume,musicVolume:state.data.settings.musicVolume});
  function renderGameplaySettings(){
    if(state.activeSource!=="mine"){$("#main").replaceChildren(LexeditorUI.notice({message:"Vanilla uses no Lexeditor gameplay tweaks. Select a mod to configure Tweaks."}));return}
    const settings=state.data.settings;
    const flying=numberControl(settings.flyingEvaBonus,settings.minimum,settings.maximum,1,value=>settings.flyingEvaBonus=value,{"aria-label":"Flying EVA Bonus"});
    const flyingEnabled=el("input",{type:"checkbox",checked:settings.flyingEvaEnabled,"aria-label":"Enable Flying EVA Bonus",onchange:event=>{settings.flyingEvaEnabled=event.target.checked;shell.refresh()}});
    const singleGf=el("input",{type:"checkbox",checked:settings.singleGf,"aria-label":"Monogamy",onchange:event=>{settings.singleGf=event.target.checked;shell.refresh()}});
    const gfSpellbooks=el("input",{type:"checkbox",checked:settings.gfSpellbooksEnabled,"aria-label":"GF Spellbooks",onchange:event=>{settings.gfSpellbooksEnabled=event.target.checked;shell.refresh()}});
    const autoSort=el("input",{type:"checkbox",checked:settings.autoSortInventory,"aria-label":"Auto-sort Inventory",onchange:event=>{settings.autoSortInventory=event.target.checked;shell.refresh()}});
    const autoSortMagic=el("input",{type:"checkbox",checked:settings.autoSortMagic,"aria-label":"Auto-sort Magic Menu",onchange:event=>{settings.autoSortMagic=event.target.checked;shell.refresh()}});
    const enhancedAbilityMenu=el("input",{type:"checkbox",checked:settings.enhancedAbilityMenu,"aria-label":"Enhanced Ability Menu",onchange:event=>{settings.enhancedAbilityMenu=event.target.checked;shell.refresh()}});
    const universalItem=el("input",{type:"checkbox",checked:settings.universalItem,"aria-label":"Universal Item",onchange:event=>{settings.universalItem=event.target.checked;shell.refresh()}});
    const scannedTargetScan=el("input",{type:"checkbox",checked:settings.scannedTargetScan,disabled:!settings.enhancedScanAvailable,"aria-label":"Enhanced Scan",onchange:event=>{settings.scannedTargetScan=event.target.checked;shell.refresh()}});
    const partySwitch=el("input",{type:"checkbox",checked:settings.partySwitch,disabled:!settings.partySwitchAvailable,"aria-label":"FF10-style Party Switch",onchange:event=>{settings.partySwitch=event.target.checked;shell.refresh()}});
    const drawOnce=el("input",{type:"checkbox",checked:settings.drawOncePerEnemy,"aria-label":"Draw Once per Enemy",onchange:event=>{settings.drawOncePerEnemy=event.target.checked;shell.refresh()}});
    const streamlinedDraw=el("input",{type:"checkbox",checked:settings.streamlinedDraw,"aria-label":"Streamlined Draw",onchange:event=>{settings.streamlinedDraw=event.target.checked;shell.refresh()}});
    const fixedCommandMenu=el("input",{type:"checkbox",checked:settings.fixedCommandMenu,disabled:!settings.singleGf,"aria-label":"Command Menu Rework",onchange:event=>{settings.fixedCommandMenu=event.target.checked;shell.refresh()}});
    const trueAtbWait=el("input",{type:"checkbox",checked:settings.trueAtbWait,"aria-label":"True ATB Wait",onchange:event=>{settings.trueAtbWait=event.target.checked;shell.refresh()}});
    const modernControls=el("input",{type:"checkbox",checked:settings.modernControls,disabled:!settings.modernControlsAvailable,"aria-label":"Modern Controls",onchange:event=>{settings.modernControls=event.target.checked;shell.refresh()}});
    // How fast the right stick turns the battle camera, as a multiple of the
    // shipped rate. It belongs to this tweak, so it sits in this row rather
    // than becoming a tweak of its own that does nothing on its own.
    const cameraSpeed=numberControl(settings.cameraSpeed,settings.cameraSpeedMinimum,settings.cameraSpeedMaximum,0.1,value=>{settings.cameraSpeed=value},{"aria-label":"Battle camera speed"});
    const modernControlsControl=LexeditorUI.actionRow(modernControls,unitField(cameraSpeed,"×"));
    const worldMapFullscreen=el("input",{type:"checkbox",checked:settings.worldMapFullscreen,disabled:!settings.modernControls||!settings.worldMapFullscreenAvailable,"aria-label":"Full-screen World Map",onchange:event=>{settings.worldMapFullscreen=event.target.checked;shell.refresh()}});
    const battleResultsHelp=el("input",{type:"checkbox",checked:settings.battleResultsHelp,disabled:!settings.battleResultsHelpAvailable,"aria-label":"Battle Results Item Help",onchange:event=>{settings.battleResultsHelp=event.target.checked;shell.refresh()}});
    const gfAcquisitionRework=el("input",{type:"checkbox",checked:settings.gfAcquisitionRework,disabled:!settings.gfAcquisitionReworkAvailable,"aria-label":"GF Acquisition Rework",onchange:event=>{settings.gfAcquisitionRework=event.target.checked;shell.refresh()}});
    const vibrationConsolidation=el("input",{type:"checkbox",checked:settings.vibrationConsolidation,"aria-label":"Vibration Rationalization",onchange:event=>{settings.vibrationConsolidation=event.target.checked;shell.refresh()}});
    const betterTargeting=el("input",{type:"checkbox",checked:settings.betterTargeting,"aria-label":"Better Targeting",onchange:event=>{settings.betterTargeting=event.target.checked;shell.refresh()}});
    const damageLimitRemoval=el("input",{type:"checkbox",checked:settings.damageLimitRemoval,"aria-label":"Remove Damage Limit",onchange:event=>{settings.damageLimitRemoval=event.target.checked;shell.refresh()}});
    const betterCard=el("input",{type:"checkbox",checked:settings.betterCard,"aria-label":"Better Card",onchange:event=>{settings.betterCard=event.target.checked;shell.refresh()}});
    const fastStart=el("input",{type:"checkbox",checked:settings.fastStart,"aria-label":"Fast Start",onchange:event=>{settings.fastStart=event.target.checked;shell.refresh()}});
    const xpBars=el("input",{type:"checkbox",checked:settings.xpBars,"aria-label":"XP Bars",onchange:event=>{settings.xpBars=event.target.checked;shell.refresh()}});
    const hpBars=el("input",{type:"checkbox",checked:settings.hpBars,"aria-label":"HP Bars",onchange:event=>{settings.hpBars=event.target.checked;shell.refresh()}});
    const betterHpColors=el("input",{type:"checkbox",checked:settings.betterHpColors,"aria-label":"Better HP Colors",onchange:event=>{settings.betterHpColors=event.target.checked;shell.refresh()}});
    const gfHpBars=el("input",{type:"checkbox",checked:settings.gfHpBars,disabled:!settings.singleGf,"aria-label":'GF "MP" Bars',onchange:event=>{settings.gfHpBars=event.target.checked;shell.refresh()}});
    const inGameTime=el("input",{type:"checkbox",checked:settings.inGameTime,"aria-label":"In-game Time",onchange:event=>{settings.inGameTime=event.target.checked;shell.refresh()}});
    const interactionIndicators=el("input",{type:"checkbox",checked:settings.interactionIndicators,"aria-label":"Interaction Indicators",onchange:event=>{settings.interactionIndicators=event.target.checked;shell.refresh()}});
    const noMagicConsumption=el("input",{type:"checkbox",checked:settings.noMagicConsumption,"aria-label":"No Magic Consumption",onchange:event=>{settings.noMagicConsumption=event.target.checked;shell.refresh()}});
    const gfHpCasting=el("input",{type:"checkbox",checked:settings.gfHpCasting,disabled:!settings.singleGf||!settings.noMagicConsumption,"aria-label":"GF HP Casting",onchange:event=>{settings.gfHpCasting=event.target.checked;shell.refresh()}});
    const dropsAfterMug=el("input",{type:"checkbox",checked:settings.dropsAfterMug,"aria-label":"Drops After Mug",onchange:event=>{settings.dropsAfterMug=event.target.checked;shell.refresh()}});
    const dropChance=el("input",{type:"checkbox",checked:settings.dropChance,"aria-label":"Drop Chance Rework",onchange:event=>{settings.dropChance=event.target.checked;shell.refresh()}});
    const sharedMagic=el("input",{type:"checkbox",checked:settings.sharedMagicInventory,disabled:!settings.sharedMagicInventoryAvailable&&!settings.sharedMagicInventory,"aria-label":"Shared Party Magic Inventory",onchange:event=>{settings.sharedMagicInventory=event.target.checked;shell.refresh()}});
    const flatStatAbilities=el("input",{type:"checkbox",checked:settings.flatStatAbilities,"aria-label":"Flat +Stat Abilities",onchange:event=>{settings.flatStatAbilities=event.target.checked;shell.refresh()}});
    // The Formulae page lives under Tweaks now, so its owning toggle lives
    // here with the other tweaks. It stays unavailable until every row in the
    // central Formulae Rework contract has a real runtime patch, and the
    // Formulae subtab unlocks only while this tweak is enabled.
    const formulaeRework=el("input",{type:"checkbox",checked:settings.formulaeRework,disabled:state.activeSource!=="mine"||!settings.formulaeReworkAvailable,"aria-label":"Formulae Rework",onchange:event=>{settings.formulaeRework=event.target.checked;shell.refresh();renderSettings()}});
    const maxSpellEnabled=el("input",{type:"checkbox",checked:settings.maxSpellEnabled,"aria-label":"Enable Max Spell",onchange:event=>{settings.maxSpellEnabled=event.target.checked;shell.refresh()}});
    const maxSpellValue=numberControl(settings.maxSpell,settings.maxSpellMinimum,settings.maxSpellMaximum,1,value=>settings.maxSpell=value,{"aria-label":"Maximum spell stock"});
    // Issue #498: an unmanaged side (null) shows 100, the game's normal
    // level, without arming the gain. Touching a slider stores a real
    // 0-100 gain that launch writes to that layer's FFNx.toml key.
    const sfxVolume=numberControl(settings.sfxVolume ?? 100,settings.audioVolumeMinimum,settings.audioVolumeMaximum,1,value=>settings.sfxVolume=value,{"aria-label":"SFX volume"});
    const musicVolume=numberControl(settings.musicVolume ?? 100,settings.audioVolumeMinimum,settings.audioVolumeMaximum,1,value=>settings.musicVolume=value,{"aria-label":"Music volume"});
    const row=(title,description,control)=>{
      const toggle=control.matches?.('input[type="checkbox"]')?control:control.querySelector?.('input[type="checkbox"]');
      if(toggle&&toggle!==control)toggle.remove();
      return detailPanel({title,help:description,actions:toggle,
        body:control===toggle?[]:detailField({label:"",control})});
    };
    // The number is a percentage of effective EVA, so it carries its unit. A
    // bare number here reads as flat points and the row label alone does not
    // say which.
    const flyingControl=LexeditorUI.actionRow(flyingEnabled,unitField(flying,"% EVA"));
    const maxSpellControl=LexeditorUI.actionRow(maxSpellEnabled,maxSpellValue);
    const view=el("section",{class:"settings-view"},
      row("AUTO-SORT INVENTORY","Sorts the inventory before the Item screen opens, then runs the normal Item-screen initialization.",autoSort,"boolean"),
      row("AUTO-SORT MAGIC MENU","Uses the Attack, Restore, Indirect order for every character when the Magic menu opens.",autoSortMagic,"boolean"),
      row("BETTER CARD","Removes enemies that cannot become cards from Card targeting and disables Card when no valid target exists.",betterCard,"boolean"),
      row("BETTER TARGETING","Removes the red Target labels.",betterTargeting,"boolean"),
      row("COMMAND MENU REWORK","Gives each character the fixed four-slot command layout. Requires Monogamy.",fixedCommandMenu,"boolean"),
      row("DRAW ONCE PER ENEMY","After any party member successfully Draws from an enemy instance, that enemy cannot be Drawn from again during that battle.",drawOnce,"boolean"),
      row("DROP CHANCE REWORK",dropChanceDescription(),dropChance,"boolean"),
      row("DROPS AFTER MUG","A successfully Mugged enemy still rolls its normal death drops. Mugging the same enemy twice remains prohibited; its item-slot distribution follows the current Drop Chance setting.",dropsAfterMug,"boolean"),
      row("ENHANCED ABILITY MENU","Shows unfinished GF abilities first, orders each group by name, and dims completed abilities.",enhancedAbilityMenu,"boolean"),
      row("ENHANCED SCAN","Card Game opens Scan target selection without requiring or consuming Scan Magic and without spending the active character's turn.",scannedTargetScan,"boolean"),
      row("FAST START","Skips the Square Enix logo movie and the opening credits, then uses the game's normal transition into the main menu.",fastStart,"boolean"),
      row("FF10-STYLE PARTY SWITCH","Look Left opens the reserve-party selector during an active turn. Confirming a replacement spends that turn.",partySwitch,"boolean"),
      row("FLAT +STAT ABILITIES","Changes +Stat% abilities into fixed-point +Stat abilities and updates their in-game names and descriptions.",flatStatAbilities,"boolean"),
      row("FORMULAE REWORK","Uses Lexer's reworked battle formulae and unlocks the Formulae subtab. Only healing and physical accuracy have runtime patches today; melee damage, magic damage, status infliction and Mug remain preview-only, so the toggle stays unavailable until every listed formula has a guarded game patch.",formulaeRework,"boolean"),
      row("FLYING EVA BONUS","Adds the selected effective EVA to intrinsic flying targets against grounded melee attacks. A hit rate of 255 does not bypass it.",flyingControl,"value-toggle"),
      row("FULL-SCREEN WORLD MAP",settings.worldMapFullscreenAvailable?"R1 opens the full-screen map from the world map; L1 opens the Journal. The base is the game's own world-map textures, always visible. Location names appear once discovered or Journal-revealed, and selecting a location sets a waypoint only. Requires Modern Controls.":settings.worldMapFullscreenBlocker,worldMapFullscreen,"boolean"),
      row("BATTLE RESULTS ITEM HELP",settings.battleResultsHelpAvailable?"The battle reward screen shows Item, Quantity and Help columns so every received item's help text is visible at once, using current item text including mod edits.":settings.battleResultsHelpBlocker,battleResultsHelp,"boolean"),
      row("GF HP CASTING","Battle Magic spends the spell’s GF HP cost instead of spell stock. Set costs in Magic → Attack Data. Requires Monogamy and No Magic Consumption. A character without a GF or enough GF HP cannot cast.",gfHpCasting,"boolean"),
      row("GF ACQUISITION REWORK",settings.gfAcquisitionReworkAvailable?"Awards drawable GFs automatically on winning their vanilla boss fight instead of through Draw, with missed GFs recovered at their Disc 4 boss. Ordinary spell Draw is unaffected, and disabling keeps acquired GFs.":settings.gfAcquisitionReworkBlocker,gfAcquisitionRework,"boolean"),
      row('GF "MP" BARS',"Shows a blue bar above each party name for the junctioned GF's HP, which is spent like MP, including damage it takes while being summoned. Requires Monogamy. With more than one GF junctioned the bar is hidden and the FFNx log says why.",gfHpBars,"boolean"),
      row("HP BARS","Shows thin red HP bars below the active party's HP numbers in the main menu and in battle. The lost part is black.",hpBars,"boolean"),
      row("BETTER HP COLORS","Smoothly blends living HP numbers from white at full HP through yellow at 50% and orange at 25% toward red near zero. KO keeps FF8's vanilla display. Applies in battle and the verified shared character menu panels where FF8 already recolours HP.",betterHpColors,"boolean"),
      row("IN-GAME TIME","Shows your computer's local clock where the main menu shows play time. It does not replace FF8's saved play-time counter: that keeps counting, and timed events still measure against it.",inGameTime,"boolean"),
      row("INTERACTION INDICATORS","Shows a fixed HUD cue when the field interaction selector has a target. Card-capable Talk scripts add a distinct CARD cue. It never presses a button or starts the interaction for you.",interactionIndicators,"boolean"),
      row("MAX SPELL","Sets the maximum stock for each spell. A full stack keeps the same junction effect as 100 spells in vanilla.",maxSpellControl,"value-toggle"),
      row("MODERN CONTROLS",settings.modernControlsBlocker||el("div",{},el("p",{},"Modern bindings for battle and the world map. The number is the camera turn rate as a multiple of the shipped speed, from 0.2 to 4."),el("ul",{class:"tweak-bindings"},el("li",{},"Right stick: turns the battle camera while it is idle, and rotates the world map camera. Up tilts the view up. The camera stops level with what it looks at."),el("li",{},"RT / R2 / left mouse button: fire. The gunblade trigger, and Irvine's shots."),el("li",{},"LT / L2 / right mouse button: hold to flee."),el("li",{},"B / Circle / Backspace: end Irvine's Shot early."),el("li",{},"RT and LT on the world map: accelerate and reverse vehicles."))),modernControlsControl,"value-toggle"),
      row("MONOGAMY","Allows one GF on each character. Warning: when gameplay starts, any character who already has several GFs junctioned will have all of those GFs unequipped.",singleGf,"boolean"),
      row("GF SPELLBOOKS","Uses the ordered spell pages configured under GFs → Spellbook. Requires Monogamy on and Shared Party Magic Inventory off. Turning this off preserves your pages.",gfSpellbooks,"boolean"),
      row("MUSIC VOLUME","Sets the music gain this mod requests from FFNx, from 0 (silent) to 100 (full). Sound effects are untouched. The gain is written to FFNx.toml when the game launches; 100 matches the game's normal level.",unitField(musicVolume,"%")),
      row("NO MAGIC CONSUMPTION","Casting spells in battle or from the field Magic menu keeps their stock. Items, discarding and other inventory operations are unchanged; works with Shared Magic and Max Spell.",noMagicConsumption,"boolean"),
      row("REMOVE DAMAGE LIMIT","Uses FF8's existing 60,000-damage path instead of the normal 9,999 cap.",damageLimitRemoval,"boolean"),
      row("SFX VOLUME","Sets the sound-effects gain this mod requests from FFNx, from 0 (silent) to 100 (full). Music is untouched. The gain is written to FFNx.toml when the game launches; 100 matches the game's normal level.",unitField(sfxVolume,"%")),
      row("SHARED PARTY MAGIC INVENTORY","Uses one lossless 32-slot Magic pool for the party. Works with Party Switch and the selected Max Spell cap. If existing stocks cannot merge without loss, the game keeps them unchanged and disables sharing for that launch; details are written to FFNx.shared-magic.log.",sharedMagic,"boolean"),
      row("STREAMLINED DRAW","Skips the spell list when only one spell is available and submits the native Stock action directly.",streamlinedDraw,"boolean"),
      row("TRUE ATB WAIT","Works only when the game is set to ATB Wait mode. Stops all party and enemy ATB filling while any party member is ready to act. Active mode keeps its normal behavior.",trueAtbWait,"boolean"),
      row("UNIVERSAL ITEM","Look Right opens the normal battle Item menu without using an equipped command slot. The shortcut follows the configured input mapping.",universalItem,"boolean"),
      row("VIBRATION RATIONALIZATION","Start uses the normal field and battle pause behavior instead of FFNx's separate vibration screen.",vibrationConsolidation,"boolean"),
      row("XP BARS","Shows thin yellow XP bars below character and GF level rows, including the active and reserve party in the main menu, and on the post-battle report.",xpBars,"boolean"));
    const settingsView=LexeditorUI.settingsColumns([...view.children],tweakTabProps());
    $("#main").replaceChildren(settingsView);
    bindSettingDependencies(settingsView,[{
      key:"singleGf->fixedCommandMenu",
      dependency:singleGf,
      dependent:fixedCommandMenu,
    },{key:"singleGf->gfHpBars",dependency:singleGf,dependent:gfHpBars},{key:"singleGf->gfHpCasting",dependency:singleGf,dependent:gfHpCasting},{key:"noMagicConsumption->gfHpCasting",dependency:noMagicConsumption,dependent:gfHpCasting}]);
  }

  async function loadReshade(){
    try{const value=await LexeditorUI.callWindow?.("mod_reshade","ff8");if(value)state.reshade=value}
    catch(_error){/* browser preview has no desktop host; the page names it below */}
  }
  async function actReshade(method,...args){
    try{const value=await LexeditorUI.callWindow?.(method,"ff8",...args);if(value)state.reshade=value;else await loadReshade()}
    catch(error){LexeditorUI.showToast?.(error.message||String(error),true)}
    renderSettings();
  }
  async function renderReshade(){
    if(!state.reshade)await loadReshade();
    const section=LexeditorUI.reshadeSection({snapshot:state.reshade,act:actReshade});
    const body=section||LexeditorUI.notice({message:"Open this page in the Lexeditor desktop app to manage ReShade."});
    $("#main").replaceChildren(LexeditorUI.settingsColumns([body],tweakTabProps()));
  }
  function renderPlatformSettings(){
    $("#main").replaceChildren(platformConfigView({config:state.platformConfig,showHeader:false,query:state.platformQuery,...tweakTabProps(),disabled:state.activeSource!=="mine",search:value=>{state.platformQuery=value},change:(id,value)=>{const field=(state.platformConfig?.sections||[]).flatMap(section=>section.fields).find(candidate=>candidate.id===id);if(field){field.value=value;shell.refresh()}}}));
  }
  function dropChanceDescription(){
    // Weights out of 256, from drop_chance.py.
    const vanilla={normal:[178,51,15,12],rare:[128,114,14,0]},rework={normal:[137,68,34,17],rare:[94,70,53,39]};
    const percent=value=>`${(value/256*100).toFixed(1)}%`;
    const change=(before,after)=>LexeditorUI.badge(`${percent(before)} → ${percent(after)}`,{tone:before===0?"warning":""});
    return el("div",{},
      el("p",{},el("strong",{},"Fixes a vanilla bug: "),"with the Rare Item ability, the fourth loot slot - usually the rarest item an enemy has - can never drop or be Mugged. The rework makes it reachable again and evens out the odds of the rarer slots, with and without Rare Item."),
      columnList({class:"drop-chance-table","aria-label":"Drop Chance slot probabilities, vanilla to rework",
        rows:[0,1,2,3].map(index=>({key:index,slot:index+1,normal:index,rare:index})),
        key:entry=>entry.key, localSort:false, template:'48px minmax(0,1fr) minmax(0,1fr)',
        columns:[{key:"slot",label:"Slot"},
          {key:"normal",label:"Normal",render:entry=>change(vanilla.normal[entry.slot-1],rework.normal[entry.slot-1])},
          {key:"rare",label:"Rare Item",render:entry=>change(vanilla.rare[entry.slot-1],rework.rare[entry.slot-1])}]}));
  }
  const TWEAK_TABS=[{id:"gameplay",label:"Gameplay"},{id:"formulae",label:"Formulae"},{id:"platform",label:"FFNx"},{id:"reshade",label:"ReShade"}];
  const tweakTabProps=()=>({tabs:TWEAK_TABS.map(tab=>tab.id==="formulae"?{...tab,disabled:!state.data.settings.formulaeRework}:tab),activeTab:state.settingsTab,
    tabsLabel:"Tweak settings",
    changeTab:value=>{state.settingsTab=value;renderSettings()}});
  function renderSettings(){
    const toolbar=$("#toolbar");toolbar.replaceChildren();toolbar.hidden=true;
    // The Formulae subtab unlocks only while its owning tweak is enabled; without it, fall back to the Gameplay list that owns the toggle.
    if(state.settingsTab==="formulae"&&!state.data.settings.formulaeRework)state.settingsTab="gameplay";
    if(state.settingsTab==="platform")renderPlatformSettings();else if(state.settingsTab==="formulae")renderFormulae();else if(state.settingsTab==="reshade")renderReshade();else renderGameplaySettings();
  }

  const DEFAULT_FLYING_EVA_BONUS=25;
  function formulaInput(label,key,min,max,step=1){return detailField({label,control:numberControl(state.formula[key],min,max,step,value=>{state.formula[key]=value})})}
  function renderFormulae(){
    const toolbar=$("#toolbar");toolbar.replaceChildren();toolbar.hidden=true;
    const f=state.formula,weapons=state.data.weapons?.rows||[],settings=state.data.settings;
    if(!weapons.some(row=>Number(row.id)===Number(f.weaponId)))f.weaponId=weapons[0]?.id??0;
    const weapon=weapons.find(row=>Number(row.id)===Number(f.weaponId)),weaponField=name=>weapon?.fields?.find(field=>field.field===name),fieldValue=name=>Number(weaponField(name)?.value??0);
    // The owning toggle lives in the Tweaks Gameplay list; this subtab unlocks
    // only while it is enabled, so no second toggle lives here.
    const preset=()=>detailField({label:"Weapon preset",control:selectControl(f.weaponId,weapons.map(row=>({id:row.id,name:row.name})),value=>{f.weaponId=value;renderFormulae()})});
    const formulaTerm=(name,label,help)=>{const field=weaponField(name);return field?detailField({label,help:infoHelp(help),control:fieldSourceControl(field,"weapons",weapon.id)}):null};
    const boost=()=>state.data.settings.flyingEvaEnabled?state.data.settings.flyingEvaBonus:0;
    const calculate=()=>{const strength=Math.min(255,Math.max(0,Math.trunc(Number(f.strength)+fieldValue("str_bonus")))),inner=Math.trunc((265-Number(f.vitality))*(strength+Math.trunc(strength*strength/16))/256),middle=Math.max(0,Math.trunc(fieldValue("attack_power")*inner/16)),low=Math.max(0,Math.trunc(middle*240/256)),average=Math.max(0,middle),high=Math.max(0,Math.trunc(middle*272/256)),flyingPenalty=f.flying&&Boolean(fieldValue("melee"))&&!f.float?boost():0,luckTerm=settings.formulaeRework?Number(f.luck):Math.floor(Number(f.luck)/2),effective=Math.max(0,Math.min(100,fieldValue("hit_rate")+luckTerm-Number(f.eva)-Number(f.targetLuck)-flyingPenalty)),chance=Math.max(0,Math.min(100,(Math.floor(255*effective/100)+1)/256*100));return{low,average,high,flyingPenalty,chance}};
    const checkbox=(label,key)=>detailField({label,control:el("input",{type:"checkbox",checked:f[key],onchange:event=>{f[key]=event.target.checked;updateOutputs()}})});
    const damageOutput=LexeditorUI.detailNote(""),accuracyOutput=LexeditorUI.detailNote("");
    const section=(title,body)=>detailSection({title,body});
    const damage=section("PHYSICAL DAMAGE",[
      preset(),section("FORMULA",[
        LexeditorUI.mathFormula("STR = min(255, attacker STR + weapon STR bonus)"),
        LexeditorUI.mathFormula("DAMAGE = floor(POWER * floor((265 - VIT) * (STR + floor(STR^2 / 16)) / 256) / 16) * RANDOM / 256"),
        LexeditorUI.detailNote("RANDOM = 240 to 272")]),
      section("EDITABLE FORMULA TERMS",[
        formulaTerm("attack_power","Weapon attack power","The selected weapon's stored attack power."),
        formulaTerm("str_bonus","Weapon STR bonus","The selected weapon's stored Strength bonus.")]),
      section("PREVIEW INPUTS",[formulaInput("Attacker STR","strength",0,255),formulaInput("Target VIT","vitality",0,255)]),damageOutput]);
    const flyingTerm=sourceControl(unitField(numberControl(boost(),0,100,1,value=>state.data.settings.flyingEvaBonus=value),"%"),()=>state.data.settings.flyingEvaBonus,DEFAULT_FLYING_EVA_BONUS,[],value=>state.data.settings.flyingEvaBonus=Number(value),value=>`${formatNumber(value)}%`);
    const accuracyLuck=settings.formulaeRework?"attacker LUCK":"floor(attacker LUCK / 2)";
    const accuracy=section("PHYSICAL ACCURACY",[
      preset(),LexeditorUI.detailNote("A hit rate of 255 receives no bypass."),
      section("FORMULA",[
        LexeditorUI.mathFormula(`EFFECTIVE = clamp(hit rate + ${accuracyLuck} - target EVA - target LUCK - flying penalty, 0, 100)`),
        LexeditorUI.mathFormula("HIT CHANCE = (floor(255 * EFFECTIVE / 100) + 1) / 256 * 100%")]),
      section("EDITABLE FORMULA TERMS",[
        formulaTerm("hit_rate","Weapon hit rate","Weapon accuracy contributes directly to effective hit chance before target Evasion and Luck; FF8's special 255 value uses the always-hit bypass."),
        formulaTerm("melee","Melee weapon","Marks the attack as close-range for this formula; grounded melee attacks take the flying-target accuracy penalty."),
        detailField({label:"Flying EVA bonus",help:infoHelp("This penalty applies to grounded melee attackers when the target is flying."),control:flyingTerm})]),
      section("PREVIEW INPUTS",[formulaInput("Attacker LUCK","luck",0,255),formulaInput("Target EVA","eva",0,255),formulaInput("Target LUCK","targetLuck",0,255),checkbox("Target is flying","flying"),checkbox("Attacker has Float","float")]),accuracyOutput]);
    function updateOutputs(){const value=calculate();damageOutput.textContent=`DAMAGE: ${formatNumber(value.low)} TO ${formatNumber(value.high)} · AVERAGE ${formatNumber(value.average)}`;accuracyOutput.textContent=`FLYING PENALTY: ${formatNumber(value.flyingPenalty)}% · HIT CHANCE: ${formatNumber(value.chance,{maximumFractionDigits:1})}%`}
    // The backend owns the complete requested inventory and each row's runtime
    // status. A formula cannot disappear from this page merely because its native
    // implementation is unfinished.
    const formulaRows=settings.formulaeReworkFormulas||[];
    const reworkCard=formula=>detailSection({title:`${String(formula.name||formula.id).toUpperCase()} · ${formula.status==="implemented"?"IMPLEMENTED":"INCOMPLETE"}`,
      attrs:{"data-formula-id":formula.id},body:[
        section("REWORKED",LexeditorUI.mathFormula(formula.replacement||"Not specified")),
        section("VANILLA",LexeditorUI.mathFormula(formula.vanilla||"Not documented")),
        formula.blocker?LexeditorUI.detailNote(`INCOMPLETE: ${formula.blocker}`):null].filter(Boolean)});
    const implementedCount=formulaRows.filter(formula=>formula.status==="implemented").length;
    const master=section("FORMULAE REWORK",[
      LexeditorUI.detailNote("The Formulae Rework tweak in the Gameplay list owns this page. It stays unavailable until every listed formula has a guarded game patch."),
      LexeditorUI.detailNote(`${implementedCount}/${formulaRows.length} requested runtime formulae are implemented.`)])
    const view=LexeditorUI.stack({fill:false},master,LexeditorUI.tileGrid([damage,accuracy,...formulaRows.map(reworkCard)],{minWidth:450}));
    view.addEventListener("input",()=>requestAnimationFrame(updateOutputs));updateOutputs();
    // The stacked damage, accuracy and per-formula cards run taller than the
    // main region, and this plugin clips #main, so the page needs the shared
    // tweaks scroll container; without it the lowest cards render below the
    // window with no way to reach them.
    // The Tweaks subtab bar sits above the scroll container, matching the Gameplay and FFNx lists, so the viewer can leave this subtab again.
    const tweaks=tweakTabProps(),scroller=el("div",{class:"lex-tweaks-scroll",tabindex:"-1"},detailPanel({heading:false,body:view}));
    $("#main").replaceChildren(subtabBar({tabs:tweaks.tabs,active:"formulae",label:tweaks.tabsLabel,change:tweaks.changeTab}),scroller);
  }

  function startingDataEdits(){const edits=[],current=state.data.init,before=state.base.init;if(!current||!before)return edits;for(const kind of ["general","config"])current[kind].fields.forEach((field,index)=>{if(field.value!==before[kind].fields[index].value)edits.push({kind,id:0,field:field.field,value:field.value})});for(const [key,kind] of [["gfs","gf"],["characters","character"]])for(const row of current[key].rows){const base=before[key].rows.find(value=>value.id===row.id);row.fields.forEach((field,index)=>{if(field.value!==base.fields[index].value)edits.push({kind,id:row.id,field:field.field,value:field.value})});if(kind==="character")row.magics.forEach((slot,index)=>{const old=base.magics[index];if(slot.magicId!==old.magicId||slot.quantity!==old.quantity)edits.push({kind:"magic",id:row.id,slot:slot.slot,magicId:slot.magicId,quantity:slot.quantity})})}current.inventory.rows.forEach((slot,index)=>{const old=before.inventory.rows[index];if(slot.itemId!==old.itemId||slot.quantity!==old.quantity)edits.push({kind:"inventory",id:0,slot:slot.slot,itemId:slot.itemId,quantity:slot.quantity})});return edits}

  async function saveAll(){
    try{
      const jobs=[],kernelEdits=[];let textEdits=[],enemyAiDocuments=[],enemyBattleTextEdits=[];
      const cardEdits=state.data.cards.rows.flatMap(row=>{const base=state.base.cards.find(value=>value.id===row.id);return ["top","bottom","left","right","element","power"].filter(field=>row[field]!==base[field]).map(field=>({id:row.id,field,value:row[field]}))});
      if(cardEdits.length)jobs.push(api("/api/cards/save",post({edits:cardEdits})));
      if(signature(state.data.items.rows)!==signature(state.base.items)){
        const edits=state.data.items.rows.filter((row,index)=>
          signature(row)!==signature(state.base.items[index]));
        jobs.push(api("/api/items/save",post({edits})));
      }
      if(signature(state.data.menuItems.rows)!==signature(state.base.menuItems)){
        const edits=state.data.menuItems.rows.filter((row,index)=>signature(row)!==signature(state.base.menuItems[index])).map(row=>({id:row.id,typeId:row.typeId,flags:row.flags,param1:row.param1,param2:row.param2}));
        jobs.push(api("/api/menu-items/save",post({edits})));
      }
      if(signature(state.data.shops.rows)!==signature(state.base.shops)){
        const edits=state.data.shops.rows.flatMap((row,index)=>
          row.slots.filter((slot,slotIndex)=>
            signature(slot)!==signature(state.base.shops[index].slots[slotIndex]))
            .map(slot=>({shopId:row.id,slot:slot.slot,itemId:slot.itemId,rare:slot.rare})));
        jobs.push(api("/api/shops/save",post({edits})));
      }
      if(signature(state.data.weapons.rows)!==signature(state.base.weapons)){
        const edits=state.data.weapons.rows.filter((row,index)=>
          signature(row)!==signature(state.base.weapons[index])).map(row=>({
            id:row.id,upgradePrice:row.upgradePrice,ingredients:row.ingredients,
            fields:row.fields.map(field=>({field:field.field,value:field.value})),
          }));
        jobs.push(api("/api/weapons/save",post({edits})));
      }
      for(const [view,section] of [["battleItems",8],["ammoEffects",22],["magic",2],["gfs",3],["characters",7],["abilityJunction",12],["abilityCommand",13],["abilityStat",14],["abilityCharacter",15],["abilityParty",16],["abilityGf",17],["abilityMenu",18]]){
        if(signature(state.data[view].rows)===signature(state.base[view]))continue;
        const edits=state.data[view].rows.flatMap((row,index)=>
          row.fields.filter((field,fieldIndex)=>
            field.value!==state.base[view][index].fields[fieldIndex].value)
            .map(field=>({id:row.id,field:field.field,value:field.value})));
        kernelEdits.push({section,edits});
      }
      if(signature(state.data.text.rows)!==signature(state.base.text)){
        textEdits=state.data.text.rows.filter((row,index)=>row.value!==state.base.text[index].value).map(row=>({source:row.source,sectionId:row.sectionId,recordId:row.recordId,slot:row.slot,value:row.value}));
      }
      if(signature(state.data.enemies.rows)!==signature(state.base.enemies)){
        const edits=state.data.enemies.rows.flatMap((row,index)=>
          [...row.fields.filter((field,fieldIndex)=>
            field.value!==state.base.enemies[index].fields[fieldIndex].value)
            .map(field=>({id:row.id,field:field.field,value:field.value})),
          ...(row.scanDescription!==state.base.enemies[index].scanDescription?[{id:row.id,field:"scan_description",value:row.scanDescription}]:[])]);
        jobs.push(api("/api/enemies/save",post({edits})));
      }
      if(signature(state.data.enemyTables.rows)!==signature(state.base.enemyTables)){
        const edits=[];for(const row of state.data.enemyTables.rows){const base=state.base.enemyTables.find(value=>value.id===row.id);if(signature(row)===signature(base))continue;for(const [tier,entries] of Object.entries(row.tables.abilities))for(const entry of entries)edits.push({id:row.id,kind:"ability",tier,slot:entry.slot,type:entry.type,animation:entry.animation,abilityId:entry.abilityId});for(const kind of ["draw","mug","drops"])for(const [tier,entries] of Object.entries(row.tables[kind]))for(const entry of entries)edits.push({id:row.id,kind:kind==="drops"?"drop":kind,tier,slot:entry.slot,valueId:entry.valueId,quantity:entry.quantity});for(const entry of row.tables.cards)edits.push({id:row.id,kind:"card",slot:entry.slot,cardId:entry.cardId});for(const entry of row.tables.devour)edits.push({id:row.id,kind:"devour",slot:entry.slot,devourId:entry.devourId});for(const entry of row.tables.renzokuken)edits.push({id:row.id,kind:"renzokuken",slot:entry.slot,value:entry.value});for(const kind of ["elementDefence","statusDefence"])for(const entry of row.tables[kind])edits.push({id:row.id,kind,slot:entry.slot,stored:entry.stored})}
        jobs.push(api("/api/enemy-tables/save",post({edits})));
      }
      if(signature(state.data.enemyAi.rows)!==signature(state.base.enemyAi)){
        for(const row of state.data.enemyAi.rows){const base=state.base.enemyAi.find(value=>value.id===row.id);if(!base||signature(row)===signature(base))continue;enemyAiDocuments.push({id:row.id,sources:row.scripts.map(script=>({id:script.id,source:script.source}))})}
      }
      if(signature(state.data.enemyBattleText.rows)!==signature(state.base.enemyBattleText)){
        for(const row of state.data.enemyBattleText.rows){const base=state.base.enemyBattleText.find(value=>value.id===row.id);if(!base||signature(row)===signature(base))continue;for(const line of row.lines){const old=base.lines.find(value=>value.id===line.id);if(old&&line.text!==old.text)enemyBattleTextEdits.push({id:row.id,line:line.id,text:line.text})}}
      }
      if(signature(state.data.refine.rows)!==signature(state.base.refine)){
        const edits=[];for(const row of state.data.refine.rows){const base=state.base.refine.find(value=>value.table===row.table&&Number(value.id)===Number(row.id));if(!base||signature(row)===signature(base))continue;const edit={table:row.table,id:row.id};for(const field of ["text","outputQuantity","inputId","inputQuantity","outputId"])if(row[field]!==base[field])edit[field]=row[field];edits.push(edit)}
        if(edits.length)jobs.push(api("/api/refine/save",post({edits})));
      }
      if(signature(state.data.encounters.rows)!==signature(state.base.encounters)){
        const edits=[];for(const row of state.data.encounters.rows){const base=state.base.encounters[row.id];if(signature(row)===signature(base))continue;if(row.stageId!==base.stageId||row.flags!==base.flags||row.cameraMain!==base.cameraMain||row.cameraSecondary!==base.cameraSecondary)edits.push({id:row.id,stageId:row.stageId,flags:row.flags,cameraMain:row.cameraMain,cameraSecondary:row.cameraSecondary});for(const slot of row.slots){const before=base.slots[slot.slot];if(signature(slot)!==signature(before))edits.push({id:row.id,slot:slot.slot,enemyId:slot.enemyId,enabled:slot.enabled,visible:slot.visible,loaded:slot.loaded,targetable:slot.targetable,x:slot.x,y:slot.y,z:slot.z,level:slot.level})}}
        jobs.push(api("/api/encounters/save",post({edits})));
      }
      if(signature(state.data.world.rows)!==signature(state.base.world)){
        const edits=state.data.world.rows.filter((row,index)=>signature(row)!==signature(state.base.world[index]));
        jobs.push(api("/api/world-map/save",post({edits})));
      }
      if(signature(state.data.fields.rows)!==signature(state.base.fields)){
        const edits=[];for(const row of state.data.fields.rows){if(!row._loaded)continue;const base=state.base.fields.find(value=>value.key===row.key),fieldEncounters=row.randomEncounters,oldEncounters=base?.randomEncounters;if(fieldEncounters?.formations?.length&&oldEncounters){for(let slot=0;slot<fieldEncounters.formations.length;slot++)if(Number(fieldEncounters.formations[slot])!==Number(oldEncounters.formations?.[slot]))edits.push({type:"fieldEncounter",map:row.key,kind:"formation",slot,value:fieldEncounters.formations[slot]});if(Number(fieldEncounters.rate)!==Number(oldEncounters.rate))edits.push({type:"fieldEncounter",map:row.key,kind:"rate",value:fieldEncounters.rate})}for(const tile of row.background?.tiles||[]){const before=base?.background?.tiles?.[tile.id];if(!before)continue;const edit={type:"background",map:row.key,tile:tile.id};for(const field of row.background.editableFields||[])if(tile[field]!==before[field])edit[field]=tile[field];if(Object.keys(edit).length>3)edits.push(edit)}for(const line of row.dialogue||[]){const before=base?.dialogue?.[line.id];if(before&&line.text!==before.text)edits.push({type:"dialogue",map:row.key,line:line.id,text:line.text})}for(const method of row.scripts?.methods||[]){const before=base?.scripts?.methods?.find(value=>value.id===method.id);if(before&&method.source!==before.source)edits.push({type:"script",map:row.key,method:method.id,source:method.source})}for(const triangle of row.walkmesh?.triangles||[])for(const vertex of triangle.vertices){const before=base?.walkmesh?.triangles?.[triangle.id]?.vertices?.[vertex.id];if(!before)continue;const edit={type:"walkmesh",map:row.key,triangle:triangle.id,vertex:vertex.id};for(const field of ["x","y","z","adjacent"])if(Number(vertex[field])!==Number(before[field]))edit[field]=vertex[field];if(Object.keys(edit).length>4)edits.push(edit)}for(const player of row.players||[])for(const param of player.params||[]){const before=base?.players?.[player.id]?.params?.[param.id];if(before&&Number(param.value)!==Number(before.value))edits.push({map:row.key,player:player.id,param:param.id,value:param.value})}for(const kind of ["gateway","trigger"]){const collection=kind==="gateway"?"gateways":"triggers",entries=row.entrances?.[collection]||[],oldEntries=base?.entrances?.[collection]||[];for(const entry of entries){const old=oldEntries[entry.id],idField=kind==="gateway"?"fieldId":"doorId";if(old&&Number(entry[idField])!==Number(old[idField]))edits.push({type:"entrance",map:row.key,kind,slot:entry.id,field:idField,value:entry[idField]});for(const point of (kind==="gateway"?["exitA","exitB","destination"]:["lineA","lineB"]))for(const axis of ["x","y","z"])if(old&&Number(entry[point][axis])!==Number(old[point][axis]))edits.push({type:"entrance",map:row.key,kind,slot:entry.id,field:point,axis,value:entry[point][axis]})}}for(const headerField of ["control","pvp","focus"]){const header=row.entrances?.header,oldHeader=base?.entrances?.header;if(header&&oldHeader&&Number(header[headerField])!==Number(oldHeader[headerField]))edits.push({type:"entrance",map:row.key,kind:"misc",field:headerField,value:header[headerField]})}for(const collection of ["cameraRanges","screenRanges"]){const rangeKind=collection==="cameraRanges"?"cameraRange":"screenRange";for(const entry of row.entrances?.[collection]||[]){const old=base?.entrances?.[collection]?.[entry.id];if(!old||!entry.present)continue;for(const edge of ["top","bottom","right","left"])if(Number(entry[edge])!==Number(old[edge]))edits.push({type:"entrance",map:row.key,kind:rangeKind,slot:entry.id,field:edge,value:entry[edge]})}}for(const camera of row.camera?.cameras||[]){const old=base?.camera?.cameras?.[camera.id];if(!old)continue;if(Number(camera.zoom)!==Number(old.zoom))edits.push({type:"camera",map:row.key,camera:camera.id,field:"zoom",value:camera.zoom});for(let vector=0;vector<3;vector++)for(const axis of ["x","y","z"])if(Number(camera.axis[vector][axis])!==Number(old.axis[vector][axis]))edits.push({type:"camera",map:row.key,camera:camera.id,field:"axis"+vector,axis,value:camera.axis[vector][axis]});for(const axis of ["x","y","z"])if(Number(camera.position[axis])!==Number(old.position[axis]))edits.push({type:"camera",map:row.key,camera:camera.id,field:"position",axis,value:camera.position[axis]})}for(const frame of row.movie?.frames||[]){const old=base?.movie?.frames?.[frame.id];if(!old)continue;for(let point=0;point<frame.points.length;point++)for(const axis of ["x","y","z"])if(Number(frame.points[point][axis])!==Number(old.points[point][axis]))edits.push({type:"movie",map:row.key,frame:frame.id,point,axis,value:frame.points[point][axis]})}}
        if(edits.length)jobs.push(api("/api/field/save",post({edits})));
      }
      if(signature(state.data.init)!==signature(state.base.init))jobs.push(api("/api/init/save",post({edits:startingDataEdits()})));
      if(signature(state.data.sfx.rows)!==signature(state.base.sfx)){
        const edits=state.data.sfx.rows.filter(row=>row.audioBase64||row.audioRevert).map(row=>row.audioRevert&&!row.audioBase64?{id:row.id,revert:true}:{id:row.id,audioBase64:row.audioBase64,ext:row.audioExt});
        if(edits.length)jobs.push(api("/api/sfx/save",post({edits})));
      }
      if(signature(state.data.models.rows)!==signature(state.base.models.rows)){
        const edits=state.data.models.rows.filter(row=>row.datBase64||row.datRevert).map(row=>row.datRevert&&!row.datBase64?{file:row.file,revert:true}:{file:row.file,datBase64:row.datBase64});
        if(edits.length)jobs.push(api("/api/models/save",post({edits})));
      }
      const settingsDirty=signature(state.data.settings)!==signature(state.base.settings);
      const results=await Promise.all(jobs);
      if(window.ff8SpellbookDrafts?.size){
        const edits=[...window.ff8SpellbookDrafts].map(([id,pages])=>({id,field:"__spellbook",value:pages.length?pages:null}));
        results.push(await api("/api/kernel/save",post({section:3,edits})));
        window.ff8SpellbookDrafts.clear();
      }
      if(enemyAiDocuments.length)results.push(await api("/api/enemy-ai/save",post({documents:enemyAiDocuments})));
      if(enemyBattleTextEdits.length)results.push(await api("/api/enemy-battle-text/save",post({edits:enemyBattleTextEdits})));
      for(const request of kernelEdits)results.push(await api("/api/kernel/save",post(request)));
      if(textEdits.length)results.push(await api("/api/text/save",post({edits:textEdits})));
      if(settingsDirty)results.push(await api("/api/settings/save",post(settingsPayload())));
      const platformEdits=platformChanges();
      if(Object.keys(platformEdits).length){state.platformConfig=await api("/api/platform-config/save",post({sha256:state.savedPlatformConfig.sha256,changes:platformEdits}));state.savedPlatformConfig=clone(state.platformConfig);results.push({saved:Object.keys(platformEdits).length})}
      await reloadEditable();
      shell.history.clear();
      setStatus(results.length
        ?`Saved ${results.reduce((sum,result)=>sum+(result.saved||0),0)} records or fields`
        :"No changes to save");
      render();
    }catch(error){const view=state.tab,row=state.data[view]?.rows?.find(candidate=>candidate.id===state.selected[view]),message=error.message||String(error);setStatus("Save failed");showAlert({title:"Save failed",items:[{item:row?.name||"Save",issue:message,activate:row?()=>{state.selected[view]=row.id;navigate(view)}:null}],closeLabel:"Confirm and Close"});throw error}
  }
  function post(body){return {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}}
  async function loadDataset(dataset,tolerant=false){const suffix=`dataset=${encodeURIComponent(dataset)}`,get=path=>tolerant?api(path).catch(()=>null):api(path);const [battleItems,ammoEffects,cards,items,menuItems,shops,weapons,magic,gfs,characters,abilityJunction,abilityCommand,abilityStat,abilityCharacter,abilityParty,abilityGf,abilityMenu,text,enemies,enemyTables,enemyAi,enemyBattleText,refine,encounters,world,fields,init,sfx,models,textures]=await Promise.all([get(`/api/kernel?section=8&${suffix}`),get(`/api/kernel?section=22&${suffix}`),get(`/api/cards?${suffix}`),get(`/api/items?${suffix}`),get(`/api/menu-items?${suffix}`),get(`/api/shops?${suffix}`),get(`/api/weapons?${suffix}`),get(`/api/kernel?section=2&${suffix}`),get(`/api/kernel?section=3&${suffix}`),get(`/api/kernel?section=7&${suffix}`),get(`/api/kernel?section=12&${suffix}`),get(`/api/kernel?section=13&${suffix}`),get(`/api/kernel?section=14&${suffix}`),get(`/api/kernel?section=15&${suffix}`),get(`/api/kernel?section=16&${suffix}`),get(`/api/kernel?section=17&${suffix}`),get(`/api/kernel?section=18&${suffix}`),get(`/api/text?${suffix}`),get(`/api/enemies?${suffix}`),get(`/api/enemy-tables?${suffix}`),get(`/api/enemy-ai?${suffix}`),get(`/api/enemy-battle-text?${suffix}`),get(`/api/refine?${suffix}`),get(`/api/encounters?${suffix}`),get(`/api/world-map?${suffix}`),get(`/api/fields?${suffix}`),get(`/api/init?${suffix}`),get(`/api/sfx?${suffix}`),get(`/api/models?${suffix}`),get(`/api/textures?${suffix}`)]);return {battleItems,ammoEffects,cards,items,menuItems,shops,weapons,magic,gfs,characters,abilityJunction,abilityCommand,abilityStat,abilityCharacter,abilityParty,abilityGf,abilityMenu,text,enemies,enemyTables,enemyAi,enemyBattleText,refine,encounters,world,fields,init,sfx,models,textures}}
  async function reloadEditable(){const [current,vanilla,settings,references,platformConfig,mods]=await Promise.all([loadDataset("current"),loadDataset("vanilla"),api("/api/settings"),api("/api/references"),api("/api/platform-config"),api("/api/mods")]);for(const dataset of [current,vanilla])for(const row of dataset.encounters.rows)row.name=encounterName(row);Object.assign(state.data,{...current,settings});state.vanilla=vanilla;state.mods=mods;state.references=references.rows||[];state.platformConfig=platformConfig;state.savedPlatformConfig=clone(platformConfig);state.referenceData={};await Promise.all(state.references.map(async reference=>{const dataset=await loadDataset(`reference:${reference.id}`,true);if(dataset?.encounters)for(const row of dataset.encounters.rows)row.name=encounterName(row);state.referenceData[reference.id]=dataset}));for(const name of editableDatasets)state.base[name]=clone(state.data[name].rows);state.base.init=clone(state.data.init);state.base.settings=clone(settings);resetHistoryBaseSigs()}
  async function switchProjectSource(value){const next=String(value||"mine");if(next===state.activeSource)return;if(next==="mine"){state.activeSource="mine";await reloadEditable()}else if(next==="vanilla"){state.activeSource="vanilla";for(const name of editableDatasets)state.data[name]=clone(state.vanilla[name]);state.data.init=clone(state.vanilla.init);state.data.settings=clone(state.base.settings||state.data.settings)}else if(next.startsWith("mod:")){const dataset=await loadDataset(next);for(const row of dataset.encounters.rows)row.name=encounterName(row);state.activeSource=next;Object.assign(state.data,dataset);state.data.settings=clone(state.base.settings||state.data.settings)}else throw new Error(`Unknown mod source: ${next}`);shell.history?.clear();render()}
  function displayModName(name){return name==="Lexer's Mod for FF8"?"Lexer's Mod":name}
  function projectSources(){
    const rows=[{key:"vanilla",label:"Vanilla",path:state.dashboard?.baseline?.root||"Extracted unchanged FF8 data",readOnly:true,enabled:true}];
    for(const mod of state.mods?.rows||[])rows.push({key:mod.selected?"mine":`mod:${mod.id}`,label:displayModName(mod.name),path:mod.path,readOnly:!mod.selected,enabled:mod.enabled,managed:true,removable:!mod.selected,
      settings:(mod.folderConfig||[]).map(option=>({...option,value:mod.folderOptions?.[option.id]??option.default})),
      notes:[mod.error,mod.folderError,...(state.mods?.composition?.conflicts||[]).filter(conflict=>conflict.claimants?.includes(mod.id)).map(conflict=>conflict.warning||`${conflict.path}: ${conflict.winner||"Higher priority mod takes precedence"}`)].filter(Boolean)});
    return rows;
  }
  async function changeProjectSource(key,change){
    const latest=await api("/api/mods"),rows=clone(latest.rows||[]);
    const index=rows.findIndex(row=>(row.selected?"mine":`mod:${row.id}`)===key);
    if(index<0)throw Error("This mod is no longer available.");
    const row=rows[index];
    if(change.remove){
      if(row.selected)throw Error("The editable project cannot be removed here.");
      if(state.activeSource===key)await switchProjectSource("mine");
      state.mods=await api(`/api/mods/${encodeURIComponent(row.id)}`,{method:"DELETE"});
    }else{
      if(change.enabled!==undefined)row.enabled=change.enabled;
      if(change.option)row.folderOptions={...row.folderOptions,[change.option]:change.value};
      if(change.move){const target=index+change.move;if(target>=0&&target<rows.length){rows.splice(index,1);rows.splice(target,0,row);}}
      state.mods=await api("/api/mods/configure",post({order:rows.map(row=>row.id),enabled:Object.fromEntries(rows.map(row=>[row.id,row.enabled])),folderOptions:Object.fromEntries(rows.map(row=>[row.id,row.folderOptions||{}]))}));
    }
    shell.refresh();
  }
  function addProjectSource(){
    return new Promise((resolve,reject)=>{
      const input=el("input",{type:"file",accept:".iroj",hidden:true});
      input.addEventListener("cancel",()=>{input.remove();resolve()});
      input.addEventListener("change",async()=>{try{
        const file=input.files?.[0];if(file)state.mods=await api(`/api/mods/import?filename=${encodeURIComponent(file.name)}`,{method:"POST",headers:{"Content-Type":"application/octet-stream"},body:file});
        shell.refresh();resolve();
      }catch(error){reject(error)}finally{input.remove()}});
      document.body.append(input);input.click();
    });
  }
  function discardAll(){window.ff8SpellbookDrafts?.clear();for(const name of editableDatasets)if(state.data[name])state.data[name].rows=clone(state.base[name]||[]);state.data.init=clone(state.base.init||{});state.data.settings=clone(state.base.settings||{});state.platformConfig=clone(state.savedPlatformConfig);shell.history?.clear();setStatus("Restored the last saved state");render();shell.refresh()}
  let cardsUI;
  function renderCards(){cardsUI??=FF8CardsUI({el,state,rowOf,filtered,showPaged,sharedDetail,detailSection,detailField,numberControl,selectControl,sourceControl,referenceValues,infoHelp,shell,noteFieldEdit,subtabBar,detailPanel,recordId,columnList,conceptIcon,ensureFieldDetail});return cardsUI.render()}
  const views={cards:renderCards,abilities:renderAbilities,starting:renderStartingData,items:renderItems,refine:renderRefine,shops:renderShops,weapons:renderWeapons,magic:()=>renderKernel("magic","Magic"),gfs:renderGFs,characters:renderCharacters,text:renderText,enemies:renderEnemies,encounters:renderEncounters,fields:renderFields,world:renderWorldMap,settings:renderSettings,sfx:renderSfx,models:renderModels,textures:renderTextures,datamap:renderDataMap,dashboard:renderDashboard};
  // An ability record lives in a category subtab of Abilities, so a link to one
  // names its dataset (abilityJunction) and lands on that subtab.
  async function navigate(tab){if(!(await enemyAiBeforeLeave()))return false;if(tab==="formulae"){state.settingsTab="formulae";tab="settings"}if(/^ability[A-Z]/.test(tab)){state.abilityTab=tab;tab="abilities"}state.tab=tab;render()}
  function render(){document.querySelectorAll("nav button[data-tab]").forEach(button=>button.classList.toggle("active",button.dataset.tab===state.tab));if(state.booting||state.bootFailed)return;const toolbar=$("#toolbar");toolbar.hidden=false;toolbar.classList.toggle("portrait-toolbar",state.tab==="gfs"||state.tab==="characters");views[state.tab]();shell.refresh()}
  async function prepareGameplayLaunch(){if(dirtyCount())await saveAll();const result=await api("/api/settings/activate",post({}));if(!result.ready)throw new Error("The FFNx gameplay patch did not pass its launch check.");setStatus("Gameplay patch ready")}
  async function confirmGameplayPatch(){for(let attempt=0;attempt<40;attempt++){await new Promise(resolve=>setTimeout(resolve,500));const status=await api("/api/settings/runtime");if(status.loaded){setStatus("FFNx loaded the gameplay patch");return}if(status.logReady&&attempt>5){showAlert({title:"FFNx did not load the gameplay patch",message:status.message});return}}showAlert({title:"FFNx patch check timed out",message:"FFNx did not write a current patch result within 20 seconds. The game can remain open, but these gameplay settings are not confirmed active."})}
  const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ff8",name:"Final Fantasy 8",themeName:"ff8",theme:{bg:"#000",panel:"#626262","panel-2":"#4f4f4f",border:"#929292",text:"#fff",muted:"#d0d0d0",accent:"#aa2432","accent-text":"#fff",highlight:"#fff",success:"#d8d8d8",font:'"FF8 Menu","Arial Narrow",sans-serif',"heading-font":'"FF8 Menu","Arial Narrow",sans-serif'}},tabs:[["characters","Characters"],["cards","Cards"],["encounters","Encounters"],["fields","Field"],["world","World"],["enemies","Enemies"],["gfs","GFs"],["items","Items"],["refine","Refine"],["abilities","Abilities"],["magic","Magic"],["text","Text"],["shops","Shops"],["starting","New Game"],["weapons","Weapons"],["sfx","SFX"],["models","Models"],["textures","Textures"],["settings","Tweaks"]].map(([id,label])=>({id,label})),activeTab:()=>state.tab,navigate,resetView:tab=>{state.columnPrefs[tab]?.reset?.()},help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the FF8 Data Map",info:()=>navigate("dashboard"),infoActive:()=>state.tab==="dashboard",infoTitle:"Open FF8 setup and runtime information",projectSnapshot:async()=>({canCreate:false,projects:[]}),projectSources:projectSources,projectActiveSource:()=>state.activeSource,selectProjectSource:switchProjectSource,sourcesReplaceProjects:true,changeProjectSource,addProjectSource,pendingChanges:()=>LexeditorUI.pendingChangeList({...state.base,platformConfig:state.savedPlatformConfig},{...historyFullCapture(),platformConfig:state.platformConfig}),dirtyCount,readonly:()=>state.activeSource!=="mine",save:saveAll,discard:discardAll,beforeLaunch:prepareGameplayLaunch,afterLaunch:confirmGameplayPatch,history:{capture:historyCapture,restore:historyRestore,render,enabled:()=>!state.booting&&state.activeSource==="mine",limit:50}});
  async function boot(){try{[state.dashboard,state.datamap,state.editorSettings]=await Promise.all([api("/api/dashboard"),api("/api/datamap"),api("/api/editor-settings").catch(()=>({showNewGame:false}))]);if(state.editorSettings?.showNewGame!==true)document.querySelector('nav button[data-tab="starting"]')?.remove();LexeditorUI.configureThemeSounds(state.dashboard.themeSounds);await reloadEditable();state.booting=false;setStatus(state.dashboard.runtime.installed?"FFNx ready":"FFNx needed for in-game loading");render();LexeditorUI.finishPluginLoading()}catch(error){state.booting=false;state.bootFailed=true;LexeditorUI.finishPluginLoading();$("#main").replaceChildren(el("div",{class:"empty"},`Failed to load FF8 plugin: ${error.message}`));setStatus("Load failed")}}
  window.addEventListener("lexeditor-settings-ready",()=>{if(!state.booting&&state.tab==="dashboard")renderDashboard()});
  window.addEventListener("ff8-spellbook-changed",()=>shell.refresh());
  boot();
  
