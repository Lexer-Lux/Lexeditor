"""Build offline credits from reviewed attributions and unchanged original notices."""
from __future__ import annotations
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    path=(ROOT/relative).resolve()
    if ROOT not in path.parents or not path.is_file():
        raise ValueError(f'Invalid credit notice: {relative}')
    return path.read_text('utf-8-sig')

def generate() -> dict:
    spec=json.loads(read('ui/credits-sources.json'))
    result={'schema':1,'shared':copy.deepcopy(spec['shared']),'plugins':{}}
    for key,recipe in spec['plugins'].items():
        if 'sameAs' in recipe:
            section=copy.deepcopy(result['plugins'][recipe['sameAs']])
        elif 'source' in recipe:
            section=json.loads(read(recipe['source']))
            for notice in section.get('licenses',[]):
                notice['sourcePath']=recipe['licenseRoot']+'/'+notice.pop('url').lstrip('/')
        else:section=copy.deepcopy(recipe)
        result['plugins'][key]=section
    for section in [result['shared'],*result['plugins'].values()]:
        for notice in section.get('licenses',[]):notice['text']=read(notice['sourcePath'])
    return result

if __name__=='__main__':
    (ROOT/'ui/credits.json').write_text(json.dumps(generate(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
