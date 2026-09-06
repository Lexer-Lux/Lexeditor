"""Character names, 64 growth curves, growth bonuses and character AI.

Offsets: Shojy/Elena d85e026 CharacterData.cs, BattleAndGrowthData.cs,
StatCurve.cs. AI pool has twelve owner slots and ends before the RNG table.
"""
from __future__ import annotations
from . import ai
from .battle import number,text,read_values,write_values,validate_rows
from .format_codec import bounds

BRACKETS=('2–11','12–21','22–31','32–41','42–51','52–61','62–81','82–99')
CURVE_FIELDS=[f for i,bracket in enumerate(BRACKETS) for f in (
    number(f'gradient{i}','Gradient',i*2,group='Levels '+bracket),
    number(f'base{i}','Base (ignored for experience)',i*2+1,signed=True,group='Levels '+bracket))]
BONUS_FIELDS=[number(f'bonus{i}',f'Difference bracket {i}',i) for i in range(12)]
NAME_FIELDS=[text('name','Initial name',0,12)]
EXTRAS={
    'characterNames':{'label':'Initial names','fields':NAME_FIELDS,'section':4,'offset':0x10,'stride':132,'count':9,'size':12},
    'growthCurves':{'label':'Growth curves','fields':CURVE_FIELDS,'section':3,'offset':0x21C,'stride':16,'count':64,'size':16},
    'growthBonuses':{'label':'Growth bonuses','fields':BONUS_FIELDS,'section':3,'offset':0x1F8,'stride':12,'count':3,'size':12},
    'characterAI':{'label':'Character AI','fields':ai.metadata(),'section':3},
}


def records(kernel,key):
    spec=EXTRAS[key];raw=kernel.sections[spec['section']-1]
    if key=='characterAI':
        bounds(raw,0x61C,2048)
        return ai.Pool(raw[0x61C:0xE1C],12).records('Character AI owner')
    rows=[]
    for i in range(spec['count']):
        at=spec['offset']+i*spec['stride'];bounds(raw,at,spec['size'])
        values=read_values(raw[at:at+spec['size']],spec['fields'])
        name=values.get('name',f"{spec['label']} {i}")
        if key=='growthCurves':name=f'{"Primary stat" if i<37 else "HP" if i<46 else "MP" if i<55 else "Experience"} curve {i}'
        if key=='growthBonuses':name=('Primary stat bonus','HP bonus percent','MP bonus percent')[i]
        rows.append({'id':i,'name':name,'description':'Kernel initialization/growth data; existing saves are not rewritten. Unknown bytes remain unchanged.', 'values':values})
    return rows


def apply(kernel,key,rows):
    validate_rows(rows,records(kernel,key))
    spec=EXTRAS[key];raw=bytearray(kernel.sections[spec['section']-1])
    if key=='characterAI':
        raw[0x61C:0xE1C]=ai.Pool(raw[0x61C:0xE1C],12).apply({r['id']:r.get('values') for r in rows})
    else:
        for row in rows:
            at=spec['offset']+row['id']*spec['stride'];size=spec['size']
            raw[at:at+size]=write_values(raw[at:at+size],spec['fields'],row.get('values'))
    kernel.sections[spec['section']-1]=raw
