"use strict";
  const CURVE_BRACKETS=["2–11","12–21","22–31","32–41","42–51","52–61","62–81","82–99"];
  function fieldByKey(key){return category().fields.find(field=>field.key===key)}
  function fieldDetail(row,field){const help=semanticHelp(field);return detailField({className:"ff7-field",label:field.label,help:help?infoHelp(help):null,control:semanticControl(row,field),dataType:semanticType(field),min:field.minimum,max:field.maximum})}
  function ordinarySections(row,omit=new Set()){
    const metadata=category(),fields=metadata.fields.filter(field=>!omit.has(field.key)),groups=[...new Set(fields.map(field=>field.group||"Kernel data"))],body=[];
    if(metadata.descriptionEditable){
      const help="The in-game description stored in this FF7 KERNEL.BIN. Byte escapes are preserved for game control codes.",control=descriptionControl(row);control.style.width="100%";
      body.push(detailSection({title:"DESCRIPTION",attrs:{"data-concept":"editable-description"},help:infoHelp(help),body:el("div",{style:"padding:10px;min-width:0"},control)}));
    }
    body.push(...groups.map(group=>detailSection({title:group.toUpperCase(),body:fields.filter(field=>(field.group||"Kernel data")===group).map(field=>fieldDetail(row,field))})));
    return body;
  }
  function conceptTable(rows,template,columns,label){return columnList({rows,key:entry=>entry.key,class:"ff7-concept-table",editable:true,template,columns,"aria-label":label})}
  function conceptPanel(row,body){return detailPanel({className:"ff7-detail",title:displayRowName(row),identity:recordId(row.id),meta:null,body})}
  function growthCurveKind(row){return row.id<37?"primary":row.id<46?"hp":row.id<55?"mp":"exp"}
  function growthBracket(level){return level<12?0:level<22?1:level<32?2:level<42?3:level<52?4:level<62?5:level<82?6:7}
  function growthCurveValue(row,level){const i=growthBracket(level),gradient=Number(row.values[`gradient${i}`]),base=Number(row.values[`base${i}`]),kind=growthCurveKind(row);if(kind==="hp")return base*40+(level-1)*gradient;if(kind==="mp")return base*2+Math.floor((level-1)*gradient/10);if(kind==="exp")return Math.floor(gradient*(level-1)*(level-1)/10);return base+Math.floor(gradient*level/100)}
  function growthCurvePreview(row){const values=Array.from({length:98},(_,i)=>growthCurveValue(row,i+2)),min=Math.min(...values),max=Math.max(...values),span=Math.max(1,max-min),points=values.map((value,i)=>`${(i*100/(values.length-1)).toFixed(2)},${(32-(value-min)*30/span).toFixed(2)}`),ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg"),title=document.createElementNS(ns,"title"),line=document.createElementNS(ns,"polyline");svg.setAttribute("viewBox","0 0 100 34");svg.setAttribute("role","img");svg.setAttribute("aria-label",`${row.name} curve preview`);svg.setAttribute("preserveAspectRatio","none");title.textContent=`${row.name}: ${min} to ${max}`;line.setAttribute("points",points.join(" "));line.setAttribute("fill","none");line.setAttribute("stroke","currentColor");line.setAttribute("stroke-width","1.2");line.setAttribute("vector-effect","non-scaling-stroke");svg.append(title,line);return el("div",{},svg,el("small",{},`Level 2–99 preview · ${min} → ${max}`))}
  function growthCurveDetail(row){
    const kind=growthCurveKind(row),formula=kind==="hp"?"Baseline = Base × 40 + (Level − 1) × Gradient":kind==="mp"?"Baseline = Base × 2 + floor((Level − 1) × Gradient / 10)":kind==="exp"?"EXP for level = floor(Gradient × (Level − 1)² / 10); Base is ignored":"Baseline = Base + floor(Gradient × Level / 100)",brackets=CURVE_BRACKETS.map((levels,i)=>({key:i,levels,gradient:fieldByKey(`gradient${i}`),base:fieldByKey(`base${i}`)}));
    const table=conceptTable(brackets,"minmax(82px,.8fr) minmax(90px,1fr) minmax(90px,1fr)",[
      {key:"levels",label:"Levels",render:entry=>entry.levels},
      {key:"gradient",label:"Gradient",render:entry=>semanticControl(row,{...entry.gradient,rerenderOnChange:true})},
      {key:"base",label:kind==="exp"?"Base (unused)":"Base",render:entry=>semanticControl(row,{...entry.base,rerenderOnChange:true})},
    ],"Growth curve brackets");
    return conceptPanel(row,[detailSection({title:"FORMULA & PREVIEW",attrs:{"data-concept":"growth-curve"},body:[detailField({label:"FORMULA",control:readonlyField(formula)}),growthCurvePreview(row)]}),detailSection({title:"LEVEL BRACKETS",body:table})]);
  }
  function growthBonusDetail(row){const unit=row.id===0?"Stat gain":row.id===1?"HP factor (%)":"MP factor (%)",entries=Array.from({length:12},(_,i)=>({key:i,index:i,field:fieldByKey(`bonus${i}`)})),table=conceptTable(entries,"72px minmax(120px,1fr)",[{key:"index",label:"Difference",render:entry=>entry.index},{key:"value",label:unit,render:entry=>semanticControl(row,entry.field)}],"Growth bonus brackets");return conceptPanel(row,[detailSection({title:"RANDOMIZED LEVEL GAIN",attrs:{"data-concept":"growth-bonuses"},help:infoHelp("The game compares the current stat to the selected growth curve, adds a random 1–8 modifier, clamps the result to bracket 0–11, then uses this table for the final gain/factor."),body:table})])}
  function equipmentDetail(row){
    const count=state.tab==="accessories"?2:4,slots=state.tab==="weapons"||state.tab==="armor"?8:0,omit=new Set();for(let i=1;i<=count;i++){omit.add(`boostedStat${i}`);omit.add(`boostedStat${i}Bonus`)}for(let i=1;i<=slots;i++)omit.add(`materiaSlot${i}`);
    const body=ordinarySections(row,omit),bonuses=Array.from({length:count},(_,i)=>({key:i+1,stat:fieldByKey(`boostedStat${i+1}`),amount:fieldByKey(`boostedStat${i+1}Bonus`)}));
    body.push(detailSection({title:"STAT BONUSES",attrs:{"data-concept":"equipment-stat-bonuses"},body:conceptTable(bonuses,"44px minmax(120px,1fr) minmax(90px,.8fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"stat",label:"Stat",render:e=>semanticControl(row,e.stat)},{key:"amount",label:"Amount",render:e=>semanticControl(row,e.amount)}],"Equipment stat bonuses")}));
    if(slots){const entries=Array.from({length:8},(_,i)=>({key:i+1,field:fieldByKey(`materiaSlot${i+1}`)}));body.push(detailSection({title:"MATERIA SLOTS",attrs:{"data-concept":"equipment-materia-slots"},body:conceptTable(entries,"44px minmax(150px,1fr)",[{key:"slot",label:"Slot",numberedId:true,render:e=>e.key},{key:"kind",label:"Layout / growth",render:e=>semanticControl(row,e.field)}],"Equipment Materia slots")}))}
    return conceptPanel(row,body);
  }
  function characterDetail(row){
    const settingsTable=(keys,label)=>conceptTable(keys.map((key,index)=>({key:index,field:fieldByKey(key)})),"minmax(140px,.9fr) minmax(170px,1.3fr)",[
      {key:"setting",label:"Setting",render:e=>e.field.label},
      {key:"value",label:"Value",render:e=>semanticControl(row,e.field)},
    ],label);
    const body=[];

    body.push(detailSection({title:"STARTING CHARACTER",attrs:{"data-concept":"character-loadout"},body:settingsTable([
      "storedId","weaponId","armorId","accessoryId","rowByte"
    ],"Starting character and loadout")}));
    body.push(detailSection({title:"STARTING BATTLE STATUS",body:el("div",{style:"padding:10px;min-width:0"},semanticControl(row,fieldByKey("characterFlags")))}));

    body.push(detailSection({title:"PROGRESSION",attrs:{"data-concept":"character-progression"},body:settingsTable([
      "level","currentExp","expToNextLevel","levelProgress","experienceCurve","recruitOffsetRaw"
    ],"Character starting progression")}));

    const stats=["strength","vitality","magic","spirit","dexterity","luck"].map((key,index)=>({
      key:index,name:key[0].toUpperCase()+key.slice(1),value:fieldByKey(key),bonus:fieldByKey(`${key}Bonus`),curve:fieldByKey(`${key}Curve`)
    }));
    body.push(detailSection({title:"CORE STATS",attrs:{"data-concept":"character-core-stats"},body:[el("span",{"data-concept":"character-growth-curves",hidden:true}),conceptTable(stats,
      "minmax(88px,.8fr) minmax(72px,.6fr) minmax(72px,.6fr) minmax(145px,1.25fr)",[
        {key:"stat",label:"Stat",render:e=>e.name},
        {key:"value",label:"Start",render:e=>semanticControl(row,e.value)},
        {key:"bonus",label:"Bonus",render:e=>semanticControl(row,e.bonus)},
        {key:"curve",label:"Growth curve",render:e=>semanticControl(row,e.curve)},
      ],"Character core stats and growth curves")]}));

    const resources=[
      {key:"hp",name:"HP",current:fieldByKey("currentHp"),base:fieldByKey("baseHp"),maximum:fieldByKey("maxHp"),curve:fieldByKey("hpCurve")},
      {key:"mp",name:"MP",current:fieldByKey("currentMp"),base:fieldByKey("baseMp"),maximum:fieldByKey("maxMp"),curve:fieldByKey("mpCurve")},
    ];
    body.push(detailSection({title:"HP / MP",attrs:{"data-concept":"character-resources"},body:conceptTable(resources,
      "64px repeat(3,minmax(58px,.55fr)) minmax(125px,1.2fr)",[
        {key:"resource",label:"Resource",render:e=>e.name},
        {key:"current",label:"Current",render:e=>semanticControl(row,e.current)},
        {key:"base",label:"Base",render:e=>semanticControl(row,e.base)},
        {key:"maximum",label:"Maximum",render:e=>semanticControl(row,e.maximum)},
        {key:"curve",label:"Growth curve",render:e=>semanticControl(row,e.curve)},
      ],"Character HP and MP initialization")}));

    body.push(detailSection({title:"STARTING LIMIT STATE",attrs:{"data-concept":"character-limit-state"},body:settingsTable([
      "limitLevel","limitBar","killCount","limit1Uses","limit2Uses","limit3Uses"
    ],"Starting Limit state")}));
    body.push(detailSection({title:"LIMITS ALREADY LEARNED",body:el("div",{style:"padding:10px;min-width:0"},semanticControl(row,fieldByKey("learnedLimits")))}));

    const learning=[
      {key:"12",milestone:"Learn Limit 1-2",metric:"Limit 1-1 uses",field:fieldByKey("usesForLimit12")},
      {key:"2",milestone:"Unlock Limit level 2",metric:"Enemy kills",field:fieldByKey("killsForLimit2")},
      {key:"22",milestone:"Learn Limit 2-2",metric:"Limit 2-1 uses",field:fieldByKey("usesForLimit22")},
      {key:"3",milestone:"Unlock Limit level 3",metric:"Enemy kills",field:fieldByKey("killsForLimit3")},
      {key:"32",milestone:"Learn Limit 3-2",metric:"Limit 3-1 uses",field:fieldByKey("usesForLimit32")},
    ];
    body.push(detailSection({title:"LIMIT LEARNING",attrs:{"data-concept":"character-limit-learning"},body:conceptTable(learning,
      "minmax(145px,1.2fr) minmax(110px,.8fr) minmax(85px,.65fr)",[
        {key:"milestone",label:"Milestone",render:e=>e.milestone},
        {key:"metric",label:"Requirement",render:e=>e.metric},
        {key:"amount",label:"Amount",render:e=>semanticControl(row,e.field)},
      ],"Limit learning requirements")}));

    const limits=[
      {key:1,level:"Level 1",first:fieldByKey("limitAttack11"),second:fieldByKey("limitAttack12"),divisor:fieldByKey("limitHpDivisor1")},
      {key:2,level:"Level 2",first:fieldByKey("limitAttack21"),second:fieldByKey("limitAttack22"),divisor:fieldByKey("limitHpDivisor2")},
      {key:3,level:"Level 3",first:fieldByKey("limitAttack31"),second:fieldByKey("limitAttack32"),divisor:fieldByKey("limitHpDivisor3")},
      {key:4,level:"Level 4",first:fieldByKey("limitAttack4"),second:null,divisor:fieldByKey("limitHpDivisor4")},
    ];
    body.push(detailSection({title:"LIMIT ATTACKS",attrs:{"data-concept":"character-limit-attacks"},body:conceptTable(limits,
      "70px minmax(125px,1.2fr) minmax(125px,1.2fr) minmax(78px,.65fr)",[
        {key:"level",label:"Level",render:e=>e.level},
        {key:"first",label:"Attack 1",render:e=>semanticControl(row,e.first)},
        {key:"second",label:"Attack 2",render:e=>e.second?semanticControl(row,e.second):"—"},
        {key:"divisor",label:"HP divisor",render:e=>semanticControl(row,e.divisor)},
      ],"Character Limit attacks and gauge divisors")}));

    for(const equipment of ["weapon","armor"]){
      const entries=Array.from({length:8},(_,i)=>({key:i+1,materia:fieldByKey(`${equipment}Materia${i}`),ap:fieldByKey(`${equipment}MateriaAp${i}`)}));
      body.push(detailSection({title:`STARTING ${equipment.toUpperCase()} MATERIA`,attrs:{"data-concept":`${equipment}-materia`},body:conceptTable(entries,
        "44px minmax(150px,1.3fr) minmax(90px,.7fr)",[
          {key:"slot",label:"Slot",numberedId:true,render:e=>e.key},
          {key:"materia",label:"Materia",render:e=>semanticControl(row,e.materia)},
          {key:"ap",label:"AP",render:e=>semanticControl(row,e.ap)},
        ],`${equipment} starting Materia`)}));
    }
    return conceptPanel(row,body);
  }
  function enemyDetail(row){
    const omit=new Set();for(let i=0;i<8;i++){omit.add(`element${i}`);omit.add(`rate${i}`)}for(let i=0;i<16;i++){omit.add(`attack${i}`);omit.add(`animation${i}`);omit.add(`camera${i}`)}for(let i=0;i<4;i++){omit.add(`item${i}`);omit.add(`dropRate${i}`)}for(let i=0;i<3;i++)omit.add(`manipulate${i}`);const body=ordinarySections(row,omit);
    const resist=Array.from({length:8},(_,i)=>({key:i+1,target:fieldByKey(`element${i}`),response:fieldByKey(`rate${i}`)}));body.push(detailSection({title:"RESISTANCES",attrs:{"data-concept":"enemy-resistances"},body:conceptTable(resist,"44px minmax(140px,1fr) minmax(120px,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"target",label:"Element / status",render:e=>semanticControl(row,e.target)},{key:"response",label:"Response",render:e=>semanticControl(row,e.response)}],"Enemy resistances")}));
    const actions=Array.from({length:16},(_,i)=>({key:i+1,attack:fieldByKey(`attack${i}`),animation:fieldByKey(`animation${i}`),camera:fieldByKey(`camera${i}`)}));body.push(detailSection({title:"ACTIONS",attrs:{"data-concept":"enemy-actions"},body:conceptTable(actions,"44px minmax(150px,1.3fr) minmax(90px,.7fr) minmax(90px,.7fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"attack",label:"Attack",render:e=>semanticControl(row,e.attack)},{key:"animation",label:"Animation",render:e=>semanticControl(row,e.animation)},{key:"camera",label:"Camera",render:e=>semanticControl(row,e.camera)}],"Enemy action slots")}));
    const loot=Array.from({length:4},(_,i)=>({key:i+1,item:fieldByKey(`item${i}`),rate:fieldByKey(`dropRate${i}`)}));body.push(detailSection({title:"LOOT",attrs:{"data-concept":"enemy-loot"},body:conceptTable(loot,"44px minmax(150px,1.2fr) minmax(150px,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"item",label:"Item",render:e=>semanticControl(row,e.item)},{key:"rate",label:"Method / chance",render:e=>semanticControl(row,e.rate)}],"Enemy drop and steal slots")}));
    const manipulate=Array.from({length:3},(_,i)=>({key:i+1,attack:fieldByKey(`manipulate${i}`)}));body.push(detailSection({title:"MANIPULATE / BERSERK",attrs:{"data-concept":"enemy-manipulate"},body:conceptTable(manipulate,"44px minmax(160px,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"attack",label:"Attack",render:e=>semanticControl(row,e.attack)}],"Enemy manipulate actions")}));return conceptPanel(row,body)
  }
  function formationDetail(row){
    const omit=new Set();for(let i=0;i<6;i++)for(const suffix of ["enemy","x","y","z","row","cover","flags"])omit.add(`slot${i}_${suffix}`);for(let i=0;i<3;i++)for(const axis of ["x","y","z","directionX","directionY","directionZ"])omit.add(`camera${i}_${axis}`);for(let i=0;i<4;i++)omit.add(`arena${i}`);const body=[];
    const slots=Array.from({length:6},(_,i)=>({key:i+1,enemy:fieldByKey(`slot${i}_enemy`),x:fieldByKey(`slot${i}_x`),y:fieldByKey(`slot${i}_y`),z:fieldByKey(`slot${i}_z`),row:fieldByKey(`slot${i}_row`),cover:fieldByKey(`slot${i}_cover`),flags:fieldByKey(`slot${i}_flags`)}));
    body.push(detailSection({title:"ENEMY SLOTS",attrs:{"data-concept":"formation-slots"},body:conceptTable(slots,"36px minmax(0,1fr) 68px",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"enemy",label:"Enemy",render:e=>semanticControl(row,e.enemy)},{key:"row",label:"Row",render:e=>semanticControl(row,e.row)}],"Formation enemy slots")}));
    body.push(detailSection({title:"ENEMY POSITIONS",attrs:{"data-concept":"formation-positions"},body:conceptTable(slots,"36px repeat(3,minmax(0,1fr))",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"x",label:"X",render:e=>semanticControl(row,e.x)},{key:"y",label:"Y",render:e=>semanticControl(row,e.y)},{key:"z",label:"Z",render:e=>semanticControl(row,e.z)}],"Formation enemy positions")}));
    body.push(detailSection({title:"SLOT FLAGS",attrs:{"data-concept":"formation-flags"},body:conceptTable(slots,"36px repeat(2,minmax(0,1fr))",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"cover",label:"Cover",render:e=>semanticControl(row,e.cover)},{key:"flags",label:"Initial flags",render:e=>semanticControl(row,e.flags)}],"Formation enemy slot flags")}));
    const cameras=Array.from({length:3},(_,i)=>({key:i+1,...Object.fromEntries(["x","y","z","directionX","directionY","directionZ"].map(axis=>[axis,fieldByKey(`camera${i}_${axis}`)]))}));
    body.push(detailSection({title:"CAMERA POSITIONS",attrs:{"data-concept":"formation-cameras"},body:conceptTable(cameras,"36px repeat(3,minmax(0,1fr))",[{key:"camera",label:"#",numberedId:true,render:e=>e.key},...['x','y','z'].map(axis=>({key:axis,label:axis.toUpperCase(),render:e=>semanticControl(row,e[axis])}))],"Formation camera positions")}));
    body.push(detailSection({title:"CAMERA DIRECTIONS",attrs:{"data-concept":"formation-camera-directions"},body:conceptTable(cameras,"36px repeat(3,minmax(0,1fr))",[{key:"camera",label:"#",numberedId:true,render:e=>e.key},...['directionX','directionY','directionZ'].map(axis=>({key:axis,label:`Dir ${axis.slice(9)}`,render:e=>semanticControl(row,e[axis])}))],"Formation camera directions")}));
    const arenas=Array.from({length:4},(_,i)=>({key:i+1,field:fieldByKey(`arena${i}`)}));body.push(detailSection({title:"ARENA CANDIDATES",attrs:{"data-concept":"formation-arenas"},body:conceptTable(arenas,"36px minmax(0,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"arena",label:"Arena ID",render:e=>semanticControl(row,e.field)}],"Formation arena candidates")}));
    body.push(...ordinarySections(row,omit));return conceptPanel(row,body)
  }
  function shopDetail(row){const omit=new Set();for(let i=0;i<10;i++){omit.add(`type${i}`);omit.add(`item${i}`)}const body=[],entries=Array.from({length:10},(_,i)=>({key:i+1,index:i,kind:fieldByKey(`type${i}`),product:fieldByKey(`item${i}`)}));body.push(detailSection({title:"INVENTORY",attrs:{"data-concept":"shop-inventory"},body:conceptTable(entries,"36px 48px minmax(68px,.65fr) minmax(0,1.35fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"active",label:"Active",render:e=>e.index<Number(row.values.count)?"Yes":"No"},{key:"kind",label:"Kind",render:e=>semanticControl(row,{...e.kind,rerenderOnChange:true})},{key:"product",label:"Product",render:e=>semanticControl(row,e.product)}],"Shop inventory slots")}));body.push(...ordinarySections(row,omit));return conceptPanel(row,body)}
  function weightedEncounterDetail(row){const count=state.tab==="worldEncounters"?14:10,omit=new Set();for(let i=0;i<count;i++){omit.add(`battle${i}`);omit.add(`chance${i}`)}const body=ordinarySections(row,omit),entries=Array.from({length:count},(_,i)=>({key:i+1,battle:fieldByKey(`battle${i}`),chance:fieldByKey(`chance${i}`)}));body.push(detailSection({title:"WEIGHTED ENCOUNTERS",attrs:{"data-concept":"weighted-encounters"},body:conceptTable(entries,"44px minmax(160px,1.4fr) minmax(90px,.7fr) 72px",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"battle",label:"Battle",render:e=>semanticControl(row,e.battle)},{key:"weight",label:"Weight / 64",render:e=>semanticControl(row,e.chance)},{key:"percent",label:"Share",render:e=>`${Math.round(Number(row.values[e.chance.key])*1000/64)/10}%`}],"Weighted encounter table")}));return conceptPanel(row,body)}
  function materiaDetail(row){
    const apKeys=["level2Ap","level3Ap","level4Ap","level5Ap"],body=ordinarySections(row,new Set(apKeys)),entries=apKeys.map((key,index)=>({key:index+2,level:index+2,field:fieldByKey(key)}));
    const progression=detailSection({title:"LEVEL PROGRESSION",attrs:{"data-concept":"materia-level-progression"},help:infoHelp("AP thresholds are cumulative. The final column shows the additional AP required after the preceding level threshold."),body:conceptTable(entries,"62px minmax(110px,1fr) minmax(110px,.8fr)",[
      {key:"level",label:"Level",render:entry=>entry.level},
      {key:"total",label:"Total AP",render:entry=>semanticControl(row,{...entry.field,rerenderOnChange:true})},
      {key:"increment",label:"From prior",render:entry=>{const previous=entry.level===2?0:Number(row.values[`level${entry.level-1}Ap`]);return Number(row.values[entry.field.key])-previous}},
    ],"Materia AP level progression")});
    body.splice(category().descriptionEditable?1:0,0,progression);return conceptPanel(row,body);
  }
  function aiEventFields(){return category().fields.filter(field=>/^script\d+$/.test(field.key)).sort((a,b)=>Number(a.key.slice(6))-Number(b.key.slice(6)))}
  function aiUsedCount(row){return aiEventFields().filter(field=>String(row.values[field.key]||"").trim()).length}
  function aiDetail(row){
    const fields=aiEventFields(),eventKey=`${state.tab}/${row.id}`;let selected=Number(state.aiEvent[eventKey]);
    if(!Number.isInteger(selected)||selected<0||selected>=fields.length){const firstUsed=fields.findIndex(field=>String(row.values[field.key]||"").trim());selected=firstUsed>=0?firstUsed:0;state.aiEvent[eventKey]=selected}
    const selector=el("select",{"aria-label":`AI event for ${row.name}`,disabled:readonly(),onchange:event=>{state.aiEvent[eventKey]=Number(event.target.value);render()}},...fields.map((field,index)=>{const source=String(row.values[field.key]||""),lines=source.trim()?source.split(/\r?\n/).filter(line=>line.trim()).length:0;return el("option",{value:index},`${field.label} — ${lines?`${lines} line${lines===1?"":"s"}`:"Empty"}`)}));selector.value=String(selected);
    const field=fields[selected],editor=semanticControl(row,field),used=aiUsedCount(row);editor.style.width="100%";editor.style.fontFamily="ui-monospace, SFMono-Regular, Consolas, monospace";editor.style.lineHeight="1.35";editor.rows=12;
    const eventHelp=field.help||"Edit this FF7 battle-AI event as FF7 game-VM assembly. Invalid opcodes, bad jumps, and missing END instructions are rejected on save.";
    const toolbar=el("div",{style:"display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:8px 10px;align-items:center;padding:10px 10px 8px;min-width:0"},
      el("strong",{style:"font-size:.78rem;letter-spacing:.06em"},"EVENT"),selector,
      el("strong",{style:"font-size:.78rem;letter-spacing:.06em"},"EVENTS"),el("span",{style:"white-space:nowrap"},`${used} / ${fields.length} used`));
    return conceptPanel(row,[detailSection({title:"BATTLE AI",attrs:{"data-concept":"ai-event-editor"},help:infoHelp("Choose one of FF7's sixteen battle-AI event hooks. Empty events are valid and can be filled here; saving an empty event removes that script. "+eventHelp),body:el("div",{style:"min-width:0"},toolbar,el("div",{style:"padding:0 10px 10px;min-width:0"},editor))})]);
  }
  function settingsConcept(row,entries,label){
    const rows=entries.map(([key,name],index)=>({key:index,field:fieldByKey(key),name})).filter(entry=>entry.field);
    return conceptTable(rows,"minmax(135px,.9fr) minmax(165px,1.25fr)",[
      {key:"setting",label:"Setting",render:entry=>entry.name||entry.field.label},
      {key:"value",label:"Value",render:entry=>semanticControl(row,entry.field)},
    ],label);
  }
  function newGameStateDetail(row){
    const party=[["party1","Slot 1"],["party2","Slot 2"],["party3","Slot 3"]].map(([key,name],index)=>({key:index+1,name,field:fieldByKey(key)}));
    return conceptPanel(row,[
      detailSection({title:"STARTING PARTY",attrs:{"data-concept":"new-game-setup"},help:infoHelp("These character identities are copied into a newly initialized save.  Existing saves are not rewritten."),body:conceptTable(party,"70px minmax(180px,1fr)",[
        {key:"slot",label:"Slot",render:entry=>entry.name},
        {key:"character",label:"Character",render:entry=>semanticControl(row,entry.field)},
      ],"New-game party")}),
      detailSection({title:"STARTING RESOURCES",body:settingsConcept(row,[["gil","Gil"]],"New-game resources")}),
    ]);
  }
  function attackDetail(row){
    const enemy=state.tab==="enemyAttacks";
    const keys=enemy?{
      name:"name",accuracy:"accuracy",cost:"cost",formula:"formula",power:"power",target:"target",condition:"condition",status:"statusChance",statuses:"statuses",elements:"elements",additional:"additionalEffect",modifier:"modifier",special:"specialFlags"
    }:{
      accuracy:"accuracyRate",cost:"mpCost",formula:"damageCalculationId",power:"attackPower",target:"targetData",condition:"conditionSubmenu",status:"statusChange",statuses:"statusFlags",elements:"elementFlags",additional:"additionalEffects",modifier:"additionalEffectsModifier",special:"specialAttackFlags"
    };
    const omit=new Set(Object.values(keys));
    const body=[];
    if(keys.name&&fieldByKey(keys.name))body.push(detailSection({title:"ATTACK NAME",attrs:{"data-concept":"attack-name"},body:el("div",{style:"padding:10px;min-width:0"},semanticControl(row,fieldByKey(keys.name)))}));
    body.push(detailSection({title:"COST & DAMAGE",attrs:{"data-concept":"attack-core"},body:settingsConcept(row,[
      [keys.accuracy,"Accuracy"],[keys.cost,"MP cost"],[keys.formula,"Damage / healing formula"],[keys.power,"Power"],
    ],"Attack cost and damage")}));
    body.push(detailSection({title:"TARGETING & STATUS",attrs:{"data-concept":"attack-effects"},body:settingsConcept(row,[
      [keys.target,"Targeting"],[keys.condition,"Condition"],[keys.status,"Status change"],[keys.statuses,"Statuses affected"],[keys.elements,"Elements"],
    ],"Attack targeting and status")}));
    body.push(detailSection({title:"EXTRA BEHAVIOR",body:settingsConcept(row,[
      [keys.additional,"Additional behavior"],[keys.modifier,"Effect modifier"],[keys.special,"Special properties"],
    ],"Attack extra behavior")}));
    body.push(...ordinarySections(row,omit));
    return conceptPanel(row,body);
  }
  function materiaEquipEffectDetail(row){
    const stats=[["strength","Strength"],["vitality","Vitality"],["magic","Magic"],["spirit","Spirit"],["dexterity","Dexterity"],["luck","Luck"]].map(([key,name],index)=>({key:index,name,field:fieldByKey(key)}));
    const resources=[["hpPercent","HP"],["mpPercent","MP"]].map(([key,name],index)=>({key:index,name,field:fieldByKey(key)}));
    return conceptPanel(row,[
      detailSection({title:"STAT CHANGES",attrs:{"data-concept":"materia-equip-effect"},help:infoHelp("This shared template is selected by Materia equip-effect IDs. Values are the stat changes applied while that Materia is equipped."),body:conceptTable(stats,"minmax(120px,.9fr) minmax(120px,1fr)",[
        {key:"stat",label:"Stat",render:entry=>entry.name},{key:"change",label:"Change",render:entry=>semanticControl(row,entry.field)},
      ],"Materia equip-effect stat changes")}),
      detailSection({title:"HP / MP",body:conceptTable(resources,"minmax(120px,.9fr) minmax(120px,1fr)",[
        {key:"resource",label:"Resource",render:entry=>entry.name},{key:"change",label:"Percent change",render:entry=>semanticControl(row,entry.field)},
      ],"Materia equip-effect HP and MP changes")}),
    ]);
  }
  function recruitDetail(row){
    const body=[];
    const name=fieldByKey("name");if(name)body.push(detailSection({title:"INITIAL NAME",attrs:{"data-concept":"recruit-name"},body:el("div",{style:"padding:10px;min-width:0"},semanticControl(row,name))}));
    body.push(detailSection({title:"STARTING CHARACTER",attrs:{"data-concept":"recruit-loadout"},body:settingsConcept(row,[
      ["storedId","Character identity"],["weaponId","Weapon"],["armorId","Armor"],["accessoryId","Accessory"],["rowByte","Row"],["characterFlags","Battle mood"],
    ],"Recruit starting loadout")}));
    body.push(detailSection({title:"PROGRESSION",body:settingsConcept(row,[["level","Level"],["currentExp","Experience"],["expToNextLevel","EXP to next level"],["levelProgress","Level progress"]],"Recruit progression")}));
    const stats=["strength","vitality","magic","spirit","dexterity","luck"].map((key,index)=>({key:index,name:key[0].toUpperCase()+key.slice(1),value:fieldByKey(key),bonus:fieldByKey(`${key}Bonus`)}));
    body.push(detailSection({title:"CORE STATS",attrs:{"data-concept":"recruit-stats"},body:conceptTable(stats,"minmax(90px,.8fr) minmax(85px,.7fr) minmax(85px,.7fr)",[
      {key:"stat",label:"Stat",render:entry=>entry.name},{key:"start",label:"Start",render:entry=>semanticControl(row,entry.value)},{key:"bonus",label:"Bonus",render:entry=>semanticControl(row,entry.bonus)},
    ],"Recruit core stats")}));
    const resources=[
      {key:"hp",name:"HP",current:fieldByKey("currentHp"),base:fieldByKey("baseHp"),maximum:fieldByKey("maxHp")},
      {key:"mp",name:"MP",current:fieldByKey("currentMp"),base:fieldByKey("baseMp"),maximum:fieldByKey("maxMp")},
    ];
    body.push(detailSection({title:"HP / MP",body:conceptTable(resources,"64px repeat(3,minmax(70px,.8fr))",[
      {key:"resource",label:"Resource",render:entry=>entry.name},{key:"current",label:"Current",render:entry=>semanticControl(row,entry.current)},{key:"base",label:"Base",render:entry=>semanticControl(row,entry.base)},{key:"maximum",label:"Maximum",render:entry=>semanticControl(row,entry.maximum)},
    ],"Recruit HP and MP")}));
    body.push(detailSection({title:"STARTING LIMIT STATE",body:settingsConcept(row,[["limitLevel","Limit level"],["limitBar","Limit gauge"],["learnedLimits","Limits learned"],["killCount","Kill count"],["limit1Uses","Level 1 uses"],["limit2Uses","Level 2 uses"],["limit3Uses","Level 3 uses"]],"Recruit Limit state")}));
    for(const equipment of ["weapon","armor"]){
      const entries=Array.from({length:8},(_,i)=>({key:i+1,materia:fieldByKey(`${equipment}Materia${i}`),ap:fieldByKey(`${equipment}MateriaAp${i}`)}));
      body.push(detailSection({title:`STARTING ${equipment.toUpperCase()} MATERIA`,attrs:{"data-concept":`recruit-${equipment}-materia`},body:conceptTable(entries,"44px minmax(150px,1.3fr) minmax(90px,.7fr)",[
        {key:"slot",label:"Slot",numberedId:true,render:entry=>entry.key},{key:"materia",label:"Materia",render:entry=>semanticControl(row,entry.materia)},{key:"ap",label:"AP",render:entry=>semanticControl(row,entry.ap)},
      ],`Recruit ${equipment} Materia`)}));
    }
    return conceptPanel(row,body);
  }
  function textRecordDetail(row){
    const field=fieldByKey("text"),control=semanticControl(row,field),area=control.matches?.("textarea")?control:control.querySelector?.("textarea");
    control.style.width="100%";if(area){area.rows=10;area.style.width="100%";area.style.minHeight="12rem"}
    const isKernel=state.tab==="texts",section=isKernel?Math.floor(Number(row.id)/65536):null,index=isKernel?(Number(row.id)&0xFFFF):Number(row.id),chars=String(row.values.text||"").length;
    return conceptPanel(row,[
      detailSection({title:"GAME TEXT",attrs:{"data-concept":"text-editor"},help:(semanticHelp(field)?infoHelp(semanticHelp(field)):null),body:el("div",{style:"padding:10px;min-width:0"},control)}),
      detailSection({title:"RECORD",body:[
        detailField({label:isKernel?"SECTION / ENTRY":"EXECUTABLE ENTRY",control:readonlyField(isKernel?`${section} / ${index}`:String(index))}),
        detailField({label:"CHARACTERS",control:readonlyField(String(chars))}),
        detailField({label:"STORAGE",control:readonlyField(row.description||"Bounded FF7 text storage; oversized edits are rejected on save.")}),
      ]}),
    ]);
  }
  function recordDetail(row){
    if(state.tab==="growthCurves")return growthCurveDetail(row);
    if(state.tab==="growthBonuses")return growthBonusDetail(row);
    if(state.tab==="materia")return materiaDetail(row);
    if(state.tab==="materiaEquipEffects")return materiaEquipEffectDetail(row);
    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return aiDetail(row);
    if(state.tab==="characters")return characterDetail(row);
    if(state.tab==="recruits")return recruitDetail(row);
    if(state.tab==="initialState")return newGameStateDetail(row);
    if(["playerAttacks","limitBreaks","enemyAttacks"].includes(state.tab))return attackDetail(row);
    if(["weapons","armor","accessories"].includes(state.tab))return equipmentDetail(row);
    if(state.tab==="enemies")return enemyDetail(row);
    if(state.tab==="encounters")return formationDetail(row);
    if(state.tab==="shops")return shopDetail(row);
    if(["fieldEncounters","worldEncounters"].includes(state.tab))return weightedEncounterDetail(row);
    if(["texts","exeText"].includes(state.tab))return textRecordDetail(row);
    return conceptPanel(row,ordinarySections(row));
  }
  const MASTER_SUMMARY_FIELDS={
    characters:[["level","LV"],["maxHp","HP"],["maxMp","MP"]],
    recruits:[["level","LV"],["maxHp","HP"],["maxMp","MP"]],
    commands:[["initialCursorAction","ACTION"]],
    playerAttacks:[["mpCost","MP"],["attackPower","PWR"],["damageCalculationId","CALC"]],
    limitBreaks:[["mpCost","MP"],["attackPower","PWR"],["damageCalculationId","CALC"]],
    items:[["attackPower","PWR"],["damageCalculationId","CALC"]],
    weapons:[["attackStrength","ATK"],["accuracyRate","HIT"],["growthRate","AP"]],
    armor:[["defense","DEF"],["magicDefense","M.DEF"],["growthRate","AP"]],
    accessories:[["specialEffect","FX"]],
    materia:[["level5Ap","M.AP"],["materiaType","TYPE"]],
    materiaEquipEffects:[["hpPercent","HP%"],["mpPercent","MP%"]],
    enemies:[["level","LV"],["hp","HP"],["experience","EXP"]],
    enemyAttacks:[["cost","MP"],["power","PWR"],["formula","CALC"]],
    shops:[["type","TYPE"],["count","SLOTS"]],
    prices:[["price","PRICE"]],
    initialState:[["gil","GIL"]],
    initialInventory:[["amount","QTY"]],
    initialMateria:[["ap","AP"]],
    stolenMateria:[["ap","AP"]],
    magicOrder:[["menuGroup","MENU"],["position","POS"]],
    itemSortOrder:[["position","SORT"]],
    materiaPriority:[["priority","ORDER"]],
    audioMixing:[["volume","VOL"],["pan","PAN"]],
    apMultiplier:[["multiplier","RATE"]],
  };
  function globalInventoryRecord(value,priceTable=false){
    const id=Number(value),specs=priceTable?[["items",0,128],["weapons",128,128],["armor",256,32],["accessories",288,32],["materia",384,96]]:[["items",0,128],["weapons",128,128],["armor",256,32],["accessories",288,32]];
    for(const [group,start,count] of specs)if(id>=start&&id<start+count){const record=rowById(group,id-start);if(record)return{group,record}}
    return null;
  }
  const CHARACTER_AI_NAMES=["Cloud","Barret","Tifa","Aerith","Red XIII","Yuffie","Cait Sith","Vincent","Cid","Young Cloud","Sephiroth","Unknown owner"];
  function displayRowName(row){
    if(state.tab==="prices"){
      const hit=globalInventoryRecord(row.id,true);if(hit)return`${candidateLabel(hit.record)} — ${labels[hit.group]||hit.group}`;
    }
    if(state.tab==="itemSortOrder"){
      const hit=globalInventoryRecord(row.id,false);if(hit)return`${candidateLabel(hit.record)} — ${labels[hit.group]||hit.group}`;
    }
    if(state.tab==="materiaPriority"){
      const record=rowById("materia",row.id);if(record)return candidateLabel(record);
    }
    if(state.tab==="initialInventory"){
      const value=Number(row.values.item);if(value===0x1FF)return`Slot ${row.id+1} — Empty`;
      const hit=globalInventoryRecord(value,false);return`Slot ${row.id+1} — ${hit?candidateLabel(hit.record):`Unknown item ${value}`}`;
    }
    if(state.tab==="initialMateria"||state.tab==="stolenMateria"){
      const value=Number(row.values.materia),record=value===0xFF?null:rowById("materia",value);
      return`Slot ${row.id+1} — ${value===0xFF?"Empty":record?candidateLabel(record):`Unknown Materia ${value}`}`;
    }
    if(state.tab==="magicOrder"){
      const record=rowById("playerAttacks",row.id);if(record)return candidateLabel(record);
    }
    if(state.tab==="characterAI")return`${CHARACTER_AI_NAMES[row.id]||`Owner ${row.id}`} AI`;
    if(state.tab==="enemyAI"){const scene=Math.floor(Number(row.id)/3),slot=Number(row.id)%3,enemy=(state.records.enemies||[]).find(candidate=>Number(candidate.id)===scene*3+slot);return enemy?`${candidateLabel(enemy)} — Scene ${scene}`:`Unused enemy slot ${slot+1} — Scene ${scene}`}
    if(state.tab==="formationAI"){const formation=rowById("encounters",row.id);return formation?`${candidateLabel(formation)} AI`:`Battle ${row.id} AI`}
    return String(row.values?.name||row.name||`Record ${row.id}`);
  }
