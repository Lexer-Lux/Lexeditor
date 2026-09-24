"""Render production UI with disposable data; never open an installed game."""
# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    '.github/scripts/ui_visual_acceptance.py',
    'tests/global_controls_check.py',
    'tests/control_layout_browser_check.py',
    'tests/restart_browser_check.py',
    'tests/home_restart_browser_check.py',
    'tests/global_browser_check.py',
    'tests/data_map_browser_check.py',
    'tests/rdr_browser_check.py',
    'tests/rdr2_browser_check.py',
    'tests/verify_rdr2_loot_sounds_browser.py',
    'tests/warband_browser_check.py',
    'tests/ff8_graph_design_a_browser_check.py',
    'tests/wse2_helper_browser_check.py',
)


def main():
    failed = []
    for check in CHECKS:
        print(f'Running {check}', flush=True)
        args = []
        if check in ('tests/rdr_browser_check.py', 'tests/rdr2_browser_check.py'):
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
