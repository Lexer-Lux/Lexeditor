"""The window restart button restarts all of Lexeditor, not just the plugin."""
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import desktop_host
from plugins.blank.plugin import BlankSession

ROOT = Path(__file__).resolve().parents[2]


def ui():
    return (ROOT / 'ui' / 'framework.js').read_text(encoding='utf-8', errors='replace')


def host():
    return (ROOT / 'core' / 'desktop_host.py').read_text(encoding='utf-8', errors='replace')


def test_restart_button_calls_full_restart():
    source = ui()
    assert 'callWindow("restart_lexeditor")' in source
    assert 'title: "Restart Lexeditor", "aria-label": "Restart Lexeditor"' in source
    assert 'label: "Restart Lexeditor", developer: true' in source
    assert 'Restart this plugin' not in source
    assert 'Restart the plugin' not in source


def test_plugin_restart_kept_for_project_switch():
    assert 'def restart_plugin(self' in host()
    assert '_restart_for_project' in host()


def test_full_restart_relaunches():
    source = host()
    assert 'def restart_lexeditor(self' in source
    assert 'restart_requested = api._restart_requested' in source
    assert 'DETACHED_PROCESS' in source


@pytest.mark.parametrize('restart,frozen,closed_event', [
    (True, False, True), (True, True, True), (True, False, False),
    (False, False, True),
])
def test_replacement_starts_only_after_old_service_exits(
        monkeypatch, tmp_path, restart, frozen, closed_event):
    """Run host shutdown against a real private child, without a native window."""
    class Event(list):
        def __iadd__(self, callback):
            self.append(callback)
            return self

        def fire(self):
            for callback in self:
                callback()

    session = BlankSession(extra_env={
        'LEXEDITOR_BLANK_PROJECTS': str(tmp_path / 'samples.json'),
    })
    session.start()
    process = session.process
    api = desktop_host.HostApi.__new__(desktop_host.HostApi)
    api._lock = threading.RLock()
    api._mouse_navigation = None
    api._session = session
    api._dirty_count = 0
    api._restart_requested = False
    api._close_authorized = False
    api.migrate_user_data = Mock()
    events = SimpleNamespace(**{name: Event() for name in (
        'maximized', 'shown', 'closing', 'closed')})
    window = SimpleNamespace(events=events)
    window.destroy = Mock(side_effect=events.closed.fire if closed_event else None)

    def start(**_kwargs):
        assert process.poll() is None
        if restart:
            assert api.restart_lexeditor() == {'restarting': True}
        elif closed_event:
            events.closed.fire()

    def launch(*args, **kwargs):
        assert session.wait_closed()
        assert process.poll() is not None
        assert api._session is None

    popen = Mock(side_effect=launch)
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(
        settings={}, create_window=Mock(return_value=window), start=start))
    monkeypatch.setattr(desktop_host, 'HostApi', lambda _plugins: api)
    monkeypatch.setattr(desktop_host, 'configure_process_identity', lambda: None)
    monkeypatch.setattr(desktop_host, 'load_window_geometry', lambda: {
        'bounds': [0, 0, 1000, 700]})
    monkeypatch.setattr(desktop_host, 'STORAGE', tmp_path / 'webview')
    monkeypatch.setattr(desktop_host, 'LEGACY_STORAGE', tmp_path / 'absent')
    monkeypatch.setattr(sys, 'argv', ['Lexeditor.py', '--plugin', 'blank'])
    monkeypatch.setattr(sys, 'frozen', frozen, raising=False)
    monkeypatch.setattr(desktop_host.subprocess, 'Popen', popen)
    try:
        assert desktop_host.run_host({}) == 0
        assert process.poll() is not None
        if restart:
            arguments = [sys.executable, '--plugin', 'blank'] if frozen else [
                sys.executable, 'Lexeditor.py', '--plugin', 'blank']
            flags = 0
            if desktop_host.os.name == 'nt':
                flags = (desktop_host.subprocess.DETACHED_PROCESS
                         | desktop_host.subprocess.CREATE_NEW_PROCESS_GROUP)
            popen.assert_called_once_with(arguments, cwd=str(desktop_host.ROOT),
                                          close_fds=True, creationflags=flags)
        else:
            popen.assert_not_called()
    finally:
        session.stop()

def test_exit_without_saving_discards_first():
    source = ui()
    assert 'const canDiscard = typeof options.discard === "function";' in source
    assert 'await options.discard();' in source
    assert 'could not be discarded. Lexeditor stayed open.' in source
    assert 'Discarded, but the action did not complete. Try again or cancel.' in source
