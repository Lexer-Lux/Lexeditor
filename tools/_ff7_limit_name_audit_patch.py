from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def replace_once(path,old,new,label):
    text=path.read_text(encoding='utf-8')
    if new in text:return
    if old not in text:raise SystemExit(f'{label}: insertion point changed')
    path.write_text(text.replace(old,new,1),encoding='utf-8')

# Core KERNEL names are first-class editable game text just like descriptions.
path=ROOT/'games/ff7/kernel.py'
replace_once(path,
'''        descriptions = string_table(bytes(self.sections[category.text_description_section - 1]))
        count = len(section) // category.record_size
''',
'''        descriptions = string_table(bytes(self.sections[category.text_description_section - 1]))
        count = len(section) // category.record_size
''','kernel read marker')
replace_once(path,
'''        description_index = category.text_description_section - 1
        current_descriptions = string_table(bytes(self.sections[description_index]))
        if len(current_descriptions) < expected_count:
            raise ValueError(f"{category.label} description count does not match its records")
        next_descriptions = list(current_descriptions)
''',
'''        name_index = category.text_name_section - 1
        description_index = category.text_description_section - 1
        current_names = string_table(bytes(self.sections[name_index]))
        current_descriptions = string_table(bytes(self.sections[description_index]))
        if len(current_names) < expected_count or len(current_descriptions) < expected_count:
            raise ValueError(f"{category.label} text count does not match its records")
        next_names, next_descriptions = list(current_names), list(current_descriptions)
''','kernel apply text state')
replace_once(path,
'''            description = record.get("description")
            if type(description) is not str:
                raise ValueError(f"{category.label} record {record_index} description must be text")
''',
'''            name, description = record.get("name"), record.get("description")
            if type(name) is not str or type(description) is not str:
                raise ValueError(f"{category.label} record {record_index} name/description must be text")
''','kernel apply name validation')
replace_once(path,
'''            next_section[start:start + category.record_size] = current
            next_descriptions[record_index] = description
        packed_descriptions = None
        if next_descriptions != current_descriptions:
            packed_descriptions = pack_strings(next_descriptions)
        self.sections[category.section - 1] = next_section
        if packed_descriptions is not None:
            self.sections[description_index] = bytearray(packed_descriptions)
''',
'''            next_section[start:start + category.record_size] = current
            next_names[record_index], next_descriptions[record_index] = name, description
        packed_names = pack_strings(next_names) if next_names != current_names else None
        packed_descriptions = pack_strings(next_descriptions) if next_descriptions != current_descriptions else None
        self.sections[category.section - 1] = next_section
        if packed_names is not None:self.sections[name_index] = bytearray(packed_names)
        if packed_descriptions is not None:self.sections[description_index] = bytearray(packed_descriptions)
''','kernel apply text pack')
replace_once(path,
'''            "id": category.key, "label": category.label,
            "descriptionEditable": True, "fields": fields,
''',
'''            "id": category.key, "label": category.label,
            "nameEditable": True, "descriptionEditable": True, "fields": fields,
''','kernel metadata name editable')

# Expose the 71 Limit names/descriptions that live after the 128 ordinary attacks.
path=ROOT/'games/ff7/kernel_extra.py'
replace_once(path,
'''from .format_codec import bounds, read_int
''',
'''from .format_codec import bounds, read_int, string_table, pack_strings
''','kernel extra text imports')
replace_once(path,
'''MAGIC_ORDER_FIELDS=[
    number('menuGroup','Magic-menu section',0,maximum=0xFF,group='Menu placement'),
    number('position','Position within section',0,maximum=31,group='Menu placement'),
]
''',
'''MAGIC_ORDER_FIELDS=[
    number('menuGroup','Magic-menu section',0,maximum=0xFF,group='Menu placement'),
    number('position','Position within section',0,maximum=31,group='Menu placement'),
]
LIMIT_TEXT_FIELDS=[text('name','Limit name',0,65535),text('description','Limit description',0,65535)]
''','limit text fields')
replace_once(path,
'''    'magicOrder':{'label':'Magic menu','fields':MAGIC_ORDER_FIELDS,'section':3},
''',
'''    'magicOrder':{'label':'Magic menu','fields':MAGIC_ORDER_FIELDS,'section':3},
    'limitTexts':{'label':'Limit text','fields':LIMIT_TEXT_FIELDS,'section':2},
''','limit text category')
replace_once(path,
'''    if key=='magicOrder':
        raw=_growth_section(kernel);attacks=kernel.records('playerAttacks')
''',
'''    if key=='limitTexts':
        names=string_table(bytes(kernel.sections[18]));descriptions=string_table(bytes(kernel.sections[10]))
        if len(names)<199 or len(descriptions)<199:raise ValueError('Magic text sections do not contain the 71 Limit strings')
        return [{'id':i,'name':names[128+i] or f'Limit {i+1}','description':'Limit Break name/description stored in KERNEL text.',
                 'values':{'name':names[128+i],'description':descriptions[128+i]}} for i in range(71)]
    if key=='magicOrder':
        raw=_growth_section(kernel);attacks=kernel.records('playerAttacks')
''','limit text records')
replace_once(path,
'''    if key=='characterAI':
        raw=bytearray(kernel.sections[2]);bounds(raw,0x61C,2048)
''',
'''    if key=='limitTexts':
        names=string_table(bytes(kernel.sections[18]));descriptions=string_table(bytes(kernel.sections[10]))
        if len(names)<199 or len(descriptions)<199:raise ValueError('Magic text sections do not contain the 71 Limit strings')
        next_names,next_descriptions=list(names),list(descriptions)
        for row in rows:
            values=row.get('values') if isinstance(row,dict) else None
            if not isinstance(values,dict) or set(values)!={'name','description'} or any(type(values[k]) is not str for k in values):
                raise ValueError('Limit text requires exact name and description strings')
            next_names[128+row['id']],next_descriptions[128+row['id']]=values['name'],values['description']
        kernel.sections[18]=bytearray(pack_strings(next_names));kernel.sections[10]=bytearray(pack_strings(next_descriptions));return
    if key=='characterAI':
        raw=bytearray(kernel.sections[2]);bounds(raw,0x61C,2048)
''','limit text apply')

# The EXE contains the authoritative 71 x 28-byte Limit attack records.
path=ROOT/'games/ff7/extended.py'
replace_once(path,
'''DEFAULT_NAME_FIELDS = [text('name','Default name',0,12)]
PRICE_TABLES = [('Items', 0, 128), ('Weapons', 128, 128), ('Armor', 256, 32),
''',
'''DEFAULT_NAME_FIELDS = [text('name','Default name',0,12)]
LIMIT_FIELDS = [number(k,l,o,s) for k,l,o,s in (
    ('accuracyRate','Accuracy',0,1),('impactEffectId','Impact effect ID',1,1),('targetHurtActionIndex','Target hurt action ID',2,1),
    ('mpCost','MP cost',4,2),('impactSound','Impact sound ID',6,2),('cameraMovementIdSingle','Single-target camera ID',8,2),
    ('cameraMovementIdMulti','Multi-target camera ID',10,2),('targetData','Target flags',12,1),('attackEffectId','Attack effect ID',13,1),
    ('damageCalculationId','Damage calculation ID',14,1),('attackPower','Attack power',15,1),('conditionSubmenu','Condition submenu',16,1),
    ('statusChange','Status change',17,1),('additionalEffects','Additional effects',18,1),('additionalEffectsModifier','Effect modifier',19,1),
    ('statusFlags','Status flags',20,4),('elementFlags','Element flags',24,2),('specialAttackFlags','Special attack flags',26,2))]
PRICE_TABLES = [('Items', 0, 128), ('Weapons', 128, 128), ('Armor', 256, 32),
''','limit fields')
replace_once(path,
'''        ranges = [(0x5202B8,120),(0x520810,264),(0x521A18,80*84),
                  (0x523458,320*4),(0x523A58,96*4)]
''',
'''        ranges = [(0x51DCD4,71*28),(0x5202B8,120),(0x520810,264),(0x521A18,80*84),
                  (0x523458,320*4),(0x523A58,96*4)]
''','limit allowed EXE range')
replace_once(path,
'''    def _offset(self, category, index):
        return (0x521A18 + index * 84 if category == 'shops' else 0x523458 + index * 4) + self.shift
''',
'''    def _offset(self, category, index):
        if category=='limits':return 0x51DCD4+self.shift+index*28
        return (0x521A18 + index * 84 if category == 'shops' else 0x523458 + index * 4) + self.shift
''','limit EXE offset')
replace_once(path,
'''        if category == 'shops':
            return [{'id':i, 'name':f'Shop {i}', 'description':'Ten inventory slots; only Inventory count slots are active. Field shop-opening scripts are unchanged.',
''',
'''        if category == 'limits':
            return [{'id':i,'gameId':128+i,'name':f'Limit {i+1}','description':'Authoritative executable Limit Break attack record; its name/description live in KERNEL text.',
                     'values':read_values(self.data[self._offset(category,i):self._offset(category,i)+28],LIMIT_FIELDS)} for i in range(71)]
        if category == 'shops':
            return [{'id':i, 'name':f'Shop {i}', 'description':'Ten inventory slots; only Inventory count slots are active. Field shop-opening scripts are unchanged.',
''','limit EXE records')
replace_once(path,
'''        if category in ('recruits','defaultNames'):
            start, size, fields = (0x520810,132,RECRUIT_FIELDS) if category == 'recruits' else (0x5202B8,12,DEFAULT_NAME_FIELDS)
''',
'''        if category in ('recruits','defaultNames'):
            start, size, fields = (0x520810,132,RECRUIT_FIELDS) if category == 'recruits' else (0x5202B8,12,DEFAULT_NAME_FIELDS)
''','extended apply marker')
replace_once(path,
'''        replacement = bytearray(self.data)
        fields, size = (SHOP_FIELDS, 84) if category == 'shops' else (PRICE_FIELDS, 4)
''',
'''        replacement = bytearray(self.data)
        if category=='limits':fields,size=LIMIT_FIELDS,28
        else:fields, size = (SHOP_FIELDS, 84) if category == 'shops' else (PRICE_FIELDS, 4)
''','limit EXE apply fields')
replace_once(path,
'''    'shop': {'categories':{'shops':{'label':'Shops','fields':SHOP_FIELDS}, 'prices':{'label':'Prices','fields':PRICE_FIELDS}, 'recruits':{'label':'Recruits','fields':RECRUIT_FIELDS}, 'defaultNames':{'label':'Default names','fields':DEFAULT_NAME_FIELDS}},
''',
'''    'shop': {'categories':{'shops':{'label':'Shops','fields':SHOP_FIELDS}, 'prices':{'label':'Prices','fields':PRICE_FIELDS}, 'limits':{'label':'Limit attacks','fields':LIMIT_FIELDS}, 'recruits':{'label':'Recruits','fields':RECRUIT_FIELDS}, 'defaultNames':{'label':'Default names','fields':DEFAULT_NAME_FIELDS}},
''','limit EXE family category')
replace_once(path,
'''FAMILIES['shop']['note']='Shop inventories, prices, default names and Cait Sith/Vincent starting data in a recognized English executable; saves replace project copies only.'
''',
'''FAMILIES['shop']['note']='Limit attacks, shop inventories, prices, default names and Cait Sith/Vincent starting data in a recognized English executable; saves replace project copies only.'
''','shop family note')

# Limit IDs refer to EXE Limit records, not KERNEL attacks 0..127.
path=ROOT/'games/ff7/semantics.py'
replace_once(path,
'''def metadata_for(category: str, key: str) -> dict:
    if category in CORE and key in CORE[category]: return dict(CORE[category][key])
''',
'''def metadata_for(category: str, key: str) -> dict:
    if category == 'limits' and key in CORE['playerAttacks']: return dict(CORE['playerAttacks'][key])
    if category in CORE and key in CORE[category]: return dict(CORE[category][key])
''','limit semantics alias')
replace_once(path,
'''for level in ("11","12","21","22","31","32","4"):
    CHARACTERS[f"limitAttack{level}"] = reference("playerAttacks", label=f"Limit {level} attack", help="Player-attack record used by this Limit Break slot.")
''',
'''for level in ("11","12","21","22","31","32","4"):
    CHARACTERS[f"limitAttack{level}"] = reference("limits", label=f"Limit {level} attack", empty=255, value_key="gameId", help="Executable Limit Break attack record used by this slot; 255 means none.")
''','correct Limit references')

# Binary verification must include editable names/descriptions for all core KERNEL categories.
path=ROOT/'games/ff7/storage.py'
replace_once(path,
'''    if category in {'items','weapons','armor','accessories','materia'}:
        descriptions={r['id']:r.get('description') for r in expected}
        restored={r['id']:r.get('description') for r in actual}
        if descriptions!=restored:return False
''',
'''    if category in {'commands','playerAttacks','items','weapons','armor','accessories','materia'}:
        names={r['id']:r.get('name') for r in expected};restored_names={r['id']:r.get('name') for r in actual}
        descriptions={r['id']:r.get('description') for r in expected};restored={r['id']:r.get('description') for r in actual}
        if names!=restored_names or descriptions!=restored:return False
''','core name/description readback')

# UI: names are editable; Limit rows and references use linked KERNEL Limit text.
path=ROOT/'games/ff7/editor.html'
replace_once(path,
'''  const integrated=["accessories","armor","characters","initialState","initialInventory","initialMateria","stolenMateria","commands","playerAttacks","magicOrder","items","materia","weapons","enemies","encounters","enemyAttacks","shops","prices","texts","characterNames","growthCurves","growthBonuses","characterAI","enemyAI","formationAI","recruits","defaultNames","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"];
''',
'''  const integrated=["accessories","armor","characters","initialState","initialInventory","initialMateria","stolenMateria","commands","playerAttacks","limits","limitTexts","magicOrder","items","materia","weapons","enemies","encounters","enemyAttacks","shops","prices","texts","characterNames","growthCurves","growthBonuses","characterAI","enemyAI","formationAI","recruits","defaultNames","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"];
''','UI integrated Limits')
replace_once(path,
'''  const labels={accessories:"Accessories",armor:"Armor",characters:"Characters",initialState:"New game",initialInventory:"Starting inventory",initialMateria:"Starting Materia",stolenMateria:"Yuffie stolen Materia",commands:"Commands",playerAttacks:"Player attacks",magicOrder:"Magic menu",items:"Items",materia:"Materia",weapons:"Weapons",enemies:"Enemies",encounters:"Encounters",shops:"Shops",prices:"Prices",texts:"Text",enemyAttacks:"Enemy attacks",tweaks:"Tweaks",characterNames:"Initial names",growthCurves:"Growth curves",growthBonuses:"Growth bonuses",characterAI:"Character AI",enemyAI:"Enemy AI",formationAI:"Formation AI",recruits:"Recruits",defaultNames:"Default names",fieldEncounters:"Field encounters",worldEncounters:"World encounters",yuffieEncounters:"Yuffie encounters",chocoboRatings:"Chocobo ratings"};
''',
'''  const labels={accessories:"Accessories",armor:"Armor",characters:"Characters",initialState:"New game",initialInventory:"Starting inventory",initialMateria:"Starting Materia",stolenMateria:"Yuffie stolen Materia",commands:"Commands",playerAttacks:"Player attacks",limits:"Limit attacks",limitTexts:"Limit text",magicOrder:"Magic menu",items:"Items",materia:"Materia",weapons:"Weapons",enemies:"Enemies",encounters:"Encounters",shops:"Shops",prices:"Prices",texts:"Text",enemyAttacks:"Enemy attacks",tweaks:"Tweaks",characterNames:"Initial names",growthCurves:"Growth curves",growthBonuses:"Growth bonuses",characterAI:"Character AI",enemyAI:"Enemy AI",formationAI:"Formation AI",recruits:"Recruits",defaultNames:"Default names",fieldEncounters:"Field encounters",worldEncounters:"World encounters",yuffieEncounters:"Yuffie encounters",chocoboRatings:"Chocobo ratings"};
''','UI Limit labels')
replace_once(path,
'''  const groups={characters:["characters","characterNames","growthCurves","growthBonuses","characterAI","recruits","defaultNames"],initialState:["initialState","initialInventory","initialMateria","stolenMateria"],commands:["commands","playerAttacks","magicOrder"],enemies:["enemies","enemyAttacks","enemyAI"],encounters:["encounters","formationAI","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"],shops:["shops","prices"]};
''',
'''  const groups={characters:["characters","characterNames","growthCurves","growthBonuses","characterAI","recruits","defaultNames"],initialState:["initialState","initialInventory","initialMateria","stolenMateria"],commands:["commands","playerAttacks","limits","limitTexts","magicOrder"],enemies:["enemies","enemyAttacks","enemyAI"],encounters:["encounters","formationAI","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"],shops:["shops","prices"]};
''','UI Limit subtab')
replace_once(path,
'''  function candidateValue(field,candidate){return Number(candidate[field.referenceValueKey||"id"])}
  function candidateLabel(candidate){return String(candidate.values?.name||candidate.name||`Record ${candidate.id}`)}
  function referenceChoices(field,row){return referenceRows(field,row).map(candidate=>({value:candidateValue(field,candidate),label:candidateLabel(candidate),category:field.referenceCategory,recordId:Number(candidate.id)}))}
''',
'''  function candidateValue(field,candidate){return Number(candidate[field.referenceValueKey||"id"])}
  function displayRowName(row,group=state.tab){
    if(group==="limits"){const text=rowById("limitTexts",row.id);return String(text?.values?.name||row.name||`Limit ${Number(row.id)+1}`)}
    return String(row.values?.name||row.name||`Record ${row.id}`)
  }
  function candidateLabel(candidate,group){return displayRowName(candidate,group)}
  function referenceChoices(field,row){return referenceRows(field,row).map(candidate=>({value:candidateValue(field,candidate),label:candidateLabel(candidate,field.referenceCategory),category:field.referenceCategory,recordId:Number(candidate.id)}))}
''','UI linked Limit names')
replace_once(path,
'''    return specs.flatMap(([category,offset])=>(state.records[category]||[]).map(record=>({value:offset+Number(record.id),label:`${candidateLabel(record)} — ${labels[category]||category}`,category,recordId:Number(record.id)})));
''',
'''    return specs.flatMap(([category,offset])=>(state.records[category]||[]).map(record=>({value:offset+Number(record.id),label:`${candidateLabel(record,category)} — ${labels[category]||category}`,category,recordId:Number(record.id)})));
''','UI inventory labels')
replace_once(path,
'''  function descriptionControl(row){
''',
'''  function nameControl(row){
    const input=el("input",{type:"text",spellcheck:"false",value:row.name||"",disabled:readonly(),"aria-label":`Name for ${displayRowName(row)}`,oninput:event=>{if(readonly())return;row.name=event.target.value;shellRefresh()}});input.value=String(row.name||"");
    const vanilla=rowById(state.tab,row.id,state.data.vanilla)?.name||"";return provenanceControl({control:input,current:()=>row.name,vanilla,internal:true,apply:value=>{if(readonly())return;row.name=String(value);input.value=row.name;shellRefresh()}})
  }
  function descriptionControl(row){
''','UI name control')
replace_once(path,
'''    if(metadata.descriptionEditable)body.push(detailSection({title:"TEXT",body:detailField({label:"DESCRIPTION",help:infoHelp("The in-game description stored in this FF7 KERNEL.BIN. Byte escapes are preserved for game control codes."),control:descriptionControl(row),dataType:"TEXT"})}));
''',
'''    if(metadata.nameEditable||metadata.descriptionEditable)body.push(detailSection({title:"TEXT",body:[...(metadata.nameEditable?[detailField({label:"NAME",help:infoHelp("The in-game record name stored in FF7's KERNEL text section."),control:nameControl(row),dataType:"TEXT"})]:[]),...(metadata.descriptionEditable?[detailField({label:"DESCRIPTION",help:infoHelp("The in-game description stored in this FF7 KERNEL.BIN. Byte escapes are preserved for game control codes."),control:descriptionControl(row),dataType:"TEXT"})]:[])]}));
''','UI name/description section')
replace_once(path,
'''  function conceptPanel(row,body){return detailPanel({className:"ff7-detail",title:row.values.name||row.name,identity:recordId(row.id),meta:null,body})}
''',
'''  function conceptPanel(row,body){return detailPanel({className:"ff7-detail",title:displayRowName(row),identity:recordId(row.id),meta:null,body})}
''','UI concept linked title')
replace_once(path,
'''      {key:"name",label:"Name",sortable:true,grow:2,render:row=>el("span",{title:row.values.name||row.name},row.values.name||row.name)},
''',
'''      {key:"name",label:"Name",sortable:true,grow:2,render:row=>el("span",{title:displayRowName(row)},displayRowName(row))},
''','UI list linked name')
replace_once(path,
'''    const rows=[...state.records[group]].filter(row=>!query||`${row.id} ${row.values.name||row.name} ${searchableDescription?row.description||"":""} ${row.values.text||""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())).sort((a,b)=>{const left=a[sort.key],right=b[sort.key];return(typeof left==="string"?left.localeCompare(right):Number(left)-Number(right))*sort.dir});
''',
'''    const rows=[...state.records[group]].filter(row=>!query||`${row.id} ${displayRowName(row,group)} ${searchableDescription?row.description||"":""} ${row.values.text||""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())).sort((a,b)=>{const left=sort.key==="name"?displayRowName(a,group):a[sort.key],right=sort.key==="name"?displayRowName(b,group):b[sort.key];return(typeof left==="string"?left.localeCompare(right):Number(left)-Number(right))*sort.dir});
''','UI linked search/sort')

# Regression fixtures: provide the extra 71 Magic text strings and prove Limit ID semantics/name writes.
path=ROOT/'tools/verify_ff7_datasets.py'
replace_once(path,
'''    for key, category in base.CATEGORIES.items():
        sections[category.section - 1] = bytearray(category.record_size * COUNTS[key])
        sections[category.text_name_section - 1] = text_table(COUNTS[key], "Record")
        sections[category.text_description_section - 1] = text_table(COUNTS[key], "Help")
    return sections
''',
'''    for key, category in base.CATEGORIES.items():
        sections[category.section - 1] = bytearray(category.record_size * COUNTS[key])
        sections[category.text_name_section - 1] = text_table(COUNTS[key], "Record")
        sections[category.text_description_section - 1] = text_table(COUNTS[key], "Help")
    sections[18]=text_table(199,"Magic");sections[10]=text_table(199,"MagicHelp")
    return sections
''','fixture Limit text counts')
replace_once(path,
'''                self.assertEqual(sum(map(len, data["records"].values())), 1298)
''',
'''                self.assertEqual(sum(map(len, data["records"].values())), 1369)
''','kernel record count with Limit text')
insert='''\n    def test_core_names_and_limit_text_are_editable_without_cross_section_changes(self):\n        original=Kernel(self.source)\n        kernel=Kernel(self.source);rows=kernel.records("items");rows[0]["name"]="Renamed Item";kernel.apply("items",rows)\n        changed=[i for i,(a,b) in enumerate(zip(original.sections,kernel.sections)) if a!=b]\n        self.assertEqual(changed,[19]);self.assertEqual(kernel.records("items")[0]["name"],"Renamed Item")\n        kernel=Kernel(self.source);rows=kernel.records("limitTexts");self.assertEqual(len(rows),71);self.assertEqual(rows[0]["values"]["name"],"Magic128")\n        rows[0]["values"].update(name="Braver X",description="Limit help X");kernel.apply("limitTexts",rows)\n        changed=[i for i,(a,b) in enumerate(zip(original.sections,kernel.sections)) if a!=b]\n        self.assertEqual(changed,[10,18]);restored=kernel.records("limitTexts")[0]["values"];self.assertEqual(restored,{"name":"Braver X","description":"Limit help X"})\n\n'''
replace_once(path,
'''    def test_noop_preserves_all_decoded_bytes(self):
''',insert+'''    def test_noop_preserves_all_decoded_bytes(self):
''','name/Limit text regression')

path=ROOT/'tools/verify_ff7_extended.py'
replace_once(path,
'''    for i in range(10):
        at=0x5202B8+shift+i*12;data[at:at+12]=codec.encode_text(f'Name{i}').ljust(12,b'\\xff')
''',
'''    for i in range(71):
        at=0x51DCD4+shift+i*28;data[at:at+28]=bytes((i&0xFF,))*28
    for i in range(10):
        at=0x5202B8+shift+i*12;data[at:at+12]=codec.encode_text(f'Name{i}').ljust(12,b'\\xff')
''','EXE Limit fixture')
replace_once(path,
'''                obj=ex.ShopExecutable(source,source);rows=obj.records('shops')
                rows[0]['values']['item0']=17;obj.apply('shops',rows)
''',
'''                obj=ex.ShopExecutable(source,source);limits=obj.records('limits');self.assertEqual((len(limits),limits[0]['gameId']),(71,128))
                limits[0]['values']['attackPower']=77;obj.apply('limits',limits)
                rows=obj.records('shops');rows[0]['values']['item0']=17;obj.apply('shops',rows)
''','EXE Limit test edit')
replace_once(path,
'''                allowed={0x521A18+shift+8}|set(range(0x523A58+shift+95*4,0x523A58+shift+96*4))
''',
'''                allowed={0x51DCD4+shift+15,0x521A18+shift+8}|set(range(0x523A58+shift+95*4,0x523A58+shift+96*4))
''','EXE Limit allowed byte')
replace_once(path,
'''                self.assertEqual(ex.ShopExecutable(saved,source).records('prices'),obj.records('prices'))
''',
'''                reread=ex.ShopExecutable(saved,source);self.assertEqual(reread.records('prices'),obj.records('prices'));self.assertEqual(reread.records('limits'),obj.records('limits'))
''','EXE Limit readback')

path=ROOT/'tools/verify_ff7_semantic_surface.py'
replace_once(path,
'''        self.assertEqual(meta["characters"]["limitAttack11"]["referenceCategory"],"playerAttacks")
''',
'''        self.assertEqual(meta["characters"]["limitAttack11"]["referenceCategory"],"limits")
        self.assertEqual(meta["characters"]["limitAttack11"]["referenceValueKey"],"gameId")
        self.assertEqual(meta["characters"]["limitAttack11"]["emptyValue"],255)
''','Limit semantic regression')

# Rendered UI proves the Character selector resolves EXE Limit ID 128 to KERNEL Limit text and names are editable.
path=ROOT/'tools/verify_ff7_rendered_neutral.py'
insert='''\n\ndef test_limit_reference_and_core_name_editing_are_semantic(self):\n    self.install();self.open();self.navigate("characters")\n    selector=self.page.get_by_label("Limit 11 attack for Slot0",exact=True);self.assertEqual(selector.evaluate("e=>e.tagName"),"SELECT")\n    selector.select_option("128");self.assertIn("Magic128",selector.locator("option:checked").inner_text())\n    self.navigate("limits");self.assertIn("Magic128",self.page.get_by_label("Limit attacks records").inner_text())\n    self.navigate("items");name=self.page.get_by_label("Name for Record0",exact=True);name.fill("Renamed Item")\n    self.page.get_by_role("button",name="Save").click();self.page.wait_for_timeout(150)\n    self.assertEqual(self.page.get_by_label("Name for Renamed Item",exact=True).input_value(),"Renamed Item")\n    self.originals_unchanged()\n'''
replace_once(path,
'''target.RenderedTests.open = open_with_neutral
''',insert+'''\ntarget.RenderedTests.open = open_with_neutral
''','rendered Limit/name test')
replace_once(path,
'''target.RenderedTests.test_holistic_ff7_concept_views_and_new_game_data = test_holistic_ff7_concept_views_and_new_game_data
''',
'''target.RenderedTests.test_holistic_ff7_concept_views_and_new_game_data = test_holistic_ff7_concept_views_and_new_game_data
target.RenderedTests.test_limit_reference_and_core_name_editing_are_semantic = test_limit_reference_and_core_name_editing_are_semantic
''','register rendered Limit/name test')
