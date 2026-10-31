"""Combine independent TAE animation records, retaining opaque event payloads.

Event lists, timestamps and added animations combine by animation ID. Existing
geometry descriptors stay unchanged. Other structural edits refuse,
so the caller can report a whole-member conflict rather than discard data.
"""
from bisect import bisect_right
import base64
import hashlib
import struct

from .tae import TaeDocument, TaeError, EVENT_TYPES, MAX_FILE, _wstring


def _ranges(ids, directory):
    ranges = []
    for index, key in enumerate(ids):
        if ranges and key == ranges[-1][1]+1:
            ranges[-1][1] = key
        else:
            ranges.append([key, key, directory+index*8])
    return ranges


def _records(data):
    doc = TaeDocument(data)
    boundaries = {len(data)}
    directory, groups = struct.unpack_from('<2I', data, 88)
    ids = [anim['id'] for anim in doc.anims]
    if ids != sorted(set(ids)):
        raise TaeError('Animation directory is not uniquely ordered')
    if struct.unpack_from('<I', data, 104)[0] not in (0, doc.anims[0]['offset']):
        raise TaeError('Animation first-record pointer is not supported')
    count, group_rows = struct.unpack_from('<2I', data, groups)
    actual = [list(struct.unpack_from('<3I', data, group_rows+i*12)) for i in range(count)]
    if actual != _ranges(ids, directory):
        raise TaeError('Animation grouping is not supported')
    spans = [(12, 16), (84, 96), (100, 108),
             (directory, directory+len(ids)*8), (groups, groups+8),
             (group_rows, group_rows+count*12)]
    boundaries.update((directory, directory+len(ids)*8, groups, group_rows, group_rows+count*12))
    for anim in doc.anims:
        at = anim['offset']
        n, events, _, _, ticks, pool, file = struct.unpack_from('<7I', data, at)
        for start, size in ((at, 28), (events, n*12), (pool, ticks*4), (file, 24)):
            boundaries.update((start, start+size))
        spans += [(at, at+28), (events, events+n*12), (pool, pool+ticks*4), (file, file+24)]
        name = struct.unpack_from('<I', data, file+8)[0]
        text = _wstring(data, name, 'An animation name') if name not in (0, len(data)) else ''
        anim['merge_file'] = file
        anim['merge_name'] = text.encode('utf-16-le')+b'\0\0' if text else b''
        if name not in (0, len(data)):
            boundaries.add(name)
            boundaries.add(name+len(anim['merge_name']))
            spans.append((name, name+len(anim['merge_name'])))
        boundaries.update(e['data_off'] for e in anim['events'])
    bounds = sorted(boundaries)
    records = {}
    for anim in doc.anims:
        events = []
        for event in anim['events']:
            at = event['data_off']
            end = bounds[bisect_right(bounds, at)]
            known = EVENT_TYPES.get(event['type'])
            size = 8 if event['empty'] else min(end-at, known[0]) if known else end-at
            if size < 8:
                raise TaeError('Overlapping animation event records')
            event['merge_size'] = size
            spans.append((at, at+size))
            # The parameter pointer is structural, never an animation value.
            payload = data[at:at+4] + bytes([event['empty']]) + data[at+8:at+size]
            times = tuple(data[event[key]:event[key]+4] for key in ('start_off', 'end_off'))
            events.append((times, payload))
        pool = tuple(data[at:at+4] for at in anim['pool'])
        file = anim['merge_file']
        metadata = (data[file:file+4]+data[file+12:file+24], anim['merge_name'])
        records[anim['id']] = (metadata, pool, tuple(events))
    return doc, records, spans


def _record_hash(record):
    if record is None:
        return None
    metadata,pool,events = record
    sections = [metadata,pool,*[(*times,payload) for times,payload in events]]
    digest = hashlib.sha256()
    digest.update(struct.pack('<I',len(sections)))
    for section in sections:
        digest.update(struct.pack('<I',len(section)))
        for data in section:
            digest.update(struct.pack('<I',len(data)))
            digest.update(data)
    return digest.hexdigest()


def _metadata_hash(data):
    """Container identity without relocatable directories or record counts."""
    try:
        header = bytearray(data[:144])
        for start,end in ((12,16),(84,96),(100,108)):
            header[start:end] = bytes(end-start)
        names = struct.unpack_from('<I',data,148)[0]
        if not 152 <= names <= len(data)-16:
            raise TaeError('Animation container names are not supported')
        skeleton,sib = struct.unpack_from('<2I',data,names)
        labels = tuple((_wstring(data,at,'Animation container name') if at else '').encode('utf-16-le')
                       for at in (skeleton,sib))
        metadata = bytes(header)+data[144:148]+data[names+8:names+16]
        digest = hashlib.sha256(metadata)
        for label in labels:
            digest.update(struct.pack('<I',len(label))+label)
        return digest.hexdigest()
    except struct.error as error:
        raise TaeError('Animation container metadata is incomplete') from error


def create_edits(before,after):
    """Anchor changed animation IDs, excluding every untouched record."""
    # Composition validates supported structural changes and normalizes the
    # empty-name sentinel when an author appended animations.
    normalized,_ = compose(before,[('release',after)])
    _old,original,_ = _records(before)
    _new,changed,_ = _records(normalized)
    metadata = _metadata_hash(before)
    if _metadata_hash(normalized) != metadata:
        raise TaeError('Animation container metadata changed')
    rows = [{'id':key,'before':_record_hash(original.get(key))}
            for key in sorted(changed) if changed[key] != original.get(key)]
    return {'kind':'tae','metadata':metadata,'source':base64.b64encode(normalized).decode('ascii'),'rows':rows}


def edit_rows(spec):
    """Bounded record identities for both loading and the Mods change list."""
    if (type(spec) is not dict or set(spec) != {'kind','metadata','source','rows'} or spec['kind'] != 'tae'
            or type(spec['source']) is not str or len(spec['source']) > 4*((MAX_FILE+2)//3)
            or type(spec['rows']) is not list or len(spec['rows'])>10000):
        raise TaeError('Invalid portable animation contribution')
    seen = set()
    for row in spec['rows']:
        if (type(row) is not dict or set(row) != {'id','before'} or type(row['id']) is not int
                or not 0 <= row['id'] < 2**32 or row['id'] in seen):
            raise TaeError('Invalid portable animation record')
        seen.add(row['id'])
        before = row['before']
        if before is not None and (type(before) is not str or len(before)!=64
                or any(char not in '0123456789abcdef' for char in before)):
            raise TaeError('Invalid portable animation anchor')
    return spec['rows']


def apply_edits(original,spec):
    """Rebase only declared animation records through the composition writer."""
    rows = edit_rows(spec)
    source = base64.b64decode(spec['source'],validate=True)
    if len(source)>MAX_FILE:
        raise TaeError('Portable animation source exceeds its size limit')
    base,current,_ = _records(original)
    modified,records,_ = _records(source)
    if _metadata_hash(original) != spec['metadata'] or _metadata_hash(source) != spec['metadata']:
        raise TaeError('Animation container metadata conflicts with installed data')
    animations = {anim['id']:anim for anim in modified.anims}
    winners = {}
    for row in rows:
        if row['id'] not in records:
            raise TaeError('Invalid portable animation record')
        key,before = row['id'],row['before']
        after = _record_hash(records[key])
        if _record_hash(current.get(key)) not in (before,after):
            raise TaeError(f'Animation {key}: conflicts with installed data')
        if current.get(key) != records[key]:
            winners[key] = source,animations[key],records[key]
    return _write_records(original,base,current,winners)


def compose(vanilla, mods):
    """Return bytes and (animation label, conflicting owners) pairs."""
    base, original, spans = _records(vanilla)
    # Reject changes outside the layout fields replayed through the records.
    fixed = bytearray(b'\1' * len(vanilla))
    for start, end in spans:
        fixed[start:end] = bytes(end-start)
    winners, owners, conflicts = {}, {}, {}
    for name, data in mods:
        if data == vanilla:
            continue
        # An appended animation must not turn a preserved EOF/empty-name
        # sentinel into a string read from the newly appended binary records.
        normalized = bytearray(data)
        for anim in base.anims:
            file = anim['merge_file']
            if (struct.unpack_from('<I', vanilla, file+8)[0] == len(vanilla)
                    and data[file:file+24] == vanilla[file:file+24]):
                struct.pack_into('<I', normalized, file+8, 0)
        data = bytes(normalized)
        doc, records, _ = _records(data)
        if len(data) < len(vanilla) or not original.keys() <= records.keys():
            raise TaeError('Removed animation records cannot be combined')
        if any(fixed[i] and data[i] != value for i, value in enumerate(vanilla)):
            raise TaeError('Animation metadata changes cannot be combined')
        for anim in doc.anims:
            key = anim['id']
            if key in original and records[key][0] != original[key][0]:
                raise TaeError('Existing animation descriptors cannot be combined')
            if records[key] == original.get(key):
                continue
            if key in winners and winners[key][2] != records[key]:
                names = conflicts.setdefault(key, [])
                for owner in (owners[key], name):
                    if owner not in names:
                        names.append(owner)
            winners[key] = (data, anim, records[key])
            owners[key] = name
    if not winners:
        return vanilla, []
    return _write_records(vanilla,base,original,winners), [(f'animation {key}', names) for key, names in conflicts.items()]


def _write_records(vanilla, base, original, winners):
    """Replay selected records through the same writer used by composition."""
    if not winners:
        return vanilla
    result = bytearray(vanilla)
    for anim in base.anims:
        file = struct.unpack_from('<I', vanilla, anim['offset']+24)[0]
        if struct.unpack_from('<I', vanilla, file+8)[0] == len(vanilla):
            struct.pack_into('<I', result, file+8, 0)
    locations = {anim['id']: anim['offset'] for anim in base.anims}
    for key, chosen in winners.items():
        data, source, _ = chosen
        count, events, _, _, ticks, pool, _ = struct.unpack_from('<7I', data, source['offset'])
        result += bytes(-len(result) % 4)
        if key in locations:
            header = locations[key]
            file = struct.unpack_from('<I', vanilla, header+24)[0]
        else:
            header = locations[key] = len(result)
            result += bytes(28)
            file = len(result)
            old_file = source['merge_file']
            result += data[old_file:old_file+24]
            name = source['merge_name']
            struct.pack_into('<2I', result, file+4, file+8, file+24 if name else 0)
            result += name
            result += bytes(-len(result) % 4)
        new_events = len(result)
        result += bytes(count*12)
        new_pool = len(result)
        result += data[pool:pool+ticks*4]
        struct.pack_into('<7I', result, header, count, new_events, 0, 0, ticks, new_pool, file)
        for index, event in enumerate(source['events']):
            at = len(result)
            result += data[event['data_off']:event['data_off']+event['merge_size']]
            struct.pack_into('<3I', result, new_events+index*12,
                             new_pool+event['start_off']-pool,
                             new_pool+event['end_off']-pool, at)
            struct.pack_into('<I', result, at+4, 0 if event['empty'] else at+8)
        if len(result) > MAX_FILE:
            raise TaeError('Combined animation file is too large')
    if locations.keys() != original.keys():
        result += bytes(-len(result) % 4)
        directory = len(result)
        ids = sorted(locations)
        for key in ids:
            result += struct.pack('<2I', key, locations[key])
        groups = len(result)
        ranges = _ranges(ids, directory)
        result += struct.pack('<2I', len(ranges), groups+8)
        result += b''.join(struct.pack('<3I', *row) for row in ranges)
        struct.pack_into('<3I', result, 84, len(ids), directory, groups)
        struct.pack_into('<I', result, 100, len(ids))
        struct.pack_into('<I', result, 104, locations[ids[0]])
    if len(result) > MAX_FILE:
        raise TaeError('Combined animation file is too large')
    struct.pack_into('<I', result, 12, len(result))
    _, records, _ = _records(bytes(result))
    expected = original | {key: chosen[2] for key, chosen in winners.items()}
    if records != expected:
        raise TaeError('Combined animation records failed verification')
    return bytes(result)
