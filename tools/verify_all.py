"""Run the verifier suite in parallel, or just the checks you name.

Each rendered verifier boots its own headless Edge and its own plugin service on
its own free port, so they are independent processes and there is no reason to
run them one at a time. Sequentially the suite takes about 3.5 minutes, which is
long enough that it stops being run.

    python tools/verify_all.py                  every verifier
    python tools/verify_all.py ff8 curve        only verifiers matching a name
    python tools/verify_all.py --jobs 4         fewer workers on a busy machine
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(ROOT / ".venv" / "Scripts" / "python.exe")


def _once(tool: Path) -> tuple[int, str]:
    proc = subprocess.run([PYTHON if Path(PYTHON).is_file() else sys.executable, str(tool)],
                          capture_output=True, text=True, cwd=str(ROOT))
    stream = proc.stdout.strip() or proc.stderr.strip()
    tail = (stream.splitlines() or [""])[-1]
    if proc.returncode:
        tail = (proc.stderr.strip().splitlines() or [tail])[-1]
    return proc.returncode, tail[:220]


def run(tool: Path) -> tuple[Path, int, float, str]:
    """Run one verifier, retrying a single time before calling it a failure.

    Several verifiers settle with a fixed sleep rather than waiting for a real
    ready signal, so under parallel load an eval can run against a page that
    is not up yet. That produced a different one or two failures on every
    run. A retry keeps the suite honest without pretending the flake is not
    there: anything that needed a second attempt is REPORTED as FLAKY, so it
    stays visible and fixable instead of being silently swallowed.
    """
    started = time.time()
    code, tail = _once(tool)
    if code:
        time.sleep(2)
        second, second_tail = _once(tool)
        if not second:
            return tool, 0, time.time() - started, f"FLAKY (passed on retry): {tail}"
        code, tail = second, second_tail
    return tool, code, time.time() - started, tail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="*", help="substrings; a verifier runs if it matches any")
    # Each browser verifier costs ~14 processes and about half a gigabyte, so
    # parallelism here is measured in BROWSERS, not CPUs. Four at a time is
    # ~56 processes: enough to be quick, far below what wedges a desktop.
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--list", action="store_true", help="print the selection and stop")
    arguments = parser.parse_args()

    # This file matches its own glob. Left in, it re-invokes itself, and each
    # copy fans the whole suite out again through the thread pool - the suite
    # squared, then cubed. Roughly 40 of these verifiers each start a headless
    # browser worth ~14 processes, so a single stray run put 654 browser
    # processes and 28GB on the machine and froze it. Excluding self is what
    # actually prevents that; the job-object cleanup is a separate safeguard.
    tools = [tool for tool in sorted((ROOT / "tools").glob("verify_*.py"))
             if tool.resolve() != Path(__file__).resolve()]
    if arguments.patterns:
        tools = [tool for tool in tools
                 if any(pattern.lower() in tool.name.lower() for pattern in arguments.patterns)]
    if not tools:
        print("No verifier matched.")
        return 1
    if arguments.list:
        for tool in tools:
            print(tool.name)
        return 0

    # Longest first, so a 2-minute sweep never starts last and defines the
    # wall time on its own. Durations come from the previous run.
    timings = {}
    cache = ROOT / "_scratch" / "verify-durations.json"
    try:
        timings = json.loads(cache.read_text(encoding="utf-8"))
    except Exception:
        timings = {}
    tools.sort(key=lambda tool: -timings.get(tool.name, 1.0))

    started = time.time()
    measured = {}
    failures = []
    done = 0
    jobs = max(1, min(6, arguments.jobs))
    if jobs != arguments.jobs:
        print(f"Limiting to {jobs} parallel verifiers: each starts a browser.")
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for tool, code, seconds, tail in pool.map(run, tools):
            done += 1
            label = 'FAIL' if code else ('FLAKY' if tail.startswith('FLAKY') else 'PASS')
            print(f"[{done}/{len(tools)}] {label} {tool.name} ({seconds:.1f}s) {tail}",
                  flush=True)
            measured[tool.name] = round(seconds, 1)
            if code:
                failures.append((tool.name, tail))
    print(f"\n{len(tools) - len(failures)}/{len(tools)} passed in {time.time() - started:.1f}s "
          f"on {arguments.jobs} workers")
    for name, tail in failures:
        print(f"FAILED {name}: {tail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
