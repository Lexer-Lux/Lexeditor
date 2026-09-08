from pathlib import Path


def replace_once(path, old, new):
    target = Path(path)
    text = target.read_text()
    if old not in text:
        raise SystemExit(f"expected patch anchor missing in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1))


extended = "games/ff7/extended.py"

replace_once(
    extended,
    "DEFAULT_NAME_FIELDS = [text('name','Default name',0,12)]\nPRICE_TABLES = [('Items', 0, 128), ('Weapons', 128, 128), ('Armor', 256, 32),\n                ('Accessories', 288, 32), ('Materia', 384, 96)]\n",
    """DEFAULT_NAME_FIELDS = [text('name','Default name',0,12)]
LIMIT_FIELDS = [number(k,l,o,s,group=g) for k,l,o,s,g in (
    ('accuracyRate','Accuracy',0x00,1,'Damage'), ('impactEffectId','Impact effect ID',0x01,1,'Advanced / engine data'),
    ('targetHurtActionIndex','Target hurt action ID',0x02,1,'Advanced / engine data'), ('mpCost','MP cost',0x04,2,'Cost'),
    ('impactSound','Impact sound ID',0x06,2,'Advanced / engine data'), ('cameraMovementIdSingle','Single-target camera ID',0x08,2,'Advanced / engine data'),
    ('cameraMovementIdMulti','Multi-target camera ID',0x0A,2,'Advanced / engine data'), ('targetData','Target flags',0x0C,1,'Targeting'),
    ('attackEffectId','Attack visual effect ID',0x0D,1,'Advanced / engine data'), ('damageCalculationId','Damage formula',0x0E,1,'Damage'),
    ('attackPower','Power',0x0F,1,'Damage'), ('conditionSubmenu','Condition submenu',0x10,1,'Status / condition'),
    ('statusChange','Status change',0x11,1,'Status / condition'), ('additionalEffects','Additional behavior',0x12,1,'Extra behavior'),
    ('additionalEffectsModifier','Effect modifier',0x13,1,'Extra behavior'), ('statusFlags','Statuses',0x14,4,'Status / condition'),
    ('elementFlags','Elements',0x18,2,'Damage'), ('specialAttackFlags','Special attack flags',0x1A,2,'Extra behavior'),
)]
MATERIA_EQUIP_FIELDS = [number(key, label, i * 2, 2, signed=True, group='Stat changes')
                        for i, (key, label) in enumerate((
                            ('strength','Strength'), ('vitality','Vitality'), ('magic','Magic'), ('spirit','Spirit'),
                            ('dexterity','Dexterity'), ('luck','Luck'), ('hpPercent','HP %'), ('mpPercent','MP %')))]
ITEM_SORT_FIELDS = [number('position','Name-sort position',0,2,group='Menu ordering')]
MATERIA_PRIORITY_FIELDS = [number('priority','Menu priority',0,1,group='Menu ordering')]
AUDIO_FIELDS = [number('volume','Volume',0,4,signed=True,group='Audio mixing'),
                number('pan','Pan',4,4,signed=True,group='Audio mixing')]
AP_MULTIPLIER_FIELDS = [number('multiplier','Master Materia sale AP multiplier',0,1,group='Economy')]
EXE_TEXT_FIELDS = [text('text','Text',size=65535)]
PRICE_TABLES = [('Items', 0, 128), ('Weapons', 128, 128), ('Armor', 256, 32),
                ('Accessories', 288, 32), ('Materia', 384, 96)]


def _exe_text_records():
    records = []
    def add_block(label, start, count, size, first=1):
        for index in range(count):
            records.append({'name':f'{label} {first + index}', 'offset':start + index * size, 'size':size})

    add_block('Quit menu text', 0x517F70, 3, 30)
    add_block('Quit menu text', 0x517FD0, 2, 4, 4)
    add_block('Config menu text', 0x5184A8, 51, 48)
    add_block('Main menu text', 0x518EC0, 23, 20)
    add_block('Battle status name', 0x51CE28, 27, 10)
    cursor, arena_index = 0x51D188, 1
    for size, count in ((16,1),(24,1),(22,4),(32,25),(34,3)):
        for _ in range(count):
            records.append({'name':f'Battle Arena text {arena_index}', 'offset':cursor, 'size':size})
            cursor += size; arena_index += 1
    add_block('Bizarro menu text', 0x51D740, 6, 38)
    add_block('Limit menu text', 0x51DAD8, 14, 36)
    add_block('Element name', 0x51EB40, 9, 10)
    add_block('Status menu effect name', 0x51EBA0, 27, 20)
    add_block('Status menu text', 0x51EDC0, 27, 15)
    add_block('Equip menu text', 0x51EFA8, 23, 12)
    add_block('Unequip text', 0x51F118, 4, 36)
    add_block('Materia menu text', 0x51F1A8, 42, 20)
    add_block('Magic menu text', 0x51F5E8, 14, 20)
    add_block('Item menu text', 0x51F768, 11, 12)
    cursor = 0x51F7F0
    characters = ('Cloud','Barret','Tifa','Aerith','Red XIII','Yuffie','Vincent','Cid','Cait Sith')
    for index, character in enumerate(characters):
        kinds = ('success','failure','wrong character') if index < 8 else ('wrong character',)
        for kind in kinds:
            records.append({'name':f'Level 4 Limit {character} — {kind}', 'offset':cursor, 'size':34})
            cursor += 34
    add_block('Shop name', 0x5215C8, 9, 20)
    add_block('Shop text', 0x521680, 18, 46)
    add_block('Save menu text', 0x523D60, 36, 36)
    add_block('Chocobo race prize name', 0x57AFD0, 24, 16)
    add_block('Chocobo name', 0x57B258, 46, 7)
    records.append({'name':'Teioh name', 'offset':0x57AEA8, 'size':7})
    return tuple(records)


EXE_TEXT_RECORDS = _exe_text_records()
EXE_EDIT_RANGES = [
    (0x5202B8,120), (0x520810,264), (0x521A18,80*84), (0x523458,320*4), (0x523A58,96*4),
    (0x51DCD4,71*28), (0x4FD4C8,21*16), (0x51FB48,320*2), (0x51FDC8,96),
    (0x565C60,128*4), (0x565E60,128*4), (0x31ED4F,1), (0x31ED9E,1),
] + [(row['offset'], row['size']) for row in EXE_TEXT_RECORDS]
"""
)

replace_once(
    extended,
    """        if identity not in EXE_PROFILES:
            raise ValueError(f'Unsupported English executable SHA-1 {identity}. Shop editing requires a known build; no offsets are guessed.')
        self.shift = EXE_PROFILES[identity]
        if source[:2] != b'MZ' or source[self.shift:self.shift + 4] != b'\\x55\\x8b\\xec\\xc7':
            raise ValueError('Executable identity/header mismatch')
        if len(data) != len(source):
            raise ValueError('Project executable length differs from the supported source')
        bounds(data, 0x523A58 + self.shift, 96 * 4)
        self.original, self.data = bytes(data), bytearray(data)
        # Only our documented data ranges may differ from the supported source.
        # This prevents a foreign executable project from inheriting its profile.
        ranges = [(0x5202B8,120),(0x520810,264),(0x521A18,80*84),
                  (0x523458,320*4),(0x523A58,96*4)]
        cursor = 0
        for start, size in sorted(ranges):
            start += self.shift
            if data[cursor:start] != source[cursor:start]:
                raise ValueError('Project executable contains changes outside supported data')
            cursor = start + size
        if data[cursor:] != source[cursor:]:
            raise ValueError('Project executable contains changes outside supported data')
""",
    """        if identity not in EXE_PROFILES:
            raise ValueError(f'Unsupported English executable SHA-1 {identity}. Executable editing requires a known build; no offsets are guessed.')
        self.shift = EXE_PROFILES[identity]
        if source[:2] != b'MZ' or source[self.shift:self.shift + 4] != b'\\x55\\x8b\\xec\\xc7':
            raise ValueError('Executable identity/header mismatch')
        if len(data) != len(source):
            raise ValueError('Project executable length differs from the supported source')
        for start, size in EXE_EDIT_RANGES:
            bounds(data, start + self.shift, size)
        self.original, self.data = bytes(data), bytearray(data)
        # Only Scarlet-proved, explicitly modeled data ranges may differ from
        # the supported source. A project EXE never inherits a profile merely
        # because its launcher/header happens to look compatible.
        cursor = 0
        for start, size in sorted(EXE_EDIT_RANGES):
            start += self.shift
            if data[cursor:start] != source[cursor:start]:
                raise ValueError('Project executable contains changes outside supported data')
            cursor = start + size
        if data[cursor:] != source[cursor:]:
            raise ValueError('Project executable contains changes outside supported data')
"""
)

replace_once(
    extended,
    """    def records(self, category):
        if category in ('recruits','defaultNames'):
""",
    """    def records(self, category):
        if category == 'limitBreaks':
            return [{'id':i, 'name':f'Limit break {i}',
                     'description':'Executable Limit attack data. Names/descriptions remain in the game text tables.',
                     'values':read_values(self.data[0x51DCD4+self.shift+i*28:0x51DCD4+self.shift+(i+1)*28], LIMIT_FIELDS)}
                    for i in range(71)]
        if category == 'materiaEquipEffects':
            return [{'id':i, 'name':f'Materia equip effect {i}',
                     'description':'Shared stat-change template selected by Materia equip-effect IDs; HP/MP values are percentage points.',
                     'values':read_values(self.data[0x4FD4C8+self.shift+i*16:0x4FD4C8+self.shift+(i+1)*16], MATERIA_EQUIP_FIELDS)}
                    for i in range(21)]
        if category == 'exeText':
            rows = []
            for i, spec in enumerate(EXE_TEXT_RECORDS):
                at = spec['offset'] + self.shift
                fields = [text('text','Text',0,spec['size'])]
                rows.append({'id':i, 'name':spec['name'],
                             'description':f'Fixed executable text field; maximum encoded storage is {spec["size"]} bytes. Unchanged padding/control bytes are preserved.',
                             'values':read_values(self.data[at:at+spec['size']], fields)})
            return rows
        if category == 'itemSortOrder':
            return [{'id':i, 'name':f'Inventory item ID {i}',
                     'description':'Position used by FF7 when sorting the 320 item/equipment IDs by name.',
                     'values':{'position':read_int(self.data,0x51FB48+self.shift+i*2,2)}} for i in range(320)]
        if category == 'materiaPriority':
            return [{'id':i, 'name':f'Materia {i}',
                     'description':'Priority byte used by the Materia menu ordering logic.',
                     'values':{'priority':read_int(self.data,0x51FDC8+self.shift+i,1)}} for i in range(96)]
        if category == 'audioMixing':
            return [{'id':i, 'name':f'Audio slot {i}',
                     'description':'Executable audio mix table entry. Slot-to-sound identity remains engine data.',
                     'values':{'volume':read_int(self.data,0x565C60+self.shift+i*4,4,True),
                               'pan':read_int(self.data,0x565E60+self.shift+i*4,4,True)}} for i in range(128)]
        if category == 'apMultiplier':
            return [{'id':0, 'name':'Master Materia sale price',
                     'description':'AP multiplier used when pricing mastered Materia for sale. FF7 stores the value in two executable instructions; both copies are updated together.',
                     'values':{'multiplier':read_int(self.data,0x31ED4F+self.shift,1)}}]
        if category in ('recruits','defaultNames'):
"""
)

replace_once(
    extended,
    """    def apply(self, category, rows):
        validate_rows(rows, self.records(category))
        if category in ('recruits','defaultNames'):
""",
    """    def apply(self, category, rows):
        validate_rows(rows, self.records(category))
        if category in ('limitBreaks','materiaEquipEffects'):
            start, size, fields = (0x51DCD4,28,LIMIT_FIELDS) if category == 'limitBreaks' else (0x4FD4C8,16,MATERIA_EQUIP_FIELDS)
            replacement = bytearray(self.data)
            for row in rows:
                at = start + self.shift + row['id'] * size
                replacement[at:at+size] = write_values(self.data[at:at+size],fields,row.get('values'))
            self.data = replacement
            return
        if category == 'exeText':
            replacement = bytearray(self.data)
            for row in rows:
                spec = EXE_TEXT_RECORDS[row['id']]; at = spec['offset'] + self.shift
                fields = [text('text','Text',0,spec['size'])]
                replacement[at:at+spec['size']] = write_values(self.data[at:at+spec['size']],fields,row.get('values'))
            self.data = replacement
            return
        if category in ('itemSortOrder','materiaPriority'):
            start, size, fields = (0x51FB48,2,ITEM_SORT_FIELDS) if category == 'itemSortOrder' else (0x51FDC8,1,MATERIA_PRIORITY_FIELDS)
            replacement = bytearray(self.data)
            for row in rows:
                at = start + self.shift + row['id'] * size
                replacement[at:at+size] = write_values(self.data[at:at+size],fields,row.get('values'))
            self.data = replacement
            return
        if category == 'audioMixing':
            replacement = bytearray(self.data)
            for row in rows:
                volume = 0x565C60 + self.shift + row['id'] * 4
                pan = 0x565E60 + self.shift + row['id'] * 4
                virtual = self.data[volume:volume+4] + self.data[pan:pan+4]
                written = write_values(virtual,AUDIO_FIELDS,row.get('values'))
                replacement[volume:volume+4] = written[:4]; replacement[pan:pan+4] = written[4:]
            self.data = replacement
            return
        if category == 'apMultiplier':
            written = write_values(self.data[0x31ED4F+self.shift:0x31ED50+self.shift],AP_MULTIPLIER_FIELDS,rows[0].get('values'))
            replacement = bytearray(self.data)
            replacement[0x31ED4F+self.shift] = written[0]
            replacement[0x31ED9E+self.shift] = written[0]
            self.data = replacement
            return
        if category in ('recruits','defaultNames'):
"""
)

replace_once(
    extended,
    """    'shop': {'categories':{'shops':{'label':'Shops','fields':SHOP_FIELDS}, 'prices':{'label':'Prices','fields':PRICE_FIELDS}, 'recruits':{'label':'Recruits','fields':RECRUIT_FIELDS}, 'defaultNames':{'label':'Default names','fields':DEFAULT_NAME_FIELDS}},
             'source':'Supported English game executable',
             'note':'80 shop inventories and global item/equipment/materia prices in a supported executable. Saves write a project copy, never the installed executable. Shop-opening scripts are unchanged.'},
""",
    """    'shop': {'categories':{
                 'shops':{'label':'Shops','fields':SHOP_FIELDS}, 'prices':{'label':'Prices','fields':PRICE_FIELDS},
                 'recruits':{'label':'Recruits','fields':RECRUIT_FIELDS}, 'defaultNames':{'label':'Default names','fields':DEFAULT_NAME_FIELDS},
                 'limitBreaks':{'label':'Limit breaks','fields':LIMIT_FIELDS},
                 'materiaEquipEffects':{'label':'Materia equip effects','fields':MATERIA_EQUIP_FIELDS},
                 'exeText':{'label':'Executable text','fields':EXE_TEXT_FIELDS},
                 'itemSortOrder':{'label':'Item name sort','fields':ITEM_SORT_FIELDS},
                 'materiaPriority':{'label':'Materia priority','fields':MATERIA_PRIORITY_FIELDS},
                 'audioMixing':{'label':'Audio mixing','fields':AUDIO_FIELDS},
                 'apMultiplier':{'label':'Master Materia sale price','fields':AP_MULTIPLIER_FIELDS}},
             'source':'Supported English game executable',
             'note':'Scarlet-proved executable data: shops/prices, initialization, Limit attacks, Materia equip effects, fixed UI/battle text, menu ordering, audio mix values and the mastered-Materia sale multiplier. Saves write a project copy, never the installed executable.'},
"""
)

replace_once(
    extended,
    "FAMILIES['shop']['note']='Shop inventories, prices, default names and Cait Sith/Vincent starting data in a recognized English executable; saves replace project copies only.'\n",
    "FAMILIES['shop']['note']='Named, fixed-layout data proved by Scarlet in a recognized English executable; saves replace project copies only and reject changes outside explicitly modeled ranges.'\n"
)

semantics = "games/ff7/semantics.py"
replace_once(
    semantics,
    """def metadata_for(category: str, key: str) -> dict:
    if category in CORE and key in CORE[category]: return dict(CORE[category][key])
""",
    """def metadata_for(category: str, key: str) -> dict:
    if category == 'limitBreaks' and key in CORE['playerAttacks']: return dict(CORE['playerAttacks'][key])
    if category in CORE and key in CORE[category]: return dict(CORE[category][key])
"""
)
replace_once(
    semantics,
    """    \"prices\": \"Price\", \"fieldEncounters\": \"Encounter settings\", \"worldEncounters\": \"Encounter settings\",\n""",
    """    \"prices\": \"Price\", \"limitBreaks\": \"Attack\", \"materiaEquipEffects\": \"Stat changes\",\n    \"itemSortOrder\": \"Menu ordering\", \"materiaPriority\": \"Menu ordering\", \"audioMixing\": \"Audio mixing\",\n    \"apMultiplier\": \"Economy\", \"fieldEncounters\": \"Encounter settings\", \"worldEncounters\": \"Encounter settings\",\n"""
)

editor = "games/ff7/editor.html"
replace_once(
    editor,
    '  const integrated=["accessories","armor","characters","initialState","initialInventory","initialMateria","stolenMateria","commands","playerAttacks","magicOrder","items","materia","weapons","enemies","encounters","enemyAttacks","shops","prices","texts","characterNames","growthCurves","growthBonuses","characterAI","enemyAI","formationAI","recruits","defaultNames","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"];\n',
    '  const integrated=["accessories","armor","characters","initialState","initialInventory","initialMateria","stolenMateria","commands","playerAttacks","limitBreaks","magicOrder","items","itemSortOrder","materia","materiaEquipEffects","materiaPriority","apMultiplier","weapons","enemies","encounters","enemyAttacks","shops","prices","texts","exeText","audioMixing","characterNames","growthCurves","growthBonuses","characterAI","enemyAI","formationAI","recruits","defaultNames","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"];\n'
)
replace_once(
    editor,
    '  const labels={accessories:"Accessories",armor:"Armor",characters:"Characters",initialState:"New game",initialInventory:"Starting inventory",initialMateria:"Starting Materia",stolenMateria:"Yuffie stolen Materia",commands:"Commands",playerAttacks:"Player attacks",magicOrder:"Magic menu",items:"Items",materia:"Materia",weapons:"Weapons",enemies:"Enemies",encounters:"Encounters",shops:"Shops",prices:"Prices",texts:"Text",enemyAttacks:"Enemy attacks",tweaks:"Tweaks",characterNames:"Initial names",growthCurves:"Growth curves",growthBonuses:"Growth bonuses",characterAI:"Character AI",enemyAI:"Enemy AI",formationAI:"Formation AI",recruits:"Recruits",defaultNames:"Default names",fieldEncounters:"Field encounters",worldEncounters:"World encounters",yuffieEncounters:"Yuffie encounters",chocoboRatings:"Chocobo ratings"};\n',
    '  const labels={accessories:"Accessories",armor:"Armor",characters:"Characters",initialState:"New game",initialInventory:"Starting inventory",initialMateria:"Starting Materia",stolenMateria:"Yuffie stolen Materia",commands:"Commands",playerAttacks:"Player attacks",limitBreaks:"Limit breaks",magicOrder:"Magic menu",items:"Items",itemSortOrder:"Name sort",materia:"Materia",materiaEquipEffects:"Equip effects",materiaPriority:"Menu priority",apMultiplier:"Master sale price",weapons:"Weapons",enemies:"Enemies",encounters:"Encounters",shops:"Shops",prices:"Prices",texts:"Text",exeText:"Executable text",audioMixing:"Audio mixing",enemyAttacks:"Enemy attacks",tweaks:"Tweaks",characterNames:"Initial names",growthCurves:"Growth curves",growthBonuses:"Growth bonuses",characterAI:"Character AI",enemyAI:"Enemy AI",formationAI:"Formation AI",recruits:"Recruits",defaultNames:"Default names",fieldEncounters:"Field encounters",worldEncounters:"World encounters",yuffieEncounters:"Yuffie encounters",chocoboRatings:"Chocobo ratings"};\n'
)
replace_once(
    editor,
    '  const groups={characters:["characters","characterNames","growthCurves","growthBonuses","characterAI","recruits","defaultNames"],initialState:["initialState","initialInventory","initialMateria","stolenMateria"],commands:["commands","playerAttacks","magicOrder"],enemies:["enemies","enemyAttacks","enemyAI"],encounters:["encounters","formationAI","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"],shops:["shops","prices"]};\n',
    '  const groups={characters:["characters","characterNames","growthCurves","growthBonuses","characterAI","recruits","defaultNames"],initialState:["initialState","initialInventory","initialMateria","stolenMateria"],commands:["commands","playerAttacks","limitBreaks","magicOrder"],items:["items","itemSortOrder"],materia:["materia","materiaEquipEffects","materiaPriority","apMultiplier"],enemies:["enemies","enemyAttacks","enemyAI"],encounters:["encounters","formationAI","fieldEncounters","worldEncounters","yuffieEncounters","chocoboRatings"],shops:["shops","prices"],texts:["texts","exeText"]};\n'
)

verify = "tools/verify_ff7_extended.py"
replace_once(
    verify,
    """def exe_fixture(shift=0x400):
    data = bytearray(0x525000)
    data[:2] = b'MZ'; data[shift:shift+4]=b'\\x55\\x8b\\xec\\xc7'
""",
    """def exe_fixture(shift=0x400):
    data = bytearray(0x57C000)
    data[:2] = b'MZ'; data[shift:shift+4]=b'\\x55\\x8b\\xec\\xc7'
    for spec in ex.EXE_TEXT_RECORDS:
        at=spec['offset']+shift;data[at:at+spec['size']]=codec.encode_text('X').ljust(spec['size'],b'\\xff')
    for i in range(320):struct.pack_into('<H',data,0x51FB48+shift+i*2,i)
    for i in range(96):data[0x51FDC8+shift+i]=i
    data[0x31ED4F+shift]=data[0x31ED9E+shift]=2
    for i in range(128):
        struct.pack_into('<i',data,0x565C60+shift+i*4,i)
        struct.pack_into('<i',data,0x565E60+shift+i*4,-i)
"""
)
replace_once(
    verify,
    "\n\nclass SaveTests(unittest.TestCase):\n",
    """

    def test_exe_named_surface_roundtrip_and_isolation(self):
        source=exe_fixture();sha=hashlib.sha1(source).hexdigest().upper();shift=0x400
        with patch.dict(ex.EXE_PROFILES,{sha:shift}):
            obj=ex.ShopExecutable(source,source)
            expected={'limitBreaks':71,'materiaEquipEffects':21,'exeText':476,'itemSortOrder':320,
                      'materiaPriority':96,'audioMixing':128,'apMultiplier':1}
            self.assertEqual({key:len(obj.records(key)) for key in expected},expected)
            for key in expected:obj.apply(key,obj.records(key))
            self.assertEqual(obj.to_bytes(),source)

            rows=obj.records('limitBreaks');rows[0]['values']['attackPower']=77;obj.apply('limitBreaks',rows)
            rows=obj.records('materiaEquipEffects');rows[0]['values']['strength']=-7;obj.apply('materiaEquipEffects',rows)
            rows=obj.records('exeText');rows[0]['values']['text']='Quit';obj.apply('exeText',rows)
            rows=obj.records('itemSortOrder');rows[319]['values']['position']=7;obj.apply('itemSortOrder',rows)
            rows=obj.records('materiaPriority');rows[95]['values']['priority']=1;obj.apply('materiaPriority',rows)
            rows=obj.records('audioMixing');rows[0]['values']['volume']=-123;rows[0]['values']['pan']=456;obj.apply('audioMixing',rows)
            rows=obj.records('apMultiplier');rows[0]['values']['multiplier']=3;obj.apply('apMultiplier',rows)
            saved=obj.to_bytes(); reread=ex.ShopExecutable(saved,source)
            self.assertEqual(reread.records('limitBreaks')[0]['values']['attackPower'],77)
            self.assertEqual(reread.records('materiaEquipEffects')[0]['values']['strength'],-7)
            self.assertEqual(reread.records('exeText')[0]['values']['text'],'Quit')
            self.assertEqual(reread.records('itemSortOrder')[319]['values']['position'],7)
            self.assertEqual(reread.records('materiaPriority')[95]['values']['priority'],1)
            self.assertEqual(reread.records('audioMixing')[0]['values'],{'volume':-123,'pan':456})
            self.assertEqual(reread.records('apMultiplier')[0]['values']['multiplier'],3)
            self.assertEqual(saved[0x31ED4F+shift],3);self.assertEqual(saved[0x31ED9E+shift],3)

            bad=bytearray(saved);bad[0x51CF40+shift]^=1
            with self.assertRaisesRegex(ValueError,'outside supported data'):ex.ShopExecutable(bytes(bad),source)
            rows=reread.records('exeText');rows[0]['values']['text']='x'*100
            with self.assertRaises(ValueError):reread.apply('exeText',rows)


class SaveTests(unittest.TestCase):
"""
)

print('FF7 executable surface patch applied')
