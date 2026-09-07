from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{path}: anchor not found: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Retry a transiently failed baseline instead of caching unavailable for the whole process.
replace_once(
    "games/ff9/memoria_baseline.py",
    '        if root is None and _last is not None and not force:\n            return _last\n',
    '        if root is None and _last is not None and not force and _last.get("ready"):\n            return _last\n',
)

# Arrays such as shop inventories and equipment ability lists are real editable values.
p = Path("games/ff9/memoria_csv.py")
s = p.read_text(encoding="utf-8")
old = '''            elif "[" in normalized or "{" in normalized:\n                descriptor.update(kind="stored", editable=False)\n            elif normalized in {"string", ""}:\n'''
new = '''            elif normalized.endswith("[]"):\n                item_type = normalized[:-2].strip()\n                descriptor.update(kind="list", itemType=item_type)\n                if item_type in _INTEGER_RANGES:\n                    descriptor.update(itemKind="integer", itemMin=_INTEGER_RANGES[item_type][0], itemMax=_INTEGER_RANGES[item_type][1])\n                else:\n                    descriptor.update(itemKind="token")\n            elif "[" in normalized or "{" in normalized:\n                descriptor.update(kind="stored", editable=False)\n            elif normalized in {"string", ""}:\n'''
if old not in s:
    raise SystemExit("memoria_csv array descriptor anchor missing")
s = s.replace(old, new, 1)
old = '''            identity = by_name.get("Id", by_name.get("id", str(len(rows))))\n            name = by_name.get("Comment") or by_name.get("Name") or _comment_text(suffix)\n            rows.append({"line": line_number, "id": identity,\n                         "name": name or f"Record {identity}", "raw": by_name, "suffix": suffix})\n'''
new = '''            identity = by_name.get("Id", by_name.get("id", str(len(rows))))\n            comment_name = by_name.get("Comment") or by_name.get("Name")\n            suffix_name = _comment_text(suffix)\n            name = comment_name or suffix_name\n            if comment_name and suffix_name and re.fullmatch(r"Shop\\s+\\d+", comment_name.strip(), flags=re.I):\n                richer = re.sub(r"^Shop\\s+\\d+\\s*", "", suffix_name, flags=re.I).strip()\n                if richer:\n                    name = richer\n            rows.append({"line": line_number, "id": identity,\n                         "name": name or f"Record {identity}", "raw": by_name, "suffix": suffix})\n'''
if old not in s:
    raise SystemExit("memoria_csv name anchor missing")
s = s.replace(old, new, 1)
old = '''        if kind == "text":\n            if not isinstance(value, str) or "\\n" in value or "\\r" in value:\n                raise ValueError(f"{field['key']} must be one line of text")\n            return value\n        raise ValueError(f"{field['key']} is not editable")\n'''
new = '''        if kind == "list":\n            if not isinstance(value, str) or "\\n" in value or "\\r" in value or ";" in value:\n                raise ValueError(f"{field['key']} must be a comma-separated one-line list")\n            tokens = [token.strip() for token in value.split(",") if token.strip()]\n            if field.get("itemKind") == "integer":\n                minimum, maximum = field["itemMin"], field["itemMax"]\n                for token in tokens:\n                    if not re.fullmatch(r"[-+]?\\d+", token):\n                        raise ValueError(f"{field['key']} must contain only whole numbers")\n                    number = int(token)\n                    if not minimum <= number <= maximum:\n                        raise ValueError(f"{field['key']} entries must be from {minimum} through {maximum}")\n            else:\n                for token in tokens:\n                    if not re.fullmatch(r"[A-Za-z0-9_.:+-]+", token):\n                        raise ValueError(f"{field['key']} contains an invalid list token")\n            return ", ".join(tokens)\n        if kind == "text":\n            if not isinstance(value, str) or "\\n" in value or "\\r" in value:\n                raise ValueError(f"{field['key']} must be one line of text")\n            return value\n        raise ValueError(f"{field['key']} is not editable")\n'''
if old not in s:
    raise SystemExit("memoria_csv serializer anchor missing")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

# Data Map describes integration coverage, not whether a cache file exists this instant.
p = Path("games/ff9/server.py")
s = p.read_text(encoding="utf-8")
old = '''        integrated.append({\n            "filename": row["relativePath"], "controls": row["controls"],\n            "notes": f"{row['label']}. Writes a project overlay; the game baseline is never overwritten.",\n            "status": "integrated" if available else "not-integrated",\n            "coverage": "structured" if available else "unavailable",\n            "openable": available, "target": row["tab"],\n            "dataset": row["key"], "datasetKey": row["key"],\n        })\n'''
new = '''        integrated.append({\n            "filename": row["relativePath"], "controls": row["controls"],\n            "notes": (f"{row['label']}. Structured editor is integrated; writes a project overlay and never overwrites the game baseline."\n                      + (" Source data is available now." if available else " The local baseline is not available yet; opening the view will retry it.")),\n            "status": "integrated", "coverage": "structured",\n            "openable": True, "sourceAvailable": available, "target": row["tab"],\n            "dataset": row["key"], "datasetKey": row["key"],\n        })\n'''
if old not in s:
    raise SystemExit("server data map anchor missing")
s = s.replace(old, new, 1)
s = s.replace('"controls": "Improved Interface and Better Eat runtime",', '"controls": "Lexeditor FF9 runtime tweaks",', 1)
p.write_text(s, encoding="utf-8")

# Use shared property controls and conceptual FF9 records instead of mirroring raw CSV boundaries.
p = Path("games/ff9/editor.html")
s = p.read_text(encoding="utf-8")
s = s.replace(
    'const {el,columnList,columnPreferences,detailPanel,detailSection,detailField,readonlyField,recordId,pagedListDetail,booleanMark,subtabBar,infoHelp,clone,infoIcon}=LexeditorUI;',
    'const {el,columnList,columnPreferences,detailPanel,detailSection,detailField,readonlyField,recordId,pagedListDetail,booleanMark,subtabBar,infoHelp,clone,infoIcon,toggleRow}=LexeditorUI;',
    1,
)
old = '''  const prefCache={};\n  const catalogRow=key=>state.catalog.find(value=>value.key===key);\n  const choices=tab=>tab==="accessories"?["items"]:state.catalog.filter(value=>value.tab===tab).map(value=>value.key);\n'''
new = '''  const prefCache={};\n  const catalogRow=key=>state.catalog.find(value=>value.key===key);\n  const CHARACTER_NAV_KEYS=["characters","leveling"];\n  const ITEM_CATEGORY_FLAGS=["Weapon","Armlet","Helmet","Armor","Accessory","Item","Gem","Usable"];\n  const ITEM_PARTY_FLAGS=["Zidane","Vivi","Garnet","Steiner","Freya","Quina","Eiko","Amarant","Cinna","Marcus","Blank","Beatrix"];\n  const choices=tab=>tab==="accessories"?["items"]:tab==="characters"?CHARACTER_NAV_KEYS:state.catalog.filter(value=>value.tab===tab).map(value=>value.key);\n'''
if old not in s:
    raise SystemExit("editor choices anchor missing")
s = s.replace(old, new, 1)
old = '''  function setValue(data,row,field,value){row.values[field.key]=value;shell.refresh()}\n  function fieldControl(data,row,field){const note=readOnlyNote(data,field);let control;if(note||!field.editable||field.kind==="stored")control=readonlyField(String(row.values[field.key]??""),{className:"ff9-readonly"});else if(field.kind==="boolean")control=el("input",{type:"checkbox",checked:!!row.values[field.key],onchange:event=>setValue(data,row,field,event.target.checked)});else if(field.kind==="integer"||field.kind==="number")control=el("input",{type:"number",min:field.min,max:field.max,step:field.step||1,value:row.values[field.key],oninput:event=>{if(event.target.value!=="")setValue(data,row,field,Number(event.target.value))}});else control=el("input",{type:"text",value:row.values[field.key]??"",oninput:event=>setValue(data,row,field,event.target.value)});return detailField({label:field.label.toLocaleUpperCase(),help:note?infoHelp(note):null,control,dataType:note?"READ ONLY":field.declaredType,min:field.min,max:field.max})}\n  function detail(data,row){const editable=data.fields.filter(field=>field.editable&&field.kind!=="stored"&&!readOnlyNote(data,field)),stored=data.fields.filter(field=>!field.editable||field.kind==="stored"||readOnlyNote(data,field));const body=[];if(editable.length)body.push(detailSection({title:"EDITABLE DATA",body:editable.map(field=>fieldControl(data,row,field))}));if(stored.length)body.push(detailSection({title:"STORED DATA",body:stored.map(field=>fieldControl(data,row,field))}));return detailPanel({className:"ff9-detail",title:row.name,identity:recordId(row.id),meta:`${data.label} · ${data.source} CSV`,body})}\n'''
new = '''  function setValue(data,row,field,value){row.values[field.key]=value;shell.refresh()}\n  function fieldControl(data,row,field){const note=readOnlyNote(data,field);let control;if(note||!field.editable||field.kind==="stored")control=readonlyField(String(row.values[field.key]??""),{className:"ff9-readonly"});else if(field.kind==="boolean")control=el("input",{type:"checkbox",checked:!!row.values[field.key],onchange:event=>setValue(data,row,field,event.target.checked)});else if(field.kind==="integer"||field.kind==="number")control=el("input",{type:"number",min:field.min,max:field.max,step:field.step||1,value:row.values[field.key],oninput:event=>{if(event.target.value!=="")setValue(data,row,field,Number(event.target.value))}});else control=el("input",{type:"text",value:row.values[field.key]??"",oninput:event=>setValue(data,row,field,event.target.value)});const listNote=field.kind==="list"?(data.key==="shops"&&field.key==="Items"?"Ordered item IDs sold by this shop. Separate entries with commas.":"This Memoria array is edited as a comma-separated list."):null;return detailField({label:field.label.toLocaleUpperCase(),help:note?infoHelp(note):listNote?infoHelp(listNote):null,control,dataType:note?"READ ONLY":field.declaredType,min:field.min,max:field.max})}\n  const fieldRows=(data,row,exclude=[])=>{const blocked=new Set(exclude.map(String));return data&&row?data.fields.filter(field=>!blocked.has(field.key)&&field.key.toLocaleLowerCase()!=="id"&&field.key.toLocaleLowerCase()!=="comment").map(field=>fieldControl(data,row,field)):[]};\n  function boolProperty(data,row,label,keys,help){const fields=new Map(data.fields.map(field=>[field.key,field]));const toggles=keys.filter(key=>fields.has(key)).map(key=>({key,label:key,checked:!!row.values[key],disabled:state.activeSource!=="mine",change:value=>setValue(data,row,fields.get(key),value)}));return toggles.length?detailField({label,help:help?infoHelp(help):null,control:toggleRow({label,toggles}),dataType:"FLAGS"}):null}\n  function itemSections(data,row,title="ITEM DATA"){const grouped=[...ITEM_CATEGORY_FLAGS,...ITEM_PARTY_FLAGS];const body=fieldRows(data,row,grouped);const categories=boolProperty(data,row,"CATEGORIES",ITEM_CATEGORY_FLAGS,"Related item category/usability checks are one property; the stored bits are an implementation detail.");const party=boolProperty(data,row,"EQUIPPABLE BY",ITEM_PARTY_FLAGS,"The party-member equipment checks are one multi-boolean property.");if(categories)body.push(categories);if(party)body.push(party);return detailSection({title,body})}\n  function detail(data,row){if(data.key==="items")return detailPanel({className:"ff9-detail",title:row.name,identity:recordId(row.id),meta:`Items · ${data.source} CSV`,body:[itemSections(data,row)]});const editable=data.fields.filter(field=>field.editable&&field.kind!=="stored"&&!readOnlyNote(data,field)),stored=data.fields.filter(field=>!field.editable||field.kind==="stored"||readOnlyNote(data,field));const body=[];if(editable.length)body.push(detailSection({title:"EDITABLE DATA",body:editable.map(field=>fieldControl(data,row,field))}));if(stored.length)body.push(detailSection({title:"STORED DATA",body:stored.map(field=>fieldControl(data,row,field))}));return detailPanel({className:"ff9-detail",title:row.name,identity:recordId(row.id),meta:`${data.label} · ${data.source} CSV`,body})}\n'''
if old not in s:
    raise SystemExit("editor detail anchor missing")
s = s.replace(old, new, 1)
marker = '  function setToolbar(nodes=[]){$("#toolbar").replaceChildren(...nodes)}\n'
if marker not in s:
    raise SystemExit("editor composite insertion marker missing")
composite = r'''  const rowById=(data,id)=>data?.rows?.find(row=>String(row.id)===String(id))||null;
  function characterDetail(base,row,parameters,equipment,commandSets){const param=rowById(parameters,row.id);const equipmentRow=param?rowById(equipment,param.values.DefaultEquipmentSet):null;const commandRow=param?rowById(commandSets,param.values.DefaultCommandSet):null;const body=[detailSection({title:"BASE STATS",body:fieldRows(base,row)}),detailSection({title:"HP / MP",body:[detailField({label:"HP",help:infoHelp("FF9 has no per-character base HP field. Max HP is calculated from the shared level curve and the character's current Strength, including growth bonuses."),control:readonlyField("Derived: BonusHP[level] × current Strength ÷ 50"),dataType:"DERIVED"}),detailField({label:"MP",help:infoHelp("FF9 has no per-character base MP field. Max MP is calculated from the shared level curve and the character's current Magic, including growth bonuses."),control:readonlyField("Derived: BonusMP[level] × current Magic ÷ 100"),dataType:"DERIVED"}),detailField({label:"LEVEL CURVE",control:el("button",{type:"button",onclick:()=>{state.datasetChoice.characters="leveling";render()}},"Edit shared HP / MP level curve")})]})];if(param)body.push(detailSection({title:"CHARACTER PARAMETERS",body:fieldRows(parameters,param,["DefaultEquipmentSet","DefaultCommandSet"])}));if(equipmentRow)body.push(detailSection({title:"STARTING EQUIPMENT",body:fieldRows(equipment,equipmentRow)}));if(commandRow)body.push(detailSection({title:"COMMAND SET",body:fieldRows(commandSets,commandRow)}));return detailPanel({className:"ff9-detail",title:row.name,identity:recordId(row.id),meta:"Combined character record · Memoria CSV overlays",body})}
  async function renderCharacterComposite(){const [base,parameters,equipment,commandSets]=await Promise.all([loadDataset("characters"),loadDataset("character-parameters"),loadDataset("default-equipment"),loadDataset("command-sets")]);if(!base||base.unavailable){renderDataset(base,"characters");return}const rows=viewRows(base,"characters"),selected=rows.find(row=>row.line===state.selected.characters)||rows[0];if(selected)state.selected.characters=selected.line;const layout=pagedListDetail({rows,key:row=>row.line,slots:true,selected:selected?.line??null,page:state.page.characters||0,pageSize:state.pageSize.characters||12,noun:"characters",className:"ff9-layout",splitKey:"ff9-characters-combined",rowsKey:"ff9-characters-combined",defaultSplit:44,minLeft:340,minRight:420,search:{key:"ff9-characters",value:state.query.characters||"",label:"Search characters",change:value=>{state.query.characters=value;state.page.characters=0;render()}},sync:next=>{state.page.characters=next.page;state.pageSize.characters=next.pageSize;if(next.selected!==null)state.selected.characters=next.selected},change:next=>{state.page.characters=next.page;state.pageSize.characters=next.pageSize;if(next.selected!==null)state.selected.characters=next.selected;render()},master:view=>tablePanel(base,"characters",view.rows,view.selected,view.select),detail:row=>characterDetail(base,row,parameters,equipment,commandSets)});$("#main").replaceChildren(layout)}
  const equipmentSpec=tab=>tab==="weapons"?{specific:"weapons",id:"WeaponId",title:"WEAPON STATS",test:row=>row.values.Weapon===true}:tab==="accessories"?{specific:"armor",id:"ArmorId",title:"DEFENCE / EVASION",test:row=>row.values.Accessory===true}:{specific:"armor",id:"ArmorId",title:"DEFENCE / EVASION",test:row=>row.values.Armlet===true||row.values.Helmet===true||row.values.Armor===true};
  function equipmentDetail(tab,items,row,specific,stats){const spec=equipmentSpec(tab);const specificRow=rowById(specific,row.values[spec.id]);const statRow=rowById(stats,row.values.BonusId);const body=[itemSections(items,row,"SHARED ITEM DATA")];if(specificRow)body.push(detailSection({title:spec.title,body:fieldRows(specific,specificRow)}));if(statRow)body.push(detailSection({title:"EQUIPMENT BONUSES",body:fieldRows(stats,statRow)}));return detailPanel({className:"ff9-detail",title:row.name,identity:recordId(row.id),meta:`${tab==="accessories"?"Accessory":tab==="armor"?"Armor":"Weapon"} · combined Memoria item records`,body})}
  async function renderEquipmentComposite(tab){const spec=equipmentSpec(tab);const [items,specific,stats]=await Promise.all([loadDataset("items"),loadDataset(spec.specific),loadDataset("item-stats")]);if(!items||items.unavailable){renderDataset(items,"items");return}const key=`equipment-${tab}`;const source={...items,rows:items.rows.filter(spec.test)};const rows=viewRows(source,key),selected=rows.find(row=>row.line===state.selected[key])||rows[0];if(selected)state.selected[key]=selected.line;const layout=pagedListDetail({rows,key:row=>row.line,slots:true,selected:selected?.line??null,page:state.page[key]||0,pageSize:state.pageSize[key]||12,noun:tab,className:"ff9-layout",splitKey:`ff9-${key}`,rowsKey:`ff9-${key}`,defaultSplit:44,minLeft:340,minRight:420,search:{key:`ff9-${key}`,value:state.query[key]||"",label:`Search ${tab}`,change:value=>{state.query[key]=value;state.page[key]=0;render()}},sync:next=>{state.page[key]=next.page;state.pageSize[key]=next.pageSize;if(next.selected!==null)state.selected[key]=next.selected},change:next=>{state.page[key]=next.page;state.pageSize[key]=next.pageSize;if(next.selected!==null)state.selected[key]=next.selected;render()},master:view=>tablePanel(items,key,view.rows,view.selected,view.select),detail:row=>equipmentDetail(tab,items,row,specific,stats)});$("#main").replaceChildren(layout)}
'''
s = s.replace(marker, composite + marker, 1)
old = '''  function toolbar(){const keys=choices(state.tab);if(keys.length<=1){setToolbar();return}const buttons=keys.map(key=>({id:key,label:catalogRow(key)?.label||key}));const strip=subtabBar({tabs:buttons,active:activeKey(),label:`${tabs.find(tab=>tab.id===state.tab)?.label} datasets`,change:key=>{state.datasetChoice[state.tab]=key;state.page[key]=0;loadDataset(key).then(render)}});setToolbar([strip])}\n'''
new = '''  function toolbar(){const keys=choices(state.tab);if(keys.length<=1){setToolbar();return}const label=key=>key==="characters"?"Characters":key==="leveling"?"Level curve":catalogRow(key)?.label||key;const buttons=keys.map(key=>({id:key,label:label(key)}));const strip=subtabBar({tabs:buttons,active:activeKey(),label:`${tabs.find(tab=>tab.id===state.tab)?.label} datasets`,change:key=>{state.datasetChoice[state.tab]=key;state.page[key]=0;loadDataset(key).then(render)}});setToolbar([strip])}\n'''
if old not in s:
    raise SystemExit("editor toolbar anchor missing")
s = s.replace(old, new, 1)
old = '''  async function render(){if(!state.dashboard)return;if(state.tab==="info"){setToolbar();info()}else if(state.tab==="datamap")dataMap();else if(state.tab==="tweaks")tweaks();else if(state.activeSource!=="mine"){setToolbar();planned()}else{toolbar();const key=activeKey();if(!key)planned();else renderDataset(await loadDataset(key),key)}shell.refresh()}\n'''
new = '''  async function render(){if(!state.dashboard)return;if(state.tab==="info"){setToolbar();info()}else if(state.tab==="datamap")dataMap();else if(state.tab==="tweaks")tweaks();else if(state.activeSource!=="mine"){setToolbar();planned()}else{toolbar();const key=activeKey();if(!key)planned();else if(state.tab==="characters"&&key==="characters")await renderCharacterComposite();else if(["weapons","armor","accessories"].includes(state.tab))await renderEquipmentComposite(state.tab);else renderDataset(await loadDataset(key),key)}shell.refresh()}\n'''
if old not in s:
    raise SystemExit("editor render anchor missing")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

# Explicit property semantics in the UI manual.
p = Path("docs/UI-MANUAL.md")
s = p.read_text(encoding="utf-8")
old = '''A **Detail panel** edits one selected record. It has one identity heading and\ngroups of rows. Every row uses the same label-to-value division. A plugin can\nchange that division for a page, but individual rows do not choose unrelated\npositions.\n'''
new = '''A **Detail panel** edits one selected record. It has one identity heading and\ngroups of rows. Every row uses the same label-to-value division. A plugin can\nchange that division for a page, but individual rows do not choose unrelated\npositions.\n\nA **property** is one labeled row in a Detail panel. A property can contain one\nvariable or several tightly related variables. Related booleans that together\ndescribe one concept belong in one multi-boolean property row (the shared\n`toggleRow()` control); they are not split into a stack of separate properties\njust because the source format stores them as separate bits or columns.\n'''
if old not in s:
    raise SystemExit("UI manual property anchor missing")
p.write_text(s.replace(old, new, 1), encoding="utf-8")

# Tests.
p = Path("tests/test_ff9_csv.py")
s = p.read_text(encoding="utf-8")
s += r'''


def test_shop_integer_array_is_editable_and_uses_real_suffix_name(store):
    fixture(store, "shops", b"# Comment;Id;Items\n# ;Int32;Int32[]\nShop 0000;0;1, 2;# Shop 0000 Dali Weapon Shop\n")
    loaded = store.load("shops")
    field = next(value for value in loaded["fields"] if value["key"] == "Items")
    assert field["kind"] == "list" and field["itemKind"] == "integer" and field["editable"]
    assert loaded["rows"][0]["name"] == "Dali Weapon Shop"
    saved = store.save("shops", loaded["sha256"], [{"line": loaded["rows"][0]["line"], "values": {"Items": "3, 4, 5"}}])
    assert saved["rows"][0]["values"]["Items"] == "3, 4, 5"
    assert b"Shop 0000;0;3, 4, 5;# Shop 0000 Dali Weapon Shop" in Path(saved["sourcePath"]).read_bytes()


def test_integer_array_rejects_non_numeric_entries(store):
    fixture(store, "shops", b"# Comment;Id;Items\n# ;Int32;Int32[]\nShop 0000;0;1, 2;# Shop 0000 Test\n")
    loaded = store.load("shops")
    with pytest.raises(ValueError, match="whole numbers"):
        store.save("shops", loaded["sha256"], [{"line": loaded["rows"][0]["line"], "values": {"Items": "1, nope"}}])


def test_failed_default_baseline_is_retried(tmp_path, monkeypatch):
    payload = b"# Id;Value\n# Int32;UInt8\n0;1\n"
    monkeypatch.setattr(paths, "DATA_ROOT", tmp_path / "cache")
    monkeypatch.setattr(baseline, "FILES", {"Items/Test.csv": hashlib.sha256(payload).hexdigest()})
    monkeypatch.setattr(baseline, "_last", None)
    calls = {"count": 0}
    def downloader(_relative):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("temporary network failure")
        return payload
    first = baseline.ensure(downloader=downloader)
    second = baseline.ensure(downloader=downloader)
    assert not first["ready"] and second["ready"] and calls["count"] == 2
'''
p.write_text(s, encoding="utf-8")

p = Path("tests/test_ff9_http.py")
s = p.read_text(encoding="utf-8")
s += r'''


def test_data_map_reports_editor_integration_even_before_baseline_arrives(service, monkeypatch):
    monkeypatch.setattr(service[0], "catalog", lambda: [{
        "available": False, "relativePath": "StreamingAssets/Data/Items/Items.csv",
        "controls": "Items", "label": "Items", "tab": "items", "key": "items",
    }])
    row = service[0].data_map()["rows"][0]
    assert row["status"] == "integrated" and row["coverage"] == "structured"
    assert row["openable"] is True and row["sourceAvailable"] is False
'''
p.write_text(s, encoding="utf-8")

p = Path("tests/ff9_editor.test.cjs")
s = p.read_text(encoding="utf-8")
s += r'''


test('FF9 uses shared multi-boolean properties and conceptual character/equipment views', async () => {
  const e = await editor();
  assert.match(source, /toggleRow/);
  assert.match(source, /ITEM_CATEGORY_FLAGS/);
  assert.match(source, /ITEM_PARTY_FLAGS/);
  assert.match(source, /renderCharacterComposite/);
  assert.match(source, /renderEquipmentComposite/);
  e.run('state.catalog=[{key:"characters",tab:"characters"},{key:"character-parameters",tab:"characters"},{key:"default-equipment",tab:"characters"},{key:"leveling",tab:"characters"}]');
  assert.deepEqual(Array.from(e.run('choices("characters")')), ['characters','leveling']);
});
'''
p.write_text(s, encoding="utf-8")
