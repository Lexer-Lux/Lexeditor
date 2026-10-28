"""Evaluate a mod in a disposable child; only the parent commits its outputs.

This contains crashes and timeouts, not malicious code: enabled scripts remain
trusted code with the user's filesystem access.
"""
import base64
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile

from core import script_mods
from core.runtime_bootstrap import service_command

BUILD_TIMEOUT = 60
RESULT_LIMIT = 128 * 1024 * 1024


def evaluate(root, settings, context):
    try:
        return _evaluate(root, settings, context)
    except OSError as error:
        raise script_mods.ScriptModInfrastructureError(f'Could not run build worker: {error}') from error


def _evaluate(root, settings, context):
    request = {'root': str(root), 'settings': settings, 'current': context.current,
               'enabled': {name: str(path) for name, path in context._enabled.items()},
               'game': str(context.game_root) if context.game_root else None,
               'library': str(context._library_root) if context._library_root else None}
    environment = os.environ.copy()
    environment.pop('LEXEDITOR_SERVICE_PIPE', None)
    with tempfile.TemporaryDirectory(prefix='lexeditor-build-') as temporary:
        result_path = Path(temporary) / 'result.json'
        request['result'] = str(result_path)
        params_path = Path(temporary) / 'params.bin'
        request['params'] = str(params_path)
        if context._params is not None:
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
                raise script_mods.ScriptModError(f'Build did not finish within {BUILD_TIMEOUT} seconds') from error
            if child.returncode or not result_path.is_file():
                raise script_mods.ScriptModError(f'Build worker exited unexpectedly ({child.returncode})')
        if result_path.stat().st_size > RESULT_LIMIT:
            raise script_mods.ScriptModError('Build output exceeds the 128 MiB limit')
        result = json.loads(result_path.read_text('utf-8'))
        if 'infrastructureError' in result:
            raise script_mods.ScriptModInfrastructureError(result['infrastructureError'])
        if 'error' in result:
            raise script_mods.ScriptModError(result['error'], folders=result.get('folders', ()))
        outputs = {name: base64.b64decode(data, validate=True) for name, data in result['outputs'].items()}
        context._inputs = result['inputs']
        if params_path.is_file():
            if params_path.stat().st_size > RESULT_LIMIT:
                raise script_mods.ScriptModError('Build parameter snapshot exceeds the 128 MiB limit')
            context._params = params_path.read_bytes()
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
    from .tweak_mods import BuildContext
    context = BuildContext({name: Path(path) for name, path in request['enabled'].items()},
                           Path(request['game']) if request['game'] else None,
                           Path(request['library']) if request['library'] else None)
    context.current = request['current']
    params_path = Path(request['params'])
    if params_path.is_file():
        context._params = params_path.read_bytes()
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
        result = {'outputs': encoded, 'inputs': context._inputs}
        if context._params is not None and not params_path.exists():
            if len(context._params) > RESULT_LIMIT:
                raise script_mods.ScriptModError('Build parameter snapshot exceeds the 128 MiB limit')
            params_path.write_bytes(context._params)
    except BaseException as error:
        result = {'error': f'{type(error).__name__}: {str(error)[:4000]}',
                  'folders': [str(folder) for folder in getattr(error, 'folders', ())]}
    Path(request['result']).write_text(json.dumps(result), encoding='utf-8')


if __name__ == '__main__':
    main()
