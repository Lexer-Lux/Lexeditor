"""Run the Python and JavaScript regression tests, including the host lifecycle."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q', '--tb=short'], cwd=ROOT)
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js is required for JavaScript regression tests.')
    scripts = sorted((ROOT / 'tests').glob('test_*.js')) + sorted((ROOT / 'tests').glob('*.test.cjs'))
    javascript = subprocess.run([node, '--test', *map(str, scripts)], cwd=ROOT)
    return 1 if result.returncode or javascript.returncode else 0


if __name__ == '__main__':
    sys.exit(main())
