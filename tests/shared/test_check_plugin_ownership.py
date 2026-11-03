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
