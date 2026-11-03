"""Activity is bounded, per-operation, readable while work is locked, and optional."""
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
import threading
import urllib.request
import json

import pytest

from core import operation_progress as progress
from core.plugin_http import PluginRequestHandler


def test_threaded_operations_keep_their_own_labels_and_results():
    barrier = threading.Barrier(2)
    def work(token):
        with progress.operation(token):
            progress.report(token)
            barrier.wait(timeout=5)
            assert progress.snapshot(token) == {'running': True, 'label': token}
        return token
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(work, ['first', 'second'])) == ['first', 'second']
    assert progress.snapshot('first') == {'running': False, 'label': 'first'}
    progress.report('outside an operation')
    assert progress.snapshot('second')['label'] == 'second'


def test_failure_propagates_and_finished_status_does_not_capture_later_activity():
    with pytest.raises(OSError, match='disk full'):
        with progress.operation('failed'):
            progress.report('Installing game files')
            raise OSError('disk full')
    assert progress.snapshot('failed') == {'running': False, 'label': 'Installing game files'}
    progress.report('Unrelated work')
    assert progress.snapshot('failed')['label'] == 'Installing game files'


@pytest.mark.parametrize('token', [None, {}, [], '../other', 'x'*65])
def test_missing_or_invalid_tracking_does_not_stop_work(token):
    with progress.operation(token):
        progress.report('Working')
    assert progress.snapshot(token) == {}


def test_activity_records_and_labels_are_bounded():
    for index in range(progress.LIMIT + 2):
        with progress.operation(f'bounded-{index}'):
            progress.report('x' * 10000)
    assert progress.snapshot('bounded-0') == {}
    assert len(progress.snapshot(f'bounded-{progress.LIMIT + 1}')['label']) == 180
    copy = progress.snapshot(f'bounded-{progress.LIMIT + 1}')
    copy['label'] = 'changed copy'
    assert progress.snapshot(f'bounded-{progress.LIMIT + 1}')['label'] != 'changed copy'


def test_http_status_is_readable_while_the_operation_holds_its_data_lock():
    ready, release = threading.Event(), threading.Event()
    data_lock = threading.Lock()
    class Handler(PluginRequestHandler):
        def do_GET(self):
            if self.send_operation_progress():
                return
            with progress.operation('http-operation'), data_lock:
                progress.report('Building Estus Rework')
                ready.set()
                release.wait(timeout=5)
                self.send_json({'saved': True})
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    def get(path):
        with urllib.request.urlopen(base + path, timeout=3) as response:
            assert 'no-store' in response.headers['Cache-Control']
            return json.load(response)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(get, '/work')
            try:
                assert ready.wait(timeout=3)
                assert get('/api/operation-progress?id=http-operation') == {
                    'running': True, 'label': 'Building Estus Rework'}
                assert not result.done()
            finally:
                release.set()
            assert result.result(timeout=3) == {'saved': True}
        assert not get('/api/operation-progress?id=http-operation')['running']
    finally:
        release.set()
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize('fails', [False, True])
def test_host_switch_reports_while_its_library_lock_is_held(tmp_path, fails):
    from core.desktop_host import HostApi
    from core import mods_service
    folder = tmp_path / 'mod'
    folder.mkdir()
    (folder / 'mod.json').write_text(json.dumps({'name': 'Test mod', 'enabled': False}))
    ready, release = threading.Event(), threading.Event()
    host = HostApi.__new__(HostApi)
    host._mod_library_lock = threading.RLock()
    host._game_mods = lambda _: tmp_path
    host._mod_state = lambda _: None
    host._mod_rows = lambda _: [mods_service.mod_row(folder)]
    host._mod_adapter = lambda _: object()
    host.mod_library_status = lambda _: {'canManage': True}
    def activate(*_args):
        progress.report('Combining enabled mods')
        ready.set()
        assert release.wait(timeout=5)
        if fails:
            raise ValueError('Cannot build this mod')
        return {}
    host._activate_mods = activate
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(host.set_mod_enabled, 'test', str(folder), True, 'host-switch')
        try:
            assert ready.wait(timeout=3)
            assert host.operation_progress('host-switch') == {
                'running': True, 'label': 'Combining enabled mods'}
            assert not result.done()
        finally:
            release.set()
        if fails:
            with pytest.raises(ValueError, match='Cannot build this mod'):
                result.result(timeout=3)
        else:
            assert result.result(timeout=3)['enabled']
    assert mods_service.mod_row(folder)['enabled'] is not fails
    assert not host.operation_progress('host-switch')['running']

