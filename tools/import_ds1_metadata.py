"""Refresh the small, pinned Smithbox DS1 editor metadata subset (MIT)."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'plugins/ds1/metadata'
REVISION = '057b417887cc7d0ddc8001602be3f5339f42c74f'
BASE = 'Smithbox.Release/Output/Assets/PARAM/DS1R/'
TABLES = {'EquipParamGoods': 'EquipParamGoods', 'EquipParamWeapon': 'EquipParamWeapon',
          'EquipParamProtector': 'EquipParamProtector', 'EquipParamAccessory': 'EquipParamAccessory',
          'Magic': 'MagicParam', 'NpcParam': 'NpcParam'}


def fetch(path):
    with urlopen('https://raw.githubusercontent.com/vawser/Smithbox/' + REVISION + '/' + quote(path), timeout=30) as reply:
        return reply.read()


def main():
    with urlopen('https://api.github.com/repos/vawser/Smithbox/git/trees/' + REVISION + '?recursive=1', timeout=30) as reply:
        tree = json.load(reply)
    assert not tree.get('truncated'), 'Incomplete upstream tree'
    paths = {entry['path'] for entry in tree['tree']}
    provenance = {}

    def save(source, target):
        data = fetch(source)
        text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        if target.endswith('.xml'):
            text = re.sub(r'encoding="utf-16"', 'encoding="utf-8"', text)
        destination = ROOT / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding='utf-8', newline='\n')
        provenance[target] = {'path': source, 'sha256': hashlib.sha256(data).hexdigest()}
        return text

    tasks = []
    for table, definition in TABLES.items():
        text = save(BASE + 'Defs/' + definition + '.xml', 'defs/' + table + '.xml')
        param_type = ET.fromstring(text).findtext('ParamType')
        for upstream, local, name, extension in (
            ('Param Meta', 'meta', table, '.xml'),
            ('Param Annotations/English', 'annotations', param_type, '.json'),
            ('Param Row Names', 'row_names', table, '.json'),
        ):
            candidates = [p for p in paths if p.startswith(BASE + upstream + '/') and p.endswith('/' + name + extension)]
            if not candidates and name == table:
                candidates = [p for p in paths if p.startswith(BASE + upstream + '/') and p.endswith('/' + definition + extension)]
            if len(candidates) > 1:
                candidates = [p for p in candidates if '/English/' in p]
            assert len(candidates) == 1, (table, upstream, candidates)
            tasks.append((candidates[0], local + '/' + name + extension))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda task: save(*task), tasks))
    enums = set()
    for path in (ROOT / 'defs').glob('*.xml'):
        meta = {node.tag: node.attrib for node in ET.parse(ROOT / 'meta' / path.name).getroot().find('Field')}
        for node in ET.parse(path).iter('Field'):
            key = re.split(r'[\[:\s=]', node.attrib['Def'].split()[1])[0]
            attrs = meta.get(key, {})
            name = attrs.get('Enum') or node.findtext('Enum')
            if name and 'IsBool' not in attrs and name != 'EQUIP_BOOL':
                enums.add(name)
    missing_enums = []
    for name in sorted(enums):
        source = BASE + 'Param Enums/' + name + '.json'
        if source not in paths:
            missing_enums.append(name)
            continue
        save(source, 'enums/' + name + '.json')
    (ROOT / 'SOURCE.json').write_text(json.dumps({
        'source': 'https://github.com/vawser/Smithbox', 'revision': REVISION, 'license': 'MIT',
        'scope': 'DS1 item and enemy parameter metadata only; no GPL dependencies or executable code.',
        'unavailableEnums': missing_enums,
        'transformations': ['UTF-8 BOM removed; XML declarations normalized to UTF-8.'],
        'files': dict(sorted(provenance.items())),
    }, indent=2) + '\n', encoding='utf-8')
    print(f'Imported {len(provenance)} pinned metadata files ({sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file())} bytes).')


if __name__ == '__main__':
    main()
