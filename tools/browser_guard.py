"""Make a spawned browser die with the process that spawned it.

Two things went wrong before this existed, and both leaked browsers onto the
user's machine until it froze:

1. Popen.terminate() kills only the process it was given. A browser spawns a
   whole tree - renderer, GPU, network, crashpad - and terminating the parent
   ORPHANS every child. That leaked on every run, even a clean one.
2. A `finally:` block does not run when the interpreter is hard-killed, which
   is exactly what `timeout N python verify_x.py` does. Every timed-out run
   leaked its entire browser tree.

Politely-coded cleanup cannot fix either case, so this does not rely on it. A
Windows Job Object with KILL_ON_JOB_CLOSE makes the KERNEL responsible: when
this process exits for any reason at all - normal return, exception, SIGTERM,
or an unblockable kill - Windows closes the last handle to the job and
terminates every process inside it.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import tempfile

_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOBOBJECT_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BASIC_LIMIT(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BASIC_LIMIT),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


# Held for the lifetime of the interpreter. Letting this be garbage collected
# would close the job and kill the browser mid-run.
_JOB = None


def _job_handle():
    global _JOB
    if _JOB is not None:
        return _JOB
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _EXTENDED_LIMIT()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
            job, _JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info), ctypes.sizeof(info)):
        kernel32.CloseHandle(job)
        return None
    _JOB = job
    return _JOB


def adopt(process: subprocess.Popen) -> bool:
    """Put a spawned process and everything it spawns under this process.

    Returns True when the kernel accepted the job assignment. False means the
    caller must not rely on automatic cleanup - `kill_tree` is then the only
    protection, and it still cannot survive a hard kill.
    """
    if os.name != "nt" or process is None or process.poll() is not None:
        return False
    job = _job_handle()
    if not job:
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(
        _PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, process.pid)
    if not handle:
        return False
    try:
        return bool(kernel32.AssignProcessToJobObject(job, handle))
    finally:
        kernel32.CloseHandle(handle)


def kill_tree(process: subprocess.Popen) -> None:
    """Kill a process AND its children, for the ordinary exit path.

    terminate() alone leaves the browser's child processes running, so this
    uses taskkill /T. It is best-effort: the job object above is what actually
    guarantees cleanup.
    """
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, check=False)
        except Exception:
            pass
    try:
        process.terminate()
        process.wait(timeout=10)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass

_INSTALLED = False


def install_autoadopt() -> bool:
    """Put EVERY process this interpreter spawns under the kill-on-close job.

    The verifier scripts each spawn their own browser with their own cleanup,
    so fixing them one by one would leave the next new script to leak again.
    Wrapping Popen once means a spawned browser cannot outlive its script even
    if the script is killed outright and its cleanup never runs.
    """
    global _INSTALLED
    if _INSTALLED or os.name != "nt":
        return _INSTALLED
    if not _job_handle():
        return False
    original = subprocess.Popen

    class GuardedPopen(original):
        def __init__(self, *args, **kwargs):
            # A headless browser still plays page audio through the real
            # speakers, so verifier runs made the machine chirp with plugin
            # theme sounds. Muting here covers every script rather than
            # relying on each one to remember the flag.
            headless = False
            try:
                command = args[0] if args else kwargs.get("args")
                if isinstance(command, list) and any(
                        isinstance(part, str) and part.startswith("--headless")
                        for part in command):
                    headless = True
                    if "--mute-audio" not in command:
                        command.insert(1, "--mute-audio")
            except Exception:
                pass
            if headless:
                # Counts ONLY browsers this guard started, so the user's own
                # browsing neither trips the cap nor gets swept.
                live = ours_alive()
                if len(live) >= BROWSER_LIMIT:
                    raise BrowserLimitReached(
                        f"refusing to launch: {len(live)} guarded browsers are "
                        f"already running (limit {BROWSER_LIMIT}). "
                        "Something is not cleaning up; run browser_guard.sweep_ours().")
            super().__init__(*args, **kwargs)
            if headless:
                _register(self.pid)
            try:
                adopt(self)
            except Exception:
                pass  # never let bookkeeping break a real command

    subprocess.Popen = GuardedPopen
    _INSTALLED = True
    return True


# ---- Hard cap -------------------------------------------------------------
# The job object is meant to guarantee cleanup, and in isolation it does. It
# did NOT hold across a full suite run: browsers climbed past 79 and kept
# climbing, and the user's machine had to be hard rebooted. Until that is
# understood, no amount of care in the calling code is enough - so launching is
# refused outright once too many browsers are alive. A refused launch fails one
# script loudly; an unrefused one takes the whole machine down.

BROWSER_LIMIT = 24
_TH32CS_SNAPPROCESS = 0x00000002
_MAX_PATH = 260


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * _MAX_PATH),
    ]


# Counts msedge ONLY. An earlier version also counted chrome.exe, which is
# the user's actual browser, so it reported 45 "leaked browsers" that were
# their own Chrome and led to a confidently wrong all-clear. This tool must
# never count a process Lexeditor did not start.
def browser_count(names=("msedge.exe",)) -> int:
    """Count live browser processes without spawning anything.

    Deliberately uses a toolhelp snapshot rather than shelling out to
    PowerShell: this runs on every launch, and a counter that itself spawns a
    process would be absurd.
    """
    if os.name != "nt":
        return 0
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return 0
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        wanted = {name.lower() for name in names}
        total = 0
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return 0
        while True:
            if entry.szExeFile.lower() in wanted:
                total += 1
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
        return total
    finally:
        kernel32.CloseHandle(snapshot)


class BrowserLimitReached(RuntimeError):
    """Raised instead of launching a browser onto an already loaded machine."""


# ---- Ours-only registry ---------------------------------------------------
# browser_count() counts EVERY msedge, which includes the user's own browsing -
# 45 of them were open while writing this. A cap on that number would misfire,
# and a sweeper built on it would close the user's real tabs. So every browser
# this guard launches records its PID in one shared file, and both the cap and
# the sweeper work only from that list. Nothing here can ever touch a browser
# the user opened themselves.


REGISTRY = Path(tempfile.gettempdir()) / "lexeditor-browser-pids.txt"
_SYNCHRONIZE = 0x00100000
_STILL_ACTIVE = 259


def _alive(pid: int) -> bool:
    if os.name != "nt":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(_SYNCHRONIZE | 0x0400, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return code.value == _STILL_ACTIVE
        return False
    finally:
        kernel32.CloseHandle(handle)


def _register(pid: int) -> None:
    try:
        with REGISTRY.open("a", encoding="utf-8") as handle:
            handle.write(str(pid) + chr(10))
    except OSError:
        pass


def ours_alive() -> list[int]:
    """PIDs of browsers THIS guard launched that are still running."""
    try:
        raw = REGISTRY.read_text(encoding="utf-8").split()
    except OSError:
        return []
    live = []
    for value in raw:
        try:
            pid = int(value)
        except ValueError:
            continue
        if pid not in live and _alive(pid):
            live.append(pid)
    try:  # keep the file from growing without bound
        REGISTRY.write_text("".join(str(pid) + chr(10) for pid in live), encoding="utf-8")
    except OSError:
        pass
    return live


def sweep_ours() -> int:
    """Kill every browser this guard launched. Never touches the user's own."""
    killed = 0
    for pid in ours_alive():
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20, check=False)
            killed += 1
        except Exception:
            pass
    return killed
