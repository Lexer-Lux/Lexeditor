"""Refresh clean project data atomically after a filesystem notification."""
import hashlib

from . import native_rules, record_edits, weapon_skills
from .store import ItemStore
from .map_store import MapStore, MAX_MAP
from .tae_store import TaeStore, MAX_BINDER
from .formats import MAX_ARCHIVE
from .tweak_mods import checked


def _changed(path, expected, limit):
    if path is None:
        return False
    path = checked(path)
    if not path.exists():
        return expected is not None
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError(f'{path.name} cannot be refreshed: unsupported file type or size')
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(block)
            if size > limit:
                raise ValueError(f'{path.name} grew beyond its size limit during refresh')
            digest.update(block)
    return digest.hexdigest() != expected


def _sources(items, rules, maps, animations, skills, paths=None):
    sources = []
    if items.document is not None:
        for name in ('source', 'output', 'text_source', 'text_output', 'menu_source', 'menu_output'):
            hash_name = {'source':'source_hash', 'output':'output_hash', 'text_source':'text_hash',
                         'text_output':'text_output_hash', 'menu_source':'menu_hash',
                         'menu_output':'menu_output_hash'}[name]
            sources.append((getattr(items,name),getattr(items,hash_name),MAX_ARCHIVE))
        sources.append((items.records_path,items.records_hash,record_edits.LIMIT))
    for store,limit in ((maps,MAX_MAP),(animations,MAX_BINDER)):
        for entry in store.hashes.values():
            sources.extend((entry[name],entry[f'{name}_hash'],limit) for name in ('source','output'))
    sources.append((items.project/native_rules.SETTINGS_FILE,rules.saved_hash,native_rules.SETTINGS_LIMIT))
    if rules.legacy is not None:
        sources.append((items.project/native_rules.LEGACY_FILE,rules.legacy['sha256'],native_rules.SETTINGS_LIMIT))
    sources.append((items.project/weapon_skills.RELATIVE,skills.saved_hash,weapon_skills.LIMIT))
    sources = list(dict.fromkeys(source for source in sources if source[0] is not None))
    if paths is None:
        return sources
    wanted = [path.casefold().rstrip('/') for path in paths]
    return [source for source in sources if source[0].is_relative_to(items.project) and any(
        (relative := source[0].relative_to(items.project).as_posix().casefold()) == name
        or relative.startswith(name+'/') for name in wanted)]


def changed(items, rules, maps, animations, skills, paths=None):
    """A read-only probe; unchanged notifications must not lock the editor."""
    return items.project is not None and any(
        _changed(*source) for source in _sources(items,rules,maps,animations,skills,paths))


def refresh(items, rules, maps, animations, skills, paths=None):
    """Return replacement stores, or None. Caller holds the session lock.

    Only already-loaded sources are compared. No library walk, deployment,
    builder, or author-code execution happens here. Every replacement loads
    before any old store is retired, so one bad file cannot erase good data.
    """
    if items.project is None:
        return None
    if ((items.document is not None and items.document.dirty_count)
            or rules.dirty_count or maps.dirty_count or animations.dirty_count or skills.dirty_count):
        return None
    changed = {source for source in _sources(items,rules,maps,animations,skills,paths) if _changed(*source)}
    if not changed:
        return None
    fresh = ItemStore(items.game_root,items.project,items.read_only)
    if items.document is not None:
        fresh.load()
    fresh_rules = native_rules.NativeRules(items.game_root,items.project,items.read_only)
    fresh_rules.live = dict(rules.live)
    fresh_skills = weapon_skills.WeaponSkills(items.game_root,items.project,items.read_only)
    fresh_maps = MapStore(items.game_root,items.project,items.read_only,fresh)
    fresh_animations = TaeStore(items.game_root,items.project,items.read_only,fresh)
    # Retain unchanged decoded documents; a parameter update must not parse
    # every animation the reader has opened during this session.
    for target,old,limit in ((fresh_maps,maps,MAX_MAP),(fresh_animations,animations,MAX_BINDER)):
        target.docs = dict(old.docs)
        target.hashes = dict(old.hashes)
        target.vanilla_docs = dict(old.vanilla_docs)
        for name,entry in old.hashes.items():
            if any((entry[key],entry[f'{key}_hash'],limit) in changed for key in ('source','output')):
                target.docs.pop(name)
                target.get(name)
    if any(_changed(*source) for source in _sources(fresh,fresh_rules,fresh_maps,fresh_animations,fresh_skills,paths)):
        raise ValueError('The mod changed again while its files were being refreshed; current editor data was kept')
    return fresh,fresh_rules,fresh_maps,fresh_animations,fresh_skills
