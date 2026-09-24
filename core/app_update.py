"""User-started release updates for the installed source checkout.

The host prepares a release while it is open. A detached copy of this module
updates the checkout only after the host and its plugin services have stopped.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from contextlib import contextmanager

REPOSITORY = "https://github.com/Lexer-Lux/Lexeditor.git"
LATEST = "https://api.github.com/repos/Lexer-Lux/Lexeditor/releases/latest"


def command(args, *, cwd, timeout=180):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[-2000:])
    return result.stdout.strip()


def git(root, *args):
    return command(["git", *args], cwd=root)


def latest_release():
    request = urllib.request.Request(LATEST, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "Lexeditor-updater"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    tag = data.get("tag_name", "")
    if (data.get("draft") or data.get("prerelease")
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", tag)):
        raise RuntimeError("GitHub did not return a supported stable release.")
    return {"tag": tag, "published": data.get("published_at", "")}


def is_ancestor(root, first, second):
    result = subprocess.run(["git", "merge-base", "--is-ancestor", first, second],
                            cwd=root, capture_output=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode not in (0, 1):
        raise RuntimeError("Could not compare the installed version with the release.")
    return result.returncode == 0


def check(root, *, release=None, repository=REPOSITORY):
    root = Path(root).resolve()
    if not shutil.which("git") or not (root / ".git").exists():
        raise RuntimeError("This update method needs the Git source installation of Lexeditor.")
    release = release or latest_release()
    tag = release["tag"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", tag):
        raise ValueError("Invalid release tag")
    # Fetch the exact published tag from the official repository, not a mutable
    # local tag or an install's possibly changed origin configuration.
    ref = "refs/lexeditor-updates/" + uuid.uuid4().hex
    try:
        git(root, "fetch", "--no-tags", repository, "refs/tags/" + tag + ":" + ref)
        target = git(root, "rev-parse", ref + "^{commit}")
    finally:
        git(root, "update-ref", "-d", ref)
    current = git(root, "rev-parse", "HEAD")
    if current == target:
        status, message = "current", "The latest release is already installed."
    elif is_ancestor(root, target, current):
        status, message = "ahead", "This install is newer than the latest published release."
    elif not is_ancestor(root, current, target):
        status, message = "diverged", "This install has separate local commits. An update would replace that work."
    elif git(root, "status", "--porcelain"):
        status, message = "modified", "Save and commit local source changes before updating."
    else:
        status, message = "available", "A new release is ready to install."
    return {**release, "status": status, "message": message,
            "available": status == "available", "current": current, "target": target}


def prepare(root, storage):
    with update_lock(Path(storage) / "updates"):
        pass
    result = check(root)  # Refresh on Install; never use a stale UI result.
    if not result["available"]:
        raise RuntimeError(result["message"])
    job = Path(storage) / "updates" / uuid.uuid4().hex
    job.mkdir(parents=True)
    worker = job / "worker.py"
    shutil.copy2(__file__, worker)
    plan = {**result, "root": str(Path(root).resolve()), "python": sys.executable,
            "parent": os.getpid(), "worker": str(worker)}
    path = job / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def apply_update(root, current, target, python):
    """Fast-forward clean source files; retain an old-commit recovery reference."""
    root = Path(root).resolve()
    if git(root, "rev-parse", "HEAD") != current or git(root, "status", "--porcelain"):
        raise RuntimeError("The install changed after the update was prepared. No files were replaced.")
    if not is_ancestor(root, current, target):
        raise RuntimeError("The release is no longer a forward update.")
    backup = "refs/lexeditor-backups/" + uuid.uuid4().hex
    git(root, "update-ref", backup, current)
    old_requirements = git(root, "show", current + ":requirements.txt")
    new_requirements = git(root, "show", target + ":requirements.txt")
    try:
        git(root, "merge", "--ff-only", target)
        if old_requirements != new_requirements:
            command([python, "-m", "pip", "install", "--disable-pip-version-check",
                     "-r", str(root / "requirements.txt")], cwd=root, timeout=600)
        command([python, str(root / "app.py"), "--list"], cwd=root, timeout=60)
    except Exception:
        # --keep refuses to discard source changes made by another process.
        git(root, "reset", "--keep", current)
        if old_requirements != new_requirements:
            command([python, "-m", "pip", "install", "--disable-pip-version-check",
                     "-r", str(root / "requirements.txt")], cwd=root, timeout=600)
        raise
    return backup


def wait_for_parent(pid):
    if not pid:
        return
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle and ctypes.get_last_error() != 87:
            raise RuntimeError("Could not verify that Lexeditor has closed.")
        if handle:
            try:
                if kernel.WaitForSingleObject(handle, 120000) != 0:
                    raise RuntimeError("Lexeditor did not close. No files were replaced.")
            finally:
                kernel.CloseHandle(handle)
    else:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(.2)
        raise RuntimeError("Lexeditor did not close. No files were replaced.")


def launch(plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    return subprocess.Popen([plan["python"], plan["worker"], str(plan_path)],
                            cwd=str(Path(plan_path).parent), close_fds=True,
                            creationflags=flags, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@contextmanager
def update_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "install.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Another Lexeditor update is running.") from error
        yield


def worker(plan_path):
    path = Path(plan_path)
    plan = json.loads(path.read_text(encoding="utf-8"))
    result_path = path.parent.parent / "last-result.json"
    closed = False
    try:
        wait_for_parent(plan["parent"])
        if path.with_suffix(".cancelled").exists():
            return
        closed = True
        with update_lock(path.parent.parent):
            backup = apply_update(plan["root"], plan["current"], plan["target"], plan["python"])
        result = {"success": True, "message": "Installed " + plan["tag"], "backup": backup}
    except Exception as error:
        result = {"success": False, "message": "Update failed: " + str(error)}
    result_path.write_text(json.dumps(result), encoding="utf-8")
    if closed:
        subprocess.Popen([plan["python"], str(Path(plan["root"]) / "app.py")],
                         cwd=plan["root"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


if __name__ == "__main__":
    worker(sys.argv[1])
