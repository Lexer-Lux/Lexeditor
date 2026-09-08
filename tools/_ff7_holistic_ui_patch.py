from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def replace_once(path,old,new,label):
    text=path.read_text(encoding='utf-8')
    if new in text:return
    if old not in text:raise SystemExit(f'{label}: insertion point changed')
    path.write_text(text.replace(old,new,1),encoding='utf-8')

path=ROOT/'games/ff7/editor.html'
replace_once(path,
'''  const integrated=["accessories","armor","characters","commands","playerAttacks","items","materia","weapons","enemies","encounters","enemyAttacks","shops","prices","texts","characterNames","growthCurves","growthBonuses","characterAI","enemyAI","formationAI","recruits","defaultNames","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"];
  const unresolved=["tweaks"];
  const labels={accessories:"Accessories",armor:"Armor",characters:"Characters",commands:"Commands",playerAttacks:"Player attacks",items:"Items",materia:"Materia",weapons:"Weapons",enemies:"Enemies",encounters:"Encounters",shops:"Shops",prices:"Prices",texts:"Text",enemyAttacks:"Enemy attacks",tweaks:"Tweaks",characterNames:"Initial names",growthCurves:"Growth curves",growthBonuses:"Growth bonuses",characterAI:"Character AI",enemyAI:"Enemy AI",formationAI:"Formation AI",recruits:"Recruits",defaultNames:"Default names",fieldEncounters:"Field encounters",worldEncounters:"World encounters",yuffieEncounters:"Yuffie encounters",chocoboRatings:"Chocobo ratings"};
  const groups={characters:["characters","characterNames","growthCurves","growthBonuses","characterAI","recruits","defaultNames"],commands:["commands","playerAttacks"],enemies:["enemies","enemyAttacks","enemyAI"],encounters:["encounters","formationAI","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"],shops:["shops","prices"]};''',
'''  const integrated=["accessories","armor","characters","initialState","initialInventory","initialMateria","stolenMateria","commands","playerAttacks","magicOrder","items","materia","weapons","enemies","encounters","enemyAttacks","shops","prices","texts","characterNames","growthCurves","growthBonuses","characterAI","enemyAI","formationAI","recruits","defaultNames","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"];
  const unresolved=["tweaks"];
  const labels={accessories:"Accessories",armor:"Armor",characters:"Characters",initialState:"New game",initialInventory:"Starting inventory",initialMateria:"Starting Materia",stolenMateria:"Yuffie stolen Materia",commands:"Commands",playerAttacks:"Player attacks",magicOrder:"Magic menu",items:"Items",materia:"Materia",weapons:"Weapons",enemies:"Enemies",encounters:"Encounters",shops:"Shops",prices:"Prices",texts:"Text",enemyAttacks:"Enemy attacks",tweaks:"Tweaks",characterNames:"Initial names",growthCurves:"Growth curves",growthBonuses:"Growth bonuses",characterAI:"Character AI",enemyAI:"Enemy AI",formationAI:"Formation AI",recruits:"Recruits",defaultNames:"Default names",fieldEncounters:"Field encounters",worldEncounters:"World encounters",yuffieEncounters:"Yuffie encounters",chocoboRatings:"Chocobo ratings"};
  const groups={characters:["characters","characterNames","growthCurves","growthBonuses","characterAI","recruits","defaultNames"],initialState:["initialState","initialInventory","initialMateria","stolenMateria"],commands:["commands","playerAttacks","magicOrder"],enemies:["enemies","enemyAttacks","enemyAI"],encounters:["encounters","formationAI","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"],shops:["shops","prices"]};''',
'navigation categories')

replace_once(path,
'''  function inventoryReferenceControl(row,field){return selectControl(row,field,()=>inventoryChoices(true))}''',
'''  function inventoryReferenceControl(row,field){return selectControl(row,field,()=>inventoryChoices(field.includeMateria!==false))}''',
'inventory reference scope')

# Allow concept views whose preview/linked selector depends on a scalar/enum to repaint immediately.
replace_once(path,
'''        else{delete state.invalid[key];row.values[field.key]=value}
        shellRefresh();''',
'''        else{delete state.invalid[key];row.values[field.key]=value}
        field.rerenderOnChange?render():shellRefresh();''',
'number rerender')
replace_once(path,
'''      if(readonly())return;row.values[field.key]=Number(event.target.value);shellRefresh();
    }},...choices.map(choice=>el("option",{value:choice.value},choice.label)));''',
'''      if(readonly())return;row.values[field.key]=Number(event.target.value);field.rerenderOnChange?render():shellRefresh();
    }},...choices.map(choice=>el("option",{value:choice.value},choice.label)));''',
'enum rerender')

# Drop/steal is one packed byte in scene.bin; present its actual game meaning.
replace_once(path,
'''  function semanticControl(row,field){
    if(field.dataType==="text")return textControl(row,field);''',
'''  function lootRateDecoded(value){const raw=Number(value)&0xFF;return{mode:raw>=0x80?"steal":"drop",amount:raw&0x7F}}
  function lootRateSummary(value){const data=lootRateDecoded(value),percent=Math.round(data.amount*1000/63)/10;return`${data.mode==="steal"?"Steal":"Drop"} — ${data.amount}/63 (${percent}%)`}
  function lootRateControl(row,field){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]),initial=lootRateDecoded(row.values[field.key]);
    const mode=el("select",{"aria-label":`${field.label} method for ${row.name}`,disabled:readonly()},el("option",{value:"drop"},"Drop"),el("option",{value:"steal"},"Steal"));
    const amount=el("input",{type:"number",min:0,max:127,step:1,"aria-label":`${field.label} chance for ${row.name}`,disabled:readonly(),value:initial.amount});mode.value=initial.mode;
    const root=el("div",{class:"lex-semantic-compound"},mode,amount);
    const update=()=>{if(readonly())return;const n=Math.max(0,Math.min(127,Number(amount.value)||0));row.values[field.key]=(mode.value==="steal"?0x80:0)|n;shellRefresh()};
    mode.addEventListener("change",update);amount.addEventListener("input",update);
    return provenanceControl({control:root,current:()=>Number(row.values[field.key]),vanilla,internal:true,format:lootRateSummary,apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function semanticControl(row,field){
    if(field.dataType==="text")return textControl(row,field);''',
'loot rate control')
replace_once(path,
'''    if(field.dataType==="statusChange")return statusChangeControl(row,field);
    return numberControl(row,field);''',
'''    if(field.dataType==="statusChange")return statusChangeControl(row,field);
    if(field.dataType==="lootRate")return lootRateControl(row,field);
    return numberControl(row,field);''',
'loot rate dispatch')
replace_once(path,
'''    return {text:"TEXT",enum:"SELECT",flags:"FLAGS",reference:"REF",inventoryReference:"REF",shopReference:"REF",boolean:"BOOL",scaled:"VALUE",statusChange:"STATUS"}[field.dataType]||"INT";''',
'''    return {text:"TEXT",enum:"SELECT",flags:"FLAGS",reference:"REF",inventoryReference:"REF",shopReference:"REF",boolean:"BOOL",scaled:"VALUE",statusChange:"STATUS",lootRate:"LOOT"}[field.dataType]||"INT";''',
'loot rate type')

old='''  function recordDetail(row){
    const metadata=category(),groups=[...new Set(metadata.fields.map(field=>field.group||"Kernel data"))];
    const body=[];
    if(metadata.descriptionEditable)body.push(detailSection({title:"TEXT",body:detailField({label:"DESCRIPTION",help:infoHelp("The in-game description stored in this FF7 KERNEL.BIN. Byte escapes are preserved for game control codes."),control:descriptionControl(row),dataType:"TEXT"})}));
    body.push(...groups.map(group=>detailSection({title:group.toUpperCase(),body:metadata.fields.filter(field=>(field.group||"Kernel data")===group).map(field=>{const help=semanticHelp(field);return detailField({className:"ff7-field",label:field.label,help:help?infoHelp(help):null,control:semanticControl(row,field),dataType:semanticType(field),min:field.minimum,max:field.maximum})})})));
    return detailPanel({className:"ff7-detail",title:row.values.name||row.name,identity:recordId(row.id),meta:null,body});
  }
'''
new='''  const CURVE_BRACKETS=["2–11","12–21","22–31","32–41","42–51","52–61","62–81","82–99"];
  function fieldByKey(key){return category().fields.find(field=>field.key===key)}
  function fieldDetail(row,field){const help=semanticHelp(field);return detailField({className:"ff7-field",label:field.label,help:help?infoHelp(help):null,control:semanticControl(row,field),dataType:semanticType(field),min:field.minimum,max:field.maximum})}
  function ordinarySections(row,omit=new Set()){
    const metadata=category(),fields=metadata.fields.filter(field=>!omit.has(field.key)),groups=[...new Set(fields.map(field=>field.group||"Kernel data"))],body=[];
    if(metadata.descriptionEditable)body.push(detailSection({title:"TEXT",body:detailField({label:"DESCRIPTION",help:infoHelp("The in-game description stored in this FF7 KERNEL.BIN. Byte escapes are preserved for game control codes."),control:descriptionControl(row),dataType:"TEXT"})}));
    body.push(...groups.map(group=>detailSection({title:group.toUpperCase(),body:fields.filter(field=>(field.group||"Kernel data")===group).map(field=>fieldDetail(row,field))})));
    return body;
  }
  function conceptTable(rows,template,columns,label){return columnList({rows,key:entry=>entry.key,class:"ff7-concept-table",editable:true,template,columns,"aria-label":label})}
  function conceptPanel(row,body){return detailPanel({className:"ff7-detail",title:row.values.name||row.name,identity:recordId(row.id),meta:null,body})}
  function growthCurveKind(row){return row.id<37?"primary":row.id<46?"hp":row.id<55?"mp":"exp"}
  function growthBracket(level){return level<12?0:level<22?1:level<32?2:level<42?3:level<52?4:level<62?5:level<82?6:7}
  function growthCurveValue(row,level){const i=growthBracket(level),gradient=Number(row.values[`gradient${i}`]),base=Number(row.values[`base${i}`]),kind=growthCurveKind(row);if(kind==="hp")return base*40+(level-1)*gradient;if(kind==="mp")return base*2+Math.floor((level-1)*gradient/10);if(kind==="exp")return Math.floor(gradient*(level-1)*(level-1)/10);return base+Math.floor(gradient*level/100)}
  function growthCurvePreview(row){const values=Array.from({length:98},(_,i)=>growthCurveValue(row,i+2)),min=Math.min(...values),max=Math.max(...values),span=Math.max(1,max-min),points=values.map((value,i)=>`${(i*100/(values.length-1)).toFixed(2)},${(32-(value-min)*30/span).toFixed(2)}`),svg=el("svg",{viewBox:"0 0 100 34",role:"img","aria-label":`${row.name} curve preview`,preserveAspectRatio:"none"},el("title",{},`${row.name}: ${min} to ${max}`),el("polyline",{points:points.join(" "),fill:"none",stroke:"currentColor","stroke-width":"1.2","vector-effect":"non-scaling-stroke"}));return el("div",{},svg,el("small",{},`Level 2–99 preview · ${min} → ${max}`))}
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
    const omit=new Set(),growth=[['Strength','strengthCurve'],['Vitality','vitalityCurve'],['Magic','magicCurve'],['Spirit','spiritCurve'],['Dexterity','dexterityCurve'],['Luck','luckCurve'],['HP','hpCurve'],['MP','mpCurve'],['Experience','experienceCurve']];
    for(const [,key] of growth)omit.add(key);for(const equipment of ["weapon","armor"])for(let i=0;i<8;i++){omit.add(`${equipment}Materia${i}`);omit.add(`${equipment}MateriaAp${i}`)}
    const body=ordinarySections(row,omit);for(const equipment of ["weapon","armor"]){const entries=Array.from({length:8},(_,i)=>({key:i+1,materia:fieldByKey(`${equipment}Materia${i}`),ap:fieldByKey(`${equipment}MateriaAp${i}`)}));body.push(detailSection({title:`STARTING ${equipment.toUpperCase()} MATERIA`,attrs:{"data-concept":`${equipment}-materia`},body:conceptTable(entries,"44px minmax(150px,1.3fr) minmax(90px,.7fr)",[{key:"slot",label:"Slot",numberedId:true,render:e=>e.key},{key:"materia",label:"Materia",render:e=>semanticControl(row,e.materia)},{key:"ap",label:"AP",render:e=>semanticControl(row,e.ap)}],`${equipment} starting Materia`)}))}
    const growthRows=growth.map(([name,key])=>({key,name,field:fieldByKey(key)}));body.push(detailSection({title:"GROWTH CURVES",attrs:{"data-concept":"character-growth-curves"},body:conceptTable(growthRows,"minmax(90px,.7fr) minmax(160px,1.3fr)",[{key:"stat",label:"Stat",render:e=>e.name},{key:"curve",label:"Curve",render:e=>semanticControl(row,e.field)}],"Character growth curve assignments")}));return conceptPanel(row,body)
  }
  function enemyDetail(row){
    const omit=new Set();for(let i=0;i<8;i++){omit.add(`element${i}`);omit.add(`rate${i}`)}for(let i=0;i<16;i++){omit.add(`attack${i}`);omit.add(`animation${i}`);omit.add(`camera${i}`)}for(let i=0;i<4;i++){omit.add(`item${i}`);omit.add(`dropRate${i}`)}for(let i=0;i<3;i++)omit.add(`manipulate${i}`);const body=ordinarySections(row,omit);
    const resist=Array.from({length:8},(_,i)=>({key:i+1,target:fieldByKey(`element${i}`),response:fieldByKey(`rate${i}`)}));body.push(detailSection({title:"RESISTANCES",attrs:{"data-concept":"enemy-resistances"},body:conceptTable(resist,"44px minmax(140px,1fr) minmax(120px,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"target",label:"Element / status",render:e=>semanticControl(row,e.target)},{key:"response",label:"Response",render:e=>semanticControl(row,e.response)}],"Enemy resistances")}));
    const actions=Array.from({length:16},(_,i)=>({key:i+1,attack:fieldByKey(`attack${i}`),animation:fieldByKey(`animation${i}`),camera:fieldByKey(`camera${i}`)}));body.push(detailSection({title:"ACTIONS",attrs:{"data-concept":"enemy-actions"},body:conceptTable(actions,"44px minmax(150px,1.3fr) minmax(90px,.7fr) minmax(90px,.7fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"attack",label:"Attack",render:e=>semanticControl(row,e.attack)},{key:"animation",label:"Animation",render:e=>semanticControl(row,e.animation)},{key:"camera",label:"Camera",render:e=>semanticControl(row,e.camera)}],"Enemy action slots")}));
    const loot=Array.from({length:4},(_,i)=>({key:i+1,item:fieldByKey(`item${i}`),rate:fieldByKey(`dropRate${i}`)}));body.push(detailSection({title:"LOOT",attrs:{"data-concept":"enemy-loot"},body:conceptTable(loot,"44px minmax(150px,1.2fr) minmax(150px,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"item",label:"Item",render:e=>semanticControl(row,e.item)},{key:"rate",label:"Method / chance",render:e=>semanticControl(row,e.rate)}],"Enemy drop and steal slots")}));
    const manipulate=Array.from({length:3},(_,i)=>({key:i+1,attack:fieldByKey(`manipulate${i}`)}));body.push(detailSection({title:"MANIPULATE / BERSERK",attrs:{"data-concept":"enemy-manipulate"},body:conceptTable(manipulate,"44px minmax(160px,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"attack",label:"Attack",render:e=>semanticControl(row,e.attack)}],"Enemy manipulate actions")}));return conceptPanel(row,body)
  }
  function formationDetail(row){
    const omit=new Set();for(let i=0;i<6;i++)for(const suffix of ["enemy","x","y","z","row","cover","flags"])omit.add(`slot${i}_${suffix}`);for(let i=0;i<3;i++)for(const axis of ["x","y","z","directionX","directionY","directionZ"])omit.add(`camera${i}_${axis}`);for(let i=0;i<4;i++)omit.add(`arena${i}`);const body=ordinarySections(row,omit);
    const slots=Array.from({length:6},(_,i)=>({key:i+1,enemy:fieldByKey(`slot${i}_enemy`),x:fieldByKey(`slot${i}_x`),y:fieldByKey(`slot${i}_y`),z:fieldByKey(`slot${i}_z`),row:fieldByKey(`slot${i}_row`),cover:fieldByKey(`slot${i}_cover`),flags:fieldByKey(`slot${i}_flags`)}));body.push(detailSection({title:"ENEMY SLOTS",attrs:{"data-concept":"formation-slots"},body:conceptTable(slots,"40px minmax(130px,1.4fr) repeat(3,minmax(62px,.55fr)) minmax(90px,.8fr) minmax(82px,.7fr) minmax(82px,.7fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"enemy",label:"Enemy",render:e=>semanticControl(row,e.enemy)},{key:"x",label:"X",render:e=>semanticControl(row,e.x)},{key:"y",label:"Y",render:e=>semanticControl(row,e.y)},{key:"z",label:"Z",render:e=>semanticControl(row,e.z)},{key:"row",label:"Row",render:e=>semanticControl(row,e.row)},{key:"cover",label:"Cover",render:e=>semanticControl(row,e.cover)},{key:"flags",label:"Flags",render:e=>semanticControl(row,e.flags)}],"Formation enemy slots")}));
    const cameras=Array.from({length:3},(_,i)=>({key:i+1,...Object.fromEntries(["x","y","z","directionX","directionY","directionZ"].map(axis=>[axis,fieldByKey(`camera${i}_${axis}`)]))}));body.push(detailSection({title:"CAMERAS",attrs:{"data-concept":"formation-cameras"},body:conceptTable(cameras,"40px repeat(6,minmax(68px,1fr))",[{key:"camera",label:"#",numberedId:true,render:e=>e.key},...['x','y','z','directionX','directionY','directionZ'].map(axis=>({key:axis,label:axis.startsWith('direction')?`Dir ${axis.slice(9)}`:axis.toUpperCase(),render:e=>semanticControl(row,e[axis])}))],"Formation cameras")}));
    const arenas=Array.from({length:4},(_,i)=>({key:i+1,field:fieldByKey(`arena${i}`)}));body.push(detailSection({title:"ARENA CANDIDATES",attrs:{"data-concept":"formation-arenas"},body:conceptTable(arenas,"44px minmax(120px,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"arena",label:"Arena ID",render:e=>semanticControl(row,e.field)}],"Formation arena candidates")}));return conceptPanel(row,body)
  }
  function shopDetail(row){const omit=new Set();for(let i=0;i<10;i++){omit.add(`type${i}`);omit.add(`item${i}`)}const body=ordinarySections(row,omit),entries=Array.from({length:10},(_,i)=>({key:i+1,index:i,kind:fieldByKey(`type${i}`),product:fieldByKey(`item${i}`)}));body.push(detailSection({title:"INVENTORY",attrs:{"data-concept":"shop-inventory"},body:conceptTable(entries,"44px 62px minmax(130px,.8fr) minmax(180px,1.3fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"active",label:"Active",render:e=>e.index<Number(row.values.count)?"Yes":"No"},{key:"kind",label:"Kind",render:e=>semanticControl(row,{...e.kind,rerenderOnChange:true})},{key:"product",label:"Product",render:e=>semanticControl(row,e.product)}],"Shop inventory slots")}));return conceptPanel(row,body)}
  function weightedEncounterDetail(row){const count=state.tab==="worldEncounters"?14:10,omit=new Set();for(let i=0;i<count;i++){omit.add(`battle${i}`);omit.add(`chance${i}`)}const body=ordinarySections(row,omit),entries=Array.from({length:count},(_,i)=>({key:i+1,battle:fieldByKey(`battle${i}`),chance:fieldByKey(`chance${i}`)}));body.push(detailSection({title:"WEIGHTED ENCOUNTERS",attrs:{"data-concept":"weighted-encounters"},body:conceptTable(entries,"44px minmax(160px,1.4fr) minmax(90px,.7fr) 72px",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"battle",label:"Battle",render:e=>semanticControl(row,e.battle)},{key:"weight",label:"Weight / 64",render:e=>semanticControl(row,e.chance)},{key:"percent",label:"Share",render:e=>`${Math.round(Number(row.values[e.chance.key])*1000/64)/10}%`}],"Weighted encounter table")}));return conceptPanel(row,body)}
  function recordDetail(row){
    if(state.tab==="growthCurves")return growthCurveDetail(row);
    if(state.tab==="growthBonuses")return growthBonusDetail(row);
    if(state.tab==="characters")return characterDetail(row);
    if(["weapons","armor","accessories"].includes(state.tab))return equipmentDetail(row);
    if(state.tab==="enemies")return enemyDetail(row);
    if(state.tab==="encounters")return formationDetail(row);
    if(state.tab==="shops")return shopDetail(row);
    if(["fieldEncounters","worldEncounters"].includes(state.tab))return weightedEncounterDetail(row);
    return conceptPanel(row,ordinarySections(row));
  }
'''
replace_once(path,old,new,'concept detail renderers')

# Rendered regression: require the holistic, concept-level surfaces rather than merely typed controls.
path=ROOT/'tools/verify_ff7_rendered_neutral.py'
insert='''\n\ndef test_holistic_ff7_concept_views_and_new_game_data(self):\n    self.install(); self.open()\n    self.navigate("initialState")\n    self.assertEqual(self.page.get_by_label("Party member 1 for New game defaults", exact=True).evaluate("e=>e.tagName"), "SELECT")\n    self.navigate("initialInventory")\n    self.assertEqual(self.page.get_by_label("Item / equipment for Slot 1 — Unknown item 421", exact=True).evaluate("e=>e.tagName"), "SELECT")\n    self.navigate("magicOrder")\n    self.assertEqual(self.page.get_by_label("Magic-menu section for Record0", exact=True).evaluate("e=>e.tagName"), "SELECT")\n\n    for tab, concept in (("growthCurves","growth-curve"),("growthBonuses","growth-bonuses"),("characters","character-growth-curves"),("weapons","equipment-materia-slots"),("enemies","enemy-loot"),("encounters","formation-slots"),("shops","shop-inventory"),("fieldEncounters","weighted-encounters")):\n        self.navigate(tab)\n        self.assertEqual(self.page.locator(f'[data-concept="{concept}"]').count(),1,(tab,concept))\n\n    self.navigate("growthCurves")\n    self.assertEqual(self.page.get_by_role("img", name="Primary stat curve 0 curve preview").count(),1)\n    self.assertEqual(self.page.get_by_label("Growth curve brackets").locator("input").count(),16)\n    self.navigate("enemies")\n    self.assertEqual(self.page.get_by_label("Loot slot 1 method / chance method for Enemy0", exact=True).evaluate("e=>e.tagName"),"SELECT")\n    self.assertEqual(self.page.get_by_label("Back-attack damage multiplier for Enemy0", exact=True).get_attribute("step"),"0.125")\n    self.originals_unchanged()\n'''
replace_once(path,
'''target.RenderedTests.open = open_with_neutral\n''',
insert+'''\ntarget.RenderedTests.open = open_with_neutral\n''',
'holistic rendered test')
replace_once(path,
'''target.RenderedTests.test_accessory_description_is_editable_game_text = test_accessory_description_is_editable_game_text\n''',
'''target.RenderedTests.test_accessory_description_is_editable_game_text = test_accessory_description_is_editable_game_text\ntarget.RenderedTests.test_holistic_ff7_concept_views_and_new_game_data = test_holistic_ff7_concept_views_and_new_game_data\n''',
'register holistic rendered test')
