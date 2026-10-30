"""Typed MSB1 event fields. Padding and unknown event bytes stay intact."""
import math
import struct

# name, byte offset in subtype data, storage type, optional reference list
SPECS = {
    0: [('preset', 0, 'i', None)],
    1: [('soundType', 0, 'i', None), ('soundId', 4, 'i', None)],
    2: [('effectId', 0, 'i', None)],
    3: [(f'windMin{axis}', i*4, 'f', None) for i, axis in enumerate('XYZ')]
       + [('unknown12', 12, 'f', None)]
       + [(f'windMax{axis}', 16+i*4, 'f', None) for i, axis in enumerate('XYZ')]
       + [('unknown28', 28, 'f', None)]
       + [(f'cycle{i+1}', 32+i*4, 'f', None) for i in range(4)]
       + [(f'power{i+1}', 48+i*4, 'f', None) for i in range(4)],
    4: [('treasurePart', 4, 'i', 'part')]
       + [(f'itemLot{i+1}', 8+i*8, 'i', None) for i in range(5)]
       + [('inChest', 48, '?', None), ('hidden', 49, '?', None)],
    5: [('maxCount', 0, 'B', None), ('spawnType', 1, 'b', None), ('limitCount', 2, 'h', None),
        ('minCount', 4, 'h', None), ('maxSpawnCount', 6, 'h', None),
        ('minInterval', 8, 'f', None), ('maxInterval', 12, 'f', None), ('initialCount', 16, 'i', None)]
       + [(f'spawnRegion{i+1}', 48+i*4, 'i', 'region') for i in range(4)]
       + [(f'spawnPart{i+1}', 64+i*4, 'i', 'part') for i in range(32)],
    7: [('activationEntityId', 0, 'i', None), ('activationPart', 4, 'i', 'part'),
        ('activationParam', 8, 'h', None), ('activationState', 10, 'B', None), ('activationFlag', 12, 'i', None)],
    8: [('spawnRegion', 0, 'i', 'region')],
    9: [('posX', 0, 'f', None), ('posY', 4, 'f', None), ('posZ', 8, 'f', None), ('rotY', 12, 'f', None)],
    10: [('navigationRegion', 0, 'i', 'region')],
    11: [('unknown0', 0, 'i', None)] + [(f'unknown{i*4}', i*4, 'f', None) for i in range(1, 6)],
    12: [('hostEntityId', 0, 'i', None), ('invasionFlag', 4, 'i', None), ('activationItem', 8, 'i', None)],
}
SIZES = {0: 4, 1: 8, 2: 4, 3: 64, 4: 52, 5: 256, 7: 16, 8: 16, 9: 16, 10: 16, 11: 32, 12: 16}
LABELS = {0: 'Light', 1: 'Sound', 2: 'Effect', 3: 'Wind', 4: 'Treasure', 5: 'Spawner',
          7: 'Object activation', 8: 'Spawn point', 9: 'Map offset', 10: 'Navigation event',
          11: 'Environment', 12: 'NPC invasion'}


def event(doc, key):
    from .msb import MsbError
    etype = int(key[0][5:])
    found = next((item for item in doc.events if item['type'] == etype and item['seq'] == key[1]), None)
    if etype not in SPECS or found is None:
        raise MsbError('Select a map event')
    if found['bhead'] + SIZES[etype] > len(doc.plain):
        raise MsbError('This map event is truncated')
    return found


def fields(item):
    yield 'attachedPart', item['ahead'], 'i', 'part'
    yield 'attachedRegion', item['ahead']+4, 'i', 'region'
    yield 'entityId', item['ahead']+8, 'i', None
    for name, offset, dtype, reference in SPECS[item['type']]:
        yield name, item['bhead']+offset, dtype, reference


def label(name):
    import re
    return re.sub(r'([a-z])([A-Z])', r'\1 \2', name).capitalize().replace(' id', ' ID')


def read(doc, key):
    item = event(doc, key)
    result = []
    for name, address, dtype, reference in fields(item):
        value = struct.unpack_from('<'+dtype, doc.plain, address)[0]
        original = None if tuple(key) in doc.added else struct.unpack_from('<'+dtype, doc.original, address)[0]
        options = {}
        if reference is not None:
            source = doc.parts if reference == 'part' else doc.points
            options = {'-1': 'None'} | {str(i): target['name'] for i, target in enumerate(source)}
        limits = {'B': (0, 255), 'b': (-128, 127), 'h': (-32768, 32767), 'i': (-2**31, 2**31-1)}
        low, high = limits.get(dtype, (None, None))
        result.append({'key': name, 'label': label(name), 'description': '',
                       'group': LABELS[item['type']], 'value': value, 'vanilla': original,
                       'type': 'bool' if dtype == '?' else 'enum' if reference else 'number',
                       'dtype': {'?': 'bool', 'f': 'f32', 'B': 'u8', 'b': 's8', 'h': 's16', 'i': 's32'}[dtype],
                       'enum': options, 'minimum': low, 'maximum': high, 'editable': True})
    return {'partId': key[1], 'type': key[0], 'name': item['name'],
            'kind': LABELS[item['type']], 'model': '', 'think': None, 'fields': result}


def placements(doc):
    for item in doc.events:
        if item['type'] not in SPECS or item['type'] == 0:
            continue
        point = doc.points[item['point']] if 0 <= item['point'] < len(doc.points) else None
        yield {'partId': item['seq'], 'type': f"event{item['type']}",
               'kind': LABELS[item['type']], 'name': item['name'], 'model': '',
               'pos': tuple(point['pos']) if point else (0, 0, 0),
               'rot': (0, 0, 0), 'scale': (1, 1, 1)}


def edit(doc, key, name, value):
    from .msb import MsbError
    item = event(doc, key)
    spec = next((spec for spec in fields(item) if spec[0] == name), None)
    if spec is None:
        raise MsbError('This map event field is protected')
    _, address, dtype, reference = spec
    if dtype == '?':
        if type(value) is not bool:
            raise MsbError('Choose on or off')
    elif dtype == 'f':
        if type(value) not in (int, float) or not math.isfinite(value):
            raise MsbError('Enter a finite number')
    elif type(value) is not int:
        raise MsbError('Enter a whole number')
    if reference:
        count = len(doc.parts if reference == 'part' else doc.points)
        if not -1 <= value < count:
            raise MsbError('Choose a record from this map')
    try:
        encoded = struct.pack('<'+dtype, value)
        if dtype == 'f' and not math.isfinite(struct.unpack('<f', encoded)[0]):
            raise OverflowError
    except (struct.error, OverflowError):
        raise MsbError('That value is outside the map format range') from None
    doc._write(address, len(encoded), encoded)
    item['area'], item['point'], item['flag'] = struct.unpack_from('<3i', doc.plain, item['ahead'])
    unit = (tuple(key), name)
    if tuple(key) not in doc.added and encoded == doc.original[address:address+len(encoded)]:
        doc.dirty.discard(unit)
    else:
        doc.dirty.add(unit)
    return read(doc, key)


def duplicate(doc, key):
    item = event(doc, key)
    etype = item['type']
    common = bytearray(doc.plain[item['ahead']:item['ahead']+16])
    struct.pack_into('<i', common, 8, -1)
    return insert(doc, etype, item['name'], common,
                  bytes(doc.plain[item['bhead']:item['bhead']+SIZES[etype]]))


def insert(doc, etype, hint, common, data):
    from .msb import _event
    identity = max((e['seq'] for e in doc.events if e['type'] == etype), default=-1) + 1
    ordinal = max((e['part'] for e in doc.events), default=-1) + 1
    name = f"{hint}_{identity}"
    names = {e['name'] for e in doc.events}
    while name in names:
        name += '_copy'
    encoded = name.encode('shift_jis')+b'\0'
    encoded += bytes(-len(encoded)%4)
    ahead = 28+len(encoded)
    base = len(doc.plain)
    doc.plain += struct.pack('<7i', 28, ordinal, etype, identity, ahead, ahead+16, 0)+encoded+common+data
    index = next((i for i, e in enumerate(doc.events) if e['type'] > etype), len(doc.events))
    doc._relocate_param(1, extra=[base], at=index)
    added = _event(doc.plain, base, len(doc.parts), len(doc.points))
    doc.events.insert(index, added)
    doc._strings.extend(added['spans'])
    new_key = ('light' if etype == 0 else f'event{etype}', identity)
    if etype == 0:
        doc._lights[(0, identity)] = added
    doc.added.add(new_key)
    doc.dirty.add((new_key, 'preset' if etype == 0 else 'entityId'))
    return doc.read_light(new_key) if etype == 0 else read(doc, new_key)


def create(doc, etype, pos):
    from .msb import MsbError
    if etype not in SPECS:
        raise MsbError('Select a map event kind')
    if len(pos) != 3 or any(type(value) not in (int, float) or not math.isfinite(value) for value in pos):
        raise MsbError('An event needs a finite position')
    data = bytearray(SIZES[etype])
    for name, offset, dtype, reference in SPECS[etype]:
        if reference or name in ('soundId', 'hostEntityId', 'activationEntityId', 'activationParam') or name.startswith('itemLot'):
            struct.pack_into('<'+dtype, data, offset, -1)
    if etype == 4:
        for index in range(5):
            struct.pack_into('<i', data, 12+8*index, -1)
    if etype == 11:
        struct.pack_into('<5f', data, 4, *([1.]*5))
    region = doc.add_region(shape=0, pos=pos)
    region_index = next(i for i, point in enumerate(doc.points) if point['index'] == region['partId'])
    return insert(doc, etype, LABELS[etype].replace(' ', ''), struct.pack('<4i', -1, region_index, -1, 0), data)


def remove(doc, key):
    from .msb import MsbError
    item = event(doc, key)
    if item['type'] == 11:
        environments = [e for e in doc.events if e['type'] == 11]
        index = environments.index(item)
        if any(struct.unpack_from('<h', doc.plain, p['type_data']+2)[0] == index
               for p in doc.parts if p['type'] == 5):
            raise MsbError('This environment is used by a collision; change that reference before removing it')
        for part in doc.parts:
            if part['type'] == 5:
                at = part['type_data']+2
                value = struct.unpack_from('<h', doc.plain, at)[0]
                if value > index:
                    struct.pack_into('<h', doc.plain, at, value-1)
    doc._relocate_param(1, drop=[item['base']])
    doc.events.remove(item)
    actual_key = ('light', key[1]) if item['type'] == 0 else tuple(key)
    if item['type'] == 0:
        del doc._lights[(0, key[1])]
    doc.added.discard(actual_key)
    doc.dirty = {unit for unit in doc.dirty if unit[0] != actual_key}
    doc.removed.append({'type': key[0], 'id': key[1], 'name': item['name'], 'kind': LABELS[item['type']]})
    return {'type': key[0], 'id': key[1], 'name': item['name']}
