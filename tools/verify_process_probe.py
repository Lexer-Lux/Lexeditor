"""Verify that launcher process checks use kernel liveness, not stale names."""

from __future__ import annotations

import os
import subprocess
import sys
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import process_probe  # noqa: E402


def main() -> int:
    if os.name != "nt":
        print("Process probe is Windows-only")
        return 0
    executable = Path(sys.executable)
    process = subprocess.Popen(
        [str(executable), "-c", "import time; time.sleep(30)"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            live = process_probe.live_processes((executable.name,))
            if any(int(row["pid"]) == process.pid for row in live):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("A live child was not reported as live")
        process.terminate()
        process.wait(timeout=10)
        assert not any(int(row["pid"]) == process.pid
                       for row in process_probe.live_processes((executable.name,)))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)

    # The repeated FF8 entries on this machine currently have zero threads.
    # They can remain named in Windows, but they must never block a launch,
    # install, or Stop-button state.
    ff8_live = process_probe.live_processes(("FF8_EN.exe", "FF8_Launcher.exe"))
    ff8_stale = process_probe.zombie_processes(("FF8_EN.exe", "FF8_Launcher.exe"))
    assert not ff8_live
    assert all(int(row.get("threads", 0)) == 0 for row in ff8_stale)
    print({"liveChildDetected": True, "terminatedChildExcluded": True,
           "ff8Live": len(ff8_live), "ff8Stale": len(ff8_stale)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
