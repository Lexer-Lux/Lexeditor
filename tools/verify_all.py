"""Run the verifier suite in parallel, or just the checks you name.

Run a small selection first; legacy checks can require private game data or
platform-specific build tools. Each attempt has a deadline and a complete log.

    python tools/verify_all.py                  every verifier
    python tools/verify_all.py ff8 curve        only verifiers matching a name
    python tools/verify_all.py --jobs 4         fewer workers on a busy machine
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PYTHON = str(ROOT / ".venv" / "Scripts" / "python.exe")


def _once(tool: Path, timeout: float = 180, output: Path | None = None,
          attempt: int = 1, max_log_bytes: int = 8 * 1024 * 1024) -> tuple[int, str]:
    output = output or ROOT / "_scratch" / "verify-results"
    output.mkdir(parents=True, exist_ok=True)
    log = output / f"{tool.stem}.attempt-{attempt}.log"
    environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    # Files avoid pipe deadlocks and retain output if a child must be stopped.
    with log.open("w", encoding="utf-8") as stream:
        proc = subprocess.Popen(
            [PYTHON if Path(PYTHON).is_file() else sys.executable, str(tool)],
            stdout=stream, stderr=subprocess.STDOUT, cwd=str(ROOT), env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            start_new_session=os.name != "nt")
        deadline = time.monotonic() + timeout
        reason = None
        while True:
            if log.stat().st_size > max_log_bytes:
                reason = f"OUTPUT LIMIT: log exceeded {max_log_bytes} bytes"
                break
            code = proc.poll()
            if code is not None:
                break
            if time.monotonic() >= deadline:
                reason = f"TIMEOUT after {timeout:g}s"
                break
            time.sleep(min(.1, max(0, deadline-time.monotonic())))
        if reason:
            if os.name == "nt":
                from tools.browser_guard import kill_tree
                kill_tree(proc)
            else:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            proc.wait(timeout=15)
            if log.stat().st_size > max_log_bytes:
                stream.truncate(max_log_bytes)
                stream.seek(0, os.SEEK_END)
            stream.write(f"\n{reason}\n")
            code = 124 if reason.startswith("TIMEOUT") else 125
    tail = (log.read_text(encoding="utf-8", errors="replace").strip().splitlines() or [""])[-1]
    return code, tail[:220]


def run(tool: Path, timeout: float = 180, output: Path | None = None,
        retries: int = 1) -> tuple[Path, int, float, str]:
    """Run one verifier, retrying a single time before calling it a failure.

    Several verifiers settle with a fixed sleep rather than waiting for a real
    ready signal, so under parallel load an eval can run against a page that
    is not up yet. That produced a different one or two failures on every
    run. A retry keeps the suite honest without pretending the flake is not
    there: anything that needed a second attempt is REPORTED as FLAKY, so it
    stays visible and fixable instead of being silently swallowed.
    """
    started = time.time()
    code, tail = _once(tool, timeout, output)
    if code and code not in (124, 125) and retries:
        time.sleep(2)
        second, second_tail = _once(tool, timeout, output, 2)
        if not second:
            return tool, 0, time.time() - started, f"FLAKY (passed on retry): {tail}"
        code, tail = second, second_tail
    return tool, code, time.time() - started, tail


def main() -> int:
    # Redirected Windows consoles can use cp1252. Node's status glyphs must
    # never crash the parent after all tests have completed successfully.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="*", help="substrings; a verifier runs if it matches any")
    # Each browser verifier costs ~14 processes and about half a gigabyte, so
    # parallelism here is measured in BROWSERS, not CPUs. Four at a time is
    # ~56 processes: enough to be quick, far below what wedges a desktop.
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--list", action="store_true", help="print the selection and stop")
    parser.add_argument("--exclude", action="append", default=[], help="exclude a name substring; repeat as needed")
    parser.add_argument("--timeout", type=float, default=180, help="seconds per attempt")
    parser.add_argument("--retries", type=int, choices=(0, 1), default=1)
    parser.add_argument("--output", type=Path, default=ROOT / "_scratch" / "verify-results")
    arguments = parser.parse_args()
    if not 0 < arguments.timeout < float("inf"):
        parser.error("--timeout must be a finite positive number")

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
    tools = [tool for tool in tools if not any(
        pattern.lower() in tool.name.lower() for pattern in arguments.exclude)]
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
    results = []
    done = 0
    jobs = max(1, min(6, arguments.jobs))
    if jobs != arguments.jobs:
        print(f"Limiting to {jobs} parallel verifiers: each starts a browser.")
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        pending = [pool.submit(partial(run, timeout=arguments.timeout,
                    output=arguments.output, retries=arguments.retries), tool) for tool in tools]
        for future in as_completed(pending):
            try:
                tool, code, seconds, tail = future.result()
            except Exception as error:
                tool = tools[pending.index(future)]
                code, seconds, tail = 1, 0, f"Runner error: {type(error).__name__}: {error}"
            done += 1
            label = 'FAIL' if code else ('FLAKY' if tail.startswith('FLAKY') else 'PASS')
            print(f"[{done}/{len(tools)}] {label} {tool.name} ({seconds:.1f}s) {tail}",
                  flush=True)
            measured[tool.name] = round(seconds, 1)
            results.append(dict(name=tool.name, status=label, exitCode=code,
                                seconds=round(seconds, 2), detail=tail))
            if code:
                failures.append((tool.name, tail))
    print(f"\n{len(tools) - len(failures)}/{len(tools)} passed in {time.time() - started:.1f}s "
          f"on {jobs} workers")
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(timings | measured, indent=2), encoding="utf-8")
    print(f"Full logs and report: {arguments.output}")
    for name, tail in failures:
        print(f"FAILED {name}: {tail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
