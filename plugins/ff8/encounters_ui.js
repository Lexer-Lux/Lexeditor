  // The Encounters tab: battle formations, the region/ground rule table that
  // picks an encounter group, and the groups themselves.
  //
  // What the game stores, and what that forces on this screen:
  //   * wmset section 1 is a flat list of four-byte rules, each holding a
  //     region code, a ground code and an encounter-group number. The list
  //     ends at a zero entry and the section's length is fixed by the file's
  //     pointer table, so a rule can be re-aimed but one cannot be added or
  //     removed here. That is why the table below edits only the group number:
  //     every cell that holds a rule is a rule the file already has.
  //   * section 4 groups eight scene.out formation numbers. A formation is a
  //     scene.out record with eight enemy slots.
  function encounterRuleRows(){return state.data.world?.rows?.filter(row=>row.kind==="helper")||[]}
  function encounterGroupRows(){return state.data.world?.rows?.filter(row=>row.kind==="group")||[]}
  function encounterGroupById(id){return encounterGroupRows().find(row=>Number(row.id)===Number(id))||null}
  function encounterRowById(id){return state.data.encounters?.rows?.find(row=>Number(row.id)===Number(id))||null}
  function encounterRuleById(id){return encounterRuleRows().find(row=>Number(row.id)===Number(id))||null}
  function encounterRulesForGroup(id){return encounterRuleRows().filter(rule=>Number(rule.encounterGroup)===Number(id))}
  function encounterCellKey(regionId,groundId){return `${Number(regionId)}:${Number(groundId)}`}

  // The region and ground pairs the world map can actually present to the
  // lookup: each terrain segment's own region cell crossed with the ground
  // codes its polygons use. An empty pair here is a combination the player can
  // stand on with no rule stored for it.
  function encounterReachablePairs(){
    const pairs=new Map();
    for(const segment of state.data.world?.rows||[]){
      if(segment.kind!=="worldSegment")continue;
      const region=worldRow(state.data,"region",segment.id);
      if(!region)continue;
      for(const ground of segment.groundTypes||[]){
        const key=encounterCellKey(region.regionId,ground);
        pairs.set(key,(pairs.get(key)||0)+1);
      }
    }
    return pairs;
  }

  function showEncounterSubtab(tab,view,id){
    state.encountersTab=tab;
    if(view){state.selected[view]=id;state.pages[view]=0;state.filters[view]="";state.modOnly=false}
    navigate("encounters");
  }

  // ---- Enemy previews ------------------------------------------------------
  // A battle model file carries the enemy number it belongs to and its TIM
  // images, which is the same picture the Models tab shows. There is no other
  // rendered enemy art in the game data, so a slot with no battle texture says
  // so instead of showing a stand-in.
  function encounterEnemyTexture(enemyId){
    const model=state.data.models?.rows?.find(row=>row.enemyId!=null&&Number(row.enemyId)===Number(enemyId)&&(row.tims?.length||0)>0);
    if(!model)return null;
    const target=`battle/${model.file}#0`;
    return el("img",{src:`/assets/texture.png?id=${encodeURIComponent(target)}&palette=0&dataset=${encodeURIComponent(assetDataset())}`,
      alt:`Battle texture for ${model.name}`,loading:"lazy"});
  }
  function encounterSlotLevelText(slot){
    const rule=encounterLevelRule(slot.level);
    if(rule.mode==="fixed")return `Level ${rule.value}`;
    if(rule.mode==="maximum")return `Level up to ${rule.value}`;
    if(rule.mode==="ultimecia")return "Level 1 to 100";
    return `Level byte ${slot.level}`;
  }
  function encounterEnemyBox(slot){
    const enemy=enemyById(slot.enemyId);
    const name=slot.enabled
      ? recordHoverLabel("enemies",enemy,enemyDisplayName(enemy.name))
      : "Empty";
    const box=LexeditorUI.iconSlot({shape:"square",
      content:slot.enabled?encounterEnemyTexture(slot.enemyId):null,
      message:slot.enabled?"No battle texture":""});
    const attrs={"aria-label":`Battle position ${slot.slot+1}`,
      "data-lex-battle-position":String(slot.slot+1)};
    if(!slot.enabled)attrs["data-lex-empty-position"]="";
    return {caption:name,media:box,footer:slot.enabled?encounterSlotLevelText(slot):"—",attrs};
  }
  // Six boxes, one per battle position. scene.out keeps eight slots per
  // formation; slots 7 and 8 appear as extra boxes when they are switched on,
  // so nothing stored is hidden here. Formations edits all eight.
  function encounterPreviewGrid(row){
    if(!row)return LexeditorUI.notice({message:"This formation number is not a scene.out record, so it has no enemies to show."});
    const shown=row.slots.filter((slot,index)=>index<6||slot.enabled);
    // The shared figure grid names each enemy over its box and gives the level
    // under it, and wraps the boxes when the panel is too narrow for six.
    const grid=LexeditorUI.figureGrid(shown.map(encounterEnemyBox),{captionAbove:true});
    grid.setAttribute("aria-label",`Formation ${row.id} enemies`);
    return grid;
  }
  function encounterBattleChoice(group,change){
    const control=selectControl(encounterGroupBattleSlot(),group.encounters.map((value,index)=>({
      value:index,name:`Battle ${index+1} · formation ${value}`})),value=>{state.encounterBattleSlot=Number(value);change()});
    control.setAttribute("aria-label",`Battle position shown for encounter group ${group.id}`);
    return control;
  }
  function encounterGroupBattleSlot(){return Math.max(0,Math.min(7,Number(state.encounterBattleSlot)||0))}

  // ---- Rules: region x ground -> group ------------------------------------
  function encounterRuleVanilla(rule){return worldRow(state.vanilla,"helper",rule.id)?.encounterGroup}
  function encounterRuleReferences(rule){
    return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,
      value:worldRow(state.referenceData[reference.id],"helper",rule.id)?.encounterGroup}))
      .filter(entry=>entry.value!==undefined);
  }
  function encounterRuleControl(rule,refresh){
    const maximum=Math.max(0,encounterGroupRows().length-1);
    const apply=value=>{rule.encounterGroup=Math.max(0,Math.min(maximum,Number(value)||0));refresh()};
    const control=numberControl(rule.encounterGroup,0,maximum,1,value=>{rule.encounterGroup=Number(value);refresh()},
      {"aria-label":`Region ${rule.regionId} ground ${rule.groundId} encounter group`,class:"ff8-encounter-rule-input"});
    const select=()=>{state.selected.encounterRule=rule.id;refresh()};
    control.addEventListener("focus",select);
    control.addEventListener("pointerdown",select);
    return sourceControl(control,()=>rule.encounterGroup,encounterRuleVanilla(rule),encounterRuleReferences(rule),apply);
  }
  function encounterRuleCell(regionId,groundId,cells,reachable,refresh){
    const rules=cells.get(encounterCellKey(regionId,groundId))||[];
    if(!rules.length){
      const known=reachable.size>0;
      const onMap=reachable.has(encounterCellKey(regionId,groundId));
      const title=!known
        ? `No rule is stored for region ${regionId} with ground ${groundId}. World terrain is unavailable, so whether the map can reach this pair is unknown.`
        : onMap
          ? `The map has terrain with region ${regionId} and ground ${groundId}, and no rule is stored for it. The game has nothing to look up there.`
          : `No rule is stored for region ${regionId} with ground ${groundId}, and no world terrain uses that pair.`;
      // A shape the map really uses and has nothing stored for is the one that
      // needs attention; the rest are simply empty cells.
      const blank=LexeditorUI.badge(onMap?"!":"—",{...(onMap?{tone:"warning"}:{}),title});
      blank.dataset.lexRuleCell=onMap?"missing":"blank";
      return blank;
    }
    const controls=rules.map(rule=>encounterRuleControl(rule,refresh));
    if(rules.length===1)return controls[0];
    // Two stored rules for one cell: the first control keeps the cell editable
    // and the badge says the rest are there. Nothing is hidden.
    const clash=LexeditorUI.tileGrid([...controls,
      LexeditorUI.badge("!!",{tone:"warning",
        title:`${rules.length} stored rules use region ${regionId} with ground ${groundId}. Only one of them can decide the battles there, and which one is not established. Point the spare rules somewhere else.`})],
      {columns:rules.length+1,minWidth:64});
    clash.dataset.lexRuleCell="clash";
    return clash;
  }
  function encounterRuleTable(refresh){
    const rules=encounterRuleRows(),reachable=encounterReachablePairs(),cells=new Map();
    for(const rule of rules){
      const key=encounterCellKey(rule.regionId,rule.groundId);
      if(!cells.has(key))cells.set(key,[]);
      cells.get(key).push(rule);
    }
    const axis=(fromRules,index)=>[...new Set([...fromRules,
      ...[...reachable.keys()].map(key=>Number(key.split(":")[index]))])].sort((left,right)=>left-right);
    const regions=axis(rules.map(rule=>Number(rule.regionId)),0);
    const grounds=axis(rules.map(rule=>Number(rule.groundId)),1);
    const rows=regions.map(regionId=>({id:regionId,regionId}));
    const columns=[{key:"regionId",label:"REGION",numberedId:true,sortable:false,
      help:"Region code of the world-map cell the player is standing in. Regions are set on the World tab.",
      render:row=>row.regionId},
      ...grounds.map(ground=>({key:`ground:${ground}`,label:`GROUND ${ground}`,sortable:false,align:"center",
        help:`Terrain code ${ground}. The cell below holds the encounter group the game uses for this region and this ground.`,
        render:row=>encounterRuleCell(row.regionId,ground,cells,reachable,refresh)}))];
    const template=`84px repeat(${Math.max(1,grounds.length)},minmax(66px,1fr))`;
    return {table:columnList({rows,key:row=>row.id,columns,localSort:false,template,
      class:"ff8-encounter-rule-table ff8-record-list","aria-label":"Encounter rules by region and ground"}),
      regions,grounds,rules,cells,reachable};
  }
  function encounterRuleSummary(built){
    const clashes=[...built.cells.values()].filter(entry=>entry.length>1).length;
    const missing=[...built.reachable.keys()].filter(key=>!built.cells.has(key)).length;
    const parts=[`${built.rules.length} stored rules over ${built.regions.length} regions and ${built.grounds.length} ground codes`];
    parts.push(built.reachable.size
      ? `${missing} of ${built.reachable.size} region and ground pairs used by world terrain have no rule`
      : "world terrain is unavailable, so unreachable and uncovered pairs cannot be counted");
    parts.push(clashes?`${clashes} ${clashes===1?"pair has":"pairs have"} more than one rule`
      :"no pair has more than one rule");
    return LexeditorUI.detailNote(`${parts.join(". ")}.`);
  }

  // ---- Group preview panel -------------------------------------------------
  function encounterGroupPreviewPanel(rule,refresh,origin){
    const group=encounterGroupById(rule?.encounterGroup);
    const where=rule?`Region ${rule.regionId} · ground ${rule.groundId}`:"No rule selected";
    const help="The encounter group this rule selects, and the enemies waiting in one of its eight battles. "
      +"The group name opens the Groups page at that group. Each box is a battle position: the enemy's name above it and the level it fights at below.";
    if(!group)return detailPanel({title:"NO ENCOUNTER GROUP",help,meta:where,
      className:"ff8-encounter-group-preview",
      body:LexeditorUI.notice({message:"Select a group number in the table to preview the battles it holds."})});
    const slot=encounterGroupBattleSlot(),formationId=group.encounters[slot];
    const title=hoverable({content:`ENCOUNTER GROUP ${group.id}`,targetType:"encounterGroups",targetId:group.id,
      targetLabel:`encounter group ${group.id}`,class:"ff8-encounter-group-link",
      activate:()=>showEncounterSubtab("groups","encounterGroups",group.id)});
    const finder=el("button",{type:"button",title:"Choose an encounter group","aria-label":"Choose an encounter group",
      onclick:event=>{event.preventDefault();event.stopPropagation();
        beginSearcher({type:"encounterGroups",prompt:"Select the encounter group this region and ground should use.",
          target:()=>showEncounterSubtab("groups"),origin,
          accept:value=>{const rule=encounterRuleById(state.selected.encounterRule);if(rule)rule.encounterGroup=Number(value);refresh()}})}},
      LexeditorUI.selectionIcon());
    return detailPanel({title,help,meta:where,
      className:"ff8-encounter-group-preview",identity:recordId(group.id),
      body:[detailField({label:"GROUP",showType:false,
        help:infoHelp("The encounter group the selected rule points at. Choose another from the Groups list and the rule's cell in the table changes with it."),
        control:LexeditorUI.choiceField(hoverable({content:`Group ${group.id}`,targetType:"encounterGroups",
          targetId:group.id,targetLabel:`encounter group ${group.id}`,
          activate:()=>showEncounterSubtab("groups","encounterGroups",group.id)}),finder)}),
      detailField({label:"BATTLE",showType:false,
        help:infoHelp("A group holds eight battle formations and the game picks one of them at random. Choose which of the eight to preview here."),
        control:encounterBattleChoice(group,refresh)}),
      detailSection({className:"ff8-encounter-preview-section",title:`FORMATION ${formationId}`,
        help:infoHelp("The enemies in the chosen battle. A name above each box, the level it fights at below it. Open a name to edit that enemy."),
        body:[encounterPreviewGrid(encounterRowById(formationId))]})]});
  }

  function renderEncounterRules(){
    const toolbar=$("#toolbar");toolbar.replaceChildren();toolbar.hidden=true;
    if(!state.data.world?.rows?.length)return LexeditorUI.notice({message:"World-map data is unavailable, so encounter rules cannot be shown."});
    // A reload can leave a selection pointing at a rule that is gone.
    if(!encounterRuleById(state.selected.encounterRule))
      state.selected.encounterRule=encounterRuleRows()[0]?.id??null;
    let layout=null,preview=null;
    const refresh=()=>{
      if(!layout)return;
      const next=encounterGroupPreviewPanel(encounterRuleById(state.selected.encounterRule),
        refresh,()=>showEncounterSubtab("rules"));
      layout.lexReplacePanel(preview,next);preview=next;shell.refresh();
    };
    const built=encounterRuleTable(refresh);
    const rule=encounterRuleById(state.selected.encounterRule);
    const table=detailPanel({title:"ENCOUNTER RULES",className:"ff8-encounter-rules-panel",
      help:"Every stored rule, with region codes down the side and ground codes across the top. The number in a cell is the encounter group the game uses there. "
        +"A dash means no rule is stored for that pair; an exclamation mark means world terrain uses that pair and no rule covers it. "
        +"Where two rules store the same pair both are shown and marked; which of them the game obeys is not established here. "
        +"Rules cannot be added or removed: the file reserves a fixed number of them.",
      body:[encounterRuleSummary(built),built.table]});
    preview=encounterGroupPreviewPanel(rule,refresh,()=>showEncounterSubtab("rules"));
    layout=LexeditorUI.panelLayout([table,preview],"ff8-encounter-rules",
      {layoutKey:"ff8-encounter-rules",defaultSizes:[1.35,1]});
    return layout;
  }

  // ---- Groups --------------------------------------------------------------
  function encounterGroupSlotControl(row,index,refresh){
    const value=row.encounters[index],formation=encounterRowById(value);
    const label=formation?`${value} · ${encounterName(formation)}`:`Formation ${value} (not in scene.out)`;
    const link=hoverable({content:label,targetType:"encounters",targetId:value,targetLabel:`battle formation ${value}`,
      activate:()=>showEncounterSubtab("formations","encounters",Number(value))});
    const accept=next=>{row.encounters[index]=Number(next);refresh()};
    const finder=el("button",{type:"button",title:"Choose a battle formation",
      "aria-label":`Choose the battle formation for group ${row.id} battle ${index+1}`,
      onclick:event=>{event.preventDefault();event.stopPropagation();
        beginSearcher({type:"encounters",prompt:`Select the battle formation for group ${row.id}, battle ${index+1}.`,
          target:()=>showEncounterSubtab("formations"),
          origin:()=>showEncounterSubtab("groups","encounterGroups",row.id),accept})}},
      LexeditorUI.selectionIcon());
    const vanilla=worldRow(state.vanilla,"group",row.id)?.encounters?.[index];
    const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,
      value:worldRow(state.referenceData[reference.id],"group",row.id)?.encounters?.[index]})).filter(entry=>entry.value!==undefined);
    return sourceControl(LexeditorUI.choiceField(link,finder),()=>row.encounters[index],vanilla,references,accept,
      next=>{const target=encounterRowById(next);return target?`${next} · ${encounterName(target)}`:String(next)});
  }
  function encounterGroupUsage(row){
    const rules=encounterRulesForGroup(row.id);
    if(!rules.length)return LexeditorUI.notice({message:"No region and ground rule selects this group, so the world map never starts these battles."});
    return columnList({rows:rules,key:rule=>rule.id,fill:true,localSort:false,
      class:"ff8-encounter-usage-table ff8-record-list","aria-label":`Rules that select encounter group ${row.id}`,
      columns:[{key:"id",label:"RULE",numberedId:true,sortable:false,
          help:"Position of this rule in the stored list. The number is fixed; the group it points at is not.",
          render:rule=>rule.id},
        {key:"regionId",label:"REGION",sortable:false,help:"Region code this rule matches.",render:rule=>rule.regionId},
        {key:"groundId",label:"GROUND",sortable:false,help:"Ground code this rule matches.",render:rule=>rule.groundId},
        {key:"open",label:"RULES PAGE",sortable:false,help:"Open the rules table with this rule selected.",
          render:rule=>hoverable({content:`Region ${rule.regionId} · ground ${rule.groundId}`,targetType:"encounterRules",
            targetId:rule.id,targetLabel:`encounter rule ${rule.id}`,
            activate:()=>{state.selected.encounterRule=rule.id;showEncounterSubtab("rules")}})}]});
  }
  function encounterGroupDetail(row,prefs){
    const refresh=()=>renderEncounters();
    const slot=encounterGroupBattleSlot(),formationId=row.encounters[slot];
    const battles=columnList({rows:row.encounters.map((value,index)=>({id:index,value})),key:entry=>entry.id,
      fill:true,localSort:false,editable:true,class:"ff8-encounter-group-table ff8-record-list",
      template:"80px minmax(220px,1.6fr) minmax(90px,.6fr)","aria-label":`Encounter group ${row.id} battles`,
      columns:[{key:"id",label:"BATTLE",numberedId:true,sortable:false,
        help:"Position in this group. The game picks one of the eight when a battle starts on this terrain.",
        render:entry=>entry.id+1},
      {key:"value",label:"FORMATION",sortable:false,
        help:"The scene.out battle formation used by this position. Use the chooser to pick one from the Formations page, or open the name to edit it there.",
        render:entry=>encounterGroupSlotControl(row,entry.id,refresh)},
      {key:"preview",label:"PREVIEW",sortable:false,
        help:"Show this battle's enemies in the preview below.",
        render:entry=>el("button",{type:"button",class:"ff8-encounter-preview-pick","aria-pressed":String(entry.id===slot),
          "aria-label":`Preview battle ${entry.id+1} of encounter group ${row.id}`,
          onclick:()=>{state.encounterBattleSlot=entry.id;refresh()}},entry.id===slot?"Shown":"Show")}]});
    return sharedDetail({...row,name:`ENCOUNTER GROUP ${row.id}`},prefs,[
      detailSection({title:"BATTLES IN THIS GROUP",
        help:infoHelp("The eight battle formations this group can start. Changing one changes which enemies appear on every terrain that uses this group."),
        body:[battles]}),
      detailSection({className:"ff8-encounter-preview-section",title:`FORMATION ${formationId} ENEMIES`,
        help:infoHelp("The enemies in the battle chosen above: a name over each box and the level it fights at underneath. Open a name to edit that enemy."),
        body:[encounterPreviewGrid(encounterRowById(formationId))]}),
      detailSection({title:"WHERE THIS GROUP IS USED",
        help:infoHelp("The region and ground rules that select this group. A group with no rule is stored but never reached."),
        body:[encounterGroupUsage(row)]})],
      "ff8-encounter-group-detail");
  }
  function encounterGroupEnemyNames(row){
    const names=new Set();
    for(const value of row.encounters){
      const formation=encounterRowById(value);
      if(!formation)continue;
      for(const slot of formation.slots)if(slot.enabled)names.add(enemyDisplayName(slot.enemyName));
    }
    return [...names].join(", ");
  }
  function renderEncounterGroups(){
    const groups=encounterGroupRows();
    if(!groups.length)return LexeditorUI.notice({message:"World-map data is unavailable, so encounter groups cannot be shown."});
    const sortValue=(row,key)=>key==="enemies"?encounterGroupEnemyNames(row)
      :key==="ruleCount"?encounterRulesForGroup(row.id).length
      :key==="encounters"?row.encounters.join(",")
      :rowSortValue(row,key);
    const query=state.filters.encounterGroups.trim().toLocaleLowerCase();
    const matching=groups.filter(row=>!query
      ||`${row.id} ${row.encounters.join(" ")} ${encounterGroupEnemyNames(row)}`.toLocaleLowerCase().includes(query));
    const [sortKey,direction]=state.sorts.encounterGroups;
    const visible=[...matching].sort((left,right)=>direction*String(sortValue(left,sortKey)).localeCompare(
      String(sortValue(right,sortKey)),undefined,{numeric:true,sensitivity:"base"}));
    return showPaged("encounterGroups",visible,[
      {key:"id",label:"GROUP",help:"Number of this encounter group. Rules point at this number."},
      {key:"encounters",label:"FORMATIONS",help:"The eight scene.out battle formations in this group.",
        render:row=>row.encounters.join(", ")},
      {key:"enemies",label:"ENEMIES",help:"Every enemy switched on in this group's battles.",
        sortValue:row=>encounterGroupEnemyNames(row),render:row=>encounterGroupEnemyNames(row)||"none"},
      {key:"ruleCount",label:"RULES",
        help:"How many region and ground rules choose this group. Zero means the world map never reaches it.",
        sortValue:row=>encounterRulesForGroup(row.id).length,
        render:row=>encounterRulesForGroup(row.id).length||"none"}],
      encounterGroupDetail,"66px minmax(118px,1fr) minmax(130px,1.2fr) 66px",
      {noun:"encounter groups",fixedTemplate:true,defaultSplit:36,minLeft:420,minRight:540},false);
  }

  // ---- The tab -------------------------------------------------------------
  function renderEncounterFormations(){
    const rows=filtered("encounters",["name","id","stageId"]);
    return showPaged("encounters",rows,[{key:"id",label:"ID",help:"scene.out record number of this battle formation. Encounter groups and field maps refer to it."},
      {key:"name",label:"Encounter",help:"The enemies switched on in this formation. Select a row to edit its slots."},
      {key:"stageId",label:"Stage",pinned:false,help:"Battle stage number used when this formation starts."}],
      encounterDetail,"74px minmax(180px,1fr)",{defaultSplit:26,minLeft:220,minRight:600},false);
  }
  const encounterTabs=[
    {id:"formations",label:"Formations",help:"Every battle formation in scene.out: which enemies stand in which of the eight slots, the level they fight at, and the stage and cameras the battle uses."},
    {id:"rules",label:"Rules",help:"The world-map lookup: a region code and a ground code together choose one encounter group. Edit the group number in a cell to change which battles happen on that terrain. The file holds a fixed number of rules, so a pair with no rule cannot be given one here."},
    {id:"groups",label:"Groups",help:"An encounter group holds eight battle formations; the game picks one of them when a world-map battle starts. Rules choose the group, this page chooses its battles."}];
  function renderEncounters(){
    if(!encounterTabs.some(tab=>tab.id===state.encountersTab))state.encountersTab="formations";
    const bar=subtabBar({className:"ff8-encounter-tabs",tabs:encounterTabs,active:state.encountersTab,label:"Encounters",
      change:value=>{state.encountersTab=value;renderEncounters()}});
    const content=state.encountersTab==="rules"?renderEncounterRules()
      :state.encountersTab==="groups"?renderEncounterGroups()
      :renderEncounterFormations();
    $("#main").replaceChildren(LexeditorUI.stack(bar,content));
  }
