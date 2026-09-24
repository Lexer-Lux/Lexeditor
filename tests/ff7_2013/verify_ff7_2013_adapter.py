"""Source-only FF7 2013 adapter acceptance with a generated KERNEL fixture."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff7_2013 import plugin as target
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ff7"))
from verify_ff7_datasets import write_kernel


EXPECTED = {
    "legacy FF7 product identity, shared editor and capabilities confirmed",
    "Data Map structured/openable coverage contract confirmed",
    "416 English KERNEL.BIN records decoded",
    "bounded armor edit stayed inside the project, survived binary readback and reopened",
    "installed English KERNEL.BIN source remained byte-identical",
}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7-2013-source-") as name:
        game = Path(name) / "game"
        kernel = game / "data" / "lang-en" / "kernel" / "KERNEL.BIN"
        kernel.parent.mkdir(parents=True, exist_ok=True)
        write_kernel(kernel)
        (game / "ff7_en.exe").write_bytes(b"synthetic-ff7-2013-exe")

        original_root = target.DEFAULT_ROOT
        try:
            target.DEFAULT_ROOT = game
            messages = target.smoke()
        finally:
            target.DEFAULT_ROOT = original_root

    missing = EXPECTED.difference(messages)
    if missing:
        raise AssertionError(f"FF7 2013 adapter smoke missed evidence: {sorted(missing)}")
    print("\n".join(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
