"""DS1R high/low map collision meshes, decoded without rewriting Havok data.

MSB collision instances supply the transform and hit filter. Each split
HKX binder supplies the triangles. MeshSubpartStorage stores four indices
per face; the fourth is face metadata, never another triangle corner.
"""
import base64
import functools
import math
import re
import struct
from pathlib import Path

from . import bhf, hkx
from .formats import FormatError, inflate

MESH_TYPE = 'hkpStorageExtendedMeshShape::MeshSubpartStorage'
MAX_VERTICES = 1_000_000


def _encode(values, dtype):
    return base64.b64encode(struct.pack(f'<{len(values)}{dtype}', *values)).decode('ascii')


def meshes(source):
    """Only read mesh storage items; physics objects can contain cycles."""
    data = inflate(source) if source[:4] == b'DCX\0' else bytes(source)
    if len(data) > hkx.MAX_FILE:
        raise FormatError('Collision geometry is too large')
    entries = hkx._peek_tables(data)
    reader = hkx._TagReader(data, 0, [], entries)
    result = []
    for index, item in enumerate(entries):
        if item['type'] is None or item['type'].name != MESH_TYPE:
            continue
        for mesh in reader.item_objects(index):
            vertices = mesh.get('vertices') or []
            indices = next((mesh.get(key) for key in ('indices8', 'indices16', 'indices32')
                            if mesh.get(key)), [])
            if not vertices or len(vertices) > MAX_VERTICES or len(indices) % 4:
                raise FormatError('Collision mesh has invalid vertices or faces')
            positions = [float(value) for vertex in vertices for value in vertex[:3]]
            if len(positions) != len(vertices) * 3 or not all(map(math.isfinite, positions)):
                raise FormatError('Collision mesh has invalid coordinates')
            triangles = [value for at in range(0, len(indices), 4) for value in indices[at:at+3]]
            if any(type(value) is not int or not 0 <= value < len(vertices) for value in triangles):
                raise FormatError('Collision face points outside its vertices')
            result.append({'positions': _encode(positions, 'f'),
                           'indices': _encode(triangles, 'I'), 'normals': '',
                           'verts': len(vertices), 'tris': len(triangles)//3,
                           'cull': False, 'mat_def': '', 'name': f'Collision {len(result)+1}'})
    if not result:
        raise FormatError('This collision has no supported triangle storage')
    return result


def preview_meshes(source):
    """Apply extended-mesh transforms while retaining older storage previews."""
    from .collision_write import CollisionDocument
    data = inflate(source) if source[:4] == b'DCX\0' else bytes(source)
    entries = hkx._peek_tables(data)
    names = [item['type'].name for item in entries if item['type'] is not None]
    if names.count('CustomParamStorageExtendedMeshShape') != 1 or names.count('hkpMoppCode') != 1:
        return meshes(source)
    document = CollisionDocument(source)
    return preview_document(document,document.meshes)


def preview_document(document, values):
    result = []
    for index,mesh in enumerate(values):
        vertices = document.transformed_vertices(index,mesh['vertices'])
        result.append({'positions':_encode([v for row in vertices for v in row],'f'),
            'indices':_encode([v for face in mesh['faces'] for v in face[:3]],'I'),
            'normals':'','verts':len(vertices),'tris':len(mesh['faces']),'cull':False,'mat_def':'',
            'name':f'Collision {index+1}'})
    return result


def source(game_root, project, map_name, model_name, layer):
    """High and low share one MSB instance, but have separate files."""
    if (not re.fullmatch(r'h[A-Za-z0-9_]+', model_name)
            or not re.fullmatch(r'm\d\d_\d\d_\d\d_\d\d\.msb',map_name)
            or layer not in ('collisionHigh','collisionLow')):
        raise FormatError('Invalid map collision model name')
    folder = Path('map') / Path(map_name).stem
    prefix = 'h' if layer == 'collisionHigh' else 'l'
    name = prefix + model_name[1:]
    roots = [Path(project)] if project is not None else []
    roots.append(Path(game_root))
    for root in roots:
        candidates = [root/folder/(stem+suffix) for stem in (name,name+'a'+Path(map_name).stem[1:3])
                      for suffix in ('.hkx.dcx','.hkx') if (root/folder/(stem+suffix)).is_file()]
        if len(candidates) > 1:
            raise FormatError(f'{model_name}: multiple loose collision files declare the same member')
        if candidates:
            return candidates[0],None,name
    archive = prefix + Path(map_name).stem[1:]
    header = next((root/folder/(archive+'.hkxbhd') for root in roots
                   if (root/folder/(archive+'.hkxbhd')).is_file()),None)
    if header is not None:
        relative = folder/(archive+'.hkxbdt')
        body = next((root/relative for root in roots if (root/relative).is_file()),None)
        if body is not None:
            return header,body,name
    return None


@functools.lru_cache(maxsize=32)
def _directory(path, stamp):
    if stamp[1] > 2*1024*1024:
        raise FormatError('Collision archive directory is too large')
    return bhf.parse_bhf(Path(path).read_bytes(), suffix='.hkx')


def geometry(game_root, project, map_name, model_name):
    result, notes = [], []
    for layer in ('collisionHigh','collisionLow'):
        try:
            located = source(game_root,project,map_name,model_name,layer)
            if located is None:
                raise FormatError('No collision file')
            header,body,name = located
            if body is None:
                if header.stat().st_size > hkx.MAX_FILE:
                    raise FormatError('Collision file is too large')
                raw = header.read_bytes()
            else:
                stat = header.stat()
                directory = _directory(str(header), (stat.st_mtime_ns, stat.st_size))
                # MSB uses h0000B2; binder paths add the area suffix A10.
                candidates = [key for key in directory if key == name.lower()
                              or key.startswith(name.lower() + 'a')]
                if len(candidates) != 1:
                    raise FormatError(f'{header.name} has no unique member for {name}')
                offset, size = directory[candidates[0]]
                raw = bhf.read_member(body, offset, size)
            result.extend(dict(mesh, layer=layer) for mesh in preview_meshes(raw))
        except (FormatError, OSError, ValueError, IndexError, TypeError, struct.error, RecursionError) as error:
            notes.append(f'{layer}: {error}')
    return {'meshes': result, 'notes': notes}
