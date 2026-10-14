"""Map viewport data: placements with scales, model resolution, geometry.

A map references models by name; this module finds each model's bytes
(map pieces are standalone files, characters and objects live in
binders) and serves viewport-ready geometry. Read-only.
"""
import base64
import functools
import re
import struct
from pathlib import Path

from .flver import FlverDocument, FlverError
from .formats import FormatError, inflate, members
from .msb import MAP_DIR

MODEL_FILES = {1: ('obj', '.objbnd.dcx'), 2: ('chr', '.chrbnd.dcx'), 4: ('chr', '.chrbnd.dcx')}
MAX_GEOMETRY = 512 * 1024 * 1024


def _overlay(project, relative):
    """The mod's override when present, else the installed file."""
    if project is not None:
        own = Path(project) / relative
        if own.is_file():
            return own
    return None


def resolve_model(game_root, project, map_name, model):
    """Where a map model's geometry lives: ('piece', path),
    ('member', binder path, member name), or ('skip', reason)."""
    mtype, name = model['type'], model['name']
    if mtype == 0:
        folder = Path(map_name).stem
        for suffix in ('.flver.dcx', '.flver'):
            relative = Path('map') / folder / (name + suffix)
            own = _overlay(project, relative)
            if own is not None:
                return ('piece', own)
            live = Path(game_root) / relative
            if live.is_file():
                return ('piece', live)
        matches = sorted((Path(game_root) / 'map' / folder).glob(name + '*.flver.dcx'))
        if len(matches) == 1:
            return ('piece', matches[0])
        return ('skip', 'no model file')
    if mtype in MODEL_FILES:
        folder, suffix = MODEL_FILES[mtype]
        relative = Path(folder) / (name + suffix)
        own = _overlay(project, relative)
        if own is not None:
            return ('member', own, name + '.flver')
        live = Path(game_root) / relative
        if live.is_file():
            return ('member', live, name + '.flver')
        return ('skip', 'no binder')
    return ('skip', 'collision and navigation have no visible mesh')


def _read_member(binder, member):
    try:
        plain = binder.read_bytes()
    except OSError as error:
        raise FlverError(f'Cannot read {binder.name}') from error
    if plain[:4] == b'DCX\0':
        try:
            plain = inflate(plain)
        except FormatError as error:
            raise FlverError(f'Cannot open {binder.name}') from error
    try:
        found = members(plain)
    except FormatError as error:
        raise FlverError(f'Cannot open {binder.name}') from error
    names = found if isinstance(found, dict) else {m.name: m for m in found}
    if member not in names:
        raise FlverError(f'{binder.name} has no {member}')
    entry = names[member]
    if isinstance(entry, dict):
        offset, size = entry['offset'], entry['size']
    else:
        offset, size = entry.offset, entry.size
    if offset + size > len(plain):
        raise FlverError(f'{member} runs past the end of {binder.name}')
    return plain[offset:offset + size]


@functools.lru_cache(maxsize=64)
def _cached_geometry(kind, location, member, stamp, skin=False):
    if kind == 'piece':
        try:
            raw = Path(location).read_bytes()
        except OSError as error:
            raise FlverError(f'Cannot read {Path(location).name}') from error
    else:
        raw = _read_member(Path(location), member)
    if len(raw) > MAX_GEOMETRY:
        raise FlverError('Model file is too large')
    return _encode(FlverDocument(raw), skin)


def _encode_skin(doc, mesh):
    """Per-vertex skinning resolved to model bone indices. Vertex bone
    ids index the mesh's own bone list; a mesh without skin members or
    without a list hangs off its default bone. Weights are normalized
    so no vertex collapses."""
    count = len(mesh['positions'])
    if not mesh['bone_ids'] and not mesh['weights']:
        mesh = dict(mesh, bone_ids=[(0, 0, 0, 0)] * count,
                    weights=[(1.0, 0.0, 0.0, 0.0)] * count, bone_list=[])
    if len(mesh['bone_ids']) != count or len(mesh['weights']) != count:
        raise FlverError('Skin arrays do not match the vertices')
    ids, weights = [], []
    for local, raw in zip(mesh['bone_ids'], mesh['weights']):
        if mesh['bone_list']:
            if any(part >= len(mesh['bone_list']) for part in local):
                raise FlverError('A vertex names a bone outside its mesh')
            ids.extend(mesh['bone_list'][part] for part in local)
        else:
            ids.extend([mesh['default_bone']] * 4)
        total = sum(raw)
        weights.extend([part / total for part in raw] if total else [1.0, 0.0, 0.0, 0.0])
    if any(bone >= len(doc.bones) for bone in ids):
        raise FlverError('A vertex names a bone outside its model')
    return {'skin_ids': base64.b64encode(struct.pack('<%dI' % len(ids), *ids)).decode('ascii'),
            'skin_weights': base64.b64encode(
                struct.pack('<%df' % len(weights), *weights)).decode('ascii')}


def _encode(doc, skin=False):
    meshes = []
    for index in range(len(doc.meshes)):
        mesh = doc.mesh_data(index)
        positions = [c for vertex in mesh['positions'] for c in vertex]
        normals = [c for vertex in mesh['normals'] for c in vertex]
        if len(normals) // 3 != len(positions) // 3:
            normals = [0.0, 1.0, 0.0] * (len(positions) // 3)
        # DS1 winds faces clockwise (DirectX front); WebGL wants
        # counter-clockwise. Measured on the real Undead Burg: 96.7% of
        # triangles disagree with their vertex normals before this swap.
        flat = [i for triangle in mesh['triangles']
                for i in (triangle[0], triangle[2], triangle[1])]
        entry = {
            'positions': base64.b64encode(struct.pack('<%df' % len(positions), *positions)).decode('ascii'),
            'normals': base64.b64encode(struct.pack('<%df' % len(normals), *normals)).decode('ascii'),
            'indices': base64.b64encode(struct.pack('<%dI' % len(flat), *flat)).decode('ascii'),
            'verts': len(positions) // 3, 'tris': len(flat) // 3,
            'material': mesh['material'], 'cull': mesh['cull'],
            'mat_def': mesh['mat_def'].rsplit('/', 1)[-1].rsplit('\\', 1)[-1],
        }
        if skin:
            entry.update(_encode_skin(doc, mesh))
        meshes.append(entry)
    return {'meshes': meshes, 'notes': doc.notes}


def model_geometry(game_root, project, map_name, model):
    """Base64 float32 geometry for one model, cached by file stamp."""
    resolved = resolve_model(game_root, project, map_name, model)
    if resolved[0] == 'skip':
        raise FlverError(resolved[1])
    kind, location = resolved[0], resolved[1]
    member = resolved[2] if kind == 'member' else ''
    try:
        stat = Path(location).stat()
    except OSError as error:
        raise FlverError(f'Cannot read {Path(location).name}') from error
    return _cached_geometry(kind, str(location), member, (stat.st_mtime_ns, stat.st_size))


CHR_ID = re.compile(r'^[A-Za-z0-9_]+$')


def resolve_chr(game_root, project, chr_id):
    """Where a character model's geometry lives: ('member', binder path,
    member name), or ('skip', reason). The ID is a bare binder stem, so
    anything outside letters, digits and underscore is rejected."""
    if not CHR_ID.match(chr_id or ''):
        return ('skip', 'unknown character model')
    relative = Path('chr') / (chr_id + '.chrbnd.dcx')
    own = _overlay(project, relative)
    if own is not None:
        return ('member', own, chr_id + '.flver')
    live = Path(game_root) / relative
    if live.is_file():
        return ('member', live, chr_id + '.flver')
    return ('skip', 'no binder')


def chr_geometry(game_root, project, chr_id, skin=False):
    """Base64 float32 geometry for one character model, cached by file
    stamp, with per-vertex skinning when playback needs it."""
    resolved = resolve_chr(game_root, project, chr_id)
    if resolved[0] == 'skip':
        raise FlverError(resolved[1])
    _kind, location, member = resolved
    try:
        stat = Path(location).stat()
    except OSError as error:
        raise FlverError(f'Cannot read {Path(location).name}') from error
    return _cached_geometry('member', str(location), member,
                            (stat.st_mtime_ns, stat.st_size), skin)


def chr_dummies(game_root, project, chr_id):
    """Dummy points and mesh inventory for one character model."""
    resolved = resolve_chr(game_root, project, chr_id)
    if resolved[0] == 'skip':
        raise FlverError(resolved[1])
    raw = _read_member(Path(resolved[1]), resolved[2])
    doc = FlverDocument(raw)
    return {'meshes': len(doc.meshes), 'bones': len(doc.bones),
            'dummies': [{'id': dummy['ref_id'],
                         'pos': [float(axis) for axis in dummy['pos']],
                         'bone': dummy['attach_bone']}
                        for dummy in doc.dummies]}


PART_PREFIXES = {1: 'AM', 2: 'BD', 5: 'HD', 6: 'LG'}
PART_VARIANTS = {0: 'A', 1: 'M', 2: 'F', 4: 'A', 5: 'E'}


def part_candidates(table, category, gender, model_id):
    """Binder stems a row's model may live under: [(stem, variant)],
    or (None, reason). Weapons share one unisex binder; armor names its
    piece and fit. Dual-gender armor ships two binders (male first); the
    reader picks which to preview.
    """
    if table == 'EquipParamWeapon':
        return ([(f'WP_A_{model_id:04d}', None)], None)
    prefix = PART_PREFIXES.get(category)
    if prefix is None:
        return (None, 'this armor piece has no wearable model')
    if gender == 3:
        return ([(f'{prefix}_M_{model_id:04d}', 'M'),
                 (f'{prefix}_F_{model_id:04d}', 'F')], None)
    variant = PART_VARIANTS.get(gender)
    if variant is None:
        return (None, 'this armor piece has no wearable model')
    return ([(f'{prefix}_{variant}_{model_id:04d}', None)], None)


def _part_member(binder, stem):
    """The binder member holding the model: the stem's own mesh, else
    the first mesh in the binder.
    """
    try:
        plain = binder.read_bytes()
    except OSError as error:
        raise FlverError(f'Cannot read {binder.name}') from error
    if plain[:4] == b'DCX\0':
        try:
            plain = inflate(plain)
        except FormatError as error:
            raise FlverError(f'Cannot open {binder.name}') from error
    try:
        found = members(plain)
    except FormatError as error:
        raise FlverError(f'Cannot open {binder.name}') from error
    names = list(found) if isinstance(found, dict) else [m.name for m in found]
    wanted = stem + '.flver'
    if wanted in names:
        return wanted
    meshes = sorted(name for name in names if name.lower().endswith('.flver'))
    if not meshes:
        raise FlverError(f'{binder.name} holds no model mesh')
    return meshes[0]


def resolve_part(game_root, project, stem):
    """Where a weapon or armor model's geometry lives: ('member',
    binder path, member name), or ('skip', reason). The stem is a bare
    binder name, so anything outside letters, digits and underscore is
    rejected.
    """
    if not CHR_ID.match(stem or ''):
        return ('skip', 'unknown part model')
    relative = Path('parts') / (stem + '.partsbnd.dcx')
    own = _overlay(project, relative)
    live = own if own is not None else Path(game_root) / relative
    if not live.is_file():
        return ('skip', 'no binder')
    try:
        member = _part_member(live, stem)
    except FlverError as error:
        return ('skip', str(error))
    return ('member', live, member)


def part_geometry(game_root, project, stem):
    """Base64 float32 geometry for one weapon or armor model, cached by
    file stamp.
    """
    resolved = resolve_part(game_root, project, stem)
    if resolved[0] == 'skip':
        raise FlverError(resolved[1])
    _kind, location, member = resolved
    try:
        stat = Path(location).stat()
    except OSError as error:
        raise FlverError(f'Cannot read {Path(location).name}') from error
    return _cached_geometry('member', str(location), member,
                            (stat.st_mtime_ns, stat.st_size))


def part_view(game_root, project, stem):
    """Availability and mesh inventory for one weapon or armor model."""
    resolved = resolve_part(game_root, project, stem)
    if resolved[0] == 'skip':
        return {'stem': stem, 'available': False, 'reason': resolved[1]}
    raw = _read_member(Path(resolved[1]), resolved[2])
    doc = FlverDocument(raw)
    return {'stem': stem, 'available': True, 'meshes': len(doc.meshes),
            'file': Path(resolved[1]).name}


def map_view(mapstore, map_name):
    """Placements and model availability for the viewport."""
    doc = mapstore.get(map_name)
    models = {}
    for model in doc.models:
        resolved = resolve_model(mapstore.game_root, mapstore.project, map_name, model)
        models[model['name']] = {'type': model['type'], 'available': resolved[0] != 'skip',
                                  'reason': '' if resolved[0] != 'skip' else resolved[1]}
    parts = []
    for part in doc.view_parts():
        parts.append({'key': f"{part['type']}:{part['id']}", 'name': part['name'],
                      'kind': part['kind'], 'model': part['model'],
                      'pos': list(part['pos']), 'rot': list(part['rot']),
                      'scale': list(part['scale'])})
    return {'map': map_name, 'models': models, 'parts': parts}
