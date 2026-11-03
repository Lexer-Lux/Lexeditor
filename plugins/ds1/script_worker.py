"""Evaluate a mod in a disposable child; only the parent commits its outputs.

This contains crashes and timeouts, not malicious code: enabled scripts remain
trusted code with the user's filesystem access.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile

from core import script_mods
from core.plugin_files import atomic_write, read_bounded
from core.runtime_bootstrap import service_command

BUILD_TIMEOUT = 60
RESULT_LIMIT = 128 * 1024 * 1024
INFRASTRUCTURE_EXIT = 72  # The worker could not publish an operation error.


def _read_payload(path, label):
    """Bound both snapshot and response reads, including growth during a read."""
    try:
        if path.stat().st_size > RESULT_LIMIT:
            raise ValueError(f'Build worker {label} exceeds the 128 MiB limit')
        with path.open('rb') as stream:
            raw = read_bounded(stream, RESULT_LIMIT + 1)
        if len(raw) > RESULT_LIMIT:
            raise ValueError(f'Build worker {label} grew beyond its size limit')
        return raw
    except (OSError, ValueError) as error:
        raise script_mods.ScriptModInfrastructureError(f'Could not read build worker {label}: {error}') from error


def _read_result(path):
    """A broken transport is an operation failure, never evidence against a mod."""
    raw = _read_payload(path, 'response')
    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError('Expected a build worker response object')
        return result
    except (ValueError, RecursionError) as error:
        raise script_mods.ScriptModInfrastructureError(f'Could not read build worker response: {error}') from error


def evaluate(root, settings, context):
    try:
        return _evaluate(root, settings, context)
    except OSError as error:
        raise script_mods.ScriptModInfrastructureError(f'Could not run build worker: {error}') from error


def _evaluate(root, settings, context):
    request = {'root': str(root), 'settings': settings, 'current': context.current,
               'enabled': {name: str(path) for name, path in context._enabled.items()},
               'game': str(context.game_root) if context.game_root else None,
               'cache': str(context._cache_root) if getattr(context, '_cache_root', None) else None,
               'library': str(context._library_root) if context._library_root else None}
    environment = os.environ.copy()
    environment.pop('LEXEDITOR_SERVICE_PIPE', None)
    with tempfile.TemporaryDirectory(prefix='lexeditor-build-') as temporary:
        result_path = Path(temporary) / 'result.json'
        request['result'] = str(result_path)
        params_path = Path(temporary) / 'params.bin'
        request['params'] = str(params_path)
        if context._params is not None:
            if not isinstance(context._params, (bytes, bytearray)) or len(context._params) > RESULT_LIMIT:
                raise script_mods.ScriptModInfrastructureError('Build parameter snapshot is invalid or exceeds the 128 MiB limit')
            params_path.write_bytes(context._params)
        with subprocess.Popen(service_command(__name__), cwd=Path(__file__).resolve().parents[2],
                              env=environment, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                              start_new_session=os.name != 'nt') as child:
            try:
                child.communicate(json.dumps(request).encode('utf-8'), timeout=BUILD_TIMEOUT)
            except subprocess.TimeoutExpired as error:
                if os.name == 'nt':
                    child.kill()
                else:
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                try:
                    building = _read_result(result_path) == {'building': True}
                except script_mods.ScriptModInfrastructureError:
                    building = False
                failure = script_mods.ScriptModError if building else script_mods.ScriptModInfrastructureError
                raise failure(f'Build did not finish within {BUILD_TIMEOUT} seconds') from error
            if child.returncode == INFRASTRUCTURE_EXIT:
                raise script_mods.ScriptModInfrastructureError('Build worker could not publish its response; check temporary-folder access and free disk space')
            result = _read_result(result_path)
            if child.returncode or result == {'building': True}:
                failure = (script_mods.ScriptModError if result == {'building': True}
                           else script_mods.ScriptModInfrastructureError)
                raise failure(f'Build worker exited unexpectedly ({child.returncode})')
        if 'infrastructureError' in result:
            raise script_mods.ScriptModInfrastructureError(result['infrastructureError'])
        if 'error' in result:
            try:
                folders = result.get('folders', [])
                if not isinstance(result['error'], str) or not isinstance(folders, list) or any(
                        not isinstance(folder, str) for folder in folders):
                    raise ValueError('Invalid build worker error response')
                failure = script_mods.ScriptModError(result['error'], folders=folders)
            except (OSError, ValueError, TypeError) as error:
                raise script_mods.ScriptModInfrastructureError(f'Invalid build worker response: {error}') from error
            raise failure
        try:
            if not isinstance(result['outputs'], dict) or not isinstance(result['inputs'], dict):
                raise ValueError('Invalid build worker outputs or inputs')
            if type(result.get('cacheable', False)) is not bool:
                raise ValueError('Invalid build worker cache status')
            if any(not isinstance(name, str) or not isinstance(data, str) for name,data in result['outputs'].items()):
                raise ValueError('Invalid build worker output encoding')
            outputs = {name: base64.b64decode(data, validate=True) for name, data in result['outputs'].items()}
        except (KeyError, ValueError, TypeError) as error:
            raise script_mods.ScriptModInfrastructureError(f'Invalid build worker response: {error}') from error
        context._inputs = result['inputs']
        context._build_cacheable = result.get('cacheable',False)
        if params_path.is_file():
            context._params = _read_payload(params_path, 'parameter snapshot')
        return outputs


def main():
    # Keep descendants in a kill-on-close job, including after a forced timeout.
    with os.fdopen(0, 'rb') as incoming:
        request = json.loads(incoming.read(1024 * 1024 + 1))
    job = None
    try:
        if os.name == 'nt':
            from core.service_lifetime import _own_windows_tree
            job = _own_windows_tree()
    except OSError as error:
        Path(request['result']).write_text(json.dumps({'infrastructureError': str(error)}), encoding='utf-8')
        return
    try:
        from core.build_dependencies import BuildDependencies
        roots = [Path(request['root'])/'script',*[Path(path)/'script' for path in request['enabled'].values()]]
        with BuildDependencies(roots) as dependencies:
            _build(request,dependencies)
    except BaseException as error:
        try:
            atomic_write(Path(request['result']), json.dumps({'infrastructureError': str(error)[:4000]}).encode('utf-8'))
        except Exception:
            raise SystemExit(INFRASTRUCTURE_EXIT)


def _build(request, dependencies):
    from .tweak_mods import BuildContext
    context = BuildContext({name: Path(path) for name, path in request['enabled'].items()},
                           Path(request['game']) if request['game'] else None,
                           Path(request['library']) if request['library'] else None,
                           cache_root=Path(request['cache']) if request.get('cache') else None)
    context.current = request['current']
    context.begin_build(Path(request['root']))
    params_path = Path(request['params'])
    if params_path.is_file():
        context._params = _read_payload(params_path, 'parameter snapshot')
    _seed_compression(Path(request['root']))
    # Startup failures must not be confused with a crash in author code.
    # Atomic publication keeps this acknowledgement if a crash interrupts
    # the final response, using the same temporary transport file.
    atomic_write(Path(request['result']), b'{"building":true}')
    try:
        outputs = script_mods.execute_script(Path(request['root']), request['settings'], context)
        if not isinstance(outputs, dict):
            raise script_mods.ScriptModError('build() must return {path: contents}')
        encoded = {}
        total = 0
        for name, data in outputs.items():
            if not isinstance(name, str) or not isinstance(data, (str, bytes, bytearray)):
                raise script_mods.ScriptModError('Build outputs must map paths to text or bytes')
            data = data.encode('utf-8') if isinstance(data, str) else bytes(data)
            total += len(data)
            if total > RESULT_LIMIT * 3 // 4 - 65536:
                raise script_mods.ScriptModError('Build output exceeds the 128 MiB limit')
            encoded[name] = base64.b64encode(data).decode('ascii')
    except (script_mods.ScriptModInfrastructureError, script_mods.ScriptModRollbackError) as error:
        result = {'infrastructureError': str(error)[:4000]}
    except BaseException as error:
        result = {'error': f'{type(error).__name__}: {str(error)[:4000]}',
                  'folders': [str(folder) for folder in getattr(error, 'folders', ())]}
    else:
        # These are execution-service duties after the mod returned valid
        # outputs. A failed snapshot or response must never incriminate it.
        for path,digest in dependencies.inputs().items():
            context._remember('python',path,digest)
        result = {'outputs': encoded, 'inputs': context._inputs, 'cacheable':dependencies.complete}
        if context._params is not None and not params_path.exists():
            if len(context._params) > RESULT_LIMIT:
                raise script_mods.ScriptModInfrastructureError('Build parameter snapshot exceeds the 128 MiB limit')
            params_path.write_bytes(context._params)
    atomic_write(Path(request['result']), json.dumps(result).encode('utf-8'))


def _seed_compression(root):
    """Reuse this mod's owned outputs even after the disposable cache evicts them."""
    from .tweak_mods import ALLOWED_ROOTS, checked
    try:
        outputs = script_mods._generated_files(root, ALLOWED_ROOTS)
        remaining = RESULT_LIMIT
        for relative, digest in outputs.items():
            if not relative.endswith('.dcx'):
                continue
            path = checked(root/relative)
            if not path.is_file() or path.stat().st_size > remaining:
                continue
            size = path.stat().st_size
            with path.open('rb') as stream:
                data = stream.read(size+1)
            remaining -= len(data)
            if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
                continue
            from .formats import remember_compression
            remember_compression(data)
    except Exception:
        pass  # Ownership validation in the parent still guards actual writes.


if __name__ == '__main__':
    main()
