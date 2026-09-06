"""Independent, snapshot-checked FF7 scene, text and shop project datasets.

Binary layout references and limits are recorded in codex/ff7-data.md.
No game assets are bundled; unknown executable builds are never patched.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import struct
import tempfile
from threading import RLock
import zlib

from .battle import SceneArchive, SCENE_CATEGORIES, number, text, read_values, write_values, validate_rows
from .format_codec import bounds, digest, lzs_decode, lzs_encode, string_table, pack_strings, read_int

TEXT_SECTIONS = (
    'Command help', 'Magic help', 'Item help', 'Weapon help', 'Armor help',
    'Accessory help', 'Materia help', 'Key item help', 'Command names', 'Magic names',
    'Item names', 'Weapon names', 'Armor names', 'Accessory names', 'Materia names',
    'Key item names', 'Battle text', 'Summon attack names',
)


class KernelText:
    def __init__(self, data):
        raw = lzs_decode(data, limit=27648)
        self.original, self.sections, self.strings = data, [], []
        offset = 0
        for _ in TEXT_SECTIONS:
            size = read_int(raw, offset, 4); offset += 4
            bounds(raw, offset, size)
            section = raw[offset:offset + size]; offset += size
            self.sections.append(section)
            self.strings.append(string_table(section))
        if offset != len(raw):
            raise ValueError('kernel2.bin has unexpected trailing data')
        self.initial = deepcopy(self.strings)

    def records(self, category='texts'):
        return [{'id':section * 65536 + index, 'name':f'{label} {index}',
                 'description':'English kernel2 text. Backslash byte escapes preserve game control codes.',
                 'values':{'text':value}}
                for section, label in enumerate(TEXT_SECTIONS)
                for index, value in enumerate(self.strings[section])]

    def apply(self, category, rows):
        validate_rows(rows, self.records())
        replacement = deepcopy(self.strings)
        for row in rows:
            if not isinstance(row.get('values'), dict) or set(row['values']) != {'text'}:
                raise ValueError('Text record must contain exactly its text field')
            section, index = divmod(row['id'], 65536)
            value = row['values']['text']
            if type(value) is not str:
                raise ValueError('Text must be a string')
            replacement[section][index] = value
        self.strings = replacement

    def to_bytes(self):
        if self.strings == self.initial:
            return self.original
        output = bytearray()
        for i, strings in enumerate(self.strings):
            section = self.sections[i] if strings == self.initial[i] else pack_strings(strings)
            output.extend(struct.pack('<I', len(section))); output.extend(section)
        if len(output) > 27648:
            raise ValueError('kernel2.bin exceeds the 27648-byte game buffer; shorten the edited text')
        return lzs_encode(bytes(output))


# Source executable identity -> raw file offset adjustment. Verified against
# Scarlet 10a2283 ExeData.cs; launcher EXEs are deliberately absent.
EXE_PROFILES = {
    '1C9A6F4B6F554B1B4ECB38812F9396A026A677D6': 0x400,
    'AC306AE92615AF75FF36BBA6347C67CA1284151D': 0x200,
    'D270E690A0EA2C9D57AF506D102CF1A794E2ADCD': 0x200,
    '684A0E87840138B4E02FC8EDB9AE2E2591CE4982': 0x400,
    '141822081B3F24EA70BE35D59449E0CA098881E3': 0x400,
}
SHOP_FIELDS = [number('type', 'Shop type (0–8)', 0, maximum=8),
               number('dialogue', 'Dialogue set', 1), number('count', 'Inventory count', 2, maximum=10)]
for i in range(10):
    SHOP_FIELDS += [number(f'type{i}', 'Kind: 0 item/equipment, 1 materia', 4 + i * 8, 4,
                           group=f'Inventory slot {i + 1}'),
                    number(f'item{i}', 'Item ID', 8 + i * 8, 2, group=f'Inventory slot {i + 1}')]
PRICE_FIELDS = [number('price', 'Purchase price (gil)', 0, 4)]
PRICE_TABLES = [('Items', 0, 128), ('Weapons', 128, 128), ('Armor', 256, 32),
                ('Accessories', 288, 32), ('Materia', 384, 96)]


class ShopExecutable:
    def __init__(self, data, source):
        identity = hashlib.sha1(source).hexdigest().upper()
        if identity not in EXE_PROFILES:
            raise ValueError(f'Unsupported English executable SHA-1 {identity}. Shop editing requires a known build; no offsets are guessed.')
        self.shift = EXE_PROFILES[identity]
        if source[:2] != b'MZ' or source[self.shift:self.shift + 4] != b'\x55\x8b\xec\xc7':
            raise ValueError('Executable identity/header mismatch')
        if len(data) != len(source):
            raise ValueError('Project executable length differs from the supported source')
        bounds(data, 0x523A58 + self.shift, 96 * 4)
        self.original, self.data = bytes(data), bytearray(data)
        # Only our documented data ranges may differ from the supported source.
        # This prevents a foreign executable project from inheriting its profile.
        start = 0x521A18 + self.shift
        end = 0x523A58 + self.shift + 96 * 4
        if data[:start] != source[:start] or data[end:] != source[end:]:
            raise ValueError('Project executable contains changes outside supported shop/price data')
        for row in self.records('shops'):
            if row['values']['count'] > 10 or row['values']['type'] > 8:
                raise ValueError('Executable contains an invalid shop table')

    def _offset(self, category, index):
        return (0x521A18 + index * 84 if category == 'shops' else 0x523458 + index * 4) + self.shift

    def records(self, category):
        if category == 'shops':
            return [{'id':i, 'name':f'Shop {i}', 'description':'Ten inventory slots; only Inventory count slots are active. Field shop-opening scripts are unchanged.',
                     'values':read_values(self.data[self._offset(category,i):self._offset(category,i) + 84], SHOP_FIELDS)} for i in range(80)]
        return [{'id':start + i, 'name':f'{label} {i}', 'description':'Global purchase price; this is not a per-shop markup.',
                 'values':{'price':read_int(self.data, self._offset(category, start + i), 4)}}
                for label,start,count in PRICE_TABLES for i in range(count)]

    def apply(self, category, rows):
        validate_rows(rows, self.records(category))
        replacement = bytearray(self.data)
        fields, size = (SHOP_FIELDS, 84) if category == 'shops' else (PRICE_FIELDS, 4)
        for row in rows:
            offset = self._offset(category, row['id'])
            chunk = write_values(self.data[offset:offset + size], fields, row.get('values'))
            if category == 'shops':
                for i in range(chunk[2]):
                    kind, item = read_int(chunk, 4 + i * 8, 4), read_int(chunk, 8 + i * 8)
                    if kind not in (0,1) or item >= (96 if kind == 1 else 320):
                        raise ValueError(f'Shop {row["id"]} slot {i + 1} has an invalid item/materia reference')
            replacement[offset:offset + size] = chunk
        self.data = replacement

    def to_bytes(self):
        return bytes(self.data)


FAMILIES = {
    'scene': {'categories':SCENE_CATEGORIES, 'source':'scene.bin',
              'note':'Enemies, attacks and four formations per scene. AI and field/world encounter placement are preserved. Original block membership is retained; an overflowing edit is refused.'},
    'text': {'categories':{'texts':{'label':'Text', 'fields':[text('text','Text',size=65535)]}}, 'source':'kernel2.bin',
             'note':'All 18 English kernel2 text sections, with preserved game-byte escapes and a bounded game buffer. KERNEL.BIN embedded text is not rewritten.'},
    'shop': {'categories':{'shops':{'label':'Shops','fields':SHOP_FIELDS}, 'prices':{'label':'Prices','fields':PRICE_FIELDS}},
             'source':'Supported English game executable',
             'note':'80 shop inventories and global item/equipment/materia prices in a supported executable. Saves write a project copy, never the installed executable. Shop-opening scripts are unchanged.'},
}
ERRORS = (OSError, ValueError, EOFError, struct.error, zlib.error)
LOCK = RLock()


def _case_path(root, relative):
    path = Path(root)
    for part in Path(relative).parts:
        if not path.is_dir():
            return None
        matches = [p for p in path.iterdir() if p.name.casefold() == part.casefold()]
        if len(matches) > 1:
            raise ValueError(f'Ambiguous case-insensitive FF7 source: {relative}')
        if not matches:
            return None
        path = matches[0]
    return path if path.is_file() else None


def resolve_source(game_root, family):
    if family == 'scene':
        candidates = [f'{prefix}data/{lang}battle/scene.bin' for prefix in ('', 'ff7/workingdir/') for lang in ('','lang-en/')]
    elif family == 'text':
        candidates = [f'{prefix}data/lang-en/kernel/kernel2.bin' for prefix in ('', 'ff7/workingdir/')]
    else:
        candidates = ['ff7/resources/ff7_1.02/ff7_en', 'ff7_en.exe', 'ff7.exe']
    found = {p for name in candidates if (p := _case_path(game_root, name)) is not None}
    if len(found) != 1:
        raise ValueError(f'{FAMILIES[family]["source"]}: expected one source, found {len(found)}. Checked: ' + ', '.join(candidates))
    source = found.pop()
    if not source.resolve().is_relative_to(Path(game_root).resolve()):
        raise ValueError('Source resolves outside the selected game directory')
    return source, source.relative_to(game_root)


def model(family, data, source):
    return ShopExecutable(data, source) if family == 'shop' else (SceneArchive(data) if family == 'scene' else KernelText(data))


def _target(game_root, project_root, source, relative):
    root, game = Path(project_root).resolve(), Path(game_root).resolve()
    if root == game or root.is_relative_to(game):
        raise ValueError('The FF7 mod project must be outside the installed game directory')
    target = Path(project_root) / relative
    if not target.resolve().is_relative_to(root) or target.is_symlink():
        raise ValueError('Project output escapes the project directory')
    if target.exists() and target.samefile(source):
        raise ValueError('Project output aliases the installed source')
    return target


def load_extended(game_root, project_root):
    result = {'categories':[], 'records':{}, 'vanilla':{}, 'errors':{}, 'families':{}}
    for family, info in FAMILIES.items():
        result['categories'] += [dict(value, id=key, family=family) for key,value in info['categories'].items()]
        report = {'categories':list(info['categories']), 'note':info['note'], 'sourceRelativePath':None}
        result['families'][family] = report
        try:
            source, relative = resolve_source(game_root, family)
            report.update(sourceRelativePath=relative.as_posix())
            target = _target(game_root, project_root, source, relative)
            original = source.read_bytes()
            active = target.read_bytes() if target.exists() else original
            vanilla, current = model(family, original, original), model(family, active, original)
            report.update(sourceSha256=digest(original), activeSha256=digest(active), usingProject=target.exists(), projectPath=str(target))
            pending = {}
            for key in info['categories']:
                rows, baseline = current.records(key), vanilla.records(key)
                if [r['id'] for r in rows] != [r['id'] for r in baseline]:
                    raise ValueError('Project record identities differ from the installed source')
                pending[key] = (rows, baseline)
            for key,(rows,baseline) in pending.items():
                result['records'][key], result['vanilla'][key] = rows, baseline
        except ERRORS as error:
            report['error'] = str(error)
            result['errors'].update({key:str(error) for key in info['categories']})
    return result


def save_extended(game_root, project_root, payload):
    with LOCK:
        if not isinstance(payload, dict) or payload.get('family') not in FAMILIES:
            raise ValueError('Save must select a supported FF7 source family')
        family = payload['family']
        records = payload.get('records')
        if not isinstance(records, dict) or set(records) != set(FAMILIES[family]['categories']):
            raise ValueError('Save must contain exactly the selected family datasets')
        source, relative = resolve_source(game_root, family)
        target = _target(game_root, project_root, source, relative)
        original = source.read_bytes(); existed = target.exists()
        active = target.read_bytes() if existed else original
        expected = {'sourceSha256':digest(original), 'activeSha256':digest(active), 'usingProject':existed}
        if any(key not in payload or type(payload[key]) is not type(value) or payload[key] != value for key,value in expected.items()):
            raise ValueError('FF7 data changed outside this editor. Reload before saving.')
        current = model(family, active, original)
        for key,rows in records.items():
            current.apply(key, rows)
        output = current.to_bytes()
        verified = model(family, output, original)
        for key,rows in records.items():
            if {r['id']:r['values'] for r in verified.records(key)} != {r['id']:r['values'] for r in rows}:
                raise ValueError(f'{key} failed binary round-trip verification')
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name+'.', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(output); stream.flush(); os.fsync(stream.fileno())
            if temporary.read_bytes() != output:
                raise ValueError('Temporary FF7 file failed readback')
            _target(game_root, project_root, source, relative)
            if source.read_bytes() != original or target.exists() != existed or (existed and target.read_bytes() != active):
                raise ValueError('FF7 data changed while saving. Reload before saving.')
            backup = None
            if existed:
                # An exclusive new backup cannot follow/overwrite another file's symlink.
                with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name+'.lexeditor-', suffix='.bak', delete=False) as stream:
                    backup = stream.name
                    stream.write(active); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, target)
            return {'saved':True, 'path':str(target), 'sha256':digest(output), 'bytes':len(output), 'backup':backup,
                    'sourceSha256':digest(original), 'activeSha256':digest(output), 'usingProject':True}
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
