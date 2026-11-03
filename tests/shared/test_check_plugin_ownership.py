"""Shared CI must retain every browser caller without rerunning aggregates."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import check_plugin
from tests.shared import verify_browser_regressions as browsers


def test_global_browser_partition_preserves_all_real_entrypoints():
    declared = set(browsers.CHECKS)
    assert declared and all((ROOT / check).is_file() for check in declared)
    cross = set(browsers.selected_checks(cross_plugin_only=True))
    shared = declared - cross
    assert shared and cross
    owned = {path.relative_to(ROOT).as_posix()
             for path in check_plugin.owned(None)['scripts']}
    assert shared <= owned, f'Shared browser checks lost from global CI: {shared - owned}'
    assert cross.isdisjoint(owned)
    assert all(not check.startswith('tests/shared/') for check in cross)
    assert any(command[1:] == ['tests/shared/verify_browser_regressions.py', '--cross-plugin']
               for command in check_plugin.commands(None))


def test_global_discovery_does_not_launch_nested_full_suites():
    owned = {path.name for path in check_plugin.owned(None)['scripts']}
    assert {'verify_all.py', 'verify_regressions.py', 'verify_browser_regressions.py'}.isdisjoint(owned)
    # Omitting the nested pytest/node launcher must retain the owned unit gates.
    gates = check_plugin.owned(None)
    assert gates['pytest']
    for path in list((ROOT / 'tests').glob('*/test_*.js')) + list((ROOT / 'tests').glob('*/*.test.cjs')):
        owner = None if path.parent.name == 'shared' else path.parent.name
        assert path in check_plugin.owned(owner)['node'], f'JavaScript regression lost its owner: {path}'
    assert (ROOT / 'tests/shared/restart_browser_check.py') in gates['scripts']


def test_shared_pytest_collects_all_failures_with_stack_diagnostics(monkeypatch):
    from types import SimpleNamespace
    paths = [ROOT / 'tests/shared/test_first.py', ROOT / 'tests/shared/test_second.py']
    calls = []
    monkeypatch.setattr(check_plugin, 'utf8_console', lambda: None)
    monkeypatch.setattr(sys, 'argv', ['check_plugin.py', '--global'])
    monkeypatch.setattr(check_plugin, 'owned', lambda _: {
        'pytest': paths, 'node': [], 'powershell': [], 'scripts': []})
    monkeypatch.setattr(check_plugin, 'commands', lambda _: [])
    def run(command, **_):
        calls.append(command)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(check_plugin.subprocess, 'run', run)
    assert check_plugin.main() == 1
    assert len(calls) == 1
    command = calls[0]
    assert command[1:3] == ['-m', 'pytest']
    assert '-x' not in command and not any(arg.startswith('--maxfail') for arg in command)
    assert 'faulthandler_timeout=120' in command
    assert command[-2:] == [path.relative_to(ROOT).as_posix() for path in paths]
