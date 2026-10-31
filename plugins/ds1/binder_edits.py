"""Sparse script-binder contributions, preserving untouched installed members."""
import base64
import hashlib

from . import formats,texts,script_edits,tae_merge
from .tae import CHR_DIR,TaeDocument,TaeError

MAX_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 4096


def supported(relative):
    return (bool(relative.parts) and (relative.parts[0].lower() in ('script','menu')
            and relative.name.lower().removesuffix('.dcx').endswith(('.talkesdbnd','.menuesdbnd'))
            or relative.parent == CHR_DIR and relative.name.lower().endswith('.anibnd.dcx')))


def _unpack(raw):
    plain = formats.inflate(raw) if raw.startswith(b'DCX\0') else raw
    formats.members(plain)  # Also validate name bounds and duplicate semantics.
    entries = texts.bnd3_entries(plain)
    if any(not 0 < len(entry.name) <= 1024 for entry in entries):
        raise ValueError('Script binder member name exceeds its portable limit')
    result = {(entry.member_id,entry.name):entry for entry in entries}
    if len(result) != len(entries):
        raise ValueError('Duplicate script binder member identity')
    return plain,entries,result


def validate_original(raw):
    _plain,entries,_by_id = _unpack(raw)
    for entry in entries:
        if entry.name.lower().endswith('.esd'):
            script_edits.validate_original(entry.data)
        elif entry.name.lower().endswith('.tae'):
            TaeDocument(entry.data)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def create(before,after):
    first,_old,a = _unpack(before)
    last,_new,b = _unpack(after)
    if (first[12:16],first[24:32]) != (last[12:16],last[24:32]):
        raise ValueError('Script binder metadata changes cannot be exported as member edits')
    changes = []
    for identity in sorted(a.keys()|b.keys()):
        original,changed = a.get(identity),b.get(identity)
        if original is not None and changed is not None and original.data == changed.data:
            continue
        payload = None
        if changed is not None:
            if original is not None and changed.name.lower().endswith('.esd'):
                payload = {'kind':'esd','edits':script_edits.create(original.data,changed.data)}
            elif original is not None and changed.name.lower().endswith('.tae'):
                TaeDocument(changed.data)
                try:
                    payload = {'kind':'tae','edits':tae_merge.create_edits(original.data,changed.data)}
                except TaeError:
                    # Unsupported descriptor/layout changes retain the
                    # existing exact member anchor, never an inferred delta.
                    payload = {'kind':'bytes','data':base64.b64encode(changed.data).decode('ascii')}
            else:
                if changed.name.lower().endswith('.esd'):
                    script_edits.parse(changed.data)
                elif changed.name.lower().endswith('.tae'):
                    TaeDocument(changed.data)
                payload = {'kind':'bytes','data':base64.b64encode(changed.data).decode('ascii')}
        changes.append({'id':identity[0],'name':identity[1],
                        'beforeHash':_sha(original.data) if original is not None else None,'after':payload})
    spec = {'kind':'binder','members':changes}
    if len(changes)>MAX_MEMBERS:
        raise ValueError('Too many portable binder member changes')
    return spec


def materialize(original,spec):
    if type(spec) is not dict or set(spec) != {'kind','members'} or spec['kind'] != 'binder':
        raise ValueError('Invalid portable script binder')
    if type(spec['members']) is not list or len(spec['members']) > MAX_MEMBERS:
        raise ValueError('Invalid portable binder member list')
    plain,entries,owned = _unpack(original)
    seen = set()
    for change in spec['members']:
        if (type(change) is not dict or set(change) != {'id','name','beforeHash','after'}
                or type(change['id']) is not int or not 0 <= change['id'] < 2**32
                or type(change['name']) is not str or not 0 < len(change['name']) <= 1024):
            raise ValueError('Invalid script binder member record')
        identity = change['id'],change['name']
        if identity in seen:
            raise ValueError('Duplicate portable binder member')
        seen.add(identity)
        before = change['beforeHash']
        if before is not None and (type(before) is not str or len(before) != 64):
            raise ValueError('Invalid script binder member anchor')
        current = owned.get(identity)
        after = change['after']
        if after is None:
            if current is not None and _sha(current.data) != before:
                raise ValueError(f'{identity[1]}: removing it would discard installed changes')
            owned.pop(identity,None)
            continue
        if type(after) is not dict or after.get('kind') not in ('esd','tae','bytes'):
            raise ValueError('Invalid script binder payload')
        if after['kind'] == 'esd':
            if set(after) != {'kind','edits'} or before is None or current is None:
                raise ValueError(f'{identity[1]}: the script member anchor is missing')
            payload = script_edits.materialize(current.data,after['edits'])
        elif after['kind'] == 'tae':
            if (set(after) != {'kind','edits'} or before is None or current is None
                    or not identity[1].lower().endswith('.tae')):
                raise ValueError(f'{identity[1]}: the animation member anchor is missing')
            payload = tae_merge.apply_edits(current.data,after['edits'])
        else:
            if (set(after) != {'kind','data'} or type(after['data']) is not str
                    or len(after['data']) > MAX_BYTES):
                raise ValueError('Invalid portable binder byte string')
            payload = base64.b64decode(after['data'],validate=True)
            if current is None:
                if before is not None:
                    raise ValueError(f'{identity[1]}: the member anchor is missing')
            elif _sha(current.data) not in (before,_sha(payload)):
                raise ValueError(f'{identity[1]}: the member anchor conflicts with installed data')
            if identity[1].lower().endswith('.esd'):
                script_edits.parse(payload)
            elif identity[1].lower().endswith('.tae'):
                TaeDocument(payload)
        owned[identity] = texts.Entry(identity[0],identity[1],0x40,payload)
    ordered = [owned[(entry.member_id,entry.name)] for entry in entries if (entry.member_id,entry.name) in owned]
    original_ids = {(entry.member_id,entry.name) for entry in entries}
    ordered.extend(owned[key] for key in sorted(owned.keys()-original_ids))
    original_names,current_names = {},{}
    for entry in entries:
        original_names[entry.name] = original_names.get(entry.name,0)+1
    for entry in ordered:
        current_names[entry.name] = current_names.get(entry.name,0)+1
        if current_names[entry.name] > max(1,original_names.get(entry.name,0)):
            raise ValueError(f'{entry.name}: a different installed member uses this name')
    if ordered == entries:
        return original
    ordered.sort(key=lambda entry:entry.member_id)
    result = texts.build_bnd3(plain,ordered)
    formats.members(result)
    return formats.deflate(original,result) if original.startswith(b'DCX\0') else result
