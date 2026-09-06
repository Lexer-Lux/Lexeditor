"""Offline, pinned WSE2 package installation. Upstream checks are read-only.

The Lexeditor package keeps the publisher's engine/Steam bytes unchanged and
omits the self-updating launcher, dedicated servers and debug symbols. Only an
explicit Install/Repair action writes game files; opening Home or Play never
installs, downloads, changes pins, or invokes the publisher's launcher.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import threading
import urllib.request
import uuid
import zipfile

from game_version import game_version

PINNED_RELEASE = "v1.1.5.1"
PACKAGE_VERSION = "1.1.5.1-lex1"
PACKAGE_SHA256 = "43dc883e0f78cd1fad49dea696080154be0b498000980f63d91e96712707cd31"
PACKAGE_ROOT = Path(__file__).resolve().parent / "runtime"
REPOSITORY = "https://github.com/Ruslan-700/WSE2-Releases"
LATEST_RELEASE_API = "https://api.github.com/repos/Ruslan-700/WSE2-Releases/releases/latest"
RELEASE_NOTES = REPOSITORY + "/releases/tag/" + PINNED_RELEASE
PROCESS_NAMES = ("mb_warband.exe", "mb_warband_wse2.exe", "mb_warband_wse2_x64.exe", "wse2_launcher.exe", "mb_warband_wse2_dedicated.exe", "mb_warband_wse2_dedicated_x64.exe", "mb_warband_wse2_dedicated_campaign.exe", "mb_warband_wse2_dedicated_campaign_x64.exe")
_LOCK = threading.RLock()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else _digest(stream.read())


def _safe_name(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return bool(parts) and not name.startswith("/") and not any(
        p in {".", "..", ""} or p.endswith((".", " ")) or ":" in p or "\\" in p for p in name.split("/"))


def _manifest(package_root: Path = PACKAGE_ROOT) -> dict:
    result = json.loads((Path(package_root) / "manifest.json").read_text(encoding="utf-8"))
    if (result.get("schema") != 1 or result.get("version") != PINNED_RELEASE
            or result.get("packageVersion") != PACKAGE_VERSION or result.get("sha256") != PACKAGE_SHA256
            or result.get("archive") != f"wse2-{PACKAGE_VERSION}.zip" or result.get("steamAppId") != "48700"):
        raise RuntimeError("The bundled WSE2 manifest does not match Lexeditor's pin.")
    files = result.get("files")
    if not isinstance(files, dict) or not files:
        raise RuntimeError("The bundled WSE2 file manifest is empty.")
    for name, info in files.items():
        if not _safe_name(name) or not re.fullmatch(r"[0-9a-f]{64}", info.get("sha256", "")):
            raise RuntimeError("Unsafe WSE2 package manifest.")
        if not isinstance(info.get("size"), int) or not 0 <= info["size"] <= 64 * 1024 * 1024:
            raise RuntimeError("Invalid WSE2 package member size.")
        if name.lower().endswith((".bat", ".cmd", ".pdb")) or "launcher" in name.lower() or "dedicated" in name.lower():
            raise RuntimeError("An updater, launcher or server must not ship in the managed WSE2 package.")
    required = {"mb_warband_wse2.exe", "mb_warband_wse2_x64.exe", "steam_api_wse2.dll", "steam_api64.dll", "steam_appid.txt"}
    if not required <= files.keys():
        raise RuntimeError("The WSE2 package is missing engine or Steam components.")
    return result


def _target(root: Path, relative: str) -> Path:
    """Never follow symlinks/junctions into vanilla modules or other installs."""
    if not _safe_name(relative):
        raise RuntimeError(f"Unsafe WSE2 path: {relative}")
    current = root
    for part in relative.split("/"):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise RuntimeError(f"WSE2 installation refuses linked paths: {current}")
    if not current.resolve().is_relative_to(root.resolve()):
        raise RuntimeError(f"WSE2 path escapes the game: {relative}")
    return current


def _state_root(root: Path) -> Path:
    return _target(root, ".lexeditor/wse2")


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _json_write(path: Path, value: dict) -> None:
    _atomic(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _json_read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


@contextmanager
def _installation_lock(root: Path):
    with _LOCK:
        folder = _state_root(root)
        folder.mkdir(parents=True, exist_ok=True)
        path = _target(root, ".lexeditor/wse2/install.lock")
        with path.open("a+b") as handle:
            if handle.tell() == 0:
                handle.write(b"0"); handle.flush()
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError("Another WSE2 install or launch is in progress.") from error
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)


def _assert_closed(root: Path) -> None:
    """Fail closed on process-query errors; never overwrite a running engine."""
    if os.name != "nt":
        return  # Enables offline fixture installation on Linux.
    import ctypes
    from ctypes import wintypes
    # Use the shared structure but keep the query fail-closed for file writes.
    from process_probe import PROCESSENTRY32W
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32NextW.argtypes = kernel.Process32FirstW.argtypes
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot in (None, 0, wintypes.HANDLE(-1).value):
        raise RuntimeError("Cannot verify that Warband is closed; WSE2 files were not changed.")
    try:
        entry = PROCESSENTRY32W(); entry.dwSize = ctypes.sizeof(entry)
        available = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while available:
            if entry.szExeFile.casefold() in PROCESS_NAMES:
                handle = kernel.OpenProcess(0x100000, False, entry.th32ProcessID)
                if not handle:
                    if ctypes.get_last_error() != 87:
                        raise RuntimeError("Cannot verify an existing Warband process is stopped.")
                else:
                    try:
                        if kernel.WaitForSingleObject(handle, 0) != 0:
                            raise RuntimeError("Close Warband and the WSE2 launcher before installing or repairing WSE2.")
                    finally:
                        kernel.CloseHandle(handle)
            available = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise RuntimeError("Warband process enumeration failed; no WSE2 files changed.")
    finally:
        kernel.CloseHandle(snapshot)


def package_files(package_root: Path = PACKAGE_ROOT) -> tuple[dict, dict[str, bytes]]:
    manifest = _manifest(package_root)
    archive = Path(package_root) / manifest["archive"]
    if _hash(archive) != PACKAGE_SHA256:
        raise RuntimeError("The bundled WSE2 archive failed its pinned SHA-256 check. No game files were changed.")
    data = {}
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) != len(manifest["files"]) or {i.filename for i in entries} != set(manifest["files"]):
            raise RuntimeError("The bundled WSE2 archive does not match its file manifest.")
        for info in entries:
            expected = manifest["files"][info.filename]
            if info.file_size != expected["size"] or stat.S_ISLNK(info.external_attr >> 16):
                raise RuntimeError("Invalid WSE2 archive entry.")
            raw = bundle.read(info)
            if _digest(raw) != expected["sha256"]:
                raise RuntimeError(f"WSE2 member failed verification: {info.filename}")
            data[info.filename] = raw
    if data["steam_appid.txt"].strip() != b"48700":
        raise RuntimeError("WSE2 is not configured for the Warband Steam application.")
    return manifest, data


def _root_identity(root: Path) -> str:
    return os.path.normcase(str(root.resolve()))


def status(game_root: Path | None, *, package_root: Path = PACKAGE_ROOT) -> dict:
    """Read-only actual-install evidence; receipts cannot bless changed binaries."""
    base = {"runtime": "WSE2", "pinned": PINNED_RELEASE, "packageVersion": PACKAGE_VERSION,
            "source": REPOSITORY, "releaseNotes": RELEASE_NOTES, "installed": False,
            "present": False, "managed": False, "version": "", "autoUpdate": False,
            "steamVerified": False}
    if game_root is None:
        return {**base, "message": "Warband is not installed or has not been located."}
    root = Path(game_root).resolve()
    try:
        manifest = _manifest(package_root)
        folder = _state_root(root)
        receipt = _json_read(folder / "receipt.json")
        present = (root / "mb_warband_wse2.exe").is_file() or (root / "mb_warband_wse2_x64.exe").is_file()
        mismatches = []
        for name, expected in manifest["files"].items():
            target = _target(root, name)
            if not target.is_file() or target.stat().st_size != expected["size"] or _hash(target) != expected["sha256"]:
                mismatches.append(name)
        executable = "mb_warband_wse2.exe" if (root / "mb_warband_wse2.exe").is_file() else "mb_warband_wse2_x64.exe"
        version = PINNED_RELEASE if present and executable not in mismatches else game_version(str(root), (executable,))
        pending = (folder / "pending.json").exists()
        managed = receipt.get("root") == _root_identity(root) and receipt.get("packageVersion") == PACKAGE_VERSION
        ready = present and not mismatches and managed and not pending
        message = ("Pinned WSE2 package verified; automatic updating disabled. Steam session acceptance is separate."
                   if ready else "WSE2 install was interrupted. Use Install/Repair to recover."
                   if pending else "WSE2 differs from the pinned package. Use Install/Repair WSE2; Play will not run an unverified copy."
                   if present else "Install the bundled WSE2 package to enable this plugin's extender features.")
        return {**base, "installed": ready, "present": present, "managed": managed, "version": version,
                "integrity": "verified" if ready else "recovery-required" if pending else "unmanaged" if not managed else "mismatch",
                "mismatches": mismatches, "pending": pending, "gameRoot": str(root),
                "lastInstalled": receipt.get("installedAt", "") if managed else "", "message": message}
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        return {**base, "message": f"WSE2 could not be verified: {error}", "error": str(error)}


def require_managed(game_root: Path) -> None:
    result = status(game_root)
    if not result["installed"]:
        raise RuntimeError(result["message"])


@contextmanager
def verified_launch(game_root: Path):
    """Serialize managed engine creation with installs without holding during play."""
    with _installation_lock(Path(game_root).resolve()):
        require_managed(game_root)
        yield


def _rollback(root: Path, transaction: dict, manifest: dict) -> None:
    """Only undo our known writes; retain journal if external edits prevent recovery."""
    txid = transaction.get("id", "")
    if not re.fullmatch(r"[0-9a-f]{32}", txid) or transaction.get("root") != _root_identity(root):
        raise RuntimeError("Invalid WSE2 recovery journal; no files restored.")
    records = transaction.get("files", [])
    if not isinstance(records, list) or {r.get("path") for r in records} != set(manifest["files"]) or len(records) != len(manifest["files"]):
        raise RuntimeError("Invalid WSE2 recovery file list.")
    restores = []
    for row in records:
        name = row["path"]
        target = _target(root, name)
        original = row.get("original")
        if original is not None and not re.fullmatch(r"[0-9a-f]{64}", str(original)):
            raise RuntimeError("Invalid WSE2 recovery hash.")
        current = _hash(target) if target.is_file() else None
        # A different post-install user edit is never overwritten during recovery.
        if current not in (original, manifest["files"][name]["sha256"]):
            raise RuntimeError(f"WSE2 recovery found an external edit to {name}. Backup and journal retained.")
        old = None
        if original is not None:
            backup = _target(root, f".lexeditor/wse2/backups/{txid}/files/{name}")
            old = backup.read_bytes()
            if _digest(old) != original:
                raise RuntimeError(f"WSE2 backup failed verification: {name}")
        restores.append((target, current, original, old))
    for target, current, original, old in reversed(restores):
        if current == original:
            continue
        if original is None:
            target.unlink(missing_ok=True)
        else:
            _atomic(target, old)
    folder = _state_root(root)
    prior = transaction.get("previousReceipt")
    if prior is None:
        (folder / "receipt.json").unlink(missing_ok=True)
    elif isinstance(prior, dict):
        _json_write(folder / "receipt.json", prior)
    else:
        raise RuntimeError("Invalid previous WSE2 receipt.")
    (folder / "pending.json").unlink()


def install(game_root: Path, *, package_root: Path = PACKAGE_ROOT, closed_check=None) -> dict:
    """Install shipped bytes offline, with durable backups and recoverable rollback."""
    root = Path(game_root).resolve()
    if not (root / "mb_warband.exe").is_file() or not (root / "Modules").is_dir():
        raise RuntimeError("Locate a complete Warband installation before installing WSE2.")
    manifest, files = package_files(package_root)  # Verify everything BEFORE writes.
    assert_closed = closed_check or _assert_closed
    with _installation_lock(root):
        assert_closed(root)
        folder = _state_root(root)
        journal = folder / "pending.json"
        if journal.exists():
            _rollback(root, _json_read(journal), manifest)
        current = status(root, package_root=package_root)
        if current["installed"]:
            return {**current, "changed": False}
        txid = uuid.uuid4().hex
        previous = _json_read(folder / "receipt.json") if (folder / "receipt.json").exists() else None
        records = []
        for name in files:
            target = _target(root, name)
            if target.exists() and not target.is_file():
                raise RuntimeError(f"WSE2 destination is not a file: {name}")
            old = target.read_bytes() if target.exists() else None
            if old is not None:
                backup = _target(root, f".lexeditor/wse2/backups/{txid}/files/{name}")
                _atomic(backup, old)
            records.append({"path": name, "original": _digest(old) if old is not None else None})
        transaction = {"id": txid, "root": _root_identity(root), "files": records, "previousReceipt": previous}
        _json_write(journal, transaction)
        try:
            assert_closed(root)
            for row in records:
                target = _target(root, row["path"])
                current_hash = _hash(target) if target.is_file() else None
                if current_hash != row["original"]:
                    raise RuntimeError(f"WSE2 destination changed during installation: {row['path']}")
                _atomic(target, files[row["path"]])
            for name, expected in manifest["files"].items():
                if _hash(_target(root, name)) != expected["sha256"]:
                    raise RuntimeError(f"WSE2 readback failed: {name}")
            _json_write(folder / "receipt.json", {"schema": 1, "root": _root_identity(root),
                        "version": PINNED_RELEASE, "packageVersion": PACKAGE_VERSION,
                        "installedAt": datetime.now(timezone.utc).isoformat(), "backup": txid,
                        "packageSha256": PACKAGE_SHA256})
            journal.unlink()
        except Exception as error:
            try:
                _rollback(root, transaction, manifest)
            except Exception as recovery_error:
                raise RuntimeError(f"WSE2 install failed ({error}); recovery requires attention ({recovery_error}). Backups retained in {folder}.") from error
            raise RuntimeError(f"WSE2 install failed; previous files restored: {error}") from error
        return {**status(root, package_root=package_root), "changed": True}


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor-WSE2/1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise RuntimeError("WSE2 release metadata is too large.")
    return json.loads(raw)


def upstream_release(fetch_json=None) -> dict:
    """Latest is information, NEVER an install target or a mutable pin."""
    base = {"runtime": "WSE2", "pinned": PINNED_RELEASE, "packageVersion": PACKAGE_VERSION, "source": REPOSITORY}
    try:
        payload = (fetch_json or _fetch_json)(LATEST_RELEASE_API)
        latest = str(payload.get("tag_name", ""))
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)\.(\d+)", latest)
        if not match or payload.get("draft") or payload.get("prerelease"):
            raise RuntimeError("Upstream did not return a valid stable WSE2 release.")
        return {**base, "latest": latest, "published": str(payload.get("published_at", "")),
                "releaseNotes": REPOSITORY + "/releases/tag/" + latest,
                "behind": tuple(map(int, match.groups())) > (1, 1, 5, 1)}
    except Exception as error:
        return {**base, "error": str(error), "behind": False}
