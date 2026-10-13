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
from .monsters import NPC_FIELDS, RESISTANCES, WEAKNESSES, classified_monster, duplicate_stem, base_stem, MONSTER_FAMILIES
from .attacks import ATTACK_FIELDS, AttackReferences
from .effects import TABLE as EFFECT_TABLE, SUBTABS as EFFECT_SUBTABS, GROUPS as EFFECT_GROUPS, PROTECTED as EFFECT_PROTECTED, presentation, EffectReferences, reference_keys, reference_switches

FormatError = DS3FormatError
GRAPH_TABLE = 'CalcCorrectGraph'
METADATA = Path(__file__).with_name('metadata')
TABLES = {'EquipParamGoods': (92, 1), 'EquipParamWeapon': (272, 1),
          'EquipParamProtector': (232, 2), 'EquipParamAccessory': (64, 1), 'Magic': (48, 2),
          'NpcParam': (336, 3), 'AtkParam_Npc': (128, 1), 'AtkParam_Pc': (128, 1),
          'BehaviorParam': (32, 2), 'Bullet': (160, 2), 'SpEffectParam': (368, 2),
          'ReinforceParamWeapon': (88, 1), 'ReinforceParamProtector': (48, 1),
          'ItemLotParam': (148, 2), 'ShopLineupParam': (32, 1), 'ObjActParam': (32, 1),
          'NpcThinkParam': (112, 1),
          GRAPH_TABLE: (80, 1)}
OPTIONAL_TABLES = frozenset({'SpEffectParam', GRAPH_TABLE})
SIZES = {'u8': 1, 's8': 1, 'dummy8': 1, 'u16': 2, 's16': 2,
         'u32': 4, 's32': 4, 'b32': 4, 'f32': 4, 'angle32': 4, 'f64': 8}
MAX_ARCHIVE = 64 * 1024 * 1024
SUBTABS = (
    ('consumables', 'Consumables', 'EquipParamGoods'),
    ('upgrades', 'Upgrade Items', 'EquipParamGoods'),
    ('keys', 'Key Items', 'EquipParamGoods'), ('spells', 'Spells', 'Magic'),
    ('weapons', 'Weapons', 'EquipParamWeapon'), ('ammo', 'Ammo', 'EquipParamWeapon'),
    ('armor', 'Armor', 'EquipParamProtector'), ('rings', 'Rings', 'EquipParamAccessory'),
    ('menu-labels', 'Menu labels', 'MenuText'),
)
ENEMY_SUBTABS = (('monsters', 'Monsters', 'NpcParam'),
                 ('behaviors', 'Behaviors', 'BehaviorParam'),
                 ('ai', 'AI', 'NpcThinkParam'))

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

# What a cast spends. Vanilla leaves every spell at 0 (free); the Spell
# Stamina Costs tweak sets each spell's Elden Ring value.
MAGIC_FIELDS = {
    'stamina': ('Stamina Consumption', 'Properties',
                'Each cast of this spell spends this much stamina. 0 is free, as in vanilla. '
                'The Spell Stamina Costs tweak sets each spell\'s Elden Ring value.'),
}

# Armor Rework gives every armor piece its own absorption effect in slot 3,
# one per upgrade level: effect ID = 30,000,000 + armor ID + level.
ABSORPTION_BASE = 30_000_000
# Enemies too: 40,000,000 + enemy ID, in one of the enemy's spEffectID slots.
ENEMY_ABSORPTION_BASE = 40_000_000
ABSORPTION_CUTS = (('neutralDamageCutRate', 'Physical'), ('slashDamageCutRate', 'Slash'),
                   ('blowDamageCutRate', 'Strike'), ('thrustDamageCutRate', 'Thrust'),
                   ('magicDamageCutRate', 'Magic'), ('fireDamageCutRate', 'Fire'),
                   ('thunderDamageCutRate', 'Lightning'))
# The armor upgrade table column that scales each cut at higher upgrade levels.
# Slash, strike and thrust follow their own columns, independent of physical.
UPGRADE_MULTIPLIERS = {'neutralDamageCutRate': 'physicsDefRate', 'slashDamageCutRate': 'slashDefRate',
                       'blowDamageCutRate': 'blowDefRate', 'thrustDamageCutRate': 'thrustDefRate',
                       'magicDamageCutRate': 'magicDefRate', 'fireDamageCutRate': 'fireDefRate',
                       'thunderDamageCutRate': 'thunderDefRate'}
MAX_UPGRADE_LEVEL = 15
ATTACK_SUBTABS = (('attacks', 'Attacks', 'AtkParam_Npc'),
                  ('player-attacks', 'Player attacks', 'AtkParam_Pc'),
                  ('projectiles', 'Projectiles', 'Bullet'))
WORLD_SUBTABS = (('drops', 'Drops', 'ItemLotParam'),
                 ('shops', 'Shops', 'ShopLineupParam'),
                 ('treasure', 'Treasure', 'ObjActParam'))
# Reviewed behavior and projectile fields. Costs, call targets and flight
# physics are safe numbers; identity and judgement fields stay read-only.
BEHAVIOR_EDITABLE = frozenset({'stamina', 'mp', 'heroPoint', 'category', 'refType', 'refId'})
BULLET_EDITABLE = frozenset({
    'life', 'dist', 'shootInterval', 'gravityInRange', 'gravityOutRange',
    'initVellocity', 'accelInRange', 'accelOutRange', 'maxVellocity', 'minVellocity',
    'accelTime', 'homingBeginDist', 'homingAngle', 'hormingStopRange', 'hormingOffsetRange',
    'hitRadius', 'hitRadiusMax', 'spreadTime', 'expDelay', 'numShoot',
    'shootAngle', 'shootAngleInterval', 'shootAngleXInterval', 'shootAngleXZ',
    'dmgHitRecordLifeTime', 'damageDamp', 'spelDamageDamp', 'fireDamageDamp',
    'thunderDamageDamp', 'staminaDamp', 'knockbackDamp', 'lockShootLimitAng',
    'isPenetrate', 'isPenetrateMap', 'isHitBothTeam', 'isAttackSFX', 'isEndlessHit',
    'isHitForceMagic', 'isHitDarkForceMagic', 'atkId_Bullet', 'HitBulletID',
    'autoSearchNPCThinkID', 'spEffectId0', 'spEffectId1', 'spEffectId2', 'spEffectId3',
    'spEffectId4', 'spEffectIDForShooter', 'atkAttribute', 'spAttribute',
    'launchConditionType', 'FollowType'})
# Reviewed AI fields. Senses, distances, timers and movement flags are safe
# numbers; logic and goal script IDs stay read-only.
THINK_EDITABLE = frozenset({
    'nearDist', 'midDist', 'farDist', 'outDist', 'BackHomeLife_OnHitEneWal',
    'eye_dist', 'ear_dist', 'ear_soundcut_dist', 'nose_dist',
    'maxBackhomeDist', 'backhomeDist', 'backhomeBattleDist', 'nonBattleActLife',
    'BackHome_LookTargetTime', 'BackHome_LookTargetDist',
    'SightTargetForgetTime', 'SoundTargetForgetTime', 'BattleStartDist',
    'targetSys_DmgEffectRate', 'TeamAttackEffectivity',
    'eye_angX', 'eye_angY', 'ear_angX', 'ear_angY',
    'callHelp_CallValidMinDistTarget', 'callHelp_CallValidRange',
    'callHelp_ForgetTimeByArrival', 'callHelp_MinWaitTime', 'callHelp_MaxWaitTime',
    'goalAction_ToCaution', 'goalAction_ToFind', 'callHelp_ReplyBehaviorType',
    'disablePathMove', 'skipArrivalVisibleCheck', 'thinkAttr_doAdmirer',
    'enableNaviFlg_Edge', 'enableNaviFlg_LargeSpace', 'enableNaviFlg_Ladder',
    'enableNaviFlg_Hole', 'enableNaviFlg_Door', 'enableNaviFlg_InSideWall'})
STATS_SUBTABS = (
    ('curves', 'Scaling curves', GRAPH_TABLE),
    ('scaling', 'Weapon scaling', 'EquipParamWeapon'),
    ('spell-reqs', 'Spell requirements', 'Magic'),
    ('weapon-upgrades', 'Weapon upgrades', 'ReinforceParamWeapon'),
    ('armor-upgrades', 'Armor upgrades', 'ReinforceParamProtector'),
)
# The Stats tab shows these properties of records it shares with Items. Curves
# and upgrade levels show every field, so those tables list their whole
# schema here.
STATS_WHOLE_TABLES = (GRAPH_TABLE, 'ReinforceParamWeapon', 'ReinforceParamProtector')
STATS_FIELDS = {
    GRAPH_TABLE: ('stageMaxVal0', 'stageMaxVal1', 'stageMaxVal2', 'stageMaxVal3', 'stageMaxVal4',
                  'stageMaxGrowVal0', 'stageMaxGrowVal1', 'stageMaxGrowVal2', 'stageMaxGrowVal3',
                  'stageMaxGrowVal4', 'adjPt_maxGrowVal0', 'adjPt_maxGrowVal1', 'adjPt_maxGrowVal2',
                  'adjPt_maxGrowVal3', 'adjPt_maxGrowVal4', 'init_inclination_soul',
                  'adjustment_value', 'boundry_inclination_soul', 'boundry_value'),
    'EquipParamWeapon': ('properStrength', 'properAgility', 'properMagic', 'properFaith',
                         'correctStrength', 'correctAgility', 'correctMagic', 'correctFaith',
                         'correctType', 'isLuckCorrect', 'levelSyncCorrectID'),
    'Magic': ('requirementIntellect', 'requirementFaith', 'slotLength', 'stamina'),
    'ReinforceParamWeapon': ('physicsAtkRate', 'magicAtkRate', 'fireAtkRate', 'thunderAtkRate',
                  'staminaAtkRate', 'saWeaponAtkRate', 'saDurabilityRate', 'correctStrengthRate',
                  'correctAgilityRate', 'correctMagicRate', 'correctFaithRate', 'physicsGuardCutRate',
                  'magicGuardCutRate', 'fireGuardCutRate', 'thunderGuardCutRate',
                  'poisonGuardResistRate', 'diseaseGuardResistRate', 'bloodGuardResistRate',
                  'curseGuardResistRate', 'staminaGuardDefRate', 'spEffectId1', 'spEffectId2',
                  'spEffectId3', 'residentSpEffectId1', 'residentSpEffectId2', 'residentSpEffectId3',
                  'materialSetId', 'reinforcementLevel'),
    'ReinforceParamProtector': ('physicsDefRate', 'magicDefRate', 'fireDefRate', 'thunderDefRate',
                  'slashDefRate', 'blowDefRate', 'thrustDefRate', 'resistPoisonRate',
                  'resistDiseaseRate', 'resistBloodRate', 'resistCurseRate', 'residentSpEffectId1',
                  'residentSpEffectId2', 'residentSpEffectId3', 'materialSetId'),
}


def stats_fields(sub, table):
    """A Stats subtab's field filter for a record, or None for every field."""
    match = next((entry for entry in STATS_SUBTABS if entry[0] == sub), None)
    if match is None or match[2] != table or table in STATS_WHOLE_TABLES:
        return None
    return STATS_FIELDS[table]


def _graph_group(key):
    if key.startswith('stageMaxVal'):
        return 'Thresholds'
    if key.startswith('stageMaxGrowVal'):
        return 'Growth'
    if key.startswith('adjPt_maxGrowVal'):
        return 'Curve shape'
    return 'Level-up cost'


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
        try:
            name = plain[name_offset:end].decode('shift_jis')
        except UnicodeDecodeError:
            raise FormatError('BND3 name is not decodable')
        name = name.replace('\\', '/').rsplit('/', 1)[-1]
        if name in result:
            raise FormatError('Duplicate BND3 member name')
        result[name] = Member(name, offset, size)
        spans.append((offset, offset + size))
    spans.sort()
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise FormatError('Overlapping BND3 payloads')
    return result


def pack(template, items):
    """Rebuild a binder: the template's layout carrying new member bytes.

    The names must match the template's; entry order, ids and stored names
    are kept, and payloads are laid out as the game ships them: names packed
    tight, data starting on a 16-byte boundary, each non-empty payload aligned
    to 16 bytes, empty members taking no space.
    """
    owned = members(template)
    if set(items) != set(owned):
        raise FormatError('Rebuilt binder members do not match its template')
    count = struct.unpack_from('<I', template, 16)[0]
    directory_end = 32 + count * 24
    stored = []
    for index in range(count):
        _flags, _size, _offset, file_id, name_offset, _unpacked = struct.unpack_from(
            '<6I', template, 32 + index * 24)
        full = bytes(template[name_offset:template.find(b'\0', name_offset) + 1])
        base = full[:-1].decode('shift_jis').replace('\\', '/').rsplit('/', 1)[-1]
        stored.append((file_id, full, bytes(items[base])))
    names_end = directory_end + sum(len(full) for _id, full, _data in stored)
    out = bytearray(template[:32])
    struct.pack_into('<II', out, 16, count, names_end)
    out += b'\0' * (directory_end - len(out))
    name_offsets = []
    for _id, full, _data in stored:
        name_offsets.append(len(out))
        out += full
    out += b'\0' * (-len(out) % 16)
    for index, ((file_id, _full, data), name_offset) in enumerate(zip(stored, name_offsets)):
        # Aligned lazily: an empty member sits tight after the previous
        # payload, and only a payload with bytes moves to a 16-byte boundary.
        if data:
            out += b'\0' * (-len(out) % 16)
        struct.pack_into('<6I', out, 32 + index * 24, 0x40, len(data), len(out),
                         file_id, name_offset, len(data))
        out += data
    return bytes(out)


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
        if table == 'NpcParam' and key in NPC_FIELDS:
            label, group, description = NPC_FIELDS[key]
        if table in ('AtkParam_Npc', 'AtkParam_Pc') and key in ATTACK_FIELDS:
            label, group, description = ATTACK_FIELDS[key]
        if table == 'EquipParamProtector' and key in ARMOR_FIELDS:
            label, group, description = ARMOR_FIELDS[key]
        if table == 'Magic' and key in MAGIC_FIELDS:
            label, group, description = MAGIC_FIELDS[key]
        if table == EFFECT_TABLE:
            label, group, description = presentation(key, label, description)
        enum_name = attrs.get('Enum') or node.findtext('Enum')
        if 'IsBool' in attrs or enum_name in ('EQUIP_BOOL', 'SP_EFFECT_BOOL'): enum_name = None
        choices = _enum(enum_name) if enum_name else {}
        if table in ('AtkParam_Npc', 'AtkParam_Pc') and key == 'atkAttribute':
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
        if table == 'NpcParam' and key not in NPC_FIELDS:
            protected = True
        if table == 'BehaviorParam' and key not in BEHAVIOR_EDITABLE:
            protected = True
        if table == 'Bullet' and key not in BULLET_EDITABLE:
            protected = True
        if table == 'NpcThinkParam' and key not in THINK_EDITABLE:
            protected = True
        if table in ('AtkParam_Npc', 'AtkParam_Pc') and key not in ATTACK_FIELDS:
            protected = True
        field = FieldSpec(key, dtype, field_offset, count, bit_used if bits else None, bits,
                          label, description, group,
                          'IsBool' in attrs or bits == 1 or (table == 'NpcParam' and key in WEAKNESSES),
                          enum_name, attrs.get('Refs'), padding)
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
        # An enemy's guard absorption is 0-100% for every kind; slash, strike
        # and thrust were declared -100 to 100 though no enemy goes below 0.
        if table == 'NpcParam' and key in ('slashGuardCutRate', 'blowGuardCutRate', 'thrustGuardCutRate'):
            low = max(low, 0)
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
        # Rows this session added (no original bytes) and removed, by identity.
        self._added_rows = set()
        self._removed_rows = []
        # When each change was last made, so Save's list reads newest first.
        self._edited_at = {}
        # The game's own item names (texts.TextDocument), when the store has
        # them; reference names stand in for the rest.
        self.texts = None
        # The game's own menu text (texts.MenuDocument), when the store
        # has it; without it the Menu labels subtab is empty.
        self.menu_texts = None
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
            # Byte 47 is the shipped paramdef version: 0 everywhere except
            # ReinforceParamWeapon, which ships 0xff.
            if len(payload) < 48 or payload[44:47] != b'\0\x02\0' or payload[47] not in (0, 0xff):
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

    def _change_key(self, table, row_id, key):
        """The change a stored field belongs to, as the reader made it."""
        if table == EFFECT_TABLE and key.endswith('DamageCutRate') and row_id >= ABSORPTION_BASE:
            if row_id >= ENEMY_ABSORPTION_BASE:
                return ('NpcParam', row_id - ENEMY_ABSORPTION_BASE, 'absorption:' + key)
            return ('EquipParamProtector', (row_id - ABSORPTION_BASE) // 100 * 100, 'absorption:' + key)
        return (table, row_id, key)

    @property
    def dirty_count(self):
        changes = {self._change_key(*entry) for entry in self.dirty}
        return len(changes) + len(self._removed_rows) + (len(self.texts.dirty) if self.texts else 0) + (len(self.menu_texts.dirty) if self.menu_texts else 0)

    def pending_changes(self, limit=200):
        """What Save would write, one row per change: label, before and after."""
        rows = []
        latest = {}
        for entry in self.dirty:
            change = self._change_key(*entry)
            latest[change] = max(latest.get(change, 0), self._edited_at.get(entry, 0))
        for table, row_id, key in sorted(latest, key=lambda change: (-latest[change], str(change)))[:limit]:
            try:
                name = self.display_name(table, row_id)
                if key.startswith('absorption:'):
                    cut = key.split(':', 1)[1]
                    base = (ENEMY_ABSORPTION_BASE if table == 'NpcParam' else ABSORPTION_BASE) + row_id
                    field = next(f['spec'] for f in self.schemas[EFFECT_TABLE]['fields'] if f['spec'].key == cut)
                    _r, start, data = self._row(EFFECT_TABLE, base)
                    before = read_field(bytes(self.original_plain[start:start + len(data)]), field, '<')
                    after = read_field(data, field, '<')
                    kind = dict(ABSORPTION_CUTS)[cut]
                    # The precision the field shows: at one decimal, 3.95% and
                    # 4.04% both read "4.0% -> 4.0%", a change that looked like none.
                    percent = lambda rate: f'{(1 - rate) * 100:.3f}'.rstrip('0').rstrip('.') + '%'
                    rows.append({'label': f'{name} · {kind} absorption',
                                 'before': percent(before), 'after': percent(after)})
                    continue
                item = next(f for f in self.schemas[table]['fields'] if f['spec'].key == key)
                field = item['spec']
                _r, start, data = self._row(table, row_id)
                added = (table, row_id) in self._added_rows
                before = None if added else _shown(read_field(bytes(self.original_plain[start:start + len(data)]), field, '<'), field)
                after = _shown(read_field(data, field, '<'), field)
                rows.append({'label': f'{name} · {field.label}', 'before': before, 'after': after})
            except (FormatError, StopIteration, KeyError):
                rows.append({'label': f'{table} {row_id} · {key}'})
        for gone in self._removed_rows:
            rows.append({'label': f"{gone['name']} (removed)",
                         'before': f"{gone['table']} {gone['id']}", 'after': 'removed'})
        if self.texts:
            from .texts import KIND_LABELS
            for kind, table, item in sorted(self.texts.dirty, key=str)[:limit]:
                rows.append({'label': f'{KIND_LABELS[kind]} · {table} {item}'})
        if self.menu_texts:
            from .texts import MENU_LABELS
            for key in sorted(self.menu_texts.dirty):
                display, _text_id = MENU_LABELS[key]
                rows.append({'label': f'Menu label · {display}',
                             'before': self.menu_texts.original_label(key) or '',
                             'after': self.menu_texts.label(key) or ''})
        return rows

    def display_name(self, table, row_id, row=None):
        """The item's in-game name, else its reference name, else a number."""
        if table == 'MenuText':
            from .texts import MENU_LABELS, MENU_LABEL_IDS
            if row_id in MENU_LABEL_IDS:
                return MENU_LABELS[MENU_LABEL_IDS[row_id]][0]
            return f'Menu label {row_id}'
        named = self.texts.name(table, row_id) if self.texts else None
        if named: return named
        row = row or self.params[table].row(row_id)
        fallback = f'Item {row_id}'
        if table in ('AtkParam_Npc', 'AtkParam_Pc'):
            fallback = f'Attack {row_id}'
        elif table == 'ItemLotParam':
            fallback = f'Drop {row_id}'
        elif table == 'ShopLineupParam':
            fallback = f'Shop entry {row_id}'
        elif table == 'ObjActParam':
            fallback = f'Treasure {row_id}'
        elif table == 'BehaviorParam':
            fallback = f'Behavior {row_id}'
        elif table == 'Bullet':
            fallback = f'Projectile {row_id}'
        elif table == 'NpcThinkParam':
            fallback = f'AI {row_id}'
        return self.schemas[table]['names'].get(row_id) or row.name or fallback

    def renamable(self, table):
        return bool(self.texts and self.texts.renamable(table))

    def rename(self, table, row_id, name, only=None):
        if not self.renamable(table):
            raise FormatError('These records have no in-game name to change.')
        self._row(table, row_id)
        self.texts.rename(table, row_id, name)
        self._effects = None  # effect choices and links are listed by name
        return self.read_row(table, row_id, only=only)

    def _description_fields(self, table, row_id):
        """The item's in-game descriptions as detail fields, longest last."""
        result = []
        for key, long, label, help, limit, control in (
                ('description', False, 'Description',
                 'The one-line summary shown in the inventory list. Up to 200 characters. Blank removes it.',
                 200, 'text'),
                ('longDescription', True, 'Full description',
                 'The full text shown on the item detail screen. It can span lines, up to 2000 characters. Blank removes it.',
                 2000, 'longtext')):
            current = self.texts.description(table, row_id, long) or ''
            original = self.texts.original_description(table, row_id, long) or ''
            result.append({'key': key, 'label': label, 'description': help, 'group': 'Description',
                           'dtype': 'text', 'value': current, 'type': control,
                           'minimum': None, 'maximum': None, 'maxLength': limit,
                           'required': False, 'enum': {}, 'protectedReason': '',
                           'editable': True, 'vanilla': original})
        return result

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
        if tab in {entry[0] for entry in STATS_SUBTABS}:
            return self._stats_rows(tab)
        if tab == 'menu-labels':
            return self._menu_label_rows()
        match = next((entry for entry in SUBTABS + ENEMY_SUBTABS + ATTACK_SUBTABS + WORLD_SUBTABS if entry[0] == tab), None)
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

    def _stats_rows(self, tab):
        """One Stats subtab: every curve, every weapon's scaling or every spell's requirements."""
        if tab == 'curves':
            if GRAPH_TABLE not in self.params:
                raise FormatError('CalcCorrectGraph.param is missing. Open a complete Remastered parameter archive.')
            table = GRAPH_TABLE
        else:
            table = next(entry[2] for entry in STATS_SUBTABS if entry[0] == tab)
        result = []
        for row in self.params[table].rows:
            values, display = self.row_values(table, row.row_id)
            result.append({'id': row.row_id, 'name': self.display_name(table, row.row_id, row),
                           'table': table, 'values': values, 'display': display})
        return result

    def _menu_label_rows(self):
        """The equipment defense labels as records: fixed names, editable text."""
        if self.menu_texts is None:
            return []
        from .texts import MENU_LABELS
        return [{'id': text_id, 'table': 'MenuText', 'name': display,
                 'values': {'label': self.menu_texts.label(key) or ''}, 'display': {}}
                for key, (display, text_id) in MENU_LABELS.items()]

    def is_monster(self, row_id):
        if classified_monster(row_id, self.schemas['NpcParam']['names'].get(row_id),
                              self.value('NpcParam', row_id, 'npcType')):
            return True
        # A duplicate of a reviewed monster keeps its bytes and semantics;
        # only the reference name is missing. Its param name, which readers
        # cannot edit, carries the family stem instead.
        row = self._rows_by_id['NpcParam'].get(row_id)
        stem = duplicate_stem(row.name, row_id) if row is not None else None
        return (row_id >= 120000 and stem in MONSTER_FAMILIES
                and self.value('NpcParam', row_id, 'npcType') == 0) if row is not None else False

    def attack_references(self):
        if not hasattr(self, '_attack_references'):
            self._attack_references = AttackReferences(self)
        return self._attack_references

    def _vanilla_row(self, table, row_id):
        """The row's bytes in the game's own file, or None for a row vanilla lacks."""
        if (table, row_id) in self._added_rows:
            return None
        if self.vanilla_document is not None:
            try:
                return self.vanilla_document._row(table, row_id)[2]
            except FormatError:
                return None
        _row, start, data = self._row(table, row_id)
        return bytes(self.original_plain[start:start + len(data)])

    def _value_spans(self, table):
        """Each number's span across the game's own rows of a table, for the
        slider. A field bounded only by its type put every record's fill at
        the same spot. Read once per table."""
        cache = self.__dict__.setdefault('_spans_cache', {})
        if table in cache:
            return cache[table]
        source = self.vanilla_document if self.vanilla_document is not None else self
        plain = source.plain if source is not self else self.original_plain
        offset, size = source.members[table + '.param'].offset, TABLES[table][0]
        fields = [item['spec'] for item in self.schemas[table]['fields']
                  if not item['spec'].padding and item['spec'].array_length == 1 and not item['spec'].is_bool]
        found = {}
        for row in source.params[table].rows:
            data = bytes(plain[offset + row.data_offset:offset + row.data_offset + size])
            for field in fields:
                value = read_field(data, field, '<')
                if isinstance(value, float) and not math.isfinite(value):
                    continue
                low, high = found.get(field.key, (value, value))
                found[field.key] = (min(low, value), max(high, value))
        spans = {}
        for key, (low, high) in found.items():
            # From zero (or the lowest value, when the game goes below zero)
            # to a quarter past the highest, so the largest vanilla value is
            # not already the end of the slider.
            low = min(low, 0)
            high = high + (high - low) * 0.25 if high > low else low + max(1, abs(low))
            spans[key] = (low, high)
        cache[table] = spans
        return spans

    def read_row(self, table, row_id, only=None):
        if table == 'MenuText':
            return self._read_menu_label(row_id, only)
        if table == 'NpcParam' and not self.is_monster(row_id):
            raise FormatError('This record is not a reviewed standard monster')
        row, _, data = self._row(table, row_id)
        vanilla = self._vanilla_row(table, row_id)
        fields = []
        spans = self._value_spans(table)
        effect_keys = set(reference_keys(self, table, row_id)) if EFFECT_TABLE in self.params else set()
        for item in self.schemas[table]['fields']:
            field = item['spec']
            if table == 'NpcParam' and field.key not in NPC_FIELDS:
                continue
            if table in ('AtkParam_Npc', 'AtkParam_Pc') and field.key not in ATTACK_FIELDS:
                continue
            if table == 'BehaviorParam' and field.key not in BEHAVIOR_EDITABLE:
                continue
            if table == 'Bullet' and field.key not in BULLET_EDITABLE:
                continue
            if table == 'NpcThinkParam' and field.key not in THINK_EDITABLE:
                continue
            if field.padding or field.array_length != 1: continue
            value = _shown(read_field(data, field, '<'), field)
            finite = not isinstance(value, float) or math.isfinite(value)
            original = _shown(read_field(vanilla, field, '<'), field) if vanilla is not None else None
            if isinstance(original, float) and not math.isfinite(original):
                original = None
            options = self.effect_references().choices if field.key in effect_keys else item['enum']
            # A float the PARAMDEF leaves unbounded shows no range: dtype
            # extremes (±3.4e38) are not bounds the reader can act on.
            unbounded = field.dtype in ('f32', 'f64', 'angle32') and (item['min'], item['max']) in (
                (-3.4028234663852886e38, 3.4028234663852886e38), (-1.7976931348623157e308, 1.7976931348623157e308))
            fields.append({'key': field.key, 'label': field.label, 'description': field.description,
                           'group': _graph_group(field.key) if table == GRAPH_TABLE else
                           field.group if table in ('NpcParam', 'AtkParam_Npc', 'AtkParam_Pc', EFFECT_TABLE) else '',
                           'dtype': field.dtype, 'value': value if finite else str(value),
                           'type': 'bool' if field.is_bool else 'enum' if options else 'number',
                           'minimum': None if unbounded else item['min'], 'maximum': None if unbounded else item['max'],
                           'enum': options, 'protectedReason': item.get('protectedReason', ''),
                           'editable': item['editable'] and finite, 'vanilla': original,
                           'sliderMin': spans.get(field.key, (None, None))[0],
                           'sliderMax': spans.get(field.key, (None, None))[1]})
        if table == 'NpcParam':
            order = {key: index for index, key in enumerate(NPC_FIELDS)}
            fields.sort(key=lambda field: order[field['key']])
        if table in ('AtkParam_Npc', 'AtkParam_Pc'):
            order = {key: index for index, key in enumerate(ATTACK_FIELDS)}
            fields.sort(key=lambda field: order[field['key']])
        if table in ('EquipParamProtector', 'NpcParam'):
            # With Armor Rework, absorption replaces flat defense: it takes the
            # defense fields' place, and they are not shown (they stay 0).
            absorption = self._absorption_fields(row_id, table)
            if absorption:
                replaced = set(ARMOR_FIELDS) if table == 'EquipParamProtector' else {
                    'def_phys', 'def_slash', 'def_blow', 'def_thrust', 'def_mag', 'def_fire', 'def_thunder'}
                group = next(field['group'] for field in fields if field['key'] in replaced)
                for field in absorption:
                    field['group'] = group
                at = next(index for index, field in enumerate(fields) if field['key'] in replaced)
                fields = ([field for field in fields[:at] if field['key'] not in replaced] + absorption
                          + [field for field in fields[at:] if field['key'] not in replaced])
        if self.texts is not None and self.texts.describable(table):
            fields += self._description_fields(table, row_id)
        if only is not None:
            keep = set(only)
            fields = [field for field in fields if field['key'] in keep]
        result = {'id': row_id, 'table': table, 'name': self.display_name(table, row_id, row),
                  'renamable': self.renamable(table), 'fields': fields}
        if table == EFFECT_TABLE:
            fields.sort(key=lambda field: EFFECT_GROUPS.index(field['group']))
            result['effectUsage'] = self.effect_references().incoming.get(row_id, [])
        result['effectLinks'] = self.effect_references().outgoing.get((table, row_id), [])
        if table == 'AtkParam_Npc': result['impact'] = self.attack_references().impact(row_id)
        return result

    def _read_menu_label(self, row_id, only=None):
        from .texts import MENU_LABELS, MENU_LABEL_IDS
        if self.menu_texts is None or row_id not in MENU_LABEL_IDS:
            raise FormatError('Unknown menu label')
        key = MENU_LABEL_IDS[row_id]
        fields = []
        if only is None or 'label' in only:
            fields.append({'key': 'label', 'label': 'Menu label',
                           'description': ('The text the equipment panel shows for this defense. '
                                           'One line, up to 200 characters.'),
                           'group': '', 'dtype': 'text', 'value': self.menu_texts.label(key) or '',
                           'type': 'text', 'minimum': None, 'maximum': None, 'maxLength': 200,
                           'required': True, 'enum': {}, 'protectedReason': '',
                           'editable': True, 'vanilla': self.menu_texts.original_label(key) or ''})
        return {'id': row_id, 'table': 'MenuText', 'name': MENU_LABELS[key][0],
                'renamable': False, 'fields': fields, 'effectLinks': []}

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
        # Right-click restores the mod's saved absorption: vanilla has no
        # absorption effects, so the saved build is this field's original.
        _row, start, data = self._row(EFFECT_TABLE, levels[0])
        saved = bytes(self.original_plain[start:start + len(data)])
        specs = {item['spec'].key: item['spec'] for item in self.schemas[EFFECT_TABLE]['fields']}
        for cut, kind in ABSORPTION_CUTS:
            rate = self.value(EFFECT_TABLE, levels[0], cut)
            original = round((1 - read_field(saved, specs[cut], '<')) * 100, 3)
            fields.append({'key': 'absorption:' + cut, 'label': f'{kind} absorption (%)',
                           'description': (f'Share of {kind.lower()} damage this enemy takes off every hit, from its '
                                           'Armor Rework effect. Negative values make it take more damage.'
                                           if table == 'NpcParam' else
                                           f'Share of {kind.lower()} damage this piece absorbs, from its Armor Rework '
                                           'effect. Pieces multiply. Negative values make the wearer take more damage. '
                                           'Upgrade levels scale from this value by the armor upgrade table.'),
                           'group': 'Absorption', 'dtype': 'f32', 'value': round((1 - rate) * 100, 3),
                           'type': 'number', 'minimum': -100.0, 'maximum': 99.0, 'enum': {},
                           'protectedReason': '', 'editable': True, 'vanilla': original})
        return fields

    def _edit_absorption(self, row_id, cut, value, table='EquipParamProtector'):
        levels = self._absorption_levels(row_id, table)
        if not levels or cut not in dict(ABSORPTION_CUTS):
            raise FormatError('This record has no Armor Rework absorption')
        if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or not -100 <= value <= 99:
            raise FormatError('Absorption must be between -100 and 99')
        spec = next(f['spec'] for f in self.schemas[EFFECT_TABLE]['fields'] if f['spec'].key == cut)
        reinforce_key = UPGRADE_MULTIPLIERS[cut]
        reinforce_rows = self._rows_by_id.get('ReinforceParamProtector', {})
        reinforce_id = self.value('EquipParamProtector', row_id, 'reinforceTypeId') if table != 'NpcParam' else None
        for effect in levels:
            # An upgrade level scales the +0 absorption by the armor upgrade
            # table's multiplier for that level; 0 stays 0, a negative value
            # moves toward zero by the same step. Without a row, no scaling.
            level = effect - levels[0]
            multiplier = 1.0
            if reinforce_id is not None and reinforce_id + level in reinforce_rows:
                multiplier = self.value('ReinforceParamProtector', reinforce_id + level, reinforce_key)
            absorbed = min(99.0, max(-100.0, value + abs(value) * (multiplier - 1) if level else value))
            # Back to the saved percentage, as shown (three decimals), is back
            # to the saved rate exactly - undo sends the shown value.
            _r, start, data = self._row(EFFECT_TABLE, effect)
            saved = read_field(bytes(self.original_plain[start:start + len(data)]), spec, '<')
            rate = saved if round((1 - saved) * 100, 3) == round(absorbed, 3) else round(1 - absorbed / 100, 6)
            self._write(EFFECT_TABLE, effect, cut, rate)
        return self.read_row(table, row_id)

    def edit(self, table, row_id, key, value, only=None):
        # No parameter table has these keys (audited across TABLES), so they
        # unambiguously name the item's in-game description texts.
        if key in ('description', 'longDescription'):
            self._row(table, row_id)
            if self.texts is None or not self.texts.describable(table):
                raise FormatError('These records have no in-game description to change.')
            self.texts.set_description(table, row_id, value, long=key == 'longDescription')
            return self.read_row(table, row_id, only=only)
        if table == 'MenuText':
            if key != 'label':
                raise FormatError('This field is protected')
            if self.menu_texts is None:
                raise FormatError('The menu text archive is missing. Menu labels cannot be edited.')
            from .texts import MENU_LABEL_IDS
            if row_id not in MENU_LABEL_IDS:
                raise FormatError('Unknown menu label')
            self.menu_texts.set_label(MENU_LABEL_IDS[row_id], value)
            return self.read_row(table, row_id, only=only)
        if table in ('EquipParamProtector', 'NpcParam') and isinstance(key, str) and key.startswith('absorption:'):
            if table == 'NpcParam' and not self.is_monster(row_id):
                raise FormatError('This record is not a reviewed standard monster')
            self._row(table, row_id)
            return self._edit_absorption(row_id, key.split(':', 1)[1], value, table)
        if table == 'NpcParam' and not self.is_monster(row_id):
            raise FormatError('This record is not a reviewed standard monster')
        self._write(table, row_id, key, value)
        return self.read_row(table, row_id, only=only)

    def _write(self, table, row_id, key, value):
        """Validate and store one field. The caller reads the record back."""
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
        links_effect = EFFECT_TABLE in self.params and key in set(reference_keys(self, table, row_id))
        if links_effect and str(int(value)) not in self.effect_references().choices:
            raise FormatError('Choose an existing effect or None')
        added = (table, row_id) in self._added_rows
        original = None if added else self.original_plain[start:start + len(data)]
        # A value that reads the same as the saved one IS the saved one. The
        # editor shows a float to seven digits and undo sends back what it
        # showed, so without this an undone edit stayed a pending change
        # (Lexer: undo all the way back and "there are still 7 changes").
        # A row this session added has no saved value to match.
        if not added and field.dtype in ('f32', 'f64', 'angle32') and isinstance(value, (int, float)):
            saved = read_field(original, field, '<')
            if isinstance(saved, float) and math.isfinite(saved) and _shown(float(value), field) == _shown(saved, field):
                value = saved
        replacement = write_field(data, field, value, '<')
        # The effect index only changes when a link, or what decides whether a
        # field is a link, does; rebuilding it on every edit froze the editor.
        if links_effect or key in reference_switches(self, table):
            self._effects = None
        self.plain[start:start + len(data)] = replacement
        dirty_key = (table, row_id, key)
        if not added and read_field(replacement, field, '<') == read_field(original, field, '<'):
            self.dirty.discard(dirty_key)
        else:
            self.dirty.add(dirty_key)
            self._edited_at[dirty_key] = len(self._edited_at) + 1

    def _repack_table(self, table, member_bytes):
        """Carry rebuilt member bytes: relaid binder, reparsed rows, cold caches."""
        items = {name: bytes(self.plain[entry.offset:entry.offset + entry.size])
                 for name, entry in self.members.items()}
        items[table + '.param'] = bytes(member_bytes)
        self.plain = bytearray(pack(bytes(self.original_plain), items))
        self.members = members(self.plain)
        member = self.members[table + '.param']
        param = ParamView(bytes(self.plain[member.offset:member.offset + member.size]))
        if not param.rows or len({row.row_id for row in param.rows}) != len(param.rows):
            raise FormatError(f'Empty or duplicate {table} row IDs')
        self.params[table] = param
        self._rows_by_id[table] = {row.row_id: row for row in param.rows}
        self._effects = None
        self.__dict__.pop('_attack_references', None)
        self.__dict__.get('_spans_cache', {}).pop(table, None)

    def _current_param(self, table):
        if table not in TABLES or table not in self.params:
            raise FormatError(f'{table}.param is missing. Open a complete Remastered parameter archive.')
        member = self.members[table + '.param']
        return ParamView(bytes(self.plain[member.offset:member.offset + member.size]))

    def add_row(self, table, source_id, new_id=None):
        """Duplicate a row under a fresh ID, appended last. Returns the record."""
        if type(source_id) is not int or isinstance(source_id, bool):
            raise FormatError('Invalid item identity')
        view = self._current_param(table)
        try:
            source = view.row(source_id)
        except DS3FormatError:
            raise FormatError(f'Expected one row ID {source_id}; found 0') from None
        if table == 'NpcParam' and not self.is_monster(source_id):
            raise FormatError('This record is not a reviewed standard monster')
        if new_id is None:
            new_id = max(row.row_id for row in view.rows) + 1
        if type(new_id) is not int or isinstance(new_id, bool) or not -(2 ** 31) <= new_id < 2 ** 31:
            raise FormatError('A row ID is a whole number from -2147483648 to 2147483647')
        if any(row.row_id == new_id for row in view.rows):
            raise FormatError('That row ID is already taken')
        taken = {row.name for row in view.rows if row.name}
        reference = self.schemas[table].get('names', {}).get(source_id)
        if table == 'NpcParam':
            # The duplicate stays openable as a monster only under a family
            # stem; the source gate guarantees one of these is a family.
            stem = next((candidate for candidate in (base_stem(source.name), reference)
                         if candidate in MONSTER_FAMILIES),
                        reference or base_stem(source.name) or f'Row {source_id}')
        else:
            stem = base_stem(source.name) or reference or f'Row {source_id}'
        name, suffix = f'{stem} ({new_id})', 2
        while name in taken:
            name, suffix = f'{stem} ({new_id}) {suffix}', suffix + 1
        try:
            name.encode('shift_jis')
        except UnicodeEncodeError:
            name = f'Row {new_id}'
        try:
            rebuilt = view.copy_row(source_id, new_id, name, TABLES[table][0])
        except DS3FormatError as error:
            raise FormatError(str(error)) from None
        self._repack_table(table, rebuilt)
        self._added_rows.add((table, new_id))
        fields = self.schemas[table]['fields']
        key = next((item['spec'].key for item in fields if item['editable']), fields[0]['spec'].key)
        dirty_key = (table, new_id, key)
        self.dirty.add(dirty_key)
        self._edited_at[dirty_key] = len(self._edited_at) + 1
        return self.read_row(table, new_id)

    def remove_row(self, table, row_id):
        """Drop a row's directory entry and payload. Its name stays orphaned."""
        if type(row_id) is not int or isinstance(row_id, bool):
            raise FormatError('Invalid item identity')
        view = self._current_param(table)
        if len(view.rows) <= 1:
            raise FormatError('A table keeps at least one row')
        try:
            view.row(row_id)
        except DS3FormatError:
            raise FormatError(f'Expected one row ID {row_id}; found 0') from None
        name = self.display_name(table, row_id)
        try:
            rebuilt = view.delete_row(row_id, TABLES[table][0])
        except DS3FormatError as error:
            raise FormatError(str(error)) from None
        self._repack_table(table, rebuilt)
        self._added_rows.discard((table, row_id))
        for entry in [entry for entry in self.dirty if entry[:2] == (table, row_id)]:
            self.dirty.discard(entry)
            self._edited_at.pop(entry, None)
        self._removed_rows.append({'table': table, 'id': row_id, 'name': name})
        return {'table': table, 'id': row_id, 'name': name}

    def export(self):
        if self.plain == self.original_plain: return self.original
        return deflate(self.original, self.plain)
