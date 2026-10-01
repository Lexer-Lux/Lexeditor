"""Shared component/tweak transactions. Imported manifests never execute code.

Tweak callbacks are registered by a trusted plugin. They must persist their
boolean state and make repeated writes idempotent. Loader adapters opt in to
accepting component roots; the shared host owns selection and recovery.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Callable

from core.mod_library import metadata, relative_path, file_tree
from core.plugin_files import atomic_write


@dataclass(frozen=True)
class BundledTweak:
    name: str
    read: Callable[[Path], bool]
    write: Callable[[Path, bool], None]


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


class BundleManager:
    def __init__(self, library: Path, game: Path, adapter, tweaks: dict[str, BundledTweak]):
        self.library, self.game = Path(library).resolve(), Path(game).resolve()
        self.adapter, self.tweaks = adapter, tweaks
        self.state_path = self.library / '.bundles.json'
        self.journal = self.library / '.bundles-pending.json'

    def catalog(self):
        result = {}
        for root in sorted(self.library.iterdir()) if self.library.is_dir() else []:
            if root.is_dir() and not root.name.startswith('.') and not root.is_symlink():
                for row in components(root):
                    token = root.name + '/' + row['id']
                    result[token] = {**row, 'parent': str(root.resolve()), 'token': token}
        return result

    def _read(self, path, fallback):
        if not path.exists():
            return fallback
        value = json.loads(path.read_text('utf-8'))
        if not isinstance(value, dict) or value.get('version') != 1:
            raise ValueError('Invalid bundled mod state; restore its saved copy before continuing')
        return value

    def state(self):
        default = {'version': 1, 'mods': [], 'components': []}
        if not self.state_path.exists():
            default['mods'] = list(self.adapter.active_mod_ids(self.game))
        return self._read(self.state_path, default)

    def _paths(self, state, catalog):
        mods, selected = state.get('mods'), state.get('components')
        if not isinstance(mods, list) or not isinstance(selected, list):
            raise ValueError('Invalid bundled selection')
        if any(not isinstance(v, str) for v in mods + selected) or len(set(mods)) != len(mods) or len(set(selected)) != len(selected):
            raise ValueError('Choose each mod and component once')
        roots = []
        for name in mods:
            relative = relative_path(name)
            root = (self.library / relative).resolve()
            if len(relative.parts) != 1 or root.parent != self.library or not root.is_dir() or components(root):
                raise ValueError('Choose standalone mods from this library, and bundle components individually')
            roots.append(root)
        for token in selected:
            if token not in catalog:
                raise ValueError(f'Unknown bundled component: {token}')
            row = catalog[token]
            missing = set(row['tweaks']) - self.tweaks.keys()
            if missing:
                raise ValueError('This game has not registered these tweaks: ' + ', '.join(sorted(missing)))
            roots.append(Path(row['path']))
        if selected and not getattr(self.adapter, 'supports_bundle_components', False):
            raise ValueError('This game loader does not support bundled components yet')
        names = [p.name.casefold() for p in roots]
        if len(set(names)) != len(names):
            raise ValueError('Active mod and component folders must have distinct names for this loader')
        return roots

    def snapshot(self):
        catalog, state = self.catalog(), self.state()
        selected = set(state['components'])
        rows = []
        for token, row in catalog.items():
            unknown = set(row['tweaks']) - self.tweaks.keys()
            error = ('Unregistered tweaks: ' + ', '.join(sorted(unknown))) if unknown else ''
            if not getattr(self.adapter, 'supports_bundle_components', False):
                error = 'This game loader does not support bundled components yet.'
            links = [{'id': key, 'name': self.tweaks[key].name if key in self.tweaks else key}
                     for key in row['tweaks']]
            rows.append({**row, 'enabled': token in selected, 'linkedTweaks': links, 'error': error})
        used = {key for row in catalog.values() for key in row['tweaks']}
        tweak_rows = []
        for key in sorted(used & self.tweaks.keys()):
            actual = self.tweaks[key].read(self.game)
            if type(actual) is not bool:
                raise ValueError(f'Tweak {key} did not report a boolean state')
            owners = [token for token, row in catalog.items() if key in row['tweaks']]
            expected = any(token in selected for token in owners)
            tweak_rows.append({'id': key, 'name': self.tweaks[key].name, 'enabled': actual,
                               'components': owners, 'inconsistent': actual != expected})
        expected = {p.name for p in self._paths(state, catalog)} if self.state_path.exists() else None
        deployment_differs = expected is not None and expected != set(self.adapter.active_mod_ids(self.game))
        return {'components': rows, 'tweaks': tweak_rows, 'selection': state,
                'inconsistent': deployment_differs or any(t['inconsistent'] for t in tweak_rows),
                'recoveryRequired': self.journal.exists()}

    def _save(self, path, value):
        atomic_write(path, (json.dumps(value, indent=2) + '\n').encode())

    def _restore(self, pending, catalog):
        # Restore persisted tweak settings before recomposing the prior mod set.
        for key, value in pending['tweaks'].items():
            if key not in self.tweaks or type(value) is not bool:
                raise ValueError('A registered tweak is missing during recovery')
            self.tweaks[key].write(self.game, value)
            if self.tweaks[key].read(self.game) is not value:
                raise ValueError(f'Tweak {key} could not be restored')
        roots = self._paths(pending['before'], catalog)
        self.adapter.activate(roots, self.game)
        if set(self.adapter.active_mod_ids(self.game)) != {p.name for p in roots}:
            raise ValueError('The loader did not restore the previous component selection')
        self._save(self.state_path, pending['before'])
        self.journal.unlink()

    def recover(self):
        if self.journal.exists():
            self._restore(self._read(self.journal, None), self.catalog())

    def activate(self, mods, selected):
        if self.journal.exists():
            raise ValueError('Recover the interrupted bundled mod change before applying another selection')
        catalog, before = self.catalog(), self.state()
        after = {'version': 1, 'mods': mods, 'components': selected}
        roots = self._paths(after, catalog)
        self._paths(before, catalog)  # Prove rollback can address all prior sources.
        used = {key for row in catalog.values() for key in row['tweaks']} & self.tweaks.keys()
        prior = {key: self.tweaks[key].read(self.game) for key in used}
        if any(type(value) is not bool for value in prior.values()):
            raise ValueError('A linked tweak did not report a boolean state')
        pending = {'version': 1, 'before': before, 'after': after, 'tweaks': prior}
        self._save(self.journal, pending)
        try:
            for key in sorted(used):
                wanted = any(key in catalog[token]['tweaks'] for token in selected)
                self.tweaks[key].write(self.game, wanted)
                if self.tweaks[key].read(self.game) is not wanted:
                    raise ValueError(f'Tweak {key} did not persist the requested state')
            self.adapter.activate(roots, self.game)
            if set(self.adapter.active_mod_ids(self.game)) != {p.name for p in roots}:
                raise ValueError('The loader did not persist the requested component selection')
            self._save(self.state_path, after)
            self.journal.unlink()
        except Exception as error:
            try:
                self._restore(pending, catalog)
            except Exception as recovery:
                raise RuntimeError(f'{error}. Rollback needs recovery: {recovery}') from error
            raise
        return self.snapshot()

    def toggle_tweak(self, key, enabled):
        if type(enabled) is not bool or key not in self.tweaks:
            raise ValueError('Choose a registered tweak and a boolean state')
        catalog, state = self.catalog(), self.state()
        owners = {token for token, row in catalog.items() if key in row['tweaks']}
        if not owners:
            raise ValueError('This tweak is not linked to a bundled component')
        selected = set(state['components'])
        selected = selected | owners if enabled else selected - owners
        return self.activate(state['mods'], sorted(selected))
