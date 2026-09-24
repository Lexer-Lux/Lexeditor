"""Render production UI with disposable data; never open an installed game."""
# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CHECKS = (
    '.github/scripts/ui_visual_acceptance.py',
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


def main():
    failed = []
    for check in CHECKS:
        print(f'Running {check}', flush=True)
        args = []
        if check in ('tests/rdr/rdr_browser_check.py', 'tests/rdr2/rdr2_browser_check.py'):
            args = ['--screenshots', str(DEV_CACHE / Path(check).stem)]
        result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / check), *args], cwd=ROOT)
        if result.returncode:
            failed.append(check)
    print(f'Browser fixtures: {len(CHECKS)-len(failed)}/{len(CHECKS)} passed', flush=True)
    for check in failed:
        print(f'FAILED {check}')
    return bool(failed)


if __name__ == '__main__':
    sys.exit(main())
