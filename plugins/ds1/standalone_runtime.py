"""Headless data-record composition for the standalone loader.

Ships with the loader's private runtime. It uses the editor's format adapters
and transactions, never executes a mod's Python builder, and has no editor UI.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from contextlib import contextmanager

from core.mod_builds import ModBuildError
from core import mod_library, mod_requires, mods_service
from core.plugin_files import atomic_write
from . import deployment, exe_patches, menu_dim, menu_layout, menu_scripts, mod_loader, tweak_mods

REPORT = 'lexeditor-ds1-load.json'
MAX_REPORT = 1024 * 1024


def discover(roots, game=None):
    """The same declared identities and switches, across explicit locations."""
    rows, seen = [], set()
    for root in roots:
        root = tweak_mods.checked(Path(root)).resolve()
        if root in seen or not root.is_dir():
            continue
        seen.add(root)
        for folder in sorted(root.iterdir()):
            if folder.name.startswith('.') or not folder.is_dir():
                continue
            try:
                tweak_mods.checked(folder)
                if game is not None and root in (game,game/'mods') and not (folder/'runtime.lxd').is_file():
                    continue
                if not (folder/'mod.json').is_file():
                    continue
                info = mod_library.metadata(folder)
                if info.get('enabled') is not True:
                    continue
                row = {'path': folder, 'id': str(info.get('id') or folder.name),
                       'name': info.get('name') or folder.name, 'order': info.get('order',1000)}
                if type(row['order']) is not int:
                    continue
                rows.append(row)
            except (ValueError, OSError):
                continue
            if len(rows) > 128:
                raise ValueError('The standalone loader supports at most 128 enabled mods')
    duplicates = {row['id'].casefold() for row in rows if sum(
        other['id'].casefold() == row['id'].casefold() for other in rows) > 1}
    return sorted([row for row in rows if row['id'].casefold() not in duplicates],
                  key=lambda row:(row['order'],row['name'].casefold()))


def _stamp(path):
    try:
        stat = Path(path).stat()
        return [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
    except OSError:
        return None


def _requires_data(folder):
    from .runtime_mods import FILENAME, HEADER, MAGIC, VERSION
    path = tweak_mods.checked(Path(folder)/FILENAME)
    if not path.is_file():
        return False
    with path.open('rb') as stream:
        header = stream.read(HEADER.size)
    if len(header) != HEADER.size:
        return False  # Native loading diagnoses an invalid module separately.
    magic,version,*values = HEADER.unpack(header)
    return magic == MAGIC and version == VERSION and values[-1] == 1


def _modules(rows):
    from . import runtime_mods
    modules = []
    total = 0
    for row in rows:
        try:
            path = tweak_mods.checked(row['path']/runtime_mods.FILENAME)
            if not path.exists():
                continue
            if path.stat().st_size > runtime_mods.MAX_SIZE:
                raise ValueError('The native module exceeds its size limit')
            data = runtime_mods.read(row['path'])
            total += len(data)
            if total > runtime_mods.MAX_TOTAL_SIZE:
                raise ValueError('Enabled native modules exceed their combined size limit')
            modules.append({'folder':str(row['path']),'data':data})
        except (OSError,ValueError) as error:
            raise ModBuildError([row['path']],f"{row['name']}: {error}") from error
    return modules


def _identity(rows, game, targets):
    from . import native_rules
    paths, contributors = [], []
    for row in rows:
        folder = row['path']
        inputs = [path for _, path in mod_loader.content_files(folder,row['name'])]
        for kind in tweak_mods.BUILT_FOLDERS[1:]:
            inputs.extend(tweak_mods.built_files(folder,kind))
        source = tweak_mods.checked(folder/native_rules.SETTINGS_FILE)
        if source.exists():
            inputs.append(source)
        requires_data = _requires_data(folder)
        if inputs or requires_data:
            contributors.append([str(folder),row['id'],row['name'],mod_requires.declared(folder),requires_data])
            paths.extend(inputs)
    paths.extend(game/mod_library.relative_path(target) for target in targets)
    for target in targets:
        relative = mod_library.relative_path(target)
        managed = tweak_mods.managed_menu(relative)
        if managed is not None:
            paths.extend((managed.backup(game), managed.manifest(game), deployment._marker_path(game,relative)))
    record, warning = tweak_mods.runtime_record(game)
    project = record.get('project') if record else None
    stamped = []
    for path in paths:
        if path.name == native_rules.SETTINGS_FILE:
            value = native_rules.digest(native_rules._read_optional(path,native_rules.SETTINGS_LIMIT))
        elif path == game/tweak_mods.RUNTIME_PATCH and path.is_file():
            with path.open('rb') as stream:
                data = stream.read(tweak_mods.MAX_RUNTIME+1)
            if len(data) > tweak_mods.MAX_RUNTIME:
                raise ValueError('The installed shared patch exceeds its size limit')
            value = hashlib.sha256(data).hexdigest()
        else:
            value = _stamp(path)
        stamped.append([str(path),value])
    from . import runtime_mods
    allocations = []
    shared = bool(project) or any(tweak_mods.built_files(row['path'],kind)
                                  for row in rows for kind in (menu_dim.FOLDER,'native-support'))
    for entry in _modules(rows):
        module = runtime_mods.inspect(entry['data'])
        allocations.extend([rva,size] for kind,rva,size,_ in module['records']
                           if kind == exe_patches.BLOCK and module['fixed'])
        if shared:
            allocations.append([entry['folder'],module['claims'],
                                [[rva,size] for kind,rva,size,_ in module['records'] if kind == exe_patches.HOOK]])
    payload = [mod_loader._composition_revision().hex(), contributors, project, warning, stamped, allocations]
    return hashlib.sha256(json.dumps(payload,separators=(',',':')).encode()).hexdigest()


def _specs(rows, kind, validate):
    try:
        return tweak_mods._built([{**row,'path':str(row['path'])} for row in rows],kind,validate)
    except tweak_mods.TweakError as error:
        raise ModBuildError(error.folders,str(error)) from error


def prepare(game, rows, roots=()):
    from . import native_support
    modules = _modules(rows)
    data = []
    for row in rows:
        try:
            native_support.require_built_rules(row['path'])
            mod = mod_loader.read_mod(row['path'],row['name'])
            if mod is not None and (mod.files or mod.edits):
                data.append(mod)
            elif _requires_data(row['path']) and not any(
                    tweak_mods.built_files(row['path'],kind) for kind in tweak_mods.BUILT_FOLDERS[1:]):
                raise ModBuildError([row['path']],f"{row['name']}: required prebuilt data is missing; rebuild or reinstall this mod")
        except (ValueError,OSError) as error:
            raise ModBuildError([row['path']],f"{row['name']}: {error}") from error
    from . import composition_cache
    cache_root = composition_cache.user_root()
    tweak_mods.claim_menu_files(game)
    layouts = _specs(rows,'layout',menu_layout.validate)
    scripts = _specs(rows,'esd',menu_scripts.validate)
    dims = _specs(rows,menu_dim.FOLDER,menu_dim.validate)
    files = []
    for managed, specs in [(tweak_mods.LAYOUT,layouts)] + [
            (managed,[spec for spec in scripts if any(change['archive'] == tweak_mods.ESD_ARCHIVE[managed]
                                                      for change in spec['changes'])]) for managed in tweak_mods.ESD]:
        in_use = tweak_mods._layout_in_use(game) if managed == tweak_mods.LAYOUT else tweak_mods._esd_in_use(game,managed)
        if not specs and not in_use:
            continue
        current, manifest = tweak_mods._installed(game,managed,'restore it before applying mods')
        original = tweak_mods._original(game,current,manifest,managed)
        try:
            after = tweak_mods._compose_menu(original,specs,managed,cache_root,current=current,manifest=manifest)
        except ValueError as error:
            folders = getattr(error,'folders',())
            if not folders:
                raise
            raise ModBuildError(folders,str(error)) from error
        files.append({'managed':managed,'before':current,'after':after,'mods':tweak_mods._changes(specs),
                      'inputs':tweak_mods._menu_identity(original,specs,managed),
                      'previous':tweak_mods._current_manifest(current,manifest,managed),'project':None})
    composition = mod_loader.compose_installed(game,data,cache_root=cache_root,menu_files=files)
    mod_loader.align_menu_textures(game,composition,tweak_mods.prepared_menu_layout(game,files))
    # Shared menu support is linked at load time; no author script or compiler
    # runs here. Ordinary mod machine code stays in each runtime.lxd.
    dim_patch = menu_dim.patch_spec(dims)
    support = [exe_patches.validate(dim_patch,menu_dim.OWNER)] if dim_patch else []
    if support:
        support[0]['folders'] = list(dict.fromkeys(spec['folder'] for spec in dims))
    support.extend(_specs(rows,native_support.FOLDER,native_support.validate))
    record, _warning = tweak_mods.runtime_record(game)
    libraries = [*roots,*(row['path'].parent for row in rows)]
    if record and native_support.owns_project(record.get('project'),libraries):
        record = {**record,'project':None}
    if record and record.get('project'):
        support.append(exe_patches.validate(record['project']['spec'],'Project native rules'))
    if support:
        executable = deployment.vanilla_source(game,Path(exe_patches.EXECUTABLE)).read_bytes()
        from . import runtime_mods
        try:
            patch = runtime_mods.shared_patch(executable,support,modules) or b''
        except exe_patches.PatchError as error:
            if not error.folders:
                raise
            raise ModBuildError(error.folders,str(error)) from error
    else:
        patch = b''
    return data, composition, files, patch, record


@contextmanager
def write_window(startup_pid=None):
    """Only the loader's pre-entry callback may write while its game exists."""
    if startup_pid is None:
        yield tweak_mods.ensure_game_closed
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenEventW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenEventW(0x100000, False, f'Local\\Lexeditor.DS1.Startup.{int(startup_pid)}')
    if not handle:
        raise ValueError('The loader startup window is unavailable')
    def check():
        if kernel.WaitForSingleObject(handle, 0) != 0:
            raise ValueError('The loader startup window has ended')
    try:
        check()
        yield check
    finally:
        kernel.CloseHandle(handle)


def run(game: Path, roots: list[Path], *, startup_pid=None) -> dict:
    with write_window(startup_pid) as before_write:
        before_write()
        return _run(game, roots, before_write)


def _run(game: Path, roots: list[Path], before_write) -> dict:
    game = tweak_mods.checked(Path(game)).resolve()
    report_path = tweak_mods.checked(game/REPORT)
    record_path = tweak_mods.checked(game/tweak_mods.RUNTIME_RECORD)
    disabled = []
    with tweak_mods.locked(game):
        before_write()
        rows = discover(roots,game)
        try:
            raw = tweak_mods._bounded_file(report_path,MAX_REPORT,cache=True)
            prior = json.loads(raw) if isinstance(raw,bytes) else None
            valid = type(prior) is dict and prior.get('version') == 1
            for key in ('targets','loaded','warnings','conflicts'):
                values = prior.get(key) if valid else None
                valid = valid and type(values) is list and all(type(value) is str for value in values)
            failures = prior.get('disabled') if valid else None
            valid = valid and type(failures) is list and all(type(row) is dict and all(
                type(row.get(key)) is str for key in ('id','name','error')) for row in failures)
            if valid and prior.get('signature') == _identity(rows,game,prior['targets']):
                enabled = {row['id'] for row in rows}
                remaining = [row for row in failures if row['id'] not in enabled]
                if remaining != failures:
                    prior['disabled'] = remaining
                    before_write()
                    atomic_write(report_path,(json.dumps(prior,indent=2)+'\n').encode())
                return {**prior,'reused':True}
        except (ValueError,OSError,TypeError,RecursionError):
            pass  # A disposable report never blocks loading or triggers code execution.
        _record, warning = tweak_mods.runtime_record(game)
        while True:
            try:
                available = {row['id'] for row in rows} | {'lexeditor-loader'}
                for row in rows:
                    if any(need not in available for need in mod_requires.declared(row['path'])):
                        raise ModBuildError([row['path']],f"{row['name']}: a required mod is unavailable")
                data, composition, files, patch, record = prepare(game,rows,roots)
                break
            except ModBuildError as error:
                failed = {Path(path).resolve() for path in error.folders}
                if not failed or not failed <= {row['path'].resolve() for row in rows}:
                    raise
                for row in rows:
                    if row['path'].resolve() in failed:
                        before_write()
                        mods_service.set_enabled(row['path'],False)
                        disabled.append({'id':row['id'],'name':row['name'],'error':str(error)})
                rows = [row for row in rows if row['path'].resolve() not in failed]
        done = []
        try:
            for item in files:
                done.append(item)
                tweak_mods._write(game,item['before'],item['after'],item['mods'],item['managed'],
                                 inputs=item.get('inputs'), before_write=before_write)
            before_write()
            if composition.files:
                owner = data[-1].folder if data else rows[-1]['path'] if rows else None
                deployment.apply(game,owner,composed=composition.files)
            else:
                deployment.disable(game)
        except Exception:
            tweak_mods._undo(game,done,before_write=before_write)
            raise
        before_write()
        atomic_write(game/tweak_mods.RUNTIME_PATCH,patch)
        if record is not None:
            record['patchSha256'] = hashlib.sha256(patch).hexdigest()
            before_write()
            atomic_write(record_path,(json.dumps(record,indent=2)+'\n').encode())
        targets = [str(path) for path in composition.files] + [str(item['managed'].relative) for item in files]
        targets += [tweak_mods.RUNTIME_PATCH]
        data_folders = {mod.folder.resolve() for mod in data}
        for row in rows:
            if any(tweak_mods.built_files(row['path'],kind) for kind in tweak_mods.BUILT_FOLDERS[1:]):
                data_folders.add(row['path'].resolve())
        report = {'version':1,'loaded':[row['id'] for row in rows if row['path'].resolve() in data_folders],
                  'disabled':disabled,'targets':targets,
                  'warnings':[warning] if warning else [],
                  'conflicts':[str(conflict.part) for conflict in composition.conflicts][:128]}
        report['signature'] = _identity(rows,game,targets)
        raw = (json.dumps(report,indent=2)+'\n').encode()
        if len(raw) > MAX_REPORT:
            raise ValueError('The loader report exceeds its limit')
        before_write()
        atomic_write(report_path,raw)
        return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--game',required=True,type=Path)
    parser.add_argument('--root',action='append',default=[],type=Path)
    parser.add_argument('--startup-pid',type=int)
    args = parser.parse_args()
    try:
        run(args.game,args.root,startup_pid=args.startup_pid)
    except Exception as error:
        try:
            atomic_write(args.game/REPORT,(json.dumps({'version':1,'error':str(error)[:2000],'loaded':[]})+'\n').encode())
        except OSError:
            pass
        print(str(error),file=sys.stderr)
        sys.exit(1)
