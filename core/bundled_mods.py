"""Bundle mods: one library mod with several selectable components.

A bundle's mod.json declares its components (see `components`). Each
component is a folder inside the bundle that the game's loader deploys on
its own. Which components deploy is ordinary tweak settings: one on/off
field per component, rendered by the shared tweak-settings UI from the
schema `schema` derives, stored in the bundle's own settings.json next to
the mod. There is no separate apply step and no library-wide bundle state:
ticking a component saves it like any other setting, and the game's loader
reads the saved selection the next time it deploys (a switch deploys at
once, like every other Mods tab switch).

A component's `tweaks` list is inert: it once named callbacks the game
registered in-process, which no game does. The format is still validated
so old bundles keep importing; nothing reads the names.
"""
import json
from pathlib import Path
import re

from core.mod_library import metadata, relative_path, file_tree
from core.plugin_files import atomic_write

VALUES_FILE = "settings.json"


def components(root: Path) -> list[dict]:
    """Validate the opt-in mod.json bundle layout without changing files."""
    bundle = metadata(root).get('bundle')
    if bundle is None:
        return []
    if not isinstance(bundle, dict) or bundle.get('version') != 1:
        raise ValueError('Unsupported bundled mod version')
    rows = bundle.get('components')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 256:
        raise ValueError('A bundle needs between 1 and 256 components')
    result, ids, paths = [], set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid bundled component')
        key, name, path, tweaks = (row.get(k) for k in ('id', 'name', 'path', 'tweaks'))
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', key) or key.casefold() in ids:
            raise ValueError('Component IDs must be unique short names')
        if not isinstance(name, str) or not name.strip() or len(name) > 160:
            raise ValueError('A component needs a short display name')
        if not isinstance(path, str):
            raise ValueError('A component needs a relative folder')
        target = (root / relative_path(path)).resolve()
        if root.resolve() not in target.parents or not target.is_dir():
            raise ValueError('Component folders must be inside their bundle')
        if any(target == other or target in other.parents or other in target.parents for other in paths):
            raise ValueError('Component folders must not overlap')
        if not isinstance(tweaks, list) or len(tweaks) > 64 or any(
                not isinstance(t, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', t) for t in tweaks):
            raise ValueError('Component tweaks must be registered tweak IDs')
        if len(tweaks) != len(set(tweaks)):
            raise ValueError('A component lists a tweak more than once')
        file_tree(target)  # Reject links/reparse points, including inside payloads.
        cursor = root / relative_path(path)
        while cursor != root:
            attrs = cursor.lstat()
            if cursor.is_symlink() or getattr(attrs, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Component folders cannot contain links')
            cursor = cursor.parent
        ids.add(key.casefold()); paths.append(target)
        result.append({'id': key, 'name': name.strip(), 'path': str(target), 'tweaks': tweaks})
    return result


def inspect_bundle(root, files, adapter):
    """Check each component through the same game adapter as standalone mods."""
    rows = components(root)
    if not rows:
        return adapter.inspect(root, files)
    if not getattr(adapter, 'supports_bundle_components', False):
        return {'valid': False, 'problems': ['This game loader does not support bundled components yet.'],
                'packages': [], 'assets': {}, 'notDeployed': []}
    packages, problems = [], []
    for row in rows:
        child = Path(row['path'])
        subset = [p.relative_to(child.relative_to(root.resolve())) for p in files
                  if child.relative_to(root.resolve()) in p.parents]
        report = adapter.inspect(child, subset)
        problems.extend(f"{row['name']}: {p}" for p in report.get('problems', []))
        packages.extend((child.relative_to(root.resolve()) / p).as_posix() for p in report.get('packages', []))
        if not report.get('valid') and not report.get('problems'):
            problems.append(f"{row['name']}: component cannot be loaded")
    expected = set(file_tree(root))
    if set(files) != expected:
        problems.append('Import a bundle with all of its files so linked components stay complete.')
    return {'valid': not problems, 'problems': problems, 'packages': packages, 'assets': {}, 'notDeployed': []}


def schema(root: Path) -> dict:
    """One on/off field per component, shaped like a tweak-mod schema.

    The shared tweak-settings UI renders this without any bundle-specific
    surface. A component starts off: enabling a bundle never deploys a
    part the reader did not tick.
    """
    fields = [{'key': row['id'], 'label': row['name'], 'type': 'bool',
               'default': False, 'help': ''} for row in components(Path(root))]
    return {'title': '', 'help': '', 'blocker': '', 'requires': [], 'conflicts': [],
            'needsDriver': False, 'fields': fields}


def values(root: Path) -> dict:
    """The reader's component selection over the all-off defaults.

    Stored beside the bundle in settings.json, in the same shape as a
    tweak mod's values. A stored value that is not on or off falls back
    to its default instead of failing the whole mod.
    """
    root = Path(root)
    fields = schema(root)['fields']
    path = root / VALUES_FILE
    if not path.exists():
        return {field['key']: False for field in fields}
    try:
        stored = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'{VALUES_FILE} is not readable JSON: {error}') from error
    stored = stored.get('values', {}) if isinstance(stored, dict) else {}
    result = {}
    for field in fields:
        picked = stored.get(field['key'], False)
        result[field['key']] = picked if type(picked) is bool else False
    return result


def save_values(root: Path, changes: dict) -> dict:
    """Validate and store changed component switches; unknown keys are refused."""
    root = Path(root)
    known = [field['key'] for field in schema(root)['fields']]
    if not isinstance(changes, dict):
        raise ValueError('Settings must be an object')
    unknown = sorted(set(changes) - set(known))
    if unknown:
        raise ValueError('Unknown settings: ' + ', '.join(unknown))
    current = values(root)
    for key, picked in changes.items():
        if type(picked) is not bool:
            raise ValueError(f'{key} must be on or off')
        current[key] = picked
    atomic_write(root / VALUES_FILE,
                 (json.dumps({'values': current}, indent=2) + '\n').encode('utf-8'))
    return current


def selected_paths(root: Path, selected: dict | None = None) -> list[Path]:
    """The enabled components' folders, in bundle order."""
    root = Path(root)
    picked = values(root) if selected is None else selected
    return [Path(row['path']) for row in components(root) if picked.get(row['id']) is True]


def expand_roots(roots, adapter=None) -> list[Path]:
    """Replace each bundle with its enabled components' folders.

    The game's loader keeps receiving plain mod folders; only the host
    knows some came out of a bundle. A bundle on a loader without
    component support is refused the same way its import is.
    """
    expanded = []
    for root in roots:
        rows = components(Path(root))
        if not rows:
            expanded.append(Path(root))
            continue
        if adapter is not None and not getattr(adapter, 'supports_bundle_components', False):
            raise ValueError('This game loader does not support bundled components yet')
        expanded.extend(selected_paths(Path(root)))
    names = [path.name.casefold() for path in expanded]
    if len(set(names)) != len(names):
        raise ValueError('Active mod and component folders must have distinct names for this loader')
    return expanded
