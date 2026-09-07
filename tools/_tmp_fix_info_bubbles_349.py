from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path, old, new):
    path = ROOT / path
    text = path.read_text('utf-8')
    if old not in text:
        raise SystemExit(f'{path}: anchor not found: {old[:160]!r}')
    path.write_text(text.replace(old, new, 1), 'utf-8')


# ---------------------------------------------------------------------------
# Shared framework: an info bubble is authored semantic help, never generated
# field metadata. Operational/native control tooltips remain a separate system.
# ---------------------------------------------------------------------------
replace_once(
    'ui/framework.js',
'''  // Every interactive control gets a concise native tooltip even when a plugin
  // has no richer ?-marker description. We only derive facts visible in the DOM
  // (label, type, bounds, unit and authored apply requirement); we never guess
  // undocumented gameplay semantics from a field name.
''',
'''  // Native control tooltips are an operational/accessibility fallback. They are
  // deliberately separate from the circular ? info bubble, which is reserved for
  // authored semantic help about what a property means and affects.
''')

replace_once(
    'ui/framework.js',
'''    // Describe the actual control's contract. Never infer an engine behavior or
    // restart rule from a raw field name; retain the plugin's authored meaning.
    const labelText = (options.label instanceof Node ? options.label.textContent : String(options.label || "value")).trim();
    const suppliedHelp = options.help instanceof Element
      ? String(options.help.getAttribute("aria-label") || options.help.getAttribute("title") || "").trim()
      : String(options.description || "").trim();
    const meaning = suppliedHelp || (readOnly
      ? `${labelText} is read-only in this view.`
      : inputType === "checkbox" ? `Enable or disable ${labelText}.`
      : input?.tagName === "SELECT" ? `Choose ${labelText} from the listed values.`
      : `Edit the stored ${labelText} value. A gameplay interpretation is not documented for this field.`);
    const finiteBound = bound => bound !== null && bound !== undefined && bound !== "" && Number.isFinite(Number(bound));
    const facts = [];
    if (readOnly && !/read.only/i.test(meaning)) facts.push("Read-only in this view.");
    if (numericLike) {
      if (finiteBound(min) && finiteBound(max)) facts.push(`Allowed range: ${min} to ${max}.`);
      else if (finiteBound(min)) facts.push(`Minimum: ${min}.`);
      else if (finiteBound(max)) facts.push(`Maximum: ${max}.`);
      if (dataType === "INT") facts.push("Whole numbers only.");
      else if (finiteBound(step) && Number(step) > 0) facts.push(`Step: ${step}.`);
    }
    const unit = String(options.unit || control?.querySelector?.(".lex-unit")?.textContent || "").trim();
    if (unit) facts.push(`Unit: ${unit}.`);
    if (options.applyRequirement) facts.push(`Apply: ${String(options.applyRequirement).trim()}`);
    const helpText = [meaning, ...facts].join(" ");
    const helpMarker = options.help || infoHelp(helpText);
    // Native fallback and assistive text exist on the input itself, not just '?'.
    if (input) {
      if (!input.getAttribute("aria-label") && labelText) input.setAttribute("aria-label", labelText);
      input.setAttribute("aria-description", helpText);
      if (!input.title) input.title = helpText;
    }
''',
'''    // The metadata rail already displays the type and numeric range. An info
    // bubble appears only when the caller authored semantic help. Never fabricate
    // a ? from the label, storage type, bounds, step, unit, or edit operation.
    const labelText = (options.label instanceof Node ? options.label.textContent : String(options.label || "value")).trim();
    const suppliedHelp = options.help instanceof Element
      ? String(options.help.getAttribute("aria-label") || options.help.getAttribute("title") || "").trim()
      : String(options.description || "").trim();
    const helpMarker = options.help || (suppliedHelp ? infoHelp(suppliedHelp) : null);
    if (input) {
      if (!input.getAttribute("aria-label") && labelText) input.setAttribute("aria-label", labelText);
      // Semantic authored help is also useful to assistive technology. When no
      // semantic help exists, installControlHelp may still add an operational
      // native tooltip/description, but that never creates a circular ?.
      if (suppliedHelp && !input.getAttribute("aria-description"))
        input.setAttribute("aria-description", suppliedHelp);
    }
''')

# ---------------------------------------------------------------------------
# UI manual: codify the distinction so this cannot be reinterpreted later.
# ---------------------------------------------------------------------------
replace_once(
    'docs/UI-MANUAL.md',
'''An **info bubble** is the filled circular `?` beside a property. Its circle,
glyph, placement and interaction are shared. It is centred in the metadata space
between the panel edge and the property label, and its glyph is centred inside the
circle.
''',
'''An **info bubble** is the filled circular `?` beside a property. Its circle,
glyph, placement and interaction are shared. It is centred in the metadata space
between the panel edge and the property label, and its glyph is centred inside the
circle.

Info-bubble text explains **meaning and consequences**, not visible UI metadata.
It should tell a mod author what the property represents in the game/editor, what
changing it affects, non-obvious value semantics, important relationships with
other properties, or caveats that cannot be inferred from the label alone.

Never put the property's data type, numeric range, step size, displayed unit,
current value, or generic instructions such as `Set X`, `Edit X`, `Choose X`, or
`Enable/disable X` in an info bubble. Those facts are already represented by the
field and its metadata. If no useful semantic explanation is known, omit the info
bubble rather than filling it with tautological or storage-level text.
''')

# ---------------------------------------------------------------------------
# Blank: its bubbles demonstrate the semantic contract, not range/type metadata.
# ---------------------------------------------------------------------------
blank = ROOT / 'games/blank/editor.html'
text = blank.read_text('utf-8')
repls = {
    'infoHelp("A normal editable text value.")': 'infoHelp("Blank uses this sample to demonstrate the shared text control and Vanilla-reference behavior; it has no game-specific meaning.")',
    'infoHelp("This integer accepts only whole values from 0 through 255. The Vanilla reference stays inside the field.")': 'infoHelp("This sample demonstrates an internal Vanilla reference: changing the live value leaves the unchanged reference available inside the same field.")',
    'infoHelp("A bounded whole-number property. Focus it to reveal its type and valid range.")': 'infoHelp("This sample record demonstrates a numeric property with a Vanilla reference; it has no game-specific meaning.")',
}
for old, new in repls.items():
    if old not in text: raise SystemExit(f'Blank anchor missing: {old}')
    text = text.replace(old, new, 1)
blank.write_text(text, 'utf-8')

# ---------------------------------------------------------------------------
# FF7: preserve actual field descriptions; unknown numeric storage gets no ?.
# ---------------------------------------------------------------------------
replace_once(
    'games/ff7/editor.html',
'''  function semanticHelp(field){
    if(field.help)return field.help;
    if(field.dataType==="text")return "English game text. Use byte escapes for control codes; unsupported characters and oversized text are refused on save.";
    return `Stored as a bounded ${field.dataType}. Storage range: ${field.minimum} to ${field.maximum}${field.step>1?`; step ${field.step}`:""}.`;
  }
''',
'''  function semanticHelp(field){
    if(field.help)return field.help;
    if(field.dataType==="text")return "This is game-visible text. Byte escapes preserve FF7 control codes; unsupported characters or text that cannot fit are refused on save rather than corrupting the kernel.";
    return "";
  }
''')
replace_once(
    'games/ff7/editor.html',
'''body:metadata.fields.filter(field=>(field.group||"Kernel data")===group).map(field=>detailField({className:"ff7-field",label:field.label,help:infoHelp(semanticHelp(field)),control:semanticControl(row,field),dataType:semanticType(field),min:field.minimum,max:field.maximum}))''',
'''body:metadata.fields.filter(field=>(field.group||"Kernel data")===group).map(field=>{const help=semanticHelp(field);return detailField({className:"ff7-field",label:field.label,help:help?infoHelp(help):null,control:semanticControl(row,field),dataType:semanticType(field),min:field.minimum,max:field.maximum})})''')

# ---------------------------------------------------------------------------
# FF8: remove storage-only filler and keep only gameplay relationships/caveats.
# ---------------------------------------------------------------------------
ff8 = ROOT / 'games/ff8/editor.html'
text = ff8.read_text('utf-8')
repls = {
    'help:infoHelp(state.data.menuItems.parameterTypes.find(entry=>entry.name===row.param1Type)?.description||"Stored parameter 1.")': 'help:(help=>help?infoHelp(help):null)(state.data.menuItems.parameterTypes.find(entry=>entry.name===row.param1Type)?.description||"")',
    'help:infoHelp(state.data.menuItems.parameterTypes.find(entry=>entry.name===row.param2Type)?.description||"Stored parameter 2.")': 'help:(help=>help?infoHelp(help):null)(state.data.menuItems.parameterTypes.find(entry=>entry.name===row.param2Type)?.description||"")',
    'infoHelp("Choose the buy price and the percentage returned when the item is sold. FF8 stores the percentage in steps of 5%.")': 'infoHelp("Sell price is derived from this item\'s buy price and sell percentage; changing either changes the gil returned when the item is sold to a shop.")',
    'detailSection({className:"enemy-table-section",title:"RENZOKUKEN",help:infoHelp("These are the exact stored Renzokuken table values."),body:renzokuken})': 'detailSection({className:"enemy-table-section",title:"RENZOKUKEN",body:renzokuken})',
    'infoHelp("Choose a fixed level from 1 to 100, a maximum level from 1 to 100, or Ultimecia Castle\'s random level from 1 to 100. Unresolved special vanilla codes remain unchanged until you choose a proved rule.")': 'infoHelp("This can force one level, cap the enemy at a maximum level, or use Ultimecia Castle\'s random-level rule. Unresolved special vanilla codes remain unchanged until you choose a proved rule.")',
    'formulaTerm("hit_rate","WEAPON HIT RATE","The selected weapon\'s stored Hit value in both percent and X/255 formats.")': 'formulaTerm("hit_rate","WEAPON HIT RATE","Weapon accuracy contributes directly to effective hit chance before target Evasion and Luck; FF8\'s special 255 value uses the always-hit bypass.")',
    'formulaTerm("melee","MELEE WEAPON","The selected weapon\'s stored melee flag.")': 'formulaTerm("melee","MELEE WEAPON","Marks the attack as close-range for this formula; grounded melee attacks take the flying-target accuracy penalty.")',
    'infoHelp("The encounter region assigned to this visible 32 by 24 map segment.")': 'infoHelp("This region combines with the segment\'s ground type to choose which world-map encounter rule and encounter group apply here.")',
    'infoHelp("The region selected for this 32 by 24 world-map segment.")': 'infoHelp("This region combines with ground type to choose which world-map encounter rule and encounter group apply in this segment.")',
    'infoHelp("The world-map ground type paired with this region.")': 'infoHelp("Combined with Region ID, this terrain type selects the world-map encounter group used here.")',
}
for old, new in repls.items():
    if old not in text: raise SystemExit(f'FF8 anchor missing: {old[:120]}')
    text = text.replace(old, new, 1)
ff8.write_text(text, 'utf-8')

# ---------------------------------------------------------------------------
# FF9: give the raw Memoria fields actual game relationships. Unknown fields get
# no bubble rather than generic CSV/list-editing filler.
# ---------------------------------------------------------------------------
ff9 = ROOT / 'games/ff9/editor.html'
text = ff9.read_text('utf-8')
anchor = '''  const readOnlyNote=(data,field)=>EXPLAINED_READ_ONLY[`${data.key}:${field.key}`]||null;\n'''
insert = r'''  const readOnlyNote=(data,field)=>EXPLAINED_READ_ONLY[`${data.key}:${field.key}`]||null;
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
  };
  function semanticFieldHelp(data,field){
    if(data.key.startsWith("ability-")&&field.key==="AP")return "AP this character must earn from eligible equipment to permanently learn the linked ability.";
    if(data.key==="item-stats"&&["Dexterity","Strength","Magic","Will"].includes(field.key))return `When a character levels while equipment using this bonus row is equipped, FF9 adds this ${field.key} bonus into the character's accumulated stat-growth bonus.`;
    if(data.key==="item-stats"&&field.key==="AttackElement")return "Element added to physical attacks by equipment that references this bonus row.";
    if(data.key==="item-stats"&&field.key==="GuardElement")return "Elements guarded against by equipment that references this bonus row.";
    if(data.key==="item-stats"&&field.key==="AbsorbElement")return "Elements converted from damage into healing by equipment that references this bonus row.";
    if(data.key==="item-stats"&&field.key==="HalfElement")return "Elements whose incoming damage is halved by equipment that references this bonus row.";
    if(data.key==="item-stats"&&field.key==="WeakElement")return "Elements to which equipment using this bonus row makes the wearer weak.";
    if(data.key==="command-sets"&&field.key!=="Id")return field.key.includes("Trance")?"Command ID placed in this battle-menu slot while the character is in Trance.":"Command ID placed in this battle-menu slot in the character's normal state.";
    return FIELD_HELP[`${data.key}:${field.key}`]||"";
  }
'''
if anchor not in text: raise SystemExit('FF9 semantic-help insertion anchor missing')
text = text.replace(anchor, insert, 1)
old = '''  function fieldControl(data,row,field){const note=readOnlyNote(data,field);let control;if(note||!field.editable||field.kind==="stored")control=readonlyField(String(row.values[field.key]??""),{className:"ff9-readonly"});else if(field.kind==="boolean")control=el("input",{type:"checkbox",checked:!!row.values[field.key],onchange:event=>setValue(data,row,field,event.target.checked)});else if(field.kind==="integer"||field.kind==="number")control=el("input",{type:"number",min:field.min,max:field.max,step:field.step||1,value:row.values[field.key],oninput:event=>{if(event.target.value!=="")setValue(data,row,field,Number(event.target.value))}});else control=el("input",{type:"text",value:row.values[field.key]??"",oninput:event=>setValue(data,row,field,event.target.value)});const listNote=field.kind==="list"?(data.key==="shops"&&field.key==="Items"?"Ordered item IDs sold by this shop. Separate entries with commas.":"This Memoria array is edited as a comma-separated list."):null;return detailField({label:field.label.toLocaleUpperCase(),help:note?infoHelp(note):listNote?infoHelp(listNote):null,control,dataType:note?"READ ONLY":field.declaredType,min:field.min,max:field.max})}
'''
new = '''  function fieldControl(data,row,field){const note=readOnlyNote(data,field),semantic=note||semanticFieldHelp(data,field);let control;if(note||!field.editable||field.kind==="stored")control=readonlyField(String(row.values[field.key]??""),{className:"ff9-readonly"});else if(field.kind==="boolean")control=el("input",{type:"checkbox",checked:!!row.values[field.key],onchange:event=>setValue(data,row,field,event.target.checked)});else if(field.kind==="integer"||field.kind==="number")control=el("input",{type:"number",min:field.min,max:field.max,step:field.step||1,value:row.values[field.key],oninput:event=>{if(event.target.value!=="")setValue(data,row,field,Number(event.target.value))}});else control=el("input",{type:"text",value:row.values[field.key]??"",oninput:event=>setValue(data,row,field,event.target.value)});return detailField({label:field.label.toLocaleUpperCase(),help:semantic?infoHelp(semantic):null,control,dataType:note?"READ ONLY":field.declaredType,min:field.min,max:field.max})}
'''
if old not in text: raise SystemExit('FF9 fieldControl anchor missing')
text = text.replace(old, new, 1)
text = text.replace('"Related item category/usability checks are one property; the stored bits are an implementation detail."', '"These switches decide which FF9 item/equipment categories this record belongs to and whether it behaves as a normal usable item. More than one category can apply to the same underlying item record."', 1)
text = text.replace('"The party-member equipment checks are one multi-boolean property."', '"Each switch controls whether that character is allowed to equip this record. Guest-character switches matter only while that character is actually available."', 1)
ff9.write_text(text, 'utf-8')

# ---------------------------------------------------------------------------
# RDR2 settings: strip the exact metadata the UI already displays. Unknown
# setting semantics produce no bubble. Keep real lifecycle consequences.
# ---------------------------------------------------------------------------
rdr2 = ROOT / 'games/rdr2/editor.html'
text = rdr2.read_text('utf-8')
text = text.replace('if(key==="Enabled")return `Enable or disable ${humanSettingName(section)}. This switch does not delete its saved settings.`;', 'if(key==="Enabled")return `Master switch for ${humanSettingName(section)}. Turning it off leaves the rest of this section saved so the same configuration returns when it is re-enabled.`;', 1)
text = text.replace('return `${channel} channel, 0-255, of the ${humanSettingName(m[1]).toLowerCase()} colour.`;', 'return `${channel} component of the ${humanSettingName(m[1]).toLowerCase()} colour. RGB components control hue/brightness while Alpha controls opacity.`;', 1)
old = '''function settingHelp(section,setting){
  const compound=`${section.name}|${setting.key}`;
  const ordinary=(setting.help||"").trim()||schemaMap("help")[compound]||
    settingPatternHelp(section.name,setting.key)||
    `Edits ${setting.key} in the [${section.name}] section of this mod's INI. This installed setting has no field-specific behavior description.`;
  const boundary=settingConstBoundary(section.name,setting.key);
  const range=settingRange(section.name,setting.key);
  const facts=[];
  if(range&&range.min!==undefined&&range.max!==undefined)facts.push(`Editor range: ${range.min} to ${range.max}.`);
  const authoredUnit=schemaMap("units")[compound];
  if(typeof authoredUnit==="string"&&authoredUnit.trim())facts.push(`Unit: ${authoredUnit}.`);
  if(boundary)facts.push(`Apply requirement: ${boundary}`);
  return [ordinary,...facts].join(" ");
}
'''
new = '''function settingHelp(section,setting){
  const compound=`${section.name}|${setting.key}`;
  const ordinary=(setting.help||"").trim()||schemaMap("help")[compound]||settingPatternHelp(section.name,setting.key)||"";
  const boundary=settingConstBoundary(section.name,setting.key);
  if(!ordinary&&!boundary)return "";
  // Bounds and units are already printed by the property control/metadata. Only
  // lifecycle consequences belong here in addition to authored behavior help.
  return [ordinary,boundary?`Changing this setting requires: ${boundary}`:""].filter(Boolean).join(" ");
}
'''
if old not in text: raise SystemExit('RDR2 settingHelp anchor missing')
text = text.replace(old, new, 1)
rdr2.write_text(text, 'utf-8')

# ---------------------------------------------------------------------------
# Browser regression: metadata remains visible, but no semantic ? exists unless
# explicitly authored. The native operational tooltip remains independent.
# ---------------------------------------------------------------------------
test = ROOT / 'tests/global_controls_check.py'
text = test.read_text('utf-8')
old = '''        page.evaluate('''()=>{
          const U=LexeditorUI,e=U.el;window.__value=15;
          const input=e('input',{id:'quantity',type:'number',value:15,min:0,max:100,step:1,oninput:event=>__value=Number(event.target.value)});
          document.querySelector('#main').replaceChildren(U.detailField({label:'Quantity',dataType:'INT',min:0,max:100,control:U.unitField(input,'%')}));
        }''')
        number = page.locator('#quantity')
'''
new = '''        page.evaluate('''()=>{
          const U=LexeditorUI,e=U.el;window.__value=15;
          const input=e('input',{id:'quantity',type:'number',value:15,min:0,max:100,step:1,oninput:event=>__value=Number(event.target.value)});
          document.querySelector('#main').replaceChildren(U.detailField({label:'Quantity',dataType:'INT',min:0,max:100,control:U.unitField(input,'%')}));
        }''')
        # Type/range metadata stays visible in the rail, but metadata alone must
        # never manufacture a circular semantic-help bubble.
        assert page.locator('.lex-field-type-name').inner_text() == 'INT'
        assert '0-100' in page.locator('.lex-field-type-range').inner_text().replace(' ', '')
        assert page.locator('.lex-info-help').count() == 0
        page.evaluate('''()=>{
          const U=LexeditorUI,e=U.el,input=e('input',{id:'semantic-quantity',type:'number',value:15,min:0,max:100,step:1});
          document.querySelector('#main').append(U.detailField({label:'Semantic quantity',dataType:'INT',min:0,max:100,
            help:U.infoHelp('Controls how many copies the game grants when this reward is awarded.'),control:U.unitField(input,'%')}));
        }''')
        semantic_help=page.locator('.lex-info-help').last
        assert semantic_help.get_attribute('aria-label') == 'Controls how many copies the game grants when this reward is awarded.'
        semantic_help.hover();page.locator('.lex-help-popover').wait_for()
        bubble=page.locator('.lex-help-popover').inner_text()
        assert bubble == 'Controls how many copies the game grants when this reward is awarded.'
        assert not any(word in bubble for word in ('Range:', 'Step:', 'Unit:', 'Set Semantic', 'Edit Semantic'))
        number = page.locator('#quantity')
'''
if old not in text: raise SystemExit('global_controls detailField test anchor missing')
text = text.replace(old, new, 1)
text = text.replace("'settings_save_discard_isolation_and_visible_failure':'pass','automatic_control_tooltips':'pass','history_cancellation_and_failure':'pass',", "'settings_save_discard_isolation_and_visible_failure':'pass','native_control_tooltips':'pass','semantic_info_bubbles':'pass','history_cancellation_and_failure':'pass',", 1)
test.write_text(text, 'utf-8')

# Static contract catches reintroduction of the exact anti-pattern even without
# a browser. It intentionally does not reject semantic special values/thresholds.
static = ROOT / 'tests/test_info_bubble_semantics.py'
static.write_text(r'''"""Info bubbles explain semantics; visible property metadata stays out of them."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text("utf-8")


def test_detail_field_never_fabricates_info_bubbles_from_metadata():
    framework = text("ui/framework.js")
    assert 'options.help || infoHelp(helpText)' not in framework
    assert 'const helpMarker = options.help || (suppliedHelp ? infoHelp(suppliedHelp) : null);' in framework
    # Operational/native tooltips may describe ranges; the semantic marker may not
    # be built from those generated facts.
    semantic_block = framework[framework.index('const suppliedHelp = options.help instanceof Element'):framework.index('const typeRail = element("div", {class: "lex-field-type-rail"}')]
    for forbidden in ('Allowed range:', 'Minimum:', 'Maximum:', 'Whole numbers only.', 'Step:', 'Unit:', 'Edit the stored', 'Enable or disable', 'Choose ${labelText}'):
        assert forbidden not in semantic_block


def test_manual_defines_semantic_only_contract():
    manual = text("docs/UI-MANUAL.md")
    assert "Info-bubble text explains **meaning and consequences**" in manual
    assert "Never put the property's data type, numeric range, step size, displayed unit" in manual
    assert "If no useful semantic explanation is known, omit the info" in manual


def test_known_metadata_filler_is_gone_from_plugins():
    sources = "\n".join(text(path) for path in (
        "games/blank/editor.html", "games/ff7/editor.html", "games/ff8/editor.html",
        "games/ff9/editor.html", "games/rdr/editor.html", "games/rdr2/editor.html",
    ))
    for forbidden in (
        "Storage range:", "Editor range:", "This Memoria array is edited as a comma-separated list.",
        "Stored parameter 1.", "Stored parameter 2.", "These are the exact stored Renzokuken table values.",
        "A bounded whole-number property. Focus it to reveal its type and valid range.",
    ):
        assert forbidden not in sources


def test_ff9_has_real_semantic_help_for_core_relationships():
    ff9 = text("games/ff9/editor.html")
    for key in (
        '"characters:Strength"', '"characters:Magic"', '"leveling:BonusHP"',
        '"leveling:BonusMP"', '"items:AbilityIds"', '"items:BonusId"',
        '"shops:Items"', '"abilities:Gems"', '"actions:scriptId"',
        '"status-data:ContiCount(duration)"',
    ):
        assert key in ff9
    assert 'return FIELD_HELP[`${data.key}:${field.key}`]||"";' in ff9


def test_rdr2_setting_help_does_not_append_visible_metadata():
    rdr2 = text("games/rdr2/editor.html")
    block = rdr2[rdr2.index("function settingHelp(section,setting)"):rdr2.index("function settingUnit(section,key)")]
    assert "Editor range:" not in block
    assert "Unit:" not in block
    assert "has no field-specific behavior description" not in block
''', 'utf-8')
