"""Map viewport data: placements with scales, model resolution, geometry.

A map references models by name; this module finds each model's bytes
(map pieces are standalone files, characters and objects live in
binders) and serves viewport-ready geometry. Read-only.
"""
import base64
import functools
import hashlib
import io
import re
import struct
from collections import OrderedDict
from pathlib import Path

from .assets import (AssetError, COLLISION_EXTENSIONS, MODEL_KINDS, check_relative, dds_info,
                       parse_tpf)
from .bhf import BhfError, inflate_member, parse_bhf
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


def _read_flver(kind, location, member):
    if kind == 'piece':
        try:
            raw = Path(location).read_bytes()
        except OSError as error:
            raise FlverError(f'Cannot read {Path(location).name}') from error
    else:
        raw = _read_member(Path(location), member)
    if len(raw) > MAX_GEOMETRY:
        raise FlverError('Model file is too large')
    return raw


DIFFUSE_TYPES = frozenset({'g_diffuse', 'gdiffuse'})
LIGHTMAP_TYPES = frozenset({'g_lightmap'})
MAX_TEXTURE_PIXELS = 16 * 1024 * 1024
TEXTURE_PREVIEW_CAP = 1024
MAP_TEXTURE_CAP = 256
STRIP_TEXTURE_CAP = 256
PNG_CACHE_SIZE = 128
MEMBER_CACHE_SIZE = 64


def _diffuse_name(material):
    """The material's diffuse texture stem (LG_M_9240.tga -> LG_M_9240),
    or None when it names none."""
    for texture in material.get('textures', []):
        path = texture.get('path') or ''
        if texture.get('type', '').lower() in DIFFUSE_TYPES and path:
            stem = path.replace('\\', '/').rsplit('/', 1)[-1]
            return stem.rsplit('.', 1)[0] if '.' in stem else stem
    return None


def _lightmap_name(material):
    """The material's baked-light texture stem, or None when it names
    none. Same stem rule as the diffuse; the resolver treats both
    alike."""
    for texture in material.get('textures', []):
        path = texture.get('path') or ''
        if texture.get('type', '').lower() in LIGHTMAP_TYPES and path:
            stem = path.replace('\\', '/').rsplit('/', 1)[-1]
            return stem.rsplit('.', 1)[0] if '.' in stem else stem
    return None


def _binder_plain(location):
    """A binder's inflated bytes, or None when it cannot be read."""
    try:
        plain = Path(location).read_bytes()
    except OSError:
        return None
    if plain[:4] == b'DCX\0':
        try:
            plain = inflate(plain)
        except FormatError:
            return None
    return plain


def _stamp(location):
    """A file's (mtime, size) stamp, or None when it cannot be statted."""
    try:
        stat = Path(location).stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


@functools.lru_cache(maxsize=8)
def _cached_binder_plain(location, stamp):
    """A binder's inflated bytes, shared across a map's models. Every
    model resolved its textures from the same containers, and
    re-reading them per model made big maps open slowly. The file
    stamp is part of the key, so a rebuilt mod still reloads.
    Bounded small: binders are the biggest files the viewport
    touches."""
    return _binder_plain(location)


def _shared_binder_plain(location):
    stamp = _stamp(location)
    if stamp is None:
        return _binder_plain(location)
    return _cached_binder_plain(str(location), stamp)


@functools.lru_cache(maxsize=256)
def _cached_bhf_table(location, stamp):
    """One texture header's parsed table, shared across a map's
    models. Headers are small; the stamp keys a rebuild. Sized past
    a full tileset sweep (53 headers on the vanilla game) so one
    map's models stop evicting each other's tables."""
    return parse_bhf(Path(location).read_bytes())


def _split_tables(kind, location, member, game_root, project, area=None):
    """[(label, member table, data path)] plus notes: a character
    binder's companion archive, plus the map area's archives for
    pieces and for binders placed on a map (objects keep their
    textures with the map, not in their own binder). Maps borrow
    across tilesets - Kiln pieces wear m10 shared textures - so
    when an area is in play every other tileset is a fallback
    after the area's own archives. A companion header without its
    data file is reported once, here."""
    tables, notes = [], []
    areas = []
    if kind == 'member':
        binder = Path(location)
        if binder.name.lower().endswith('.chrbnd.dcx'):
            stem = binder.name[:-len('.chrbnd.dcx')]
            plain = _shared_binder_plain(location)
            names = {}
            if plain is not None:
                try:
                    found = members(plain)
                except FormatError:
                    found = None
                if found is not None:
                    names = found if isinstance(found, dict) else {m.name: m for m in found}
            wanted = stem + '.chrtpfbhd'
            if wanted in names:
                entry = names[wanted]
                if isinstance(entry, dict):
                    offset, size = entry['offset'], entry['size']
                else:
                    offset, size = entry.offset, entry.size
                bdt = binder.parent / (stem + '.chrtpfbdt')
                if not bdt.is_file():
                    notes.append(f'{bdt.name}: companion texture archive not found')
                else:
                    try:
                        tables.append((wanted, parse_bhf(plain[offset:offset + size]), bdt))
                    except BhfError as error:
                        notes.append(f'{wanted}: {error}')
        if area:
            areas.append(area)
    else:
        areas.append(Path(location).parent.name.split('_')[0])
    roots = []
    for root in (project, game_root):
        if root and str(root) not in roots:
            roots.append(str(root))
    searched = set()
    for want in areas:
        for root in roots:
            for bhd in sorted((Path(root) / 'map' / want).glob('*.tpfbhd')):
                searched.add(str(bhd))
                bdt = bhd.with_suffix('.tpfbdt')
                if not bdt.is_file():
                    notes.append(f'{bdt.name}: companion texture archive not found')
                    continue
                try:
                    stamp = _stamp(bhd)
                    table = (_cached_bhf_table(str(bhd), stamp) if stamp is not None
                             else parse_bhf(bhd.read_bytes()))
                    tables.append((bhd.name, table, bdt))
                except (BhfError, OSError) as error:
                    notes.append(f'{bhd.name}: {error}')
    if areas:
        for root in roots:
            pattern = Path(root) / 'map'
            if not pattern.is_dir():
                continue
            for bhd in sorted(pattern.glob('m??/*.tpfbhd')):
                if str(bhd) in searched:
                    continue
                searched.add(str(bhd))
                label = f'{bhd.parent.name}/{bhd.name}'
                bdt = bhd.with_suffix('.tpfbdt')
                if not bdt.is_file():
                    notes.append(f'{label}: companion texture archive not found')
                    continue
                try:
                    stamp = _stamp(bhd)
                    table = (_cached_bhf_table(str(bhd), stamp) if stamp is not None
                             else parse_bhf(bhd.read_bytes()))
                    tables.append((label, table, bdt))
                except (BhfError, OSError) as error:
                    notes.append(f'{label}: {error}')
    return tables, notes


def _tileset_singles(kind, location, game_root, project, area=None):
    """(label, TPF bytes) from single-file tileset archives: the map's
    own tileset first, then every other tileset. A few props (m10's
    ivy, its pot) ship in m10_9999.tpf.dcx instead of the split
    archives. Reads lazily so the scan stops at the first hit."""
    areas = []
    if kind == 'member':
        if area:
            areas.append(area)
    else:
        areas.append(Path(location).parent.name.split('_')[0])
    if not areas:
        return
    roots = []
    for root in (project, game_root):
        if root and str(root) not in roots:
            roots.append(str(root))
    seen = set()
    for want in areas:
        for root in roots:
            for single in sorted((Path(root) / 'map' / want).glob('*.tpf*')):
                if single.suffix == '.dcx':
                    stem = single.name[:-len('.tpf.dcx')] if single.name.endswith('.tpf.dcx') else None
                else:
                    stem = single.name[:-len('.tpf')] if single.name.endswith('.tpf') else None
                if stem is None or str(single) in seen:
                    continue
                seen.add(str(single))
                try:
                    blob = single.read_bytes()
                except OSError:
                    continue
                if blob[:4] == b'DCX\0':
                    try:
                        blob = inflate(blob)
                    except FormatError:
                        continue
                yield f'{single.parent.name}/{single.name}', blob
    for root in roots:
        pattern = Path(root) / 'map'
        if not pattern.is_dir():
            continue
        for single in sorted(pattern.glob('m??/*.tpf')) + sorted(pattern.glob('m??/*.tpf.dcx')):
            if str(single) in seen:
                continue
            seen.add(str(single))
            try:
                blob = single.read_bytes()
            except OSError:
                continue
            if blob[:4] == b'DCX\0':
                try:
                    blob = inflate(blob)
                except FormatError:
                    continue
            yield f'{single.parent.name}/{single.name}', blob


CHR_STEM = re.compile(r'^c(\d+)', re.IGNORECASE)


def _sibling_binder(game_root, project, name):
    """The binder a cross-referenced character texture names: c2510's
    cloak texture is c2519's, and c2790's gear textures are c2799's,
    kept in that character's binder. None when the name does not
    start with a character stem or its binder is not installed."""
    match = CHR_STEM.match(name or '')
    if match is None:
        return None
    relative = Path('chr') / ('c' + match.group(1) + '.chrbnd.dcx')
    for root in (project, game_root):
        if not root:
            continue
        binder = Path(root) / relative
        if binder.is_file():
            return binder
    return None


def _tpf_sources(kind, location, member):
    """(label, TPF bytes) candidates: the binder's same-stem TPF first,
    then its other TPFs; a standalone flver's same-stem sidecars."""
    if kind == 'member':
        plain = _shared_binder_plain(location)
        if plain is None:
            return
        try:
            found = members(plain)
        except FormatError:
            return
        names = found if isinstance(found, dict) else {m.name: m for m in found}
        stem = Path(member).stem + '.tpf'
        ordered = ([stem] if stem in names else []) + sorted(
            name for name in names if name.lower().endswith('.tpf') and name != stem)
        for name in ordered:
            entry = names[name]
            if isinstance(entry, dict):
                offset, size = entry['offset'], entry['size']
            else:
                offset, size = entry.offset, entry.size
            if offset + size <= len(plain):
                yield name, plain[offset:offset + size]
        return
    name = Path(location).name
    for tail in ('.flver.dcx', '.flver'):
        if name.endswith(tail):
            stem = name[:-len(tail)]
            break
    else:
        stem = Path(location).stem
    for suffix in ('.tpf.dcx', '.tpf'):
        sidecar = Path(location).parent / (stem + suffix)
        if not sidecar.is_file():
            continue
        try:
            blob = sidecar.read_bytes()
        except OSError:
            continue
        if blob[:4] == b'DCX\0':
            try:
                blob = inflate(blob)
            except FormatError:
                continue
        yield sidecar.name, blob


_PNG_CACHE = OrderedDict()
_MEMBER_CACHE = OrderedDict()


def _cached_member(bdt, offset, size):
    """One archive member's inflated bytes, shared across a map's
    models. Every model pulled the same tileset archives through
    zlib again; the data-file stamp is part of the key, so a
    rebuilt mod still reloads. Bounded: members are small
    (median 85KB on the Depths) but many."""
    key = (str(bdt), offset, size, _stamp(bdt))
    hit = _MEMBER_CACHE.get(key)
    if hit is not None:
        _MEMBER_CACHE.move_to_end(key)
        return hit
    blob = inflate_member(bdt, offset, size)
    _MEMBER_CACHE[key] = blob
    while len(_MEMBER_CACHE) > MEMBER_CACHE_SIZE:
        _MEMBER_CACHE.popitem(last=False)
    return blob


def _dds_png(blob, cap=TEXTURE_PREVIEW_CAP):
    """A DDS blob as PNG bytes, capped for previews. Decodes are
    cached by content hash: one map shows the same texture on many
    models, and decoding it once keeps map opens fast."""
    info = dds_info(blob)
    if info['width'] * info['height'] > MAX_TEXTURE_PIXELS:
        raise AssetError('That texture is too large to preview')
    key = (hashlib.blake2b(bytes(blob), digest_size=16).digest(), cap)
    hit = _PNG_CACHE.get(key)
    if hit is not None:
        _PNG_CACHE.move_to_end(key)
        return hit
    from PIL import Image
    try:
        with Image.open(io.BytesIO(bytes(blob))) as image:
            image.load()
            if max(image.size) > cap:
                image.thumbnail((cap, cap))
            out = io.BytesIO()
            image.save(out, format='PNG')
            png = out.getvalue()
    except Exception as error:
        raise AssetError(f'That texture cannot be previewed: {error}') from error
    _PNG_CACHE[key] = png
    while len(_PNG_CACHE) > PNG_CACHE_SIZE:
        _PNG_CACHE.popitem(last=False)
    return png


def _resolve_textures(kind, location, member, needed, game_root=None, project=None,
                      cap=TEXTURE_PREVIEW_CAP, area=None, with_meta=False):
    """Diffuse PNGs by material name: the model's own textures, then
    its companion and area archives, then a sibling character's
    binder when the name is a character stem. Anything missing or
    undecodable stays out (the mesh renders gray, as before) with a
    note saying why. with_meta also returns per-texture source
    names and sizes for the Models strip."""
    found, notes, missing = {}, [], list(needed)
    meta = {} if with_meta else None
    saw = False

    def take(label, blob, names):
        """Decode the wanted names from one TPF's bytes."""
        nonlocal saw
        if not names:
            return
        saw = True
        try:
            textures = parse_tpf(blob)
        except AssetError as error:
            notes.append(f'{label}: {error}')
            return
        by_name = {}
        for entry in textures:
            by_name.setdefault(entry['name'].lower(), entry)
        for name in list(names):
            entry = by_name.get(name.lower())
            if entry is None:
                continue
            raw = blob[entry['offset']:entry['offset'] + entry['size']]
            try:
                png = _dds_png(raw, cap)
            except (AssetError, FlverError, FormatError, ValueError,
                    struct.error, KeyError, OSError) as error:
                notes.append(f'{name}: {error}')
                continue
            found[name] = png
            missing.remove(name)
            if meta is not None:
                info = dds_info(raw)
                meta[name] = {'name': entry['name'], 'width': info['width'],
                              'height': info['height'], 'format': info['format']}

    for label, blob in _tpf_sources(kind, location, member):
        if not missing:
            break
        take(label, blob, missing)
    if missing:
        for name in list(missing):
            binder = _sibling_binder(game_root, project, name)
            if binder is None:
                continue
            stem = binder.name.split('.')[0]
            for label, blob in _tpf_sources('member', str(binder), stem + '.flver'):
                take(f'{binder.name}:{label}', blob, [name])
                if name in found:
                    break
    if missing:
        tables, split_notes = _split_tables(kind, location, member, game_root, project, area)
        notes.extend(split_notes)
        for name in list(missing):
            binder = _sibling_binder(game_root, project, name)
            if binder is None:
                continue
            more, more_notes = _split_tables('member', str(binder), '', game_root, project)
            notes.extend(more_notes)
            tables.extend(more)
        if tables:
            saw = True

        for name in list(missing):
            for label, table, bdt in tables:
                slot = table.get(name.lower())
                if slot is None:
                    continue
                try:
                    blob = _cached_member(bdt, slot[0], slot[1])
                except BhfError as error:
                    notes.append(f'{label}: {error}')
                    continue
                take(label, blob, [name])
                if name in found:
                    break
    if missing:
        for label, blob in _tileset_singles(kind, location, game_root, project, area):
            if not missing:
                break
            take(label, blob, missing)
    if not saw:
        notes.append('no texture container found')
    for name in missing:
        notes.append(f'{name}: no texture with that name')
    if with_meta:
        return found, notes, meta
    return found, notes


def model_strip_pngs(game_root, project, relative, side, member, wanted):
    """Downscaled companion PNGs for one Models-tab file's strip.

    ({stem: png bytes}, {stem: source name and size}) for the preview
    member's texture maps, resolved exactly like the drawer's. Empty
    when the file holds no previewable member.
    """
    resolved = resolve_asset_model(game_root, project, check_relative(relative),
                                   side, member or None)
    if resolved[0] == 'skip':
        return {}, {}
    kind, location = resolved[0], resolved[1]
    shown = resolved[2] if kind == 'member' else ''
    area = None
    parts = check_relative(relative).parts
    if len(parts) > 1 and parts[0] == 'map':
        area = parts[1].split('_')[0] or None
    found, _notes, meta = _resolve_textures(kind, str(location), shown, list(wanted),
                                            game_root, project, STRIP_TEXTURE_CAP, area,
                                            with_meta=True)
    return found, meta


def _textured(kind, location, member, stamp, skin, game_root, project, cap, area=None):
    encoded = _encode(FlverDocument(_read_flver(kind, location, member)), skin, True)
    needed = sorted({name for mesh in encoded['meshes']
                     for name in (mesh.get('map'), mesh.get('light')) if name})
    if not needed:
        encoded['textures'] = {}
        return encoded
    found, notes = _resolve_textures(kind, location, member, needed, game_root, project, cap,
                                     area)
    encoded['textures'] = found
    encoded['notes'].extend(notes)
    return encoded


def _payload(cached, known=None):
    """A cached geometry with its PNGs base64-encoded for JSON. The
    cache keeps the shared PNG bytes; only the copy goes over the wire.
    texture_ids tags each PNG by content, and known skips blobs the
    client already holds (a map repeats its textures per model)."""
    nave = known or frozenset()
    payload = dict(cached)
    ids, textures = {}, {}
    for name, png in cached.get('textures', {}).items():
        digest = hashlib.blake2b(png, digest_size=16).hexdigest()
        ids[name] = digest
        if digest not in nave:
            textures[name] = base64.b64encode(png).decode('ascii')
    payload['textures'] = textures
    payload['texture_ids'] = ids

    return payload


@functools.lru_cache(maxsize=16)
def _cached_textured(kind, location, member, stamp, skin=False, game_root=None, project=None):
    """Textured geometry for the model drawer: UVs, per-mesh diffuse
    names and the decoded PNGs. Bounded small against the drawer's
    one-model-at-a-time use."""
    return _textured(kind, location, member, stamp, skin, game_root, project,
                     TEXTURE_PREVIEW_CAP)


@functools.lru_cache(maxsize=128)
def _cached_map(kind, location, member, stamp, game_root=None, project=None, area=None):
    """Textured geometry for the map viewport: room for a map's models
    at a small texture cap, since maps show acres at a time. The area
    is part of the key: one binder's objects wear different textures
    on different maps."""
    return _textured(kind, location, member, stamp, False, game_root, project,
                     MAP_TEXTURE_CAP, area)


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


def _encode(doc, skin=False, textured=False):
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
        if textured:
            uvs = [c for vertex in mesh['uvs'] for c in vertex]
            ok = bool(uvs) and len(mesh['uvs']) == len(mesh['positions'])
            packed = struct.pack('<%df' % len(uvs), *uvs) if ok else b''
            entry['uv'] = base64.b64encode(packed).decode('ascii')
            uvs2 = [c for vertex in mesh['uvs2'] for c in vertex]
            ok2 = bool(uvs2) and len(mesh['uvs2']) == len(mesh['positions'])
            packed2 = struct.pack('<%df' % len(uvs2), *uvs2) if ok2 else b''
            light = _lightmap_name(doc.meshes[index]['material'])
            if light and not ok2 and ok:
                packed2 = packed
            entry['uv1'] = base64.b64encode(packed2).decode('ascii')
            entry['map'] = _diffuse_name(doc.meshes[index]['material'])
            entry['light'] = light
        if skin:
            entry.update(_encode_skin(doc, mesh))
        meshes.append(entry)
    return {'meshes': meshes, 'notes': doc.notes}


def model_geometry(game_root, project, map_name, model, known=None):
    """Base64 float32 geometry for one model, cached by file stamp,
    with UVs and diffuse textures for the viewport. known skips
    texture blobs the caller already holds (content ids stay)."""
    resolved = resolve_model(game_root, project, map_name, model)
    if resolved[0] == 'skip':
        raise FlverError(resolved[1])
    kind, location = resolved[0], resolved[1]
    member = resolved[2] if kind == 'member' else ''
    try:
        stat = Path(location).stat()
    except OSError as error:
        raise FlverError(f'Cannot read {Path(location).name}') from error
    area = Path(map_name).stem.split('_')[0]
    return _payload(_cached_map(kind, str(location), member, (stat.st_mtime_ns, stat.st_size),
                                  game_root, project, area), known)


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
    stamp, with per-vertex skinning when playback needs it and diffuse
    textures for the drawer."""
    resolved = resolve_chr(game_root, project, chr_id)
    if resolved[0] == 'skip':
        raise FlverError(resolved[1])
    _kind, location, member = resolved
    try:
        stat = Path(location).stat()
    except OSError as error:
        raise FlverError(f'Cannot read {Path(location).name}') from error
    return _payload(_cached_textured('member', str(location), member,
                                        (stat.st_mtime_ns, stat.st_size), skin,
                                        game_root, project))


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
    file stamp, with UVs and diffuse textures for the drawer.
    """
    resolved = resolve_part(game_root, project, stem)
    if resolved[0] == 'skip':
        raise FlverError(resolved[1])
    _kind, location, member = resolved
    try:
        stat = Path(location).stat()
    except OSError as error:
        raise FlverError(f'Cannot read {Path(location).name}') from error
    return _payload(_cached_textured('member', str(location), member,
                                        (stat.st_mtime_ns, stat.st_size), False,
                                        game_root, project))


def resolve_asset_model(game_root, project, relative, side, member=None):
    """Where a Models-tab file's preview mesh lives: ('member', path,
    member name), ('piece', path), or ('skip', reason). The side names
    whose bytes preview: the mod's override unless the game side is
    asked for, else the installed file, like the asset detail."""
    relative = check_relative(relative)
    lowered = relative.as_posix().lower()
    inner = lowered[:-4] if lowered.endswith('.dcx') else lowered
    leaf = inner.rsplit('/', 1)[-1]
    extension = '.' + leaf.rsplit('.', 1)[-1] if '.' in leaf else ''
    if extension in COLLISION_EXTENSIONS:
        return ('skip', 'collision and navigation have no visible mesh')
    live = None
    if (side or 'mod') != 'game' and project is not None:
        own = Path(project) / relative
        if own.is_file():
            live = own
    if live is None:
        if game_root is None:
            return ('skip', 'Select the installed game before browsing its files')
        candidate = Path(game_root) / relative
        if candidate.is_file():
            live = candidate
    if live is None:
        return ('skip', 'The installed game has no such file')
    if extension == '.flver':
        return ('piece', live)
    if extension not in MODEL_KINDS:
        return ('skip', 'That file holds no model mesh')
    try:
        plain = live.read_bytes()
    except OSError:
        return ('skip', f'Cannot read {live.name}')
    if plain[:4] == b'DCX\0':
        try:
            plain = inflate(plain)
        except FormatError:
            return ('skip', f'Cannot open {live.name}')
    try:
        found = members(plain)
    except FormatError:
        return ('skip', f'Cannot open {live.name}')
    names = found if isinstance(found, dict) else {entry.name: entry for entry in found}
    flvers = sorted(name for name in names if name.lower().endswith('.flver'))
    if not flvers:
        return ('skip', f'{live.name} holds no model mesh')
    if member:
        # A key into the binder's own member table, never a path, so an
        # unknown member can only miss, never escape.
        if member not in flvers:
            return ('skip', f'{live.name} has no {member}')
        return ('member', live, member)
    stem = leaf.rsplit('.', 1)[0]
    wanted = stem + '.flver'
    return ('member', live, wanted if wanted in flvers else flvers[0])


def asset_geometry(game_root, project, relative, side, member=None):
    """Base64 float32 geometry for one Models-tab file, cached by file
    stamp, with UVs and diffuse textures for the drawer. Map pieces
    resolve their area's split texture archives like the viewport."""
    relative = check_relative(relative)
    resolved = resolve_asset_model(game_root, project, relative, side, member)
    if resolved[0] == 'skip':
        raise FlverError(resolved[1])
    kind = resolved[0]
    member = resolved[2] if kind == 'member' else ''
    location = resolved[1]
    try:
        stat = Path(location).stat()
    except OSError as error:
        raise FlverError(f'Cannot read {Path(location).name}') from error
    stamp = (stat.st_mtime_ns, stat.st_size)
    area = None
    if len(relative.parts) > 1 and relative.parts[0] == 'map':
        area = relative.parts[1].split('_')[0] or None
    if area is not None:
        return _payload(_cached_map(kind, str(location), member, stamp,
                                    game_root, project, area))
    return _payload(_cached_textured(kind, str(location), member, stamp, False,
                                     game_root, project))


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
