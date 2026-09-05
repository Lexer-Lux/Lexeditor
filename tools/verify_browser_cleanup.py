"""Prove a spawned browser cannot outlive the script that spawned it.

This exists because it already went wrong once, badly: leaked headless Edge
processes accumulated until the user's machine froze and had to be hard
restarted, twice. Popen.terminate() killed only the launcher and orphaned every
child renderer, and a `finally` block never runs when a script is killed by a
timeout, which is how the verifiers were routinely run.

The fix must be enforced by the kernel rather than by careful code, so this
checks the guarantee the way it actually failed: kill the parent outright,
with no chance to clean up, and require the browser to be gone anyway.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import browser_guard  # noqa: E402

HARNESS = Path(r"C:\RDR2Mod\tools\reverse-engineering\render_crime_editors_55_62.py")


def edge_count() -> int:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process msedge -ErrorAction SilentlyContinue).Count"],
        capture_output=True, text=True, timeout=60)
    return int((result.stdout or "0").strip() or 0)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    source = browser_guard.__file__ and Path(browser_guard.__file__).read_text(encoding="utf-8")
    require("KILL_ON_JOB_CLOSE" in source and "AssignProcessToJobObject" in source,
            "cleanup must be enforced by a kill-on-close job object, not by tidy code")
    require("--mute-audio" in source,
            "headless browsers must be muted; they play page audio on the real speakers")

    # Every verifier reaches a browser through this harness, so the guard has to
    # be installed there or 40 scripts each leak on their own.
    harness = HARNESS.read_text(encoding="utf-8")
    require("browser_guard" in harness and "install_autoadopt" in harness,
            "the shared verifier harness must install the browser guard for every script")

    shot = (ROOT / "tools" / "shot.py").read_text(encoding="utf-8")
    require("browser_guard.adopt" in shot and "kill_tree" in shot
            and "browser.terminate()" not in shot,
            "shot.py must adopt and kill the whole tree, never bare terminate()")

    # THE ACTUAL CAUSE of the machine freezes was not a leak: verify_all.py
    # matched its own glob, so it re-invoked itself and each copy fanned the
    # whole suite out again through a thread pool. About 40 verifiers each
    # start a browser worth ~14 processes, so one stray run reached 654
    # processes and 28GB and wedged the desktop. Both guards are checked here.
    runner = (ROOT / "tools" / "verify_all.py").read_text(encoding="utf-8")
    require("tool.resolve() != Path(__file__).resolve()" in runner,
            "verify_all.py must exclude ITSELF from its glob or it runs the suite recursively")
    require("min(6, arguments.jobs)" in runner,
            "parallel verifiers must be capped; each one costs a whole browser")

    import subprocess as _sp
    listed = _sp.run([sys.executable, str(ROOT / "tools" / "verify_all.py"), "--list"],
                     capture_output=True, text=True, timeout=180).stdout
    require("verify_all.py" not in listed,
            "verify_all.py still selects itself")

    baseline = edge_count()
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "tools" / "shot.py"), "ff8", "cleanup-probe",
         "--size", "1200x800"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        started = False
        for _ in range(60):
            if edge_count() > baseline:
                started = True
                break
            if process.poll() is not None:
                break
            time.sleep(0.5)
        require(started, "the probe never started a browser, so nothing was proven")
        # No terminate, no signal handler, no finally: the harshest case.
        process.kill()
        process.wait(timeout=30)
        for _ in range(30):
            if edge_count() <= baseline:
                break
            time.sleep(1)
        leaked = edge_count() - baseline
        require(leaked <= 0,
                f"{leaked} browser processes survived a hard kill of their parent")
    finally:
        if process.poll() is None:
            browser_guard.kill_tree(process)
    print("Browser cleanup: survives a hard kill, muted, installed for every verifier.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
