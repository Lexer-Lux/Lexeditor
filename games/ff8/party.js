  function renderCharacters(){const rows=[...state.data.characters.rows].sort((a,b)=>a.name.localeCompare(b.name,undefined,{sensitivity:"base"}));if(!rows.some(row=>row.id===state.selected.characters))state.selected.characters=rows[0]?.id??null;const row=rows.find(candidate=>candidate.id===state.selected.characters);if(!row){$("#toolbar").replaceChildren();$("#main").replaceChildren(LexeditorUI.notice({message:"No character records were found."}));return}const detailId="character-detail";$("#toolbar").replaceChildren(portraitTabs("characters",rows,row.id,detailId,id=>{state.selected.characters=id;renderCharacters();shell.refresh()}));$("#main").replaceChildren(detailPanel({heading:false,className:"lex-detail detail character-detail",attrs:{id:detailId,role:"tabpanel","aria-labelledby":`characters-tab-${row.id}`,"data-character":row.id},body:characterDetail(row)}))}
  const GF_ATTACK_FIELDS=new Set(['attack_animation','attack_type','gf_power','status_window_flags','target_info','attack_flags_type','attack_flags','target_animation','hit_count','element','status_1','status_2','status_attack_enabler','power_mod','level_mod','ability1_unlocker']);
  const gfPanelOrder=["GF Compatibility","General","Attack","Abilities"];
  function gfFieldsByPanel(row){const routed=new Map(gfPanelOrder.map(group=>[group,[]])),seen=new Set();for(const field of row.fields){const group=GF_ATTACK_FIELDS.has(field.field)?'Attack':field.group;if(seen.has(field.field)||!routed.has(group))throw new Error(`GF field routing failed: ${field.field}`);seen.add(field.field);routed.get(group).push(field)}if(seen.size!==row.fields.length)throw new Error("GF field routing omitted a field");return routed}
  function gfEntityLabel(field){const target=gfByName(field.label);return target?hoverable({content:LexeditorUI.inlineLabel(el("img",{src:`/assets/portraits/gfs/${target.id}.png`,alt:""}),el("span",{},field.label)),targetType:"gf",targetId:target.id,targetLabel:`${field.label} GF`,activate:()=>openGFByName(field.label)}):field.label}
  function gfFieldRow(field,row){return detailField({attrs:{"data-field":field.field},label:gfEntityLabel(field),help:field.help?infoHelp(field.help):null,control:fieldSourceControl(field,"gfs",row.id)})}
  function gfCompatibilityLabel(field){return gfEntityLabel(field)}
  function sortGfTable(kind,key){const [active,direction]=state.gfSorts[kind];state.gfSorts[kind]=[key,active===key?-direction:1];renderGFs()}
  // GF compatibility reads the same wherever it appears: one sortable table of
  // GF against the change this record applies, in its own panel. The Magic tab
  // shows exactly this panel, so the two are not two designs of one thing.
  function compatibilityPanel(fields,view,rowId){
    const [sortKey,sortDir]=state.gfSorts.compatibility;
    const sorted=[...fields].sort((a,b)=>sortDir*String(sortKey==="value"?gfCompatibilityFormat(a.value):a.label)
      .localeCompare(String(sortKey==="value"?gfCompatibilityFormat(b.value):b.label),undefined,{numeric:true,sensitivity:"base"}));
    const table=columnList({rows:sorted,key:field=>field.field,editable:true,fill:true,
      sortState:{key:sortKey,dir:sortDir},sort:key=>{state.gfSorts.compatibility=[key,sortKey===key?-sortDir:1];if(view==="magic")renderKernel("magic","Magic");else renderGFs()},
      template:"minmax(135px,1fr) minmax(75px,100px)",
      columns:[{key:"label",label:"GF",align:"start",help:view==="magic"?"Casting this spell changes compatibility with each listed GF by this amount.":"Summoning this GF changes the summoner’s compatibility with each listed GF by this amount.",sortable:true,render:gfCompatibilityLabel},
        {key:"value",label:"Change",sortable:true,render:field=>fieldSourceControl(field,view,rowId)}]});
    table.dataset.gfPanel="compatibility";
    return table;
  }
  const GF_CURVE_FIELDS=["gf_hp_modifier_1","gf_hp_modifier_2","gf_hp_modifier_3","gf_level_modifier_1","gf_level_modifier_2"];
  function gfPanel(title,fields,row,className){if(className==="compatibility")return compatibilityPanel(fields,"gfs",row.id);
    // The five curve modifiers are the graphs' variables, so they are not also
    // listed as loose numbers above them.
    const curveFields=fields.filter(field=>GF_CURVE_FIELDS.includes(field.field));
    const rest=fields.filter(field=>!GF_CURVE_FIELDS.includes(field.field));
    const growth=className==="general"?gfStatGrowth(curveFields,row.id):null;
    return detailSection({title,body:[growth,...(growth?rest:fields).map(field=>gfFieldRow(field,row))].filter(Boolean),attrs:{"data-gf-panel":className,"aria-label":title}})}
  // In "Ability" mode the stored number is 100 + the ability slot. Showing
  // that raw number made the prerequisite unreadable, so the slot is chosen
  // by name and the offset is applied here rather than by the reader.
  function gfPrereqSlot(field,slots){
    const select=el("select",{class:"gf-prereq-slot","aria-label":"Required ability",
      onchange:event=>{field.value=100+Number(event.target.value);shell.refresh()}},
      ...slots.map(([slot,name])=>el("option",{value:String(slot)},
        `#${String(slot).padStart(2,"0")} ${name}`)));
    select.value=String(Math.max(1,Number(field.value)-100));
    return select;
  }
  function gfPrereqKind(field,row){
    // 1-100 is a GF level, 101-121 is "after this ability slot is learned".
    // The selector just moves the stored number between those two ranges.
    const isSlot=Number(field.value)>100;
    const select=el("select",{class:"gf-prereq-kind","aria-label":"Prerequisite kind",onchange:event=>{
      const wantSlot=event.target.value==="slot",current=Number(field.value)||0;
      field.value=wantSlot?(current>100?current:Math.min(121,100+Math.max(1,current))):(current>100?Math.max(1,current-100):Math.max(1,current));
      renderGFs();shell.refresh();
    }},el("option",{value:"level"},"Level"),el("option",{value:"slot"},"Ability"));
    select.value=isSlot?"slot":"level";
    return select;
  }
  function gfAbilities(fields,row){const groups=new Map();for(const field of fields){const key=field.row||field.field;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(field)}const find=(values,suffix="")=>values.find(field=>suffix?field.field.endsWith(suffix):/^ability\d+$/.test(field.field)),rows=[...groups].map(([key,values])=>({key,slot:Number(String(key).replace(/^ability/,""))||0,ability:find(values),level:find(values,"_level_or_prereq"),alternate:find(values,"_alt_prereq")})),[sortKey,sortDir]=state.gfSorts.abilities,sorted=rows.sort((a,b)=>sortDir*(sortKey==="slot"?a.slot-b.slot:String(displayFieldValue(a[sortKey])).localeCompare(String(displayFieldValue(b[sortKey])),undefined,{numeric:true,sensitivity:"base"})));sorted.forEach(entry=>{entry.id=Number(String(entry.key).replace(/^ability/,""))||0});const slotNames=sorted.map(entry=>[entry.id,entry.ability?.lookup?.entries?.find(o=>Number(o.value)===Number(entry.ability.value))?.name||`slot ${entry.id}`]).sort((a,b)=>a[0]-b[0]);const table=columnList({rows:sorted,key:entry=>entry.key,editable:true,fill:true,sortState:{key:sortKey,dir:sortDir},sort:key=>sortGfTable("abilities",key),template:"52px minmax(125px,1.2fr) minmax(140px,1fr) minmax(90px,.8fr)",columns:[{key:"slot",label:"Slot",sortable:true,sortValue:entry=>entry.slot,numberedId:true,render:entry=>entry.id},{key:"ability",label:"Ability",sortable:true,render:entry=>entry.ability?fieldSourceControl(entry.ability,"gfs",row.id):"—"},{key:"level",label:"Prereq",help:"Choose whether this ability unlocks at a GF level or after another ability slot is learned. Values 1–100 are a GF level; 101–121 are the matching ability slot on this GF.",sortable:true,render:entry=>entry.level?LexeditorUI.controlGroup([gfPrereqKind(entry.level,row),Number(entry.level.value)>100?gfPrereqSlot(entry.level,slotNames):fieldSourceControl(entry.level,"gfs",row.id)]):"—"},{key:"alternate",label:"Alt. Prereq",help:"Points to another ability slot on this GF. This ability stays available only while that other ability is unfinished. 255 means no alternate restriction.",sortable:true,render:entry=>entry.alternate?fieldSourceControl(entry.alternate,"gfs",row.id):"—"}]});table.dataset.gfAbilities="true";return detailSection({title:"ABILITIES",
      body:table,attrs:{"data-gf-panel":"abilities"}})}
  function renderGFs(){
    const rows=[...state.data.gfs.rows].sort((a,b)=>a.name.localeCompare(b.name,undefined,{sensitivity:"base"}));
    if(!rows.some(row=>row.id===state.selected.gfs))state.selected.gfs=rows[0]?.id??null;
    const row=rows.find(candidate=>candidate.id===state.selected.gfs);if(!row){$("#toolbar").replaceChildren();$("#main").replaceChildren(LexeditorUI.notice({message:"No GF records were found."}));return}
    const subtabs=portraitTabs("gfs",rows,row.id,"gf-detail",id=>{state.selected.gfs=id;renderGFs();shell.refresh()});
    $("#toolbar").replaceChildren(subtabs);
    const routed=gfFieldsByPanel(row),defaults=state.data.init.gfs.rows.find(value=>Number(value.id)===Number(row.id));
    const center=gfCenterPanel(row,routed,defaults);
    const panels=[compatibilityPanel(routed.get('GF Compatibility'),'gfs',row.id),center,gfAbilities(routed.get('Abilities'),row)];
    const layout=panelLayout(panels,"gf-three-panel",{layoutKey:"ff8-gfs",defaultSizes:[.9,1.05,1.4],minSizes:[230,245,470],stackAt:1000});
    Object.assign(layout,{id:"gf-detail"});layout.setAttribute("role","tabpanel");layout.setAttribute("aria-labelledby",`gfs-tab-${row.id}`);layout.dataset.gf=row.id;$("#main").replaceChildren(layout);
  }
  function gfCenterPanel(row,routed,defaults){
    const active=state.gfDetailTab||'properties';
    const content=active==='attack'?gfPanel('',routed.get('Attack'),row,'attack'):
      active==='defaults'?(defaults?startingFields(defaults.fields,'gf',defaults.id):LexeditorUI.detailNote('No initial state for this GF.')):
      gfPanel('',routed.get('General'),row,'general');
    return tabbedPanel({tabs:[{id:'properties',label:'Properties'},
      {id:'attack',label:'Attack',help:'Set the GF summon’s power, animation, targets, damage, elements and status effects.'},
      {id:'defaults',label:'Defaults',help:'Initial GF state used when a new game begins. Changes do not alter an existing save.'}],
      active,label:'GF details',change:id=>{state.gfDetailTab=id;renderGFs()},content});
  }
  function fieldGroups(fields,view,rowId,collapsible=true,prefs=null){
    const groups=new Map();
    for(const field of fields){
      if(!groups.has(field.group))groups.set(field.group,[]);
      groups.get(field.group).push(field);
    }
    return LexeditorUI.tileGrid([...groups].map(([name,rows])=>{
      return detailSection({title:name,body:rows.map(field=>
        detailField({label:field.label,help:field.help?infoHelp(field.help):null,
          control:fieldSourceControl(field,view,rowId),pin:prefs?.pinButton(`field:${field.field}`,field.label)}))});
    }));
  }
  function gfCompatibilityFormat(value){const modifier=(Number(value)-100)/10;return modifier>0?`+${formatNumber(modifier,{maximumFractionDigits:1})}`:formatNumber(modifier,{maximumFractionDigits:1})}
  function gfCompatibilityControl(field){
    const control=el("input",{type:"text",inputmode:"decimal",value:gfCompatibilityFormat(field.value),class:"gf-compat-input","aria-label":`${field.label} compatibility modifier`,oninput:event=>{const next=Number(String(event.target.value).replaceAll(",",""));if(!Number.isFinite(next))return;const bounded=Math.max(-10,Math.min(15.5,Math.round(next*10)/10));field.value=Math.round(bounded*10+100);shell.refresh()},onblur:event=>{event.target.value=gfCompatibilityFormat(field.value)}});
    return control
  }
  const booleanGlyph=value=>value?"\u2713":"\u00d7";
  const booleanMark=value=>el("span",{class:"lex-boolean-mark lex-ui-symbol"},booleanGlyph(value));
  function flagSourceControl(field,view,rowId){
    const lookup=field.lookup,word=value=>Number(value??0);
    const vanillaField=rowOf(state.vanilla,view,rowId)?.fields?.find(value=>value.field===field.field);
    const references=referenceValues(view,rowId,value=>value?.fields?.find(entry=>entry.field===field.field)?.value);
    const switches=toggleRow({label:field.label,value:()=>word(field.value),toggles:lookup.entries.map(entry=>{
      const bit=Number(entry.mask??entry.value);
      return {key:String(bit),label:entry.name,icon:LexeditorUI.inlineLabel(conceptIcon(lookup.name,entry.name)),
        help:entry.description||null,checked:(word(field.value)&bit)===bit,
        change:checked=>{field.value=checked?(word(field.value)|bit):(word(field.value)&~bit);noteFieldEdit(view,field)}};
    })});
    return sourceControl(switches,()=>word(field.value),vanillaField?word(vanillaField.value):undefined,
      references,value=>{field.value=word(value)},value=>`0x${word(value).toString(16).toUpperCase()}`);
  }
  function hitRateSourceControl(field,view,rowId){const vanilla=rowOf(state.vanilla,view,rowId)?.fields?.find(value=>value.field===field.field)?.value,references=referenceValues(view,rowId,value=>value?.fields?.find(entry=>entry.field===field.field)?.value);// FF8 stores hit rate as a percentage, not a fraction of 255: the battle formula clamps "hit rate + LUCK/2 - EVA" to 0-100 before rolling. A weapon reading 98 is 98%, not 38.43%. Values above 100 are the always-hit range.
    const input=numberControl(field.value,0,255,1,value=>{field.value=Math.max(0,Math.min(255,Math.round(Number(value)||0)));noteFieldEdit(view,field)},{"aria-label":field.label});return sourceControl(unitField(input,"%"),()=>field.value,vanilla,references,value=>{field.value=Math.max(0,Math.min(255,Math.round(Number(value)||0)))},value=>`${formatNumber(value)}%`,{internal:true})}
  // Editing a property that is also pinned as a column has to redraw the
  // list, or the table keeps showing the old value while the detail shows the
  // new one. shell.refresh() only updates the shell chrome.
  let pinnedRenderPending=false;
  function noteFieldEdit(view,field){
    shell.refresh();
    if(!view||!field)return;
    const active=state.columnPrefs[view]?.active?.();
    if(!active||!active.some(column=>column.key===field.field||column.key===`field:${field.field}`))return;
    if(pinnedRenderPending)return;
    pinnedRenderPending=true;
    requestAnimationFrame(()=>{pinnedRenderPending=false;render()});
  }
  function fieldSourceControl(field,view,rowId,options={}){if(!field)return el("span",{},"—");if(view&&field.lookup?.type==="flags")return flagSourceControl(field,view,rowId);if(view&&field.field==="hit_rate")return hitRateSourceControl(field,view,rowId);const compatibility=field.formula==="gf_compat",control=compatibility?gfCompatibilityControl(field):fieldControl(field);if(!view)return control;const vanillaField=rowOf(state.vanilla,view,rowId)?.fields?.find(value=>value.field===field.field),boolean=field.control==="boolean",read=value=>boolean?Boolean(value):value,references=referenceValues(view,rowId,value=>read(value?.fields?.find(entry=>entry.field===field.field)?.value)),format=compatibility?gfCompatibilityFormat:(boolean?booleanMark:undefined);return sourceControl(control,()=>read(field.value),read(vanillaField?.value),references,value=>field.value=boolean?Boolean(value):value,format,options)}
  const elementIcons={Fire:288,Ice:289,Thunder:290,Earth:291,Poison:292,Wind:293,Water:294,Holy:295};
  const statusIcons={Death:272,Poison:273,Petrify:274,Petrifying:274,Darkness:275,Silence:276,Berserk:277,Zombie:278,Sleep:279,Slow:280,Stop:281,Curse:282,"Curse (unused for attack)":282,Confuse:283,Confusion:283,Drain:284};
  function conceptIcon(lookup,name){const id=lookup==="element"?elementIcons[name]:statusIcons[name];return id?LexeditorUI.inlineLabel(el("img",{src:`/assets/icons/${id}.png`,alt:"",title:`${name} game icon`})):null}
  function fieldControl(field){const lookup=field.lookup;if(field.control==="boolean")return el("input",{type:"checkbox",checked:Boolean(field.value),"aria-label":field.label,onchange:event=>{field.value=event.target.checked;shell.refresh()}});if(lookup?.type==="enum")return lookup.name==="item"?itemSelectControl(field.value,lookup.entries.map(entry=>({...entry,iconId:itemById(entry.value)?.iconId})),value=>field.value=value):selectControl(field.value,lookup.entries,value=>field.value=value);if(lookup?.type==="flags"){return LexeditorUI.toggleRow({label:field.label,value:()=>field.value,toggles:lookup.entries.map(entry=>{
    const bit=Number(entry.mask??entry.value);
    return {label:entry.name,bit,checked:(field.value&bit)===bit,icon:conceptIcon(lookup.name,entry.name),change:checked=>{field.value=checked?(field.value|bit):(field.value&~bit);shell.refresh()}};
  })})}if(field.field==="hit_rate")return ratio255Control(field.value,value=>field.value=value,field.label);const control=numberControl(field.value,field.minimum,field.maximum,field.control==="percent"?.1:1,value=>field.value=value);return field.control==="percent"?unitField(control,"%"):control}

  function enemyDisplayName(name){
    const text=String(name??""),match=text.match(/^\{([^{}]+)\}$/);
    return match?`「${match[1]}」`:text;
  }
  const enemyCurveOrder=["HP","STR","VIT","MAG","SPR","SPD","EVA"];
  function enemyCurveFields(fields,stat){return fields.filter(field=>field.field.startsWith(`${stat.toLocaleLowerCase()}_`)).sort((left,right)=>left.field.localeCompare(right.field,undefined,{numeric:true}))}
  function enemyCurveValue(stat,fields,level){
    const [A,B,C,D]=enemyCurveFields(fields,stat).map(field=>Number(field.value)||0);
    if(stat==="HP")return Math.floor(A*(level*level/20+level))+10*B+100*C*level+1000*D;
    if(stat==="STR"||stat==="MAG")return Math.floor(level*A/40)+(B?Math.floor(level/(4*B)):0)+Math.floor(C/4)+(D?Math.floor(level*level/(8*D)):0);
    return level*A+(B?Math.floor(level/B):0)+C-(D?Math.floor(level/D):0);
  }
  function enemyCurveFormula(stat){
    if(stat==="HP")return "HP(L)=⌊A(L²/20+L)⌋+10·B+100·C·L+1000·D";
    if(stat==="STR"||stat==="MAG")return `${stat}(L)=⌊L·A/40⌋+⌊L/(4·B)⌋+⌊C/4⌋+⌊L²/(8·D)⌋`;
    return `${stat}(L)=L·A+⌊L/B⌋+C−⌊L/D⌋`;
  }
  function enemyCurveRange(stat,fields){
    const maximum=Math.max(0,...Array.from({length:100},(_unused,index)=>enemyCurveValue(stat,fields,index+1)));
    const baseline=stat==="HP"?9999:255,step=stat==="HP"?1000:50;
    return {min:0,max:Math.max(baseline,Math.ceil(maximum/step)*step)};
  }
  function enemyStatGrowth(fields,rowId){
    const cards=enemyCurveOrder.map(stat=>{
      const statFields=enemyCurveFields(fields,stat),variables=statFields.map((field,index)=>({label:"ABCD"[index],control:fieldSourceControl(field,"enemies",rowId,{internal:true})}));
      return curveEditor({title:stat,overlayExtrema:true,variables,domain:{min:1,max:100},range:()=>enemyCurveRange(stat,statFields),graphLabel:`${stat} from enemy level 1 to 100`,evaluate:level=>enemyCurveValue(stat,statFields,level),formula:coloredCurveFormula(enemyCurveFormula(stat))});
    });
    const index=Math.max(0,Math.min(cards.length-1,state.enemyStatPage||0));
    return LexeditorUI.pagedPane(cards[index],pager({inline:true,page:index,pages:cards.length,pageSize:1,total:cards.length,noun:"stats",change:value=>{state.enemyStatPage=value;renderEnemies()}}));
  }
  function magicSearchControl(value,prompt,accept,origin){
    const magic=state.data.magic.rows.find(row=>Number(row.id)===Number(value))||{id:value,name:`Magic ${value}`};
    // The name is an ordinary hoverable and the magnifier is its own control,
    // so following the link and picking a different record stay separate.
    const link=hoverable({content:magicLabel(magic),targetType:"magic",targetId:magic.id,targetLabel:magic.name,activate:()=>{state.selected.magic=Number(magic.id);navigate("magic")}});
    const finder=el("button",{type:"button",title:"Choose magic","aria-label":"Choose magic",onclick:event=>{event.preventDefault();event.stopPropagation();beginSearcher({type:"magic",prompt,target:()=>navigate("magic"),origin,accept})}},LexeditorUI.selectionIcon());
    return LexeditorUI.choiceField(link,finder);
  }
  function enemyTableRow(dataset,id){return rowOf(dataset,"enemyTables",id)}
  function enemyAiRow(dataset,id){return rowOf(dataset,"enemyAi",id)}
  function enemyBattleTextRow(dataset,id){return rowOf(dataset,"enemyBattleText",id)}
  function enemyTableReferences(id,read){return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:read(enemyTableRow(state.referenceData[reference.id],id))})).filter(entry=>entry.value!==undefined)}
  function enemyTableSource(control,row,read,apply,format=value=>String(value)){return sourceControl(control,()=>read(row),read(enemyTableRow(state.vanilla,row.id)),enemyTableReferences(row.id,read),apply,format)}
  function choiceName(entries,value){return entries.find(entry=>Number(entry.id??entry.value)===Number(value))?.name??String(value)}
  function enemyAbilityValueControl(row,entry){const choices=state.data.enemyTables.choices,origin=()=>{state.selected.enemies=row.id;navigate("enemies")},set=value=>{entry.abilityId=Number(value);renderEnemies();shell.refresh()};if(Number(entry.type)===2)return magicSearchControl(entry.abilityId,`Select Magic for ${row.name}.`,set,origin);if(Number(entry.type)===4)return itemSearchControl(entry.abilityId,`Select the Item for ${row.name}.`,set,origin);const entries=Number(entry.type)===0?[{id:0,name:"Not defined"}]:choices.enemyAbilities;return selectControl(entry.abilityId,entries,set)}
  function enemyAbilitiesSection(row,tier=null){const choices=state.data.enemyTables.choices,rows=(tier?[[tier,row.tables.abilities[tier]]]:Object.entries(row.tables.abilities)).flatMap(([entryTier,entries])=>entries.map(entry=>({...entry,tier:entryTier,key:`${entryTier}-${entry.slot}`}))),columns=[...(tier?[]:[{key:"tier",label:"Tier"}]),{key:"slot",label:"Slot",render:entry=>entry.slot+1},{key:"type",label:"Type",sortValue:entry=>entry.type,render:entry=>enemyTableSource(selectControl(entry.type,choices.abilityTypes,value=>{entry.type=value;entry.abilityId=0;renderEnemies()}),row,value=>value?.tables.abilities[entry.tier][entry.slot]?.type,value=>entry.type=Number(value),value=>choiceName(choices.abilityTypes,value))},{key:"ability",label:"Ability",sortValue:entry=>entry.abilityId,render:entry=>enemyTableSource(enemyAbilityValueControl(row,entry),row,value=>value?.tables.abilities[entry.tier][entry.slot]?.abilityId,value=>entry.abilityId=Number(value))},{key:"animation",label:"Anim.",headerTitle:"Animation",render:entry=>enemyTableSource(numberControl(entry.animation,0,255,1,value=>entry.animation=value),row,value=>value?.tables.abilities[entry.tier][entry.slot]?.animation,value=>entry.animation=Number(value))}],/* The Anim. column holds a number input, and a number input is its digits
   plus its spinner. Forty-four pixels cut the spinner off on all forty-eight
   rows. */
template=tier?"40px minmax(62px,.72fr) minmax(96px,1.28fr) 60px":"90px 58px minmax(120px,.8fr) minmax(180px,1.4fr) 90px",table=columnList({rows,key:entry=>entry.key,class:"ff8-record-list enemy-ability-table",editable:true,template,columns});return detailSection({className:"enemy-table-section",title:tier?`${tier.toLocaleUpperCase()} LEVEL`:"ABILITIES",body:table})}
  function enemyPairSection(row,kind,title,valueLabel){
    const tiers=[['low','LOW'],['medium','MID'],['high','HI']], draw=kind==='draw';
    const origin=()=>{state.selected.enemies=row.id;navigate('enemies')};
    // Keep the actual stored entry, not a spread copy: saveAll reads this
    // array. Display labels never sort, compact, or renumber DAT slots.
    const entryFor=(tier,index)=>(row.tables[kind][tier]||[])[index];
    const slotCell=(tier,label,index)=>{
      const entry=entryFor(tier,index);
      if(!entry)return "";
      const read=value=>value?.tables[kind]?.[tier]?.find(value=>value.slot===entry.slot);
      const set=value=>{entry.valueId=Number(value);shell.refresh()};
      const prompt=`Select ${valueLabel} for ${row.name}, ${label.toLowerCase()} level.`;
      const choice=draw?magicSearchControl(entry.valueId,prompt,set,origin):itemSearchControl(entry.valueId,prompt,set,origin);
      choice.title=choice.textContent.trim();
      const value=enemyTableSource(choice,row,value=>read(value)?.valueId,set);
      const quantity=numberControl(entry.quantity,0,255,1,value=>entry.quantity=Math.round(value),
        {'aria-label':`${title} ${tier} choice ${entry.slot+1} quantity`});
      quantity.addEventListener('blur',()=>quantity.value=String(entry.quantity));
      return LexeditorUI.quantityChoice(value,enemyTableSource(quantity,row,value=>read(value)?.quantity,value=>entry.quantity=Number(value)));
    };
    const table=columnList({
      rows:tiers.map(([tier,label])=>({key:tier,tier,label})),
      key:entry=>entry.key,
      class:`enemy-tier-table enemy-${kind}-table`,
      'aria-label':`${title} by level tier`,
      editable:true, localSort:false, showHeader:!draw,
      template:'42px repeat(4,minmax(0,1fr))',
      rowClass:entry=>`enemy-tier-row enemy-tier-${entry.tier}`,
      columns:[{key:'label',label:'',render:entry=>entry.label},
        ...[0,1,2,3].map(index=>({key:`slot${index}`,label:`SLOT ${index+1}`,
          render:entry=>slotCell(entry.tier,entry.label,index)}))],
    });
    return detailSection({className:'enemy-table-section enemy-tier-section',title,body:el('fieldset',{class:'enemy-table-controls',disabled:state.activeSource!=='mine'},table)});
  }
  function enemyCardChoices(row){
    const choices=state.data.enemyTables.choices.cards;
    return LexeditorUI.tileGrid(row.tables.cards.map(entry=>{
      const id=Number(entry.cardId),card=rowOf(state.data,'cards',id)||choices.find(value=>Number(value.id)===id);
      const name=card?.name||`Card ${id}`,origin=()=>{state.selected.enemies=row.id;navigate('enemies')};
      const set=value=>{entry.cardId=Number(value);shell.refresh()};
      const placeholder=el('span',{class:'enemy-card-placeholder','aria-hidden':'true'},id===255?'—':'?');
      const art=LexeditorUI.iconSlot({content:placeholder});
      if(id>=0&&id<110){
        const image=el('img',{src:`/assets/cards/${id}.png`,alt:name,
          onload:()=>{placeholder.hidden=true},onerror:()=>{image.remove();placeholder.textContent='Art unavailable'}});
        art.append(image);
      }
      const choose=el('button',{type:'button',disabled:state.activeSource!=='mine',
        'aria-label':`Choose card for slot ${entry.slot+1}: ${name}`,
        title:`Choose card for slot ${entry.slot+1}: ${name}`,onclick:()=>beginSearcher({type:'cards',
          prompt:`Select card ${entry.slot+1} for ${row.name}.`,target:()=>navigate('cards'),origin,accept:set})},
        LexeditorUI.figureGrid([{media:art,caption:name}]));
      // 255 is a real sentinel in the existing schema, not card zero. Keep it
      // selectable even though the Cards tab only contains the 110 real cards.
      const clear=el('button',{type:'button',disabled:state.activeSource!=='mine'||id===255,
        title:'Set to Immune (stored card ID 255)','aria-label':`Clear card slot ${entry.slot+1}`,
        onclick:()=>{set(255);renderEnemies()}},'×');
      const control=LexeditorUI.stack({fill:false},choose,LexeditorUI.actionRow(clear));control.dataset.slot=entry.slot;
      return enemyTableSource(control,row,value=>value?.tables.cards.find(value=>value.slot===entry.slot)?.cardId,
        set,value=>rowOf(state.data,'cards',Number(value))?.name||choiceName(choices,value));
    }),{columns:3,minWidth:80});
  }
  function enemySimpleTables(row){
    const cards=enemyCardChoices(row),devourChoices=state.data.enemyTables.choices.devour||[];
    const tierNames=['LOW','MID','HIGH'];
    // Devouring an enemy has one outcome per tier, so the three tiers are one
    // property with three variables - the same shape a stat block uses -
    // rather than three rows of a table with a one-word first column.
    const devourControl=entry=>{
      const id=Number(entry.devourId),choices=devourChoices.some(value=>Number(value.id)===id)?devourChoices:[...devourChoices,{id,name:`Unknown (${id})`}];
      return enemyTableSource(selectControl(id,choices,value=>{entry.devourId=Number(value);shell.refresh()}),row,
        value=>value?.tables.devour[entry.slot]?.devourId,value=>entry.devourId=Number(value),value=>choiceName(choices,value));
    };
    const devour=multiNumberRow((row.tables.devour||[]).map(entry=>({
        label:tierNames[entry.slot]||`Tier ${entry.slot+1}`,
        title:`${tierNames[entry.slot]||`Tier ${entry.slot+1}`}-tier Devour outcome`,
        control:devourControl(entry)})),{columns:3,stacked:true});
    const renzokuken=columnList({rows:row.tables.renzokuken,key:entry=>entry.slot,class:"ff8-record-list",editable:true,template:"70px minmax(120px,1fr)",columns:[
      {key:"slot",label:"Hit",help:"Which hit of the Renzokuken sequence this row sets. Squall's limit strikes several times, and each hit reads its own entry in this table.",render:entry=>entry.slot+1},
      {key:"value",label:"Damage",help:"The damage multiplier this hit contributes, out of 65,535. It is not a damage figure: the engine scales it by Squall's attack and the enemy's defence.",render:entry=>enemyTableSource(numberControl(entry.value,0,65535,1,value=>entry.value=value),row,value=>value?.tables.renzokuken[entry.slot]?.value,value=>entry.value=Number(value))}]});
    return [detailSection({className:"enemy-table-section",title:"CARDS",body:cards}),detailSection({className:"enemy-table-section",title:"DEVOUR",body:devour}),detailSection({className:"enemy-table-section",title:"RENZOKUKEN",body:renzokuken})]
  }

  const enemyDefencePrevious=new WeakMap();
  function enemyDefenceSection(row,kind,title){
    const element=kind==='elementDefence',names=['Fire','Ice','Thunder','Earth','Poison','Wind','Water','Holy'];
    const aliases={Blind:'Darkness',Mute:'Silence','Sub-petrify':'Petrify'};
    const neutral=element?100:0,immune=element?0:155;
    const help=infoHelp(element?
      'The stored byte is shown as 900 − 10 × byte. 100% is neutral; exactly 0% is immune. Negative values remain distinct and editable. Toggle an icon for full immunity; toggle again to restore the previous value.':
      'Status defence is the stored byte − 100 (−100% to 155%). 155% means immune. Toggle an icon for full immunity; toggle again to restore the previous value.');
    const grid=LexeditorUI.tileGrid(row.tables[kind].map(entry=>{
        const name=element?names[entry.slot]:(state.data.enemyTables.choices.statuses||[]).find(value=>Number(value.id)===entry.slot)?.name||`Status ${entry.slot+1}`;
        const read=value=>value?.tables[kind]?.find(value=>value.slot===entry.slot)?.percent;
        const isImmune=()=>Number(entry.percent)===immune;
        const setPercent=value=>{
          const number=Number(value);if(!Number.isFinite(number))return;
          entry.stored=Math.max(0,Math.min(255,Math.round(element?(900-number)/10:number+100)));
          entry.percent=element?900-entry.stored*10:entry.stored-100;
        };
        const input=el('input',{type:'number',min:element?-1650:-100,max:element?900:155,step:element?10:1,
          value:entry.percent,'aria-label':`${name} defence percent`,oninput:()=>{
            if(input.validity.valid&&input.value!==''){setPercent(input.value);shell.refresh()}
          },onchange:()=>{if(input.value!=='')setPercent(input.value);input.value=entry.percent;sync();shell.refresh()}});
        const checkbox=el('input',{type:'checkbox','aria-label':`${name} immune`,onchange:()=>{
          if(checkbox.checked){if(!isImmune())enemyDefencePrevious.set(entry,entry.percent);setPercent(immune)}
          else setPercent(enemyDefencePrevious.get(entry)??neutral);
          input.value=entry.percent;sync();input.dispatchEvent(new Event('change',{bubbles:true}));
        }});
        // A status the game has no icon for - or whose icon will not load -
        // shows a plain mark in the icon's place, so every tile reads alike.
        const fallback=()=>el('span',{class:'enemy-status-fallback','aria-hidden':'true'},'▧');
        const icon=conceptIcon(element?'element':'status',aliases[name]||name)||fallback();
        icon.querySelector?.('img')?.addEventListener('error',()=>icon.replaceWith(fallback()),{once:true});
        const tile=LexeditorUI.iconValue({icon,label:name,toggle:checkbox,control:enemyTableSource(unitField(input,'%'),row,read,setPercent,value=>`${value}%`)});tile.dataset.defence=name;
        const sync=()=>{const checked=isImmune();checkbox.checked=checked;checkbox.disabled=state.activeSource!=='mine';
          input.disabled=checked||state.activeSource!=='mine';tile.classList.toggle('immune',checked)};
        sync();return tile;
      }),{minWidth:95});
    return detailSection({title,help,body:grid});
  }
  const enemyScanElementNames=['Fire','Ice','Thunder','Earth','Poison','Wind','Water','Holy'];
  function enemyGeneratedScanDetails(row){
    const table=enemyTableRow(state.data,row.id),choices=state.data.enemyTables.choices.devour||[];
    if(!table?.tables)return 'DETAILS';
    const groups={Weak:[],Resist:[],Immune:[],Absorb:[]};
    for(const entry of table.tables.elementDefence||[]){const name=enemyScanElementNames[entry.slot]||`Element ${entry.slot+1}`,value=Number(entry.percent);if(value>100)groups.Weak.push(`${name} ${value}%`);else if(value>0&&value<100)groups.Resist.push(`${name} ${value}%`);else if(value===0)groups.Immune.push(name);else if(value<0)groups.Absorb.push(`${name} ${Math.abs(value)}%`)}
    const lines=['DETAILS'];for(const [label,values] of Object.entries(groups))if(values.length)lines.push(`${label}: ${values.join(', ')}`);if(lines.length===1)lines.push('Elements: Neutral');
    const tiers=['Low','Mid','High'];for(const entry of table.tables.devour||[]){const found=choices.find(value=>Number(value.id)===Number(entry.devourId));lines.push(`Devour ${tiers[entry.slot]||entry.slot+1}: ${found?.name||`Unknown ${entry.devourId}`}`)}
    return lines.join('\n');
  }
  function enemyScanWithDetails(description,details){const text=String(description??''),marker='{NewPage}DETAILS',index=text.indexOf(marker),base=(index>=0?text.slice(0,index):text).replace(/\s+$/,'');return `${base}${base?'{NewPage}':''}${details}`}
  function applyEnemyScanDetails(row){row.scanDescription=enemyScanWithDetails(row.scanDescription,enemyGeneratedScanDetails(row))}
  function enemyScanSection(row,prefs){
    const input=LexeditorUI.textArea({rows:6,"aria-label":`Scan description for ${row.name}`,oninput:event=>{row.scanDescription=event.target.value;shell.refresh()}});input.value=row.scanDescription??"";
    const details=enemyGeneratedScanDetails(row),apply=el('button',{type:'button',class:'secondary-action',disabled:state.activeSource!=='mine',onclick:()=>{applyEnemyScanDetails(row);renderEnemies();shell.refresh()}},'UPDATE DETAILS');
    const applyAll=el('button',{type:'button',class:'secondary-action',disabled:state.activeSource!=='mine',onclick:()=>{for(const enemy of state.data.enemies.rows)if(enemy.available)applyEnemyScanDetails(enemy);renderEnemies();shell.refresh()}},'UPDATE ALL');
    return detailSection({className:"enemy-scan-section",title:"SCAN",body:[detailField({label:"DESCRIPTION",control:sourceControl(input,()=>row.scanDescription,rowOf(state.vanilla,"enemies",row.id)?.scanDescription,referenceValues("enemies",row.id,value=>value?.scanDescription),value=>row.scanDescription=String(value??"")),pin:prefs?.pinButton("scanDescription","Scan description")}),LexeditorUI.actionRow(apply,applyAll),LexeditorUI.detailNote(details)]})
  }
  function enemyPropertyLabel(field){const labels={"Medium level starts":"MED LV","High level starts":"HIGH LV","Auto-Reflect":"REFLECT","Auto-Shell":"SHELL","Auto-Protect":"PROTECT","Surprise immunity":"NO SURPRISE","Diablos misses":"NO DIABLOS","Always yields a card":"ALWAYS CARD","Extra XP":"EXTRA XP","Mug rate":"MUG %","Drop rate":"DROP %"};return labels[field.label]||field.label}
  // Each enemy flag is its own field in the data, but on screen they are one
  // property of switches, the same control as an item's USE FLAGS. Their
  // reference is the flags packed into a word, bit n being the nth switch.
  function enemyFlagsField(flags,rowId,prefs){
    const short={"Auto-Reflect":"Reflect","Auto-Shell":"Shell","Auto-Protect":"Protect","Surprise immunity":"No Surprise","Diablos misses":"No Diablos","Always yields a card":"Always Card"};
    const on=(row,field)=>Boolean(row?.fields?.find(value=>value.field===field.field)?.value),
      word=read=>flags.reduce((total,field,index)=>read(field)?total+2**index:total,0),
      apply=value=>{flags.forEach((field,index)=>{field.value=Boolean(Math.floor(Number(value)/2**index)%2)});renderEnemies();shell.refresh()},
      switches=toggleRow({label:'Enemy flags',value:()=>word(field=>Boolean(field.value)),toggles:flags.map((field,index)=>({key:field.field,bit:index,label:short[field.label]||field.label,help:field.help?`${field.label}: ${field.help}`:field.label,checked:Boolean(field.value),
        pin:prefs?.pinButton(`field:${field.field}`,field.label),change:next=>{field.value=next;noteFieldEdit('enemies',field);shell.refresh()}}))});
    return detailField({className:'enemy-flags',label:'FLAGS',control:sourceControl(switches,()=>word(field=>Boolean(field.value)),word(field=>on(rowOf(state.vanilla,'enemies',rowId),field)),
      referenceValues('enemies',rowId,row=>word(field=>on(row,field))),apply,value=>`0x${Number(value).toString(16).toLocaleUpperCase()}`)});
  }
  function enemyProperties(fields,rowId,prefs){
    const numeric=fields.filter(field=>field.control!=='boolean'),flags=fields.filter(field=>field.control==='boolean');
    const result=detailSection({title:'PROPERTIES',body:[
      ...numeric.map(field=>detailField({label:enemyPropertyLabel(field),help:field.help?infoHelp(field.help):null,
        pin:prefs?.pinButton(`field:${field.field}`,field.label),control:fieldSourceControl(field,'enemies',rowId,{internal:true})})),
      flags.length?enemyFlagsField(flags,rowId,prefs):null]});
    if(state.activeSource!=='mine')result.querySelectorAll('input,select,button').forEach(control=>control.disabled=true);
    return result;
  }
  function enemyAiCatalog(){return state.data.enemyAi.opcodes||[]}
  function enemyAiMnemonic(name){return String(name).toLocaleUpperCase().replace(/[^A-Z0-9]+/g,"_").replace(/^_+|_+$/g,"")}
  function enemyAiFormatScript(script){return script.instructions.map(instruction=>{const values=instruction.operands.map(operand=>{let value=operand.value;if(["jump16","skip16"].includes(operand.type))value=`@${instruction.targetLabel||"MISSING"}`;else if(operand.type==="bool")value=Number(value)?"true":"false";return `${operand.type}=${value}`});return `${instruction.label}: ${enemyAiMnemonic(instruction.name)}[${instruction.opcode}]${values.length?` ${values.join(" ")}`:""}`}).join("\n")}
  function enemyAiNormalizeScript(script){let offset=0;const catalog=enemyAiCatalog();for(const [index,instruction] of script.instructions.entries()){const definition=catalog.find(value=>Number(value.opcode)===Number(instruction.opcode));if(definition){instruction.name=definition.name;instruction.size=definition.size}instruction.key=instruction.key||`new-${script.id}-${Date.now()}-${index}`;instruction.index=index;instruction.offset=offset;instruction.label=`L${offset.toString(16).padStart(4,"0").toLocaleUpperCase()}`;offset+=Number(instruction.size)||1}script.size=offset;const byKey=new Map(script.instructions.map(value=>[value.key,value]));for(const instruction of script.instructions){const branch=instruction.operands.find(value=>["jump16","skip16"].includes(value.type));if(!branch){delete instruction.targetOffset;delete instruction.targetLabel;delete instruction.targetValid;delete instruction.targetKey;continue}const target=instruction.targetKey==="end"?null:byKey.get(instruction.targetKey),targetOffset=instruction.targetKey==="end"?offset:target?.offset;instruction.targetValid=targetOffset!==undefined;instruction.targetOffset=targetOffset;instruction.targetLabel=instruction.targetValid?(instruction.targetKey==="end"?"END":target.label):"MISSING";if(instruction.targetValid)branch.value=targetOffset-(instruction.offset+instruction.size)}return script}
  function enemyAiSyncSource(script){enemyAiNormalizeScript(script);script.source=enemyAiFormatScript(script);return script}
  function enemyAiChangeOpcode(script,instruction,opcode){const definition=enemyAiCatalog().find(value=>Number(value.opcode)===Number(opcode));if(!definition)return;const branch=definition.operands.find(value=>["jump16","skip16"].includes(value.type));instruction.opcode=Number(opcode);instruction.name=definition.name;instruction.size=definition.size;instruction.operands=JSON.parse(JSON.stringify(definition.operands));instruction.raw="Rebuilt on save";if(branch&&!instruction.targetKey){const next=script.instructions[instruction.index+1];instruction.targetKey=next?.key||"end"}enemyAiSyncSource(script);renderEnemies();shell.refresh()}
  function enemyAiInsert(script,index){script.instructions.splice(index+1,0,{key:`new-${script.id}-${Date.now()}-${Math.random()}`,opcode:13,name:"No-op",size:2,raw:"Rebuilt on save",editable:true,operands:[{type:"u8",value:0,minimum:0,maximum:255,control:"number",index:0,size:1}]});enemyAiSyncSource(script);renderEnemies();shell.refresh()}
  function enemyAiDelete(script,index){const removed=script.instructions[index],replacement=script.instructions[index+1]?.key||script.instructions[index-1]?.key||"end";script.instructions.splice(index,1);for(const instruction of script.instructions)if(instruction.targetKey===removed.key)instruction.targetKey=replacement;enemyAiSyncSource(script);renderEnemies();shell.refresh()}
  function enemyAiMove(script,index,direction){const target=index+direction;if(target<0||target>=script.instructions.length)return;const [instruction]=script.instructions.splice(index,1);script.instructions.splice(target,0,instruction);enemyAiSyncSource(script);renderEnemies();shell.refresh()}
  function enemyAiOperandControl(operand,update){if(operand.control==="boolean")return el("input",{type:"checkbox",checked:Boolean(operand.value),"aria-label":operand.type,onchange:event=>update(event.target.checked?1:0)});if(operand.control==="enum")return selectControl(operand.value,operand.choices,value=>update(Number(value)));return numberControl(operand.value,operand.minimum,operand.maximum,1,value=>update(Number(value)),{"aria-label":operand.type})}
  function enemyAiOperand(row,script,instruction,operand){
    if(["jump16","skip16"].includes(operand.type)){
      const targets=script.instructions.filter(value=>operand.type!=="skip16"||value.offset>=instruction.offset+instruction.size);
      const chosen=targets.find(value=>value.key===instruction.targetKey);
      const control=lazyOptions(el("select",{"aria-label":`${operand.type} target`,onchange:event=>{instruction.targetKey=event.target.value;enemyAiSyncSource(script);renderEnemies();shell.refresh()}},chosen?el("option",{value:chosen.key},chosen.label):el("option",{value:"end"},"END")),()=>[...targets.map(value=>({value:value.key,label:value.label})),{value:"end",label:"END"}]);
      return el('label',{class:'lex-instruction-operand'},operand.type==='skip16'?'Otherwise':'Target',control);
    }
    const find=dataset=>{const other=enemyAiRow(dataset,row.id)?.scripts?.find(value=>value.id===script.id)?.instructions?.find(value=>value.key===instruction.key||value.offset===instruction.offset);return other?.operands?.find(value=>value.index===operand.index)?.value};
    const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:find(state.referenceData[reference.id])})).filter(value=>value.value!==undefined);
    const update=value=>{operand.value=value;enemyAiSyncSource(script);shell.refresh();if(operand.type==='subject')renderEnemies()};
    const labels={subject:'Test',subject_param:'Parameter',comparator:'Compare',value16:'Value',battle_var:'Variable',local_var:'Variable',global_var:'Variable',u8:'Value',ability_line:'Action',target:'Target'};
    return el('label',{class:'lex-instruction-operand'},labels[operand.type]||operand.type.replaceAll('_',' '),sourceControl(enemyAiOperandControl(operand,update),()=>operand.value,find(state.vanilla),references,update,undefined,{internal:true}));
  }
  function enemyAiOpcodeControl(script,instruction,choices){const control=selectControl(instruction.opcode,choices,value=>enemyAiChangeOpcode(script,instruction,value));control.classList.add("enemy-ai-opcode");control.setAttribute("aria-label",`Opcode at ${instruction.label}`);return control}
  function enemyAiDescription(row,instruction,script){
    const values=instruction.operands.map(operand=>operand.choices?.find(choice=>Number(choice.id)===Number(operand.value))?.name??operand.value);
    const targetInstruction=script?.instructions.find(value=>value.key===instruction.targetKey);
    const target=instruction.targetLabel==='END'?'the end of this script':targetInstruction?`step ${targetInstruction.index+1}`:instruction.targetLabel;
    const ability=line=>{
      const table=enemyTableRow(state.data,row.id),choices=state.data.enemyTables?.choices;
      return ['low','medium','high'].map(tier=>{
        const entry=table?.tables.abilities[tier]?.find(value=>value.slot===Number(line));
        if(!entry)return `${tier}: special action ${line}`;
        const list=entry.type===2?state.data.magic?.rows:entry.type===4?state.data.items?.rows:choices?.enemyAbilities;
        return `${tier}: ${list?.find(value=>Number(value.id)===entry.abilityId)?.name||`ability ${entry.abilityId}`}`;
      }).join('; ');
    };
    if(!instruction.editable)return 'Unknown instruction bytes are preserved. This part cannot be edited.';
    switch(Number(instruction.opcode)){
      case 0:return 'Stop this script.';
      case 2:{const subject=Number(instruction.operands[0].value),constant=(subject>=80&&subject<=87)||(subject>=96&&subject<=103);return `If ${values[0]}${constant?'':` (parameter ${values[1]})`} ${values[2]} ${values[3]}, run the next step. Otherwise go to ${target}.`;}
      case 4:return `Target ${values[0]}.`;
      case 11:return `Choose one action at random: ${values.map(ability).join(' / ')}.`;
      case 12:return `Use action ${values[0]} (${ability(values[0])}).`;
      case 14:case 15:case 17:return `Set ${instruction.operands[0].type.replace('_var','')} variable ${values[0]} to ${values[1]}.`;
      case 18:case 19:case 21:return `Add ${values[1]} to ${instruction.operands[0].type.replace('_var','')} variable ${values[0]}.`;
      case 35:return Number(instruction.operands[0]?.value)===0?'Continue with the next instruction.':`Go to ${target}.`;
      case 1:case 24:case 26:{const text=enemyBattleTextRow(state.data,row.id)?.lines?.find(line=>line.id===Number(values[0]))?.text;return `${instruction.name}: ${text||`battle text ${values[0]}`}.`;}
      default:return `${instruction.name}${values.length?': '+instruction.operands.map((operand,index)=>`${operand.type.replaceAll('_',' ')} ${values[index]}`).join(', '):''}.`;
    }
  }
  function enemyAiScript(row,script){
    enemyAiNormalizeScript(script);
    const pageKey=`${row.id}:${script.id}`;
    state.enemyAiPages??={};
    state.enemyAiPageSizes??={};
    const opcodeChoices=enemyAiCatalog().map(value=>({id:value.opcode,name:value.name}));
    return LexeditorUI.instructionList({rows:script.instructions,page:state.enemyAiPages[pageKey]||0,pageSize:state.enemyAiPageSizes[pageKey],
      editable:state.activeSource==='mine',changePage:(value,size)=>{state.enemyAiPages[pageKey]=value;state.enemyAiPageSizes[pageKey]=size},
      controls:instruction=>{
        const controls=el('div',{class:'lex-instruction-controls'},enemyAiOpcodeControl(script,instruction,opcodeChoices),
          ...instruction.operands.filter(operand=>{
            const subject=Number(instruction.operands[0]?.value);
            return !(instruction.opcode===2&&operand.type==='subject_param'&&operand.value===200&&((subject>=80&&subject<=87)||(subject>=96&&subject<=103)));
          }).map(operand=>enemyAiOperand(row,script,instruction,operand)));
        if(state.activeSource!=='mine'||!instruction.editable)controls.querySelectorAll('input,select,button').forEach(control=>control.disabled=true);
        return controls;
      },describe:instruction=>enemyAiDescription(row,instruction,script),
      move:(from,to)=>enemyAiMove(script,from,to-from),
      insert:index=>enemyAiInsert(script,index),remove:index=>enemyAiDelete(script,index)});
  }
  function enemyAiSourceReference(dataset,row,scriptId){return enemyAiRow(dataset,row.id)?.scripts?.find(value=>value.id===scriptId)?.source}
  function enemyAiSourceScript(row,script){const input=LexeditorUI.codeField({rows:12,wrap:"off","aria-label":`${script.name} enemy AI source`,oninput:event=>{script.source=event.target.value;state.enemyAiDirtyRow=row;shell.refresh()}});input.value=script.source??"";input.readOnly=state.activeSource!=="mine";const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:enemyAiSourceReference(state.referenceData[reference.id],row,script.id)})).filter(value=>value.value!==undefined),summary=value=>`${String(value??"").split(/\r?\n/).filter(Boolean).length} lines`;return sourceControl(input,()=>script.source,enemyAiSourceReference(state.vanilla,row,script.id),references,value=>{script.source=String(value??"");state.enemyAiDirtyRow=row;shell.refresh()},summary,{internal:true})}
  async function enemyAiApplySource(row){
    const document=enemyAiRow(state.data,row.id);
    const sources=()=>document.scripts.map(script=>({id:script.id,source:script.source}));
    const submitted=sources();
    try{
      const result=await api("/api/enemy-ai/source/compile",post({sources:submitted}));
      // Do not replace edits made while the compiler was running.
      if(JSON.stringify(sources())!==JSON.stringify(submitted))return enemyAiApplySource(row);
      document.scripts=result.scripts;
      for(const [index,script] of document.scripts.entries()){
        script.source=result.sources[index];enemyAiNormalizeScript(script);
      }
      state.enemyAiDirtyRow=null;
      setStatus(`Compiled ${row.name} AI source`);shell.refresh();return true;
    }catch(error){
      setStatus("AI source has an error");
      showAlert({title:"AI source has an error",message:error.message||String(error)});
      return false;
    }
  }
  async function enemyAiBeforeLeave(){
    if(!state.enemyAiDirtyRow)return true;
    if(state.enemyAiCompilePending)return false;
    state.enemyAiCompilePending=true;
    try{return await enemyAiApplySource(state.enemyAiDirtyRow);}
    finally{state.enemyAiCompilePending=false;}
  }
  function enemyAiPanel(row){
    const ai=enemyAiRow(state.data,row.id);
    if(!ai?.available)return LexeditorUI.detailNote('This enemy has no battle-script section.');
    state.enemyAiScriptTab??=ai.scripts[0]?.id;
    const script=ai.scripts.find(value=>value.id===state.enemyAiScriptTab)||ai.scripts[0];
    const raw=state.enemyAiView==='source';
    const switchMode=async id=>{
      if(!(await enemyAiBeforeLeave()))return;
      state.enemyAiScriptTab=id;state.enemyAiView=raw?'structure':'source';renderEnemies();
    };
    const help='Right-click a script tab to switch between friendly rows and raw code. Drag a row to reorder it; Alt+Up or Alt+Down also moves a focused row. Branches follow their target instruction. Unknown bytes remain read-only. Raw edits compile when you leave a tab. An error keeps the current tab open.';
    const tabs=ai.scripts.map(value=>({id:value.id,label:value.name,help,
      attrs:{'aria-label':value.name,'aria-description':raw?'Raw code view':'Friendly view',oncontextmenu:event=>{event.preventDefault();switchMode(value.id)}}}));
    const content=raw?enemyAiSourceScript(row,script):enemyAiScript(row,script);
    return tabbedPanel({tabs,active:script.id,label:'Enemy AI scripts',change:async id=>{if(!(await enemyAiBeforeLeave()))return;state.enemyAiScriptTab=id;renderEnemies()},content});
  }
  function enemyBattleTextPanel(row,prefs){const scan=enemyScanSection(row,prefs);const document=enemyBattleTextRow(state.data,row.id),help=message=>LexeditorUI.detailNote(message);if(!document?.available)return LexeditorUI.stack({fill:false},scan,help("This enemy has no battle-script section."));if(!document.lines.length)return LexeditorUI.stack({fill:false},scan,help("This enemy has no local battle dialogue."));const vanilla=enemyBattleTextRow(state.vanilla,row.id),referenceLine=(dataset,id)=>enemyBattleTextRow(dataset,row.id)?.lines?.find(value=>value.id===id)?.text;return LexeditorUI.stack({fill:false},scan,help("These lines are used by this enemy during battle. Each line number matches a Show Text instruction in the AI view."),...document.lines.map(line=>{const input=LexeditorUI.textArea({rows:4,maxlength:400,"aria-label":`Battle text line ${line.id} for ${row.name}`,oninput:event=>{line.text=event.target.value;shell.refresh()}});input.value=line.text;const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:referenceLine(state.referenceData[reference.id],line.id)})).filter(value=>value.value!==undefined);return detailSection({className:"enemy-battle-text-line",title:`LINE ${line.id}`,body:sourceControl(input,()=>line.text,vanilla?.lines?.find(value=>value.id===line.id)?.text,references,value=>line.text=String(value??""))})}))}
  function enemyDetail(row,prefs){
    const table=enemyTableRow(state.data,row.id),tab=state.enemyDetailTab||'properties';
    const tabs=[{id:'properties',label:'Properties'},{id:'actions',label:'Actions',help:'The AI uses these action slots. Each level tier can use a different ability in the same slot.'},{id:'loot',label:'Loot'},
      {id:'renzokuken',label:'Renzokuken'},{id:'defense',label:'Defense'},
      {id:'text',label:'Text'},{id:'stats',label:'Stats',help:'Edit the coefficients to change how this enemy grows with its level.'}];
    let body=[];
    if(tab==='properties'){
      body=[enemyProperties(row.fields.filter(field=>field.group!=='Stat curves'),row.id,prefs)];
    }else if(tab==='actions'&&table)body=['low','medium','high'].map(tier=>enemyAbilitiesSection(table,tier));
    else if(tab==='loot'&&table)body=[enemyPairSection(table,'mug','MUG','Item'),enemyPairSection(table,'draw','DRAW','Magic'),enemyPairSection(table,'drops','DROPS','Item'),...enemySimpleTables(table).slice(0,2)];
    else if(tab==='renzokuken'&&table)body=enemySimpleTables(table).slice(2);
    else if(tab==='defense'&&table)body=[enemyDefenceSection(table,'elementDefence','ELEMENT'),enemyDefenceSection(table,'statusDefence','STATUS')];
    else if(tab==='text')body=[enemyBattleTextPanel(row,prefs)];
    else if(tab==='stats')body=[enemyStatGrowth(row.fields.filter(field=>field.group==='Stat curves'),row.id)];
    return tabbedPanel({tabs,active:tab,label:'Enemy details',change:async value=>{if(!(await enemyAiBeforeLeave()))return;state.enemyDetailTab=value;renderEnemies()},content:tab==='stats'?body:sharedDetail({...row,name:enemyDisplayName(row.name)},prefs,body,'enemy-detail')});
  }
  function enemyLeadingPanel(row){return enemyAiPanel(row)}
