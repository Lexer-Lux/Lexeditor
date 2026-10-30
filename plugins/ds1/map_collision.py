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
                           'cull': False, 'mat_def': '', 'name': f'Collision {len(result)+1}'})
    if not result:
        raise FormatError('This collision has no supported triangle storage')
    return result


def sources(game_root, project, map_name, model_name):
    """High and low share one MSB instance, but have separate files."""
    if not re.fullmatch(r'h[A-Za-z0-9_]+', model_name):
        raise FormatError('Invalid map collision model name')
    folder = Path('map') / Path(map_name).stem
    for prefix, layer in (('h', 'collisionHigh'), ('l', 'collisionLow')):
        name = prefix + model_name[1:]
        # A loose member in the mod is the editable override of a binder member.
        roots = [Path(project)] if project is not None else []
        roots.append(Path(game_root))
        loose = next((root / folder / (name + suffix) for root in roots
                      for suffix in ('.hkx.dcx', '.hkx')
                      if (root / folder / (name + suffix)).is_file()), None)
        if loose is not None:
            yield layer, loose, None, name
            continue
        archive = prefix + Path(map_name).stem[1:]
        header = next((root / folder / (archive + '.hkxbhd') for root in roots
                       if (root / folder / (archive + '.hkxbhd')).is_file()), None)
        if header is not None:
            relative = folder / (archive + '.hkxbdt')
            body = next((root / relative for root in roots if (root / relative).is_file()), None)
            if body is not None:
                yield layer, header, body, name


@functools.lru_cache(maxsize=32)
def _directory(path, stamp):
    if stamp[1] > 2*1024*1024:
        raise FormatError('Collision archive directory is too large')
    return bhf.parse_bhf(Path(path).read_bytes(), suffix='.hkx')


def geometry(game_root, project, map_name, model_name):
    result, notes = [], []
    for layer, header, body, name in sources(game_root, project, map_name, model_name):
        try:
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
            result.extend(dict(mesh, layer=layer) for mesh in meshes(raw))
        except (FormatError, OSError, ValueError, IndexError, TypeError, struct.error, RecursionError) as error:
            notes.append(f'{layer}: {error}')
    found = {mesh['layer'] for mesh in result}
    for layer in ('collisionHigh', 'collisionLow'):
        if layer not in found and not any(note.startswith(layer + ':') for note in notes):
            notes.append(f'{layer}: no collision file')
    return {'meshes': result, 'notes': notes}
