"""Character growth/AI and the remaining documented KERNEL section 3/4 data.

Offsets: Shojy/Elena d85e026 CharacterData.cs, BattleAndGrowthData.cs,
InitialData.cs, StatCurve.cs, SpellIndex.cs and InventoryItem/InventoryMateria.
Unknown bytes, the RNG table and scene lookup table remain preserved.
"""
from __future__ import annotations

from . import ai
from .battle import number, text, read_values, write_values, validate_rows
from .format_codec import bounds, read_int

BRACKETS=('2–11','12–21','22–31','32–41','42–51','52–61','62–81','82–99')
CURVE_FIELDS=[f for i,bracket in enumerate(BRACKETS) for f in (
    number(f'gradient{i}','Gradient',i*2,group='Levels '+bracket),
    number(f'base{i}','Base (ignored for experience)',i*2+1,signed=True,group='Levels '+bracket))]
BONUS_FIELDS=[number(f'bonus{i}',f'Difference bracket {i}',i) for i in range(12)]
NAME_FIELDS=[text('name','Initial name',0,12)]
INITIAL_STATE_FIELDS=[
    number('party1','Party member 1',0,maximum=255,group='Starting party'),
    number('party2','Party member 2',1,maximum=255,group='Starting party'),
    number('party3','Party member 3',2,maximum=255,group='Starting party'),
    number('gil','Starting gil',3,size=4,maximum=0xFFFFFFFF,group='Starting resources'),
]
INITIAL_INVENTORY_FIELDS=[
    number('item','Item / equipment',0,size=2,maximum=0x1FF,group='Starting inventory'),
    number('amount','Quantity',0,maximum=0x7F,group='Starting inventory'),
]
INITIAL_MATERIA_FIELDS=[
    number('materia','Materia',0,maximum=0xFF,group='Starting Materia'),
    number('ap','AP',1,size=3,maximum=0xFFFFFF,group='Starting Materia'),
]
MAGIC_ORDER_FIELDS=[
    number('menuGroup','Magic-menu section',0,maximum=0xFF,group='Menu placement'),
    number('position','Position within section',0,maximum=31,group='Menu placement'),
]

EXTRAS={
    'characterNames':{'label':'Initial names','fields':NAME_FIELDS,'section':4,'offset':0x10,'stride':132,'count':9,'size':12},
    'growthCurves':{'label':'Growth curves','fields':CURVE_FIELDS,'section':3,'offset':0x21C,'stride':16,'count':64,'size':16},
    'growthBonuses':{'label':'Growth bonuses','fields':BONUS_FIELDS,'section':3,'offset':0x1F8,'stride':12,'count':3,'size':12},
    'characterAI':{'label':'Character AI','fields':ai.metadata(),'section':3},
    'magicOrder':{'label':'Magic menu','fields':MAGIC_ORDER_FIELDS,'section':3},
    'initialState':{'label':'Starting setup','fields':INITIAL_STATE_FIELDS,'section':4},
    'initialInventory':{'label':'Starting inventory','fields':INITIAL_INVENTORY_FIELDS,'section':4},
    'initialMateria':{'label':'Starting Materia','fields':INITIAL_MATERIA_FIELDS,'section':4},
    'stolenMateria':{'label':'Yuffie stolen Materia','fields':INITIAL_MATERIA_FIELDS,'section':4},
}


def _initial_section(kernel):
    raw=kernel.sections[3]
    bounds(raw,0,0xB2C)
    return raw


def _growth_section(kernel):
    raw=kernel.sections[2]
    bounds(raw,0,0xF94)
    return raw


def _global_inventory_name(kernel,item):
    if item==0x1FF:return 'Empty'
    for category,start,count in (('items',0,128),('weapons',128,128),('armor',256,32),('accessories',288,32)):
        if start<=item<start+count:
            rows=kernel.records(category)
            index=item-start
            if index<len(rows):return rows[index].get('name') or f'{category} {index}'
    return f'Unknown item {item}'


def _materia_name(kernel,index):
    if index==0xFF:return 'Empty'
    rows=kernel.records('materia')
    if 0<=index<len(rows):return rows[index].get('name') or f'Materia {index}'
    return f'Unknown Materia {index}'


def records(kernel,key):
    spec=EXTRAS[key]
    if key=='characterAI':
        raw=kernel.sections[2];bounds(raw,0x61C,2048)
        return ai.Pool(raw[0x61C:0xE1C],12).records('Character AI owner')
    if key=='magicOrder':
        raw=_growth_section(kernel);attacks=kernel.records('playerAttacks')
        rows=[]
        for i in range(56):
            packed=raw[0xF5C+i]
            group,position=(0xFF,0) if packed==0xFF else (packed>>5,packed&0x1F)
            name=attacks[i].get('name') if i<len(attacks) else None
            rows.append({'id':i,'name':name or f'Player attack {i}',
                         'description':'Controls where this spell appears in the Magic command menu; 0xFF means unlisted.',
                         'values':{'menuGroup':group,'position':position}})
        return rows
    if key=='initialState':
        raw=_initial_section(kernel)
        values={'party1':raw[0x4A4],'party2':raw[0x4A5],'party3':raw[0x4A6],
                'gil':read_int(raw,0xB28,4)}
        return [{'id':0,'name':'New game defaults',
                 'description':'Party and gil copied into a new save. Existing saves are not rewritten.',
                 'values':values}]
    if key=='initialInventory':
        raw=_initial_section(kernel);rows=[]
        for i in range(320):
            packed=read_int(raw,0x4A8+i*2,2);item=packed&0x1FF;amount=(packed>>9)&0x7F
            rows.append({'id':i,'name':f'Slot {i+1} — {_global_inventory_name(kernel,item)}',
                         'description':'Initial item/equipment stock copied into a new save.',
                         'values':{'item':item,'amount':amount}})
        return rows
    if key in ('initialMateria','stolenMateria'):
        raw=_initial_section(kernel);start,count=(0x728,200) if key=='initialMateria' else (0xA48,48)
        rows=[]
        for i in range(count):
            at=start+i*4;index=raw[at];ap=int.from_bytes(raw[at+1:at+4],'little')
            rows.append({'id':i,'name':f'Slot {i+1} — {_materia_name(kernel,index)}',
                         'description':('Initial Materia stock copied into a new save.' if key=='initialMateria' else
                                        'Materia stored in Yuffie’s temporary stolen-Materia inventory for the Wutai sequence.'),
                         'values':{'materia':index,'ap':ap}})
        return rows

    raw=kernel.sections[spec['section']-1]
    rows=[]
    for i in range(spec['count']):
        at=spec['offset']+i*spec['stride'];bounds(raw,at,spec['size'])
        values=read_values(raw[at:at+spec['size']],spec['fields'])
        name=values.get('name',f"{spec['label']} {i}")
        if key=='growthCurves':name=f'{"Primary stat" if i<37 else "HP" if i<46 else "MP" if i<55 else "Experience"} curve {i}'
        if key=='growthBonuses':name=('Primary stat bonus','HP bonus percent','MP bonus percent')[i]
        rows.append({'id':i,'name':name,'description':'Kernel initialization/growth data; existing saves are not rewritten. Unknown bytes remain unchanged.', 'values':values})
    return rows


def _exact_values(row,keys,label):
    values=row.get('values') if isinstance(row,dict) else None
    if not isinstance(values,dict) or set(values)!=set(keys):
        raise ValueError(f'{label} has an invalid field set')
    if any(type(values[key]) is not int for key in keys):
        raise ValueError(f'{label} values must be integers')
    return values


def apply(kernel,key,rows):
    expected=records(kernel,key);validate_rows(rows,expected)
    spec=EXTRAS[key]
    if key=='characterAI':
        raw=bytearray(kernel.sections[2]);bounds(raw,0x61C,2048)
        raw[0x61C:0xE1C]=ai.Pool(raw[0x61C:0xE1C],12).apply({r['id']:r.get('values') for r in rows})
        kernel.sections[2]=raw;return
    if key=='magicOrder':
        raw=bytearray(_growth_section(kernel))
        for row in rows:
            values=_exact_values(row,('menuGroup','position'),'Magic-menu row')
            group,position=values['menuGroup'],values['position']
            if group not in (*range(8),0xFF) or not 0<=position<=31:
                raise ValueError('Magic-menu section must be 0–7 or 255 and position must be 0–31')
            raw[0xF5C+row['id']]=0xFF if group==0xFF else (group<<5)|position
        kernel.sections[2]=raw;return
    if key=='initialState':
        raw=bytearray(_initial_section(kernel));values=_exact_values(rows[0],('party1','party2','party3','gil'),'Starting setup')
        if any(not 0<=values[name]<=255 for name in ('party1','party2','party3')) or not 0<=values['gil']<=0xFFFFFFFF:
            raise ValueError('Starting party IDs or gil are outside their storage range')
        raw[0x4A4:0x4A7]=bytes(values[name] for name in ('party1','party2','party3'))
        raw[0xB28:0xB2C]=values['gil'].to_bytes(4,'little');kernel.sections[3]=raw;return
    if key=='initialInventory':
        raw=bytearray(_initial_section(kernel))
        for row in rows:
            values=_exact_values(row,('item','amount'),'Starting inventory row')
            if not 0<=values['item']<=0x1FF or not 0<=values['amount']<=0x7F:
                raise ValueError('Starting inventory item must be 0–511 and quantity 0–127')
            packed=values['item']|(values['amount']<<9);at=0x4A8+row['id']*2
            raw[at:at+2]=packed.to_bytes(2,'little')
        kernel.sections[3]=raw;return
    if key in ('initialMateria','stolenMateria'):
        raw=bytearray(_initial_section(kernel));start=0x728 if key=='initialMateria' else 0xA48
        for row in rows:
            values=_exact_values(row,('materia','ap'),'Starting Materia row')
            if not 0<=values['materia']<=0xFF or not 0<=values['ap']<=0xFFFFFF:
                raise ValueError('Materia ID or AP is outside its storage range')
            at=start+row['id']*4;raw[at]=values['materia'];raw[at+1:at+4]=values['ap'].to_bytes(3,'little')
        kernel.sections[3]=raw;return

    raw=bytearray(kernel.sections[spec['section']-1])
    for row in rows:
        at=spec['offset']+row['id']*spec['stride'];size=spec['size']
        raw[at:at+size]=write_values(raw[at:at+size],spec['fields'],row.get('values'))
    kernel.sections[spec['section']-1]=raw
