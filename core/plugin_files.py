"""File and download helpers every plugin was writing for itself.

Four plugins had their own `_atomic_write`, two their own `_fetch_file`, each a
copy of the same twenty lines with a different message in the errors. This is
that code once, with the message passed in.
"""
from __future__ import annotations

import os
import hashlib
import stat
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Callable

Progress = Callable[[int, int, str], None]
USER_AGENT = "Lexeditor/1.0"


def is_link(path: Path) -> bool:
    """Recognize symlinks and Windows reparse points on supported Python versions."""
    try:
        info = Path(path).lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def atomic_write(path: Path, data: bytes) -> None:
    """Write the whole file or none of it.

    A half-written game file is worse than no file: the game loads it, and the
    player has no way to tell what happened. Write beside the target, flush to
    the disk, then replace in one step.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        # A file extracted read-only (mod zips arrive that way) refuses
        # the replace on every attempt: no retry window helps. The caller
        # asked to overwrite the content, so the file must be writable.
        try:
            if not os.access(path, os.W_OK):
                os.chmod(path, 0o666)
        except OSError:
            pass
    handle, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        deadline = time.monotonic() + 2
        while True:
            try:
                os.replace(name, path)
                break
            except PermissionError as error:
                # Windows lets antivirus, search indexing and cloud sync hold
                # a file briefly after it changes; the replace then fails
                # with access denied even though nothing is wrong. Wait it
                # out briefly, then say what to close instead of the bare
                # system error.
                if time.monotonic() >= deadline:
                    where = path.name if path.parent == Path(".") else path.parent.name + "/" + path.name
                    raise PermissionError(
                        f"Could not write {where}: access is denied. Close any program "
                        "holding the file (the game, an editor, a sync tool) and check "
                        "the file is not read-only.") from error
                time.sleep(0.1)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_write_group(changes: dict[Path, bytes], expected: dict[Path, str | None], *, limit=512*1024*1024) -> None:
    """Commit related project files, restoring caught failures as one group.

    expected holds each file's hash when opened (None means absent). Both
    snapshots and new contents share the memory bound. External changes are
    refused before writing and preserved if found while rolling back.
    """
    if set(changes) != set(expected) or any(not isinstance(data, bytes) for data in changes.values()):
        raise ValueError('A grouped save needs one expected hash per output file')
    if len({Path(path).resolve() for path in changes}) != len(changes):
        raise ValueError('A grouped save cannot write the same path twice')
    total = sum(len(data) for data in changes.values())
    if total > limit:
        raise ValueError('The grouped save exceeds its memory limit')

    def snapshot(path):
        if is_link(path):
            raise ValueError(f'{path.name}: a grouped save cannot follow a link')
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return None
        if size > limit:
            raise ValueError(f'{path.name} is too large to save safely')
        with path.open('rb') as stream:
            data = stream.read(min(size+1, limit+1))
            if len(data) > limit or stream.read(1):
                raise ValueError(f'{path.name} grew during the save')
        return data

    def digest(data):
        return hashlib.sha256(data).hexdigest() if data is not None else None

    originals = {}
    for path in changes:
        before = snapshot(path)
        if digest(before) != expected[path]:
            raise ValueError(f'{path.name} changed outside Lexeditor; unsaved edits were kept')
        total += len(before or b'')
        if total > limit:
            raise ValueError('The grouped save exceeds its memory limit')
        originals[path] = before
    touched = []
    try:
        for path, data in changes.items():
            if digest(snapshot(path)) != expected[path]:
                raise ValueError(f'{path.name} changed during the save; external bytes were kept')
            touched.append(path)
            atomic_write(path, data)
    except Exception as error:
        failures = []
        for path in reversed(touched):
            try:
                current = digest(snapshot(path))
                if current == expected[path]:
                    continue
                if current != digest(changes[path]):
                    raise ValueError('changed externally; external bytes were kept')
                if originals[path] is None:
                    path.unlink()
                else:
                    atomic_write(path, originals[path])
            except Exception as rollback_error:
                failures.append(f'{path.name}: {rollback_error}')
        if failures:
            raise RuntimeError(f'Save failed: {error}; could not restore ' + '; '.join(failures)) from error
        raise


def fetch_file(url: str, target: Path, *, limit: int, progress: Progress | None = None,
               label: str = "Downloading…", too_large: str = "The download is larger than the allowed limit") -> None:
    """Download to a file, refusing anything past `limit` bytes.

    The limit is checked against the declared length and again as the bytes
    arrive, because a server may declare anything it likes.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response, Path(target).open("wb") as stream:
        total = int(response.headers.get("Content-Length") or 0)
        if total > limit:
            raise RuntimeError(too_large)
        current = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            current += len(block)
            if current > limit:
                raise RuntimeError(too_large)
            stream.write(block)
            if progress:
                progress(current, total, label)
