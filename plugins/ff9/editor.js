  "use strict";
  const {el,columnList,columnPreferences,detailPanel,detailSection,detailField,multiNumberRow,readonlyField,recordId,pagedListDetail,booleanMark,subtabBar,infoHelp,clone,infoIcon,toggleRow}=LexeditorUI;
  const $=selector=>document.querySelector(selector);
  async function api(path,body){const response=await fetch(path,body===undefined?undefined:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const payload=await response.json();if(!response.ok)throw new Error(payload.error||response.statusText);return payload}
  const tabs=[
    {id:"accessories",label:"Accessories"},{id:"abilities",label:"Abilities"},{id:"armor",label:"Armor"},{id:"items",label:"Items"},{id:"magic",label:"Magic"},{id:"weapons",label:"Weapons"},
    {id:"characters",label:"Characters"},{id:"enemies",label:"Enemies"},{id:"encounters",label:"Encounters"},{id:"shops",label:"Shops"},{id:"synthesis",label:"Synthesis"},
    {id:"effects",label:"Effects"},{id:"tetra-master",label:"Tetra Master"},{id:"world",label:"World"},{id:"tweaks",label:"Tweaks"}
  ];
  const state={tab:"items",modOnly:false,reshade:null,dashboard:null,dataMap:null,catalog:[],datasets:{},datasetChoice:{},activeSource:"mine",selected:{},query:{},page:{},pageSize:{},sort:{},mapQuery:"",mapStatus:"",mapPage:0,mapSort:["filename",1],busy:false,error:"",runtimeError:"",tweak:"memoria",walkmeshScene:null,features:null,savedFeatures:null,deployment:null};
  const prefCache={};
  const catalogRow=key=>state.catalog.find(value=>value.key===key);
  const CHARACTER_NAV_KEYS=["characters","leveling"];
  const ITEM_CATEGORY_FLAGS=["Weapon","Armlet","Helmet","Armor","Accessory","Item","Gem","Usable"];
  const ITEM_PARTY_FLAGS=["Zidane","Vivi","Garnet","Steiner","Freya","Quina","Eiko","Amarant","Cinna","Marcus","Blank","Beatrix"];
  const choices=tab=>tab==="accessories"?["items"]:tab==="characters"?CHARACTER_NAV_KEYS:state.catalog.filter(value=>value.tab===tab).map(value=>value.key);
  const battleKeys=["enemies","encounters","enemy-attacks","scene-flags"];
  function activeKey(){const available=choices(state.tab);return state.datasetChoice[state.tab]||available[0]||null}
  function viewRows(data,key){let rows=data.rows;if(state.tab==="accessories")rows=rows.filter(row=>row.values.Accessory===true);const query=(state.query[key]||"").toLocaleLowerCase();if(query)rows=rows.filter(row=>`${row.id??""} ${row.name} ${Object.values(row.values).join(" ")}`.toLocaleLowerCase().includes(query));const sort=state.sort[key]||{key:"name",dir:1};const column=columnsFor(data,key).find(value=>value.key===sort.key);return [...rows].sort((left,right)=>{const value=row=>column?.sortValue?column.sortValue(row):sort.key==="name"?row.name:sort.key==="id"?row.id:row.values[sort.key];const a=value(left),b=value(right);return (typeof a==="string"?a.localeCompare(String(b),undefined,{numeric:true,sensitivity:"base"}):Number(a)-Number(b))*sort.dir})}
  function changedFields(data,row){const original=data.originalByLine[String(row.line)];const values={};for(const field of data.fields)if(field.editable&&JSON.stringify(row.values[field.key])!==JSON.stringify(original.values[field.key]))values[field.key]=row.values[field.key];return values}
  // "Mod contents only" keeps the rows this project has actually changed. A row
  // counts as changed when an editable field differs from the copy the dataset
  // was loaded as, which is the comparison a save writes from. A composite row
  // counts the linked records shown beside it too, because editing one of those
  // is still an edit to that row.
  function rowChanged(data,row,linked=[]){
    if(Object.keys(changedFields(data,row)).length)return true;
    return linked.some(entry=>entry&&entry.row&&Object.keys(changedFields(entry.data,entry.row)).length);
  }
  function modOnlySpec(key,changed){
    return {available:state.activeSource==="mine",value:state.modOnly===true,changed,
      change:value=>{state.modOnly=value;state.page[key]=0;render()}};
  }
  function featureChanges(){const current=state.features?.features||{},saved=state.savedFeatures?.features||{};return Object.fromEntries(Object.keys(current).filter(key=>current[key]!==saved[key]).map(key=>[key,current[key]]))}
  function dirtyCount(){if(state.activeSource!=="mine")return 0;let count=Object.keys(featureChanges()).length;for(const data of Object.values(state.datasets))if(data?.rows)for(const row of data.rows)count+=Object.keys(changedFields(data,row)).length;return count}
  function installData(payload){payload.originalRows=clone(payload.rows);payload.originalByLine=Object.fromEntries(payload.originalRows.map(row=>[String(row.line),row]));state.datasets[payload.key]=payload;if(payload.key==="field-walkmesh-triangles"&&payload.activeScene)state.walkmeshScene=payload.activeScene;if(!payload.rows.some(row=>row.line===state.selected[payload.key]))state.selected[payload.key]=payload.rows[0]?.line??null;return payload}
  async function loadDataset(key,force=false,scene=null){if(!key)return null;const triangle=key==="field-walkmesh-triangles",requested=triangle?(scene||state.walkmeshScene||null):null,cached=state.datasets[key];if(!force&&cached&&!cached.unavailable&&(!triangle||!requested||cached.activeScene===requested))return cached;const meta=catalogRow(key);try{const suffix=requested?`&scene=${encodeURIComponent(requested)}`:"";return installData(await api(`/api/dataset?key=${encodeURIComponent(key)}${suffix}`))}catch(error){state.datasets[key]={key,unavailable:true,error:error.message,relativePath:meta?.relativePath};return state.datasets[key]}}
  function sourceHasId(data){return data.fields.some(field=>field.key.toLocaleLowerCase()==="id")}
  function fieldValue(row,field){const value=row.values[field.key];if(field.kind==="boolean")return booleanMark(value);if(field.kind==="fixed-list"&&Array.isArray(value))return value.join(", ");return value===""?"—":String(value)}
  // The list and detail fields use the same column definitions, including
  // the linked records in equipment and character views.
  function columnSources(data,key){
    const sources=[{data,row:record=>record,prefix:""}];
    const add=(name,row)=>{const linked=state.datasets[name];if(linked&&!linked.unavailable)sources.push({data:linked,row,prefix:`${name}:`})};
    if(key.startsWith("equipment-")){
      const spec=equipmentSpec(key.slice(10));
      add(spec.specific,record=>rowById(state.datasets[spec.specific],record.values[spec.id]));
      add("item-stats",record=>rowById(state.datasets["item-stats"],record.values.BonusId));
    }else if(key==="characters"){
      const param=record=>rowById(state.datasets["character-parameters"],record.id);
      add("character-parameters",param);
      add("default-equipment",record=>rowById(state.datasets["default-equipment"],param(record)?.values.DefaultEquipmentSet));
      add("command-sets",record=>rowById(state.datasets["command-sets"],param(record)?.values.DefaultCommandSet));
    }
    return sources;
  }
  function columnsFor(data,key){
    const columns=[{key:"name",label:"Name",sortable:true,width:"minmax(9em,1.6fr)"}];
    if(sourceHasId(data))columns.unshift({key:"id",label:"ID",numberedId:data.rows.every(row=>row.id===null||row.id===undefined||/^[-+]?\\d+$/.test(String(row.id))),sortable:true});
    for(const source of columnSources(data,key)){
      source.data.fields.filter(field=>!["id","comment","name"].includes(field.key.toLocaleLowerCase())).forEach((field,index)=>{
        const value=record=>source.row(record)?.values[field.key];
        // A derived column exists because the file it belongs to cannot supply
        // that value at all — the ability lists carry no MP cost of their own.
        // Leaving it unpinned would hide the one column the panel was built to
        // add, so derived columns start shown.
        columns.push({key:source.prefix+field.key,label:field.label,pinned:field.declaredType==="DERIVED"||(!source.prefix&&index<1),
          sortable:true,width:"minmax(0,1fr)",numeric:["integer","number"].includes(field.kind),sortValue:value,
          render:record=>{const linked=source.row(record);return linked?fieldValue(linked,field):"—"}});
      });
    }
    if(key==="shops")stockColumn(columns);
    return columns;
  }
  // A shop's own CSV cell is a comma list of item ids, which reaches the list
  // as a wall of numbers. The list states how many items the shop stocks, and
  // the panel beside it resolves every id to the item's name and its prices.
  function stockColumn(columns){
    const column=columns.find(value=>value.key==="Items");
    if(!column)return;
    column.label=el("span",{},"Stock",infoHelp("How many items this shop sells, in the order the shop displays them. The panel for each shop lists those items by name. The underlying list of item ids stays editable at the bottom of that panel."));
    column.numeric=true;
    column.sortValue=record=>(record.stock||[]).length;
    column.render=record=>{const count=(record.stock||[]).length;return count?`${count} item${count===1?"":"s"}`:"Nothing"};
  }
  function prefsFor(data,key,columns=columnsFor(data,key)){if(!prefCache[key])prefCache[key]=columnPreferences(`ff9-${key}`,columns,()=>render());return prefCache[key]}
  function tablePanel(data,key,rows,selected,select){const columns=columnsFor(data,key);return columnList({rows,key:row=>row.line,selected,select,sortState:state.sort[key]||{key:"name",dir:1},sort:column=>{const current=state.sort[key]||{key:"name",dir:1};state.sort[key]=current.key===column?{key:column,dir:-current.dir}:{key:column,dir:1};state.page[key]=0;render()},columnPreferences:prefsFor(data,key,columns),columns,class:"ff9-table","aria-label":`${data.label} table`})}
  const EXPLAINED_READ_ONLY={
    "shops:Comment":"Final Fantasy 9 has no shop names. Memoria's shop export carries only Comment, Id and Items, and it fills Comment with a generated placeholder such as “Shop 0000” so the rows can be told apart. Lexeditor shows it as the shop's name, but the game never reads it, so editing it would rename nothing.",
  };
  const readOnlyNote=(data,field)=>EXPLAINED_READ_ONLY[`${data.key}:${field.key}`]||null;
  const FIELD_HELP={
    "characters:Dexterity":"The character's base Dexterity/Speed component. FF9 adds level growth and accumulated bonuses to it; the normal speed calculation caps the result at 50.",
    "characters:Strength":"The character's base Strength component. Level growth and accumulated bonuses build on it, and current Strength is also the stat used to scale maximum HP.",
    "characters:Magic":"The character's base Magic component. Level growth and accumulated bonuses build on it, and current Magic is also the stat used to scale maximum MP.",
    "characters:Will":"The character's base Will/Spirit component. FF9 adds level growth and accumulated bonuses to it; the normal Spirit calculation caps the result at 50.",
    "characters:Gems":"Base Magic Stone capacity. Character level and accumulated capacity bonuses add to this value to determine the support-ability budget.",
    "leveling:Experience":"The cumulative EXP threshold associated with this level on FF9's shared level curve.",
    "leveling:BonusHP":"The shared HP coefficient for this level. Maximum HP uses this coefficient multiplied by the character's current Strength, then divided by 50.",
    "leveling:BonusMP":"The shared MP coefficient for this level. Maximum MP uses this coefficient multiplied by the character's current Magic, then divided by 100.",
    "items:WeaponId":"Links this item record to its weapon-performance row. Items that are not weapons do not use a weapon row.",
    "items:ArmorId":"Links this item record to the defence/evasion row used by armor and accessories.",
    "items:EffectId":"Links a usable item to the Item Effects record that defines what happens when the item is used.",
    "items:Price":"Base gil purchase price used when a normal shop sells this item.",
    "items:SellingPrice":"Gil paid to the player when this item is sold back where selling is allowed.",
    "items:BonusId":"Links equipment to the shared stat/element bonus record applied by that piece of equipment.",
    "items:AbilityIds":"Abilities associated with this equipment for FF9's equipment-learning system. These are the abilities a character can access/learn from the item when the character is eligible for them.",
    "items:GraphicsId":"Selects the inventory/menu graphic associated with this item record.",
    "items:ColorId":"Selects the color variant used with the item's menu graphic.",
    "weapons:Category":"Weapon family/category used by FF9's weapon handling and presentation.",
    "weapons:StatusIndex":"Selects the status-set entry associated with this weapon's attack behavior.",
    "weapons:Model":"Battle model used for this weapon.",
    "weapons:ScriptId":"Battle script used to resolve this weapon's normal attack behavior.",
    "weapons:Power":"Attack-power input supplied to the weapon's battle script.",
    "weapons:Elements":"Element flags carried by the weapon attack and consumed by the battle calculation.",
    "weapons:Rate":"Rate parameter supplied to the weapon/status attack logic; its exact effect depends on the selected battle script.",
    "weapons:HitSfx":"Sound effect played for this weapon's hit/impact presentation.",
    "armor:P.Def":"Physical defence contributed by this armor-data row.",
    "armor:P.Eva":"Physical evasion contributed by this armor-data row.",
    "armor:M.Def":"Magical defence contributed by this armor-data row.",
    "armor:M.Eva":"Magical evasion contributed by this armor-data row.",
    "item-effects:Targets":"Targeting mode used when this item effect is selected in battle or a menu that invokes the effect.",
    "item-effects:DefaultAlly":"Controls whether the targeting cursor begins on allies when this effect is opened.",
    "item-effects:Dead":"Allows this effect to target KO'd/dead characters.",
    "item-effects:DefaultDead":"Makes a KO'd/dead target the default target class for this effect when applicable.",
    "item-effects:ScriptId":"Battle/effect script that implements what this item actually does.",
    "item-effects:Power":"Magnitude input supplied to the selected item-effect script.",
    "item-effects:Rate":"Success/rate input supplied to the selected item-effect script; interpretation can vary by script.",
    "item-effects:Element":"Element associated with this item effect for scripts that consume an element.",
    "item-effects:Status":"Status flags associated with this effect for scripts that apply or inspect statuses.",
    "initial-items:ItemID":"Item placed in the party's starting inventory by this initial-inventory entry.",
    "initial-items:Count":"Starting quantity of the linked item.",
    "mix-items:Result":"Item produced by this mix recipe.",
    "mix-items:Ingredients":"Items consumed by this mix recipe.",
    "shops:Items":"This ordered list is the shop's actual stock. Adding or removing item IDs changes what the shop offers for sale.",
    "synthesis:Shops":"Shop IDs in which this synthesis recipe is available.",
    "synthesis:Price":"Gil charged to perform this synthesis recipe; ingredient items are consumed separately.",
    "synthesis:Result":"Item produced when the synthesis succeeds.",
    "synthesis:Ingredients":"Items consumed by this synthesis recipe.",
    "abilities:Gems":"Magic Stones required to equip this support ability. This cost consumes part of the character's available Magic Stone capacity.",
    "character-parameters:DefaultRow":"Initial battle-row flag assigned when this character setup is created. Normal row-changing mechanics can change the character's row afterward.",
    "character-parameters:DefaultWinPose":"Selects the default victory-pose behavior for this character setup.",
    "character-parameters:DefaultCategory":"Character-category flags used by FF9 to distinguish actor capabilities/roles in battle logic.",
    "character-parameters:DefaultCommandSet":"Links this character setup to the command-set row that fills the battle command menu.",
    "character-parameters:DefaultEquipmentSet":"Links this character setup to the predefined equipment set used for starting/default gear.",
    "character-parameters:BattleParameterFormula":"Memoria expression that chooses the character's battle-parameter/model setup from runtime context such as weapon shape or story state.",
    "character-parameters:NameKeyword":"Localization keyword used to resolve the character's default/display name.",
    "commands:Ability":"Single ability associated with commands that dispatch one fixed ability.",
    "commands:Abilities":"Ability list exposed by commands that open a selectable ability menu.",
    "default-equipment:Weapon":"Weapon equipped by this predefined starting-equipment set.",
    "default-equipment:Head":"Headgear equipped by this predefined starting-equipment set.",
    "default-equipment:Wrist":"Wrist/arm equipment in this predefined starting-equipment set.",
    "default-equipment:Armor":"Body armor in this predefined starting-equipment set.",
    "default-equipment:Accessory":"Accessory in this predefined starting-equipment set.",
    "actions:targets":"Targeting mode used when this battle action is selected.",
    "actions:defaultAlly":"Controls whether the action's targeting cursor begins on the ally side.",
    "actions:forDead":"Allows the action to target KO'd/dead units.",
    "actions:defaultOnDead":"Makes KO'd/dead units the default target class when the action supports them.",
    "actions:defaultCamera":"Lets the action use its normal battle-camera behavior rather than suppressing it.",
    "actions:scriptId":"Battle script that implements this action's gameplay effect.",
    "actions:power":"Magnitude input supplied to the selected battle script.",
    "actions:elements":"Element flags associated with the action for scripts/calculations that consume elements.",
    "actions:rate":"Success/rate input supplied to the selected battle script; interpretation can vary by script.",
    "actions:statusIndex":"Selects the status-set entry associated with this action.",
    "actions:mp":"MP consumed when this action is used through a command that charges its listed cost.",
    "magic-sword-sets:Supporter":"Character whose presence/ability support enables this Magic Sword relationship.",
    "magic-sword-sets:Beneficiary":"Character who receives the Magic Sword ability set from this relationship.",
    "magic-sword-sets:BaseAbilities":"Base abilities considered for this Magic Sword pairing.",
    "magic-sword-sets:UnlockedAbilities":"Magic Sword abilities made available when their corresponding conditions are satisfied.",
    "status-data:OprCount(tick)":"Controls the periodic-operation cadence for statuses that execute repeated tick logic.",
    "status-data:ContiCount(duration)":"Base duration counter used by statuses whose lifetime is measured by the status system.",
    "status-data:ClearOnApply":"Statuses cleared when this status is successfully applied.",
    "status-data:ImmunityProvided":"Statuses the affected unit becomes immune to while this status is providing immunity.",
    "status-data:SPSEffect":"Sprite-particle effect associated with this status's visual presentation.",
    "status-data:SHPEffect":"Shape-particle effect associated with this status's visual presentation.",
    "status-sets:Statuses":"Statuses grouped under this reusable status-set ID. Actions, weapons, and other records can refer to the set by index.",
    "tetra-cards:ATK(UP)":"Attack value printed/used on the card's upper edge in Tetra Master data.",
    "tetra-cards:MDEF(RIGHT)":"Defence value associated with the card's right edge in Tetra Master data.",
    "tetra-cards:MATK(DOWN)":"Attack value associated with the card's lower edge in Tetra Master data.",
    "tetra-cards:PDEF(LEFT)":"Defence value associated with the card's left edge in Tetra Master data.",
    "world-transport:speed_move":"Forward movement speed for this world-map transport type.",
    "world-transport:speed_rotation":"Turning speed for this world-map transport type.",
    "world-transport:speed_updown":"Vertical movement speed for transports that can change altitude.",
    "world-transport:flg_fly":"Controls whether this transport type uses flying/airborne movement behavior.",
    "world-transport:encount":"Controls whether random world-map encounters can occur while using this transport type.",
    "world-transport:radius":"Collision/footprint radius used for this transport on the world map.",
    "field-walkmesh:Active":"Whether this field walkmesh floor starts enabled for pathing. Lexeditor changes only Memoria's BGI_FLOOR_ACTIVE bit; scripts can still enable or disable floors at runtime.",
    "field-walkmesh-triangles:Active":"Whether this field walkmesh triangle starts enabled for pathing. Lexeditor changes only Memoria's BGI_TRI_ACTIVE bit; scripts can still enable or disable triangles at runtime.",
    "field-walkmesh-triangles:AlternateFootstep":"Selects Memoria's alternate footstep surface for this triangle. This is the same 0x1000 flag exposed by Memoria Field Creator as “Alternate footstep.”",
    "field-walkmesh-triangles:PreventNPC":"Prevents non-player field actors from pathing into this triangle. This is Memoria Field Creator's documented 0x4000 “Prevent NPC pathing” flag.",
    "field-walkmesh-triangles:PreventPC":"Prevents the player-controlled field actor from pathing into this triangle. This is Memoria Field Creator's documented 0x8000 “Prevent PC pathing” flag.",
    "enemy-attacks:Target":"Targeting mode for this enemy attack, chosen from Memoria's verified 16-entry TargetType list.",
    "enemy-attacks:DefaultAlly":"Starts this attack's targeting cursor on the ally side.",
    "enemy-attacks:DisplayStats":"Target-display mode (0-7). Memoria names 0-4 (None, HP, MP, Debuffs, Buffs); higher values have no verified meaning and are kept as stored numbers.",
    "enemy-attacks:VfxIndex":"Battle VFX index (0-511) selected for this attack.",
    "enemy-attacks:LegacySfx":"Twelve sound bits Memoria reads and discards when loading the scene. Lexeditor shows the stored value and preserves it verbatim; it is never editable.",
    "enemy-attacks:ForDead":"Allows this attack to target KO'd/dead units.",
    "enemy-attacks:DefaultCamera":"Lets this attack use its normal battle-camera behavior rather than suppressing it.",
    "enemy-attacks:DefaultOnDead":"Makes KO'd/dead units the default target class when this attack supports them.",
    "enemy-attacks:ScriptId":"Battle script that implements this attack's gameplay effect.",
    "enemy-attacks:Power":"Magnitude input supplied to the selected battle script.",
    "enemy-attacks:Elements":"Element flags carried by this attack and consumed by the battle calculation.",
    "enemy-attacks:Rate":"Rate parameter supplied to the attack logic; its exact effect depends on the selected battle script.",
    "enemy-attacks:Category":"Attack category byte stored by the battle-scene format. Memoria loads it without documenting category values, so Lexeditor edits only the stored byte.",
    "enemy-attacks:AddStatusNo":"Status-set index applied by this attack. Values 0-38 match Memoria's verified StatusSetId list; the Status sets dataset shows set membership.",
    "enemy-attacks:MP":"MP cost stored for this enemy attack.",
    "enemy-attacks:Type":"Attack type byte stored by the battle-scene format. Memoria loads it without documenting type values, so Lexeditor edits only the stored byte.",
    "enemy-attacks:Vfx2":"Secondary VFX value stored for this attack.",
    "enemy-attacks:Name":"Numeric name reference stored for this attack. Memoria converts it to text at load; Lexeditor edits only the stored number.",
    "scene-flags:SpecialStart":"Marks this battle as a special start (Memoria SB2_FLG_SPECIAL).",
    "scene-flags:BackAttack":"The party is attacked from behind in this battle (Memoria SB2_FLG_BACKATK).",
    "scene-flags:NoGameOver":"Losing this battle does not trigger game over (Memoria SB2_FLG_NOGAMEOVER).",
    "scene-flags:NoExp":"This battle awards no experience (Memoria SB2_FLG_EXPZERO).",
    "scene-flags:NoWinPose":"Skips the victory pose after this battle (Memoria SB2_FLG_NOWINPOSE).",
    "scene-flags:NoRunaway":"The party cannot escape from this battle (Memoria SB2_FLG_NORUNAWAY).",
    "scene-flags:NoNeighboring":"Sets the no-near-attack rule for this battle (Memoria SB2_FLG_NONEARATK).",
    "scene-flags:NoMagical":"Blocks magical actions in this battle (Memoria SB2_FLG_NOMAGICAL).",
    "scene-flags:ReverseAttack":"Reverses attack sides for this battle (Memoria SB2_FLG_REVERSEATK).",
    "scene-flags:FixedCamera1":"Fixes battle camera 1 for this battle (Memoria SB2_FLG_FIXEDCAM1).",
    "scene-flags:FixedCamera2":"Fixes battle camera 2 for this battle (Memoria SB2_FLG_FIXEDCAM2).",
    "scene-flags:AfterEvent":"Runs an event after this battle (Memoria SB2_FLG_AFTEREVENT).",
    "scene-flags:OtherFlags":"Upper flag bits 12-15. Memoria names two of them but no pinned code path consumes them, so Lexeditor preserves them verbatim and never edits them."
  };
  function semanticFieldHelp(data,field){
    const dataKey=String(data?.key||"");
    if(dataKey.startsWith("ability-")&&field.key==="AP")return "AP this character must earn from eligible equipment to permanently learn the linked ability.";
    if(dataKey.startsWith("ability-")&&field.key==="Id")return "Which ability this slot holds. AA: followed by a battle-action id is an active ability; SA: followed by a support-ability id is a support ability. The value 0 is the file's own void ability — an unused slot in this character's learn list, shown here as an empty slot.";
    if(dataKey.startsWith("ability-")&&field.key==="mp")return "MP the matching battle action costs, read from Battle/Actions.csv. It is shown here and edited on that file, so that one ability cannot end up with two different costs.";
    if(dataKey==="item-stats"&&["Dexterity","Strength","Magic","Will"].includes(field.key))return `When a character levels while equipment using this bonus row is equipped, FF9 adds this ${field.key} bonus into the character's accumulated stat-growth bonus.`;
    if(dataKey==="item-stats"&&field.key==="AttackElement")return "Element added to physical attacks by equipment that references this bonus row.";
    if(dataKey==="item-stats"&&field.key==="GuardElement")return "Elements guarded against by equipment that references this bonus row.";
    if(dataKey==="item-stats"&&field.key==="AbsorbElement")return "Elements converted from damage into healing by equipment that references this bonus row.";
    if(dataKey==="item-stats"&&field.key==="HalfElement")return "Elements whose incoming damage is halved by equipment that references this bonus row.";
    if(dataKey==="item-stats"&&field.key==="WeakElement")return "Elements to which equipment using this bonus row makes the wearer weak.";
    if(dataKey==="command-sets"&&field.key!=="Id")return field.key.includes("Trance")?"Command ID placed in this battle-menu slot while the character is in Trance.":"Command ID placed in this battle-menu slot in the character's normal state.";
    if(dataKey==="enemies"){
      const help={MaxHP:"Maximum HP for this enemy type in this battle scene.",MaxMP:"Maximum MP for this enemy type in this battle scene.",WinGil:"Gil awarded by this enemy record when battle rewards are resolved.",WinExp:"Experience awarded by this enemy record when battle rewards are resolved.",AP:"Ability Points contributed by this enemy record to the battle reward.",Speed:"Enemy Dexterity/Speed stat used by battle timing logic.",Strength:"Enemy Strength stat used by physical battle calculations.",Magic:"Enemy Magic stat used by magical battle calculations.",Spirit:"Enemy Spirit/Will stat used by battle calculations.",Level:"Enemy level used by formulas and scripts that reference target or caster level.",HitRate:"Enemy hit-rate stat used by applicable physical calculations.",PhysicalDefence:"Enemy physical defence stat.",PhysicalEvade:"Enemy physical evasion stat.",MagicalDefence:"Enemy magical defence stat.",MagicalEvade:"Enemy magical evasion stat.",BlueMagic:"Blue Magic ability ID learned by Quina when this enemy is successfully eaten/cooked; 0 means no linked Blue Magic in vanilla-format data.",GuardElement:"Bit mask of elements this enemy guards.",AbsorbElement:"Bit mask of elements this enemy absorbs.",HalfElement:"Bit mask of elements whose damage is halved.",WeakElement:"Bit mask of elements to which this enemy is weak."};
      if(help[field.key])return help[field.key];
      if(/^WinItem\d+$/.test(field.key))return "Item ID in one of this enemy record's battle-reward drop slots.";
      if(/^StealItem\d+$/.test(field.key))return "Item ID in one of this enemy record's steal slots.";
    }
    if(dataKey==="encounters"){
      if(field.key==="Rate")return "Encounter-pattern selection weight stored by this battle scene.";
      if(field.key==="MonsterCount")return "Number of active enemy placements in this encounter pattern. FF9 raw16 supports at most four slots.";
      if(field.key==="Camera")return "Battle camera index selected for this encounter pattern.";
      if(field.key==="AP")return "Ability Points attached to this encounter pattern by the battle-scene format.";
      if(/^Slot\d+Type$/.test(field.key))return "Zero-based enemy-type index within this same battle scene. Lexeditor bounds it to the scene's actual enemy-type count.";
      if(/^Slot\d+[XYZ]$/.test(field.key))return "World-space placement coordinate for this enemy slot in the encounter pattern.";
      if(/^Slot\d+Rotation$/.test(field.key))return "Stored rotation value for this enemy placement.";
    }
    return FIELD_HELP[`${dataKey}:${field.key}`]||"";
  }
  function setValue(data,row,field,value){row.values[field.key]=value;shell.refresh();toolbar()}
  // A property carries the value its record shipped with, so right-clicking it
  // puts that value back - the reset every other game's properties already
  // have. The plugin supplies the vanilla value and how to write one back; the
  // shared framework owns the comparison, the reference rail and the restore.
  const sameValue=(left,right)=>JSON.stringify(left)===JSON.stringify(right);
  const formatFieldValue=field=>field.kind==="fixed-list"?value=>Array.isArray(value)?value.join(", "):String(value):null;
  function vanillaValue(data,row,field){const base=data.vanilla?.[String(row.line)];if(base&&Object.prototype.hasOwnProperty.call(base,field.key))return base[field.key];const original=data.originalByLine?.[String(row.line)]?.values;return original?original[field.key]:undefined}
  // Restoring a value or taking a reference writes the model and rebuilds the
  // panel, so a grouped number box shows the value that was just restored
  // instead of the digits the reader typed into it.
  function sourceControl(control,current,vanilla,apply,format){return LexeditorUI.provenanceControl({control,current,vanilla,format:format||undefined,same:sameValue,apply:value=>{apply(value);render()}})}
  function fieldPin(data,field){
    const key=["accessories","armor","weapons"].includes(state.tab)?`equipment-${state.tab}`:activeKey();
    if(!key)return null;
    const base=state.datasets[key.startsWith("equipment-")?"items":key];
    if(!base)return null;
    const source=columnSources(base,key).find(value=>value.data.key===data.key);
    if(!source)return null;
    const column=field.key.toLocaleLowerCase();
    if(column==="comment"||source.prefix&&["id","name"].includes(column))return null;
    return prefsFor(base,key).pinButton(["id","name"].includes(column)?column:source.prefix+field.key,field.label);
  }
  function fieldControl(data,row,field){
    const note=readOnlyNote(data,field),semantic=note||semanticFieldHelp(data,field),bounds=row.fieldBounds?.[field.key]||field;let control;
    if(note||!field.editable||field.kind==="stored")control=readonlyField(String(row.values[field.key]??""));
    else if(field.kind==="boolean")control=el("input",{type:"checkbox",checked:!!row.values[field.key],onchange:event=>setValue(data,row,field,event.target.checked)});
    else if(field.kind==="integer"||field.kind==="number")control=el("input",{type:"number",min:bounds.min,max:bounds.max,step:field.step||1,value:row.values[field.key],oninput:event=>{if(event.target.value!=="")setValue(data,row,field,Number(event.target.value))}});
    else if(field.kind==="enum")control=el("select",{value:row.values[field.key],onchange:event=>setValue(data,row,field,event.target.value)},...(field.choices||[]).map(value=>el("option",{value,selected:value===row.values[field.key]},value)));
    else if(field.kind==="fixed-list"){
      const values=Array.isArray(row.values[field.key])?row.values[field.key]:[],labels=field.vector3?["X","Y","Z"]:field.key==="ColorBase"?["R","G","B"]:Array.from({length:field.length},(_value,index)=>String(index+1));
      control=multiNumberRow(labels.map((label,index)=>({label,control:el("input",{type:"number",min:field.itemMin,max:field.itemMax,step:field.itemKind==="integer"?1:(field.step||"any"),value:values[index]??0,oninput:event=>{if(event.target.value==="")return;const next=[...values];next[index]=Number(event.target.value);setValue(data,row,field,next)}})})),{columns:Math.min(3,field.length||3)});
    }else control=el("input",{type:"text",value:row.values[field.key]??"",oninput:event=>setValue(data,row,field,event.target.value)});
    if(!note&&field.editable&&field.kind!=="stored")
      control=sourceControl(control,()=>row.values[field.key],vanillaValue(data,row,field),
        next=>setValue(data,row,field,next),formatFieldValue(field));
    // A single on/off property is a boolean, whatever word the CSV's type line
    // stores it as ("Bit", "Boolean"). The shared field only lays a checkbox
    // out and points its leader arrow at it under the name it knows, so the
    // declared word is translated rather than passed through: passed through,
    // the box stretched to the full row with no arrow at all.
    const dataType=note?"READ ONLY":field.kind==="boolean"?"BOOL":field.declaredType;
    return detailField({label:field.label.toLocaleUpperCase(),pin:fieldPin(data,field),help:semantic?infoHelp(semantic):null,control,dataType,min:bounds.min,max:bounds.max});
  }
  const fieldRows=(data,row,exclude=[])=>{const blocked=new Set(exclude.map(String));return data&&row?data.fields.filter(field=>!blocked.has(field.key)&&field.key.toLocaleLowerCase()!=="id"&&field.key.toLocaleLowerCase()!=="comment").map(field=>fieldControl(data,row,field)):[]};
  function boolProperty(data,row,label,keys,help){const fields=new Map(data.fields.map(field=>[field.key,field]));const toggles=keys.filter(key=>fields.has(key)).map(key=>({key,label:key,pin:fieldPin(data,fields.get(key)),checked:!!row.values[key],disabled:state.activeSource!=="mine",change:value=>setValue(data,row,fields.get(key),value)}));return toggles.length?detailField({label,help:help?infoHelp(help):null,control:toggleRow({label,toggles}),dataType:"FLAGS"}):null}
  function itemSections(data,row,title="ITEM DATA"){const grouped=[...ITEM_CATEGORY_FLAGS,...ITEM_PARTY_FLAGS];const body=fieldRows(data,row,grouped);const categories=boolProperty(data,row,"CATEGORIES",ITEM_CATEGORY_FLAGS,"These switches decide which FF9 item/equipment categories this record belongs to and whether it behaves as a normal usable item. More than one category can apply to the same underlying item record.");const party=boolProperty(data,row,"EQUIPPABLE BY",ITEM_PARTY_FLAGS,"Each switch controls whether that character is allowed to equip this record. Guest-character switches matter only while that character is actually available.");if(categories)body.push(categories);if(party)body.push(party);return detailSection({title,body})}
  // A record's panel carries no subtitle. The tab already says which records it
  // shows, and the file name and format under the record's name told a player
  // nothing they could act on.
  function detail(data,row){const identity=sourceHasId(data)?recordId(row.id):null;if(data.key==="items")return detailPanel({className:"ff9-detail",title:row.name,identity,body:[itemSections(data,row)]});if(data.key==="shops")return shopDetail(data,row);if(data.key==="tetra-cards")return cardDetail(data,row);if(data.key.startsWith("ability-"))return abilityDetail(data,row);const visible=data.fields.filter(field=>!["id","comment"].includes(field.key.toLocaleLowerCase())),editable=visible.filter(field=>field.editable&&field.kind!=="stored"&&!readOnlyNote(data,field)),stored=visible.filter(field=>!field.editable||field.kind==="stored"||readOnlyNote(data,field));const body=[];if(editable.length)body.push(detailSection({title:"EDITABLE DATA",body:editable.map(field=>fieldControl(data,row,field))}));if(stored.length)body.push(detailSection({title:"STORED DATA",body:stored.map(field=>fieldControl(data,row,field))}));return detailPanel({className:"ff9-detail",title:row.name,identity,body})}
  const gilValue=value=>value===""||value===null||value===undefined?"—":`${LexeditorUI.formatNumber(value)} gil`;
  // A shop record is one row of item ids. The ids are the editable truth, but
  // a reader needs the items themselves, so the panel resolves every id to the
  // item record that owns its name and prices.
  function shopDetail(data,row){
    const stock=Array.isArray(row.stock)?row.stock:[],rows=stock.map((entry,index)=>({...entry,slot:index+1}));
    const body=[];
    body.push(stock.length?columnList({fill:true,rows,key:entry=>entry.slot,class:"ff9-shop-table ff9-record-list",columns:[
      {key:"slot",label:"Slot",width:"54px"},
      {key:"name",label:"Item",sortable:true,width:"minmax(120px,2fr)"},
      {key:"buyPrice",label:"Buy price",numeric:true,sortable:true,width:"minmax(90px,1fr)",render:entry=>gilValue(entry.buyPrice)},
      {key:"sellPrice",label:"Sell price",numeric:true,sortable:true,width:"minmax(90px,1fr)",render:entry=>gilValue(entry.sellPrice)}
    ]}):detailSection({title:"STOCK",body:[LexeditorUI.detailNote("This shop stocks no items.")]}));
    const visible=data.fields.filter(field=>!["id","comment"].includes(field.key.toLocaleLowerCase())),editable=visible.filter(field=>field.editable&&field.kind!=="stored"&&!readOnlyNote(data,field)),stored=visible.filter(field=>!field.editable||field.kind==="stored"||readOnlyNote(data,field));
    if(editable.length)body.push(detailSection({title:"EDITABLE DATA",body:editable.map(field=>fieldControl(data,row,field))}));
    if(stored.length)body.push(detailSection({title:"STORED DATA",body:stored.map(field=>fieldControl(data,row,field))}));
    return detailPanel({className:"ff9-detail",title:row.name,identity:null,body});
  }
  // A Tetra Master card is read the way the game draws it: one value on each
  // edge and the card's icon in a corner. The shared stat card owns that shape,
  // so this screen supplies only FF9's own values, their order and their names.
  // The art is cut from the player's own install into a private cache
  // (card_art.py); nothing is bundled, and without an install the card keeps
  // its plain face.
  const CARD_SIDES=[["ATK(UP)","Attack, up edge"],["PDEF(LEFT)","Defence, left edge"],["MDEF(RIGHT)","Defence, right edge"],["MATK(DOWN)","Attack, down edge"]];
  function cardDetail(data,row){
    // The card's own dataset owns the range and the icon names, so the card,
    // the property rows and a saved file all read the same values.
    const sideRange=key=>{const field=data.fields.find(value=>value.key===key)||{};
      return [Number.isFinite(field.min)?field.min:1,Number.isFinite(field.max)?field.max:10]};
    const stored=key=>Number(row.values[key])||0;
    // QuadMist prints a ten as A.
    const rank=key=>stored(key)===10?"A":String(stored(key));
    const write=(key,next)=>{const [low,high]=sideRange(key);row.values[key]=Math.max(low,Math.min(high,Number(next)||low));shell.refresh();render()};
    const step=(key,direction)=>{const [low,high]=sideRange(key),value=stored(key),span=high-low+1;
      const raised=low+(((value-low+1)%span)+span)%span;
      write(key,direction>0?raised:value<=low?high:value-1)};
    let card=null;
    const iconField=data.fields.find(value=>value.key==="Icon");
    const picker=LexeditorUI.choicePopover({label:"Choose the card's icon",boundary:()=>card,
      choices:(iconField?.choices||[]).map(name=>({value:name,label:name})),
      select:name=>{row.values.Icon=name;shell.refresh();render()}});
    const rankButton=([key,label])=>el("button",{type:"button",disabled:state.activeSource!=="mine",
      title:`${label}: click to raise, right-click to lower`,
      "aria-label":`${label}, currently ${rank(key)}`,
      onclick:()=>step(key,1),oncontextmenu:event=>{event.preventDefault();step(key,-1)}},rank(key));
    const icon=el("button",{type:"button",disabled:state.activeSource!=="mine",
      title:`Change the card's icon, currently ${row.values.Icon}`,
      "aria-label":`Card icon, currently ${row.values.Icon}`,
      onclick:()=>picker.openFor(icon)},el("span",{class:"ff9-card-icon"},String(row.values.Icon||"")));
    card=LexeditorUI.statCard({image:`/assets/cards/${Number(row.id)}.png`,label:row.name,
      ranks:CARD_SIDES.map(rankButton),corner:icon,cornerWord:true});
    // The card beside what it holds, as the FF8 card screen lays it out: the
    // shared panel's own layout, asked for by name.
    return detailPanel({bodyLayout:"beside",className:"ff9-detail ff9-card-detail",title:row.name,
      identity:recordId(row.id),body:[
        detailSection({title:"PREVIEW",body:[card],
          help:infoHelp("The card as QuadMist draws it, with each number on the edge it belongs to. Click a number to raise it and right-click to lower it. The corner shows the card's icon; press it to choose another. The art is read from your installed game.")}),
        detailSection({title:"CARD",body:fieldRows(data,row)})]});
  }
  // An ability row is a slot in one character's learn list: the id says which
  // ability it holds, and the file stores no cost of its own. The MP cost comes
  // from the matching battle action, so it is shown as a derived value.
  function abilityDetail(data,row){
    const fieldFor=key=>{const field=data.fields.find(value=>value.key===key);return field?fieldControl(data,row,field):null};
    const body=[],slot=fieldFor("Id");
    if(slot)body.push(detailSection({title:"SLOT",body:[slot]}));
    const cost=fieldFor("mp");
    if(cost)body.push(detailSection({title:row.action?`BATTLE ACTION · ${row.action}`:"BATTLE ACTION",body:[cost]}));
    const editable=data.fields.filter(field=>field.editable&&!["id","comment"].includes(field.key.toLocaleLowerCase()));
    if(editable.length)body.push(detailSection({title:"EDITABLE DATA",body:editable.map(field=>fieldControl(data,row,field))}));
    return detailPanel({className:"ff9-detail",title:row.name,identity:recordId(row.id),body});
  }
  // Missing source is an availability state, not a claim that the format is unintegrated.
  function unavailable(key){const meta=catalogRow(key),data=state.datasets[key],battle=battleKeys.includes(key),walkmesh=key.startsWith("field-walkmesh");return detailPanel({
    title:data?.label||meta?.label||tabs.find(tab=>tab.id===state.tab)?.label||"FF9 data",body:[
    LexeditorUI.notice({tone:"warning",title:"Source currently unavailable",
      message:data?.error||(battle?"The installed p0data2.bin battle-scene source is not available right now.":walkmesh?"No installed p0data1 field bundle or project BGI override is available right now.":"The verified Memoria baseline source could not be loaded right now.")}),
    detailSection({title:"PROJECT",body:[
      LexeditorUI.detailNote(battle?"The format-specific battle editor is integrated, but it needs an installed FF9 p0data2 source to enumerate battle scenes. Saves write only Memoria raw16 project overlays.":walkmesh?"The walkmesh editor is a deliberately partial integration: it edits only the documented floor/triangle activity bits and writes a canonical loose .bgi.bytes project overlay while preserving every other byte.":"This editor format is integrated. Reopening it retries the verified Memoria baseline; saves still write only to the selected project overlay and never overwrite the installed-game baseline."),
      detailField({label:"FOLDER",control:readonlyField(data?.sourcePath||meta?.projectPath||state.dashboard.project.root,{format:false})})]})]})}
  function statusPanel(title,meta,message){return detailPanel({title,meta,body:[detailSection({title:"STATE",body:[LexeditorUI.detailNote(message)]})]})}
  function renderDataset(data,key){if(!data||data.unavailable||data.available===false){$("#main").replaceChildren(unavailable(key));return}if(!data.rows.length){const meta=key.startsWith("field-walkmesh")?"BGI walkmesh":battleKeys.includes(key)?"BattleScene raw16":`${data.source} CSV`;$("#main").replaceChildren(statusPanel(data.label,meta,"This source is valid but contains no records."));return}const rows=viewRows(data,key),selected=rows.find(row=>row.line===state.selected[key])||rows[0];if(selected)state.selected[key]=selected.line;const layout=pagedListDetail({modOnly:modOnlySpec(key,row=>rowChanged(data,row)),rows,key:row=>row.line,slots:true,selected:selected?.line??null,page:state.page[key]||0,pageSize:state.pageSize[key]||12,fit:{minRowHeight:40},noun:"records",className:"ff9-layout",splitKey:`ff9-${state.tab}-${key}`,rowsKey:`ff9-${state.tab}-${key}`,defaultSplit:44,minLeft:340,minRight:420,search:{key:`ff9-${key}`,value:state.query[key]||"",label:`Search ${data.label}`,change:value=>{state.query[key]=value;state.page[key]=0;render()}},sync:next=>{state.page[key]=next.page;state.pageSize[key]=next.pageSize;if(next.selected!==null)state.selected[key]=next.selected},change:next=>{state.page[key]=next.page;state.pageSize[key]=next.pageSize;if(next.selected!==null)state.selected[key]=next.selected;render()},master:view=>tablePanel(data,key,view.rows,view.selected,view.select),detail:row=>detail(data,row)});$("#main").replaceChildren(layout)}

  const rowById=(data,id)=>data?.rows?.find(row=>String(row.id)===String(id))||null;
  function characterDetail(base,row,parameters,equipment,commandSets){const param=rowById(parameters,row.id);const equipmentRow=param?rowById(equipment,param.values.DefaultEquipmentSet):null;const commandRow=param?rowById(commandSets,param.values.DefaultCommandSet):null;const body=[detailSection({title:"BASE STATS",body:fieldRows(base,row)}),detailSection({title:"HP / MP",body:[detailField({label:"HP",help:infoHelp("FF9 has no per-character base HP field. Max HP is calculated from the shared level curve and the character's current Strength, including growth bonuses."),control:readonlyField("Derived: BonusHP[level] × current Strength ÷ 50"),dataType:"DERIVED"}),detailField({label:"MP",help:infoHelp("FF9 has no per-character base MP field. Max MP is calculated from the shared level curve and the character's current Magic, including growth bonuses."),control:readonlyField("Derived: BonusMP[level] × current Magic ÷ 100"),dataType:"DERIVED"}),detailField({label:"LEVEL CURVE",control:el("button",{type:"button",onclick:()=>{state.datasetChoice.characters="leveling";render()}},"Edit shared HP / MP level curve")})]})];if(param)body.push(detailSection({title:"CHARACTER PARAMETERS",body:fieldRows(parameters,param,["DefaultEquipmentSet","DefaultCommandSet"])}));if(equipmentRow)body.push(detailSection({title:"STARTING EQUIPMENT",body:fieldRows(equipment,equipmentRow)}));if(commandRow)body.push(detailSection({title:"COMMAND SET",body:fieldRows(commandSets,commandRow)}));return detailPanel({className:"ff9-detail",title:row.name,identity:recordId(row.id),body})}
  async function renderCharacterComposite(){const [base,parameters,equipment,commandSets]=await Promise.all([loadDataset("characters"),loadDataset("character-parameters"),loadDataset("default-equipment"),loadDataset("command-sets")]);if(!base||base.unavailable){renderDataset(base,"characters");return}const rows=viewRows(base,"characters"),selected=rows.find(row=>row.line===state.selected.characters)||rows[0];if(selected)state.selected.characters=selected.line;const layout=pagedListDetail({modOnly:modOnlySpec("characters",row=>{const param=rowById(parameters,row.id);return rowChanged(base,row,[{data:parameters,row:param},{data:equipment,row:param?rowById(equipment,param.values.DefaultEquipmentSet):null},{data:commandSets,row:param?rowById(commandSets,param.values.DefaultCommandSet):null}])}),rows,key:row=>row.line,slots:true,selected:selected?.line??null,page:state.page.characters||0,pageSize:state.pageSize.characters||12,fit:{minRowHeight:40},noun:"characters",className:"ff9-layout",splitKey:"ff9-characters-combined",rowsKey:"ff9-characters-combined",defaultSplit:44,minLeft:340,minRight:420,search:{key:"ff9-characters",value:state.query.characters||"",label:"Search characters",change:value=>{state.query.characters=value;state.page.characters=0;render()}},sync:next=>{state.page.characters=next.page;state.pageSize.characters=next.pageSize;if(next.selected!==null)state.selected.characters=next.selected},change:next=>{state.page.characters=next.page;state.pageSize.characters=next.pageSize;if(next.selected!==null)state.selected.characters=next.selected;render()},master:view=>tablePanel(base,"characters",view.rows,view.selected,view.select),detail:row=>characterDetail(base,row,parameters,equipment,commandSets)});$("#main").replaceChildren(layout)}
  const equipmentSpec=tab=>tab==="weapons"?{specific:"weapons",id:"WeaponId",title:"WEAPON STATS",test:row=>row.values.Weapon===true}:tab==="accessories"?{specific:"armor",id:"ArmorId",title:"DEFENCE / EVASION",test:row=>row.values.Accessory===true}:{specific:"armor",id:"ArmorId",title:"DEFENCE / EVASION",test:row=>row.values.Armlet===true||row.values.Helmet===true||row.values.Armor===true};
  function equipmentDetail(tab,items,row,specific,stats){const spec=equipmentSpec(tab);const specificRow=rowById(specific,row.values[spec.id]);const statRow=rowById(stats,row.values.BonusId);const body=[itemSections(items,row,"SHARED ITEM DATA")];if(specificRow)body.push(detailSection({title:spec.title,body:fieldRows(specific,specificRow)}));if(statRow)body.push(detailSection({title:"EQUIPMENT BONUSES",body:fieldRows(stats,statRow)}));return detailPanel({className:"ff9-detail",title:row.name,identity:recordId(row.id),body})}
  async function renderEquipmentComposite(tab){const spec=equipmentSpec(tab);const [items,specific,stats]=await Promise.all([loadDataset("items"),loadDataset(spec.specific),loadDataset("item-stats")]);if(!items||items.unavailable){renderDataset(items,"items");return}const key=`equipment-${tab}`;const source={...items,rows:items.rows.filter(spec.test)};const rows=viewRows(source,key),selected=rows.find(row=>row.line===state.selected[key])||rows[0];if(selected)state.selected[key]=selected.line;const layout=pagedListDetail({modOnly:modOnlySpec(key,row=>rowChanged(items,row,[{data:specific,row:rowById(specific,row.values[spec.id])},{data:stats,row:rowById(stats,row.values.BonusId)}])),rows,key:row=>row.line,slots:true,selected:selected?.line??null,page:state.page[key]||0,pageSize:state.pageSize[key]||12,fit:{minRowHeight:40},noun:tab,className:"ff9-layout",splitKey:`ff9-${key}`,rowsKey:`ff9-${key}`,defaultSplit:44,minLeft:340,minRight:420,search:{key:`ff9-${key}`,value:state.query[key]||"",label:`Search ${tab}`,change:value=>{state.query[key]=value;state.page[key]=0;render()}},sync:next=>{state.page[key]=next.page;state.pageSize[key]=next.pageSize;if(next.selected!==null)state.selected[key]=next.selected},change:next=>{state.page[key]=next.page;state.pageSize[key]=next.pageSize;if(next.selected!==null)state.selected[key]=next.selected;render()},master:view=>tablePanel(items,key,view.rows,view.selected,view.select),detail:row=>equipmentDetail(tab,items,row,specific,stats)});$("#main").replaceChildren(layout)}
  function setToolbar(nodes=[]){$("#toolbar").replaceChildren(...nodes)}
  function toolbar(){const keys=choices(state.tab);if(keys.length<=1){setToolbar();return}const current=activeKey(),label=key=>key==="characters"?"Characters":key==="leveling"?"Level curve":catalogRow(key)?.label||key;const buttons=keys.map(key=>({id:key,label:label(key)}));const strip=subtabBar({tabs:buttons,active:current,label:`${tabs.find(tab=>tab.id===state.tab)?.label} datasets`,change:key=>{state.datasetChoice[state.tab]=key;state.page[key]=0;loadDataset(key).then(render)}});const controls=[strip];if(current==="field-walkmesh-triangles"){const data=state.datasets[current];if(data?.scenes?.length){controls.push(el("select",{"aria-label":"Field walkmesh",title:dirtyCount()?"Save or discard changes before switching fields.":"Choose the field whose walkmesh triangles to edit",disabled:state.busy||dirtyCount()>0,onchange:event=>{state.walkmeshScene=event.target.value;state.page[current]=0;loadDataset(current,true,state.walkmeshScene).then(render)}},...data.scenes.map(scene=>el("option",{value:scene.value,selected:scene.value===data.activeScene},`${scene.label}${scene.source==="project"?" · project":""}`))))}}setToolbar(controls)}
  function info(){
    const game=state.dashboard.game,base=state.dashboard.baseline,runtime=state.dashboard.runtime||{};
    const compatibility=state.dashboard.modCompatibility||{},externalMods=compatibility.mods||[];
    const value=text=>readonlyField(String(text??""),{format:false});
    const summary=(values,empty="None detected")=>values.length
      ? values.slice(0,4).join(", ")+(values.length>4?` (+${values.length-4} more)`:"")
      : empty;
    const disabled=state.busy||state.activeSource!=="mine";
    const actions=LexeditorUI.actionRow(
      el("button",{type:"button",disabled:disabled||runtime.recoveryRequired,onclick:()=>runtimeAction("install")},runtime.installed?"Reinstall pinned Memoria":"Install Memoria"),
      el("button",{type:"button",disabled:disabled||!runtime.installed||runtime.recoveryRequired,onclick:()=>runtimeAction("settings")},"Open Memoria settings"));
    if(runtime.recoveryRequired)actions.append(el("button",{type:"button",disabled,onclick:()=>runtimeAction("recover")},"Recover previous installation"));
    $("#main").replaceChildren(detailPanel({className:"lex-information-panel ff9-information",
      icon:infoIcon(),title:"Information",meta:"Installation, baseline data, and the Memoria helper",body:[
      detailSection({title:"GAME",body:[
        detailField({label:"STATE",control:value(game.ready?"Ready":"Incomplete"),
          help:infoHelp(game.ready?"Ready means Lexeditor found the FF9 installation layout and the launcher/player files this editor depends on.":"Incomplete means one or more FF9 installation paths required by Lexeditor are missing or unreadable; the installation problems identify the concrete cause.")}),
        detailField({label:"FOLDER",control:value(game.root)}),
        detailField({label:"STEAM APP",control:value(`${game.steamAppId} · build ${game.steamBuildId||"unknown"}`)}),
      ]}),
      detailSection({title:"GAME DATA",body:[
        detailField({label:"BASELINE",control:value(base.message),
          help:infoHelp("Saves create or update only the selected project's StreamingAssets/Data overlay. Lexeditor never writes the installed game's p0data containers.")}),
        detailField({label:"PROJECT",control:value(state.dashboard.project.root)}),
      ]}),
      detailSection({title:"MEMORIA",body:[
        detailField({label:"STATE",control:value(state.busy?"Working…":runtime.recoveryRequired?"Recovery required":runtime.installed?"Installed":"Not installed"),help:infoHelp(runtime.message||"")}),
        detailField({label:"VERSION",control:value(runtime.version||"Unknown")}),
        detailField({label:"PINNED RELEASE",control:value(runtime.pinned||"—")}),
        detailField({label:"UPDATES",control:value(runtime.installed
          ?(runtime.updatesDisabled?"Memoria automatic checks disabled":"Memoria automatic checks need repair")
          :"Pinned installs are managed by Lexeditor"),
          help:infoHelp("Lexeditor pins Memoria and reports newer upstream releases through the shared Updates drawer. Memoria's own automatic update check is disabled after install so the runtime cannot silently move away from the tested version.")}),
        detailField({label:"ACTIONS",control:actions,help:infoHelp("Play opens Memoria's launcher, where its own settings can be edited. Installation keeps recovery copies and preserves existing INI files.")}),
        ...(runtime.recoveryRequired?[detailField({label:"RECOVERY COPY",control:value(runtime.recoveryBackup)})]:[]),
        ...(state.runtimeError?[el("p",{role:"alert"},state.runtimeError)]:[]),
      ]}),
      detailSection({title:"EXTERNAL MOD COMPATIBILITY",body:[
        detailField({label:"ENABLED",control:value(summary(externalMods.map(mod=>mod.name))),
          help:infoHelp("Read-only snapshot of Memoria FolderNames and enabled mods' ModDescription.xml metadata. Lexeditor does not install, edit, enable, disable, or remove these mods.")}),
        detailField({label:"RUNTIME ORDER",control:value(summary(compatibility.folderNames||[],"No active mod folders")),
          help:infoHelp("Memoria FolderNames is highest-priority first. Ordinary replacement assets use the first matching folder; format-specific patch files may deliberately compose in a different order.")}),
        detailField({label:"METADATA WARNINGS",control:value(summary([
            ...(compatibility.error?[compatibility.error]:[]),
            ...externalMods.filter(mod=>!mod.metadata||mod.error).map(mod=>`${mod.name}: ${mod.error||"ModDescription.xml unavailable"}`)
          ],"None detected")),
          help:infoHelp("Missing or malformed metadata is reported as unknown, never treated as proof that the mod is compatible.")}),
        detailField({label:"UNSUPPORTED RUNTIME",control:value(summary((compatibility.unsupportedByPinnedMemoria||[]).map(mod=>`${mod.name} (needs ${mod.minimumMemoriaVersion||"valid version metadata"})`),"None detected")),
          help:infoHelp("Mods declaring a MinimumMemoriaVersion newer than Lexeditor's pinned helper, or an invalid minimum version, are outside this candidate's supported runtime boundary.")}),
        detailField({label:"RUNTIME UNKNOWN",control:value(summary((compatibility.unknownRuntimeCompatibility||[]).map(mod=>mod.name),"None detected")),
          help:infoHelp("These enabled mods do not declare MinimumMemoriaVersion. Their metadata does not prove compatibility with Lexeditor's pinned helper; only native testing can establish it.")}),
        detailField({label:"DECLARED CONFLICTS",control:value(summary((compatibility.declaredConflicts||[]).map(row=>row.mods.join(" ↔ ")),"None declared")),
          help:infoHelp("These are author-declared incompatibilities among enabled mods. Missing metadata is not proof that a combination is safe in game.")}),
        detailField({label:"EXACT PATH OVERLAPS",control:value(summary((compatibility.overlaps||[]).map(row=>`${row.mod}: ${row.path}`),"None detected")),
          help:infoHelp("For Lexeditor-generated CSV, battle raw16, and field-walkmesh BGI replacements, first/highest priority wins the whole file. Other Memoria patch-file families can compose, and event scripts have separate append/MergeScripts behavior; this overlap list therefore reports shared paths without inventing a universal semantic winner."+(compatibility.projectScanTruncated?" The project scan hit its 10,000-file safety cap, so additional overlaps may exist.":""))}),
      ]}),
      LexeditorUI.modLoaderSection({
        loader:"Memoria's Mod Manager installs, enables and removes external FF9 mods. Lexeditor owns only its separate Lexeditor mod folder and opens Memoria's launcher for the external-mod UI. Mods that require a Memoria version newer than Lexeditor's pinned v2025.07.04 are outside the current supported loader boundary.",
        output:"Save writes the selected Lexeditor project. Deploy copies only that project's StreamingAssets overrides plus the Lexeditor runtime into <FF9>/Lexeditor; installed game archives and other mod folders stay untouched.",
        order:"Memoria's FolderNames list is highest-priority first. Lexeditor deploy keeps Lexeditor first there and, when Priorities already exists, first in that launcher list too; it does not invent a missing Priorities setting. Lexeditor-generated CSV, battle raw16, and field-walkmesh BGI replacements are first-hit whole-file overrides. Memoria patch files may compose low-to-high, while event scripts have separate append/MergeScripts behavior; Lexeditor does not claim a universal cross-mod semantic merge.",
        safety:"Installed game data and external mod folders are read only to Lexeditor. Memoria installation keeps a recovery copy, and deploy/revert preserve unrelated Memoria.ini settings and mod-order entries.",
        removal:"Revert removes only the marker-owned <FF9>/Lexeditor folder and its FolderNames/Priorities entries. External mods remain installed and are managed through Memoria's launcher.",
      }),
    ]}));
  }
  let runtimeRefresh=null;
  async function refreshRuntime(){
    if(runtimeRefresh)return runtimeRefresh;
    runtimeRefresh=(async()=>{
      const [runtime,map,deployment,compatibility]=await Promise.all([
        api("/api/runtime"),api("/api/datamap"),api("/api/deployment"),api("/api/mod-compat")
      ]);
      state.dashboard.runtime=runtime;
      state.dataMap=map;
      state.deployment=deployment;
      state.dashboard.modCompatibility=compatibility;
    })();
    try{await runtimeRefresh}finally{runtimeRefresh=null}
  }
  async function runtimeAction(action){
    if(state.busy||state.activeSource!=="mine")return;
    if(dirtyCount()){state.runtimeError="Save or discard your changes before changing Memoria.";await render();return}
    if(action==="install"&&!await LexeditorUI.confirmAction({title:"Install Memoria?",message:"Close FF9 and its launcher first.\n\nExisting settings are preserved, and every game file this changes is backed up.",confirmLabel:"Install",cancelLabel:"Cancel"}))return;
    if(action==="recover"&&!await LexeditorUI.confirmAction({title:"Restore the game files?",message:"This puts back the files as they were before the interrupted Memoria installation.",confirmLabel:"Restore",cancelLabel:"Cancel"}))return;
    state.busy=true;state.runtimeError="";await render();
    try{await api(`/api/runtime/${action}`,{});if(runtimeRefresh)await runtimeRefresh;await refreshRuntime()}
    catch(error){state.runtimeError=error.message;try{await refreshRuntime()}catch(refreshError){state.runtimeError+=` ${refreshError.message}`}}
    finally{state.busy=false;await render()}
  }
  function tweaks(){
    const tabs=[{id:"memoria",label:"Memoria"},{id:"improved",label:"Improved Interface"},{id:"eat",label:"Better Eat"},{id:"xp",label:"XP Bars"},{id:"hpmp",label:"HP/MP Bars"},{id:"row",label:"Row Rework"}];
    setToolbar([subtabBar({tabs,active:state.tweak,label:"Tweaks",change:id=>{state.tweak=id;tweaks()}})]);
    if(state.tweak==="memoria"){
      $("#main").replaceChildren(detailPanel({paginate:true,className:"ff9-detail ff9-tweaks",
        title:"Memoria",meta:"Handled by the Memoria launcher",body:[
          detailSection({title:"WHERE THESE SETTINGS LIVE",body:[
            detailField({label:"EDITOR",control:readonlyField("Memoria's own launcher. Lexeditor does not duplicate it.")}),
            detailField({label:"HOW",control:readonlyField("Press Play. The Memoria launcher opens and its settings are edited there.")}),
          ]}),
          LexeditorUI.reshadeSection({snapshot:state.reshade,save:saveReshade,act:actReshade}),
        ]}));
      return;
    }
    const defs={
      improved:{key:"ImprovedInterface",title:"Improved Interface",description:"Adds Circle reveal-only dialogue, Square fast-forward, snapshot-only dialogue history, full-width battle ATB/Trance with HP/MP bars, queued action drain, an unbeaten Tetra Master opponent prompt, and highlights Mognet when the current Moogle can receive one of your carried letters. Keyboard equivalents follow your normal Memoria bindings."},
      eat:{key:"BetterEat",title:"Better Eat",description:"Disables useless Eat/Cook targets, refuses to consume enemies that cannot teach Quina anything, and gives enemies carrying an unlearned Blue Magic ability a blue glow."},
      xp:{key:"XPBars",title:"XP Bars",description:"Adds an experience-progress bar under each party member's block on the post-battle EXP screen."},
      hpmp:{key:"HPMPBars",title:"HP/MP Bars",description:"Adds a red HP bar and blue MP bar directly below each party member's HP and MP text in battle."},
      row:{key:"RowRework",title:"Row Rework",description:"Doubles the battle distance between the front and back rows, prevents an all-back-row party formation, pulls the whole party to the front when no living front-row character remains, and prevents short-range physical melee from being used by or against back-row party members."}
    };
    const def=defs[state.tweak]||defs.improved,key=def.key,title=def.title,description=def.description;
    const enabled=!!state.features?.features?.[key],deployed=state.deployment?.deployed;
    // The checkbox is built on its own and handed straight to the shared
    // field. Reaching back into a wrapper for it assumed a live DOM, which the
    // headless editor tests do not provide.
    const toggleInput=el("input",{type:"checkbox",checked:enabled,disabled:state.busy||state.activeSource!=="mine",onchange:event=>{state.features.features[key]=event.target.checked;shell.refresh()}});
    const toggle=el("label",{},toggleInput," Enabled");
    const actions=LexeditorUI.actionRow(
      el("button",{type:"button",disabled:state.busy||dirtyCount()>0||state.activeSource!=="mine",onclick:()=>deploymentAction("deploy")},deployed?"Redeploy Project":"Deploy Project"),
      el("button",{type:"button",disabled:state.busy||!deployed||state.activeSource!=="mine",onclick:()=>deploymentAction("revert")},"Revert Lexeditor Mod"));
    // The bespoke card is gone: Tweaks is the shared settings page every game
    // uses, so the switch, the deployment state and the ReShade section all
    // read the same here as anywhere else.
    $("#main").replaceChildren(detailPanel({paginate:true,className:"ff9-detail ff9-tweaks",title,
      identity:enabled?"ON":"OFF",meta:"Memoria runtime tweaks",body:[
        detailSection({title:"TWEAK",body:[
          detailField({label:"WHAT IT DOES",control:readonlyField(description)}),
          detailField({label:"ENABLED",dataType:"BOOL",control:toggleInput}),
        ]}),
        detailSection({title:"DEPLOYMENT",body:[
          detailField({label:"STATE",control:readonlyField(deployed
            ?(state.deployment.runtimeCurrent?"Deployed runtime is current."
              :"Deployed runtime needs redeployment.")
            :"Save changes, then Deploy Project to activate them in Memoria.")}),
          detailField({label:"ACTIONS",control:actions}),
        ]}),
        LexeditorUI.reshadeSection({snapshot:state.reshade,save:saveReshade,act:actReshade}),
      ]}));
  }
  async function loadReshade(){
    try{const value=await LexeditorUI.callWindow?.("mod_reshade","ff9");if(value)state.reshade=value}
    catch(_error){/* browser preview has no desktop host; the section still renders */}
  }
  // Install, remove and "choose the DLL" each answer with a fresh snapshot.
  async function actReshade(method,...args){
    try{
      const value=method==="adopt_reshade"
        ? await LexeditorUI.callWindow?.(method)
        : await LexeditorUI.callWindow?.(method,"ff9",...args);
      if(value&&value.manifest)state.reshade=value;else await loadReshade();
    }catch(error){LexeditorUI.showToast?.(error.message||String(error),true);}
    tweaks();
  }
  async function saveReshade(manifest){
    try{const value=await LexeditorUI.callWindow?.("save_mod_reshade","ff9",manifest);if(value)state.reshade=value}
    catch(error){LexeditorUI.showToast?.(error.message||String(error),true)}
    tweaks();
  }
  async function deploymentAction(action){
    if(state.busy||state.activeSource!=="mine")return;
    if(dirtyCount()){state.runtimeError="Save your project changes before deployment.";await render();return}
    if(action==="revert"&&!await LexeditorUI.confirmAction({title:"Remove the Lexeditor mod?",message:"Only the Lexeditor-owned FF9 Memoria mod folder, its FolderNames entry, and its Priorities entry when that setting exists are removed. Nothing else is touched.",confirmLabel:"Remove",cancelLabel:"Cancel"}))return;
    state.busy=true;shell.refresh();
    try{state.deployment=await api(`/api/deployment/${action}`,{});state.dataMap=await api("/api/datamap");state.runtimeError=""}
    catch(error){state.runtimeError=error.message;throw error}
    finally{state.busy=false;await render()}
  }
  function planned(){const label=tabs.find(tab=>tab.id===state.tab)?.label||"FF9 data";$("#main").replaceChildren(detailPanel({title:label,body:[
    LexeditorUI.notice({tone:"warning",title:"Format not integrated",
      message:"The installed vanilla source for this area remains inside p0data asset containers. No safe editable CSV source is present."})]}))}
  function dataMap(){const view=LexeditorUI.dataMap({rows:state.dataMap.rows,query:state.mapQuery,status:state.mapStatus,page:state.mapPage,sort:state.mapSort,pageSize:100,open:row=>{if(row.target){if(row.datasetKey)state.datasetChoice[row.target]=row.datasetKey;navigate(row.target)}},changeQuery:value=>{state.mapQuery=value;state.mapPage=0;dataMap()},changeStatus:value=>{state.mapStatus=value;state.mapPage=0;dataMap()},changePage:page=>{state.mapPage=page;dataMap()},changeSort:key=>{const [active,direction]=state.mapSort;state.mapSort=[key,active===key?-direction:1];dataMap()}});state.mapPage=view.page;setToolbar(view.controls);$("#main").replaceChildren(view.content);shell.refresh()}
  async function render(){if(!state.dashboard)return;if(state.tab==="info"){setToolbar();info()}else if(state.tab==="datamap")dataMap();else if(state.tab==="tweaks"){if(!state.reshade)await loadReshade();tweaks()}else if(state.activeSource!=="mine"){setToolbar();planned()}else{toolbar();const key=activeKey();if(!key)planned();else{if(!state.datasets[key])$("#main").replaceChildren(statusPanel(catalogRow(key)?.label||tabs.find(tab=>tab.id===state.tab)?.label||"FF9 data","Verified source","Loading records…"));if(state.tab==="characters"&&key==="characters")await renderCharacterComposite();else if(["weapons","armor","accessories"].includes(state.tab))await renderEquipmentComposite(state.tab);else renderDataset(await loadDataset(key),key)}}shell.refresh()}
  // render() is async, so navigate returns its promise: a caller that needs the
// page to exist can wait for it instead of guessing.
function navigate(tab){state.tab=tab;const drawn=render();if(tab==="info"&&!state.busy)refreshRuntime().then(()=>{if(state.tab===tab)render()}).catch(error=>{state.runtimeError=error.message;if(state.tab==="info")render()});return drawn}
  async function save(){if(state.busy)return;state.busy=true;shell.refresh();try{for(const [key,data] of Object.entries(state.datasets)){if(!data?.rows)continue;const changes=data.rows.map(row=>({line:row.line,scene:row.scene,record:row.record,values:changedFields(data,row)})).filter(change=>Object.keys(change.values).length);if(changes.length)installData(await api("/api/save",{key,sha256:data.sha256,sceneHashes:data.sceneHashes||{},changes}))}if(Object.keys(featureChanges()).length){state.features=await api("/api/features/save",{sha256:state.savedFeatures.sha256,features:state.features.features});state.savedFeatures=clone(state.features)}state.error=""}catch(error){state.error=error.message;throw error}finally{state.busy=false;render()}}
  async function discard(){for(const key of Object.keys(state.datasets))await loadDataset(key,true);state.features=await api("/api/features");state.savedFeatures=clone(state.features);state.deployment=await api("/api/deployment");render()}
  async function switchProjectSource(value){state.activeSource=String(value||"mine")==="vanilla"?"vanilla":"mine";await render()}
  const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"ff9",name:"Final Fantasy IX",themeName:"ff9",theme:{bg:"#14181c",panel:"#575a59","panel-2":"#4a4d4c",border:"#707878",text:"#f4f4f4",muted:"#cfd2d2",accent:"#4060b0","accent-text":"#fff",highlight:"#fff",success:"#d8dcdc",font:'"FF9 Menu","Trebuchet MS",sans-serif',"heading-font":'"FF9 Heading","FF9 Menu","Trebuchet MS",sans-serif'}},tabs,activeTab:()=>state.tab,navigate,help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the FF9 Data Map",info:()=>navigate("info"),infoActive:()=>state.tab==="info",infoTitle:"Open FF9 plugin information",projectSources:()=>[{key:"vanilla",label:"Vanilla",path:state.dashboard?.game?.root||"Installed p0data containers"}],projectActiveSource:()=>state.activeSource,selectProjectSource:switchProjectSource,pendingChanges:()=>[...LexeditorUI.pendingChangeList(state.savedFeatures?.features,state.features?.features,"Features"),...Object.entries(state.datasets).flatMap(([name,data])=>(data?.rows||[]).flatMap(row=>Object.entries(changedFields(data,row)).map(([key,after])=>({label:`${name} / ${row.name||row.line} / ${key}`,before:data.originalByLine[String(row.line)].values[key],after}))))],dirtyCount,readonly:()=>state.busy||state.activeSource!=="mine",save,discard});
  window.addEventListener("focus",()=>{if(state.dashboard&&!state.busy&&state.tab==="info")refreshRuntime().then(()=>render()).catch(error=>{state.runtimeError=error.message})});
  Promise.all([api("/api/dashboard"),api("/api/datamap"),api("/api/catalog"),api("/api/features"),api("/api/deployment")]).then(([dashboard,map,catalog,features,deployment])=>{state.dashboard=dashboard;state.dataMap=map;state.catalog=catalog.datasets;state.features=features;state.savedFeatures=clone(features);state.deployment=deployment;render().then(()=>LexeditorUI.finishPluginLoading())}).catch(error=>{$("#main").replaceChildren(statusPanel("Final Fantasy IX","Startup error",`Failed to load FF9 data: ${error.message}`));LexeditorUI.finishPluginLoading()});
  
