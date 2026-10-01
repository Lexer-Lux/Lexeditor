"""Fixed-size DS1 item edits. Preserve all archive bytes outside edited cells.

BND3/DCX facts: Apache-2.0 SoulsTemplates (see credits.md). PARAM cell codecs
are reused from Lexeditor's DS3 integration; no SoulsFormats code is used.
"""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET
import zlib

from plugins.ds3.formats import DS3FormatError, FieldSpec, ParamView, read_field, write_field

FormatError = DS3FormatError
METADATA = Path(__file__).with_name('metadata')
TABLES = {'EquipParamGoods': (92, 1), 'EquipParamWeapon': (272, 1),
          'EquipParamProtector': (232, 2), 'EquipParamAccessory': (64, 1), 'Magic': (48, 2)}
SIZES = {'u8': 1, 's8': 1, 'dummy8': 1, 'u16': 2, 's16': 2,
         'u32': 4, 's32': 4, 'b32': 4, 'f32': 4, 'angle32': 4, 'f64': 8}
MAX_ARCHIVE = 64 * 1024 * 1024
SUBTABS = (
    ('consumables', 'Consumables', 'EquipParamGoods'),
    ('upgrades', 'Upgrade Items', 'EquipParamGoods'),
    ('keys', 'Key Items', 'EquipParamGoods'), ('spells', 'Spells', 'Magic'),
    ('weapons', 'Weapons', 'EquipParamWeapon'), ('ammo', 'Ammo', 'EquipParamWeapon'),
    ('armor', 'Armor', 'EquipParamProtector'), ('rings', 'Rings', 'EquipParamAccessory'),
)


def inflate(source):
    if len(source) < 76 or source[:4] != b'DCX\0' or source[40:44] != b'DFLT':
        raise FormatError('Expected a DS1 DFLT-compressed parameter archive')
    if (source[4:24] != bytes.fromhex('000100000000001800000024000000240000002c')
            or source[24:28] != b'DCS\0' or source[36:40] != b'DCP\0'
            or source[68:76] != b'DCA\0\0\0\0\x08'):
        raise FormatError('Unsupported DS1 DCX header')
    length, compressed = struct.unpack_from('>II', source, 28)
    if not 32 <= length <= MAX_ARCHIVE or compressed != len(source) - 76:
        raise FormatError('Invalid DCX lengths')
    decoder = zlib.decompressobj()
    try:
        plain = decoder.decompress(source[76:], length + 1)
    except zlib.error as error:
        raise FormatError('Invalid compressed archive') from error
    if len(plain) != length or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise FormatError('Compressed archive length mismatch')
    return plain


@dataclass(frozen=True)
class Member:
    name: str
    offset: int
    size: int


def members(plain):
    # This adapter handles the measured PC Remastered uncompressed-member shape.
    if len(plain) < 32 or plain[:4] != b'BND3' or plain[12:16] != b'\x74\0\0\0':
        raise FormatError('Unsupported BND3 format; expected PC Remastered parameters')
    count, names_end = struct.unpack_from('<II', plain, 16)
    directory_end = 32 + count * 24
    if not 1 <= count <= 4096 or not directory_end <= names_end <= len(plain):
        raise FormatError('Invalid BND3 directory')
    result = {}
    spans = []
    for index in range(count):
        flags, size, offset, _id, name_offset, unpacked = struct.unpack_from('<6I', plain, 32 + index * 24)
        if flags != 0x40 or size != unpacked or not names_end <= offset <= len(plain) - size:
            raise FormatError('Compressed, overlapping or invalid BND3 member')
        if not directory_end <= name_offset < names_end:
            raise FormatError('BND3 name is outside its directory')
        end = plain.find(b'\0', name_offset, names_end)
        if end < 0:
            raise FormatError('Unterminated BND3 name')
        name = plain[name_offset:end].decode('shift_jis').replace('\\', '/').rsplit('/', 1)[-1]
        if name in result:
            raise FormatError('Duplicate BND3 member name')
        result[name] = Member(name, offset, size)
        spans.append((offset, offset + size))
    spans.sort()
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise FormatError('Overlapping BND3 payloads')
    return result


def _enum(name):
    path = METADATA / 'enums' / (name + '.json')
    if not path.is_file(): return {}
    raw = json.loads(path.read_text('utf-8-sig'))
    return {str(row['Key']): next((n['Text'] for n in row.get('Names', []) if n['Language'] == 'English'), str(row['Key']))
            for row in raw['Options']}


@lru_cache(maxsize=5)
def schema(table):
    if table not in TABLES:
        raise FormatError('Unsupported item table')
    root = ET.parse(METADATA / 'defs' / (table + '.xml')).getroot()
    param_type = root.findtext('ParamType')
    meta = ET.parse(METADATA / 'meta' / (table + '.xml')).getroot().find('Field')
    metadata = {node.tag: node.attrib for node in meta}
    annotations = json.loads((METADATA / 'annotations' / (param_type + '.json')).read_text('utf-8'))
    annotations = {field['Field']: field for field in annotations['Fields']}
    rows = json.loads((METADATA / 'row_names' / (table + '.json')).read_text('utf-8'))
    names = {int(row['ID']): row['Entries'][0] for row in rows['Entries'] if row['Entries']}
    fields = []
    offset = 0
    bit_width = bit_used = bit_start = 0
    for node in root.findall('Fields/Field'):
        match = re.fullmatch(r'(\w+)\s+([^\s=\[:]+)(?:\[(\d+)\])?(?::(\d+))?(?:\s*=.*)?', node.attrib['Def'])
        if not match or match[1] not in SIZES:
            raise FormatError('Unsupported item field declaration')
        dtype, key = match[1], match[2]
        count, bits = int(match[3] or 1), int(match[4]) if match[4] else None
        size = SIZES[dtype]
        if bits is None:
            bit_width = bit_used = 0
            field_offset = offset
            offset += size * count
        else:
            if count != 1 or not 1 <= bits <= size * 8:
                raise FormatError('Invalid item bitfield')
            if bit_width != size * 8 or bit_used + bits > bit_width:
                bit_width, bit_used, bit_start = size * 8, 0, offset
                offset += size
            field_offset = bit_start
        attrs, annotation = metadata.get(key, {}), annotations.get(key, {})
        label = annotation.get('Name') or key
        enum_name = attrs.get('Enum') or node.findtext('Enum')
        if 'IsBool' in attrs or enum_name == 'EQUIP_BOOL': enum_name = None
        choices = _enum(enum_name) if enum_name else {}
        padding = dtype == 'dummy8' or 'Padding' in attrs or key.lower().startswith('pad')
        protected = padding or count != 1 or 'Obsolete' in attrs or not annotation or (enum_name and not choices) or bool(re.search(r'unknown|unused|dummy|reserved|^unk', label, re.I))
        field = FieldSpec(key, dtype, field_offset, count, bit_used if bits else None, bits,
                          label, annotation.get('Description', ''), 'Properties',
                          'IsBool' in attrs or bits == 1, enum_name, attrs.get('Refs'), padding)
        low, high = field.minimum, field.maximum
        if low is None:
            low, high = (-3.4028234663852886e38, 3.4028234663852886e38) if dtype != 'f64' else (-1.7976931348623157e308, 1.7976931348623157e308)
        # Honor PARAMDEF ranges while preserving pre-existing exceptional values.
        for tag, is_min in (('Minimum', True), ('Maximum', False)):
            text = node.findtext(tag)
            if text is not None:
                value = float(text)
                if math.isfinite(value):
                    if is_min: low = max(low, value)
                    else: high = min(high, value)
        if low > high:
            protected = True
        fields.append({'spec': field, 'min': low, 'max': high, 'enum': choices, 'editable': not protected})
        if bits: bit_used += bits
    if offset != TABLES[table][0]:
        raise FormatError(f'{table} definition size {offset} does not match the audited row size')
    return {'type': param_type, 'size': offset, 'fields': fields, 'names': names}


class ItemDocument:
    def __init__(self, source):
        self.original = source
        self.original_plain = inflate(source)
        self.plain = bytearray(self.original_plain)
        self.members = members(self.plain)
        self.params = {}
        self.schemas = {table: schema(table) for table in TABLES}
        self.dirty = set()
        for table, (row_size, version) in TABLES.items():
            member = self.members.get(table + '.param')
            if member is None:
                raise FormatError(f'Missing item table {table}')
            payload = self.plain[member.offset:member.offset + member.size]
            if len(payload) < 48 or payload[44:48] != b'\0\x02\0\0':
                raise FormatError(f'Unsupported {table} PARAM header')
            param = ParamView(payload)
            if param.big_endian or param.param_type != self.schemas[table]['type'] or param.header_version != version:
                raise FormatError(f'Unsupported {table} layout/version')
            if not param.rows or len({r.row_id for r in param.rows}) != len(param.rows):
                raise FormatError(f'Empty or duplicate {table} row IDs')
            directory_end = (64 if param.format2d & 4 or param.format2d & 3 == 3 else 48) + len(param.rows) * (24 if param.long_offsets else 12)
            if not directory_end <= param.strings_offset <= member.size:
                raise FormatError(f'Invalid {table} strings boundary')
            offsets = sorted(row.data_offset for row in param.rows)
            if any(b - a != row_size for a, b in zip(offsets, offsets[1:])) or offsets[0] < directory_end or offsets[-1] + row_size > param.strings_offset:
                raise FormatError(f'{table} row boundaries do not match metadata')
            self.params[table] = param

    @property
    def dirty_count(self):
        return len(self.dirty)

    def _row(self, table, row_id):
        if table not in TABLES or type(row_id) is not int:
            raise FormatError('Invalid item identity')
        row = self.params[table].row(row_id)
        start = self.members[table + '.param'].offset + row.data_offset
        return row, start, bytes(self.plain[start:start + TABLES[table][0]])

    def value(self, table, row_id, key):
        field = next(f['spec'] for f in self.schemas[table]['fields'] if f['spec'].key == key)
        return read_field(self._row(table, row_id)[2], field, '<')

    def list_rows(self, tab):
        match = next((entry for entry in SUBTABS if entry[0] == tab), None)
        if match is None: raise FormatError('Unknown Items subtab')
        table = match[2]
        result = []
        for row in self.params[table].rows:
            if table == 'EquipParamGoods':
                category = self.value(table, row.row_id, 'goodsType')
                if tab != ('keys' if category == 1 else 'upgrades' if category == 2 else 'consumables'):
                    continue
                # Spell records are edited through Magic, not duplicate inventory goods.
                if category in (5, 6, 7): continue
            if table == 'EquipParamWeapon':
                ammo = self.value(table, row.row_id, 'weaponCategory') in (13, 14)
                if (tab == 'ammo') != ammo: continue
            result.append({'id': row.row_id, 'name': self.schemas[table]['names'].get(row.row_id) or row.name or f'Item {row.row_id}', 'table': table})
        if tab == 'spells':
            table = 'EquipParamGoods'
            for row in self.params[table].rows:
                if self.value(table, row.row_id, 'goodsType') in (5, 6, 7):
                    result.append({'id': row.row_id, 'name': 'Spell item: ' + (self.schemas[table]['names'].get(row.row_id) or row.name or str(row.row_id)), 'table': table})
        return result

    def read_row(self, table, row_id):
        row, _, data = self._row(table, row_id)
        fields = []
        for item in self.schemas[table]['fields']:
            field = item['spec']
            if field.padding or field.array_length != 1: continue
            value = read_field(data, field, '<')
            finite = not isinstance(value, float) or math.isfinite(value)
            fields.append({'key': field.key, 'label': field.label, 'description': field.description,
                           'dtype': field.dtype, 'value': value if finite else str(value),
                           'type': 'bool' if field.is_bool else 'enum' if item['enum'] else 'number',
                           'minimum': item['min'], 'maximum': item['max'], 'enum': item['enum'],
                           'editable': item['editable'] and finite})
        return {'id': row_id, 'table': table, 'name': self.schemas[table]['names'].get(row_id) or row.name or f'Item {row_id}', 'fields': fields}

    def edit(self, table, row_id, key, value):
        row, start, data = self._row(table, row_id)
        item = next((f for f in self.schemas[table]['fields'] if f['spec'].key == key), None)
        if item is None or not item['editable']:
            raise FormatError('This field is protected')
        field = item['spec']
        if type(value) not in (int, float, bool) or not math.isfinite(value):
            raise FormatError('Enter a finite number')
        if field.dtype not in ('f32', 'f64', 'angle32') and int(value) != value:
            raise FormatError('Enter a whole number')
        if field.is_bool and value not in (0, 1): raise FormatError('Expected a checkbox value')
        if not item['min'] <= value <= item['max']:
            raise FormatError(f"{field.label} must be between {item['min']} and {item['max']}")
        if item['enum'] and str(int(value)) not in item['enum']:
            raise FormatError('Choose a listed value')
        replacement = write_field(data, field, value, '<')
        self.plain[start:start + len(data)] = replacement
        original = self.original_plain[start:start + len(data)]
        dirty_key = (table, row_id, key)
        if read_field(replacement, field, '<') == read_field(original, field, '<'):
            self.dirty.discard(dirty_key)
        else:
            self.dirty.add(dirty_key)
        return self.read_row(table, row_id)

    def export(self):
        if self.plain == self.original_plain: return self.original
        compressed = zlib.compress(bytes(self.plain), 9)
        header = bytearray(self.original[:76])
        struct.pack_into('>II', header, 28, len(self.plain), len(compressed))
        return bytes(header) + compressed
