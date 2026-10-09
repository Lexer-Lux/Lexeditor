"""Fixed-size DS1 item/resistance/attack/effect edits; preserve other bytes.

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
from .monsters import RESISTANCES, classified_monster
from .attacks import ATTACK_FIELDS, AttackReferences
from .effects import TABLE as EFFECT_TABLE, SUBTABS as EFFECT_SUBTABS, GROUPS as EFFECT_GROUPS, PROTECTED as EFFECT_PROTECTED, presentation, EffectReferences, reference_keys

FormatError = DS3FormatError
METADATA = Path(__file__).with_name('metadata')
TABLES = {'EquipParamGoods': (92, 1), 'EquipParamWeapon': (272, 1),
          'EquipParamProtector': (232, 2), 'EquipParamAccessory': (64, 1), 'Magic': (48, 2),
          'NpcParam': (336, 3), 'AtkParam_Npc': (128, 1),
          'BehaviorParam': (32, 2), 'Bullet': (160, 2), 'SpEffectParam': (368, 2)}
OPTIONAL_TABLES = frozenset({'SpEffectParam'})
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
ENEMY_SUBTABS = (('monsters', 'Monsters', 'NpcParam'),)

# Armor defense, said the way the game uses it (0x2DC350): physical, magic,
# fire and lightning are unsigned whole numbers the game reads as 0 or more;
# slash, strike and thrust scale physical defense by (100 + value) / 100.
ARMOR_FIELDS = {}
for key, kind in [('defensePhysics', 'Physical'), ('defenseMagic', 'Magic'),
                  ('defenseFire', 'Fire'), ('defenseThunder', 'Lightning')]:
    ARMOR_FIELDS[key] = (f'{kind} defense', 'Defense',
        f'Flat {kind.lower()} defense this piece adds. The game stores and reads it as a whole number '
        'of 0 or more, so it cannot be negative. For negative protection, give the piece negative '
        'absorption (Armor Rework) or an effect that raises damage taken.')
for key, kind in [('defenseSlash', 'Slash'), ('defenseBlow', 'Strike'), ('defenseThrust', 'Thrust')]:
    ARMOR_FIELDS[key] = (f'{kind} vs physical (%)', 'Defense',
        f'Changes this piece\'s physical defense against {kind.lower()} attacks by this percentage: '
        '-100 makes it 0, 50 makes it one and a half times. It is not a defense value of its own.')

# Armor Rework gives every armor piece its own absorption effect in slot 3,
# one per upgrade level: effect ID = 30,000,000 + armor ID + level.
ABSORPTION_BASE = 30_000_000
# Enemies too: 40,000,000 + enemy ID, in one of the enemy's spEffectID slots.
ENEMY_ABSORPTION_BASE = 40_000_000
ABSORPTION_CUTS = (('neutralDamageCutRate', 'Physical'), ('slashDamageCutRate', 'Slash'),
                   ('blowDamageCutRate', 'Strike'), ('thrustDamageCutRate', 'Thrust'),
                   ('magicDamageCutRate', 'Magic'), ('fireDamageCutRate', 'Fire'),
                   ('thunderDamageCutRate', 'Lightning'))
MAX_UPGRADE_LEVEL = 15
ATTACK_SUBTABS = (('attacks', 'Attacks', 'AtkParam_Npc'),)


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


def deflate(original, plain):
    """Compress plain bytes into a DCX shaped like the original one."""
    inflate(original)
    compressed = zlib.compress(bytes(plain), 9)
    header = bytearray(original[:76])
    struct.pack_into('>II', header, 28, len(plain), len(compressed))
    return bytes(header) + compressed


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


@lru_cache(maxsize=None)
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
        description, group = annotation.get('Description', ''), 'Properties'
        if table == 'NpcParam' and key in RESISTANCES:
            label, group, description = RESISTANCES[key]
        if table == 'AtkParam_Npc' and key in ATTACK_FIELDS:
            label, group, description = ATTACK_FIELDS[key]
        if table == 'EquipParamProtector' and key in ARMOR_FIELDS:
            label, group, description = ARMOR_FIELDS[key]
        if table == EFFECT_TABLE:
            label, group, description = presentation(key, label, description)
        enum_name = attrs.get('Enum') or node.findtext('Enum')
        if 'IsBool' in attrs or enum_name in ('EQUIP_BOOL', 'SP_EFFECT_BOOL'): enum_name = None
        choices = _enum(enum_name) if enum_name else {}
        if table == 'AtkParam_Npc' and key == 'atkAttribute':
            choices = {**choices, '0': 'Standard'}
        padding = dtype == 'dummy8' or 'Padding' in attrs or key.lower().startswith('pad')
        # Goods and Magic carry sixteen one-bit covenant slots. Their own
        # annotations named them differently (Goods by number only, Magic by
        # name up to 9, then by number), so both read the game's covenant
        # list. DS1 has nine covenants and "none"; the other slots stay as
        # stored and are not shown.
        vow = re.fullmatch(r'vowType(\d+)', key) if table in ('EquipParamGoods', 'Magic') else None
        if vow:
            covenant = _enum('VOW_TYPE').get(vow[1], '').removeprefix('Covenant: ')
            if not covenant or covenant.isdigit():
                padding = True
            else:
                thing = 'spell' if table == 'Magic' else 'item'
                label = 'Usable with no covenant' if covenant == 'None' else f'Usable in {covenant}'
                description = (f'If ON, this {thing} can be used while in no covenant.' if covenant == 'None'
                               else f'If ON, this {thing} can be used while in the {covenant} covenant.')
        protected = padding or count != 1 or 'Obsolete' in attrs or not annotation or (enum_name and not choices) or bool(re.search(r'unknown|unused|dummy|reserved|^unk', label, re.I))
        reason = ''
        if table == EFFECT_TABLE:
            if key in EFFECT_PROTECTED:
                protected, reason = True, EFFECT_PROTECTED[key]
            elif 'Obsolete' in attrs:
                protected, reason = True, 'This is a legacy field with no supported use.'
            elif enum_name and not choices:
                reason = 'The choices for this property are not documented.'
            if protected:
                group = 'Protected properties'
        if table == 'NpcParam' and key not in RESISTANCES:
            protected = True
        if table in ('BehaviorParam', 'Bullet') or (table == 'AtkParam_Npc' and key not in ATTACK_FIELDS):
            protected = True
        field = FieldSpec(key, dtype, field_offset, count, bit_used if bits else None, bits,
                          label, description, group,
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
        fields.append({'spec': field, 'min': low, 'max': high, 'enum': choices, 'editable': not protected, 'protectedReason': reason})
        if bits: bit_used += bits
    if offset != TABLES[table][0]:
        raise FormatError(f'{table} definition size {offset} does not match the audited row size')
    return {'type': param_type, 'size': offset, 'fields': fields, 'names': names}


def _shown(value, field):
    """A stored value as the reader should see it."""
    if field.dtype == 'f32' and isinstance(value, float) and math.isfinite(value):
        return float(f'{value:.7g}')
    return value


class ItemDocument:
    def __init__(self, source):
        self.original = source
        self.original_plain = inflate(source)
        self.plain = bytearray(self.original_plain)
        self.members = members(self.plain)
        self.params = {}
        self._rows_by_id = {}
        self._effects = None
        self.schemas = {table: schema(table) for table in TABLES}
        self.dirty = set()
        # The game's own item names (texts.TextDocument), when the store has
        # them; reference names stand in for the rest.
        self.texts = None
        # The game's own parameters, when this document is a mod's: each
        # field's vanilla value, for right-click restore. None means this
        # document was read from the game's own file, so its original is vanilla.
        self.vanilla_document = None
        for table, (row_size, version) in TABLES.items():
            member = self.members.get(table + '.param')
            if member is None and table in OPTIONAL_TABLES:
                continue
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
            self._rows_by_id[table] = {row.row_id: row for row in param.rows}

    @property
    def dirty_count(self):
        return len(self.dirty) + (len(self.texts.dirty) if self.texts else 0)

    def display_name(self, table, row_id, row=None):
        """The item's in-game name, else its reference name, else a number."""
        named = self.texts.name(table, row_id) if self.texts else None
        if named: return named
        row = row or self.params[table].row(row_id)
        return self.schemas[table]['names'].get(row_id) or row.name or (f'Attack {row_id}' if table == 'AtkParam_Npc' else f'Item {row_id}')

    def renamable(self, table):
        return bool(self.texts and self.texts.renamable(table))

    def rename(self, table, row_id, name):
        if not self.renamable(table):
            raise FormatError('These records have no in-game name to change.')
        self._row(table, row_id)
        self.texts.rename(table, row_id, name)
        return self.read_row(table, row_id)

    def _row(self, table, row_id):
        if table not in TABLES or type(row_id) is not int:
            raise FormatError('Invalid item identity')
        if table not in self.params:
            raise FormatError(f'{table}.param is missing. Open a complete Remastered parameter archive.')
        row = self._rows_by_id[table].get(row_id)
        if row is None:
            raise FormatError(f'Expected one row ID {row_id}; found 0')
        start = self.members[table + '.param'].offset + row.data_offset
        return row, start, bytes(self.plain[start:start + TABLES[table][0]])

    def row_values(self, table, row_id):
        """A row's shown properties, for pinned table columns: the stored value,
        and what a reader sees for it (an enum's name, Yes or No)."""
        data = self._row(table, row_id)[2]
        values, display = {}, {}
        for item in self.schemas[table]['fields']:
            field = item['spec']
            if field.padding or field.array_length != 1: continue
            value = _shown(read_field(data, field, '<'), field)
            if isinstance(value, float) and not math.isfinite(value): value = str(value)
            values[field.key] = value
            if field.is_bool: display[field.key] = 'Yes' if value else 'No'
            elif item['enum']: display[field.key] = item['enum'].get(str(value), f'Unknown ({value})')
        return values, display

    def value(self, table, row_id, key):
        field = next(f['spec'] for f in self.schemas[table]['fields'] if f['spec'].key == key)
        return read_field(self._row(table, row_id)[2], field, '<')

    def row_name(self, table, row_id):
        row = self._rows_by_id.get(table, {}).get(row_id)
        fallback = f'Effect {row_id}' if table == EFFECT_TABLE else f'Item {row_id}'
        return self.schemas[table]['names'].get(row_id) or (row.name if row else None) or fallback

    def effect_references(self):
        if self._effects is None:
            self._effects = EffectReferences(self)
        return self._effects

    def list_rows(self, tab):
        if tab in {entry[0] for entry in EFFECT_SUBTABS}:
            if EFFECT_TABLE not in self.params:
                raise FormatError('SpEffectParam.param is missing. Open a complete Remastered parameter archive.')
            return self.effect_references().rows(tab)
        match = next((entry for entry in SUBTABS + ENEMY_SUBTABS + ATTACK_SUBTABS if entry[0] == tab), None)
        if match is None: raise FormatError('Unknown editor subtab')
        table = match[2]
        result = []
        for row in self.params[table].rows:
            if table == 'NpcParam' and not self.is_monster(row.row_id):
                continue
            if table == 'EquipParamGoods':
                category = self.value(table, row.row_id, 'goodsType')
                if tab != ('keys' if category == 1 else 'upgrades' if category == 2 else 'consumables'):
                    continue
                # Spell records are edited through Magic, not duplicate inventory goods.
                if category in (5, 6, 7): continue
            if table == 'EquipParamWeapon':
                ammo = self.value(table, row.row_id, 'weaponCategory') in (13, 14)
                if (tab == 'ammo') != ammo: continue
            values, display = self.row_values(table, row.row_id)
            result.append({'id': row.row_id, 'name': self.display_name(table, row.row_id, row), 'table': table,
                           'values': values, 'display': display})
        if tab == 'spells':
            table = 'EquipParamGoods'
            for row in self.params[table].rows:
                if self.value(table, row.row_id, 'goodsType') in (5, 6, 7):
                    values, display = self.row_values(table, row.row_id)
                    result.append({'id': row.row_id, 'name': 'Spell item: ' + self.display_name(table, row.row_id, row), 'table': table,
                                   'values': values, 'display': display})
        return result

    def is_monster(self, row_id):
        return classified_monster(row_id, self.schemas['NpcParam']['names'].get(row_id),
                                  self.value('NpcParam', row_id, 'npcType'))

    def attack_references(self):
        if not hasattr(self, '_attack_references'):
            self._attack_references = AttackReferences(self)
        return self._attack_references

    def _vanilla_row(self, table, row_id):
        """The row's bytes in the game's own file, or None for a row vanilla lacks."""
        if self.vanilla_document is not None:
            try:
                return self.vanilla_document._row(table, row_id)[2]
            except FormatError:
                return None
        _row, start, data = self._row(table, row_id)
        return bytes(self.original_plain[start:start + len(data)])

    def read_row(self, table, row_id):
        if table == 'NpcParam' and not self.is_monster(row_id):
            raise FormatError('This record is not a reviewed standard monster')
        row, _, data = self._row(table, row_id)
        vanilla = self._vanilla_row(table, row_id)
        fields = []
        effect_keys = set(reference_keys(self, table, row_id)) if EFFECT_TABLE in self.params else set()
        for item in self.schemas[table]['fields']:
            field = item['spec']
            if table == 'NpcParam' and field.key not in RESISTANCES:
                continue
            if table == 'AtkParam_Npc' and field.key not in ATTACK_FIELDS:
                continue
            if field.padding or field.array_length != 1: continue
            value = _shown(read_field(data, field, '<'), field)
            finite = not isinstance(value, float) or math.isfinite(value)
            original = _shown(read_field(vanilla, field, '<'), field) if vanilla is not None else None
            if isinstance(original, float) and not math.isfinite(original):
                original = None
            options = self.effect_references().choices if field.key in effect_keys else item['enum']
            fields.append({'key': field.key, 'label': field.label, 'description': field.description,
                           'group': field.group if table in ('NpcParam', 'AtkParam_Npc', EFFECT_TABLE) else '',
                           'dtype': field.dtype, 'value': value if finite else str(value),
                           'type': 'bool' if field.is_bool else 'enum' if options else 'number',
                           'minimum': item['min'], 'maximum': item['max'], 'enum': options, 'protectedReason': item.get('protectedReason', ''),
                           'editable': item['editable'] and finite, 'vanilla': original})
        if table == 'NpcParam':
            order = {key: index for index, key in enumerate(RESISTANCES)}
            fields.sort(key=lambda field: order[field['key']])
        if table in ('EquipParamProtector', 'NpcParam'):
            fields += self._absorption_fields(row_id, table)
        result = {'id': row_id, 'table': table, 'name': self.display_name(table, row_id, row),
                  'renamable': self.renamable(table), 'fields': fields}
        if table == EFFECT_TABLE:
            fields.sort(key=lambda field: EFFECT_GROUPS.index(field['group']))
            result['effectUsage'] = self.effect_references().incoming.get(row_id, [])
        result['effectLinks'] = self.effect_references().outgoing.get((table, row_id), [])
        if table == 'AtkParam_Npc': result['impact'] = self.attack_references().impact(row_id)
        return result

    def _absorption_levels(self, row_id, table='EquipParamProtector'):
        """The record's Armor Rework effects, +0 first, or [] for a record without one."""
        if EFFECT_TABLE not in self.params:
            return []
        if table == 'NpcParam':
            base = ENEMY_ABSORPTION_BASE + row_id
            slots = [self.value('NpcParam', row_id, f'spEffectID{index}') for index in range(8)]
            return [base] if base in slots and base in self._rows_by_id[EFFECT_TABLE] else []
        base = self.value('EquipParamProtector', row_id, 'residentSpEffectId3')
        if base != ABSORPTION_BASE + row_id or base not in self._rows_by_id[EFFECT_TABLE]:
            return []
        return [base + level for level in range(MAX_UPGRADE_LEVEL + 1)
                if base + level in self._rows_by_id[EFFECT_TABLE]]

    def _absorption_fields(self, row_id, table='EquipParamProtector'):
        levels = self._absorption_levels(row_id, table)
        if not levels:
            return []
        fields = []
        for cut, kind in ABSORPTION_CUTS:
            rate = self.value(EFFECT_TABLE, levels[0], cut)
            fields.append({'key': 'absorption:' + cut, 'label': f'{kind} absorption (%)',
                           'description': (f'Share of {kind.lower()} damage this enemy takes off every hit, from its '
                                           'Armor Rework effect. Negative values make it take more damage.'
                                           if table == 'NpcParam' else
                                           f'Share of {kind.lower()} damage this piece absorbs, from its Armor Rework '
                                           'effect. Pieces multiply. Negative values make the wearer take more damage. '
                                           'Upgraded levels keep their bonus over this value.'),
                           'group': 'Absorption', 'dtype': 'f32', 'value': round((1 - rate) * 100, 3),
                           'type': 'number', 'minimum': -100.0, 'maximum': 99.0, 'enum': {},
                           'protectedReason': '', 'editable': True})
        return fields

    def _edit_absorption(self, row_id, cut, value, table='EquipParamProtector'):
        levels = self._absorption_levels(row_id, table)
        if not levels or cut not in dict(ABSORPTION_CUTS):
            raise FormatError('This record has no Armor Rework absorption')
        if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or not -100 <= value <= 99:
            raise FormatError('Absorption must be between -100 and 99')
        # Every upgrade level moves by the same amount, so its bonus over +0 stays.
        change = value - (1 - self.value(EFFECT_TABLE, levels[0], cut)) * 100
        for effect in levels:
            current = (1 - self.value(EFFECT_TABLE, effect, cut)) * 100
            absorbed = min(99.0, max(-100.0, current + change))
            self.edit(EFFECT_TABLE, effect, cut, round(1 - absorbed / 100, 6))
        return self.read_row(table, row_id)

    def edit(self, table, row_id, key, value):
        if table in ('EquipParamProtector', 'NpcParam') and isinstance(key, str) and key.startswith('absorption:'):
            if table == 'NpcParam' and not self.is_monster(row_id):
                raise FormatError('This record is not a reviewed standard monster')
            self._row(table, row_id)
            return self._edit_absorption(row_id, key.split(':', 1)[1], value, table)
        if table == 'NpcParam' and not self.is_monster(row_id):
            raise FormatError('This record is not a reviewed standard monster')
        row, start, data = self._row(table, row_id)
        item = next((f for f in self.schemas[table]['fields'] if f['spec'].key == key), None)
        if item is None or not item['editable']:
            raise FormatError('This field is protected')
        field = item['spec']
        if (type(value) not in (int, float, bool) or (type(value) is bool and not field.is_bool)
                or (isinstance(value, float) and not math.isfinite(value))):
            raise FormatError('Enter a finite number')
        if field.dtype not in ('f32', 'f64', 'angle32') and int(value) != value:
            raise FormatError('Enter a whole number')
        if field.is_bool and value not in (0, 1): raise FormatError('Expected a checkbox value')
        if not item['min'] <= value <= item['max']:
            raise FormatError(f"{field.label} must be between {item['min']} and {item['max']}")
        if item['enum'] and str(int(value)) not in item['enum']:
            raise FormatError('Choose a listed value')
        if EFFECT_TABLE in self.params and key in set(reference_keys(self, table, row_id)):
            if str(int(value)) not in self.effect_references().choices:
                raise FormatError('Choose an existing effect or None')
        replacement = write_field(data, field, value, '<')
        self._effects = None
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
        return deflate(self.original, self.plain)
