"""Pinned Memoria installation, verified payloads and recoverable writes.

Only an explicit editor action downloads or runs the publisher's patcher.
The official patcher catches some extraction errors and still returns zero;
verify its declared output files before accepting an installation.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request
from typing import Callable

from .memoria_patcher import inspect_payload, installation_files
from .memoria_recovery import Recovery, atomic_json, digest, install_lock, root_key, verify_install

LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", Path(__file__).resolve().parents[2] / "out")) / "Lexeditor"
STATE_PATH = LOCAL_DATA / "helpers" / "memoria.json"
UPSTREAM_CACHE_PATH = LOCAL_DATA / "helpers" / "memoria-upstream.json"
UPSTREAM_CHECK_SECONDS = 6 * 60 * 60
CACHE_ROOT = LOCAL_DATA / "helpers" / "downloads"
PINNED_RELEASE = "v2025.07.04"
RELEASES_API = "https://api.github.com/repos/Albeoris/Memoria/releases"
RELEASE_API = f"{RELEASES_API}/tags/{PINNED_RELEASE}"
LATEST_RELEASE_API = f"{RELEASES_API}/latest"
REPOSITORY = "https://github.com/Albeoris/Memoria"
ASSET_NAME = "Memoria.Patcher.exe"
MAX_ASSET_BYTES = 120 * 1024 * 1024
MANAGED_RELATIVE = Path("x64") / "FF9_Data" / "Managed"
CONFIG_NAME = "Memoria.ini"
Progress = Callable[[int, int, str], None]
JsonFetcher = Callable[[str], dict]
FileFetcher = Callable[[str, Path, "Progress | None"], None]
_sha256 = digest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_state(path: Path = STATE_PATH) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_state(state: dict, path: Path = STATE_PATH) -> None:
    atomic_json(Path(path), state)


def _state_for_root(root: Path, state_path: Path) -> dict:
    state = _read_state(state_path)
    entries = state.get("installations", {})
    if isinstance(entries, dict) and isinstance(entries.get(root_key(root)), dict):
        return entries[root_key(root)]
    # Migrate the previous single-install record, but never use another root.
    recorded_root = state.get("gameRoot")
    if isinstance(recorded_root, str) and root_key(Path(recorded_root)) == root_key(root):
        return state
    return {}


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise RuntimeError("The Memoria release metadata is too large")
    return json.loads(data.decode("utf-8"))


def _fetch_file(url: str, target: Path, progress: Progress | None = None) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as stream:
        total = int(response.headers.get("Content-Length") or 0)
        if total > MAX_ASSET_BYTES:
            raise RuntimeError("The Memoria download is larger than the allowed limit")
        current = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            current += len(block)
            if current > MAX_ASSET_BYTES:
                raise RuntimeError("The Memoria download is larger than the allowed limit")
            stream.write(block)
            if progress:
                progress(current, total, "Downloading Memoria…")


def release(fetch_json: JsonFetcher = _fetch_json) -> dict:
    """Require the exact approved tag, asset, publisher URL and SHA-256."""
    payload = fetch_json(RELEASE_API)
    if (not isinstance(payload, dict) or payload.get("tag_name") != PINNED_RELEASE
            or payload.get("draft") or payload.get("prerelease")):
        raise RuntimeError("GitHub did not return the pinned stable Memoria release")
    candidates = [asset for asset in payload.get("assets", [])
                  if isinstance(asset, dict) and asset.get("name") == ASSET_NAME]
    if len(candidates) != 1:
        raise RuntimeError("The pinned Memoria release has no unique {ASSET_NAME}")
    asset = candidates[0]
    expected_url = f"{REPOSITORY}/releases/download/{PINNED_RELEASE}/{ASSET_NAME}"
    value = str(asset.get("digest", ""))
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", value):
        raise RuntimeError("The Memoria release does not publish a valid SHA-256 digest")
    if asset.get("browser_download_url") != expected_url:
        raise RuntimeError("The Memoria patcher URL does not belong to the pinned release")
    size = asset.get("size")
    if size is not None and (type(size) is not int or not 0 < size <= MAX_ASSET_BYTES):
        raise RuntimeError("The Memoria patcher asset size is invalid")
    return {"version": PINNED_RELEASE, "published": str(payload.get("published_at", "")),
            "name": ASSET_NAME, "url": expected_url, "sha256": value[7:].casefold(),
            "source": REPOSITORY}


def upstream_release(fetch_json: JsonFetcher = _fetch_json, *,
                     cache_path: Path = UPSTREAM_CACHE_PATH,
                     max_age_seconds: int = UPSTREAM_CHECK_SECONDS,
                     force: bool = False, now: Callable[[], datetime] | None = None) -> dict:
    """Report newest upstream release with a persistent six-hour network cadence.

    The shell already caches within one process. This cache prevents every Lexeditor
    restart from hitting GitHub as well, while `force=True` remains available for an
    explicit developer refresh. Nothing here installs or changes the pinned release.
    """
    clock = now or (lambda: datetime.now(timezone.utc))
    current = clock()
    cached = _read_state(cache_path)
    checked = str(cached.get("checkedAt", ""))
    if not force and checked:
        try:
            age = (current - datetime.fromisoformat(checked)).total_seconds()
        except ValueError:
            age = max_age_seconds + 1
        if 0 <= age < max_age_seconds and isinstance(cached.get("result"), dict):
            return {**cached["result"], "cached": True, "checkedAt": checked}
    try:
        payload = fetch_json(LATEST_RELEASE_API)
        if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
            raise RuntimeError("GitHub did not return a stable Memoria release")
        latest = str(payload.get("tag_name", "")).strip()
        if not latest:
            raise RuntimeError("GitHub returned a Memoria release without a tag")
        result = {"runtime": "Memoria", "pinned": PINNED_RELEASE, "latest": latest,
                  "published": str(payload.get("published_at", "")),
                  "behind": latest != PINNED_RELEASE, "source": REPOSITORY}
        checked_at = current.isoformat(timespec="seconds")
        atomic_json(Path(cache_path), {"checkedAt": checked_at, "result": result})
        return {**result, "cached": False, "checkedAt": checked_at}
    except Exception as error:
        previous = cached.get("result") if isinstance(cached.get("result"), dict) else {}
        return {"runtime": "Memoria", "pinned": PINNED_RELEASE, **previous,
                "error": str(error), "cached": bool(previous), "checkedAt": checked}


def _game_running(game_root: Path) -> bool:
    """Fail closed when the process list is unavailable, including the launcher."""
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                            text=True, timeout=10, check=False,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise RuntimeError("Windows could not check whether Final Fantasy 9 is running")
        rows = list(csv.reader(io.StringIO(result.stdout)))
        if not rows or any(len(row) < 2 or not row[1].isdigit() for row in rows):
            raise RuntimeError("Windows returned an unreadable process list; Memoria will not modify the game")
        names = {row[0].casefold() for row in rows}
        return bool(names & {"ff9.exe", "ff9_launcher.exe", "ff9_launcher.fix", "memoria.patcher.exe"}) or any(
            name.startswith("memoria-") and name.endswith(".exe") for name in names)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("Cannot check running processes. Memoria will not modify the game.") from error



def _binary_version(path: Path) -> str:
    """Read the assembly's Windows version resource, not an arbitrary INI key."""
    if os.name != "nt" or not path.is_file():
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        library = ctypes.WinDLL("version", use_last_error=True)
        library.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        library.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        library.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        library.GetFileVersionInfoW.restype = wintypes.BOOL
        library.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
        library.VerQueryValueW.restype = wintypes.BOOL
        handle = wintypes.DWORD()
        size = library.GetFileVersionInfoSizeW(str(path), ctypes.byref(handle))
        if not size or size > 1024 * 1024:
            return ""
        buffer = ctypes.create_string_buffer(size)
        if not library.GetFileVersionInfoW(str(path), 0, size, buffer):
            return ""
        pointer, length = ctypes.c_void_p(), wintypes.UINT()
        if not library.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)) or length.value < 52:
            return ""
        fixed = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))
        if fixed[0] != 0xFEEF04BD:
            return ""
        numbers = (fixed[2] >> 16, fixed[2] & 0xffff, fixed[