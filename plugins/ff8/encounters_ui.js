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
  function encounterEnemyPreview(enemyId){
    const model=state.data.models?.rows?.find(row=>row.enemyId!=null&&Number(row.enemyId)===Number(enemyId)&&row.file);
    if(!model)return null;
    return FF8ModelThumbnail({file:model.file,dataset:assetDataset(),label:model.name,revision:model.sha256});
  }
  function encounterSlotLevelText(slot){
    const rule=encounterLevelRule(slot.level);
    if(rule.mode==="fixed")return `Level ${rule.value}`;
    if(rule.mode==="maximum")return `Level up to ${rule.value}`;
    if(rule.mode==="ultimecia")return "Level 1 to 100";
    return "Special level";
  }
  function encounterEnemyBox(slot,formation,origin){
    const enemy=enemyById(slot.enemyId);
    const name=slot.enabled
      ? recordHoverLabel("enemies",enemy,enemyDisplayName(enemy.name))
      : "Empty";
    const finder=el('button',{type:'button',disabled:state.activeSource!=='mine',
      'aria-label':`Choose enemy for formation ${formation.id} slot ${slot.slot+1}`,
      onclick:()=>beginSearcher({type:'enemies',prompt:`Choose the enemy for formation ${formation.id}, slot ${slot.slot+1}.`,
        target:()=>navigate('enemies'),origin,
        accept:value=>{if(state.activeSource!=='mine')return;const next=enemyById(value);
          slot.enemyId=Number(value);slot.enemyName=next.name;slot.enabled=true;
          formation.name=encounterName(formation);shell.refresh();}})},LexeditorUI.selectionIcon());
    const card=LexeditorUI.recordCard({title:name,identity:slot.slot+1,
      image:slot.enabled?encounterEnemyPreview(slot.enemyId):LexeditorUI.noImage('Empty slot'),
      body:slot.enabled?encounterSlotLevelText(slot):null,action:finder});
    card.setAttribute('aria-label',`Battle position ${slot.slot+1}`);
    card.dataset.lexBattlePosition=String(slot.slot+1);
    if(!slot.enabled)card.dataset.lexEmptyPosition='';
    return card;
  }
  // Six boxes, one per battle position. scene.out keeps eight slots per
  // formation; slots 7 and 8 appear as extra boxes when they are switched on,
  // so nothing stored is hidden here. Formations edits all eight.
  function encounterPreviewGrid(row,origin){
    if(!row)return LexeditorUI.notice({message:"This formation number is not a scene.out record, so it has no enemies to show."});
    const shown=row.slots.filter((slot,index)=>index<6||slot.enabled);
    // The shared holder keeps six cards balanced as the pane narrows.
    const grid=LexeditorUI.tileGrid(shown.map(slot=>encounterEnemyBox(slot,row,origin)),{minWidth:100,balanced:true});
    grid.setAttribute("aria-label",`Formation ${row.id} enemies`);
    return grid;
  }

  // ---- Rules: region x ground -> group ------------------------------------
  function encounterRuleVanilla(rule){return worldRow(state.vanilla,"helper",rule.id)?.encounterGroup}
  function encounterRuleReferences(rule){
    return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,
      value:worldRow(state.referenceData[reference.id],"helper",rule.id)?.encounterGroup}))
      .filter(entry=>entry.value!==undefined);
  }
  // A rule's group is chosen with the thing finder: from the heading of the
  // group panel, or by right-clicking the rule's cell. A plain click shows
  // what the cell holds in that panel (Lexer, 2026-09-27).
  function chooseRuleGroup(rule,refresh){
    if(state.activeSource!=='mine')return;
    const apply=value=>{if(state.activeSource!=='mine'||!encounterGroupById(value))return;rule.encounterGroup=Number(value);refresh()};
    beginSearcher({type:'encounterGroups',prompt:`Choose the encounter group for region ${rule.regionId}, ground ${rule.groundId}.`,
      target:()=>showEncounterSubtab('groups'),origin:()=>showEncounterSubtab('rules'),accept:apply});
  }
  function encounterRuleControl(rule,refresh){
    const apply=value=>{if(state.activeSource!=='mine'||!encounterGroupById(value))return;rule.encounterGroup=Number(value);refresh()};
    const control=el('button',{type:'button',
      'aria-label':`Region ${rule.regionId} ground ${rule.groundId} encounter group`,class:'ff8-encounter-rule-input',
      title:'Click to show this group; right-click to choose a different group',
      oncontextmenu:event=>{event.preventDefault();state.selected.encounterRule=rule.id;chooseRuleGroup(rule,refresh)}},String(rule.encounterGroup));
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
          ? `Region ${regionId} has ground ${groundId} on the map, and no random battle starts on it: no rule is stored for it. The shipped game leaves many pairs like this, so it is not an error.`
          : `No rule is stored for region ${regionId} with ground ${groundId}, and no world terrain uses that pair.`;
      // A pair the map has but no rule for is normal - the shipped game starts
      // no battles on it - so it gets a quiet dot, not a warning mark (Lexer:
      // the untouched table was "chock full of !").
      const blank=LexeditorUI.readonlyField(onMap?"·":"—",{
        title:`${title} This cell cannot be edited because there is no stored rule.`,
        'aria-label':`Region ${regionId} ground ${groundId}: ${onMap?'on the map, no battles':'no rule'}`});
      blank.dataset.lexRuleCell=onMap?"no-battles":"blank";
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
    const columns=grounds.map(ground=>({key:`ground:${ground}`,label:String(ground),align:"center",
      render:row=>encounterRuleCell(row.regionId,ground,cells,reachable,refresh)}));
    const template=`52px repeat(${Math.max(1,grounds.length)},minmax(46px,1fr))`;
    return {table:LexeditorUI.matrixTable({rows,key:row=>row.id,columns,template,
      rowAxis:{key:"regionId",label:"REGION",numberedId:true,render:row=>row.regionId,
        help:"Region code of the world-map cell the player is standing in. Region codes are set on the World tab."},
      columnAxis:{label:"TERRAIN",help:"Terrain code of the ground the player is standing on. The region and terrain together choose an encounter group."},
      class:"ff8-encounter-rule-table ff8-record-list","aria-label":"Encounter rules by region and ground"}),
      regions,grounds,rules,cells,reachable};
  }

  // ---- Group preview panel -------------------------------------------------
  function encounterGroupPreviewPanel(rule,refresh,origin){
    const group=encounterGroupById(rule?.encounterGroup);
    if(!group)return detailPanel({title:"Encounter group",
      className:"ff8-encounter-group-preview",
      body:LexeditorUI.notice({message:"Select a group number in the table to preview the battles it holds."})});
    return encounterGroupPanel(group,refresh,origin,'ff8-encounter-group-preview',
      state.activeSource==='mine'?{find:()=>chooseRuleGroup(rule,refresh),
        findTitle:`Choose a different group for region ${rule.regionId}, ground ${rule.groundId}`}:{});
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
    const table=built.table;
    table.classList.add('ff8-encounter-rules-panel');
    preview=encounterGroupPreviewPanel(rule,refresh,()=>showEncounterSubtab("rules"));
    layout=LexeditorUI.panelLayout([table,preview],"ff8-encounter-rules",
      {layoutKey:"ff8-encounter-rules",defaultSizes:[1.35,1]});
    return layout;
  }

  // ---- Groups --------------------------------------------------------------
  function encounterGroupSlotControl(row,index,refresh,origin){
    const value=row.encounters[index];
    const link=hoverable({content:el("span",{},"Formation ",recordId(value)),targetType:"encounters",targetId:value,targetLabel:`battle formation ${value}`,class:'ff8-encounter-formation-link',
      activate:()=>showEncounterSubtab("formations","encounters",Number(value))});
    const accept=next=>{if(state.activeSource!=='mine'||!encounterRowById(next))return;row.encounters[index]=Number(next);refresh()};
    const finder=el("button",{type:"button",title:"Choose a battle formation",disabled:state.activeSource!=='mine',class:'ff8-encounter-formation-finder',
      "aria-label":`Choose the battle formation for group ${row.id} battle ${index+1}`,
      onclick:event=>{event.preventDefault();event.stopPropagation();
        beginSearcher({type:"encounters",prompt:`Select the battle formation for group ${row.id}, battle ${index+1}.`,
          target:()=>showEncounterSubtab("formations"),
          origin:origin||(()=>showEncounterSubtab("groups","encounterGroups",row.id)),accept})}},
      LexeditorUI.selectionIcon());
    const vanilla=worldRow(state.vanilla,"group",row.id)?.encounters?.[index];
    const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,
      value:worldRow(state.referenceData[reference.id],"group",row.id)?.encounters?.[index]})).filter(entry=>entry.value!==undefined);
    return sourceControl(LexeditorUI.choiceField(link,finder),()=>row.encounters[index],vanilla,references,accept,
      next=>`Formation #${next}`);
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
        {key:"groundId",label:"GROUND",sortable:false,help:"Ground code this rule matches.",render:rule=>worldGroundLink(rule.groundId)},
        {key:"open",label:"RULES PAGE",sortable:false,help:"Open the rules table with this rule selected.",
          render:rule=>hoverable({content:`Region ${rule.regionId} · ground ${rule.groundId}`,targetType:"encounterRules",
            targetId:rule.id,targetLabel:`encounter rule ${rule.id}`,
            activate:()=>{state.selected.encounterRule=rule.id;showEncounterSubtab("rules")}})}]});
  }
  function encounterGroupPanel(row,refresh,origin,className='ff8-encounter-group-detail',heading={}){
    // A formation can fill several of the eight slots, so the group does not
    // give every formation the same share (Lexer: "encounter chances aren't
    // actually equal ... the editor doesn't say that at all").
    const share=value=>row.encounters.filter(entry=>Number(entry)===Number(value)).length;
    const formations=row.encounters.map((value,index)=>{
      const strip=el('div',{class:'ff8-encounter-formation-row',
        'data-formation-position':index,'aria-label':`Battle ${index+1} of encounter group ${row.id}`},
        el('div',{class:'ff8-encounter-formation-choice'},encounterGroupSlotControl(row,index,refresh,origin),
          el('span',{class:'ff8-encounter-formation-share','data-formation-share':share(value)},`${share(value)} of ${row.encounters.length}`)),
        encounterPreviewGrid(encounterRowById(value),origin));
      return strip;
    });
    return detailPanel({title:'Encounter group',identity:recordId(row.id),className,...heading,
      help:'The game chooses one of these eight slots when this group starts a battle. A formation can fill several slots; the count beside it says how many. If the game picks a slot evenly, a formation in three slots comes up three times as often as one in a single slot; how it picks is not yet proven. Hover a formation ID to replace it. Changing an enemy changes that formation everywhere it is used. Special level means the enemy uses a level rule we do not yet understand.',
      body:[detailSection({body:LexeditorUI.stack({fill:false,className:'ff8-encounter-formations'},...formations)}),
        detailSection({title:'WHERE THIS GROUP IS USED',
          help:infoHelp('These region and ground rules select this group. Open a rule to change its group.'),
          body:[encounterGroupUsage(row)]})]});
  }
  function encounterGroupDetail(row,prefs){
    return encounterGroupPanel(row,()=>renderEncounters(),()=>showEncounterSubtab('groups','encounterGroups',row.id));
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
    {id:"rules",label:"Rules",help:"Each number is the encounter group used for that region and terrain. Choose a number to change the group. A dash means no rule is stored for a pair the loaded map does not use. A dot means the map has that ground in that region but no rule is stored, so no random battle starts there; the shipped game leaves many such pairs. Without map data, a dash means the pair's use is unknown. Cells without rules are read-only because this editor can change stored rules but cannot add them."},
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
