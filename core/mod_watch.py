"""Shared filesystem watcher for mod libraries: which top-level mod folders changed.

One watcher per canonical library root, shared through a bounded registry.
The Save rebuild badge polls it instead of re-hashing the whole library or
rebuilding on every request: only changed folder names and a revision cross
the wire, and the expensive staleness check runs only when the revision moves.

Windows watches with ReadDirectoryChangesW on a daemon thread; other systems
fall back to throttled metadata polling (stat only, never byte hashing).
Worker failures are reported as status, never raised. No third-party
dependency (no watchdog).
"""
from __future__ import annotations

import atexit
from collections import OrderedDict
import ctypes
import os
import struct
import threading
import time

MAX_WATCHERS = 4
MAX_TRACKED_MODS = 128
COALESCE_SEC = 0.2
RETRY_SEC = 2.0
POLL_SEC = 1.0
MAX_STAT_ENTRIES = 4096

_IGNORE_DIRS = frozenset({".git", "__pycache__"})
_IGNORE_SUFFIXES = (".tmp", ".temp", ".swp", ".swx", "~")

if os.name == "nt":
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # noqa: F841
    from ctypes import wintypes

    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.HANDLE]
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.ReadDirectoryChangesW.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                           wintypes.BOOL, wintypes.DWORD, wintypes.LPDWORD,
                                           wintypes.LPVOID, wintypes.LPVOID]
    _k32.ReadDirectoryChangesW.restype = wintypes.BOOL
    _k32.CancelIoEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    _k32.CancelIoEx.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL
    class _Overlapped(ctypes.Structure):
        _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                    ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD), ('hEvent', wintypes.HANDLE)]
    _k32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    _k32.CreateEventW.restype = wintypes.HANDLE
    _k32.ResetEvent.argtypes = [wintypes.HANDLE]
    _k32.ResetEvent.restype = wintypes.BOOL
    _k32.GetOverlappedResult.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Overlapped), wintypes.LPDWORD, wintypes.BOOL]
    _k32.GetOverlappedResult.restype = wintypes.BOOL
    _INVALID_HANDLE = ctypes.c_void_p(-1).value
    _ERROR_NOTIFY_ENUM_DIR = 1022
    _ERROR_OPERATION_ABORTED = 995


def _canonical(root) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(root)))


class ModWatcher:
    """Changed top-level folders under one library root, with a revision.

    snapshot(since) is non-destructive, so any number of polling clients can
    share one watcher. notify() is the test hook and the exact entry point the
    worker uses for real events.
    """

    def __init__(self, root: str):
        self.root = root
        self._lock = threading.Lock()
        self._revision = 0
        self._changed: dict[str, int] = {}
        self._status: str | None = None
        self._last_bump = 0.0
        self._pending = set()
        self._stop = threading.Event()
        self._closed = False
        self._needs_resync = False
        self._handle_lock = threading.Lock()
        self._handle = None
        target = self._run_windows if os.name == "nt" else self._run_poll
        self._thread = threading.Thread(target=target, name="lexeditor-modwatch",
                                        daemon=True)
        self._thread.start()

    @property
    def closed(self) -> bool:
        return self._closed

    def notify(self, relative) -> None:
        """Record a change at a root-relative path. Ignores version-control,
        bytecode-cache and temporary paths; anything else marks its top-level
        folder changed."""
        text = relative if isinstance(relative, str) else os.fspath(relative)
        parts = [p for p in text.replace("\\", "/").split("/") if p not in ("", ".")]
        if not parts:
            return
        if any(p in _IGNORE_DIRS for p in parts):
            return
        leaf = parts[-1].lower()
        if leaf.startswith("~") or leaf.endswith(_IGNORE_SUFFIXES):
            return
        self._record_many((parts[0],))

    def snapshot(self, since=0) -> dict:
        """{'revision', 'changed', 'status'} without consuming anything."""
        try:
            since = max(0, int(since))
        except (TypeError, ValueError):
            since = 0
        with self._lock:
            if self._pending and time.monotonic() - self._last_bump >= COALESCE_SEC:
                self._revision += 1
                for name in self._pending:
                    self._changed[name] = self._revision
                self._pending.clear()
                while len(self._changed) > MAX_TRACKED_MODS:
                    del self._changed[min(self._changed, key=self._changed.get)]
            return {"revision": self._revision,
                    "changed": sorted(name for name, rev in self._changed.items()
                                      if rev > since),
                    "status": self._status}

    def close(self) -> None:
        """Stop the worker, unblock its read, and release the handle exactly once."""
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        if os.name == "nt":
            with self._handle_lock:
                handle = self._handle
            if handle is not None:
                try:
                    _k32.CancelIoEx(handle, None)
                except Exception:
                    pass
        self._thread.join(timeout=5.0)
        if os.name == "nt":
            with self._handle_lock:
                handle = self._handle
                self._handle = None
            if handle is not None:
                try:
                    _k32.CloseHandle(handle)
                except Exception:
                    pass

    def _set_status(self, message: str | None) -> None:
        with self._lock:
            self._status = message

    def _record_many(self, folders) -> None:
        """One revision bump per burst; the changed set stays bounded."""
        now = time.monotonic()
        with self._lock:
            self._last_bump = now
            self._pending.update(folders)
            if len(self._pending) > MAX_TRACKED_MODS:
                self._pending = {'*'}

    def _mark_all(self) -> None:
        """Overflow or a (re)appearing root: every top-level folder changed."""
        try:
            with os.scandir(self.root) as entries:
                names = [entry.name for _, entry in zip(range(512), entries)
                         if entry.name not in _IGNORE_DIRS]
        except OSError:
            names = []
        if names:
            self._record_many(names)
        else:
            with self._lock:
                self._last_bump = time.monotonic()
                self._pending.add('*')

    # Windows worker: one directory handle, recursive, blocking reads.

    def _open_handle(self):
        handle = _k32.CreateFileW(self.root, 0x0001, 0x0001 | 0x0002 | 0x0004,
                                  None, 3, 0x42000000, None)
        if handle is None or handle == _INVALID_HANDLE:
            error = ctypes.get_last_error()
            if error in (2, 3):
                self._set_status("mod library not found; watching for it")
            else:
                self._set_status(f"cannot watch mod library ({error})")
            return None
        return handle

    def _close_owned(self, handle) -> None:
        with self._handle_lock:
            if self._handle != handle:
                return
            self._handle = None
        try:
            _k32.CloseHandle(handle)
        except Exception:
            pass

    def _parse_buffer(self, raw: bytes) -> None:
        """Walk FILE_NOTIFY_INFORMATION entries with bounds checks; any event
        kind (added, removed, modified, renamed) marks its path changed."""
        offset = 0
        size = len(raw)
        for _ in range(4096):
            if offset + 12 > size:
                break
            nxt, _action, namelen = struct.unpack_from("<III", raw, offset)
            end = offset + 12 + namelen
            if namelen % 2 or end > size:
                break
            try:
                name = raw[offset + 12:end].decode("utf-16-le")
            except UnicodeError:
                name = ""
            if name:
                self.notify(name)
            if nxt == 0 or offset + nxt >= size or nxt < 12:
                break
            offset += nxt

    def _run_windows(self) -> None:
        buf = ctypes.create_string_buffer(65536)
        done = wintypes.DWORD()
        handle = None
        event = _k32.CreateEventW(None, True, False, None)
        if not event:
            self._set_status('Could not create the directory notification event')
            return
        overlap = _Overlapped()
        overlap.hEvent = event
        try:
            while not self._stop.is_set():
                if handle is None:
                    if not os.path.isdir(self.root):
                        self._set_status("mod library not found; watching for it")
                        self._needs_resync = True
                        if self._stop.wait(RETRY_SEC):
                            break
                        continue
                    handle = self._open_handle()
                    if handle is None:
                        self._needs_resync = True
                        if self._stop.wait(RETRY_SEC):
                            break
                        continue
                    with self._handle_lock:
                        self._handle = handle
                    self._needs_resync = False
                    self._mark_all()
                    self._set_status(None)
                _k32.ResetEvent(event)
                with self._handle_lock:
                    if self._stop.is_set():
                        break
                    ok = _k32.ReadDirectoryChangesW(handle, buf, len(buf), True,
                                                   0x01 | 0x02 | 0x08 | 0x10,
                                                   None, ctypes.byref(overlap), None)
                if ok or ctypes.get_last_error() == 997:
                    ok = _k32.GetOverlappedResult(handle, ctypes.byref(overlap), ctypes.byref(done), True)
                if self._stop.is_set():
                    break
                if ok:
                    if done.value:
                        self._parse_buffer(bytes(buf.raw[:done.value]))
                    else:
                        self._mark_all()
                    continue
                error = ctypes.get_last_error()
                if error == _ERROR_NOTIFY_ENUM_DIR:
                    self._mark_all()
                    continue
                if error == _ERROR_OPERATION_ABORTED:
                    break
                self._set_status(f"directory watch failed ({error}); retrying")
                self._close_owned(handle)
                handle = None
                self._needs_resync = True
                if self._stop.wait(1.0):
                    break
        finally:
            if handle is not None:
                self._close_owned(handle)
            _k32.CloseHandle(event)

    # Fallback worker: throttled stat-only polling, never byte hashing.

    def _stat_tree(self):
        found: dict[str, tuple] = {}
        truncated = False
        stack = [""]
        seen = set()
        while stack and len(found) < MAX_STAT_ENTRIES:
            rel = stack.pop()
            absdir = self.root if not rel else os.path.join(self.root, rel)
            try:
                with os.scandir(absdir) as entries:
                    listed = list(entries)
            except OSError:
                continue
            for entry in listed:
                if len(found) >= MAX_STAT_ENTRIES:
                    truncated = True
                    break
                if entry.name in _IGNORE_DIRS or entry.is_symlink():
                    continue
                child = entry.name if not rel else rel + "/" + entry.name
                try:
                    if entry.is_dir(follow_symlinks=False):
                        info = entry.stat(follow_symlinks=False)
                        key = (info.st_dev, info.st_ino)
                        if key in seen:
                            continue
                        seen.add(key)
                        found[child] = ("d", info.st_mtime_ns)
                        stack.append(child)
                    else:
                        info = entry.stat(follow_symlinks=False)
                        found[child] = ("f", info.st_size, info.st_mtime_ns)
                except OSError:
                    continue
        return found, truncated

    def _run_poll(self) -> None:
        known: dict[str, tuple] = {}
        baselined = False
        saw_missing = False
        while not self._stop.wait(POLL_SEC):
            if not os.path.isdir(self.root):
                known = {}
                saw_missing = True
                self._set_status("mod library not found; watching for it")
                continue
            found, truncated = self._stat_tree()
            if truncated:
                self._set_status("mod library too large; reporting all changed")
                self._mark_all()
                known = found
                baselined = True
                saw_missing = False
                continue
            if saw_missing:
                saw_missing = False
                baselined = True
                known = found
                self._set_status(None)
                self._mark_all()
                continue
            if not baselined:
                baselined = True
                known = found
                self._set_status(None)
                continue
            self._set_status(None)
            for rel, meta in found.items():
                if known.get(rel) != meta:
                    self.notify(rel)
            for rel in known:
                if rel not in found:
                    self.notify(rel)
            known = found


_registry_lock = threading.Lock()
_registry: OrderedDict[str, ModWatcher] = OrderedDict()


def get(root) -> ModWatcher:
    """The shared watcher for a library root, retiring the least recently used
    watcher past four roots."""
    key = _canonical(root)
    retire = []
    with _registry_lock:
        watcher = _registry.get(key)
        if watcher is None or watcher.closed:
            watcher = ModWatcher(os.path.abspath(os.fspath(root)))
            _registry[key] = watcher
        else:
            _registry.move_to_end(key)
        while len(_registry) > MAX_WATCHERS:
            oldest = next(iter(_registry))
            if oldest == key:
                break
            retire.append(_registry.pop(oldest))
    for victim in retire:
        try:
            victim.close()
        except Exception:
            pass
    return watcher


def snapshot(root, since=0) -> dict:
    """Non-destructive {'revision', 'changed', 'status'} for a library root."""
    return get(root).snapshot(since)


def close_all() -> None:
    """Release every watcher. Runs at exit; daemons back it up."""
    with _registry_lock:
        watchers = list(_registry.values())
        _registry.clear()
    for watcher in watchers:
        try:
            watcher.close()
        except Exception:
            pass


atexit.register(close_all)
