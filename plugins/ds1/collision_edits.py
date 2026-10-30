"""Portable collision member/vertex/face anchors over an installed split pair."""
import base64
import hashlib
import math

from . import collision_archive, collision_merge, hkx
from .collision_write import CollisionDocument
from .formats import FormatError

MAX_FIELDS = 1000000


def supported(relative):
    return collision_archive.header_for(relative) == relative


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _layout(document):
    return _hash(collision_merge._metadata(document).encode('utf-8'))


def _validate_mesh(mesh):
    if type(mesh) is not dict or set(mesh) != {'vertices', 'faces', 'flags'}:
        raise FormatError('Invalid portable collision mesh')
    for name, rows in mesh.items():
        if type(rows) is not list or not 0 < len(rows) <= 1000000:
            raise FormatError('Invalid portable collision element count')
        for row in rows:
            if (type(row) is not list or (name != 'flags' and len(row) != 4)
                    or (name == 'flags' and not 1 <= len(row) <= 256)):
                raise FormatError('Invalid portable collision element')
            if name == 'vertices':
                if any(type(v) not in (float, int) or not math.isfinite(v) for v in row):
                    raise FormatError('Invalid portable collision coordinate')
            elif any(type(v) is not int or v < 0 or v > (255 if name == 'flags' else 0xffffffff) for v in row):
                raise FormatError('Invalid portable collision metadata')
    if len(mesh['vertices']) != len(mesh['flags']) or len({len(row) for row in mesh['flags']}) != 1:
        raise FormatError('Portable collision vertex metadata does not match its vertices')
    if any(index >= len(mesh['vertices']) for face in mesh['faces'] for index in face[:3]):
        raise FormatError('Portable collision face points outside its vertices')


def _create_member(before, after):
    first, last = CollisionDocument(before), CollisionDocument(after)
    layout = _layout(first)
    if (len(first.meshes) != len(last.meshes) or layout != _layout(last)
            or any(a['index_field'] != b['index_field'] for a, b in zip(first.meshes, last.meshes))):
        return {'kind':'collisionRaw', 'beforeHash':_hash(before),
                'after':base64.b64encode(after).decode('ascii')}
    meshes = []
    for index in range(len(first.meshes)):
        old, new = collision_merge._mesh(first, index), collision_merge._mesh(last, index)
        _validate_mesh(old)
        _validate_mesh(new)
        if old == new:
            continue
        # Verify that the writer can represent the metadata carried by this
        # contribution. Geometry is not compiled again just to export it.
        collision_merge._update(old, new)
        if any(len(old[key]) != len(new[key]) for key in old):
            meshes.append({'id':index, 'before':old, 'after':new})
            continue
        fields = []
        for kind in old:
            for row, (a, b) in enumerate(zip(old[kind], new[kind])):
                for component, (left, right) in enumerate(zip(a, b)):
                    if left != right:
                        fields.append({'kind':kind, 'row':row, 'component':component,
                                       'before':left, 'after':right})
        if len(fields) > MAX_FIELDS:
            raise FormatError('Too many portable collision fields')
        meshes.append({'id':index, 'counts':[len(old['vertices']), len(old['faces']), len(old['flags'])],
                       'fields':fields})
    return {'kind':'collisionMesh', 'layout':layout, 'meshes':meshes} if meshes else None


def create(before_header, before_body, after_header, after_body):
    before = collision_archive.CollisionArchive(before_header, before_body)
    after = collision_archive.CollisionArchive(after_header, after_body)
    if before.identities() != after.identities():
        raise FormatError('Collision directory additions/removals need structural archive contributions')
    members = []
    for name, row in before.members.items():
        a, b = before.member(name), after.member(name)
        if a == b:
            continue
        edits = _create_member(a, b)
        if edits is not None:
            members.append({'name':name, 'id':row['id'], 'path':row['name'], 'edits':edits})
    return {'kind':'collision', 'members':members}


def _materialize_member(original, spec):
    document = CollisionDocument(original)
    if type(spec) is not dict:
        raise FormatError('Invalid portable collision member')
    if spec.get('kind') == 'collisionRaw':
        if (set(spec) != {'kind', 'beforeHash', 'after'} or type(spec['after']) is not str
                or type(spec['beforeHash']) is not str or len(spec['beforeHash']) != 64
                or any(c not in '0123456789abcdef' for c in spec['beforeHash'])
                or len(spec['after']) > 4*((hkx.MAX_FILE+2)//3)):
            raise FormatError('Invalid portable collision physics')
        after = base64.b64decode(spec['after'], validate=True)
        if len(after) > hkx.MAX_FILE:
            raise FormatError('Portable collision physics is too large')
        CollisionDocument(after)
        if _hash(original) not in (spec['beforeHash'], _hash(after)):
            raise FormatError('Collision physics conflicts with installed data')
        return after
    if (set(spec) != {'kind', 'layout', 'meshes'} or spec['kind'] != 'collisionMesh'
            or spec['layout'] != _layout(document) or type(spec['meshes']) is not list
            or len(spec['meshes']) > len(document.meshes)):
        raise FormatError('Portable collision layout does not match installed data')
    updates, seen = {}, set()
    for mesh in spec['meshes']:
        if (type(mesh) is not dict or type(mesh.get('id')) is not int or mesh['id'] in seen
                or not 0 <= mesh['id'] < len(document.meshes)):
            raise FormatError('Invalid portable collision mesh identity')
        index = mesh['id']
        seen.add(index)
        old = collision_merge._mesh(document, index)
        if set(mesh) == {'id', 'before', 'after'}:
            _validate_mesh(mesh['before'])
            _validate_mesh(mesh['after'])
            if old != mesh['before'] and old != mesh['after']:
                raise FormatError(f'Collision mesh {index+1}: structural edits conflict with installed data')
            new = mesh['after']
        elif (set(mesh) == {'id', 'counts', 'fields'} and type(mesh['counts']) is list
                and len(mesh['counts']) == 3 and all(type(v) is int for v in mesh['counts'])
                and mesh['counts'] == [len(old['vertices']), len(old['faces']), len(old['flags'])]
                and type(mesh['fields']) is list and len(mesh['fields']) <= MAX_FIELDS):
            new = {key:[list(row) for row in rows] for key, rows in old.items()}
            fields = set()
            for field in mesh['fields']:
                if (type(field) is not dict or set(field) != {'kind', 'row', 'component', 'before', 'after'}
                        or type(field['kind']) is not str or field['kind'] not in old
                        or type(field['row']) is not int or not 0 <= field['row'] < len(old[field['kind']])
                        or type(field['component']) is not int or not 0 <= field['component'] < len(old[field['kind']][field['row']])):
                    raise FormatError('Invalid portable collision field')
                key = (field['kind'], field['row'], field['component'])
                if key in fields:
                    raise FormatError('Duplicate portable collision field')
                fields.add(key)
                a, b = field['before'], field['after']
                if any(type(v) not in (float, int) or not math.isfinite(v) for v in (a,b)):
                    raise FormatError('Invalid portable collision field value')
                value = old[key[0]][key[1]][key[2]]
                if value not in (a,b):
                    raise FormatError(f'Collision mesh {index+1}, {key}: conflicts with installed data')
                new[key[0]][key[1]][key[2]] = b
        else:
            raise FormatError('Portable collision element counts do not match installed data')
        _validate_mesh(new)
        if old != new:
            updates[index] = collision_merge._update(old, new)
    return document.export(updates)


def materialize(header, body, spec):
    archive = collision_archive.CollisionArchive(header, body)
    if (type(spec) is not dict or set(spec) != {'kind','members'} or spec['kind'] != 'collision'
            or type(spec['members']) is not list or len(spec['members']) > collision_archive.MAX_MEMBERS):
        raise FormatError('Invalid portable split collision contribution')
    updates = {}
    for member in spec['members']:
        if (type(member) is not dict or set(member) != {'name','id','path','edits'}
                or type(member['name']) is not str or member['name'] not in archive.members
                or member['name'] in updates):
            raise FormatError('Invalid portable split collision member identity')
        row = archive.members[member['name']]
        if type(member['id']) is not int or member['id'] != row['id'] or member['path'] != row['name']:
            raise FormatError('Portable collision directory identity does not match installed data')
        updates[member['name']] = _materialize_member(archive.member(member['name']), member['edits'])
    return archive.replace(updates)


def validate_original(header, body, spec):
    """Only called after failure, to distinguish bad game data from bad mods."""
    archive = collision_archive.CollisionArchive(header, body)
    members = spec.get('members', []) if type(spec) is dict else []
    if type(members) is list:
        for row in members[:collision_archive.MAX_MEMBERS]:
            if type(row) is dict and type(row.get('name')) is str and row['name'] in archive.members:
                CollisionDocument(archive.member(row['name']))
