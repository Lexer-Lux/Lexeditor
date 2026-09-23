"""Edit proven loot context and item sound mappings without rewriting other XML."""
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

ROOT_TAG='CLootSoundsMapCollection'


def read(text):
    root=ET.fromstring(text)
    if root.tag!=ROOT_TAG: raise ValueError('Not a loot sound map')
    rows=[]
    for index, sound_map in enumerate(root.findall('./SoundMaps/Item')):
        for section in ('SoundSets','Sounds'):
            for position,item in enumerate(sound_map.findall(section+'/Item')):
                key=item.get('key',''); value=(item.text or '').strip()
                if not key: raise ValueError('Missing sound-map key')
                rows.append({'id':f'{index}:{section}:{position}:{key}','map':index,'section':section,'key':key,'value':value})
    return {'available':True,'rows':rows,
            'categories':sorted({r['value'] for r in rows if r['section']=='Sounds'}),
            'soundSets':sorted({r['value'] for r in rows if r['section']=='SoundSets'})}


def apply(text, edits):
    model=read(text);rows={row['id']:row for row in model['rows']}; changes={}
    for edit in edits:
        row=rows.get(edit.get('id'))
        if row is None: raise ValueError('Unknown pickup sound mapping')
        value=edit.get('value')
        choices=model['categories'] if row['section']=='Sounds' else model['soundSets']
        if value not in choices: raise ValueError('Choose an existing sound event or soundset; new audio must be registered first')
        if row['id'] in changes: raise ValueError('Duplicate sound mapping edit')
        changes[row['id']]=value
    # Address sections in source order, retaining declarations, comments and spacing.
    map_index=-1
    def patch_map(match):
        nonlocal map_index
        map_index+=1; body=match.group(0)
        for section in ('SoundSets','Sounds'):
            def patch_section(section_match):
                segment=section_match.group(0)
                position=-1
                def patch_item(item_match):
                    nonlocal position
                    position+=1
                    identity=f'{map_index}:{section}:{position}:{item_match[2]}'
                    if identity not in changes or changes[identity] == rows[identity]['value']:
                        return item_match.group(0)
                    return item_match[1]+escape(changes[identity])+item_match[4]
                segment=re.sub(r'(<Item\s+key=["\']([^"\']+)["\']\s*>)([^<]*)(</Item>)',patch_item,segment)
                return segment
            body=re.sub(r'<'+section+r'>.*?</'+section+r'>',patch_section,body,flags=re.S)
        return body
    output=re.sub(r'<Item>\s*<SoundSets>.*?</Sounds>\s*</Item>',patch_map,text,flags=re.S)
    result=read(output)
    for row in result['rows']:
        if row['id'] in changes and row['value']!=changes[row['id']]: raise ValueError('Sound mapping was not changed')
    return output,sum(rows[key]['value']!=value for key,value in changes.items())
