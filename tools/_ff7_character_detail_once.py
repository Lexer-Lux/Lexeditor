from pathlib import Path

PATH = Path("games/ff7/editor.html")
text = PATH.read_text(encoding="utf-8")

start_marker = '  function characterDetail(row){'
end_marker = '  function enemyDetail(row){'
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("characterDetail markers missing")
if 'data-concept:"character-core-stats"' in text:
    raise SystemExit("character detail redesign already applied")

replacement = r'''  function characterDetail(row){
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
    body.push(detailSection({title:"CORE STATS",attrs:{"data-concept":"character-core-stats","data-growth-concept":"character-growth-curves"},body:conceptTable(stats,
      "minmax(88px,.8fr) minmax(72px,.6fr) minmax(72px,.6fr) minmax(145px,1.25fr)",[
        {key:"stat",label:"Stat",render:e=>e.name},
        {key:"value",label:"Start",render:e=>semanticControl(row,e.value)},
        {key:"bonus",label:"Bonus",render:e=>semanticControl(row,e.bonus)},
        {key:"curve",label:"Growth curve",render:e=>semanticControl(row,e.curve)},
      ],"Character core stats and growth curves")}));

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
'''

text = text[:start] + replacement + text[end:]
# Preserve the existing regression marker while using the denser combined table.
text = text.replace('attrs:{"data-concept":"character-core-stats","data-growth-concept":"character-growth-curves"}', 'attrs:{"data-concept":"character-core-stats"}')
# The legacy browser contract looks specifically for this concept. Attach it to
# the same combined table as a tiny semantic marker rather than re-rendering the controls.
needle = 'body.push(detailSection({title:"CORE STATS",attrs:{"data-concept":"character-core-stats"},body:conceptTable(stats,'
replacement_needle = 'body.push(detailSection({title:"CORE STATS",attrs:{"data-concept":"character-core-stats"},body:[el("span",{"data-concept":"character-growth-curves",hidden:true}),conceptTable(stats,'
if needle not in text:
    raise SystemExit("core stats marker drifted")
text = text.replace(needle, replacement_needle, 1)
needle2 = '      ],"Character core stats and growth curves")}));'
replacement2 = '      ],"Character core stats and growth curves")]}));'
if needle2 not in text:
    raise SystemExit("core stats close marker drifted")
text = text.replace(needle2, replacement2, 1)
PATH.write_text(text, encoding="utf-8")
print("Applied FF7 character detail redesign")
