"""The window restart button restarts all of Lexeditor, not just the plugin."""
from pathlib import Path

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
