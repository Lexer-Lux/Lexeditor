"""Verify the pinned Memoria baseline preparation contract."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff9 import memoria_baseline


def main() -> None:
    fixtures = {relative: f"fixture:{relative}".encode() for relative in memoria_baseline.FILES}
    old_files = memoria_baseline.FILES
    memoria_baseline.FILES = {relative: hashlib.sha256(data).hexdigest() for relative, data in fixtures.items()}
    try:
        with tempfile.TemporaryDirectory(prefix="lexeditor-ff9-baseline-", ignore_cleanup_errors=True) as directory:
            calls = []
            result = memoria_baseline.ensure(Path(directory), lambda relative: calls.append(relative) or fixtures[relative])
            assert result["ready"] and result["prepared"] == len(fixtures)
            assert calls == list(fixtures)
            cached = memoria_baseline.ensure(Path(directory), lambda _relative: (_ for _ in ()).throw(AssertionError("network used")))
            assert cached["ready"]
            target = Path(directory) / "StreamingAssets" / "Data" / next(iter(fixtures))
            target.write_bytes(b"corrupt")
            repaired = memoria_baseline.ensure(Path(directory), lambda relative: fixtures[relative])
            assert repaired["ready"] and target.read_bytes() == fixtures[next(iter(fixtures))]
        print("FF9 verified Memoria baseline: PASS")
    finally:
        memoria_baseline.FILES = old_files


if __name__ == "__main__":
    main()
