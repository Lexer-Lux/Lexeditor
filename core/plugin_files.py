"""File and download helpers every plugin was writing for itself.

Four plugins had their own `_atomic_write`, two their own `_fetch_file`, each a
copy of the same twenty lines with a different message in the errors. This is
that code once, with the message passed in.
"""
from __future__ import annotations

import os
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Callable

Progress = Callable[[int, int, str], None]
USER_AGENT = "Lexeditor/1.0"


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
