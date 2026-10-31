"""DS1 tweak mods: build the enabled ones and apply them to the game.

A DS1 tweak mod (see core/script_mods.py) builds `native/<id>.json`, a patch
description that exe_patches.py combines with every other enabled tweak's,
and optionally `layout/<id>.json`, text nodes menu_layout.py adds to the
vanilla menu layout, and `esd/<id>.json`, commands menu_scripts.py inserts
into the ingame and common menu scripts.

DarkSoulsRemastered.exe is never written. Applying installs Lexeditor's
loader (dinput8.dll) and lexeditor-ds1-patch.bin beside it, and the loader
patches the game in memory as it starts (plugins/ds1/runtime/). Writing the
executable failed whenever a crashed game was still listed by Windows,
which keeps the file locked. Old executable backups and journals remain
read-only; Steam verifies the executable when an older tool changed it.

The menu layout is a data file and is still replaced, only when a tweak asks
for nodes or an earlier Apply changed it. The ingame and common menu scripts
follow the same rule for command insertions. It keeps one original copy and an
ownership journal beside it; the journal records replacement intent before
the file is written, so an interrupted Apply or Restore can be retried
without trusting unknown bytes. Outside modifications are refused, never
overwritten. The game folder also holds a one-byte OS lock file.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import inspect
import json
import keyword
import os
from pathlib import Path
from time import perf_counter
import stat
import sys
import struct
from typing import Callable

from core import mod_metadata, mod_requires, script_mods
from core.plugin_files import atomic_write
from core.process_probe import live_processes

from . import exe_patches, menu_dim, menu_layout, menu_scripts

ALLOWED_ROOTS = ("native", "layout", "esd", "menu-dim", "script", "msg", "event")
ALLOWED_ROOTS += ("param",)
BACKUP_FILE = "DarkSoulsRemastered.exe.lexeditor-original"
MANIFEST_FILE = "DarkSoulsRemastered.exe.lexeditor-tweaks.json"
MODS_ENV = "LEXEDITOR_DS1_MODS_ROOT"
LOCK_FILE = "DarkSoulsRemastered.exe.lexeditor-tweaks.lock"
MAX_MANIFEST = 1024 * 1024


@contextmanager
def _exclusive(game_root: Path):
    """Serialize cooperating editor processes; closing releases the OS lock."""
    path = checked(Path(game_root) / LOCK_FILE)
    if path.exists() and (not path.is_file() or path.stat().st_size > 1):
        raise TweakError("The executable tweak lock file is invalid")
    from core.file_lock import exclusive
    with exclusive(path):
        yield


class TweakError(script_mods.ScriptModError):
    """A tweak operation failed; the message identifies any recovery needed."""


@dataclass(frozen=True)
class Managed:
    """One game file tweaks rewrite, with its preserved original and journal."""
    relative: str
    label: str
    limit: int
    vanilla: Callable[[bytes], bool]

    def live(self, game_root: Path) -> Path:
        return Path(game_root) / self.relative

    def backup(self, game_root: Path) -> Path:
        return Path(game_root) / (self.relative + ".lexeditor-original")

    def manifest(self, game_root: Path) -> Path:
        return Path(game_root) / (self.relative + ".lexeditor-tweaks.json")


def mods_root() -> Path:
    override = os.environ.get(MODS_ENV)
    if override:
        return Path(override)
    from core.mod_library import default_user_library_root
    return default_user_library_root() / "ds1"


def checked(path: Path) -> Path:
    """Refuse links and junctions on a protected path before following it."""
    path = Path(os.path.abspath(path))
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise TweakError("A protected tweak path contains a symlink or junction")
        if entry == path and stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise TweakError("A protected tweak file has more than one hard link")
    return path


def _read(path: Path, managed: "Managed | None" = None) -> bytes:
    managed = managed or EXECUTABLE
    path = checked(path)
    if not path.is_file():
        raise TweakError(f"{path.name} is missing")
    if path.stat().st_size > managed.limit:
        raise TweakError(f"{path.name} is too large to be the Remastered {managed.label}")
    with path.open('rb') as stream:
        data = stream.read(managed.limit+1)
    if len(data) > managed.limit:
        raise TweakError(f'{path.name} grew beyond its size limit')
    return data


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_vanilla(data: bytes) -> bool:
    return len(data) == exe_patches.VANILLA_SIZE and _sha(data) == exe_patches.VANILLA_SHA256


EXECUTABLE = Managed(exe_patches.EXECUTABLE, "executable", 128 * 1024 * 1024, lambda data: is_vanilla(data))
# The loader DLL in the game folder, read only to tell ours from another mod's.
RUNTIME_FILE = Managed("dinput8.dll", "loader", 64 * 1024 * 1024, lambda data: False)
LAYOUT = Managed(menu_layout.RELATIVE.as_posix(), "menu layout", 16 * 1024 * 1024,
                 lambda data: menu_layout.is_vanilla(data))
ESD_INGAME = Managed(menu_scripts.RELATIVE["ingame"].as_posix(), "ingame menu scripts",
                     16 * 1024 * 1024, lambda data: menu_scripts.is_vanilla(data, "ingame"))
ESD_COMMON = Managed(menu_scripts.RELATIVE["common"].as_posix(), "common menu scripts",
                     16 * 1024 * 1024, lambda data: menu_scripts.is_vanilla(data, "common"))
ESD = (ESD_INGAME, ESD_COMMON)
ESD_ARCHIVE = {ESD_INGAME: "ingame", ESD_COMMON: "common"}
assert EXECUTABLE.backup(Path()).name == BACKUP_FILE and EXECUTABLE.manifest(Path()).name == MANIFEST_FILE


def managed_menu(relative):
    return next((item for item in (LAYOUT, *ESD) if Path(item.relative) == relative), None)


def menu_baseline(game_root, managed):
    """Resolve old dual-writer records without treating either output as vanilla."""
    from . import deployment
    marker_path = checked(deployment._marker_path(game_root, Path(managed.relative)))
    data = deployment._read_marker(marker_path)
    if data is None:
        current, manifest = _installed(game_root, managed, 'restore it before applying mods')
        return current, _original(game_root, current, manifest, managed), manifest
    current = _read(managed.live(game_root), managed)
    original = _read(managed.backup(game_root), managed)
    manifest = _manifest(game_root, managed)
    if _sha(original) != data['originalHash'] or (manifest and not _original_matches(original, manifest, managed)):
        raise TweakError(f'The preserved original {managed.label} differs between ownership records; both were kept')
    known = {data['originalHash'], data.get('activeHash'), data.get('pendingHash')}
    if manifest:
        known.update((manifest['sha256'], (manifest.get('pending') or {}).get('sha256')))
    if _sha(current) not in known or not _menu_baseline(original, managed):
        raise TweakError(f'The installed {managed.label} changed outside its recorded writers; all copies were kept')
    names = list(dict.fromkeys([*manifest.get('mods', []),
                               *(['Installed data mods']
                                 if _sha(current) != _sha(original) else [])]))
    return current, original, {'version': 2, 'sha256': _sha(current), 'originalHash': _sha(original),
                               'mods': names, 'project': None, 'inputs': None, 'pending': None}


def claim_menu_files(game_root):
    """Transfer legacy data journals to the sole menu writer, keeping game bytes intact."""
    from . import deployment
    from core.file_lock import exclusive
    if not any(checked(deployment._marker_path(game_root, Path(managed.relative))).is_file()
               for managed in (LAYOUT, *ESD)):
        return
    with exclusive(checked(Path(game_root) / deployment.DATA_LOCK)):
        transfers = []
        for managed in (LAYOUT, *ESD):
            path = checked(deployment._marker_path(game_root, Path(managed.relative)))
            if not path.is_file():
                continue
            with path.open('rb') as stream:
                before = stream.read(deployment.MAX_MARKER + 1)
            current, original, manifest = menu_baseline(game_root, managed)
            transfers.append((managed, path, before, current, original, manifest, _manifest(game_root, managed)))
        for managed, path, before, current, original, manifest, previous in transfers:
            with path.open('rb') as stream:
                unchanged = stream.read(deployment.MAX_MARKER + 1) == before
            if (not unchanged or _manifest(game_root, managed) != previous or _read(managed.live(game_root), managed) != current
                    or _read(managed.backup(game_root), managed) != original):
                raise TweakError('Menu ownership changed during migration; all copies were kept')
            _save_manifest(game_root, manifest, managed)
            path.unlink()


def tweak_rows(root: Path | None = None) -> list[dict]:
    """Every tweak mod in the DS1 library, in load order."""
    root = checked(Path(root or mods_root()))
    rows = []
    if root.is_dir():
        for folder in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
            try:
                checked(folder)
                if not folder.is_dir():
                    continue
                checked(folder / "mod.json")
                checked(folder / script_mods.VALUES_FILE)
                metadata = script_mods._read_json(folder / 'mod.json')
            except (OSError, ValueError):
                # Shared library discovery already exposes unreadable metadata
                # as an off/error row. Never let it hide the healthy catalog.
                continue
            if not isinstance(metadata, dict):
                continue
            scripted = isinstance(metadata.get('script'), dict)
            from . import native_rules, native_support
            module = (folder/'runtime.lxd').is_file()
            if not scripted and not module and not (folder/native_rules.SETTINGS_FILE).is_file() and not (folder/native_support.FOLDER).is_dir():
                continue
            row = script_mods.catalog_row(folder) if scripted else {
                'path': str(folder), 'error': '', 'values': {}, 'schema': script_mods.schema(folder)}
            row['prebuilt'] = not scripted
            row['module'] = module
            order = metadata.get('order', 1000)
            if not isinstance(order, int) or isinstance(order, bool):
                row['error'] = 'Load order must be a whole number'
                order = 1000
            row.update({"id": str(metadata.get("id") or folder.name), "name": str(metadata.get("name") or folder.name),
                        "enabled": metadata.get("enabled") is True, "order": order})
            rows.append(row)
    for row in rows:
        if sum(other['enabled'] and other['id'].casefold() == row['id'].casefold() for other in rows) > 1:
            row['error'] = 'Multiple enabled tweak mods share this id'
    return sorted(rows, key=lambda row: (row["order"], row["name"].casefold()))


def save(changes: dict, root: Path | None = None) -> list[dict]:
    """Store switches and values for several tweak mods, all or none."""
    rows = {row["id"]: row for row in tweak_rows(root)}
    if not isinstance(changes, dict):
        raise TweakError("Send tweak ids mapped to their changes")
    for mod_id, change in changes.items():
        if mod_id not in rows:
            raise TweakError(f"There is no DS1 tweak mod {mod_id}")
        if not isinstance(change, dict) or set(change) - {"enabled", "values"}:
            raise TweakError(f"{mod_id}: send enabled and values only")
        if "enabled" in change and type(change["enabled"]) is not bool:
            raise TweakError(f"{rows[mod_id]['name']} must be on or off")
    planned = {mod_id: change["enabled"] for mod_id, change in changes.items() if "enabled" in change}
    if planned:
        try:
            mod_requires.check_changes(root or mods_root(), planned)
        except ValueError as error:
            raise TweakError(str(error)) from error
    ensure_loader_mod(root)
    touched = [Path(rows[mod_id]["path"]) / name for mod_id in changes
               for name in ("mod.json", script_mods.VALUES_FILE)]
    before = {path: path.read_bytes() if path.is_file() else None for path in touched}
    try:
        for mod_id, change in changes.items():
            folder = Path(rows[mod_id]["path"])
            if "values" in change:
                script_mods.save_values(folder, change["values"])
            if "enabled" in change:
                metadata = mod_metadata._stored(folder)
                metadata["enabled"] = change["enabled"]
                atomic_write(folder / "mod.json", (json.dumps(metadata, indent=2) + "\n").encode("utf-8"))
    except Exception:
        for path, content in before.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, content)
        raise
    return tweak_rows(root)


#: The loader as its own library mod: switching it on installs Lexeditor's
#: loader (dinput8.dll), which applies executable patches in memory, switches
#: the game's anti-tamper protection off, installs multiplayer protection,
#: and isolates modded saves.
#: Executable-patch mods need it on.
LOADER_ID = "lexeditor-loader"
LOADER_FOLDER = "Lexeditor Loader"
LOADER_NAME = "Lexeditor Loader"
LOADER_DESCRIPTION = ("Installs Lexeditor's loader, which applies executable patches in memory "
                      "when the game starts. The loader switches the game's anti-tamper protection "
                      "off and adds multiplayer protection. Modded play uses separate characters "
                      "that Steam Cloud can sync. Removing the loader returns to your vanilla characters.")


def _loader_folder(root: Path) -> Path | None:
    """The folder claiming the loader id, or None when no mod does."""
    try:
        entries = sorted(Path(root).iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return None
    for candidate in entries:
        if not candidate.is_dir() or candidate.name.startswith("."):
            continue
        try:
            stored = mod_metadata._stored(candidate)
        except (OSError, ValueError):
            continue
        if isinstance(stored, dict) and str(stored.get("id") or candidate.name) == LOADER_ID:
            return candidate
    return None


def ensure_loader_mod(root: Path | None = None) -> Path:
    """The loader mod's folder, created on first use.

    The loader is an ordinary mod in the reader's library (a mod.json with
    no script and no settings), so the Mods tab switches it and other mods
    can require it. A library whose removed debug flag was on migrates
    switched on; the flag file is then deleted.
    """
    folder = checked(Path(root or mods_root()))
    folder.mkdir(parents=True, exist_ok=True)
    found = _loader_folder(folder)
    if found is not None:
        # Update only our description, preserving the reader's other metadata.
        metadata = mod_metadata._stored(found)
        if metadata.get("description") != LOADER_DESCRIPTION:
            metadata["description"] = LOADER_DESCRIPTION
            atomic_write(found / "mod.json", (json.dumps(metadata, indent=2) + "\n").encode("utf-8"))
        _drop_debug_flag(folder)
        return found
    enabled = False
    try:
        enabled = json.loads((folder / DEBUG_FILE).read_text(encoding="utf-8")).get("debugMode") is True
    except (OSError, ValueError, AttributeError):
        enabled = False
    target = checked(folder / LOADER_FOLDER)
    target.mkdir(parents=True, exist_ok=True)
    atomic_write(target / "mod.json", (json.dumps(
        {"id": LOADER_ID, "name": LOADER_NAME, "description": LOADER_DESCRIPTION,
         "enabled": enabled, "order": 0}, indent=2) + "\n").encode("utf-8"))
    _drop_debug_flag(folder)
    return target


def _drop_debug_flag(folder: Path) -> None:
    try:
        (Path(folder) / DEBUG_FILE).unlink(missing_ok=True)
    except OSError:
        pass


def loader_mod_state(root: Path | None = None) -> tuple[bool, bool]:
    """(installed, enabled) for the loader mod. Missing or unreadable is neither."""
    folder = _loader_folder(root or mods_root())
    if folder is None:
        return False, False
    try:
        stored = mod_metadata._stored(folder)
    except (OSError, ValueError):
        return False, False
    return True, isinstance(stored, dict) and stored.get("enabled") is True


def _needs_loader(spec: dict) -> bool:
    """Whether one built native description patches the executable."""
    return bool(spec.get("islands") or spec.get("hooks") or spec.get("sectionVirtualSize"))


def _refuse_without_loader(owners: list[str], root: Path | None) -> None:
    """Refuse executable patches while the loader mod is off, naming who needs it."""
    if not owners:
        return
    installed, enabled = loader_mod_state(root)
    if enabled:
        return
    state = "switched off" if installed else "not installed"
    if len(owners) == 1:
        raise TweakError(f"{owners[0]} requires {LOADER_NAME}, which is {state}.")
    raise TweakError(f"{' and '.join(owners)} require {LOADER_NAME}, which is {state}.")


class BuildContext:
    """What a DS1 tweak script gets from Lexeditor."""

    def __init__(self, enabled: dict[str, Path], game_root: Path | None = None,
                 library_root: Path | None = None, *, cache_root=None):
        self._enabled = enabled
        self.game_root = Path(game_root) if game_root is not None else None
        self._library_root = library_root
        self._cache_root = cache_root
        self._params: bytes | None = None
        self.current = ""
        self._inputs = {}
        self._source_hashes = {}
        self._building_source = None
        self._building_root = None
        self._module_sources = {}

    def _remember(self, kind, name, value):
        token = _sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8'))
        self._inputs.setdefault(kind, {})[name] = token
        return value

    def _originals(self, outputs):
        from . import deployment
        if self.game_root is None:
            return None
        result = {}
        for relative in [exe_patches.EXECUTABLE, *sorted(outputs)]:
            if Path(relative).parts[0] in ('native', 'layout', 'esd'):
                continue
            path = checked(deployment.vanilla_source(self.game_root, Path(relative)))
            if path not in self._source_hashes:
                self._source_hashes[path] = _sha(path.read_bytes()) if path.is_file() else None
            result[relative] = self._source_hashes[path]
        return result

    def cached_build(self, root, outputs):
        """Reuse only verified outputs made from the same source and observed inputs."""
        try:
            manifest = json.loads((root / script_mods.MANIFEST_FILE).read_text('utf-8'))
            record = manifest.get('build')
            if (not isinstance(record, dict) or not record.get('cacheable',True)
                    or record.get('compiler') != _script_compiler_revision()
                    or record.get('source') != script_mods.source_fingerprint(root)
                    or record.get('game') != str(self.game_root)
                    or record.get('originals') != self._originals(outputs)):
                return False
            for relative, digest in outputs.items():
                path = checked(root / relative)
                if not path.is_file() or _sha(path.read_bytes()) != digest:
                    return False
            self._inputs = {}
            for kind, requests in record['inputs'].items():
                for name in requests:
                    if kind == 'enabled':
                        self.enabled(name)
                    elif kind == 'settings':
                        self.settings(name)
                    elif kind == 'module':
                        dependency = self._enabled.get(name)
                        self._remember('module', name, script_mods.source_fingerprint(dependency) if dependency else None)
                    elif kind == 'contributors':
                        self._contributor_sources(name)
                    elif kind == 'file':
                        self.game_file(name)
                    elif kind == 'python':
                        from core.build_dependencies import fingerprint
                        self._remember('python',name,fingerprint(name))
                    elif kind == 'params':
                        self.game_params()
                    else:
                        return False
            return self._inputs == record['inputs']
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return False

    def begin_build(self, root):
        self._inputs = {}
        self._build_cacheable = True
        self._building_root = Path(root).resolve()
        self._building_source = None
        try:
            self._building_source = script_mods.source_fingerprint(root)
        except Exception:
            pass  # Fingerprinting only controls reuse, never the build itself.

    def run_script(self, root, settings):
        from .script_worker import evaluate
        return evaluate(root, settings, self)

    def build_record(self, root, outputs):
        return {'source': self._building_source, 'compiler': _script_compiler_revision(),
                'game': str(self.game_root), 'originals': self._originals(outputs), 'inputs': self._inputs,
                'cacheable':getattr(self,'_build_cacheable',False)}

    def game_file(self, relative: str | Path) -> bytes:
        """Verified pristine game bytes, with their hash recorded as a build input."""
        from . import assets, deployment
        path = Path(str(relative).replace("\\", "/"))
        if (not isinstance(relative, (str, Path)) or not path.parts or path.is_absolute()
                or path.drive or ".." in path.parts
                or any(":" in part or "\0" in part or part.rstrip(" .") != part
                       for part in path.parts)):
            raise TweakError("A game file must name a safe relative path inside the installed game")
        managed = next((item for item in (EXECUTABLE, LAYOUT, *ESD)
                        if path == Path(item.relative)), None)
        if managed is None and not assets.is_owned(path):
            assets.check_relative(path)
        if self.game_root is None:
            raise TweakError("A game folder is required to read a pristine game file")
        game_root = checked(self.game_root)
        checked(game_root / path)
        if managed is not None:
            data = _original(game_root, _read(managed.live(game_root), managed),
                             _manifest(game_root, managed), managed)
        else:
            # Deployment covers structured files and supported assets;
            # native-managed files use their own journals.
            checked(deployment._backup_path(game_root, path))
            checked(deployment._marker_path(game_root, path))
            source = checked(deployment.vanilla_source(game_root, path))
            data = _bounded_file(source,assets.MAX_ASSET_BYTES)
            if data is None:
                raise TweakError(f'{path.name}: the pristine game file is missing')
        self._remember('file', path.as_posix(), _sha(data))
        return data

    def game_params(self) -> bytes | None:
        """The game's GameParam.parambnd.dcx as this Apply deploys it: vanilla
        with every active data mod combined over it in load order, so a tweak
        reads what the game will (another mod's curve or cost edits included).
        None outside an Apply, when no game folder is known."""
        if self.game_root is None:
            self._remember('params', 'game', None)
            return None
        if self._params is None:
            from . import deployment, mod_loader
            selected = None
            try:
                source = checked(deployment.vanilla_source(self.game_root, mod_loader.RELATIVE))
                if not source.is_file():
                    self._remember('params', 'game', None)
                    return None
                mods = mod_loader.active_mods(self._library_root or mods_root(), only=frozenset({mod_loader.RELATIVE}))
                original = source.read_bytes()
                selected = mods  # active_mods already filtered both archives and edits to GameParam.
                combined = mod_loader._compose_files({mod_loader.RELATIVE: original}, selected, False, self._cache_root)
                self._params = combined.files.get(mod_loader.RELATIVE, original)
            except script_mods.ModBuildError:
                raise
            except Exception as error:
                try:
                    if selected is not None:
                        # Use the composer's failure attribution, only on the
                        # exceptional path. The requesting script is innocent.
                        mod_loader.compose_installed(self.game_root, selected, conflicts_only=True)
                except script_mods.ModBuildError:
                    raise
                except Exception:
                    pass
                raise script_mods.ScriptModInfrastructureError(f'Could not read combined game parameters: {error}') from error
        self._remember('params', 'game', _sha(self._params) if self._params is not None else None)
        return self._params

    def enabled(self, mod_id: str) -> bool:
        return self._remember('enabled', mod_id, mod_id in self._enabled)

    def settings(self, mod_id: str) -> dict | None:
        root = self._enabled.get(mod_id)
        try:
            value = script_mods.values(root) if root else None
        except Exception as error:
            raise TweakError(f'{mod_id}: {error}', folders=[root]) from error
        return self._remember('settings', mod_id, value)

    def module(self, mod_id: str, name: str):
        """An enabled dependency's own module, through the shared package loader."""
        root = self._enabled.get(mod_id)
        if root is None:
            raise TweakError(f"{mod_id} must be enabled before reading its build module")
        try:
            source = self._remember('module', mod_id, script_mods.source_fingerprint(root))
            return self._current_module(root,name,source)
        except BaseException as error:
            raise TweakError(f'{mod_id}: {error}', folders=[root]) from error

    def _current_module(self, root, name, source):
        root = Path(root).resolve()
        package_name = script_mods._package_name(root)
        package = sys.modules.get(package_name)
        # Keep the executing package's module state; refresh other packages
        # only when their content identity changes.
        if root != self._building_root or package is None:
            if package is None or self._module_sources.get(root) != (source,package):
                script_mods.load_script(root)
                package = sys.modules[package_name]
                self._module_sources[root] = (source,package)
        return package if name == '__init__' else script_mods.import_module(root,name)

    def _contributor_sources(self, module_name):
        if (not isinstance(module_name,str) or not module_name.isascii()
                or not module_name.isidentifier() or keyword.iskeyword(module_name)):
            raise TweakError('A contributor module name must be a single Python identifier')
        sources = []
        for mod_id, root in self._enabled.items():
            try:
                root = checked(Path(root))
                if checked(root/script_mods.SCRIPT_FOLDER/f'{module_name}.py').is_file():
                    sources.append((mod_id,str(root.resolve()),script_mods.source_fingerprint(root)))
            except (OSError,ValueError) as error:
                raise TweakError(f'{mod_id}: {error}',folders=[root]) from error
        return self._remember('contributors',module_name,sources)

    def contributors(self, module_name: str) -> tuple:
        """Enabled (mod_id, module) pairs for a named script module, in load order.

        Cache replay checks the complete set without executing providers.
        """
        result = []
        for mod_id,root,source in self._contributor_sources(module_name):
            try:
                result.append((mod_id,self._current_module(Path(root),module_name,source)))
            except BaseException as error:
                raise TweakError(f'{mod_id}: {error}',folders=[root]) from error
        return tuple(result)


@lru_cache(maxsize=1)
def _script_compiler_revision():
    from core import build_dependencies
    from . import script_worker
    sources = [inspect.getsource(BuildContext).encode(),sys.version.encode(),
               *(Path(module.__file__).read_bytes() for module in (script_mods,script_worker,build_dependencies))]
    return _sha(b'\0'.join(sources))


@lru_cache(maxsize=1)
def _installation_revision():
    """Link/deploy changes can require Apply while author outputs stay cached."""
    from .mod_loader import _composition_revision
    sources = [_composition_revision(),Path(__file__).read_bytes(),
               *(Path(package/'runtime-manifest.json').read_bytes()
                 for package in (LOADER_PACKAGE,LOADER_PACKAGE/'debug',LOADER_PACKAGE/'online'))]
    return _sha(b'\0'.join(sources))


def build_specs(root: Path | None = None, game_root: Path | None = None, *, cache_root=None, timings=None, original=None) -> list[dict]:
    """Build every enabled tweak mod and read back its executable patches.

    Mods whose build patches the executable need the loader mod switched
    on; anything else builds without it.

    The same build writes any layout/<id>.json or esd/<id>.json; layout_specs and esd_specs read those.
    Every mod's menu-dim/<id>.json joins into one loader-owned description
    at the end (menu_dim.py).
    """
    try:
        mod_requires.check_enabled(root or mods_root())
    except ValueError as error:
        raise TweakError(str(error), folders=getattr(error, 'folders', ())) from error
    rows = [row for row in tweak_rows(root) if row["enabled"]]
    ensure_loader_mod(root)
    context = BuildContext({row["id"]: Path(row["path"]) for row in rows}, game_root, root, cache_root=cache_root)
    script_mods.build_batch(rows, context, allowed_roots=ALLOWED_ROOTS, error=TweakError, timings=timings)
    from . import native_support, native_rules
    if game_root is not None and any((Path(row['path'])/native_rules.SETTINGS_FILE).is_file() for row in rows):
        if original is None:
            original = _read(checked(Path(game_root)/exe_patches.EXECUTABLE))
        native_support.build_sources(rows,original)
    specs = _built([row for row in rows if not row.get('prebuilt')], "native", exe_patches.validate)
    support = native_support.specs(rows)
    dims = _built(rows, menu_dim.FOLDER, menu_dim.validate)
    _refuse_without_loader([spec["owner"] for spec in specs if _needs_loader(spec)]
                           + [spec["owner"] for spec in dims if spec["textIds"]]
                           + [row['name'] for row in rows if row.get('prebuilt') and row.get('module',True)]
                           + [spec['owner'] for spec in support if _needs_loader(spec)], root)
    try:
        dim = menu_dim.patch_spec(dims)
    except ValueError as error:
        raise TweakError(str(error), folders=[spec["folder"] for spec in dims]) from error
    aggregate = exe_patches.validate(dim, menu_dim.OWNER) if dim else None
    if aggregate is not None:
        aggregate['folders'] = list(dict.fromkeys(spec['folder'] for spec in dims))
    return specs + support + ([aggregate] if aggregate is not None else [])


def layout_specs(root: Path | None = None) -> list[dict]:
    """The menu-layout nodes the last build_specs produced."""
    return _built([row for row in tweak_rows(root) if row["enabled"]], "layout", menu_layout.validate)


def esd_specs(root: Path | None = None) -> list[dict]:
    """The menu-script commands the last build_specs produced."""
    return _built([row for row in tweak_rows(root) if row["enabled"]], "esd", menu_scripts.validate)


BUILT_FOLDERS = ('native', 'layout', 'esd', menu_dim.FOLDER, 'native-support')
MAX_BUILT_COMPONENTS = 64
MAX_BUILT_COMPONENT_BYTES = 16 * 1024 * 1024


def built_files(root: Path, kind: str) -> list[Path]:
    """The bounded component files consumed by building and runtime loading."""
    if kind not in BUILT_FOLDERS:
        raise TweakError('Unknown built component folder')
    directory = checked(Path(root)/kind)
    if not directory.exists():
        return []
    files = []
    for path in directory.glob('*.json'):
        files.append(path)
        if len(files) > MAX_BUILT_COMPONENTS:
            raise TweakError(f'{kind} has more than {MAX_BUILT_COMPONENTS} patch components')
    for path in files:
        checked(path)
        if not path.is_file() or path.stat().st_size > MAX_BUILT_COMPONENT_BYTES:
            raise TweakError(f'{kind}/{path.name} is not a bounded patch file')
    return sorted(files)


def read_built(path: Path) -> bytes:
    raw = _bounded_file(path,MAX_BUILT_COMPONENT_BYTES)
    if raw is None:
        raise TweakError(f'{path.name} is missing')
    return raw


def _built(rows: list[dict], folder: str, check) -> list[dict]:
    specs = []
    for row in rows:
        try:
            for target in built_files(Path(row['path']), folder):
                raw = read_built(target)
                value = json.loads(raw)
                if folder == 'native-support':
                    from . import native_support
                    native_support.check_source(Path(row['path']),target.relative_to(row['path']),value)
                spec = check(value, row["name"])
                spec["folder"] = row["path"]
                specs.append(spec)
        except Exception as error:
            raise TweakError(f"{row['name']}: {error}", folders=[row['path']]) from error
    return specs


#: A mod's built native descriptions are small; the Mods tab reads them with
#: a bound, without running anything.
MAX_NATIVE_FILES = 64
MAX_NATIVE_BYTES = 1024 * 1024


def native_spans(folder: Path, owner: str) -> dict[str, list[tuple[int, int]]]:
    """(start, end) of every address a mod's built native patches claim, by kind.

    Reads the mod's native/*.json as last built, without running its script:
    a mod that was never built claims nothing here and is still checked when
    it is enabled. Damaged files are skipped; enabling reports them.
    """
    found: dict[str, list[tuple[int, int]]] = {"hooks": [], "state": [], "islands": []}
    if not script_mods.is_script_mod(folder) and (Path(folder)/'runtime.lxd').is_file():
        from . import runtime_mods
        try:
            checked(Path(folder)/runtime_mods.FILENAME)
            module = runtime_mods.inspect(runtime_mods.read(folder))
            found['hooks'] = [(rva, rva+size) for kind, rva, size, _ in module['records'] if kind == exe_patches.HOOK]
            found['state'] = [(rva, rva+size) for rva, size in module['claims']]
            if module['fixed']:
                found['islands'] = [(rva, rva+size) for kind, rva, size, _ in module['records'] if kind == exe_patches.BLOCK]
        except (ValueError, OSError):
            pass
    try:
        from . import native_support
        files = sorted((Path(folder) / "native").glob("*.json")) if script_mods.is_script_mod(folder) else []
        files += built_files(Path(folder),native_support.FOLDER)
    except OSError:
        return found
    for path in files[:MAX_NATIVE_FILES]:
        try:
            if path.is_symlink() or path.stat().st_size > MAX_NATIVE_BYTES:
                continue
            spec = exe_patches.validate(json.loads(path.read_text(encoding="utf-8")), owner)
        except (OSError, ValueError):
            continue
        for kind, spans in exe_patches.spans(spec).items():
            found[kind] += spans
    return found


def build_fingerprint(folder: Path, *, produced=False) -> str:
    """What the last build of one tweak mod saw, hashed together.

    The switch, load order, name, settings, schema, script and built files:
    anything that changes what the mod builds. The installed record keeps one
    fingerprint per enabled mod; a mod whose fingerprint differs was changed
    since the last build and needs rebuilding. Built files are read post-build,
    so a hand edit to one also asks for a rebuild, which overwrites it from
    the script.
    """
    folder = Path(folder)
    parts = {"source": script_mods.source_fingerprint(folder), 'compiler': _script_compiler_revision(),
             'installationEngine':_installation_revision()}
    try:
        manifest = script_mods._read_json(folder / script_mods.MANIFEST_FILE) or {}
        record = manifest.get('build') or {}
        dependencies = (record.get('inputs') or {}).get('python',{})
        from core import build_dependencies
        if (type(dependencies) is not dict or len(dependencies)>build_dependencies.MAX_INPUTS
                or any(type(name) is not str or not _digest(value) for name,value in dependencies.items())):
            raise ValueError('Invalid compiler dependency record')
        parts['python'] = dict(dependencies) if produced else {
            name:_sha(json.dumps(build_dependencies.fingerprint(name),sort_keys=True,separators=(',',':')).encode())
            for name in dependencies}
    except (script_mods.ScriptModError,OSError,ValueError,TypeError,AttributeError,RuntimeError):
        parts['python'] = None  # An invalid optional cache requests a rebuild.
        record = {}
    from . import native_rules, native_support
    parts['nativeRules'] = native_rules.digest(native_rules._read_optional(folder/native_rules.SETTINGS_FILE,native_rules.SETTINGS_LIMIT))
    parts['nativeSupport'] = {path.name:_sha(read_built(path)) for path in built_files(folder,native_support.FOLDER)}
    if not script_mods.is_script_mod(folder) and (folder/'runtime.lxd').is_file():
        from . import runtime_mods
        checked(folder/runtime_mods.FILENAME)
        parts['prebuilt'] = _sha(runtime_mods.read(folder))
    if produced:
        # Record the source actually used, so an edit by another chat during
        # the build stays stale instead of being stamped as already installed.
        parts['source'] = record.get('source', parts['source'])
        parts['compiler'] = record.get('compiler', parts['compiler'])
    outputs = {}
    for dirname in ALLOWED_ROOTS:
        out_dir = folder / dirname
        if not out_dir.is_dir():
            continue
        for path in sorted(out_dir.rglob("*.json")):
            if not path.is_file() or script_mods.owns(path.relative_to(folder)):
                continue
            try:
                digest = _sha(path.read_bytes())
            except OSError:
                continue
            outputs[path.relative_to(folder).as_posix()] = digest
    parts["outputs"] = outputs
    try:
        generated = script_mods._generated_files(folder, ALLOWED_ROOTS)
    except script_mods.ScriptModError:
        # Status must flag damaged ownership for the normal attributed build
        # failure/recovery path, not silently treat it as an unchanged mod.
        parts['invalidManifest'] = _sha((folder / script_mods.MANIFEST_FILE).read_bytes())
        generated = {}
    parts['generated'] = {relative: _sha((folder / relative).read_bytes())
                          if (folder / relative).is_file() else None
                          for relative in generated}
    return _sha(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8"))


STUCK_GAME = ('A closed Dark Souls Remastered is still listed by Windows and keeps DarkSoulsRemastered.exe locked (a crashed game whose process cannot be ended). Close every Lexeditor window; if DarkSoulsRemastered.exe is still in Task Manager after that, restart Windows. Then try again; nothing was lost.')
EXECUTABLE_CHANGED = ('Native mods need the verified Steam executable. Verify Dark Souls Remastered game files in Steam, '
                      'then apply the mods again. Lexeditor leaves the executable and its old backups untouched.')


def ensure_game_closed() -> None:
    if os.name != "nt":
        raise TweakError("Executable tweaks can only be applied on Windows")
    if live_processes([exe_patches.EXECUTABLE]):
        raise TweakError("Close Dark Souls Remastered before applying mods")


def game_closed() -> bool:
    """True when a tweak install may run now: Windows, and the game shut."""
    try:
        ensure_game_closed()
    except TweakError:
        return False
    return True


LOCKED_SUFFIX = ".lexeditor-locked"
# Moved-aside copies kept per data file; small loader files have a larger cap.
MAX_LOCKED = 4
MAX_LOCKED_SMALL = 64
SMALL_FILE = 1024 * 1024


def _move_aside(game_root: Path, live: Path, error: Exception) -> Path:
    """Rename a pinned file out of the way, keeping at most MAX_LOCKED of each.

    Windows can pin a loaded DLL or data file after a crash. The executable
    is excluded from this writer and is never moved aside.
    """
    if live.suffix.casefold() == '.exe':
        raise TweakError('Lexeditor never moves a game executable') from error
    _clear_moved_aside(game_root)
    limit = MAX_LOCKED_SMALL if live.is_file() and live.stat().st_size <= SMALL_FILE else MAX_LOCKED
    for index in range(limit):
        try:
            target = checked(live.with_name(live.name + LOCKED_SUFFIX + (f"-{index}" if index else "")))
        except TweakError:
            continue  # An unsafe leftover occupies this slot; preserve it.
        if target.exists():
            continue
        try:
            os.replace(live, target)
            return target
        except OSError:
            break
    raise TweakError(f"Windows will not let Lexeditor replace or move {live.name}. {STUCK_GAME}") from error


def _clear_moved_aside(game_root: Path) -> None:
    """Delete files moved aside earlier, once Windows has let go of them."""
    owned = {name.casefold() for name in (RUNTIME_DLL, RUNTIME_PATCH, RUNTIME_RECORD, RUNTIME_LOG, RUNTIME_CONFIG)}
    for path in Path(game_root).glob("*" + LOCKED_SUFFIX + "*"):
        if path.name.casefold().split(LOCKED_SUFFIX, 1)[0] not in owned:
            continue
        try:
            checked(path).unlink()
        except (OSError, TweakError):
            pass  # still pinned; a later Apply or Restore tries again


def _put(game_root: Path, path: Path, data: bytes) -> None:
    """Write a game-folder file, moving a pinned old copy aside first."""
    if path.suffix.casefold() == '.exe':
        raise TweakError('Lexeditor never writes a game executable')
    try:
        atomic_write(path, data)
    except PermissionError as error:
        moved = _move_aside(game_root, path, error)
        try:
            atomic_write(path, data)
        except Exception as failure:
            try:
                if not path.exists():
                    os.replace(moved,path)
            except OSError as rollback_error:
                raise TweakError(f'Could not replace {path.name}: {failure}; restoring its moved copy failed: {rollback_error}') from failure
            raise


def _remove(game_root: Path, path: Path) -> None:
    """Delete a game-folder file, or move it aside when it is pinned."""
    if path.suffix.casefold() == '.exe':
        raise TweakError('Lexeditor never deletes a game executable')
    try:
        path.unlink(missing_ok=True)
    except PermissionError as error:
        _move_aside(game_root, path, error)


# No project argument means retain the last explicitly applied project rules.
# Passing None removes that contribution, without disabling library tweak mods.
_KEEP_PROJECT = object()


def locked(game_root: Path):
    """Hold the tweak lock across a whole prepare, commit and rollback."""
    return _exclusive(checked(Path(game_root)))


def _digest(value) -> bool:
    return (type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _mod_names(value) -> bool:
    return type(value) is list and all(type(name) is str and name for name in value)


def _project(value):
    if value is None:
        return None
    if (type(value) is not dict or set(value) != {"path", "settingsHash", "spec"}
            or type(value["path"]) is not str or not value["path"]
            or not _digest(value["settingsHash"])):
        raise TweakError("The saved native project description is damaged")
    try:
        exe_patches.validate(value["spec"], "Project native rules")
    except (ValueError, exe_patches.PatchError) as error:
        raise TweakError("The saved native project description is damaged") from error
    return value


def _manifest(game_root: Path, managed: Managed = EXECUTABLE) -> dict:
    """A file's ownership record: version 1 (tweaks) or 2 (plus project rules).

    Read with a hard bound, and refuse anything damaged, including a damaged
    pending entry: a journal is only trusted when every hash in it is real.
    """
    path = checked(managed.manifest(game_root))
    if not path.exists():
        return {}
    damaged = f"The {managed.label} tweak manifest is damaged"
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST:
        raise TweakError(f"The {managed.label} tweak manifest is missing or too large")
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST:
        raise TweakError(f"The {managed.label} tweak manifest grew beyond its limit")
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise TweakError(damaged) from error
    if (type(data) is not dict or type(data.get("version")) is not int or data["version"] not in (1, 2)
            or not _digest(data.get("sha256")) or not _mod_names(data.get("mods"))):
        raise TweakError(damaged)
    if 'originalHash' in data and (managed == EXECUTABLE or not _digest(data['originalHash'])):
        raise TweakError(damaged)
    keys = {"sha256", "mods"} | ({"project"} if data["version"] == 2 else set())
    pending = data.get("pending")
    if pending is not None and (type(pending) is not dict or set(pending) - {"inputs"} != keys
                                or not _digest(pending["sha256"]) or not _mod_names(pending["mods"])):
        raise TweakError(damaged)
    if data["version"] == 2:
        _project(data.get("project"))
        if pending is not None:
            _project(pending["project"])
    return data


def _menu_baseline(current: bytes, managed: Managed) -> bool:
    """Recognize data we can edit; this never relaxes executable identity."""
    from . import formats, esd
    try:
        if managed == LAYOUT:
            layout = menu_layout.Drb(formats.inflate(current))
            for dialog in layout.dialogs():
                layout.nodes(dialog)
            return True
        if managed in ESD:
            plain = formats.inflate(current)
            entries = formats.members(plain)
            scripts = [entry for name,entry in entries.items() if name.endswith('.esd')]
            if not scripts:
                return False
            for entry in scripts:
                esd.parse(bytes(plain[entry.offset:entry.offset+entry.size]))
            return True
    except (ValueError,IndexError,KeyError,struct.error):
        return False
    return False


def _original_matches(original: bytes, manifest: dict, managed: Managed) -> bool:
    digest = manifest.get('originalHash')
    return _sha(original) == digest if digest is not None else managed.vanilla(original)


def _original(game_root: Path, current: bytes, manifest: dict, managed: Managed = EXECUTABLE) -> bytes:
    """The verified deployment baseline, including a preserved foreign menu."""
    backup = checked(managed.backup(game_root))
    if backup.exists():
        original = _read(backup, managed)
        if not _original_matches(original,manifest,managed):
            raise TweakError(f"The preserved original {managed.label} changed; refusing to continue")
        if not manifest and current != original:
            raise TweakError(f'The installed {managed.label} differs from its unmanaged preserved copy; both were kept')
        return original
    if managed.vanilla(current) or (not manifest and _menu_baseline(current,managed)):
        return current
    raise TweakError(f"The preserved original {managed.label} is missing; refusing to continue")


def _owned(current: bytes, manifest: dict, managed: Managed = EXECUTABLE) -> bool:
    if managed.vanilla(current):
        return True
    digest = _sha(current)
    if manifest:
        return digest in (manifest.get("sha256"), (manifest.get("pending") or {}).get("sha256"))
    return _menu_baseline(current,managed)


def _current_manifest(current: bytes, manifest: dict, managed: Managed = EXECUTABLE) -> dict:
    """Which recipe produced the bytes, including a write interrupted before completion."""
    pending = manifest.get("pending")
    if pending and _sha(current) == pending["sha256"]:
        return {**({'originalHash':manifest['originalHash']} if 'originalHash' in manifest else {}),
                "version": 2, "sha256": pending["sha256"], "mods": list(pending["mods"]),
                "project": pending.get("project"), "inputs": pending.get("inputs"), "pending": None}
    vanilla = managed.vanilla(current)
    return {**({'originalHash':manifest['originalHash']} if 'originalHash' in manifest else {}),
            "version": 2, "sha256": _sha(current),
            "mods": [] if vanilla else list(manifest.get("mods", [])),
            "project": None if vanilla else manifest.get("project"),
            "inputs": None if vanilla else manifest.get("inputs"),
            "pending": None}


def _save_manifest(game_root: Path, value: dict, managed: Managed = EXECUTABLE) -> None:
    raw = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_MANIFEST:
        raise TweakError(f"The {managed.label} tweak manifest exceeds its size limit")
    atomic_write(checked(managed.manifest(game_root)), raw)


def _finish_manifest(game_root: Path, current: bytes, mods: list[str], project=None,
                     managed: Managed = EXECUTABLE, *, inputs=None, original_hash=None) -> None:
    if managed.vanilla(current) and not mods and project is None:
        checked(managed.manifest(game_root)).unlink(missing_ok=True)
    else:
        _save_manifest(game_root, {**({'originalHash':original_hash} if original_hash is not None else {}),
                                   "version": 2, "sha256": _sha(current), "mods": list(mods),
                                   "project": project, "inputs": inputs, "pending": None}, managed)


def _write(game_root: Path, before: bytes, after: bytes, mods: list[str],
           managed: Managed = EXECUTABLE, project=None, *, inputs=None, before_write=None) -> None:
    """Journal one expected-image replacement; keep the original plus the latest intent."""
    if Path(managed.relative).suffix.casefold() == '.exe':
        raise TweakError('Lexeditor never writes a game executable')
    game_root = checked(Path(game_root))
    live = checked(managed.live(game_root))
    backup = checked(managed.backup(game_root))
    old = _manifest(game_root, managed)
    if not _owned(before, old, managed) or _read(live, managed) != before:
        raise TweakError(f"The {managed.label} changed while the tweaks were being prepared")
    original = _original(game_root, before, old, managed)
    if (managed in (LAYOUT, *ESD) and after != before
            and (len(after) > managed.limit or not _menu_baseline(after, managed))):
        raise TweakError(f'The composed {managed.label} is invalid; nothing was written')
    project = _project(project)
    desired = {"sha256": _sha(after), "mods": list(mods), "project": project}
    if inputs is not None:
        desired['inputs'] = inputs
    journal = {**_current_manifest(before, old, managed), "pending": desired}
    if managed != EXECUTABLE:
        journal['originalHash'] = _sha(original)
    # Check the bound before creating a backup or replacing anything.
    if len(json.dumps(journal, allow_nan=False).encode("utf-8")) > MAX_MANIFEST - 1024:
        raise TweakError(f"The {managed.label} tweak manifest exceeds its size limit")
    if after == before and not old and not mods and project is None:
        return
    if not backup.exists():
        # Exclusive creation cannot overwrite an unmanaged file or a link.
        with backup.open("xb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if _read(backup, managed) != original:
            raise TweakError(f"The original {managed.label} backup did not verify")
    # Journal first. A crash before or after replacement leaves one of these
    # two complete, known images; neither an arbitrary hash nor a partial file
    # is accepted. Restore uses the same protocol.
    _save_manifest(game_root, journal, managed)
    (before_write or ensure_game_closed)()
    if _read(live, managed) != before:
        raise TweakError(f"The {managed.label} changed before replacement")
    if after != before:
        # A pinned file is moved aside and the new one written in its place;
        # the journal above covers an interruption.
        _put(game_root, live, after)
    if _read(live, managed) != after:
        raise TweakError(f"{managed.label.capitalize()} verification failed; the original and pending intent were kept")
    _finish_manifest(game_root, after, mods, project, managed, inputs=inputs,
                     original_hash=_sha(original) if managed != EXECUTABLE else None)


def _installed(game_root: Path, managed: Managed, action: str) -> tuple[bytes, dict]:
    current = _read(managed.live(game_root), managed)
    manifest = _manifest(game_root, managed)
    if not _owned(current, manifest, managed):
        raise TweakError(f"The installed {managed.label} was changed outside Lexeditor; {action}")
    return current, manifest


def _layout_in_use(game_root: Path) -> bool:
    """The layout is managed once a tweak changed it, until it is restored."""
    return checked(LAYOUT.manifest(game_root)).is_file() or checked(LAYOUT.backup(game_root)).exists()


def _esd_in_use(game_root: Path, managed: Managed) -> bool:
    """A menu script archive is managed once a tweak changed it, until restored."""
    # A restored original can retain its backup; only the journal owns it.
    return checked(managed.manifest(game_root)).is_file()


def _changes(specs: list[dict]) -> list[str]:
    """Only mods that change something are recorded as applied."""
    return [spec["owner"] for spec in specs
            if spec.get("islands") or spec.get("hooks") or spec.get("sectionVirtualSize")
            or spec.get("nodes") or spec.get("moves") or spec.get("changes")]


# --- The in-memory loader ------------------------------------------------------
#
# Tweaks are never written into DarkSoulsRemastered.exe. Apply puts Lexeditor's
# loader (dinput8.dll, built from plugins/ds1/runtime/) beside it with the
# combined patch description; the game loads the DLL before its own code runs
# and the DLL patches the game in memory. A crashed game Windows keeps listed
# locks only the executable, which is never written or moved. Old executable
# copies are preserved; Steam verification restores an altered game image.

RUNTIME_DLL = "dinput8.dll"
RUNTIME_PATCH = "lexeditor-ds1-patch.bin"
RUNTIME_RECORD = "lexeditor-ds1-runtime.json"
RUNTIME_LOG = "lexeditor-ds1-patch.log"
RUNTIME_CONFIG = 'lexeditor-ds1.ini'
LOADER_PACKAGE = Path(__file__).with_name("runtime") / "package"
MAX_RUNTIME = 16 * 1024 * 1024
# Any of these in the game folder means Lexeditor's tweaks are, or were, installed.
OWNED_FILES = (MANIFEST_FILE, BACKUP_FILE, RUNTIME_RECORD, RUNTIME_PATCH, RUNTIME_CONFIG)


def loader_manifest(package: Path) -> dict:
    with (package/'runtime-manifest.json').open('rb') as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise TweakError("Lexeditor's published loader metadata exceeds its size limit")
    value = json.loads(raw)
    if (type(value) is not dict or not _digest(value.get('sha256'))
            or type(value.get('previousSha256',[])) is not list or len(value.get('previousSha256',[])) > 128
            or not all(_digest(digest) for digest in value.get('previousSha256',[]))):
        raise TweakError("Lexeditor's published loader metadata is damaged")
    return value


def loader_bytes(debug: bool = False, *, online: bool = False) -> bytes:
    """The shipped loader, checked against the hash it was published with.

    The debug loader (runtime/package/debug) blocks the game's network and
    switches Arxan off with dearxan, so a debugger can attach (#742).
    Apply installs the online build with reporting protection and isolated saves."""
    if debug and online:
        raise TweakError("Choose the debug or online loader")
    package = LOADER_PACKAGE / "online" if online else LOADER_PACKAGE / "debug" if debug else LOADER_PACKAGE
    manifest = loader_manifest(package)
    with (package/RUNTIME_DLL).open('rb') as stream:
        data = stream.read(MAX_RUNTIME+1)
    if len(data) > MAX_RUNTIME:
        raise TweakError("Lexeditor's shipped loader exceeds its size limit")
    if _sha(data) != manifest.get("sha256"):
        raise TweakError("Lexeditor's DS1 loader does not match its published hash; reinstall Lexeditor")
    return data


# Removed flag, read once to migrate: a debug install becomes an enabled loader mod.


DEBUG_FILE = ".lexeditor-ds1.json"


def runtime_record(game_root: Path) -> tuple[dict | None, str]:
    """Read shared runtime metadata without making a cache an activation gate.

    The optional legacy project recipe is not reconstructible from mod folders.
    A damaged record therefore reports that loss rather than claiming it loaded.
    Protected paths still fail closed; they are never treated as disposable.
    """
    record_path = checked(Path(game_root) / RUNTIME_RECORD)
    if not record_path.exists():
        return None, ''
    try:
        if not record_path.is_file() or record_path.stat().st_size > MAX_MANIFEST:
            raise ValueError('Invalid record size')
        with record_path.open('rb') as stream:
            raw = stream.read(MAX_MANIFEST + 1)
        if len(raw) > MAX_MANIFEST:
            raise ValueError('The record grew beyond its limit')
        record = json.loads(raw)
        if (type(record) is not dict or record.get("version") != 1 or not _mod_names(record.get("mods"))
                or not _digest(record.get("patchSha256")) or not _digest(record.get("dllSha256"))):
            raise TweakError("Lexeditor's loader record is damaged")
        _project(record.get("project"))
        built = record.get("built")
        if built is not None and (type(built) is not dict or not all(
                type(key) is str and _digest(value) for key, value in built.items())):
            raise TweakError("Lexeditor's loader record is damaged")
        modules = record.get('modules', {})
        if (type(modules) is not dict or len(modules) > 128
                or any(type(path) is not str or not _digest(value) for path, value in modules.items())):
            raise TweakError("Lexeditor's prebuilt mod record is damaged")
        recovery = record.get('recovery', '')
        if type(recovery) is not str or len(recovery) > 2000:
            raise ValueError('Invalid recovery notice')
        return record, recovery
    except (ValueError, OSError, RecursionError):
        return None, ('The installed loader record is damaged. Folder mods can be rebuilt, '
                      'but any legacy Project native rules must be applied again from their project.')


def _runtime(game_root: Path) -> dict:
    """What Lexeditor's loader files in the game folder hold now."""
    game_root = Path(game_root)
    patch_path, dll_path = (checked(game_root / name) for name in (RUNTIME_PATCH, RUNTIME_DLL))
    record, problem = runtime_record(game_root)
    patch = None
    if patch_path.exists():
        try:
            if not patch_path.is_file() or patch_path.stat().st_size > MAX_RUNTIME:
                raise ValueError('Invalid patch size')
            with patch_path.open('rb') as stream:
                patch = stream.read(MAX_RUNTIME + 1)
            if len(patch) > MAX_RUNTIME:
                raise ValueError('The patch grew beyond its limit')
            if patch:
                exe_patches.read_runtime_patch(patch)
        except (ValueError, OSError, struct.error):
            patch = None
            problem = problem or 'The installed shared patch is damaged; apply the mods again to rebuild it.'
    dll = _sha(_read(dll_path, RUNTIME_FILE)) if dll_path.exists() else None
    # A cache's self-declared hash cannot establish ownership of a foreign DLL.
    ours = {_sha(loader_bytes()), _sha(loader_bytes(debug=True)), _sha(loader_bytes(online=True))}
    for package in (LOADER_PACKAGE,LOADER_PACKAGE/'debug',LOADER_PACKAGE/'online'):
        ours.update(loader_manifest(package).get('previousSha256',[]))
    active = bool(record and patch is not None and dll in ours and dll == record['dllSha256']
                  and _sha(patch) == record['patchSha256'])
    if record and not active and not problem:
        problem = 'Installed loader files are incomplete or changed; apply the mods again to rebuild them.'
    return {"record": record, "patch": patch, "dll": dll, 'problem': problem,
            "foreignDll": dll is not None and dll not in ours,
            "active": active}


def _runtime_status(game_root: Path) -> dict:
    state = _runtime(game_root)
    result = {"applied": list(state["record"]["mods"]) if state["active"] else [],
              "project": state["record"].get("project") if state["active"] else None,
              'built': dict(state['record'].get('built') or {}) if state['active'] else {},
              "problem": state['problem'], "loaderMessage": "",
              "installed": bool(state['record'] or state['patch'] is not None
                                or state['dll'] is not None and not state['foreignDll'])}

    if state["foreignDll"] and (state["record"] or state["patch"] is not None):
        result["problem"] = (f"Another mod's {RUNTIME_DLL} replaced Lexeditor's loader, so the tweaks are not loaded. "
                             "Remove it, then Apply again.")
    log = checked(Path(game_root) / RUNTIME_LOG)
    if log.is_file() and log.stat().st_size <= 65536:
        result["loaderMessage"] = log.read_text(encoding="utf-8", errors="replace").strip()
    return result


ONLINE_NOTICE = ("Mods use separate characters with multiplayer protection. "
                 "Removing the loader returns to your vanilla characters.")


def launch_notice(game_root: Path) -> str:
    """Describe the installed runtime; old offline loaders remain identified."""
    try:
        runtime = _runtime(checked(Path(game_root)))
    except (ValueError, OSError):
        return ""
    if not runtime["active"]:
        return ""
    if runtime["dll"] == _sha(loader_bytes(online=True)):
        return ONLINE_NOTICE
    return "Online play is off: the installed loader needs updating."


def needs_rebuild(game_root: Path, root: Path | None = None) -> dict:
    """Whether the installed tweaks differ from the library, and which mods changed.

    Save rebuilds installed mods and repairs missing metadata for an owned
    loader. An untouched game has nothing to rebuild: first installation is
    explicit through the Mods switches. Damaged metadata and an unreadable
    library remain status problems rather than exceptions from this probe.
    """
    result: dict = {"needed": False, "stale": [], "set": False}
    try:
        runtime = _runtime(checked(Path(game_root)))
    except (ValueError, OSError):
        return result
    record = runtime["record"]
    if record is None:
        result['needed'] = bool(runtime['dll'] is not None and not runtime['foreignDll']
                                or runtime['patch'] is not None)
        return result
    modules_changed = False
    for path, expected in (record.get('modules') or {}).items():
        try:
            from .runtime_mods import read
            target = Path(path)
            if target.name != 'runtime.lxd' or target.parent.parent.resolve() != Path(root or mods_root()).resolve():
                modules_changed = True
                continue
            if _sha(read(checked(Path(path)).parent)) != expected:
                modules_changed = True
        except (ValueError, OSError):
            modules_changed = True
    try:
        rows = [row for row in tweak_rows(root) if row["enabled"]]
    except (ValueError, OSError):
        return result
    built = record.get("built") or {}
    stale = []
    for row in rows:
        try:
            digest = build_fingerprint(Path(row["path"]))
        except (ValueError, OSError):
            # tweak_rows just read this mod fine; a lock landing between
            # that and this read is transient interference, not a change.
            # Calling it stale flashed the changed alert on and off.
            continue
        if built.get(row["id"]) != digest:
            stale.append(row["id"])
    result["stale"] = sorted(stale)
    result["set"] = set(built) != {row["id"] for row in rows}

    result["needed"] = bool(stale) or result["set"] or modules_changed or not runtime['active']
    return result


def _bounded_file(path: Path, limit: int, *, cache=False):
    path = checked(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise TweakError(f'{path.name} is not a regular file')
    stat = path.stat()
    if stat.st_size > limit:
        if not cache:
            raise TweakError(f'{path.name} exceeds its supported size')
        return {'oversized':(stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)}
    with path.open('rb') as stream:
        raw = stream.read(stat.st_size+1)
    if len(raw) > limit:
        raise TweakError(f'{path.name} grew beyond its size limit')
    if len(raw) != stat.st_size:
        raise TweakError(f'{path.name} changed size while it was being read')
    return raw


def _runtime_file(game_root: Path, name: str):
    limits = {RUNTIME_DLL:MAX_RUNTIME,RUNTIME_PATCH:MAX_RUNTIME,RUNTIME_RECORD:MAX_MANIFEST,
              RUNTIME_CONFIG:MAX_MANIFEST,RUNTIME_LOG:MAX_MANIFEST}
    if name not in limits:
        raise TweakError('Unsupported runtime transaction target')
    return _bounded_file(game_root/name,limits[name],cache=name in (RUNTIME_PATCH,RUNTIME_RECORD,RUNTIME_LOG))


def _rollback_runtime(game_root: Path, receipt: dict) -> None:
    errors = []
    for name,item in reversed(list(receipt.items())):
        try:
            current = _runtime_file(game_root,name)
            if current == item['before']:
                continue
            if current != item['after']:
                raise TweakError(f'{name} changed during runtime rollback; its new contents were preserved')
            ensure_game_closed()
            before = item['before']
            if before is None:
                _remove(game_root,checked(game_root/name))
            elif type(before) is dict:
                # An oversized disposable cache had no loadable prior state.
                # Keep a small explicit repair marker instead of copying an
                # unbounded corrupt blob or fabricating a valid ownership record.
                _put(game_root,checked(game_root/name),b'Runtime cache requires rebuild.\n')
            else:
                _put(game_root,checked(game_root/name),before)
        except Exception as error:
            errors.append(str(error))
    if errors:
        raise TweakError('; '.join(errors))


def _runtime_batch(game_root: Path, writes: dict, *, expected=None) -> dict:
    receipt = {name:{'before':_runtime_file(game_root,name),'after':after} for name,after in writes.items()}
    if expected is not None and any(item['before'] != expected[name] for name,item in receipt.items()):
        raise TweakError('Loader files changed while the mods were being prepared')
    done = {}
    try:
        for name,item in receipt.items():
            if item['before'] == item['after']:
                continue
            ensure_game_closed()
            if _runtime_file(game_root,name) != item['before']:
                raise TweakError(f'{name} changed during runtime installation')
            done[name] = item
            if item['after'] is None:
                _remove(game_root,checked(game_root/name))
            else:
                _put(game_root,checked(game_root/name),item['after'])
    except Exception as failure:
        try:
            _rollback_runtime(game_root,done)
        except Exception as rollback_error:
            raise TweakError(f'Runtime installation failed: {failure}; rollback failed: {rollback_error}') from failure
        raise
    return done


def _write_runtime(game_root: Path, patch: bytes | None, mods: list[str], project,
                   built: dict | None = None, *, library=None, modules=None, expected=None) -> dict:
    """Install, replace or remove the loader and its patch description.

    With the loader mod on, the loader goes in even with no tweak to apply."""
    game_root = checked(Path(game_root))
    state = _runtime(game_root)
    if patch is None:
        # The DLL first: without it the game never reads the rest.
        writes = {}
        if state["dll"] is not None and not state["foreignDll"]:
            writes[RUNTIME_DLL] = None
        writes.update({name:None for name in (RUNTIME_PATCH,RUNTIME_RECORD,RUNTIME_LOG,RUNTIME_CONFIG)})
        return _runtime_batch(game_root,writes,expected=expected)
    if state["foreignDll"]:
        raise TweakError(f"Another mod's {RUNTIME_DLL} is in the game folder. Lexeditor's loader needs that name; "
                         "preserve the other loader as dinput8.chain.dll, then Apply again. "
                         "Do not replace an existing chained loader. Nothing was changed.")
    loader = loader_bytes(online=True)
    record = {"version": 1, "mods": list(mods), "project": _project(project),
              "patchSha256": _sha(patch), "dllSha256": _sha(loader),
              "built": dict(built or {}), 'modules': dict(modules or {})}
    # A malformed record may have held an unrecoverable legacy project recipe.
    # Keep that fact visible after rebuilding healthy folder contributions.
    _old_record, recovery = runtime_record(game_root)
    if recovery and project is None:
        record['recovery'] = recovery
    raw = (json.dumps(record, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_MANIFEST or len(patch) > MAX_RUNTIME:
        raise TweakError("The combined tweaks are too large")
    # The record names the DLL as Lexeditor's, so it goes last: a DLL write
    # that fails must not leave a record claiming a DLL that is not there.
    return _runtime_batch(game_root,{RUNTIME_DLL:loader,RUNTIME_PATCH:patch,
                          RUNTIME_CONFIG:_library_configuration(Path(library or mods_root())),RUNTIME_RECORD:raw},
                          expected=expected)


def configure_library(game_root: Path, library: Path) -> None:
    _put(game_root,checked(game_root/RUNTIME_CONFIG),_library_configuration(library))


def _library_configuration(library: Path) -> bytes:
    library = checked(Path(library)).absolute()
    if any(character in str(library) for character in '\r\n'):
        raise TweakError('The mod library path contains a line break')
    import sys
    engine = Path(__file__).resolve().parents[2]
    contents = '[Mods]\nLibrary='+str(library)+'\n[Runtime]\nPython='+sys.executable+'\nEngine='+str(engine)+'\n'
    return contents.encode('utf-16')


def _menu_cache_value(value):
    if isinstance(value, bytes):
        return {'__bytes__': value.hex()}
    raise TypeError(f'Unsupported menu cache value: {type(value).__name__}')


def prepared_menu_layout(game_root: Path, files: list[dict]) -> bytes | None:
    """The future layout when planned, otherwise the actual installed layout."""
    for item in files:
        if item.get('managed') == LAYOUT:
            return item['after']
    path = checked(LAYOUT.live(game_root))
    return _read(path,LAYOUT) if path.is_file() else None


def _menu_identity(original, specs, managed):
    try:
        from .mod_loader import _composition_revision
        kind = 'layout' if managed == LAYOUT else ESD_ARCHIVE[managed]
        return _sha(json.dumps([_composition_revision().hex(), kind, managed.relative, _sha(original), specs],
                              sort_keys=True, separators=(',', ':'), default=_menu_cache_value).encode('utf-8'))
    except (OSError, TypeError, ValueError):
        return None  # Optional recipe metadata cannot prevent composition.


def _compose_menu(original, specs, managed, cache_root, *, current=None, manifest=None):
    """Reuse unchanged layout/menu-script archives with the same bounded output cache."""
    identity = _menu_identity(original, specs, managed)
    # The journal already verifies which bytes are installed. Remember their
    # recipe there, so eviction from the disposable archive cache cannot force
    # an unchanged menu through decompression, composition and compression.
    if identity is not None and current is not None and manifest is not None and _owned(current, manifest, managed):
        if _current_manifest(current, manifest, managed).get('inputs') == identity:
            return current
    key = None
    if cache_root is not None and identity is not None:
        from . import composition_cache
        try:
            key = identity.encode('ascii')
            cached = composition_cache.load(cache_root, key)
            if cached is not None:
                return cached
        except Exception:
            key = None  # Reuse is optional; composition still works without it.
    result = (menu_layout.compose(original, specs) if managed == LAYOUT else
              menu_scripts.compose(original, specs, ESD_ARCHIVE[managed]))
    if key is not None:
        try:
            composition_cache.store(cache_root, key, result)
        except Exception:
            pass
    return result


def prepare(game_root: Path, root: Path | None = None, *, project=_KEEP_PROJECT, cache_root=None) -> dict:
    """Build and check every file's new contents before the caller changes anything.

    Hold locked(game_root) from here through commit or rollback.
    """
    ensure_game_closed()
    game_root = checked(Path(game_root))
    _clear_moved_aside(game_root)
    current = _read(EXECUTABLE.live(game_root))
    if not is_vanilla(current):
        raise TweakError(EXECUTABLE_CHANGED)
    original = current
    claim_menu_files(game_root)
    runtime = _runtime(game_root)
    expected_runtime = {name:_runtime_file(game_root,name) for name in
                        (RUNTIME_DLL,RUNTIME_PATCH,RUNTIME_RECORD,RUNTIME_CONFIG,RUNTIME_LOG)
                        if name != RUNTIME_DLL or not runtime['foreignDll']}
    # A project contribution can depend on verified original instruction bytes.
    chosen = (runtime.get('record') or {}).get('project') if project is _KEEP_PROJECT else (
        project(original) if callable(project) else project)
    chosen = _project(chosen)
    if chosen is not None:
        from . import native_support
        # Once this folder has ordinary mod-native properties, its switch is
        # authoritative, including when it is off. Retire the old global copy.
        if native_support.owns_project(chosen,[root or mods_root()]):
            chosen = None
    if chosen is not None and _needs_loader(chosen["spec"]):
        _refuse_without_loader(["Project native rules"], root)
    script_timings = []
    native = build_specs(root, game_root, cache_root=cache_root, timings=script_timings, original=original)
    # Fingerprinted after the build, so the fingerprint covers the built files too.
    built = {}
    for row in tweak_rows(root):
        if row['enabled']:
            try:
                built[row['id']] = build_fingerprint(Path(row['path']),produced=True)
            except (ValueError,OSError) as error:
                raise TweakError(f"{row['name']}: {error}",folders=[row['path']]) from error
    layout = layout_specs(root)
    scripts = esd_specs(root)
    loader = loader_mod_state(root)[1]
    specs = native + ([exe_patches.validate(chosen["spec"], "Project native rules")] if chosen else [])
    try:
        # Validate the complete native set together. Ordinary mod code is
        # linked independently at startup; only shared menu/project support
        # remains in the loader-owned patch.
        exe_patches._layout(original, specs)
        from . import runtime_mods
        module_writes, module_hashes, modules = [], {}, []
        module_bytes = 0
        for row in tweak_rows(root):
            if not row['enabled']:
                continue
            folder = checked(Path(row['path']))
            target = checked(folder/runtime_mods.FILENAME)
            try:
                before = _bounded_file(target,runtime_mods.MAX_SIZE,cache=not row.get('prebuilt'))
            except (ValueError,OSError) as error:
                raise TweakError(f"{row['name']}: {error}",folders=[folder]) from error
            if row.get('prebuilt'):
                if before is None:
                    if row.get('module',True):
                        raise TweakError(f"{row['name']}: missing prebuilt mod", folders=[folder])
                else:
                    try:
                        runtime_mods.inspect(before)
                    except exe_patches.PatchError as error:
                        raise TweakError(f"{row['name']}: {error}", folders=[folder]) from error
                after = before
                if after is not None and any(built_files(folder,kind) for kind in BUILT_FOLDERS[1:]):
                    after = runtime_mods.require_data(after)
                    if before != after:
                        module_writes.append({'path':str(target),'before':before,'after':after})
            else:
                owned = [spec for spec in native if spec.get('folder') == row['path'] and not spec.get('shared')]
                from . import mod_loader
                requires_data = bool(mod_loader.content_files(folder, row['name'])) or any(
                    built_files(folder, kind) for kind in BUILT_FOLDERS[1:])
                try:
                    after = runtime_mods.build(original, owned, requires_data=requires_data)
                except exe_patches.PatchError as error:
                    raise TweakError(f"{row['name']}: {error}",folders=[folder]) from error
                if before != after:
                    module_writes.append({'path': str(target), 'before': before, 'after': after})
            if after is not None:
                module_bytes += len(after)
                if module_bytes > runtime_mods.MAX_TOTAL_SIZE:
                    raise TweakError('Enabled native modules exceed their combined size limit',folders=[folder])
                module_hashes[str(target)] = _sha(after)
                modules.append({'folder':str(folder),'data':after})
        patch = runtime_mods.shared_patch(original, [spec for spec in specs if not spec.get('folder') or spec.get('shared')], modules)
        # Prebuilt mods have no source description to feed the old combined
        # composer. Check their actual compiled claims together with sources.
        claimed = []
        writes = {item['path']: item['after'] for item in module_writes}
        for row in tweak_rows(root):
            if not row['enabled']:
                continue
            target = checked(Path(row['path'])/runtime_mods.FILENAME)
            data = writes.get(str(target)) if str(target) in writes else (runtime_mods.read(target.parent) if target.is_file() else None)
            if data is None:
                continue
            module = runtime_mods.inspect(data)
            ranges = [(rva, rva+size) for kind, rva, size, _ in module['records']
                      if kind == exe_patches.HOOK or kind == exe_patches.BLOCK and module['fixed']]
            ranges += [(rva, rva+size) for rva, size in module['claims']]
            for low, high in ranges:
                for other_low, other_high, name in claimed:
                    if low < other_high and other_low < high:
                        raise TweakError(f"{row['name']} conflicts with {name} at {max(low,other_low):X}", folders=[row['path']])
            claimed.extend((low, high, row['name']) for low, high in ranges)
    except exe_patches.PatchError as error:
        raise TweakError(str(error), folders=error.folders) from error
    if patch is None and (loader or module_hashes):
        patch = b""
    files = []
    menu_timings = []
    if layout or _layout_in_use(game_root):
        menu_started = perf_counter()
        layout_current, layout_manifest = _installed(game_root, LAYOUT, "restore it before applying tweaks")
        layout_original = _original(game_root, layout_current, layout_manifest, LAYOUT)
        try:
            layout_after = _compose_menu(layout_original, layout, LAYOUT, cache_root,
                                         current=layout_current, manifest=layout_manifest)
        except ValueError as error:
            raise TweakError(str(error), folders=getattr(error, 'folders', ())) from error
        files.append({"managed": LAYOUT, "before": layout_current, "after": layout_after,
                      "inputs": _menu_identity(layout_original, layout, LAYOUT),
                      "mods": _changes(layout) if layout_after != layout_original else [], "project": None,
                      "previous": _current_manifest(layout_current, layout_manifest, LAYOUT)})
        menu_timings.append({'file': LAYOUT.relative, 'seconds': perf_counter() - menu_started})
    for managed in ESD:
        targeted = [spec for spec in scripts
                    if any(change["archive"] == ESD_ARCHIVE[managed] for change in spec["changes"])]
        if targeted or _esd_in_use(game_root, managed):
            menu_started = perf_counter()
            esd_current, esd_manifest = _installed(game_root, managed, "restore it before applying tweaks")
            esd_original = _original(game_root, esd_current, esd_manifest, managed)
            try:
                esd_after = _compose_menu(esd_original, targeted, managed, cache_root,
                                          current=esd_current, manifest=esd_manifest)
            except ValueError as error:
                raise TweakError(str(error), folders=getattr(error, 'folders', ())) from error
            files.append({"managed": managed, "before": esd_current, "after": esd_after,
                          "inputs": _menu_identity(esd_original, targeted, managed),
                          "mods": _changes(targeted) if esd_after != esd_original else [], "project": None,
                          "previous": _current_manifest(esd_current, esd_manifest, managed)})
            menu_timings.append({'file': managed.relative, 'seconds': perf_counter() - menu_started})
    if patch is None and not loader and any(
            item.get("managed") in (LAYOUT, *ESD) and not item["managed"].vanilla(item["after"])
            for item in files):
        # No native patches, but a menu file stays managed: keep an empty
        # patch and its record, so later changes still ask for a rebuild.
        patch = b""
    return {"files": files, "executableSha256": _sha(current), 'scripts': script_timings, 'menus': menu_timings,
            "runtime": {"patch": patch, "mods": _changes(native) + [row['name'] for row in tweak_rows(root) if row['enabled'] and row.get('prebuilt')],
                        "project": chosen if patch else None, "expected": expected_runtime,
                        "built": built, 'library': str(Path(root or mods_root()).absolute()),
                        'modules': module_hashes, 'moduleWrites': module_writes}}


def _undo(game_root: Path, done: list[dict], *, before_write=None) -> None:
    """Put files already written back, newest first. Never undo a file changed since."""
    errors = []
    for item in reversed(done):
        try:
            if 'runtime' in item:
                _rollback_runtime(game_root,item['runtime'])
                continue
            if item.get('module'):
                from . import runtime_mods
                path = checked(Path(item['path']))
                current = _bounded_file(path,runtime_mods.MAX_SIZE,cache=True)
                if current == item['before']:
                    continue
                if current != item['after']:
                    raise TweakError('The prebuilt mod changed during rollback')
                if item['before'] is None or type(item['before']) is dict:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, item['before'])
                continue
            previous = item['previous']
            managed = item['managed']
            if Path(managed.relative).suffix.casefold() == '.exe':
                continue  # Obsolete entries are outside this rollback writer's domain.
            current = _read(managed.live(game_root), managed)
            if current == item['before']:
                continue
            if current != item['after']:
                raise TweakError(f'The {managed.label} changed during rollback')
            _write(game_root, item['after'], item['before'], previous.get('mods', []),
                   managed, project=previous.get('project'), inputs=previous.get('inputs'), before_write=before_write)
        except Exception as error:
            errors.append(str(error))
    if errors:
        raise TweakError('; '.join(errors))


def commit(game_root: Path, plan: dict) -> None:
    """Write every file in the plan; if one fails, the ones written go back."""
    # The patch was made for the executable prepare() read; one replaced since
    # would only be caught by the loader as the game starts.
    if _sha(_read(EXECUTABLE.live(checked(Path(game_root))))) != plan["executableSha256"]:
        raise TweakError("The executable changed while the tweaks were being prepared")
    done = []
    try:
        for item in plan["files"]:
            done.append(item)
            _write(game_root, item["before"], item["after"], item["mods"], item["managed"],
                   project=item["project"], inputs=item.get('inputs'))
        runtime = plan["runtime"]
        for item in runtime.get('moduleWrites', []):
            from . import runtime_mods
            path = checked(Path(item['path']))
            current = _bounded_file(path,runtime_mods.MAX_SIZE,cache=True)
            if current != item['before']:
                raise TweakError('A prebuilt mod changed while the build was being prepared')
            done.append({**item, 'module': True})
            if item['after'] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, item['after'])
        # The unit restores its exact bytes if any individual write fails.
        # Keep the successful receipt for a later data-deployment rollback.
        runtime['receipt'] = _write_runtime(game_root, runtime['patch'], runtime['mods'], runtime['project'], runtime.get('built'),
                                            library=runtime.get('library'), modules=runtime.get('modules'),
                                            expected=runtime.get('expected'))
        done.append({'runtime':runtime['receipt']})
    except Exception as failure:
        try:
            _undo(game_root, done)
        except Exception as rollback_error:
            raise TweakError(f'Deployment failed: {failure}; rollback failed: {rollback_error}') from failure
        raise


def rollback(game_root: Path, plan: dict) -> None:
    runtime = plan["runtime"]
    if 'receipt' not in runtime:
        return  # Preparation did not commit installed files.
    _undo(game_root, [*plan['files'], *[{**item,'module':True} for item in runtime.get('moduleWrites',[])],
                     {'runtime':runtime['receipt']}])


def apply(game_root: Path, root: Path | None = None, *, project=_KEEP_PROJECT) -> dict:
    """Combine every enabled tweak and the project's rules, for the loader."""
    # A running game stops everything before any write, the lock file included.
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        commit(game_root, prepare(game_root, root, project=project))
    return status(game_root, root)


def restore(game_root: Path, root: Path | None = None) -> dict:
    """The game as it ships: no loader, and the original files back."""
    ensure_game_closed()
    game_root = checked(Path(game_root))
    with _exclusive(game_root):
        return _restore_locked(game_root,root)


def _restore_locked(game_root: Path, root: Path | None = None) -> dict:
    """Restore owned menus before removing the loader. Caller holds locked()."""
    claim_menu_files(game_root)
    _clear_moved_aside(game_root)
    managed_files = (([LAYOUT] if _layout_in_use(game_root) else [])
                     + [managed for managed in ESD if _esd_in_use(game_root, managed)])
    targets = [(managed,*_installed(game_root,managed,'it was left alone')) for managed in managed_files]
    originals = [(managed,current,manifest,_original(game_root,current,manifest,managed))
                 for managed,current,manifest in targets]
    done = []
    try:
        for managed, current, manifest, original in originals:
            if not managed.vanilla(current) or manifest:
                done.append({'managed':managed,'before':current,'after':original,
                             'previous':_current_manifest(current,manifest,managed)})
                _write(game_root, current, original, [], managed)
        _write_runtime(game_root,None,[],None)
    except Exception as failure:
        try:
            _undo(game_root,done)
        except Exception as rollback_error:
            raise TweakError(f'Restore failed: {failure}; rollback failed: {rollback_error}') from failure
        raise
    return status(game_root, root)


def _file_status(game_root: Path, managed: Managed) -> dict:
    current = _read(managed.live(game_root), managed)
    if managed == EXECUTABLE:
        vanilla = is_vanilla(current)
        return {'backupOk': vanilla, 'state': 'vanilla' if vanilla else 'unknown', 'applied': [],
                'problem': '' if vanilla else EXECUTABLE_CHANGED, 'project': None, 'pendingRecovery': False}
    manifest = _manifest(game_root, managed)
    backup = checked(managed.backup(game_root))
    result = {"backupOk": backup.is_file() and _original_matches(_read(backup, managed),manifest,managed),
              "state": "unknown", "applied": [], "problem": "", "project": None,
              "pendingRecovery": bool(manifest.get("pending"))}
    if not _owned(current, manifest, managed):
        result["problem"] = f"The installed {managed.label} was changed outside Lexeditor"
        return result
    active = _current_manifest(current, manifest, managed)
    result["state"] = "vanilla" if managed.vanilla(current) else "tweaked"
    result["applied"] = list(active["mods"])
    result["project"] = active.get("project")
    if result["state"] == "tweaked" and not result["backupOk"]:
        result["problem"] = f"The preserved original {managed.label} is missing or changed"
    return result


def status(game_root: Path, root: Path | None = None) -> dict:
    """What is installed now, without building or changing anything."""
    result = {"applied": [], "state": "unknown", "backupOk": False, "problem": "",
              "pendingRecovery": False, "project": None, "loaderMessage": "",
              "canRestore": False,
              'built': {},
              "windows": os.name == "nt", "modsRoot": str(Path(root or mods_root())),
              "needsRebuild": False, "staleMods": []}
    try:
        result["tweaks"] = tweak_rows(root)
        game_root = Path(game_root)
        executable = _file_status(game_root, EXECUTABLE)
        files = [executable]
        if _layout_in_use(game_root):
            files.append(_file_status(game_root, LAYOUT))
        for managed in ESD:
            if _esd_in_use(game_root, managed):
                files.append(_file_status(game_root, managed))
        runtime = _runtime_status(game_root)
        result['canRestore'] = runtime['installed'] or any(item['applied'] for item in files[1:])
        result["backupOk"] = executable["backupOk"] or executable["state"] == "vanilla"
        states = {item["state"] for item in files}
        tweaked = "tweaked" in states or bool(runtime["applied"])
        result["state"] = "unknown" if "unknown" in states else "tweaked" if tweaked else "vanilla"
        names = runtime["applied"] + [name for item in files for name in item["applied"]]
        result["applied"] = list(dict.fromkeys(names))
        result["project"] = runtime["project"] or executable["project"]
        result['built'] = runtime['built']
        result["pendingRecovery"] = any(item["pendingRecovery"] for item in files)
        result["loaderMessage"] = runtime["loaderMessage"]

        result["problem"] = runtime["problem"] or next((item["problem"] for item in files if item["problem"]), "")
        rebuild = needs_rebuild(game_root, root)
        names = {row["id"]: row.get("name") or row["id"] for row in result["tweaks"]}
        result["needsRebuild"] = rebuild["needed"]
        result["staleMods"] = [names.get(mod_id, mod_id) for mod_id in rebuild["stale"]]
    except (ValueError, OSError) as error:
        result.setdefault("tweaks", [])
        result["problem"] = str(error)
    return result
