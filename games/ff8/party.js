  function renderCharacters(){const rows=[...state.data.characters.rows].sort((a,b)=>a.name.localeCompare(b.name,undefined,{sensitivity:"base"}));if(!rows.some(row=>row.id===state.selected.characters))state.selected.characters=rows[0]?.id??null;const row=rows.find(candidate=>candidate.id===state.selected.characters);if(!row){$("#toolbar").replaceChildren();$("#main").replaceChildren(el("div",{class:"empty"},"No character records were found."));return}const detailId="character-detail";$("#toolbar").replaceChildren(portraitTabs("characters",rows,row.id,detailId,id=>{state.selected.characters=id;renderCharacters();shell.refresh()}));$("#main").replaceChildren(detailPanel({heading:false,className:"lex-detail detail character-detail",attrs:{id:detailId,role:"tabpanel","aria-labelledby":`characters-tab-${row.id}`,"data-character":row.id},body:characterDetail(row)}))}
  const gfPanelOrder=["GF Compatibility","General","Abilities"];
  function gfFieldsByPanel(row){const routed=new Map(gfPanelOrder.map(group=>[group,[]])),seen=new Set();for(const field of row.fields){if(seen.has(field.field)||!routed.has(field.group))throw new Error(`GF field routing failed: ${field.field}`);seen.add(field.field);routed.get(field.group).push(field)}if(seen.size!==row.fields.length)throw new Error("GF field routing omitted a field");return routed}
  function gfEntityLabel(field){const target=gfByName(field.label);return target?hoverable({class:"gf-entity-label",content:[el("span",{class:"gf-link-portrait-slot"},el("img",{class:"gf-link-portrait",src:`/assets/portraits/gfs/${target.id}.png`,alt:""})),el("span",{},field.label)],targetType:"gf",targetId:target.id,targetLabel:`${field.label} GF`,activate:()=>openGFByName(field.label)}):field.label}
  function gfFieldRow(field,row){return detailField({className:"gf-field-row",attrs:{"data-field":field.field},label:gfEntityLabel(field),help:field.help?infoHelp(field.help):null,control:fieldSourceControl(field,"gfs",row.id)})}
  function gfCompatibilityLabel(field){return gfEntityLabel(field)}
  function sortGfTable(kind,key){const [active,direction]=state.gfSorts[kind];state.gfSorts[kind]=[key,active===key?-direction:1];renderGFs()}
  // GF compatibility reads the same wherever it appears: one sortable table of
  // GF against the change this record applies, in its own panel. The Magic tab
  // shows exactly this panel, so the two are not two designs of one thing.
  function compatibilityPanel(fields,view,rowId){
    const [sortKey,sortDir]=state.gfSorts.compatibility;
    const sorted=[...fields].sort((a,b)=>sortDir*String(sortKey==="value"?gfCompatibilityFormat(a.value):a.label)
      .localeCompare(String(sortKey==="value"?gfCompatibilityFormat(b.value):b.label),undefined,{numeric:true,sensitivity:"base"}));
    const table=columnList({rows:sorted,key:field=>field.field,class:"gf-compat-table ff8-record-list",editable:true,
      sortState:{key:sortKey,dir:sortDir},sort:key=>sortGfTable("compatibility",key),
      template:"minmax(135px,1fr) minmax(75px,100px)",
      columns:[{key:"label",label:"GF",sortable:true,render:gfCompatibilityLabel},
        {key:"value",label:"Change",sortable:true,render:field=>fieldSourceControl(field,view,rowId)}]});
    return detailSection({className:"gf-panel compatibility",title:"COMPATIBILITY",
      help:infoHelp("Each time this GF is summoned from the command menu, the summoner's compatibility with the listed GFs changes by these amounts."),
      body:table,attrs:{"data-gf-panel":"compatibility"}});
  }
  const GF_CURVE_FIELDS=["gf_hp_modifier_1","gf_hp_modifier_2","gf_hp_modifier_3","gf_level_modifier_1","gf_level_modifier_2"];
  function gfPanel(title,fields,row,className){if(className==="compatibility")return compatibilityPanel(fields,"gfs",row.id);
    // The five curve modifiers are the graphs' variables, so they are not also
    // listed as loose numbers above them.
    const curveFields=fields.filter(field=>GF_CURVE_FIELDS.includes(field.field));
    const rest=fields.filter(field=>!GF_CURVE_FIELDS.includes(field.field));
    const growth=className==="general"?gfStatGrowth(curveFields,row.id):null;
    return detailSection({className:`gf-panel ${className}`,title,body:[growth,...(growth?rest:fields).map(field=>gfFieldRow(field,row))].filter(Boolean),attrs:{"data-gf-panel":className,"aria-label":title}})}
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
  function gfAbilities(fields,row){const groups=new Map();for(const field of fields){const key=field.row||field.field;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(field)}const find=(values,suffix="")=>values.find(field=>suffix?field.field.endsWith(suffix):/^ability\d+$/.test(field.field)),rows=[...groups].map(([key,values])=>({key,ability:find(values),level:find(values,"_level_or_prereq"),alternate:find(values,"_alt_prereq")})),[sortKey,sortDir]=state.gfSorts.abilities,sorted=rows.sort((a,b)=>sortDir*String(displayFieldValue(a[sortKey])).localeCompare(String(displayFieldValue(b[sortKey])),undefined,{numeric:true,sensitivity:"base"}));sorted.forEach(entry=>{entry.id=Number(String(entry.key).replace(/^ability/,""))||0});const slotNames=sorted.map(entry=>[entry.id,entry.ability?.lookup?.entries?.find(o=>Number(o.value)===Number(entry.ability.value))?.name||`slot ${entry.id}`]).sort((a,b)=>a[0]-b[0]);const table=columnList({rows:sorted,key:entry=>entry.key,class:"gf-ability-table ff8-record-list",editable:true,sortState:{key:sortKey,dir:sortDir},sort:key=>sortGfTable("abilities",key),template:"52px minmax(125px,1.2fr) minmax(140px,1fr) minmax(90px,.8fr)",columns:[{key:"slot",label:"Slot",sortable:false,numberedId:true,render:entry=>entry.id},{key:"ability",label:"Ability",sortable:true,render:entry=>entry.ability?fieldSourceControl(entry.ability,"gfs",row.id):"—"},{key:"level",label:"Prereq",help:"Choose whether this ability unlocks at a GF level or after another ability slot is learned. Values 1–100 are a GF level; 101–121 are the matching ability slot on this GF.",sortable:true,render:entry=>entry.level?el("div",{class:"gf-prereq-cell"},gfPrereqKind(entry.level,row),Number(entry.level.value)>100?gfPrereqSlot(entry.level,slotNames):fieldSourceControl(entry.level,"gfs",row.id)):"—"},{key:"alternate",label:"Alt. Prereq",help:"Points to another ability slot on this GF. This ability stays available only while that other ability is unfinished. 255 means no alternate restriction.",sortable:true,render:entry=>entry.alternate?fieldSourceControl(entry.alternate,"gfs",row.id):"—"}]});    return detailSection({className:"gf-panel abilities",title:"ABILITIES",
      body:table,attrs:{"data-gf-panel":"abilities"}})}
  function renderGFs(){
    const rows=[...state.data.gfs.rows].sort((a,b)=>a.name.localeCompare(b.name,undefined,{sensitivity:"base"}));
    if(!rows.some(row=>row.id===state.selected.gfs))state.selected.gfs=rows[0]?.id??null;
    const row=rows.find(candidate=>candidate.id===state.selected.gfs);if(!row){$("#toolbar").replaceChildren();$("#main").replaceChildren(el("div",{class:"empty"},"No GF records were found."));return}
    const subtabs=portraitTabs("gfs",rows,row.id,"gf-detail",id=>{state.selected.gfs=id;renderGFs();shell.refresh()});
    $("#toolbar").replaceChildren(subtabs);
    const routed=gfFieldsByPanel(row),panels=gfPanelOrder.map(group=>group==="Abilities"?gfAbilities(routed.get(group),row):gfPanel(group==="GF Compatibility"?"COMPATIBILITY":group.toLocaleUpperCase(),routed.get(group),row,group==="General"?"general":"compatibility"));
    const layout=panelLayout(panels,"gf-three-panel",{layoutKey:"ff8-gfs",defaultSizes:[.9,1.05,1.4],minSizes:[230,245,470],stackAt:1000});
    Object.assign(layout,{id:"gf-detail"});layout.setAttribute("role","tabpanel");layout.setAttribute("aria-labelledby",`gfs-tab-${row.id}`);layout.dataset.gf=row.id;$("#main").replaceChildren(layout);
  }
  function fieldGroups(fields,view,rowId,collapsible=true,prefs=null){
    const groups=new Map();
    for(const field of fields){
      if(!groups.has(field.group))groups.set(field.group,[]);
      groups.get(field.group).push(field);
    }
    return el("div",{class:"field-groups"},...[...groups].map(([name,rows])=>{
      return detailSection({className:"field-group",title:name,body:rows.map(field=>
        detailField({className:"field-row",label:field.label,help:field.help?infoHelp(field.help):null,
          control:fieldSourceControl(field,view,rowId),pin:prefs?.pinButton(`field:${field.field}`,field.label)}))});
    }));
  }
  function gfCompatibilityFormat(value){const modifier=(Number(value)-100)/10;return modifier>0?`+${formatNumber(modifier,{maximumFractionDigits:1})}`:formatNumber(modifier,{maximumFractionDigits:1})}
  function gfCompatibilityControl(field){
    const control=el("input",{type:"text",inputmode:"decimal",value:gfCompatibilityFormat(field.value),class:"gf-compat-input","aria-label":`${field.label} compatibility modifier`,oninput:event=>{const next=Number(String(event.target.value).replaceAll(",",""));if(!Number.isFinite(next))return;const bounded=Math.max(-10,Math.min(15.5,Math.round(next*10)/10));field.value=Math.round(bounded*10+100);shell.refresh()},onblur:event=>{event.target.value=gfCompatibilityFormat(field.value)}});
    return el("span",{class:"gf-compat-control"},control)
  }
  const booleanGlyph=value=>value?"\u2713":"\u00d7";
  const booleanMark=value=>el("span",{class:"lex-boolean-mark lex-ui-symbol"},booleanGlyph(value));
  function flagSourceControl(field,view,rowId){
    const lookup=field.lookup,vanillaField=rowOf(state.vanilla,view,rowId)?.fields?.find(value=>value.field===field.field),referenceFields=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,field:rowOf(state.referenceData[reference.id],view,rowId)?.fields?.find(value=>value.field===field.field)})),iconOnly=["element","j_status"].includes(String(lookup.name));
    return el("div",{class:`flag-list flag-list-${String(lookup.name||"flags").replace(/[^a-z0-9_-]/gi,"-")} ${iconOnly?"flag-list-icon-toggles":""}`},...lookup.entries.map(entry=>{
      const bit=Number(entry.mask??entry.value),read=value=>(Number(value??0)&bit)===bit,apply=checked=>{field.value=checked?(Number(field.value)|bit):(Number(field.value)&~bit)},setState=checked=>{stateMark.textContent=booleanGlyph(checked);stateMark.classList.toggle("positive",checked);stateMark.classList.toggle("negative",!checked)},input=el("input",{type:"checkbox",checked:read(field.value),"aria-label":entry.name,onchange:event=>{apply(event.target.checked);setState(event.target.checked);shell.refresh()}}),stateMark=el("span",{class:`ff8-flag-state ${read(field.value)?"positive":"negative"}`,"aria-hidden":"true"},booleanGlyph(read(field.value))),control=el("label",{class:iconOnly?"ff8-icon-toggle":"ff8-flag-toggle",title:entry.name},input,conceptIcon(lookup.name,entry.name),iconOnly?stateMark:el("span",{},entry.name));
      const refs=referenceFields.filter(reference=>reference.field).map(reference=>({name:reference.name,shortName:reference.shortName,value:read(reference.field.value)}));
      return sourceControl(control,()=>read(field.value),read(vanillaField?.value),refs,apply,booleanMark);
    }))
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
  function conceptIcon(lookup,name){const id=lookup==="element"?elementIcons[name]:statusIcons[name];return id?el("img",{class:"ff8-concept-icon",src:`/assets/icons/${id}.png`,alt:"",title:`${name} game icon`}):null}
  function fieldControl(field){const lookup=field.lookup;if(field.control==="boolean")return el("input",{type:"checkbox",checked:Boolean(field.value),"aria-label":field.label,onchange:event=>{field.value=event.target.checked;shell.refresh()}});if(lookup?.type==="enum")return lookup.name==="item"?itemSelectControl(field.value,lookup.entries.map(entry=>({...entry,iconId:itemById(entry.value)?.iconId})),value=>field.value=value):selectControl(field.value,lookup.entries,value=>field.value=value);if(lookup?.type==="flags"){return el("div",{class:`flag-list flag-list-${String(lookup.name||"flags").replace(/[^a-z0-9_-]/gi,"-")}`},...lookup.entries.map(entry=>{const bit=Number(entry.mask??entry.value),checked=(field.value&bit)===bit;return el("label",{title:entry.name},el("input",{type:"checkbox",checked,"aria-label":entry.name,onchange:event=>{field.value=event.target.checked?(field.value|bit):(field.value&~bit);shell.refresh()}}),conceptIcon(lookup.name,entry.name),entry.name)}))}if(field.field==="hit_rate")return ratio255Control(field.value,value=>field.value=value,field.label);const control=numberControl(field.value,field.minimum,field.maximum,field.control==="percent"?.1:1,value=>field.value=value);return field.control==="percent"?unitField(control,"%"):control}

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
      return curveEditor({title:stat,className:"ff8-character-curve ff8-enemy-curve",overlayExtrema:true,variables,domain:{min:1,max:100},range:()=>enemyCurveRange(stat,statFields),graphLabel:`${stat} from enemy level 1 to 100`,evaluate:level=>enemyCurveValue(stat,statFields,level),formula:coloredCurveFormula(enemyCurveFormula(stat))});
    });
    return detailSection({className:"enemy-stat-growth character-stat-growth",title:"STAT CURVES",help:infoHelp("Each graph previews how this enemy stat changes as enemy level changes, using FF8's verified four-byte stat equation."),body:el("div",{class:"character-curve-grid"},...cards)});
  }
  function magicSearchControl(value,prompt,accept,origin){
    const magic=state.data.magic.rows.find(row=>Number(row.id)===Number(value))||{id:value,name:`Magic ${value}`};
    // The name is an ordinary hoverable and the magnifier is its own control,
    // so following the link and picking a different record stay separate.
    const link=hoverable({class:"ff8-entity-search-name",content:magicLabel(magic),targetType:"magic",targetId:magic.id,targetLabel:magic.name,activate:()=>{state.selected.magic=Number(magic.id);navigate("magic")}});
    const finder=el("button",{type:"button",class:"ff8-entity-search-button",title:"Choose magic","aria-label":"Choose magic",onclick:event=>{event.preventDefault();event.stopPropagation();beginSearcher({type:"magic",prompt,target:()=>navigate("magic"),origin,accept})}},searchIcon());
    return el("span",{class:"ff8-entity-search"},link,finder);
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
    const tiers=[['low','LOW'],['medium','MED'],['high','HIGH']], draw=kind==='draw';
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
      return el('div',{class:'enemy-tier-entry','data-slot':entry.slot},value,
        enemyTableSource(unitField(quantity,'×',{unitClass:'enemy-quantity-unit',boxed:false}),row,
          value=>read(value)?.quantity,value=>entry.quantity=Number(value)));
    };
    const table=columnList({
      rows:tiers.map(([tier,label])=>({key:tier,tier,label})),
      key:entry=>entry.key,
      class:`enemy-tier-table enemy-${kind}-table`,
      'aria-label':`${title} by level tier`,
      editable:true, localSort:false, showHeader:!draw,
      template:'42px repeat(4,minmax(0,1fr))',
      rowClass:entry=>`enemy-tier-row enemy-tier-${entry.tier}`,
      columns:[{key:'label',label:'LEVEL',render:entry=>entry.label},
        ...[0,1,2,3].map(index=>({key:`slot${index}`,label:`SLOT ${index+1}`,
          render:entry=>slotCell(entry.tier,entry.label,index)}))],
    });
    return detailSection({className:'enemy-table-section enemy-tier-section',title,body:el('fieldset',{class:'enemy-table-controls',disabled:state.activeSource!=='mine'},table)});
  }
  function enemyCardChoices(row){
    const choices=state.data.enemyTables.choices.cards;
    return el('fieldset',{class:'enemy-card-choices',disabled:state.activeSource!=='mine'},...row.tables.cards.map(entry=>{
      const id=Number(entry.cardId),card=rowOf(state.data,'cards',id)||choices.find(value=>Number(value.id)===id);
      const name=card?.name||`Card ${id}`,origin=()=>{state.selected.enemies=row.id;navigate('enemies')};
      const set=value=>{entry.cardId=Number(value);shell.refresh()};
      const placeholder=el('span',{class:'enemy-card-placeholder','aria-hidden':'true'},id===255?'—':'?');
      const art=el('span',{class:'enemy-card-art'},placeholder);
      if(id>=0&&id<110){
        const image=el('img',{src:`/assets/cards/${id}.png`,alt:name,
          onload:()=>{placeholder.hidden=true},onerror:()=>{image.remove();placeholder.textContent='Art unavailable'}});
        art.append(image);
      }
      const choose=el('button',{type:'button',class:'enemy-card-finder',disabled:state.activeSource!=='mine',
        'aria-label':`Choose card for slot ${entry.slot+1}: ${name}`,
        title:`Choose card for slot ${entry.slot+1}: ${name}`,onclick:()=>beginSearcher({type:'cards',
          prompt:`Select card ${entry.slot+1} for ${row.name}.`,target:()=>navigate('cards'),origin,accept:set})},
        art,el('span',{class:'enemy-card-name'},el('span',{},name),searchIcon()));
      // 255 is a real sentinel in the existing schema, not card zero. Keep it
      // selectable even though the Cards tab only contains the 110 real cards.
      const clear=el('button',{type:'button',class:'enemy-card-clear',disabled:state.activeSource!=='mine'||id===255,
        title:'Set to Immune (stored card ID 255)','aria-label':`Clear card slot ${entry.slot+1}`,
        onclick:()=>{set(255);renderEnemies()}},'×');
      const control=el('div',{class:'enemy-card-choice','data-slot':entry.slot},choose,clear);
      return enemyTableSource(control,row,value=>value?.tables.cards.find(value=>value.slot===entry.slot)?.cardId,
        set,value=>rowOf(state.data,'cards',Number(value))?.name||choiceName(choices,value));
    }));
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
    const devour=detailField({label:"DEVOUR",
      help:infoHelp("Devouring the enemy gives one of these three outcomes. Which tier you get depends on the enemy's level at the time; the cut-offs differ for a few vanilla enemies, so Lexeditor does not state a universal range."),
      control:multiNumberRow((row.tables.devour||[]).map(entry=>({
        label:tierNames[entry.slot]||`Tier ${entry.slot+1}`,
        title:`${tierNames[entry.slot]||`Tier ${entry.slot+1}`}-tier Devour outcome`,
        control:devourControl(entry)})),{columns:3})});
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
    const grid=el('fieldset',{class:`enemy-defence-grid ${element?'enemy-elements':'enemy-statuses'}`,disabled:state.activeSource!=='mine'},
      ...row.tables[kind].map(entry=>{
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
        const mark=el('span',{class:'enemy-immunity-label','aria-hidden':'true'},'IMMUNE');
        const checkbox=el('input',{type:'checkbox','aria-label':`${name} immune`,onchange:()=>{
          if(checkbox.checked){if(!isImmune())enemyDefencePrevious.set(entry,entry.percent);setPercent(immune)}
          else setPercent(enemyDefencePrevious.get(entry)??neutral);
          input.value=entry.percent;sync();input.dispatchEvent(new Event('change',{bubbles:true}));
        }});
        const icon=conceptIcon(element?'element':'status',aliases[name]||name);
        // Some defence bytes (e.g. Haste/Unused) have no mapped native menu
        // icon. Keep a named tile, never a blank or invented game sprite.
        const fallback=el('span',{class:'enemy-status-fallback',hidden:!!icon,'aria-hidden':'true'},'▧');
        if(icon)icon.addEventListener('error',()=>{icon.remove();fallback.hidden=false},{once:true});
        const toggle=el('label',{class:'ff8-icon-toggle enemy-defence-toggle',title:`${name}: toggle immunity`},
          checkbox,icon,fallback,mark);
        const tile=el('div',{class:'enemy-defence-tile','data-defence':name},toggle,
          el('span',{class:'enemy-defence-name'},name),enemyTableSource(unitField(input,'%'),row,read,setPercent,value=>`${value}%`));
        const sync=()=>{const checked=isImmune();checkbox.checked=checked;checkbox.disabled=state.activeSource!=='mine';
          input.disabled=checked||state.activeSource!=='mine';tile.classList.toggle('immune',checked);mark.hidden=!checked};
        sync();return tile;
      }));
    return detailSection({className:'enemy-table-section enemy-defence-section',title,help,body:grid});
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
    const input=el("textarea",{rows:6,"aria-label":`Scan description for ${row.name}`,oninput:event=>{row.scanDescription=event.target.value;shell.refresh()}});input.value=row.scanDescription??"";
    const details=enemyGeneratedScanDetails(row),apply=el('button',{type:'button',class:'secondary-action',disabled:state.activeSource!=='mine',onclick:()=>{applyEnemyScanDetails(row);renderEnemies();shell.refresh()}},'UPDATE DETAILS');
    const applyAll=el('button',{type:'button',class:'secondary-action',disabled:state.activeSource!=='mine',onclick:()=>{for(const enemy of state.data.enemies.rows)if(enemy.available)applyEnemyScanDetails(enemy);renderEnemies();shell.refresh()}},'UPDATE ALL');
    return detailSection({className:"enemy-scan-section",title:"SCAN",body:[detailField({label:"DESCRIPTION",control:sourceControl(input,()=>row.scanDescription,rowOf(state.vanilla,"enemies",row.id)?.scanDescription,referenceValues("enemies",row.id,value=>value?.scanDescription),value=>row.scanDescription=String(value??"")),pin:prefs?.pinButton("scanDescription","Scan description")}),el('div',{class:'enemy-scan-details-actions'},apply,applyAll),el('pre',{class:'enemy-scan-details-preview'},details)]})
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
    const property=field=>el('div',{class:'enemy-property'},
      el('span',{class:'enemy-property-name',title:field.label},enemyPropertyLabel(field),field.help?infoHelp(field.help):null,
        prefs?.pinButton(`field:${field.field}`,field.label)),fieldSourceControl(field,'enemies',rowId,{internal:true}));
    return detailSection({className:'enemy-properties-section',title:'PROPERTIES',body:el('fieldset',{class:'enemy-properties-compact',disabled:state.activeSource!=='mine'},
      el('div',{class:'enemy-properties-row enemy-properties-numeric',style:`--enemy-property-count:${Math.max(1,numeric.length)}`},...numeric.map(property)),
      flags.length?enemyFlagsField(flags,rowId,prefs):null)});
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
  function enemyAiOperand(row,script,instruction,operand){if(["jump16","skip16"].includes(operand.type)){const targets=script.instructions.filter(value=>operand.type!=="skip16"||value.offset>=instruction.offset+instruction.size),chosen=targets.find(value=>value.key===instruction.targetKey),control=lazyOptions(el("select",{"aria-label":`${operand.type} target`,onchange:event=>{instruction.targetKey=event.target.value;enemyAiSyncSource(script);renderEnemies();shell.refresh()}},chosen?el("option",{value:chosen.key},chosen.label):el("option",{value:"end"},"END")),()=>[...targets.map(value=>({value:value.key,label:value.label})),{value:"end",label:"END"}]);return el("label",{class:"enemy-ai-operand",title:`${operand.type} target`},el("small",{},"TARGET"),autoFitControlText(control))}const find=dataset=>{const other=enemyAiRow(dataset,row.id)?.scripts?.find(value=>value.id===script.id)?.instructions?.find(value=>value.key===instruction.key||value.offset===instruction.offset);return other?.operands?.find(value=>value.index===operand.index)?.value},references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:find(state.referenceData[reference.id])})).filter(value=>value.value!==undefined),update=value=>{operand.value=value;enemyAiSyncSource(script);shell.refresh()};return el("label",{class:"enemy-ai-operand",title:`${operand.type} operand ${operand.index+1}`},el("small",{},operand.type.toLocaleUpperCase()),sourceControl(enemyAiOperandControl(operand,update),()=>operand.value,find(state.vanilla),references,update))}
  function enemyAiOpcodeControl(script,instruction,choices){const control=selectControl(instruction.opcode,choices,value=>enemyAiChangeOpcode(script,instruction,value));control.classList.add("enemy-ai-opcode");control.setAttribute("aria-label",`Opcode at ${instruction.label}`);return control}
  function enemyAiScript(row,script){enemyAiNormalizeScript(script);const opcodeChoices=enemyAiCatalog().map(value=>({id:value.opcode,name:`${value.opcode} · ${value.name}`})),instructions=el("div",{class:"enemy-ai-instructions"},...script.instructions.map((instruction,index)=>el("div",{class:"enemy-ai-instruction","data-offset":instruction.offset},el("span",{class:"enemy-ai-instruction-label"},instruction.label),enemyAiOpcodeControl(script,instruction,opcodeChoices),el("div",{class:"enemy-ai-actions"},el("button",{type:"button",class:"enemy-ai-action",title:"Move instruction up",disabled:index===0,onclick:()=>enemyAiMove(script,index,-1)},"↑"),el("button",{type:"button",class:"enemy-ai-action",title:"Move instruction down",disabled:index===script.instructions.length-1,onclick:()=>enemyAiMove(script,index,1)},"↓"),el("button",{type:"button",class:"enemy-ai-action",title:"Insert instruction after",onclick:()=>enemyAiInsert(script,index)},"+"),el("button",{type:"button",class:"enemy-ai-action",title:"Delete instruction",onclick:()=>enemyAiDelete(script,index)},"−")),instruction.editable?el("div",{class:"enemy-ai-operands"},...instruction.operands.map(operand=>enemyAiOperand(row,script,instruction,operand))):el("span",{class:"enemy-ai-operands readonly-note"},"Preserved; unsupported"),el("code",{class:"enemy-ai-raw",title:instruction.raw},instruction.raw),instruction.targetLabel?el("span",{class:`enemy-ai-branch${instruction.targetValid?"":" invalid"}`},`→ ${instruction.targetLabel}`):null)));return detailSection({className:"enemy-ai-script",title:script.name.toLocaleUpperCase(),body:instructions})}
  function enemyAiSourceReference(dataset,row,scriptId){return enemyAiRow(dataset,row.id)?.scripts?.find(value=>value.id===scriptId)?.source}
  function enemyAiSourceScript(row,script){const input=el("textarea",{class:"enemy-ai-source-editor",spellcheck:"false",wrap:"off","aria-label":`${script.name} enemy AI source`,oninput:event=>{script.source=event.target.value;shell.refresh()}});input.value=script.source??"";const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:enemyAiSourceReference(state.referenceData[reference.id],row,script.id)})).filter(value=>value.value!==undefined),summary=value=>`${String(value??"").split(/\r?\n/).filter(Boolean).length} lines`;return detailSection({className:"enemy-ai-source-script",title:script.name.toLocaleUpperCase(),body:sourceControl(input,()=>script.source,enemyAiSourceReference(state.vanilla,row,script.id),references,value=>{script.source=String(value??"");shell.refresh()},summary)})}
  async function enemyAiApplySource(row){const document=enemyAiRow(state.data,row.id);try{const result=await api("/api/enemy-ai/source/compile",post({sources:document.scripts.map(script=>({id:script.id,source:script.source}))}));document.scripts=result.scripts;for(const [index,script] of document.scripts.entries()){script.source=result.sources[index];enemyAiNormalizeScript(script)}setStatus(`Compiled ${row.name} AI source`);renderEnemies();shell.refresh()}catch(error){setStatus("AI source has an error");showAlert({title:"AI source has an error",message:error.message||String(error)})}}
  function enemyAiPanel(row,table){const ai=enemyAiRow(state.data,row.id),tabs=subtabBar({className:"enemy-ai-view-tabs",tabs:[{id:"structure",label:"Structure"},{id:"source",label:"Source"}],active:state.enemyAiView,label:"Enemy AI editor view",change:value=>{state.enemyAiView=value;renderEnemies()}}),boundary=el("p",{class:"enemy-ai-boundary"},state.enemyAiView==="source"?"Source uses stable labels, exact opcode names, and typed operands. Branch operands name a label. Apply Source validates it and updates the structural view; Save also compiles it through the same fail-closed DAT compiler.":"The five conditional scripts below are decoded and rebuilt with the proved FF8 opcode table. You can replace, insert, delete, and reorder instructions. Branches target instruction labels and are recalculated when the script changes. Unsupported raw tails remain fail-closed.");if(!ai?.available)return el("div",{class:"enemy-ai-content"},tabs,el("p",{class:"readonly-note"},"This enemy has no battle-script section."));if(state.enemyAiView==="source")return el("div",{class:"enemy-ai-content"},tabs,boundary,el("div",{class:"enemy-ai-source-actions"},el("button",{type:"button",class:"enemy-ai-source-apply",onclick:()=>enemyAiApplySource(row)},"Apply Source")),...ai.scripts.map(script=>enemyAiSourceScript(row,script)));const scripts=ai.scripts.map(script=>enemyAiScript(row,script)),actions=table?[detailSection({className:"enemy-action-definitions",title:"ACTION DEFINITIONS",help:infoHelp("These are the fixed low, medium, and high-level action lists referenced by AI commands. They are data tables, not the conditional AI program."),body:["low","medium","high"].map(tier=>enemyAbilitiesSection(table,tier))})]:el("p",{class:"readonly-note"},"No structured action definitions are available for this enemy.");return el("div",{class:"enemy-ai-content"},tabs,boundary,...scripts,actions)}
  function enemyBattleTextPanel(row,prefs){const scan=enemyScanSection(row,prefs);const document=enemyBattleTextRow(state.data,row.id),help=message=>el("h3",{class:"enemy-battle-text-help"},"BATTLE TEXT ",infoHelp(message));if(!document?.available)return el("div",{class:"enemy-battle-text-content"},scan,help("This enemy has no battle-script section."));if(!document.lines.length)return el("div",{class:"enemy-battle-text-content"},scan,help("This enemy has no local battle dialogue."));const vanilla=enemyBattleTextRow(state.vanilla,row.id),referenceLine=(dataset,id)=>enemyBattleTextRow(dataset,row.id)?.lines?.find(value=>value.id===id)?.text;return el("div",{class:"enemy-battle-text-content"},scan,help("These lines are used by this enemy during battle. Each line number matches a Show Text instruction in the AI view."),...document.lines.map(line=>{const input=el("textarea",{rows:4,maxlength:400,"aria-label":`Battle text line ${line.id} for ${row.name}`,oninput:event=>{line.text=event.target.value;shell.refresh()}});input.value=line.text;const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:referenceLine(state.referenceData[reference.id],line.id)})).filter(value=>value.value!==undefined);return detailSection({className:"enemy-battle-text-line",title:`LINE ${line.id}`,body:sourceControl(input,()=>line.text,vanilla?.lines?.find(value=>value.id===line.id)?.text,references,value=>line.text=String(value??""))})}))}
  function enemyDetail(row,prefs){const table=enemyTableRow(state.data,row.id),body=[];if(row.available){const other=row.fields.filter(field=>field.group!=="Stat curves");body.push(enemyProperties(other,row.id,prefs))}else body.push(el("p",{class:"readonly-note"},"This enemy file is not available in the extracted game data."));if(table)body.push(enemyPairSection(table,"draw","DRAW","Magic"),enemyPairSection(table,"mug","MUG","Item"),enemyPairSection(table,"drops","DROPS","Item"),...enemySimpleTables(table),enemyDefenceSection(table,"elementDefence","ELEMENT DEFENCE"),enemyDefenceSection(table,"statusDefence","STATUS DEFENCE"));const detail=sharedDetail({...row,name:enemyDisplayName(row.name)},prefs,body,"enemy-detail");return detail}
  function enemyLeadingPanel(row,prefs){const table=enemyTableRow(state.data,row.id);const tabs=[{id:"stats",label:"Stats"},{id:"ai",label:"AI"},{id:"battleText",label:"Battle Text"}],content=state.enemyPanelTab==="ai"?enemyAiPanel(row,table):state.enemyPanelTab==="battleText"?enemyBattleTextPanel(row,prefs||state.columnPrefs.enemies):row.available?enemyStatGrowth(row.fields.filter(field=>field.group==="Stat curves"),row.id):el("p",{class:"readonly-note"},"Enemy data unavailable"),tabbed=tabbedPanel({className:"enemy-tabbed-column",contentClassName:state.enemyPanelTab==="stats"?"enemy-curve-column":"",tabs,active:state.enemyPanelTab,label:`${row.name} enemy views`,change:value=>{state.enemyPanelTab=value;renderEnemies();shell.refresh()},content});return tabbed}
