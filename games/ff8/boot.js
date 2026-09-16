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
        detailField({label:"FOLDER",control:value(game.root),
          pin:el("button",{class:"ff8-folder-button",type:"button",title:"Open the game folder","aria-label":"Open the game folder",onclick:openFolder},folderIcon())}),
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
  const settingsPayload=()=>({flyingEvaBonus:state.data.settings.flyingEvaBonus,flyingEvaEnabled:state.data.settings.flyingEvaEnabled,autoSortInventory:state.data.settings.autoSortInventory,autoSortMagic:state.data.settings.autoSortMagic,enhancedAbilityMenu:state.data.settings.enhancedAbilityMenu,singleGf:state.data.settings.singleGf,fixedCommandMenu:state.data.settings.fixedCommandMenu,universalItem:state.data.settings.universalItem,scannedTargetScan:state.data.settings.scannedTargetScan,partySwitch:state.data.settings.partySwitch,drawOncePerEnemy:state.data.settings.drawOncePerEnemy,streamlinedDraw:state.data.settings.streamlinedDraw,formulaeRework:state.data.settings.formulaeRework,trueAtbWait:state.data.settings.trueAtbWait,betterTargeting:state.data.settings.betterTargeting,modernControls:state.data.settings.modernControls,vibrationConsolidation:state.data.settings.vibrationConsolidation,sharedMagicInventory:state.data.settings.sharedMagicInventory,damageLimitRemoval:state.data.settings.damageLimitRemoval,betterCard:state.data.settings.betterCard,fastStart:state.data.settings.fastStart,xpBars:state.data.settings.xpBars,hpBars:state.data.settings.hpBars,gfHpBars:state.data.settings.gfHpBars,inGameTime:state.data.settings.inGameTime,noMagicConsumption:state.data.settings.noMagicConsumption,gfHpCasting:state.data.settings.gfHpCasting,gfHpCastingCosts:state.data.settings.gfHpCastingCosts,dropsAfterMug:state.data.settings.dropsAfterMug,dropChance:state.data.settings.dropChance,flatStatAbilities:state.data.settings.flatStatAbilities,maxSpellEnabled:state.data.settings.maxSpellEnabled,maxSpell:state.data.settings.maxSpell});
  function renderGameplaySettings(){
    if(state.activeSource!=="mine"){$("#main").replaceChildren(el("section",{class:"settings-view"},el("div",{class:"readonly-note"},"Vanilla uses no Lexeditor gameplay tweaks. Select a mod to configure Tweaks.")));return}
    const settings=state.data.settings;
    const flying=numberControl(settings.flyingEvaBonus,settings.minimum,settings.maximum,1,value=>settings.flyingEvaBonus=value,{"aria-label":"Flying EVA Bonus"});
    const flyingEnabled=el("input",{type:"checkbox",checked:settings.flyingEvaEnabled,"aria-label":"Enable Flying EVA Bonus",onchange:event=>{settings.flyingEvaEnabled=event.target.checked;shell.refresh()}});
    const singleGf=el("input",{type:"checkbox",checked:settings.singleGf,"aria-label":"Monogamy",onchange:event=>{settings.singleGf=event.target.checked;shell.refresh()}});
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
    const modernControlsControl=el("span",{class:"tweak-value"},modernControls,unitField(cameraSpeed,"×"));
    const vibrationConsolidation=el("input",{type:"checkbox",checked:settings.vibrationConsolidation,"aria-label":"Vibration Rationalization",onchange:event=>{settings.vibrationConsolidation=event.target.checked;shell.refresh()}});
    const betterTargeting=el("input",{type:"checkbox",checked:settings.betterTargeting,"aria-label":"Better Targeting",onchange:event=>{settings.betterTargeting=event.target.checked;shell.refresh()}});
    const damageLimitRemoval=el("input",{type:"checkbox",checked:settings.damageLimitRemoval,"aria-label":"Remove Damage Limit",onchange:event=>{settings.damageLimitRemoval=event.target.checked;shell.refresh()}});
    const betterCard=el("input",{type:"checkbox",checked:settings.betterCard,"aria-label":"Better Card",onchange:event=>{settings.betterCard=event.target.checked;shell.refresh()}});
    const fastStart=el("input",{type:"checkbox",checked:settings.fastStart,"aria-label":"Fast Start",onchange:event=>{settings.fastStart=event.target.checked;shell.refresh()}});
    const xpBars=el("input",{type:"checkbox",checked:settings.xpBars,"aria-label":"XP Bars",onchange:event=>{settings.xpBars=event.target.checked;shell.refresh()}});
    const hpBars=el("input",{type:"checkbox",checked:settings.hpBars,"aria-label":"HP Bars",onchange:event=>{settings.hpBars=event.target.checked;shell.refresh()}});
    const gfHpBars=el("input",{type:"checkbox",checked:settings.gfHpBars,disabled:!settings.singleGf,"aria-label":"GF HP Bars",onchange:event=>{settings.gfHpBars=event.target.checked;shell.refresh()}});
    const inGameTime=el("input",{type:"checkbox",checked:settings.inGameTime,"aria-label":"In-game Time",onchange:event=>{settings.inGameTime=event.target.checked;shell.refresh()}});
    const noMagicConsumption=el("input",{type:"checkbox",checked:settings.noMagicConsumption,"aria-label":"No Magic Consumption",onchange:event=>{settings.noMagicConsumption=event.target.checked;shell.refresh()}});
    const gfHpCasting=el("input",{type:"checkbox",checked:settings.gfHpCasting,disabled:!settings.singleGf||!settings.noMagicConsumption,"aria-label":"GF HP Casting",onchange:event=>{settings.gfHpCasting=event.target.checked;shell.refresh()}});
    const dropsAfterMug=el("input",{type:"checkbox",checked:settings.dropsAfterMug,"aria-label":"Drops After Mug",onchange:event=>{settings.dropsAfterMug=event.target.checked;shell.refresh()}});
    const dropChance=el("input",{type:"checkbox",checked:settings.dropChance,"aria-label":"Drop Chance Rework",onchange:event=>{settings.dropChance=event.target.checked;shell.refresh()}});
    const sharedMagic=el("input",{type:"checkbox",checked:settings.sharedMagicInventory,disabled:!settings.sharedMagicInventoryAvailable&&!settings.sharedMagicInventory,"aria-label":"Shared Party Magic Inventory",onchange:event=>{settings.sharedMagicInventory=event.target.checked;shell.refresh()}});
    const flatStatAbilities=el("input",{type:"checkbox",checked:settings.flatStatAbilities,"aria-label":"Flat +Stat Abilities",onchange:event=>{settings.flatStatAbilities=event.target.checked;shell.refresh()}});
    const maxSpellEnabled=el("input",{type:"checkbox",checked:settings.maxSpellEnabled,"aria-label":"Enable Max Spell",onchange:event=>{settings.maxSpellEnabled=event.target.checked;shell.refresh()}});
    const maxSpellValue=numberControl(settings.maxSpell,settings.maxSpellMinimum,settings.maxSpellMaximum,1,value=>settings.maxSpell=value,{"aria-label":"Maximum spell stock"});
    const row=(title,description,control,className="")=>el("div",{class:"setting-row"},el("div",{class:"setting-copy"},el("strong",{},title),description instanceof Element?description:el("p",{},description)),el("label",{class:`setting-control ${className}`.trim()},control));
    // The number is a percentage of effective EVA, so it carries its unit. A
    // bare number here reads as flat points and the row label alone does not
    // say which.
    const flyingControl=el("span",{class:"tweak-value"},flyingEnabled,unitField(flying,"% EVA"));
    const maxSpellControl=el("span",{class:"tweak-value"},maxSpellEnabled,maxSpellValue);
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
      row("FAST START","Completes the native opening credits immediately, then uses the game's normal transition and main-menu initialization.",fastStart,"boolean"),
      row("FF10-STYLE PARTY SWITCH","Look Left opens the reserve-party selector during an active turn. Confirming a replacement spends that turn.",partySwitch,"boolean"),
      row("FLAT +STAT ABILITIES","Changes +Stat% abilities into fixed-point +Stat abilities and updates their in-game names and descriptions.",flatStatAbilities,"boolean"),
      row("FLYING EVA BONUS","Adds the selected effective EVA to intrinsic flying targets against grounded melee attacks. A hit rate of 255 does not bypass it.",flyingControl,"value-toggle"),
      row("GF HP CASTING","Battle Magic spends the spell’s GF HP cost instead of spell stock. Set costs in Magic → Attack Data. Requires Monogamy and No Magic Consumption. A character without a GF or enough GF HP cannot cast.",gfHpCasting,"boolean"),
      row("GF HP BARS","Shows blue GF HP bars above party names, filling left to right. Requires Monogamy. Shows only one junctioned GF, including damage during summoning. Multiple junctioned GFs cause an error and hide the bar.",gfHpBars,"boolean"),
      row("HP BARS","Shows a red HP bar under each party member's HP during battle.",hpBars,"boolean"),
      row("IN-GAME TIME","Shows your computer's local clock where the main menu shows play time. It does not replace FF8's saved play-time counter: that keeps counting, and timed events still measure against it.",inGameTime,"boolean"),
      row("MAX SPELL","Sets the maximum stock for each spell. A full stack keeps the same junction effect as 100 spells in vanilla.",maxSpellControl,"value-toggle"),
      row("MODERN CONTROLS",settings.modernControlsBlocker||"Right stick turns the battle camera while the camera is idle, and gives the world map analog rotation. The number is the turn rate as a multiple of the shipped speed, from 0.2 to 4. The camera stops level with what it is looking at rather than dropping through the ground.",modernControlsControl,"value-toggle"),
      row("MONOGAMY","Allows one GF on each character. Warning: when gameplay starts, any character who already has several GFs junctioned will have all of those GFs unequipped.",singleGf,"boolean"),
      row("NO MAGIC CONSUMPTION","Casting spells in battle or from the field Magic menu keeps their stock. Items, discarding and other inventory operations are unchanged; works with Shared Magic and Max Spell.",noMagicConsumption,"boolean"),
      row("REMOVE DAMAGE LIMIT","Uses FF8's existing 60,000-damage path instead of the normal 9,999 cap.",damageLimitRemoval,"boolean"),
      row("SHARED PARTY MAGIC INVENTORY","Uses one lossless 32-slot Magic pool for the party. Works with Party Switch and the selected Max Spell cap. If existing stocks cannot merge without loss, the game keeps them unchanged and disables sharing for that launch; details are written to FFNx.shared-magic.log.",sharedMagic,"boolean"),
      row("STREAMLINED DRAW","Skips the spell list when only one spell is available and submits the native Stock action directly.",streamlinedDraw,"boolean"),
      row("TRUE ATB WAIT","Works only when the game is set to ATB Wait mode. Stops all party and enemy ATB filling while any party member is ready to act. Active mode keeps its normal behavior.",trueAtbWait,"boolean"),
      row("UNIVERSAL ITEM","Look Right opens the normal battle Item menu without using an equipped command slot. The shortcut follows the configured input mapping.",universalItem,"boolean"),
      row("VIBRATION RATIONALIZATION","Start uses the normal field and battle pause behavior instead of FFNx's separate vibration screen.",vibrationConsolidation,"boolean"),
      row("XP BARS","Shows yellow XP bars under main-menu character names, under character and GF level rows, and on the post-battle report.",xpBars,"boolean"));
    $("#main").replaceChildren(LexeditorUI.settingsColumns([...view.children],tweakTabProps()));
    bindSettingDependencies(view,[{
      key:"singleGf->fixedCommandMenu",
      dependency:singleGf,
      dependent:fixedCommandMenu,
    },{key:"singleGf->gfHpBars",dependency:singleGf,dependent:gfHpBars},{key:"singleGf->gfHpCasting",dependency:singleGf,dependent:gfHpCasting},{key:"noMagicConsumption->gfHpCasting",dependency:noMagicConsumption,dependent:gfHpCasting}]);
  }

  function renderPlatformSettings(){
    $("#main").replaceChildren(platformConfigView({config:state.platformConfig,showHeader:false,query:state.platformQuery,...tweakTabProps(),disabled:state.activeSource!=="mine",search:value=>{state.platformQuery=value},change:(id,value)=>{const field=(state.platformConfig?.sections||[]).flatMap(section=>section.fields).find(candidate=>candidate.id===id);if(field){field.value=value;shell.refresh()}}}));
  }
  function dropChanceDescription(){
    const normal=[137,68,34,17],rare=[94,70,53,39];
    const chance=value=>el("span",{},`${(value/256*100).toFixed(2)}%`,el("small",{},`${value}/256`));
    return el("div",{},el("p",{},"In vanilla, Rare Item makes the fourth loot slot impossible to receive. This rework restores that chance and improves the odds of the rarer slots. Applies to enemy drops and Mug. Values when enabled:"),
      columnList({class:"drop-chance-table","aria-label":"Drop Chance slot probabilities",
        rows:normal.map((value,index)=>({key:index,slot:index+1,normal:value,rare:rare[index]})),
        key:entry=>entry.key, localSort:false, template:'60px minmax(0,1fr) minmax(0,1fr)',
        columns:[{key:"slot",label:"Slot"},{key:"normal",label:"Normal",render:entry=>chance(entry.normal)},
          {key:"rare",label:"Rare Item",render:entry=>chance(entry.rare)}]}));
  }
  const TWEAK_TABS=[{id:"gameplay",label:"Gameplay"},{id:"platform",label:"FFNx"}];
  const tweakTabProps=()=>({tabs:TWEAK_TABS,activeTab:state.settingsTab,
    tabsLabel:"Tweak settings",
    changeTab:value=>{state.settingsTab=value;renderSettings()}});
  function renderSettings(){
    const toolbar=$("#toolbar");toolbar.replaceChildren();toolbar.hidden=true;
    if(state.settingsTab==="platform")renderPlatformSettings();else renderGameplaySettings();
  }

  const DEFAULT_FLYING_EVA_BONUS=25;
  function formulaInput(label,key,min,max,step=1){return el("label",{class:"formula-preview-input"},label,numberControl(state.formula[key],min,max,step,value=>{state.formula[key]=value}))}
  function renderFormulae(){
    const toolbar=$("#toolbar");toolbar.replaceChildren();toolbar.hidden=true;
    const f=state.formula,weapons=state.data.weapons?.rows||[],settings=state.data.settings;
    if(!weapons.some(row=>Number(row.id)===Number(f.weaponId)))f.weaponId=weapons[0]?.id??0;
    const weapon=weapons.find(row=>Number(row.id)===Number(f.weaponId)),weaponField=name=>weapon?.fields?.find(field=>field.field===name),fieldValue=name=>Number(weaponField(name)?.value??0);
    const formulaeRework=el("input",{type:"checkbox",checked:settings.formulaeRework,disabled:state.activeSource!=="mine"||!settings.formulaeReworkAvailable,"aria-label":"Formulae Rework",onchange:event=>{settings.formulaeRework=event.target.checked;shell.refresh();renderFormulae()}});
    const preset=()=>el("label",{class:"formula-preset"},el("strong",{},"WEAPON PRESET"),selectControl(f.weaponId,weapons.map(row=>({id:row.id,name:row.name})),value=>{f.weaponId=value;renderFormulae()}));
    const formulaTerm=(name,label,help)=>{const field=weaponField(name);return field?detailField({label,help:infoHelp(help),control:fieldSourceControl(field,"weapons",weapon.id)}):null};
    const boost=()=>state.data.settings.flyingEvaEnabled?state.data.settings.flyingEvaBonus:0;
    const calculate=()=>{const strength=Math.min(255,Math.max(0,Math.trunc(Number(f.strength)+fieldValue("str_bonus")))),inner=Math.trunc((265-Number(f.vitality))*(strength+Math.trunc(strength*strength/16))/256),middle=Math.max(0,Math.trunc(fieldValue("attack_power")*inner/16)),low=Math.max(0,Math.trunc(middle*240/256)),average=Math.max(0,middle),high=Math.max(0,Math.trunc(middle*272/256)),flyingPenalty=f.flying&&Boolean(fieldValue("melee"))&&!f.float?boost():0,luckTerm=settings.formulaeRework?Number(f.luck):Math.floor(Number(f.luck)/2),effective=Math.max(0,Math.min(100,fieldValue("hit_rate")+luckTerm-Number(f.eva)-Number(f.targetLuck)-flyingPenalty)),chance=Math.max(0,Math.min(100,(Math.floor(255*effective/100)+1)/256*100));return{low,average,high,flyingPenalty,chance}};
    const checkbox=(label,key)=>el("label",{},el("input",{type:"checkbox",checked:f[key],onchange:event=>{f[key]=event.target.checked;updateOutputs()}}),label);
    const damageOutput=el("div",{class:"formula-output"}),accuracyOutput=el("div",{class:"formula-output"});
    const damage=el("section",{class:"formula-card"},el("h2",{},"PHYSICAL DAMAGE"),preset(),el("h3",{class:"formula-subheading"},"FORMULA"),el("div",{class:"formula-expression"},"STR = min(255, attacker STR + weapon STR bonus)",el("br"),"DAMAGE = floor(POWER × floor((265 − VIT) × (STR + floor(STR² / 16)) / 256) / 16) × RANDOM / 256",el("br"),"RANDOM = 240 to 272"),el("h3",{class:"formula-subheading"},"EDITABLE FORMULA TERMS"),el("div",{class:"formula-terms"},formulaTerm("attack_power","WEAPON ATTACK POWER","The selected weapon's stored attack power."),formulaTerm("str_bonus","WEAPON STR BONUS","The selected weapon's stored Strength bonus.")),el("h3",{class:"formula-subheading"},"PREVIEW INPUTS"),el("div",{class:"formula-preview-inputs"},formulaInput("Attacker STR","strength",0,255),formulaInput("Target VIT","vitality",0,255)),damageOutput);
    const flyingTerm=sourceControl(unitField(numberControl(boost(),0,100,1,value=>state.data.settings.flyingEvaBonus=value),"%"),()=>state.data.settings.flyingEvaBonus,DEFAULT_FLYING_EVA_BONUS,[],value=>state.data.settings.flyingEvaBonus=Number(value),value=>`${formatNumber(value)}%`);
    const accuracyLuck=settings.formulaeRework?"attacker LUCK":"floor(attacker LUCK / 2)";
    const accuracy=el("section",{class:"formula-card"},el("h2",{},"PHYSICAL ACCURACY"),preset(),el("p",{},"A hit rate of 255 receives no bypass."),el("h3",{class:"formula-subheading"},"FORMULA"),el("div",{class:"formula-expression"},`EFFECTIVE = clamp(hit rate + ${accuracyLuck} − target EVA − target LUCK − flying penalty, 0, 100)`,el("br"),"HIT CHANCE = (floor(255 × EFFECTIVE / 100) + 1) / 256 × 100%"),el("h3",{class:"formula-subheading"},"EDITABLE FORMULA TERMS"),el("div",{class:"formula-terms"},formulaTerm("hit_rate","WEAPON HIT RATE","Weapon accuracy contributes directly to effective hit chance before target Evasion and Luck; FF8's special 255 value uses the always-hit bypass."),formulaTerm("melee","MELEE WEAPON","Marks the attack as close-range for this formula; grounded melee attacks take the flying-target accuracy penalty."),detailField({label:"FLYING EVA BONUS",help:infoHelp("This penalty applies to grounded melee attackers when the target is flying."),control:flyingTerm})),el("h3",{class:"formula-subheading"},"PREVIEW INPUTS"),el("div",{class:"formula-preview-inputs"},formulaInput("Attacker LUCK","luck",0,255),formulaInput("Target EVA","eva",0,255),formulaInput("Target LUCK","targetLuck",0,255),checkbox("Target is flying","flying"),checkbox("Attacker has Float","float")),accuracyOutput);
    function updateOutputs(){const value=calculate();damageOutput.textContent=`DAMAGE: ${formatNumber(value.low)} TO ${formatNumber(value.high)} · AVERAGE ${formatNumber(value.average)}`;accuracyOutput.textContent=`FLYING PENALTY: ${formatNumber(value.flyingPenalty)}% · HIT CHANCE: ${formatNumber(value.chance,{maximumFractionDigits:1})}%`}
    // The backend owns the complete requested inventory and each row's runtime
    // status. A formula cannot disappear from this page merely because its native
    // implementation is unfinished.
    const formulaRows=settings.formulaeReworkFormulas||[];
    const reworkCard=formula=>el("section",{class:"formula-card formula-rework","data-formula-id":formula.id},
      el("h2",{},`${String(formula.name||formula.id).toUpperCase()} · ${formula.status==="implemented"?"IMPLEMENTED":"INCOMPLETE"}`),
      el("h3",{class:"formula-subheading"},"REWORKED"),
      el("div",{class:"formula-expression"},formula.replacement||"Not specified"),
      el("h3",{class:"formula-subheading"},"VANILLA"),
      el("div",{class:"formula-expression formula-vanilla"},formula.vanilla||"Not documented"),
      formula.blocker?el("p",{class:"readonly-note"},`INCOMPLETE: ${formula.blocker}`):null);
    const implementedCount=formulaRows.filter(formula=>formula.status==="implemented").length;
    const master=el("section",{class:"formula-rework-master"},el("h2",{},"FORMULAE REWORK"),el("label",{class:"formula-rework-toggle"},el("span",{},"Use Lexer's reworked battle formulae"),formulaeRework),el("p",{},`${implementedCount}/${formulaRows.length} requested runtime formulae are implemented. The owning toggle remains unavailable until every listed formula has a guarded game patch.`));
    const rework=formulaRows.map(reworkCard);
    const view=el("div",{class:"formulae-view",oninput:()=>requestAnimationFrame(updateOutputs)},master,damage,accuracy,...rework);updateOutputs();
    $("#main").replaceChildren(view);
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
      for(const [view,section] of [["magic",2],["gfs",3],["characters",7],["abilityJunction",12],["abilityCommand",13],["abilityStat",14],["abilityCharacter",15],["abilityParty",16],["abilityGf",17],["abilityMenu",18]]){
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
        const edits=[];for(const row of state.data.fields.rows){if(!row._loaded)continue;const base=state.base.fields.find(value=>value.key===row.key),fieldEncounters=row.randomEncounters,oldEncounters=base?.randomEncounters;if(fieldEncounters?.formations?.length&&oldEncounters){for(let slot=0;slot<fieldEncounters.formations.length;slot++)if(Number(fieldEncounters.formations[slot])!==Number(oldEncounters.formations?.[slot]))edits.push({type:"fieldEncounter",map:row.key,kind:"formation",slot,value:fieldEncounters.formations[slot]});if(Number(fieldEncounters.rate)!==Number(oldEncounters.rate))edits.push({type:"fieldEncounter",map:row.key,kind:"rate",value:fieldEncounters.rate})}for(const tile of row.background?.tiles||[]){const before=base?.background?.tiles?.[tile.id];if(!before)continue;const edit={type:"background",map:row.key,tile:tile.id};for(const field of row.background.editableFields||[])if(tile[field]!==before[field])edit[field]=tile[field];if(Object.keys(edit).length>3)edits.push(edit)}for(const line of row.dialogue||[]){const before=base?.dialogue?.[line.id];if(before&&line.text!==before.text)edits.push({type:"dialogue",map:row.key,line:line.id,text:line.text})}for(const method of row.scripts?.methods||[]){const before=base?.scripts?.methods?.find(value=>value.id===method.id);if(before&&method.source!==before.source)edits.push({type:"script",map:row.key,method:method.id,source:method.source})}for(const triangle of row.walkmesh?.triangles||[])for(const vertex of triangle.vertices){const before=base?.walkmesh?.triangles?.[triangle.id]?.vertices?.[vertex.id];if(!before)continue;const edit={type:"walkmesh",map:row.key,triangle:triangle.id,vertex:vertex.id};for(const field of ["x","y","z","adjacent"])if(Number(vertex[field])!==Number(before[field]))edit[field]=vertex[field];if(Object.keys(edit).length>4)edits.push(edit)}for(const player of row.players||[])for(const param of player.params||[]){const before=base?.players?.[player.id]?.params?.[param.id];if(before&&Number(param.value)!==Number(before.value))edits.push({map:row.key,player:player.id,param:param.id,value:param.value})}for(const kind of ["gateway","trigger"]){const collection=kind==="gateway"?"gateways":"triggers",entries=row.entrances?.[collection]||[],oldEntries=base?.entrances?.[collection]||[];for(const entry of entries){const old=oldEntries[entry.id],idField=kind==="gateway"?"fieldId":"doorId";if(old&&Number(entry[idField])!==Number(old[idField]))edits.push({type:"entrance",map:row.key,kind,slot:entry.id,field:idField,value:entry[idField]});for(const point of (kind==="gateway"?["exitA","exitB","destination"]:["lineA","lineB"]))for(const axis of ["x","y","z"])if(old&&Number(entry[point][axis])!==Number(old[point][axis]))edits.push({type:"entrance",map:row.key,kind,slot:entry.id,field:point,axis,value:entry[point][axis]})}}}
        if(edits.length)jobs.push(api("/api/field/save",post({edits})));
      }
      if(signature(state.data.init)!==signature(state.base.init))jobs.push(api("/api/init/save",post({edits:startingDataEdits()})));
      const settingsDirty=signature(state.data.settings)!==signature(state.base.settings);
      const results=await Promise.all(jobs);
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
  async function loadDataset(dataset,tolerant=false){const suffix=`dataset=${encodeURIComponent(dataset)}`,get=path=>tolerant?api(path).catch(()=>null):api(path);const [cards,items,menuItems,shops,weapons,magic,gfs,characters,abilityJunction,abilityCommand,abilityStat,abilityCharacter,abilityParty,abilityGf,abilityMenu,text,enemies,enemyTables,enemyAi,enemyBattleText,refine,encounters,world,fields,init]=await Promise.all([get(`/api/cards?${suffix}`),get(`/api/items?${suffix}`),get(`/api/menu-items?${suffix}`),get(`/api/shops?${suffix}`),get(`/api/weapons?${suffix}`),get(`/api/kernel?section=2&${suffix}`),get(`/api/kernel?section=3&${suffix}`),get(`/api/kernel?section=7&${suffix}`),get(`/api/kernel?section=12&${suffix}`),get(`/api/kernel?section=13&${suffix}`),get(`/api/kernel?section=14&${suffix}`),get(`/api/kernel?section=15&${suffix}`),get(`/api/kernel?section=16&${suffix}`),get(`/api/kernel?section=17&${suffix}`),get(`/api/kernel?section=18&${suffix}`),get(`/api/text?${suffix}`),get(`/api/enemies?${suffix}`),get(`/api/enemy-tables?${suffix}`),get(`/api/enemy-ai?${suffix}`),get(`/api/enemy-battle-text?${suffix}`),get(`/api/refine?${suffix}`),get(`/api/encounters?${suffix}`),get(`/api/world-map?${suffix}`),get(`/api/fields?${suffix}`),get(`/api/init?${suffix}`)]);return {cards,items,menuItems,shops,weapons,magic,gfs,characters,abilityJunction,abilityCommand,abilityStat,abilityCharacter,abilityParty,abilityGf,abilityMenu,text,enemies,enemyTables,enemyAi,enemyBattleText,refine,encounters,world,fields,init}}
  async function reloadEditable(){const [current,vanilla,settings,references,platformConfig,mods]=await Promise.all([loadDataset("current"),loadDataset("vanilla"),api("/api/settings"),api("/api/references"),api("/api/platform-config"),api("/api/mods")]);for(const dataset of [current,vanilla])for(const row of dataset.encounters.rows)row.name=encounterName(row);Object.assign(state.data,{...current,settings});state.vanilla=vanilla;state.mods=mods;state.references=references.rows||[];state.platformConfig=platformConfig;state.savedPlatformConfig=clone(platformConfig);state.referenceData={};await Promise.all(state.references.map(async reference=>{const dataset=await loadDataset(`reference:${reference.id}`,true);if(dataset?.encounters)for(const row of dataset.encounters.rows)row.name=encounterName(row);state.referenceData[reference.id]=dataset}));for(const name of editableDatasets)state.base[name]=clone(state.data[name].rows);state.base.init=clone(state.data.init);state.base.settings=clone(settings)}
  async function switchProjectSource(value){const next=String(value||"mine");if(next===state.activeSource)return;if(next==="mine"){state.activeSource="mine";await reloadEditable()}else if(next==="vanilla"){state.activeSource="vanilla";for(const name of editableDatasets)state.data[name]=clone(state.vanilla[name]);state.data.init=clone(state.vanilla.init);state.data.settings=clone(state.base.settings||state.data.settings)}else if(next.startsWith("mod:")){const dataset=await loadDataset(next);for(const row of dataset.encounters.rows)row.name=encounterName(row);state.activeSource=next;Object.assign(state.data,dataset);state.data.settings=clone(state.base.settings||state.data.settings)}else throw new Error(`Unknown mod source: ${next}`);shell.history?.clear();render()}
  function displayModName(name){return name==="Lexer's Mod for FF8"?"Lexer's Mod":name}
  function projectSources(){
    const rows=[{key:"vanilla",label:"Vanilla",path:state.dashboard?.baseline?.root||"Extracted unchanged FF8 data",readOnly:true,enabled:true}];
    for(const mod of state.mods?.rows||[])if(mod.enabled||mod.selected)rows.push({key:mod.selected?"mine":`mod:${mod.id}`,label:displayModName(mod.name),path:mod.path,readOnly:!mod.selected,enabled:mod.enabled});
    return rows;
  }
  async function openModOrder(){
    let [latest,featured]=await Promise.all([api("/api/mods"),api("/api/mods/featured")]),working=clone(latest.rows||[]);
    const backdrop=el("div",{class:"lex-dialog-backdrop","data-lex-history-control":true});
    const list=el("div",{class:"ff8-mod-list"}),featuredList=el("div",{class:"ff8-featured-list"}),conflicts=el("div",{class:"ff8-mod-conflicts"});
    const close=()=>backdrop.remove();
    const renderConflicts=composition=>{
      const rows=composition?.conflicts||[];
      conflicts.replaceChildren(el("strong",{},"CONFLICTS"),...(rows.length?rows.map(row=>el("div",{class:"ff8-mod-conflict"},el("span",{},row.path),el("b",{},`Winner: ${row.winner}`),el("small",{},`Claimants, low to high: ${row.claimants.join(" → ")}`))):[el("div",{class:"readonly-note"},"No file conflicts in the active order.")]));
    };
    const applyResult=result=>{latest=result;working=clone(result.rows||[]);state.mods=result;draw();renderConflicts(result.composition);shell.refresh()};
    const confirmDelete=mod=>{
      const layer=el("div",{class:"lex-dialog-backdrop","data-lex-history-control":true}),cancel=el("button",{class:"lex-dialog-action",type:"button",onclick:()=>layer.remove()},"Cancel"),remove=el("button",{class:"lex-dialog-action primary",type:"button"},"Delete Mod");
      remove.onclick=async()=>{remove.disabled=cancel.disabled=true;try{if(state.activeSource===`mod:${mod.id}`)await switchProjectSource("mine");const result=await api(`/api/mods/${encodeURIComponent(mod.id)}`,{method:"DELETE"});applyResult(result);featured=await api("/api/mods/featured");drawFeatured();layer.remove();setStatus(`Deleted ${mod.name}`)}catch(error){layer.remove();showAlert({title:"Could not delete mod",message:error.message||String(error)})}};
      layer.append(el("section",{class:"lex-dialog",role:"alertdialog","aria-modal":"true"},el("h2",{},`DELETE ${mod.name.toUpperCase()}?`),el("p",{},"This removes only this managed mod. It does not remove FFNx, the game, other mods, or your editable project."),el("div",{class:"lex-dialog-actions"},cancel,remove)));document.body.append(layer);remove.focus();
    };
    const installFeatured=async entry=>{const button=featuredList.querySelector(`[data-featured-id="${CSS.escape(entry.id)}"] button`);if(button)button.disabled=true;try{const result=await api("/api/mods/featured/install",post({id:entry.id}));applyResult(result);featured=await api("/api/mods/featured");drawFeatured();setStatus(`Installed ${result.installed?.name||entry.name}`)}catch(error){showAlert({title:`Could not download ${entry.name}`,message:error.message||String(error)});if(button)button.disabled=false}};
    const drawFeatured=()=>featuredList.replaceChildren(...(featured.rows||[]).map(entry=>{const installed=working.find(mod=>mod.id===entry.id),selected=installed?.selected,button=el("button",{class:"ff8-mod-action",type:"button",disabled:!!selected,onclick:()=>installFeatured(entry)},selected?"SOURCE PROJECT":installed?"Update Latest":"Download Latest");return el("div",{class:"ff8-featured-row","data-featured-id":entry.id},el("span",{},el("b",{},displayModName(entry.name))," ",el("small",{class:"ff8-mod-badge"},"★ FEATURED")),button)}));
    const draw=()=>list.replaceChildren(...working.map((mod,index)=>{
      const check=el("input",{type:"checkbox",checked:mod.enabled,disabled:!!mod.error,"aria-label":`Enable ${mod.name}`,onchange:event=>{mod.enabled=event.target.checked;row.dataset.enabled=String(mod.enabled)}});
      const up=el("button",{class:"ff8-mod-move",type:"button",disabled:index===0,title:"Move toward lower priority",onclick:()=>{[working[index-1],working[index]]=[working[index],working[index-1]];draw()}},"↑");
      const down=el("button",{class:"ff8-mod-move",type:"button",disabled:index===working.length-1,title:"Move toward higher priority",onclick:()=>{[working[index],working[index+1]]=[working[index+1],working[index]];draw()}},"↓");
      const remove=mod.selected?el("span",{"aria-hidden":"true"}):el("button",{class:"ff8-mod-action",type:"button",title:`Delete ${mod.name}`,onclick:()=>confirmDelete(mod)},"Delete…");
      const folderOptions=el("span",{class:"ff8-mod-folder-options"},...(mod.folderConfig||[]).map(definition=>{const select=el("select",{"aria-label":`${mod.name}: ${definition.name}`,onchange:event=>{mod.folderOptions=mod.folderOptions||{};mod.folderOptions[definition.id]=Number(event.target.value)}},...definition.values.map(choice=>el("option",{value:String(choice.value),selected:Number(mod.folderOptions?.[definition.id]??definition.default)===Number(choice.value)},choice.name)));return el("label",{class:"ff8-mod-folder-option"},el("span",{},definition.name),select)}));
      const info=el("span",{class:"ff8-mod-name"},el("b",{},displayModName(mod.name)," ",mod.featured?el("small",{class:"ff8-mod-badge"},"★ FEATURED"):null),el("small",{},mod.error||`${mod.selected?"EDIT TARGET":mod.container==="iroj"?"IROJ ARCHIVE":"READ-ONLY FOLDER"}${mod.version?` · ${mod.version}`:""} · ${mod.path}`),mod.folderError?el("small",{class:"ff8-mod-folder-error"},`Conditional folders disabled: ${mod.folderError}`):null,(mod.folderConfig||[]).length?folderOptions:null);
      const row=el("div",{class:"ff8-mod-row","data-enabled":String(mod.enabled),"data-mod-id":mod.id},check,info,remove,up,down);return row;
    }));
    const archiveInput=el("input",{type:"file",accept:".iroj",hidden:true,onchange:async event=>{const file=event.target.files?.[0];if(!file)return;importButton.disabled=true;try{const result=await api(`/api/mods/import?filename=${encodeURIComponent(file.name)}`,{method:"POST",headers:{"Content-Type":"application/octet-stream"},body:file});working.splice(0,working.length,...clone(result.rows||[]));draw();setStatus(`Imported ${result.imported?.name||file.name}`)}catch(error){showAlert({title:"Could not import IROJ",message:error.message||String(error)})}finally{event.target.value="";importButton.disabled=false}}});
    const importButton=el("button",{class:"lex-dialog-action",type:"button",onclick:()=>archiveInput.click()},"Import IROJ…");
    const cancel=el("button",{class:"lex-dialog-action",type:"button",onclick:close},"Cancel");
    const save=el("button",{class:"lex-dialog-action primary",type:"button",onclick:async()=>{save.disabled=true;try{state.mods=await api("/api/mods/configure",post({order:working.map(row=>row.id),enabled:Object.fromEntries(working.map(row=>[row.id,row.enabled])),folderOptions:Object.fromEntries(working.map(row=>[row.id,row.folderOptions||{}]))}));if(state.activeSource.startsWith("mod:")&&!state.mods.rows.some(row=>`mod:${row.id}`===state.activeSource&&row.enabled))await switchProjectSource("mine");renderConflicts(state.mods.composition);shell.refresh();setStatus("Saved FF8 mod load order")}catch(error){showAlert({title:"Could not save load order",message:error.message||String(error)})}finally{save.disabled=false}}},"Save Order");
    renderConflicts(latest.composition);draw();drawFeatured();
    backdrop.append(el("section",{class:"lex-dialog ff8-mod-order",role:"dialog","aria-modal":"true","aria-label":"FF8 mod load order"},el("h2",{},"FF8 MOD LOAD ORDER"),el("div",{class:"ff8-mod-priority"},el("span",{},"LOW PRIORITY"),el("span",{},"HIGH PRIORITY")),list,featuredList,conflicts,archiveInput,el("div",{class:"lex-dialog-actions"},importButton,cancel,save)));
    document.body.append(backdrop);
  }
  function discardAll(){for(const name of editableDatasets)if(state.data[name])state.data[name].rows=clone(state.base[name]||[]);state.data.init=clone(state.base.init||{});state.data.settings=clone(state.base.settings||{});state.platformConfig=clone(state.savedPlatformConfig);shell.history?.clear();setStatus("Restored the last saved state");render();shell.refresh()}
  let cardsUI;
  function renderCards(){cardsUI??=FF8CardsUI({el,state,rowOf,filtered,showPaged,sharedDetail,detailSection,detailField,numberControl,selectControl,sourceControl,referenceValues,infoHelp,shell,noteFieldEdit,subtabBar,detailPanel,recordId,columnList,conceptIcon,ensureFieldDetail});return cardsUI.render()}
  const views={cards:renderCards,abilities:renderAbilities,starting:renderStartingData,items:renderItems,refine:renderRefine,shops:renderShops,weapons:renderWeapons,magic:()=>renderKernel("magic","Magic"),gfs:renderGFs,characters:renderCharacters,text:renderText,enemies:renderEnemies,encounters:renderEncounters,maps:renderMaps,world:renderWorldMap,fields:renderFields,formulae:renderFormulae,settings:renderSettings,datamap:renderDataMap,dashboard:renderDashboard};
  // An ability record lives in a category subtab of Abilities, so a link to one
  // names its dataset (abilityJunction) and lands on that subtab.
  function navigate(tab){if(tab==="fields"||tab==="world"){state.mapsTab=tab==="fields"?"field":"world";tab="maps"}if(/^ability[A-Z]/.test(tab)){state.abilityTab=tab;tab="abilities"}state.tab=tab;render()}
  function render(){document.querySelectorAll("nav button[data-tab]").forEach(button=>button.classList.toggle("active",button.dataset.tab===state.tab));if(state.booting||state.bootFailed)return;const toolbar=$("#toolbar");toolbar.hidden=false;toolbar.classList.toggle("portrait-toolbar",state.tab==="gfs"||state.tab==="characters");views[state.tab]();shell.refresh()}
  async function prepareGameplayLaunch(){if(dirtyCount())await saveAll();const result=await api("/api/settings/activate",post({}));if(!result.ready)throw new Error("The FFNx gameplay patch did not pass its launch check.");setStatus("Gameplay patch ready")}
  async function confirmGameplayPatch(){for(let attempt=0;attempt<40;attempt++){await new Promise(resolve=>setTimeout(resolve,500));const status=await api("/api/settings/runtime");if(status.loaded){setStatus("FFNx loaded the gameplay patch");return}if(status.logReady&&attempt>5){showAlert({title:"FFNx did not load the gameplay patch",message:status.message});return}}showAlert({title:"FFNx patch check timed out",message:"FFNx did not write a current patch result within 20 seconds. The game can remain open, but these gameplay settings are not confirmed active."})}
  const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ff8",name:"Final Fantasy 8",themeName:"ff8",theme:{bg:"#000",panel:"#626262","panel-2":"#4f4f4f",border:"#929292",text:"#fff",muted:"#d0d0d0",accent:"#aa2432","accent-text":"#fff",highlight:"#fff",success:"#d8d8d8",font:'"FF8 Menu","Arial Narrow",sans-serif',"heading-font":'"FF8 Menu","Arial Narrow",sans-serif'}},tabs:[["characters","Characters"],["cards","Cards"],["encounters","Encounters"],["maps","Maps"],["enemies","Enemies"],["formulae","Formulae"],["gfs","GFs"],["items","Items"],["refine","Refine"],["abilities","Abilities"],["magic","Magic"],["text","Text"],["shops","Shops"],["starting","Start"],["weapons","Weapons"],["settings","Tweaks"]].map(([id,label])=>({id,label})),activeTab:()=>state.tab,navigate,resetView:tab=>{state.columnPrefs[tab]?.reset?.()},help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the FF8 Data Map",info:()=>navigate("dashboard"),infoActive:()=>state.tab==="dashboard",infoTitle:"Open FF8 setup and runtime information",projectSnapshot:async()=>({canCreate:false,projects:[]}),projectSources:projectSources,projectActiveSource:()=>state.activeSource,selectProjectSource:switchProjectSource,sourcesReplaceProjects:true,manageProjectSources:openModOrder,pendingChanges:()=>LexeditorUI.pendingChangeList({...state.base,platformConfig:state.savedPlatformConfig},{...historyCapture(),platformConfig:state.platformConfig}),dirtyCount,readonly:()=>state.activeSource!=="mine",save:saveAll,discard:discardAll,beforeLaunch:prepareGameplayLaunch,afterLaunch:confirmGameplayPatch,history:{capture:historyCapture,restore:historyRestore,render,enabled:()=>!state.booting&&state.activeSource==="mine",limit:50}});
  async function boot(){try{[state.dashboard,state.datamap]=await Promise.all([api("/api/dashboard"),api("/api/datamap")]);LexeditorUI.configureThemeSounds(state.dashboard.themeSounds);await reloadEditable();state.booting=false;setStatus(state.dashboard.runtime.installed?"FFNx ready":"FFNx needed for in-game loading");render();LexeditorUI.finishPluginLoading()}catch(error){state.booting=false;state.bootFailed=true;LexeditorUI.finishPluginLoading();$("#main").replaceChildren(el("div",{class:"empty"},`Failed to load FF8 plugin: ${error.message}`));setStatus("Load failed")}}
  window.addEventListener("lexeditor-settings-ready",()=>{if(!state.booting&&state.tab==="dashboard")renderDashboard()});
  window.addEventListener("beforeunload",event=>{if(!window.__lexeditorNavigating&&dirtyCount())event.preventDefault()});
  boot();
  
