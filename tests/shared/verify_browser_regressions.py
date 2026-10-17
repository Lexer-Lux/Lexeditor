"""Render production UI with disposable data; never open an installed game."""
# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CHECKS = (
    'tests/shared/ui_visual_acceptance_check.py',
    'tests/shared/global_controls_check.py',
    'tests/shared/control_layout_browser_check.py',
    'tests/shared/restart_browser_check.py',
    'tests/shared/home_restart_browser_check.py',
    'tests/shared/global_browser_check.py',
    'tests/shared/data_map_browser_check.py',
    'tests/rdr/rdr_browser_check.py',
    'tests/rdr2/rdr2_browser_check.py',
    'tests/rdr2/verify_rdr2_loot_sounds_browser.py',
    'tests/warband/warband_browser_check.py',
    'tests/ff8/ff8_graph_design_a_browser_check.py',
    'tests/warband/wse2_helper_browser_check.py',
)


def selected_checks(cross_plugin_only=False):
    return tuple(check for check in CHECKS
                 if not cross_plugin_only or not check.startswith('tests/shared/'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cross-plugin', action='store_true',
                        help='Run only plugin callers; shared fixtures have their own global checks.')
    args = parser.parse_args()
    checks = selected_checks(args.cross_plugin)
    failed = []
    for check in checks:
        print(f'Running {check}', flush=True)
        args = []
        if check in ('tests/rdr/rdr_browser_check.py', 'tests/rdr2/rdr2_browser_check.py'):
            args = ['--screenshots', str(DEV_CACHE / Path(check).stem)]
        result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / check), *args], cwd=ROOT)
        if result.returncode:
            failed.append(check)
    print(f'Browser fixtures: {len(checks)-len(failed)}/{len(checks)} passed', flush=True)
    for check in failed:
        print(f'FAILED {check}')
    return bool(failed)


if __name__ == '__main__':
    sys.exit(main())
