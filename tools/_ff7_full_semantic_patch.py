from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing replacement marker in {path}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---- semantics.py: correct/complete the metadata catalogue -----------------
semantics = ROOT / "games/ff7/semantics.py"
text = semantics.read_text(encoding="utf-8")
text = text.replace('(0x00,"Front row"),(0xFE,"Back row")', '(0xFF,"Front row"),(0xFE,"Back row")')
text = text.replace('_field(label=None, help="Relative weight out of 64 for this encounter entry.")', '_field(help="Relative weight out of 64 for this encounter entry.")')
text = text.replace(
    '"statusImmunity": _field(label="Status immunities", dataType="flags", flags=flags(*STATUSES), group="Defenses", help="Statuses this enemy cannot normally receive."),',
    '"statusImmunity": _field(label="Status immunities", dataType="flags", flags=flags(*STATUSES), invertBits=True, bitWidth=32, group="Defenses", help="Statuses this enemy cannot normally receive. scene.bin stores this mask inverted; Lexeditor shows the logical immunities."),')
# Resistance slots are an element/status selector plus a named reaction code.
needle = '        **{f"attack{i}": reference("enemyAttacks", label=f"Action {i+1} attack", empty=65535, help="Scene-local enemy attack used by this action slot.", value_key="gameId", scope="scene") for i in range(16)},'
insert = '''        **{f"element{i}": _field(label=f"Resistance slot {i+1} target", dataType="enum", choices=choices(\n            *(([(value, label) for value, label in ((0,"Fire"),(1,"Ice"),(2,"Lightning"),(3,"Earth"),(4,"Poison"),(5,"Gravity"),(6,"Water"),(7,"Wind"),(8,"Holy"),(9,"Restorative"),(10,"Cut"),(11,"Hit"),(12,"Punch"),(13,"Shoot"),(14,"Shout"),(15,"Hidden"))] +\n              [(0x20 + value, label + " (status)") for value, label in STATUS_INDEX if value != 0xFF] + [(0xFF,"None")]))), group="Resistances", help="Element or status affected by this resistance slot. Status IDs are stored with FF7's 0x20 offset." ) for i in range(8)},\n        **{f"rate{i}": _field(label=f"Resistance slot {i+1} response", dataType="enum", choices=choices((0,"Killed by"),(1,"Cannot miss"),(2,"Double damage"),(4,"Half damage"),(5,"Nullify"),(6,"Absorb"),(7,"Full cure"),(0xFF,"None")), group="Resistances", help="How this enemy reacts to the element/status in the matching resistance slot.") for i in range(8)},\n        **{f"attack{i}": reference("enemyAttacks", label=f"Action {i+1} attack", empty=65535, help="Scene-local enemy attack used by this action slot.", value_key="gameId", scope="scene") for i in range(16)},'''
if needle not in text:
    raise SystemExit("enemy action semantic marker missing")
text = text.replace(needle, insert, 1)
# Explicitly explain rates/animations/cameras instead of leaving them as ordinary bytes.
marker = '        **{f"item{i}": _field(label=f"Loot slot {i+1}", dataType="inventoryReference", emptyValue=65535, group="Loot", help="Global item/equipment referenced by this drop/steal slot.") for i in range(4)},'
replacement = marker + '''\n        **{f"dropRate{i}": _field(label=f"Loot slot {i+1} rate", group="Loot", help="Drop/steal probability parameter expressed as x/63 by Scarlet. 0xFF is also used with an empty item slot.") for i in range(4)},\n        **{f"animation{i}": advanced(f"Action {i+1} animation ID", "Raw enemy action-animation index; no authoritative human animation-name table is available.") for i in range(16)},\n        **{f"camera{i}": advanced(f"Action {i+1} camera ID", "Raw battle-camera program ID; no authoritative human camera-name table is available.") for i in range(16)},'''
if marker not in text:
    raise SystemExit("enemy loot semantic marker missing")
text = text.replace(marker, replacement, 1)
# More obvious primary grouping for genuine scalar values.
text = text.replace('CORE = {', '''CORE = {''')
# Metadata aliases/defaults and raw-field quarantine are handled centrally below.
old = '''def metadata_for(category: str, key: str) -> dict:
    if category in CORE and key in CORE[category]: return dict(CORE[category][key])
    if category in SCENE and key in SCENE[category]: return dict(SCENE[category][key])
    if category == "characters" and key in CHARACTERS: return dict(CHARACTERS[key])
    if category == "shops" and key in SHOP: return dict(SHOP[key])
    if category in ("fieldEncounters", "worldEncounters") and key in ENCOUNTERS: return dict(ENCOUNTERS[key])
    if category in SPECIAL and key in SPECIAL[category]: return dict(SPECIAL[category][key])
    return {}


def apply(category: str, fields_in):
    """Return JSON metadata copies with human-facing overrides applied."""
    result = []
    for field in fields_in:
        value = dict(field) if isinstance(field, dict) else {
            "key": field.key, "label": field.label, "dataType": "int",
            "minimum": field.minimum, "maximum": field.maximum, "step": field.scale,
        }
        value.update(metadata_for(category, value["key"]))
        if "group" not in value:
            value["group"] = "Data"
        result.append(value)
    return result
'''
new = '''def metadata_for(category: str, key: str) -> dict:
    if category in CORE and key in CORE[category]: return dict(CORE[category][key])
    if category in SCENE and key in SCENE[category]: return dict(SCENE[category][key])
    if category in ("characters", "recruits") and key in CHARACTERS: return dict(CHARACTERS[key])
    if category == "shops" and key in SHOP: return dict(SHOP[key])
    if category in ("fieldEncounters", "worldEncounters") and key in ENCOUNTERS: return dict(ENCOUNTERS[key])
    if category in SPECIAL and key in SPECIAL[category]: return dict(SPECIAL[category][key])
    return {}


DEFAULT_GROUPS = {
    "items": "Effect", "weapons": "Combat", "armor": "Defense", "accessories": "Equipment",
    "characters": "Starting stats", "recruits": "Starting data", "enemies": "Stats / rewards",
    "enemyAttacks": "Attack", "encounters": "Battle setup", "shops": "Shop",
    "prices": "Price", "fieldEncounters": "Encounter settings", "worldEncounters": "Encounter settings",
}
RAW_HINTS = (" id", " flags", " mask", " byte", "camera", "animation", "layout", "arena", "cover flags")


def apply(category: str, fields_in):
    """Return JSON metadata copies with human-facing overrides applied."""
    result = []
    for field in fields_in:
        value = dict(field) if isinstance(field, dict) else {
            "key": field.key, "label": field.label, "dataType": "int",
            "minimum": field.minimum, "maximum": field.maximum, "step": field.scale,
        }
        authored = metadata_for(category, value["key"])
        value.update(authored)
        label = str(value.get("label") or value["key"])
        if not authored and any(hint in label.casefold() for hint in RAW_HINTS):
            value.update(advanced(label, "Engine/storage identifier retained for advanced editing because no authoritative human name mapping is available yet."))
        value.setdefault("group", DEFAULT_GROUPS.get(category, "Data"))
        value.setdefault("help", "Numeric game value. Lexeditor writes the original FF7 field directly and preserves unrelated bytes.")
        result.append(value)
    return result
'''
if old not in text:
    raise SystemExit("semantics metadata functions marker missing")
text = text.replace(old, new, 1)
# Scalar grouping/help and unresolved advanced engine fields.
extra = '''
# Scalar fields that are genuinely numeric but still need domain language.
for key, label, help_text in (
    ("attackPower", "Power", "Base power consumed by the selected item formula."),
    ("attackStrength", "Attack power", "Base power used by this weapon's damage formula."),
    ("criticalRate", "Critical rate", "Weapon critical-hit rate parameter."),
    ("accuracyRate", "Accuracy", "Weapon accuracy rate parameter."),
):
    target = CORE["items"] if key == "attackPower" else CORE["weapons"]
    target[key] = _field(label=label, group="Effect" if key == "attackPower" else "Combat", help=help_text)
for key, label in (("defense","Defense"),("magicDefense","Magic defense"),("evade","Evade"),("magicEvade","Magic evade")):
    CORE["armor"][key] = _field(label=label, group="Defense", help=f"Armor {label.casefold()} value.")
for key in ("dialogue",):
    SHOP[key] = advanced("Dialogue set", "Raw shop dialogue/menu text set index; no authoritative named dialogue table is exposed by this plugin.")
for i in range(4):
    SCENE["encounters"][f"arena{i}"] = advanced(f"Arena candidate {i+1} ID", "Raw battle arena candidate ID; no authoritative arena-name table is available here.")
for camera in range(3):
    for axis in ("x","y","z","directionX","directionY","directionZ"):
        SCENE["encounters"][f"camera{camera}_{axis}"] = _field(label=f"Camera {camera+1} {axis}", group="Advanced / engine data", help="Raw formation camera coordinate/direction value.", advanced=True)
for slot in range(6):
    for suffix, label in (("cover","Cover flags"),("flags","Initial condition flags")):
        SCENE["encounters"][f"slot{slot}_{suffix}"] = advanced(f"Enemy slot {slot+1} {label}", "Packed formation-engine flags; retained under Advanced until every bit is authoritatively named.")
for level in ("11","12","21","22","31","32","4"):
    CHARACTERS[f"limitAttack{level}"] = advanced(f"Limit {level} attack ID", "Raw global Limit attack index. Kept under Advanced until the plugin exposes the corresponding named attack table.")
CHARACTERS["levelProgress"] = _field(label="Starting level progress", group="Starting progression", help="Progress within the current level at initialization (0–255 gauge).")
for i in range(1,5):
    CHARACTERS[f"limitHpDivisor{i}"] = _field(label=f"Limit level {i} HP divisor", group="Limit gain", help="HP-loss divisor used by FF7's Limit gauge gain calculation for this Limit level.")
'''
text += extra
semantics.write_text(text, encoding="utf-8")


# ---- kernel.py: apply semantic metadata to all core KERNEL categories -------
replace("games/ff7/kernel.py", "from .format_codec import pack_strings, string_table\n", "from .format_codec import pack_strings, string_table\nfrom . import semantics\n")
replace("games/ff7/kernel.py", '''            if category.key == "materia":
                metadata.update(MATERIA_FIELD_UI.get(field.key, {}))
            fields.append(metadata)
''', '''            if category.key == "materia":
                metadata.update(MATERIA_FIELD_UI.get(field.key, {}))
            metadata.update(semantics.metadata_for(category.key, field.key))
            metadata.setdefault("group", semantics.DEFAULT_GROUPS.get(category.key, "Data"))
            metadata.setdefault("help", "Numeric game value. Lexeditor writes the original FF7 field directly and preserves unrelated bytes.")
            fields.append(metadata)
''')


# ---- datasets.py: semantic character/recruit metadata ----------------------
replace("games/ff7/datasets.py", "from . import kernel_extra\n", "from . import kernel_extra\nfrom . import semantics\n")
old = '''    result.append({"id": "characters", "label": "Characters", "note": CHARACTER_NOTE,
        "fields": [{"key": f.key, "label": f.label, "dataType": "int",
            "minimum": f.minimum, "maximum": f.maximum, "step": f.scale,
            "group": "Starting stats" if f in INITIAL_FIELDS else "Growth and limits"}
            for f in INITIAL_FIELDS + LIMIT_FIELDS]})
'''
new = '''    character_fields = [{"key": f.key, "label": f.label, "dataType": "int",
        "minimum": f.minimum, "maximum": f.maximum, "step": f.scale,
        "group": "Starting stats" if f in INITIAL_FIELDS else "Growth and limits"}
        for f in INITIAL_FIELDS + LIMIT_FIELDS]
    result.append({"id": "characters", "label": "Characters", "note": CHARACTER_NOTE,
        "fields": semantics.apply("characters", character_fields)})
'''
replace("games/ff7/datasets.py", old, new)


# ---- battle.py: expose scene/game IDs for named cross-references -----------
old = '''                rows.append({'id':scene * count + slot, 'name':values.get('name', f'Battle {scene * 4 + slot}'),
                             'description':f'Scene {scene}, slot {slot}: {suffix}. AI is edited separately.', 'values':values})
'''
new = '''                game_id = (read_int(raw, slot * 2) if category == 'enemies' else
                           read_int(raw, 0x840 + slot * 2) if category == 'enemyAttacks' else scene * 4 + slot)
                rows.append({'id':scene * count + slot, 'scene':scene, 'gameId':game_id,
                             'name':values.get('name', f'Battle {scene * 4 + slot}'),
                             'description':f'Scene {scene}, slot {slot}: {suffix}. AI is edited separately.', 'values':values})
'''
replace("games/ff7/battle.py", old, new)


# ---- extended.py: semantic metadata for scene/shop/encounter families ------
replace("games/ff7/extended.py", "from .format_codec import bounds, digest, lzs_decode, lzs_encode, string_table, pack_strings, read_int\n", "from .format_codec import bounds, digest, lzs_decode, lzs_encode, string_table, pack_strings, read_int\nfrom . import semantics\n")
old = "        result['categories'] += [dict(value, id=key, family=family) for key,value in info['categories'].items()]\n"
new = '''        for key, value in info['categories'].items():
            category = dict(value, id=key, family=family)
            category['fields'] = semantics.apply(key, value['fields'])
            result['categories'].append(category)
'''
replace("games/ff7/extended.py", old, new)


# ---- editor.html: render semantic compounds/references ---------------------
editor = ROOT / "games/ff7/editor.html"
html = editor.read_text(encoding="utf-8")
start = html.index('  function flagsSummary(field,value){')
end = html.index('\n\n  function descriptionControl(row){', start)
block = r'''  function flagMask(field){return field.bitWidth?2**Number(field.bitWidth)-1:0xFFFFFFFF}
  function logicalFlags(field,value){const raw=Number(value)>>>0;return field.invertBits?((~raw)>>>0)&flagMask(field):raw}
  function flagsSummary(field,value){
    const number=logicalFlags(field,value),labels=(field.flags||[]).filter(flag=>(number&Number(flag.value))!==0).map(flag=>flag.label);
    const known=(field.flags||[]).reduce((mask,flag)=>mask|Number(flag.value),0)>>>0,unknown=(number&~known)>>>0;
    if(unknown)labels.push(`Unknown bits 0x${unknown.toString(16).toUpperCase()}`);
    return labels.length?labels.join(", "):"None";
  }
  function flagsControl(row,field){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);
    const raw=()=>Number(row.values[field.key])>>>0;
    const logical=()=>logicalFlags(field,raw());
    const group=toggleRow({label:`${field.label} for ${row.name}`,columns:3,toggles:(field.flags||[]).map(flag=>({
      label:flag.label,checked:(logical()&Number(flag.value))!==0,disabled:readonly(),help:flag.help,change:checked=>{
        if(readonly())return;
        const bit=Number(flag.value),value=raw();
        row.values[field.key]=field.invertBits?(checked?(value&~bit):(value|bit)):(checked?(value|bit):(value&~bit));
        shellRefresh();
      }
    }))});
    return provenanceControl({control:group,current:raw,vanilla,internal:true,format:value=>flagsSummary(field,value),
      apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function referenceRows(field,row){
    let rows=[...(state.records[field.referenceCategory]||[])];
    if(field.referenceScope==="scene")rows=rows.filter(candidate=>candidate.scene===row.scene);
    return rows;
  }
  function candidateValue(field,candidate){return Number(candidate[field.referenceValueKey||"id"])}
  function candidateLabel(candidate){return String(candidate.values?.name||candidate.name||`Record ${candidate.id}`)}
  function referenceChoices(field,row){return referenceRows(field,row).map(candidate=>({value:candidateValue(field,candidate),label:candidateLabel(candidate)}))}
  function inventoryChoices(includeMateria=true){
    const specs=[["items",0],["weapons",128],["armor",256],["accessories",288],...(includeMateria?[["materia",320]]:[])];
    return specs.flatMap(([category,offset])=>(state.records[category]||[]).map(record=>({value:offset+Number(record.id),label:`${candidateLabel(record)} — ${labels[category]||category}`})));
  }
  function semanticChoiceSummary(choices,value,emptyValue){
    if(emptyValue!==undefined&&Number(value)===Number(emptyValue))return "None";
    const choice=choices.find(candidate=>Number(candidate.value)===Number(value));
    return choice?.label||enumSummary({choices},value);
  }
  function selectControl(row,field,choiceFactory){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);
    const current=Number(row.values[field.key]);
    const choices=choiceFactory();
    if(field.emptyValue!==undefined&&!choices.some(c=>Number(c.value)===Number(field.emptyValue)))choices.unshift({value:Number(field.emptyValue),label:"None"});
    for(const value of [current,vanilla])if(!choices.some(c=>Number(c.value)===value))choices.push({value,label:semanticChoiceSummary(choices,value,field.emptyValue)});
    const select=el("select",{disabled:readonly(),"aria-label":`${field.label} for ${row.name}`,onchange:event=>{
      if(readonly())return;row.values[field.key]=Number(event.target.value);field.rerenderOnChange?render():shellRefresh();
    }},...choices.map(choice=>el("option",{value:choice.value},choice.label)));
    select.value=String(current);
    return provenanceControl({control:select,current:()=>row.values[field.key],vanilla,internal:true,
      format:value=>semanticChoiceSummary(choices,value,field.emptyValue),apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function referenceControl(row,field){return selectControl(row,field,()=>referenceChoices(field,row))}
  function inventoryReferenceControl(row,field){return selectControl(row,field,()=>inventoryChoices(true))}
  function shopReferenceControl(row,field){return selectControl(row,field,()=>Number(row.values[field.kindField])===1?(state.records.materia||[]).map(record=>({value:Number(record.id),label:candidateLabel(record)})):inventoryChoices(false))}
  function booleanControl(row,field){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);
    const input=el("input",{type:"checkbox",checked:!!Number(row.values[field.key]),disabled:readonly(),"aria-label":`${field.label} for ${row.name}`,onchange:event=>{if(readonly())return;row.values[field.key]=event.target.checked?1:0;shellRefresh()}});
    input.checked=!!Number(row.values[field.key]);
    return provenanceControl({control:input,current:()=>Number(row.values[field.key]),vanilla,internal:true,format:value=>Number(value)?"Enabled":"Disabled",apply:value=>{if(readonly())return;row.values[field.key]=Number(value)?1:0;render()}});
  }
  function scaledControl(row,field){
    const scale=Number(field.displayScale)||1,key=`${state.tab}/${row.id}/${field.key}`,raw=Number(row.values[field.key]);
    const input=el("input",{type:"number",min:Number(field.minimum)*scale,max:Number(field.maximum)*scale,step:scale,value:raw*scale,disabled:readonly(),"aria-label":`${field.label} for ${row.name}`,oninput:event=>{
      if(readonly())return;const shown=Number(event.target.value),value=shown/scale;
      if(event.target.value===""||!Number.isInteger(value)||!event.target.checkValidity())state.invalid[key]=event.target.value;
      else{delete state.invalid[key];row.values[field.key]=value}shellRefresh();
    }});
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);
    return provenanceControl({control:input,current:()=>Number(row.values[field.key]),vanilla,internal:true,format:value=>String(Number(value)*scale),apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function statusChangeDecoded(value){
    const raw=Number(value);if(raw===0xFF)return{mode:"none",amount:0};if(raw<0x40)return{mode:"inflict",amount:raw};if(raw<0x80)return{mode:"cure",amount:raw-0x40};if(raw<0xC0)return{mode:"swap",amount:raw-0x80};return{mode:"unknown",amount:raw};
  }
  function statusChangeSummary(value){const data=statusChangeDecoded(value);if(data.mode==="none")return"None";if(data.mode==="unknown")return`Unknown / modded (0x${Number(value).toString(16).toUpperCase()})`;return`${data.mode[0].toUpperCase()+data.mode.slice(1)} — ${data.amount}/63`}
  function statusChangeControl(row,field){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]),initial=statusChangeDecoded(row.values[field.key]);
    const modes=[{value:"none",label:"None"},{value:"inflict",label:"Inflict"},{value:"cure",label:"Cure"},{value:"swap",label:"Swap"}];
    if(initial.mode==="unknown")modes.push({value:"unknown",label:statusChangeSummary(row.values[field.key])});
    const mode=el("select",{"aria-label":`${field.label} mode for ${row.name}`,disabled:readonly()},...modes.map(value=>el("option",{value:value.value},value.label)));
    const amount=el("input",{type:"number",min:0,max:63,step:1,"aria-label":`${field.label} chance or amount for ${row.name}`,disabled:readonly()});
    mode.value=initial.mode;amount.value=String(initial.mode==="unknown"?0:initial.amount);amount.disabled=readonly()||["none","unknown"].includes(initial.mode);
    const root=el("div",{class:"lex-semantic-compound"},mode,amount);
    const update=()=>{if(readonly())return;const selected=mode.value;if(selected==="unknown")return;const n=Math.max(0,Math.min(63,Number(amount.value)||0));row.values[field.key]=selected==="none"?0xFF:selected==="inflict"?n:selected==="cure"?0x40+n:0x80+n;amount.disabled=readonly()||selected==="none";root.dispatchEvent(new Event("change",{bubbles:true}));shellRefresh()};
    mode.addEventListener("change",update);amount.addEventListener("input",update);
    return provenanceControl({control:root,current:()=>Number(row.values[field.key]),vanilla,internal:true,format:statusChangeSummary,apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function semanticControl(row,field){
    if(field.dataType==="text")return textControl(row,field);
    if(field.dataType==="enum")return enumControl(row,field);
    if(field.dataType==="flags")return flagsControl(row,field);
    if(field.dataType==="reference")return referenceControl(row,field);
    if(field.dataType==="inventoryReference")return inventoryReferenceControl(row,field);
    if(field.dataType==="shopReference")return shopReferenceControl(row,field);
    if(field.dataType==="boolean")return booleanControl(row,field);
    if(field.dataType==="scaled")return scaledControl(row,field);
    if(field.dataType==="statusChange")return statusChangeControl(row,field);
    return numberControl(row,field);
  }
  function semanticHelp(field){
    if(field.help)return field.help;
    if(field.dataType==="text")return "English game text. Use byte escapes for control codes; unsupported characters and oversized text are refused on save.";
    return "Numeric game value. Lexeditor writes the documented FF7 value directly and preserves unrelated bytes.";
  }
  function semanticType(field){
    return {text:"TEXT",enum:"SELECT",flags:"FLAGS",reference:"REF",inventoryReference:"REF",shopReference:"REF",boolean:"BOOL",scaled:"VALUE",statusChange:"STATUS"}[field.dataType]||"INT";
  }'''
html = html[:start] + block + html[end:]
editor.write_text(html, encoding="utf-8")


# ---- focused regression suite ----------------------------------------------
test = ROOT / "tools/verify_ff7_semantic_surface.py"
test.write_text(r'''"""Regression contract: FF7 UI exposes game concepts, not storage bytes."""
from __future__ import annotations

from pathlib import Path
import unittest

import verify_ff7_datasets as kernel_fixtures
import verify_ff7_extended as extended_fixtures
from games.ff7 import battle, datasets, extended, semantics


class SemanticSurfaceTests(unittest.TestCase):
    def test_core_kernel_categories_are_humanized(self):
        meta={category["id"]:{f["key"]:f for f in category["fields"]} for category in datasets.category_metadata()}
        expected={
            "items":{"targetData":"flags","damageCalculationId":"enum","statusChange":"statusChange","statusFlags":"flags","elementFlags":"flags"},
            "weapons":{"targetData":"flags","damageCalculationId":"enum","growthRate":"enum","equipableBy":"flags","attackElements":"flags"},
            "armor":{"elementDamageModifier":"enum","status":"enum","growthRate":"enum","equipableBy":"flags","elementalDefense":"flags"},
            "accessories":{"boostedStat1":"enum","specialEffect":"enum","elementalDefense":"flags","statusDefense":"flags","equipableBy":"flags"},
            "characters":{"weaponId":"reference","armorId":"reference","accessoryId":"reference","characterFlags":"flags","rowByte":"enum","learnedLimits":"flags","weaponMateria0":"reference","strengthCurve":"reference","recruitOffsetRaw":"scaled"},
        }
        for category, fields in expected.items():
            for key, kind in fields.items(): self.assertEqual(meta[category][key]["dataType"],kind,(category,key))
        self.assertEqual(next(c for c in meta["characters"]["rowByte"]["choices"] if c["label"]=="Front row")["value"],0xFF)

    def test_extended_categories_are_humanized(self):
        categories={}
        for key, spec in battle.SCENE_CATEGORIES.items(): categories[key]=semantics.apply(key,spec["fields"])
        categories["shops"]=semantics.apply("shops",extended.SHOP_FIELDS)
        from games.ff7 import archives
        categories["fieldEncounters"]=semantics.apply("fieldEncounters",archives.FIELD_FIELDS)
        categories["chocoboRatings"]=semantics.apply("chocoboRatings",archives.CHOCOBO_FIELDS)
        by={key:{f["key"]:f for f in fields} for key,fields in categories.items()}
        self.assertEqual(by["enemies"]["statusImmunity"]["dataType"],"flags")
        self.assertTrue(by["enemies"]["statusImmunity"]["invertBits"])
        self.assertEqual(by["enemies"]["attack0"]["dataType"],"reference")
        self.assertEqual(by["enemyAttacks"]["target"]["dataType"],"flags")
        self.assertEqual(by["enemyAttacks"]["formula"]["dataType"],"enum")
        self.assertEqual(by["enemyAttacks"]["statusChance"]["dataType"],"statusChange")
        self.assertEqual(by["enemyAttacks"]["specialFlags"]["dataType"],"flags")
        self.assertTrue(by["enemyAttacks"]["specialFlags"]["invertBits"])
        self.assertEqual(by["encounters"]["slot0_enemy"]["dataType"],"reference")
        self.assertEqual(by["shops"]["type"]["dataType"],"enum")
        self.assertEqual(by["shops"]["item0"]["dataType"],"shopReference")
        self.assertEqual(by["fieldEncounters"]["enabled"]["dataType"],"boolean")
        self.assertEqual(by["fieldEncounters"]["battle0"]["dataType"],"reference")
        self.assertEqual(by["chocoboRatings"]["rating"]["dataType"],"enum")

    def test_raw_storage_fields_are_quarantined_when_no_mapping_exists(self):
        collections=[
            *(semantics.apply(key,spec["fields"]) for key,spec in battle.SCENE_CATEGORIES.items()),
            semantics.apply("shops",extended.SHOP_FIELDS),
        ]
        suspicious=(" id"," flags"," mask"," byte","camera","animation","layout","arena","cover flags")
        for fields in collections:
            for field in fields:
                if field["dataType"] in {"enum","flags","reference","inventoryReference","shopReference","boolean","statusChange"}: continue
                if any(word in str(field.get("label","")).casefold() for word in suspicious):
                    self.assertTrue(field.get("advanced"),field)
                    self.assertEqual(field.get("group"),"Advanced / engine data",field)

    def test_scene_records_expose_reference_identity_without_changing_bytes(self):
        raw=extended_fixtures.scene_fixture(); scene=battle.SceneArchive(raw)
        enemy=scene.records("enemies")[0]; attack=scene.records("enemyAttacks")[0]; formation=scene.records("encounters")[0]
        self.assertEqual((enemy["scene"],enemy["gameId"]),(0,0))
        self.assertEqual((attack["scene"],attack["gameId"]),(0,0))
        self.assertEqual((formation["scene"],formation["gameId"]),(0,0))
        for category in battle.SCENE_CATEGORIES: scene.apply(category,scene.records(category))
        self.assertEqual(scene.to_bytes(),raw)

    def test_status_and_special_flag_storage_remains_exact(self):
        # Logical toggles are a presentation concern. Binary models continue to
        # round-trip the original stored masks exactly, including inverted fields.
        raw=extended_fixtures.scene_fixture(); obj=battle.SceneArchive(raw)
        enemy=obj.records("enemies")[0]["values"]["statusImmunity"]
        attack=obj.records("enemyAttacks")[0]["values"]["specialFlags"]
        self.assertEqual(enemy,int.from_bytes(obj.scenes[0][0x348:0x34C],"little"))
        self.assertEqual(attack,int.from_bytes(obj.scenes[0][0x4C0+26:0x4C0+28],"little"))


if __name__=="__main__": unittest.main(verbosity=2)
''',encoding="utf-8")

# Existing FF7 binary job already invokes verify_ff7_accessories.py; import the
# semantic TestCase there so the new contract runs without workflow-file edits.
accessories = ROOT / "tools/verify_ff7_accessories.py"
a = accessories.read_text(encoding="utf-8")
if "from verify_ff7_semantic_surface import SemanticSurfaceTests" not in a:
    a = a.replace("import unittest\n", "import unittest\n\nfrom verify_ff7_semantic_surface import SemanticSurfaceTests\n", 1)
accessories.write_text(a, encoding="utf-8")

print("FF7 full semantic patch applied")
