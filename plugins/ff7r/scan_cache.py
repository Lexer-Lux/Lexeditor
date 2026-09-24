"""Single-flight cache for FF7R installed-input scans.

Every Tweaks group load used to re-scan the installed game from scratch:
each probe listed every PAK through a repak subprocess, re-read the installed
executable, or re-parsed all text/DataObject packages. Opening Tweaks fired
seventeen of those scans at once, which peaked past 5 GB and starved the host
until the whole program looked frozen.

The scanned inputs are installed files, so a scan result is a pure function of
the install's identity plus the scan parameters. Callers cache results here
keyed by exactly that. Concurrent requests for the same scan share one
computation instead of stampeding. The cache lives only in this server process:
installed files do not change underneath a running editor, and a restart simply
scans again. Failures are never cached.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections.abc import Callable, Hashable
from typing import TypeVar

T = TypeVar("T")

_guard = threading.Lock()
_results: dict[Hashable, object] = {}
_in_flight: dict[Hashable, threading.Event] = {}
_errors: dict[Hashable, BaseException] = {}


def cached(key: Hashable, compute: Callable[[], T]) -> T:
    """Return the cached result for key, computing it once when missing."""
    with _guard:
        if key in _results:
            return copy.deepcopy(_results[key])  # type: ignore[return-value]
        event = _in_flight.get(key)
        if event is None:
            event = threading.Event()
            _in_flight[key] = event
            owner = True
        else:
            owner = False
    if not owner:
        event.wait()
        with _guard:
            if key in _results:
                return copy.deepcopy(_results[key])  # type: ignore[return-value]
            raise _errors[key]
    try:
        value = compute()
    except BaseException as error:
        with _guard:
            del _in_flight[key]
            _errors[key] = error
        event.set()
        raise
    with _guard:
        _results[key] = value
        _errors.pop(key, None)
        del _in_flight[key]
    event.set()
    return copy.deepcopy(value)


def clear() -> None:
    """Drop every cached scan result. Tests only; call while idle."""
    with _guard:
        _results.clear()
        _errors.clear()


def index_fingerprint(index: dict, *, text: bool = False) -> str:
    """Hash the index rows a corpus scan consumes.

    The signature alone is only a label: fixture indexes reuse one signature
    for different contents. The rows (with their archive/fixture references)
    are the scan's actual inputs, so they join the key.
    """
    if text:
        rows = list(index.get("textAssets", []))
    else:
        rows = [row for row in index.get("assets", []) if not row.get("synthetic")]
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
