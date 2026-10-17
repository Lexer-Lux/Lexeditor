"""Character animation lists and sampled playback frames, read-only.

Animation data lives in chr binders: the character's own .anibnd.dcx
holds its skeleton, its .tae event files and usually its motion files,
with overflow motions in sibling cXXXX_aXX binders. Names link the
pieces: a00_9000.hkx plays anim 9000, cued by a00.tae for the player
and by cXXXX.tae for everyone else.
"""
import base64
import functools
import re
import struct
from pathlib import Path

from .formats import FormatError
from .hkx import HkxDocument, HkxError, _PeekUnsupported, peek_animation, sample_frames
from .tae import TaeError
from .viewport import CHR_ID, _overlay, resolve_chr

BINDER_NAME = re.compile(r'^[A-Za-z0-9_]+\.anibnd\.dcx$')
MEMBER_NAME = re.compile(r'^[A-Za-z0-9_]+\.hkx$')
ANIM_NAME = re.compile(r'^(a\d+)_(\d+)\.hkx$')
SKELETONS = ('Skeleton.hkx', 'skeleton.hkx')
MAX_BINDER = 512 * 1024 * 1024


def _binder_path(game_root, project, binder):
    if not BINDER_NAME.match(binder or ''):
        raise HkxError('Unknown animation binder')
    relative = Path('chr') / binder
    own = _overlay(project, relative)
    if own is not None:
        return own
    live = Path(game_root) / relative
    if live.is_file():
        return live
    raise HkxError(f'{binder} is not installed')


def _binder_rank(name):
    if '_dlc' in name:
        return 5
    if '_lo.' in name:
        return 4
    if '_md.' in name:
        return 3
    if re.search(r'_a..\.anibnd\.dcx$', name):
        return 2
    if '_hi.' in name:
        return 1
    return 0


def _binders(game_root, project, chr_id):
    """The character's own binder plus its motion siblings, ranked so
    the best copy of a motion wins: main, high detail, motion banks,
    medium, low, DLC. Delayload pair binders (cXXXX_cYYYY) need two
    skeletons at once, which playback does not stage, so they stay out."""
    if not CHR_ID.match(chr_id or ''):
        raise HkxError('Unknown character model')
    found = []
    for root in ([Path(project)] if project else []) + [Path(game_root)]:
        folder = root / 'chr'
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob(chr_id + '*.anibnd.dcx')):
            shape = rf'{re.escape(chr_id)}(_a..(_hi|_md|_lo)?|_dlc)?\.anibnd\.dcx'
            if re.fullmatch(shape, path.name):
                if path.name not in [name for name, _ in found]:
                    found.append((path.name, path))
    return sorted(found, key=lambda entry: (_binder_rank(entry[0]), entry[0]))


def _open(binder):
    from .formats import inflate, members
    try:
        plain = Path(binder).read_bytes()
    except OSError as error:
        raise HkxError(f'Cannot read {Path(binder).name}') from error
    if len(plain) > MAX_BINDER:
        raise HkxError('Animation binder is too large')
    if plain[:4] == b'DCX\0':
        try:
            plain = inflate(plain)
        except FormatError as error:
            raise HkxError(f'Cannot open {Path(binder).name}') from error
    try:
        found = members(plain)
    except FormatError as error:
        raise HkxError(f'Cannot open {Path(binder).name}') from error
    names = found if isinstance(found, dict) else {m.name: m for m in found}
    return plain, names


def _entry(plain, names, binder, member):
    if member not in names:
        raise HkxError(f'{Path(binder).name} has no {member}')
    entry = names[member]
    if isinstance(entry, dict):
        offset, size = entry['offset'], entry['size']
    else:
        offset, size = entry.offset, entry.size
    if offset + size > len(plain):
        raise HkxError(f'{member} runs past the end of {Path(binder).name}')
    return plain[offset:offset + size]


@functools.lru_cache(maxsize=32)
def _parsed_binder(binder, stamp):
    plain, names = _open(binder)
    docs, broken = {}, {}
    for member in sorted(names):
        if not member.endswith('.hkx'):
            continue
        try:
            docs[member] = HkxDocument(_entry(plain, names, binder, member))
        except HkxError as error:
            broken[member] = str(error)
    return docs, broken


def _stamp(path):
    try:
        stat = Path(path).stat()
    except OSError as error:
        raise HkxError(f'Cannot read {Path(path).name}') from error
    return (stat.st_mtime_ns, stat.st_size)


def list_chars(game_root, project):
    """Character IDs with a main animation binder, game and project
    union. Skeleton presence is checked when one is opened."""
    stems = set()
    for root in ([Path(project)] if project else []) + [Path(game_root)]:
        folder = root / 'chr'
        if not folder.is_dir():
            continue
        for path in folder.glob('*.anibnd.dcx'):
            match = re.fullmatch(r'([A-Za-z0-9_]+)\.anibnd\.dcx', path.name)
            if match and '_' not in match.group(1):
                stems.add(match.group(1))
    return sorted(stems)


def list_anims(game_root, project, chr_id, tae_store=None):
    """The character's skeleton flag and playable motions: file, binder,
    TAE link, duration and frame count. Headers are peeked, not parsed,
    so listing never pays for curves; members whose headers fail to read
    are listed as unavailable, with the reason, and a motion whose curves
    fail opens loud when sampled. A character with no binders at all is
    an error. With a TAE store, every motion also names its
    event entry (or none), and event animations no motion plays list
    under 'orphans'."""
    binders = _binders(game_root, project, chr_id)
    if not binders:
        raise HkxError('No animation binder is installed')
    stamps = tuple((binder, _stamp(path)) for binder, path in binders)
    listed = _listed_anims(chr_id, stamps,
                           tuple(str(path) for _binder, path in binders))
    if tae_store is None:
        return listed
    try:
        taes = tae_store.get(f'{chr_id}.anibnd.dcx')['taes']
    except (TaeError, ValueError, OSError):
        taes = {}
    anims, linked = [], set()
    for motion in listed['anims']:
        link = tae_link(taes, chr_id, motion['file']) if motion.get('file') else None
        if link is not None:
            linked.add(link)
        anims.append({**motion, 'tae': link[0] if link else None,
                      'taeIndex': link[1] if link else None})
    return {'chr': listed['chr'], 'skeleton': listed['skeleton'],
            'anims': anims, 'orphans': event_orphans(tae_store, chr_id, linked)}


def _headline(blob):
    """A motion's list-row headline: peeked scalars, or a full read when
    the peek cannot map the layout. None when the file holds nothing
    playable, like the full reader skipping it."""
    try:
        return peek_animation(blob)
    except _PeekUnsupported:
        pass
    doc = HkxDocument(blob)
    if not doc.animations or not doc.bindings:
        return None
    anim = doc.animations[0]
    return {'duration': anim['duration'], 'frames': anim['frames']}


@functools.lru_cache(maxsize=16)
def _listed_anims(chr_id, stamps, paths):
    skeleton, anims, seen = False, [], {}
    for (binder, _stamp), path in zip(stamps, paths):
        plain, names = _open(path)
        for member in sorted(names):
            if not member.endswith('.hkx'):
                continue
            if member in SKELETONS:
                try:
                    doc = HkxDocument(_entry(plain, names, path, member))
                except HkxError:
                    continue
                skeleton = skeleton or bool(doc.skeletons)
                continue
            match = ANIM_NAME.match(member)
            base = {'file': member, 'binder': binder, 'bank': match.group(1) if match else None,
                    'id': int(match.group(2)) if match else None}
            try:
                headline = _headline(_entry(plain, names, path, member))
            except HkxError as error:
                entry = {**base, 'available': False, 'reason': str(error)}
            else:
                if headline is None:
                    continue
                entry = {**base, 'duration': headline['duration'], 'frames': headline['frames']}
            if member in seen:
                if anims[seen[member]].get('available', True):
                    continue
                anims[seen[member]] = entry
                continue
            seen[member] = len(anims)
            anims.append(entry)
    return {'chr': chr_id, 'skeleton': skeleton, 'anims': anims}


def skeleton(game_root, project, chr_id):
    """The Havok skeleton (names, parents, reference pose) with the
    FLVER bone list it drives. FLVER bones carry extras the animation
    never moves (SFX and dummy anchors); they keep the bind pose."""
    from .flver import FlverDocument
    binders = _binders(game_root, project, chr_id)
    if not binders:
        raise HkxError('No animation binder is installed')
    hka = None
    for binder, path in binders:
        docs, _broken = _parsed_binder(str(path), _stamp(path))
        for member in SKELETONS:
            if member in docs and docs[member].skeletons:
                hka = docs[member].skeletons[0]
        if hka is not None:
            break
    if hka is None:
        raise HkxError('No skeleton is installed')
    flver_bones = []
    resolved = resolve_chr(game_root, project, chr_id)
    if resolved[0] == 'member':
        plain, names = _open(resolved[1])
        # The same mesh the geometry endpoint skins: skin indices are
        # positions in this file's bone list, so a binder holding
        # several models must not lend another file's bones.
        flvers = sorted(name for name in names if name.endswith('.flver'))
        picked = f'{chr_id}.flver' if f'{chr_id}.flver' in flvers else (flvers[:1] or [None])[0]
        if picked is not None:
            doc = FlverDocument(_entry(plain, names, resolved[1], picked))
            flver_bones = [{'name': bone['name'], 'parent': bone['parent'],
                            'pos': list(bone['pos']), 'rot': list(bone['rot']),
                            'scale': list(bone['scale'])} for bone in doc.bones]
    order = {bone['name']: index for index, bone in enumerate(hka['bones'])}
    return {'hka': {'bones': [bone['name'] for bone in hka['bones']],
                    'parents': list(hka['parents']),
                    'pose': [{'t': entry['t'], 'q': entry['q'], 's': entry['s']}
                             for entry in hka['pose']]},
            'flver': flver_bones,
            'map': [order.get(bone['name'], -1) for bone in flver_bones]}


def _b64(values, code):
    return base64.b64encode(struct.pack('<%d%s' % (len(values), code), *values)).decode('ascii')


@functools.lru_cache(maxsize=8)
def _sampled_frames(anim_path, member, anim_stamp, skel_path, skel_member, skel_stamp):
    anim_plain, anim_names = _open(anim_path)
    anim_doc = HkxDocument(_entry(anim_plain, anim_names, anim_path, member))
    if not anim_doc.animations or not anim_doc.bindings:
        raise HkxError(f'{member} holds no playable animation')
    skel_plain, skel_names = _open(skel_path)
    skel_doc = HkxDocument(_entry(skel_plain, skel_names, skel_path, skel_member))
    if not skel_doc.skeletons:
        raise HkxError('No skeleton is installed')
    anim = anim_doc.animations[0]
    frames = sample_frames(anim, skel_doc.skeletons[0], anim_doc.bindings[0])
    bones = len(skel_doc.skeletons[0]['bones'])
    flat_t, flat_q, flat_s = [], [], []
    for pose in frames:
        for trans, quat, scale in pose:
            flat_t.extend(trans)
            flat_q.extend(quat)
            flat_s.extend(scale)
    motion = anim_doc.animations[0]['motion']
    return {'frames': len(frames), 'bones': bones, 'duration': anim['duration'],
            'frame_duration': anim['frame_duration'],
            'translations': _b64(flat_t, 'f'), 'rotations': _b64(flat_q, 'f'),
            'scales': _b64(flat_s, 'f'),
            'motion': None if motion is None else _b64(
                [c for sample in motion['samples'] for c in sample], 'f')}


def tae_link(taes, chr_id, member):
    """The (event file, animation index) cueing a motion, or None.

    A motion aBB_III.hkx takes its events from the animation numbered
    III in BB.tae. The player banks events per motion set (a00.tae);
    every other character keeps one file under its own ID.
    """
    match = ANIM_NAME.match(member or '')
    if match is None:
        return None
    candidates = [f'{match.group(1)}.tae', f'{chr_id}.tae']
    want = int(match.group(2))
    for name in candidates:
        if name not in taes:
            continue
        try:
            anims = taes[name].list_anims()
        except (TaeError, ValueError):
            continue
        index = next((anim['index'] for anim in anims if anim['id'] == want), None)
        if index is not None:
            return (name, index)
    return None


def event_orphans(tae_store, chr_id, linked):
    """Event animations no motion plays.

    A binder may carry events for motions it does not ship; those
    animations are still editable, so they list alongside the motions.
    """
    try:
        taes = tae_store.get(f'{chr_id}.anibnd.dcx')['taes']
    except (TaeError, ValueError, OSError):
        return []
    orphans = []
    for name in sorted(taes):
        try:
            anims = taes[name].list_anims()
        except (TaeError, ValueError):
            continue
        for anim in anims:
            if (name, anim['index']) in linked:
                continue
            orphans.append({'file': None, 'name': anim['name'],
                            'binder': f'{chr_id}.anibnd.dcx', 'tae': name,
                            'taeIndex': anim['index'], 'events': anim['events']})
    return orphans


def anim_events(tae_store, chr_id, binder, member):
    """The TAE events cueing this motion, or none when the motion has
    no event file entry."""
    if tae_store is None:
        return []
    try:
        taes = tae_store.get(f'{chr_id}.anibnd.dcx')['taes']
    except (TaeError, ValueError, OSError):
        return []
    found = tae_link(taes, chr_id, member)
    if found is None:
        return []
    name, index = found
    try:
        rows = tae_store.list_events(f'{chr_id}.anibnd.dcx', name, index)
    except (TaeError, ValueError, OSError):
        return []
    return [{'start': row['values']['start'], 'end': row['values']['end'],
             'type': row['values']['type'], 'label': row['values']['label']} for row in rows]


def anim_frames(game_root, project, chr_id, binder, member, tae_store=None):
    """Sampled local transforms per skeleton bone per frame, root
    motion samples, and the motion's TAE event cues."""
    if not MEMBER_NAME.match(member or '') or member in SKELETONS:
        raise HkxError('Unknown animation file')
    path = _binder_path(game_root, project, binder)
    expected = [name for name, _ in _binders(game_root, project, chr_id)]
    if binder not in expected:
        raise HkxError('Animation binder belongs to another character')
    skel_binder = next((name for name in expected if name == f'{chr_id}.anibnd.dcx'), expected[0])
    skel_path = _binder_path(game_root, project, skel_binder)
    skel_docs, _broken = _parsed_binder(str(skel_path), _stamp(skel_path))
    skel_member = next((name for name in SKELETONS if name in skel_docs
                        and skel_docs[name].skeletons), None)
    if skel_member is None:
        raise HkxError('No skeleton is installed')
    payload = _sampled_frames(str(path), member, _stamp(path), str(skel_path),
                              skel_member, _stamp(skel_path))
    payload['events'] = anim_events(tae_store, chr_id, binder, member)
    return payload
