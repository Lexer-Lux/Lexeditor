"""Fast clipping regression gate; no installed game is required."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    raise SystemExit(subprocess.call(
        [sys.executable, '-m', 'pytest', '-q', 'tests/test_text_clipping.py'], cwd=ROOT))
