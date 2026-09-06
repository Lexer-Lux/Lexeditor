"""Build offline credits from reviewed attributions and unchanged original notices."""
from __future__ import annotations
import argparse
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

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check generated credits without writing files.')
    args = parser.parse_args(argv)
    expected = json.dumps(generate(), ensure_ascii=False, indent=2) + '\n'
    destination = ROOT / 'ui/credits.json'
    if args.check:
        if not destination.is_file() or destination.read_text('utf-8') != expected:
            parser.exit(1, 'Offline credits are stale. Run python tools/generate_credits.py.\n')
        return 0
    destination.write_text(expected, encoding='utf-8')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
