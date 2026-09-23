"""Persistent, rate-limited upstream Memoria release checks."""
from __future__ import annotations
from datetime import datetime, timezone
import json, os
from pathlib import Path
from typing import Callable
from . import memoria_manager as manager
from .memoria_recovery import atomic_json

LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", Path(__file__).resolve().parents[2] / "out")) / "Lexeditor"
UPSTREAM_CACHE_PATH = LOCAL_DATA / "helpers" / "memoria-upstream.json"
UPSTREAM_CHECK_SECONDS = 6 * 60 * 60

def _read(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}

def upstream_release(fetch_json: Callable[[str], dict] = manager._fetch_json, *, cache_path: Path = UPSTREAM_CACHE_PATH, max_age_seconds: int = UPSTREAM_CHECK_SECONDS, force: bool = False, now: Callable[[], datetime] | None = None) -> dict:
    clock = now or (lambda: datetime.now(timezone.utc))
    current = clock()
    if current.tzinfo is None: current = current.replace(tzinfo=timezone.utc)
    cache = _read(cache_path)
    checked = str(cache.get("checkedAt", ""))
    if checked and not force:
        try: age = (current - datetime.fromisoformat(checked)).total_seconds()
        except ValueError: age = max_age_seconds + 1
        result = cache.get("result")
        if 0 <= age < max_age_seconds and isinstance(result, dict):
            return {**result, "cached": True, "checkedAt": checked}
    try:
        payload = fetch_json(manager.LATEST_RELEASE_API)
        if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
            raise RuntimeError("GitHub did not return a stable Memoria release")
        latest = str(payload.get("tag_name", "")).strip()
        if not latest: raise RuntimeError("GitHub returned a Memoria release without a tag")
        result = {"runtime":"Memoria","pinned":manager.PINNED_RELEASE,"latest":latest,"published":str(payload.get("published_at","")),"behind":latest != manager.PINNED_RELEASE,"source":manager.REPOSITORY}
        checked_at = current.isoformat(timespec="seconds")
        atomic_json(Path(cache_path), {"checkedAt": checked_at, "result": result})
        return {**result, "cached": False, "checkedAt": checked_at}
    except Exception as error:
        previous = cache.get("result") if isinstance(cache.get("result"), dict) else {}
        return {"runtime":"Memoria","pinned":manager.PINNED_RELEASE,**previous,"error":str(error),"cached":bool(previous),"checkedAt":checked}

def install() -> None:
    manager.UPSTREAM_CACHE_PATH = UPSTREAM_CACHE_PATH
    manager.UPSTREAM_CHECK_SECONDS = UPSTREAM_CHECK_SECONDS
    manager.upstream_release = upstream_release
