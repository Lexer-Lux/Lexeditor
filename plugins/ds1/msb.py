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
PLACEMENT_TYPES = frozenset({0, 1, 2, 4, 5, 8, 9, 10, 11})
KNOWN_PART_TYPES = frozenset({0, 1, 2, 4, 5, 8, 9, 10, 11})
KNOWN_MODEL_TYPES = frozenset({0, 1, 2, 4, 5, 6})
TYPE_LABELS = {0: 'Map piece', 2: 'Enemy', 10: 'Dummy enemy', 4: 'Player',
               1: 'Object', 9: 'Object', 5: 'Collision', 8: 'Navigation', 11: 'Connect collision'}
# Type-data blob sizes from the SoulsTemplates Part.bt layout: enemy
# carries think/NPC/talk IDs plus patrol and animation fields (0x40),
# object carries collision and animation fields (0x18), player is four
# zero ints (0x10). Verified by reading every installed map file.
TYPE_DATA_SIZES = {0: 8, 2: 0x40, 10: 0x40, 1: 0x18, 9: 0x18,
                   4: 0x10, 5: 0x50, 8: 0x20, 11: 0x10}
# MSB1 collision behavior, independently of the surface's material.
HIT_FILTERS = {str(i): label for i, label in enumerate((
    'Solid (no foot IK)', 'Solid 1', 'Solid 2', 'Solid 3', 'Solid 4', 'Solid 5',
    'Solid 6', 'Solid 7', 'Normal', 'Water A', 'Unknown 10', 'NPCs only A',
    'Unknown 12', 'Death camera', 'Lethal fall', 'Kill plane', 'Water B',
    'Group switch', 'Unknown 18', 'NPCs only B', 'Level exit A', 'Slide',
    'Fall protection', 'Level exit B'))}
EVENT_HEADER = 28
POINT_HEADER = 60
LIGHT_EVENT = 0
# Event kinds from their names across all 35 maps: torches and point
# lights (0), boss music and insects (1), light walls (2), wind (3),
# treasure (4), generators (5), blood writing (6), chest triggers (7),
# respawn points (8), map offsets (9), navmesh banks (10). Kinds 11
# and 12 have no plain reading yet, so they keep their number.
EVENT_TYPE_LABELS = {0: 'Light', 1: 'Sound', 2: 'SFX', 3: 'Wind',
                     4: 'Treasure', 5: 'Generator', 6: 'Message',
                     7: 'ObjAct', 8: 'Spawn point', 9: 'Map offset',
                     10: 'Navmesh'}
MAX_FILE = 8 * 1024 * 1024


MESSAGE_EVENT = 6
MESSAGE_TEXT_BANK = 131072
# Event-chain tail [28, nextPart, nextType, ordinal, aheadOff, bheadOff]
# follows this many data ints. Verified by locating the 28 slot against
# file order for every event in all 17 maps; types 3, 4, 5 and 11+
# carry no chain fields (see codex/ds1/map-messages.md).
CHAIN_PREFIX = {0: 1, 1: 2, 2: 1, 6: 2, 7: 4, 8: 4, 9: 4, 10: 4}
MESSAGE_FIELDS = {
    'text': ('Message', 'Message',
             "Which developer message shows here. The list holds the Text tab's Blood writing "
             'entries; templates need words this message cannot supply.'),
    'point': ('Marker', 'Position',
              'The invisible marker this message sits on. None hides the message.'),
    'flag': ('Flag', 'Message',
             'The game probably shows this message only while this event flag is set. '
             '-1 leaves no flag on it.'),
}


class MsbError(FormatError):
    """A map file Lexeditor cannot safely read."""


PLACEMENT_FIELDS = {
    # The vectors carry no bubble: their help was cleared, so every axis
    # holds no text.
    'posX': ('Position X', 'Position', ''),
    'posY': ('Position Y', 'Position', ''),
    'posZ': ('Position Z', 'Position', ''),
    'rotX': ('Rotation X', 'Rotation', ''),
    'rotY': ('Rotation Y', 'Rotation', ''),
    'rotZ': ('Rotation Z', 'Rotation', ''),
    'scaleX': ('Scale X', 'Scale', ''),
    'scaleY': ('Scale Y', 'Scale', ''),
    'scaleZ': ('Scale Z', 'Scale', ''),
    'npcId': ('Enemy', 'Placement', "Which enemy's stats and AI this placement uses. The model stays the same."),
}
FLOAT_FIELDS = {key: offset for key, offset in
                (('posX', 0x14), ('posY', 0x18), ('posZ', 0x1c),
                 ('rotX', 0x20), ('rotY', 0x24), ('rotZ', 0x28),
                 ('scaleX', 0x2c), ('scaleY', 0x30), ('scaleZ', 0x34))}
LIGHT_POINT_OFFSETS = {'posX': 0x10, 'posY': 0x14, 'posZ': 0x18}
REGION_SHAPES = {0: ('Point', ()), 1: ('Circle', ('radius',)),
                 2: ('Sphere', ('radius',)), 3: ('Cylinder', ('radius', 'height')),
                 4: ('Rectangle', ('width', 'depth')), 5: ('Box', ('width', 'depth', 'height'))}
LIGHT_FIELDS = {
    'posX': ('Position X', 'Position', ''),
    'posY': ('Position Y', 'Position', ''),
    'posZ': ('Position Z', 'Position', ''),
    'preset': ('Light look', 'Light',
               "Which of the game's built-in light looks this light wears. "
               'Lights that look alike share a number; torches change it by area.'),
}


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
    elif ptype == PLAYER_TYPE and blob[:16] != bytes(16):
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


def _point(data, off):
    if not 0 <= off <= len(data) - POINT_HEADER:
        raise MsbError('A map point entry is out of bounds')
    words = struct.unpack_from('<15i', data, off)
    if words[0] != POINT_HEADER:
        raise MsbError('A map point entry has an unexpected shape')
    if words[1] != 0 or words[2] < 0:
        raise MsbError('A map point entry has an unsupported kind')
    pos = struct.unpack_from('<3f', data, off + 0x10)
    name, ns, ne = _cstr(data, off + POINT_HEADER, 'A map point name')
    shape = words[3]
    if shape not in REGION_SHAPES:
        raise MsbError('A region has an unsupported shape')
    dimensions = REGION_SHAPES[shape][1]
    shape_at, entity_at = off + words[12], off + words[13]
    if not 0 <= shape_at <= len(data) - 4 * len(dimensions) or not 0 <= entity_at <= len(data)-4:
        raise MsbError('A region has invalid shape or entity data')
    return {'index': words[2], 'type': words[1], 'name': name,
            'pos': pos, 'rot': struct.unpack_from('<3f', data, off + 28),
            'shape': shape, 'dimensions': dict(zip(dimensions, struct.unpack_from('<%df' % len(dimensions), data, shape_at))),
            'shape_at': shape_at, 'entity_at': entity_at,
            'entityId': struct.unpack_from('<i', data, entity_at)[0],
            'base': off, 'spans': [(ns, ne)]}


def _event(data, off, nparts, npoints):
    if not 0 <= off <= len(data) - EVENT_HEADER:
        raise MsbError('A map event entry is out of bounds')
    name_off, part, etype, seq, ahead, bhead, zero = struct.unpack_from('<7i', data, off)
    if name_off != EVENT_HEADER or zero != 0 or bhead - ahead != 16:
        raise MsbError('A map event entry has an unexpected shape')
    name, ns, ne = _cstr(data, off + EVENT_HEADER, 'A map event name')
    if not off + ahead + 16 <= len(data) or not off + bhead + 4 <= len(data):
        raise MsbError('A map event entry is out of bounds')
    area, point, flag, last = struct.unpack_from('<4i', data, off + ahead)
    event = {'part': part, 'type': etype, 'seq': seq, 'name': name,
             'base': off, 'ahead': off + ahead, 'bhead': off + bhead,
             'area': area, 'point': point, 'flag': flag,
             'spans': [(off, off + EVENT_HEADER), (ns, ne)]}
    if etype == LIGHT_EVENT:
        if not -1 <= area < nparts:
            raise MsbError('A light points outside the part list')
        if not 0 <= point < npoints or last != 0:
            raise MsbError('A light points outside the point list')
        event['preset'] = struct.unpack_from('<i', data, off + bhead)[0]
    return event


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
        self.points = []
        for off in params[2]['offsets']:
            point = _point(self.plain, off)
            self.points.append(point)
            self._strings.extend(point['spans'])
        if len({point['index'] for point in self.points}) != len(self.points):
            raise MsbError('Map region identities are not unique')
        self.events = []
        seen_events = set()
        for off in params[1]['offsets']:
            event = _event(self.plain, off, len(self.parts), len(self.points))
            key = (event['type'], event['seq'])
            if key in seen_events:
                raise MsbError('Map event identities are not unique')
            seen_events.add(key)
            self.events.append(event)
            self._strings.extend(event['spans'])
        self._lights = {(0, event['seq']): event for event in self.events
                        if event['type'] == LIGHT_EVENT}
        self._messages = {(MESSAGE_EVENT, event['seq']): event for event in self.events
                          if event['type'] == MESSAGE_EVENT}

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
            if part['type'] == 5:
                entry['hitFilter'] = self.plain[part['type_data']]
            result.append(entry)
        result.extend({'partId': point['index'], 'type': 'region', 'kind': 'Region',
                       'name': point['name'], 'model': '', 'pos': tuple(point['pos']),
                       'rot': tuple(point['rot']), 'scale': (1, 1, 1)} for point in self.points)
        from . import msb_events
        result.extend(msb_events.placements(self))
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
            if part['type'] == 5:
                result[-1]['hitFilter'] = self.plain[part['type_data']]
        result.extend({'id': point['index'], 'type': 'region', 'kind': 'Region',
                       'name': point['name'], 'model': '', 'pos': tuple(point['pos']),
                       'rot': tuple(point['rot']), 'scale': (1, 1, 1),
                       'shape': point['shape'], 'dimensions': dict(point['dimensions'])} for point in self.points)
        return result

    def lights(self):
        """Every light event with its point position. A light is a
        type-0 event: its name, two part links, a shared point that
        carries the position in metres, and one preset word that
        picks the game's built-in look. Effects often share the
        point (a torch flame stands where its light shines)."""
        users = {}
        for event in self.events:
            users.setdefault(event['point'], []).append(event)
        result = []
        for (etype, seq), event in sorted(self._lights.items()):
            point = self.points[event['point']]
            sharers = [{'type': other['type'],
                        'kind': EVENT_TYPE_LABELS.get(other['type'],
                                                      f"Event {other['type']}"),
                        'name': other['name']}
                       for other in users.get(event['point'], [])
                       if other is not event]
            result.append({'key': f'light:{seq}', 'type': etype, 'seq': seq,
                           'name': event['name'], 'pos': tuple(point['pos']),
                           'point': event['point'], 'preset': event['preset'],
                           'flag': event['flag'],
                           'part': self.parts[event['area']]['name'] if event['area'] >= 0 else None,
                           'areaPart': self.parts[event['area']]['name'] if event['area'] >= 0 else None,
                           'sharers': sharers})
        return result

    def messages(self):
        """Developer soapstone messages in file order."""
        return [self._message_entry(event)
                for (_etype, _seq), event in sorted(self._messages.items())]

    def _message_entry(self, event):
        point = event['point']
        if 0 <= point < len(self.points):
            pos = tuple(self.points[point]['pos'])
            point_name = self.points[point]['name']
        else:
            pos, point_name = None, None
        sharers = [other['name'] for other in self.events
                   if other is not event and other['point'] == point and point >= 0]
        stored = struct.unpack_from('<i', self.plain, event['bhead'])[0]
        part_name = (self.parts[event['part']]['name']
                     if 0 <= event['part'] < len(self.parts) else None)
        area = event['area']
        area_name = (self.parts[area]['name']
                     if 0 <= area < len(self.parts) else None)
        return {'key': f"message:{event['seq']}", 'type': event['type'], 'seq': event['seq'],
                'name': event['name'], 'pos': pos, 'point': point, 'pointName': point_name,
                'part': event['part'], 'partName': part_name, 'area': area, 'areaName': area_name,
                'flag': event['flag'], 'textId': stored - MESSAGE_TEXT_BANK, 'storedId': stored,
                'sharers': sharers}

    def _message(self, message_key):
        key = tuple(message_key) if isinstance(message_key, list) else message_key
        event = self._messages.get((MESSAGE_EVENT, key[1]) if isinstance(key, tuple) else None)
        if event is None:
            raise MsbError('Select a message on the map')
        return event

    def _message_readback(self, event, field):
        if field in LIGHT_POINT_OFFSETS:
            point = self.points[event['point']]
            return struct.unpack_from(
                '<f', self.plain, point['base'] + LIGHT_POINT_OFFSETS[field])[0]
        if field == 'text':
            return struct.unpack_from('<i', self.plain, event['bhead'])[0] - MESSAGE_TEXT_BANK
        if field == 'flag':
            return struct.unpack_from('<i', self.plain, event['ahead'] + 8)[0]
        return struct.unpack_from('<i', self.plain, event['ahead'] + 4)[0]

    def _message_original(self, event, field):
        if ('message', event['seq']) in self.added:
            return None
        try:
            if field in LIGHT_POINT_OFFSETS:
                point = self.points[event['point']]
                return struct.unpack_from(
                    '<f', self.original, point['base'] + LIGHT_POINT_OFFSETS[field])[0]
            if field == 'text':
                return struct.unpack_from('<i', self.original, event['bhead'])[0] - MESSAGE_TEXT_BANK
            if field == 'flag':
                return struct.unpack_from('<i', self.original, event['ahead'] + 8)[0]
            return struct.unpack_from('<i', self.original, event['ahead'] + 4)[0]
        except (struct.error, IndexError):
            return None

    def read_message(self, message_key):
        event = self._message(message_key)
        entry = self._message_entry(event)
        fields = []
        label, group, description = MESSAGE_FIELDS['text']
        fields.append({'key': 'text', 'label': label, 'description': description, 'group': group,
                       'dtype': 's32', 'value': entry['textId'], 'type': 'number',
                       'minimum': None, 'maximum': None,
                       'enum': {}, 'editable': True,
                       'vanilla': self._message_original(event, 'text')})
        label, group, description = MESSAGE_FIELDS['point']
        fields.append({'key': 'point', 'label': label, 'description': description, 'group': group,
                       'dtype': 's32', 'value': entry['point'], 'type': 'number',
                       'minimum': None, 'maximum': None,
                       'enum': ({str(index): point['name'] for index, point in enumerate(self.points)}
                                | {'-1': 'None (hidden)'}),
                       'editable': True,
                       'vanilla': self._message_original(event, 'point')})
        label, group, description = MESSAGE_FIELDS['flag']
        fields.append({'key': 'flag', 'label': label, 'description': description, 'group': group,
                       'dtype': 's32', 'value': entry['flag'], 'type': 'number',
                       'minimum': None, 'maximum': None,
                       'enum': {}, 'editable': True,
                       'vanilla': self._message_original(event, 'flag')})
        if entry['pos'] is not None:
            sharers = entry['sharers']
            shared = (' ' + ', '.join(sharers) + ' share this spot, so they move too.'
                      if sharers else '')
            for key in ('posX', 'posY', 'posZ'):
                label, group, description = LIGHT_FIELDS[key]
                raw_vanilla = self._message_original(event, key)
                fields.append({'key': key, 'label': label, 'description': description + shared,
                               'group': group, 'dtype': 'f32',
                               'value': round(self._message_readback(event, key), 3), 'type': 'number',
                               'minimum': None, 'maximum': None,
                               'enum': {}, 'editable': True,
                               'vanilla': None if raw_vanilla is None else round(raw_vanilla, 3)})
        return {'key': f"message:{event['seq']}", 'kind': 'Message', 'textId': entry['textId'],
                'name': event['name'], 'point': entry['pointName'], 'part': entry['partName'],
                'areaPart': entry['areaName'], 'fields': fields}

    def message_modified(self, message_key):
        """Whether this session changed the message."""
        key = tuple(message_key)
        if key in self.added:
            return True
        return any(entry[0] == key for entry in self.dirty)

    def edit_message(self, message_key, field, value):
        """Change one message field. message_key is the ('message', seq)
        identity from messages(). The position writes the shared point,
        so markers standing on it move along."""
        event = self._message(message_key)
        if field in LIGHT_POINT_OFFSETS:
            if event['point'] < 0:
                raise MsbError('Give this message a position marker before moving it')
            if type(value) not in (int, float) or isinstance(value, bool):
                raise MsbError('Enter a finite number')
            if not math.isfinite(value):
                raise MsbError('Enter a finite number')
            point = self.points[event['point']]
            start = point['base'] + LIGHT_POINT_OFFSETS[field]
            try:
                saved = struct.unpack_from('<f', self.original, start)[0]
            except struct.error:
                saved = float('nan')
            if math.isfinite(saved) and float(f'{float(value):.7g}') == float(f'{saved:.7g}'):
                value = saved
            self._write(start, 4, struct.pack('<f', value))
            pos = list(point['pos'])
            pos[['posX', 'posY', 'posZ'].index(field)] = struct.unpack_from('<f', self.plain, start)[0]
            point['pos'] = tuple(pos)
        elif field == 'text':
            if type(value) is not int or isinstance(value, bool) or value < 0:
                raise MsbError('Pick one of the offered messages')
            if value > 2 ** 31 - 1 - MESSAGE_TEXT_BANK:
                raise MsbError('That message number cannot be stored in a map file')
            self._write(event['bhead'], 4, struct.pack('<i', value + MESSAGE_TEXT_BANK))
        elif field == 'flag':
            if type(value) is not int or isinstance(value, bool) or not -(2 ** 31) <= value < 2 ** 31:
                raise MsbError('Enter a whole number')
            self._write(event['ahead'] + 8, 4, struct.pack('<i', value))
            event['flag'] = value
        elif field == 'point':
            if type(value) is not int or isinstance(value, bool) or not -1 <= value < len(self.points):
                raise MsbError("Select one of this map's markers or none")
            self._write(event['ahead'] + 4, 4, struct.pack('<i', value))
            event['point'] = value
        else:
            raise MsbError('This message field is protected')
        key = (('message', event['seq']), field)
        if (self.plain == self.original
                or self._message_readback(event, field) == self._message_original(event, field)):
            self.dirty.discard(key)
        else:
            self.dirty.add(key)
        return self.read_message(('message', event['seq']))

    @property
    def dirty_count(self):
        return len(self.dirty) + len(self.removed)

    def placement_modified(self, part_key):
        """Whether this session changed the placement: an edited field or an added copy."""
        key = tuple(part_key)
        if key in self.added:
            return True
        return any(entry[0] == key for entry in self.dirty)

    def light_modified(self, light_key):
        """Whether this session changed the light."""
        key = tuple(light_key)
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
            if part['type'] == 5:
                for field, offset, size, label in (
                        ('hitFilter', 0, 1, 'Collision behavior'),
                        ('startsDisabled', 0x26, 1, 'Starts disabled')):
                    units.append(((part['type'], part['id']), field,
                                  part['type_data'] + offset, size, label, part['name']))
        for (_etype, seq), event in sorted(self._messages.items()):
            name = event['name']
            units.append((('message', seq), 'text', event['bhead'], 4,
                          MESSAGE_FIELDS['text'][0], name))
            units.append((('message', seq), 'point', event['ahead'] + 4, 4,
                          MESSAGE_FIELDS['point'][0], name))
            units.append((('message', seq), 'flag', event['ahead'] + 8, 4,
                          MESSAGE_FIELDS['flag'][0], name))
            if 0 <= event['point'] < len(self.points):
                point = self.points[event['point']]
                for field, offset in LIGHT_POINT_OFFSETS.items():
                    units.append((('message', seq), field, point['base'] + offset, 4,
                                  LIGHT_FIELDS[field][0], name))
        for point in self.points:
            for field, address, dtype, label in self._region_fields(point):
                units.append((('region', point['index']), field, address,
                              struct.calcsize('<' + dtype), label, point['name']))
        from . import msb_events
        for event in self.events:
            if event['type'] in msb_events.SPECS:
                for field, address, dtype, _ref in msb_events.fields(event):
                    units.append(((f"event{event['type']}", event['seq']), field, address,
                                  struct.calcsize('<'+dtype), msb_events.label(field), event['name']))
        # Shared coordinates remain one fact across region/message views.
        return list({(unit[2], unit[3]): unit for unit in units}.values())

    def _region(self, key):
        point = next((point for point in self.points if point['index'] == key[1]), None)
        if point is None:
            raise MsbError('Select a region')
        return point

    def _region_fields(self, point):
        for field, offset in FLOAT_FIELDS.items():
            if field.startswith('scale'):
                continue
            # Region translation starts four bytes before a part's translation.
            yield field, point['base'] + offset - 4, 'f', PLACEMENT_FIELDS[field][0]
        for index, field in enumerate(REGION_SHAPES[point['shape']][1]):
            yield field, point['shape_at'] + 4*index, 'f', field.capitalize()
        yield 'entityId', point['entity_at'], 'i', 'Entity ID'

    def read_region(self, key):
        point = self._region(key)
        fields = [{'key': 'shapeType', 'label': 'Shape', 'description': '', 'group': 'Shape',
                   'dtype': 's32', 'value': point['shape'], 'type': 'enum',
                   'enum': {str(k): v[0] for k, v in REGION_SHAPES.items()}, 'editable': True,
                   'minimum': 0, 'maximum': 5,
                   'vanilla': None if tuple(key) in self.added else struct.unpack_from('<i', self.original, point['base']+12)[0]}]
        for field, address, dtype, label in self._region_fields(point):
            value = struct.unpack_from('<' + dtype, self.plain, address)[0]
            original = None if tuple(key) in self.added or address+4 > len(self.original) else struct.unpack_from('<' + dtype, self.original, address)[0]
            fields.append({'key': field, 'label': label, 'description': '',
                           'group': 'Position' if field.startswith('pos') else 'Rotation' if field.startswith('rot') else 'Shape',
                           'dtype': 'f32' if dtype == 'f' else 's32', 'value': value,
                           'vanilla': original, 'type': 'number', 'enum': {}, 'editable': True,
                           'minimum': 0 if field in point['dimensions'] else None, 'maximum': None})
        return {'partId': point['index'], 'type': 'region', 'kind': 'Region',
                'name': point['name'], 'model': REGION_SHAPES[point['shape']][0], 'think': None,
                'fields': fields}

    def edit_region(self, key, field, value):
        point = self._region(key)
        if field == 'shapeType':
            if type(value) is not int or value not in REGION_SHAPES:
                raise MsbError('Select a region shape')
            if point['shape'] == value:
                return self.read_region(key)
            dimensions = [point['dimensions'].get(name, 1.0) for name in REGION_SHAPES[value][1]]
            shape_at = len(self.plain)
            self.plain += struct.pack('<%df' % len(dimensions), *dimensions)
            struct.pack_into('<i', self.plain, point['base']+12, value)
            struct.pack_into('<i', self.plain, point['base']+48, shape_at-point['base'])
            point.update(_point(self.plain, point['base']))
            self.dirty.add((tuple(key), field))
            self.dirty = {unit for unit in self.dirty if unit[0] != tuple(key)
                          or unit[1] == 'shapeType' or unit[1] in {spec[0] for spec in self._region_fields(point)}}
            return self.read_region(key)
        spec = next((item for item in self._region_fields(point) if item[0] == field), None)
        if spec is None:
            raise MsbError('This region field is protected')
        _, address, dtype, _ = spec
        if dtype == 'f':
            if type(value) not in (int, float) or not math.isfinite(value):
                raise MsbError('Enter a finite number')
            if field in point['dimensions'] and value < 0:
                raise MsbError('Region dimensions cannot be negative')
        elif type(value) is not int or not -(2**31) <= value < 2**31:
            raise MsbError('Enter a whole entity ID')
        try:
            encoded = struct.pack('<' + dtype, value)
        except (OverflowError, struct.error):
            raise MsbError('That value is outside the map format range') from None
        if dtype == 'f' and not math.isfinite(struct.unpack('<f', encoded)[0]):
            raise MsbError('That value is outside the map format range')
        self._write(address, 4, encoded)
        refreshed = _point(self.plain, point['base'])
        point.update(refreshed)
        unit = (tuple(key), field)
        if tuple(key) not in self.added and encoded == self.original[address:address+4]:
            self.dirty.discard(unit)
        else:
            self.dirty.add(unit)
        return self.read_region(key)

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
        if part_key[0] == 'region':
            return self.edit_region(part_key, field, value)
        if str(part_key[0]).startswith('event'):
            from . import msb_events
            return msb_events.edit(self, part_key, field, value)
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
        elif field in ('hitFilter', 'startsDisabled') and part['type'] == 5:
            if field == 'hitFilter':
                if type(value) is not int or str(value) not in HIT_FILTERS:
                    raise MsbError('Select a collision behavior')
                offset = 0
            else:
                if type(value) is not bool:
                    raise MsbError('Starts disabled must be on or off')
                offset = 0x26
            self._write(part['type_data'] + offset, 1, bytes([value]))
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
        if field in ('hitFilter', 'startsDisabled') and part['type'] == 5:
            value = self.plain[part['type_data'] + (0 if field == 'hitFilter' else 0x26)]
            return bool(value) if field == 'startsDisabled' else value
        if field in FLOAT_FIELDS:
            return struct.unpack_from('<f', self.plain, part['base'] + FLOAT_FIELDS[field])[0]
        return struct.unpack_from('<i', self.plain, part['type_data'] + 12)[0]

    def _original_value(self, part, field):
        if (part['type'], part['id']) in self.added:
            return None
        if field in ('hitFilter', 'startsDisabled') and part['type'] == 5:
            value = self.original[part['type_data'] + (0 if field == 'hitFilter' else 0x26)]
            return bool(value) if field == 'startsDisabled' else value
        if field in FLOAT_FIELDS:
            return struct.unpack_from('<f', self.original, part['base'] + FLOAT_FIELDS[field])[0]
        return struct.unpack_from('<i', self.original, part['type_data'] + 12)[0]

    def read_placement(self, part_key):
        if part_key[0] == 'region':
            return self.read_region(part_key)
        if str(part_key[0]).startswith('event'):
            from . import msb_events
            return msb_events.read(self, part_key)
        part = self._by_id.get(tuple(part_key) if isinstance(part_key, list) else part_key)
        if part is None or part['type'] not in PLACEMENT_TYPES:
            raise MsbError('Select an enemy, object or player-start placement')
        # Positions and rotations are unbounded floats, and the enemy is
        # bounded by its option list: none of them shows a numeric range.
        fields = []
        for key in ('posX', 'posY', 'posZ', 'rotX', 'rotY', 'rotZ',
                    'scaleX', 'scaleY', 'scaleZ'):
            label, group, description = PLACEMENT_FIELDS[key]
            # Display precision only: a float32's decimal expansion carries
            # dust past three places (179.99998 for 180 degrees). The stored
            # bytes keep full precision; only the shown value is rounded.
            # Added placements have no vanilla value to round.
            raw_vanilla = self._original_value(part, key)
            fields.append({'key': key, 'label': label, 'description': description, 'group': group,
                           'dtype': 'f32', 'value': round(self._readback(part, key), 3), 'type': 'number',
                           'minimum': None, 'maximum': None,
                           'enum': {}, 'editable': True,
                           'vanilla': None if raw_vanilla is None else round(raw_vanilla, 3)})
        if part['type'] in ENEMY_TYPES:
            label, group, description = PLACEMENT_FIELDS['npcId']
            fields.append({'key': 'npcId', 'label': label, 'description': description, 'group': group,
                           'dtype': 's32', 'value': part['npc'], 'type': 'number',
                           'minimum': None, 'maximum': None,
                           'enum': {}, 'editable': True, 'vanilla': self._original_value(part, 'npcId')})
        if part['type'] == 5:
            for key, label in (('hitFilter', 'Collision behavior'), ('startsDisabled', 'Starts disabled')):
                fields.append({'key': key, 'label': label, 'description': '', 'group': 'Collision',
                               'dtype': 'u8', 'type': 'bool' if key == 'startsDisabled' else 'enum',
                               'value': self._readback(part, key), 'minimum': 0, 'maximum': 23 if key == 'hitFilter' else 1,
                               'enum': HIT_FILTERS if key == 'hitFilter' else {}, 'editable': True,
                               'vanilla': self._original_value(part, key)})
        return {'partId': part['id'], 'type': part['type'], 'kind': TYPE_LABELS[part['type']],
                'name': part['name'], 'model': self.models[part['model']]['name'],
                'think': part['think'], 'fields': fields}

    def _light(self, light_key):
        key = tuple(light_key) if isinstance(light_key, list) else light_key
        event = self._lights.get((0, key[1]) if isinstance(key, tuple) else None)
        if event is None:
            raise MsbError('Select a light on the map')
        return event

    def _light_readback(self, event, field):
        if field in LIGHT_POINT_OFFSETS:
            point = self.points[event['point']]
            return struct.unpack_from(
                '<f', self.plain, point['base'] + LIGHT_POINT_OFFSETS[field])[0]
        return struct.unpack_from('<i', self.plain, event['bhead'])[0]

    def _light_original(self, event, field):
        if ('light', event['seq']) in self.added:
            return None
        if field in LIGHT_POINT_OFFSETS:
            point = self.points[event['point']]
            return struct.unpack_from(
                '<f', self.original, point['base'] + LIGHT_POINT_OFFSETS[field])[0]
        return struct.unpack_from('<i', self.original, event['bhead'])[0]

    def read_light(self, light_key):
        event = self._light(light_key)
        point = self.points[event['point']]
        sharers = [other['name'] for other in self.events
                   if other is not event and other['point'] == event['point']]
        shared = (' ' + ', '.join(sharers) + ' share this spot, so they move too.'
                  if sharers else '')
        fields = []
        for key in ('posX', 'posY', 'posZ'):
            label, group, description = LIGHT_FIELDS[key]
            raw_vanilla = self._light_original(event, key)
            fields.append({'key': key, 'label': label, 'description': description + shared,
                           'group': group, 'dtype': 'f32',
                           'value': round(self._light_readback(event, key), 3), 'type': 'number',
                           'minimum': None, 'maximum': None,
                           'enum': {}, 'editable': True,
                           'vanilla': None if raw_vanilla is None else round(raw_vanilla, 3)})
        label, group, description = LIGHT_FIELDS['preset']
        fields.append({'key': 'preset', 'label': label, 'description': description,
                       'group': group, 'dtype': 's32',
                       'value': self._light_readback(event, 'preset'), 'type': 'number',
                       'minimum': None, 'maximum': None,
                       'enum': {}, 'editable': True,
                       'vanilla': self._light_original(event, 'preset')})
        return {'key': f"light:{event['seq']}", 'kind': 'Light',
                'preset': event['preset'],
                'name': event['name'], 'point': point['name'],
                'part': self.parts[event['area']]['name'] if event['area'] >= 0 else None,
                'areaPart': self.parts[event['area']]['name'] if event['area'] >= 0 else None,
                'fields': fields}

    def edit_light(self, light_key, field, value):
        """Change one light field. light_key is the ('light', seq)
        identity from lights(). The position writes the shared point,
        so effects standing on it move along."""
        event = self._light(light_key)
        if field in LIGHT_POINT_OFFSETS:
            if type(value) not in (int, float) or isinstance(value, bool):
                raise MsbError('Enter a finite number')
            if not math.isfinite(value):
                raise MsbError('Enter a finite number')
            point = self.points[event['point']]
            start = point['base'] + LIGHT_POINT_OFFSETS[field]
            saved = (struct.unpack_from('<f', self.original, start)[0]
                     if start+4 <= len(self.original) else float('nan'))
            if math.isfinite(saved) and float(f'{float(value):.7g}') == float(f'{saved:.7g}'):
                value = saved
            self._write(start, 4, struct.pack('<f', value))
            pos = list(point['pos'])
            pos[['posX', 'posY', 'posZ'].index(field)] = struct.unpack_from('<f', self.plain, start)[0]
            point['pos'] = tuple(pos)
        elif field == 'preset':
            if type(value) is not int or isinstance(value, bool) or not -(2 ** 31) <= value < 2 ** 31:
                raise MsbError('Enter a whole number')
            self._write(event['bhead'], 4, struct.pack('<i', value))
            event['preset'] = value
        else:
            raise MsbError('This light field is protected')
        key = (('light', event['seq']), field)
        if (self.plain == self.original
                or self._light_readback(event, field) == self._light_original(event, field)):
            self.dirty.discard(key)
        else:
            self.dirty.add(key)
        return self.read_light(('light', event['seq']))

    def _entity_ids(self):
        ids = []
        for item in self.parts:
            ent = item['base'] + struct.unpack_from('<i', self.plain, item['base'] + 0x58)[0]
            ids.append(struct.unpack_from('<i', self.plain, ent)[0])
        return ids

    def _relocate_param(self, index, extra=(), drop=(), at=None):
        """Rewrite one parameter directory at the end of the file: the old
        entry offsets minus drops plus extras, then point the previous
        directory's link at it. Directory links must keep climbing through
        the file, so a moved directory drags every directory after it
        along; entries keep their bytes throughout. Callers pass the
        format's directory index (1 for EVENTS, 2 for POINTS, 3 for
        PARTS); at files extras mid-list instead of last."""
        bases, base = [], 0
        for step in range(4):
            bases.append(base)
            base = _param(self.plain, base, step)['next']
        heads = [struct.unpack_from('<iIi', self.plain, bases[step]) for step in range(4)]
        olds = [struct.unpack_from('<%di' % (heads[step][2] - 1), self.plain, bases[step] + 12)
                if heads[step][2] > 1 else ()
                for step in range(4)]
        kept = [off for off in olds[index] if off not in drop]
        kept = kept + list(extra) if at is None else kept[:at] + list(extra) + kept[at:]
        if len(set(kept)) != len(kept):
            raise MsbError('Map entries are not unique')
        entries = [list(olds[step]) for step in range(4)]
        entries[index] = kept
        sites = []
        for step in range(index, 4):
            version, name_off, _count = heads[step]
            sites.append(len(self.plain))
            self.plain += struct.pack('<iIi', version, name_off, len(entries[step]) + 1)
            for off in entries[step]:
                self.plain += struct.pack('<i', off)
            self.plain += struct.pack('<i', 0)
        for pos, step in enumerate(range(index, 4)):
            struct.pack_into('<i', self.plain, sites[pos] + 12 + 4 * len(entries[step]),
                             sites[pos + 1] if pos + 1 < len(sites) else 0)
        if index > 0:
            prev_base = bases[index - 1]
            prev_count = struct.unpack_from('<i', self.plain, prev_base + 8)[0]
            struct.pack_into('<i', self.plain, prev_base + 12 + 4 * (prev_count - 1), sites[0])

    def _shift_dirs(self, at, delta):
        """Slide every live directory offset at or past at by delta. Names
        and every entry-internal pointer are entry-relative; only the
        directory links and entry offsets are absolute."""
        base = 0
        for _ in range(4):
            _version, _name_off, count = struct.unpack_from('<iIi', self.plain, base)
            if _name_off >= at:
                struct.pack_into('<i', self.plain, base + 4, _name_off + delta)
            for slot in range(count - 1):
                off = struct.unpack_from('<i', self.plain, base + 12 + 4 * slot)[0]
                if off >= at:
                    struct.pack_into('<i', self.plain, base + 12 + 4 * slot, off + delta)
            link_at = base + 12 + 4 * (count - 1)
            nxt = struct.unpack_from('<i', self.plain, link_at)[0]
            if nxt > 0 and nxt >= at:
                struct.pack_into('<i', self.plain, link_at, nxt + delta)
                nxt += delta
            if nxt <= 0:
                break
            base = nxt

    def _shift_caches(self, at, delta):
        """Slide every cached absolute span at or past at by delta."""
        for part in self.parts:
            if part['base'] >= at:
                part['base'] += delta
            if part['type_data'] >= at:
                part['type_data'] += delta
            part['spans'] = [(low + delta, high + delta) if low >= at else (low, high)
                             for low, high in part['spans']]
        for point in self.points:
            if point['base'] >= at:
                point['base'] += delta
            for field in ('shape_at', 'entity_at'):
                if field in point and point[field] >= at:
                    point[field] += delta
            point['spans'] = [(low + delta, high + delta) if low >= at else (low, high)
                              for low, high in point['spans']]
        for event in self.events:
            if event['base'] >= at:
                event['base'] += delta
            if event['ahead'] >= at:
                event['ahead'] += delta
            if event['bhead'] >= at:
                event['bhead'] += delta
            event['spans'] = [(low + delta, high + delta) if low >= at else (low, high)
                              for low, high in event['spans']]
        for model in self.models:
            model['spans'] = [(low + delta, high + delta) if low >= at else (low, high)
                              for low, high in model['spans']]
        self._strings = [(low + delta, high + delta) if low >= at else (low, high)
                         for low, high in self._strings]

    def _splice(self, at, blob):
        """Insert blob at at, sliding later bytes, caches, directories and
        the vanilla shadow along. The shadow takes zeros: added bytes have
        no original to compare, and added entries never read it."""
        self.plain[at:at] = blob
        self.original = self.original[:at] + bytes(len(blob)) + self.original[at:]
        self._shift_caches(at, len(blob))
        self._shift_dirs(at, len(blob))

    def _excise(self, start, end):
        """Cut [start, end) out, sliding later bytes, caches, directories
        and the vanilla shadow down. The victim's bytes leave both sides,
        so survivors keep their originals beside them."""
        del self.plain[start:end]
        self.original = self.original[:start] + self.original[end:]
        self._shift_caches(end, start - end)
        self._shift_dirs(end, start - end)

    def _relocate_parts(self, extra=(), drop=()):
        self._relocate_param(3, extra=extra, drop=drop)


    @staticmethod
    def _chain_slots(etype, bhead):
        """(nextPart, nextType) offsets for an event, or None when the type
        carries no chain fields. Indexed by CHAIN_PREFIX, not text-bearing."""
        prefix = CHAIN_PREFIX.get(etype)
        if prefix is None:
            return None
        return bhead + 4 * (prefix + 1), bhead + 4 * (prefix + 2)

    def _message_insert_at(self):
        """Where a new message event files: before the first event above
        type 6. Messages sort among their own kind in the engine's
        directory, and without a follower there is nowhere to file one."""
        for index, event in enumerate(self.events):
            if event['type'] > MESSAGE_EVENT:
                return index
        raise MsbError('This map files nothing after messages, so it cannot take one')

    def _message_link(self, event, next_part, next_type):
        """Retired no-op: each chain tail overlaps its follower's header,
        so filing the bytes in order links them; writes would clobber."""
        return  # Retired: tails overlap follower headers, so stitching writes nothing.
        if slots is None:
            return
        struct.pack_into('<i', self.plain, slots[0], next_part)
        struct.pack_into('<i', self.plain, slots[1], next_type)

    def _message_renumber(self):
        """Retired no-op: ordinals alias follower seqs; filing order numbers them."""
        return  # Retired: ordinals alias follower seqs, so renumbering writes nothing.
        slot = 4 * (CHAIN_PREFIX[MESSAGE_EVENT] + 3)
        for pos, event in enumerate(run):
            struct.pack_into('<i', self.plain, event['bhead'] + slot,
                             0 if pos == len(run) - 1 else pos + 1)

    def _add_point(self, pos, hint):
        """Append a point entry at the end of the file and file it with the
        rest. Its shape follows the nearest existing point: unknown header
        values come from there, repointed at the new entry's own name."""
        taken = {point['name'] for point in self.points}
        name, suffix = hint, 2
        while name in taken:
            name, suffix = f"{hint}_{suffix}", suffix + 1
        try:
            name_bytes = name.encode('shift_jis') + b'\0'
        except UnicodeEncodeError:
            raise MsbError('That name cannot be stored in a map file') from None
        padded = name_bytes + bytes(-len(name_bytes) % 4)
        ahead = 60 + len(padded)
        if self.points:
            template = min(self.points,
                           key=lambda item: sum((one - two) ** 2
                                                for one, two in zip(item['pos'], pos)))
            t_padded = len(template['name'].encode('shift_jis')) + 1
            t_padded += -t_padded % 4
            t_ahead = 60 + t_padded
            header = bytearray(self.plain[template['base']:template['base'] + 60])
            struct.pack_into('<i', header, 8, max(point['index'] for point in self.points)+1)
            struct.pack_into('<3f', header, 16, *pos)
            ints = list(struct.unpack_from('<8i', header, 28))
            rebase = {t_ahead: ahead,
                      t_ahead + 4: ahead + 4,
                      t_ahead + 8: ahead + 8}
            header[28:60] = struct.pack('<8i', *[rebase.get(value, value) for value in ints])
            tail = self.plain[template['base'] + 60 + t_padded:template['base'] + 60 + t_padded + 12]
        else:
            header = bytearray(60)
            struct.pack_into('<i', header, 0, 60)
            struct.pack_into('<3f', header, 16, *pos)
            header[28:60] = struct.pack('<8i', 0, 0, 0, ahead, ahead + 4, 0, ahead + 8, 0)
            tail = bytes(12)
        base = len(self.plain)
        self.plain += bytes(header) + padded + bytes(tail)
        self._relocate_param(2, extra=[base])
        point = _point(self.plain, base)
        self.points.append(point)
        self._strings.append((base + 60, base + 60 + len(name_bytes)))
        return len(self.points) - 1

    def _insert_message_event(self, hint, part, area, point, flag, stored, unknown):
        """Splice one message event's owned bytes ahead of the first
        greater-typed event. Its tail is the follower's header, so no writes stitch it."""
        try:
            hint_bytes = hint.encode('shift_jis')
        except UnicodeEncodeError:
            raise MsbError('That name cannot be stored in a map file') from None
        del hint_bytes
        at = self._message_insert_at()
        seqs = [seq for (_etype, seq) in self._messages]
        new_seq = max(seqs) + 1 if seqs else 0
        if new_seq >= 2 ** 31:
            raise MsbError('This map holds no free message identity')
        taken = {event['name'] for event in self.events}
        name, suffix = f"{hint}_{new_seq}", 2
        while name in taken:
            name, suffix = f"{hint}_{new_seq}_{suffix}", suffix + 1
        name_bytes = name.encode('shift_jis') + b'\0'
        base = len(self.plain)
        padded = name_bytes + bytes(-len(name_bytes) % 4)
        ahead, bhead = 28 + len(padded), 28 + len(padded) + 16
        base = self.events[at]['base']
        self._splice(base, (struct.pack('<7i', 28, part, MESSAGE_EVENT, new_seq, ahead, bhead, 0)
                       + padded + struct.pack('<4i', area, point, flag, 0)
                       + struct.pack('<2i', stored, unknown)))
        self._relocate_param(1, extra=[base], at=at)
        event = {'part': part, 'type': MESSAGE_EVENT, 'seq': new_seq, 'name': name,
                 'area': area, 'point': point, 'flag': flag,
                 'base': base, 'ahead': base + ahead, 'bhead': base + bhead,
                 'spans': [(base, base + 28), (base + 28, base + 28 + len(name_bytes))]}
        self.events.insert(at, event)
        self._messages[(MESSAGE_EVENT, new_seq)] = event
        self._strings.append((base + 28, base + 28 + len(name_bytes)))
        follower = self.events[at + 1]
        self._message_link(event, follower['part'], follower['type'])
        if at > 0:
            self._message_link(self.events[at - 1], part, MESSAGE_EVENT)
        self._message_renumber()
        return event

    def add_message(self, message_key):
        """Duplicate a message: fresh identity and name, but the same
        marker and anchor, so it stands on its source's spot until it
        takes a marker of its own."""
        source = self._message(message_key)
        stored = struct.unpack_from('<i', self.plain, source['bhead'])[0]
        unknown = struct.unpack_from('<i', self.plain, source['bhead'] + 4)[0]
        event = self._insert_message_event(source['name'], source['part'], source['area'],
                                           source['point'], source['flag'], stored, unknown)
        key = ('message', event['seq'])
        self.added.add(key)
        self.dirty.add((key, 'text'))
        if event['point'] >= 0:
            for field in LIGHT_POINT_OFFSETS:
                self.dirty.add((key, field))
        return self.read_message(key)

    def create_message(self, text_id, pos, name=None):
        """A new message from scratch: a fresh marker under it, anchored
        to the map's first piece, with no flag on it."""
        if type(text_id) is not int or isinstance(text_id, bool) or text_id < 0:
            raise MsbError('Pick one of the offered messages')
        if text_id > 2 ** 31 - 1 - MESSAGE_TEXT_BANK:
            raise MsbError('That message number cannot be stored in a map file')
        try:
            pos = [float(axis) for axis in pos]
        except (TypeError, ValueError):
            raise MsbError('A new message needs somewhere to stand') from None
        if len(pos) != 3 or not all(math.isfinite(axis) for axis in pos):
            raise MsbError('A new message needs somewhere to stand')
        part = next((index for index, item in enumerate(self.parts)
                     if item['type'] in (0, 1)), None)
        if part is None:
            raise MsbError('This map has no map piece or object to hang a message on')
        # Nothing may file after messages: fail here, before the marker lands.
        self._message_insert_at()
        point = self._add_point(pos, 'MessagePoint')
        areas = [item['area'] for item in self.events if item['type'] == MESSAGE_EVENT]
        event = self._insert_message_event('Message' if name is None else str(name), part,
                                           areas[0] if areas else -1, point, -1,
                                           text_id + MESSAGE_TEXT_BANK, 0)
        key = ('message', event['seq'])
        self.added.add(key)
        self.dirty.add((key, 'text'))
        for field in LIGHT_POINT_OFFSETS:
            self.dirty.add((key, field))
        return self.read_message(key)

    def remove_message(self, message_key):
        """Cut a message out of the map; its neighbours re-seat across the gap.
        Its marker stays where it stood; other events may share it."""
        key = tuple(message_key)
        event = self._message(key)
        at = next(index for index, item in enumerate(self.events) if item is event)
        if at + 1 >= len(self.events):
            raise MsbError('That message files last, so lifting it would break the chain')
        follower = self.events[at + 1]
        if at > 0:
            self._message_link(self.events[at - 1], follower['part'], follower['type'])
        self._relocate_param(1, drop=[event['base']])
        self._excise(event['base'], self.events[at + 1]['base'])
        del self.events[at]
        del self._messages[(MESSAGE_EVENT, event['seq'])]
        self._strings = [span for span in self._strings if span not in event['spans']]
        self._message_renumber()
        self.added.discard(key)
        self.removed.append({'type': MESSAGE_EVENT, 'id': event['seq'], 'name': event['name'],
                             'kind': 'Message'})
        self.dirty = {entry for entry in self.dirty if entry[0] != key}
        return {'type': MESSAGE_EVENT, 'id': event['seq'], 'name': event['name']}

    def add_placement(self, part_key):
        """Duplicate a placement: fresh identity and name, its own entity,
        appended last. The copy starts where its source stands."""
        if part_key[0] == 'region':
            return self.add_region(part_key)
        if str(part_key[0]).startswith('event'):
            from . import msb_events
            return msb_events.duplicate(self, part_key)
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
        self._model_counts()
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
        if str(model_name).startswith('@region:'):
            try:
                shape = int(model_name.split(':', 1)[1])
            except ValueError:
                raise MsbError('Select a region shape') from None
            return self.add_region(shape=shape, pos=pos)
        if str(model_name).startswith('@event:'):
            from . import msb_events
            try:
                etype = int(model_name.split(':', 1)[1])
            except ValueError:
                raise MsbError('Select a map event kind') from None
            return msb_events.create(self, etype, pos)
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
        if key[0] == 'region':
            return self.remove_region(key)
        if str(key[0]).startswith('event'):
            from . import msb_events
            return msb_events.remove(self, key)
        part = self._by_id.get(key)
        if part is None or part['type'] not in PLACEMENT_TYPES:
            raise MsbError('Select an enemy, object or player-start placement')
        if part['type'] == PLAYER_TYPE:
            raise MsbError('The player start cannot be removed')
        self._remap_part_references(part)
        self._relocate_parts(drop=[part['base']])
        del self._by_id[key]
        self.parts.remove(part)
        self._model_counts()
        self.added.discard(key)
        self.dirty = {entry for entry in self.dirty if entry[0] != key}
        self.removed.append({'type': part['type'], 'id': part['id'], 'name': part['name'],
                             'kind': TYPE_LABELS[part['type']]})
        return {'type': part['type'], 'id': part['id'], 'name': part['name']}

    def _model_counts(self):
        for index, model in enumerate(self.models):
            count = sum(part['model'] == index for part in self.parts)
            struct.pack_into('<i', self.plain, model['spans'][0][0]+16, count)

    def _remap_part_references(self, removed):
        """Part list indices differ from stable (type,id) identities."""
        gone = self.parts.index(removed)
        if removed['type'] == 5:
            collisions = [part for part in self.parts if part['type'] == 5]
            collision_index = collisions.index(removed)
            if any(struct.unpack_from('<i', self.plain, part['type_data'])[0] == collision_index
                   for part in self.parts if part['type'] == 11):
                raise MsbError('Remove the connected collision that uses this collision first')
        slots = [event['ahead'] for event in self.events]
        for event in self.events:
            if event['type'] in (4, 7):
                slots.append(event['bhead'] + 4)
            elif event['type'] == 5:
                slots.extend(event['bhead'] + 64 + 4*i for i in range(32))
        for part in self.parts:
            if part['type'] in ENEMY_TYPES:
                slots.append(part['type_data'] + 28)
            elif part['type'] in OBJECT_TYPES:
                slots.append(part['type_data'] + 4)
            elif part['type'] == 11 and removed['type'] == 5:
                at = part['type_data']
                value = struct.unpack_from('<i', self.plain, at)[0]
                if value > collision_index:
                    struct.pack_into('<i', self.plain, at, value - 1)
        for at in slots:
            value = struct.unpack_from('<i', self.plain, at)[0]
            if value >= gone:
                struct.pack_into('<i', self.plain, at, -1 if value == gone else value-1)
        for event in self.events:
            event['area'] = struct.unpack_from('<i', self.plain, event['ahead'])[0]

    def add_region(self, key=None, shape=5, pos=(0, 0, 0)):
        if key is not None:
            source = self._region(key)
        else:
            if type(shape) is not int or shape not in REGION_SHAPES:
                raise MsbError('Select a region shape')
            if len(pos) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in pos):
                raise MsbError('A region needs a finite position')
            source = {'name': REGION_SHAPES[shape][0], 'shape': shape, 'pos': pos,
                      'rot': (0, 0, 0), 'dimensions': {field: 1.0 for field in REGION_SHAPES[shape][1]}}
        identity = max((point['index'] for point in self.points), default=-1) + 1
        name = f"{source['name']}_{identity}"
        names = {point['name'] for point in self.points}
        while name in names:
            name += '_copy'
        encoded = name.encode('shift_jis') + b'\0'
        encoded += bytes(-len(encoded) % 4)
        shape_data = struct.pack('<%df' % len(source['dimensions']), *source['dimensions'].values())
        base = len(self.plain)
        shape_at = POINT_HEADER + len(encoded) + 8
        header = struct.pack('<4i6f5i', POINT_HEADER, 0, identity, source['shape'],
                             *source['pos'], *source['rot'], shape_at-8, shape_at-4,
                             shape_at, shape_at+len(shape_data), 0)
        self.plain += header + encoded + bytes(8) + shape_data + struct.pack('<i', -1)
        self._relocate_param(2, extra=[base])
        point = _point(self.plain, base)
        self.points.append(point)
        self._strings.extend(point['spans'])
        self.added.add(('region', identity))
        self.dirty.add((('region', identity), 'posX'))
        return self.read_region(('region', identity))

    def remove_region(self, key):
        point = self._region(key)
        gone = self.points.index(point)
        if any(event['type'] == LIGHT_EVENT and event['point'] == gone for event in self.events):
            raise MsbError('This region positions a light; move that light to another region before removing it')
        slots = [(event['ahead']+4, 'i') for event in self.events]
        for event in self.events:
            if event['type'] in (8, 10):
                slots.append((event['bhead'], 'i'))
            elif event['type'] == 5:
                slots.extend((event['bhead'] + 48 + 4*i, 'i') for i in range(4))
        for part in self.parts:
            if part['type'] in ENEMY_TYPES:
                slots.extend((part['type_data'] + 40 + 2*i, 'h') for i in range(8))
        for at, dtype in slots:
            value = struct.unpack_from('<'+dtype, self.plain, at)[0]
            if value >= gone:
                struct.pack_into('<'+dtype, self.plain, at, -1 if value == gone else value-1)
        for event in self.events:
            event['point'] = struct.unpack_from('<i', self.plain, event['ahead']+4)[0]
        self._relocate_param(2, drop=[point['base']])
        self.points.remove(point)
        self.added.discard(tuple(key))
        self.dirty = {entry for entry in self.dirty if entry[0] != tuple(key)}
        self.removed.append({'type': 'region', 'id': key[1], 'name': point['name'], 'kind': 'Region'})
        return {'type': 'region', 'id': key[1], 'name': point['name']}

    def export(self):
        return bytes(self.plain)
