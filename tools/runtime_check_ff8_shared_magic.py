"""Run an isolated FF8 startup with Shared Magic and repaired Fast Start.

This check never changes the selected mod. It temporarily points FFNx at a
private runtime, then restores the exact config and all managed runtime links.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from games.ff8 import fast_start, ffnx_manager, paths


def _new_text(path: Path, offset: int, *, rewritten_after_ns: int | None = None) -> str:
    if not path.is_file():
        return ""
    if rewritten_after_ns is not None:
        if path.stat().st_mtime_ns <= rewritten_after_ns:
            return ""
        offset = 0
    with path.open("rb") as stream:
        stream.seek(min(offset, path.stat().st_size))
        return stream.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()

    game = paths.GAME_ROOT.resolve()
    config = game / "FFNx.toml"
    executable = game / "FF8_EN.exe"
    main_log = game / "FFNx.log"
    shared_log = game / "FFNx.shared-magic.log"
    active_direct = paths.RUNTIME_DIRECT_ROOT.resolve()
    original_config = config.read_bytes()
    launch_barrier_ns = time.time_ns()
    shared_offset = shared_log.stat().st_size if shared_log.is_file() else 0
    process: subprocess.Popen[bytes] | None = None

    try:
        with tempfile.TemporaryDirectory(prefix="lexeditor-shared-magic-") as raw:
            runtime = Path(raw).resolve()
            for name in ffnx_manager.RUNTIME_LINK_NAMES:
                (runtime / name).mkdir(parents=True, exist_ok=True)
            (runtime / "hext" / "ff8" / "en_nv").mkdir(parents=True)
            (runtime / "direct" / "lexeditor").mkdir(parents=True)
            (runtime / "direct" / "lexeditor" / "gameplay.toml").write_text(
                "schemaVersion = 1\nsharedMagicInventory = true\nmagicStockLimit = 100\n",
                encoding="utf-8",
                newline="\n",
            )
            (runtime / "hext" / "ff8" / "en_nv" / "000000__runtime-check.txt").write_text(
                "# Isolated Shared Magic startup check.\n" + fast_start.build_hext(True),
                encoding="utf-8",
                newline="\n",
            )
            ffnx_manager._set_project_paths(config, runtime / "direct")
            process = subprocess.Popen([str(executable)], cwd=str(game))
            deadline = time.monotonic() + args.timeout
            outcome = "timeout"
            while time.monotonic() < deadline:
                main_text = _new_text(
                    main_log, 0, rewritten_after_ns=launch_barrier_ns,
                )
                if "Exception " in main_text or "Unhandled" in main_text:
                    outcome = "crash"
                    break
                if "MODE_MAIN_MENU" in main_text:
                    outcome = "main-menu"
                    break
                if process.poll() is not None:
                    outcome = f"exited-{process.returncode}"
                    break
                time.sleep(0.25)
            shared_text = _new_text(shared_log, shared_offset)
            print(f"outcome={outcome}")
            for line in main_text.splitlines():
                if any(key in line for key in ("Applied Hext", "MODE_MAIN_MENU", "Exception", "Unhandled")):
                    print(f"main: {line}")
            for line in shared_text.splitlines():
                if any(key in line for key in ("init requested", "heartbeat", "failed", "error")):
                    print(f"shared: {line}")
            if outcome != "main-menu":
                return 1
            if "init requested=1 installedFunctions=28 installedCalls=4" not in shared_text:
                print("shared: complete hook installation was not reported")
                return 1
            return 0
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        config.write_bytes(original_config)
        # Recreate every link after the temporary directory is gone. A Windows
        # junction can otherwise survive while pointing at a deleted target.
        ffnx_manager._set_project_paths(config, active_direct)


if __name__ == "__main__":
    raise SystemExit(main())
