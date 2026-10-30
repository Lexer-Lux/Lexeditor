"""Combine collision edits by vertex/face, rebuilding the final index once."""
import json

from .collision_write import CollisionDocument
from . import collision_hull
from .formats import FormatError

FACE_ARRAYS = {'materialIndices':255, 'materialIndices16':65535}


def _metadata(document):
    ignored = {
        'hkpMoppCode': {'data'}, 'hkpMoppCode::CodeInfo': {'offset'},
        'CustomParamStorageExtendedMeshShape': {'aabbHalfExtents', 'aabbCenter', 'cachedNumChildShapes'},
        'hkpExtendedMeshShape::TrianglesSubpart': {'numVertices', 'numTriangleShapes'},
        'hkpStorageExtendedMeshShape::MeshSubpartStorage': {'vertices', 'indices8', 'indices16', 'indices32'},
        'hkpMeshShape::Subpart': {'numVertices','numTriangles'},
        'hkpStorageMeshShape::SubpartStorage': {'vertices','indices16','indices32'},
        'CustomMeshParameter': {'vertexDataBuffer'},
        'hkpConvexVerticesShape': {'rotatedVertices','numVertices','planeEquations','connectivity','aabbCenter','aabbHalfExtents'},
    }

    def strip(value):
        if isinstance(value, dict):
            omit = ignored.get(value.get('__class__'), set())
            return {key: (True if item and key in FACE_ARRAYS and value.get('__class__') in
                         ('hkpStorageExtendedMeshShape::MeshSubpartStorage','hkpStorageMeshShape::SubpartStorage')
                         else strip(item)) for key, item in value.items() if key not in omit}
        if isinstance(value, list):
            return [strip(item) for item in value]
        return value

    values = [document.reader.item_objects(1), document._value(document.shape)]
    if document.code is not None:
        values.append(document._value(document.code))
    return json.dumps(strip(values), sort_keys=True, separators=(',', ':'))


def _mesh(document, index):
    mesh = document.meshes[index]
    if document.kind == 'convex':
        return {'vertices':mesh['vertices'],'faces':mesh['faces'],'flags':[[] for _ in mesh['vertices']]}
    material = document._value(document.materials[index])
    stride, flags = material['vertexDataStride'], material['vertexDataBuffer'] or []
    if type(stride) is not int or not 0 <= stride <= 256 or len(flags) != len(mesh['vertices'])*stride:
        raise FormatError('Collision vertex metadata has an unsupported stride')
    result = {'vertices': mesh['vertices'], 'faces': mesh['faces'],
              'flags': [flags[i*stride:(i+1)*stride] for i in range(len(mesh['vertices']))]}
    storage = document._value(document.storage[index])
    for name,maximum in FACE_ARRAYS.items():
        if storage.get(name):
            values = storage[name]
            if len(values) != len(mesh['faces']) or any(type(v) is not int or not 0 <= v <= maximum for v in values):
                raise FormatError('Collision face metadata has an unsupported layout')
            result[name] = [[v] for v in values]
    return result


def _update(old, new):
    if set(old) != set(new):
        raise FormatError('Collision mesh metadata arrays do not match their source')
    # The fourth vertex component is preserved game metadata, not a spatial
    # coordinate. Match it explicitly when a topology edit adds a vertex.
    sources = []
    for index, vertex in enumerate(new['vertices']):
        if index < len(old['vertices']) and old['vertices'][index][3] == vertex[3]:
            sources.append(index)
        else:
            source = next((i for i, row in enumerate(old['vertices']) if row[3] == vertex[3]), None)
            if source is None:
                raise FormatError('Collision vertex metadata cannot be represented by this writer')
            sources.append(source)
    return {'vertices': [row[:3] for row in new['vertices']],
            'faces': [row[:3] for row in new['faces']],
            'vertex_sources': sources,
            'face_sources': [min(i, len(old['faces'])-1) for i in range(len(new['faces']))],
            'vertex_flags': new['flags'], 'face_tags': [row[3] for row in new['faces']],
            'face_data': {name:[row[0] for row in new[name]] for name in FACE_ARRAYS if name in new}}


def merge(original, variants, *, conflicts_only=False):
    """Return bytes and (part, owners) conflicts, in lowest-first load order.

    Independent edits to existing vertices/faces combine. A count-changing
    edit owns its whole subpart; unsupported physics changes own the member.
    These ownership boundaries are reported rather than silently discarding
    an earlier mod's incompatible geometry.
    """
    prepared = []
    for name,raw in variants:
        if raw != original:
            document = CollisionDocument(raw)
            prepared.append((name,document,[_mesh(document,i) for i in range(len(document.meshes))]))
    return merge_states(original,prepared,conflicts_only=conflicts_only)


def merge_states(original, prepared, *, conflicts_only=False):
    """Merge validated editable records; compile only the final combined mesh."""
    base = CollisionDocument(original)
    metadata = _metadata(base)
    if not prepared:
        return original, []
    if any(len(doc.meshes) != len(base.meshes) or _metadata(doc) != metadata or
           any(a['index_field'] != b['index_field'] for a, b in zip(base.meshes, doc.meshes))
           for _, doc, _ in prepared):
        owners = [name for name, _, _ in prepared]
        document,values = prepared[-1][1:]
        updates = {i:_update(_mesh(document,i),value) for i,value in enumerate(values)
                   if _mesh(document,i) != value}
        return (original if conflicts_only else document.export(updates)), [('Collision physics', owners)] if len(owners) > 1 else []
    originals = [_mesh(base, i) for i in range(len(base.meshes))]
    current = [{key: [list(row) for row in rows] for key, rows in mesh.items()} for mesh in originals]
    owners, structural, conflicts = {}, {}, {}

    def conflict(key, names):
        values = conflicts.setdefault(key, [])
        for name in names:
            if name not in values:
                values.append(name)

    for name, document, values in prepared:
        for index, before in enumerate(originals):
            after = values[index]
            if before == after:
                continue
            label = f'Collision mesh {index+1}'
            kinds = ('vertices','flags') if base.kind == 'convex' else tuple(before)
            if any(len(after[key]) != len(before[key]) for key in kinds):
                previous = [owner for key, owner in owners.items() if key[0] == index]
                if index in structural:
                    previous.append(structural[index])
                if current[index] != after and previous:
                    conflict(label, [*previous, name])
                current[index] = after
                structural[index] = name
                owners = {key: owner for key, owner in owners.items() if key[0] != index}
                continue
            if index in structural:
                # Applying an anchored field edit after a topology edit is
                # ambiguous. The later mod's subpart wins and says so.
                if current[index] != after:
                    conflict(label, [structural[index], name])
                current[index] = after
                structural[index] = name
                continue
            for kind in kinds:
                for row_id, (old, new) in enumerate(zip(before[kind], after[kind])):
                    for component, (old_value, new_value) in enumerate(zip(old, new)):
                        if old_value == new_value:
                            continue
                        key = (index, kind, row_id, component)
                        previous = owners.get(key)
                        if previous is not None and current[index][kind][row_id][component] != new_value:
                            conflict(f'{label}, {kind} {row_id}:{component}', [previous, name])
                        current[index][kind][row_id][component] = new_value
                        owners[key] = name
    if base.kind == 'convex':
        for index,mesh in enumerate(current):
            try:
                mesh['faces'] = collision_hull.build(mesh['vertices'])['faces']
            except FormatError:
                contributors = [name for name,_,values in prepared if values[index]['vertices'] != originals[index]['vertices']]
                if len(contributors) < 2:
                    raise
                conflict(f'Collision mesh {index+1}',contributors)
                mesh = next(values[index] for name,_,values in reversed(prepared) if name == contributors[-1])
                current[index] = mesh
    updates = {i: _update(before, after) for i, (before, after) in enumerate(zip(originals, current))
               if before != after}
    return original if conflicts_only else base.export(updates), list(conflicts.items())
