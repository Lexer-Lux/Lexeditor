"""Remastered map placements (MSB1), edited in place with byte preservation.

Layout facts: Apache-2.0 SoulsTemplates MSB/MSB1 templates (MSB1.bt,
Model.bt, Part.bt) by Meowmaritus and TKGP at commit
f1d114a3668e3c97a1ace82411158df6b3bc50a4 (see credits.md). No template
code is redistributed. Verified against all 35 installed map files:
param order, names and versions, part and model type sets, and enemy
NPC links (2495 of 2532 placements resolve to NpcParam rows).
Positions are metres and rotations are degrees, from measured value
ranges across the real maps.
"""
import math
import struct
from pathlib import Path

from .formats import FormatError

MAP_DIR = Path('map/MapStudio')
PARAM_NAMES = ('MODEL_PARAM_ST', 'EVENT_PARAM_ST', 'POINT_PARAM_ST', 'PARTS_PARAM_ST')
PART_SIZE = 0x64
MODEL_SIZE = 0x20
ENTITY_SIZE = 0x18
ENEMY_READ = 20
ENEMY_TYPES = frozenset({2, 10})
PLAYER_TYPE = 4
OBJECT_TYPES = frozenset({1, 9})
PLACEMENT_TYPES = ENEMY_TYPES | OBJECT_TYPES | frozenset({PLAYER_TYPE})
KNOWN_PART_TYPES = frozenset({0, 1, 2, 4, 5, 8, 9, 10, 11})
KNOWN_MODEL_TYPES = frozenset({0, 1, 2, 4, 5, 6})
TYPE_LABELS = {2: 'Enemy', 10: 'Dummy enemy', 4: 'Player', 1: 'Object', 9: 'Object'}
# Type-data blob sizes from the SoulsTemplates Part.bt layout: enemy
# carries think/NPC/talk IDs plus patrol and animation fields (0x40),
# object carries collision and animation fields (0x18), player is four
# zero ints (0x10). Verified by reading every installed map file.
TYPE_DATA_SIZES = {2: 0x40, 10: 0x40, 1: 0x18, 9: 0x18, 4: 0x10}
MAX_FILE = 8 * 1024 * 1024


class MsbError(FormatError):
    """A map file Lexeditor cannot safely read."""


PLACEMENT_FIELDS = {
    'posX': ('Position X', 'Position', 'Position along the X axis, in metres.'),
    'posY': ('Position Y', 'Position', 'Position along the Y axis, in metres.'),
    'posZ': ('Position Z', 'Position', 'Position along the Z axis, in metres.'),
    'rotX': ('Rotation X', 'Rotation', 'Rotation around the X axis, in degrees.'),
    'rotY': ('Rotation Y', 'Rotation', 'Rotation around the Y axis, in degrees.'),
    'rotZ': ('Rotation Z', 'Rotation', 'Rotation around the Z axis, in degrees.'),
    'scaleX': ('Scale X', 'Scale', 'Scale along the X axis, as a multiplier. 1 is full size.'),
    'scaleY': ('Scale Y', 'Scale', 'Scale along the Y axis, as a multiplier. 1 is full size.'),
    'scaleZ': ('Scale Z', 'Scale', 'Scale along the Z axis, as a multiplier. 1 is full size.'),
    'npcId': ('Enemy', 'Placement', "Which enemy's stats and AI this placement uses. The model stays the same."),
}
FLOAT_FIELDS = {key: offset for key, offset in
                (('posX', 0x14), ('posY', 0x18), ('posZ', 0x1c),
                 ('rotX', 0x20), ('rotY', 0x24), ('rotZ', 0x28),
                 ('scaleX', 0x2c), ('scaleY', 0x30), ('scaleZ', 0x34))}


def _cstr(data, offset, what):
    """A stored string and the bytes it occupies, terminator included."""
    if not 0 <= offset < len(data):
        raise MsbError(f'{what} offset is invalid')
    end = data.find(b'\0', offset)
    if end < 0:
        raise MsbError(f'{what} is not terminated')
    try:
        text = bytes(data[offset:end]).decode('shift_jis')
    except UnicodeError as error:
        raise MsbError(f'{what} is not decodable') from error
    return text, offset, end + 1


def _param(data, base, index):
    name = PARAM_NAMES[index]
    if base + 12 > len(data):
        raise MsbError(f'{name} directory is truncated')
    version, name_off, count = struct.unpack_from('<iIi', data, base)
    if version != 0:
        raise MsbError(f'{name} has an unsupported version or byte order')
    found, _, _ = _cstr(data, name_off, f'{name} name')
    if found != name:
        raise MsbError(f'Expected {name}; found {found}')
    if count < 1:
        raise MsbError(f'{name} count is invalid')
    end = base + 16 + 4 * (count - 1)
    if end > len(data):
        raise MsbError(f'{name} directory is truncated')
    offsets = struct.unpack_from('<%di' % (count - 1), data, base + 12) if count > 1 else ()
    nxt = struct.unpack_from('<i', data, base + 12 + 4 * (count - 1))[0]
    if len(set(offsets)) != len(offsets):
        raise MsbError(f'{name} entries are not unique')
    return {'offsets': offsets, 'next': nxt}


def _model(data, off):
    if not 0 <= off <= len(data) - MODEL_SIZE:
        raise MsbError('A map model entry is out of bounds')
    name_off, mtype, mid, sib_off, inst, u14, u18, u1c = struct.unpack_from('<8i', data, off)
    if mtype not in KNOWN_MODEL_TYPES:
        raise MsbError(f'Unsupported map model type {mtype}')
    if (u14, u18, u1c) != (0, 0, 0):
        raise MsbError('A map model entry has unexpected padding')
    if name_off <= 0 or sib_off <= 0:
        raise MsbError('A map model name offset is invalid')
    name, ns, ne = _cstr(data, off + name_off, 'A map model name')
    sib, ss, se = _cstr(data, off + sib_off, 'A map model path')
    return {'id': mid, 'type': mtype, 'name': name, 'path': sib,
            'spans': [(off, off + MODEL_SIZE), (ns, ne), (ss, se)]}


def _check_type_blob(ptype, blob):
    """The template's fixed words hold, so the blob copies whole."""
    if ptype in ENEMY_TYPES:
        zeros = struct.unpack_from('<2i', blob, 0) + struct.unpack_from('<B', blob, 0x15) \
            + struct.unpack_from('<2i', blob, 0x20)
        if zeros != (0, 0, 0, 0, 0):
            raise MsbError('That enemy stores values this version does not understand')
    elif ptype in OBJECT_TYPES:
        zeros = (struct.unpack_from('<i', blob, 0)[0], struct.unpack_from('<h', blob, 0x0A)[0],
                 struct.unpack_from('<i', blob, 0x14)[0])
        rest = (struct.unpack_from('<h', blob, 0x0E)[0], struct.unpack_from('<i', blob, 0x10)[0])
        if zeros != (0, 0, 0) or rest[0] not in (-1, 0) or rest[1] not in (-1, 0):
            raise MsbError('That object stores values this version does not understand')
    elif blob[:16] != bytes(16):
        raise MsbError('That player start stores values this version does not understand')


def _part(data, off):
    if not 0 <= off <= len(data) - PART_SIZE:
        raise MsbError('A map part entry is out of bounds')
    name_off, ptype, pid, model, sib_off = struct.unpack_from('<5i', data, off)
    if ptype not in KNOWN_PART_TYPES:
        raise MsbError(f'Unsupported map part type {ptype}')
    pos = struct.unpack_from('<3f', data, off + 0x14)
    rot = struct.unpack_from('<3f', data, off + 0x20)
    scale = struct.unpack_from('<3f', data, off + 0x2C)
    ent_off, type_off, unk60 = struct.unpack_from('<iii', data, off + 0x58)
    if unk60 != 0:
        raise MsbError('A map part entry has unexpected padding')
    if name_off <= 0 or sib_off <= 0 or ent_off <= 0 or type_off <= 0:
        raise MsbError('A map part offset is invalid')
    name, ns, ne = _cstr(data, off + name_off, 'A map part name')
    sib, ss, se = _cstr(data, off + sib_off, 'A map part path')
    ent = off + ent_off
    if not ent + ENTITY_SIZE <= len(data):
        raise MsbError('A map part entity is out of bounds')
    tabs = off + type_off
    if not tabs < len(data):
        raise MsbError('A map part data offset is invalid')
    part = {'id': pid, 'type': ptype, 'model': model, 'name': name, 'pos': pos, 'rot': rot,
            'scale': scale,
            'base': off, 'type_data': tabs, 'think': None, 'npc': None,
            'spans': [(off, off + PART_SIZE), (ns, ne), (ss, se), (ent, ent + ENTITY_SIZE)]}
    if ptype in ENEMY_TYPES:
        if not tabs + ENEMY_READ <= len(data):
            raise MsbError('An enemy placement is out of bounds')
        z0, z4, think, npc, _talk = struct.unpack_from('<5i', data, tabs)
        if (z0, z4) != (0, 0):
            raise MsbError('An enemy placement has unexpected padding')
        part.update(think=think, npc=npc)
        part['spans'].append((tabs, tabs + ENEMY_READ))
    return part


class MsbDocument:
    """One map file's placements. Edits rewrite fixed-size fields in place;
    everything else, including names and unknown tables, is preserved."""

    def __init__(self, source, map_name=''):
        if len(source) > MAX_FILE:
            raise MsbError('The map file is too large')
        self.original = bytes(source)
        self.plain = bytearray(source)
        self.map_name = map_name
        self.models = []
        self.parts = []
        self._by_id = {}
        self._strings = []
        self.dirty = set()
        # Placements this session added (no original bytes) and removed.
        self.added = set()
        self.removed = []
        params = []
        base = 0
        for index in range(4):
            param = _param(self.plain, base, index)
            params.append(param)
            nxt = param['next']
            if index < 3 and nxt <= base:
                raise MsbError('Map params do not follow each other')
            base = nxt
        if base != 0:
            raise MsbError('The map has an unexpected trailing param')
        for off in params[0]['offsets']:
            model = _model(self.plain, off)
            self.models.append(model)
            self._strings.extend(model['spans'][1:])
        for off in params[3]['offsets']:
            part = _part(self.plain, off)
            if not 0 <= part['model'] < len(self.models):
                raise MsbError('A map part points outside the model list')
            key = (part['type'], part['id'])
            if key in self._by_id:
                raise MsbError('Map part identities are not unique')
            self.parts.append(part)
            self._by_id[key] = part
            self._strings.extend(part['spans'][1:3])

    def placements(self):
        """Enemy, object and player-start parts in file order."""
        result = []
        for part in self.parts:
            if part['type'] not in PLACEMENT_TYPES:
                continue
            entry = {'partId': part['id'], 'type': part['type'],
                     'kind': TYPE_LABELS[part['type']], 'name': part['name'],
                     'model': self.models[part['model']]['name'],
                     'pos': tuple(part['pos']), 'rot': tuple(part['rot']),
                     'scale': tuple(part['scale'])}
            if part['type'] in ENEMY_TYPES:
                entry.update(think=part['think'], npc=part['npc'])
            result.append(entry)
        return result

    def view_parts(self):
        """Every part with its model, for the viewport. Collision and
        navigation geometry is world-baked Havok data, so those parts
        carry counts, never meshes."""
        result = []
        for part in self.parts:
            model = self.models[part['model']]
            if part['type'] in TYPE_LABELS:
                kind = TYPE_LABELS[part['type']]
            elif part['type'] in (5, 11):
                kind = 'Collision'
            elif part['type'] == 8:
                kind = 'Navigation'
            else:
                kind = 'Map piece' if part['type'] == 0 else 'Part'
            result.append({'id': part['id'], 'type': part['type'], 'kind': kind,
                           'name': part['name'], 'model': model['name'],
                           'pos': tuple(part['pos']), 'rot': tuple(part['rot']),
                           'scale': tuple(part['scale'])})
        return result

    @property
    def dirty_count(self):
        return len(self.dirty) + len(self.removed)

    def placement_modified(self, part_key):
        """Whether this session changed the placement: an edited field or an added copy."""
        key = tuple(part_key)
        if key in self.added:
            return True
        return any(entry[0] == key for entry in self.dirty)

    def merge_units(self):
        """Editable spans for mod merging: ((type, id), field, start, size,
        label, part name) per placement field."""
        units = []
        for part in self.parts:
            if part['type'] not in PLACEMENT_TYPES:
                continue
            for field, offset in FLOAT_FIELDS.items():
                units.append(((part['type'], part['id']), field, part['base'] + offset,
                              4, PLACEMENT_FIELDS[field][0], part['name']))
            if part['type'] in ENEMY_TYPES:
                units.append(((part['type'], part['id']), 'npcId', part['type_data'] + 12,
                              4, PLACEMENT_FIELDS['npcId'][0], part['name']))
        return units

    def _write(self, start, size, payload):
        end = start + size
        for low, high in self._strings:
            if start < high and low < end:
                raise MsbError('The edit would overwrite stored text')
        self.plain[start:end] = payload

    def edit(self, part_key, field, value, npc_ids=None):
        """Change one placement field. part_key is the (type, id) identity
        from placements(). npc_ids, when given, is the set of NpcParam
        row IDs a placement may point at."""
        part = self._by_id.get(tuple(part_key) if isinstance(part_key, list) else part_key)
        if part is None or part['type'] not in PLACEMENT_TYPES:
            raise MsbError('Select an enemy, object or player-start placement')
        is_new = (part['type'], part['id']) in self.added
        if field in FLOAT_FIELDS:
            if type(value) not in (int, float) or isinstance(value, bool):
                raise MsbError('Enter a finite number')
            if not math.isfinite(value):
                raise MsbError('Enter a finite number')
            start = part['base'] + FLOAT_FIELDS[field]
            if not is_new:
                saved = struct.unpack_from('<f', self.original, start)[0]
                if math.isfinite(saved) and float(f'{float(value):.7g}') == float(f'{saved:.7g}'):
                    value = saved
            self._write(start, 4, struct.pack('<f', value))
            index = ['posX', 'posY', 'posZ', 'rotX', 'rotY', 'rotZ',
                     'scaleX', 'scaleY', 'scaleZ'].index(field)
            target = list(part['pos']) if index < 3 else list(part['rot']) if index < 6 else list(part['scale'])
            target[index % 3] = struct.unpack_from('<f', self.plain, start)[0]
            if index < 3:
                part['pos'] = tuple(target)
            elif index < 6:
                part['rot'] = tuple(target)
            else:
                part['scale'] = tuple(target)
        elif field == 'npcId':
            if part['type'] not in ENEMY_TYPES:
                raise MsbError('Only enemy placements name an enemy')
            if type(value) is not int or isinstance(value, bool) or not -(2 ** 31) <= value < 2 ** 31:
                raise MsbError('Enter a whole NPC ID')
            if is_new:
                if npc_ids is not None and value not in npc_ids:
                    raise MsbError('Choose an enemy the game knows')
            else:
                original_npc = struct.unpack_from('<i', self.original, part['type_data'] + 12)[0]
                if npc_ids is not None and value not in npc_ids and value != original_npc:
                    raise MsbError('Choose an enemy the game knows')
            self._write(part['type_data'] + 12, 4, struct.pack('<i', value))
            part['npc'] = value
        else:
            raise MsbError('This placement field is protected')
        key = ((part['type'], part['id']), field)
        if not is_new and (self.plain == self.original
                           or self._readback(part, field) == self._original_value(part, field)):
            self.dirty.discard(key)
        else:
            self.dirty.add(key)
        return self.read_placement((part['type'], part['id']))

    def _readback(self, part, field):
        if field in FLOAT_FIELDS:
            return struct.unpack_from('<f', self.plain, part['base'] + FLOAT_FIELDS[field])[0]
        return struct.unpack_from('<i', self.plain, part['type_data'] + 12)[0]

    def _original_value(self, part, field):
        if (part['type'], part['id']) in self.added:
            return None
        if field in FLOAT_FIELDS:
            return struct.unpack_from('<f', self.original, part['base'] + FLOAT_FIELDS[field])[0]
        return struct.unpack_from('<i', self.original, part['type_data'] + 12)[0]

    def read_placement(self, part_key):
        part = self._by_id.get(tuple(part_key) if isinstance(part_key, list) else part_key)
        if part is None or part['type'] not in PLACEMENT_TYPES:
            raise MsbError('Select an enemy, object or player-start placement')
        # Positions and rotations are unbounded floats, and the enemy is
        # bounded by its option list: none of them shows a numeric range.
        fields = []
        for key in ('posX', 'posY', 'posZ', 'rotX', 'rotY', 'rotZ',
                    'scaleX', 'scaleY', 'scaleZ'):
            label, group, description = PLACEMENT_FIELDS[key]
            fields.append({'key': key, 'label': label, 'description': description, 'group': group,
                           'dtype': 'f32', 'value': self._readback(part, key), 'type': 'number',
                           'minimum': None, 'maximum': None,
                           'enum': {}, 'editable': True, 'vanilla': self._original_value(part, key),
                           'sliderMin': None, 'sliderMax': None})
        if part['type'] in ENEMY_TYPES:
            label, group, description = PLACEMENT_FIELDS['npcId']
            fields.append({'key': 'npcId', 'label': label, 'description': description, 'group': group,
                           'dtype': 's32', 'value': part['npc'], 'type': 'number',
                           'minimum': None, 'maximum': None,
                           'enum': {}, 'editable': True, 'vanilla': self._original_value(part, 'npcId'),
                           'sliderMin': None, 'sliderMax': None})
        return {'partId': part['id'], 'type': part['type'], 'kind': TYPE_LABELS[part['type']],
                'name': part['name'], 'model': self.models[part['model']]['name'],
                'think': part['think'], 'fields': fields}

    def _entity_ids(self):
        ids = []
        for item in self.parts:
            ent = item['base'] + struct.unpack_from('<i', self.plain, item['base'] + 0x58)[0]
            ids.append(struct.unpack_from('<i', self.plain, ent)[0])
        return ids

    def _relocate_parts(self, extra=(), drop=()):
        """Rewrite the PARTS directory at the end of the file: the old entry
        offsets minus drops plus extras, then point POINT's next at it. Every
        entry keeps its bytes; only the directory moves."""
        bases, base = [], 0
        for index in range(4):
            bases.append(base)
            base = _param(self.plain, base, index)['next']
        point_base, parts_base = bases[2], bases[3]
        version, name_off, count = struct.unpack_from('<iIi', self.plain, parts_base)
        old = struct.unpack_from('<%di' % (count - 1), self.plain, parts_base + 12) if count > 1 else ()
        kept = [off for off in old if off not in drop] + list(extra)
        if len(set(kept)) != len(kept):
            raise MsbError('Map part entries are not unique')
        site = len(self.plain)
        self.plain += struct.pack('<iIi', version, name_off, len(kept) + 1)
        for off in kept:
            self.plain += struct.pack('<i', off)
        self.plain += struct.pack('<i', 0)
        point_count = struct.unpack_from('<i', self.plain, point_base + 8)[0]
        struct.pack_into('<i', self.plain, point_base + 12 + 4 * (point_count - 1), site)

    def add_placement(self, part_key):
        """Duplicate a placement: fresh identity and name, its own entity,
        appended last. The copy starts where its source stands."""
        part = self._by_id.get(tuple(part_key) if isinstance(part_key, list) else part_key)
        if part is None or part['type'] not in PLACEMENT_TYPES:
            raise MsbError('Select an enemy, object or player-start placement')
        ptype = part['type']
        size = TYPE_DATA_SIZES[ptype]
        tabs = part['type_data']
        if tabs + size > len(self.plain):
            raise MsbError('That placement stores less than its kind needs; it cannot be duplicated')
        blob = bytes(self.plain[tabs:tabs + size])
        _check_type_blob(ptype, blob)
        new_id = max(item['id'] for item in self.parts if item['type'] == ptype) + 1
        if new_id >= 2 ** 31:
            raise MsbError('This map holds no free identity for that kind of placement')
        taken = {item['name'] for item in self.parts}
        name, suffix = f"{part['name']}_{new_id}", 2
        while name in taken:
            name, suffix = f"{part['name']}_{new_id}_{suffix}", suffix + 1
        try:
            name_bytes = name.encode('shift_jis') + b'\0'
        except UnicodeEncodeError:
            raise MsbError('That name cannot be stored in a map file') from None
        sib = bytes(self.plain[part['spans'][2][0]:part['spans'][2][1]])
        entity = bytearray(self.plain[part['spans'][3][0]:part['spans'][3][1]])
        # An entity of -1 means none; a real one must not be shared, or one
        # script would drive both placements.
        if struct.unpack_from('<i', entity, 0)[0] != -1:
            fresh = max(self._entity_ids()) + 1
            if fresh >= 2 ** 31:
                raise MsbError('This map holds no free entity for that placement')
            struct.pack_into('<i', entity, 0, fresh)
        base = len(self.plain)
        name_at = base + PART_SIZE
        sib_at = name_at + len(name_bytes)
        ent_at = sib_at + len(sib)
        tabs_at = ent_at + ENTITY_SIZE
        entry = bytearray(self.plain[part['base']:part['base'] + PART_SIZE])
        struct.pack_into('<i', entry, 0, PART_SIZE)
        struct.pack_into('<i', entry, 8, new_id)
        struct.pack_into('<i', entry, 16, sib_at - base)
        struct.pack_into('<i', entry, 0x58, ent_at - base)
        struct.pack_into('<i', entry, 0x5C, tabs_at - base)
        self.plain += entry + name_bytes + sib + entity + blob
        self._relocate_parts(extra=[base])
        new = {'id': new_id, 'type': ptype, 'model': part['model'], 'name': name,
               'pos': part['pos'], 'rot': part['rot'], 'scale': part['scale'],
               'base': base, 'type_data': tabs_at,
               'think': part['think'], 'npc': part['npc'],
               'spans': [(base, base + PART_SIZE), (name_at, name_at + len(name_bytes)),
                         (sib_at, sib_at + len(sib)), (ent_at, ent_at + ENTITY_SIZE)]}
        if ptype in ENEMY_TYPES:
            new['spans'].append((tabs_at, tabs_at + ENEMY_READ))
        self.parts.append(new)
        self._by_id[(ptype, new_id)] = new
        self._strings.extend(new['spans'][1:3])
        self.added.add((ptype, new_id))
        for field in ('posX', 'posY', 'posZ'):
            self.dirty.add(((ptype, new_id), field))
        return self.read_placement((ptype, new_id))

    def create_placement(self, model_name, pos, rot, npc=None):
        """A new placement copied from the map's own bytes: the first
        enemy or object placement of the named model is the template, so
        sibling paths, entities and type data stay model-correct. The
        copy takes the given transform, a fresh identity and a fresh
        entity; a pasted enemy also takes the copied enemy identity."""
        index = next((num for num, model in enumerate(self.models)
                      if model['name'] == model_name), None)
        if index is None:
            raise MsbError('That model is not in this map')
        try:
            pos, rot = list(pos), list(rot)
        except TypeError:
            raise MsbError('A placement needs a position and a rotation') from None
        if len(pos) != 3 or len(rot) != 3:
            raise MsbError('A placement needs a position and a rotation')
        template = next((part for part in self.parts
                         if part['model'] == index and part['type'] in PLACEMENT_TYPES
                         and part['type'] != PLAYER_TYPE), None)
        if template is None:
            raise MsbError('That model has no enemy or object placement in this map to copy from')
        row = self.add_placement((template['type'], template['id']))
        key = (row['type'], row['partId'])
        for field, value in zip(('posX', 'posY', 'posZ', 'rotX', 'rotY', 'rotZ'), pos + rot):
            self.edit(key, field, value)
        if npc is not None and row['type'] in ENEMY_TYPES:
            self.edit(key, 'npcId', npc)
        return self.read_placement(key)

    def remove_placement(self, part_key):
        """Drop a placement from the directory. Its bytes stay orphaned."""
        key = tuple(part_key) if isinstance(part_key, list) else part_key
        part = self._by_id.get(key)
        if part is None or part['type'] not in PLACEMENT_TYPES:
            raise MsbError('Select an enemy, object or player-start placement')
        if part['type'] == PLAYER_TYPE:
            raise MsbError('The player start cannot be removed')
        self._relocate_parts(drop=[part['base']])
        del self._by_id[key]
        self.parts.remove(part)
        self.added.discard(key)
        self.dirty = {entry for entry in self.dirty if entry[0] != key}
        self.removed.append({'type': part['type'], 'id': part['id'], 'name': part['name'],
                             'kind': TYPE_LABELS[part['type']]})
        return {'type': part['type'], 'id': part['id'], 'name': part['name']}

    def export(self):
        return bytes(self.plain)
