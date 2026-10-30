"""Portable record contributions, rebased through the existing archive adapters.

The release stores changed PARAM rows, FMG entries, MSB fields, EMEVD events and
ESD states/members, with old values as anchors. Materialization preserves unrelated
installed data and feeds ordinary archives into the editor's shared composer.
"""
import json
import struct
import base64
import hashlib
import zlib
from functools import lru_cache
from pathlib import Path

from core.mod_library import relative_path
from . import formats, texts, script_edits, binder_edits, map_edits

FILENAME = Path('records.lxd')
LIMIT = 64 * 1024 * 1024
DECODED_LIMIT = 256 * 1024 * 1024
PACKED = struct.Struct('<8sI')
PACKED_MAGIC = b'LXD1REC\0'
MAX_ROWS = 100000


def supports(relative):
    from .mod_loader import FILES
    from . import emevd
    return (relative in FILES or emevd.is_event_file(relative)
            or script_edits.supported(relative) or binder_edits.supported(relative) or map_edits.supported(relative))


@lru_cache(maxsize=128)
def _targets(path,size,modified,changed):
    # Cache only the small target index, never the parsed record payloads.
    return tuple(decode(read(Path(path))))


def targets(path):
    from .tweak_mods import checked
    path = checked(path)
    stamp = path.stat()
    return _targets(str(path),stamp.st_size,stamp.st_mtime_ns,stamp.st_ctime_ns)


def read(path):
    from .tweak_mods import checked
    path = checked(path)
    if path.stat().st_size > LIMIT:
        raise ValueError('The record contributions exceed 64 MiB')
    with path.open('rb') as stream:
        raw = stream.read(LIMIT+1)
    if len(raw) > LIMIT:
        raise ValueError('The record contributions grew beyond 64 MiB')
    return raw


def encode(files):
    raw = json.dumps({'version':1,'files':{str(key).replace('\\','/'):value for key,value in files.items()}},
                     ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    if len(raw) > DECODED_LIMIT:
        raise ValueError('The decoded record contributions exceed 256 MiB')
    packed = PACKED.pack(PACKED_MAGIC,len(raw))+zlib.compress(raw,6) if len(raw)>65536 else raw
    if len(packed)>LIMIT:
        raise ValueError('The packed record contributions exceed 64 MiB')
    return packed


def decode(raw):
    if len(raw) > LIMIT:
        raise ValueError('The record contributions exceed 64 MiB')
    if raw.startswith(PACKED_MAGIC):
        if len(raw)<PACKED.size:
            raise ValueError('The packed record header is incomplete')
        _magic,size = PACKED.unpack_from(raw)
        if size>DECODED_LIMIT:
            raise ValueError('The decoded record contributions exceed 256 MiB')
        try:
            decoder = zlib.decompressobj()
            unpacked = decoder.decompress(raw[PACKED.size:],size+1)
        except zlib.error as error:
            raise ValueError('The packed record contributions are damaged') from error
        if (len(unpacked)!=size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail):
            raise ValueError('The packed record contribution lengths do not match')
        raw = unpacked
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result:
                raise ValueError('Duplicate record contribution key')
            result[key] = value
        return result
    def invalid_constant(_value):
        raise ValueError('Non-finite numbers are not portable record data')
    value = json.loads(raw,object_pairs_hook=unique,parse_constant=invalid_constant)
    if (type(value) is not dict or set(value) != {'version','files'}
            or type(value['version']) is not int or value['version'] != 1
            or type(value['files']) is not dict or len(value['files']) > 128):
        raise ValueError('Unsupported record contributions')
    result = {}
    for name,spec in value['files'].items():
        if len(name) > 512:
            raise ValueError('The record contribution path is too long')
        path = relative_path(name)
        if not supports(path) or path in result or type(spec) is not dict:
            raise ValueError('Invalid record contribution target')
        result[path] = spec
    return result


def _entries(data):
    plain = formats.inflate(data)
    return plain,texts.bnd3_entries(plain)


def _same_directory(before,after):
    if [(e.member_id,e.name,e.flags) for e in before] != [(e.member_id,e.name,e.flags) for e in after]:
        raise ValueError('Archive directory changes cannot be exported as record edits')


def _row(row):
    return {'name':row[1].hex() if row[1] is not None else None,'data':row[2].hex()}


def _header(data):
    return (data[6:10]+data[12:48]).hex()


def validate_original(relative,original):
    """Diagnose a failed rebase without blaming a mod for damaged game data."""
    from . import emevd,mod_loader
    if map_edits.supported(relative):
        map_edits.MsbDocument(original,relative.name)
    elif emevd.is_event_file(relative):
        _event_document(original)
    elif script_edits.supported(relative):
        script_edits.validate_original(original)
    elif binder_edits.supported(relative):
        binder_edits.validate_original(original)
    elif relative == mod_loader.RELATIVE:
        _plain,entries = _entries(original)
        for entry in entries:
            if entry.name.lower().endswith('.param'):
                mod_loader.ParamView(entry.data)
    elif relative in mod_loader.FILES:
        document = texts.MenuDocument if relative == texts.MENU_RELATIVE else texts.TextDocument
        document(original)


def create(relative,before,after):
    from . import mod_loader
    from . import emevd
    if map_edits.supported(relative):
        return map_edits.create(relative,before,after)
    if emevd.is_event_file(relative):
        return _create_events(before,after)
    if script_edits.supported(relative):
        return script_edits.create(before,after)
    if binder_edits.supported(relative):
        return binder_edits.create(before,after)
    if relative == mod_loader.RELATIVE:
        _base,originals = _entries(before)
        _changed,modified = _entries(after)
        _same_directory(originals,modified)
        tables = []
        for old,new in zip(originals,modified):
            if old.data == new.data:
                continue
            spans = mod_loader._row_spans(old.data)
            if not spans or _header(old.data) != _header(new.data):
                raise ValueError(f'{old.name}: unsupported parameter layout change')
            size = spans[0][1]-spans[0][0]
            a,b = mod_loader._table_rows(old.data,size),mod_loader._table_rows(new.data,size)
            if a is None or b is None or not 0 < size <= 65536:
                raise ValueError(f'{old.name}: unreadable parameter rows')
            tail = mod_loader._standard_tail(old.data,size,a)
            if tail is None or mod_loader._standard_tail(new.data,size,b) is None:
                raise ValueError(f'{old.name}: unsupported parameter record layout')
            first,last = {r[0]:r for r in a},{r[0]:r for r in b}
            if len(first) != len(a) or len(last) != len(b):
                raise ValueError(f'{old.name}: duplicate parameter IDs')
            rows = [{'id':key,'before':_row(first[key]) if key in first else None,
                     'after':_row(last[key]) if key in last else None}
                    for key in sorted(first.keys()|last.keys()) if first.get(key) != last.get(key)]
            tables.append({'name':old.name,'memberId':old.member_id,'size':size,'header':_header(old.data),'rows':rows})
        return {'kind':'params','tables':tables}
    document = texts.MenuDocument if relative == texts.MENU_RELATIVE else texts.TextDocument
    base,changed = document(before),document(after)
    _same_directory(base.entries,changed.entries)
    tables = []
    for position,(old,new) in enumerate(zip(base.entries,changed.entries)):
        if old.data == new.data:
            continue
        if position not in base.tables or position not in changed.tables:
            raise ValueError(f'{old.name}: unsupported non-text member change')
        a,b = base.tables[position][1],changed.tables[position][1]
        rows = [{'id':key,'before':a.get(key),'after':b.get(key)}
                for key in sorted(a.keys()|b.keys()) if a.get(key) != b.get(key)]
        tables.append({'name':old.name,'memberId':old.member_id,'rows':rows})
    return {'kind':'texts','tables':tables}


def _hex(value,limit,*,size=None):
    if type(value) is not str or len(value) > limit*2:
        raise ValueError('Invalid record byte string')
    data = bytes.fromhex(value)
    if len(data) > limit or (size is not None and len(data) != size):
        raise ValueError('Invalid record byte length')
    return data


def _saved_row(value,size):
    if value is None:
        return None
    if type(value) is not dict or set(value) != {'name','data'}:
        raise ValueError('Invalid parameter record')
    return (None if value['name'] is None else _hex(value['name'],65536),
            _hex(value['data'],65536,size=size))


def _changes(rows):
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise ValueError('Invalid record change list')
    seen = set()
    for change in rows:
        if (type(change) is not dict or set(change) != {'id','before','after'}
                or type(change['id']) is not int or not -(2**31) <= change['id'] < 2**31
                or change['id'] in seen):
            raise ValueError('Invalid or duplicate record ID')
        seen.add(change['id'])
        yield change


def materialize(relative,original,spec):
    from . import mod_loader
    if original is None:
        raise ValueError(f'{relative}: the installed baseline is missing')
    from . import emevd
    if map_edits.supported(relative):
        return map_edits.materialize(relative,original,spec)
    if emevd.is_event_file(relative):
        return _materialize_events(original,spec)
    if script_edits.supported(relative):
        return script_edits.materialize(original,spec,talk_options=relative.parts[0].lower()!='chr')
    if binder_edits.supported(relative):
        return binder_edits.materialize(original,spec)
    kind = 'params' if relative == mod_loader.RELATIVE else 'texts'
    if (type(spec) is not dict or set(spec) != {'kind','tables'} or spec['kind'] != kind
            or type(spec['tables']) is not list or len(spec['tables']) > 4096):
        raise ValueError('Invalid record contribution format')
    if kind == 'params':
        plain,entries = _entries(original)
        doc = None
    else:
        document = texts.MenuDocument if relative == texts.MENU_RELATIVE else texts.TextDocument
        doc = document(original)
        plain,entries = doc.plain,list(doc.entries)
    positions = {(entry.member_id,entry.name):index for index,entry in enumerate(entries)}
    original_payloads = [entry.data for entry in entries]
    if len(positions) != len(entries):
        raise ValueError('The installed archive has duplicate member names')
    seen = set()
    units = mod_loader._Units()
    for table in spec['tables']:
        keys = {'name','memberId','rows','size','header'} if kind == 'params' else {'name','memberId','rows'}
        if (type(table) is not dict or set(table) != keys or type(table['name']) is not str
                or type(table['memberId']) is not int):
            raise ValueError('Invalid record table')
        name = table['name']
        identity = table['memberId'],name
        if identity in seen or identity not in positions:
            raise ValueError(f'{name}: the record table anchor is missing or duplicated')
        seen.add(identity)
        position = positions[identity]
        entry = entries[position]
        if kind == 'params':
            size = table['size']
            if type(size) is not int or not 0 < size <= 65536 or table['header'] != _header(entry.data):
                raise ValueError(f'{name}: the parameter layout anchor does not match')
            current = mod_loader._table_rows(entry.data,size)
            tail = mod_loader._standard_tail(entry.data,size,current) if current else None
            if current is None or tail is None:
                raise ValueError(f'{name}: the installed parameter layout is unsupported')
            order = [r[0] for r in current]
            rows = {r[0]:(r[1],r[2]) for r in current}
            if len(rows) != len(current):
                raise ValueError(f'{name}: duplicate installed parameter IDs')
            for change in _changes(table['rows']):
                key = change['id']
                before,after = (_saved_row(change[side],size) for side in ('before','after'))
                live = rows.get(key)
                if before is None or after is None:
                    if live not in (before,after):
                        raise ValueError(f'{name} {key}: the added/removed record anchor does not match')
                    if after is None:
                        rows.pop(key,None)
                    else:
                        if key not in rows:
                            order.append(key)
                        rows[key] = after
                    continue
                if live is None:
                    raise ValueError(f'{name} {key}: the record anchor is missing')
                row_name,data = live[0],bytearray(live[1])
                if before[0] != after[0]:
                    if row_name not in (before[0],after[0]):
                        raise ValueError(f'{name} {key}: the name anchor does not match')
                    row_name = after[0]
                for offset,width,mask,label in units.of(name.replace('\\','/').rsplit('/',1)[-1],size):
                    old = int.from_bytes(before[1][offset:offset+width],'little') & mask
                    new = int.from_bytes(after[1][offset:offset+width],'little') & mask
                    if old == new:
                        continue
                    live_value = int.from_bytes(data[offset:offset+width],'little')
                    if live_value & mask not in (old,new):
                        raise ValueError(f'{name} {key}, {label}: the field anchor does not match')
                    data[offset:offset+width] = ((live_value & ~mask)|new).to_bytes(width,'little')
                rows[key] = row_name,bytes(data)
            if rows.keys() == {r[0] for r in current} and all(rows[key][0] == row_name for key,row_name,_data in current):
                # Field-only edits keep every byte outside the row payloads,
                # including noncanonical offsets, padding and orphan names.
                payload = bytearray(entry.data)
                for index,(key,_name,_data) in enumerate(current):
                    offset = struct.unpack_from('<I',entry.data,48+index*12+4)[0]
                    payload[offset:offset+size] = rows[key][1]
                payload = bytes(payload)
            else:
                payload = mod_loader._write_table(entry.data,size,
                    [(key,*rows[key]) for key in order if key in rows],tail)
        else:
            if position not in doc.tables:
                raise ValueError(f'{name}: the text table anchor is missing')
            groups,current = doc.tables[position]
            updated = dict(current)
            for change in _changes(table['rows']):
                if any(value is not None and (type(value) is not str or len(value)>1024*1024)
                       for value in (change['before'],change['after'])):
                    raise ValueError('Invalid text record')
                if updated.get(change['id']) not in (change['before'],change['after']):
                    raise ValueError(f"{name} {change['id']}: the text anchor does not match")
                updated[change['id']] = change['after']
            payload = texts.build_fmg(entry.data,groups,updated)
        entries[position] = texts.Entry(entry.member_id,entry.name,entry.flags,payload)
    if all(entry.data == old for entry,old in zip(entries,original_payloads)):
        return original
    return formats.deflate(original,texts.build_bnd3(plain,entries))


def _event_document(data):
    from . import emevd
    return emevd.read(formats.inflate(data) if data.startswith(b'DCX\0') else data)


def describe(files):
    """Identity-level changes already carried by portable script/event records."""
    changes = []
    for relative,spec in files.items():
        if spec.get('kind') == 'esd':
            changes += script_edits.describe(spec,f'ESD ({relative.name})')
            continue
        if spec.get('kind') == 'binder':
            for member in spec['members']:
                after = member['after']
                name = member['name'].replace('\\','/').rsplit('/',1)[-1]
                if after is not None and after.get('kind') == 'esd':
                    changes += script_edits.describe(after['edits'],f'{relative.name}/{name}')
                else:
                    changes.append({'table':relative.name,'id':member['id'],'label':name,
                        'fields':['Archive member'],'added':member['beforeHash'] is None,'removed':after is None})
            continue
        if spec.get('kind') != 'events':
            continue
        for change in _changes(spec.get('rows')):
            changes.append({'table':f'Events ({relative.name})','id':change['id'],
                'label':f"Event {change['id']}",'fields':['Event record'],
                'added':change['before'] is None,'removed':change['after'] is None})
    return changes


def _event_bytes(event):
    from . import emevd
    return (base64.b64encode(emevd.write(emevd.Document((event,)))).decode('ascii')
            if event is not None else None)


def _event(value,identity):
    from . import emevd
    if value is None:
        return None
    if type(value) is not str or len(value) > LIMIT:
        raise ValueError('Invalid portable event bytes')
    document = emevd.read(base64.b64decode(value,validate=True))
    if (len(document.events) != 1 or document.events[0].id != identity
            or document.strings or document.linked):
        raise ValueError('A portable event must contain only its declared event record')
    return document.events[0]


def _create_events(before,after):
    a,b = _event_document(before),_event_document(after)
    if (a.linked,a.strings) != (b.linked,b.strings):
        raise ValueError('Event string/link changes cannot be relocated from opaque instruction arguments')
    first,last = {event.id:event for event in a.events},{event.id:event for event in b.events}
    rows = [{'id':key,'before':_event_bytes(first.get(key)),'after':_event_bytes(last.get(key))}
            for key in sorted(first.keys()|last.keys()) if first.get(key) != last.get(key)]
    return {'kind':'events','linked':list(a.linked),'stringsSize':len(a.strings),
            'stringsHash':hashlib.sha256(a.strings).hexdigest(),'rows':rows}


def _materialize_events(original,spec):
    from dataclasses import replace
    from . import emevd
    if (type(spec) is not dict or set(spec) != {'kind','linked','stringsSize','stringsHash','rows'}
            or spec['kind'] != 'events' or type(spec['linked']) is not list
            or len(spec['linked']) > MAX_ROWS or any(type(item) is not int for item in spec['linked'])
            or type(spec['stringsSize']) is not int or not 0 <= spec['stringsSize'] <= emevd.MAX_BYTES
            or type(spec['stringsHash']) is not str or len(spec['stringsHash']) != 64):
        raise ValueError('Invalid portable event format')
    document = _event_document(original)
    if (tuple(spec['linked']) != document.linked[:len(spec['linked'])]
            or len(document.strings) < spec['stringsSize']
            or hashlib.sha256(document.strings[:spec['stringsSize']]).hexdigest() != spec['stringsHash']):
        raise ValueError('The event string/link pool anchor does not match')
    events = {event.id:event for event in document.events}
    for change in _changes(spec['rows']):
        key = change['id']
        before,after = (_event(change[side],key) for side in ('before','after'))
        current = events.get(key)
        if before is None or after is None:
            if current not in (before,after):
                raise ValueError(f'Event {key}: the added/removed record anchor does not match')
            if after is None:
                events.pop(key,None)
            else:
                events[key] = after
        else:
            if current is None:
                raise ValueError(f'Event {key}: the record anchor is missing')
            merged,collisions = emevd.merge(emevd.Document((before,)),[
                ('Installed data',emevd.Document((current,))),('Mod edit',emevd.Document((after,)))])
            if collisions:
                raise ValueError(f'Event {key}: the edited record anchor conflicts with installed data')
            events[key] = merged.events[0]
    ordered = [events[event.id] for event in document.events if event.id in events]
    existing = {event.id for event in document.events}
    ordered.extend(events[key] for key in sorted(events.keys()-existing))
    result = replace(document,events=tuple(ordered))
    if result == document:
        return original
    plain = emevd.write(result)
    return formats.deflate(original,plain) if original.startswith(b'DCX\0') else plain
