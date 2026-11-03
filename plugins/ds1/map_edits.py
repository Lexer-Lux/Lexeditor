"""Portable MSB field anchors, using the map adapter's editable merge units."""
import base64
import hashlib

from .msb import MAP_DIR, MAX_FILE, MsbDocument

MAX_FIELDS = 100000


def supported(relative):
    return relative.parent == MAP_DIR and relative.suffix == '.msb'


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _layout(document):
    data = bytearray(document.plain)
    for _key,_field,at,size,_label,_name in document.merge_units():
        data[at:at+size] = bytes(size)
    return _sha(data)


def create(relative,before,after):
    first,last = MsbDocument(before,relative.name),MsbDocument(after,relative.name)
    if len(before) != len(after) or _layout(first) != _layout(last):
        # Structural changes cannot be replayed through field offsets. Keep
        # an exact anchor rather than treating unrelated installed edits as
        # reversions contributed by this mod.
        return {'kind':'map','beforeHash':_sha(before),'after':base64.b64encode(after).decode('ascii')}
    fields = [{'offset':at,'before':before[at:at+size].hex(),'after':after[at:at+size].hex()}
              for _key,_field,at,size,_label,_name in first.merge_units()
              if before[at:at+size] != after[at:at+size]]
    if len(fields)>MAX_FIELDS:
        raise ValueError('Too many portable map fields')
    return {'kind':'map','layout':_layout(first),'fields':fields}


def materialize(relative,original,spec):
    document = MsbDocument(original,relative.name)
    if type(spec) is not dict or spec.get('kind') != 'map':
        raise ValueError('Invalid portable map contribution')
    if set(spec) == {'kind','beforeHash','after'}:
        if type(spec['after']) is not str or len(spec['after'])>4*((MAX_FILE+2)//3):
            raise ValueError('Portable map exceeds its size limit')
        data = base64.b64decode(spec['after'],validate=True)
        if len(data)>MAX_FILE:
            raise ValueError('Portable map exceeds its size limit')
        MsbDocument(data,relative.name)
        if _sha(original) not in (spec['beforeHash'],_sha(data)):
            raise ValueError(f'{relative.name}: structural map changes conflict with installed data')
        return data
    if (set(spec) != {'kind','layout','fields'} or spec['layout'] != _layout(document)
            or type(spec['fields']) is not list or len(spec['fields'])>MAX_FIELDS):
        raise ValueError(f'{relative.name}: portable map layout does not match installed data')
    units = {at:(size,label,name) for _key,_field,at,size,label,name in document.merge_units()}
    result,seen = bytearray(original),set()
    for field in spec['fields']:
        if (type(field) is not dict or set(field) != {'offset','before','after'}
                or type(field['offset']) is not int or field['offset'] not in units or field['offset'] in seen):
            raise ValueError('Invalid portable map field')
        at = field['offset'];seen.add(at)
        size,label,name = units[at]
        if any(type(field[key]) is not str or len(field[key]) != size*2 for key in ('before','after')):
            raise ValueError('Invalid portable map field bytes')
        before,after = bytes.fromhex(field['before']),bytes.fromhex(field['after'])
        if original[at:at+size] not in (before,after):
            raise ValueError(f'{relative.name} {name}, {label}: conflicts with installed data')
        result[at:at+size] = after
    MsbDocument(bytes(result),relative.name)
    return bytes(result)
